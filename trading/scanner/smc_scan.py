#!/usr/bin/env python3
"""Read-only SMC/ICT scanner for Binance USDT-M perpetuals. Alert-only: places no orders.

Data:
  * Shortlist + spread/funding/OI/24h volume: CoinGecko /derivatives (Binance Futures tickers).
  * Candles: Yahoo Finance chart API (spot, USD-quoted aggregate) as a PROXY for Binance perp candles,
    because fapi.binance.com returns HTTP 451 from this environment.
Rules (all on CLOSED candles only):
  * Swing high/low: fractal, N bars each side (strict on the left, >= on the right).
    A swing is only usable from the close of bar i+N ("knowable_at").
  * Sweep: a bar trades beyond a confirmed, untaken swing level but CLOSES back inside it.
  * BOS/CHoCH: a bar CLOSES beyond the latest confirmed swing in the opposite direction.
    CHoCH if it flips the prior break direction, BOS if it continues it.
  * Displacement: range >= 1.5 x ATR(14) and body >= 60% of range.
  * FVG: 3-candle imbalance, size >= 0.1 x ATR; tracked until touched / fully filled.
  * Candidate (15m) = sweep -> displacement + BOS/CHoCH (within 16 bars) -> unfilled FVG in the leg.
    Anything less is Watch. 5m confirmation = a 5m BOS/CHoCH in the trade direction after the zone is touched.
"""
import json, os, sys, time, urllib.request, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smc_core import worst_fill  # noqa: E402
from plans import find_setups  # noqa: E402  (separate 1H plan only)
from scalp_status import label, tracked  # noqa: E402
STATE = os.path.join(os.environ.get('SCAN_STATE_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'journal', 'forward'), 'watch_state_crypto.json')
from report import render  # noqa: E402
PLAN_SETUPS = []
from zoneinfo import ZoneInfo

UK = ZoneInfo('Europe/London'); UTC = dt.timezone.utc
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
OPEN = urllib.request.build_opener(urllib.request.ProxyHandler({'https': os.environ['HTTPS_PROXY']}))

# ---- assumptions (stated in the report) ----
FEE_TAKER = 0.0005      # Binance USDT-M VIP0 taker, per side, no BNB discount (assumption)
SLIPPAGE = 0.0002       # per side, assumption for liquid contracts
LIQ = dict(min_oi=50e6, max_spread_pct=0.03, max_abs_funding_pct=0.05)
NONCRYPTO = set(('XAU XAG PAXG XAUT CL BZ NG HG USDC FDUSD SOXL SOXS SNDK KORU SKHYNIX SKHY MU SPCX QQQ SNXX NVDA '
                 'INTC UVXY SQQQ TQQQ SKDD APP QCOM AAOI MVLL NBIS ANTHROPIC ZHIPU TSLA AAPL META AMZN GOOGL MSFT COIN '
                 'MSTR HOOD PLTR AMD SPY CRCL EWY EWJ TSM ORCL AVGO ARM BABA SMCI NFLX LLY RDDT JPM V UBER UNH SHOP DIS '
                 'PYPL CRWV IBIT SAMSUNG DRAM MUU').split())
YMAP = {'HYPE': 'HYPE32196-USD', 'PEPE': 'PEPE24478-USD', 'UNI': 'UNI7083-USD', 'SUI': 'SUI20947-USD',
        'TAO': 'TAO22974-USD'}

def get_json(url):
    return json.loads(OPEN.open(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=40).read())

def uk(ts): return dt.datetime.fromtimestamp(ts, UK).strftime('%a %H:%M')
def ukd(ts): return dt.datetime.fromtimestamp(ts, UK).strftime('%d %b %H:%M')

NOW = time.time()

# ---------------- shortlist ----------------
cg = get_json('https://api.coingecko.com/api/v3/derivatives?include_tickers=unexpired')
allp = [x for x in cg if x.get('market') == 'Binance (Futures)' and x.get('contract_type') == 'perpetual'
        and str(x.get('symbol', '')).endswith('USDT') and float(x.get('price') or 0) > 0]
cg_asof = max(x['last_traded_at'] for x in allp)
crypto = [x for x in allp if x['symbol'][:-4] not in NONCRYPTO]
def liq_reason(x):
    r = []
    if (x.get('open_interest') or 0) < LIQ['min_oi']: r.append(f"OI ${(x.get('open_interest') or 0)/1e6:.0f}M < $50M")
    if x.get('spread') is None: r.append('spread missing')
    elif x['spread'] > LIQ['max_spread_pct']: r.append(f"spread {x['spread']}% > 0.03%")
    if abs(x.get('funding_rate') or 0) > LIQ['max_abs_funding_pct']: r.append(f"funding {x['funding_rate']:+.3f}%")
    return r
top_vol = sorted(crypto, key=lambda x: -x['volume_24h'])[:20]
gainers = sorted([x for x in crypto if not liq_reason(x)], key=lambda x: -x['price_percentage_change_24h'])[:5]
short, rejected = [], []
for x in top_vol:
    (rejected if liq_reason(x) else short).append(x)
losers = sorted([x for x in crypto if not liq_reason(x)], key=lambda x: x['price_percentage_change_24h'])[:5]
for x in gainers + losers:                      # L2: top-20 volume + top-5 gainers + top-5 losers, cap 30
    if x not in short and len(short) < 30: short.append(x)
for x in sorted([x for x in crypto if not liq_reason(x)], key=lambda x: -x['volume_24h']):
    if x not in short and len(short) < 20: short.append(x)   # fill to 20 with remaining liquid contracts when available

# ---------------- candles ----------------
def yahoo(sym, interval, rng, sec):
    d = get_json(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={interval}&range={rng}')['chart']['result'][0]
    q = d['indicators']['quote'][0]
    rows = [(t, o, h, l, c) for t, o, h, l, c in zip(d['timestamp'], q['open'], q['high'], q['low'], q['close'])
            if None not in (o, h, l, c) and t % sec == 0 and t + sec <= NOW]   # closed, aligned bars only
    return rows

def resample(rows, src_sec, dst_sec):
    out, cur, key = [], [], None
    for r in rows:
        k = r[0] - r[0] % dst_sec
        if k != key:
            if cur and len(cur) == dst_sec // src_sec: out.append((key, cur[0][1], max(x[2] for x in cur), min(x[3] for x in cur), cur[-1][4]))
            cur, key = [], k
        cur.append(r)
    if cur and len(cur) == dst_sec // src_sec and key + dst_sec <= NOW:
        out.append((key, cur[0][1], max(x[2] for x in cur), min(x[3] for x in cur), cur[-1][4]))
    return out

# ---------------- SMC primitives + original scalp (moved verbatim to scalp_original.py) ----------------
from scalp_original import atr, swings, analyse, htf_context, setup_15m, confirm_5m, scalp_sequences  # noqa: E402

# ---------------- run ----------------
report = dict(scan_time_uk=dt.datetime.fromtimestamp(NOW, UK).strftime('%a %d %b %Y %H:%M:%S %Z'),
              coingecko_asof_uk=ukd(cg_asof), coingecko_lag_min=round((NOW - cg_asof) / 60, 1),
              n_binance_usdt_perps=len(allp), n_crypto=len(crypto),
              rejected_top_volume=[dict(sym=x['symbol'], why=liq_reason(x)) for x in rejected], symbols=[])
for x in short:
    base = x['symbol'][:-4]; scale = 1.0
    if base.startswith('1000'): base, scale = base[4:], 1000.0
    ysym = YMAP.get(base, f'{base}-USD')
    item = dict(sym=x['symbol'], yahoo=ysym, perp_price=float(x['price']), index=x.get('index'), chg24=x['price_percentage_change_24h'],
                vol24=x['volume_24h'], oi=x.get('open_interest'), funding=x.get('funding_rate'), spread=x.get('spread'))
    try:
        h1 = [(t, o*scale, h*scale, l*scale, c*scale) for t, o, h, l, c in yahoo(ysym, '1h', '60d', 3600)]
        m15 = [(t, o*scale, h*scale, l*scale, c*scale) for t, o, h, l, c in yahoo(ysym, '15m', '5d', 900)]
        m5 = [(t, o*scale, h*scale, l*scale, c*scale) for t, o, h, l, c in yahoo(ysym, '5m', '2d', 300)]
    except Exception as e:
        item['status'] = f'UNAVAILABLE: candle fetch failed ({str(e)[:60]})'; report['symbols'].append(item); continue
    h4 = resample(h1, 3600, 14400)
    stale = []
    for name, rows, sec in (('4H', h4, 14400), ('1H', h1, 3600), ('15m', m15, 900), ('5m', m5, 300)):
        if len(rows) < 30: stale.append(f'{name}: only {len(rows)} bars')
        elif NOW - (rows[-1][0] + sec) > 2 * sec: stale.append(f'{name}: last close {ukd(rows[-1][0] + sec)}')
    item['last_closed'] = {k: ukd(rows[-1][0] + sec) for k, rows, sec in (('4H', h4, 14400), ('1H', h1, 3600), ('15m', m15, 900), ('5m', m5, 300)) if rows}
    item['spot_last'] = m5[-1][4] if m5 else None
    item['proxy_gap_pct'] = round(100 * (item['spot_last'] / item['index'] - 1), 3) if (m5 and item['index']) else None
    if stale:
        item['status'] = 'UNAVAILABLE: stale/missing data: ' + '; '.join(stale); report['symbols'].append(item); continue
    item['ctx4h'] = htf_context(h4, 2, 14400); item['ctx1h'] = htf_context(h1, 3, 3600)
    r15 = analyse(m15, 2, 900); r5 = analyse(m5, 2, 300); a15 = r15['atr'][-1]
    hs_ = (x.get('spread') or 0.02) / 200
    costs_ = (FEE_TAKER + hs_ + SLIPPAGE, FEE_TAKER + hs_, FEE_TAKER + hs_ + SLIPPAGE)
    for rr in find_setups('B', h1, m15, item['ctx4h']['bias'], m15[-1][4], costs_, NOW):   # separate 1H plan
        rr['sym'] = x['symbol']; rr['costs'] = costs_; PLAN_SETUPS.append(rr)
    item['atr15'] = a15; item['last15'] = m15[-1][4]
    seqs = scalp_sequences(m15, m5, h1, item['ctx1h']['bias'], x.get('spread'), NOW, r15, r5,
                           keep=tracked(STATE, x['symbol'], NOW))   # original scalp, unchanged (+ plans already shown)
    for s_ in seqs: label(s_, m5, m15, h1, r15['swings'], NOW)                                 # status + conditional plan
    item['seqs'] = seqs; item['status'] = 'ok'
    # keep a little raw context for the report
    item['recent15'] = [e | {'t_uk': ukd(e['t'])} for e in r15['events'][-12:]]
    report['symbols'].append(item)

okk = [it for it in report['symbols'] if it.get('status') == 'ok']
breadth = dict(n=len(okk), bear=sum(it['ctx1h']['bias'] == 'bear' for it in okk), bull=sum(it['ctx1h']['bias'] == 'bull' for it in okk))
# coverage, reported (not filtered): perps the snapshot shows with price 0.00 are never screened (original gate)
noprice = [x for x in cg if x.get('market') == 'Binance (Futures)' and x.get('contract_type') == 'perpetual'
           and str(x.get('symbol', '')).endswith('USDT') and not float(x.get('price') or 0) > 0]
noprice_liquid = sorted([x for x in noprice if x['symbol'][:-4] not in NONCRYPTO and not liq_reason(x)], key=lambda x: -(x.get('volume_24h') or 0))
unavail = [f"{it['sym']} ({it['status'].split(':')[0].lower()}: {it['status'].split(':', 2)[-1].strip()[:40]})" for it in report['symbols'] if it.get('status') != 'ok']
DATA = [f"**Data:** {report['n_crypto']} crypto USDT perps screened (CoinGecko snapshot {report['coingecko_lag_min']} min old) → "
        f"{len(short)} shortlisted → {len(okk)} analysed. Candles: Yahoo spot (proxy for the Binance contract), closed bars only. "
        "All levels APPROXIMATE, paper watchlist only.",
        "- **READY NOW unavailable — live contract data missing** (Binance API HTTP 451: no exact-contract closed candles or bid/ask).",
        f"- Failed liquidity (top-20 volume): " + (', '.join(f"{r['sym']} ({'; '.join(r['why'])})" for r in report['rejected_top_volume']) or 'none')]
if unavail: DATA.append('- **Not evaluated (no data):** ' + ', '.join(unavail))
if noprice_liquid:
    DATA.append(f"- **Not screened:** {len(noprice)} perps show price 0.00 in the snapshot (rounding), so the scanner skips them; "
                f"{len(noprice_liquid)} of them would pass liquidity: " + ', '.join(f"{x['symbol']} (${(x.get('volume_24h') or 0) / 1e6:.0f}M vol)" for x in noprice_liquid[:5])
                + '. Fix pending your approval.')
DATA.append('- News blackouts (N1–N6) are not coded in the scanner; the calendar is unverified, so check news times yourself.')
FOUR_ROWS = render(report['symbols'], PLAN_SETUPS, breadth, DATA, now=NOW,
                   state_path=STATE)
report['plans'] = PLAN_SETUPS; report['four_rows_md'] = FOUR_ROWS
report['not_screened_price0'] = [x['symbol'] for x in noprice]
open(f'{OUT}/scan.md', 'w').write(f"# Scan {report['scan_time_uk']}\n\n" + FOUR_ROWS + "\n")
json.dump(report, open(f'{OUT}/scan.json', 'w'), indent=1, default=str)
print(FOUR_ROWS)
print()
print('scan', report['scan_time_uk'], '| CoinGecko as of', report['coingecko_asof_uk'], f"({report['coingecko_lag_min']} min old)")
print('rejected (top-20 volume, failed liquidity):', ', '.join(f"{r['sym']} [{'; '.join(r['why'])}]" for r in report['rejected_top_volume']))
for it in report['symbols']:
    if it['status'] != 'ok':
        print(f"\n{it['sym']}: {it['status']}"); continue
    c4, c1 = it['ctx4h'], it['ctx1h']
    def b(c):
        lb = c['last_break']; return f"{c['bias']} (last {lb['ev']} {lb['dir']} @ {lb['level']:.6g} on {ukd(lb['t'])})" if lb else str(c['bias'])
    print(f"\n{it['sym']} BinanceIndex {it['index']:.6g} YahooSpot {it['spot_last']:.6g} proxyGap {it['proxy_gap_pct']}% 24h {it['chg24']:+.2f}% spread {it['spread']}% fund {it['funding']:+.4f}% | last closed {it['last_closed']}")
    print(f"  4H {b(c4)} | 1H {b(c1)} | 1H last swing H {c1['lastH']['price']:.6g} ({ukd(c1['lastH']['t'])}, known {ukd(c1['lastH']['known_at'])}) L {c1['lastL']['price']:.6g} ({ukd(c1['lastL']['t'])}, known {ukd(c1['lastL']['known_at'])})")
    for s in it['seqs']:
        print(f"  15m {s['dir']}: {s['status']} age {s['age_h']}h dist {s.get('dist_pct')}%/{s.get('dist_atr1h')}xATR1H | sweep {s['sweep']['level']:.6g} (swing {s['sweep']['swing_t']}) on {s['sweep']['bar']} ext {s['sweep']['extreme']:.6g}"
              f" | brk {s['brk']} | disp {s['disp']} | FVG {s['fvg']} | inval {s['invalidated']} | missing {s['missing']} | conflict {s.get('conflict')}")
        if s.get('entry_ce'):
            print(f"     CE {s['entry_ce']:.6g} stop {s['stop']:.6g} risk {s['risk_pct']}% costR {s['cost_R']} targets {[round(v, 6) for v in s['targets']]} netR {s.get('net_R_t1')}/{s.get('net_R_t2')} confirm5m {s.get('confirm5m')}")
