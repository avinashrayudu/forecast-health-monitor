"""
Builds the simulated "actual" weeks for every brand, with injected cash-drift events.

For each brand and scenario this produces three books from the same engine:
  forecast        what the brand expected at week 0 (no noise, no events)
  counterfactual  what happened with normal week-to-week noise but no events
  actual          the same noise plus the injected events

The event labels (which brand, which week, which cause) are written to
world/labels/<scenario>.json for scoring only. The monitor never reads them;
a test checks that nothing under monitor/ imports this module or the labels.

The 12 development events below were used while building the detector. The
holdout events live in world/holdout_events.py and were written after the
monitor was frozen.

Built by Avinash Rayudu.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np

from world.engine import N_WEEKS, book, expected_drivers, forecast, noisy_drivers

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "world" / "labels"

DEV_EVENTS = [
    dict(id="E01", brand="fernwood-goods", cause="refunds", line="dtc_payouts", start=1, end=2,
         desc="quality issue: refunds on SKU FW-2201 run 4x normal", params={"sku": "FW-2201", "mult": 4.0}),
    dict(id="E02", brand="lark-and-pine", cause="timing", line="dtc_payouts", start=5, end=5,
         desc="Shopify holds a week of payouts during a risk review", params={"lag": 1.0}),
    dict(id="E03", brand="tidewater-swim", cause="reserve", line="marketplace_payouts", start=4, end=4,
         desc="Amazon holds a reserve on the BFCM settlement, released two settlements later",
         params={"share": 0.35, "release_after": 4}),
    dict(id="E04", brand="copperleaf-tea", cause="late_receivable", line="wholesale_receipts", start=3, end=5,
         desc="Mapleton Gifts pays three weeks late", params={"retailer": "Mapleton Gifts", "delay": 3}),
    dict(id="E05", brand="north-arc-outdoor", cause="overspend", line="ad_spend_accrual", start=2, end=5,
         desc="Meta campaigns run 45% over plan", params={"platform": "meta", "mult": 1.45}),
    dict(id="E06", brand="saltmarsh-apparel", cause="fx", line="inventory", start=10, end=10,
         desc="USD strengthens 6% against CAD before the spring deposit", params={"from_week": 6, "mult": 1.06}),
    dict(id="E07", brand="marigold-skin", cause="volume", line="dtc_payouts", start=7, end=9,
         desc="December orders run 30% below plan after a site outage and a weak gift campaign",
         params={"mult": 0.70}),
    dict(id="E08", brand="bramble-pet", cause="chargebacks", line="dtc_payouts", start=6, end=6,
         desc="a cluster of fraud chargebacks", params={"amount": 9000.0}),
    dict(id="E09", brand="quillon-coffee", cause="timing", line="inventory", start=7, end=7,
         desc="supplier asks for the spring deposit three weeks early", params={"bill": "PO-SPRING-DEP", "weeks": 3}),
    dict(id="E10", brand="hollis-home", cause="price", line="freight_duty", start=2, end=2,
         desc="BFCM freight invoice comes in 60% above estimate", params={"bill": "FRT-BFCM", "mult": 1.6}),
    dict(id="E11", brand="north-arc-outdoor", cause="one_off", line="other_opex", start=9, end=9,
         desc="unplanned legal bill", params={"counterparty": "Hartwell Legal LLP", "amount": 24000.0}),
    dict(id="E12", brand="bramble-pet", cause="price", line="fulfillment_3pl", start=10, end=10,
         desc="3PL raises its pick-and-pack rate 30% from December", params={"bill": "TPL-202612", "mult": 1.3}),
]


def apply_event(cfg, d, ev):
    p = ev["params"]
    c = ev["cause"]
    a, b = ev["start"], ev["end"]
    wk = slice(a, b + 1)
    if c == "refunds":
        d["dtc_refunds_by_sku"][p["sku"]][wk] *= p["mult"]
    elif c == "timing" and ev["line"] == "dtc_payouts":
        d["dtc_lag"][wk] = p["lag"]
    elif c == "reserve":
        dep = expected_drivers(cfg)
        hold = p["share"] * float(np.sum(d["amz_sales"][a - 2:a] * (1 - d["amz_fee_rate"][a - 2:a])))
        d["amz_reserve_hold"][a] += hold
        if a + p["release_after"] < N_WEEKS:
            d["amz_reserve_release"][a + p["release_after"]] += hold
    elif c == "late_receivable":
        r = p["retailer"]
        terms = next(x["terms_weeks"] for x in cfg["retailers"] if x["name"] == r)
        for due in range(a, b + 1):
            i = due - terms + 12          # invoice index whose due week is `due`
            if 0 <= i < len(d["wh_delay_weeks"][r]):
                d["wh_delay_weeks"][r][i] = p["delay"]
    elif c == "overspend":
        d["ad_by_platform"][p["platform"]][wk] *= p["mult"]
    elif c == "fx":
        d["fx"][p["from_week"]:] *= p["mult"]
    elif c == "volume":
        for k in d["dtc_refunds_by_sku"]:
            d["dtc_refunds_by_sku"][k][wk] *= p["mult"]
        d["dtc_gross"][wk] *= p["mult"]
        d["dtc_chargebacks"][wk] *= p["mult"]
    elif c == "chargebacks":
        d["dtc_chargebacks"][a] += p["amount"]
    elif c == "fees" and ev["line"] == "dtc_payouts":
        d["dtc_fee_rate"][a:] += p["delta"]
    elif c == "fees" and ev["line"] == "marketplace_payouts":
        d["amz_fee_rate"][a:] += p["delta"]
    elif c == "timing" and ev["line"] in ("inventory", "freight_duty", "fulfillment_3pl", "other_ap"):
        d["bill_due_shift"][p["bill"]] = p["weeks"]
    elif c == "price" and "bill" in p:
        d["bill_price_mult"][p["bill"]] = p["mult"]
    elif c == "price" and "tpl_from_week" in p:
        d["tpl_rate"][p["tpl_from_week"]:] *= p["mult"]
    elif c == "one_off":
        d["one_offs"].append((a, p["counterparty"], p["amount"]))
    else:
        raise ValueError(f"no injector for {ev}")


def seed_for(slug, scenario):
    return int(hashlib.sha256(f"{slug}|{scenario}".encode()).hexdigest()[:8], 16)


def build_scenario(cfgs: dict, events: list, scenario: str) -> dict:
    """Returns {slug: {'forecast', 'counterfactual', 'actual'}} and writes the labels."""
    out = {}
    labels = []
    for slug, cfg in cfgs.items():
        base = noisy_drivers(cfg, seed_for(slug, scenario))
        act_d = copy.deepcopy(base)
        evs = [e for e in events if e["brand"] == slug]
        for e in evs:
            apply_event(cfg, act_d, e)
        fc = forecast(cfg)
        cf = book(cfg, base)
        act = book(cfg, act_d)
        out[slug] = {"forecast": fc, "counterfactual": cf, "actual": act}
        for e in evs:
            lab = dict(e)
            # every line-week this event alone moved by more than half the brand's materiality
            one_d = copy.deepcopy(base)
            apply_event(cfg, one_d, e)
            one = book(cfg, one_d)
            affected = {}
            for line in one.lines:
                diff = one.lines[line] - cf.lines[line]
                wks = [int(w) for w in np.nonzero(np.abs(diff) > cfg["materiality"] / 2)[0]]
                if wks:
                    affected[line] = wks
            lab["affected"] = affected
            lab["cash_impact"] = round(float(np.sum(one.total() - cf.total())), 2)
            lab["impact_on_line"] = round(float(np.sum(one.lines[e["line"]] - cf.lines[e["line"]])), 2)
            lab["max_weekly_cash_shift"] = round(float(np.max(np.abs(one.cash - cf.cash))), 2)
            labels.append(lab)
    LABELS.mkdir(parents=True, exist_ok=True)
    (LABELS / f"{scenario}.json").write_text(json.dumps(labels, indent=1, default=str))
    return out


def load_configs():
    return json.loads((ROOT / "config" / "brands.json").read_text())
