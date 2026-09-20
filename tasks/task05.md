# Lesson 5 build task: dbt II, marts and tests

Lesson 4 staged six raw tables into schema `staging`. Staging renames
and types; it computes nothing. A mart computes: it is the table that
answers a question. This lesson builds the first one, the league
table, from match results alone, and proves it right by testing it
against the table the API publishes. The API's own table is sitting
in `stg_standings`, so the mart has an answer key. The mart must never
read that answer key; it must arrive at the same numbers from
`stg_matches`.

## Tests in five lines

A test in dbt is a query that returns the rows that are wrong. Zero
rows is a pass. A generic test is declared in YAML on a model or a
column (`unique`, `not_null`, `accepted_values`, and every test a
package ships); dbt writes the query for you. A singular test is a
`.sql` file in the project's `tests/` folder holding one `select` that
you write; its file name is its test name. `dbt build` runs both
kinds, and both count in the `tests` number of the gate line.

## Input

The six staging models from lesson 4, as you built them. The ones this
lesson reads:

`stg_matches`, 306 rows, one per match: `match_id`, `kickoff_utc`,
`home_team_id`, `away_team_id`, `home_score`, `away_score`. Every
team plays 34 matches, 17 at home and 17 away. No team plays twice at
the same `kickoff_utc`.

`stg_teams`, 18 rows: `team_id`, `short_name`.

`stg_standings`, 54 rows: the API's table, 18 teams x 3 blocks
(`table`, `home`, `away`). This is the answer key.

What the answer key says, facts you can check with `dbt show`:

- Points are 3 for a win, 1 for a draw, 0 for a loss. `points`
  summed over the `table` block is 848.
- In the `table` block, Al Fateh (rank 11) and Al Khaleej (rank 12)
  both have 37 points. Al Khaleej has the better goal difference,
  -8 against -14. Al Fateh is still above them.
- In the `home` block, Al Hazem (rank 7) and Al Taawoun (rank 8) both
  have 26 points. Al Taawoun has the better goal difference, +5
  against -8. Al Hazem is still above them.
- Every other tie on points, in all three blocks, is broken by goal
  difference. Every tie in this season is between exactly two teams.

The rule that reproduces all 54 ranks, checked row by row against the
API. Order teams within a block by:

```
1. points                                          higher first
2. points from the matches between the tied teams  higher first
3. goal difference in those matches                higher first
4. goal difference                                 higher first
5. goals for                                       higher first
```

"The matches between the tied teams" means all their meetings this
season, home and away, in every block. Al Fateh beat Al Khaleej 1-0
twice. Al Hazem drew 2-2 at Al Taawoun and won 2-0 at home.

## Easy tier (start here)

1. Marts live in `models/marts/`, are materialized as tables, and
   land in schema `marts`. Staging stays in `staging`. Fact to know
   before you start: dbt's default rule glues a model's custom schema
   onto the profile's schema, so `+schema: marts` on its own gives
   `staging_marts`. The schema in DuckDB must be named `marts`.
2. Build `mart_standings`: the `table` block only, 18 rows, one per
   team, key `team_id`. It reads `ref('stg_matches')` and
   `ref('stg_teams')`, nothing else. Exactly these 11 columns, in this
   order:

```
rank             INTEGER   1 to 18, rule in step 3, then step 5
team_id          VARCHAR
team_name        VARCHAR   stg_teams.short_name
played           INTEGER   matches played
won              INTEGER
drawn            INTEGER
lost             INTEGER
goals_for        INTEGER
goals_against    INTEGER
goal_difference  INTEGER   goals_for - goals_against
points           INTEGER   3 x won + drawn
```

3. First version of `rank`: order by `points`, then
   `goal_difference`, then `goals_for`, all higher first. Rules 2
   and 3 from the Input section are left out on purpose in this
   step.
4. Tests. In YAML, exactly one `unique` and one `not_null` on
   `team_id`. Then one singular test, `tests/` folder, file name
   yours: it returns a row for every difference between
   `mart_standings` and the 18 `table` rows of `stg_standings`, on all
   11 columns. A row in the mart that is not in the API is a
   difference; a row in the API that is not in the mart is a
   difference too. `uv run dbt build`, last two lines:

```
Processed: 7 models | 15 tests
Summary: 22 total | 21 success | 1 error
```

   Your singular test fails, and dbt says with how many rows:

```
Test failed (4 failed row(s)): <your test name>
```

5. Add rules 2 and 3 to `rank`, so it follows all five rules from the
   Input section. `uv run dbt build`, last two lines:

```
Processed: 7 models | 15 tests
Summary: 22 total | 22 success
```

6. Verify with `dbt show`, exact results:

```sql
select rank, team_name, points, goal_difference
from {{ ref('mart_standings') }} where points = 37 order by rank
-- 11 Al Fateh 37 -14 / 12 Al Khaleej 37 -8

select sum(points), sum(won), sum(goals_for) from {{ ref('mart_standings') }}
-- 848 / 236 / 921
```

7. Answer here, in words: in step 4 the test failed with 4 rows.
   Which teams were they, and why 4 rows for that many teams? Then:
   your test checks both directions. Give one concrete wrong mart
   that a one-direction check would have passed. Last: why must
   `mart_standings` not read `stg_standings`, when reading it would
   make the test pass on the first try?

**Withheld:** how the schema comes out as `marts` and not
`staging_marts`. How "points from the matches between the tied teams"
becomes SQL. How your singular test finds differences in both
directions.

## Mid tier (builds on easy)

8. Extend `mart_standings` to all three blocks: 54 rows, one per team
   per block, key `standing_key`, unique per `(type, team_id)`. The
   `home` block counts only home matches, `away` only away matches,
   `table` counts all. `rank` restarts at 1 in each block and uses the
   same five rules. Rule 2 still uses all meetings between the tied
   teams, home and away, whatever the block. Build `standing_key` the
   same way `stg_standings.standing_key` is built, so the same
   `(type, team_id)` gives the same key in both. Exactly these 13
   columns, in this order:

```
standing_key     VARCHAR   unique per (type, team_id), same value as in stg_standings
type             VARCHAR   'table' | 'home' | 'away'
rank             INTEGER   1 to 18 within the block
team_id          VARCHAR
team_name        VARCHAR
played           INTEGER
won              INTEGER
drawn            INTEGER
lost             INTEGER
goals_for        INTEGER
goals_against    INTEGER
goal_difference  INTEGER
points           INTEGER
```

9. Tests, replacing the easy tier's `mart_standings` tests. Exactly
   these seven, nothing else on the mart:

```
standing_key  unique                                       dbt built-in
standing_key  not_null                                     dbt built-in
type          accepted_values 'table', 'home', 'away'      dbt built-in
rank          values between 1 and 18                      dbt_expectations.expect_column_values_to_be_between
model         row count equals 54                          dbt_expectations.expect_table_row_count_to_equal
model         equals stg_standings on the 13 columns       dbt_utils.equality, compare_columns = the 13
tests/        one singular test: for every team, the table row equals home plus away
              on played, won, drawn, lost, goals_for, goals_against, points
```

   The easy tier's singular test is deleted; `dbt_utils.equality`
   does its job now. `dbt_expectations` is the package
   `metaplane/dbt_expectations`, version `[">=0.10.0", "<0.11.0"]`
   (0.10.10 today). `dbt deps` pulls it plus `godatadriven/dbt_date`,
   which it depends on; `package-lock.yml` lists three packages. On
   Fusion, test arguments sit under an `arguments:` key. `uv run dbt
   build`, last two lines:

```
Processed: 7 models | 19 tests
Summary: 26 total | 26 success
```

10. Verify with `dbt show`, exact results:

```sql
select type, count(*), sum(points) from {{ ref('mart_standings') }}
group by 1 order by 1 desc
-- table 18 848 / home 18 475 / away 18 373

select type, rank, team_name, points, goal_difference
from {{ ref('mart_standings') }} where type = 'home' and points = 26 order by rank
-- home 7 Al Hazem 26 -8 / home 8 Al Taawoun 26 5
```

11. Run `uv run load.py`, then `uv run dbt build` again. Same last
    two lines.
12. Answer here, in words: run `uv run dbt compile` and open what
    `dbt_utils.equality` compiled to under `target/`. Say in plain
    words what that query does, and how it compares to your easy-tier
    singular test. Then: the `table = home + away` test would still
    pass if every number in the mart were wrong in the same way.
    What does it catch that `dbt_utils.equality` does not, and when
    would that matter? Last: `stg_standings` has a `movement`
    column (`up`, `down`, `stable`) that this mart does not have.
    What would the mart need, that `stg_matches` alone does not give
    it in one row per team, to compute `movement`?

**Withheld:** how one model produces all three blocks. How rule 2
works inside a block when the tied pair is only tied in that block.

## Hard tier (optional)

`stg_standings.form` on the 18 `table` rows is JSON list text, six
entries, most recent first. Lesson 4's hard tier turned it into rows;
if you did not build that, build it here. The API's form is a claim;
this tier checks it against the matches.

13. If `stg_standings_form` does not exist, build it to lesson 4's
    hard-tier spec: from `ref('stg_standings')`, `table` rows only,
    108 rows, key `form_key` unique per `(team_id, position)`,
    columns `form_key`, `team_id`, `position` (INTEGER, 1 = most
    recent), `result` (VARCHAR, `'W'` | `'D'` | `'L'`). Build
    `form_key` from `(team_id, position)` the same way as step 14.
    Exactly one `unique` and one `not_null` on `form_key`. Fact:
    Fusion's static analysis types `from_json(x, '["json"]')` as
    `VARCHAR`, so an `unnest` over it fails at compile time with
    `TableFunctionResolutionFailed (dbt0210)`, even though DuckDB
    itself would run it.
14. Build `mart_team_form` in `models/marts/`: each team's last six
    matches, from `ref('stg_matches')` only. 108 rows, key `form_key`,
    unique per `(team_id, position)`. Exactly these 9 columns, in this
    order:

```
form_key       VARCHAR    unique per (team_id, position)
team_id        VARCHAR
position       INTEGER    1 = the team's most recent match by kickoff_utc, 6 = sixth most recent
match_id       VARCHAR
kickoff_utc    the type stg_matches gave it
opponent_id    VARCHAR    the other team in that match
goals_for      BIGINT     this team's goals in that match
goals_against  BIGINT
result         VARCHAR    'W' | 'D' | 'L' for this team
```

15. Tests on `mart_team_form`: one `unique` and one `not_null` on
    `form_key`, and one `dbt_utils.equality` against
    `stg_standings_form` with `compare_columns` = `form_key`,
    `team_id`, `position`, `result`. `uv run dbt build`, last two
    lines:

```
Processed: 9 models | 24 tests
Summary: 33 total | 33 success
```

    And:

```sql
select result, count(*) from {{ ref('mart_team_form') }} group by 1
-- D 25 / L 42 / W 41
```

**Withheld:** how "last six per team" is picked. How JSON list text
becomes rows with a position.

## Constraints

- Marts read staging through `ref()` only. No mart calls `source()`,
  and no mart reads `data/*.json`. Zero network.
- `mart_standings` never reads `stg_standings`, and `mart_team_form`
  never reads `stg_standings` or `stg_standings_form`. The API's
  numbers are only ever on the other side of a test.
- The six lesson 4 staging models are not modified. The hard tier
  adds `stg_standings_form` if it is missing; nothing else changes in
  staging.
- dbt never writes to schema `raw`. `ingest.py`, `contracts.py` and
  `load.py` are never modified.
- Tests per tier are exactly the ones listed. The `Summary:` total is
  exact because of this rule.
- Use the tools people use: dbt packages, macros, dbt's own features.
  Add a package through `packages.yml`, run `dbt deps`, commit
  `package-lock.yml`. Know what each macro and generic test compiles
  to (`dbt compile` writes it under `target/`), so you can defend it.

## Rules

- No skeleton on purpose. The design decisions are the lesson.
- Two gates: `uv run dbt build` last two lines, then the `dbt show`
  results. Close DBeaver and the DuckDB CLI first; DuckDB allows one
  writer.
- `dbt show` prints a box table, not the one-line comments above. The
  comments give the values in row order.
- Answer steps 7 and 12 here in words, not in a file.
- When it builds and the lines match, tell me and I will review your
  models.
