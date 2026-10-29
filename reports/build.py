"""
Builds the HTML reports from a run of the development scenario.

  reports/cash_brief_fernwood.html    Fernwood's weekly Cash Brief, Monday Nov 16 (actuals through Nov 15)
  reports/portfolio_10_brands.html    10-brand health board, replayable week by week
  reports/index.html                  landing page with the evaluation results

Every number on these pages comes from the code paths the evals score: the
monitor's findings, the reforecast, and the monitored bill-payment policy.

Built by Avinash Rayudu. All brands and numbers are synthetic.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np

from actions.plan import RULES, fund_trough, headroom, monitored_steps, need, sweep_vs_paydown, wk
from monitor.attribute import components
from world.engine import CASH_LINES, INFLOW_LINES, N_WEEKS, WEEKS
from world.inject_events import DEV_EVENTS, build_scenario, load_configs

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports"
BRIEF_WEEK = 3                         # Monday Nov 16: actuals through Nov 15

LINE_NAMES = {"dtc_payouts": "Shopify payouts", "marketplace_payouts": "Amazon settlements",
              "wholesale_receipts": "Wholesale receipts", "payroll": "Payroll", "inventory": "Inventory POs",
              "freight_duty": "Freight and duty", "fulfillment_3pl": "3PL", "other_ap": "Packaging and software",
              "card_autopay": "Card autopay", "ad_direct": "Meta direct debit", "fixed_costs": "Fixed costs",
              "sales_tax": "Sales tax", "debt_service": "Credit line interest", "other_opex": "Bank fees and other",
              "ad_spend_accrual": "Ad spend on the card (not cash yet)"}

CSS = """
:root{--bg:#f7f7f5;--card:#ffffff;--ink:#1c1d1f;--muted:#5d6168;--line:#e3e3df;--accent:#2f5d8a;
--red:#b3261e;--amber:#9a6700;--green:#2e7d4f;--red-bg:#fbeceb;--amber-bg:#fdf3dc;--green-bg:#e8f4ec;
--plan:#2f5d8a;--fc:#9aa3ad;--act:#1c1d1f;--buf:#b3261e}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141517;--card:#1d1f22;--ink:#ececea;
--muted:#a4a8ae;--line:#33363b;--accent:#8db8e3;--red:#f08a83;--amber:#e6b34d;--green:#7cc79a;--red-bg:#3a1f1e;
--amber-bg:#3a3020;--green-bg:#1f3327;--plan:#8db8e3;--fc:#6b737c;--act:#ececea;--buf:#f08a83}}
:root[data-theme="dark"]{--bg:#141517;--card:#1d1f22;--ink:#ececea;--muted:#a4a8ae;--line:#33363b;--accent:#8db8e3;
--red:#f08a83;--amber:#e6b34d;--green:#7cc79a;--red-bg:#3a1f1e;--amber-bg:#3a3020;--green-bg:#1f3327;
--plan:#8db8e3;--fc:#6b737c;--act:#ececea;--buf:#f08a83}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:1040px;margin:0 auto;padding:28px 16px 64px}
.card p,.action{overflow-wrap:anywhere}table.wide{min-width:880px}td.w{min-width:200px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.01em}h2{font-size:18px;margin:32px 0 10px}
h3{font-size:15px;margin:18px 0 6px}
.sub{color:var(--muted);margin:0 0 20px}.card{background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:18px 20px;margin:12px 0;overflow-x:auto}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.kpi .v{font-size:24px;font-weight:650;font-variant-numeric:tabular-nums}.kpi .l{color:var(--muted);font-size:13px}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}
td.n,th.n{text-align:right;white-space:nowrap}.neg{color:var(--red)}.muted{color:var(--muted)}
.pill{display:inline-block;padding:1px 9px;border-radius:999px;font-size:12px;font-weight:600}
.red{background:var(--red-bg);color:var(--red)}.amber{background:var(--amber-bg);color:var(--amber)}
.green{background:var(--green-bg);color:var(--green)}
.action{border-left:4px solid var(--accent);padding:10px 14px;margin:10px 0;background:var(--card);
border-radius:0 8px 8px 0;border-top:1px solid var(--line);border-right:1px solid var(--line);
border-bottom:1px solid var(--line)}
.action b{display:block;margin-bottom:2px}.scroll{overflow-x:auto}
.legend{display:flex;gap:16px;flex-wrap:wrap;color:var(--muted);font-size:13px;margin-top:6px}
.legend i{display:inline-block;width:18px;height:3px;vertical-align:middle;margin-right:6px}
footer{color:var(--muted);font-size:13px;margin-top:40px;border-top:1px solid var(--line);padding-top:14px}
a{color:var(--accent)}input[type=range]{width:100%}
.wk{font-weight:650;font-size:18px}.small{font-size:13px}
"""


def money(x, sign=False):
    s = f"${abs(x):,.0f}"
    if x < 0:
        return f"({s})" if not sign else f"-{s}"
    return f"+{s}" if sign and x > 0 else s


def page(title, body, desc="", wide=False):
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport "
            f"content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title>"
            f"<meta name=description content='{html.escape(desc)}'><style>{CSS}</style></head><body>"
            f"<main{' style=\"max-width:1240px\"' if wide else ''}>{body}"
            f"<footer>Built by Avinash Rayudu. All brands, vendors and numbers are synthetic. Source: "
            f"<a href='https://github.com/avinashrayudu/forecast-health-monitor'>forecast-health-monitor</a>."
            f"</footer></main></body></html>")


def line_chart(series, buffer, width=960, height=260, start_week=0, marks=None):
    """series: list of (label, values, css var, dashed, from_week)."""
    pad_l, pad_r, pad_t, pad_b = 64, 16, 14, 30
    allv = [v for _, vals, _, _, fw in series for v in vals] + [buffer, 0]
    lo, hi = min(allv), max(allv)
    span = hi - lo or 1
    lo -= span * 0.05
    hi += span * 0.08
    X = lambda w: pad_l + (w - start_week) * (width - pad_l - pad_r) / (N_WEEKS - 1 - start_week)
    Y = lambda v: pad_t + (hi - v) * (height - pad_t - pad_b) / (hi - lo)
    g = [f"<svg viewBox='0 0 {width} {height}' width='100%' role='img' aria-label='cash path chart'>"]
    step = 10 ** int(np.log10(max(1, (hi - lo) / 4)))
    step = step * (5 if (hi - lo) / step > 20 else 2 if (hi - lo) / step > 8 else 1)
    v = (lo // step + 1) * step
    while v < hi:
        g.append(f"<line x1={pad_l} x2={width - pad_r} y1={Y(v):.1f} y2={Y(v):.1f} stroke='var(--line)'/>"
                 f"<text x={pad_l - 8} y={Y(v) + 4:.1f} text-anchor=end font-size=11 fill='var(--muted)'>"
                 f"${v / 1000:,.0f}K</text>")
        v += step
    for w in range(start_week, N_WEEKS):
        if (w - start_week) % 2 == 0 or N_WEEKS - start_week <= 7:
            g.append(f"<text x={X(w):.1f} y={height - 10} text-anchor=middle font-size=11 fill='var(--muted)'>"
                     f"{WEEKS[w].strftime('%b %-d')}</text>")
    g.append(f"<line x1={pad_l} x2={width - pad_r} y1={Y(buffer):.1f} y2={Y(buffer):.1f} stroke='var(--buf)' "
             f"stroke-dasharray='4 4' stroke-width=1.5 /><text x={width - pad_r} y={Y(buffer) - 5:.1f} "
             f"text-anchor=end font-size=11 fill='var(--buf)'>buffer {money(buffer)}</text>")
    for label, vals, color, dashed, fw in series:
        pts = " ".join(f"{X(fw + i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
        g.append(f"<polyline points='{pts}' fill=none stroke='var({color})' stroke-width=2.4 "
                 f"{'stroke-dasharray=\"6 4\"' if dashed else ''} stroke-linejoin=round />")
    for (w, v, text) in (marks or []):
        g.append(f"<circle cx={X(w):.1f} cy={Y(v):.1f} r=4.5 fill='var(--red)'/><text x={X(w) + 8:.1f} "
                 f"y={Y(v) + 4:.1f} font-size=12 fill='var(--red)'>{html.escape(text)}</text>")
    g.append("</svg>")
    return "".join(g)


def spark(actual, plan, buffer, t, width=130, height=36):
    vals = list(actual) + list(plan)
    lo, hi = min(vals + [buffer]), max(vals + [buffer])
    span = hi - lo or 1
    X = lambda w: 2 + w * (width - 4) / (N_WEEKS - 1)
    Y = lambda v: 3 + (hi - v) * (height - 6) / span
    a = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(actual))
    p = " ".join(f"{X(t + i):.1f},{Y(v):.1f}" for i, v in enumerate(plan))
    return (f"<svg viewBox='0 0 {width} {height}' width={width} height={height}>"
            f"<line x1=0 x2={width} y1={Y(buffer):.1f} y2={Y(buffer):.1f} stroke='var(--buf)' stroke-dasharray='3 3'/>"
            + (f"<polyline points='{a}' fill=none stroke='var(--act)' stroke-width=1.8 />" if len(actual) > 1 else "")
            + f"<polyline points='{p}' fill=none stroke='var(--plan)' stroke-width=1.8 stroke-dasharray='4 3'/></svg>")


# ------------------------------------------------------------------------------------------- data
def run():
    cfgs = load_configs()
    books = build_scenario(cfgs, DEV_EVENTS, "dev")
    steps = {s: monitored_steps(b["forecast"], b["actual"]) for s, b in books.items()}
    return cfgs, books, steps


def status_of(cfg, plan, t, findings_new):
    buf = cfg["cash_buffer"]
    rest = plan.cash[t:]
    low = float(rest.min())
    low_w = t + int(np.argmin(rest))
    if low < buf and low_w - t <= 1:
        return "red", "Under the buffer this week or next"
    if low < buf:
        return "amber", f"Under the buffer in the week of {wk(low_w)}"
    if low < 1.15 * buf:
        return "amber", "Within 15% of the buffer"
    if any(abs(f["amount"]) >= 2 * cfg["materiality"] for f in findings_new):
        return "amber", "New drift found"
    return "green", "On track"


def snapshot(cfgs, books, steps, t):
    rows = []
    for slug, st in steps.items():
        cfg, s = cfgs[slug], st[t]
        plan, act, fc = s["plan"], books[slug]["actual"], books[slug]["forecast"]
        new = [f for f in s["findings"] if f["detected_week"] == t - 1]
        status, why = status_of(cfg, plan, t, new)
        rest = plan.cash[t:]
        low_w = t + int(np.argmin(rest))
        rows.append(dict(
            slug=slug, brand=cfg["brand"], status=status, why=why,
            cash=float(act.cash[t - 1]) if t > 0 else cfg["opening_cash"], buffer=cfg["cash_buffer"],
            low=float(rest.min()), low_week=wk(low_w), draw=s["draw"], headroom=headroom(cfg),
            last_week_var=float(act.total()[t - 1] - fc.total()[t - 1]) if t > 0 else 0.0,
            new=[f["explanation"] for f in new],
            open=[f["explanation"] for f in s["findings"] if t - 4 <= f["detected_week"] < t - 1],
            discounts_now=s["discounts_now"],
            spark=spark(act.cash[:t], plan.cash[t:], cfg["cash_buffer"], t)))
    order = {"red": 0, "amber": 1, "green": 2}
    return sorted(rows, key=lambda r: (order[r["status"]], r["low"] / r["buffer"]))


# ------------------------------------------------------------------------------------------- variance bridge
def variance_bridge(fc, act, t):
    """Week-0 forecast closing cash to actual closing cash after t weeks, one step per line and driver.
    The steps come from monitor.attribute.components, so they sum to the difference exactly."""
    steps = []
    for l in CASH_LINES:
        comps, _, _ = components(fc, act, l)
        for k, c in comps.items():
            v = float(np.sum(c[:t]))
            if abs(v) >= 1:
                steps.append((f"{LINE_NAMES[l]}: {k.replace('_', ' ')}", v))
    start, end = float(fc.cash[t - 1]), float(act.cash[t - 1])
    other = end - start - sum(v for _, v in steps)
    if abs(other) >= 1:
        steps.append(("Rounding", other))
    return start, end, sorted(steps, key=lambda x: x[1])


def bridge_html(start, end, steps, t):
    mx = max(abs(v) for _, v in steps) or 1.0
    rows = "".join(
        f"<tr><td>{html.escape(n)}</td><td style='width:45%'><div style='height:12px;width:{100 * abs(v) / mx:.1f}%;"
        f"background:var({'--red' if v < 0 else '--green'})'></div></td>"
        f"<td class='n {'neg' if v < 0 else ''}'>{money(v, True)}</td></tr>" for n, v in steps)
    return (f"<table><tr><th>Step</th><th></th><th class=n>Amount</th></tr>"
            f"<tr><td><b>Week-0 forecast, closing cash in the week of {wk(t - 1)}</b></td><td></td><td class=n><b>{money(start)}"
            f"</b></td></tr>{rows}<tr><td><b>Actual closing cash</b></td><td></td><td class=n><b>{money(end)}</b></td></tr>"
            f"</table>")


# ------------------------------------------------------------------------------------------- brief
def brief(cfgs, books, steps):
    t = BRIEF_WEEK
    slug = "fernwood-goods"
    cfg = cfgs[slug]
    fc, act = books[slug]["forecast"], books[slug]["actual"]
    s = steps[slug][t]
    plan = s["plan"]
    buf = cfg["cash_buffer"]
    low_w = t + int(np.argmin(plan.cash[t:]))
    low = float(plan.cash[low_w])
    draw = s["draw"]
    nxt = steps[slug][t + 1]
    inc = RULES["credit_line"]["draw_increment"]
    needs = need(plan.cash, buf, inc, s["margin"])
    repay_w = next((w for w in range(t + 1, N_WEEKS) if needs[w] == 0), None)
    weeks_out = (repay_w or N_WEEKS) - t
    interest = draw * cfg["loc_apr"] * weeks_out / 52
    bills_by_id = {b["id"]: b for b in plan.bills}
    # what lands this week
    week_lines = sorted(((LINE_NAMES[l], float(plan.lines[l][t])) for l in CASH_LINES if abs(plan.lines[l][t]) > 1),
                        key=lambda x: x[1])
    outs = [(n, v) for n, v in week_lines if v < 0]
    ins = [(n, v) for n, v in week_lines if v > 0]
    big_bills = [b for b in plan.bills if b["pay_week"] == t]
    # variance so far (weeks 0..t-1), by line and driver
    var_rows = []
    for l in CASH_LINES:
        v = float(np.sum(act.lines[l][:t] - fc.lines[l][:t]))
        if abs(v) < 250:
            continue
        comps, _, _ = components(fc, act, l)
        parts = sorted(((k, float(np.sum(c[:t]))) for k, c in comps.items() if abs(np.sum(c[:t])) >= 250),
                       key=lambda x: x[1])
        var_rows.append((LINE_NAMES[l], v, ", ".join(f"{k.replace('_', ' ')} {money(x, True)}" for k, x in parts)))
    total_var = float(np.sum(act.total()[:t] - fc.total()[:t]))
    b_start, b_end, b_steps = variance_bridge(fc, act, t)
    bridge = bridge_html(b_start, b_end, b_steps, t)
    findings = s["findings"]
    tpl = [b for b in s["discounts_now"]]
    tpl_txt = ""
    for bid in tpl:
        b = bills_by_id[bid]
        save = b["amount"] * b["fx"] * b["discount_pct"]
        extra_int = b["amount"] * (1 - b["discount_pct"]) * cfg["loc_apr"] * max(1, b["due_week"] - t) / 52
        tpl_txt += (f"<div class=action><b>Pay {bid} ({html.escape(b['vendor'])}) this week and take the "
                    f"{b['discount_pct']:.0%} early-pay discount.</b>{money(b['amount'])} due the week of "
                    f"{wk(b['due_week'])}; paying now saves {money(save)}. It lands in the trough, so it is funded "
                    f"from the draw: at most about {money(extra_int)} of interest even if it stayed on the line "
                    f"until the due date. Discount beats the cost of the cash, so the plan takes it.</div>")
    sweep = sweep_vs_paydown(plan, low_w + 1)
    original_low = fc.low_point()
    chart = line_chart([
        ("Week-0 forecast", fc.cash, "--fc", True, 0),
        ("Actual", act.cash[:t], "--act", False, 0),
        ("Reforecast (this plan, before the draw)", plan.cash[t - 1:], "--plan", True, t - 1),
    ], buf, marks=[(low_w, low, f"{money(low)} week of {wk(low_w)}")])
    find_html = "".join(
        f"<tr><td>{wk(f['detected_week'])}</td><td>{html.escape(LINE_NAMES.get(f['line'], f['line']))}</td>"
        f"<td>{html.escape(f['cause'].replace('_', ' '))}</td><td>{html.escape(f['explanation'])}</td>"
        f"<td class=n>{money(f['amount'], True)}</td></tr>" for f in findings)
    body = f"""
<p class=sub>Fernwood Goods · Weekly Cash Brief</p>
<h1>Week of {WEEKS[t].strftime('%B %-d, %Y')}</h1>
<p class=sub>Actuals through {(WEEKS[t] - __import__('datetime').timedelta(days=1)).strftime('%b %-d')}.
13-week direct cash forecast, refreshed every Monday. Synthetic brand.</p>
<div class=kpis>
<div class=kpi><div class=l>Cash at Friday close</div><div class=v>{money(act.cash[t - 1])}</div></div>
<div class=kpi><div class=l>Low point this window</div><div class="v neg">{money(low)}</div>
<div class=l>week of {wk(low_w)}, {money(buf - low)} under the {money(buf)} buffer</div></div>
<div class=kpi><div class=l>Draw this week</div><div class=v>{money(draw)}</div>
<div class=l>repay week of {wk(repay_w) if repay_w is not None else 'after the window'}</div></div>
<div class=kpi><div class=l>Forecast vs actual so far</div><div class=v>{money(total_var, True)}</div>
<div class=l>{t} weeks of actuals</div></div>
</div>

<h2>What to do this week</h2>
<div class=action><b>Draw {money(draw)} on the credit line on Monday, before the purchase-order wire.</b>
The reforecast puts closing cash at {money(low)} this week. The draw covers the {money(buf - low)} gap plus a
{money(s['margin'][t])} cushion for receipts not yet in (1.65 standard deviations of a normal week). It fits the
line: {money(headroom(cfg))} of headroom. Repay in the week of {wk(repay_w) if repay_w is not None else '-'},
when BFCM payouts land. Interest is about {money(interest)} at {cfg['loc_apr']:.0%} APR.</div>
{tpl_txt}
<div class=action><b>Pay the BFCM bills on their due dates; nothing critical moves.</b>
{', '.join(f"{html.escape(b['id'])} ({html.escape(b['vendor'])}) {money(b['amount'] * b['fx'])}" for b in big_bills if b['criticality'] in ('critical', 'high') and b['id'] not in s['discounts_now'])}.
The vendor rules never allow inventory, freight or 3PL to be paid late.</div>
<div class=action><b>After the trough: pay down the line before sweeping to savings.</b>{html.escape(sweep['action'])}</div>

<h2>Why cash bottoms this week</h2>
<div class=card><div class=scroll>{chart}</div>
<div class=legend><span><i style="background:var(--fc)"></i>Week-0 forecast</span>
<span><i style="background:var(--act)"></i>Actual</span><span><i style="background:var(--plan)"></i>Reforecast</span>
<span><i style="background:var(--buf)"></i>Buffer</span></div>
<p class=small>Week-0 forecast low point: {money(original_low[1])} in the week of {wk(original_low[0])}. The BFCM
inventory balance, its freight, October's card statement, payroll and October's sales tax all leave in the same
week, while most BFCM receipts arrive one to two weeks later.</p>
<table><tr><th>Cash in this week</th><th class=n>Amount</th><th>Cash out this week</th><th class=n>Amount</th></tr>
{''.join(f"<tr><td>{html.escape(ins[i][0]) if i < len(ins) else ''}</td><td class=n>{money(ins[i][1]) if i < len(ins) else ''}</td><td>{html.escape(outs[i][0]) if i < len(outs) else ''}</td><td class='n neg'>{money(outs[i][1]) if i < len(outs) else ''}</td></tr>" for i in range(max(len(ins), len(outs))))}
</table></div>

<h2>Forecast to actual: the variance bridge</h2>
<div class=card>{bridge}
<p class=small>Each step swaps one driver from forecast to actual, so the steps add up to the difference exactly.
Refunds drive the miss: without them, cash would have come in about $6,000 ahead of the forecast.</p></div>

<h2>What changed since the week-0 forecast</h2>
<div class=card><table><tr><th>Line</th><th class=n>Actual vs forecast</th><th>Driver split</th></tr>
{''.join(f"<tr><td>{html.escape(n)}</td><td class='n {'neg' if v < 0 else ''}'>{money(v, True)}</td><td class=muted>{html.escape(p)}</td></tr>" for n, v, p in var_rows)}
<tr><td><b>Total</b></td><td class=n><b>{money(total_var, True)}</b></td><td></td></tr></table>
<h3>Findings the monitor raised</h3>
<table><tr><th>Week found</th><th>Line</th><th>Cause</th><th>What it saw</th><th class=n>Amount</th></tr>{find_html}</table>
<p class=small>The refund finding feeds the reforecast: FW-2201's refund rate is carried for two more weeks. The Google
finding is small, sits on the card (not cash until the December autopay) and was not one of the injected events, so
it is one of the monitor's false alarms in this run; it is shown because the brief prints everything the monitor
raised.</p></div>

<h2>How this was built</h2>
<div class=card small><p class=small>The forecast is driver-based: Shopify sales and refunds by SKU, fees,
chargebacks, payout timing, Amazon settlements, wholesale terms by retailer, ad spend by platform, bills with terms
and dates. Variance is split by swapping one driver at a time from forecast to actual, so the pieces add up to the
line exactly. A finding needs to beat both the driver's normal noise (3 standard deviations) and Fernwood's
materiality ({money(cfg['materiality'])}). The draw, bill and paydown actions come from actions/plan.py and
actions/vendor_rules.yaml. Accuracy is measured on hidden events in evals/results.</p></div>
"""
    return page("Fernwood Cash Brief", body, "Fernwood Goods weekly cash brief, week of Nov 16, 2026 (synthetic).")


# ------------------------------------------------------------------------------------------- board
def board(cfgs, books, steps):
    snaps = {t: snapshot(cfgs, books, steps, t) for t in range(1, N_WEEKS)}
    data = {}
    for t, rows in snaps.items():
        data[t] = dict(label=WEEKS[t].strftime("%b %-d, %Y"), rows=[dict(
            brand=r["brand"], status=r["status"], why=r["why"], cash=money(r["cash"]), buffer=money(r["buffer"]),
            low=money(r["low"]), low_week=r["low_week"], low_ratio=round(r["low"] / r["buffer"], 2),
            draw=money(r["draw"]) if r["draw"] else "-", var=money(r["last_week_var"], True),
            var_neg=r["last_week_var"] < 0, new=r["new"], open=r["open"], spark=r["spark"],
            disc=r["discounts_now"]) for r in rows])
    payload = json.dumps(data)
    body = f"""
<p class=sub>Portfolio health board</p>
<h1>10 brands, one Monday at a time</h1>
<p class=sub>Each row is a brand's 13-week cash picture as of the Monday shown, using only actuals through the
Friday before. Slide to replay the quarter. Synthetic brands; the development events are hidden in the data.</p>
<div class=card><label for=w class=small>Week of</label> <span id=lab class=wk></span>
<input id=w type=range min=1 max={N_WEEKS - 1} value={BRIEF_WEEK}>
<div class=kpis id=k style="margin-top:10px"></div></div>
<div class="card scroll"><table class=wide><thead><tr><th>Status</th><th>Brand</th><th class=n>Cash Friday</th>
<th class=n>Low point ahead</th><th class=n>Draw this week</th><th class=n>Last week vs
forecast</th><th>Cash path</th><th>New this week</th></tr></thead><tbody id=rows></tbody></table>
<div class=legend><span><i style="background:var(--act)"></i>actual</span><span><i style="background:var(--plan)"></i>reforecast</span>
<span><i style="background:var(--buf)"></i>buffer</span></div></div>
<p class=small>Status: red when the reforecast goes under the buffer this week or next; amber when it goes under later
in the window, comes within 15% of it, or a new finding is at least twice the brand's materiality; green otherwise.
Draws are sized by actions/plan.py.</p>
<script>
const D={payload};
const esc=s=>s.replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));
function render(t){{const d=D[t];document.getElementById('lab').textContent=d.label;
const c={{red:0,amber:0,green:0}};d.rows.forEach(r=>c[r.status]++);
const draws=d.rows.filter(r=>r.draw!=='-').length;
document.getElementById('k').innerHTML=`<div class=kpi><div class=l>Red</div><div class=v>${{c.red}}</div></div>
<div class=kpi><div class=l>Amber</div><div class=v>${{c.amber}}</div></div><div class=kpi><div class=l>Green</div>
<div class=v>${{c.green}}</div></div><div class=kpi><div class=l>Brands drawing this week</div><div class=v>${{draws}}</div></div>`;
document.getElementById('rows').innerHTML=d.rows.map(r=>`<tr><td><span class="pill ${{r.status}}">${{r.status}}</span>
<div class="small muted">${{esc(r.why)}}</div></td><td><b>${{esc(r.brand)}}</b></td><td class=n>${{r.cash}}</td>
<td class=n>${{r.low}}<div class="small muted">${{r.low_week}} · buffer ${{r.buffer}}</div></td>
<td class=n>${{r.draw}}</td><td class="n ${{r.var_neg?'neg':''}}">${{r.var}}</td><td>${{r.spark}}</td>
<td class='small w'>${{r.new.length?r.new.map(esc).join('<br>'):'<span class=muted>none</span>'}}
${{r.disc.length?'<div class=muted>Early-pay discounts taken: '+r.disc.join(', ')+'</div>':''}}</td></tr>`).join('');}}
const s=document.getElementById('w');s.addEventListener('input',e=>render(e.target.value));render(s.value);
</script>"""
    return page("Portfolio Cash Health", body, "10-brand cash health board, replayable by week (synthetic).", wide=True)


def index():
    res = (ROOT / "evals" / "results" / "results.md").read_text() if (ROOT / "evals" / "results" /
                                                                       "results.md").exists() else ""
    body = f"""<p class=sub>forecast-health-monitor</p><h1>Cash drift monitor for DTC brands</h1>
<p class=sub>A 13-week cash forecast that explains its own misses, then turns the answer into dated actions.</p>
<div class=card><ul><li><a href=cash_brief_fernwood.html>Fernwood Cash Brief, week of Nov 16</a></li>
<li><a href=portfolio_10_brands.html>10-brand health board</a></li></ul></div>
<h2>Evaluation results</h2><div class=card><pre style="white-space:pre-wrap;font-size:12.5px">{html.escape(res)}</pre></div>"""
    return page("Forecast Health Monitor", body, "Reports index")


def main():
    cfgs, books, steps = run()
    OUT.mkdir(exist_ok=True)
    (OUT / "cash_brief_fernwood.html").write_text(brief(cfgs, books, steps))
    (OUT / "portfolio_10_brands.html").write_text(board(cfgs, books, steps))
    (OUT / "index.html").write_text(index())
    print("wrote reports/cash_brief_fernwood.html, reports/portfolio_10_brands.html, reports/index.html")


if __name__ == "__main__":
    main()
