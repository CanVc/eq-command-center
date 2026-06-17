# EQ Command Center

Local EverQuest market scanner and gear finder.

The first scope is focused on:

- Temple of Veeshan / oldtov item imports
- EverQuest log watching
- WTS auction parsing
- critical deal detection
- local SQLite storage
- console / Discord alerts

See:

- `docs/project-brief/project-brief.txt`
- `docs/data-model/data-model.sql`

## Development

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -e .
```

Install frontend dependencies once before running the full suite; Node.js/npm must be available:

```bash
cd web
npm install
npx playwright install chromium
cd ..
```

Run the test suite. The script auto-reruns with `.venv/Scripts/python.exe` when the local venv exists, then runs Python tests plus frontend test/build/e2e commands:

```bash
python scripts/run_tests.py
```

Useful variants:

```bash
# Verbose unittest output
python scripts/run_tests.py --verbose

# Python tests only
python scripts/run_tests.py --no-frontend

# Run automated tests, then a smoke test against the local DB
python scripts/run_tests.py --smoke --db data/eqmarket.sqlite
```

Testing policy and conventions are documented in `docs/testing-policy.md`.

Run only the smoke test against a local SQLite database:

```bash
python scripts/smoke_api.py --db data/eqmarket.sqlite
```

Initialize the local database:

```bash
eqmarket init-db --db data/eqmarket.sqlite
```

Run the local FastAPI server:

```bash
eqmarket serve-api --db data/eqmarket.sqlite
```

The server binds to `127.0.0.1:8000` by default. You can also set the database path for direct `uvicorn` runs with `EQMARKET_DB_PATH`:

```bash
uvicorn eqmarket.api.app:app --host 127.0.0.1 --port 8000
```

Configure your EverQuest log path from the frontend Settings page with the file picker, or pass it directly to the CLI. Once saved, `import-log` and `run-alerts` can reuse the configured path.

Preview EverQuest auction parsing without writing to SQLite:

```bash
eqmarket import-log --log "C:\\Users\\Public\\Daybreak Game Company\\Installed Games\\EverQuest\\Logs\\eqlog_Dreadbank_frostreaver.txt" --dry-run
```

Import parsed WTS auction listings into SQLite:

```bash
# Uses the log path saved in Settings
eqmarket import-log --db data/eqmarket.sqlite --server frostreaver

# Or override it for this run
eqmarket import-log --log "C:\\Users\\Public\\Daybreak Game Company\\Installed Games\\EverQuest\\Logs\\eqlog_Dreadbank_frostreaver.txt" --db data/eqmarket.sqlite --server frostreaver
```

Resolve pending item names into Lucy item/spell data:

```bash
eqmarket enrich-pending --db data/eqmarket.sqlite --limit 25
```

Resolved rows stay in `pending_items` for audit with `status = 'resolved'`, but they disappear from the active pending queue.

Import TLP Auctions market reference prices and Krono conversion for local resolved listings/watchlist items:

```bash
eqmarket import-tlp-prices --db data/eqmarket.sqlite --server frostreaver --limit 100 --history-days 3
```

Useful variants:

```bash
# Fast seed from cached TLP catalog medians only
eqmarket import-tlp-prices --db data/eqmarket.sqlite --server frostreaver --no-history

# Seed every TLP catalog item/median into items + market_prices
eqmarket import-tlp-prices --db data/eqmarket.sqlite --server frostreaver --all-catalog --no-history
```

Score recent resolved listings against imported market prices and print console alerts:

```bash
eqmarket score-listings --db data/eqmarket.sqlite --server frostreaver --limit 200 --min-discount 30
```

Run the full alert pipeline in one command. TLP history prices default to the last 3 days, which is safer for a fresh server with rapidly falling prices:

```bash
# Uses the log path saved in Settings if available
eqmarket run-alerts --db data/eqmarket.sqlite --server frostreaver --history-days 3

# Or override it for this run
eqmarket run-alerts --db data/eqmarket.sqlite --server frostreaver --log "C:\\Users\\Public\\Daybreak Game Company\\Installed Games\\EverQuest\\Logs\\eqlog_Dreadbank_frostreaver.txt" --history-days 3
```

Avoid refreshing TLP prices every run and rank with cached prices/manual overrides only:

```bash
eqmarket run-alerts --db data/eqmarket.sqlite --server frostreaver --log "C:\\Users\\Public\\Daybreak Game Company\\Installed Games\\EverQuest\\Logs\\eqlog_Dreadbank_frostreaver.txt" --skip-price-refresh
```

Or refresh only missing/stale recent prices:

```bash
eqmarket run-alerts --db data/eqmarket.sqlite --server frostreaver --log "C:\\Users\\Public\\Daybreak Game Company\\Installed Games\\EverQuest\\Logs\\eqlog_Dreadbank_frostreaver.txt" --price-max-age-hours 12
```

In the web UI, `TLP max age` controls the same stale-price window. It defaults to 6 hours; set it to 0 to refresh every eligible recent item.
