# L5: dbt II, marts and tests

## The concept

### The problem

Lesson 4 staged six raw tables. Staging renames and types, it
computes nothing. So far Dawri has not answered a single football
question, and the first one is the obvious one: what is the league
table?

1. **The easy way teaches nothing and proves nothing.** The API
   publishes its own table, and it is sitting in `stg_standings`.
   Copying it is a `select *`. But then Dawri only repeats what the
   API says, and can never compute a table the API does not publish.
2. **Computing it yourself can be silently wrong.** A league table
   from 306 results looks simple: 3 points, 1 point, order by points.
   Then two teams tie on 37 points and the obvious tie-break puts
   them the wrong way round. Without something to check against, you
   would never know.
3. **"It looks right" is not a test.** A mart needs a proof that runs
   on every build, not a glance at the top three rows.

### What we want

`mart_standings`, computed from `stg_matches` alone, and proven equal
to the API's table by a test, row for row and column for column. The
API's table is the answer key. The mart never reads it: it only ever
sits on the other side of a test.

### What you will understand at the end

| Idea | In one line |
|---|---|
| Staging vs mart | Staging cleans. A mart computes: it is the table that answers a question. |
| A test is a query | It returns the rows that are wrong. Zero rows is a pass. |
| Generic vs singular | Generic tests are declared in YAML and written for you. A singular test is a `select` you write. |
| Answer key testing | Derive the numbers independently, then test against a trusted source, in both directions. |
| Rules hide in ties | The real ranking rule only shows where two teams tie. Head to head comes before goal difference here. |

Easy builds the overall table and lets a test find the tie-break bug.
Mid adds the home and away blocks and swaps in package tests. Hard
checks the API's form claim against the matches.

### Before and after

```
BEFORE                                  AFTER
staging only, nothing computed          mart_standings, 54 rows, from stg_matches alone
the league table is the API's word      every rank recomputed and tested against the API
2 tests per model (unique, not_null)    generic + package + singular tests
everything lands in schema staging      marts land in schema marts, as tables
```

Guardrails for every tier:

- Marts read staging through `ref()` only. No mart calls `source()`, no mart reads `data/*.json`. Zero network.
- `mart_standings` never reads `stg_standings`, and `mart_team_form` never reads `stg_standings` or `stg_standings_form`. The API's numbers are only ever on the other side of a test.
- The six lesson 4 staging models are not modified. The hard tier adds `stg_standings_form` if it is missing, nothing else changes in staging.
- dbt never writes to schema `raw`. `ingest.py`, `contracts.py` and `load.py` are never modified.
- Tests per tier are exactly the ones listed. The `Summary:` total is exact because of this rule.
- Use the tools people use: dbt packages, macros, dbt's own features. Add a package through `packages.yml`, run `dbt deps`, commit `package-lock.yml`. Know what each macro and generic test compiles to (`dbt compile` writes it under `target/`).
- Gates: `uv run dbt build` last two lines, then the `dbt show` results. Close DBeaver and the DuckDB CLI first: DuckDB allows one writer.
- `dbt show` prints a box table, not the one-line comments below. The comments give the values in row order.

---

## Easy: the overall table, and the bug a test finds

**Target output**

`uv run dbt build`, last two lines, after step 5:

```
Processed: 7 models | 15 tests
Summary: 22 total | 22 success
```

`dbt show`, exact results:

```sql
select rank, team_name, points, goal_difference
from {{ ref('mart_standings') }} where points = 37 order by rank
-- 11 Al Fateh 37 -14 / 12 Al Khaleej 37 -8

select sum(points), sum(won), sum(goals_for) from {{ ref('mart_standings') }}
-- 848 / 236 / 921
```

**Spec**

1. Marts live in `models/marts/`, are materialized as tables, and
   land in schema `marts`. Staging stays in `staging`. Fact to know
   before you start: dbt's default rule glues a model's custom schema
   onto the profile's schema, so `+schema: marts` on its own gives
   `staging_marts`. The schema in DuckDB must be named `marts`.
2. Build `mart_standings`: the `table` block only, 18 rows, one per
   team, key `team_id`. It reads `ref('stg_matches')` and
   `ref('stg_teams')`, nothing else. Exactly these 11 columns, in
   this order:

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
   `goal_difference`, then `goals_for`, all higher first. Rules 2 and
   3 of the ranking rule (see Reference) are left out on purpose in
   this step.
4. Tests. In YAML, exactly one `unique` and one `not_null` on
   `team_id`. Then one singular test, `tests/` folder, file name
   yours: it returns a row for every difference between
   `mart_standings` and the 18 `table` rows of `stg_standings`, on
   all 11 columns. A row in the mart that is not in the API is a
   difference, and a row in the API that is not in the mart is a
   difference too. `uv run dbt build`, last two lines:

   ```
   Processed: 7 models | 15 tests
   Summary: 22 total | 21 success | 1 error
   ```

   Your singular test fails, and dbt says with how many rows:

   ```
   Test failed (4 failed row(s)): <your test name>
   ```

5. Add rules 2 and 3 to `rank`, so it follows all five rules. The
   build now ends with the target output.
6. Verify with `dbt show`: the exact results in the target output.
7. In chat: in step 4 the test failed with 4 rows. Which teams were
   they, and why 4 rows for that many teams? Then: your test checks
   both directions. Give one concrete wrong mart that a one-direction
   check would have passed. Last: why must `mart_standings` not read
   `stg_standings`, when reading it would make the test pass on the
   first try?

**Withheld:** how the schema comes out as `marts` and not
`staging_marts`. How "points from the matches between the tied teams"
becomes SQL. How your singular test finds differences in both
directions.

---

## Mid: three blocks, package tests

**Target output**

`uv run dbt build`, last two lines:

```
Processed: 7 models | 19 tests
Summary: 26 total | 26 success
```

`dbt show`, exact results:

```sql
select type, count(*), sum(points) from {{ ref('mart_standings') }}
group by 1 order by 1 desc
-- table 18 848 / home 18 475 / away 18 373

select type, rank, team_name, points, goal_difference
from {{ ref('mart_standings') }} where type = 'home' and points = 26 order by rank
-- home 7 Al Hazem 26 -8 / home 8 Al Taawoun 26 5
```

After `uv run load.py`, a second `uv run dbt build` ends with the same
two lines.

**Spec**

8. Extend `mart_standings` to all three blocks: 54 rows, one per team
   per block, key `standing_key`, unique per `(type, team_id)`. The
   `home` block counts only home matches, `away` only away matches,
   `table` counts all. `rank` restarts at 1 in each block and uses
   the same five rules. Rule 2 still uses all meetings between the
   tied teams, home and away, whatever the block. Build
   `standing_key` the same way `stg_standings.standing_key` is built,
   so the same `(type, team_id)` gives the same key in both. Exactly
   these 13 columns, in this order:

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

   The easy tier's singular test is deleted, `dbt_utils.equality`
   does its job now. `dbt_expectations` is the package
   `metaplane/dbt_expectations`, version `[">=0.10.0", "<0.11.0"]`
   (0.10.10 today). `dbt deps` pulls it plus `godatadriven/dbt_date`,
   which it depends on. `package-lock.yml` lists three packages. On
   Fusion, test arguments sit under an `arguments:` key.
10. Verify with `dbt show`: the exact results in the target output.
11. Run `uv run load.py`, then `uv run dbt build` again. Same last
    two lines.
12. In chat: run `uv run dbt compile` and open what
    `dbt_utils.equality` compiled to under `target/`. Say in plain
    words what that query does, and how it compares to your easy-tier
    singular test. Then: the `table = home + away` test would still
    pass if every number in the mart were wrong in the same way. What
    does it catch that `dbt_utils.equality` does not, and when would
    that matter? Last: `stg_standings` has a `movement` column (`up`,
    `down`, `stable`) that this mart does not have. What would the
    mart need, that `stg_matches` alone does not give it in one row
    per team, to compute `movement`?

**Withheld:** how one model produces all three blocks. How rule 2
works inside a block when the tied pair is only tied in that block.

---

## Hard (optional): check the API's form claim

`stg_standings.form` on the 18 `table` rows is JSON list text, six
entries, most recent first. Lesson 4's hard tier turned it into rows.
If you did not build that, build it here. The API's form is a claim,
this tier checks it against the matches.

**Target output**

`uv run dbt build`, last two lines:

```
Processed: 9 models | 24 tests
Summary: 33 total | 33 success
```

```sql
select result, count(*) from {{ ref('mart_team_form') }} group by 1
-- D 25 / L 42 / W 41
```

**Spec**

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
    matches, from `ref('stg_matches')` only. 108 rows, key
    `form_key`, unique per `(team_id, position)`. Exactly these 9
    columns, in this order:

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
    `team_id`, `position`, `result`.

**Withheld:** how "last six per team" is picked. How JSON list text
becomes rows with a position.

---

## Reference

### Tests in five lines

A test in dbt is a query that returns the rows that are wrong. Zero
rows is a pass. A generic test is declared in YAML on a model or a
column (`unique`, `not_null`, `accepted_values`, and every test a
package ships); dbt writes the query for you. A singular test is a
`.sql` file in the project's `tests/` folder holding one `select` that
you write; its file name is its test name. `dbt build` runs both
kinds, and both count in the `tests` number of the gate line.

### Input and the answer key

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
