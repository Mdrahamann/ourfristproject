"""Shared SMC primitives (closed candles only, no look-ahead).
Rows are tuples (t_open_unix, o, h, l, c[, v]). Rules mirror CLAUDE.md ids S1, SW1, DP1, MS1, F1.
Thresholds are PROVISIONAL (CLAUDE.md marks them [PROPOSED])."""

DISP_ATR = 1.5      # DP1 range >= 1.5 x ATR14
DISP_BODY = 0.60    # DP1 body >= 60% of range
FVG_ATR = 0.10      # F1 min size 0.1 x ATR14


def atr(rows, n=14):
    out, trs = [], []
    for i, r in enumerate(rows):
        tr = r[2] - r[3] if i == 0 else max(r[2] - r[3], abs(r[2] - rows[i-1][4]), abs(r[3] - rows[i-1][4]))
        trs.append(tr)
        w = trs[-n:]
        out.append(sum(w) / len(w))
    return out


def swings(rows, n, sec):
    """S1 fractal swings; usable only from known_at = close of bar i+n."""
    out = []
    for i in range(n, len(rows) - n):
        h, l = rows[i][2], rows[i][3]
        if all(h > rows[j][2] for j in range(i-n, i)) and all(h >= rows[j][2] for j in range(i+1, i+n+1)):
            out.append(dict(kind='H', price=h, t=rows[i][0], i=i, known_i=i+n, known_at=rows[i+n][0] + sec))
        if all(l < rows[j][3] for j in range(i-n, i)) and all(l <= rows[j][3] for j in range(i+1, i+n+1)):
            out.append(dict(kind='L', price=l, t=rows[i][0], i=i, known_i=i+n, known_at=rows[i+n][0] + sec))
    return out


def analyse(rows, n, sec, max_age=None, fvg_state=True):
    """Walk bars in time; a swing is used only after it became knowable.
    Returns events (sweep / BOS / CHoCH / displacement), FVGs, swings, ATR, last break direction."""
    a = atr(rows)
    sw = sorted(swings(rows, n, sec), key=lambda s: s['known_i'])
    k, ref_h, ref_l, last_dir = 0, None, None, None
    untaken, events = [], []
    for i, r in enumerate(rows):
        t, o, h, l, c = r[:5]
        while k < len(sw) and sw[k]['known_i'] < i:
            s = sw[k]; k += 1; untaken.append(s)
            if s['kind'] == 'H': ref_h = s
            else: ref_l = s
        if max_age:
            untaken = [s for s in untaken if i - s['i'] <= max_age]
        rng, body = h - l, abs(c - o)
        if a[i] > 0 and rng >= DISP_ATR * a[i] and body >= DISP_BODY * rng:
            events.append(dict(ev='displacement', dir='bull' if c > o else 'bear', t=t, i=i, close=c))
        if ref_h and 'broken' not in ref_h and c > ref_h['price']:
            kind = 'CHoCH' if last_dir == 'bear' else 'BOS'
            events.append(dict(ev=kind, dir='bull', level=ref_h['price'], swing_t=ref_h['t'], swing_known=ref_h['known_at'], t=t, i=i, close=c))
            ref_h['broken'] = t; last_dir = 'bull'
        if ref_l and 'broken' not in ref_l and c < ref_l['price']:
            kind = 'CHoCH' if last_dir == 'bull' else 'BOS'
            events.append(dict(ev=kind, dir='bear', level=ref_l['price'], swing_t=ref_l['t'], swing_known=ref_l['known_at'], t=t, i=i, close=c))
            ref_l['broken'] = t; last_dir = 'bear'
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
    fv = []
    for i in range(2, len(rows)):
        A, C = rows[i-2], rows[i]
        if C[3] > A[2] and C[3] - A[2] >= FVG_ATR * a[i]:
            fv.append(dict(dir='bull', lo=A[2], hi=C[3], t=rows[i-1][0], i=i, known_at=C[0] + sec))
        if C[2] < A[3] and A[3] - C[2] >= FVG_ATR * a[i]:
            fv.append(dict(dir='bear', lo=C[2], hi=A[3], t=rows[i-1][0], i=i, known_at=C[0] + sec))
    if fvg_state:
        for f in fv:
            f['touched'] = f['filled'] = None
            for j in range(f['i'] + 1, len(rows)):
                t, o, h, l, c = rows[j][:5]
                if f['dir'] == 'bull':
                    if f['touched'] is None and l <= f['hi']: f['touched'] = t
                    if l <= f['lo']: f['filled'] = t; break
                else:
                    if f['touched'] is None and h >= f['lo']: f['touched'] = t
                    if h >= f['hi']: f['filled'] = t; break
    return dict(events=events, fvgs=fv, swings=sw, atr=a, last_dir=last_dir)


def worst_fill(direction, tp, sl, c_entry, c_tp, c_stop, min_r=2.0):
    """§10: worst acceptable fill so that net R to `tp` >= min_r.
    c_* are per-side cost fractions (fees + half-spread + slippage), counted once each."""
    k = min_r
    if direction == 'bull':
        return (tp * (1 - c_tp) + k * sl * (1 - c_stop)) / ((1 + k) * (1 + c_entry))
    return (tp * (1 + c_tp) + k * sl * (1 + c_stop)) / ((1 + k) * (1 - c_entry))
