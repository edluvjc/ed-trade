"""
Actions — turns the system's state into explicit instructions.

Writes docs/actions.json with three lists the dashboard renders:

  buy:   new signal clusters not currently held (candidates for
         a paper entry via `paper_trade.py enter TICKER`)
  hold:  open paper positions inside their hold window, with a
         countdown of days remaining
  sell:  open paper positions past the hold window (the next
         scheduled run exits them automatically)

These are the mechanical outputs of the ruleset. They are exact,
they are timestamped, and they carry countdowns — and none of that
makes them predictions. The dashboard says so on the page.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
DOCS = HERE.parent / "docs"
HOLD_DAYS = 30


def main():
    from main import fetch_congress_trades, find_clusters

    positions = {}
    pos_file = HERE / "open_positions.json"
    if pos_file.exists():
        positions = json.loads(pos_file.read_text())

    clusters = find_clusters(fetch_congress_trades())
    now = datetime.now(timezone.utc)

    buy = []
    for c in clusters:
        if c["ticker"] in positions:
            continue
        buy.append(
            {
                "ticker": c["ticker"],
                "why": f"{len(c['buyers'])} politicians bought within 21 days",
                "detail": ", ".join(c["buyers"][:3])
                + ("…" if len(c["buyers"]) > 3 else ""),
            }
        )

    hold, sell = [], []
    for tk, meta in positions.items():
        entered = datetime.fromisoformat(meta["entered"])
        exit_date = entered + timedelta(days=HOLD_DAYS)
        days_left = (exit_date - now).days
        row = {
            "ticker": tk,
            "entered": meta["entered"][:10],
            "exit_date": exit_date.strftime("%Y-%m-%d"),
        }
        if days_left > 0:
            row["days_left"] = days_left
            row["why"] = f"{days_left} days left in the {HOLD_DAYS}-day hold"
            hold.append(row)
        else:
            row["why"] = "hold window complete; next run exits automatically"
            sell.append(row)

    DOCS.mkdir(exist_ok=True)
    (DOCS / "actions.json").write_text(
        json.dumps(
            {
                "generated": now.isoformat(timespec="minutes"),
                "buy": buy[:8],
                "hold": sorted(hold, key=lambda r: r["days_left"]),
                "sell": sell,
            },
            indent=0,
        )
    )
    print(f"actions: {len(buy)} buy, {len(hold)} hold, {len(sell)} sell")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(HERE))
    main()
