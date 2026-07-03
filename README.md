# Market Watcher

A free-tier signal aggregator. It watches congressional stock
disclosures, cross-references news and price action, alerts your
phone when signals cluster, and tests the resulting strategy with
paper money so you get an honest verdict before a real dollar moves.

What it is: an information tool with a built-in honesty layer.
What it is not: a prediction engine or a path to 1,000x. Disclosures
lag the actual trades by up to 45 days and the big funds saw all of
this before you did. The paper account exists to measure whether
there is any edge left anyway.

## Total cost: $0

| Piece | Service | Cost |
|---|---|---|
| Scheduler | GitHub Actions cron | Free tier |
| Disclosure data | Senate/House Stock Watcher mirrors | Free |
| News | Public RSS feeds | Free |
| Price data | yfinance (15-min delayed) | Free |
| Alerts | Telegram bot | Free |
| Paper trading | Alpaca paper API | Free |

## Setup (about 30 minutes)

### 1. Repo
Create a new **private** GitHub repository and push these files to it.

### 2. Telegram bot (5 min)
1. In Telegram, message **@BotFather**, send `/newbot`, follow prompts.
2. Copy the bot token it gives you.
3. Message your new bot anything, then visit
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   and copy your `chat.id` from the response.

### 3. Alpaca paper account (10 min)
1. Sign up free at alpaca.markets.
2. Dashboard -> Paper Trading -> generate API keys.
3. You start with $100,000 in fake money. Ignore the number; only
   the percentage return vs SPY matters.

### 4. GitHub secrets
Repo -> Settings -> Secrets and variables -> Actions -> add:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `ALPACA_KEY_ID`
- `ALPACA_SECRET_KEY`

### 5. Turn it on
Actions tab -> enable workflows -> run "Market Watcher" manually once
to verify. After that it runs itself every 2 hours on weekdays.

## How the signal works

A **cluster** = two or more distinct members of Congress purchasing
the same ticker within 21 days, above a $15k midpoint estimate.
When a new cluster appears you get one Telegram message with the
buyers, total size, 1-month price context, and any matching headlines.

To paper-trade a signal you like:
```
python watcher/paper_trade.py enter TICKER
```
It buys 5% of paper equity, holds 30 days, exits automatically on the
next scheduled run past the hold window. Every trade logs to
`trades_log.csv`.

To check the verdict:
```
python watcher/paper_trade.py report
```
Compare the strategy return against SPY over the same window. Run it
for at least 3 months before believing anything. If it does not beat
SPY, that is a successful experiment: it cost you nothing and saved
you real money.

## Tuning

Edit the constants at the top of `watcher/main.py`:
- `CLUSTER_THRESHOLD` — politicians required to form a cluster
- `LOOKBACK_DAYS` — disclosure window
- `MIN_TRADE_SIZE` — noise floor
- `RSS_FEEDS` — add sector-specific feeds

And in `paper_trade.py`:
- `POSITION_FRACTION`, `HOLD_DAYS`, `MAX_OPEN_POSITIONS`

## If the disclosure feeds return 403

The S3 mirrors occasionally block cloud IPs. Two fallbacks, both free:
1. The same data lives in the `timothycarambat/senate-stock-watcher-data`
   GitHub repo as daily JSON files under `data/` — swap the URL in
   `main.py` to the raw.githubusercontent.com path.
2. Official sources directly: House Clerk disclosures
   (disclosures-clerk.house.gov) and Senate eFD (efdsearch.senate.gov)
   are scrapeable but need session handling; ask me and I will write
   that scraper if the mirrors die.

## Honest limitations

- Disclosure lag is structural. STOCK Act allows 45 days; members
  file late routinely. You are always trading old information.
- The community data mirrors update daily, not in real time.
- Keyword news matching is crude. It surfaces, it does not understand.
- yfinance is unofficial and occasionally breaks; the script degrades
  gracefully (price context is optional).
- If the paper account beats SPY for a quarter, that is interesting,
  not proof. Three months is one regime. Keep testing.

## Cross-sectional factor engine (factors/)

`python factors/screen.py` ranks the full S&P 500 on five factors
with peer-reviewed support (momentum, value, quality, low-vol, size),
combines them into a weighted composite, and flags any ticker that
also has a congressional buy cluster. Output: `factors/ranked.csv`
plus the top decile printed. First run takes ~15 min (fundamentals
fetch); cached daily after that.

`python factors/backtest.py` tests the momentum decile over 10 years
against SPY, then against 500 random portfolios built the same way.
The random-portfolio null test is the honesty check: beating SPY in
one window is easy to fluke, beating 95% of random portfolios is
harder. `python factors/backtest.py lowvol` tests low-volatility.

Free-data limits, stated plainly: value and quality use current
fundamentals only (no free historical fundamentals exist), and the
universe is today's S&P 500, which carries survivorship bias. Both
inflate results. Backtest output is an upper bound on the truth.

## Free API upgrades (watcher/providers.py)

Set one more free key and the fragile layers get replaced:

- `FINNHUB_KEY` (free at finnhub.io, 60 calls/min): per-ticker
  company news replaces the RSS keyword matching, and real-time
  quotes replace delayed data. Add it as a GitHub Actions secret
  alongside the others.
- Your existing Alpaca paper keys now also serve as a price-data
  backup: if yfinance breaks (it does, a few times a year), the
  watcher automatically pulls daily bars from Alpaca's free IEX
  feed instead.

Everything degrades gracefully: no keys means the original RSS +
yfinance behavior, wrong keys means a skipped layer, never a crash.
Free-tier note: Finnhub's quote and company-news endpoints are free;
its historical candles and pre-scored sentiment are paid, so this
module deliberately avoids them.

## Live tracker (docs/)

A GitHub Pages dashboard charts your paper strategy against SPY,
both normalized to 100 at the start, updated every scheduled run.

Enable it once: repo Settings -> Pages -> Source: "Deploy from a
branch" -> branch `main`, folder `/docs`. Your tracker will live at
`https://<username>.github.io/<repo>/`.

The verdict stamp at the top is deliberately stubborn: below 30
trades and 90 days it labels any lead or deficit as statistically
indistinguishable from luck, because it is. The page updates every
2 hours with the workflow, so "real time" means "at most 2 hours
stale," which is the honest ceiling for a $0 stack.

Note: if the repo is private, GitHub Pages requires a paid plan.
Free workaround: make the repo public (the only sensitive things
are in Secrets, which are never exposed) or view docs/index.html
locally.

## iPhone widget (widget/)

`widget/edtrade-widget.js` is a Scriptable widget. Install the free
Scriptable app, paste the script in, set BASE to your GitHub Pages
URL, and add a small or medium Scriptable widget to your home screen.

Small: the spread vs SPY plus strategy/SPY returns. Medium: adds the
next pending action (sell first, then buy, then hold). Tapping opens
the full dashboard. iOS controls widget refresh timing (roughly every
15-60 minutes), which comfortably outpaces the 2-hour data cycle.

The widget requires the repo's GitHub Pages site to be public, since
Scriptable fetches the JSON without authentication.
