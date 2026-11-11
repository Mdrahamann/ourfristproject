#!/usr/bin/env python3
"""Causal paper replay of one UK day for Plan A (15m/5m) and Plan B (1H/15m), both directions.
Read-only, no orders. Uses ONLY information knowable at each candle close. Live scan rules are NOT changed:
variants are run separately for comparison.
Data: Yahoo spot / underlying-stock candles (proxy), CoinGecko snapshot for spread. Fills are ESTIMATES."""
import bisect, datetime as dt, json, os, sys, time, urllib.request
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scanner'))
from smc_core import analyse, worst_fill  # noqa: E402

UK = ZoneInfo('Europe/London')
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
DAY = dt.datetime(2026, 11, 11, tzinfo=UK)
DAY0 = DAY.timestamp()
NOW = time.time()
SCANS = {'03:25': '03:25:17', '05:03': '05:03:02', '14:37': '14:37:04', '15:19': '15:19:50', '16:27': '16:27:09', '17:27': '17:27:52'}
SCAN_T = {k: dt.datetime.strptime(f'2026-11-11 {v}', '%Y-%m-%d %H:%M:%S').replace(tzinfo=UK).timestamp() for k, v in SCANS.items()}
OPEN = urllib.request.build_opener(urllib.request.ProxyHandler({'https': os.environ['HTTPS_PROXY']}))
FEE, SLIP = 0.0005, 0.0002
P = {'A': dict(s='15m', s_sec=900, s_n=2, c='5m', c_sec=300, c_n=2, window=16, expiry=16, ew=300, ctx='1H'),
     'B': dict(s='1h', s_sec=3600, s_n=3, c='15m', c_sec=900, c_n=2, window=16, expiry=16, ew=900, ctx='4H')}


def get_json(url):
    return json.loads(OPEN.open(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=40).read())


def yahoo(sym, iv, rng, sec, scale=1.0, aligned=True):
    d = get_json(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={iv}&range={rng}')['chart']['result'][0]
    q = d['indicators']['quote'][0]
    return [(t, o * scale, h * scale, l * scale, c * scale) for t, o, h, l, c in zip(d['timestamp'], q['open'], q['high'], q['low'], q['close'])
            if None not in (o, h, l, c) and t + sec <= NOW and (t % sec == 0 or not aligned)]


def resample(rows, src, dst):
    out, cur, key = [], [], None
    for r in rows:
        k = r[0] - r[0] % dst
        if k != key:
            if cur and len(cur) == dst // src: out.append((key, cur[0][1], max(x[2] for x in cur), min(x[3] for x in cur), cur[-1][4]))
            cur, key = [], k
        cur.append(r)
    return out


def u(t):
    return dt.datetime.fromtimestamp(t, UK).strftime('%H:%M') if t else None


def replay(plan, S, C, ctx_rows, ctx_n, ctx_sec, costs, variant):
    p = P[plan]
    c_e, c_tp, c_s = costs
    rS = analyse(S, p['s_n'], p['s_sec'], max_age=400, fvg_state=False)
    rC = analyse(C, p['c_n'], p['c_sec'], max_age=400, fvg_state=False)
    rX = analyse(ctx_rows, ctx_n, ctx_sec, max_age=400, fvg_state=False)
    ctx_br = sorted((e['t'] + ctx_sec, e['dir']) for e in rX['events'] if e['ev'] in ('BOS', 'CHoCH'))
    ctx_t = [x[0] for x in ctx_br]
    brks = [e for e in rS['events'] if e['ev'] in ('BOS', 'CHoCH')]
    swC = {k: sorted((w['known_at'], w['price']) for w in rC['swings'] if w['kind'] == k) for k in 'HL'}
    swCk = {k: [x[0] for x in v] for k, v in swC.items()}
    tC = [r[0] for r in C]
    endS = {r[0] + p['s_sec']: r for r in S}
    out, seen = [], set()
    min_r = 1.5 if 'rr1.5' in variant else 2.0
    for s in [e for e in rS['events'] if e['ev'] == 'sweep' and e['t'] + p['s_sec'] >= DAY0 - p['window'] * p['s_sec']]:
        d = s['dir']; bull = d == 'bull'
        rec = dict(plan=plan, dir=d, sweep_t=s['t'], sweep_level=s['level'], extreme=s['extreme'])
        brk = next((e for e in brks if e['dir'] == d and s['i'] <= e['i'] <= s['i'] + p['window']), None)
        hi_i = brk['i'] if brk else min(len(S) - 1, s['i'] + p['window'])
        disp = next((e for e in rS['events'] if e['ev'] == 'displacement' and e['dir'] == d and s['i'] <= e['i'] <= hi_i), None)
        fv = [f for f in rS['fvgs'] if f['dir'] == d and s['i'] <= f['i'] <= hi_i + 2]
        # first close beyond the sweep extreme (structure invalidation), causal time = bar close
        inval = next((S[j][0] + p['s_sec'] for j in range(s['i'] + 1, len(S))
                      if (bull and S[j][4] < s['extreme']) or (not bull and S[j][4] > s['extreme'])), None)
        if 'no_disp' in variant and brk and fv and not disp:
            disp = dict(t=None)
        if not (brk and disp and fv):
            if s['t'] + p['s_sec'] < DAY0: continue
            miss = [m for m, v in (('structure break', brk), ('strong candle', disp), ('price gap', fv)) if not v]
            rec.update(block='missing setup: ' + '+'.join(miss), block_t=s['t'] + p['s_sec'], group='n/a'); out.append(rec); continue
        f = next((z for z in fv if z['t'] == disp['t']), None) or max(fv, key=lambda z: z['hi'] - z['lo'])
        if (d, f['i']) in seen: continue
        seen.add((d, f['i']))
        ci = max(brk['i'], f['i'])
        Tc = S[ci][0] + p['s_sec']
        if Tc < DAY0 or Tc > NOW: continue
        ix = bisect.bisect_right(ctx_t, Tc) - 1
        bias = ctx_br[ix][1] if ix >= 0 else None
        group = 'main' if bias == d else 'countertrend'
        rec.update(Tc=Tc, zone=(f['lo'], f['hi']), brk_level=brk['level'], brk_t=brk['t'] + p['s_sec'], brk_kind=brk['ev'],
                   disp_t=disp.get('t'), group=group, bias=bias)
        if inval and inval <= Tc:
            rec.update(block='invalidated before setup completed', block_t=inval); out.append(rec); continue
        if any(e['dir'] != d and brk['i'] < e['i'] <= ci for e in brks):
            rec.update(block='conflict before setup completed', block_t=Tc); out.append(rec); continue
        endsS = [r[0] + p['s_sec'] for r in S]

        def targets_at(T):
            """Targets using only info knowable at time T: swings known by T and untaken by bars closed by T;
            capped by opposing FVGs known by T and unfilled by T (CLAUDE.md T1/T2)."""
            last_i = bisect.bisect_right(endsS, T) - 1
            kt = 'H' if bull else 'L'
            cand = []
            for w in rS['swings']:
                if w['kind'] != kt or w['known_at'] > T or w['i'] < last_i - 400: continue
                later = S[w['i'] + 1: last_i + 1]
                if bull and w['price'] > f['hi'] and all(r[2] < w['price'] for r in later): cand.append(w['price'])
                if not bull and w['price'] < f['lo'] and all(r[3] > w['price'] for r in later): cand.append(w['price'])
            opp = [z for z in rS['fvgs'] if z['dir'] != d and z['known_at'] <= T and last_i - 400 <= z['i'] <= last_i and not any(
                (z['dir'] == 'bear' and r[2] >= z['hi']) or (z['dir'] == 'bull' and r[3] <= z['lo']) for r in S[z['i'] + 1: last_i + 1])]
            if bull:
                caps = [z['lo'] for z in opp if z['lo'] > f['hi']]; cap = min(caps) if caps else None
                return sorted(set(min(x, cap) if cap else x for x in cand))
            caps = [z['hi'] for z in opp if z['hi'] < f['lo']]; cap = max(caps) if caps else None
            return sorted(set(max(x, cap) if cap else x for x in cand), reverse=True)
        a = rS['atr'][ci]
        stop = s['extreme'] - max(0.001 * s['extreme'], 0.25 * a) if bull else s['extreme'] + max(0.001 * s['extreme'], 0.25 * a)
        ce = (f['lo'] + f['hi']) / 2
        expiry = f['known_at'] + p['expiry'] * p['s_sec']
        rec.update(stop=stop, expiry=expiry)
        if abs(ce - stop) / ce < 0.003:
            rec.update(block='R:R: stop < 0.3%', block_t=Tc); out.append(rec); continue
        tg0 = targets_at(Tc)

        def wfill(tg):
            if not tg: return None, None, None
            t1, t2 = tg[0], (tg[1] if len(tg) > 1 else tg[0])
            return t1, t2, worst_fill(d, t2, stop, c_e, c_tp, c_s, min_r)
        tp1, tp2, W = wfill(tg0)
        rec.update(tp1_at_setup=tp1, tp2_at_setup=tp2, worst_fill_at_setup=W,
                   rr_feasible_at_setup=bool(W is not None and ((bull and W >= f['lo']) or (not bull and W <= f['hi']))))
        touched = conf = None; tried = []
        j = bisect.bisect_left(tC, Tc)
        block = None
        while j < len(C):
            t, o, h, l, c = C[j]
            E = t + p['c_sec']
            if E > expiry: block = ('expired: zone never touched' if touched is None else 'expired: no confirmation close'), E; break
            if E in endS and ((bull and endS[E][4] < s['extreme']) or (not bull and endS[E][4] > s['extreme'])): block = 'invalidated (close beyond sweep)', E; break
            if any(e['dir'] != d and e['t'] > brk['t'] and e['t'] + p['s_sec'] <= E for e in brks): block = 'conflict (opposite break)', E; break
            tp1, tp2, W = wfill(targets_at(t))                      # plan as known when this candle opened
            if 'no_tp1_cancel' not in variant and tp1 is not None and ((bull and h >= tp1) or (not bull and l <= tp1)):
                block = 'late: TP1 reached before entry', E; break
            if touched is None and ((bull and l <= f['hi']) or (not bull and h >= f['lo'])): touched = t
            if touched is not None:
                if 'no_zone_fill_cancel' not in variant and ((bull and l < f['lo']) or (not bull and h > f['hi'])): block = 'zone filled before confirmation', E; break
                kk = 'H' if bull else 'L'
                ix = bisect.bisect_right(swCk[kk], t) - 1
                if ix >= 0:
                    lvl = swC[kk][ix][1]
                    if ((bull and c > lvl) or (not bull and c < lvl)) and lvl not in tried:
                        tried.append(lvl)
                        conf = dict(t=E, close=c, level=lvl)
                        tp1, tp2, W = wfill(targets_at(E))
                        if W is None: block = 'R:R: no untaken target at confirmation', E; break
                        if (bull and W < f['lo']) or (not bull and W > f['hi']):
                            block = f'R:R < {min_r:g}:1 net at confirmation (worst fill {W:.6g} outside zone)', E; break
                        rec.update(tp1=tp1, tp2=tp2, worst_fill=W)
                        if (bull and c <= W) or (not bull and c >= W):
                            rec.update(entry_t=E, entry=c, entry_how='confirmation close inside range', conf=conf); break
                        fill = None
                        for k in range(j + 1, len(C)):
                            if C[k][0] >= E + p['ew']: break
                            if (bull and C[k][3] <= W) or (not bull and C[k][2] >= W): fill = (C[k][0] + p['c_sec'], W); break
                        if fill:
                            rec.update(entry_t=fill[0], entry=fill[1], entry_how='pullback to worst fill in window', conf=conf); break
                        if 'reconfirm' not in variant:
                            block = f'late: confirmation close {c:.6g} beyond worst fill {W:.6g}', E; break
            j += 1
        else:
            block = 'open: still waiting at data end', NOW
        rec.update(touched=touched, conf=conf)
        if block and 'entry_t' not in rec:
            rec.update(block=block[0], block_t=block[1]); out.append(rec); continue
        # manage paper trade (estimate)
        e0, k0 = rec['entry'], bisect.bisect_left(tC, rec['entry_t'])
        tp1, tp2 = rec['tp1'], rec['tp2']
        cur, rem, done, R = stop, 1.0, False, 0.0
        risk = abs(e0 - stop)
        legs = []
        for k in range(k0, len(C)):
            t, o, h, l, c = C[k]
            hs_ = (l <= cur) if bull else (h >= cur)
            tgt = tp2 if done else tp1
            ht = (h >= tgt) if bull else (l <= tgt)
            if hs_:
                legs.append((rem, cur, 'stop' if not done else 'breakeven')); rem = 0; break
            if ht:
                if not done and tp1 != tp2:
                    legs.append((0.5, tp1, 'TP1')); rem = 0.5; done = True; cur = e0; continue
                legs.append((rem, tp2, 'TP2')); rem = 0; break
        if rem > 0: legs.append((rem, C[-1][4], 'open at data end'))
        sg = 1 if bull else -1
        R = sum(fr * (sg * (px - e0) - px * c_tp - e0 * c_e) for fr, px, _ in legs) / (risk + e0 * c_e + stop * c_s)
        rec.update(block='ENTRY', block_t=rec['entry_t'], result='/'.join(x[2] for x in legs), netR=round(R, 2))
        out.append(rec)
    return out


def main():
    cg = json.load(open(os.path.join(HERE, '..', '..', '..', 'tmp_cg.json'))) if False else get_json('https://api.coingecko.com/api/v3/derivatives?include_tickers=unexpired')
    b = {x['symbol']: x for x in cg if x.get('market') == 'Binance (Futures)' and x.get('contract_type') == 'perpetual'}
    U = json.load(open(sys.argv[2]))   # {symbol: [yahoo, scale, scope_label]}
    res = []
    for sym, (ysym, scale, scope) in U.items():
        x = b.get(sym) or {}
        try:
            m5 = yahoo(ysym, '5m', '5d', 300, scale, scope != 'stock')
            m15 = yahoo(ysym, '15m', '5d', 900, scale, scope != 'stock')
            h1 = yahoo(ysym, '1h', '60d', 3600, scale, scope != 'stock')
        except Exception as e:
            res.append(dict(sym=sym, scope=scope, data=f'unavailable: {str(e)[:60]}')); continue
        idx = x.get('index')
        gap = round(100 * (m5[-1][4] / idx - 1), 2) if idx and m5 else None
        if gap is not None and abs(gap) > 3:
            res.append(dict(sym=sym, scope=scope, data=f'unavailable: Yahoo {ysym} price {m5[-1][4]:.6g} vs Binance index {idx:.6g} ({gap:+.1f}%), wrong instrument')); continue
        hs = (x.get('spread') or 0.02) / 200
        costs = (FEE + hs + SLIP, FEE + hs, FEE + hs + SLIP)
        h4 = resample(h1, 3600, 14400) if scope != 'stock' else yahoo(ysym, '1d', '6mo', 86400, scale, False)
        for variant in ('live', 'no_tp1_cancel', 'no_zone_fill_cancel', 'reconfirm', 'rr1.5', 'no_disp',
                        'all:no_tp1_cancel+no_zone_fill_cancel+reconfirm', 'all:no_tp1_cancel+no_zone_fill_cancel+reconfirm+rr1.5+no_disp'):
            for plan, S, C, cx, cn, cs in (('A', m15, m5, h1, 3, 3600), ('B', h1, m15, h4, 2, 14400 if scope != 'stock' else 86400)):
                for r in replay(plan, S, C, cx, cn, cs, costs, variant):
                    r.update(sym=sym, scope=scope, variant=variant, proxy_gap=gap); res.append(r)
    json.dump(res, open(os.path.join(OUT, 'replay.json'), 'w'), default=str)
    print('records', len(res))


if __name__ == '__main__':
    main()
