"""
Actions from the cash forecast.

  fund_trough(book)            credit-line draw ahead of the low point, repay date, interest cost
  sweep_vs_paydown(book)       what to do with cash above the buffer after the trough
  ap_policies(...)             four bill-payment policies, scored on the actual weeks:
      due_date      pay every bill on its due date
      pay_early     take every early-payment discount
      plan_once     forecast-aware plan made once, at week 0, from the original forecast
      monitored     forecast-aware plan re-made every week from the monitor's reforecast

Each policy also sizes its credit-line draws from its own forecast: the first three
once, at week 0; the monitored policy every Monday from the latest reforecast. On the
actual weeks a policy is judged on discounts captured, interest paid, and any week
the brand falls under its buffer with no draw planned for it ("unplanned breach").

The forecast-aware policies take a discount only when it is worth more than the
credit-line interest needed to cover any dip under the buffer and the draw fits
the line's headroom, defer only bills the vendor rules allow to move, and never
pay a critical bill late.

Built by Avinash Rayudu.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import yaml

from monitor.detect import scan
from monitor.reforecast import apply_rules, splice
from world.engine import N_WEEKS, WEEKS, book

ROOT = Path(__file__).resolve().parent.parent
RULES = yaml.safe_load((ROOT / "actions" / "vendor_rules.yaml").read_text())


def wk(w):
    return WEEKS[w].strftime("%b %-d") if 0 <= w < N_WEEKS else f"week {w}"


# --------------------------------------------------------------------------- funding
def fund_trough(bk, from_week: int = 0):
    cfg = bk.cfg
    buf = cfg["cash_buffer"]
    cash = bk.cash
    low_w = from_week + int(np.argmin(cash[from_week:]))
    low = float(cash[low_w])
    out = dict(low_week=low_w, low_week_label=wk(low_w), low_cash=round(low, 2), buffer=buf,
               gap=round(max(0.0, buf - low), 2), draw=0.0)
    if low >= buf:
        out["action"] = "No draw needed: the low point stays above the buffer."
        return out
    inc = RULES["credit_line"]["draw_increment"]
    draw = math.ceil((buf - low) / inc) * inc
    first = next(w for w in range(from_week, N_WEEKS) if cash[w] < buf)
    repay = next((w for w in range(low_w + 1, N_WEEKS) if all(cash[x] - draw >= buf for x in range(w, N_WEEKS))),
                 None)
    weeks = (repay if repay is not None else N_WEEKS) - first
    interest = draw * cfg["loc_apr"] * weeks / 52
    headroom = cfg["loc_limit"] - cfg["loc_drawn"]
    out.update(draw=float(draw), draw_week=first, draw_week_label=wk(first), repay_week=repay,
               repay_week_label=wk(repay) if repay is not None else "after the window", weeks_outstanding=weeks,
               interest=round(interest, 2), headroom=headroom, within_limit=draw <= headroom,
               action=(f"Draw ${draw:,.0f} on the credit line in the week of {wk(first)}; repay in the week of "
                       f"{wk(repay) if repay is not None else 'the next window'}. Interest about ${interest:,.0f} "
                       f"at {cfg['loc_apr']:.0%} APR."))
    return out


def sweep_vs_paydown(bk, after_week: int = 0):
    """Cash above the buffer that the rest of the window never needs."""
    cfg = bk.cfg
    buf = cfg["cash_buffer"]
    for w in range(after_week, N_WEEKS):
        spare = float(np.min(bk.cash[w:])) - buf
        if spare > 25000:
            pay = min(spare, cfg["loc_drawn"])
            sweep = spare - pay
            gain = pay * (cfg["loc_apr"] - cfg["savings_apy"])
            return dict(week=w, week_label=wk(w), spare=round(spare, 2), paydown=round(pay, 2),
                        sweep=round(sweep, 2), annual_benefit_vs_sweep=round(gain, 2),
                        action=(f"From the week of {wk(w)}, ${spare:,.0f} sits above the buffer for the rest of the "
                                f"window. Pay down ${pay:,.0f} of the credit line first ({cfg['loc_apr']:.0%} APR "
                                f"saved vs {cfg['savings_apy']:.2%} earned), worth about ${gain:,.0f} a year more "
                                f"than sweeping it" + (f"; sweep the other ${sweep:,.0f} to savings." if sweep > 0
                                                       else ".")))
    return dict(week=None, action="No cash sits above the buffer for the rest of the window; keep it in operating.")


# --------------------------------------------------------------------------- AP policies
def max_late(b):
    return RULES["criticality"][b["criticality"]]["max_weeks_late"]


def discount_deadline(b):
    return b["issue_week"] + b["discount_weeks"]


def need(cash, buf, inc, margin=None):
    """Credit-line balance (above today's) needed each week to hold the buffer, in round draws.
    `margin` adds a cushion per week for cash the forecast cannot see yet (v2)."""
    m = np.zeros(len(cash)) if margin is None else margin
    return np.array([math.ceil(max(0.0, buf + mm - c) / inc) * inc for c, mm in zip(cash, m)], dtype=float)


def cash_sigma(bk):
    """Typical week-to-week noise in each week's receipts, from the brand's calibrated variability."""
    nz = bk.cfg["noise"]
    s = np.sqrt((nz["dtc"] * bk.lines["dtc_payouts"]) ** 2 + (nz["amazon"] * bk.lines["marketplace_payouts"]) ** 2 +
                (nz["wholesale"] * bk.lines["wholesale_receipts"]) ** 2)
    return s


def draw_margin(bk, from_week=0):
    """v2 (after the holdout): size draws to cover 1.65 sigma of unseen receipts, cumulated from
    the planning week, so a normal bad week does not breach the buffer."""
    z = RULES["credit_line"].get("margin_sigma", 0.0)
    s = cash_sigma(bk)
    out = np.zeros(N_WEEKS)
    for w in range(from_week, N_WEEKS):
        out[w] = z * float(np.sqrt(np.sum(s[from_week:w + 1] ** 2)))
    return out


def gap_cost(cash, buf, apr, inc=RULES["credit_line"]["draw_increment"]):
    """Interest on the draws needed to hold the buffer."""
    return float(np.sum(need(cash, buf, inc)) * apr / 52)


def headroom(cfg):
    return max(0.0, cfg["loc_limit"] - cfg["loc_drawn"])


def headroom_ok(cfg, cash):
    inc = RULES["credit_line"]["draw_increment"]
    return float(np.max(need(cash, cfg["cash_buffer"], inc))) <= headroom(cfg)


def decide_bills(cfg, d, t_from, t_to, pay_weeks, discounts):
    """Forecast-aware decisions for bills whose decision week falls in [t_from, t_to]."""
    base = book(cfg, d, pay_weeks, discounts)
    buf, apr = cfg["cash_buffer"], cfg["loc_apr"]
    for b in sorted(base.bills, key=lambda b: b["issue_week"]):
        if b["id"] in discounts or b["discount_pct"] <= 0:
            continue
        dl = discount_deadline(b)
        if not (t_from <= dl <= t_to) or dl >= b["due_week"]:
            continue
        trial_pw = dict(pay_weeks, **{b["id"]: max(dl, b["issue_week"])})
        trial_ds = discounts | {b["id"]}
        trial = book(cfg, d, trial_pw, trial_ds)
        saving = b["amount"] * b["fx"] * b["discount_pct"]
        extra = gap_cost(trial.cash, buf, apr) - gap_cost(base.cash, buf, apr)
        if saving > extra and headroom_ok(cfg, trial.cash):
            pay_weeks, discounts, base = trial_pw, trial_ds, trial
    for b in sorted(base.bills, key=lambda b: b["due_week"]):
        ml = max_late(b)
        if ml <= 0 or not (t_from <= b["due_week"] <= t_to) or b["id"] in pay_weeks:
            continue
        if base.cash[b["due_week"]] >= buf:
            continue
        best, best_cost = None, gap_cost(base.cash, buf, apr)
        for k in range(1, ml + 1):
            trial = book(cfg, d, dict(pay_weeks, **{b["id"]: b["due_week"] + k}), discounts)
            c = gap_cost(trial.cash, buf, apr)
            if c < best_cost - 1:
                best, best_cost = b["due_week"] + k, c
        if best is not None:
            pay_weeks = dict(pay_weeks, **{b["id"]: best})
            base = book(cfg, d, pay_weeks, discounts)
    return pay_weeks, discounts


def policy_plan(name, fc, act):
    """Returns (pay_weeks, discounts, planned credit-line draws per week)."""
    cfg = fc.cfg
    inc = RULES["credit_line"]["draw_increment"]
    buf = cfg["cash_buffer"]
    if name in ("due_date", "pay_early", "plan_once"):
        if name == "due_date":
            pw, ds = {}, set()
        elif name == "pay_early":
            pw, ds = {}, set()
            for b in fc.bills:
                if b["discount_pct"] > 0:
                    pw[b["id"]] = max(discount_deadline(b), b["issue_week"])
                    ds.add(b["id"])
        else:
            pw, ds = decide_bills(cfg, fc.drivers, 0, N_WEEKS - 1, {}, set())
        plan = book(cfg, fc.drivers, pw, ds)
        draws = need(plan.cash, buf, inc, draw_margin(plan, 0))        # sized once, at week 0
        return pw, ds, np.minimum(draws, headroom(cfg))
    if name == "monitored":
        steps = monitored_steps(fc, act)
        return steps[-1]["pay_weeks"], steps[-1]["discounts"], np.array([x["draw"] for x in steps])
    raise ValueError(name)


def monitored_steps(fc, act):
    """The monitored policy week by week. On the Monday of week t it knows actuals through t-1,
    re-runs the monitor and the reforecast, decides this week's bills and sizes this week's draw."""
    cfg = fc.cfg
    inc = RULES["credit_line"]["draw_increment"]
    buf = cfg["cash_buffer"]
    pw, ds = {}, set()
    steps = []
    for t in range(N_WEEKS):
        if t > 0:
            findings = scan(fc, act, t - 1)
            d = apply_rules(fc, act, t - 1, splice(fc, act, t - 1), findings)
        else:
            findings, d = [], fc.drivers
        before = (dict(pw), set(ds))
        pw, ds = decide_bills(cfg, d, t, t, pw, ds)
        plan = book(cfg, d, pw, ds)
        margin = draw_margin(plan, t)
        draw = min(need(plan.cash, buf, inc, margin)[t], headroom(cfg))
        steps.append(dict(week=t, findings=findings, plan=plan, margin=margin, draw=float(draw),
                          pay_weeks=dict(pw), discounts=set(ds),
                          decided_now=[k for k in pw if k not in before[0]],
                          discounts_now=[k for k in ds if k not in before[1]]))
    return steps


def score_on_actuals(fc, act, pay_weeks, discounts, draws):
    """Apply a pay plan and its planned draws to the actual weeks. Bills whose actual due date
    moved earlier are paid by the actual due date (the plan is revised when the bill changes)."""
    cfg = fc.cfg
    actual_due = {b["id"]: b["due_week"] for b in act.bills}
    pw = {}
    for bid, w in pay_weeks.items():
        pw[bid] = min(w, actual_due.get(bid, w)) if max_late_by_id(fc, bid) == 0 else w
    bk = book(cfg, act.drivers, pw, discounts)
    buf, apr = cfg["cash_buffer"], cfg["loc_apr"]
    broken = []
    for b in bk.bills:
        late = b["pay_week"] - actual_due[b["id"]]
        if late > max_late(b):
            broken.append((b["id"], "late"))
        if RULES["never_pay_before_issue"] and b["pay_week"] < b["issue_week"]:
            broken.append((b["id"], "before issue"))
    disc = sum(b["amount"] * b["fx"] * b["discount_pct"] for b in bk.bills if b["id"] in discounts)
    interest = float(np.sum(draws) * apr / 52)
    covered = bk.cash + draws
    gap = np.maximum(0.0, buf - covered)
    return dict(discounts=round(float(disc), 2), interest=round(interest, 2), net=round(float(disc) - interest, 2),
                unplanned_breach_weeks=int(np.sum(gap > 0)), worst_unplanned_gap=round(float(gap.max()), 2),
                overdraft_weeks=int(np.sum(covered < 0)), peak_draw=round(float(draws.max()), 2),
                min_cash_with_draws=round(float(covered.min()), 2), rules_broken=broken,
                bills_paid_early=len(discounts))


def max_late_by_id(fc, bid):
    for b in fc.bills:
        if b["id"] == bid:
            return max_late(b)
    return 0


POLICIES = ["due_date", "pay_early", "plan_once", "monitored"]


def compare_policies(fc, act):
    return {p: score_on_actuals(fc, act, *policy_plan(p, fc, act)) for p in POLICIES}
