# Why scans keep saying "No setup" (investigation, 15 Nov 2026)

## Main cause
The 10 Nov plans were read by eye from Yahoo 5m charts. They used simpler setups that the original skill allows (breakout-retest, trend-pullback), levels chosen by eye, and a "5m candle closes back in the zone" trigger.

Since 11 Nov the scanner applies a coded version of the rules:
- The skill's **"example qualifying sequence (not mandatory)"** (sweep → displacement → structure shift → retracement → confirmation) became the **only** accepted pattern.
- Zones must be FVGs.
- The strong candle needs range ≥ 1.5×ATR and body ≥ 60% [PROPOSED].
- Targets are the nearest untaken swings.
- The stop sits beyond the sweep extreme.
- 2:1 net after costs (R3, original rule).
- The C2 trigger (decision 2, 11 Nov) replaced the in-zone trigger.

Breakout-retest and trend-pullback setups without a sweep are **not detected at all**.

## Evidence
**Saved scans** (22 crypto runs, 12–14 Nov, 252 sequences):

| Outcome | Sequences |
|---|---|
| Never completed (strong candle missing in 121) | 135 |
| Invalidated | 109 |
| Complete setups | 24 |
| Entries | 0 |

The 24 complete setups were killed by:
- 2:1 failures: 12
- Opposite breaks: 9
- Expiry: 9
- Confirmation past the max entry: 3
- TP1 reached first: 3
- No target: 3

**Paper replay** (`replay_scalp_week.py`, 12 Nov 00:00 → 15 Nov 07:45, 20 coins, 15-min steps, Yahoo proxy):

| Variant | Complete setups | Entries | Result |
|---|---|---|---|
| Live rules | 44 | 1 (SUI short 14 Nov 07:15, between scans) | +0.31R |
| Strong candle optional | 114 | 2 | +3.07R |
| 10 Nov in-zone trigger | 44 | 0 | — |
| Both | 114 | 0 | — |

Sample far too small to validate anything. These are not rule changes.

## Data
**Exact contract:**
- fapi.binance.com answers HTTP 451.
- data.binance.vision, data-api.binance.vision and www.binance.com are blocked by this environment's network policy.
- TradingView's public chart page works for `BINANCE:XXXUSDT.P`: closed bars plus a streaming bid/ask, tested on LINKUSDT.P. It's unofficial (page scrape), about 20 s per symbol and timeframe, and restricted by TradingView's terms. Not wired into the scanner.

**Yahoo spot vs the exact LINKUSDT perpetual** (72 h, 299 bars, no gaps):
- Median price gap 0.05%, max 0.6%.
- Same detected BOS/CHoCH bar only about 50% of the time; sweeps about 80%.

**ARCHE LINK short** (14 Nov 02:44 UTC, zone 9.78–9.83): on LINKUSDT.P the zone was **never reached**; 9.542 was hit at 03:45 from about 9.61.

## Fixed (verified)
1. Perps whose CoinGecko price rounds to 0.00 (1000PEPE, PUMP) were silently dropped. They now use the index price, and 1000PEPEUSDT is back in the shortlist (×1000 spot vs index gap −0.68%).
2. Yahoo 1H lagging while 15m is current (13 coins skipped at 00:39 on 13 Nov): missing hours are rebuilt from 15m. Matches the real 1H exactly on LINK, BTC and SOL.
3. WAIT plans whose current 5m trigger level is already past the max entry or TP1 (AAPL, 13 Nov) are now flagged instead of shown as normal waits.

## Not changed (needs the user's approval, paper replay first)
- A continuation detector (breakout-retest / trend-pullback, as in the original skill).
- Relaxing the strong-candle threshold.
- Target selection beyond the nearest swing.
- Using TradingView data in the scanner.
