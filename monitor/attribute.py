"""
Variance attribution: splits each line's forecast miss into the drivers behind it.

For a line in a given week, the variance (actual minus forecast) is decomposed by
swapping forecast drivers for actual ones one at a time, in a fixed order. The
components always sum exactly to the variance. Each component also gets the
amount of noise it normally carries, so the detector can tell drift from noise.

  dtc_payouts          volume, refunds (with the SKU behind it), fees, chargebacks, timing
  marketplace_payouts  volume, fees, reserve
  wholesale_receipts   volume, late (receivables paid after their due week; catch-up is timing)
  bill lines           timing, volume, price, fx (bill by bill)
  ad_spend_accrual     overspend by platform (card activity, before it reaches the bank)
  card_autopay         overspend (ads), other card spend
  other_opex           one_off (payments to counterparties the plan did not have), noise
  sales_tax            volume
  payroll, fixed, debt unexplained (no driver detail)

The monitor sees only two books: the forecast and the actuals as reported by the
brand's own systems. It never sees how the actuals were generated.

Built by Avinash Rayudu.
"""
from __future__ import annotations

import numpy as np

from world.engine import N_WEEKS, autopay_weeks

# variability the monitor assumes for drivers the onboarded ledger cannot measure
DEFAULT_CV = {"refunds": 0.15, "chargebacks": 0.35, "other_card": 0.20, "other_opex": 0.40, "payroll": 0.01,
              "fx_weekly": 0.005}

CAUSE_OF = {"volume": "volume", "refunds": "refunds", "fees": "fees", "chargebacks": "chargebacks",
            "timing": "timing", "reserve": "reserve", "late": "late_receivable", "overspend": "overspend",
            "price": "price", "fx": "fx", "one_off": "one_off", "other": "unexplained", "noise": "unexplained",
            "unexplained": "unexplained", "direct_debit": "overspend"}


def _dtc_payouts(G, R, f, C, lag, net_pre, lag_pre):
    net = G - R - f * G - C
    out = np.zeros(len(G))
    pn, pl = net_pre, lag_pre
    for w in range(len(G)):
        out[w] = (1 - lag[w]) * net[w] + pl * pn
        pn, pl = net[w], lag[w]
    return out


def dtc_components(fc, act):
    cfg, F, A = fc.cfg, fc.drivers, act.drivers
    pre = F["dtc_gross_pre"] * (1 - cfg["refund_rate"] - cfg["fee_rate"] - cfg["chargeback_rate"])
    lag0 = cfg["payout_lag_share"]
    Rf = sum(F["dtc_refunds_by_sku"].values())
    Ra = sum(A["dtc_refunds_by_sku"].values())
    ratio = np.divide(A["dtc_gross"], F["dtc_gross"], out=np.ones_like(F["dtc_gross"]), where=F["dtc_gross"] > 0)
    steps = [
        ("base", F["dtc_gross"], Rf, F["dtc_fee_rate"], F["dtc_chargebacks"], F["dtc_lag"]),
        ("volume", A["dtc_gross"], Rf * ratio, F["dtc_fee_rate"], F["dtc_chargebacks"] * ratio, F["dtc_lag"]),
        ("refunds", A["dtc_gross"], Ra, F["dtc_fee_rate"], F["dtc_chargebacks"] * ratio, F["dtc_lag"]),
        ("fees", A["dtc_gross"], Ra, A["dtc_fee_rate"], F["dtc_chargebacks"] * ratio, F["dtc_lag"]),
        ("chargebacks", A["dtc_gross"], Ra, A["dtc_fee_rate"], A["dtc_chargebacks"], F["dtc_lag"]),
        ("timing", A["dtc_gross"], Ra, A["dtc_fee_rate"], A["dtc_chargebacks"], A["dtc_lag"]),
    ]
    vals = [_dtc_payouts(g, r, f, c, l, pre, lag0) for _, g, r, f, c, l in steps]
    comps = {steps[k][0]: vals[k] - vals[k - 1] for k in range(1, len(steps))}
    cv = cfg["noise"]["dtc"]
    # refund noise enters the week's payout mostly through that week's refunds
    spread = np.sqrt((1 - lag0) ** 2 + lag0 ** 2)
    sig = {"volume": cv * np.abs(fc.lines["dtc_payouts"]), "refunds": DEFAULT_CV["refunds"] * Rf * spread,
           "fees": np.zeros_like(Rf), "chargebacks": DEFAULT_CV["chargebacks"] * F["dtc_chargebacks"],
           "timing": np.zeros_like(Rf)}
    # which SKU drives the refund miss
    sku_delta = {k: A["dtc_refunds_by_sku"][k] - F["dtc_refunds_by_sku"][k] * ratio for k in F["dtc_refunds_by_sku"]}
    detail = {"refund_sku_delta": sku_delta, "refund_ratio": np.divide(Ra, Rf * ratio, out=np.ones_like(Ra),
                                                                        where=Rf > 0)}
    return comps, sig, detail


def amazon_components(fc, act):
    cfg, F, A = fc.cfg, fc.drivers, act.drivers
    W = len(F["amz_sales"])
    comps = {k: np.zeros(W) for k in ("volume", "fees", "reserve")}
    if cfg.get("amz_weekly_sales", 0) <= 0:
        return comps, {k: np.zeros(W) for k in comps}, {}
    sf = np.concatenate([F["amz_sales_pre"], F["amz_sales"]])
    sa = np.concatenate([A["amz_sales_pre"], A["amz_sales"]])
    ff = np.concatenate([np.full(2, cfg["amz_fee_rate"]), F["amz_fee_rate"]])
    fa = np.concatenate([np.full(2, cfg["amz_fee_rate"]), A["amz_fee_rate"]])
    sig = {k: np.zeros(W) for k in comps}
    for w in range(0, W, 2):
        s_f, s_a, f_f, f_a = sf[w:w + 2], sa[w:w + 2], ff[w:w + 2], fa[w:w + 2]
        comps["volume"][w] = float(np.sum((s_a - s_f) * (1 - f_f)))
        comps["fees"][w] = float(np.sum(s_a * (f_f - f_a)))
        comps["reserve"][w] = (A["amz_reserve_release"][w] - A["amz_reserve_hold"][w]) - \
                              (F["amz_reserve_release"][w] - F["amz_reserve_hold"][w])
        sig["volume"][w] = cfg["noise"]["amazon"] * abs(fc.lines["marketplace_payouts"][w])
    return comps, sig, {}


def wholesale_components(fc, act):
    cfg, F, A = fc.cfg, fc.drivers, act.drivers
    W = len(fc.lines["wholesale_receipts"])
    vol, late = np.zeros(W), np.zeros(W)
    by_retailer = {}
    for r in cfg.get("retailers", []):
        n = r["name"]
        inv_f, inv_a, dl = F["wh_invoices"][n], A["wh_invoices"][n], A["wh_delay_weeks"][n]
        rl = np.zeros(W)
        for i in range(len(inv_f)):
            due = (i - 12) + r["terms_weeks"]
            paid = due + int(dl[i])
            if 0 <= due < W:
                vol[due] += inv_a[i] - inv_f[i]
                late[due] -= inv_a[i]
                rl[due] -= inv_a[i]
            if 0 <= paid < W:
                late[paid] += inv_a[i]
                rl[paid] += inv_a[i]
        by_retailer[n] = rl
    sig = {"volume": cfg["noise"]["wholesale"] * np.abs(fc.lines["wholesale_receipts"]), "late": np.zeros(W)}
    return {"volume": vol, "late": late}, sig, {"late_by_retailer": by_retailer}


def bill_components(fc, act, line):
    cfg = fc.cfg
    W = len(fc.lines[line])
    comps = {k: np.zeros(W) for k in ("timing", "volume", "price", "fx")}
    bf = {b["id"]: b for b in fc.bills if b["line"] == line}
    ba = {b["id"]: b for b in act.bills if b["line"] == line}
    per_bill = {}
    for bid in set(bf) | set(ba):
        f, a = bf.get(bid), ba.get(bid)
        if f is None or a is None:
            continue
        fx_f = f["fx"]
        steps = []
        steps.append((f["pay_week"], f["amount"], fx_f))                                    # forecast
        steps.append((a["pay_week"], f["amount"], fx_f))                                    # timing
        exp_amt = f["amount"] * (a["basis"] / f["basis"]) if f.get("basis") else f["amount"]
        steps.append((a["pay_week"], exp_amt, fx_f))                                        # volume
        steps.append((a["pay_week"], a["amount"], fx_f))                                    # price
        steps.append((a["pay_week"], a["amount"], a["fx"]))                                 # fx
        def cash(wk, amt, fx):
            v = np.zeros(W)
            if 0 <= wk < W:
                v[wk] = -amt * fx
            return v
        vals = [cash(*s) for s in steps]
        for k, name in enumerate(("timing", "volume", "price", "fx"), start=1):
            comps[name] += vals[k] - vals[k - 1]
        per_bill[bid] = {"vendor": a["vendor"], "forecast_week": f["pay_week"], "actual_week": a["pay_week"],
                         "forecast_cash": -f["amount"] * fx_f, "actual_cash": -a["amount"] * a["fx"]}
    sig = {k: np.zeros(W) for k in comps}
    cv = cfg["noise"]["dtc"]
    for b in bf.values():
        w = b["pay_week"]
        if 0 <= w < W:
            if b.get("basis"):        # bills priced off last month's sales move with sales
                sig["volume"][w] += 0.6 * cv * b["amount"] * b["fx"]
            if b["currency"] != cfg["currency"]:
                sig["fx"][w] += DEFAULT_CV["fx_weekly"] * np.sqrt(max(w, 1)) * b["amount"] * b["fx"]
    return comps, sig, {"bills": per_bill}


def ads_components(fc, act):
    F, A = fc.drivers["ad_by_platform"], act.drivers["ad_by_platform"]
    direct = {"meta"} if fc.cfg.get("meta_direct_debit") else set()     # watched on ad_direct instead
    F = {p: v for p, v in F.items() if p not in direct}
    comps = {f"overspend:{p}": -(A[p] - F[p]) for p in F}
    sig = {f"overspend:{p}": fc.cfg["noise"]["ads"] * F[p] for p in F}
    return comps, sig, {}


def card_components(fc, act):
    W = len(fc.lines["card_autopay"])
    comps = {"overspend": np.zeros(W), "other": np.zeros(W)}
    sig = {"overspend": np.zeros(W), "other": np.zeros(W)}
    for k, ym in autopay_weeks():
        if 0 <= k < W:
            comps["overspend"][k] = -(act.drivers["_card_stmt_ads"].get(ym, 0) - fc.drivers["_card_stmt_ads"].get(ym, 0))
            comps["other"][k] = -(act.drivers["_card_stmt_other"].get(ym, 0) -
                                  fc.drivers["_card_stmt_other"].get(ym, 0))
            sig["overspend"][k] = fc.cfg["noise"]["ads"] / 2 * fc.drivers["_card_stmt_ads"].get(ym, 0)
            sig["other"][k] = DEFAULT_CV["other_card"] * fc.drivers["_card_stmt_other"].get(ym, 0)
    return comps, sig, {}


def opex_components(fc, act):
    W = len(fc.lines["other_opex"])
    one = np.zeros(W)
    who = {}
    planned = {cp for _, cp, _ in fc.drivers["one_offs"]}
    for (w, cp, amt) in act.drivers["one_offs"]:
        if cp not in planned and 0 <= w < W:
            one[w] -= amt
            who.setdefault(w, []).append((cp, amt))
    total = act.lines["other_opex"] - fc.lines["other_opex"]
    comps = {"one_off": one, "noise": total - one}
    sig = {"one_off": np.zeros(W), "noise": DEFAULT_CV["other_opex"] * np.abs(fc.lines["other_opex"])}
    return comps, sig, {"one_off_payees": who}


def simple_components(fc, act, line, cv):
    v = act.lines[line] - fc.lines[line]
    return {"unexplained": v}, {"unexplained": cv * np.abs(fc.lines[line])}, {}


def components(fc, act, line):
    if line == "dtc_payouts":
        return dtc_components(fc, act)
    if line == "marketplace_payouts":
        return amazon_components(fc, act)
    if line == "wholesale_receipts":
        return wholesale_components(fc, act)
    if line in ("inventory", "freight_duty", "fulfillment_3pl", "other_ap"):
        return bill_components(fc, act, line)
    if line == "ad_spend_accrual":
        comps, sig, det = ads_components(fc, act)
        rest = (act.lines[line] - fc.lines[line]) - sum(comps.values(), np.zeros(N_WEEKS))
        comps["direct_debit"] = rest          # direct-debit platforms, tested on ad_direct
        sig["direct_debit"] = np.zeros(N_WEEKS)
        return comps, sig, det
    if line == "ad_direct":
        F, A = fc.lines["ad_direct"], act.lines["ad_direct"]
        return {"overspend:meta": A - F}, {"overspend:meta": fc.cfg["noise"]["ads"] * np.abs(F)}, {}
    if line == "card_autopay":
        return card_components(fc, act)
    if line == "other_opex":
        return opex_components(fc, act)
    if line == "sales_tax":
        v = act.lines[line] - fc.lines[line]
        return {"volume": v}, {"volume": fc.cfg["noise"]["dtc"] * np.abs(fc.lines[line]) * 2}, {}
    if line == "payroll":
        return simple_components(fc, act, line, DEFAULT_CV["payroll"])
    return simple_components(fc, act, line, 0.0)


def cause_of(component: str) -> str:
    return CAUSE_OF.get(component.split(":")[0], "unexplained")
