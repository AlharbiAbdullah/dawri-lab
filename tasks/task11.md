# L11: metrics as code, on a dashboard (Rill)

## The concept

### The problem

Lesson 10 gave Dawri one definition per metric and two engines that
agree on it. Nobody can look at it yet. Every answer is a terminal
table that someone has to know how to ask for. Three symptoms:

1. **No one can browse the facts.** "How did Al Hilal's xG move across
   September?" or "which teams take more points away than at home?" is
   a new `mf query` each time, typed by the one person who knows the
   dimension names.
2. **A dashboard tool brings its own metric language.** Rill (open
   source, Mike Driscoll's company, "BI as code") defines metrics in
   its own YAML: a metrics view with dimensions and measures. It reads
   neither dbt metrics nor Apache Ossie (checked 2026-09-30: nothing in
   its docs, release notes 0.81 to 0.90, or the repo). So the first
   dashboard puts every metric in a second place, and "one definition"
   from lesson 10 is broken the moment it is useful.
3. **A reader locks out the writer.** DuckDB lets one process write a
   file or many processes read it, never both at once. Rill opens
   `data/dawri.duckdb` and keeps it open. While Rill runs,
   `dawri build` fails:

   ```
   [error] [DbDriverFailed (dbt1308)]: Failed to create schema 'marts'
   ... IO Error: Could not set lock on file ".../dawri.duckdb":
   Conflicting lock is held in .../rill (PID ...)
   ```

   (Seen on a scratch copy, 2026-09-30.) A dashboard you must close
   before every run is a dashboard nobody leaves open.

### What we want

`rill start rill` opens a Dawri dashboard on the lesson 10 metrics,
with the same names and the same numbers. `dawri run` works while the
dashboard is open, and the dashboard shows the new numbers without a
restart. A check proves Rill's numbers equal lesson 10's for every team
in both seasons. In the hard tier, Rill's metrics are generated from
the Ossie document, so there is one definition again.

### What you will understand at the end

| Idea | In one line |
|---|---|
| Metrics view | A table plus named dimensions and measures. A dashboard is a view over it, not a pile of queries. |
| BI as code | The dashboard is YAML in git: reviewed, diffed, rebuilt from scratch, never clicked together. |
| Single writer | An embedded database has one writer at a time. Serving and building need separate files, or turns. |
| Serving copy | The pipeline publishes what readers read, whole and in one step, so they never see half a build. |
| Parity across tools | When a tool cannot read the shared definition, a check that compares answers is what keeps them equal. |

### Before and after

```
BEFORE                                  AFTER
answers = typed mf queries              rill start rill: an Explore dashboard
metrics defined in dbt only             same 11 names in a Rill metrics view
Rill open -> dawri build fails          both run at once, no restart (mid)
two definitions, nobody compares        rill parity: 36 rows, 0 differences (mid)
Rill YAML written by hand               generated from the Ossie document (hard)
```

Guardrails for every tier:

- The numbers do not move. Lesson 10's gates still pass unchanged.
- Rill's measures use lesson 10's eleven metric names exactly. A
  measure Rill shows that lesson 10 does not have is out of scope.
- Deterministic only: sums and ratios of what happened. No forecast,
  no anomaly score, no "trend" line that extrapolates.
- Rill runs from the repo root (`rill start rill`,
  `rill validate rill`). It resolves a relative file path from the
  folder it runs in, not from the project folder (checked).
- No absolute path to your home folder in any committed file.
- Rill is a separate binary, not a Python dependency.
- `uv run pytest` still passes, `ruff` and `ty` clean.
- Gates: the target output of each tier.

---

## Easy: a dashboard on the marts

**Target output**

```
$ rill version
rill version v0.90.2 ...

$ rill validate rill
Resources
  KIND (4)      NAME           STATUS   ERROR   WARNING   FILE PATH
  Connector     dawri          Idle                       /connectors/dawri.yaml
  Explore       team_matches   Idle                       /metrics/team_matches.yaml
  MetricsView   team_matches   Idle                       /metrics/team_matches.yaml
  API           team_metrics   Idle                       /apis/team_metrics.yaml

Validation completed successfully

$ rill start rill        (in a second terminal; Explore opens on localhost:9009)

$ rill query --local --path rill --resolver metrics_sql \
    --properties '"sql=SELECT team_name, points, matches_played, goal_difference FROM team_matches WHERE season_id = '"'"'0de9cda0d297418699a8357a8825d46c'"'"' ORDER BY points DESC LIMIT 5"' \
    --format csv
team_name,points,matches_played,goal_difference
Al Nassr,86,34,63
Al Hilal,84,34,58
Al Ahli,81,34,46
Al Qadsiah,77,34,49
Al Ittihad,55,34,7

$ curl -s localhost:9009/v1/instances/default/api/team_metrics | jq length
36
```

The quoting in `--properties` is not decoration: see Reference.

**Spec**

1. Install Rill v0.90.2 (Reference). `rill version` prints it.
2. A Rill project in `rill/`, committed:

   ```
   rill/rill.yaml                   display_name Dawri, OLAP connector dawri
   rill/connectors/dawri.yaml       DuckDB, the file data/dawri.duckdb, read mode
   rill/metrics/team_matches.yaml   the metrics view, with its Explore dashboard
   rill/apis/team_metrics.yaml      a custom API
   ```

3. The metrics view `team_matches` on `marts.fct_team_matches`,
   timeseries `kickoff_utc`, smallest time grain `day`.

   Dimensions:

   | name | from |
   |---|---|
   | `season_id` | column `season_id` |
   | `venue` | column `venue` |
   | `result` | column `result` |
   | `team_name` | the team's name from `marts.dim_teams` |

   Measures, the eleven metrics of lesson 10, same names, with lesson
   10's labels as display names:

   | name | display name | means |
   |---|---|---|
   | `matches_played` | Played | rows |
   | `points` | Points | sum of points |
   | `goals_for` | Goals for | sum |
   | `goals_against` | Goals against | sum |
   | `goal_difference` | Goal difference | goals for minus goals against |
   | `xg_for` | xG for | sum |
   | `xg_against` | xG against | sum |
   | `xg_difference` | xG difference | xG for minus xG against |
   | `shots` | Shots | sum |
   | `shots_on_target` | Shots on target | sum |
   | `points_per_match` | Points per match | points over rows, summed first, divided after |

   The Explore dashboard is declared inside the metrics view file, with
   every dimension and measure.

4. `rill/apis/team_metrics.yaml`: a custom API that returns season,
   team name, points, goal difference, xG for and xG against for every
   season and team: 36 rows (18 teams x 2 seasons).
5. Open the dashboard and use it: pick 2026/27, split by venue, look at
   xG difference. Nothing to hand in for this step, but step 6 needs
   it.
6. In chat: using only the dashboard, how many 2025/26 teams took
   more points away than at home? Name them with both numbers. Then
   say how many clicks it took, and what the same answer costs with
   `mf query`.

**Withheld:** how a dimension gets a name from another table. Rill's
`lookup_table` feature is the obvious answer and it fails on DuckDB:
`lookup tables are not supported for duckdb dialect` (checked on
v0.90.2).

---

## Mid: build while the dashboard is open, and prove the numbers

**Target output**

```
$ rill start rill        (left running for the whole block)

$ uv run dawri build
Processed: 17 models | 43 tests | 1 unit test
Summary: 61 total | 61 success          <- no lock error

$ (throwaway edit: fct_team_matches keeps only kickoffs before 2026-09-01)
$ uv run dawri build && <query Rill: 2026/2027 matches_played, points>
70,95                                   <- was 126,170; Rill not restarted
$ (edit reverted)
$ uv run dawri build && <same query>
126,170

$ mise run rill-parity
rill parity 2025/2026: 18 teams, 0 differences
rill parity 2026/2027: 18 teams, 0 differences
```

**Spec**

7. `dawri build` and `dawri run` succeed while `rill start rill` is
   running and being queried. Nothing in Rill or Dawri is stopped,
   restarted or retried by hand.
8. After a build, the next Rill query answers from the new data, with
   Rill still running. The throwaway edit in the target output is the
   proof: 70 team rows and 95 points before 2026-09-01, 126 and 170
   after the revert.
9. A reader never sees half a build. Whatever Rill reads is replaced
   whole, in one step, only after the dbt build succeeds. A failed
   build leaves Rill answering from the last good data.
10. `mise run rill-parity`, with Rill running: for each season, fetch
    the `team_metrics` API and compare every team's points, goal
    difference, xG for and xG against with `dawri metrics` (lesson 10),
    xG at two decimals. Print the two lines in the target output. Exit
    1 on any difference, on a team present on one side only, or when
    Rill is not running (with a message that says so).
11. `rill validate rill` still passes. The dashboard still works.

**Withheld:** what Rill reads, if not `data/dawri.duckdb`, and who
writes it. How "replaced whole, in one step" is done on one filesystem.
Whether the build or a new `dawri` step does it.

---

## Hard (optional): one definition again

**Target output**

```
$ mise run rill-sync
wrote rill/metrics/team_matches.yaml: 11 measures, 4 dimensions, timeseries kickoff_utc

$ git diff --exit-code rill/metrics/team_matches.yaml; echo $?
0

$ rill validate rill
...
Validation completed successfully

$ mise run rill-parity
rill parity 2025/2026: 18 teams, 0 differences
rill parity 2026/2027: 18 teams, 0 differences

$ (branch: a measure expression edited by hand in team_matches.yaml, pushed)
$ gh run list --limit 1
completed  failure  ...    <- rill-sync: rill/metrics/team_matches.yaml is stale
```

**Spec**

12. `mise run rill-sync` generates `rill/metrics/team_matches.yaml`
    from `semantic/dawri.ossie.yaml`. No measure expression is written
    by hand anywhere in `rill/`.
    - One measure per Ossie metric, same name, expression from the
      document's ANSI_SQL dialect. 11 measures.
    - One dimension per Ossie field that is a non-time dimension on
      `fct_team_matches` (3), plus `team_name` through the document's
      relationship to `dim_teams` (1): 4 dimensions. The time field
      becomes the timeseries. The entity fields (`team`, `team_match`)
      are not dimensions.
    - The file starts with a comment saying it is generated and from
      what.
    - The metric expressions in the document are qualified
      (`SUM(fct_team_matches.points)`). Rill accepts that form when the
      table it reads is named `fct_team_matches` (checked), and not
      otherwise.
13. A check mode, `mise run rill-sync -- --check` (or a task of your
    naming), regenerates in memory and exits 1 with
    `rill/metrics/team_matches.yaml is stale` when the committed file
    differs. CI runs it on every push. Prove it red with the branch in
    the target output, then delete the branch.
14. In chat: lesson 10's step 7 found what the Ossie export lost. What
    did your dashboard lose because of it, and where would you put it
    back without breaking "generated, never hand-edited"?

**Withheld:** how the generator writes YAML Rill accepts and a diff can
compare (key order, quoting). How the relationship becomes a dimension
expression.

---

## Reference

### Install (Linux and macOS)

```
curl https://rill.sh | sh                                  # latest
curl https://rill.sh | sh -s -- --version v0.90.2          # pinned
brew install rilldata/tap/rill                             # macOS
rill version / rill upgrade / rill uninstall
```

Rill 0.90 embeds DuckDB 1.5.5, the same version as the project.
Telemetry is on by default: `analytics_enabled: false` in
`~/.rill/config.yaml` turns it off. Rill writes `~/.rill/state.yaml`
(a version check) on every run. No login is needed for anything in this
lesson.

### Project files (v0.90.2)

```yaml
# rill.yaml
compiler: rillv1
display_name: <name>
olap_connector: <connector file name>

# connectors/<name>.yaml
type: connector
driver: duckdb
path: "<file>"          # relative to the folder rill runs in
mode: read              # read | readwrite; read is the default with path

# metrics/<name>.yaml
version: 1
type: metrics_view
connector: <connector>
database_schema: <schema>     # no dot syntax in table:
table: <table>                # or model: <rill model>
timeseries: <timestamp column>
smallest_time_grain: day
dimensions:
  - name: <name>
    column: <column>          # or expression: <sql>, not both
measures:
  - name: <name>
    display_name: <label>
    expression: <aggregate sql>
    format_preset: humanize   # none | humanize | percentage | ...
explore:                      # with version: 1, no explore block = no dashboard
  dimensions: '*'
  measures: '*'

# apis/<name>.yaml
type: api
metrics_sql: SELECT <dims>, <measures> FROM <metrics view>
```

A Rill model is `type: model` with `sql:` (and `materialize:`). In
`mode: read` a DuckDB connector cannot run models: "model execution is
disabled". A model over Parquet with `materialize: false` is a view, so
it reads the files on every query (checked: a replaced Parquet file was
visible on the next query with no restart).

Docs: docs.rilldata.com/reference/project-files/metrics-views,
.../connectors, .../explore-dashboards, .../canvas-dashboards.

### Asking Rill for numbers without the UI

- `rill query --local --path rill --resolver metrics_sql --properties
  '"sql=..."' --format csv|json`. `--properties` is a key=value list
  split on commas, so a SELECT with commas must be wrapped in double
  quotes inside the single quotes, or the flag fails with
  `points must be formatted as key=value`.
- Metrics SQL: one metrics view per query, no `SELECT *`, no aggregate
  functions (the measures are the aggregates), GROUP BY is implicit,
  WHERE / ORDER BY / LIMIT work.
- Custom API: `GET localhost:9009/v1/instances/default/api/<name>`,
  JSON array, no auth locally.
- `rill validate <dir>` exits non-zero on any parse or reconcile error.
  It prints no numbers.
- Rill Developer also serves MCP at `localhost:9009/mcp` (tools
  `list_metrics_views`, `get_metrics_view`, `query_metrics_view`, ...).
  Lesson 13 may use it.

### What Rill does with the database file (checked on v0.90.2)

```
mode: read connector   ATTACHes the file READ_ONLY, keeps it open while
                       rill start runs
dbt build meanwhile    fails: "Could not set lock on file ... Conflicting
                       lock is held in .../rill"
file replaced by mv    the attached file is not reopened: old numbers
                       until Rill restarts. rill project refresh --local
                       --connector / --metrics-view does not help
Parquet view model     new file visible on the next query, no restart
```

### Numbers on the real data (landed 2026-09-25)

```
team_metrics API          36 rows
2026/27 before 09-01      70 team rows, 95 points
2026/27 all               126 team rows, 170 points
2025/26 top 5 by points   Al Nassr 86, Al Hilal 84, Al Ahli 81,
                          Al Qadsiah 77, Al Ittihad 55
```

Float sums come back unrounded from Rill (`64.37749999999998`), the
same as DuckDB's `ossie` extension. Compare at two decimals.
