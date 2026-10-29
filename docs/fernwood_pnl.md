# Fernwood Goods: corrected plan P&L

Fernwood Goods is a synthetic consumer products brand. This is the annual plan the 13-week forecast is built on.

## Why it was corrected

The first draft of this plan did not add up:

- Payroll was $145K biweekly ($3.77M a year) and fixed costs were $0.72M a year.
- Against about $2.13M of contribution after ads, that is a loss of about $2.36M, roughly 28% of revenue.
- The draft still showed a $420K profit line.

The corrected plan sets payroll at $50K biweekly and fixed costs at $34K a month. That gives about a 5% operating margin. `tests/test_forecast.py` checks it stays between 4% and 6%.

The first draft also opened with $1.0M of cash. With that balance the forecast never went under the $300K buffer, so there was no trough to manage. Opening cash is now $300K. `tests/test_forecast.py` asserts the November trough exists and breaks the buffer.

## Annual plan

| Line | Basis | Annual |
|---|---|---:|
| Revenue | | $8,400,000 |
| Shopify (DTC) | 80% of revenue | $6,720,000 |
| Amazon | 8% | $672,000 |
| Wholesale (Faire, Hudson Mercantile) | 12% | $1,008,000 |
| Cost of goods | 38% of revenue | ($3,192,000) |
| **Gross profit** | 62% | **$5,208,000** |
| Fulfillment (3PL) | 10% of revenue | ($840,000) |
| Payment processing fees | 3% of revenue | ($252,000) |
| Refunds | 6% of revenue (9% in January) | ($504,000) |
| Advertising | 22% of Shopify sales; Meta 70%, Google 30% | ($1,478,400) |
| **Contribution after ads** | 25.4% | **$2,133,600** |
| Payroll | $50,000 biweekly | ($1,300,000) |
| Fixed costs | $34,000 a month, including $10,000 of software on the card | ($408,000) |
| **Operating profit** | **5.1%** | **$425,600** |
| Credit line interest | $400,000 drawn at 11% APR (illustrative) | ($44,000) |
| **Profit before tax** | 4.5% | **$381,600** |

## Balance sheet items the cash forecast uses

| Item | Value |
|---|---|
| Opening cash, Oct 26, 2026 | $300,000 |
| Cash buffer (founder's minimum) | $300,000 |
| Credit line | $1.5M limit, $400K drawn, 11% APR (illustrative) |
| BFCM inventory balance, Kestrel Knitworks Ltd | $520,000, due the week of Nov 16 |
| BFCM freight, Harborline Freight | $95,000, due the week of Nov 16 |
| Spring deposit, Halden Textile Co | $200,000, due the week of Jan 4 |
| Wholesale terms | Faire pays in about 1 week; Hudson Mercantile in 9 weeks |
| 3PL terms | ShipNest 3PL bills on the 10th, 2/10 net 30 |
| Packaging terms | Noble Box Co bills on the 5th, 1/10 net 30 |

## How the plan becomes weekly cash

The P&L is annual and accrual-based. The forecast is weekly and cash-based, so a few lines move:

- **Cost of goods** is paid as purchase orders, not spread evenly. That is why one week in November carries $615K of inventory and freight.
- **Refunds and fees** are netted out of Shopify payouts. About 2 of 7 days of each week's sales pay out the following week.
- **Ad spend** is charged to the card and paid with the card autopay on the 22nd of the following month. October's statement lands in the week of Nov 16, next to the inventory balance.
- **Sales tax** for each month is remitted on the 20th of the next month.
- **Seasonality**: November runs at 2.1x a May month, and 40% of November's sales fall in BFCM week. December runs at 1.6x and January at 0.7x.

## Plan vs the onboarded ledger

Fernwood's ledger from dtc-cash-onboarding shows Shopify payouts of about $214K a week from Jul 6 to Oct 25. This plan implies about $115K a week of gross DTC sales for the same weeks, so the ledger runs at roughly 1.9 times the plan. (An earlier version of this note said "roughly 30% above"; that was wrong.) The two were built separately and I did not force them to agree. The other nine brands take their levels from their ledgers. Fernwood takes its levels from this plan and uses its ledger only for:

- the size of its week-to-week noise,
- its payroll Fridays,
- its card autopay date.

All numbers are synthetic.
