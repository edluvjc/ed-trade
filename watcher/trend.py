"""
Trend template sleeve — a mechanical version of the Minervini-style
trend filter, run weekly, traded as a third paper sleeve so it can
be compared head-to-head with the congressional and factor sleeves.

The checklist (all must pass, computed from free daily data):
  1. Price above the 150-day and 200-day moving averages
  2. 150-day above the 200-day
  3. 200-day rising (higher than it was one month ago)
  4. Price at least 30% above the 52-week low
  5. Price within 25% of the 52-week high
  6. Relative strength vs SPY in the top decile of the universe
     over the trailing 6 months

Qualifiers are ranked by 6-month relative strength; the sleeve
holds up to TREND_SLOTS names tagged reason="trend_template".
Exits: the shared 30-day hold plus the shared stop-loss in
paper_trade.maintain().

This encodes the *mechanical* part of the approach. The
discretionary chart-reading part (bases, pivots, volume patterns)
is deliberately not imitated, because a rule that requires human
judgment cannot be honestly backtested or blamed.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
DOCS = ROOT / "docs"
TREND_SLOTS = 2


def trend_template(prices, spy):
    """Return DataFrame of qualifying tickers with rel strength."""
    import pandas as pd
    out = []
    if len(prices) < 260:
        raise SystemExit("need ~13 months of daily prices")
    ma150 = prices.rolling(150).mean().iloc[-1]
    ma200 = prices.rolling(200).mean()
    ma200_now, ma200_prev = ma200.iloc[-1], ma200.iloc[-22]
    px = prices.iloc[-1]
    hi52 = prices.iloc[-252:].max()
    lo52 = prices.iloc[-252:].min()
    ret6m = px / prices.iloc[-126] - 1
    spy6m = float(spy.iloc[-1] / spy.iloc[-126] - 1)
    rel = ret6m - spy6m
    rel_cut = rel.quantile(0.90)
    for tk in prices.columns:
        try:
            if not (
                px[tk] > ma150[tk]
                and px[tk] > ma200_now[tk]
                and ma150[tk] > ma200_now[tk]
                and ma200_now[tk] > ma200_prev[tk]
                and px[tk] >= lo52[tk] * 1.30
                and px[tk] >= hi52[tk] * 0.75
                and rel[tk] >= rel_cut
            ):
                continue
        except (KeyError, TypeError):
            continue
        out.append({"ticker": tk, "rel_strength_6m": round(float(rel[tk]), 3)})
    out.sort(key=lambda r: -r["rel_strength_6m"])
    return out


def main():
    sys.path.insert(0, str(ROOT / "factors"))
    sys.path.insert(0, str(HERE))
    from screen import get_universe, fetch_prices
    import yfinance as yf

    print("Trend template: universe + 13mo prices...")
    tickers, _ = get_universe()
    prices = fetch_prices(tickers, period="14mo")
    spy = yf.download("SPY", period="14mo", auto_adjust=True,
                      progress=False)["Close"]
    if hasattr(spy, "columns"):
        spy = spy.iloc[:, 0]

    qual = trend_template(prices, spy)
    print(f"{len(qual)} tickers pass the template")

    DOCS.mkdir(exist_ok=True)
    (DOCS / "trend_ranking.json").write_text(json.dumps({
        "as_of": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "qualifiers": qual[:15],
    }, indent=0))

    from main import send_telegram
    if qual:
        names = ", ".join(q["ticker"] for q in qual[:5])
        send_telegram(
            "*Weekly trend template*\n"
            f"Top qualifiers: {names}\n"
            "_Mechanical trend filter (Minervini-style). The trend "
            "sleeve auto-holds the top names in the paper account "
            "to test the rule against the other two sleeves._"
        )
    else:
        send_telegram(
            "*Weekly trend template*\nNo qualifiers this week — "
            "in weak markets the filter goes to cash by design."
        )

    from paper_trade import enter, load_positions
    positions = load_positions()
    open_trend = [t for t, m in positions.items()
                  if m.get("reason") == "trend_template"]
    free = TREND_SLOTS - len(open_trend)
    for q in qual:
        if free <= 0:
            break
        if q["ticker"] in positions:
            continue
        try:
            if enter(q["ticker"], reason="trend_template"):
                free -= 1
        except Exception as e:
            print(f"[warn] trend entry {q['ticker']} failed: {e}")
    print("Trend sleeve maintained.")


if __name__ == "__main__":
    main()
