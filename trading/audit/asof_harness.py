#!/usr/bin/env python3
"""Run a scanner script AS OF a past UK time, offline. Read-only; no orders.
* Clock: time.time() is frozen at T, so the scanner's own closed-candle rule (open_time + interval <= now) applies.
* Candles: served from a local cache of Yahoo chart responses, trimmed to the range the scanner asks for, ending at T.
* CoinGecko: rebuilt from the per-symbol values (price, index, OI, spread, funding, 24h volume/change) that the
  nearest saved scan logged. The raw CoinGecko snapshot was NOT saved per scan, so liquidity is approximate.
Usage: python3 asof_harness.py SCRIPT OUTDIR 'YYYY-MM-DD HH:MM:SS' CG_JSON CACHE_DIR"""
import datetime as dt, io, json, os, re, runpy, sys, time, urllib.request
from contextlib import redirect_stdout
from zoneinfo import ZoneInfo

RANGE_S = {'d': 86400}


def run(script, out, T, cg_list, cache_dir, quiet=True):
    real = time.time

    class Resp:
        def __init__(self, b): self.b = b
        def read(self): return self.b

    class Opener:
        def open(self, req, timeout=None):
            url = getattr(req, 'full_url', req)
            if 'coingecko' in url:
                return Resp(json.dumps(cg_list).encode())
            sym, iv, rng = re.search(r'chart/([^?]+)\?interval=(\w+)&range=(\w+)', url).groups()
            try:
                d = json.load(open(f'{cache_dir}/{sym}_{iv}.json'))
            except FileNotFoundError:
                raise OSError('HTTP Error 404: Not Found (no cached data)')
            r = d['chart']['result'][0]
            if not r.get('timestamp'):
                raise OSError('no candles in cached response')
            q = r['indicators']['quote'][0]
            lo = T - int(rng[:-1]) * RANGE_S[rng[-1]]
            keep = [i for i, t in enumerate(r['timestamp']) if lo <= t < T]
            nq = {k: [q[k][i] for i in keep] for k in ('open', 'high', 'low', 'close')}
            return Resp(json.dumps({'chart': {'result': [{'timestamp': [r['timestamp'][i] for i in keep],
                                                           'indicators': {'quote': [nq]}}]}}).encode())

    bo = urllib.request.build_opener
    urllib.request.build_opener = lambda *a, **k: Opener()
    time.time = lambda: T
    if not os.environ.get('SCAN_STATE_DIR'):
        os.environ['SCAN_NO_STATE'] = '1'      # never touch the live watch state from a replay
    argv = sys.argv
    sys.argv = [script, out]
    buf = io.StringIO()
    try:
        if quiet:
            with redirect_stdout(buf):
                runpy.run_path(script, run_name='__main__')
        else:
            runpy.run_path(script, run_name='__main__')
    finally:
        time.time = real; urllib.request.build_opener = bo; sys.argv = argv
    return buf.getvalue()


def cg_from_scan(scan_json, T, extra=()):
    """Rebuild the CoinGecko rows the scanner needs from a saved scan.json (shortlisted symbols only)."""
    j = json.load(open(scan_json))
    rows = []
    for s in list(j['symbols']) + list(extra):
        px = s.get('perp_price') or 0
        rows.append(dict(market='Binance (Futures)', contract_type='perpetual', symbol=s['sym'],
                         price=str(px if px > 0 else (s.get('index') or 0)), index=s.get('index'),
                         price_percentage_change_24h=s.get('chg24') or 0, volume_24h=s.get('vol24') or 0,
                         open_interest=s.get('oi'), funding_rate=s.get('funding'), spread=s.get('spread'),
                         last_traded_at=int(T - 60 * (j.get('coingecko_lag_min') or 10))))
    return rows


if __name__ == '__main__':
    script, out, when, cg_json, cache = sys.argv[1:6]
    T = dt.datetime.strptime(when, '%Y-%m-%d %H:%M:%S').replace(tzinfo=ZoneInfo('Europe/London')).timestamp()
    print(run(script, out, T, cg_from_scan(cg_json, T), cache, quiet=True))
