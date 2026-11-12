"""Shared command-line handling for the scanners. Standard library only; no AI API."""
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, '..', 'runs')          # scan output folders (not committed)
# Stock-linked perps scanned by stock_scan.py (fixed list; leveraged/inverse ETFs and KRW-listed names left out)
STOCK_UNIVERSE = ('SPCX SKHY MU SNDK NVDA GOOGL INTC QQQ CRCL MSTR AAPL TSLA NBIS SPY META AVGO AMD MSFT DRAM AMZN '
                  'BABA TSM COIN ORCL PLTR HOOD').split()


def norm(sym):
    """'avax', 'AVAX', 'AVAXUSDT' -> 'AVAXUSDT'."""
    s = sym.strip().upper()
    return s if s.endswith('USDT') else s + 'USDT'


def parse(argv, kind):
    """[OUTDIR] [--symbol X] [--quiet]. OUTDIR defaults to trading/runs/<time>-<kind>."""
    out, symbol, quiet, a = None, None, False, list(argv)
    while a:
        x = a.pop(0)
        if x == '--symbol' and a: symbol = norm(a.pop(0))
        elif x == '--quiet': quiet = True
        elif x.startswith('--'): sys.exit(f'unknown option {x}')
        elif out is None: out = x
    out = out or os.path.join(RUNS, f"{dt.datetime.now():%Y%m%d-%H%M%S}-{kind}")
    os.makedirs(out, exist_ok=True)
    return out, symbol, quiet


def summary_of(md):
    """The 'What do I do now?' part of a scan.md (up to the first --- line)."""
    if '## What do I do now?' not in md: return ''
    s = md[md.index('## What do I do now?'):]
    return s[:s.index('\n---')] if '\n---' in s else s
