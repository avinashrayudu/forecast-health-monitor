"""The monitor: attribution adds up, it finds a known event, and it cannot see the answers."""
import ast
from pathlib import Path

import numpy as np

from monitor.attribute import components
from monitor.detect import scan
from monitor.reforecast import roll_forward
from world.engine import CASH_LINES, N_WEEKS, WATCH_LINES

ROOT = Path(__file__).resolve().parent.parent


def test_driver_components_sum_to_the_variance(dev):
    for slug, b in dev.items():
        fc, act = b["forecast"], b["actual"]
        for line in CASH_LINES + WATCH_LINES:
            comps, sig, _ = components(fc, act, line)
            total = sum(comps.values(), np.zeros(N_WEEKS))
            assert np.allclose(total, act.lines[line] - fc.lines[line], atol=0.01), (slug, line)


def test_refund_spike_is_found_and_named(dev):
    b = dev["fernwood-goods"]
    found = [f for f in scan(b["forecast"], b["actual"]) if f["cause"] == "refunds"]
    assert found and "FW-2201" in found[0]["explanation"]
    assert found[0]["detected_week"] <= 2


def test_roll_forward_with_all_weeks_equals_actuals(dev):
    for b in dev.values():
        assert np.allclose(roll_forward(b["forecast"], b["actual"], N_WEEKS - 1).cash, b["actual"].cash)


def test_monitor_and_actions_never_read_event_labels():
    banned = {"world.inject_events", "world.holdout_events", "inject_events", "holdout_events"}
    for folder in ("monitor", "actions"):
        for path in (ROOT / folder).glob("*.py"):
            src = path.read_text()
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    assert node.module not in banned, path
                if isinstance(node, ast.Import):
                    assert not {a.name for a in node.names} & banned, path
            docs = {id(n.body[0].value) for n in ast.walk(tree)
                    if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                    and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
                    assert "labels" not in node.value, f"{path} refers to the label files"
