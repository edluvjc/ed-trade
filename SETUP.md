# ED TRADE — Setup Guide

From zip file to a running system with a live dashboard and phone
widget. Total time: about an hour, most of it account signups.
Total cost: $0.

Do the steps in order. Each part ends with a checkpoint so you know
it worked before moving on.

---

## Part 1: The repository (10 min)

1. Sign in at github.com (create a free account if needed).
2. Top right: **+** -> **New repository**.
   - Name: `ed-trade` (or anything)
   - Visibility: **Public** (required for the free dashboard and
     widget; your API keys are NOT in the code, they go in Secrets
     later, which stay private)
   - Do not initialize with a README.
3. Unzip `market-watcher.zip` on your Mac.
4. In Terminal:
   ```
   cd path/to/market-watcher
   git init
   git add .
   git commit -m "ED TRADE initial"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/ed-trade.git
   git push -u origin main
   ```
   (If git asks you to authenticate, GitHub will walk you through a
   browser login the first time.)

**Checkpoint:** refresh the repo page on github.com; you should see
the folders `watcher`, `factors`, `docs`, `widget`, and
`.github/workflows`.

---

## Part 2: Telegram alerts (5 min)

1. In Telegram, search **@BotFather**, send `/newbot`, follow the
   prompts, name it whatever you like (EdTradeBot).
2. BotFather replies with a **token** (long string with a colon).
   Copy it.
3. Open a chat with your new bot and send it any message.
4. In a browser, visit:
   `https://api.telegram.org/bot<PASTE-TOKEN-HERE>/getUpdates`
5. In the response, find `"chat":{"id":123456789` — that number is
   your **chat ID**. Copy it.

**Checkpoint:** you have two values saved somewhere: bot token and
chat ID.

---

## Part 3: Alpaca paper account (10 min)

1. Sign up free at **alpaca.markets** (choose the individual
   account; you do NOT need to fund anything).
2. In the dashboard, switch to **Paper Trading** (toggle at top
   left).
3. Find **API Keys** on the paper overview page -> **Generate**.
4. Copy both the **Key ID** and the **Secret Key** (the secret is
   shown only once).

**Checkpoint:** paper account shows $100,000 fake money, and you
have two Alpaca values saved.

---

## Part 4: Finnhub key (2 min)

1. Sign up free at **finnhub.io**.
2. Your API key is on the dashboard immediately after signup.
   Copy it.

**Checkpoint:** you now have five values total: Telegram token,
Telegram chat ID, Alpaca key, Alpaca secret, Finnhub key.

---

## Part 5: Wire the secrets (5 min)

1. On your repo page: **Settings** -> **Secrets and variables** ->
   **Actions** -> **New repository secret**.
2. Add these five, names exactly as written:

   | Name | Value |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | from Part 2 |
   | `TELEGRAM_CHAT_ID` | from Part 2 |
   | `ALPACA_KEY_ID` | from Part 3 |
   | `ALPACA_SECRET_KEY` | from Part 3 |
   | `FINNHUB_KEY` | from Part 4 |

**Checkpoint:** five secrets listed. Values are hidden; that is the
point.

---

## Part 6: First run (5 min)

1. Repo -> **Actions** tab. If prompted, click
   **"I understand my workflows, enable them."**
2. Left sidebar: **Market Watcher** -> **Run workflow** ->
   green **Run workflow** button.
3. Wait ~2 minutes; the run appears with a spinner, then a green
   check.
4. Click into the run and expand **Run watcher** to see what it
   found.

**Checkpoint:** green check on the run, and if any signal clusters
currently exist you got a Telegram message. No message just means
no clusters right now — that is normal.

If the run fails with a 403 on the disclosure feeds, see the
"If the disclosure feeds return 403" section in the README for the
free fallback.

---

## Part 7: The dashboard (5 min)

1. Repo -> **Settings** -> **Pages**.
2. Source: **Deploy from a branch**. Branch: `main`, folder:
   **/docs**. Save.
3. Wait 1-2 minutes; the page shows your URL:
   `https://YOUR-USERNAME.github.io/ed-trade/`
4. Open it. You should see the ocean dashboard saying
   **Awaiting data** — correct, because snapshots only exist after
   runs with Alpaca configured. After the next scheduled run (or
   run the workflow manually again), refresh and the first
   snapshot appears.

**Checkpoint:** ED TRADE loads at your github.io URL.

---

## Part 8: Your real holdings, optional (5 min)

1. In the repo, open `watcher/holdings.json.example`, copy its
   format.
2. Create `watcher/holdings.json` with your actual positions from
   your E*TRADE positions page:
   ```json
   [
     {"ticker": "AAPL", "shares": 10, "cost_basis": 150.00}
   ]
   ```
3. Commit and push (or edit directly on github.com with the pencil
   icon -> Commit).

Reminder: the repo is public, so position sizes in this file are
visible to anyone who finds the repo. If that bothers you, skip
this part or ask for the percentages-only version.

**Checkpoint:** after the next run, a "Your holdings" card appears
on the dashboard.

---

## Part 9: iPhone widget (10 min)

1. App Store -> install **Scriptable** (free).
2. Open Scriptable -> **+** -> paste the contents of
   `widget/edtrade-widget.js`.
3. Edit the `BASE` line to your Pages URL from Part 7 (no trailing
   slash).
4. Tap the play button once to preview; you should see the widget
   render.
5. Long-press your home screen -> **+** -> search **Scriptable** ->
   choose small or medium -> add -> long-press the new widget ->
   **Edit Widget** -> Script: select yours.

**Checkpoint:** ED TRADE on your home screen.

---

## Part 10: Paper-trade a signal (whenever one arrives)

When a Telegram alert interests you, enter it in the paper account.
Easiest path: repo -> **Actions** has no manual entry, so run it
locally once:

```
cd path/to/market-watcher
pip3 install -r requirements.txt
export ALPACA_KEY_ID=xxx ALPACA_SECRET_KEY=xxx
python3 watcher/paper_trade.py enter TICKER
git add watcher/open_positions.json watcher/trades_log.csv
git commit -m "paper enter TICKER" && git push
```

From then on the scheduled runs manage the position: it exits
automatically after 30 days, logs the trade, and the dashboard and
widget update.

---

## What happens on its own from here

Every 2 hours on weekdays: fetch disclosures -> detect clusters ->
Telegram alert for new ones -> manage paper positions -> price your
holdings -> snapshot performance -> update the dashboard and
widget's data.

## The one instruction that matters

Run it for at least three months and 30 paper trades before letting
any of it near real money. The dashboard will tell you when the
sample means something. If the strategy does not beat SPY by then,
the experiment succeeded: it cost nothing and it answered the
question.
