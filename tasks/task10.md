# L10: one definition of a metric (Apache Ossie)

## The concept

### The problem

"Points" is a number every part of Dawri will need: the dashboard in
lesson 11, the API in lesson 12, the matchday brief in lesson 13, and
any AI agent you point at the data. Today it has no definition you can
hand to anyone. Three symptoms:

1. **The metric lives inside one model's SQL.** Points are computed in
   `mart_standings.sql` with `count(*) filter (...)` and a `3 * won +
   drawn` step. A second consumer cannot reuse that. It writes its own
   `SUM(...)`, and the two drift apart the first time someone changes
   one of them.
2. **The mart answers one question.** `mart_standings` is already
   aggregated to season x team x venue. "Points by month", "xG per
   match at home", "goal difference after matchday 10" each need a new
   model, because nothing below the mart is at a grain you can slice.
3. **Every tool wants its own format.** dbt's semantic YAML is read by
   MetricFlow. Rill has its own metrics YAML (checked 2026-09-30: it
   reads neither dbt metrics nor Ossie). BI tools and agents each have
   theirs. Apache Ossie (incubating since July 2026, formerly Open
   Semantic Interchange) is the vendor-neutral format for exactly this:
   datasets, fields, relationships and metrics in one YAML document that
   any tool can read.

One fact from the data: the metric answers already exist in the mart.
Rebuilt from match rows, the points, played, goals for and goals
against of all 108 `mart_standings` rows come out identical (checked on
a scratch copy). So every metric in this lesson has a truth to be
checked against.

### What we want

Every Dawri metric is defined once, in dbt, next to the model it
measures. dbt writes those definitions out, a converter turns them into
an Apache Ossie document committed in the repo, and two engines that
share no code (MetricFlow, and DuckDB's `ossie` extension) answer the
same question with the same numbers.

### What you will understand at the end

| Idea | In one line |
|---|---|
| Fact table grain | One row per thing that happened (a team in a match). Metrics are aggregates over it, so any slice is a GROUP BY, not a new model. |
| Semantic model | A model plus what its columns mean: entities (keys you can join on), dimensions (what you group by), metrics (what you add up). |
| Metric types | Simple (one aggregate), derived (arithmetic on metrics), ratio (a metric over a metric, summed first, divided after). |
| Interchange format | A document one tool writes and another reads. It carries definitions, not data. What it cannot express is lost on the way. |
| Parity | Two engines, one definition, same answer. The proof that the definition is the thing being shared. |

### Before and after

```
BEFORE                                  AFTER
points = SQL inside mart_standings      points = a metric in dbt YAML
one grain: season x team x venue        fct_team_matches: team x match, 738 rows
new question = new model                new question = new GROUP BY
definitions readable by dbt only        semantic/dawri.ossie.yaml (Apache Ossie)
one engine                              MetricFlow and DuckDB ossie agree (mid)
nothing stops the two drifting          CI regenerates and compares (hard)
```

Guardrails for every tier:

- The numbers do not move. `mart_standings` is untouched, and the new
  metrics must reproduce it: that is a test in the easy tier.
- Latest dbt semantic YAML only: `semantic_model:` under the model,
  `metrics:` under the model or at the top level. The legacy top-level
  `semantic_models:` block makes dbt print `SemanticModelDeprecated
  (dbt1157)` and write an empty semantic manifest. No dbt1157 warning
  is allowed.
- One definition. A metric's expression is written once, in dbt YAML.
  The Ossie document is generated from it and never edited by hand.
- MetricFlow runs in its own environment through `uvx`, never in the
  project's venv. It needs dbt-core 1.12, and dbt-core and the dbt v2
  `dbt` package both install a command called `dbt`.
- Deterministic only. Every metric is a sum or ratio of what happened.
  No rating, no forecast, no "expected points".
- `uv run pytest` still passes (44), and `ruff` and `ty` stay clean.
- Use the tools people use: dbt's semantic layer, MetricFlow, the Apache
  Ossie converter and Python package, DuckDB's `ossie` extension. Know
  what each does underneath: the Reference says where to look.
- Gates: the target output of each tier, run from the repo root unless
  the block says otherwise.

---

## Easy: define the metrics once, export them to Ossie

**Target output**

```
$ uv run dawri build
Processed: 16 models | 40 tests | 1 unit test
Summary: 57 total | 57 success

$ cd dbt && uvx --from "dbt-metricflow[dbt-duckdb]==0.15.0" \
    mf query --metrics points,matches_played,xg_for --group-by team_match__season_id
team_match__season_id               points    matches_played    xg_for
--------------------------------  --------  ----------------  --------
3677a75aaa514e43b2840e7fa367c91d       170               126   186.039
0de9cda0d297418699a8357a8825d46c       848               612   756.88

$ cd dbt && uvx --from "dbt-metricflow[dbt-duckdb]==0.15.0" mf list metrics
... We've found 11 metrics.

$ mise run ossie
Written to semantic/dawri.ossie.yaml
dawri 0.2.0.dev0: 1 datasets, 0 relationships, 11 metrics
```

`mf` also prints a spinner line before each table (`✔ Success ... query
completed after N seconds`). The table is the gate. Row order in the
first query is not fixed.

**Spec**

1. `dbt/models/marts/fct_team_matches.sql`, table, one row per team per
   FINISHED match. Every match gives two rows, one per side.
   738 rows: 612 for 2025/26, 126 for 2026/27.

   | column | from | type |
   |---|---|---|
   | `team_match_key` | one key per row, built from `match_id` and `team_id` | VARCHAR |
   | `season_id` | `stg_matches.season_id` | VARCHAR |
   | `match_id` | `stg_matches.match_id` | VARCHAR |
   | `matchday_id` | `stg_matches.matchday_id` | VARCHAR |
   | `kickoff_utc` | `stg_matches.kickoff_utc` | TIMESTAMP |
   | `venue` | `'home'` on the home side's row, `'away'` on the away side's | VARCHAR |
   | `team_id` | this side's team | VARCHAR |
   | `opponent_id` | the other side's team | VARCHAR |
   | `goals_for` | this side's score | INTEGER |
   | `goals_against` | the other side's score | INTEGER |
   | `result` | `'W'`, `'D'` or `'L'` for this side | VARCHAR |
   | `points` | 3 for W, 1 for D, 0 for L | INTEGER |
   | `xg_for` | `stg_teamstats`, `stat_id = 'expected-goals'`, this side's value | DOUBLE |
   | `xg_against` | same stat, the other side's value | DOUBLE |
   | `shots` | `stat_id = 'shots'`, this side's value | INTEGER |
   | `shots_on_target` | `stat_id = 'shots-on-goal'`, this side's value | INTEGER |

   All 369 finished matches have all three stats, so no stat column is
   null on the real data.

2. `dbt/models/marts/metricflow_time_spine.sql`, table, one column
   `date_day` (DATE), one row per day from 2011-01-01 to 2030-12-31:
   7,305 rows. MetricFlow needs it to answer anything by time.

3. `dbt/models/marts/_semantic.yml` holds everything about these two
   models. A model may appear in only one YAML entry in the project,
   so their tests live here too, not in `_marts.yml`.

   - `metricflow_time_spine`: declared as the time spine, standard
     granularity column `date_day`, granularity `day`.
   - `fct_team_matches`, semantic model enabled,
     `agg_time_dimension: kickoff_utc`:

     | column | role |
     |---|---|
     | `team_match_key` | primary entity `team_match` |
     | `team_id` | foreign entity `team` |
     | `kickoff_utc` | time dimension, granularity `day` |
     | `season_id` | categorical dimension |
     | `venue` | categorical dimension |
     | `result` | categorical dimension |

   - Eleven metrics, names exactly as written:

     | metric | type | definition | label |
     |---|---|---|---|
     | `matches_played` | simple | count of rows | Played |
     | `points` | simple | sum of `points` | Points |
     | `goals_for` | simple | sum of `goals_for` | Goals for |
     | `goals_against` | simple | sum of `goals_against` | Goals against |
     | `xg_for` | simple | sum of `xg_for` | xG for |
     | `xg_against` | simple | sum of `xg_against` | xG against |
     | `shots` | simple | sum of `shots` | Shots |
     | `shots_on_target` | simple | sum of `shots_on_target` | Shots on target |
     | `goal_difference` | derived | `goals_for - goals_against` | Goal difference |
     | `xg_difference` | derived | `xg_for - xg_against` | xG difference |
     | `points_per_match` | ratio | `points` over `matches_played` | Points per match |

     Give `matches_played` the description `Finished matches` and
     `points` the description `3 for a win, 1 for a draw`. Step 7
     looks at what happens to them.

4. Tests, 4 new:

   ```
   fct_team_matches.team_match_key   unique, not_null
   fct_team_matches.result           accepted_values W, D, L
   dbt/tests/assert_team_matches_rebuild_standings.sql
       rebuilds played, points, goals_for and goals_against for every
       season x team x type (table, home, away) from fct_team_matches
       and returns every row where that differs from mart_standings,
       including a row missing on either side. 0 rows = pass.
   ```

   The singular test holds on any dataset, so it is not tagged
   `full_data`. 14 + 2 = 16 models, 36 + 4 = 40 tests, 57 total.

5. MetricFlow answers the first two queries of the target output. It
   reads `dbt/target/semantic_manifest.json`, which `dawri build`
   writes. Run it from `dbt/` so it finds `profiles.yml`. dbt prints
   `Skipping semantic manifest validation due to: No dbt_cloud.yml
   config` on every build: that one warning is expected. `mf
   validate-configs` is the local validation.

6. `semantic/dawri.ossie.yaml`, committed, generated by the Apache
   Ossie dbt converter from `dbt/target/semantic_manifest.json`, with
   the semantic model named `dawri`. One command regenerates and
   validates it: `mise run ossie`, a task you add to `mise.toml`. It
   prints the converter's `Written to ...` line, then one line built
   from the document after it is loaded into the `OssieDocument`
   Pydantic model from the `apache-ossie` package:

   ```
   <name> <version>: <n> datasets, <n> relationships, <n> metrics
   ```

   If the document does not validate, the task exits non-zero.

7. In chat: open `semantic/dawri.ossie.yaml` next to `_semantic.yml`.
   Name one thing you wrote in dbt that crossed into the Ossie document
   unchanged, one that crossed in a different form, and one that did
   not cross at all. For the last one, say what a tool that reads only
   the Ossie document would get wrong because of it.

**Withheld:** how one match row becomes two team rows. How a stat
stored as one row per stat becomes columns. How `mise run ossie` gets
the converter and `apache-ossie` without adding them to the project's
dependencies, or whether it should add them.

---

## Mid: a second engine, and names instead of ids

**Target output**

```
$ uv run dawri build
Processed: 17 models | 43 tests | 1 unit test
Summary: 61 total | 61 success

$ mise run ossie
Written to semantic/dawri.ossie.yaml
dawri 0.2.0.dev0: 2 datasets, 1 relationships, 11 metrics

$ cd dbt && uvx --from "dbt-metricflow[dbt-duckdb]==0.15.0" \
    mf query --metrics points,goal_difference,xg_for,xg_against \
    --group-by team__team_name \
    --where "{{ Dimension('team_match__season_id') }} = '0de9cda0d297418699a8357a8825d46c'" \
    --order -points --limit 3
team__team_name      points    xg_for    xg_against    goal_difference
-----------------  --------  --------  ------------  -----------------
Al Nassr                 86   64.3775       21.9531                 63
Al Hilal                 84   68.045        19.7629                 58
Al Ahli                  81   54.1922       23.0439                 46

$ uv run dawri metrics 2025/2026 | head -6
team_name,points,goal_difference,xg_for,xg_against
Al Nassr,86,63,64.38,21.95
Al Hilal,84,58,68.05,19.76
Al Ahli,81,46,54.19,23.04
Al Qadsiah,77,49,61.64,33.66
Al Ittihad,55,7,45.44,41.58

$ uv run dawri metrics 2026/2027 | head -6
team_name,points,goal_difference,xg_for,xg_against
Al Hilal,18,18,25.08,8.27
Al Ittihad,17,6,14.12,9.96
Al Nassr,16,9,11.96,5.70
Al Qadsiah,16,8,16.42,6.73
NEOM SC,15,7,9.46,7.81
```

**Spec**

8. `dbt/models/marts/dim_teams.sql`, table, one row per team: 21 rows
   (18 per season, 21 across both).

   | column | from | type |
   |---|---|---|
   | `team_id` | `stg_teams.team_id` | VARCHAR |
   | `team_name` | `stg_teams.short_name` | VARCHAR |

   A team's short name is the same in every season on the landed data
   (checked: 0 teams differ).

9. In `_semantic.yml`: `dim_teams` gets a semantic model with
   `team_id` as primary entity `team` and `team_name` as a categorical
   dimension. Because `fct_team_matches.team_id` is already the foreign
   entity `team`, MetricFlow can now group any metric by
   `team__team_name`. Three new tests: `dim_teams.team_id` unique and
   not_null, and a `relationships` test from `fct_team_matches.team_id`
   to `dim_teams.team_id`. 17 models, 43 tests, 61 total.

10. `mise run ossie` now writes 2 datasets and 1 relationship. Nothing
    about the relationship is written by hand.

11. `dawri metrics SEASON`, a new command. SEASON is the same choice as
    `dawri ingest`. It answers from `semantic/dawri.ossie.yaml` through
    DuckDB's `ossie` community extension, reading
    `data/dawri.duckdb` read-only. It never writes SQL for a metric:
    the metric expressions come from the document.

    - stdout is CSV, header
      `team_name,points,goal_difference,xg_for,xg_against`, one row per
      team with a finished match in that season (18 on the real data).
    - Ordered by points, then goal difference, both descending, then
      team name.
    - `xg_for` and `xg_against` always with two decimals (`5.70`, not
      `5.7`). The float sums differ from MetricFlow's in the last
      digits (`64.37749999999998` against `64.3775`), so two decimals
      is where the two engines are compared.
    - Every line of both target blocks is exact on the real data.

12. The extension and the converter disagree about the document. The
    converter writes Ossie `0.2.0.dev0`: one model at the root. The
    `ossie` extension in DuckDB 1.5.5 reads only `0.1.1`: a
    `semantic_model` list at the root (`ossie_load` fails with
    `document has no 'semantic_model' array`). The committed file stays
    what the converter wrote. Your command bridges the gap at read
    time.

13. In chat: rank the 2025/26 table by `xg_difference` instead of
    points, with MetricFlow. Which team moves most, and what does that
    say about the question "strongest team"? Facts from the output
    only.

**Withheld:** how `dawri metrics` gets the extension loaded (and what
it does when it is not installed). How a 0.2.0.dev0 document becomes
something the extension accepts without editing the committed file. How
the extension wants dimensions and filters named (its error messages
tell you).

---

## Hard (optional): the definition cannot drift

**Target output**

```
$ mise run semantic-check
ossie: semantic/dawri.ossie.yaml matches dbt
parity 2026/2027: 18 teams, 0 differences

$ git push; gh run list --limit 1
completed  success  ...

$ (branch: points changed to 2 for a win in _semantic.yml only, pushed)
$ gh run list --limit 1
completed  failure  ...    <- semantic-check: semantic/dawri.ossie.yaml is stale
(branch deleted after)
```

**Spec**

14. `mise run semantic-check`, exit 0 only when both hold:
    - **No drift.** The Ossie document regenerated from the current dbt
      YAML is identical to the committed `semantic/dawri.ossie.yaml`.
      On a difference it prints `semantic/dawri.ossie.yaml is stale`
      and exits 1. It never overwrites the committed file.
    - **Parity.** For the live season, every row of `dawri metrics`
      equals MetricFlow's answer for the same four metrics grouped by
      `team__team_name`, compared at two decimals. It prints
      `parity <season>: <n> teams, <n> differences` and exits 1 when
      differences is not 0.
    The target block is the real data. In CI the database is the
    recorded data, so parity covers the 4 teams of the two recorded
    matches: `parity 2026/2027: 4 teams, 0 differences`.
15. CI runs `mise run semantic-check` after the dbt step, on every push.
    The recorded-data build is now 57 total (61 minus the 4 `full_data`
    tests).
16. Prove it red with the branch in the target output: change `points`
    in `_semantic.yml` so a win is worth 2, commit without running
    `mise run ossie`, push. Then answer in chat: had you also run
    `mise run ossie` and committed the new document, would any check in
    the repo fail? Run it and see. If nothing fails, name the check
    that is missing.

**Withheld:** how CI gets `mise`, `uvx` and the `ossie` extension. How
two CSV-shaped outputs from different tools are compared.

---

## Reference

### Versions, checked 2026-09-30

```
dbt (v2, Fusion)     2.0.4 in the project (2.0.6 on PyPI)
dbt-metricflow       0.15.0  (needs dbt-core >=1.11,<1.13; uvx pulls 1.12.5)
metricflow           0.213.0 (Apache 2.0 since 0.209.0, October 2025)
dbt-duckdb           1.11.0  (inside the uvx environment only)
apache/ossie         commit adfa9e4 (2026-09-29), spec 0.2.0.dev0 on main
apache-ossie         Python package, not on PyPI; lives in python/ in the repo
apache-ossie-dbt     converter, not on PyPI; lives in converters/dbt/
DuckDB ossie ext     community extension, version 5180c67, DuckDB 1.5.5
```

Both Ossie packages install from git at a pinned commit, for example:

```
uvx --from "git+https://github.com/apache/ossie@adfa9e4#subdirectory=converters/dbt" \
    ossie-dbt msi-to-ossie -i <semantic_manifest.json> -o <out.yaml> --model-name <name>

uv run --with "apache-ossie @ git+https://github.com/apache/ossie@adfa9e4#subdirectory=python" ...
    from ossie.models import OssieDocument
```

The official validator (`validation/validate.py` in the repo) reads the
JSON Schema by a path relative to its own file, so it only runs from a
checkout of the repo, not from a URL.

### What dbt v2 can and cannot do here (checked on 2.0.4)

```
latest semantic YAML          parsed; target/semantic_manifest.json written
legacy semantic_models: YAML  dbt1157 warning, semantic manifest EMPTY
dbt sl query / list           needs a dbt platform project (dbt_cloud.yml):
                              "Missing project in dbt_cloud.yaml"
osi/ folder import            dbt 1.12 only; docs: "v2 support is coming soon"
target/osi_document.json      dbt 1.12 only
dbt MCP semantic-layer tools  need the dbt platform (DBT_HOST, DBT_TOKEN)
```

That is why the export goes through the converter: dbt v2 writes the
semantic manifest, and the converter reads it.

### Ossie document shape

`0.2.0.dev0` (what the converter writes, what `OssieDocument` accepts):

```yaml
version: 0.2.0.dev0
name: <model>
datasets:
  - name: <dataset>
    source: <database.schema.table>
    primary_key: [<column>]
    fields:
      - name: <field>
        expression: {dialects: [{dialect: ANSI_SQL, expression: <sql>}]}
        dimension: {is_time: <bool>}      # only on dimensions
relationships:
  - {name: ..., from: <dataset>, to: <dataset>, from_columns: [...], to_columns: [...]}
metrics:
  - name: <metric>
    expression: {dialects: [{dialect: ANSI_SQL, expression: <aggregate sql>}]}
```

`0.1.1` (what the DuckDB extension reads):

```yaml
version: "0.1.1"
semantic_model:
  - name: <model>
    datasets: [...]
    relationships: [...]
    metrics: [...]
```

There are no `measures` or `entities` keys in Ossie. Keys come from
`primary_key`, joins from `relationships`, and a metric is a SQL
aggregate over qualified columns (`SUM(<dataset>.<column>)`).

Spec text: `core-spec/spec.md` in github.com/apache/ossie. The dbt
converter's mapping rules: `converters/dbt/README.md`.

### The DuckDB `ossie` extension

```sql
INSTALL ossie FROM community;   -- once per machine, needs the network
LOAD ossie;
SELECT * FROM ossie_load('<path to a 0.1.1 document>');
SELECT * FROM ossie_metrics();
SELECT * FROM ossie_query([<metric names>], [<dimensions>], [<filters>]);
```

`ossie_load` returns one row: name, version, datasets, fields,
relationships, metrics. On the mid-tier document: `dawri, 0.1.1, 2, 8,
1, 11`. A dataset's `source` is resolved as written, so
`"dawri"."marts"."fct_team_matches"` needs the database file to be
attached as `dawri`, which `data/dawri.duckdb` is by its file name.

### Numbers on the real data (landed 2026-09-25)

```
fct_team_matches   738 rows   2025/26: 612   2026/27: 126 (63 finished)
                   result: W 280, D 178, L 280
dim_teams          21 rows
time spine         7,305 rows

2025/26 by venue   home: 475 points, xg_difference +61.98
                   away: 373 points, xg_difference -61.98
2026/27 by month   2026-08: 95 points   2026-09: 75 points

2025/26 top 3      points  played  gd   xg_for  xg_against  points_per_match
Al Nassr           86      34      63   64.38   21.95       2.53
Al Hilal           84      34      58   68.05   19.76       2.47
Al Ahli            81      34      46   54.19   23.04       2.38
```

### Recorded data (the CI database)

```
fct_team_matches   4 rows (2 finished matches)
dim_teams          18 rows (all teams of the recorded teams file)
dbt, no full_data  easy 53 total, mid 57 total
```
