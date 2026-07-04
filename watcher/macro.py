"""
Macro watcher — the global and political layer.

Scans official and world-news RSS feeds every cycle for high-signal
macro events: rate decisions, sanctions, export controls, tariffs,
regulation, conflict escalation. New hits go to Telegram as a digest.

These are information alerts, not trades. There is no mechanical
rule here worth auto-executing, because macro headlines do not map
to a testable buy/sell instruction the way the cluster rule does.
The value is awareness: you see the event within 2 hours, alongside
whatever the other signals are doing.

Tune WATCH_TERMS to your interests. Dedupe shares seen_items.json
with the main watcher.
"""

import json
import sys
from pathlib import Path

import feedparser

HERE = Path(__file__).parent
STATE_FILE = HERE / "seen_items.json"

MACRO_FEEDS = [
    # Official sources first
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://www.sec.gov/news/pressreleases.rss",
    "https://home.treasury.gov/rss/press.xml",
    # World / markets wires
    "https://feeds.apnews.com/rss/apf-WorldNews",
    "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
]

WATCH_TERMS = [
    # monetary / rates
    "rate decision", "rate cut", "rate hike", "fomc", "federal funds",
    "quantitative", "inflation report", "cpi",
    # trade / geopolitics
    "sanction", "export control", "export restriction", "tariff",
    "trade agreement", "embargo",
    # regulation / market structure
    "antitrust", "regulation", "sec charges", "investigation",
    # conflict / supply
    "strait", "pipeline", "opec", "military", "missile", "escalat",
]


def load_seen():
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()


def save_seen(seen):
    STATE_FILE.write_text(json.dumps(sorted(seen)[-5000:], indent=0))


def scan():
    hits = []
    for url in MACRO_FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue
        source = url.split("/")[2].replace("www.", "")
        for entry in feed.entries[:30]:
            title = entry.get("title", "")
            low = title.lower()
            matched = [t for t in WATCH_TERMS if t in low]
            if matched:
                hits.append(
                    {
                        "id": "macro:" + entry.get("link", title),
                        "title": title,
                        "source": source,
                        "terms": matched[:3],
                    }
                )
    return hits


def main():
    seen = load_seen()
    hits = [h for h in scan() if h["id"] not in seen]
    if not hits:
        print("macro: no new events")
        return
    lines = ["*Macro watch*"]
    for h in hits[:8]:
        lines.append(f"[{h['source']}] {h['title']}")
    lines.append("_Context, not instructions. No rule trades on these._")
    sys.path.insert(0, str(HERE))
    from main import send_telegram
    send_telegram("\n".join(lines))
    for h in hits:
        seen.add(h["id"])
    save_seen(seen)
    print(f"macro: {len(hits)} new events alerted")


if __name__ == "__main__":
    main()
