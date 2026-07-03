"""
Holdings tracker — prices your real positions, read-only.

Edit holdings.json in this folder whenever your actual account
changes. Format:

  [
    {"ticker": "AAPL", "shares": 10, "cost_basis": 150.00},
    {"ticker": "VOO",  "shares": 5,  "cost_basis": 420.50}
  ]

cost_basis is your per-share purchase price (from your E*TRADE
positions page). Each scheduled run prices every position via the
free quote chain (Finnhub -> Alpaca -> yfinance) and writes
docs/my_holdings.json for the dashboard.

This is display only. Nothing here can place, modify, or cancel
a trade anywhere. Your broker credentials are never involved.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
DOCS = HERE.parent / "docs"
SRC = HERE / "holdings.json"


def get_price(ticker):
    sys.path.insert(0, str(HERE))
    try:
        from providers import quote
        q = quote(ticker)
        if q and q.get("price"):
            return float(q["price"]), q.get("day_change_pct")
    except Exception:
        pass
    try:
        import yfinance as yf
        h = yf.Ticker(ticker).history(period="5d")["Close"]
        if len(h) >= 2:
            return float(h.iloc[-1]), round((h.iloc[-1]/h.iloc[-2]-1)*100, 2)
        if len(h):
            return float(h.iloc[-1]), None
    except Exception:
        pass
    return None, None


def main():
    if not SRC.exists():
        print("no holdings.json; skipping (create one to track real positions)")
        return
    holdings = json.loads(SRC.read_text())
    rows, total_value, total_cost = [], 0.0, 0.0
    for h in holdings:
        tk = h["ticker"].upper()
        price, day_pct = get_price(tk)
        if price is None:
            rows.append({"ticker": tk, "error": "price unavailable"})
            continue
        value = price * h["shares"]
        cost = h.get("cost_basis", 0) * h["shares"]
        rows.append(
            {
                "ticker": tk,
                "shares": h["shares"],
                "price": round(price, 2),
                "value": round(value, 2),
                "day_change_pct": day_pct,
                "gain_pct": round((value / cost - 1) * 100, 1) if cost else None,
            }
        )
        total_value += value
        total_cost += cost
    DOCS.mkdir(exist_ok=True)
    (DOCS / "my_holdings.json").write_text(
        json.dumps(
            {
                "as_of": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                "total_value": round(total_value, 2),
                "total_gain_pct": round((total_value / total_cost - 1) * 100, 1)
                if total_cost else None,
                "positions": sorted(rows, key=lambda r: -(r.get("value") or 0)),
            },
            indent=0,
        )
    )
    print(f"priced {len(rows)} positions, total ${total_value:,.0f}")


if __name__ == "__main__":
    main()
