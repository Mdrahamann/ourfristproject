"""Original scalp plan: 15m setup, 5m candle-close confirmation. Read-only; no orders.

This is the ORIGINAL scanner logic, moved here VERBATIM from trading/scanner/smc_scan.py as it was at commit 01d5743
(11 Nov 03:16, the last version before the separate 1H plan was added). Only two things changed in the move:
  * the code now sits in a function, so both the crypto and the stock-linked scanners can call it;
  * the clock (NOW), the 1H bias, the last 15m close and the spread are passed in instead of read from globals.
Do NOT edit the rules here without the user's approval (CLAUDE.md §18). Status labels (WAIT FOR TRIGGER, MISSED...)
are added on top of these results in scalp_status.py; nothing in this file was changed to produce them."""
import datetime as dt
from zoneinfo import ZoneInfo
from smc_core import worst_fill

UK = ZoneInfo('Europe/London')
FEE_TAKER = 0.0005      # Binance USDT-M VIP0 taker ESTIMATE, per side (fee tier unconfirmed)
SLIPPAGE = 0.0002       # per side, assumption for liquid contracts


def ukd(ts): return dt.datetime.fromtimestamp(ts, UK).strftime('%d %b %H:%M')

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

def setup_15m(r15, rows15, r5, rows5, sec15, keep=()):
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
        # ADDED 12 Nov (only when `keep` is given): a sequence already shown to the user keeps being tracked until
        # its own cancel condition, even if a newer sweep on the same coin becomes the "best" one. Default: unchanged.
        if seqs and keep:
            res += [z[1] for z in seqs if z[1]['sweep']['t'] in keep and z[1] is not res[-1]]
    return res

def confirm_5m(r5, d, after_t):
    return next((e for e in r5['events'] if e['ev'] in ('BOS', 'CHoCH') and e['dir'] == d and e['t'] >= after_t), None)


def scalp_sequences(m15, m5, h1, bias1h, spread, now, r15=None, r5=None, keep=()):
    """Original 15m/5m scalp for one contract: at most one sequence per direction (best live one), with the
    original zone, 5m trigger reference, stop, targets (untaken 15m AND 1H swings), net R and worst fill."""
    NOW = now
    if r15 is None: r15 = analyse(m15, 2, 900)
    if r5 is None: r5 = analyse(m5, 2, 300)
    a15 = r15['atr'][-1]
    item = {'last15': m15[-1][4], 'ctx1h': {'bias': bias1h}}
    x = {'spread': spread}
    seqs = []
    for s in setup_15m(r15, m15, r5, m5, 900, keep):
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
            out['expiry'] = ukd(f['known_at'] + 16 * 900)            # E2 [PROPOSED]: 16 x 15m after the FVG became known
            out['expired'] = NOW > f['known_at'] + 16 * 900
            kk = 'H' if s['dir'] == 'bull' else 'L'                  # C2: last confirmed 5m swing (current reference)
            ref = max((w for w in r5['swings'] if w['kind'] == kk and w['known_at'] <= NOW), key=lambda w: w['known_at'], default=None)
            out['trigger_ref'] = dict(price=ref['price'], swing_t=ukd(ref['t']), known_at=ukd(ref['known_at'])) if ref else None
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
                         ('Watch (conflict)' if opp else 'Expired' if out.get('expired') else 'Watch (zone distant)' if out.get('dist_atr1h', 0) > 3 else 'Candidate') if complete else 'Watch')
        bias1h = item['ctx1h']['bias']
        out['group'] = 'main (1H aligned)' if bias1h == s['dir'] else 'countertrend (half risk, separate paper group)'
        out['missing'] = [n for n, v in (('BOS/CHoCH', s['brk']), ('displacement', s['disp']), ('unfilled FVG', out['fvg'])) if not v]
        seqs.append(out)
    return seqs
