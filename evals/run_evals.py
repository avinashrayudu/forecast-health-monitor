"""
Scores the monitor against hidden labels.

  python -m evals.run_evals             development events + noise-only worlds
  python -m evals.run_evals --holdout   adds the holdout events (written after the freeze)

Detection: an event counts as detected when any finding on its brand overlaps a
line-week the event moved (world/labels/<scenario>.json, "affected"). The earliest
matching finding is the diagnosis: attribution is correct when its cause matches
the event's cause. Lag is that finding's week minus the event's first week.
Findings that match no event are false alarms. Noise-only worlds have no events,
so every finding there is a false alarm.

Reforecast: at each week a finding is raised, the remaining-window low point and
ending cash are predicted two ways (roll forward vs roll forward plus rules) and
compared with what actually happened.

AP policies: four bill-payment policies scored on the actual weeks, with each
brand's credit line as configured and again with only $50K of headroom.

Built by Avinash Rayudu.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import statistics as st
from pathlib import Path

import numpy as np

from actions.plan import POLICIES, compare_policies
from monitor.detect import PARAMS, scan
from monitor.reforecast import reforecast, roll_forward
from world.engine import CASH_LINES, N_WEEKS, WATCH_LINES, book
from world.inject_events import DEV_EVENTS, build_scenario, load_configs

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "evals" / "results"
NOISE_SEEDS = [f"noise{i}" for i in range(5)]


def match(findings, labels):
    by_event = {l["id"]: [] for l in labels}
    unmatched = []
    for f in findings:
        weeks = set(range(f["first_week"], f["last_week"] + 1))
        hit = [l for l in labels if l["brand"] == f["brand"] and weeks & set(l["affected"].get(f["line"], []))]
        for l in hit:
            by_event[l["id"]].append(f)
        if not hit:
            unmatched.append(f)
    return by_event, unmatched


def score_detection(books, labels):
    findings = []
    for slug, b in books.items():
        findings += scan(b["forecast"], b["actual"])
    by_event, unmatched = match(findings, labels)
    rows = []
    for l in labels:
        fs = sorted(by_event[l["id"]], key=lambda f: (f["detected_week"], -abs(f["amount"])))
        first = fs[0] if fs else None
        rows.append(dict(id=l["id"], brand=l["brand"], cause=l["cause"], start_week=l["start"],
                         cash_impact=l["cash_impact"], detected=bool(fs),
                         diagnosed_cause=first["cause"] if first else None,
                         attribution_correct=bool(first and first["cause"] == l["cause"]),
                         lag_weeks=(first["detected_week"] - l["start"]) if first else None,
                         first_finding=first["explanation"] if first else None, findings=len(fs)))
    n = len(labels)
    det = [r for r in rows if r["detected"]]
    lags = [r["lag_weeks"] for r in det]
    matched = len(findings) - len(unmatched)
    brand_weeks = len(books) * N_WEEKS
    return dict(
        events=n, detected=len(det), recall=round(len(det) / n, 3) if n else None,
        attribution_correct=sum(r["attribution_correct"] for r in rows),
        attribution_accuracy=round(sum(r["attribution_correct"] for r in rows) / n, 3) if n else None,
        median_lag_weeks=st.median(lags) if lags else None, max_lag_weeks=max(lags) if lags else None,
        findings=len(findings), matched_findings=matched,
        precision=round(matched / len(findings), 3) if findings else None,
        false_alarms=len(unmatched), false_alarms_per_100_brand_weeks=round(100 * len(unmatched) / brand_weeks, 2),
        events_detail=rows, false_alarm_detail=[{k: f[k] for k in ("brand", "line", "component", "detected_week",
                                                                    "amount", "explanation")} for f in unmatched])


def score_reforecast(books):
    out = []
    for slug, b in books.items():
        fc, act = b["forecast"], b["actual"]
        weeks = sorted({f["detected_week"] for f in scan(fc, act)})
        for t in weeks:
            if t > N_WEEKS - 3:
                continue
            fs = scan(fc, act, t)
            rest = slice(t + 1, N_WEEKS)
            r0, r1 = roll_forward(fc, act, t), reforecast(fc, act, t, fs)
            a_low, a_end = float(act.cash[rest].min()), float(act.cash[-1])
            out.append(dict(brand=slug, week=t,
                            low_err_roll=abs(float(r0.cash[rest].min()) - a_low),
                            low_err_rules=abs(float(r1.cash[rest].min()) - a_low),
                            end_err_roll=abs(float(r0.cash[-1]) - a_end),
                            end_err_rules=abs(float(r1.cash[-1]) - a_end)))
    if not out:
        return dict(points=0)
    agg = {k: round(float(np.mean([o[k] for o in out])), 0) for k in
           ("low_err_roll", "low_err_rules", "end_err_roll", "end_err_rules")}
    agg["points"] = len(out)
    agg["rules_better_or_equal_low"] = sum(o["low_err_rules"] <= o["low_err_roll"] + 1 for o in out)
    agg["rules_better_or_equal_end"] = sum(o["end_err_rules"] <= o["end_err_roll"] + 1 for o in out)
    return agg


def score_forecast(books):
    rows = []
    for slug, b in books.items():
        fw, fl = b["forecast"].low_point()
        aw, al = b["actual"].low_point()
        rows.append(dict(brand=slug, forecast_low=round(fl), actual_low=round(al), forecast_low_week=fw,
                         actual_low_week=aw, abs_err=round(abs(fl - al)), pct_of_buffer=round(
                abs(fl - al) / b["forecast"].cfg["cash_buffer"], 3)))
    return dict(mean_abs_low_point_error=round(float(np.mean([r["abs_err"] for r in rows]))),
                low_week_hit_rate=round(float(np.mean([r["forecast_low_week"] == r["actual_low_week"]
                                                       for r in rows])), 2), brands=rows)


def score_policies(books, tight=False):
    tot = {p: dict(discounts=0.0, interest=0.0, net=0.0, unplanned_breach_weeks=0, worst_unplanned_gap=0.0,
                   overdraft_weeks=0, rules_broken=0) for p in POLICIES}
    for slug, b in books.items():
        fc, act = b["forecast"], b["actual"]
        if tight:
            cfg = copy.deepcopy(fc.cfg)
            cfg["loc_limit"] = cfg["loc_drawn"] + 50000
            fc, act = book(cfg, copy.deepcopy(fc.drivers)), book(cfg, copy.deepcopy(act.drivers))
        for p, x in compare_policies(fc, act).items():
            t = tot[p]
            for k in ("discounts", "interest", "net"):
                t[k] += x[k]
            t["unplanned_breach_weeks"] += x["unplanned_breach_weeks"]
            t["overdraft_weeks"] += x["overdraft_weeks"]
            t["worst_unplanned_gap"] = max(t["worst_unplanned_gap"], x["worst_unplanned_gap"])
            t["rules_broken"] += len(x["rules_broken"])
    return {p: {k: (round(v, 0) if isinstance(v, float) else v) for k, v in t.items()} for p, t in tot.items()}


def run_scenario(cfgs, events, name, policies=True):
    books = build_scenario(cfgs, events, name)
    labels = json.loads((ROOT / "world" / "labels" / f"{name}.json").read_text())
    res = dict(scenario=name, detection=score_detection(books, labels), reforecast=score_reforecast(books),
               forecast=score_forecast(books))
    if policies:
        res["ap_policies"] = score_policies(books)
        res["ap_policies_tight_credit"] = score_policies(books, tight=True)
    return res


def freeze_status():
    fz = ROOT / "evals" / "FREEZE.json"
    if not fz.exists():
        return "no freeze recorded"
    frozen = json.loads(fz.read_text())
    bad = [p for p, h in frozen["files"].items()
           if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h]
    return "monitor unchanged since freeze" if not bad else f"CHANGED since freeze: {bad}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    cfgs = load_configs()
    RES.mkdir(parents=True, exist_ok=True)
    results = {"detector_params": PARAMS, "freeze": freeze_status()}
    results["dev"] = run_scenario(cfgs, DEV_EVENTS, "dev")
    noise = [run_scenario(cfgs, [], s, policies=(s == NOISE_SEEDS[0])) for s in NOISE_SEEDS]
    fa = sum(n["detection"]["false_alarms"] for n in noise)
    bw = len(cfgs) * N_WEEKS * len(NOISE_SEEDS)
    lw = bw * len(CASH_LINES + WATCH_LINES)
    results["noise_only"] = dict(worlds=len(NOISE_SEEDS), brand_weeks=bw, line_weeks=lw, false_alarms=fa,
                                 per_100_brand_weeks=round(100 * fa / bw, 2), per_100_line_weeks=round(100 * fa / lw, 3),
                                 per_brand_per_13_weeks=round(fa / (len(cfgs) * len(NOISE_SEEDS)), 2),
                                 detail=[d for n in noise for d in n["detection"]["false_alarm_detail"]],
                                 forecast_mean_abs_low_point_error=round(float(np.mean(
                                     [n["forecast"]["mean_abs_low_point_error"] for n in noise]))),
                                 ap_policies=noise[0]["ap_policies"],
                                 ap_policies_tight_credit=noise[0]["ap_policies_tight_credit"])
    if args.holdout:
        from world.holdout_events import HOLDOUT_EVENTS
        results["holdout"] = run_scenario(cfgs, HOLDOUT_EVENTS, "holdout")
    out = RES / f"results{args.tag}.json"
    out.write_text(json.dumps(results, indent=1, default=float))
    md = render_md(results)
    (RES / f"results{args.tag}.md").write_text(md)
    print(md)


def render_md(R):
    L = ["# Evaluation results", "", f"Detector: z = {R['detector_params']['z']}, windows "
         f"{list(R['detector_params']['windows'])} weeks. Freeze check: {R['freeze']}.", ""]
    sets = [("Development events", R["dev"])] + ([("Holdout events (written after the freeze)", R["holdout"])]
                                                  if "holdout" in R else [])
    L += ["## Detection and diagnosis", "", "| set | events | detected | correct cause | median lag (wks) | "
          "findings | precision | false alarms |", "|---|---|---|---|---|---|---|---|"]
    for name, s in sets:
        d = s["detection"]
        L.append(f"| {name} | {d['events']} | {d['detected']} ({d['recall']:.0%}) | {d['attribution_correct']} "
                 f"({d['attribution_accuracy']:.0%}) | {d['median_lag_weeks']} | {d['findings']} | "
                 f"{d['precision']:.0%} | {d['false_alarms']} |")
    n = R["noise_only"]
    L += ["", f"Noise-only worlds ({n['worlds']} worlds, {n['brand_weeks']} brand-weeks, {n['line_weeks']} line-weeks, "
          f"no events): {n['false_alarms']} false alarms, {n['per_100_brand_weeks']} per 100 brand-weeks, "
          f"{n['per_brand_per_13_weeks']} per brand per 13 weeks.", ""]
    for name, s in sets:
        L += [f"### {name}", "", "| event | brand | cause | detected | diagnosed as | lag | first finding |",
              "|---|---|---|---|---|---|---|"]
        for r in s["detection"]["events_detail"]:
            L.append(f"| {r['id']} | {r['brand']} | {r['cause']} | {'yes' if r['detected'] else 'no'} | "
                     f"{r['diagnosed_cause'] or '-'} | {r['lag_weeks'] if r['lag_weeks'] is not None else '-'} | "
                     f"{(r['first_finding'] or '-').replace('|', '/')} |")
        if s["detection"]["false_alarm_detail"]:
            L += ["", "False alarms:", ""] + [f"- {f['brand']}, {f['line']} ({f['component']}), week "
                                             f"{f['detected_week']}: {f['explanation']}"
                                             for f in s["detection"]["false_alarm_detail"]]
        L.append("")
    L += ["## Reforecast after a finding", "", "Mean absolute error at the weeks a finding was raised, against what "
          "actually happened.", "", "| set | points | low point: roll forward | low point: with rules | "
          "ending cash: roll forward | ending cash: with rules |", "|---|---|---|---|---|---|"]
    for name, s in sets:
        r = s["reforecast"]
        L.append(f"| {name} | {r['points']} | ${r['low_err_roll']:,.0f} | ${r['low_err_rules']:,.0f} | "
                 f"${r['end_err_roll']:,.0f} | ${r['end_err_rules']:,.0f} |")
    L += ["", "## Week-0 forecast vs actual low point", ""]
    for name, s in sets:
        f = s["forecast"]
        L.append(f"- {name}: mean absolute low-point error ${f['mean_abs_low_point_error']:,.0f}; low week right "
                 f"for {f['low_week_hit_rate']:.0%} of brands.")
    L.append(f"- Noise-only worlds: mean absolute low-point error ${n['forecast_mean_abs_low_point_error']:,.0f}.")
    L += ["", "## Bill-payment policies on the actual weeks (all 10 brands, 13 weeks)", ""]
    for name, key, src in [(sets[0][0], "ap_policies", sets[0][1]),
                           (sets[0][0] + ", $50K credit headroom", "ap_policies_tight_credit", sets[0][1])] + \
            ([(sets[1][0], "ap_policies", sets[1][1]),
              (sets[1][0] + ", $50K credit headroom", "ap_policies_tight_credit", sets[1][1])] if len(sets) > 1 else []) + \
            [("Noise-only world 0", "ap_policies", n), ("Noise-only world 0, $50K credit headroom",
                                                        "ap_policies_tight_credit", n)]:
        L += [f"**{name}**", "", "| policy | discounts | interest | net | unplanned breach weeks | worst unplanned gap | "
              "rules broken |", "|---|---|---|---|---|---|---|"]
        for p, x in src[key].items():
            L.append(f"| {p} | ${x['discounts']:,.0f} | ${x['interest']:,.0f} | ${x['net']:,.0f} | "
                     f"{x['unplanned_breach_weeks']} | ${x['worst_unplanned_gap']:,.0f} | {x['rules_broken']} |")
        L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
