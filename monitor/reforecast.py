"""
Weekly reforecast: actuals through week t, then the forecast for the rest of the
window, adjusted by written rules for each kind of finding.

Two versions are compared in the evals:
  roll_forward(fc, act, t)            actual drivers through t, original forecast after t
  reforecast(fc, act, t, findings)    the same, plus the rules below

Rules (config/reforecast_rules.yaml holds the numbers):
  volume        carry the last two weeks' sales ratio for the next few weeks
  refunds       carry the SKU's elevated refund rate for the next two weeks
  reserve       expect the held amount back two settlements (four weeks) later
  late          overdue wholesale invoices arrive N weeks after due (later invoices
                stay on terms until they are missed too)
  overspend     carry the platform's overspend ratio to the end of the month
  fx            hold today's exchange rate (no view on direction)
  price (3PL)   carry a rate increase to the 3PL's later invoices
  fees          carry today's fee rate forward (added in v2, after the holdout run)
  timing, chargebacks, one_off: no forward change (the actuals already hold them)

Bill amounts and dates are known once a bill is issued, so issued bills use actual
amounts and due dates. Nothing here reads event labels.

Built by Avinash Rayudu.
"""
from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import yaml

from world.engine import N_WEEKS, book

ROOT = Path(__file__).resolve().parent.parent
RULES = yaml.safe_load((ROOT / "config" / "reforecast_rules.yaml").read_text())

WEEKLY = ["dtc_gross", "dtc_fee_rate", "dtc_chargebacks", "dtc_lag", "amz_sales", "amz_fee_rate",
          "amz_reserve_hold", "amz_reserve_release", "card_other_weekly", "tpl_rate", "payroll_noise",
          "other_opex_weekly"]


def splice(fc, act, t):
    """Driver set with actuals through week t and forecast after."""
    F, A = fc.drivers, act.drivers
    d = copy.deepcopy(F)
    n = t + 1
    for k in WEEKLY:
        d[k][:n] = A[k][:n]
    for grp in ("dtc_refunds_by_sku", "ad_by_platform"):
        for k in d[grp]:
            d[grp][k][:n] = A[grp][k][:n]
    d["fx"][:n] = A["fx"][:n]
    d["fx"][n:] = A["fx"][t]                       # hold today's rate
    for r in fc.cfg.get("retailers", []):
        name = r["name"]
        d["wh_invoices"][name][:12 + n] = A["wh_invoices"][name][:12 + n]
        for i in range(len(d["wh_delay_weeks"][name])):
            due = i - 12 + r["terms_weeks"]
            if due > t:
                continue
            paid = due + int(A["wh_delay_weeks"][name][i])
            # paid by now: we know when. Still unpaid: assume it arrives next week
            d["wh_delay_weeks"][name][i] = A["wh_delay_weeks"][name][i] if paid <= t else (t + 1 - due)
    issued = {b["id"] for b in act.bills if b["issue_week"] <= t or b["pay_week"] <= t}
    d["bill_price_mult"] = {k: v for k, v in A["bill_price_mult"].items() if k in issued}
    d["bill_due_shift"] = {k: v for k, v in A["bill_due_shift"].items() if k in issued}
    d["one_offs"] = [x for x in A["one_offs"] if x[0] <= t]
    return d


def roll_forward(fc, act, t):
    return book(fc.cfg, splice(fc, act, t))


def apply_rules(fc, act, t, d, findings):
    R = RULES
    F, A = fc.drivers, act.drivers
    W = N_WEEKS
    fut = slice(t + 1, W)
    for g in findings:
        c = g["component"]
        if g["detected_week"] > t:
            continue
        recent = slice(max(0, t - 1), t + 1)
        if c == "volume" and g["line"] == "dtc_payouts":
            ratio = float(np.sum(A["dtc_gross"][recent]) / np.sum(F["dtc_gross"][recent]))
            span = slice(t + 1, min(W, t + 1 + R["volume_carry_weeks"]))
            d["dtc_gross"][span] *= ratio
            d["dtc_chargebacks"][span] *= ratio
            for k in d["dtc_refunds_by_sku"]:
                d["dtc_refunds_by_sku"][k][span] *= ratio
        elif c == "refunds":
            span = slice(t + 1, min(W, t + 1 + R["refund_carry_weeks"]))
            for k in d["dtc_refunds_by_sku"]:
                f_ = float(np.sum(F["dtc_refunds_by_sku"][k][recent]))
                a_ = float(np.sum(A["dtc_refunds_by_sku"][k][recent]))
                if f_ > 0 and a_ / f_ > R["refund_sku_ratio_min"]:
                    d["dtc_refunds_by_sku"][k][span] *= a_ / f_
        elif c == "fees":                     # v2 (after the holdout): a fee-rate change persists
            key = "dtc_fee_rate" if g["line"] == "dtc_payouts" else "amz_fee_rate"
            d[key][t + 1:] = A[key][t]
        elif c == "reserve" and g["amount"] < 0:
            w = g["first_week"] + R["reserve_release_weeks"]
            if t < w < W:
                d["amz_reserve_release"][w] += -g["amount"]
        elif c == "late" and g["amount"] < 0:
            for r in fc.cfg.get("retailers", []):
                name = r["name"]
                # retailers with invoices due by now and still unpaid
                late_idx = [i for i in range(len(A["wh_delay_weeks"][name]))
                            if (i - 12 + r["terms_weeks"]) <= t < (i - 12 + r["terms_weeks"] +
                                                                   int(A["wh_delay_weeks"][name][i]))]
                if not late_idx:
                    continue
                for i in late_idx:
                    d["wh_delay_weeks"][name][i] = max(int(d["wh_delay_weeks"][name][i]),
                                                       R["late_receivable_delay_weeks"])
        elif c.startswith("overspend:"):
            p = c.split(":")[1]
            if p in d["ad_by_platform"]:
                ratio = float(np.sum(A["ad_by_platform"][p][recent]) / np.sum(F["ad_by_platform"][p][recent]))
                span = slice(t + 1, min(W, t + 1 + R["overspend_carry_weeks"]))
                d["ad_by_platform"][p][span] *= ratio
        elif c == "price" and g["line"] == "fulfillment_3pl":
            fb = {b["id"]: b for b in fc.bills}
            for b in act.bills:
                if b["line"] == "fulfillment_3pl" and b["issue_week"] <= t and b["id"] in fb:
                    mult = (b["amount"] / b["basis"]) / (fb[b["id"]]["amount"] / fb[b["id"]]["basis"])
                    for b2 in fc.bills:
                        if b2["line"] == "fulfillment_3pl" and b2["issue_week"] > t:
                            d["bill_price_mult"][b2["id"]] = mult
    return d


def reforecast(fc, act, t, findings):
    d = splice(fc, act, t)
    d = apply_rules(fc, act, t, d, findings)
    return book(fc.cfg, d)
