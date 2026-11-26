# Priced In

**What is the stock market pricing in, and does Kalshi agree?**

Priced In measures how US stocks move with prediction-market odds. For each liquid Kalshi contract it
estimates which stocks move with the odds, by how much per 10 points, and which market reprices first.
The method is pre-registered ([PREREGISTRATION.md](PREREGISTRATION.md)), every result is checked against
time-shift placebos, shuffled event–stock pairs and Benjamini–Hochberg q-values, and the most recent 30%
of events stay sealed until the method is frozen in code.

Served three ways: a static site (`web/`), a read-only REST API, and an MCP server for AI assistants.

## Quick start

```bash
uv sync
cp .env.example .env            # add ALPACA_KEY / ALPACA_SECRET (free plan)

uv run pricedin ingest          # Kalshi events + minute midquotes   (no keys)
uv run pricedin audit           # week-1 audit and decision gate      (no keys)
uv run pricedin bars            # stock minute bars for event and placebo windows (Alpaca)
uv run pricedin run             # event betas, lead-lag, placebos, shuffles, q-values (training events)
uv run pricedin export          # web/public/data/*.json

cd web && npm install && npm run build      # static site in web/out
```

Once the training results are final:

```bash
uv run pricedin freeze --note "method final"   # hashes config + analysis code
uv run pricedin holdout                        # one-time run including the sealed events
uv run pricedin export
```

`holdout` refuses to run without a freeze, or if any config or analysis file changed after it.

## Layout

| Path | What it does |
| --- | --- |
| `config/study.yaml` | Every pre-registered parameter: windows, thresholds, filters, draws, seed |
| `config/universe.yaml` | Contract families and the assets tested against each |
| `pricedin/sources/` | Kalshi (live + historical schemas), Polymarket, Alpaca clients with disk cache |
| `pricedin/events.py` | FOMC days (next-meeting P(cut)) and unscheduled jump detection |
| `pricedin/quality.py` | Module 3: spread, two-sidedness, activity; train / held-out split |
| `pricedin/analysis.py` | Module 1 (event betas) and module 2 (lead-lag), plus validation |
| `pricedin/stats.py` | Sufficient-statistic OLS, event bootstrap, BH q-values |
| `pricedin/freeze.py` | Freeze hash and the held-out guard |
| `pricedin/api.py`, `mcp_server.py` | REST API and MCP tools |
| `web/` | Next.js static site |
| `tests/` | Estimators recover planted effects; nulls stay null; alignment; freeze guard |

## Notes from the week-1 data checks

- Kalshi's 1-minute candlesticks include bid and ask, so the study uses true midquotes.
- Candles exist only for minutes with activity; an unchanged two-sided book is live, not stale.
- Fed decision contracts **close before the 2:00pm statement**, so FOMC days use the next meeting's
  contract, which trades through the statement and press conference.
- CPI prints at 8:30am ET, before the stock session, so it is out of scope at minute resolution.

## Tests

```bash
uv run pytest
```
