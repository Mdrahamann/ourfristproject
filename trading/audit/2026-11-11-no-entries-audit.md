# Audit: why every `scan now` on Wed 11 Nov 2026 showed no entry (written 18:05 UK)

**Mode:** read-only. Live scan rules were **not changed** during this audit. The replays are a separate paper exercise.

## Headline
1. **"Couldn't verify" applied to every scan.**
   - Binance's API returns HTTP 451 (geo-restricted) from here, so READY NOW was impossible all day.
   - Every level came from proxies: Yahoo spot candles (within 0.5% of the Binance index) or the underlying stock.
2. **"No qualifying setup" was the true paper result.**
   - A **time-ordered replay of 00:00–18:00** on the 21 shortlisted coins found **184 sweeps**.
   - Only **24** became complete Plan A/B sequences, and **0** reached a valid entry.
   - Even with **all five relaxations combined**, the replay finds **1** entry: DOGE short, −0.96R, at 14:35, which was inside the US-open window anyway.
3. **The scanner did miss things.** These cut coverage but produced no missed entries today:
   - **Price-rounding bug:** CoinGecko rounds prices under 0.005 to "0.00", and the scanner drops anything priced at zero. **72 contracts** were never screened, including **1000PEPEUSDT** ($479M volume; out of every scan from 14:37) and PUMPUSDT.
   - **Stale stock/crypto split:** MRVL, DJT, AXTI, INTW and SKUU are stock-linked perps but were treated as crypto. The stock scan uses a fixed list, so CRWV (OI $21.6M, passes L3) was never in scope, and leveraged ETFs (SOXL, SNXX) were left out entirely, even though the rule only removes them from buy-zone lists.
   - **No candles:** WLFI and ASTER passed liquidity but Yahoo has no data for them, so **20 were shortlisted and 18–19 analysed** in the afternoon scans.
   - **Old setups re-scored with today's information:** the live scanner re-checks old setups using targets as of the scan time, and ignores a zone that filled before confirmation. XMR's 01:00 long showed "Zone filled" at 03:25 but "MISSED (entry window passed)" at 14:37.
   - **Rules written but not implemented:** L1 quote volume ≥ $100M, C3 (confirm within 60 minutes), N1–N6 news blackouts, SL2 (stop not at equal highs/lows), E3 spread breach, L3 depth and volume checks.

## 1. Scan reconstruction (from saved logs: `scan.json`, `scan.md`, `stock_scan.json`, `scans.csv`)
| Scan (UK) | Code | CoinGecko age | USDT perps / crypto screened | Shortlisted | Analysed | 1H bias (bear / bull / none) | Not analysed |
|---|---|---|---|---|---|---|---|
| 03:16 | 01d5743 (before Plan A/B) | 10.2 min | 683 / 618 | 20 | 20 | 18 / 2 / 0 | — |
| 03:25 | 3d7a2ff (Plan A/B) | 9.2 min | 683 / 618 | 20 | 20 | 17 / 3 / 0 | — |
| 05:03 | 3d7a2ff | 12.1 min | 683 / 618 | 20 | 20 | 19 / 1 / 0 | — |
| 14:37 | 3d7a2ff + stock 720760e | 11.3 min | 682 / 617 | 20 | 18 | 10 / 8 / 0 | WLFI (no Yahoo timestamps), ASTER (Yahoo 404) |
| 15:19 | same | 13.9 min | 682 / 617 | 20 | 18 | 10 / 8 / 0 | WLFI, ASTER |
| 16:27 | same | 11.0 min | 683 / 618 | 20 | 19 | 5 / 14 / 0 | ASTER |
| 17:27 | same | 12.0 min | 682 / 617 | 20 | 18 | 3 / 15 / 0 | WLFI, ASTER |

**Notes:**
- No crypto-scanner code changed between 03:25 and 17:27, according to git.
- "17 of 20" means 17 of the 20 analysed had a bearish last 1H break; none lacked a 1H bias.
- "Screened" excludes the **72** zero-priced contracts (754 USDT perps exist) and 65 stock/commodity perps.
- The raw CoinGecko snapshot was **not saved** per scan. So the gainers and losers that were **not** shortlisted at each scan can't be reconstructed, except from the logged top-20-volume rejects.

## 2. Movers
| Product | What it is | In scope? | Why / values | When it moved (UK, Yahoo proxy) |
|---|---|---|---|---|
| INITUSDT | Crypto perp | Screened, **rejected by L1** every scan | 03:16 OI $16M, funding −0.930% · 03:25 OI $16M, −0.915% · 05:03 OI $19M, −0.819% · 14:37 OI $13M, spread 0.04%, −0.179% · 15:19 OI $12M, −0.115% · 16:27 OI $11M, −0.073% · 17:27 OI $11M, spread 0.04%, −0.074% | Rose +47% to **0.391 at 05:15**, then −30.5% (**06:35–07:35**), low 0.144 at 16:55. The whole move was between the 05:03 and 14:37 scans |
| OPGUSDT | Crypto perp | Not shortlisted (volume rank 58) and fails L1 | OI $9.3M, spread 0.07% (17:50) | +14% by 14:37–16:05 (high 0.1624 at 16:05) |
| NEARUSDT | Crypto perp | Shortlisted and analysed every scan | — | 3.587 → 3.81 (17:20). Plan A countertrend long at 00:45 was "late: TP1 reached before entry" at 01:30 |
| BNB / SOL / XRP | Crypto perps | Shortlisted and analysed | — | Steady climb from 07:00 lows; biggest hour 15:20–16:20 (+1.1–1.8%) |
| PEPE (spot) / **1000PEPEUSDT** (perp) | The perp is 1000× PEPE | Analysed 03:16–05:03; **dropped from 14:37 by the price-rounding bug** | Volume $479M, OI $110M, passes L1 | Fell −4.9% at 08:10–09:10 |
| SNXXB, MUUB, SOXLB (bStocks) | **Tokenized spot**, not USDⓈ-M perps | Out of scope (perps only) | Matching perps: SNXXUSDT (OI $30.7M, spread now 0.02%, earlier 0.27%), MUUUSDT (OI $9.4M), SOXLUSDT (OI $287M). SNXX and SOXL **pass L3 numbers but were excluded as leveraged ETFs** | About half the move (+15–17%) happened **pre-market**, the rest 14:30–16:27 |
| CRWVUSDT | Stock perp | **Not in the fixed stock list** | OI $21.6M, passes L3 | +14.8% pre-market, +26% total |
| DJT, AXTI, INTW, SKUU, MRVL | Stock-linked perps | Treated as **crypto**; all fail L1 | OI $0.9–18.9M | — |

**Gainers and losers:**
- At 17:50, **none of the top 30 gainers or top 30 losers** passed L1. In practice the shortlist was **top-volume names plus the fill to 20**.
- AGT, PUMP and ARIA have no Yahoo data.

## 3–4. Four rows per scan and where candidates were lost
- The four rows per scan (closest candidate, evidence, first blocking rule) are in `four_rows.md` below.
- Both plans and both directions were evaluated at every scan from 03:25.
- Plan B countertrend rows were evaluated but are only **printed** when one qualifies (§18).

**Day replay, 00:00–18:00 UK, live rules, 21 shortlisted coins.** Information is used only once knowable; targets are recomputed at each decision. Columns show where each sequence was lost:

| Row | Sweeps without a full sequence | Moved to countertrend row | Broke before completion | Zone filled | No retest | Late (TP1 first) | R:R < 2 | Passed |
|---|---|---|---|---|---|---|---|---|
| Plan A, Longs | 49 (first gap: break 23, strong candle 22, price gap 4) | 11 (countertrend outcome: 4 broke, 3 TP1, 2 filled, 1 no retest, 1 R:R) | 0 | 1 | 0 | 1 | 1 | 0 |
| Plan A, Shorts | 83 (break 67, strong candle 16) | 1 (filled) | 2 | 3 | 0 | 2 | 1 | 0 |
| Plan B, Longs | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Plan B, Shorts | 24 (break 24) | 0 | 0 | 0 | 0 | 1 | 0 | 0 |

**Not counted in the table above:**
- **Data:** WLFI and ASTER (shortlisted, no candles).
- **Liquidity:** 5–7 top-20-volume contracts rejected per scan.
- **Confirmation-level conflict** (the confirmation level is beyond the worst fill): §18 allows a fresh pullback within the 5- or 15-minute window, or a new swing before the plan expires. Code only evaluates the **first** confirmation. The "reconfirm" variant adds later confirmations and found 0 extra entries today.

**Paper variants** (separate replay; live rules unchanged):
| Variant | Entries |
|---|---|
| No TP1-before-entry cancel | 0 |
| No zone-fill cancel | 0 |
| Allow reconfirmation | 0 |
| 1.5:1 net instead of 2:1 | 0 |
| Strong candle optional | 0 |
| The three cancels removed together | 0 (R:R becomes the main blocker) |
| All five combined | **1**: DOGE short, ready 12:30, confirmed 14:30, filled 14:35 at 0.068184, stopped −0.96R |

## 5. Verified vs couldn't verify
| Item | Status |
|---|---|
| READY NOW | **Unavailable all day** (Binance HTTP 451) |
| Paper watchlist levels | Approximate. Yahoo vs Binance index gap ≤ 0.5% for all analysed coins (ZEC 0.6–1.0%) |
| News (Fed / CPI / jobs / Binance announcements) | **Unverified**, sources blocked. **Blackouts were not coded into the live scanner**, so no candidate was blocked by one. The one relaxed-variant entry (DOGE 14:35) fell in the US-open window and would have been blocked |
| Stock-linked depth / earnings | **Unverified**. Plan B stock context used the daily trend (proposed) |
| Stock-linked replay between scans | **Not run** (logs only) |

## Proposed fixes (not applied; need approval)
1. Use the CoinGecko `index` (or `last`) when `price` rounds to 0, so the 72 contracts get screened.
2. Detect stock-linked perps from instrument metadata instead of a fixed list, and drop the fixed stock universe.
3. Save the raw CoinGecko snapshot with every scan, so gainers and losers can be audited later.
4. Make the live status ordering time-ordered (zone fill before confirmation wins; targets as of decision time), and add "entry happened between scans".
5. Implement the documented-but-missing rules (C3, N1–N6, SL2, E3 spread, the L1 volume floor), or mark them as not active.

## CRYPTO: four rows per scan (closest candidate in the main group, as saved at scan time)

**Scan 03:25 UK** (282 sequences evaluated)

| Row | Closest candidate | First blocking rule | Evidence |
|---|---|---|---|
| Plan A, Longs | XMRUSDT | Zone filled | sweep 559.555 (swing 23:00, known 23:45) on 01:00 bar, extreme 559.384; BOS 562.295 close 563.657 @01:30; strong candle 01:30; gap 559.683-561.924, retest 02:00; worst fill 559.552, net R mid-zone 0.67 |
| Plan A, Shorts | WLDUSDT | Fails 2:1 net | sweep 0.3128 (swing 00:30, known 01:15) on 01:30 bar, extreme 0.3138; CHoCH 0.3092 close 0.3077 @02:00; strong candle 02:00; gap 0.309-0.3102, retest 02:30; confirm close 0.3091 vs 0.3098 @02:35; worst fill 0.312191, net R mid-zone 0.52 |
| Plan B, Longs | 1000PEPEUSDT | Invalidated | sweep 0.00524 (swing 09:00, known 13:00) on 13:00 bar, extreme 0.00521; BOS 0.00537 close 0.00554 @14:00; strong candle 14:00 |
| Plan B, Shorts | ZECUSDT | MISSED (entry window passed) | sweep 1231.23 (swing 09:00, known 13:00) on 14:00 bar, extreme 1234.52; BOS 1184.4 close 1167.7 @17:00; strong candle 16:00; gap 1194.03-1209.8, retest 15:00; confirm close 1085.57 vs 1161.78 @15:45; worst fill 1161.82, net R mid-zone 4.94 |

**Scan 05:03 UK** (287 sequences evaluated)

| Row | Closest candidate | First blocking rule | Evidence |
|---|---|---|---|
| Plan A, Longs | AVAXUSDT | Invalidated | sweep 8.249 (swing 11:30, known 12:15) on 13:30 bar, extreme 8.23; CHoCH 8.395 close 8.414 @14:30; strong candle 14:30 |
| Plan A, Shorts | HYPEUSDT | Zone filled | sweep 72.45 (swing 23:30, known 00:15) on 01:30 bar, extreme 72.53; BOS 71.62 close 71.36 @02:00; strong candle 01:45; gap 71.89-71.93, no retest; worst fill 72.3433, net R mid-zone 0.4 |
| Plan B, Longs | 1000PEPEUSDT | Invalidated | sweep 0.00524 (swing 09:00, known 13:00) on 13:00 bar, extreme 0.00521; BOS 0.00537 close 0.00554 @14:00; strong candle 14:00 |
| Plan B, Shorts | ZECUSDT | MISSED (entry window passed) | sweep 1231.23 (swing 09:00, known 13:00) on 14:00 bar, extreme 1234.52; BOS 1184.4 close 1167.7 @17:00; strong candle 16:00; gap 1194.03-1209.8, retest 15:00; confirm close 1085.57 vs 1161.78 @15:45; worst fill 1161.82, net R mid-zone 4.94 |

**Scan 14:37 UK** (224 sequences evaluated)

| Row | Closest candidate | First blocking rule | Evidence |
|---|---|---|---|
| Plan A, Longs | XMRUSDT | MISSED (entry window passed) | sweep 559.555 (swing 23:00, known 23:45) on 01:00 bar, extreme 559.384; BOS 562.295 close 563.657 @01:30; strong candle 01:30; gap 559.683-561.924, retest 02:00; confirm close 564.172 vs 563.974 @03:05; worst fill 565.942, net R mid-zone 7.47 |
| Plan A, Shorts | DOGEUSDT | Zone filled | sweep 0.06834 (swing 06:00, known 06:45) on 10:30 bar, extreme 0.06839; CHoCH 0.06788 close 0.06786 @12:15; strong candle 12:15; gap 0.06815-0.06822, no retest; worst fill 0.0682467, net R mid-zone 1.51 |
| Plan B, Longs | NEARUSDT | Invalidated | sweep 3.5551 (swing 11:00, known 15:00) on 15:00 bar, extreme 3.4975; no break; no strong candle |
| Plan B, Shorts | ZECUSDT | MISSED (entry window passed) | sweep 1231.23 (swing 09:00, known 13:00) on 14:00 bar, extreme 1234.52; BOS 1184.4 close 1167.7 @17:00; strong candle 16:00; gap 1194.03-1209.8, retest 15:00; confirm close 1085.57 vs 1161.78 @15:45; worst fill 1149.14, net R mid-zone 5.87 |

**Scan 15:19 UK** (220 sequences evaluated)

| Row | Closest candidate | First blocking rule | Evidence |
|---|---|---|---|
| Plan A, Longs | XMRUSDT | MISSED (entry window passed) | sweep 559.555 (swing 23:00, known 23:45) on 01:00 bar, extreme 559.384; BOS 562.295 close 563.657 @01:30; strong candle 01:30; gap 559.683-561.924, retest 02:00; confirm close 564.172 vs 563.974 @03:05; worst fill 566.1, net R mid-zone 7.64 |
| Plan A, Shorts | DOGEUSDT | Zone filled | sweep 0.06834 (swing 06:00, known 06:45) on 10:30 bar, extreme 0.06839; CHoCH 0.06788 close 0.06786 @12:15; strong candle 12:15; gap 0.06815-0.06822, no retest; worst fill 0.0683201, net R mid-zone 0.92 |
| Plan B, Longs | NEARUSDT | Invalidated | sweep 3.5551 (swing 11:00, known 15:00) on 15:00 bar, extreme 3.4975; no break; no strong candle |
| Plan B, Shorts | ZECUSDT | MISSED (entry window passed) | sweep 1231.23 (swing 09:00, known 13:00) on 14:00 bar, extreme 1234.52; BOS 1184.4 close 1167.7 @17:00; strong candle 16:00; gap 1194.03-1209.8, retest 15:00; confirm close 1085.57 vs 1161.78 @15:45; worst fill 1149.14, net R mid-zone 5.87 |

**Scan 16:27 UK** (250 sequences evaluated)

| Row | Closest candidate | First blocking rule | Evidence |
|---|---|---|---|
| Plan A, Longs | XMRUSDT | MISSED (entry window passed) | sweep 559.555 (swing 23:00, known 23:45) on 01:00 bar, extreme 559.384; BOS 562.295 close 563.657 @01:30; strong candle 01:30; gap 559.683-561.924, retest 02:00; confirm close 564.172 vs 563.974 @03:05; worst fill 567.207, net R mid-zone 8.82 |
| Plan A, Shorts | ZECUSDT | Invalidated | sweep 993.64 (swing 11:45, known 12:30) on 13:45 bar, extreme 996.52; BOS 972.91 close 972.78 @14:45; no strong candle |
| Plan B, Longs | NEARUSDT | Invalidated | sweep 3.5551 (swing 11:00, known 15:00) on 15:00 bar, extreme 3.4975; no break; no strong candle |
| Plan B, Shorts | ZECUSDT | MISSED (entry window passed) | sweep 1231.23 (swing 09:00, known 13:00) on 14:00 bar, extreme 1234.52; BOS 1184.4 close 1167.7 @17:00; strong candle 16:00; gap 1194.03-1209.8, retest 15:00; confirm close 1085.57 vs 1161.78 @15:45; worst fill 1149.14, net R mid-zone 5.87 |

**Scan 17:27 UK** (233 sequences evaluated)

| Row | Closest candidate | First blocking rule | Evidence |
|---|---|---|---|
| Plan A, Longs | XMRUSDT | MISSED (entry window passed) | sweep 582.354 (swing 14:30, known 15:15) on 15:15 bar, extreme 581.967; BOS 585.094 close 589.542 @15:30; strong candle 15:30; gap 584.026-586.459, retest 16:00; confirm close 588.596 vs 587.669 @16:30; worst fill 584.939, net R mid-zone 1.81 |
| Plan A, Shorts | ZECUSDT | Invalidated | sweep 1002.49 (swing 07:45, known 08:30) on 15:30 bar, extreme 1004.36; no break; no strong candle |
| Plan B, Longs | NEARUSDT | Invalidated | sweep 3.5551 (swing 11:00, known 15:00) on 15:00 bar, extreme 3.4975; no break; no strong candle |
| Plan B, Shorts | ZECUSDT | MISSED (entry window passed) | sweep 1231.23 (swing 09:00, known 13:00) on 14:00 bar, extreme 1234.52; BOS 1184.4 close 1167.7 @17:00; strong candle 16:00; gap 1194.03-1209.8, retest 15:00; confirm close 1085.57 vs 1161.78 @15:45; worst fill 1149.14, net R mid-zone 5.87 |


## STOCK-LINKED: four rows per scan (closest candidate in the main group, as saved at scan time)

**Scan 14:37 UK** (231 sequences evaluated)

| Row | Closest candidate | First blocking rule | Evidence |
|---|---|---|---|
| Plan A, Longs | GOOGLUSDT | Conflict (opposite break) | sweep 284.65 (swing 17:45, known 18:30) on 20:45 bar, extreme 284.59; CHoCH 286.525 close 295.39 @14:30; strong candle 14:30; gap 286.02-292.6, retest 16:05; confirm close 291.88 vs 291.73 @17:35; worst fill 287.802, net R mid-zone 1.19 |
| Plan A, Shorts | SNDKUSDT | Conflict (opposite break) | sweep 912.09 (swing 14:45, known 15:30) on 15:00 bar, extreme 914.82; BOS 841.034 close 836.14 @16:45; strong candle 15:15; gap 883.64-889.07, no retest; worst fill 889.993, net R mid-zone 1.69 |
| Plan B, Longs | SPCXUSDT | Invalidated | sweep 134.5 (swing 20:30, known 17:30) on 14:30 bar, extreme 133.14; no break; strong candle 14:30 |
| Plan B, Shorts | MSTRUSDT | MISSED (TP1 reached before entry) | sweep 145.3 (swing 19:30, known 16:30) on 14:30 bar, extreme 146.045; CHoCH 134.466 close 129.683 @14:30; strong candle 14:30; gap 132.14-141.68, no retest; worst fill 137.565, net R mid-zone 1.81 |

**Scan 15:19 UK** (239 sequences evaluated)

| Row | Closest candidate | First blocking rule | Evidence |
|---|---|---|---|
| Plan A, Longs | GOOGLUSDT | Conflict (opposite break) | sweep 284.65 (swing 17:45, known 18:30) on 20:45 bar, extreme 284.59; CHoCH 286.525 close 295.39 @14:30; strong candle 14:30; gap 286.02-292.6, retest 16:05; confirm close 291.88 vs 291.73 @17:35; worst fill 287.802, net R mid-zone 1.19 |
| Plan A, Shorts | NVDAUSDT | Invalidated | sweep 169 (swing 19:00, known 19:45) on 20:45 bar, extreme 169.535; no break; no strong candle |
| Plan B, Longs | SPCXUSDT | Invalidated | sweep 134.5 (swing 20:30, known 17:30) on 14:30 bar, extreme 133.14; no break; strong candle 14:30 |
| Plan B, Shorts | MSTRUSDT | MISSED (TP1 reached before entry) | sweep 145.3 (swing 19:30, known 16:30) on 14:30 bar, extreme 146.045; CHoCH 134.466 close 129.683 @14:30; strong candle 14:30; gap 132.14-141.68, no retest; worst fill 137.565, net R mid-zone 1.81 |

**Scan 16:27 UK** (226 sequences evaluated)

| Row | Closest candidate | First blocking rule | Evidence |
|---|---|---|---|
| Plan A, Longs | GOOGLUSDT | Conflict (opposite break) | sweep 284.65 (swing 17:45, known 18:30) on 20:45 bar, extreme 284.59; CHoCH 286.525 close 295.39 @14:30; strong candle 14:30; gap 286.02-292.6, retest 16:05; confirm close 291.88 vs 291.73 @17:35; worst fill 287.802, net R mid-zone 1.19 |
| Plan A, Shorts | NVDAUSDT | Invalidated | sweep 175.13 (swing 14:30, known 15:15) on 15:30 bar, extreme 175.24; no break; no strong candle |
| Plan B, Longs | SPCXUSDT | Invalidated | sweep 134.5 (swing 20:30, known 17:30) on 14:30 bar, extreme 133.14; no break; strong candle 14:30 |
| Plan B, Shorts | MSTRUSDT | MISSED (TP1 reached before entry) | sweep 145.3 (swing 19:30, known 16:30) on 14:30 bar, extreme 146.045; CHoCH 134.466 close 129.683 @14:30; strong candle 14:30; gap 132.14-141.68, no retest; worst fill 137.565, net R mid-zone 1.81 |

**Scan 17:27 UK** (221 sequences evaluated)

| Row | Closest candidate | First blocking rule | Evidence |
|---|---|---|---|
| Plan A, Longs | GOOGLUSDT | Conflict (opposite break) | sweep 284.65 (swing 17:45, known 18:30) on 20:45 bar, extreme 284.59; CHoCH 286.525 close 295.39 @14:30; strong candle 14:30; gap 286.02-292.6, retest 16:05; confirm close 291.88 vs 291.73 @17:35; worst fill 287.802, net R mid-zone 1.19 |
| Plan A, Shorts | NVDAUSDT | Invalidated | sweep 175.13 (swing 14:30, known 15:15) on 15:30 bar, extreme 175.24; no break; no strong candle |
| Plan B, Longs | SPCXUSDT | Invalidated | sweep 134.5 (swing 20:30, known 17:30) on 14:30 bar, extreme 133.14; no break; strong candle 14:30 |
| Plan B, Shorts | MSTRUSDT | MISSED (TP1 reached before entry) | sweep 145.3 (swing 19:30, known 16:30) on 14:30 bar, extreme 146.045; CHoCH 134.466 close 129.683 @14:30; strong candle 14:30; gap 132.14-141.68, no retest; worst fill 137.565, net R mid-zone 1.81 |

