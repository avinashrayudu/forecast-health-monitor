# Evaluation results

Detector: z = 3.0, windows [1, 2, 4] weeks. Freeze check: no freeze recorded.

## Detection and diagnosis

| set | events | detected | correct cause | median lag (wks) | findings | precision | false alarms |
|---|---|---|---|---|---|---|---|
| Development events | 12 | 12 (100%) | 12 (100%) | 0.0 | 18 | 94% | 1 |

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

## Reforecast after a finding

Mean absolute error at the weeks a finding was raised, against what actually happened.

| set | points | low point: roll forward | low point: with rules | ending cash: roll forward | ending cash: with rules |
|---|---|---|---|---|---|
| Development events | 18 | $9,998 | $6,371 | $19,308 | $13,081 |

## Week-0 forecast vs actual low point

- Development events: mean absolute low-point error $4,605; low week right for 100% of brands.
- Noise-only worlds: mean absolute low-point error $6,434.

## Bill-payment policies on the actual weeks (all 10 brands, 13 weeks)

**Development events**

| policy | discounts | interest | net | unplanned breach weeks | worst unplanned gap | rules broken |
|---|---|---|---|---|---|---|
| due_date | $0 | $635 | $-635 | 1 | $2,629 | 0 |
| pay_early | $35,237 | $793 | $34,444 | 1 | $937 | 0 |
| plan_once | $35,237 | $793 | $34,444 | 1 | $937 | 0 |
| monitored | $35,237 | $846 | $34,391 | 0 | $0 | 0 |

**Development events, $50K credit headroom**

| policy | discounts | interest | net | unplanned breach weeks | worst unplanned gap | rules broken |
|---|---|---|---|---|---|---|
| due_date | $0 | $423 | $-423 | 2 | $77,629 | 0 |
| pay_early | $35,237 | $423 | $34,814 | 2 | $150,937 | 0 |
| plan_once | $25,343 | $423 | $24,920 | 2 | $77,629 | 0 |
| monitored | $25,343 | $423 | $24,920 | 2 | $77,629 | 0 |

**Noise-only world 0**

| policy | discounts | interest | net | unplanned breach weeks | worst unplanned gap | rules broken |
|---|---|---|---|---|---|---|
| due_date | $0 | $635 | $-635 | 1 | $1,652 | 0 |
| pay_early | $35,058 | $793 | $34,265 | 1 | $1,652 | 0 |
| plan_once | $35,058 | $793 | $34,265 | 1 | $1,652 | 0 |
| monitored | $35,058 | $793 | $34,265 | 0 | $0 | 0 |

**Noise-only world 0, $50K credit headroom**

| policy | discounts | interest | net | unplanned breach weeks | worst unplanned gap | rules broken |
|---|---|---|---|---|---|---|
| due_date | $0 | $423 | $-423 | 3 | $47,770 | 0 |
| pay_early | $35,058 | $423 | $34,635 | 3 | $121,865 | 0 |
| plan_once | $24,967 | $423 | $24,544 | 3 | $47,770 | 0 |
| monitored | $24,967 | $476 | $24,491 | 2 | $47,770 | 0 |
