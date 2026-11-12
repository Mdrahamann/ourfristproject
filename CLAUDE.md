# CLAUDE.md

## Trading analyst rules: v0.2 (11 Nov 2026). Decisions locked; thresholds are still PROVISIONAL

Read-only ICT/SMC analyst for Binance USDⓈ-M perpetuals (crypto and stock/ETF-linked).
**Never place orders.** Paper trading and journalling only.
All times are UK time (`Europe/London`, which handles GMT and BST).

**Rule tags**
| Tag | Meaning |
|---|---|
| `[EXISTING]` | From your `crypto-futures-scalping-analyst` skill |
| `[SESSION]` | Adopted in our chat sessions (8–11 Nov 2026) |
| `[SCANNER]` | Already coded in `trading/scanner/smc_scan.py` |
| `[PROPOSED]` | A threshold I am proposing. **Needs your approval** |
| `[UNRESOLVED]` | I cannot infer it from your system. **Needs your decision** |

### Routine scans: keep usage low `[LOCKED 12 Nov]`
- **`scan now`** → run once, from the repository root: `python3 trading/scanner/scan.py`. Reply with the **short result only**:
  - the status table (original 15m/5m scalp first, separate 1H/15m plan second, Long and Short for each, with the status and the exact price or candle close being waited for);
  - the "What do I do now?" cards;
  - **one line** on data. If live contract data is unavailable, say so in that line and still show any useful watchlist result.
- **Routine scans skip** repository reviews, code edits, backtests and commits. `scan.py` appends the journal row itself, to the local file only.
- **If the command fails**, show its error output and stop. Fixing it is a separate request.
- **`full scan`** → `python3 trading/scanner/scan.py --full` (full tables and chart evidence).
- **`audit scan`** → the full scan plus coverage and data checks: what wasn't screened or evaluated, and why.
- **`scan <SYMBOL>`** → `python3 trading/scanner/scan.py --symbol <SYMBOL>`. Works for any Binance USDT perp, and for the stock-linked list in `trading/scanner/cli.py`.
- Stock-linked contracts are included automatically while the US market is open; `--stocks` forces them.

### Decisions locked on 11 Nov 2026 (v0.2). These override anything below
1. **Capital first.**
   - Risk up to **0.25% of the starting account balance** per trade (main group), or **0.125%** (countertrend group).
   - Maximum simulated position **$1,000 notional, leverage included**.
   - Size = risk ÷ (stop distance + estimated costs per unit).
   - If the minimum order size would exceed the risk limit, **skip the setup**.
   - **Never increase size** to recover a loss or to reach a daily goal.
   - **Balance and fee rates come from the user.** Until then, $ figures use a labelled placeholder balance.
2. **Session stop (paper):** stop for the UK day after **2 losing trades** or a **−0.5% drop from the starting session balance**, whichever comes first.
3. **B2:** the main strategy requires **1H alignment**. Countertrend 15m setups go to a **separate paper group at half risk**, so the two can be compared.
4. **C2 (canonical trigger):** after the planned retest, a **fully closed 5m candle beyond the last confirmed 5m swing** (high for a long, low for a short). Only swings already confirmed before that candle opened count.
5. **READY NOW** needs that candle already closed **and** a fresh quote for the exact contract inside the entry range (§16). Usual conditional plans still apply.
6. **Thresholds stay `[PROPOSED]`.** Before any threshold is called validated, show for the development period and for a later untouched period:
   - sample size
   - net results after costs
   - maximum drawdown
7. **News (N1):**
   - No new paper entries from **T−15 to T+30 minutes** around major scheduled events that affect the setup.
   - For stock-linked contracts, **company earnings** count as such an event.
   - Show the source and UK time for each event.
   - If the spread is still outside the filter after the window, keep waiting.
8. **Stock-linked contracts:**
   - OI ≥ $20M is **provisional**.
   - Also check spread, recent volume and **order-book depth on the exact contract**.
   - Skip the setup if the position would be hard to fill within the entry range.
   - If depth can't be checked, mark the setup **unverified**: no READY NOW.
9. **Fees:**
   - Fee tier is unconfirmed, so **ask the user** for the maker/taker rates on USDⓈ-M Futures.
   - Until then, use a **labelled taker-fee estimate (0.05%) on both entry and exit**, plus spread, slippage and funding where applicable.
10. **Data:**
    - **No remote access** to the user's computer or account. Public, read-only market data only.
    - If the exact contract's quote and closed candles can't be verified, show **conditional plans only**.
11. **Daily goal tracking:**
    - Report how often a day ends with **$20–$30 net**, and with **≥ $20 net**.
    - A zero-trade day is a valid day.
    - The journal also reports:
      - how often a scan found a valid entry
      - how often a READY NOW alert was still fillable when it arrived

**Where the examples come from:** the 10–11 Nov scans. They use Yahoo spot candles as a stand-in for the Binance contract, unless marked otherwise.

---

### 0. Data rules
- **D1 Closed candles only.** A bar counts only after `open_time + interval ≤ now`. Anything else is labelled "developing". `[EXISTING]`
  - PASS: at 01:32:27, the 01:25 5m bar (closed 01:30) is used.
  - FAIL: treating the 01:30 bar as closed at 01:32.
- **D2 Knowability.** A swing or FVG can be used only from the moment it became knowable (recorded as `known_at`). `[SCANNER]`
  - PASS: the 22:00 15m swing high (N=2) is known at 22:45.
  - FAIL: using that swing at 22:30.
- **D3 Contract identity.** Confirm the exact Binance symbol, `contractType = PERPETUAL`, status `TRADING`, and the product type (crypto, or stock/ETF-linked). `[EXISTING]`
  - PASS: `SPCXUSDT` → Space Exploration Technologies Corp., an equity-linked perp.
  - FAIL: analysing spot `ZEC-USD` and calling it the contract.
- **D4 Proxy data** (spot, index, underlying stock, delayed snapshots) can feed **watchlists only**. Never READY NOW. `[SESSION]`

### 1. Universe and liquidity
- **L1 Crypto filter:**
  - OI ≥ $50M `[SESSION]`
  - spread ≤ 0.03% `[SESSION]`
  - |funding| ≤ 0.05% per 8h `[SESSION]`
  - 24h quote volume ≥ **$100M** `[PROPOSED]`. Your skill names quote volume but gives no number.
  - PASS: BTCUSDT (OI $7.4B, spread 0.01%, funding +0.007%).
  - FAIL: INITUSDT (OI $15M, funding −1.17%).
- **L2 Shortlist:** top 20 by quote volume, plus the top 5 gainers and top 5 losers that pass L1, capped at 30. `[PROPOSED]` (your skill says top 10 by volume plus top 10 gainers.) Always report counts screened and analysed.
- **L3 Stock/ETF-linked filter:**
  - OI ≥ **$20M** `[SESSION, I relaxed this; needs approval]`
  - spread ≤ **0.05%** `[PROPOSED]`
  - |funding| ≤ 0.05%
  - Trade only during the US regular session: 09:30–16:00 New York, converted to UK time each day because the two countries change clocks on different dates. Flat by 20:55 UK in normal weeks `[SESSION]`.
  - Exclude leveraged and inverse ETFs (SOXL, SOXS, TQQQ, SQQQ, KORU, …) from buy-zone lists `[PROPOSED]`.
  - PASS: SPCXUSDT (OI $508M).
  - FAIL: AMZNUSDT (OI $15M), NVDAUSDT (funding +0.057%).

### 2. Higher-timeframe bias
- **B1 Bias** = direction of the last confirmed BOS/CHoCH (by candle close). Swings use N=2 on 4H and N=3 on 1H. `[SCANNER]`
- **B2 Gating** `[LOCKED v0.2]`: the main strategy requires 1H alignment; countertrend setups go to a separate half-risk paper group. Earlier proposal, kept for reference:
  - A 15m setup that agrees with the 1H bias gets full risk.
  - A setup against the 1H bias gets half risk at most, and only if the 4H isn't in the same direction as the 1H.
  - PASS: a short when 1H = bear.
  - FAIL (as proposed): the NEAR long on 11 Nov 01:25, when both 1H and 4H were bear, would be refused.

### 3. Swings
- **S1** Swing high at bar i: `high[i]` is greater than the N bars to its left and greater than or equal to the N bars to its right. Swing lows mirror this. N = 2 (5m, 15m, 4H) or 3 (1H). Knowable at the close of bar i+N. `[SCANNER]`, thresholds `[PROPOSED]`
  - PASS: BTC 15m swing high 74,459 at 10:00 (known 10:45).
  - FAIL: ETH 14:30 high 2,084.2 is not a swing, because the 15:00 high of 2,093.1 is higher.
- **S2 Equal highs/lows:** at least 2 swings within max(0.05% of price, 0.1×ATR14 on that TF). `[PROPOSED]`

### 4. Liquidity sweep
- **SW1** A bar trades beyond a confirmed, untaken swing level and **closes back inside** it. `[SCANNER]`
  - PASS: NEAR 15m at 23:00 on 10 Nov. Low 3.5255 went below the 3.537 swing (known 22:00), and the bar closed at 3.5437.
  - FAIL: ETH 15:00 on 10 Nov. Its high of 2,093.1 never exceeded the confirmed 2,099.7 swing.
- **SW2 Multi-bar failed breakout** (closes beyond, then back inside within 2 bars) `[UNRESOLVED]`. Proposal: count it, labelled "sweep (2-bar)". `[PROPOSED]`

### 5. Displacement
- **DP1** Range ≥ 1.5×ATR14 (that TF) **and** body ≥ 60% of range, in the trade direction. `[SCANNER]`, thresholds `[PROPOSED]`
  - PASS: NEAR 15m bull bar at 23:30 on 10 Nov.
  - FAIL: ETH 15m bar at 13:30 on 10 Nov. The range was big, but the body was only about 52% of it.

### 6. Market-structure shift
- **MS1 BOS/CHoCH** = a candle **close** beyond the latest confirmed opposite swing. It's a CHoCH if it flips the previous break direction, otherwise a BOS. A wick alone never counts. `[SCANNER]`
  - PASS: NEAR 15m at 00:30. Close 3.6369 is above 3.6068 (swing at 22:00, known 22:45).
  - FAIL: ZEC 15m on 10 Nov 15:00–15:15. The wick reached 1,196.7 above 1,192, but the candle closed at 1,181.
- **MS2 MSS** = a CHoCH or BOS within 16 setup-TF bars after a sweep in the same direction. `[SCANNER]`, window `[PROPOSED]`

### 7. Fair value gaps
- **F1 FVG** (3-candle gap):
  - Bullish if `low[i] > high[i−2]`. Bearish if `high[i] < low[i−2]`.
  - Size must be ≥ 0.1×ATR14.
  - Known at the close of bar i.
  - States: untouched, touched (a wick reaches the near edge), filled (a wick goes through the far edge). `[SCANNER]`, thresholds `[PROPOSED]`
  - PASS: NEAR bull FVG 3.5684–3.5800 (11 Nov), untouched at 01:25.
  - FAIL: ETH bear FVG 2,033–2,050.7 from 15:30 on 10 Nov, filled by the 20:20 high of 2,053.9.

### 8. Setup status (15m)
- **ST1 Candidate** = SW1 sweep, then DP1 + MS2 within 16 bars, then an unfilled F1 FVG created in that leg. It must not be invalidated, and there must be no later 15m BOS/CHoCH in the opposite direction. Lookback is 96 bars. `[SCANNER]`
- **ST2 Watch** = some steps are missing. List which ones.
- **ST3 Invalidated** = a setup-TF close beyond the sweep extreme.
  - PASS (Candidate): NEAR long on 11 Nov 01:25.
  - FAIL (downgraded to Watch, conflict): BNB short on 10 Nov, after a bullish 15m CHoCH at 20:45.

### 9. Retest and confirmation
- **C1 Zone touch:** a 5m bar trades into the FVG.
- **C2 Confirmation:** after the touch, a **5m close beyond the latest confirmed 5m swing** in the trade direction (a 5m BOS/CHoCH). `[SCANNER]`
  - `[LOCKED v0.2]`: this is the only trigger. The other variants used in chat ("red/green 5m close back inside the zone", "15m close back above the zone") are retired.
- **C3** Confirmation must come within 12 × 5m bars (60 minutes) of the first touch, or the setup goes back to Watch. `[PROPOSED]`
  - PASS: PEPE long on 11 Nov. Zone touched 00:30, 5m BOS close 0.00548 at 01:25 (then it failed the R:R gate).
  - FAIL: BTC short on 10 Nov. Zone touched 16:15, 5m CHoCH only at 19:10, more than 60 minutes later.

### 10. Entry range and worst acceptable fill
Costs `[PROPOSED]`, unless your fee tier is different:
- Taker fee f_t = 0.05% **ESTIMATE, applied to entry and every exit** (v0.2; fee tier unconfirmed); maker fee not used until confirmed
- Stop slippage s = 0.02%
- Entry at the **ask (long) or bid (short)**, so the spread is already paid and is **not added again**
- TP exits are limit (maker) orders; stop exits are market (taker) orders with slippage
- Funding is added only if the trade is expected to be held across 00:00, 08:00 or 16:00

| | Formula: worst acceptable fill, net R ≥ 2 to the main target |
|---|---|
| Long | `W_max = [TP·(1−f_m) + 2·SL·(1−s−f_t)] / [3·(1+f_t)]` |
| Short | `W_min = [TP·(1+f_m) + 2·SL·(1+s+f_t)] / [3·(1−f_t)]` |

- The entry range is from the near edge of the zone to `W_max` (long) or `W_min` (short).
  - PASS: BNB long, TP 690.3 and SL 677.2 → W_max ≈ 680.87. A fill at 680.3 is valid.
  - FAIL: ETH short on 10 Nov 15:05. The close of 2,082 was below the plan minimum (2,090) and gave about 1.5R → no entry.
- The scanner currently adds the spread **on top of** fees and slippage. Fix this when bid/ask quotes are used.

### 11. Stops
- **SL1** Stop = sweep extreme ∓ max(0.10% × price, 0.25 × ATR14 on 15m). `[SCANNER]`, buffer `[PROPOSED]`
- **SL2** A stop must not sit within the S2 tolerance of a visible untaken swing or an equal-high/low cluster unless it is beyond it. `[SESSION, from the XRP loss on 7 Nov]`
- **SL3** Stop distance must be ≥ 0.30% of price. `[SESSION]`
- **SL4** Never widen a stop. Exits and risk reduction are always allowed. `[EXISTING]`
  - PASS: NEAR long, stop 3.518, about 0.21% beyond the 3.5255 sweep low.
  - FAIL: AVAX long on 9 Nov, stop 8.48, only 0.01 from the visible 8.47 low at 19:15.
- **Weekend buffer** size `[UNRESOLVED]`.

### 12. Targets
- **T1** TP1 and TP2 = the nearest **untaken** confirmed swings on the far side (15m first, then 1H). TP2 is the main target for the 2R gate. `[SCANNER]`, `[SESSION]`
- **T2** If an unfilled opposing 15m or 1H FVG sits between entry and target, cap the target at its near edge. `[PROPOSED]`
  - FAIL example: ZEC long on 10 Nov 21:36 targeted 1,196.7 straight through the gaps left by the crash.
- **T3** Take 50% at TP1, then move the stop to break-even. `[SESSION]`

### 13. Expiry and invalidation
- **E1 READY NOW window** after the confirming close: 5m confirmation → 5 minutes; 1–2m refinement → 1–2 minutes. `[PROPOSED, mapping UNRESOLVED]`
- **E2 WAIT FOR TRIGGER expiry:** 16 setup-TF bars after the FVG became known, or session end, whichever comes first. `[PROPOSED]` In our sessions this was set ad hoc.
- **E3 Invalidate if any of these happens:**
  - a setup-TF close beyond the sweep extreme
  - an opposite 15m BOS/CHoCH
  - TP1 is reached before entry (don't chase)
  - the spread breaches L1/L3 `[SESSION]`
  - FAIL example: the ETH short entered at 18:40 on 10 Nov, after the plan's 18:30 expiry.

### 14. Time and news blackouts
- **N1 Major scheduled news** (FOMC decision and press conference, CPI, NFP/jobs): no new entries from T−15 to T+30 minutes. `[EXISTING says "15–30 minutes around"; exact window PROPOSED]`
- **N2 Funding** (00:00, 08:00, 16:00): no new entries from T−10 to T+5 minutes. `[SESSION used 15:50–16:05]`
- **N3 Fixed windows:** US open (09:30 New York −15/+15 minutes); 07:45–08:15. `[SESSION]`
- **N4** 13:15–13:45 UK on weekdays when the US data calendar is unverified. `[SESSION, after the 10 Nov 13:30 spike]`
- **N5 Earnings:** no stock-linked entries if earnings fall before the next US close. `[PROPOSED]`
- **N6 Binance announcements:** a symbol with a delisting, maintenance or contract-change notice is excluded. `[PROPOSED]`
  - PASS: entering at 14:50 UK on a day with no 08:30 New York release.
  - FAIL: holding the ZEC short through 13:30 on 10 Nov.

### 15. Risk and session limits
- **R1** Risk 0.25% per trade `[EXISTING]`. Half size (0.125%) after shock events `[SESSION]`; when to go back to full size is `[UNRESOLVED]`.
- **R2** At most 1 long and 1 short open at once; correlated positions count as combined risk. `[SESSION]`, `[EXISTING]`
- **R3** Net R:R ≥ 2.0 to the main target. Refuse rather than shrink. A failed gate is final. `[EXISTING]`
- **R4** `[LOCKED v0.2]` Paper session stop: **2 losing trades or −0.5% from the starting session balance** (UK day). This is tighter than the skill's 3 losses / −1%.

### 16. READY NOW gate (all must pass)
1. ST1 Candidate, with C2 confirmation closed **on the exact Binance contract** (TF, close time, close price, level).
2. A bid/ask for that contract, refreshed immediately before replying, **≤ 15 seconds old**, with source and UK timestamp.
3. The entry-side quote (ask for a long, bid for a short) is inside `[zone edge, W_max/W_min]`.
4. The spread is within L1/L3, the setup is within the E1 window, and it is not invalidated.
5. The news check is done or flagged as unverified, and N1–N6 pass.

Otherwise the result is WAIT FOR TRIGGER, MISSED (window or fill passed), or "READY NOW unavailable — live contract data missing".

### 17. Defined in your skill but not yet checkable `[UNRESOLVED]`
Order blocks, breakers, premium/discount, VWAP and volume confirmation, and the "extended candle / 24h extreme" filter.
Proposal for the last one: skip a long if price is within 0.25×ATR(1H) of the 24h high (mirror for shorts). `[PROPOSED]`
Until these are defined they are **excluded from automated checks**.

### 18. Two plans on every `scan now` `[LOCKED 11 Nov; order and names updated 11 Nov evening]`
**Every scan output starts with these four rows, in this order**, before anything else:

| Plan | Direction |
|---|---|
| Original scalp plan — 15m setup, 5m confirmation (main strategy) | Long |
| Original scalp plan — 15m setup, 5m confirmation (main strategy) | Short |
| Separate 1H plan — 1H setup, 15m confirmation | Long |
| Separate 1H plan — 1H setup, 15m confirmation | Short |

**"What do I do now?" summary** `[LOCKED 12 Nov]`: printed **above** the four rows on every scan, readable in a few seconds, in plain English. The detailed table stays underneath for understanding the setup.
- One card per live setup, titled `<COIN> long — WAIT`, `— READY NOW` or `— CANCELLED` (shorts the same; countertrend adds "(countertrend, half risk)").
- **WAIT, setup not complete yet** (only the structure break is missing):
  1. the exact setup-TF candle **close** needed (level and "by" deadline); a quick move past the level during the candle doesn't count;
  2. the retest zone; after the break, the exact confirmation candle close is given; a touch of the zone alone is still WAIT;
  3. cancel conditions (no close by the deadline, a close beyond the sweep extreme, price trading through the zone).
- **WAIT, setup complete:** the zone, the exact confirmation close (TF, level, swing time), the entry limits, stop-loss, target, cancel conditions and expiry.
- **READY NOW** (only when §16 passes): entry range, stop-loss, target and expiry **together** in one table. If the confirmation closed but only proxy data is available, the card says "CONFIRMED on stand-in prices (not READY NOW)" with the same table.
- **CANCELLED:** any setup shown on the previous scan that is no longer live, with the plain reason.
- No live setup: "Nothing to do — WAIT." At most 3 cards; any others are listed by name.

- Each row shows the best qualifying setup with its conditional entry plan, **including the exact candle close being waited for** (TF, direction, level, and the swing it comes from).
- **An empty row always says which case it is:**
  - `Checked N of M: no qualifying setup`, plus the closest setup, its chart evidence (swing, sweep, break, price gap, retest, confirmation close) and the first rule that blocked it, with the value or time; or
  - `Not evaluated: no usable candle data` (and every contract that couldn't be evaluated is listed under Data).
- If one plan has no qualifying setup, the other plan's results are still shown. Both directions are checked in both plans on every scan.
- **The original scalp is computed by the original scanner code, unchanged** (`trading/scanner/scalp_original.py`, moved verbatim from `smc_scan.py` at commit `01d5743`). Status labels and conditional plans are added on top by `scalp_status.py`, using the existing rules R3, SL3, E1, E2 and E3. The separate rewrite used for "Plan A" between 03:26 and 18:00 on 11 Nov is retired. One addition (12 Nov): a setup already shown to you keeps being tracked until one of its own cancel conditions happens, even if a newer sweep on the same coin becomes the latest sequence; with nothing tracked, the output is identical to the original.

**Countertrend paper group:** setups against the 1H trend (scalp) or the 4H trend (1H plan) are shown in a separate table directly under the four rows, at **half risk**, for both directions of both plans.

**Original scalp plan: 15m setup, 5m confirmation** (main strategy; formerly "Plan A")
- **Setup:** §3–§8 on 15m. A sweep, then a strong candle plus a structure break within 16 bars, then an unfilled 15m price gap that is the retest zone. Lookback is 24 hours.
- **Confirmation (C2):** after the retest, a **fully closed 5m candle beyond the last confirmed 5m swing** (high for a long, low for a short). Only swings confirmed before that candle opened count.
- **Trend:** 1H context. A 1H-aligned setup is main group; otherwise it goes in the countertrend table at half risk.
- **Targets:** untaken 15m **and** 1H swings, nearest first (T1), capped at an opposing unfilled 15m price gap (T2), as the original scanner did.
- **READY NOW window:** 5 minutes from the confirming close `[PROPOSED]`.
- **Plan expiry:** 16 × 15m bars after the price gap became known `[PROPOSED]`.

**Separate 1H plan: 1H setup, 15m confirmation** (additional option; formerly "Plan B")
- **Setup:** the same rules on 1H. Swings use N=3, the sequence window is 16 1H bars, and lookback is 72 hours. Zone = the 1H price gap.
- **Stop:** 1H sweep extreme ∓ max(0.10%, 0.25×ATR14 on 1H).
- **Targets:** untaken 1H swings, capped at the near edge of an opposing unfilled 1H price gap.
- **Confirmation:** after the retest, a **fully closed 15m candle beyond the last confirmed 15m swing** in the trade direction.
- **Trend:** 4H context. A 4H-aligned setup is main group; a countertrend setup gets half risk in its own row `[PROPOSED]`.
- **READY NOW window:** 15 minutes from the confirming 15m close `[PROPOSED]`.
- **Plan expiry:** 16 × 1H bars after the 1H price gap became known `[PROPOSED]`.
- **Invalidation:** a 1H close beyond the sweep extreme, an opposite 1H break, TP1 reached before entry, or the zone filled before confirmation.

**Both plans** keep the L1/L3 liquidity, N1–N6 news, R1–R4 risk and **2:1 net** rules unchanged. Every row shows:
- entry range (zone edge → **worst acceptable fill**)
- exact confirmation level
- stop, TP1/TP2, net R, expiry, invalidation and alert level

**Confirmation level vs worst fill:**
- If the current confirmation level is beyond the worst fill (for example, a long that must close above 3.6972 when the maximum entry is 3.5910), the plan needs **either a fresh pullback to the worst fill after confirmation, or a new, lower swing (higher swing for a short) to confirm against**.
- If neither happens within the READY NOW window, the setup is **MISSED**.

**Statuses:**
| Status | Meaning |
|---|---|
| `READY NOW` | Only with the exact Binance contract's closed candles **and** a fresh bid/ask (§16) |
| `CONFIRMED` | Inside the entry window, but the data is a proxy (paper only) |
| `WAIT FOR TRIGGER` | Zone not touched yet |
| `WAIT FOR TRIGGER (in zone)` | Zone touched, confirmation not closed yet |
| `MISSED` | Entry window passed, worst fill passed, or TP1 reached before entry |
| `Expired`, `Conflict`, `Zone filled`, `Fails 2:1 net`, `Invalidated`, `Watch` | Setup no longer valid or incomplete |

**Proxy data** (Yahoo spot candles, CoinGecko snapshots): every level is labelled **approximate**, setups stay on the **paper watchlist**, and the scan prints "READY NOW unavailable — live contract data missing".

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
