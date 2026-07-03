// ED TRADE — iOS home screen widget for Scriptable
//
// Setup:
//  1. Install "Scriptable" (free) from the App Store.
//  2. New script, paste this file, set BASE below to your
//     GitHub Pages URL (no trailing slash).
//  3. Long-press home screen -> add Scriptable widget (small or
//     medium) -> choose this script.
//
// iOS refreshes widgets on its own schedule, typically every
// 15-60 minutes. Your data updates every 2 hours anyway, so the
// widget is effectively always current.

const BASE = "https://YOUR-USERNAME.github.io/YOUR-REPO";

const OCEAN_TOP = new Color("#061c30");
const OCEAN_BOTTOM = new Color("#0d3a5c");
const FOAM = new Color("#5ac8fa");
const SUB = new Color("#8fb0c9");
const UP = new Color("#30d158");
const DOWN = new Color("#ff453a");
const INK = new Color("#f2f7fb");

async function getJSON(path) {
  try {
    const req = new Request(`${BASE}/${path}?t=${Date.now()}`);
    return await req.loadJSON();
  } catch (e) {
    return null;
  }
}

const perf = (await getJSON("performance.json")) || [];
const actions = await getJSON("actions.json");

const w = new ListWidget();
const grad = new LinearGradient();
grad.colors = [OCEAN_TOP, OCEAN_BOTTOM];
grad.locations = [0, 1];
w.backgroundGradient = grad;
w.setPadding(14, 14, 12, 14);

// Header
const head = w.addText("ED TRADE");
head.font = Font.boldSystemFont(11);
head.textColor = FOAM;
w.addSpacer(6);

if (perf.length < 2) {
  const t = w.addText("Awaiting data");
  t.font = Font.systemFont(14);
  t.textColor = SUB;
} else {
  const e0 = perf[0].equity, s0 = perf[0].spy;
  const last = perf[perf.length - 1];
  const strat = (100 * last.equity / e0) - 100;
  const spy = (100 * last.spy / s0) - 100;
  const spread = strat - spy;
  const leading = spread >= 0;

  // Hero spread
  const hero = w.addText(
    (leading ? "+" : "\u2212") + Math.abs(spread).toFixed(1) + " pts"
  );
  hero.font = Font.boldSystemFont(30);
  hero.textColor = leading ? UP : DOWN;
  hero.minimumScaleFactor = 0.6;
  hero.lineLimit = 1;

  const sub = w.addText("vs SPY \u00b7 paper account");
  sub.font = Font.systemFont(10);
  sub.textColor = SUB;
  w.addSpacer(8);

  // Strategy / SPY line
  const row = w.addStack();
  row.layoutHorizontally();
  const fmt = v => (v >= 0 ? "+" : "\u2212") + Math.abs(v).toFixed(1) + "%";
  const cell = (label, val, good) => {
    const s = row.addStack();
    s.layoutVertically();
    const v = s.addText(fmt(val));
    v.font = Font.semiboldSystemFont(13);
    v.textColor = good ? UP : DOWN;
    const l = s.addText(label);
    l.font = Font.systemFont(9);
    l.textColor = SUB;
  };
  cell("Strategy", strat, strat >= 0);
  row.addSpacer(14);
  cell("SPY", spy, spy >= 0);

  // Next action, if the widget is medium-sized
  if (config.widgetFamily === "medium" && actions) {
    const next =
      (actions.sell && actions.sell[0] && { tag: "SELL", c: DOWN, a: actions.sell[0] }) ||
      (actions.buy && actions.buy[0] && { tag: "BUY", c: UP, a: actions.buy[0] }) ||
      (actions.hold && actions.hold[0] && { tag: "HOLD", c: SUB, a: actions.hold[0] });
    if (next) {
      w.addSpacer(8);
      const ar = w.addStack();
      ar.layoutHorizontally();
      ar.centerAlignContent();
      const tag = ar.addText(next.tag + " ");
      tag.font = Font.boldSystemFont(11);
      tag.textColor = next.c;
      const tk = ar.addText(next.a.ticker + "  ");
      tk.font = Font.semiboldSystemFont(11);
      tk.textColor = INK;
      const why = ar.addText(next.a.why || "");
      why.font = Font.systemFont(10);
      why.textColor = SUB;
      why.lineLimit = 1;
    }
  }
}

w.addSpacer();
const foot = w.addText("hypothesis under test \u00b7 not advice");
foot.font = Font.systemFont(8);
foot.textColor = SUB;

w.url = BASE; // tapping the widget opens the full dashboard
if (config.runsInWidget) {
  Script.setWidget(w);
} else {
  await w.presentMedium();
}
Script.complete();
