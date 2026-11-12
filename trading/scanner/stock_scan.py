#!/usr/bin/env python3
"""Plan A / Plan B scan for Binance stock- and ETF-linked perpetuals. Read-only; no orders.
Context from the UNDERLYING stock (Yahoo, regular session); entry confirmation/prices/fills must come from the
Binance contract, which is not reachable here -> all levels approximate, paper watchlist only.
Depth (order book) cannot be checked -> every stock-linked setup is 'unverified' (CLAUDE.md decision 8)."""
import datetime as dt, json, os, sys, time, urllib.request
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smc_core import analyse  # noqa: E402
from plans import find_setups  # noqa: E402  (separate 1H plan only)
from scalp_original import htf_context, scalp_sequences, swings  # noqa: E402  (original scalp, unchanged)
from scalp_status import label as scalp_label, tracked  # noqa: E402
from report import render  # noqa: E402

UK, NY = ZoneInfo('Europe/London'), ZoneInfo('America/New_York')
from cli import parse, summary_of, STOCK_UNIVERSE  # noqa: E402
NOW = time.time(); OUT, SYMBOL, QUIET = parse(sys.argv[1:], 'stocks')   # [OUTDIR] [--symbol SPCX] [--quiet]
OPEN = urllib.request.build_opener()   # uses HTTPS_PROXY from the environment only if one is set
FEE_TAKER, SLIPPAGE = 0.0005, 0.0002
# exclude leveraged/inverse ETFs (L3) and KRW-listed names whose session differs
UNIVERSE = [SYMBOL[:-4]] if SYMBOL else STOCK_UNIVERSE


def get_json(url):
    return json.loads(OPEN.open(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=40).read())


def yahoo(sym, interval, rng, sec):
    d = get_json(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={interval}&range={rng}')['chart']['result'][0]
    q = d['indicators']['quote'][0]
    return [(t, o, h, l, c) for t, o, h, l, c in zip(d['timestamp'], q['open'], q['high'], q['low'], q['close'])
            if None not in (o, h, l, c) and t + sec <= NOW]


ny = dt.datetime.fromtimestamp(NOW, NY)
nm = ny.hour * 60 + ny.minute
session = ny.weekday() < 5 and 9 * 60 + 30 <= nm < 16 * 60
entries_ok = ny.weekday() < 5 and 9 * 60 + 45 <= nm < 15 * 60 + 30
cg = get_json('https://api.coingecko.com/api/v3/derivatives?include_tickers=unexpired')
b = {x['symbol'][:-4]: x for x in cg if x.get('market') == 'Binance (Futures)' and x.get('contract_type') == 'perpetual'
     and x['symbol'].endswith('USDT') and x['symbol'][:-4] in UNIVERSE}
passed, rejected, setups, ctx, items = [], [], [], {}, []
STATE = os.path.join(os.environ.get('SCAN_STATE_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'journal', 'forward'), 'watch_state_stock.json')
for k in UNIVERSE:
    x = b.get(k)
    if not x: continue
    why = []
    if (x.get('open_interest') or 0) < 20e6: why.append(f"OI ${(x.get('open_interest') or 0) / 1e6:.0f}M")
    if (x.get('spread') or 1) > 0.05: why.append(f"spread {x.get('spread')}%")
    if abs(x.get('funding_rate') or 0) > 0.05: why.append(f"funding {x['funding_rate']:+.3f}%")
    (rejected if why else passed).append((k, x, why))
for k, x, _ in passed:
    try:
        m5, m15, h1, d1 = yahoo(k, '5m', '5d', 300), yahoo(k, '15m', '5d', 900), yahoo(k, '1h', '60d', 3600), yahoo(k, '1d', '6mo', 86400)
    except Exception as e:
        ctx[k] = f'UNAVAILABLE ({str(e)[:40]})'; items.append(dict(sym=k + 'USDT', status='UNAVAILABLE: ' + ctx[k])); continue
    if len(m15) < 30 or len(h1) < 60:
        ctx[k] = 'UNAVAILABLE (too few bars)'; items.append(dict(sym=k + 'USDT', status='UNAVAILABLE: too few bars')); continue
    biasA = htf_context(h1, 3, 3600)['bias']                                         # 1H context (original scalp)
    biasB = analyse(d1, 2, 86400, max_age=400, fvg_state=False)['last_dir']         # daily used for Plan B context
    ctx[k] = dict(h1=biasA, d1=biasB, last=m5[-1][4], perp=x.get('index'), oi=x.get('open_interest'), spread=x.get('spread'))
    hs = (x.get('spread') or 0.02) / 200
    costs = (FEE_TAKER + hs + SLIPPAGE, FEE_TAKER + hs, FEE_TAKER + hs + SLIPPAGE)
    seqs = scalp_sequences(m15, m5, h1, biasA, x.get('spread'), NOW, keep=tracked(STATE, k + 'USDT', NOW))   # original scalp (+ plans shown)
    for s_ in seqs: scalp_label(s_, m5, m15, h1, swings(m15, 2, 900), NOW)
    items.append(dict(sym=k + 'USDT', status='ok', seqs=seqs))
    for rr in find_setups('B', h1, m15, biasB, m5[-1][4], costs, NOW):           # separate 1H plan
        rr['sym'] = k + 'USDT'; rr['costs'] = costs; setups.append(rr)
ok = [v for v in ctx.values() if isinstance(v, dict)]
breadth = dict(n=len(ok), bear=sum(v['h1'] == 'bear' for v in ok), bull=sum(v['h1'] == 'bull' for v in ok))
DATA = [f"**Data:** underlying US stock candles (Yahoo, regular session) stand in for the Binance contracts. All levels APPROXIMATE, paper watchlist only. "
        + ('US session OPEN' if session else 'US session CLOSED') + ('; entries allowed 09:45–15:30 New York.' if entries_ok else '; no new entries now (outside 09:45–15:30 New York).'),
        '- **READY NOW unavailable — live contract data missing.** Order-book depth and earnings dates UNVERIFIED (every stock setup is unverified).',
        '- The separate 1H plan uses the DAILY trend as context for stocks (4H not built for stocks; PROPOSED).',
        '- Universe is a fixed list of 26 names (CRWV, SOXL, SNXX and others are not included yet; fix pending your approval).']
md = render(items, setups, breadth, DATA, unit='stock-linked contracts', now=NOW,
            state_path=STATE, save_state=not SYMBOL, only_sym=SYMBOL,
            closed_note=None if entries_ok else '**US market closed (or outside 09:45–15:30 New York): no new stock-linked entries now.**')
head = (f"Stock-linked scan {dt.datetime.fromtimestamp(NOW, UK):%a %d %b %H:%M:%S %Z}: {len(b)} contracts checked, "
        f"{len(passed)} passed L3, analysed {len(ok)}. Rejected: " + ', '.join(f"{k} ({'; '.join(w)})" for k, _, w in rejected))
open(os.path.join(OUT, 'stock_scan.md'), 'w').write(head + '\n\n' + md + '\n')
ONE_LINE = (f"Stock data: {len(b)} checked → {len(passed)} passed liquidity → {len(ok)} analysed. Underlying-stock candles (Yahoo) stand in for Binance; "
            "READY NOW unavailable, order-book depth and earnings unverified. " + ('US session open.' if session else 'US session closed.')
            + (' Failed liquidity: ' + ', '.join(f"{k} ({'; '.join(w)})" for k, _, w in rejected) + '.' if rejected and SYMBOL else ''))
open(os.path.join(OUT, 'short.md'), 'w').write(summary_of(md).rstrip() + '\n\n' + ONE_LINE + '\n')
json.dump(dict(ctx=ctx, setups=setups, n_checked=len(b), n_passed=len(passed), n_analysed=len(ok), one_line=ONE_LINE),
          open(os.path.join(OUT, 'stock_scan.json'), 'w'), default=str)
if QUIET: sys.exit(0)
print(head); print(md)
for k, v in ctx.items():
    if isinstance(v, dict): print(f"  {k}: 1H {v['h1']} daily {v['d1']} last {v['last']:.2f} OI ${v['oi'] / 1e6:.0f}M spread {v['spread']}%")
    else: print(f'  {k}: {v}')
