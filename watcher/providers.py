"""
Free-tier data providers with fallback chain.

Order of preference:
  news:   Finnhub company-news (free, real coverage per ticker)
          -> RSS keyword matching (old method, fallback)
  quotes: Finnhub real-time quote (free)
          -> Alpaca IEX feed (free with paper keys; ~2-5% of
             consolidated volume, fine for signals, not execution)
          -> yfinance (delayed, fragile, last resort)
  history: yfinance (still the only free deep-history source;
          Alpaca free covers recent years as backup)

Keys (all free):
  FINNHUB_KEY        from finnhub.io (60 calls/min free tier)
  ALPACA_KEY_ID /
  ALPACA_SECRET_KEY  same paper keys you already have

Note on Finnhub free tier: quote and company-news endpoints are
free; historical candles and the pre-scored sentiment endpoint are
paid. This module only touches free endpoints and degrades
gracefully if a key is missing or an endpoint turns out to be
gated — every function returns None/[] rather than raising.
"""

import os
from datetime import datetime, timedelta, timezone

import requests

FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")
ALPACA_KEY = os.environ.get("ALPACA_KEY_ID", "")
ALPACA_SECRET = os.environ.get("ALPACA_SECRET_KEY", "")

FINNHUB = "https://finnhub.io/api/v1"
ALPACA_DATA = "https://data.alpaca.markets/v2"


def _get(url, params=None, headers=None):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


# ------------------------------------------------------------------
# News
# ------------------------------------------------------------------

def company_news(ticker, days=7, limit=5):
    """Finnhub company news, free tier. Returns [] on any failure
    so the caller can fall back to RSS."""
    if not FINNHUB_KEY:
        return []
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    data = _get(
        f"{FINNHUB}/company-news",
        params={
            "symbol": ticker,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "token": FINNHUB_KEY,
        },
    )
    if not isinstance(data, list):
        return []
    out = []
    for item in data[:limit]:
        out.append(
            {
                "id": f"news:{item.get('id', item.get('url', ''))}",
                "ticker": ticker,
                "title": item.get("headline", ""),
                "link": item.get("url", ""),
                "source": item.get("source", ""),
            }
        )
    return out


# ------------------------------------------------------------------
# Quotes
# ------------------------------------------------------------------

def quote(ticker):
    """Current price + day change. Finnhub -> Alpaca -> None."""
    if FINNHUB_KEY:
        data = _get(f"{FINNHUB}/quote",
                    params={"symbol": ticker, "token": FINNHUB_KEY})
        if data and data.get("c"):
            return {
                "price": data["c"],
                "day_change_pct": data.get("dp"),
                "source": "finnhub",
            }
    if ALPACA_KEY:
        data = _get(
            f"{ALPACA_DATA}/stocks/{ticker}/trades/latest",
            headers={
                "APCA-API-KEY-ID": ALPACA_KEY,
                "APCA-API-SECRET-KEY": ALPACA_SECRET,
            },
        )
        if data and data.get("trade", {}).get("p"):
            return {
                "price": data["trade"]["p"],
                "day_change_pct": None,
                "source": "alpaca_iex",
            }
    return None


# ------------------------------------------------------------------
# Recent daily bars (Alpaca free, backup to yfinance)
# ------------------------------------------------------------------

def recent_bars(ticker, days=35):
    """Daily bars from Alpaca's free IEX feed. Enough for the
    watcher's 1-month price context if yfinance is down."""
    if not ALPACA_KEY:
        return None
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%d"
    )
    data = _get(
        f"{ALPACA_DATA}/stocks/{ticker}/bars",
        params={"timeframe": "1Day", "start": start, "feed": "iex",
                "limit": days},
        headers={
            "APCA-API-KEY-ID": ALPACA_KEY,
            "APCA-API-SECRET-KEY": ALPACA_SECRET,
        },
    )
    bars = (data or {}).get("bars")
    if not bars:
        return None
    closes = [b["c"] for b in bars]
    vols = [b["v"] for b in bars]
    if len(closes) < 5:
        return None
    avg_vol = sum(vols[:-1]) / max(len(vols) - 1, 1)
    return {
        "ret_1m_pct": round((closes[-1] / closes[0] - 1) * 100, 1),
        "vol_ratio": round(vols[-1] / avg_vol, 1) if avg_vol else None,
    }
