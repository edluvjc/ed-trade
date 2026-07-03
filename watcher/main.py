"""
Market Watcher — free-tier signal aggregator.

Pulls three streams, scores overlaps, alerts via Telegram:
  1. Congressional stock disclosures (House Clerk + Senate eFD via
     the public JSON mirrors maintained by the unitedstates project
     and direct scraping fallback)
  2. News via RSS (Reuters, AP, sector feeds — no API key needed)
  3. Price/volume context via yfinance (free, ~15min delayed)

Designed to run on a schedule (GitHub Actions cron). Stateless
between runs except for seen_items.json, which is committed back
to the repo by the workflow so you never get duplicate alerts.

This tool surfaces information. It does not predict, recommend,
or trade real money. Paper trading only (see paper_trade.py).
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests
import yfinance as yf

# ---------------------------------------------------------------
# Config
# ---------------------------------------------------------------

STATE_FILE = Path(__file__).parent / "seen_items.json"
CONFIG_FILE = Path(__file__).parent / "config.json"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Senate Stock Watcher / House Stock Watcher public mirrors.
# These are free, community-maintained JSON dumps of the official
# eFD / House Clerk filings, updated daily.
SENATE_FEED = (
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com"
    "/aggregate/all_transactions.json"
)
HOUSE_FEED = (
    "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com"
    "/data/all_transactions.json"
)

RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.apnews.com/rss/apf-business",
    "https://www.sec.gov/news/pressreleases.rss",
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
]

LOOKBACK_DAYS = 21          # how far back a disclosure still "counts"
CLUSTER_THRESHOLD = 2       # N distinct politicians on same ticker = cluster
MIN_TRADE_SIZE = 15000      # ignore trades below this midpoint estimate


# ---------------------------------------------------------------
# State (dedupe across runs)
# ---------------------------------------------------------------

def load_state():
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()


def save_state(seen):
    # Keep the file bounded
    STATE_FILE.write_text(json.dumps(sorted(seen)[-5000:], indent=0))


# ---------------------------------------------------------------
# Stream 1: Congressional disclosures
# ---------------------------------------------------------------

AMOUNT_MIDPOINTS = {
    "$1,001 - $15,000": 8000,
    "$15,001 - $50,000": 32500,
    "$50,001 - $100,000": 75000,
    "$100,001 - $250,000": 175000,
    "$250,001 - $500,000": 375000,
    "$500,001 - $1,000,000": 750000,
    "$1,000,001 - $5,000,000": 3000000,
}


def fetch_congress_trades():
    """Return recent purchase transactions from both chambers."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    trades = []
    for url, chamber in [(SENATE_FEED, "Senate"), (HOUSE_FEED, "House")]:
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[warn] {chamber} feed failed: {e}", file=sys.stderr)
            continue
        for t in data:
            try:
                # Field names differ slightly between the two feeds
                date_str = t.get("transaction_date") or t.get("date", "")
                tdate = datetime.strptime(date_str, "%m/%d/%Y").replace(
                    tzinfo=timezone.utc
                )
            except (ValueError, TypeError):
                continue
            if tdate < cutoff:
                continue
            ttype = (t.get("type") or t.get("transaction_type") or "").lower()
            if "purchase" not in ttype:
                continue
            ticker = (t.get("ticker") or "").strip().upper()
            if not ticker or ticker in ("--", "N/A"):
                continue
            amount = AMOUNT_MIDPOINTS.get(t.get("amount", ""), 0)
            if amount < MIN_TRADE_SIZE:
                continue
            who = t.get("senator") or t.get("representative") or "Unknown"
            trades.append(
                {
                    "id": f"{chamber}:{who}:{ticker}:{date_str}",
                    "chamber": chamber,
                    "who": who,
                    "ticker": ticker,
                    "date": date_str,
                    "amount_mid": amount,
                }
            )
    return trades


def find_clusters(trades):
    """Group by ticker; flag tickers bought by >= CLUSTER_THRESHOLD
    distinct politicians within the lookback window."""
    by_ticker = {}
    for t in trades:
        by_ticker.setdefault(t["ticker"], []).append(t)
    clusters = []
    for ticker, ts in by_ticker.items():
        buyers = {t["who"] for t in ts}
        if len(buyers) >= CLUSTER_THRESHOLD:
            clusters.append(
                {
                    "ticker": ticker,
                    "buyers": sorted(buyers),
                    "total_mid": sum(t["amount_mid"] for t in ts),
                    "trades": ts,
                }
            )
    clusters.sort(key=lambda c: (-len(c["buyers"]), -c["total_mid"]))
    return clusters


# ---------------------------------------------------------------
# Stream 2: News RSS
# ---------------------------------------------------------------

def fetch_news(tickers):
    """News per ticker. Prefers Finnhub company-news (free key,
    real per-ticker coverage); falls back to RSS keyword matching
    when no key is set or the call fails."""
    try:
        from providers import company_news
        hits = []
        for tk in tickers:
            hits.extend(company_news(tk))
        if hits:
            return hits
    except Exception as e:
        print(f"[warn] finnhub news failed: {e}", file=sys.stderr)
    return _fetch_news_rss(tickers)


def _fetch_news_rss(tickers):
    """Fallback: scan RSS feeds for headlines mentioning a watched
    ticker or company name. Cheap keyword match, not NLP."""
    watch_words = set()
    names = {}
    for tk in tickers:
        watch_words.add(tk)
        try:
            info = yf.Ticker(tk).info
            name = info.get("shortName") or ""
            # First word of company name, e.g. "Lockheed" from
            # "Lockheed Martin Corporation"
            first = re.split(r"[\s,]+", name)[0]
            if len(first) > 3:
                names[first.lower()] = tk
        except Exception:
            pass

    hits = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            continue
        for entry in feed.entries[:40]:
            title = entry.get("title", "")
            low = title.lower()
            matched = None
            for word, tk in names.items():
                if word in low:
                    matched = tk
                    break
            if not matched:
                for tk in tickers:
                    if re.search(rf"\b{re.escape(tk)}\b", title):
                        matched = tk
                        break
            if matched:
                hits.append(
                    {
                        "id": f"news:{entry.get('link', title)}",
                        "ticker": matched,
                        "title": title,
                        "link": entry.get("link", ""),
                    }
                )
    return hits


# ---------------------------------------------------------------
# Stream 3: Price context
# ---------------------------------------------------------------

def price_context(ticker):
    """1-month momentum + volume anomaly. yfinance first, Alpaca
    free IEX bars as fallback when yfinance is down or blocked."""
    try:
        hist = yf.Ticker(ticker).history(period="1mo")
        if len(hist) < 5:
            raise ValueError("insufficient yfinance history")
        ret_1m = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
        avg_vol = hist["Volume"][:-1].mean()
        vol_ratio = hist["Volume"].iloc[-1] / avg_vol if avg_vol else 1
        return {"ret_1m_pct": round(ret_1m, 1), "vol_ratio": round(vol_ratio, 1)}
    except Exception:
        try:
            from providers import recent_bars
            return recent_bars(ticker)
        except Exception:
            return None


# ---------------------------------------------------------------
# Alerting
# ---------------------------------------------------------------

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[dry-run] Telegram not configured. Message:\n" + text)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
    except Exception as e:
        print(f"[warn] Telegram send failed: {e}", file=sys.stderr)


def format_cluster_alert(cluster, ctx, news_items):
    lines = [
        f"*Signal cluster: {cluster['ticker']}*",
        f"{len(cluster['buyers'])} politicians bought within "
        f"{LOOKBACK_DAYS} days (~${cluster['total_mid']:,} midpoint total)",
        "Buyers: " + ", ".join(cluster["buyers"][:5]),
    ]
    if ctx:
        lines.append(
            f"1mo return: {ctx['ret_1m_pct']}% | "
            f"volume vs avg: {ctx['vol_ratio']}x"
        )
    for n in news_items[:3]:
        lines.append(f"News: {n['title']}")
    lines.append(
        "_Disclosures lag actual trades by up to 45 days. "
        "This is information, not advice._"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------

def main():
    seen = load_state()
    trades = fetch_congress_trades()
    print(f"Fetched {len(trades)} recent congressional purchases")

    clusters = find_clusters(trades)
    print(f"Found {len(clusters)} ticker clusters")

    cluster_tickers = [c["ticker"] for c in clusters]
    news = fetch_news(cluster_tickers) if cluster_tickers else []

    alerts_sent = 0
    for cluster in clusters:
        key = "cluster:" + cluster["ticker"] + ":" + ",".join(cluster["buyers"])
        if key in seen:
            continue
        ctx = price_context(cluster["ticker"])
        related_news = [n for n in news if n["ticker"] == cluster["ticker"]]
        send_telegram(format_cluster_alert(cluster, ctx, related_news))
        seen.add(key)
        alerts_sent += 1
        time.sleep(1)

    # Also alert on fresh news for previously-flagged tickers
    for n in news:
        if n["id"] in seen:
            continue
        seen.add(n["id"])

    save_state(seen)
    print(f"Done. {alerts_sent} new cluster alerts.")


if __name__ == "__main__":
    main()
