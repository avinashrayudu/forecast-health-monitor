"""
Freezes the monitor before the holdout events are written.

Records a sha256 of every file that decides what the monitor finds, how it
reforecasts and how the actions are planned, plus the development results at the
moment of the freeze. run_evals checks these hashes and prints whether anything
changed since.

Built by Avinash Rayudu.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FROZEN = ["world/engine.py", "world/calibrate.py", "config/overrides.yaml", "config/reforecast_rules.yaml",
          "monitor/attribute.py", "monitor/detect.py", "monitor/reforecast.py", "actions/plan.py",
          "actions/vendor_rules.yaml", "evals/run_evals.py"]


def main():
    files = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FROZEN}
    out = ROOT / "evals" / "FREEZE.json"
    out.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "note": "world/holdout_events.py did not exist when this was written",
                               "files": files}, indent=1))
    snap = ROOT / "evals" / "results" / "at_freeze"
    snap.mkdir(parents=True, exist_ok=True)
    for f in ("results.json", "results.md"):
        shutil.copy(ROOT / "evals" / "results" / f, snap / f)
    print(f"froze {len(files)} files -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
