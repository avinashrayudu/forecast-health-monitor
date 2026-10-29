# Changelog

Each version lists the commits it covers. Built by Avinash Rayudu.

## How commits are structured

From v1.2.0 on, every commit message starts with its type:

| Type | Used for |
|---|---|
| `feat:` | new behavior in the forecast, monitor, actions or evals |
| `fix:` | a bug fix; the message names what was wrong |
| `freeze:` | hashes recorded before a holdout is written; nothing else in the commit |
| `data:` | new or regenerated synthetic data or events |
| `results:` | output of a run, committed as it came out; nothing else in the commit |
| `docs:` | README and docs only; no number changes without a matching `results:` commit |
| `chore:` | tooling and housekeeping |

A holdout is always `freeze:`, then `data:`, then `results:`.

## v1.2.0 (2026-10-28)

- docs: the so-what at the top of the README; every threshold explained in plain language, including the buffer,
  the cushion and the discount math.
- docs: `docs/finance_concepts.md` (AP and AR, cash vs accrual, the three-way match, tied to the projects).
- docs: where the project fits at Highbeam; how it was built.
- docs: the Zacao note now cites the verified receivables reconciliation instead of unverified figures.

## v1.1.0 (2026-10-28)

- `9c9a80e` docs: Fernwood's week-0 closing cash by week.
- `68c73a3` feat and docs: the variance bridge in the brief; README leads with the brief and the tight-credit result;
  the buffer rationale; the corrected Fernwood plan vs ledger gap (about 1.9x, not 30%).

## v1.0.0 (2026-10-27): first publication

- `73f37aa` the engine, 10 brands, 12 development and 8 holdout events (first holdout run kept in
  `evals/results/holdout_v1_frozen/`), the fixes that followed it, the Excel twin, 11 tests and the reports.
