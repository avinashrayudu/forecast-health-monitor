# forecast-health-monitor

**Why it matters.** A founder does not need a forecast that is right; forecasts miss. They need to know on Monday
why it missed and what to pay, draw or hold this week. This monitor answers that, with dates and dollar amounts.
**What it is.** A 13-week cash forecast that explains its own misses and turns the explanation into dated actions:
a credit draw with its repay date, which bills to pay early, and what to do with cash after the trough.
**Best result.** It found and named all 8 holdout cash-drift events, written after the detector was frozen. When
credit was tight, paying bills by the forecast held the worst unplanned dip to $67,629 instead of $140,937.
**See it.** [The Monday Cash Brief](https://avinashrayudu.github.io/forecast-health-monitor/reports/cash_brief_fernwood.html) ·
[10-brand health board](https://avinashrayudu.github.io/forecast-health-monitor/reports/portfolio_10_brands.html) ·
[case study](https://www.avinashrayudu.com/work/forecast-health-monitor/) ·
[finance concepts](docs/finance_concepts.md)

Built by Avinash Rayudu. Every brand, vendor and number here is synthetic.

## The Monday brief

**Fernwood Goods** is a synthetic consumer products brand with $8.4M of revenue and a corrected plan P&L that gives
about a 5% operating margin ([docs/fernwood_pnl.md](docs/fernwood_pnl.md)). Its forecast opens on Oct 26, 2026.

The [brief](https://avinashrayudu.github.io/forecast-health-monitor/reports/cash_brief_fernwood.html) is dated Nov 16
and uses actuals through Nov 15. It says:

- Refunds ran 1.7x forecast in the weeks of Nov 2 and Nov 9, and SKU FW-2201 is 99% of the excess. The reforecast
  carries that rate two more weeks, which moves the low point to **$99,718** after this week's early bill payment.
- Draw **$225,000** on the credit line on Monday and repay it in the week of Nov 23. That covers the gap plus a
  cushion for receipts not yet in. Interest is about **$476**.
- Pay ShipNest 3PL's $69,211 invoice now and take the 2% discount. It saves **$1,384** against at most about $430 of
  interest.
- Pay the inventory balance and freight on their due dates. The vendor rules never let them go late.
- After the trough, pay down **$183,313** of the credit line before sweeping anything to savings. At 11% APR against
  a 2.58% savings yield, that is worth about **$15,435** a year more.

It also prints the monitor's one false alarm for Fernwood: a $2,759 Google overspend that was noise.

**Two draws, two moments.** The week-0 forecast (Oct 26, before any actuals) bottoms at **$194,498**, $105,502 under
the buffer, so the smallest draw in $25,000 steps that holds the buffer is **$125,000**. That is the figure
[workflow-reliability-lab](https://github.com/avinashrayudu/workflow-reliability-lab) uses. By Nov 16, refunds have
pushed the reforecast low point down to $99,718, and the draw adds a cushion for receipts not yet in, so the brief
calls for **$225,000**.

### Forecast to actual: the variance bridge

Closing cash in the week of Nov 9, week-0 forecast against actual. Each step swaps one driver from forecast to
actual, so the steps add up to the difference exactly (`variance_bridge` in `reports/build.py`).

| Step | Amount |
|---|---:|
| Week-0 forecast, closing cash in the week of Nov 9 | $803,902 |
| Shopify payouts: refunds | -$14,301 |
| Amazon settlements: volume | -$1,445 |
| Payroll: unexplained | -$161 |
| Bank fees and other: noise | +$18 |
| Shopify payouts: chargebacks | +$206 |
| Wholesale receipts: volume | +$909 |
| Shopify payouts: volume | +$6,517 |
| **Actual closing cash** | **$795,644** |

Refunds drive the miss: without them, cash would have come in about $6,000 ahead of the forecast.

## When the forecast matters: tight credit

With only $50K of credit headroom, "always pay early" deepened the worst unplanned dip under the buffer to
**$140,937**. The forecast-aware policies held it at **$67,629** by giving up $9,894 of discounts. That remaining dip
is Fernwood's trough itself, which $50K of headroom cannot cover under any policy.

With normal credit, the policies tie, and that is the honest result. A 2/10 net 30 discount is worth about 37% a year,
so borrowing at 11% to take it always pays. All 10 brands, 13 actual weeks, development events:

| Policy | Discounts | Interest | Unplanned weeks under buffer | Rules broken |
|---|---:|---:|---:|---:|
| Pay on due date | $0 | $952 | 0 | 0 |
| Always pay early | $35,237 | $1,111 | 0 | 0 |
| Forecast-aware, planned once | $35,237 | $1,111 | 0 | 0 |
| Forecast-aware, re-planned weekly by the monitor | $35,237 | $1,111 | 0 | 0 |

## Detection results

The scores come from the current code (`evals/results/results.md`). The holdout results as first run, before any
post-holdout change, are in `evals/results/holdout_v1_frozen/`.

| Set | Events | Detected | Right cause | Median lag | Precision | False alarms |
|---|---:|---:|---:|---:|---:|---:|
| Development (12 events I built against) | 12 | 12 | 12 | 0 weeks | 94% | 1 |
| Holdout (8 events written after the freeze) | 8 | 8 | 8 | 0.5 weeks | 79% | 3 |
| Noise only (5 worlds, 650 brand-weeks, no events) | - | - | - | - | - | 8 (0.16 per brand per quarter) |

**What the events cover:**
- **Development:** a SKU refund spike, a Shopify payout hold, an Amazon reserve, a retailer paying late, Meta
  overspend, an FX move on a USD supplier, a sales miss, a chargeback cluster, a supplier pulling a deposit forward, a
  freight overcharge, a 3PL rate increase and an unplanned legal bill.
- **Holdout:** two causes the development set never had, a Shopify fee change and an Amazon fee change. Both were
  found and named correctly, with lags of 1 and 2 weeks.

**Reforecast after a finding.** Errors are mean absolute, at each week a finding was raised.

| Set | Low point: roll forward | Low point: with rules | Ending cash: roll forward | Ending cash: with rules |
|---|---:|---:|---:|---:|
| Development | $9,998 | $6,371 | $19,308 | $13,081 |
| Holdout | $6,473 | $5,600 | $12,855 | $13,924 |

On the holdout the rules helped the low point but made ending cash worse. The volume rule carried Copperleaf's BFCM
miss four weeks into December, after the miss had ended.

**The workbook.** [sheets/fernwood_13wk.xlsx](sheets/fernwood_13wk.xlsx) is Fernwood's forecast as an Excel model with
Inputs, Forecast, Calendar, Bills and a Check tab. Every line and week ties to the Python engine to the cent, and the
Check tab shows it (0.0000% max difference, 0 formula errors). Every number is a live formula, so changing an input
on the Inputs tab moves the forecast.

## Why these numbers

Every threshold, in plain language, with where it comes from.

| Setting | Value | In plain language | Where it comes from |
|---|---|---|---|
| Cash buffer | $300,000 for Fernwood | The cash the brand never wants to go under: about two weeks of bills, so one bad week cannot stop payroll. | A little under two weeks of Fernwood's average forecast outflows ($2.13M over 13 weeks, about $164K a week). The other nine brands get the same policy from their own ledgers: two weeks of outflow (`buffer_weeks_of_outflow: 2.0`). |
| Opening cash | $300,000 for Fernwood | Fernwood starts the quarter right at its buffer, so the November trough has to be managed. | Set in the corrected plan. The first draft opened with $1.0M, which never produced a trough (see `docs/fernwood_pnl.md`). |
| Detection bar | 3 standard deviations | A driver is flagged only when it moves about three times as far as it normally wanders week to week. | Each driver is tested every week over 1, 2 and 4-week windows, so a lower bar multiplies false alarms. At 3, the noise-only worlds give about 0.16 false alarms per brand per quarter. |
| Materiality | the larger of $2,500 or 1.5% of weekly receipts | A real move that is too small to change a decision is not worth a founder's attention. | The $2,500 floor covers small brands; the 1.5% scales with size. Set by hand. |
| Normal noise | 16 weeks of the brand's own history | "Normal" is measured from the brand itself, not assumed. | The full history window in the onboarded ledgers (Jul 6 to Oct 25). |
| Draw cushion | 1.65 standard deviations of the week's unseen receipts | Borrow a little extra so receipts that have not landed yet push cash under the buffer only about 1 week in 20. | One-sided 95%. Added after holdout v1, when two brands dipped by up to $2,717. |
| Draw size | multiples of $25,000 | Round draws, the way credit lines are usually drawn. | Set by hand; it keeps the brief readable. |
| Early-pay discount | 2/10 net 30 is worth about 37% a year | Paying 20 days early to save 2% is like earning 37% a year on that cash, far more than 11% interest. | 2/98 x 365/20. |
| Credit line and savings rates | 11% APR, 2.58% APY | Illustrative rates. Paying down a line at 11% beats earning 2.58% in savings. | Set by hand; check against a brand's real terms. |

## What changed after the holdout

`evals/FREEZE.json` holds hashes of the monitor, reforecast, actions and config, taken before
`world/holdout_events.py` existed. The first holdout run is kept as it was in `evals/results/holdout_v1_frozen/`.

That run showed three problems, which I then fixed. Every eval run prints the files changed since the freeze, so
these changes stay visible. The holdout is not a blind test for the fixed version.

1. **Draws had no cushion.** Two brands dipped under the buffer by up to $2,717 in weeks the forecast could not see
   yet. Draws now add 1.65 standard deviations of the week's unseen receipts. This removed those dips with normal
   credit, at about $210 to $320 more interest across ten brands, depending on the policy.
2. **The reforecast had no rule for fee changes.** It now carries the observed fee rate forward.
3. **Amazon fee findings were worded as processing fees.** This was a wording fix only.

I also corrected Fernwood's fixed costs. The plan's $34K a month includes $10K of software paid on the card, and the
bank line had been counting that $10K twice. Detection results did not change.

## Where Fernwood's levels come from

The other nine brands take their weekly levels straight from the cash ledgers that
[dtc-cash-onboarding](https://github.com/avinashrayudu/dtc-cash-onboarding) produced. Fernwood does not. Its
onboarded ledger shows Shopify payouts of about $214K a week from Jul 6 to Oct 25, while the corrected plan implies
about $115K a week of gross DTC sales for the same weeks: the ledger runs at roughly 1.9 times the plan. The two were
built separately and I did not force them to agree. Fernwood takes its levels from the plan, and takes the size of
its week-to-week noise, its payroll Fridays and its card autopay date from the ledger.

An earlier note in this repo, which is still in `config/overrides.yaml`, put the gap at "about 30%". That figure was
wrong. The config file is left as it was because it is under the pre-holdout freeze.

## How it works

```
data/ledgers/            10 brands' labeled cash ledgers from dtc-cash-onboarding
world/calibrate.py       weekly levels, noise, calendars and credit line per brand, from the ledgers
world/engine.py          one driver-based 13-week cash engine for both the forecast and the simulated actuals
world/inject_events.py   12 development events; labels go to world/labels/, which the monitor never reads
world/holdout_events.py  8 events written after the freeze
forecast/baseline_13wk.py  print any brand's baseline forecast
monitor/attribute.py     splits each line's miss into drivers; the pieces sum to the variance exactly
monitor/detect.py        tests each driver over 1-, 2- and 4-week windows against its noise (z = 3) and materiality
monitor/reforecast.py    actuals to date, then the forecast adjusted by rules per finding
actions/plan.py          fund the trough, bill-payment policies, sweep vs paydown
actions/vendor_rules.yaml  which bills can never be late, draw size, cushion
sheets/                  the Fernwood workbook and its check against the code
evals/                   scorer, freeze record, results
reports/                 Cash Brief, 10-brand health board, index (served by GitHub Pages)
docs/                    corrected P&L, configuration checklist, product patterns memo
tests/                   11 tests, including: the trough exists, the P&L margin is 4-6%, components sum to the
                         variance, the workbook matches the code, no vendor rule is broken, and monitor/ and
                         actions/ never import the event files or read the labels
```

**Detection.** A finding has to beat both the driver's normal noise and the brand's materiality.

**Diagnosis.** The earliest finding that overlaps an event's affected line-weeks counts as the diagnosis. It is right
only if its cause matches the hidden label.

## Run it

```
pip install -r requirements.txt
make demo      # calibrate, evals, workbook, reports, tests (under a minute)
python -m forecast.baseline_13wk    # Fernwood's week-0 forecast, line by line
```

The workbook step uses LibreOffice to calculate the formulas if it is installed. Otherwise, open the file in Excel.
The board has a slider that replays the quarter one Monday at a time.

## Limits

- **The simulated world and the forecast share one engine.** Every miss in this setup has a driver that explains it.
  Real brands have causes outside any model, so expect lower attribution accuracy on real data.
- **I wrote both the events and the detector.** The holdout was written after the freeze, but by the same person. The
  noise-only worlds are the least biased measure here.
- **The monitor reads actuals at driver grain:** orders and refunds by SKU, settlement reserve lines, invoices by
  retailer, bills with terms. Without that grain it can only say a line moved.
- **The rates are illustrative:** the 11% credit line APR and the 2.58% savings APY.

## Where this fits at Highbeam

My reading of Highbeam's public Luma pages and the AI Implementation Associate posting. This project is not
affiliated with Highbeam and uses no Highbeam data.

| This project | Highbeam / Luma workflow it would show | The role's work it rehearses |
|---|---|---|
| A driver-based 13-week forecast per brand | Luma's baseline cash forecasting and "true cash position" view | Forecast health monitoring |
| Miss attribution, detection and the Monday brief | The Alerts and reporting agent, which monitors key metrics and writes weekly reports | Explaining a messy cash situation clearly to a founder |
| Draw sizing with a cushion and a repay date | Highbeam's revolving line of credit | Cash management recommendations |
| Bill timing under vendor rules and discounts | Highbeam Bill Pay | AP and bill pay setup |
| Paydown vs sweep after the trough | The Treasury agent, which maximizes yield and minimizes interest | Cash management recommendations |
| The Excel twin that ties to the code | | Excel and Sheets modeling |

Sources: [Introducing Luma](https://www.highbeam.com/blog/introducing-luma-a-world-class-finance-team-for-every-d2c-brand),
[Luma](https://www.highbeam.com/luma),
[Highbeam Intelligence](https://www.highbeam.com/blog/expert-finance-agents-for-consumer-brands-highbeam-intelligence).

## Finance concepts

The forecast is on a cash basis: it turns the accrual plan P&L into the weeks money actually moves. Accounts
receivable shows up as wholesale receipts by retailer and terms; accounts payable as bills with terms, due dates and
discounts. [docs/finance_concepts.md](docs/finance_concepts.md) covers AP and AR, cash vs accrual and the three-way
match across all three projects.

## How I built this

I built this with Claude Code, Anthropic's coding agent. I chose the problem and set the rules the work had to
follow: synthetic brands only, one engine for the forecast and the simulated actuals, hidden event labels the monitor
never reads, freeze the detector before writing the holdout, and no number in this README that a committed run did
not produce. Claude Code wrote most of the code, the workbook builder, the tests and first drafts of the docs under
that direction and ran the evals. I read the results, decided what to fix and what to leave visible, and ran reviews
from an implementation team's point of view that drove the last rounds of changes. [CHANGELOG.md](CHANGELOG.md) shows
the order things happened in.

## Why I built this

At Zacao Chocolate, a consumer products brand in Brooklyn, I reconciled the store invoices the books said were
unpaid and found most had already been collected, never delivered or refused at delivery
([case study](https://www.avinashrayudu.com/work/zacao-receivables/)). Knowing what is really owed is half of cash
management. This project is the other half: knowing when cash is tight, why, and what to pay when.

Built by Avinash Rayudu. MIT License.
