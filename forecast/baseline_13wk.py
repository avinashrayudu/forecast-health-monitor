"""
The baseline 13-week direct cash forecast for one brand, printed as a table.

  python -m forecast.baseline_13wk fernwood-goods

The forecast is world.engine.book() fed the expected drivers. The monitor only
needs a forecast that keeps its drivers (sales, refunds by SKU, fees, payout
timing, settlements, invoices by retailer, bills, card spend by platform), so a
brand's own forecast can replace this one if it is stored at that grain.

Built by Avinash Rayudu.
"""
from __future__ import annotations

import sys

from world.engine import CASH_LINES, N_WEEKS, WEEKS, forecast
from world.inject_events import load_configs


def baseline(slug: str):
    return forecast(load_configs()[slug])


def main():
    slug = sys.argv[1] if len(sys.argv) > 1 else "fernwood-goods"
    fc = baseline(slug)
    print(f"{fc.cfg['brand']}: 13-week cash forecast from Oct 26, 2026 (synthetic), $K")
    print(f"{'':<22}" + "".join(f"{WEEKS[w].strftime('%b %d'):>8}" for w in range(N_WEEKS)))
    for line in CASH_LINES:
        if abs(fc.lines[line]).sum() > 0:
            print(f"{line:<22}" + "".join(f"{v / 1000:>8.0f}" for v in fc.lines[line]))
    print(f"{'closing cash':<22}" + "".join(f"{v / 1000:>8.0f}" for v in fc.cash))
    w, low = fc.low_point()
    print(f"low point ${low:,.0f} in the week of {WEEKS[w].strftime('%b %-d')}; buffer ${fc.cfg['cash_buffer']:,.0f}")


if __name__ == "__main__":
    main()
