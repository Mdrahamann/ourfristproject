"""Four-row scan output (CLAUDE.md §18): the ORIGINAL scalp plan (15m setup, 5m confirmation) first, the SEPARATE
1H plan (1H setup, 15m confirmation) second; longs and shorts for each. Read-only; no orders."""
import datetime as dt
from zoneinfo import ZoneInfo
from scalp_status import QUALIFYING, RANK


def hm(t):
    return dt.datetime.fromtimestamp(t, UK).strftime('%d %b %H:%M') if t else '—'

UK = ZoneInfo('Europe/London')
PLACEHOLDER_BALANCE = 1000.0      # user's balance not confirmed yet (CLAUDE.md decision 1)
MAX_NOTIONAL = 1000.0
SCALP = 'Original scalp plan — 15m setup, 5m confirmation'
ONEH = 'Separate 1H plan — 1H setup, 15m confirmation'
B_RANK = {'CONFIRMED (in entry window)': 0, 'CONFIRMED (needs pullback to worst fill)': 1, 'WAIT FOR TRIGGER (in zone)': 2,
          'WAIT FOR TRIGGER': 3, 'MISSED (entry window passed)': 4, 'MISSED (TP1 reached before entry)': 6, 'Fails 2:1 net': 7,
          'Stop too tight (<0.3%)': 8, 'Bad stop': 8, 'No untaken target': 9, 'Zone filled': 9, 'Conflict (opposite break)': 10,
          'Expired': 11, 'Watch': 13, 'Invalidated': 14}


def g(x):
    return f'{x:.6g}' if isinstance(x, (int, float)) and x is not None else str(x)


def side(d):
    return 'Long' if d == 'bull' else 'Short'


# ---------- normalise both plans to one shape ----------
def from_scalp(sym, s):
    bull = s['dir'] == 'bull'
    f = s.get('fvg') or {}
    c5, ref = s.get('confirm5m'), s.get('trigger_ref')
    if c5:
        need = f"5m close {g(c5['close'])} at {hm(s.get('t_conf'))} {'above' if bull else 'below'} {g(c5['level'])} (done)"
    elif ref:
        need = (f"a fully closed 5m candle {'above' if bull else 'below'} {g(ref['price'])} (last confirmed 5m swing "
                f"{'high' if bull else 'low'}, {ref['swing_t'][-5:]}, confirmed {ref['known_at']}). It moves to a "
                f"{'lower high' if bull else 'higher low'} if a new 5m swing forms during the pullback")
    else:
        need = 'no confirmed 5m swing yet'
    tg = s.get('targets') or []
    return dict(plan='scalp', sym=sym, dir=s['dir'], group='main' if s['group'].startswith('main') else 'countertrend',
                status=s['plan_status'], block=s.get('block'), rank=RANK.get(s['plan_status'], 20) + 0.1 * len(s.get('missing') or []),
                zone=(f.get('lo'), f.get('hi')) if f else None, touched=f.get('touched'), need=need,
                worst=s.get('worst_fill'), stop=s.get('stop'), tp1=tg[0] if tg else None, tp2=tg[1] if len(tg) > 1 else (tg[0] if tg else None),
                netR=(s.get('net_R_t1'), s.get('net_R_t2', s.get('net_R_t1'))), expiry=s.get('expiry'), dist=s.get('dist_pct'),
                sweep=f"sweep of {g(s['sweep']['level'])} (swing {s['sweep']['swing_t']}, known {s['sweep']['swing_known']}) on the {s['sweep']['bar']} 15m bar, extreme {g(s['sweep']['extreme'])}",
                brk=(f"{s['brk']['kind']} close {g(s['brk']['close'])} at {s['brk']['bar']} {'above' if bull else 'below'} {g(s['brk']['level'])}" if s.get('brk') else 'no structure break'),
                disp=(f"strong candle {s['disp']}" if s.get('disp') else 'no strong candle'),
                gap=(f"price gap {g(f['lo'])}–{g(f['hi'])} (known {f['known_at']}), {'touched ' + f['touched'] if f.get('touched') else 'not touched'}" if f else 'no unfilled price gap'),
                t_sort=s['sweep']['bar'], risk_pct=s.get('risk_pct'), cost_R=s.get('cost_R'), ce=s.get('entry_ce'),
                extreme=s['sweep']['extreme'])


def from_1h(r):
    bull = r['dir'] == 'bull'
    st = r['status']
    blk = None
    if st == 'Invalidated': blk = f"1H close {'below' if bull else 'above'} the sweep extreme {g(r['sweep']['extreme'])}"
    elif st == 'Watch': blk = 'missing ' + ', '.join(r.get('missing') or [])
    elif st == 'Zone filled': blk = 'the 1H price gap was fully filled before a 15m confirmation'
    elif st.startswith('Conflict'): blk = f"opposite 1H {r['conflict']['ev']} at {hm(r['conflict']['t'] + 3600)}" if r.get('conflict') else 'opposite 1H break'
    elif st == 'Fails 2:1 net': blk = f"worst fill {g(r['worst_fill'])} is beyond the whole zone {g(r['zone'][0])}–{g(r['zone'][1])} (net R from mid-zone {r['netR_ce'][1]})"
    elif st.startswith('MISSED (TP1'): blk = f"price reached TP1 {g(r['tp1'])} at {hm(r['tp1_first'])} before an entry"
    elif st.startswith('MISSED'): blk = f"15m close {g(r['conf']['close'])} at {hm(r['conf']['t'])}; window ended {hm(r['conf']['t'] + 900)}" if r.get('conf') else st
    elif st == 'Expired': blk = f"plan expired {hm(r['expiry'])} (16 × 1H after the price gap was known)"
    elif st in ('Bad stop', 'Stop too tight (<0.3%)', 'No untaken target'): blk = st
    c, ref = r.get('conf'), r.get('conf_ref')
    if c:
        need = f"15m close {g(c['close'])} at {hm(c['t'])} {'above' if bull else 'below'} {g(c['level'])} (done)"
    elif ref:
        need = f"a fully closed 15m candle {'above' if bull else 'below'} {g(ref['price'])} (last confirmed 15m swing {'high' if bull else 'low'}, {hm(ref['swing_t'])})"
    else:
        need = 'no confirmed 15m swing yet' if r.get('zone') else '—'
    s, b, d = r['sweep'], r.get('brk'), r.get('disp')
    z = r.get('zone')
    return dict(plan='1h', sym=r['sym'], dir=r['dir'], group=r['group'], status=st, block=blk, rank=B_RANK.get(st, 20) + 0.1 * len(r.get('missing') or []),
                zone=z, touched=hm(r['touched']) if r.get('touched') else None, need=need, worst=r.get('worst_fill'), stop=r.get('stop'),
                tp1=r.get('tp1'), tp2=r.get('tp2'), netR=r.get('netR_ce') or (None, None), expiry=hm(r['expiry']) if r.get('expiry') else None,
                dist=round(r['dist_pct'], 2) if r.get('dist_pct') is not None else None,
                sweep=f"sweep of {g(s['level'])} on the {hm(s['t'])} 1H bar, extreme {g(s['extreme'])}",
                brk=(f"{b['ev']} close {g(b['close'])} at {hm(b['t'] + 3600)} {'above' if bull else 'below'} {g(b['level'])}" if b else 'no structure break'),
                disp=(f"strong candle {hm(d['t'])}" if d else 'no strong candle'),
                gap=(f"price gap {g(z[0])}–{g(z[1])} (known {hm(r['zone_known'])}), {'touched ' + hm(r['touched']) if r.get('touched') else 'not touched'}" if z else 'no price gap'),
                t_sort=s['t'], risk_pct=(abs(r['ce'] - r['stop']) / r['ce'] * 100) if r.get('ce') else None,
                cost_R=None, ce=r.get('ce'), extreme=s['extreme'], costs=r.get('costs'))


def pick(rows, d, group):
    """Best qualifying setup for the row; otherwise the closest blocked one (most advanced status, then latest sweep)."""
    rs = [r for r in rows if r['dir'] == d and r['group'] == group]
    q = sorted([r for r in rs if r['status'] in QUALIFYING], key=lambda r: (r['rank'], -(r['netR'][1] or -9)))
    if q: return q[0], rs, None
    if not rs: return None, rs, None
    top = min(r['rank'] for r in rs)
    return None, rs, max((r for r in rs if r['rank'] == top), key=lambda r: str(r['t_sort']))


def row_text(label, d, res, n_ok, n_total, unit, lookback):
    best, rs, closest = res
    if n_ok == 0:
        return f"| {label} | {side(d)} | **Not evaluated: no usable candle data** | — | — | — | — | — | — |", None
    if best:
        st = best['status'] + ('' if not best['status'].startswith('CONFIRMED') else ' (paper; READY NOW unavailable)')
        lo, hi = (best['zone'][1], best['worst']) if d == 'bull' else (best['zone'][0], best['worst'])
        return (f"| {label} | {side(d)} | **{st}**: {best['sym']} | {best['need']} | ≈ {g(lo)} → {g(hi)} | ≈ {g(best['stop'])} | "
                f"≈ {g(best['tp1'])} / {g(best['tp2'])} | {best['netR'][0]} / {best['netR'][1]} | {best['expiry']} |"), best
    chk = f"Checked {n_ok} of {n_total} {unit}"
    if not rs:
        return f"| {label} | {side(d)} | {chk}: **no qualifying setup** (no sweep → strong candle → break → price gap in the last {lookback}) | — | — | — | — | — | — |", None
    return (f"| {label} | {side(d)} | {chk}, {len(rs)} sequence(s): **no qualifying setup**. Closest: {closest['sym']}, "
            f"{closest['status'].lower()}: {closest['block']} | — | — | — | — | — | — |"), closest


def size_line(r):
    risk = 0.0025 if r['group'] == 'main' else 0.00125
    ce, stop = r['ce'], r['stop']
    if not ce or not stop: return ''
    cost = (r['cost_R'] or 0) * abs(ce - stop) if r.get('cost_R') is not None else ce * 0.0014
    per = abs(ce - stop) + cost
    units = PLACEHOLDER_BALANCE * risk / per
    notional = min(units * ce, MAX_NOTIONAL)
    return (f"Your balance × {risk:.5f} ÷ {g(per)} per unit. With the $1,000 placeholder: about {g(notional / ce)} units "
            f"(≈ ${notional:.0f} notional{', capped at $1,000' if units * ce > MAX_NOTIONAL else ''})")


def plan_block(label, r):
    bull = r['dir'] == 'bull'
    tf = '15m' if r['plan'] == 'scalp' else '1H'
    L = [f"**{label}, {side(r['dir'])}: {r['sym']}** ({'1H-aligned main group' if r['group'] == 'main' else 'countertrend paper group, half risk'}; levels approximate)", '',
         '| | |', '|---|---|',
         f"| What happened | {r['sweep']} → {r['disp']} → {r['brk']} → {r['gap']} |",
         f"| 1. Wait for | a pullback into **{g(r['zone'][0])}–{g(r['zone'][1])}** ({'touched ' + r['touched'] if r['touched'] else ('not touched; zone edge ' + str(abs(r['dist'])) + '% ' + ('below' if r['dist'] < 0 else 'above') + ' the current price' if r['dist'] is not None else 'not touched')}) |",
         f"| 2. Exact candle close needed | {r['need']} |",
         f"| Maximum entry (worst fill for 2:1 net) | **{g(r['worst'])}** |",
         f"| Stop | {g(r['stop'])} |",
         f"| TP1 / TP2 | {g(r['tp1'])} / {g(r['tp2'])}. Take 50% at TP1, then stop to break-even |",
         f"| Net R (mid-zone) | {r['netR'][0]} / {r['netR'][1]}; exactly 2.0 at the maximum entry |",
         f"| Cancel if | a {tf} close {'below' if bull else 'above'} {g(r['extreme'])}; an opposite {tf} break; price reaches TP1 first; the zone fills before confirmation; spread above the limit |",
         f"| Valid until | {r['expiry']} |",
         f"| Alert level | {g(r['zone'][1] if bull else r['zone'][0])} |",
         f"| Size | {size_line(r)} |"]
    if r['status'].startswith('CONFIRMED'):
        L.append('| READY NOW | Unavailable: live contract data missing (closed Binance candles and a fresh bid/ask can\'t be verified here) |')
    return '\n'.join(L)


def render(scalp_items, oneh_records, breadth, data_lines, unit='coins'):
    ok = [it for it in scalp_items if it.get('status') == 'ok']
    n_ok, n_total = len(ok), len(scalp_items)
    S = [from_scalp(it['sym'], s) for it in ok for s in it.get('seqs', [])]
    B = [from_1h(r) for r in oneh_records]
    out = ['| Plan | Direction | Result | Exact candle close needed | Entry range (zone edge → max entry) | Stop | TP1 / TP2 | Net R (mid) | Valid until |',
           '|---|---|---|---|---|---|---|---|---|']
    shown, closest = [], []
    for label, rows, d, lb in ((SCALP, S, 'bull', '24h'), (SCALP, S, 'bear', '24h'), (ONEH, B, 'bull', '72h'), (ONEH, B, 'bear', '72h')):
        txt, r = row_text(label, d, pick(rows, d, 'main'), n_ok, n_total, unit, lb)
        out.append(txt)
        if r is not None: (shown if r['status'] in QUALIFYING else closest).append((label, r))
    out += ['', f"1H trend: bearish on {breadth['bear']} of {breadth['n']} {unit}, bullish on {breadth['bull']}. "
                 'Both directions were checked in both plans. Countertrend setups (against the 1H trend for the scalp, against the 4H for the 1H plan) '
                 'are a separate paper group at half risk:', '',
            '| Countertrend paper group (half risk) | Direction | Result |', '|---|---|---|']
    for label, rows, d in ((SCALP, S, 'bull'), (SCALP, S, 'bear'), (ONEH, B, 'bull'), (ONEH, B, 'bear')):
        best, rs, c = pick(rows, d, 'countertrend')
        if best:
            out.append(f"| {label} | {side(d)} | **{best['status']}**: {best['sym']}, close needed: {best['need']}; max entry ≈ {g(best['worst'])}; "
                       f"stop ≈ {g(best['stop'])}; TP ≈ {g(best['tp1'])} / {g(best['tp2'])}; net R {best['netR'][1]}; valid until {best['expiry']} |")
            shown.append((label + ' (countertrend)', best))
        elif rs:
            out.append(f"| {label} | {side(d)} | {len(rs)} sequence(s), no qualifying setup. Closest: {c['sym']}, {c['status'].lower()}: {c['block']} |")
        else:
            out.append(f"| {label} | {side(d)} | no sequence |")
    if closest:
        out += ['', '**Closest setup in each empty row (evidence from the chart):**']
        for label, r in closest:
            out.append(f"- {label.split(' — ')[0]}, {side(r['dir'])}: **{r['sym']}**: {r['sweep']} → {r['disp']} → {r['brk']} → {r['gap']}. "
                       f"Blocked by: {r['block']}")
    for label, r in shown:
        out += ['', plan_block(label, r)]
    out += [''] + data_lines
    return '\n'.join(out)
