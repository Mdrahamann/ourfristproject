"""Plan A (15m setup, 5m confirmation) and Plan B (1H setup, 15m confirmation). Read-only; no orders.
Rule ids refer to CLAUDE.md (§18 defines the two plans). Thresholds are PROVISIONAL."""
import bisect
import datetime as dt
from zoneinfo import ZoneInfo
from smc_core import analyse, worst_fill

UK = ZoneInfo('Europe/London')
PLANS = {
    'A': dict(name='Plan A: 15m setup, 5m confirmation', s_n=2, s_sec=900, c_n=2, c_sec=300, lookback=96,
              window=16, expiry=16, entry_window=300, ctx='1H', s_tf='15m', c_tf='5m'),
    'B': dict(name='Plan B: 1H setup, 15m confirmation', s_n=3, s_sec=3600, c_n=2, c_sec=900, lookback=72,
              window=16, expiry=16, entry_window=900, ctx='4H', s_tf='1H', c_tf='15m'),
}
QUALIFY = {'CONFIRMED (in entry window)': 0, 'CONFIRMED (needs pullback to worst fill)': 1,
           'WAIT FOR TRIGGER (in zone)': 2, 'WAIT FOR TRIGGER': 3}


def ukd(ts):
    return dt.datetime.fromtimestamp(ts, UK).strftime('%a %H:%M')


def find_setups(plan, S, C, ctx_dir, last, costs, now):
    P = PLANS[plan]
    c_e, c_tp, c_s = costs
    rS = analyse(S, P['s_n'], P['s_sec'], max_age=400, fvg_state=False)
    rC = analyse(C, P['c_n'], P['c_sec'], max_age=400, fvg_state=False)
    brks = [e for e in rS['events'] if e['ev'] in ('BOS', 'CHoCH')]
    swC = {k: sorted((w['known_at'], w['price'], w['t']) for w in rC['swings'] if w['kind'] == k) for k in 'HL'}
    swCk = {k: [x[0] for x in v] for k, v in swC.items()}
    tC = [r[0] for r in C]
    n, out, seen = len(S), [], set()
    for s in [e for e in rS['events'] if e['ev'] == 'sweep' and e['i'] >= n - P['lookback']]:
        d = s['dir']; bull = d == 'bull'
        brk = next((e for e in brks if e['dir'] == d and s['i'] <= e['i'] <= s['i'] + P['window']), None)
        hi_i = brk['i'] if brk else min(n - 1, s['i'] + P['window'])
        disp = next((e for e in rS['events'] if e['ev'] == 'displacement' and e['dir'] == d and s['i'] <= e['i'] <= hi_i), None)
        fv = [f for f in rS['fvgs'] if f['dir'] == d and s['i'] <= f['i'] <= hi_i + 2]
        rec = dict(plan=plan, dir=d, group='main' if ctx_dir == d else 'countertrend', sweep=s, brk=brk, disp=disp)
        inval = next((S[j][0] + P['s_sec'] for j in range(s['i'] + 1, n)
                      if (bull and S[j][4] < s['extreme']) or (not bull and S[j][4] > s['extreme'])), None)
        missing = [m for m, v in (('structure break', brk), ('strong candle', disp), ('price gap', fv)) if not v]
        if inval or missing:
            rec.update(status='Invalidated' if inval else 'Watch', missing=missing); out.append(rec); continue
        f = next((z for z in fv if z['t'] == disp['t']), None) or max(fv, key=lambda z: z['hi'] - z['lo'])
        if (d, f['i']) in seen: continue
        seen.add((d, f['i']))
        ci = max(brk['i'], f['i'])
        opp = next((e for e in brks if e['dir'] != d and e['i'] > brk['i']), None)
        filled = next((S[j][0] for j in range(f['i'] + 1, n) if (bull and S[j][3] < f['lo']) or (not bull and S[j][2] > f['hi'])), None)
        kt = 'H' if bull else 'L'
        cand = []
        for w in rS['swings']:
            if w['kind'] != kt or w['known_at'] > now or w['i'] < n - 400: continue
            later = S[w['i'] + 1:]
            if bull and w['price'] > f['hi'] and all(r[2] < w['price'] for r in later): cand.append(w['price'])
            if not bull and w['price'] < f['lo'] and all(r[3] > w['price'] for r in later): cand.append(w['price'])
        oppf = [z for z in rS['fvgs'] if z['dir'] != d and z['i'] >= n - 400 and not any(
            (z['dir'] == 'bear' and r[2] >= z['hi']) or (z['dir'] == 'bull' and r[3] <= z['lo']) for r in S[z['i'] + 1:])]
        if bull:
            caps = [z['lo'] for z in oppf if z['lo'] > f['hi']]; cap = min(caps) if caps else None
            tg = sorted(set(min(p, cap) if cap else p for p in cand))
        else:
            caps = [z['hi'] for z in oppf if z['hi'] < f['lo']]; cap = max(caps) if caps else None
            tg = sorted(set(max(p, cap) if cap else p for p in cand), reverse=True)
        a = rS['atr'][ci]
        buf = max(0.001 * s['extreme'], 0.25 * a)
        stop = s['extreme'] - buf if bull else s['extreme'] + buf
        rec.update(zone=(f['lo'], f['hi']), zone_known=f['known_at'], stop=stop,
                   expiry=f['known_at'] + P['expiry'] * P['s_sec'], conflict=opp, missing=[])
        if not tg:
            rec['status'] = 'No untaken target'; out.append(rec); continue
        tp1, tp2 = tg[0], (tg[1] if len(tg) > 1 else tg[0])
        W = worst_fill(d, tp2, stop, c_e, c_tp, c_s, 2.0)
        ce = (f['lo'] + f['hi']) / 2

        def netR(entry, tp):
            if bull: return (tp * (1 - c_tp) - entry * (1 + c_e)) / (entry * (1 + c_e) - stop * (1 - c_s))
            return (entry * (1 - c_e) - tp * (1 + c_tp)) / (stop * (1 + c_s) - entry * (1 - c_e))
        rec.update(tp1=tp1, tp2=tp2, worst_fill=W, ce=ce, netR_ce=(round(netR(ce, tp1), 2), round(netR(ce, tp2), 2)),
                   entry_range=(f['lo'], W) if bull else (W, f['hi']))
        Tc = S[ci][0] + P['s_sec']
        touched = conf = tp1_first = fill = None
        for j in range(bisect.bisect_left(tC, Tc), len(C)):
            t, o, h, l, c = C[j][:5]
            if (bull and h >= tp1) or (not bull and l <= tp1): tp1_first = t + P['c_sec']; break
            if touched is None and ((bull and l <= f['hi']) or (not bull and h >= f['lo'])): touched = t
            if touched is not None:
                kk = 'H' if bull else 'L'
                ix = bisect.bisect_right(swCk[kk], t) - 1           # swings confirmed before this candle opened
                if ix >= 0:
                    lvl = swC[kk][ix][1]
                    if (bull and c > lvl) or (not bull and c < lvl):
                        conf = dict(t=t + P['c_sec'], close=c, level=lvl)
                        if (bull and c <= W) or (not bull and c >= W):
                            fill = dict(t=conf['t'], px=c, how='confirmation close inside the entry range')
                        else:
                            for k in range(j + 1, len(C)):
                                if C[k][0] >= conf['t'] + P['entry_window']: break
                                if (bull and C[k][3] <= W) or (not bull and C[k][2] >= W):
                                    fill = dict(t=C[k][0], px=W, how='pullback to the worst fill after confirmation'); break
                        break
        kk = 'H' if bull else 'L'
        ix = bisect.bisect_right(swCk[kk], now) - 1
        ref = dict(price=swC[kk][ix][1], swing_t=swC[kk][ix][2], known_at=swC[kk][ix][0]) if ix >= 0 else None
        rec.update(touched=touched, conf=conf, tp1_first=tp1_first, fill=fill, conf_ref=ref,
                   conf_beyond_worst=bool(ref and ((bull and ref['price'] > W) or (not bull and ref['price'] < W))),
                   dist_pct=((f['hi'] if bull else f['lo']) / last - 1) * 100)
        feasible = (W >= f['lo']) if bull else (W <= f['hi'])
        if (bull and stop >= f['lo']) or (not bull and stop <= f['hi']): st = 'Bad stop'
        elif abs(ce - stop) / ce < 0.003: st = 'Stop too tight (<0.3%)'
        elif opp: st = 'Conflict (opposite break)'
        elif filled and not conf: st = 'Zone filled'
        elif not feasible: st = 'Fails 2:1 net'
        elif tp1_first: st = 'MISSED (TP1 reached before entry)'
        elif conf:
            if now >= conf['t'] + P['entry_window']: st = 'MISSED (entry window passed)'
            elif fill: st = 'CONFIRMED (in entry window)'
            else: st = 'CONFIRMED (needs pullback to worst fill)'
        elif now > rec['expiry']: st = 'Expired'
        else: st = 'WAIT FOR TRIGGER (in zone)' if touched else 'WAIT FOR TRIGGER'
        rec['status'] = st
        out.append(rec)
    return out


def _fmt(x):
    return f'{x:.6g}' if isinstance(x, float) else str(x)


def best_and_reason(setups, plan, d, group, n_lookback_h):
    rows = [s for s in setups if s['plan'] == plan and s['dir'] == d and s['group'] == group]
    q = [s for s in rows if s['status'] in QUALIFY]
    if q:
        q.sort(key=lambda s: (QUALIFY[s['status']], -s['netR_ce'][1], abs(s.get('dist_pct', 99))))
        return q[0], None
    if not rows:
        return None, f'no sweep → strong candle → break → price gap sequence in the last {n_lookback_h}h'
    cnt = {}
    for s in rows: cnt[s['status']] = cnt.get(s['status'], 0) + 1
    near = [s for s in rows if s.get('netR_ce')]
    extra = ''
    if near:
        b = max(near, key=lambda s: s['sweep']['t'])
        extra = f"; latest: {b['sym']} {b['netR_ce'][1]:.2f}R, {b['status'].lower()}"
    top = ', '.join(f'{v} {k.lower()}' for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])[:3])
    return None, f'{len(rows)} sequence(s): {top}{extra}'


RECENT_FROM = [0]


def now_ts(x):
    return (x.get('conf') or {}).get('t') or x.get('tp1_first')


def render(setups, breadth, data_label, ready_now_ok, now=None):
    RECENT_FROM[0] = (now or 0) - 7200
    L = []
    L.append(f'Data: {data_label}')
    L.append(f"1H trend: bearish on {breadth['bear']} of {breadth['n']}, bullish on {breadth['bull']}"
             + (' → Plan A checks bearish continuation shorts (main) AND countertrend longs (half risk)' if breadth['bear'] > breadth['n'] / 2 else ''))
    L.append('')
    L.append('| Row | Best setup | Status | Entry range | Confirmation needed (level) | Worst fill | Stop | TP1 / TP2 | Net R (mid-zone) | Expires |')
    L.append('|---|---|---|---|---|---|---|---|---|---|')
    order = [('A', 'bull', 'main', 'Plan A, Longs'), ('A', 'bear', 'main', 'Plan A, Shorts'),
             ('B', 'bull', 'main', 'Plan B, Longs'), ('B', 'bear', 'main', 'Plan B, Shorts'),
             ('A', 'bull', 'countertrend', 'Plan A, Longs (countertrend, half risk)'),
             ('A', 'bear', 'countertrend', 'Plan A, Shorts (countertrend, half risk)'),
             ('B', 'bull', 'countertrend', 'Plan B, Longs (countertrend vs 4H, half risk)'),
             ('B', 'bear', 'countertrend', 'Plan B, Shorts (countertrend vs 4H, half risk)')]
    details = []
    for plan, d, g, label in order:
        best, why = best_and_reason(setups, plan, d, g, 24 if plan == 'A' else 72)
        if g == 'countertrend' and not best and not ((plan, d) == ('A', 'bull') and breadth['bear'] > breadth['n'] / 2) \
                and not ((plan, d) == ('A', 'bear') and breadth['bull'] > breadth['n'] / 2):
            continue
        if not best:
            L.append(f'| **{label}** | No qualifying setup | {why} | | | | | | | |')
            continue
        P = PLANS[plan]
        st = best['status']
        if st.startswith('CONFIRMED') and not ready_now_ok:
            st += '. READY NOW unavailable: live contract data missing'
        ref = best['conf'] if best.get('conf') else best.get('conf_ref')
        need = (f"closed {P['c_tf']} candle {'above' if d == 'bull' else 'below'} last confirmed {P['c_tf']} swing "
                f"{'high' if d == 'bull' else 'low'} ≈ {_fmt(ref['level'] if best.get('conf') else ref['price'])}" if ref else 'no confirmed swing yet')
        lo, hi = best['entry_range']
        L.append(f"| **{label}** | {best['sym']} ({best['group']}) | {st} | ≈ {_fmt(lo)}–{_fmt(hi)} | {need} | ≈ {_fmt(best['worst_fill'])} | "
                 f"≈ {_fmt(best['stop'])} | ≈ {_fmt(best['tp1'])} / {_fmt(best['tp2'])} | {best['netR_ce'][0]:.2f} / {best['netR_ce'][1]:.2f} | {ukd(best['expiry'])} |")
        details.append((label, best))
    recent = [x for x in setups if x['status'].startswith('MISSED') and now_ts(x) and now_ts(x) >= RECENT_FROM[0]]
    if recent:
        L.append('')
        L.append('MISSED in the last 2 hours: ' + '; '.join(
            f"{x['sym']} {'long' if x['dir'] == 'bull' else 'short'} (Plan {x['plan']}, {x['group']}): {x['status'][8:-1]}"
            + (f", confirmed {ukd(x['conf']['t'])} at {_fmt(x['conf']['close'])} vs worst fill {_fmt(x['worst_fill'])}" if x.get('conf') else '')
            for x in sorted(recent, key=now_ts, reverse=True)[:5]))
    L.append('')
    for label, b in details:
        P = PLANS[b['plan']]
        s, brk, disp = b['sweep'], b['brk'], b['disp']
        L.append(f"**{label}: {b['sym']}** ({P['s_tf']} setup, {P['c_tf']} confirmation; levels approximate)")
        L.append(f"- Evidence: sweep of {_fmt(s['level'])} on the {ukd(s['t'])} {P['s_tf']} bar (extreme {_fmt(s['extreme'])}) → "
                 f"strong candle {ukd(disp['t'])} → {brk['ev']} {'above' if b['dir'] == 'bull' else 'below'} {_fmt(brk['level'])} "
                 f"(close {_fmt(brk['close'])}, {ukd(brk['t'])}) → price gap {_fmt(b['zone'][0])}–{_fmt(b['zone'][1])} (known {ukd(b['zone_known'])}), "
                 f"{'touched ' + ukd(b['touched']) if b.get('touched') else 'not touched yet'}")
        if b.get('conf'):
            L.append(f"- Confirmation: {P['c_tf']} close {_fmt(b['conf']['close'])} at {ukd(b['conf']['t'])} beyond {_fmt(b['conf']['level'])}; "
                     f"entry window ends {ukd(b['conf']['t'] + P['entry_window'])}"
                     + (f"; estimated fill {_fmt(b['fill']['px'])} ({b['fill']['how']})" if b.get('fill') else ''))
        elif b.get('conf_beyond_worst'):
            L.append(f"- ⚠️ The confirmation level (≈ {_fmt(b['conf_ref']['price'])}) is beyond the worst fill (≈ {_fmt(b['worst_fill'])}). "
                     f"This needs either a fresh pullback to the worst fill after confirmation, or a new "
                     f"{'lower swing high' if b['dir'] == 'bull' else 'higher swing low'} to confirm against. "
                     f"If neither happens within the entry window, it's MISSED.")
        L.append(f"- Invalidation: a {P['s_tf']} close {'below' if b['dir'] == 'bull' else 'above'} {_fmt(s['extreme'])}; an opposite {P['s_tf']} break; "
                 f"TP1 reached before entry; zone fully filled before confirmation; expiry {ukd(b['expiry'])}. Alert level: ≈ {_fmt(b['zone'][1] if b['dir'] == 'bull' else b['zone'][0])}")
    return '\n'.join(L)
