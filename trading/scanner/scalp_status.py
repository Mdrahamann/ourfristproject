"""Status labels and conditional entry plans for the ORIGINAL scalp (scalp_original.py). Read-only; no orders.
Applies the CLAUDE.md entry rules that used to be applied by hand in chat on top of the original scanner output:
R3 2:1 net (worst acceptable fill), SL3 stop >= 0.30%, E3 TP1 reached before entry, C2 5m close, E1 5-minute
READY NOW window. It does not change how setups, zones, stops or targets are found."""
import datetime as dt
from zoneinfo import ZoneInfo
from scalp_original import swings

UK = ZoneInfo('Europe/London')
ENTRY_WINDOW = 300          # E1: 5 minutes after the confirming 5m close [PROPOSED]
QUALIFYING = ('CONFIRMED (in entry window)', 'CONFIRMED (needs pullback to worst fill)', 'WAIT FOR TRIGGER (in zone)', 'WAIT FOR TRIGGER')


def ts(s, now):
    """Parse the original scanner's 'dd Mon HH:MM' UK strings back to a timestamp."""
    if not s: return None
    y = dt.datetime.fromtimestamp(now, UK).year
    t = dt.datetime.strptime(f'{y} {s}', '%Y %d %b %H:%M').replace(tzinfo=UK).timestamp()
    return t - 365 * 86400 if t > now + 86400 else t


def hm(t):
    return dt.datetime.fromtimestamp(t, UK).strftime('%a %H:%M') if t else '—'


def tp1_when_set(d, m15, h1, sw15, mid, t0):
    """E3 reference: TP1 as it stood when the setup became complete (same pool as the original: untaken 15m and 1H swings)."""
    bull = d == 'bull'
    closed = [r for r in m15 if r[0] + 900 <= t0]
    last = closed[-1][4] if closed else mid
    pool = []
    for w, rows, sec in [(w, m15, 900) for w in sw15] + [(w, h1, 3600) for w in swings(h1, 3, 3600)]:
        if w['kind'] != ('H' if bull else 'L') or w['known_at'] > t0: continue
        later = [r for r in rows[w['i'] + 1:] if r[0] + sec <= t0]
        if bull and all(r[2] < w['price'] for r in later) and w['price'] > max(mid, last): pool.append(w['price'])
        if not bull and all(r[3] > w['price'] for r in later) and w['price'] < min(mid, last): pool.append(w['price'])
    return (min(pool) if bull else max(pool)) if pool else None


def label(s, m5, m15, h1, sw15, now):
    """Add 'plan_status', 'block' (first blocking rule, with value/time) and timestamps to one original sequence."""
    bull = s['dir'] == 'bull'
    f = s.get('fvg') or {}
    s['t_touch'] = ts(f.get('touched'), now)
    s['t_expiry'] = ts(s.get('expiry'), now)
    st = s['status']
    if st == 'Invalidated':
        s['plan_status'], s['block'] = 'Invalidated', f"15m close {'below' if bull else 'above'} the sweep extreme {s['sweep']['extreme']:.6g} ({s['invalidated']})"
        return s
    if st == 'Watch (conflict)':
        s['plan_status'], s['block'] = 'Conflict', s['conflict']
        return s
    if st == 'Expired':
        s['plan_status'], s['block'] = 'Expired', f"plan expired {s['expiry']} (16 × 15m after the price gap was known)"
        return s
    if st == 'Watch (zone distant)':
        s['plan_status'], s['block'] = 'Watch (zone distant)', f"zone {s['dist_pct']}% away (> 3 × 1H ATR)"
        return s
    if st != 'Candidate':
        miss = ['structure break' if m == 'BOS/CHoCH' else 'strong candle' if m == 'displacement' else 'unfilled price gap (none, or filled)' for m in s['missing']]
        s['plan_status'], s['block'] = 'Watch', 'missing ' + ', '.join(miss)
        # one step away: sweep + strong candle + price gap exist, only the 15m break is missing, still inside 16 bars
        if s['missing'] == ['BOS/CHoCH'] and s.get('fvg') and s.get('disp'):
            deadline = ts(s['sweep']['bar'], now) + 17 * 900          # close of the 16th 15m bar after the sweep bar
            known = [w for w in sw15 if w['kind'] == ('H' if bull else 'L') and w['known_at'] <= now]
            if known and deadline > now:
                w = max(known, key=lambda w: w['known_at'])            # the swing the original scanner breaks against
                done = any((bull and r[4] > w['price']) or (not bull and r[4] < w['price'])
                           for r in m15 if r[0] >= w['known_at'] and r[0] + 900 <= now)
                s['watch_break'] = dict(level=w['price'], swing_t=w['t'], deadline=deadline, needs_new_swing=done)
        return s
    W, lo, hi = s.get('worst_fill'), f['lo'], f['hi']
    if not s.get('targets'):
        s['plan_status'], s['block'] = 'No untaken target', 'no untaken 15m/1H swing beyond the zone'
        return s
    if s['risk_pct'] < 0.30:
        s['plan_status'], s['block'] = 'Stop too tight', f"stop distance {s['risk_pct']}% < 0.30% (SL3)"
        return s
    if (bull and W < lo) or (not bull and W > hi):
        s['plan_status'], s['block'] = 'Fails 2:1 net', (f"worst fill for 2:1 after costs is {W:.6g}, {'below' if bull else 'above'} the whole zone "
                                                          f"{lo:.6g}–{hi:.6g} (net R from mid-zone {s.get('net_R_t2', s.get('net_R_t1'))})")
        return s
    # E3: TP1 (as it stood when the setup completed) reached before the zone was retested
    t0 = max(ts(s['brk']['bar'], now) + 900, ts(f['known_at'], now))
    tp0 = tp1_when_set(s['dir'], m15, h1, sw15, s['entry_ce'], t0)
    end = s['t_touch'] if s['t_touch'] else now
    hit = next((r[0] + 900 for r in m15 if t0 <= r[0] and r[0] + 900 <= now and r[0] < end
                and ((bull and tp0 and r[2] >= tp0) or (not bull and tp0 and r[3] <= tp0))), None)
    if hit:
        s['plan_status'], s['block'] = 'MISSED (TP1 reached before entry)', f"price reached TP1 {tp0:.6g} at {hm(hit)} without retesting the zone (E3, don't chase)"
        return s
    c5 = s.get('confirm5m')
    if not s['t_touch']:
        s['plan_status'], s['block'] = 'WAIT FOR TRIGGER', None
        return s
    if not c5:
        s['plan_status'], s['block'] = 'WAIT FOR TRIGGER (in zone)', None
        return s
    tc = ts(c5['bar'], now) + 300                       # close time of the confirming 5m candle
    s['t_conf'] = tc
    inside = (bull and c5['close'] <= W) or (not bull and c5['close'] >= W)
    fill = tc if inside else next((r[0] for r in m5 if tc <= r[0] < tc + ENTRY_WINDOW and r[0] + 300 <= now
                                   and ((bull and r[3] <= W) or (not bull and r[2] >= W))), None)
    s['t_fill'] = fill
    if now < tc + ENTRY_WINDOW:
        s['plan_status'] = 'CONFIRMED (in entry window)' if fill else 'CONFIRMED (needs pullback to worst fill)'
        s['block'] = None
    elif fill:
        s['plan_status'], s['block'] = 'MISSED (entry window passed)', f"confirmed {hm(tc)} at {c5['close']:.6g}, inside the entry range; the 5-minute window closed {hm(tc + ENTRY_WINDOW)}"
    else:
        s['plan_status'], s['block'] = 'MISSED (confirmation beyond worst fill)', f"5m close {c5['close']:.6g} at {hm(tc)} was {'above' if bull else 'below'} the worst fill {W:.6g}, and price didn't pull back within 5 minutes"
    return s


RANK = {'CONFIRMED (in entry window)': 0, 'CONFIRMED (needs pullback to worst fill)': 1, 'WAIT FOR TRIGGER (in zone)': 2, 'WAIT FOR TRIGGER': 3,
        'MISSED (entry window passed)': 4, 'MISSED (confirmation beyond worst fill)': 5, 'MISSED (TP1 reached before entry)': 6,
        'Fails 2:1 net': 7, 'Stop too tight': 8, 'No untaken target': 9, 'Conflict': 10, 'Expired': 11, 'Watch (zone distant)': 12,
        'Watch': 13, 'Invalidated': 14}


def tracked(state_path, sym, now):
    """Sweep bar times of scalp setups shown on the previous scan for this contract (so they keep being tracked)."""
    import json, os
    if not state_path or os.environ.get('SCAN_NO_STATE') or not os.path.exists(state_path): return set()
    try: st = json.load(open(state_path))
    except Exception: return set()
    out = set()
    for k in st:
        plan, s, d, t = k.split('|', 3)
        if plan == 'scalp' and s == sym:
            try: out.add(ts(t, now))
            except ValueError: pass
    return out
