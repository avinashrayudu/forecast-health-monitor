# forecast-health-monitor

A 13-week cash forecast that explains its own misses and then turns the explanation into dated actions: a credit draw with its repay date, which bills to pay early, and what to do with cash after the trough.

Built by Avinash Rayudu. Every brand, vendor and number here is synthetic.

## What it does, on one brand

**Fernwood Goods** is a synthetic consumer products brand with $8.4M of revenue and a corrected plan P&L that gives about a 5% operating margin ([docs/fernwood_pnl.md](docs/fernwood_pnl.md)). Its forecast opens on Oct 26, 2026.

**The trough.** Cash bottoms in the week of Nov 16 at **$194,498**, $105K under the $300K buffer. Several payments land that week:
- the BFCM inventory balance ($520K) and its freight ($95K),
- October's card statement,
- payroll and sales tax.

Most BFCM receipts arrive one to two weeks later.

**The Monday brief** ([reports/cash_brief_fernwood.html](reports/cash_brief_fernwood.html)) is dated Nov 16 and uses actuals through Nov 15. It says:

- Refunds ran 1.7x forecast in the weeks of Nov 2 and Nov 9, and SKU FW-2201 is 99% of the excess. The reforecast carries that rate two more weeks, which moves the low point to **$99,718** after this week's early bill payment.
- Draw **$225,000** on the credit line on Monday and repay it in the week of Nov 23. That covers the gap plus a cushion for receipts not yet in. Interest is about **$476**.
- Pay ShipNest 3PL's $69,211 invoice now and take the 2% discount. It saves **$1,384** against at most about $430 of interest.
- Pay the inventory balance and freight on their due dates. The vendor rules never let them go late.
- After the trough, pay down **$183,313** of the credit line before sweeping anything to savings. At 11% APR against a 2.58% savings yield, that is worth about **$15,435** a year more.

It also prints the monitor's one false alarm for Fernwood: a $2,759 Google overspend that was noise.

## Results

The scores below come from the current code (`evals/results/results.md`). The holdout results as first run, before any post-holdout change, are in `evals/results/holdout_v1_frozen/`.

| Set | Events | Detected | Right cause | Median lag | Precision | False alarms |
|---|---:|---:|---:|---:|---:|---:|
| Development (12 events I built against) | 12 | 12 | 12 | 0 weeks | 94% | 1 |
| Holdout (8 events written after the freeze) | 8 | 8 | 8 | 0.5 weeks | 79% | 3 |
| Noise only (5 worlds, 650 brand-weeks, no events) | - | - | - | - | - | 8 (0.16 per brand per quarter) |

**What the events cover:**
- **Development:** a SKU refund spike, a Shopify payout hold, an Amazon reserve, a retailer paying late, Meta overspend, an FX move on a USD supplier, a sales miss, a chargeback cluster, a supplier pulling a deposit forward, a freight overcharge, a 3PL rate increase and an unplanned legal bill.
- **Holdout:** two causes the development set never had, a Shopify fee change and an Amazon fee change. Both were found and named correctly, with lags of 1 and 2 weeks.

**Reforecast after a finding.** Errors are mean absolute, at each week a finding was raised.

| Set | Low point: roll forward | Low point: with rules | Ending cash: roll forward | Ending cash: with rules |
|---|---:|---:|---:|---:|
| Development | $9,998 | $6,371 | $19,308 | $13,081 |
| Holdout | $6,473 | $5,600 | $12,855 | $13,924 |

On the holdout the rules helped the low point but made ending cash worse. The volume rule carried Copperleaf's BFCM miss four weeks into December, after the miss had ended.

**Bill-payment policies.** All 10 brands, 13 actual weeks, development events:

| Policy | Discounts | Interest | Unplanned weeks under buffer | Rules broken |
|---|---:|---:|---:|---:|
| Pay on due date | $0 | $952 | 0 | 0 |
| Always pay early | $35,237 | $1,111 | 0 | 0 |
| Forecast-aware, planned once | $35,237 | $1,111 | 0 | 0 |
| Forecast-aware, re-planned weekly by the monitor | $35,237 | $1,111 | 0 | 0 |

The policies tie with normal credit, and that is the honest result. A 2/10 net 30 discount is worth about 37% a year, so borrowing at 11% to take it always pays.

The forecast matters when credit is tight. With only $50K of headroom, "always pay early" deepened the worst unplanned dip under the buffer to $140,937. The forecast-aware policies held it at $67,629 by giving up $9,894 of discounts. That remaining dip is Fernwood's trough itself, which $50K of headroom cannot cover under any policy.

**The workbook.** [sheets/fernwood_13wk.xlsx](sheets/fernwood_13wk.xlsx) holds 2,564 live formulas across Inputs, Forecast, Calendar, Bills and Check. It matches the Python engine to the cent on every line and week (0.0000% max difference), with 0 formula errors.

## What changed after the holdout

`evals/FREEZE.json` holds hashes of the monitor, reforecast, actions and config, taken before `world/holdout_events.py` existed. The first holdout run is kept as it was in `evals/results/holdout_v1_frozen/`.

That run showed three problems, which I then fixed. Every eval run prints the files changed since the freeze, so these changes stay visible. The holdout is not a blind test for the fixed version.

1. **Draws had no cushion.** Two brands dipped under the buffer by up to $2,717 in weeks the forecast could not see yet. Draws now add 1.65 standard deviations of the week's unseen receipts. This removed those dips with normal credit, at about $210 to $320 more interest across ten brands, depending on the policy.
2. **The reforecast had no rule for fee changes.** It now carries the observed fee rate forward.
3. **Amazon fee findings were worded as processing fees.** This was a wording fix only.

I also corrected Fernwood's fixed costs. The plan's $34K a month includes $10K of software paid on the card, and the bank line had been counting that $10K twice. Detection results did not change.

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
reports/                 Cash Brief, 10-brand health board, index
docs/                    corrected P&L, configuration checklist, product patterns memo
tests/                   11 tests, including: the trough exists, the P&L margin is 4-6%, components sum to the
                         variance, the workbook matches the code, no vendor rule is broken, and monitor/ and
                         actions/ never import the event files or read the labels
```

**Detection.** A finding has to beat both the driver's normal noise and the brand's materiality. Normal noise comes from 16 weeks of the brand's own history. Materiality is the larger of $2,500 or 1.5% of weekly receipts.

**Diagnosis.** The earliest finding that overlaps an event's affected line-weeks counts as the diagnosis. It is right only if its cause matches the hidden label.

## Run it

```
pip install -r requirements.txt
make demo      # calibrate, evals, workbook, reports, tests (under a minute)
```

The workbook step uses LibreOffice to calculate the formulas if it is installed. Otherwise, open the file in Excel. The board ([reports/portfolio_10_brands.html](reports/portfolio_10_brands.html)) has a slider that replays the quarter one Monday at a time.

## Limits

- **The simulated world and the forecast share one engine.** Every real-world miss in this setup has a driver that explains it. Real brands have causes outside any model, so expect lower attribution accuracy on real data.
- **I wrote both the events and the detector.** The holdout was written after the freeze, but by the same person. The noise-only worlds are the least biased measure here.
- **The monitor reads actuals at driver grain:** orders and refunds by SKU, settlement reserve lines, invoices by retailer, bills with terms. Without that grain it can only say a line moved.
- **The rates are illustrative:** the 11% credit line APR and the 2.58% savings APY. Fernwood's onboarded ledger runs about 30% above its plan, so Fernwood uses plan levels and takes only its noise and calendars from the ledger.

## Why I built this

At Zacao Chocolate, a consumer products brand, I built a PO-to-invoice matching agent that cut the payment cycle by 15 days. Faster payment only helps if you know which weeks can afford it. This project is the other half of that problem: knowing when cash is tight, why, and what to pay when.

Built by Avinash Rayudu. MIT License.
