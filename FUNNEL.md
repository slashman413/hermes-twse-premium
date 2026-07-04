# TWSE Premium — Funnel & Free-vs-Paid Line

## Product overview

| Tier | Price | What you get |
|------|-------|--------------|
| Free | $0 | Full 2004–2026 historical backtests, strategy methodology, GitHub Pages dashboard |
| Premium | $49/mo · $99/qtr · $299/yr | Daily actionable scan, weekly results digest, email alerts |

Ko-fi checkout: https://ko-fi.com/s/b99720d13d

---

## What stays FREE forever

The free tier is the top-of-funnel trust builder. It must remain substantive enough to prove the strategy works.

- **Full historical backtest dashboard** (2004–2026, every trade, every year)
- **Strategy methodology** — the complete 9-step "大飆股 DNA" rules (MACD 4-arrow, ADX > 20, W%R < -20, 20-day breakout, RVOL >= 1.2, monthly RSI4, etc.)
- **Annual summary statistics** — win rate, average return, best/worst years
- **Individual trade log** — every historical entry/exit with P&L
- **Equity curve charts** — year-by-year bar chart and per-trade visualization
- **Missed-signal log** — historical stocks that qualified but were skipped (capital limit)
- **Market regime indicator** (0050-based BULL/ALERT/BEAR/CRASH) — explained in methodology
- **Education posts** — how to read signals, how backtesting differs from live trading, risk management basics
- **Weekly trust posts** — last week's signals + how they performed (published publicly, one-week lag)

Rationale: giving away the history and methodology is the proof. Anyone can backtest the rules themselves — the value of Premium is not the formula, it is receiving the *computed result* every day without doing the work.

---

## What is gated behind Premium

Gate anything that saves the subscriber time *today*. The daily scan requires running code, fetching fresh data, and interpreting the output — that is the work Premium removes.

- **Today's entry signals** — the full table of stocks that triggered all 9 conditions as of last close (ticker, score, breakout %, RVOL, ATR ratio, suggested entry zone, suggested stop-loss)
- **Daily market regime reading** — whether the system is in buy/hold/stand-aside mode today
- **Email/push alert** — delivered before market open on signal days (no need to visit the dashboard)
- **Signal chart snapshots** — interactive K-line + MACD + ADX + W%R for each flagged stock, current day
- **Portfolio position tracker** — which open positions the system currently holds and at what cost basis
- **Priority access** — new strategy variants and experimental signals tested before public release

---

## Weekly trust post cadence (public, one-week lag)

Every Monday, publish a short post (social + GitHub Discussions or a static page) covering:

1. What the strategy flagged the prior week (tickers only, no entry price — that is Premium)
2. How those flags performed by end of week (% gain/loss from signal date close)
3. The week's hit rate (winning signals / total signals)
4. Current market regime reading

Purpose: these posts are the primary trust-building and SEO content. A visitor who sees three consecutive weeks of honest results — including losses — is far more likely to convert than one who reads only marketing copy.

Template: see `trust-post-week-1.md` and `trust-post-week-2.md` in this repo.

---

## Conversion path

```
Free dashboard visitor
  |
  ├─ Sees 20-year backtest → "this strategy seems to work"
  |
  ├─ Clicks "今日訊號" tab → hits paywall gate
  |
  ├─ Reads weekly trust post → sees honest last-week results
  |
  └─ Clicks Ko-fi CTA → $49/mo checkout
```

Target: 204 monthly subscribers = $10,000/month at $49/mo.
Realistic near-term: 20 subscribers ($980/mo) within 90 days of launch with consistent weekly posts and basic SEO.

---

## CAC budget

- Primary channel: organic (GitHub Pages SEO + PTT/Dcard stock forum posts linking to free dashboard)
- Secondary: weekly trust posts shared to LINE groups and stock Discord servers
- Tertiary: Ko-fi page discovery (existing followers)
- Paid ads: defer until $1k MRR — no budget to burn before product-market fit is confirmed

---

## What NOT to do

- Do not gate the historical data. That is the proof; removing it removes conversions.
- Do not publish today's signals publicly even with a delay — that destroys the Premium value prop.
- Do not make the weekly trust post a sales pitch. One paragraph of honest numbers, then one line with the subscription link. That is all.
