# Lesson 4 build task: dbt I, sources and staging

Lesson 3 put six raw tables in `data/dawri.duckdb`, schema `raw`.
From here on the pipeline is SQL over those tables, and dbt is the
tool that runs it. This lesson builds the staging layer: one model
per raw table, renamed and typed, one row per thing, nothing
computed yet. Marts, the tables that answer questions, are lesson 5.
The raw tables stay exactly as `load.py` built them; dbt reads them
and never writes to schema `raw`.

## dbt in six lines

A dbt project is a folder with `dbt_project.yml` and a `models/`
folder. A model is a `.sql` file holding one `select`; its file name
is its table name. `{{ source('raw', 'matches') }}` in a model
resolves to `raw.matches`, declared once in a `sources.yml`.
`{{ ref('stg_matches') }}` resolves to another model, and that
reference is how dbt knows the build order. `profiles.yml` says
which database: for the DuckDB adapter that is a `path` to the
`.duckdb` file and a `schema` the models land in. `dbt build` creates
every model in dependency order, then runs every test declared in
YAML, and ends with two lines:

```
Processed: 6 models | 6 tests
Summary: 12 total | 12 success
```

Those two lines are the gate in every tier.
To look at data: `uv run dbt show --inline "select ..." --limit 20`
prints a query as a table (`--limit`, never `limit` in the SQL, dbt
adds its own). Note for the Python client: fetching a `TIMESTAMPTZ`
column through `duckdb.connect()` needs `pytz`; cast it to
`VARCHAR` in the query and it does not.

## Input

The six raw tables, as lesson 3 left them. Column names are already
snake_case. Every id column is a `VARCHAR` URN.

`raw.matches`, 306 rows, 36 columns. The ones that matter:

```
match_id               VARCHAR
match_date_utc         VARCHAR   '2025-08-28T16:05:00Z'
match_date_local       VARCHAR   '2025-08-28T19:05:00'
local_time_utc_offset  VARCHAR   '+03:00', the same on all 306
status                 VARCHAR   'FINISHED' on all 306
win_reason             VARCHAR   'Draw' on 70, 'RegularTime' on 236
win_team_id            VARCHAR   NULL on the 70 draws
home_score_push        BIGINT
away_score_push        BIGINT
time                   VARCHAR   '90' on all 306
additional_time        VARCHAR   '2' to '24'
home                   STRUCT    16 fields, home.teamId, home.shortName, ...
away                   STRUCT    same 16 fields
match_set              STRUCT    14 fields, match_set.matchSetId, match_set.name
stadium_name           VARCHAR
city_name              VARCHAR
```

Eight columns are `INTEGER` holding only NULL: `round_id`,
`round_name`, `group`, `group_name`, `group_id`,
`provider_penalty_score_home`, `provider_penalty_score_away`,
`previous_legs_result`. Cup-format fields, unused in a league.

Kickoffs run from `2025-08-28T16:05:00Z` to `2026-05-21T18:00:00Z`,
107 distinct days. Every `match_set.matchSetId` is one of the 34
matchday ids, and every matchday has exactly 9 matches.

DuckDB's session `TimeZone` on your machine is `Asia/Riyadh`. Two
casts of the same string give two different texts back:

```sql
select '2025-08-28T16:05:00Z'::TIMESTAMP::VARCHAR     -- 2025-08-28 16:05:00
select '2025-08-28T16:05:00Z'::TIMESTAMPTZ::VARCHAR   -- 2025-08-28 19:05:00+03
```

`raw.matchdays`, 34 rows, 14 columns:

```
match_set_id     VARCHAR   'spl::Football_MatchDay::b51ca594...'
name             VARCHAR   'Matchday 1'
short_name       VARCHAR   'MD 1'
index            INTEGER   NULL on all 34
matchday_status  VARCHAR   'Played' on all 34
start_date_utc   VARCHAR   '2025-08-28T00:00:00Z'
end_date_utc     VARCHAR   '2025-08-30T00:00:00Z'
```

`raw.teams`, 18 rows, 15 columns: `team_id`, `short_name`,
`official_name`, `acronym_name` (`'AHL'`), `country_code` (`'SA'`),
`team_type` (`'club'`), and `stadium`, a `STRUCT` with `name` and
`cityName`. `imagery` is a struct of four logo URLs.

`raw.standings`, 54 rows: 18 teams x 3 blocks, `type` is `'table'`,
`'home'` or `'away'`. The 12 stats sit in one column:

```
type      VARCHAR
team_id   VARCHAR
stats     STRUCT(statsId VARCHAR, statsLabel VARCHAR, ..., statsValue VARCHAR)[]
```

`statsValue` is JSON text, because lesson 3 had to put an int, a
string, a list and a null into one column. The 18 `table` rows carry
these 12 `statsId`s, in this order, with these values on the row
for Al Hilal. The 36 `home` and `away` rows carry the first 11
only: there is no `form` entry on them at all.

```
rank             '2'
team             'null'
points           '84'
matches-played   '34'
win              '25'
draw             '9'
lose             '0'
goals-for        '85'
goals-against    '27'
goal-difference  '58'
movement         '"stable"'         also '"up"', '"down"'
form             '[{"formLabel": "Win", "formLabelAbbreviation": "W",
                    "formType": "W"}, ...]'   6 entries, most recent
                                              match first
```

Cross-checks that hold: `win` summed over the `table` block is 236,
over `home` is 135, over `away` is 101. Matches has 236 non-draws,
135 won by the home side, 101 by the away side. `points` summed
over the `table` block is 848.

`raw.teamstats`, 76,648 rows, one per stat per match:

```
match_id                 VARCHAR
stats_id                 VARCHAR   322 distinct
stats_label              VARCHAR
stats_unit               VARCHAR   NULL on 308 ids, 'kilometeres' on 7,
                                   'kilometres per hour' on 7
stats_value_home         DOUBLE
stats_value_away         DOUBLE
```

`(match_id, stats_id)` is unique. Two naming families share the
column: 61 kebab-case ids with a human label (`goals-scored`,
`'Goals Scored'`) and 261 camelCase Opta ids whose label is the id
itself (`totalFwdZonePass`). Some measure the same thing: `goals`
and `goals-scored` both sum to 921 across the season, and 921 is
what `home_score_push + away_score_push` sums to in matches. That
overlap is lesson 5's problem, not this one's.

`raw.playerstats`, 1,387,916 rows, one per stat per player per
match:

```
match_id      VARCHAR
player_id     VARCHAR   654 distinct players
team_id       VARCHAR
stats_id      VARCHAR   324 distinct
stats_label   VARCHAR
stats_value   DOUBLE    NULL on exactly one id, average-position,
                        once per player per match (12,164 rows)
```

12,164 player-match entries, 37 to 40 players per match, 67 to 188
stats per entry. `(match_id, player_id, stats_id)` is NOT unique:
17,183 keys appear twice. That comes from the raw file, not from
the load: inside one player's `stats` list the same `statsId`
appears twice, with the same `statsValue` both times and sometimes a
different label (`'Fouls'` and `'fouls'`). Three ids do this:
`chances-created` on every one of the 12,164 entries, `fouls` on
4,460, `saves` on 559. Distinct on the key gives 1,370,733 rows.

Also two ids for minutes: `minutes` on all 12,164 entries,
`minsPlayed` on 9,214. Where both exist they are equal; `minsPlayed`
is missing exactly on the 2,950 entries where `minutes` is 0. Not
this lesson's decision either; lesson 5 needs it for per-90.

## Easy tier (start here)

1. Add `dbt` to the project. Create a dbt project in a
  folder at the repo root. The folder name is yours; the project
   `name` is `dawri`. The profile points at `data/dawri.duckdb` and
   lands models in schema `staging`. `uv run dbt debug` passes.
2. Declare `raw.matches` as a source. Build `stg_matches`: one row
  per match, read through `source()`, exactly these 16 output
   columns, in this order. Left is the raw column, right is what
   leaves the model. Nothing else leaves; the other 20 raw columns
   are dropped.

```
match_id               -> match_id            VARCHAR, unchanged
match_date_utc         -> kickoff_utc         a timestamp type, your choice
match_date_local       -> kickoff_local       TIMESTAMP
local_time_utc_offset  -> utc_offset          VARCHAR, unchanged
status                 -> status              VARCHAR, unchanged
win_reason             -> win_reason          VARCHAR, unchanged
win_team_id            -> win_team_id         VARCHAR, unchanged
home_score_push        -> home_score          BIGINT, unchanged
away_score_push        -> away_score          BIGINT, unchanged
time                   -> minutes_played      INTEGER
additional_time        -> additional_minutes  INTEGER
home.teamId            -> home_team_id        VARCHAR, pulled out of the struct
away.teamId            -> away_team_id        VARCHAR, pulled out of the struct
match_set.matchSetId   -> matchday_id         VARCHAR, pulled out of the struct
stadium_name           -> stadium_name        VARCHAR, unchanged
city_name              -> city_name           VARCHAR, unchanged
```

   The three structs do not leave the model. Team names, logos and
   matchday names live in `raw.teams` and `raw.matchdays`; the ids
   above are the join keys to them. The one open choice is the type
   of `kickoff_utc`: `TIMESTAMP` or `TIMESTAMPTZ`. Step 4 is where
   you defend it.
3. Run `uv run dbt build`. Last two lines:

```
Processed: 1 model
Summary: 1 total | 1 success
```

   Then `uv run dbt show --inline "select count(*) as n from    {{ ref('stg_matches') }}"`:

```
|   n |
| --- |
| 306 |
```

1. Answer here, in words: the raw string is `16:05Z`. One cast gives
  back `16:05:00`, the other `19:05:00+03`. Are those the same
   instant? Which type did your model choose, and what does the
   `+03` on the way out depend on, so what would the same query
   print on a machine set to UTC? Then: if lesson 5 wants "kickoff
   in Riyadh local time", which of `match_date_utc`,
   `match_date_local` and `local_time_utc_offset` does it build from,
   and why not the other two? Say how you checked, not just the
   answer.

**Withheld:** which timestamp type `kickoff_utc` gets. That decision
is the lesson, and step 4 is where you make the case for it.

## Mid tier (builds on easy)

1. Stage the other five. Same format as step 2: left is the raw
  column, right is what leaves the model, in this order, nothing
   else leaves. Every model also has one key column, named below,
   that is unique per row. Where the grain is two or three raw
   columns, how you make one key column out of them is withheld.
   `stg_matchdays`, 34 rows, key `matchday_id`:

```
match_set_id     -> matchday_id   VARCHAR, unchanged
name             -> name          VARCHAR, unchanged
short_name       -> short_name    VARCHAR, unchanged
start_date_utc   -> start_utc     the type you gave kickoff_utc
end_date_utc     -> end_utc       the type you gave kickoff_utc
matchday_status  -> status        VARCHAR, unchanged
```

   The other 8 raw columns are dropped.

   `stg_teams`, 18 rows, key `team_id`:

```
team_id           -> team_id           VARCHAR, unchanged
short_name        -> short_name        VARCHAR, unchanged
official_name     -> official_name     VARCHAR, unchanged
acronym_name      -> acronym           VARCHAR, unchanged
country_code      -> country_code      VARCHAR, unchanged
stadium.name      -> stadium_name      VARCHAR, pulled out of the struct
stadium.cityName  -> city_name         VARCHAR, pulled out of the struct
stadium.capacity  -> stadium_capacity  BIGINT, pulled out of the struct
imagery.teamLogo  -> logo_path         VARCHAR, pulled out of the struct
```

   The other 6 raw columns and the rest of both structs are dropped.

   `stg_standings`, 54 rows, one per team per block, key
   `standing_key`, unique per `(type, team_id)`:

```
(built by you)          -> standing_key     one column, unique per (type, team_id)
type                    -> type             VARCHAR, 'table' | 'home' | 'away'
team_id                 -> team_id          VARCHAR, unchanged
short_name              -> team_name        VARCHAR, unchanged
stats: rank             -> rank             INTEGER
stats: points           -> points           INTEGER
stats: matches-played   -> played           INTEGER
stats: win              -> won              INTEGER
stats: draw             -> drawn            INTEGER
stats: lose             -> lost             INTEGER
stats: goals-for        -> goals_for        INTEGER
stats: goals-against    -> goals_against    INTEGER
stats: goal-difference  -> goal_difference  INTEGER
stats: movement         -> movement         VARCHAR, 'up' | 'down' | 'stable', no quotes
stats: form             -> form             VARCHAR, the JSON list text as is; NULL on home and away rows
```

   `stats: rank` means the `statsValue` of the entry in the `stats`
   list whose `statsId` is `rank`. The `team` entry and the other 17
   raw columns are dropped.

   `stg_teamstats`, 76,648 rows, key `team_stat_key`, unique per
   `(match_id, stats_id)`:

```
(built by you)     -> team_stat_key  one column, unique per (match_id, stats_id)
match_id           -> match_id       VARCHAR, unchanged
stats_id           -> stat_id        VARCHAR, unchanged
stats_label        -> stat_label     VARCHAR, unchanged
stats_unit         -> stat_unit      VARCHAR, unchanged
stats_value_home   -> home_value     DOUBLE, unchanged
stats_value_away   -> away_value     DOUBLE, unchanged
```

   The two abbreviation columns are dropped.

   `stg_playerstats`, 1,370,733 rows, key `player_stat_key`, unique
   per `(match_id, player_id, stats_id)`:

```
(built by you)  -> player_stat_key  one column, unique per (match_id, player_id, stats_id)
match_id        -> match_id         VARCHAR, unchanged
player_id       -> player_id        VARCHAR, unchanged
team_id         -> team_id          VARCHAR, unchanged
stats_id        -> stat_id          VARCHAR, unchanged
stats_label     -> stat_label       VARCHAR, unchanged
stats_unit      -> stat_unit        VARCHAR, unchanged
stats_value     -> value            DOUBLE, unchanged
```

   The two abbreviation columns are dropped. The raw table has
   1,387,916 rows; this model has 1,370,733, one per key.

1. Every model declares its key in YAML with exactly one `unique`
  and one `not_null` test, on the key column named above, nothing
   else. Six models, twelve tests. `uv run dbt build`, last two
   lines:

```
Processed: 6 models | 12 tests
Summary: 18 total | 18 success
```

1. Verify with `dbt show`, exact results:

```sql
select count(*) from {{ ref('stg_playerstats') }}     -- 1370733
select count(*) from {{ ref('stg_teamstats') }}       --   76648
select count(*) from {{ ref('stg_standings') }}       --      54

select type, team_name, rank, points, goal_difference
from {{ ref('stg_standings') }}
where type = 'table' order by rank
-- table Al Nassr 1 86 63 / table Al Hilal 2 84 58 / table Al Ahli 3 81 46 ...

select type, sum(won) from {{ ref('stg_standings') }} group by 1
-- table 236 / home 135 / away 101
```

1. Run `uv run load.py`, then `uv run dbt build` again. Same last
  two lines. `load.py` drops and recreates every raw table; staging
   must not care.
2. Answer here, in words: your `unique` test on `stg_playerstats`
  fails on the raw grain, 17,183 keys twice. Say what you found
   when you looked at the doubled rows, what staging does about it,
   and why that is safe. Then the opposite case: if the two copies
   had carried different values, what should staging do instead?

**Withheld, all of them "how", none of them "what":** how a list of
structs holding JSON text becomes the twelve typed columns above.
How one key column is built from a two- or three-column grain. What staging does to get from 1,387,916
rows to 1,370,733. And whether each model is a view or a table:
1.37 million rows either recompute on every query or sit on disk,
and that choice is per model.

## Hard tier (optional)

`form` on the 18 `table` rows of `stg_standings` is the JSON list
text, six entries, most recent result first: Al Nassr's reads
`W D W L W W` and their last six matches, newest first, went W, D,
W, L, W, W. Lesson 5 wants "last five results" per team as rows.

1. Build `stg_standings_form` from `ref('stg_standings')`, the 18
  `table` rows only. 108 rows, key `form_key`, unique per
    `(team_id, position)`:

```
(built by you)      -> form_key   one column, unique per (team_id, position)
team_id             -> team_id    VARCHAR
list index          -> position   INTEGER, 1 = most recent, 6 = oldest
formType of entry   -> result     VARCHAR, 'W' | 'D' | 'L'
```

```
Same YAML rule, so:
```

```
Processed: 7 models | 14 tests
Summary: 21 total | 21 success
```

```
And:
```

```sql
select result, count(*) from {{ ref('stg_standings_form') }} group by 1
-- L 42 / W 41 / D 25
```

**Withheld:** how JSON list text becomes rows with a position.

## Constraints

- Models read the raw tables through `source()` only. No model
reads `data/*.json`. Zero network.
- dbt never writes to schema `raw`. `load.py` owns it and rebuilds
it from scratch; step 8 is the check.
- `ingest.py`, `contracts.py` and `load.py` are never modified.
- The database path in the profile is relative to the project, not
absolute, and `profiles.yml` lives in the repo, not in `~/.dbt`.
This repo runs on the Mac and the Linux box; a path with a home
directory in it works on one of them. dbt's `target/`, `logs/`
and `dbt_packages/` are gitignored.
- Column names stay snake_case. Renames are allowed and expected
where a raw name says nothing (`home_score_push`).
- `stg_teamstats` and `stg_playerstats` stay long: one row per
stat. 322 and 324 ids do not become columns here. Lesson 5 picks
which ones do. Stat values stay numbers.
- `stg_standings` is wide: the 12 ids are the same on every row, so
they are columns, with the names and types in step 5.
- Exactly one `unique` and one `not_null` test per model, on its
key. The `Summary:` total is exact because of this rule.
- Use the tools people use. dbt packages (`dbt_utils`,
`dbt_expectations`, ...), macros and dbt's own features are
encouraged: the point of working in dbt is exposure to its
ecosystem. Add a package through `packages.yml`, run `dbt deps`,
commit `package-lock.yml`. Know what the macro compiles to
(`dbt compile` shows it), so you can defend it.



## Rules

- No skeleton on purpose. The design decisions are the lesson.
- `dbt` is the real dependency and you add it. That is dbt v2, the
Fusion engine: a Rust binary with the DuckDB adapter built in.
`uv add dbt` on Python 3.14 gives 2.0.4 today. On first run it
downloads the DuckDB driver once and caches it; after that it is
offline. The `Summary:` lines above are that version's format.
- No Python file this lesson, so `ruff` and `ty` have nothing to
check. Two gates: `uv run dbt debug`, then `uv run dbt build`.
- Answer steps 4 and 9 here in words, not in a file.
- When it builds and the lines match, tell me and I will review
your models.

