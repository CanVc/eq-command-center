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

Initialize the local database:

```bash
eqmarket init-db --db data/eqmarket.sqlite
```
