# Product patterns memo: what building this taught me

**Audience:** a team building finance agents for consumer products brands.
**Basis:** this repo's runs. All data is synthetic, so the numbers show the method, not real-world accuracy.

## 1. Explain the miss in the operator's words

"Shopify payouts are $14,547 under forecast" is a fact. "Refunds ran 1.7x forecast and SKU FW-2201 is 99% of the excess" is something an operator can act on.

The attribution swaps one driver at a time from forecast to actual. The pieces always add up to the line's variance, and a test checks this on every line of every brand. If the pieces did not add up, any explanation would have a gap someone could argue with.

**Pattern:** store forecasts at driver grain, not line grain. You cannot explain a line-level forecast afterward.

## 2. Each brand gets its own noise model and a false-alarm budget

A fixed threshold, like "flag anything over 10%", either buries a small brand in alerts or misses real drift at a large one.

Here, every driver is tested against its own normal noise, measured from the brand's history, and against a materiality floor. Five noise-only worlds measure the cost of that choice: 650 brand-weeks with no events produced 8 false alarms, about 0.16 per brand per quarter.

**Pattern:** publish a false-alarm budget per brand and measure it on replayed history before go-live.

## 3. Separate timing from permanent misses

A held Shopify payout ($91K at Lark & Pine) and a sales miss ($114K at Marigold) look alike in the week they happen. They call for opposite actions:

- the held payout comes back next week;
- the sales miss keeps compounding.

The monitor labels timing findings and pairs them with their reversal. The reforecast carries forward only the permanent kinds.

## 4. Watch money before it becomes cash

Ad spend on the card is not cash until the next autopay, three to seven weeks later.

At North Arc, the Meta overspend was flagged in the week of Nov 16, five weeks before it reached the bank in the Dec 22 autopay.

**Pattern:** the most useful lead time comes from accruals the bank cannot see yet: card spend, open POs and issued bills.

## 5. An action needs rules as well as a forecast

### Early-pay discounts
- **The math:** 2/10 net 30 is worth about 37% a year and 1/10 net 30 about 18%. A credit line at 11% is cheaper than either.
- **Result:** with normal credit headroom, every forecast-aware policy took every discount, the same as "always pay early".
- **Where the forecast matters:** with only $50K of headroom, "always pay early" deepened the worst unplanned dip under the buffer from about $68K to about $141K on the development set. The forecast-aware policy gave up about $10K of discounts to avoid that.

### Vendor rules
The rules held under every policy:
- inventory, freight and 3PL never paid late;
- software renewals movable by up to two weeks.

**Pattern:** let the founder state the rules once (criticality, buffer, draw size), and keep any action that would break one off the table.

## 6. Size draws with a cushion

The first frozen version sized credit draws to the exact forecast gap. On the holdout run, two brands dipped under the buffer by up to $2,717 in a week the forecast could not see yet.

**The change:** adding 1.65 standard deviations of unseen receipts to each draw removed those breaches in every run with normal credit headroom. The cost was about $210 to $320 more interest across ten brands over 13 weeks, depending on the policy and the run.

This was a post-holdout change, and the README labels it as one.

## 7. Grade the system on hidden answers

The scorer has three parts:
- injected events with labels the monitor never reads (a test enforces this);
- a holdout set written after the freeze;
- noise-only worlds.

On the holdout, the monitor found 8 of 8 events and named the right cause for all 8. That included two kinds it had never seen: a Shopify fee change and an Amazon fee change.

Two weaknesses also showed up:
- the reforecast had no rule for fees;
- the volume rule carried a BFCM miss four weeks too far.

## 8. Where this stops being evidence

- **The world and the forecast share one engine.** Real brands have causes the driver model does not contain, so real attribution accuracy will be lower than 100%.
- **The events are mine.** I wrote the holdout after the freeze, but by the same hand.
- **All 10 brands are synthetic.** They come from dtc-cash-onboarding.

## Relevance to Highbeam

What I could verify publicly:
- Luma generates code against the Vault semantic layer rather than having the model read raw data.
- Highbeam says Luma ingests and cleans financial data automatically.
- Bill Pay recognizes, categorizes and routes bills.

This repo follows the same split. Code computes every number, and the text is filled from computed findings. I did not find public detail on whether Bill Pay times payments against a cash forecast, so section 5 is a proposal, not a comparison.

The 2.58% savings APY used in the sweep-versus-paydown step is the rate Highbeam showed publicly on 9/17/26. Please verify it before reuse.

Built by Avinash Rayudu.
