"""The forecast itself: the trough exists, the plan P&L is sane, the workbook matches."""
import numpy as np
import pytest

from world.engine import WEEKS, forecast


def test_bfcm_trough_exists_and_breaks_the_buffer(cfgs):
    cfg = cfgs["fernwood-goods"]
    w, low = forecast(cfg).low_point()
    assert low < cfg["cash_buffer"], "Fernwood's November trough must go under the buffer"
    assert WEEKS[w].month == 11
    assert low > 0, "the trough should be fundable, not an overdraft"


def test_fernwood_plan_net_margin_is_about_five_percent(cfgs):
    p = cfgs["fernwood-goods"]["plan"]
    rev = p["annual_revenue"]
    dtc = rev * p["channel_mix"]["dtc"]
    contribution = rev * p["gross_margin"] - rev * (p["fulfillment_pct_revenue"] + p["payment_fees_pct_revenue"] +
                                                    p["refunds_pct_revenue"]) - dtc * p["ads_pct_dtc"]
    operating = contribution - 26 * p["payroll_biweekly"] - 12 * p["fixed_monthly"]
    assert 0.04 <= operating / rev <= 0.06


def test_cash_roll_is_consistent(cfgs):
    for cfg in cfgs.values():
        fc = forecast(cfg)
        assert np.allclose(fc.cash, cfg["opening_cash"] + np.cumsum(fc.total()))


def test_workbook_matches_code_within_one_percent():
    from sheets.check_xlsx import compare
    try:
        r = compare()
    except SystemExit as e:
        pytest.skip(str(e))
    assert r["max_cash_diff_pct"] < 0.01
    assert abs(r["low_point_sheet"] - r["low_point_code"]) < 0.01 * abs(r["low_point_code"])
