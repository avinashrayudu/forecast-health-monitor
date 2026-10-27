# Built by Avinash Rayudu
PY ?= python3

.PHONY: demo calibrate evals sheets reports test

demo: calibrate evals sheets reports test

calibrate:            ## per-brand forecast config from the onboarded ledgers
	$(PY) -m world.calibrate

evals:                ## development + noise-only + holdout scoring
	$(PY) -m evals.run_evals --holdout

sheets:               ## Fernwood workbook with live formulas, then compare it with the code
	$(PY) -m sheets.build_xlsx
	$(PY) -m sheets.check_xlsx

reports:              ## Cash Brief, 10-brand board, index
	$(PY) -m reports.build

test:
	$(PY) -m pytest -q tests

# evals/freeze.py was run once, before world/holdout_events.py was written.
# Running it again would overwrite that record, so it is not part of any target.
