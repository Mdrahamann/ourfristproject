#!/usr/bin/env python3
"""Chronological paper backtest of CLAUDE.md v0.2 rules. Read-only; places no orders.

DATA LIMITS (stated in every report):
  * Binance contract candles are geo-blocked here (HTTP 451), so candles are PROXIES:
    crypto = Yahoo spot USD aggregate; stock-linked = underlying stock (US regular session only).
  * Fills are ESTIMATED from candle closes. Spread = latest observed CoinGecko snapshot, not history.
  * Funding = latest snapshot rate applied per 00/08/16 UK crossing (estimate).
  * Scheduled-news calendar unavailable -> N1 tested only as a fixed-time proxy (08:15-09:00 New York, weekdays).
Rules are frozen before the run: development period < --split <= test period. Nothing is tuned.
"""
import argparse, bisect, datetime as dt, json, os, sys, time, urllib.request
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scanner'))
from smc_core import analyse, worst_fill  # noqa: E402

UK, NY, UTC = ZoneInfo('Europe/London'), ZoneInfo('America/New_York'), dt.timezone.utc
ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--balance', type=float, default=1000.0, help='starting account balance (placeholder until provided)')
ap.add_argument('--split', default='2026-10-21', help='UK date: dev < split <= test')
ap.add_argument('--refetch', action='store_true')
A = ap.parse_args()
os.makedirs(os.path.join(A.out, 'cache'), exist_ok=True)

CFG = dict(risk_main=0.0025, risk_ct=0.00125, max_notional=1000.0, min_notional=5.0,  # min notional: ASSUMED $5
           fee_taker=0.0005,          # ESTIMATE: Binance USDT-M VIP0 taker, both entry and exit (fee tier unconfirmed)
           slip=0.0002,               # ESTIMATE per market fill
           day_loss_cap=0.005, max_losses=2, time_stop_5m=48, expiry_15m=16, confirm_window_5m=12,
           min_stop_pct=0.003, min_net_R=2.0, sweep_window=16, max_age=400)
CRYPTO = {'BTCUSDT': 'BTC-USD', 'ETHUSDT': 'ETH-USD', 'ZECUSDT': 'ZEC-USD', 'SOLUSDT': 'SOL-USD', 'XRPUSDT': 'XRP-USD',
          'HYPEUSDT': 'HYPE32196-USD', '1000PEPEUSDT': 'PEPE24478-USD', 'NEARUSDT': 'NEAR-USD', 'DOGEUSDT': 'DOGE-USD',
          'BNBUSDT': 'BNB-USD', 'UNIUSDT': 'UNI7083-USD', 'ENAUSDT': 'ENA-USD', 'AVAXUSDT': 'AVAX-USD',
          'SUIUSDT': 'SUI20947-USD', 'AAVEUSDT': 'AAVE-USD', 'TRXUSDT': 'TRX-USD', 'LINKUSDT': 'LINK-USD',
          'LTCUSDT': 'LTC-USD', 'BCHUSDT': 'BCH-USD', 'WLDUSDT': 'WLD-USD', 'TAOUSDT': 'TAO22974-USD'}
STOCKS = {s + 'USDT': s for s in 'SPCX MU SNDK GOOGL INTC QQQ CRCL MSTR AAPL TSLA NBIS SPY META AVGO AMD MSFT NVDA'.split()}
OPEN = urllib.request.build_opener(urllib.request.ProxyHandler({'https': os.environ['HTTPS_PROXY']}))
NOW = time.time()


def get_json(url):
    return json.loads(OPEN.open(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read())


def candles(ysym, interval, rng, sec, aligned):
    path = os.path.join(A.out, 'cache', f'{ysym}_{interval}.json')
    if os.path.exists(path) and not A.refetch:
        return json.load(open(path))
    d = get_json(f'https://query1.finance.yahoo.com/v8/finance/chart/{ysym}?interval={interval}&range={rng}')['chart']['result'][0]
    q = d['indicators']['quote'][0]
    rows = [(t, o, h, l, c) for t, o, h, l, c in zip(d['timestamp'], q['open'], q['high'], q['low'], q['close'])
            if None not in (o, h, l, c) and t + sec <= NOW and (t % sec == 0 or not aligned)]
    json.dump(rows, open(path, 'w'))
    return rows


def _safe(fn, *a):
    try: return fn(*a)
    except Exception as e: return str(e)


def ukdt(ts): return dt.datetime.fromtimestamp(ts, UK)
def nydt(ts): return dt.datetime.fromtimestamp(ts, NY)


def blackout(ts, kind, proxy_news=True):
    """Return the name of the blocking window at entry time ts, or None."""
    u, n = ukdt(ts), nydt(ts)
    um = u.hour * 60 + u.minute
    for fh in (0, 8, 16):                                    # N2 funding T-10/+5
        fm = fh * 60
        if fm - 10 <= um < fm + 5 or (fh == 0 and um >= 24 * 60 - 10):
            return 'N2 funding'
    if 7 * 60 + 45 <= um < 8 * 60 + 15: return 'N3 07:45-08:15'
    nm = n.hour * 60 + n.minute
    if n.weekday() < 5 and 9 * 60 + 15 <= nm < 9 * 60 + 45: return 'N3 US open'
    if proxy_news and n.weekday() < 5 and 8 * 60 + 15 <= nm < 9 * 60: return 'N1-proxy 08:30 NY data'
    if kind == 'stock' and not (9 * 60 + 45 <= nm < 15 * 60 + 30): return 'L3 outside US session'
    return None


def funding_crossings(t0, t1):
    c, d = 0, ukdt(t0).replace(minute=0, second=0, microsecond=0)
    while d.timestamp() <= t1:
        if d.hour in (0, 8, 16) and t0 < d.timestamp() <= t1: c += 1
        d += dt.timedelta(hours=1)
    return c


def bias_at(h1_breaks, ts):
    i = bisect.bisect_right([b[0] for b in h1_breaks], ts) - 1
    return h1_breaks[i][1] if i >= 0 else None


def sim_symbol(sym, kind, m5, m15, h1, m1, spread_pct):
    hs = (spread_pct or 0.02) / 200.0                     # half-spread fraction (snapshot)
    c_e = CFG['fee_taker'] + hs + CFG['slip']             # market entry
    c_tp = CFG['fee_taker'] + hs                          # TP exit, taker ESTIMATE, no slippage
    c_s = CFG['fee_taker'] + hs + CFG['slip']             # stop / time / BE exit
    r15 = analyse(m15, 2, 900, max_age=CFG['max_age'], fvg_state=False)
    r5 = analyse(m5, 2, 300, max_age=CFG['max_age'], fvg_state=False)
    r1 = analyse(h1, 3, 3600, max_age=CFG['max_age'], fvg_state=False)
    h1sec = 3600
    h1_breaks = sorted((e['t'] + h1sec, e['dir']) for e in r1['events'] if e['ev'] in ('BOS', 'CHoCH'))
    brks15 = [e for e in r15['events'] if e['ev'] in ('BOS', 'CHoCH')]
    sw15 = [s for s in r15['swings']]
    sw5 = {k: sorted(((s['known_at'], s['price']) for s in r5['swings'] if s['kind'] == k)) for k in 'HL'}
    sw5k = {k: [x[0] for x in v] for k, v in sw5.items()}
    t5 = [r[0] for r in m5]
    end15 = {r[0] + 900: r for r in m15}
    m1i = {r[0]: r for r in m1}
    out, seen = [], set()
    for s in [e for e in r15['events'] if e['ev'] == 'sweep']:
        d = s['dir']
        brk = next((e for e in brks15 if e['dir'] == d and s['i'] <= e['i'] <= s['i'] + CFG['sweep_window']), None)
        if not brk: continue
        disp = next((e for e in r15['events'] if e['ev'] == 'displacement' and e['dir'] == d and s['i'] <= e['i'] <= brk['i']), None)
        if not disp: continue
        fv = [f for f in r15['fvgs'] if f['dir'] == d and s['i'] <= f['i'] <= brk['i'] + 2]
        if not fv: continue
        f = next((z for z in fv if z['t'] == disp['t']), None) or max(fv, key=lambda z: z['hi'] - z['lo'])
        if (d, f['i']) in seen: continue
        seen.add((d, f['i']))
        ci = max(brk['i'], f['i'])
        Tc = m15[ci][0] + 900
        bars = m15[s['i'] + 1: ci + 1]
        if any((d == 'bear' and b[4] > s['extreme']) or (d == 'bull' and b[4] < s['extreme']) for b in bars): continue
        if any((d == 'bull' and b[3] <= f['lo']) or (d == 'bear' and b[2] >= f['hi']) for b in m15[f['i'] + 1: ci + 1]): continue
        if any(e['dir'] != d and brk['i'] < e['i'] <= ci for e in brks15): continue
        bias = bias_at(h1_breaks, Tc)
        group = 'main' if bias == d else 'ct'
        # targets (T1/T2): untaken confirmed 15m swings known by Tc, beyond the zone; capped by opposing unfilled FVG (T2)
        kind_t = 'H' if d == 'bull' else 'L'
        cand = []
        for w in sw15:
            if w['kind'] != kind_t or w['known_at'] > Tc or w['i'] < ci - CFG['max_age']: continue
            later = m15[w['i'] + 1: ci + 1]
            if d == 'bull' and w['price'] > f['hi'] and all(r[2] < w['price'] for r in later): cand.append(w['price'])
            if d == 'bear' and w['price'] < f['lo'] and all(r[3] > w['price'] for r in later): cand.append(w['price'])
        opp = [z for z in r15['fvgs'] if z['dir'] != d and z['known_at'] <= Tc and ci - CFG['max_age'] <= z['i'] < ci
               and not any((z['dir'] == 'bear' and r[2] >= z['hi']) or (z['dir'] == 'bull' and r[3] <= z['lo']) for r in m15[z['i'] + 1: ci + 1])]
        if d == 'bull':
            caps = [z['lo'] for z in opp if z['lo'] > f['hi']]
            cap = min(caps) if caps else None
            tg = sorted(set(min(p, cap) if cap else p for p in cand))
        else:
            caps = [z['hi'] for z in opp if z['hi'] < f['lo']]
            cap = max(caps) if caps else None
            tg = sorted(set(max(p, cap) if cap else p for p in cand), reverse=True)
        rec = dict(sym=sym, kind=kind, dir=d, group=group, bias=bias, setup_t=Tc, zone=(f['lo'], f['hi']),
                   sweep_t=s['t'], extreme=s['extreme'], status=None)
        if not tg:
            rec['status'] = 'no_target'; out.append(rec); continue
        tp1, tp2 = tg[0], (tg[1] if len(tg) > 1 else tg[0])
        a15 = r15['atr'][ci]
        buf = max(0.001 * s['extreme'], 0.25 * a15)
        stop = s['extreme'] - buf if d == 'bull' else s['extreme'] + buf
        rec.update(tp1=tp1, tp2=tp2, stop=stop)
        expiry = f['known_at'] + CFG['expiry_15m'] * 900
        j0 = bisect.bisect_left(t5, Tc)
        touched, entry_j = None, None
        for j in range(j0, len(m5)):
            t, o, h, l, c = m5[j]
            E = t + 300
            if E > expiry: rec['status'] = 'expired'; break
            if E in end15:
                cb = end15[E][4]
                if (d == 'bull' and cb < s['extreme']) or (d == 'bear' and cb > s['extreme']): rec['status'] = 'invalidated'; break
            if any(e['dir'] != d and e['t'] > brk['t'] and e['t'] + 900 <= E for e in brks15): rec['status'] = 'conflict'; break
            if (d == 'bull' and h >= tp1) or (d == 'bear' and l <= tp1): rec['status'] = 'tp1_before_entry'; break
            if touched is None and ((d == 'bull' and l <= f['hi']) or (d == 'bear' and h >= f['lo'])): touched = j
            if touched is not None:
                if (d == 'bull' and l < f['lo']) or (d == 'bear' and h > f['hi']): rec['status'] = 'zone_filled'; break
                if j - touched > CFG['confirm_window_5m']: rec['status'] = 'no_confirmation'; break
                kk = 'H' if d == 'bull' else 'L'
                ix = bisect.bisect_right(sw5k[kk], t) - 1          # swings confirmed before this candle opened
                if ix >= 0:
                    ref = sw5[kk][ix][1]
                    if (d == 'bull' and c > ref) or (d == 'bear' and c < ref):
                        rec.update(confirm_t=E, confirm_close=c, confirm_level=ref)
                        entry_j = j
                        break
        if entry_j is None:
            if rec['status'] is None: rec['status'] = 'end_of_data'
            out.append(rec); continue
        entry, E = m5[entry_j][4], m5[entry_j][0] + 300
        W = worst_fill(d, tp2, stop, c_e, c_tp, c_s, CFG['min_net_R'])
        rec.update(entry=entry, entry_t=E, worst_fill=W)
        if (d == 'bull' and entry > W) or (d == 'bear' and entry < W): rec['status'] = 'missed_worst_fill'; out.append(rec); continue
        if (d == 'bull' and stop >= entry) or (d == 'bear' and stop <= entry): rec['status'] = 'bad_stop'; out.append(rec); continue
        if abs(entry - stop) / entry < CFG['min_stop_pct']: rec['status'] = 'stop_too_tight'; out.append(rec); continue
        rec['blackout'] = blackout(E, kind, True)
        rec['blackout_nonews'] = blackout(E, kind, False)
        # manage the trade on 5m bars (estimated fills)
        sgn = 1 if d == 'bull' else -1
        legs, cur_stop, rem, tp1_done, amb = [], stop, 1.0, tp1 == tp2, False
        tgt = tp2 if tp1_done else tp1
        for k in range(entry_j + 1, len(m5)):
            t, o, h, l, c = m5[k]
            Ek = t + 300
            hit_stop = (l <= cur_stop) if d == 'bull' else (h >= cur_stop)
            hit_tgt = (h >= tgt) if d == 'bull' else (l <= tgt)
            if hit_stop and hit_tgt:
                order = None
                sub = [m1i.get(t + 60 * x) for x in range(5)]
                if all(sub):
                    for b in sub:
                        bs = (b[3] <= cur_stop) if d == 'bull' else (b[2] >= cur_stop)
                        bt_ = (b[2] >= tgt) if d == 'bull' else (b[3] <= tgt)
                        if bs and bt_: break
                        if bs: order = 'stop'; break
                        if bt_: order = 'tgt'; break
                if order is None: amb = True; order = 'stop'          # conservative: stop first
                hit_stop, hit_tgt = order == 'stop', order == 'tgt'
            if hit_stop:
                legs.append((rem, cur_stop, Ek, 'BE' if tp1_done and cur_stop == entry else 'stop')); rem = 0; break
            if hit_tgt:
                if not tp1_done:
                    legs.append((0.5, tp1, Ek, 'TP1')); rem = 0.5; tp1_done = True; cur_stop = entry; tgt = tp2
                    continue
                legs.append((rem, tp2, Ek, 'TP2')); rem = 0; break
            ny = nydt(Ek)
            if kind == 'stock' and (ny.hour * 60 + ny.minute) >= 15 * 60 + 55:
                legs.append((rem, c, Ek, 'session_close')); rem = 0; break
            if k - entry_j >= CFG['time_stop_5m']:
                legs.append((rem, c, Ek, 'time_stop')); rem = 0; break
        if rem > 0:
            legs.append((rem, m5[-1][4], m5[-1][0] + 300, 'end_of_data'))
        rec.update(status='filled', legs=legs, ambiguous=amb, c_e=c_e, c_tp=c_tp, c_s=c_s,
                   tp1_hit=any(x[3] == 'TP1' for x in legs) or (tp1 == tp2 and any(x[3] == 'TP2' for x in legs)))
        out.append(rec)
    return out


def portfolio(sigs, group, use_news_blackout, B0, period, funding):
    """Apply session stop, concurrency, sizing ($1,000 max notional), costs. Returns trades + day table."""
    sigs = sorted([s for s in sigs if s['status'] == 'filled' and s['group'] == group and s['period'] == period],
                  key=lambda s: s['entry_t'])
    rf = CFG['risk_main'] if group == 'main' else CFG['risk_ct']
    risk_usd = rf * B0
    open_pos, trades, skipped = [], [], {}
    day = {}
    equity = B0

    def realize(upto):
        nonlocal equity
        for p in sorted([p for p in open_pos if p['exit_t'] <= upto], key=lambda p: p['exit_t']):
            open_pos.remove(p)
            dk = ukdt(p['exit_t']).date()
            st = day.setdefault(dk, dict(start=equity, pnl=0.0, losses=0, trades=0))
            st['pnl'] += p['pnl']; st['trades'] += 1
            if p['pnl'] < 0: st['losses'] += 1
            equity += p['pnl']
    for s in sigs:
        realize(s['entry_t'])
        bk = s['blackout'] if use_news_blackout else s['blackout_nonews']
        if bk: skipped[bk] = skipped.get(bk, 0) + 1; continue
        dk = ukdt(s['entry_t']).date()
        st = day.setdefault(dk, dict(start=equity, pnl=0.0, losses=0, trades=0))
        if st['losses'] >= CFG['max_losses'] or st['pnl'] <= -CFG['day_loss_cap'] * st['start']:
            skipped['session_stop'] = skipped.get('session_stop', 0) + 1; continue
        if any(p['sym'] == s['sym'] or p['dir'] == s['dir'] for p in open_pos):
            skipped['concurrency'] = skipped.get('concurrency', 0) + 1; continue
        e, stp = s['entry'], s['stop']
        per_unit = abs(e - stp) + e * s['c_e'] + stp * s['c_s']
        qty = min(risk_usd / per_unit, CFG['max_notional'] / e)
        if qty * e < CFG['min_notional']:
            skipped['below_min_notional'] = skipped.get('below_min_notional', 0) + 1; continue
        sgn = 1 if s['dir'] == 'bull' else -1
        pnl = -qty * e * s['c_e']
        fr = (funding.get(s['sym']) or 0) / 100.0
        for frac, px, tx, typ in s['legs']:
            cost = s['c_tp'] if typ in ('TP1', 'TP2') else s['c_s']
            pnl += frac * qty * (sgn * (px - e) - px * cost)
            pnl -= sgn * fr * frac * qty * e * funding_crossings(s['entry_t'], tx)
        exit_t = max(x[2] for x in s['legs'])
        p = dict(sym=s['sym'], dir=s['dir'], kind=s['kind'], entry_t=s['entry_t'], exit_t=exit_t, entry=e, stop=stp,
                 qty=qty, notional=qty * e, risk_usd=risk_usd, pnl=pnl, R=pnl / risk_usd, tp1_hit=s['tp1_hit'],
                 ambiguous=s['ambiguous'], exits='/'.join(x[3] for x in s['legs']))
        open_pos.append(p); trades.append(p)
    realize(float('inf'))
    return trades, day, skipped


def metrics(trades, day, days_in_period):
    n = len(trades)
    if not n:
        return dict(trades=0, days=days_in_period)
    eq, peak, mdd, mddR, cumR, peakR = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    for t in sorted(trades, key=lambda t: t['exit_t']):
        eq += t['pnl']; cumR += t['R']
        peak, peakR = max(peak, eq), max(peakR, cumR)
        mdd, mddR = max(mdd, peak - eq), max(mddR, peakR - cumR)
    dp = [day[d]['pnl'] for d in day]
    return dict(trades=n, tp1_before_stop=sum(t['tp1_hit'] for t in trades) / n, net_win=sum(t['pnl'] > 0 for t in trades) / n,
                avgR=sum(t['R'] for t in trades) / n, totR=sum(t['R'] for t in trades), net_usd=sum(t['pnl'] for t in trades),
                maxDD_usd=mdd, maxDD_R=mddR, ambiguous=sum(t['ambiguous'] for t in trades),
                days=days_in_period, days_traded=sum(1 for d in day if day[d]['trades']),
                days_20_30=sum(1 for x in dp if 20 <= x <= 30), days_ge_20=sum(1 for x in dp if x >= 20),
                alerts_per_day=n / days_in_period, best_day=max(dp) if dp else 0, worst_day=min(dp) if dp else 0)


def main():
    cg = get_json('https://api.coingecko.com/api/v3/derivatives?include_tickers=unexpired')
    b = {x['symbol']: x for x in cg if x.get('market') == 'Binance (Futures)' and x.get('contract_type') == 'perpetual'}
    spread = {k: (b.get(k) or {}).get('spread') for k in list(CRYPTO) + list(STOCKS)}
    funding = {k: (b.get(k) or {}).get('funding_rate') for k in list(CRYPTO) + list(STOCKS)}
    split = dt.datetime.strptime(A.split, '%Y-%m-%d').date()
    sigs, coverage, dates = [], {}, {}
    import concurrent.futures as cf
    jobs = [(y, iv, rg, sec, sym in CRYPTO) for sym, y in list(CRYPTO.items()) + list(STOCKS.items())
            for iv, rg, sec in (('5m', '60d', 300), ('15m', '60d', 900), ('1h', '730d', 3600), ('1m', '7d', 60))]
    with cf.ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda j: _safe(candles, *j), jobs))
    for sym, y in list(CRYPTO.items()) + list(STOCKS.items()):
        kind = 'crypto' if sym in CRYPTO else 'stock'
        try:
            m5 = candles(y, '5m', '60d', 300, kind == 'crypto')
            m15 = candles(y, '15m', '60d', 900, kind == 'crypto')
            h1 = candles(y, '1h', '730d', 3600, kind == 'crypto')
            m1 = candles(y, '1m', '7d', 60, kind == 'crypto')
        except Exception as e:
            coverage[sym] = f'UNAVAILABLE {str(e)[:50]}'; continue
        if len(m5) < 500:
            coverage[sym] = f'UNAVAILABLE only {len(m5)} 5m bars'; continue
        coverage[sym] = f"{ukdt(m5[0][0]):%d %b %H:%M} -> {ukdt(m5[-1][0] + 300):%d %b %H:%M} ({len(m5)} 5m bars)"
        dates.setdefault(kind, set()).update(ukdt(r[0]).date() for r in m5)
        for r in sim_symbol(sym, kind, m5, m15, h1, m1, spread.get(sym)):
            ref_t = r.get('entry_t') or r['setup_t']
            r['period'] = 'dev' if ukdt(ref_t).date() < split else 'test'
            sigs.append(r)
    json.dump(dict(cfg=CFG, coverage=coverage, sigs=sigs), open(os.path.join(A.out, 'signals.json'), 'w'), default=str)
    ndays = {k: {'dev': sum(1 for d in v if d < split), 'test': sum(1 for d in v if d >= split)} for k, v in dates.items()}
    rep = dict(run_uk=f"{ukdt(NOW):%a %d %b %Y %H:%M:%S %Z}", balance_placeholder=A.balance, split=A.split, days=ndays,
               coverage=coverage, funnel={}, results={})
    for kind in ('crypto', 'stock'):
        for period in ('dev', 'test'):
            ss = [s for s in sigs if s['kind'] == kind and s['period'] == period]
            for grp in ('main', 'ct'):
                f = {}
                for s in ss:
                    if s['group'] == grp: f[s['status']] = f.get(s['status'], 0) + 1
                rep['funnel'][f'{kind}/{period}/{grp}'] = f
                for news in (True, False):
                    tr, day, sk = portfolio([s for s in ss], grp, news, A.balance, period, funding)
                    m = metrics(tr, day, ndays[kind][period])
                    m['skipped'] = sk
                    rep['results'][f"{kind}/{period}/{grp}/{'blackout' if news else 'no_news_blackout'}"] = m
                    if news:
                        with open(os.path.join(A.out, f'trades_{kind}_{period}_{grp}.json'), 'w') as fh:
                            json.dump(tr, fh, default=str)
    json.dump(rep, open(os.path.join(A.out, 'report.json'), 'w'), indent=1, default=str)
    print(json.dumps(rep, indent=1, default=str))


if __name__ == '__main__':
    main()
