"""
Factor job — runs the cross-sectional engine on a schedule.

Weekly: ranks the full S&P 500 on momentum, value, quality, low-vol,
and size; publishes the ranking to docs/factor_ranking.json for the
dashboard; Telegrams the top names; and maintains a second paper
sleeve that auto-holds the top composite names.

The factor sleeve is tagged reason="factor_top" in the trade log, so
its performance can be separated from the congressional-cluster
sleeve later. Two strategies, one paper account, clean attribution.

Sleeve rule (deliberately simple and testable):
  - If fewer than FACTOR_SLOTS factor positions are open, enter the
    highest-ranked names not already held, one per free slot.
  - Exits happen via the existing 30-day hold machinery.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
DOCS = ROOT / "docs"
FACTOR_SLOTS = 3


def main():
    sys.path.insert(0, str(ROOT / "factors"))
    sys.path.insert(0, str(HERE))
    from screen import get_universe, fetch_prices, fetch_fundamentals, \
        compute_factors

    print("Factor job: universe + prices...")
    tickers, sectors = get_universe()
    prices = fetch_prices(tickers)
    fundamentals = fetch_fundamentals(list(prices.columns))
    z = compute_factors(prices, fundamentals)
    ranked = z.sort_values("composite", ascending=False)

    top = ranked.head(15)
    DOCS.mkdir(exist_ok=True)
    (DOCS / "factor_ranking.json").write_text(
        json.dumps(
            {
                "as_of": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                "top": [
                    {
                        "ticker": t,
                        "composite": round(float(r["composite"]), 2),
                        "momentum": round(float(r["momentum"]), 2),
                        "value": round(float(r["value"]), 2),
                        "quality": round(float(r["quality"]), 2),
                        "sector": sectors.get(t, ""),
                    }
                    for t, r in top.iterrows()
                ],
            },
            indent=0,
        )
    )

    # Telegram digest
    from main import send_telegram
    names = ", ".join(top.head(5).index)
    send_telegram(
        "*Weekly factor ranking*\n"
        f"Top composite: {names}\n"
        "_Factor exposure ranking, not a prediction. "
        "The factor sleeve auto-holds the top names in the paper "
        "account to test the rule._"
    )

    # Maintain the factor sleeve in the paper account
    from paper_trade import enter, load_positions
    positions = load_positions()
    factor_open = [t for t, m in positions.items()
                   if m.get("reason") == "factor_top"]
    free = FACTOR_SLOTS - len(factor_open)
    for ticker in top.index:
        if free <= 0:
            break
        if ticker in positions:
            continue
        try:
            if enter(ticker, reason="factor_top"):
                free -= 1
        except Exception as e:
            print(f"[warn] factor entry {ticker} failed: {e}")
    print("Factor job complete.")


if __name__ == "__main__":
    main()
