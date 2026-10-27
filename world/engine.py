"""
Driver-based 13-week cash engine.

One engine computes both the forecast and the (simulated) actuals, so every
dollar of variance can be traced to a driver: order volume, refunds, fees,
chargebacks, payout timing, Amazon reserves, receivables paid late, ad spend,
FX, bill amounts and bill timing.

  expected_drivers(cfg)          -> drivers a forecast assumes
  book(cfg, drivers)             -> weekly cash lines, bills and the cash path

The forecast is book(cfg, expected_drivers(cfg)). Actuals are the same engine
fed drivers with noise and injected events (world/inject_events.py).

Built by Avinash Rayudu. All brands and numbers are synthetic.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

WEEK0 = date(2026, 10, 26)          # Monday; forecast made with actuals through Oct 25
N_WEEKS = 13
WEEKS = [WEEK0 + timedelta(days=7 * k) for k in range(N_WEEKS)]
MONTH_MULT = {1: .70, 2: .70, 3: .85, 4: .90, 5: 1.0, 6: .85, 7: .90, 8: .85, 9: .90, 10: 1.0, 11: 2.10, 12: 1.60}
HIST_MULT = (MONTH_MULT[7] + MONTH_MULT[8] + MONTH_MULT[9] + MONTH_MULT[10]) / 4   # history window Jul-Oct
BFCM = (date(2026, 11, 23), date(2026, 11, 29))
BFCM_SHARE = 0.40

CASH_LINES = ["dtc_payouts", "marketplace_payouts", "wholesale_receipts", "payroll", "inventory", "freight_duty",
              "fulfillment_3pl", "other_ap", "card_autopay", "ad_direct", "fixed_costs", "sales_tax",
              "debt_service", "other_opex"]
WATCH_LINES = ["ad_spend_accrual"]     # not cash yet, but it becomes the card bill next month
INFLOW_LINES = {"dtc_payouts", "marketplace_payouts", "wholesale_receipts"}


def week_of(d: date) -> int:
    """Index of the forecast week containing d (may be negative or >= N_WEEKS)."""
    return (d - WEEK0).days // 7


def intensity(d: date) -> float:
    """Relative daily sales intensity; November concentrates 40% of the month in BFCM week."""
    if d.month == 11:
        month_units = MONTH_MULT[11] * 30
        if BFCM[0] <= d <= BFCM[1]:
            return month_units * BFCM_SHARE / 7
        return month_units * (1 - BFCM_SHARE) / 23
    return MONTH_MULT[d.month]


def week_mult(start: date) -> float:
    """Sales in the week starting `start`, relative to an average history week."""
    return sum(intensity(start + timedelta(days=i)) for i in range(7)) / 7 / HIST_MULT


def month_days_in_week(start: date):
    out = {}
    for i in range(7):
        d = start + timedelta(days=i)
        out[(d.year, d.month)] = out.get((d.year, d.month), 0) + 1
    return out


def week_with_day(year, month, day) -> int:
    return week_of(date(year, month, day))


def autopay_weeks():
    """[(week, (year, month) of the statement it pays)] for card autopay on the 22nd."""
    out = []
    for (y, m) in FORWARD_MONTHS[1:]:
        py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
        out.append((week_with_day(y, m, 22), (py, pm)))
    return out


FORWARD_MONTHS = [(2026, 10), (2026, 11), (2026, 12), (2027, 1)]


@dataclass
class Book:
    cfg: dict
    drivers: dict
    lines: dict                     # line -> np.array(N_WEEKS), positive = money in
    bills: list                     # every AP bill with its pay week and amounts
    opening_cash: float
    cash: np.ndarray = field(default=None)     # closing cash per week

    def total(self):
        return sum(self.lines[l] for l in CASH_LINES)

    def low_point(self):
        i = int(np.argmin(self.cash))
        return i, float(self.cash[i])


# --------------------------------------------------------------------------- expected drivers
def expected_drivers(cfg: dict) -> dict:
    W = N_WEEKS
    wm = np.array([week_mult(s) for s in WEEKS])
    pre = week_mult(WEEK0 - timedelta(days=7))
    d = {"week_mult": wm, "pre_week_mult": pre}
    # DTC
    g = cfg["dtc_weekly_gross"] * wm
    d["dtc_gross"] = g
    d["dtc_gross_pre"] = cfg["dtc_weekly_gross"] * pre
    rr = np.array([cfg.get("refund_rate_jan", cfg["refund_rate"]) if s.month == 1 else cfg["refund_rate"]
                   for s in WEEKS])
    d["dtc_refunds_by_sku"] = {sku: g * rr * sh for sku, sh in cfg["sku_shares"].items()}
    d["dtc_fee_rate"] = np.full(W, cfg["fee_rate"])
    d["dtc_chargebacks"] = g * cfg["chargeback_rate"]
    d["dtc_lag"] = np.full(W, cfg["payout_lag_share"])
    # Amazon: deposits every other week for the prior two weeks
    a = cfg.get("amz_weekly_sales", 0.0) * wm
    d["amz_sales"] = a
    d["amz_sales_pre"] = np.array([cfg.get("amz_weekly_sales", 0.0) * week_mult(WEEK0 - timedelta(days=7 * k))
                                   for k in (2, 1)])
    d["amz_fee_rate"] = np.full(W, cfg.get("amz_fee_rate", 0.30))
    d["amz_reserve_hold"] = np.zeros(W)
    d["amz_reserve_release"] = np.zeros(W)
    # wholesale invoices by retailer, issued weekly, paid on their terms
    d["wh_invoices"] = {}
    for r in cfg.get("retailers", []):
        hist = [cfg["wh_weekly"] * r["share"] * week_mult(WEEK0 - timedelta(days=7 * k)) for k in range(12, 0, -1)]
        fwd = list(cfg["wh_weekly"] * r["share"] * wm)
        d["wh_invoices"][r["name"]] = np.array(hist + fwd)      # index 0 = 12 weeks before WEEK0
    d["wh_delay_weeks"] = {r["name"]: np.zeros(12 + W, dtype=int) for r in cfg.get("retailers", [])}
    # card: ads by platform scale with DTC sales; other card spend is steady
    d["ad_by_platform"] = {p: g * cfg["ad_rate"] * sh for p, sh in cfg["ad_platforms"].items()}
    d["ad_oct_by_platform"] = {p: cfg["dtc_weekly_gross"] * cfg["ad_rate"] * sh * MONTH_MULT[10] / HIST_MULT
                               for p, sh in cfg["ad_platforms"].items()}   # weekly Oct spend (history)
    d["card_other_weekly"] = np.full(W, cfg["card_other_weekly"])
    # FX for brands paying suppliers in another currency
    d["fx"] = np.full(W, cfg.get("fx_rate", 1.0))
    # bill-level drivers
    d["tpl_rate"] = np.full(W, cfg["tpl_pct"])
    d["bill_price_mult"] = {}          # bill id -> multiplier on amount
    d["bill_due_shift"] = {}           # bill id -> weeks earlier (+) or later (-)
    d["one_offs"] = []                 # (week, counterparty, amount) unplanned payments
    d["payroll_noise"] = np.ones(W)
    d["other_opex_weekly"] = np.full(W, cfg.get("other_opex_weekly", 0.0))
    return d


# --------------------------------------------------------------------------- bills
def make_bills(cfg: dict, d: dict) -> list:
    """Every AP bill in the window, with terms. Amounts in the bill's currency."""
    bills = []
    cur = cfg.get("supplier_currency", cfg["currency"])
    for po in cfg["purchase_orders"]:
        bills.append(dict(id=po["id"], vendor=po["vendor"], line="inventory", amount=po["amount"], currency=cur,
                          issue_week=po["due_week"] - 2, due_week=po["due_week"], discount_pct=0.0,
                          discount_weeks=0, criticality="critical", category="inventory"))
    for fr in cfg["freight_invoices"]:
        bills.append(dict(id=fr["id"], vendor=cfg["forwarder"], line="freight_duty", amount=fr["amount"],
                          currency=cur, issue_week=fr["issue_week"], due_week=fr["issue_week"] + 2,
                          discount_pct=0.0, discount_weeks=0, criticality="high", category="freight"))
    # 3PL invoices on the 10th for the prior month's orders (proxied by DTC sales), 2/10 net 30
    for (y, m) in FORWARD_MONTHS[1:]:
        iw = week_with_day(y, m, 10)
        py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
        basis = month_gross(d, py, pm)
        rate = d["tpl_rate"][min(max(iw, 0), N_WEEKS - 1)]
        bills.append(dict(id=f"TPL-{y}{m:02d}", vendor=cfg["threepl"], line="fulfillment_3pl",
                          amount=rate * basis, currency=cfg["currency"], issue_week=iw, due_week=iw + 4,
                          discount_pct=0.02, discount_weeks=1, criticality="high", category="3pl",
                          basis=basis, rate=rate))
    # packaging supplier on the 5th, 1/10 net 30
    for (y, m) in FORWARD_MONTHS[1:]:
        iw = week_with_day(y, m, 5)
        py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
        bills.append(dict(id=f"PKG-{y}{m:02d}", vendor=cfg["packaging_vendor"], line="other_ap",
                          amount=cfg["packaging_pct"] * month_gross(d, py, pm), currency=cfg["currency"],
                          issue_week=iw, due_week=iw + 4, discount_pct=0.01, discount_weeks=1,
                          criticality="normal", category="packaging", basis=month_gross(d, py, pm),
                          rate=cfg["packaging_pct"]))
    bills.append(dict(id="SAAS-ANNUAL", vendor=cfg["saas_vendor"], line="other_ap", amount=cfg["saas_annual"],
                      currency=cfg["currency"], issue_week=5, due_week=9, discount_pct=0.0, discount_weeks=0,
                      criticality="low", category="software"))
    for b in bills:
        b["amount"] *= d["bill_price_mult"].get(b["id"], 1.0)
        b["due_week"] -= d["bill_due_shift"].get(b["id"], 0)
        b["issue_week"] = min(b["issue_week"], b["due_week"])     # a bill pulled forward is re-issued
        b["pay_week"] = b["due_week"]
    return [b for b in bills if b["due_week"] >= 0 or b["issue_week"] >= 0]


def month_gross(d, y, m) -> float:
    """DTC sales in a calendar month, from weekly sales split by day (history weeks extrapolated)."""
    total = 0.0
    start = date(y, m, 1)
    end = (date(y + (m == 12), m % 12 + 1, 1))
    day = start
    while day < end:
        k = week_of(day)
        if 0 <= k < N_WEEKS:
            wk_g = d["dtc_gross"][k]
            share = intensity(day) / (sum(intensity(WEEKS[k] + timedelta(days=i)) for i in range(7)))
        else:
            base = d["dtc_gross_pre"] / d["pre_week_mult"]          # average history week
            wk_start = WEEK0 + timedelta(days=7 * k)
            wk_g = base * week_mult(wk_start)
            share = intensity(day) / sum(intensity(wk_start + timedelta(days=i)) for i in range(7))
        total += wk_g * share
        day += timedelta(days=1)
    return total


# --------------------------------------------------------------------------- the book
def book(cfg: dict, d: dict, pay_weeks: dict = None, discounts_taken: set = None) -> Book:
    W = N_WEEKS
    L = {l: np.zeros(W) for l in CASH_LINES + WATCH_LINES}
    # DTC payouts: a share of each week's net is paid the following week
    g = d["dtc_gross"]
    ref = sum(d["dtc_refunds_by_sku"].values())
    net = g - ref - d["dtc_fee_rate"] * g - d["dtc_chargebacks"]
    gp = d["dtc_gross_pre"]
    net_pre = gp * (1 - cfg["refund_rate"] - cfg["fee_rate"] - cfg["chargeback_rate"])
    lag = d["dtc_lag"]
    prev_net, prev_lag = net_pre, cfg["payout_lag_share"]
    for w in range(W):
        L["dtc_payouts"][w] = (1 - lag[w]) * net[w] + prev_lag * prev_net
        prev_net, prev_lag = net[w], lag[w]
    d["_dtc_net"] = net
    # Amazon deposits on even weeks for the previous two weeks of sales
    if cfg.get("amz_weekly_sales", 0) > 0:
        sales = np.concatenate([d["amz_sales_pre"], d["amz_sales"]])     # index 0 = week -2
        fee = np.concatenate([np.full(2, cfg.get("amz_fee_rate", 0.30)), d["amz_fee_rate"]])
        for w in range(0, W, 2):
            s = sales[w:w + 2]
            f = fee[w:w + 2]
            L["marketplace_payouts"][w] = float(np.sum(s * (1 - f))) - d["amz_reserve_hold"][w] + \
                d["amz_reserve_release"][w]
    # wholesale receipts: invoice issued in week i is due i + terms, paid due + delay
    for r in cfg.get("retailers", []):
        inv = d["wh_invoices"][r["name"]]
        delay = d["wh_delay_weeks"][r["name"]]
        for i, amt in enumerate(inv):
            pw = (i - 12) + r["terms_weeks"] + int(delay[i])
            if 0 <= pw < W:
                L["wholesale_receipts"][pw] += amt
    # payroll on the brand's payroll Fridays
    for k in cfg["payroll_weeks"]:
        if 0 <= k < W:
            L["payroll"][k] -= cfg["payroll_run"] * d["payroll_noise"][k]
    # fixed costs on the 1st, sales tax on the 20th for the prior month, interest on the 1st
    for (y, m) in FORWARD_MONTHS[1:]:
        k = week_with_day(y, m, 1)
        if 0 <= k < W:
            L["fixed_costs"][k] -= cfg["fixed_monthly"]
            if cfg.get("loc_drawn", 0) > 0:
                L["debt_service"][k] -= cfg["loc_drawn"] * cfg["loc_apr"] / 12
        k20 = week_with_day(y, m, 20)
        py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
        if 0 <= k20 < W:
            L["sales_tax"][k20] -= cfg["sales_tax_rate"] * month_gross(d, py, pm)
    # card: weekly ad accrual (watched), monthly autopay on the 22nd of last month's charges
    ads = sum(d["ad_by_platform"].values())
    if cfg.get("meta_direct_debit") and "meta" in d["ad_by_platform"]:
        L["ad_direct"] -= d["ad_by_platform"]["meta"]
        card_ads = ads - d["ad_by_platform"]["meta"]
        oct_card_ads = sum(v for p, v in d["ad_oct_by_platform"].items() if p != "meta")
    else:
        card_ads = ads
        oct_card_ads = sum(d["ad_oct_by_platform"].values())
    L["ad_spend_accrual"] -= ads
    stmt_ads, stmt_other = {}, {}
    for w, s in enumerate(WEEKS):
        for ym, n in month_days_in_week(s).items():
            stmt_ads[ym] = stmt_ads.get(ym, 0.0) + card_ads[w] * n / 7
            stmt_other[ym] = stmt_other.get(ym, 0.0) + d["card_other_weekly"][w] * n / 7
    stmt_ads[(2026, 10)] = stmt_ads.get((2026, 10), 0.0) + oct_card_ads * 25 / 7
    stmt_other[(2026, 10)] = stmt_other.get((2026, 10), 0.0) + cfg["card_other_weekly"] * 25 / 7
    stmt = {k: stmt_ads.get(k, 0.0) + stmt_other.get(k, 0.0) for k in set(stmt_ads) | set(stmt_other)}
    d["_card_statements"], d["_card_stmt_ads"], d["_card_stmt_other"] = stmt, stmt_ads, stmt_other
    for (y, m) in FORWARD_MONTHS[1:]:
        k = week_with_day(y, m, 22)
        py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
        if 0 <= k < W:
            L["card_autopay"][k] -= stmt.get((py, pm), 0.0)
    # bills, paid on their pay week (default: due week); FX at the pay week's rate
    bills = make_bills(cfg, d)
    for b in bills:
        pw = (pay_weeks or {}).get(b["id"], b["pay_week"])
        b["pay_week"] = pw
        amt = b["amount"]
        if discounts_taken and b["id"] in discounts_taken:
            amt *= (1 - b["discount_pct"])
        fx = d["fx"][min(max(pw, 0), W - 1)] if b["currency"] != cfg["currency"] else 1.0
        b["fx"] = fx
        b["cash"] = amt * fx
        if 0 <= pw < W:
            L[b["line"]][pw] -= b["cash"]
    # misc operating payments plus unplanned one-offs
    L["other_opex"] -= d["other_opex_weekly"]
    for (w, cp, amt) in d["one_offs"]:
        if 0 <= w < W:
            L["other_opex"][w] -= amt
    bk = Book(cfg=cfg, drivers=d, lines=L, bills=bills, opening_cash=cfg["opening_cash"])
    bk.cash = cfg["opening_cash"] + np.cumsum(bk.total())
    return bk


def forecast(cfg: dict) -> Book:
    return book(cfg, expected_drivers(cfg))


# --------------------------------------------------------------------------- noise
def noisy_drivers(cfg: dict, seed: int) -> dict:
    """Expected drivers with week-to-week noise at the brand's historical variability."""
    rng = np.random.default_rng(seed)
    d = copy.deepcopy(expected_drivers(cfg))
    cv = cfg["noise"]
    W = N_WEEKS
    m = rng.lognormal(0, cv["dtc"], W)
    d["dtc_gross"] = d["dtc_gross"] * m
    for k in d["dtc_refunds_by_sku"]:
        d["dtc_refunds_by_sku"][k] = d["dtc_refunds_by_sku"][k] * m * rng.lognormal(0, 0.12, W)
    d["dtc_chargebacks"] = d["dtc_chargebacks"] * m * rng.lognormal(0, 0.25, W)
    if cfg.get("amz_weekly_sales", 0) > 0:
        d["amz_sales"] = d["amz_sales"] * rng.lognormal(0, cv["amazon"], W)
    for r in d["wh_invoices"]:
        n = len(d["wh_invoices"][r])
        noise = np.ones(n)
        noise[12:] = rng.lognormal(0, cv["wholesale"], n - 12)    # history invoices are already issued
        d["wh_invoices"][r] = d["wh_invoices"][r] * noise
    for p in d["ad_by_platform"]:
        d["ad_by_platform"][p] = d["ad_by_platform"][p] * rng.lognormal(0, cv["ads"], W)
    d["card_other_weekly"] = d["card_other_weekly"] * rng.lognormal(0, 0.15, W)
    d["payroll_noise"] = rng.normal(1.0, 0.005, W)
    d["other_opex_weekly"] = d["other_opex_weekly"] * rng.lognormal(0, 0.30, W)
    if cfg.get("supplier_currency", cfg["currency"]) != cfg["currency"]:
        steps = rng.normal(0, 0.004, W)
        d["fx"] = cfg["fx_rate"] * np.exp(np.cumsum(steps))
    return d
