"""Actions: vendor rules hold under every policy; draws are sized and dated."""
from actions.plan import POLICIES, RULES, compare_policies, fund_trough, policy_plan
from world.engine import forecast


def test_no_policy_breaks_a_vendor_rule(dev):
    for slug, b in dev.items():
        for p, r in compare_policies(b["forecast"], b["actual"]).items():
            assert r["rules_broken"] == [], (slug, p, r["rules_broken"])


def test_critical_bills_are_never_planned_late(dev):
    for slug, b in dev.items():
        due = {x["id"]: x for x in b["forecast"].bills}
        for p in POLICIES:
            pw, ds, draws = policy_plan(p, b["forecast"], b["actual"])
            for bid, w in pw.items():
                if due[bid]["criticality"] in ("critical", "high"):
                    assert w <= due[bid]["due_week"], (slug, p, bid)


def test_fernwood_trough_draw_covers_the_gap_in_round_amounts(cfgs):
    cfg = cfgs["fernwood-goods"]
    plan = fund_trough(forecast(cfg))
    inc = RULES["credit_line"]["draw_increment"]
    assert plan["draw"] >= plan["gap"] > 0
    assert plan["draw"] % inc == 0
    assert plan["within_limit"]
    assert plan["repay_week"] is not None and plan["repay_week"] > plan["draw_week"]
