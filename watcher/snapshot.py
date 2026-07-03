"""
Performance snapshot — run by the workflow after each watcher cycle.

Appends one row to docs/performance.json:
  { "ts": iso8601, "equity": paper account equity, "spy": SPY price }

The dashboard (docs/index.html) normalizes both series to 100 at
the first snapshot taken after the first paper trade, so the chart
is a fair race from a common start line.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

DOCS = Path(__file__).parent.parent / "docs"
PERF = DOCS / "performance.json"

ALPACA = "https://paper-api.alpaca.markets/v2"
KEY = os.environ.get("ALPACA_KEY_ID", "")
SECRET = os.environ.get("ALPACA_SECRET_KEY", "")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")


def get_equity():
    r = requests.get(
        ALPACA + "/account",
        headers={"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET},
        timeout=15,
    )
    r.raise_for_status()
    return float(r.json()["equity"])


def get_spy():
    if FINNHUB_KEY:
        r = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": "SPY", "token": FINNHUB_KEY},
            timeout=15,
        )
        if r.ok and r.json().get("c"):
            return float(r.json()["c"])
    import yfinance as yf
    h = yf.Ticker("SPY").history(period="5d")
    return float(h["Close"].iloc[-1])


def main():
    if not KEY:
        print("Alpaca keys not set; skipping snapshot")
        return
    DOCS.mkdir(exist_ok=True)
    rows = json.loads(PERF.read_text()) if PERF.exists() else []
    try:
        rows.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                "equity": get_equity(),
                "spy": get_spy(),
            }
        )
    except Exception as e:
        print(f"[warn] snapshot failed: {e}", file=sys.stderr)
        return
    PERF.write_text(json.dumps(rows, indent=0))
    print(f"snapshot #{len(rows)} written")


if __name__ == "__main__":
    main()
