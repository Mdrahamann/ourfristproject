# Graph Report - ourfristproject  (2026-11-12)

## Corpus Check
- 53 files · ~88,917 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: .csv 4, (none) 2)

## Summary
- 977 nodes · 2188 edges · 36 communities (34 shown, 2 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 38 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `16747652`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- trader-scanner/scan.py
- entry.py
- timemachine.py
- news.py
- json
- ticket.py
- exit.py
- size.py
- datetime
- facts.py
- ptr.py
- smc_scan.py
- report.py
- Trading analyst rules: v0.2 (11 Nov 2026). Decisions locked; thresholds are still PROVISIONAL
- plans.py
- bt.py
- asof_harness.py
- stock_scan.py
- os
- trader-scanner
- trader-alerts
- trader-budget
- trader-pelosi
- replay_day.py
- trader-broker
- trader-risk
- Audit: why every `scan now` on Wed 11 Nov 2026 showed no entry (written 18:05 UK)
- SMC/ICT read-only scan: Binance USDT perpetuals
- trader-entry
- trader-exit
- trader-timemachine
- Audit: instructions, rules and data feeds (Wed 11 Nov 2026, 02:55 UK)
- Examples from your journal (8–11 Nov 2026)
- Backtest v0.2: first run (Wed 11 Nov 2026, 03:10 UK)
- Paper scanner: run it yourself
- forward/README.md

## God Nodes (most connected - your core abstractions)
1. `cmd_orb()` - 23 edges
2. `Trading analyst rules: v0.2 (11 Nov 2026). Decisions locked; thresholds are still PROVISIONAL` - 22 edges
3. `evaluate()` - 20 edges
4. `build_plan()` - 20 edges
5. `check()` - 18 edges
6. `main()` - 17 edges
7. `ScanError` - 17 edges
8. `time_machine()` - 17 edges
9. `watch_loop()` - 16 edges
10. `cmd_watch()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `journal()` --indirect_call--> `f()`  [INFERRED]
  trading/scanner/scan.py → .claude/skills/trader-alerts/alerts.py
- `What it reads and writes` --references--> `sec_user_agent()`  [INFERRED]
  .claude/skills/trader-news/SKILL.md → .claude/skills/trader-news/news.py
- `watchlist()` --indirect_call--> `portfolio()`  [INFERRED]
  .claude/skills/trader-pelosi/ptr.py → trading/backtest/bt.py
- `Addendum, 20:05 UK: did the 1H-plan change alter the original scalp?` --references--> `setup_15m()`  [INFERRED]
  trading/audit/2026-11-11-no-entries-audit.md → trading/scanner/scalp_original.py
- `trader-analyst` --references--> `sec_user_agent()`  [INFERRED]
  .claude/skills/trader-analyst/SKILL.md → .claude/skills/trader-news/news.py

## Import Cycles
- None detected.

## Communities (36 total, 2 thin omitted)

### Community 0 - "trader-scanner/scan.py"
Cohesion: 0.05
Nodes (52): _absorb(), build_universe(), chart_path(), classify(), clock_label(), cmd_daily(), cmd_orb(), confirm() (+44 more)

### Community 1 - "entry.py"
Cohesion: 0.06
Nodes (48): ampm(), bar_line(), chart_path(), chart_range(), cmd_check(), cmd_watch(), emit(), on_trigger() (+40 more)

### Community 2 - "timemachine.py"
Cohesion: 0.05
Nodes (43): build_pool(), cents_away(), chart_result(), chart_url(), clock12(), clock24(), cmd_chart(), cmd_run() (+35 more)

### Community 3 - "news.py"
Cohesion: 0.05
Nodes (42): Example: the reel's stock, Safety, Steps, The rules, trader-analyst, What it never does, What it reads and writes, cik_map() (+34 more)

### Community 4 - "json"
Cohesion: 0.08
Nodes (41): active(), AlertError, cmd_add(), cmd_check(), cmd_clock(), cmd_list(), cmd_quote(), cmd_reset() (+33 more)

### Community 5 - "ticket.py"
Cohesion: 0.09
Nodes (44): amount_numbers(), apply_fill(), _clock(), cmd_approve(), cmd_decline(), cmd_fill(), cmd_flatten(), cmd_log() (+36 more)

### Community 6 - "exit.py"
Cohesion: 0.08
Nodes (39): ampm(), atr_of(), build_plan(), cents(), cmd_plan(), cmd_show(), compute(), D() (+31 more)

### Community 7 - "size.py"
Cohesion: 0.07
Nodes (35): allocate(), bracket_order(), eastern_offset(), eastern_to_utc(), _f(), fresh_price(), load_config(), load_prices() (+27 more)

### Community 8 - "datetime"
Cohesion: 0.08
Nodes (29): account(), business_days(), _cent(), check(), day_trades(), eastern_offset(), eastern_to_utc(), _f() (+21 more)

### Community 9 - "facts.py"
Cohesion: 0.08
Nodes (24): analyse(), changes(), clean_title(), _date(), exhibit_name(), facts_for(), FactsError, Fetcher (+16 more)

### Community 10 - "ptr.py"
Cohesion: 0.10
Nodes (23): _amount(), describe(), download(), _fetch_and_read(), _finish(), iso(), load_index(), load_state() (+15 more)

### Community 11 - "smc_scan.py"
Cohesion: 0.13
Nodes (14): Addendum, 20:05 UK: did the 1H-plan change alter the original scalp?, summary_of(), analyse(), atr(), confirm_5m(), htf_context(), scalp_sequences(), setup_15m() (+6 more)

### Community 12 - "report.py"
Cohesion: 0.20
Nodes (21): card(), do_now(), entry_range(), from_1h(), from_scalp(), g(), hm(), key() (+13 more)

### Community 13 - "Trading analyst rules: v0.2 (11 Nov 2026). Decisions locked; thresholds are still PROVISIONAL"
Cohesion: 0.08
Nodes (23): 0. Data rules, 10. Entry range and worst acceptable fill, 11. Stops, 12. Targets, 13. Expiry and invalidation, 14. Time and news blackouts, 15. Risk and session limits, 16. READY NOW gate (all must pass) (+15 more)

### Community 14 - "plans.py"
Cohesion: 0.16
Nodes (11): wfill(), best_and_reason(), find_setups(), _fmt(), now_ts(), render(), ukd(), analyse() (+3 more)

### Community 15 - "bt.py"
Cohesion: 0.24
Nodes (13): bias_at(), blackout(), candles(), funding_crossings(), get_json(), main(), metrics(), nydt() (+5 more)

### Community 17 - "stock_scan.py"
Cohesion: 0.20
Nodes (7): hm(), label(), tp1_when_set(), tracked(), ts(), get_json(), yahoo()

### Community 18 - "os"
Cohesion: 0.27
Nodes (6): norm(), parse(), main(), next_open_uk(), run(), us_open()

### Community 19 - "trader-scanner"
Cohesion: 0.17
Nodes (11): Data and limits, Example: the reel, Rules, Safety, Steps, The daily scan (before the open), The opening-range breakout scan (during the session), The universe (+3 more)

### Community 20 - "trader-alerts"
Cohesion: 0.18
Nodes (10): Example: the reel, Quotes, Rule types, Rules, Safety, Steps, The NYSE clock, trader-alerts (+2 more)

### Community 21 - "trader-budget"
Cohesion: 0.18
Nodes (10): Example: the reel, Rules, Safety, Step 1: set the rules once, Step 2: size the trade, Step 3: show the user, trader-budget, Weights mode (kept from v1) (+2 more)

### Community 22 - "trader-pelosi"
Cohesion: 0.18
Nodes (10): Example: a real alert, Safety, Step 1: what has been filed, Step 2: watch for new ones, Step 3: read a report, The rules, The Senate: the manual route, trader-pelosi (+2 more)

### Community 23 - "replay_day.py"
Cohesion: 0.33
Nodes (5): get_json(), main(), replay(), resample(), yahoo()

### Community 24 - "trader-broker"
Cohesion: 0.20
Nodes (9): Example: the reel, Safety, Setup A: Alpaca (official MCP server, Claude Desktop), Setup B: Interactive Brokers (connector in Claude's directory), Steps: the entry, Steps: while it is open, and out by the close, trader-broker, What it never does (+1 more)

### Community 25 - "trader-risk"
Cohesion: 0.20
Nodes (9): Entries and exits, Example: the reel, Rules, Safety, Steps, The checks, trader-risk, What it never does (+1 more)

### Community 26 - "Audit: why every `scan now` on Wed 11 Nov 2026 showed no entry (written 18:05 UK)"
Cohesion: 0.20
Nodes (9): 1. Scan reconstruction (from saved logs: `scan.json`, `scan.md`, `stock_scan.json`, `scans.csv`), 2. Movers, 3–4. Four rows per scan and where candidates were lost, 5. Verified vs couldn't verify, Audit: why every `scan now` on Wed 11 Nov 2026 showed no entry (written 18:05 UK), CRYPTO: four rows per scan (closest candidate in the main group, as saved at scan time), Headline, Proposed fixes (not applied; need approval) (+1 more)

### Community 27 - "SMC/ICT read-only scan: Binance USDT perpetuals"
Cohesion: 0.20
Nodes (9): Candidates (up to 5), Data sources and freshness, Inferred, Observed, Rescan: Tue 10 Nov 2026 21:35:56 UK, Result, Rules (closed candles only), Shortlist and liquidity filter (+1 more)

### Community 28 - "trader-entry"
Cohesion: 0.22
Nodes (8): Example: the reel, Rules, Safety, Steps, The rule, trader-entry, What it never does, What it reads and writes

### Community 29 - "trader-exit"
Cohesion: 0.22
Nodes (8): Example: the reel, Rules, Safety, Steps, Stops and targets, trader-exit, What it never does, What it reads and writes

### Community 30 - "trader-timemachine"
Cohesion: 0.22
Nodes (8): Example: the reel, How it works, Rules, Safety, Steps, trader-timemachine, What it never does, What it reads and writes

### Community 31 - "Audit: instructions, rules and data feeds (Wed 11 Nov 2026, 02:55 UK)"
Cohesion: 0.25
Nodes (7): 1. What exists today, 2. Can each rule be tested?, 3. Data sources: tested 11 Nov, 02:45–02:56 UK, from this cloud session, 4. Can the current feed support READY NOW? **Not reliably.**, 5. What a backtest needs that's missing here, 6. Decisions I need from you, Audit: instructions, rules and data feeds (Wed 11 Nov 2026, 02:55 UK)

### Community 32 - "Examples from your journal (8–11 Nov 2026)"
Cohesion: 0.25
Nodes (7): 1. Winner, but the plan's entry range was too wide: ZECUSDT SHORT, Mon 9 Nov, 2. Loser (valid only if entered before 19:15): AVAXUSDT LONG, Mon 9 Nov, 3. Near-miss, correctly skipped: ETHUSDT SHORT, Tue 10 Nov, 4. Entry already passed (MISSED / no chase): NEARUSDT LONG, Wed 11 Nov, 5. Rule violations (labelled, not counted as strategy results), Chart review template, Examples from your journal (8–11 Nov 2026)

### Community 33 - "Backtest v0.2: first run (Wed 11 Nov 2026, 03:10 UK)"
Cohesion: 0.29
Nodes (6): Backtest v0.2: first run (Wed 11 Nov 2026, 03:10 UK), ⚠️ Data limits (these results are ESTIMATES), Next development steps (development period only; the test period stays untouched until frozen again), Results, The $20–$30 per day goal under your risk rules, Why the rules produced almost no trades (diagnosis, development + test data)

### Community 34 - "Paper scanner: run it yourself"
Cohesion: 0.50
Nodes (3): Every time (from the repository folder, the one that contains CLAUDE.md), First time on a Mac, Paper scanner: run it yourself

## Knowledge Gaps
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Addendum, 20:05 UK: did the 1H-plan change alter the original scalp?` connect `smc_scan.py` to `Audit: why every `scan now` on Wed 11 Nov 2026 showed no entry (written 18:05 UK)`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Should `trader-scanner/scan.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05249569707401033 - nodes in this community are weakly interconnected._
- **Should `entry.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06049213943950786 - nodes in this community are weakly interconnected._
- **Should `timemachine.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05359937402190924 - nodes in this community are weakly interconnected._
- **Should `news.py` be split into smaller, more focused modules?**
  _Cohesion score 0.051587301587301584 - nodes in this community are weakly interconnected._
- **Should `json` be split into smaller, more focused modules?**
  _Cohesion score 0.07773664727657324 - nodes in this community are weakly interconnected._
- **Should `ticket.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09095716552088842 - nodes in this community are weakly interconnected._