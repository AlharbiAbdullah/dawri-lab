# dawri-lab

Saudi Pro League data product: facts, not predictions.

Status: working · learning build, one lesson per file in [tasks/](tasks/) · 2026-10

![The SPL API feeds an ingest step that checks a contract and lands raw JSON. DuckDB and dbt build raw, staging and marts. The marts are published as a Parquet serving copy, swapped in atomically, and read by a dashboard, a report and an app. One semantic document defines every metric.](docs/diagrams/architecture.excalidraw.svg)

## What it does

- Answers factual questions about the league: strongest team by evidence, best
  players per position (per 90, with a minutes floor).
- Never predicts. No "who wins the league".
- Gap: value for money needs an external market-value source. The SPL API has none.

## How it works

1. **Source.** The Saudi Pro League's own API (`api-sdp.spl.com.sa/v1/spl/football`),
   Opta-fed, no key. 16 seasons back to 2011/12; 2025/26 and the live 2026/27 are loaded.
2. **Ingest.** `dawri ingest` pulls each endpoint with HTTPX and writes raw JSON to `data/`.
   Pydantic contracts check the payloads at the boundary.
3. **Warehouse.** `dawri load` loads the raw JSON into DuckDB through PyArrow.
   `dawri build` runs dbt: `raw` to `staging` to `marts`, tested on every build.
4. **Publish.** After a green build, the marts are written as Parquet to
   `data/serving/` and swapped in with one rename. Readers never hold a lock on the build.
5. **Semantic.** dbt's semantic models are converted to one Apache Ossie document,
   `semantic/dawri.ossie.yaml`. Each metric is defined there once.
6. **Consume.** Rill, Evidence and Streamlit read the serving copy, with metrics
   generated from or queried through Ossie, so every screen shows the same number.

## Tech stack

![Tech stack: SPL API; Pydantic; DuckDB, PyArrow, dbt; Parquet; Rill, Evidence, Streamlit; Apache Ossie; GitHub Actions, Ruff, ty, pytest; mise, uv](docs/diagrams/tech-stack.excalidraw.svg)

## Decisions

- **A Parquet serving copy over readers on the DuckDB file:** one open reader made
  `dawri build` fail on the lock. Cost: a second copy on disk, fresh only after a publish.
- **One Ossie document over metrics in each tool:** Rill reads neither dbt metrics nor
  Ossie natively, so each tool would define its own. Cost: generated files and sync checks, on an
  incubating spec pinned to one commit.
- **Contracts at the ingest boundary over trusting the API:** the API is undocumented,
  so a shape change stops the run instead of reaching the marts. Cost: a new field means
  a contract change.
- **Recorded fixtures in CI over live calls:** tests never touch the network. Cost: the
  fixtures are a frozen snapshot and age.

## Results

Top of the 2026/27 table through Ossie, as of 2026-10-06 (`dawri metrics 2026/2027`):

| Team | Points | Goal difference | xG for | xG against |
|------|-------:|----------------:|-------:|-----------:|
| Al Hilal | 18 | 18 | 25.08 | 8.27 |
| Al Ittihad | 17 | 6 | 14.12 | 9.96 |
| Al Nassr | 16 | 9 | 11.96 | 5.70 |
| Al Qadsiah | 16 | 8 | 16.42 | 6.73 |
| NEOM SC | 15 | 7 | 9.46 | 7.81 |

## Run it

Needs [uv](https://docs.astral.sh/uv/) and [mise](https://mise.jdx.dev/).

```sh
mise install && uv sync
uv run dbt deps --project-dir dbt --profiles-dir dbt

uv run dawri run 2026/2027        # ingest -> load -> build -> publish
uv run dawri metrics 2026/2027    # team metrics, through Ossie
```

Read it:

```sh
uv run streamlit run src/dawri/app.py         # app on localhost:8501
rill start rill                               # dashboard
cd evidence && npm install && npm run sources && npm run dev  # report
```

## Checks

```sh
uv run ruff check && uv run ty check && uv run pytest   # tests never touch the network
mise run semantic-check    # Ossie document matches dbt, both engines agree
mise run rill-sync -- --check
mise run evidence-sync -- --check
mise run app-check         # the app defines no metric of its own
```

CI runs all of these on every push, with dbt built on recorded fixtures.

## Layout

```
src/dawri/   CLI, ingest, load, publish, semantic, Streamlit app
dbt/         staging and marts models, tests, semantic models
semantic/    the Ossie document
rill/        dashboard project (metrics generated from Ossie)
evidence/    report project (sources generated from Ossie)
scripts/     sync and parity scripts
tasks/       one file per lesson
docs/        API model, diagrams
```

Landed data lives in `data/` (gitignored).

## Docs

- [docs/api-model.md](docs/api-model.md): what the SPL API is and how its entities connect.
- [tasks/](tasks/): the build log, one lesson per file.
- [docs/diagrams/diagrams.py](docs/diagrams/diagrams.py): the scene script behind both diagrams.
