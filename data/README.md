# Data

`ledgers/` holds the labeled cash ledgers for 10 synthetic brands. They were produced by
[dtc-cash-onboarding](https://github.com/avinashrayudu/dtc-cash-onboarding), which turns each brand's raw exports
(Shopify, Amazon, bank, card, wholesale) into one tied-out ledger.

| File | What it is |
|---|---|
| `<brand>_upload_1.csv`, `<brand>_upload_2.csv` | two overlapping uploads of the ledger; duplicates are flagged in `is_duplicate` |
| `<brand>_brand.yaml` | brand name and currency from the kickoff call |

Columns: `source, file, row, date, account, description, amount, label, method, confidence, is_duplicate`.

`world/calibrate.py` reads Jul 6 to Oct 25, 2026 from these files to set each brand's weekly levels, noise,
payroll calendar, ad platform mix and credit line. Every brand, vendor and number is synthetic.
