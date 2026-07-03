# ED TRADE — The Very Simple Setup Guide

Every step is one action. After most steps I tell you what you
should see, so you know it worked. If what you see doesn't match,
stop there and ask me.

You need: a Mac, an iPhone, and about an hour. Everything is free.

---

## STAGE 1: Put the code on GitHub (15 min)

GitHub is a free website that stores code and, importantly for us,
runs it on a schedule for free.

1. Go to **github.com** in your browser.
2. Click **Sign up** and make a free account. (If you have one,
   sign in.)
3. Once signed in, look at the very top right corner. Click the
   **+** symbol.
4. Click **New repository**.
5. In the "Repository name" box, type: **ed-trade**
6. Make sure **Public** is selected (it's a row of circles; Public
   should have the dot). Don't worry, your passwords and keys are
   never in the code.
7. Don't check any other boxes. Click the green **Create
   repository** button at the bottom.

You should see: a mostly empty page with setup instructions on it.
Leave this browser tab open.

Now we put the files there using Terminal. Terminal is an app
already on your Mac where you type commands.

8. Find the **market-watcher.zip** file I gave you (probably in
   Downloads). Double-click it. This creates a folder called
   **market-watcher**.
9. Open the **Terminal** app (press Cmd+Space, type "terminal",
   press Enter).
10. In Terminal, type this and press Enter (if the folder isn't in
    Downloads, drag the market-watcher folder onto the Terminal
    window instead of typing the path, after typing "cd "):

    ```
    cd ~/Downloads/market-watcher
    ```

    You should see: nothing happens except a new blank line. That
    means it worked.

11. Now copy this entire block, paste it into Terminal, and press
    Enter. **Change YOUR-USERNAME to your GitHub username first**
    (it's in the web address of your repository page):

    ```
    git init
    git add .
    git commit -m "first upload"
    git branch -M main
    git remote add origin https://github.com/YOUR-USERNAME/ed-trade.git
    git push -u origin main
    ```

12. Terminal will probably ask you to log in to GitHub. Follow what
    it says; it usually opens your browser and you click
    **Authorize**.

You should see: lines of text ending with something like
"branch 'main' set up to track 'origin/main'." Now refresh your
GitHub browser tab. **You should see folders named watcher,
factors, docs, and widget.** If you see those, Stage 1 is done.

---

## STAGE 2: Make a Telegram bot (5 min)

This is how the app sends alerts to your phone.

1. Open **Telegram** on your phone (free in the App Store if you
   don't have it).
2. In the search bar, type: **BotFather** (pick the one with the
   blue check mark).
3. Tap **Start**.
4. Type **/newbot** and send it.
5. It asks for a name. Type: **Ed Trade** and send.
6. It asks for a username. Type something like
   **EdTradeAlertsBot** (must end in "bot"; if taken, add numbers).
7. BotFather replies with a message containing a **token**: a long
   code like `7712345678:AAHxx...`. **Copy it and paste it
   somewhere safe, like Notes.** Label it TOKEN.
8. Now search Telegram for the bot you just made
   (**EdTradeAlertsBot**), open it, tap Start, and send it any
   message, like "hi". (This step matters. Don't skip it.)
9. On your Mac, in your browser, go to this address, replacing
   PASTE-TOKEN with your token:

   ```
   https://api.telegram.org/botPASTE-TOKEN/getUpdates
   ```

10. You'll see a wall of text. Find where it says
    **"chat":{"id":** followed by a number, like 6621234567.
    **Copy that number into Notes.** Label it CHAT ID.

You now have 2 saved values: TOKEN and CHAT ID.

---

## STAGE 3: Make an Alpaca account (10 min)

Alpaca gives you a pretend $100,000 to test the strategy with fake
money. This is the whole point of the experiment.

1. On your Mac, go to **alpaca.markets** and click **Sign Up**.
2. Create the free account (email, password, basic questions). You
   do NOT need to deposit money. If it offers a funded account,
   skip it; you only want **Paper Trading**.
3. Once you're in the dashboard, look at the top left. There's a
   dropdown. Switch it to **Paper Trading** if it isn't already.
4. On the paper trading page, look for **API Keys** on the right
   side. Click **Generate** (or "Generate New Keys").
5. Two codes appear: a **Key ID** and a **Secret Key**. **Copy
   both into Notes.** Label them ALPACA KEY and ALPACA SECRET.
   The secret is shown only once, so do it now.

You now have 4 saved values.

---

## STAGE 4: Get a Finnhub key (2 min)

Finnhub provides free stock news and prices.

1. Go to **finnhub.io** and click **Get free API key**.
2. Sign up. Your key appears right on the dashboard after signup.
3. **Copy it into Notes.** Label it FINNHUB.

You now have 5 saved values. That's all of them.

---

## STAGE 5: Give the keys to GitHub (5 min)

GitHub stores these secretly so the app can use them. Nobody can
see them, not even you, after saving.

1. Go to your repository page:
   github.com/YOUR-USERNAME/ed-trade
2. Click **Settings** (in the row of tabs near the top of the
   repository, NOT your account settings).
3. In the left sidebar, click **Secrets and variables**, then
   click **Actions**.
4. Click the green **New repository secret** button.
5. In the Name box type exactly: **TELEGRAM_BOT_TOKEN**
   In the Secret box, paste your TOKEN from Notes.
   Click **Add secret**.
6. Repeat four more times, names typed EXACTLY like this
   (capital letters and underscores matter):

   - Name: **TELEGRAM_CHAT_ID** — paste your CHAT ID
   - Name: **ALPACA_KEY_ID** — paste your ALPACA KEY
   - Name: **ALPACA_SECRET_KEY** — paste your ALPACA SECRET
   - Name: **FINNHUB_KEY** — paste your FINNHUB key

You should see: a list of 5 secrets.

---

## STAGE 6: Turn it on (5 min)

1. On your repository page, click the **Actions** tab (top row).
2. If there's a button that says **"I understand my workflows, go
   ahead and enable them"**, click it.
3. In the left sidebar, click **Market Watcher**.
4. On the right side, click the **Run workflow** dropdown button,
   then the green **Run workflow** button inside it.
5. Refresh the page after a few seconds. You'll see a run appear
   with a yellow spinning circle. Wait about 2 minutes and refresh
   again.

You should see: a **green check mark**. That means the whole
machine ran, start to finish. Check Telegram: if any signals exist
right now, your bot messaged you. No message just means no signals
today, which is normal.

If you see a red X instead: click it, click the step that failed,
screenshot what it says, and bring it to me.

From now on it runs by itself every 2 hours on weekdays. You never
have to press this button again.

---

## STAGE 7: Turn on the website (5 min)

1. Repository page -> **Settings** -> in the left sidebar, click
   **Pages**.
2. Under "Build and deployment," set Source to **Deploy from a
   branch**.
3. Under Branch: pick **main**, and in the folder dropdown next to
   it pick **/docs**. Click **Save**.
4. Wait 2 minutes, refresh the page. A box appears at the top with
   your website address:
   **https://YOUR-USERNAME.github.io/ed-trade/**
5. Open that address.

You should see: the dark blue ED TRADE page saying "Awaiting
data." That's correct — it fills in after the next automatic run.
Check back tomorrow and there will be a chart.

Save this address. It's your dashboard from any device, anywhere.

---

## STAGE 8: The iPhone widget (10 min)

1. On your iPhone, App Store -> search **Scriptable** -> install
   (free, orange icon).
2. On your Mac, open the file **edtrade-widget.js** I gave you
   (it's also in the market-watcher folder, inside **widget**).
   Open it with TextEdit. Select all, copy.
3. Send the text to your phone however you like (email it to
   yourself, or AirDrop the file and open in Notes).
4. Open Scriptable on the phone. Tap the **+** in the top right.
5. Paste everything.
6. Near the top of the pasted text, find the line that starts with
   **const BASE =** and replace the address in quotes with YOUR
   website address from Stage 7. No slash at the end.
7. Tap the name at the top ("Untitled Script") and rename it
   **ED TRADE**. Tap Done (top left).
8. Go to your home screen. Press and hold on an empty spot until
   the icons jiggle.
9. Tap **Edit** top left, tap **Add widget**, search **Scriptable**, pick the
   medium size, tap **Add Widget**.
10. The new widget says "Select script in widget configurator."
    Press and hold the widget, tap **Edit Widget**, tap
    **Script**, choose **ED TRADE**. Tap outside to finish.

You should see: the dark blue ED TRADE widget. It says "Awaiting
data" until the site has data, then it shows the score.

---

## DONE. What happens now

- Every 2 hours on weekdays, the machine checks for congressional
  stock clusters, alerts your Telegram, manages the fake-money
  account, and updates the website and widget.
- When an alert interests you and you want to test it with fake
  money, ask me and I'll walk you through that one command.
- The website's big number will glow green or red, but read the
  small gray sentence under it. Until it says the sample means
  something, it doesn't, no matter how green the number is.
- Nothing here touches real money. That's a feature, and it stays
  that way until three months of fake trading earns otherwise.
