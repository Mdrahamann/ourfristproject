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

# ---------------- SMC primitives ----------------
def atr(rows, n=14):
    out, trs = [], []
    for i, r in enumerate(rows):
        tr = r[2] - r[3] if i == 0 else max(r[2] - r[3], abs(r[2] - rows[i-1][4]), abs(r[3] - rows[i-1][4]))
        trs.append(tr); w = trs[-n:]; out.append(sum(w) / len(w))
    return out

def swings(rows, n, sec):
    out = []
    for i in range(n, len(rows) - n):
        h, l = rows[i][2], rows[i][3]
        if all(h > rows[j][2] for j in range(i-n, i)) and all(h >= rows[j][2] for j in range(i+1, i+n+1)):
            out.append(dict(kind='H', price=h, t=rows[i][0], i=i, known_i=i+n, known_at=rows[i+n][0] + sec))
        if all(l < rows[j][3] for j in range(i-n, i)) and all(l <= rows[j][3] for j in range(i+1, i+n+1)):
            out.append(dict(kind='L', price=l, t=rows[i][0], i=i, known_i=i+n, known_at=rows[i+n][0] + sec))
    return out

def analyse(rows, n, sec):
    """Walk bars in time; only swings already knowable before bar i are used at bar i."""
    a = atr(rows); sw = sorted(swings(rows, n, sec), key=lambda s: s['known_i'])
    k, ref_h, ref_l, last_dir = 0, None, None, None
    untaken = []          # confirmed swings not yet traded through
    events = []
    for i, (t, o, h, l, c) in enumerate(rows):
        while k < len(sw) and sw[k]['known_i'] < i:
            s = sw[k]; k += 1; untaken.append(s)
            if s['kind'] == 'H': ref_h = s
            else: ref_l = s
        rng, body = h - l, abs(c - o)
        if rng >= 1.5 * a[i] and body >= 0.6 * rng:
            events.append(dict(ev='displacement', dir='bull' if c > o else 'bear', t=t, i=i, close=c))
        # structure breaks on close
        if ref_h and 'broken' not in ref_h and c > ref_h['price']:
            kind = 'CHoCH' if last_dir == 'bear' else 'BOS'
            events.append(dict(ev=kind, dir='bull', level=ref_h['price'], swing_t=ref_h['t'], swing_known=ref_h['known_at'], t=t, i=i, close=c)); ref_h['broken'] = t; last_dir = 'bull'
        if ref_l and 'broken' not in ref_l and c < ref_l['price']:
            kind = 'CHoCH' if last_dir == 'bull' else 'BOS'
            events.append(dict(ev=kind, dir='bear', level=ref_l['price'], swing_t=ref_l['t'], swing_known=ref_l['known_at'], t=t, i=i, close=c)); ref_l['broken'] = t; last_dir = 'bear'
        # sweeps: wick through an untaken swing, close back inside
        hs = [s for s in untaken if s['kind'] == 'H' and h > s['price']]
        ls = [s for s in untaken if s['kind'] == 'L' and l < s['price']]
        if hs:
            top = max(hs, key=lambda s: s['price'])
            if c < top['price']:
                events.append(dict(ev='sweep', dir='bear', level=top['price'], swing_t=top['t'], swing_known=top['known_at'], t=t, i=i, extreme=h, close=c))
            for s in hs: untaken.remove(s)
        if ls:
            bot = min(ls, key=lambda s: s['price'])
            if c > bot['price']:
                events.append(dict(ev='sweep', dir='bull', level=bot['price'], swing_t=bot['t'], swing_known=bot['known_at'], t=t, i=i, extreme=l, close=c))
            for s in ls: untaken.remove(s)
    # FVGs
    fv = []
    for i in range(2, len(rows)):
        A, C = rows[i-2], rows[i]
        if C[3] > A[2] and C[3] - A[2] >= 0.1 * a[i]:
            fv.append(dict(dir='bull', lo=A[2], hi=C[3], t=rows[i-1][0], i=i, known_at=C[0] + sec))
        if C[2] < A[3] and A[3] - C[2] >= 0.1 * a[i]:
            fv.append(dict(dir='bear', lo=C[2], hi=A[3], t=rows[i-1][0], i=i, known_at=C[0] + sec))
    for f in fv:
        f['touched'] = f['filled'] = None
        for j in range(f['i'] + 1, len(rows)):
            t, o, h, l, c = rows[j]
            if f['dir'] == 'bull':
                if f['touched'] is None and l <= f['hi']: f['touched'] = t
                if l <= f['lo']: f['filled'] = t; break
            else:
                if f['touched'] is None and h >= f['lo']: f['touched'] = t
                if h >= f['hi']: f['filled'] = t; break
    return dict(events=events, fvgs=fv, swings=sw, atr=a, last_dir=last_dir)

def htf_context(rows, n, sec):
    r = analyse(rows, n, sec)
    br = [e for e in r['events'] if e['ev'] in ('BOS', 'CHoCH')]
    last = br[-1] if br else None
    known = [s for s in r['swings'] if s['known_at'] <= rows[-1][0] + sec]
    lastH = max((s for s in known if s['kind'] == 'H'), key=lambda s: s['t'], default=None)
    lastL = max((s for s in known if s['kind'] == 'L'), key=lambda s: s['t'], default=None)
    return dict(bias=r['last_dir'], last_break=last, lastH=lastH, lastL=lastL)

def setup_15m(r15, rows15, r5, rows5, sec15):
    """For each direction, evaluate every sweep in the last 96 bars (24h) and keep the best sequence:
    a live complete sequence (Candidate) > a live partial one (Watch) > the latest invalidated one."""
    ev = r15['events']; res = []
    for d in ('bear', 'bull'):
        seqs = []
        for s in [e for e in ev if e['ev'] == 'sweep' and e['dir'] == d and e['i'] >= len(rows15) - 96]:
            brk = next((e for e in ev if e['ev'] in ('BOS', 'CHoCH') and e['dir'] == d and s['i'] <= e['i'] <= s['i'] + 16), None)
            disp = next((e for e in ev if e['ev'] == 'displacement' and e['dir'] == d and s['i'] <= e['i'] <= (brk['i'] if brk else s['i'] + 16)), None)
            hi_i = (brk['i'] if brk else s['i'] + 16) + 2
            fv = [f for f in r15['fvgs'] if f['dir'] == d and s['i'] <= f['i'] <= hi_i]
            inval = next((rows15[j][0] for j in range(s['i'] + 1, len(rows15))
                          if (d == 'bear' and rows15[j][4] > s['extreme']) or (d == 'bull' and rows15[j][4] < s['extreme'])), None)
            live_fv = [f for f in fv if not f['filled']]
            rank = (0 if inval else (2 if (brk and disp and live_fv) else 1), s['i'])
            seqs.append((rank, dict(dir=d, sweep=s, brk=brk, disp=disp, fvgs=fv, invalidated=inval)))
        if seqs: res.append(max(seqs, key=lambda z: z[0])[1])
    return res

def confirm_5m(r5, d, after_t):
    return next((e for e in r5['events'] if e['ev'] in ('BOS', 'CHoCH') and e['dir'] == d and e['t'] >= after_t), None)

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
    item['atr15'] = a15; item['last15'] = m15[-1][4]
    seqs = []
    for s in setup_15m(r15, m15, r5, m5, 900):
        sw = s['sweep']; fv = [f for f in s['fvgs'] if not f['filled']]
        out = dict(dir=s['dir'], sweep=dict(level=sw['level'], swing_t=ukd(sw['swing_t']), swing_known=ukd(sw['swing_known']), bar=ukd(sw['t']), extreme=sw['extreme']),
                   brk=dict(kind=s['brk']['ev'], level=s['brk']['level'], swing_t=ukd(s['brk']['swing_t']), swing_known=ukd(s['brk']['swing_known']), bar=ukd(s['brk']['t']), close=s['brk']['close']) if s['brk'] else None,
                   age_h=round((NOW - (sw['t'] + 900)) / 3600, 1),
                   disp=ukd(s['disp']['t']) if s['disp'] else None,
                   fvg=None, invalidated=ukd(s['invalidated']) if s['invalidated'] else None)
        if fv:
            dt_ = s['disp']['t'] if s['disp'] else None
            f = next((z for z in fv if z['t'] == dt_), None) or max(fv, key=lambda z: z['hi'] - z['lo'])
            out['fvg'] = dict(lo=f['lo'], hi=f['hi'], mid_t=ukd(f['t']), known_at=ukd(f['known_at']),
                              touched=ukd(f['touched']) if f['touched'] else None)
            buf = max(0.001 * f['hi'], 0.25 * a15)
            stop = sw['extreme'] + buf if s['dir'] == 'bear' else sw['extreme'] - buf
            entry = (f['lo'] + f['hi']) / 2
            # targets: nearest confirmed swings on the far side that are still UNTAKEN (no bar has traded through since)
            def untaken(sws, rows, kind):
                out = []
                for w in sws:
                    if w['kind'] != kind or w['known_at'] > NOW: continue
                    later = rows[w['i'] + 1:]
                    if kind == 'L' and all(r[3] > w['price'] for r in later): out.append(w['price'])
                    if kind == 'H' and all(r[2] < w['price'] for r in later): out.append(w['price'])
                return out
            if s['dir'] == 'bear':
                pool = [v for v in untaken(r15['swings'], m15, 'L') + untaken(swings(h1, 3, 3600), h1, 'L') if v < min(entry, item['last15'])]
                tg = sorted(set(pool), reverse=True)
            else:
                pool = [v for v in untaken(r15['swings'], m15, 'H') + untaken(swings(h1, 3, 3600), h1, 'H') if v > max(entry, item['last15'])]
                tg = sorted(set(pool))
            # T2 [PROPOSED]: cap targets at the near edge of an unfilled opposing 15m FVG
            opp = [z for z in r15['fvgs'] if z['dir'] != s['dir'] and not z['filled'] and z['i'] >= len(m15) - 400]
            if s['dir'] == 'bull':
                caps = [z['lo'] for z in opp if z['lo'] > f['hi']]
                if caps: tg = sorted(set(min(v, min(caps)) for v in tg))
            else:
                caps = [z['hi'] for z in opp if z['hi'] < f['lo']]
                if caps: tg = sorted(set(max(v, max(caps)) for v in tg), reverse=True)
            # v0.2 cost model (CLAUDE.md §10): spread counted once; taker ESTIMATE on entry and exit
            hs = (x.get('spread') or 0) / 200
            c_e = FEE_TAKER + hs + SLIPPAGE; c_tp = FEE_TAKER + hs; c_s = FEE_TAKER + hs + SLIPPAGE
            risk = abs(stop - entry)
            def netR(tp):
                if s['dir'] == 'bull':
                    return round((tp * (1 - c_tp) - entry * (1 + c_e)) / (entry * (1 + c_e) - stop * (1 - c_s)), 2)
                return round((entry * (1 - c_e) - tp * (1 + c_tp)) / (stop * (1 + c_s) - entry * (1 - c_e)), 2)
            out.update(entry_ce=entry, stop=stop, risk_pct=round(100 * risk / entry, 3),
                       cost_R=round(entry * (c_e + c_s) / risk, 3) if risk else None,
                       targets=tg[:2], spread_missing=x.get('spread') is None)
            if tg:
                out['net_R_t1'] = netR(tg[0])
                if len(tg) > 1: out['net_R_t2'] = netR(tg[1])
                out['worst_fill'] = worst_fill(s['dir'], tg[1] if len(tg) > 1 else tg[0], stop, c_e, c_tp, c_s, 2.0)
            a1h = atr(h1)[-1]
            near_edge = f['lo'] if s['dir'] == 'bear' else f['hi']
            out['dist_pct'] = round(100 * (near_edge / item['last15'] - 1), 2)
            out['dist_atr1h'] = round(abs(near_edge - item['last15']) / a1h, 1)
            if f['touched']:
                c5 = confirm_5m(r5, s['dir'], f['touched'])
                out['confirm5m'] = dict(kind=c5['ev'], level=c5['level'], bar=ukd(c5['t']), close=c5['close']) if c5 else None
        complete = bool(s['brk'] and s['disp'] and out['fvg'] and not s['invalidated'])
        opp = next((e for e in r15['events'] if e['ev'] in ('BOS', 'CHoCH') and e['dir'] != s['dir'] and s['brk'] and e['t'] > s['brk']['t']), None)
        out['conflict'] = f"opposite 15m {opp['ev']} {opp['dir']} @ {opp['level']:.6g} on {ukd(opp['t'])}" if opp else None
        out['status'] = ('Invalidated' if s['invalidated'] else
                         ('Watch (conflict)' if opp else 'Watch (zone distant)' if out.get('dist_atr1h', 0) > 3 else 'Candidate') if complete else 'Watch')
        bias1h = item['ctx1h']['bias']
        out['group'] = 'main (1H aligned)' if bias1h == s['dir'] else 'countertrend (half risk, separate paper group)'
        out['missing'] = [n for n, v in (('BOS/CHoCH', s['brk']), ('displacement', s['disp']), ('unfilled FVG', out['fvg'])) if not v]
        seqs.append(out)
    item['seqs'] = seqs; item['status'] = 'ok'
    # keep a little raw context for the report
    item['recent15'] = [e | {'t_uk': ukd(e['t'])} for e in r15['events'][-12:]]
    report['symbols'].append(item)

json.dump(report, open(f'{OUT}/scan.json', 'w'), indent=1, default=str)
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
