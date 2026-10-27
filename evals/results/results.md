# Evaluation results

Detector: z = 3.0, windows [1, 2, 4] weeks. Freeze check: CHANGED since freeze: ['world/calibrate.py', 'config/overrides.yaml', 'monitor/detect.py', 'monitor/reforecast.py', 'actions/plan.py', 'actions/vendor_rules.yaml'].

## Detection and diagnosis

| set | events | detected | correct cause | median lag (wks) | findings | precision | false alarms |
|---|---|---|---|---|---|---|---|
| Development events | 12 | 12 (100%) | 12 (100%) | 0.0 | 18 | 94% | 1 |
| Holdout events (written after the freeze) | 8 | 8 (100%) | 8 (100%) | 0.5 | 14 | 79% | 3 |

Noise-only worlds (5 worlds, 650 brand-weeks, 9750 line-weeks, no events): 8 false alarms, 1.23 per 100 brand-weeks, 0.16 per brand per 13 weeks.

### Development events

| event | brand | cause | detected | diagnosed as | lag | first finding |
|---|---|---|---|---|---|---|
| E01 | fernwood-goods | refunds | yes | refunds | 0 | Refunds ran 1.5x forecast (week of Nov 2 to Nov 16); SKU FW-2201 is 98% of the excess. Payouts $17,040 below forecast. |
| E02 | lark-and-pine | timing | yes | timing | 0 | Shopify paid out a smaller share of the week's sales than usual (week of Nov 30); $91,018 is held and should arrive in the following payout. |
| E03 | tidewater-swim | reserve | yes | reserve | 0 | Amazon settlement held $15,443 as a reserve (week of Nov 23). |
| E04 | copperleaf-tea | late_receivable | yes | late_receivable | 0 | Mapleton Gifts has not paid invoices that were due (week of Nov 16 to Nov 30); $10,841 overdue. |
| E05 | north-arc-outdoor | overspend | yes | overspend | 1 | Meta spend ran +54% vs plan (week of Nov 16 to Nov 30); $48,797 extra will hit the card statement and the next autopay. |
| E11 | north-arc-outdoor | one_off | yes | one_off | 0 | Unplanned payment to Hartwell Legal LLP ($24,000) (week of Dec 28). |
| E07 | marigold-skin | volume | yes | volume | 0 | Shopify sales ran -24% vs forecast (week of Dec 14 to Jan 4); payouts $113,513 below forecast. |
| E08 | bramble-pet | chargebacks | yes | chargebacks | 0 | Chargebacks of $9,745 vs $539 expected (week of Dec 7 to Dec 14). |
| E12 | bramble-pet | price | yes | price | 0 | TPL-202612 (Crateway Fulfillment) billed 29% above forecast ($17,141). |
| E09 | quillon-coffee | timing | yes | timing | 0 | PO-SPRING-DEP (Altura Green Coffee) paid week of Dec 14 instead of Jan 4 ($87,100). |
| E06 | saltmarsh-apparel | fx | yes | fx | 0 | PO-SPRING-DEP (Fenwick Mills) cost $13,467 more after the exchange rate moved (week of Jan 4). |
| E10 | hollis-home | price | yes | price | 0 | FRT-BFCM (Orchard Line Freight) billed 60% above forecast ($33,660). |

False alarms:

- fernwood-goods, ad_spend_accrual (overspend:google), week 0: Google spend ran +30% vs plan (week of Oct 26); $2,759 extra will hit the card statement and the next autopay.

### Holdout events (written after the freeze)

| event | brand | cause | detected | diagnosed as | lag | first finding |
|---|---|---|---|---|---|---|
| H01 | fernwood-goods | fees | yes | fees | 1 | Processing fees $2,900 above forecast (week of Nov 23 to Nov 30); check the fee rate. |
| H07 | lark-and-pine | one_off | yes | one_off | 0 | Unplanned payment to Brightline Studio ($15,000) (week of Nov 23). |
| H03 | tidewater-swim | timing | yes | timing | 0 | Shopify paid out a smaller share of the week's sales than usual (week of Nov 23); $234,869 is held and should arrive in the following payout. |
| H06 | copperleaf-tea | volume | yes | volume | 1 | Shopify sales ran -20% vs forecast (week of Nov 23 to Nov 30); payouts $45,015 below forecast. |
| H02 | bramble-pet | fees | yes | fees | 2 | Amazon fees $5,318 above forecast (week of Dec 21 to Jan 4); check the fee rate. |
| H04 | quillon-coffee | late_receivable | yes | late_receivable | 0 | Corner Larder has not paid invoices that were due (week of Dec 7 to Dec 21); $19,543 overdue. |
| H08 | saltmarsh-apparel | overspend | yes | overspend | 1 | Google spend ran +94% vs plan (week of Dec 14); $5,334 extra will hit the card statement and the next autopay. |
| H05 | hollis-home | refunds | yes | refunds | 0 | Refunds ran 1.6x forecast (week of Dec 28 to Jan 11); SKU HH-THROW is 88% of the excess. Payouts $12,167 below forecast. |

False alarms:

- north-arc-outdoor, ad_spend_accrual (overspend:meta), week 12: Meta spend ran +57% vs plan (week of Jan 18); $5,237 extra will hit the card statement and the next autopay.
- marigold-skin, ad_spend_accrual (overspend:meta), week 1: Meta spend ran +11% vs plan (week of Nov 2 to Nov 16); $5,605 extra will hit the card statement and the next autopay.
- saltmarsh-apparel, wholesale_receipts (volume), week 7: Wholesale invoices $24,210 above forecast (week of Dec 14).

## Reforecast after a finding

Mean absolute error at the weeks a finding was raised, against what actually happened.

| set | points | low point: roll forward | low point: with rules | ending cash: roll forward | ending cash: with rules |
|---|---|---|---|---|---|
| Development events | 18 | $9,998 | $6,371 | $19,308 | $13,081 |
| Holdout events (written after the freeze) | 12 | $6,473 | $5,600 | $12,855 | $13,924 |

## Week-0 forecast vs actual low point

- Development events: mean absolute low-point error $4,605; low week right for 100% of brands.
- Holdout events (written after the freeze): mean absolute low-point error $6,088; low week right for 100% of brands.
- Noise-only worlds: mean absolute low-point error $6,434.

## Bill-payment policies on the actual weeks (all 10 brands, 13 weeks)

**Development events**

| policy | discounts | interest | net | unplanned breach weeks | worst unplanned gap | rules broken |
|---|---|---|---|---|---|---|
| due_date | $0 | $952 | $-952 | 0 | $0 | 0 |
| pay_early | $35,237 | $1,111 | $34,127 | 0 | $0 | 0 |
| plan_once | $35,237 | $1,111 | $34,127 | 0 | $0 | 0 |
| monitored | $35,237 | $1,111 | $34,127 | 0 | $0 | 0 |

**Development events, $50K credit headroom**

| policy | discounts | interest | net | unplanned breach weeks | worst unplanned gap | rules broken |
|---|---|---|---|---|---|---|
| due_date | $0 | $635 | $-635 | 2 | $67,629 | 0 |
| pay_early | $35,237 | $635 | $34,603 | 2 | $140,937 | 0 |
| plan_once | $25,343 | $635 | $24,709 | 2 | $67,629 | 0 |
| monitored | $25,343 | $635 | $24,709 | 2 | $67,629 | 0 |

**Holdout events (written after the freeze)**

| policy | discounts | interest | net | unplanned breach weeks | worst unplanned gap | rules broken |
|---|---|---|---|---|---|---|
| due_date | $0 | $952 | $-952 | 0 | $0 | 0 |
| pay_early | $34,848 | $1,111 | $33,738 | 0 | $0 | 0 |
| plan_once | $34,848 | $1,111 | $33,738 | 0 | $0 | 0 |
| monitored | $34,848 | $1,005 | $33,843 | 0 | $0 | 0 |

**Holdout events (written after the freeze), $50K credit headroom**

| policy | discounts | interest | net | unplanned breach weeks | worst unplanned gap | rules broken |
|---|---|---|---|---|---|---|
| due_date | $0 | $635 | $-635 | 2 | $52,823 | 0 |
| pay_early | $34,848 | $635 | $34,214 | 2 | $127,012 | 0 |
| plan_once | $25,080 | $635 | $24,446 | 2 | $52,823 | 0 |
| monitored | $25,080 | $582 | $24,499 | 2 | $52,823 | 0 |

**Noise-only world 0**

| policy | discounts | interest | net | unplanned breach weeks | worst unplanned gap | rules broken |
|---|---|---|---|---|---|---|
| due_date | $0 | $952 | $-952 | 0 | $0 | 0 |
| pay_early | $35,058 | $1,111 | $33,948 | 0 | $0 | 0 |
| plan_once | $35,058 | $1,111 | $33,948 | 0 | $0 | 0 |
| monitored | $35,058 | $952 | $34,106 | 0 | $0 | 0 |

**Noise-only world 0, $50K credit headroom**

| policy | discounts | interest | net | unplanned breach weeks | worst unplanned gap | rules broken |
|---|---|---|---|---|---|---|
| due_date | $0 | $635 | $-635 | 2 | $37,770 | 0 |
| pay_early | $35,058 | $635 | $34,424 | 2 | $111,865 | 0 |
| plan_once | $24,967 | $635 | $24,333 | 2 | $37,770 | 0 |
| monitored | $24,967 | $529 | $24,438 | 2 | $37,770 | 0 |
