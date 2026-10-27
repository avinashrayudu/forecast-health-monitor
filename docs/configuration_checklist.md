# Configuration checklist: putting a new brand on the monitor

This is what I would collect for each brand before its first Monday brief. Each item maps to a field the code reads. Without it, the monitor either cannot explain a variance or explains it wrong.

## 1. Data feeds (from the onboarded cash ledger)

| Need | Grain | Used for | Field / file |
|---|---|---|---|
| Shopify orders, refunds, fees, chargebacks | daily, refunds by SKU | volume, refund, fee and chargeback drivers | `dtc_*` drivers |
| Shopify payouts | per payout | payout timing (share paid next week) | `payout_lag_share` |
| Amazon settlement reports | per settlement, with reserve lines | volume, fee and reserve drivers | `amz_*` drivers |
| Wholesale invoices | per invoice, with retailer and terms | late receivables by retailer | `retailers` |
| AP bills | per bill: vendor, issue, due, discount, currency | bill timing, price and FX drivers | `make_bills` |
| Card transactions | per charge, with merchant | ad spend by platform before it becomes cash | `ad_platforms` |
| Bank lines | per line, labeled by dtc-cash-onboarding | everything else, plus noise calibration | `data/ledgers` |

**Gate:** the ledger must pass the tie-out in dtc-cash-onboarding first. Payouts, settlements and card payments have to agree with the bank. A variance monitor on an untied ledger mostly finds onboarding errors.

## 2. Calendars (ask, then check against 12+ weeks of history)

- [ ] Payroll Fridays and run size (`payroll_weeks`, `payroll_run`)
- [ ] Card autopay day of month (default the 22nd)
- [ ] Rent and fixed-cost day (default the 1st)
- [ ] Sales tax remittance day and states (default the 20th, one rate)
- [ ] Amazon settlement cadence (default every two weeks)
- [ ] Wholesale terms by retailer, and which retailers usually pay late

## 3. Policies (the founder decides these, not the code)

- [ ] **Cash buffer**: the founder's minimum (`cash_buffer`). Default: two weeks of outflows.
- [ ] **Materiality**: the smallest miss worth a line in the brief (`materiality`). Default: the larger of $2,500 or 1.5% of weekly receipts.
- [ ] **Credit line**: limit, drawn balance, APR, draw notice and draw size (`loc_*`, `draw_increment`).
- [ ] **Vendor rules**: criticality per vendor. List the bills that must never be late and the ones that can move with notice (`actions/vendor_rules.yaml`).
- [ ] **Early-pay discounts**: which vendors offer them, and whether the founder will borrow to take them.
- [ ] **Sweep account**: the savings rate and any minimum operating balance.

## 4. Calibration checks before go-live

- [ ] Each driver's noise is measured from history (`world/calibrate.py`), not guessed. Check the clipped ones; a 35% CV usually means a labeling problem.
- [ ] Replay the last 13 weeks with no known events and count findings. Target: under one false alarm per brand per quarter. The synthetic noise-only run here gives 0.16.
- [ ] Re-run the forecast as of a past Monday and compare its low point with what happened.
- [ ] Confirm the brand's "known one-offs" (tax payments, annual renewals) are in the plan. If they are missing, each will raise an unplanned-payee finding.

## 5. What the first brief must show

- [ ] This week's low point, its date and the gap to the buffer
- [ ] Every finding with its driver and dollar amount, including ones that turn out to be noise
- [ ] Each action with a date, an amount and its cost: the draw and repayment, the bills paid early or on time, and the paydown or sweep

Built by Avinash Rayudu.
