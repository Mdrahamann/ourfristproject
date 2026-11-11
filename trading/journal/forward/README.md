# Forward paper-trading journal (from 11 Nov 2026)

Read-only, paper only. Rules: `CLAUDE.md` v0.2. UK time.

| File | One row per | Reports |
|---|---|---|
| `scans.csv` | Scan | Contracts screened and analysed; READY NOW count and status; candidates by group; news status |
| `alerts.csv` | READY NOW alert | Confirmation candle; quote and its age; entry range and worst fill; whether it was **still fillable when delivered** |
| `paper_trades.csv` | Paper trade | Fill (marked **actual** or **estimated**), size, costs split out, net $ and net R. The main and countertrend groups are tracked separately |
| `days.csv` | UK day | Valid entries found, alerts fillable on delivery, session stop, net $, and whether the day ended **$20–$30 net** or **≥ $20 net** |

**Headline metrics, computed from these files:**
- % of scans with a valid entry
- % of READY NOW alerts still fillable at delivery
- % of days with $20–$30 net, and % with ≥ $20 net

Zero-trade days count as days.
