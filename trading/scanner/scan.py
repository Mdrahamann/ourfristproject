#!/usr/bin/env python3
"""One-command paper scan: the original 15m/5m scalp first, the separate 1H/15m plan second, longs and shorts.
Read-only: places no orders. Python standard library only; NO AI API is called. The only network calls are
public market data from api.coingecko.com and query1.finance.yahoo.com.

Run from the repository folder (the one that contains CLAUDE.md):
  python3 trading/scanner/scan.py                 short result (crypto; stock-linked too while the US market is open)
  python3 trading/scanner/scan.py --symbol AVAX   one contract (crypto or a supported stock-linked one, e.g. SPCX)
  python3 trading/scanner/scan.py --full          full tables and evidence
  options: --stocks (always include stock-linked), --no-stocks, --no-journal
"""
import csv, datetime as dt, json, os, subprocess, sys
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cli import RUNS, STOCK_UNIVERSE, norm  # noqa: E402

UK, NY = ZoneInfo('Europe/London'), ZoneInfo('America/New_York')
JOURNAL = os.path.join(HERE, '..', 'journal', 'forward', 'scans.csv')


def us_open(now):
    ny = now.astimezone(NY)
    return ny.weekday() < 5 and (9, 30) <= (ny.hour, ny.minute) < (16, 0)


def next_open_uk(now):
    ny = now.astimezone(NY)
    day = ny.date() + dt.timedelta(days=0 if (ny.hour, ny.minute) < (9, 30) else 1)
    while day.weekday() >= 5: day += dt.timedelta(days=1)
    return dt.datetime(day.year, day.month, day.day, 9, 30, tzinfo=NY).astimezone(UK).strftime('%a %H:%M UK')


def run(script, out, extra):
    p = subprocess.run([sys.executable, os.path.join(HERE, script), out, '--quiet'] + extra,
                       capture_output=True, text=True, timeout=900)
    if p.returncode != 0:
        err = (p.stderr or p.stdout or '').strip().splitlines()
        print(f"SCAN FAILED ({script}, exit code {p.returncode}). Error:\n" + '\n'.join(err[-25:]))
        sys.exit(1)


def main():
    a = sys.argv[1:]
    full, sym = '--full' in a, None
    if '--symbol' in a:
        i = a.index('--symbol')
        if i + 1 >= len(a): sys.exit('usage: --symbol AVAX')
        sym = norm(a[i + 1])
    now = dt.datetime.now(UK)
    stamp = f'{now:%Y%m%d-%H%M%S}'
    do_crypto = not (sym and sym[:-4] in STOCK_UNIVERSE)
    do_stocks = (sym[:-4] in STOCK_UNIVERSE) if sym else ('--stocks' in a or (us_open(now) and '--no-stocks' not in a))
    extra = ['--symbol', sym] if sym else []
    outs = {}
    print(f"Scan {now:%a %d %b %H:%M UK}" + (f" — {sym} only" if sym else ''))
    if do_crypto:
        outs['crypto'] = os.path.join(RUNS, stamp + '-crypto'); run('smc_scan.py', outs['crypto'], extra)
    if do_stocks:
        outs['stocks'] = os.path.join(RUNS, stamp + '-stocks'); run('stock_scan.py', outs['stocks'], extra)
    for k, o in outs.items():
        md = open(os.path.join(o, 'scan.md' if k == 'crypto' else 'stock_scan.md')).read() if full else open(os.path.join(o, 'short.md')).read()
        print(f"\n=== {'Crypto' if k == 'crypto' else 'Stock-linked'} ===\n" + md.strip())
    if not sym and not do_stocks:
        print(f"\nStock-linked: not scanned, US market closed (next open {next_open_uk(now)}). Add --stocks to scan anyway.")
    print(f"\nFiles: {os.path.relpath(RUNS)}/{stamp}-*")
    if not sym and '--no-journal' not in a:
        journal(now, outs)


def journal(now, outs):
    """Append one row to the forward journal (local file only; nothing is committed or sent anywhere)."""
    c = json.load(open(os.path.join(outs['crypto'], 'scan.json'))) if 'crypto' in outs else {}
    s = json.load(open(os.path.join(outs['stocks'], 'stock_scan.json'))) if 'stocks' in outs else {}
    states = []
    for k in ('crypto', 'stock'):
        try: states += [v['title'] for v in json.load(open(os.path.join(HERE, '..', 'journal', 'forward', f'watch_state_{k}.json'))).values()]
        except Exception: pass
    ok = [x for x in c.get('symbols', []) if x.get('status') == 'ok']
    row = [f'{now:%Y-%m-%d %H:%M:%S}', 'scan.py (terminal)' if sys.stdin and sys.stdin.isatty() else 'scan.py',
           c.get('n_crypto', 0), len(c.get('symbols', [])), len(ok), s.get('n_checked', 0), s.get('n_analysed', 0), 0,
           'unavailable - no live Binance contract quote/candles', sum('CONFIRMED' in t or 'READY' in t for t in states), '',
           len(states), 'unverified (blackouts not coded)', '; '.join(states) or 'no live setup']
    with open(JOURNAL, 'a', newline='') as f:
        csv.writer(f).writerow(row)


if __name__ == '__main__':
    main()
