"""
Cross-sectional factor engine.

Ranks the S&P 500 on the factors with the deepest peer-reviewed
support, combines them into a composite score, and overlays the
congressional cluster signal from watcher/main.py.

Factors (each computed as a cross-sectional z-score):
  momentum   12-month return skipping the most recent month
             (Jegadeesh & Titman 1993; the skip avoids short-term
             reversal contamination)
  value      earnings yield (trailing E/P) and book-to-market,
             averaged (Fama & French 1992)
  quality    return on equity and profit margin, averaged
             (Novy-Marx 2013 profitability premium)
  low_vol    negative of 12-month daily return volatility
             (Ang et al. 2006 low-volatility anomaly)
  size       negative of log market cap (small tilt; weakest of
             the five post-publication, weighted accordingly)

Composite = weighted sum of z-scores. Weights reflect how well
each factor has held up out of sample since publication.

Data: yfinance (free). Prices are solid. Fundamentals are
CURRENT-quarter snapshots only, which is fine for today's screen
but means the value/quality factors cannot be honestly backtested
far into the past with free data. backtest.py therefore tests the
price-based factors (momentum, low_vol) over deep history and the
full composite only over the recent window.

Output: ranked CSV + top/bottom decile, with a column flagging
tickers that also have a live congressional cluster.
"""

import csv
import io
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf

OUT_DIR = Path(__file__).parent
UNIVERSE_URL = (
    "https://raw.githubusercontent.com/datasets/"
    "s-and-p-500-companies/main/data/constituents.csv"
)

FACTOR_WEIGHTS = {
    "momentum": 0.30,
    "value": 0.25,
    "quality": 0.25,
    "low_vol": 0.15,
    "size": 0.05,
}


def get_universe():
    r = requests.get(UNIVERSE_URL, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    # Yahoo uses dashes for share classes (BRK-B), the CSV uses dots
    tickers = [t.replace(".", "-") for t in df["Symbol"].tolist()]
    sectors = dict(zip(tickers, df["GICS Sector"]))
    return tickers, sectors


def fetch_prices(tickers, period="14mo"):
    """Batch-download daily closes. yfinance handles chunking."""
    data = yf.download(
        tickers, period=period, interval="1d",
        auto_adjust=True, progress=False, threads=True,
    )["Close"]
    if isinstance(data, pd.Series):
        data = data.to_frame()
    return data.dropna(axis=1, thresh=int(len(data) * 0.9))


def fetch_fundamentals(tickers, pause=0.05):
    """Current-snapshot fundamentals. Slow but free; cached daily."""
    cache = OUT_DIR / "fundamentals_cache.json"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if cache.exists():
        blob = json.loads(cache.read_text())
        if blob.get("date") == today:
            return blob["data"]
    out = {}
    for i, tk in enumerate(tickers):
        try:
            info = yf.Ticker(tk).info
            out[tk] = {
                "trailing_pe": info.get("trailingPE"),
                "price_to_book": info.get("priceToBook"),
                "roe": info.get("returnOnEquity"),
                "profit_margin": info.get("profitMargins"),
                "market_cap": info.get("marketCap"),
            }
        except Exception:
            out[tk] = {}
        if i % 50 == 0:
            print(f"  fundamentals {i}/{len(tickers)}", file=sys.stderr)
        time.sleep(pause)
    cache.write_text(json.dumps({"date": today, "data": out}))
    return out


def zscore(series):
    s = pd.Series(series, dtype=float)
    clean = s.replace([np.inf, -np.inf], np.nan)
    # Winsorize at 3 sigma to stop one weird ticker dominating
    mu, sd = clean.mean(), clean.std()
    if not sd or math.isnan(sd):
        return pd.Series(0.0, index=s.index)
    clipped = clean.clip(mu - 3 * sd, mu + 3 * sd)
    return ((clipped - clipped.mean()) / clipped.std()).fillna(0.0)


def compute_factors(prices, fundamentals):
    tickers = [t for t in prices.columns]
    idx = pd.Index(tickers)

    # --- momentum: 12m return skipping last ~21 trading days
    if len(prices) < 260:
        raise SystemExit("Not enough price history for 12-1 momentum")
    p_now = prices.iloc[-22]          # one month ago
    p_then = prices.iloc[-252]        # ~12 months ago
    momentum = (p_now / p_then - 1).reindex(idx)

    # --- low volatility: trailing 12m daily vol, sign-flipped
    vol = prices.pct_change().iloc[-252:].std().reindex(idx)
    low_vol = -vol

    # --- value / quality / size from fundamentals
    ep, bm, roe, margin, logcap = {}, {}, {}, {}, {}
    for tk in tickers:
        f = fundamentals.get(tk, {}) or {}
        pe = f.get("trailing_pe")
        pb = f.get("price_to_book")
        ep[tk] = (1.0 / pe) if pe and pe > 0 else np.nan
        bm[tk] = (1.0 / pb) if pb and pb > 0 else np.nan
        roe[tk] = f.get("roe") if f.get("roe") is not None else np.nan
        margin[tk] = (
            f.get("profit_margin")
            if f.get("profit_margin") is not None else np.nan
        )
        mc = f.get("market_cap")
        logcap[tk] = math.log(mc) if mc else np.nan

    z = pd.DataFrame(index=idx)
    z["momentum"] = zscore(momentum)
    z["low_vol"] = zscore(low_vol)
    z["value"] = (zscore(ep) + zscore(bm)) / 2
    z["quality"] = (zscore(roe) + zscore(margin)) / 2
    z["size"] = zscore(pd.Series(logcap)) * -1  # small = positive

    z["composite"] = sum(z[f] * w for f, w in FACTOR_WEIGHTS.items())
    return z


def congressional_overlay():
    """Pull current clusters from the watcher module if available."""
    try:
        sys.path.insert(0, str(OUT_DIR.parent / "watcher"))
        from main import fetch_congress_trades, find_clusters
        clusters = find_clusters(fetch_congress_trades())
        return {c["ticker"]: len(c["buyers"]) for c in clusters}
    except Exception as e:
        print(f"[warn] congressional overlay skipped: {e}", file=sys.stderr)
        return {}


def main():
    print("Universe...")
    tickers, sectors = get_universe()
    print(f"{len(tickers)} tickers")

    print("Prices (batch)...")
    prices = fetch_prices(tickers)
    print(f"{prices.shape[1]} tickers with clean price history")

    print("Fundamentals (slow first run, cached daily)...")
    fundamentals = fetch_fundamentals(list(prices.columns))

    print("Factors...")
    z = compute_factors(prices, fundamentals)

    overlay = congressional_overlay()
    z["congress_buyers"] = [overlay.get(t, 0) for t in z.index]
    z["sector"] = [sectors.get(t, "") for t in z.index]

    ranked = z.sort_values("composite", ascending=False).round(3)
    out = OUT_DIR / "ranked.csv"
    ranked.to_csv(out, index_label="ticker")

    decile = max(len(ranked) // 10, 10)
    print("\nTop decile (composite):")
    cols = ["composite", "momentum", "value", "quality", "congress_buyers"]
    print(ranked.head(decile)[cols].to_string())
    print(f"\nFull ranking written to {out}")
    print(
        "\nNote: this is a ranking of factor exposure, not a promise. "
        "The factors have long-run peer-reviewed support with multi-year "
        "stretches of underperformance. Test via backtest.py before "
        "believing anything."
    )


if __name__ == "__main__":
    main()
