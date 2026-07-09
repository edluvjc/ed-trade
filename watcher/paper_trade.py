"""
Paper-trading harness — Alpaca paper account (free).

This is the honesty layer. Any strategy the watcher suggests gets
executed here with fake money and logged, so after 3-6 months you
have a real answer to "does following these signals beat doing
nothing," measured against a SPY buy-and-hold benchmark.

Strategy encoded (deliberately simple, so it's testable):
  - When a cluster alert fires, buy a fixed fraction of paper
    equity in that ticker.
  - Hold for HOLD_DAYS, then sell.
  - Log every entry/exit to trades_log.csv.

Rules of the harness:
  - Equal position sizes. No leverage. No averaging down.
  - If the signals have edge, it shows up here. If they don't,
    you learned that for $0.

Setup: free account at alpaca.markets -> paper trading keys ->
set ALPACA_KEY_ID and ALPACA_SECRET_KEY as env vars / GH secrets.
"""

import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

BASE = "https://paper-api.alpaca.markets/v2"
KEY = os.environ.get("ALPACA_KEY_ID", "")
SECRET = os.environ.get("ALPACA_SECRET_KEY", "")
HEADERS = {"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET}

POSITIONS_FILE = Path(__file__).parent / "open_positions.json"
LOG_FILE = Path(__file__).parent / "trades_log.csv"

POSITION_FRACTION = 0.05   # 5% of paper equity per signal
HOLD_DAYS = 30
STOP_LOSS_PCT = 0.10   # exit early if down 10% from entry
MAX_OPEN_POSITIONS = 12


def api(method, path, **kwargs):
    r = requests.request(method, BASE + path, headers=HEADERS, timeout=20, **kwargs)
    r.raise_for_status()
    return r.json() if r.text else {}


def account_equity():
    return float(api("GET", "/account")["equity"])


def log_trade(row):
    exists = LOG_FILE.exists()
    with open(LOG_FILE, "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(
                ["timestamp", "action", "ticker", "qty", "notional",
                 "reason", "equity_after"]
            )
        w.writerow(row)


def load_positions():
    if POSITIONS_FILE.exists():
        return json.loads(POSITIONS_FILE.read_text())
    return {}


def save_positions(p):
    POSITIONS_FILE.write_text(json.dumps(p, indent=2))


def latest_price(ticker):
    """Best-effort latest trade price from Alpaca's free data feed."""
    try:
        r = requests.get(
            f"https://data.alpaca.markets/v2/stocks/{ticker}/trades/latest",
            headers=HEADERS, timeout=15,
        )
        if r.ok:
            return float(r.json()["trade"]["p"])
    except Exception:
        pass
    return None


def enter(ticker, reason="cluster_signal"):
    """Open a paper position sized at POSITION_FRACTION of equity.
    Tries a notional (dollar-amount) order first; if Alpaca rejects
    it (non-fractionable asset, or market closed), falls back to a
    whole-share order queued for the next open. Never raises: a
    failed entry is logged and skipped so one bad ticker cannot
    kill the run."""
    if not KEY:
        print("[dry-run] Alpaca not configured; would buy", ticker)
        return False
    positions = load_positions()
    if ticker in positions:
        print(f"Already holding {ticker}, skipping")
        return False
    if len(positions) >= MAX_OPEN_POSITIONS:
        print("Max positions reached, skipping", ticker)
        return False
    try:
        equity = account_equity()
    except Exception as e:
        print(f"[warn] could not read account equity: {e}", file=sys.stderr)
        return False
    notional = round(equity * POSITION_FRACTION, 2)

    order = None
    try:
        order = api(
            "POST", "/orders",
            json={"symbol": ticker, "notional": str(notional),
                  "side": "buy", "type": "market", "time_in_force": "day"},
        )
        placed = notional
    except Exception as e:
        print(f"[info] notional order for {ticker} rejected ({e}); "
              "trying whole-share fallback", file=sys.stderr)
        price = latest_price(ticker)
        qty = int(notional // price) if price else 0
        if qty < 1:
            print(f"[warn] skipping {ticker}: no price or too expensive "
                  "for one share at this position size", file=sys.stderr)
            return False
        try:
            order = api(
                "POST", "/orders",
                json={"symbol": ticker, "qty": str(qty),
                      "side": "buy", "type": "market",
                      "time_in_force": "day"},
            )
            placed = round(qty * price, 2)
        except Exception as e2:
            print(f"[warn] skipping {ticker}: fallback order also "
                  f"rejected ({e2})", file=sys.stderr)
            return False

    positions[ticker] = {
        "entered": datetime.now(timezone.utc).isoformat(),
        "notional": placed,
        "order_id": order.get("id", ""),
        "reason": reason,
        "entry_price": latest_price(ticker),
    }
    save_positions(positions)
    log_trade(
        [datetime.now(timezone.utc).isoformat(), "BUY", ticker, "",
         placed, reason, equity]
    )
    print(f"Paper-bought ${placed} of {ticker}")
    return True


def exit_stale():
    """Close positions past HOLD_DAYS, or down STOP_LOSS_PCT from
    entry (the stop-loss runs every cycle, so worst case a loser
    lives ~2 hours past the threshold)."""
    if not KEY:
        return
    positions = load_positions()
    now = datetime.now(timezone.utc)
    for ticker, meta in list(positions.items()):
        entered = datetime.fromisoformat(meta["entered"])
        expired = now - entered >= timedelta(days=HOLD_DAYS)
        stopped = False
        entry_px = meta.get("entry_price")
        if not expired and entry_px:
            cur = latest_price(ticker)
            if cur and cur <= entry_px * (1 - STOP_LOSS_PCT):
                stopped = True
        if not (expired or stopped):
            continue
        why = f"hold_expired_{HOLD_DAYS}d" if expired else               f"stop_loss_{int(STOP_LOSS_PCT*100)}pct"
        try:
            api("DELETE", f"/positions/{ticker}")
            equity = account_equity()
            log_trade([now.isoformat(), "SELL", ticker, "", "", why, equity])
            del positions[ticker]
            print(f"Paper-sold {ticker} ({why})")
        except Exception as e:
            print(f"[warn] exit {ticker} failed: {e}", file=sys.stderr)
    save_positions(positions)


def benchmark_report():
    """Compare account equity vs SPY buy-and-hold since first trade."""
    if not LOG_FILE.exists():
        print("No trades logged yet.")
        return
    with open(LOG_FILE) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    first = rows[0]
    start_equity = float(first["equity_after"])
    current = account_equity()
    strat_ret = (current / start_equity - 1) * 100
    print(f"Strategy return since {first['timestamp'][:10]}: {strat_ret:.1f}%")
    print("Compare against SPY over the same window before drawing any conclusion.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "maintain"
    if cmd == "enter" and len(sys.argv) > 2:
        enter(sys.argv[2].upper())
    elif cmd == "report":
        benchmark_report()
    else:
        exit_stale()
