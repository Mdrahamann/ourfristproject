#!/usr/bin/env python3
"""Re-run the restored crypto scanner (original scalp + separate 1H plan) AS OF many past times on 11 Nov, offline.
Read-only; no orders. Shortlist and liquidity for each time come from the nearest saved scan (raw CoinGecko
snapshots were not saved, so between scans this is approximate). Candles: cached Yahoo spot (proxy).
Usage: python3 replay_original_asof.py SAVED_SCANS_DIR CACHE_DIR OUT_DIR [step_minutes]
Writes OUT_DIR/summary.json: per time, the four main rows and the countertrend rows (status, symbol, reason)."""
import datetime as dt, glob, json, os, sys
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'scanner'))
import asof_harness as H  # noqa: E402
from scalp_status import QUALIFYING  # noqa: E402

UK = ZoneInfo('Europe/London')
saved, cache, out = sys.argv[1:4]
step = int(sys.argv[4]) if len(sys.argv) > 4 else 15
SCANNER = os.path.join(HERE, '..', 'scanner', 'smc_scan.py')
scans = []
for d in sorted(glob.glob(f'{saved}/run1111*')):
    try:
        j = json.load(open(f'{d}/scan.json'))
    except Exception:
        continue
    if len(j['symbols']) >= 20:
        t = dt.datetime.strptime(j['scan_time_uk'][:24], '%a %d %b %Y %H:%M:%S').replace(tzinfo=UK).timestamp()
        scans.append((t, f'{d}/scan.json'))
day0 = dt.datetime(2026, 11, 11, tzinfo=UK).timestamp()
times = sorted(set([day0 + 60 * m for m in range(0, 20 * 60, step)] + [t for t, _ in scans]))
res = []
for T in times:
    src = max([s for s in scans if s[0] <= T], default=scans[0])[1]
    o = f'{out}/{dt.datetime.fromtimestamp(T, UK):%H%M%S}'
    H.run(SCANNER, o, T, H.cg_from_scan(src, T), cache)
    j = json.load(open(f'{o}/scan.json'))
    seqs = [(it['sym'], s) for it in j['symbols'] if it.get('status') == 'ok' for s in it['seqs']]
    rows = []
    for sym, s in seqs:
        rows.append(dict(plan='scalp', sym=sym, dir=s['dir'], group='main' if s['group'].startswith('main') else 'countertrend',
                         status=s['plan_status'], block=s.get('block'), t_conf=s.get('t_conf'), t_fill=s.get('t_fill'),
                         zone=(s.get('fvg') or {}).get('lo'), sweep=s['sweep']['bar'], netR=s.get('net_R_t2', s.get('net_R_t1')), worst=s.get('worst_fill'),
                         conf=s.get('confirm5m')))
    for r in j['plans']:
        rows.append(dict(plan='1h', sym=r['sym'], dir=r['dir'], group=r['group'], status=r['status'], sweep=r['sweep']['t'],
                         netR=(r.get('netR_ce') or [None, None])[1], worst=r.get('worst_fill'), conf=r.get('conf'), fill=r.get('fill')))
    res.append(dict(T=T, uk=dt.datetime.fromtimestamp(T, UK).strftime('%H:%M:%S'), src=os.path.basename(os.path.dirname(src)),
                    n_ok=sum(it.get('status') == 'ok' for it in j['symbols']), rows=rows,
                    qualifying=[r for r in rows if r['status'] in QUALIFYING]))
    print(res[-1]['uk'], res[-1]['n_ok'], [(r['plan'], r['sym'], r['dir'], r['group'], r['status']) for r in res[-1]['qualifying']], flush=True)
json.dump(res, open(f'{out}/summary.json', 'w'), default=str)
