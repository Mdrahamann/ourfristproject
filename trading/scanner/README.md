# Paper scanner: run it yourself

Read-only. It never places orders, and it **calls no AI API**. It uses only Python's standard library and public
market data from `api.coingecko.com` and `query1.finance.yahoo.com`. Results are paper-watchlist levels:
Yahoo spot candles stand in for the Binance contract, so READY NOW is never shown.

## First time on a Mac
```bash
git clone -b claude/day-trader-skill-install-22d06v https://github.com/mdrahamann/ourfristproject.git ~/ourfristproject
cd ~/ourfristproject
python3 --version          # needs 3.9 or newer; if missing, run: xcode-select --install
```

## Every time (from the repository folder, the one that contains CLAUDE.md)
```bash
cd ~/ourfristproject
git pull                                          # get the latest scanner, if it changed
python3 trading/scanner/scan.py                   # short result
python3 trading/scanner/scan.py --symbol AVAX     # one contract (crypto, or a stock-linked one such as SPCX)
python3 trading/scanner/scan.py --full            # full tables and chart evidence
```
Options:
- `--stocks` always includes the stock-linked contracts (they are included automatically while the US market is open).
- `--no-stocks` leaves them out.
- `--no-journal` doesn't add a row to `trading/journal/forward/scans.csv`.

Output files go to `trading/runs/` (not committed). If a scan fails, the error is printed and the exit code is 1.

**SSL error on the python.org installer?** If you see `CERTIFICATE_VERIFY_FAILED`, run
`open "/Applications/Python 3.x/Install Certificates.command"` once, using your version number for 3.x.
