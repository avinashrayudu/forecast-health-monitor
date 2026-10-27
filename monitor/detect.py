"""
Noise-aware drift detection on top of the variance attribution.

Each week, for every line and every driver component, the detector tests the
latest 1-, 2- and 4-week windows:

  flag if |component sum| >= Z * (its normal noise over the window)
     and |component sum| >= the brand's materiality (scaled for longer windows)

Components with no normal noise (payout timing, fees, reserves, bill timing,
price changes, unplanned payees) flag on materiality alone. Flags on the same
line and driver within two weeks of each other merge into one finding, dated
the week it was first flagged.

The detector reads only the forecast book and the actual book. It never reads
how the actuals were generated or any event labels.

Built by Avinash Rayudu.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from monitor.attribute import cause_of, components
from world.engine import CASH_LINES, N_WEEKS, WATCH_LINES, WEEKS

PARAMS = {"z": 3.0, "windows": (1, 2, 4), "merge_gap_weeks": 2}


def _week_label(w):
    return WEEKS[w].strftime("%b %-d") if 0 <= w < N_WEEKS else f"week {w}"


def scan(fc, act, through_week: int = N_WEEKS - 1, params: dict = None) -> list:
    """All findings for one brand using actuals through `through_week`."""
    P = dict(PARAMS, **(params or {}))
    cfg = fc.cfg
    mat = cfg["materiality"]
    flags = []
    for line in CASH_LINES + WATCH_LINES:
        comps, sig, detail = components(fc, act, line)
        for comp, v in comps.items():
            s = sig.get(comp, np.zeros_like(v))
            for t in range(min(through_week, N_WEEKS - 1) + 1):
                for k in P["windows"]:
                    if t - k + 1 < 0:
                        continue
                    S = float(np.sum(v[t - k + 1:t + 1]))
                    sd = float(np.sqrt(np.sum(s[t - k + 1:t + 1] ** 2)))
                    # the newest week must carry its share of the drift, or the flag is stale
                    if v[t] * S <= 0 or abs(v[t]) < abs(S) / (2 * k):
                        continue
                    if abs(S) < mat * max(1.0, k / 2):
                        continue
                    if sd > 0 and abs(S) < P["z"] * sd:
                        continue
                    if comp == "direct_debit" or (comp in ("noise", "other") and sd == 0):
                        continue
                    flags.append(dict(line=line, component=comp, week=t, window=k, amount=S,
                                      z=abs(S) / sd if sd > 0 else None))
                    break
    return _merge(flags, fc, act, P)


def _merge(flags, fc, act, P):
    findings = []
    by = {}
    for f in sorted(flags, key=lambda f: (f["line"], f["component"], f["week"])):
        by.setdefault((f["line"], f["component"], f["amount"] > 0), []).append(f)
    for (line, comp, _), fl in by.items():
        cur = None
        for f in fl:
            if cur and f["week"] - cur["last_week"] <= P["merge_gap_weeks"]:
                cur["last_week"] = f["week"]
                cur["flags"].append(f)
                continue
            cur = dict(brand=fc.cfg["slug"], line=line, component=comp, cause=cause_of(comp),
                       first_week=f["week"] - f["window"] + 1, detected_week=f["week"], last_week=f["week"],
                       flags=[f])
            findings.append(cur)
    comps_cache = {}
    for g in findings:
        if g["line"] not in comps_cache:
            comps_cache[g["line"]] = components(fc, act, g["line"])
        comps, sig, detail = comps_cache[g["line"]]
        v = comps[g["component"]]
        sign = 1 if g["flags"][0]["amount"] > 0 else -1
        wk = [w for w in range(g["first_week"], g["last_week"] + 1) if v[w] * sign > 0]
        g["first_week"], g["last_week"] = wk[0], wk[-1]
        g["amount"] = round(float(np.sum(v[g["first_week"]:g["last_week"] + 1])), 2)
        zs = [f["z"] for f in g["flags"] if f["z"] is not None]
        g["max_z"] = round(max(zs), 1) if zs else None
        g["explanation"] = explain(g, fc, act, detail)
        del g["flags"]
    return sorted(findings, key=lambda g: (g["detected_week"], -abs(g["amount"])))


def explain(g, fc, act, detail) -> str:
    c, line, a, b = g["component"], g["line"], g["first_week"], g["last_week"]
    when = f"week of {_week_label(a)}" + (f" to {_week_label(b)}" if b > a else "")
    amt = f"${abs(g['amount']):,.0f}"
    direction = "below" if g["amount"] < 0 else "above"
    F, A = fc.drivers, act.drivers
    if c == "refunds":
        deltas = {k: float(np.sum(v[a:b + 1])) for k, v in detail["refund_sku_delta"].items()}
        top = max(deltas, key=lambda k: deltas[k])
        tot = sum(x for x in deltas.values() if x > 0) or 1.0
        ratio = float(np.mean(detail["refund_ratio"][a:b + 1]))
        return (f"Refunds ran {ratio:.1f}x forecast ({when}); SKU {top} is {deltas[top] / tot:.0%} of the excess. "
                f"Payouts {amt} {direction} forecast.")
    if c == "volume" and line == "dtc_payouts":
        r = float(np.sum(A["dtc_gross"][a:b + 1]) / np.sum(F["dtc_gross"][a:b + 1]) - 1)
        return f"Shopify sales ran {r:+.0%} vs forecast ({when}); payouts {amt} {direction} forecast."
    if c == "timing" and line == "dtc_payouts":
        if g["amount"] > 0:
            return f"Held Shopify payouts of {amt} arrived ({when})."
        return (f"Shopify paid out a smaller share of the week's sales than usual ({when}); {amt} is held and "
                f"should arrive in the following payout.")
    if c == "chargebacks":
        exp = float(np.sum(F["dtc_chargebacks"][a:b + 1]))
        got = float(np.sum(A["dtc_chargebacks"][a:b + 1]))
        return f"Chargebacks of ${got:,.0f} vs ${exp:,.0f} expected ({when})."
    if c == "fees":
        who = "Amazon fees" if line == "marketplace_payouts" else "Processing fees"
        return f"{who} {amt} {'above' if g['amount'] < 0 else 'below'} forecast ({when}); check the fee rate."
    if c == "reserve":
        return f"Amazon settlement held {amt} as a reserve ({when})." if g["amount"] < 0 else \
            f"Amazon released {amt} of reserve ({when})."
    if c == "volume" and line == "marketplace_payouts":
        return f"Amazon settlement {amt} {direction} forecast on sales ({when})."
    if c == "late":
        per = {r: float(np.sum(v[a:b + 1])) for r, v in detail["late_by_retailer"].items()}
        r = min(per, key=lambda k: per[k]) if g["amount"] < 0 else max(per, key=lambda k: per[k])
        return (f"{r} has not paid invoices that were due ({when}); {amt} overdue." if g["amount"] < 0 else
                f"{r} paid {amt} of overdue invoices ({when}).")
    if line in ("inventory", "freight_duty", "fulfillment_3pl", "other_ap"):
        bills = detail.get("bills", {})
        moved = [(k, x) for k, x in bills.items() if
                 (c == "timing" and x["forecast_week"] != x["actual_week"]) or
                 (c in ("price", "fx", "volume") and a <= x["actual_week"] <= b and
                  abs(x["actual_cash"] - x["forecast_cash"]) > 1)]
        if moved:
            k, x = moved[0]
            if c == "timing" and g["amount"] > 0:
                return (f"{k} ({x['vendor']}) was forecast for this week but already went out the week of "
                        f"{_week_label(x['actual_week'])}.")
            if c == "timing":
                return (f"{k} ({x['vendor']}) paid week of {_week_label(x['actual_week'])} instead of "
                        f"{_week_label(x['forecast_week'])} ({amt}).")
            chg = -g["amount"] / abs(x["forecast_cash"]) if x["forecast_cash"] else 0
            if c == "fx":
                return f"{k} ({x['vendor']}) cost {amt} more after the exchange rate moved ({when})."
            return f"{k} ({x['vendor']}) billed {abs(chg):.0%} {'above' if chg > 0 else 'below'} forecast ({amt})."
        return f"{line} {c} {amt} {direction} forecast ({when})."
    if c.startswith("overspend"):
        p = c.split(":")[1] if ":" in c else "ads"
        if line == "ad_spend_accrual":
            r = float(np.sum(A["ad_by_platform"][p][a:b + 1]) / np.sum(F["ad_by_platform"][p][a:b + 1]) - 1)
            return (f"{p.title()} spend ran {r:+.0%} vs plan ({when}); {amt} extra will hit the card "
                    f"statement and the next autopay.")
        if line == "ad_direct":
            return f"Meta direct-debit spend {amt} {'above' if g['amount'] < 0 else 'below'} plan ({when})."
        return f"Card autopay {amt} {'above' if g['amount'] < 0 else 'below'} forecast on ad spend ({when})."
    if c == "one_off":
        pays = detail["one_off_payees"]
        who = [f"{cp} (${x:,.0f})" for w in range(a, b + 1) for cp, x in pays.get(w, [])]
        return f"Unplanned payment to {', '.join(who)} ({when})."
    if c == "volume" and line == "sales_tax":
        return f"Sales tax {amt} {direction} forecast because last month's sales moved ({when})."
    if c == "volume" and line == "wholesale_receipts":
        return f"Wholesale invoices {amt} {direction} forecast ({when})."
    return f"{line} {amt} {direction} forecast with no driver detail ({when})."
