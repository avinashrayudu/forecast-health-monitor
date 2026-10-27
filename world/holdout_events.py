"""
Holdout events, written after the monitor was frozen (evals/FREEZE.json).

They use a fresh noise seed ("holdout") and include two causes the development set
never had (a processing-fee change and an Amazon fee change), plus events inside
the November trough for brands that sit close to their buffer.

Built by Avinash Rayudu.
"""
HOLDOUT_EVENTS = [
    dict(id="H01", brand="fernwood-goods", cause="fees", line="dtc_payouts", start=4, end=12,
         desc="Shopify Payments rate rises 0.5 points from BFCM week", params={"delta": 0.005}),
    dict(id="H02", brand="bramble-pet", cause="fees", line="marketplace_payouts", start=6, end=12,
         desc="Amazon referral and FBA fees rise 3 points", params={"delta": 0.03}),
    dict(id="H03", brand="tidewater-swim", cause="timing", line="dtc_payouts", start=4, end=4,
         desc="Shopify holds most of the BFCM week payout", params={"lag": 0.8}),
    dict(id="H04", brand="quillon-coffee", cause="late_receivable", line="wholesale_receipts", start=6, end=8,
         desc="Corner Larder pays two weeks late", params={"retailer": "Corner Larder", "delay": 2}),
    dict(id="H05", brand="hollis-home", cause="refunds", line="dtc_payouts", start=9, end=10,
         desc="January returns on HH-THROW run 3x", params={"sku": "HH-THROW", "mult": 3.0}),
    dict(id="H06", brand="copperleaf-tea", cause="volume", line="dtc_payouts", start=3, end=5,
         desc="BFCM sales come in 20% under plan", params={"mult": 0.80}),
    dict(id="H07", brand="lark-and-pine", cause="one_off", line="other_opex", start=4, end=4,
         desc="unplanned photo shoot invoice paid by wire", params={"counterparty": "Brightline Studio",
                                                                  "amount": 15000.0}),
    dict(id="H08", brand="saltmarsh-apparel", cause="overspend", line="ad_spend_accrual", start=6, end=7,
         desc="Google holiday campaigns run 60% over plan", params={"platform": "google", "mult": 1.6}),
]
