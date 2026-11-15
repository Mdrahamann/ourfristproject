#!/usr/bin/env python3
"""Paper replay of the ORIGINAL 15m/5m scalp over several days, with rule variants side by side. Read-only; no orders.

Live rules are not changed: variants run on patched COPIES of the code, inside this script only.
  live       : current rules (scalp_original + scalp_status: sweep -> strong candle -> break -> price gap, C2 trigger, 2:1 net)
  no_disp    : the strong-candle threshold (DP1, a PROPOSED threshold) switched off
  inzone     : the 10 Nov trigger, retired by the 11 Nov decision: a 5m candle closing in the trade direction INSIDE the
               zone and within the 2:1 entry range (instead of a 5m close beyond the last confirmed 5m swing)
  both       : no_disp + inzone
Every variant keeps: closed candles only, 1H grouping, stop/targets as the scanner computes them, 2:1 net (R3),
E3 (TP1 before entry), expiry, invalidation and opposite-break cancels. Outcomes: 50% at TP1 then break-even (T3),
rest to TP2; costs 0.12% round trip + 0.02% stop slippage. Data: cached Yahoo spot candles (proxy), so approximate.
Usage: python3 replay_scalp_week.py CACHE_DIR UNIVERSE_JSON 'YYYY-mm-dd HH:MM' STEP_MIN OUT_JSON"""
import datetime as dt, inspect, json, os, sys, types
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scanner'))
import scalp_original as SO  # noqa: E402
import scalp_status as SS  # noqa: E402

UK = ZoneInfo('Europe/London')
cache, uni, start, step, out = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3], int(sys.argv[4]), sys.argv[5]
T0 = dt.datetime.strptime(start, '%Y-%m-%d %H:%M').replace(tzinfo=UK).timestamp()

# strong candle optional: a patched copy of the original module (live module untouched)
src = inspect.getsource(SO)
assert 'if rng >= 1.5 * a[i] and body >= 0.6 * rng:' in src
SO_nd = types.ModuleType('scalp_original_nodisp'); SO_nd.__dict__['__file__'] = SO.__file__
exec(compile(src.replace('if rng >= 1.5 * a[i] and body >= 0.6 * rng:', 'if rng > 0:'), 'scalp_original_nodisp', 'exec'), SO_nd.__dict__)


def rows(y, iv, sec, scale):
    r = json.load(open(f'{cache}/{y}_{iv}.json'))['chart']['result'][0]; q = r['indicators']['quote'][0]
    return [(t, o * scale, h * scale, l * scale, c * scale) for t, o, h, l, c in zip(r['timestamp'], q['open'], q['high'], q['low'], q['close'])
            if None not in (o, h, l, c) and t % sec == 0]


def outcome(d, E, S, tp1, tp2, t_entry, m5):
    bull = d == 'bull'; cost = E * 0.0012; risk = abs(E - S) + cost + E * 0.0002
    R = lambda X: (((X - E) if bull else (E - X)) - cost) / risk
    half, stop = None, S
    for t, o, h, l, c in m5:
        if t < t_entry: continue
        hit_stop = (l <= stop) if bull else (h >= stop)
        if half is None:
            if hit_stop: return 'loss', round(-1.0, 2), t
            if (h >= tp1) if bull else (l <= tp1): half, stop = R(tp1), E
            continue
        if hit_stop: return 'tp1+be', round(0.5 * half, 2), t
        if (h >= tp2) if bull else (l <= tp2): return 'tp2', round(0.5 * half + 0.5 * R(tp2), 2), t
    last = m5[-1][4]
    return ('open', round((0.5 * half if half is not None else 0) + (0.5 if half is not None else 1) * R(last), 2), None)


FEASIBLE = ('WAIT FOR TRIGGER (in zone)', 'CONFIRMED (in entry window)', 'CONFIRMED (needs pullback to worst fill)',
            'MISSED (entry window passed)', 'MISSED (confirmation beyond worst fill)')
res = {v: dict(complete=set(), entries={}, blocks={}) for v in ('live', 'no_disp', 'inzone', 'both')}
data = {}
for sym, y in uni.items():
    sc = 1000.0 if sym.startswith('1000') else 1.0
    data[sym] = (rows(y, '5m', 300, sc), rows(y, '15m', 900, sc), rows(y, '1h', 3600, sc))
NOW = max(r[0][-1][0] for r in data.values())
T = T0
while T <= NOW:
    for sym, (m5a, m15a, h1a) in data.items():
        m5 = [r for r in m5a if T - 2 * 86400 <= r[0] and r[0] + 300 <= T]
        m15 = [r for r in m15a if T - 5 * 86400 <= r[0] and r[0] + 900 <= T]
        h1 = [r for r in h1a if T - 60 * 86400 <= r[0] and r[0] + 3600 <= T]
        if len(m15) < 40 or len(m5) < 40 or len(h1) < 40: continue
        bias = SO.htf_context(h1, 3, 3600)['bias']
        for mod, vnames in ((SO, ('live', 'inzone')), (SO_nd, ('no_disp', 'both'))):
            r15 = mod.analyse(m15, 2, 900)
            seqs = mod.scalp_sequences(m15, m5, h1, bias, 0.01, T, r15=r15)
            for s in seqs:
                SS.label(s, m5, m15, h1, r15['swings'], T)
                key = (sym, s['dir'], s['sweep']['bar'])
                grp = 'main' if s['group'].startswith('main') else 'countertrend'
                st = s['plan_status']
                for v in vnames:
                    R_ = res[v]
                    if st not in ('Watch', 'Invalidated', 'Watch (zone distant)'): R_['complete'].add(key)
                    R_['blocks'][key] = st
                    if key in R_['entries']: continue
                    f, tg = s.get('fvg') or {}, s.get('targets') or []
                    if not tg or not f: continue
                    tp1, tp2 = tg[0], (tg[1] if len(tg) > 1 else tg[0]); W = s['worst_fill']; bull = s['dir'] == 'bull'
                    if v in ('live', 'no_disp'):
                        if s.get('t_fill'):
                            c5 = s['confirm5m']; inside = (bull and c5['close'] <= W) or (not bull and c5['close'] >= W)
                            E = c5['close'] if inside else W
                            R_['entries'][key] = dict(group=grp, t=s['t_fill'], E=E, S=s['stop'], tp1=tp1, tp2=tp2,
                                                      res=outcome(s['dir'], E, s['stop'], tp1, tp2, s['t_fill'] + 300, m5a))
                    elif st in FEASIBLE and s.get('t_touch'):
                        lo, hi = f['lo'], f['hi']; exp = s['t_expiry'] or T
                        a, b = (lo, min(hi, W)) if bull else (max(lo, W), hi)
                        for t, o, h, l, c in m5:
                            if t < s['t_touch'] or t + 300 > min(T, exp): continue
                            if (bull and c > o and a <= c <= b) or (not bull and c < o and a <= c <= b):
                                R_['entries'][key] = dict(group=grp, t=t + 300, E=c, S=s['stop'], tp1=tp1, tp2=tp2,
                                                          res=outcome(s['dir'], c, s['stop'], tp1, tp2, t + 300, m5a))
                                break
    T += step * 60

u = lambda t: dt.datetime.fromtimestamp(t, UK).strftime('%d %b %H:%M') if t else '—'
summary = {}
for v, R_ in res.items():
    ents = R_['entries']
    rs = [e['res'][1] for e in ents.values()]
    import collections
    ends = collections.Counter(R_['blocks'][k] for k in R_['complete'])
    summary[v] = dict(complete_setups=len(R_['complete']), how_complete_setups_ended=dict(ends.most_common()), entries=len(ents), total_R=round(sum(rs), 2),
                      wins=sum(e['res'][0] in ('tp2', 'tp1+be') for e in ents.values()), losses=sum(e['res'][0] == 'loss' for e in ents.values()),
                      open=sum(e['res'][0] == 'open' for e in ents.values()),
                      trades=[dict(sym=k[0], dir=k[1], sweep=k[2], group=e['group'], entry_time=u(e['t']), entry=round(e['E'], 6), stop=round(e['S'], 6),
                                   tp1=round(e['tp1'], 6), tp2=round(e['tp2'], 6), result=e['res'][0], R=e['res'][1], exit=u(e['res'][2]))
                              for k, e in sorted(ents.items(), key=lambda kv: kv[1]['t'])])
json.dump(dict(start=start, end=u(NOW), step_min=step, coins=len(uni), summary=summary), open(out, 'w'), indent=1)
for v, s in summary.items():
    print(f"{v:8} complete setups {s['complete_setups']:3} | entries {s['entries']:3} | wins {s['wins']} losses {s['losses']} open {s['open']} | total {s['total_R']:+.2f}R")
    print('     ended:', s['how_complete_setups_ended'])
    for t in s['trades']: print('    ', t)
