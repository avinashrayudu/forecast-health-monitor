"""
Configures each brand's 13-week forecast from its onboarded ledger.

Reads data/ledgers/<brand>_upload_{1,2}.csv (the labeled cash ledger produced by
dtc-cash-onboarding) and config/overrides.yaml, and writes config/brands.json:
  - weekly levels for Shopify payouts, Amazon deposits and wholesale receipts
  - each line's week-to-week variability (the detector's noise model)
  - payroll calendar and run size, monthly fixed costs, 3PL, sales tax and card spend ratios
  - ad platforms and whether Meta is charged to the bank directly
  - inventory pace (for purchase orders in the window) and credit line balance

Fernwood Goods uses its corrected plan P&L for levels (see docs/fernwood_pnl.md);
its ledger still supplies noise, the payroll calendar and the card schedule.

Built by Avinash Rayudu.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from world.engine import HIST_MULT, MONTH_MULT, WEEK0, week_of

ROOT = Path(__file__).resolve().parent.parent
LEDGERS = ROOT / "data" / "ledgers"
HIST_START = date(2026, 7, 6)          # first full Monday-start week in the ledgers
HIST_END = date(2026, 10, 25)


def load_ledger(slug: str) -> pd.DataFrame:
    parts = [pd.read_csv(LEDGERS / f"{slug}_upload_{u}.csv") for u in (1, 2)]
    df = pd.concat(parts, ignore_index=True)
    df = df[~df["is_duplicate"].astype(bool)].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df[(df["date"] >= HIST_START) & (df["date"] <= HIST_END)]


def weekly(df, labels):
    s = df[df["label"].isin(labels)].copy()
    s["wk"] = [(d - HIST_START).days // 7 for d in s["date"]]
    n = (HIST_END - HIST_START).days // 7 + 1
    out = np.zeros(n)
    for k, v in s.groupby("wk")["amount"].sum().items():
        out[int(k)] = v
    return out


def detrended_cv(x):
    x = np.asarray(x, float)
    if len(x) < 4 or np.mean(np.abs(x)) == 0:
        return 0.10
    t = np.arange(len(x))
    fit = np.polyval(np.polyfit(t, x, 1), t)
    return float(np.clip(np.std(x - fit) / np.mean(np.abs(x)), 0.03, 0.35))


def calibrate(slug: str, ov: dict, defaults: dict) -> dict:
    led = load_ledger(slug)
    kick = yaml.safe_load((LEDGERS / f"{slug}_brand.yaml").read_text())
    bank = led[(led["source"] == "bank") & (led["account"] != "savings")]
    card = led[led["source"] == "card"]
    months = 16 / (52 / 12)                     # 16 history weeks
    oct_to_avg = HIST_MULT / MONTH_MULT[10]     # history in the ledger is flat; treat its level as October
    net_factor = 1 - defaults["refund_rate"] - defaults["fee_rate"] - defaults["chargeback_rate"]

    dtc_w = weekly(bank, ["processor_payout"])
    amz_dep = bank.loc[bank["label"] == "marketplace_payout", "amount"].to_numpy()
    wh_w = weekly(bank, ["wholesale_payout", "wholesale_receipt"])
    oct_dtc = float(np.mean(dtc_w[-4:]))
    cfg = dict(slug=slug, brand=kick["brand"], currency=kick["currency"])
    cfg.update({k: v for k, v in defaults.items() if k not in ("opening_weeks_of_outflow", "buffer_weeks_of_outflow")})
    cfg["dtc_weekly_gross"] = oct_dtc / net_factor * oct_to_avg
    cfg["amz_weekly_sales"] = (float(np.mean(amz_dep[-4:])) / 2 / (1 - defaults["amz_fee_rate"]) * oct_to_avg
                               if len(amz_dep) else 0.0)
    cfg["wh_weekly"] = float(np.mean(wh_w[-6:])) * oct_to_avg
    cfg["noise"] = {"dtc": detrended_cv(dtc_w), "amazon": detrended_cv(amz_dep) if len(amz_dep) > 3 else 0.10,
                    "wholesale": detrended_cv(wh_w) if wh_w.any() else 0.10, "ads": 0.0}
    # payroll calendar: the next runs continue the ledger's every-other-Friday pattern
    pay = bank[bank["label"] == "payroll"].groupby("date")["amount"].sum()
    last = max(pay.index)
    runs = [last + timedelta(days=14 * k) for k in range(1, 9)]
    cfg["payroll_weeks"] = [week_of(d) for d in runs if 0 <= week_of(d) < 13]
    cfg["payroll_run"] = float(-np.median(pay.to_numpy()[-4:]))
    monthly = lambda labs, src=bank: float(-src.loc[src["label"].isin(labs), "amount"].sum() / months)
    month_gross = cfg["dtc_weekly_gross"] * 52 / 12
    cfg["fixed_monthly"] = monthly(["rent", "software_opex"])
    cfg["tpl_pct"] = monthly(["fulfillment_3pl"]) / month_gross
    cfg["sales_tax_rate"] = monthly(["sales_tax"]) / month_gross
    card_ads = card[card["label"] == "ad_spend"]
    bank_ads = bank[bank["label"] == "ad_spend"]
    ad_monthly = float(card_ads["amount"].sum() / months) + float(-bank_ads["amount"].sum() / months)
    cfg["ad_rate"] = ad_monthly / month_gross
    plat = {}
    for desc, amt in zip(card_ads["description"], card_ads["amount"]):
        u = str(desc).upper()
        p = "meta" if "FACEBK" in u or "META" in u else "google" if "GOOGLE" in u else \
            "tiktok" if "TIKTOK" in u else "pinterest" if "PINTEREST" in u else "other"
        plat[p] = plat.get(p, 0.0) + amt
    if len(bank_ads):
        plat["meta"] = plat.get("meta", 0.0) + float(-bank_ads["amount"].sum())
        cfg["meta_direct_debit"] = True
    tot = sum(plat.values()) or 1.0
    cfg["ad_platforms"] = {p: round(v / tot, 4) for p, v in plat.items()}
    cfg["noise"]["ads"] = detrended_cv(weekly(card, ["ad_spend"])) if len(card_ads) else 0.10
    other_card = card[card["label"].isin(["software_opex", "travel_other", "shipping_supplies"])]
    cfg["card_other_weekly"] = float(other_card["amount"].sum() / 16)
    cfg["other_opex_weekly"] = float(-bank.loc[bank["label"] == "bank_fee", "amount"].sum() / 16) + 150.0
    inv_monthly = monthly(["inventory_purchase"])
    fr_ratio = monthly(["freight_duty"]) / max(inv_monthly, 1)
    cfg["purchase_orders"] = [
        {"id": "PO-BFCM-BAL", "vendor": ov.get("inventory_vendor", "main supplier"), "due_week": 1, "amount": round(1.4 * inv_monthly, -2)},
        {"id": "PO-SPRING-DEP", "vendor": ov.get("inventory_vendor", "main supplier"), "due_week": 10, "amount": round(0.5 * inv_monthly, -2)}]
    cfg["freight_invoices"] = [{"id": "FRT-BFCM", "issue_week": 0,
                                "amount": round(fr_ratio * 1.4 * inv_monthly, -2)}]
    draws = float(bank.loc[bank["label"] == "financing_draw", "amount"].sum())
    repaid = float(bank.loc[bank["label"] == "financing_repayment", "amount"].sum())
    cfg["loc_drawn"] = max(0.0, draws + repaid)
    cfg["loc_limit"] = max(4 * cfg["loc_drawn"], 0.06 * cfg["dtc_weekly_gross"] * 52)
    weekly_out = float(-bank.loc[bank["amount"] < 0, "amount"].sum() / 16) - float(
        -bank.loc[bank["label"].isin(["own_account_transfer", "financing_repayment"]) & (bank["amount"] < 0),
                  "amount"].sum() / 16)
    cfg["opening_cash"] = round(defaults["opening_weeks_of_outflow"] * weekly_out, -3)
    cfg["cash_buffer"] = round(defaults["buffer_weeks_of_outflow"] * weekly_out, -3)
    cfg["supplier_currency"] = ov.get("supplier_currency", cfg["currency"])
    cfg["fx_rate"] = ov.get("fx_rate", 1.0)
    cfg["sku_shares"] = ov["skus"]
    cfg["retailers"] = ov.get("retailers", []) if cfg["wh_weekly"] > 0 else []
    for k in ("threepl", "forwarder", "packaging_vendor", "saas_vendor"):
        cfg[k] = ov[k]
    cfg["materiality"] = max(2500.0, 0.015 * (cfg["dtc_weekly_gross"] + 2 * cfg["amz_weekly_sales"] +
                                              cfg["wh_weekly"]))
    cfg["history"] = {"dtc_weekly": dtc_w.round(2).tolist(), "wholesale_weekly": wh_w.round(2).tolist(),
                      "amazon_deposits": [round(float(x), 2) for x in amz_dep]}
    if "plan" in ov:
        apply_plan(cfg, ov["plan"])
    return cfg


def apply_plan(cfg, p):
    """Fernwood: levels from the corrected plan P&L instead of the ledger."""
    base_week = p["annual_revenue"] / 12.35 * 12 / 52 * HIST_MULT       # an average history week
    mix = p["channel_mix"]
    cfg["dtc_weekly_gross"] = base_week * mix["dtc"]
    cfg["amz_weekly_sales"] = base_week * mix["amazon"]
    cfg["wh_weekly"] = base_week * mix["wholesale"]
    cfg["refund_rate"] = p["refunds_pct_revenue"]
    cfg["refund_rate_jan"] = p["refunds_pct_january"]
    cfg["fee_rate"] = p["payment_fees_pct_revenue"]
    cfg["ad_rate"] = p["ads_pct_dtc"]
    cfg["ad_platforms"] = p["ad_platforms"]
    cfg["meta_direct_debit"] = False
    cfg["payroll_run"] = float(p["payroll_biweekly"])
    # the plan's $34K of monthly fixed costs includes $10K of software charged to the card
    cfg["fixed_monthly"] = float(p["fixed_monthly"] - p["card_software_monthly"])
    cfg["card_other_weekly"] = p["card_software_monthly"] * 12 / 52
    cfg["tpl_pct"] = p["fulfillment_pct_revenue"] / mix["dtc"]          # 3PL bills on DTC orders
    cfg["sales_tax_rate"] = p["sales_tax_rate"]
    cfg["opening_cash"] = float(p["opening_cash"])
    cfg["cash_buffer"] = float(p["cash_buffer"])
    cfg["loc_limit"] = float(p["loc_limit"])
    cfg["loc_drawn"] = float(p["loc_drawn"])
    cfg["purchase_orders"] = p["purchase_orders"]
    cfg["freight_invoices"] = p["freight_invoices"]
    cfg["plan"] = p
    cfg["materiality"] = max(2500.0, 0.015 * base_week)


def main():
    ov = yaml.safe_load((ROOT / "config" / "overrides.yaml").read_text())
    out = {}
    for slug, o in ov["brands"].items():
        out[slug] = calibrate(slug, o, ov["defaults"])
        c = out[slug]
        print(f"  {slug:<20} DTC/wk {c['dtc_weekly_gross']:>10,.0f}  AMZ/wk {c['amz_weekly_sales']:>8,.0f}  "
              f"WH/wk {c['wh_weekly']:>8,.0f}  noise dtc {c['noise']['dtc']:.3f}  opening {c['opening_cash']:>10,.0f}  "
              f"buffer {c['cash_buffer']:>9,.0f}")
    (ROOT / "config" / "brands.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
