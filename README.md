# dawri

Saudi Pro League data product, built lesson by lesson in
`~/helm/06-learning/python-programming/python-project-building/`.

Source: the Saudi Pro League's own API (`api-sdp.spl.com.sa/v1/spl/football`),
Opta-fed, no key. 16 seasons back to 2011/12.
Pipeline: raw JSON -> DuckDB -> dbt staging + marts -> Rill / FastAPI.

Tasks live in `tasks/`. Landed data lives in `data/` (gitignored).

```
uv run ruff check
uv run ty check
uv run <file>.py
```

## Direction

Deterministic only. No predictions, no "who wins the league". Marts and
dashboards answer factual questions: strongest team by evidence, best
players per position (per 90, minutes floor), value for money (needs an
external market-value source; the SPL API has none).
