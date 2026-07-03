"""
Backtest + null test for the price-based factors.

What this honestly can and cannot test with free data:

  CAN:   momentum and low-vol portfolios over ~10 years of daily
         prices for the current S&P 500 universe.
  CANNOT: value/quality historically (no free historical
         fundamentals), and the universe has survivorship bias
         (today's S&P 500 excludes the companies that died, which
         inflates every strategy including the benchmark).

Both limits inflate results. Treat output as an upper bound.

The null test is the part that keeps you honest: it reruns the
same portfolio construction on randomly selected stocks 500 times.
Your strategy has evidence of edge only if it beats most of the
random portfolios, not just SPY.

Usage:
  python factors/backtest.py            # momentum decile backtest
  python factors/backtest.py lowvol     # low-vol decile backtest
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent))
from screen import get_universe, fetch_prices

REBALANCE = "ME"       # month-end
YEARS = "10y"
N_NULL = 500
SEED = 42


def monthly_prices(period=YEARS):
    tickers, _ = get_universe()
    daily = fetch_prices(tickers, period=period)
    return daily.resample(REBALANCE).last()


def momentum_signal(monthly):
    # 12-1: return from t-12 to t-1
    return monthly.shift(1) / monthly.shift(12) - 1


def lowvol_signal(monthly):
    rets = monthly.pct_change()
    return -rets.rolling(12).std()


def decile_backtest(monthly, signal):
    """Each month: long the top decile by signal, equal weight,
    hold one month. Returns the strategy's monthly return series."""
    rets = monthly.pct_change()
    strat = []
    dates = []
    for i in range(13, len(monthly) - 1):
        sig = signal.iloc[i].dropna()
        if len(sig) < 50:
            continue
        top = sig.nlargest(max(len(sig) // 10, 10)).index
        nxt = rets.iloc[i + 1][top].dropna()
        if len(nxt):
            strat.append(nxt.mean())
            dates.append(rets.index[i + 1])
    return pd.Series(strat, index=dates)


def random_backtest(monthly, n_hold, rng):
    """Same construction, random picks. One null draw."""
    rets = monthly.pct_change()
    strat = []
    for i in range(13, len(monthly) - 1):
        avail = rets.iloc[i + 1].dropna().index
        if len(avail) < n_hold:
            continue
        pick = rng.choice(avail, size=n_hold, replace=False)
        strat.append(rets.iloc[i + 1][pick].mean())
    return np.array(strat)


def stats(series, label):
    ann_ret = (1 + series).prod() ** (12 / len(series)) - 1
    ann_vol = series.std() * np.sqrt(12)
    sharpe = ann_ret / ann_vol if ann_vol else 0
    cum = (1 + series).cumprod()
    dd = (cum / cum.cummax() - 1).min()
    print(
        f"{label:18s} ann return {ann_ret*100:6.1f}%  "
        f"vol {ann_vol*100:5.1f}%  sharpe {sharpe:5.2f}  "
        f"max drawdown {dd*100:6.1f}%"
    )
    return ann_ret


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "momentum"
    print(f"Backtesting {which} decile, {YEARS}, monthly rebalance.")
    print("Downloading prices (few minutes)...")
    monthly = monthly_prices()
    print(f"{monthly.shape[1]} tickers, {len(monthly)} months")

    signal = momentum_signal(monthly) if which == "momentum" \
        else lowvol_signal(monthly)

    strat = decile_backtest(monthly, signal)

    spy = yf.download("SPY", period=YEARS, auto_adjust=True,
                      progress=False)["Close"].resample(REBALANCE).last()
    spy_rets = spy.pct_change().dropna()
    spy_rets = spy_rets.loc[strat.index.min():strat.index.max()]
    if isinstance(spy_rets, pd.DataFrame):
        spy_rets = spy_rets.iloc[:, 0]

    print()
    strat_ann = stats(strat, f"{which} decile")
    stats(spy_rets, "SPY")

    print(f"\nNull test: {N_NULL} random portfolios, same construction...")
    rng = np.random.default_rng(SEED)
    n_hold = max(monthly.shape[1] // 10, 10)
    null_anns = []
    for k in range(N_NULL):
        r = random_backtest(monthly, n_hold, rng)
        ann = (1 + r).prod() ** (12 / len(r)) - 1
        null_anns.append(ann)
    null_anns = np.array(null_anns)
    pct = (null_anns < strat_ann).mean() * 100
    print(
        f"Strategy beats {pct:.0f}% of random portfolios "
        f"(null mean {null_anns.mean()*100:.1f}%, "
        f"null 95th pct {np.percentile(null_anns, 95)*100:.1f}%)"
    )
    if pct >= 95:
        verdict = "Evidence of real factor edge in this window."
    elif pct >= 75:
        verdict = "Weak evidence. Could easily be luck."
    else:
        verdict = "No evidence of edge over random selection."
    print(f"Verdict: {verdict}")
    print(
        "\nCaveats that inflate ALL numbers above: survivorship bias "
        "(current constituents only), no trading costs, no slippage, "
        "one historical window. Treat as upper bound."
    )


if __name__ == "__main__":
    main()
