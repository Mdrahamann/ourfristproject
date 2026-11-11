# Chart review template

Judge each decision **only with what was visible at the decision time**. Record the outcome **separately**, after the fact, and never let it change the verdict.

```
Symbol (exact Binance):        e.g. NEARUSDT (USDⓈ-M perp, crypto)
Setup / direction:             e.g. ST1 Candidate, LONG
Timeframes:                    4H / 1H bias · 15m setup · 5m confirmation
Decision timestamp (UK):       e.g. Wed 11 Nov 2026 01:25:11
Data used + age:               e.g. Yahoo spot 15m/5m (closed to 01:15 / 01:20), CoinGecko 9 min old  → proxy: watchlist only
Visible at decision time:      swings (with known_at), sweep, displacement, BOS/CHoCH, FVG + state, quote if any

Rule-by-rule verdict (rule IDs from CLAUDE.md; PASS / FAIL / N/A / UNVERIFIED):
  D1 closed candles … D3 contract … L1/L3 liquidity … B2 bias … SW1 sweep … DP1 displacement … MS2 shift …
  F1 FVG … C2 confirmation … entry vs W_max/W_min … SL1–SL3 stop … T1/T2 targets … E1–E3 expiry … N1–N6 news … R1–R4 risk
Final decision label:          READY NOW / WAIT FOR TRIGGER / WATCH / MISSED / NO TRADE / RULE VIOLATION

--- recorded later (outcome) ---
Fill:                          actual or "estimated from candles" (say which)
Path:                          TP1 / TP2 / stop / expiry, with times; "AMBIGUOUS" if one candle hit both
Net R (fees, slippage, funding):
Notes:
```

---

## Examples from your journal (8–11 Nov 2026)

These are reconstructed from our session notes. The candle checks were done on Yahoo spot data, not Binance contract candles, so **the exact fills are not verified**.

### 1. Winner, but the plan's entry range was too wide: ZECUSDT SHORT, Mon 9 Nov
| | |
|---|---|
| **Decision** | 18:04 UK plan: red 5m close below 1,188 after touching 1,188–1,195; entry ≥ 1,186; SL 1,207; TP1 1,160; TP2 1,145 |
| **Visible then** | 1H downtrend, plus a retest of the zone where price broke down |
| **Verdict** | Structure, confirmation and stop PASS. **Entry range FAIL in part**: the W_min formula gives **1,187.6**. A fill at 1,188 → net 2.06R ✅; a fill at 1,186 → net 1.79R ❌. The plan allowed fills down to 1,186 because it was sized on *gross* R:R |
| **Label** | READY NOW-eligible only for fills of 1,187.6 or higher |
| **Outcome** | Zone touched about 19:15 (~1,190). TP1 hit 23:00 (low 1,152.8), TP2 hit about 08:15 on 10 Nov. **Winner.** The actual fill is unknown |

### 2. Loser (valid only if entered before 19:15): AVAXUSDT LONG, Mon 9 Nov
| | |
|---|---|
| **Decision** | 18:04 UK plan: green 5m close above 8.64 after touching 8.58–8.62; entry ≤ 8.65; SL 8.48; TP1 8.85 |
| **Verdict** | If entered **before** 19:15, the rules PASS, so it's a **valid loser**. If entered **after** 19:15, the 8.47 swing low was visible right at the stop, so it **FAILS SL2** |
| **Outcome** | Stopped about 07:00 on 10 Nov (low ~8.46). **Loser, −1R.** The user's entry time isn't recorded, so the label stays conditional |

### 3. Near-miss, correctly skipped: ETHUSDT SHORT, Tue 10 Nov
| | |
|---|---|
| **Decision** | 14:56 plan: zone 2,090–2,098; red 5m close at **2,090 or higher**; SL 2,108; TP2 2,042 |
| **Visible then** | 15:00 touched 2,093.1 ✅. The 15:05 red close was **2,082.4** ❌, below the minimum (about 1.5R) |
| **Verdict** | Entry rule FAIL, so NO TRADE was correct |
| **Outcome** | ETH fell to 2,006 by 15:40. A winner if chased; **correctly skipped** |

### 4. Entry already passed (MISSED / no chase): NEARUSDT LONG, Wed 11 Nov
| | |
|---|---|
| **Decision** | 01:25 plan: zone 3.568–3.580; 5m BOS after touch; enter ≤ 3.585; cancel if > 3.66 before a pullback |
| **Visible then** | Candidate (sweep 23:00 → displacement 23:30 → BOS 00:30 → untouched FVG) |
| **Verdict** | The zone was never touched, and 3.66 printed first, so the setup was **CANCELLED (E3)** |
| **Outcome** | Ran to 3.70 by 01:40 with no fill. **Correct.** (PEPE at 01:25 is a second example: confirmed, but failed R3 at 1.3–1.7R) |

### 5. Rule violations (labelled, not counted as strategy results)
| Trade | What broke the rules | Outcome |
|---|---|---|
| **ZECUSDT SHORT, 10 Nov** | A limit at 1,152 **without** a confirmation close (C2). Also held through **13:30** with the news calendar unverified (N1/N4) | Stopped at 1,170 at 13:45, −1R |
| **ETHUSDT SHORT, 10 Nov 18:40** | Entered **after expiry** (18:30) and with a close of 2,041.5, **below the 2,045 minimum** | About break-even and drifting against. Closed (advised) about 20:35 |
