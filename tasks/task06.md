# L6: match detail

## The concept

### The problem

Lessons 1 to 5 built a pipeline over six families that were all about
results: who played, what the score was, what the season table says.
Dawri knows Al Hilal won 3-1. It does not know who scored, in which
minute, who assisted, who was on the pitch, or who refereed.

1. **Nothing describes the inside of a match.** "Best players per
   position" and "top scorers" need one row per thing that happened,
   and no table has that grain yet.
2. **Two endpoints describe the same goals and do not agree.** Over
   the same 306 matches, `lineups` gives 899 goals and `feed` gives
   921. The scores you already trust say 921. Picking a source by
   feel is how wrong numbers get in.
3. **An own goal belongs to two teams.** It is scored by a player on
   one team and counts for the other. Each source handles that its
   own way, and a fact table has to get it right on every row.

### What we want

Three new endpoints landed, five new raw and staging tables, and
`fct_goals`: one row per goal, 921 rows, tested so that every match's
goals add up to the score you already have. Which source it is built
from is decided with evidence.

### What you will understand at the end

| Idea | In one line |
|---|---|
| A pattern pays off | A fourth family is lesson 1 and lesson 3 again. Good structure makes new data cheap. |
| Fact table | One row per event, at the finest grain, with the keys to join everything else. |
| Source of truth | When two sources disagree, pick with evidence, and check more than the totals. |
| Reconciliation test | A fact is trusted when it adds up to a number you already trust: goals per side equal the score. |
| Nested unpacking | A list inside a list inside an object becomes rows that carry their parents' ids. |

Easy lands `lineups` with the pattern you know. Mid lands the rest,
stages it all and builds the goals fact. Hard puts the disagreement
itself in a table.

### Before and after

```
BEFORE                                  AFTER
6 families, all about results           9 families, 3 about what happened inside a match
scores only: 921 goals as a sum         fct_goals: 921 rows, scorer, minute, side, type
two sources disagree, unnoticed         source chosen with evidence, the 17 diffs in a mart
7 models, 19 tests                      13 models, 32 tests (14 and 35 with hard)
```

Guardrails for every tier:

- `ingest.py` and `load.py` are modified this lesson, that is the point of the easy tier. `contracts.py` is not touched.
- Three new families, no other endpoint. Zero requests on a rerun, 4 per second while pulling. The 918 files are the only network this lesson does.
- `data/` stays gitignored. Nothing under it is committed.
- dbt still reads raw through `source()` only and never writes to schema `raw`. The lesson 4 and 5 models are not modified.
- `fct_goals` reads one staging model, not the raw table.
- Exactly one `unique` and one `not_null` per new staging model, on its key. Marts get the tests listed in their step. The `Summary:` total is exact because of this rule.
- Use the tools people use. `load.py` unpacks JSON with plain Python today. Polars (`pl.json_normalize`) and pyarrow are both fair game. Whatever you pick, be able to say what it does to a null nested field.
- `ruff` and `ty` clean: two Python files change this lesson.
- Gates: the file counts and `load.py` output, then `uv run dbt build`, then the `dbt show` results. Close DBeaver and the DuckDB CLI first.

---

## Easy: land lineups

**Target output**

After `uv run ingest.py`, then `uv run load.py`:

```
data/lineups/0de9cda0d297418699a8357a8825d46c/  306 files
lineups: 12164        (the line load.py prints for the new family)
```

A second `uv run ingest.py` makes no requests, and a second
`uv run load.py` prints the same counts.

**Spec**

1. Extend `ingest.py` with `lineups`, the same way `teamstats` and
   `playerstats` were added in lesson 1: a path function, a fetch
   function, a write function, and a loop in `main` over the 306
   match ids. Files land at
   `data/lineups/{season_id}/{match_id}.json`, one per match. A rerun
   makes zero requests.
2. Extend `load.py` with a `lineups` family landing `raw.lineups`,
   12,164 rows, one row per player entry, fielded and benched
   together. Exactly these 17 columns. Left is the JSON path, right
   is the column:

   ```
   envelope matchId        -> match_id             VARCHAR
   home|away .teamId       -> team_id              VARCHAR
   which side the entry came from
                           -> side                 VARCHAR  'home' | 'away'
   which list it came from -> selection            VARCHAR  'fielded' | 'benched'
   home|away .tacticalFormation
                           -> tactical_formation   VARCHAR
   player .playerId        -> player_id            VARCHAR
   player .bibNumber       -> bib_number           VARCHAR, as it comes
   player .role            -> role                 BIGINT
   player .roleLabel       -> role_label           VARCHAR
   player .shortName       -> short_name           VARCHAR
   player .shirtName       -> shirt_name           VARCHAR
   player .nationality     -> nationality          VARCHAR
   player .nationalityIsoCode
                           -> nationality_iso_code VARCHAR
   player .isCaptain       -> is_captain           BOOLEAN
   player .isGoalkeeper    -> is_goalkeeper        BOOLEAN
   player .tacticalXPosition
                           -> tactical_x_position  VARCHAR, null on benched
   player .tacticalYPosition
                           -> tactical_y_position  VARCHAR, null on benched
   ```

   Everything else is dropped: `providerId`, the media name fields,
   `displayName`, `imagery`, the four all-null fields, the `staff`
   list, and the `events` list (mid tier lands that).
3. Run both scripts, twice each. Output matches the target.
4. In chat: `raw.playerstats` came from 12,164 player entries and
   `raw.lineups` has 12,164 rows. Are they the same 12,164
   `(match_id, player_id)` pairs? Check, give the numbers you got,
   and say what a row in one means that a row in the other does not.
   Lesson 2 rejected 43 players for having `role: 0`. Does this
   endpoint give those 43 a role? Show how you checked.

**Withheld:** nothing new. This tier is lesson 1 and lesson 3 applied
to a fourth match-level family, and you have written both before.

---

## Mid: matchfacts, feed, and the goals fact

**Target output**

`uv run dbt build`, last two lines:

```
Processed: 13 models | 32 tests
Summary: 45 total | 45 success
```

`dbt show`, exact results:

```sql
select count(*) goals, count(distinct match_id) matches,
       count(*) filter (goal_type = 'own-goal') own_goals
from {{ ref('fct_goals') }}
-- 921 / 291 / 38

select count(*) n, count(*) filter (side is null) no_side,
       count(*) filter (try_cast(event_id as bigint) is null) non_numeric_id
from {{ ref('stg_feed_events') }}
-- 26038 / 1519 / 2471

select min(attendance), max(attendance), sum(attendance) from {{ ref('stg_match_facts') }}
-- 193 / 53282 / 2328726
```

**Spec**

5. Add `matchfacts` and `feed` to `ingest.py`, same path scheme,
   `data/matchfacts/{season}/{match}.json` and
   `data/feed/{season}/{match}.json`. 612 more requests. Rerun makes
   zero.
6. Land four more raw tables in `load.py`.

   `raw.lineup_events`, 6,889 rows, one per entry in a player's
   `events` list:

   ```
   envelope matchId      -> match_id           VARCHAR
   home|away .teamId     -> team_id            VARCHAR
   player .playerId      -> player_id          VARCHAR
   event .type           -> type               VARCHAR
   event .label          -> label              VARCHAR
   event .time           -> time               BIGINT
   event .additionalTime -> additional_time    BIGINT
   event .relatedPlayerId
                         -> related_player_id  VARCHAR
   event .phase          -> phase              VARCHAR
   ```

   `raw.match_facts`, 306 rows, one per match:

   ```
   matchId                        -> match_id                VARCHAR
   stadium.stadiumId              -> stadium_id              VARCHAR
   stadium.stadiumName            -> stadium_name            VARCHAR
   location.cityName              -> city_name               VARCHAR
   enviroment.numberOfSpectators  -> number_of_spectators    VARCHAR, as it comes
   stadium.mapsGeoCodeLatitude    -> maps_geo_code_latitude  VARCHAR
   stadium.mapsGeoCodeLongitude   -> maps_geo_code_longitude VARCHAR
   ```

   `raw.match_officials`, 1,836 rows, one per referee per match:

   ```
   matchId              -> match_id     VARCHAR
   referee .refereeId   -> referee_id   VARCHAR
   referee .role        -> role         VARCHAR
   referee .roleLabel   -> role_label   VARCHAR
   referee .shortName   -> short_name   VARCHAR
   referee .nationality -> nationality  VARCHAR
   ```

   `raw.feed_events`, 26,038 rows, one per event:

   ```
   envelope matchId        -> match_id           VARCHAR
   event .eventId          -> event_id           VARCHAR, text, not all numeric
   event .type             -> type               VARCHAR
   event .label            -> label              VARCHAR
   which slot is filled    -> side               VARCHAR  'home' | 'away' | NULL
   filled slot .team.teamId
                           -> team_id            VARCHAR, NULL on phase markers
   filled slot .player.playerId
                           -> player_id          VARCHAR, NULL where absent
   filled slot .player.relatedPlayerId
                           -> related_player_id  VARCHAR
   filled slot .time       -> time               BIGINT
   filled slot .additionalTime
                           -> additional_time    BIGINT
   filled slot .phase, else event .phase
                           -> phase              VARCHAR
   event .homeScorePush    -> home_score_push    BIGINT
   event .awayScorePush    -> away_score_push    BIGINT
   event .timeStamp        -> time_stamp         VARCHAR
   ```

   The fat `team` object, `description`, `providerId`, the shot
   geometry (`xPosition`, `shotResult`, `xg`, which is null on all
   26,038) and every other type-specific field are dropped.
7. Stage all five new raw tables in dbt, one model each, same rules
   as lesson 4: rename, cast, one key column, exactly one `unique`
   and one `not_null` on it.

   ```
   stg_lineups          12,164   key lineup_key        per (match_id, player_id)
   stg_lineup_events     6,889   key lineup_event_key  per (match_id, player_id, type, time, additional_time)
   stg_feed_events      26,038   key feed_event_key    per (match_id, event_id)
   stg_match_officials   1,836   key official_key      per (match_id, role_label)
   stg_match_facts         306   key match_id
   ```

   Type the columns properly: `role` and the minute columns INTEGER,
   `is_captain` and `is_goalkeeper` BOOLEAN, the tactical positions
   and latitude and longitude DOUBLE, attendance INTEGER,
   `time_stamp` a timestamp. `event_id` stays VARCHAR, and the reason
   is in the Reference section.
8. Build `fct_goals` in `models/marts/`, 921 rows, one per goal, from
   `ref('stg_feed_events')`, joined to `ref('stg_matches')` for the
   team ids:

   ```
   goal_key            the feed event key
   match_id            VARCHAR
   event_id            VARCHAR
   scoring_side        VARCHAR  'home' | 'away', the side the goal counts for
   scoring_team_id     VARCHAR  the team the goal counts for
   player_id           VARCHAR  the scorer
   scorer_team_id      VARCHAR  the team the scorer plays for
   goal_type           VARCHAR  'goal' | 'penalty-goal' | 'own-goal'
   minute              INTEGER
   additional_minutes  INTEGER
   phase               VARCHAR
   home_score_after    INTEGER
   away_score_after    INTEGER
   ```

9. One singular test on `fct_goals`: for every one of the 306
   matches, the number of goals on each side equals that side's score
   in `stg_matches`. A match with no goals in the fact table still
   has to match its 0-0.
10. Verify with `dbt show`: the exact results in the target output.
11. In chat: the same 306 matches give 899 goals through `lineups`
    and 921 through `feed`, and the scores say 921. Say how you
    decided which source `fct_goals` is built from, and what you
    checked beyond the totals. Then the harder half: an own goal is
    scored by a player on one team and counts for the other. Say what
    each source does about that, how you found out, and which of the
    two needs your SQL to flip the side.

**Withheld, all "how":** how one `load.py` family unpacks a list
nested inside a list (`events` inside `fielded` inside `home`). How
the filled slot of `home` and `away` becomes one `side` column. How
the goal count per match is compared to a score that lives in another
model. Whether each new staging model is a view or a table: 26,038
rows is small, but say why you chose what you chose.

---

## Hard (optional): the disagreement as a table

**Target output**

`uv run dbt build`, last two lines:

```
Processed: 14 models | 35 tests
Summary: 49 total | 49 success
```

```sql
select sum(lineup_home_goals + lineup_away_goals) lineups,
       sum(feed_home_goals + feed_away_goals) feed,
       sum(home_score + away_score) score,
       count(*) n
from {{ ref('mart_goal_source_diff') }}
-- 41 / 63 / 63 / 17
```

**Spec**

12. Build `mart_goal_source_diff`: one row per match where the goals
    in `stg_lineup_events` disagree with the score, 17 rows, key
    `match_id`. `stg_lineup_events` has no side of its own, so join
    through `stg_lineups` to learn which team the player was on, and
    apply the own-goal rule you worked out in step 11.

    ```
    match_id            VARCHAR
    lineup_home_goals   INTEGER   from stg_lineup_events
    lineup_away_goals   INTEGER
    feed_home_goals     INTEGER   from fct_goals
    feed_away_goals     INTEGER
    home_score          INTEGER   from stg_matches
    away_score          INTEGER
    ```

13. Tests: `unique` and `not_null` on `match_id`, plus a row count
    test of exactly 17.

**Withheld:** how a model that exists to hold disagreements is tested
when the disagreement is the expected result.

---

## Reference

### The three endpoints

All three take a season id and a match id, same shape as `teamstats`
and `playerstats` in lesson 1. Note `matches/` in two of them and
`match/` in the third; the API is inconsistent and both spellings are
real.

```
seasons/{seasonId}/matches/{matchId}/lineups      ~52 KB   16 MB total
seasons/{seasonId}/match/{matchId}/matchfacts     ~4 KB   1.2 MB total
seasons/{seasonId}/matches/{matchId}/feed        ~160 KB   49 MB total
```

306 matches x 3 = 918 requests. At your 4 per second cap the floor is
four minutes; the server is slower than that, so budget 10 to 15.

### Response shapes

`lineups` has an envelope (`matchId`, `pitchSizeX`, `pitchSizeY`, both
null) and then `home` and `away`, each a team object carrying
`teamId`, `shortName`, `tacticalFormation`, `imagery`, and three
lists: `fielded` (11 players), `benched` (7 to 9), `staff` (1). A
player entry:

```
playerId             'spl::Football_Player::392aec...'
bibNumber            '1'          text, always present, always numeric
role                 1 2 3 4      never 0, never null
roleLabel            'Goalkeeper' 'Defender' 'Midfielder' 'Forward'
shortName            'Kewin'      shirtName, mediaFirstName, mediaLastName also present
nationality          'Brazil'     nationalityIsoCode 'BRA'
isCaptain            false        exactly one true per team per match
isGoalkeeper         true
tacticalXPosition    '0.5'        text; null on every benched player
tacticalYPosition    '1.03'       text; null on every benched player
events               []           see below
imagery              {...}        three webp paths
isOneBookingAway, isSuspended, averageXPosition, averageYPosition
                                  null on all 12,164 entries
```

Across the 306 files: 12,164 player entries, 6,732 fielded and 5,432
benched, 610 distinct players, 65 nationalities, 18 distinct
formations (`4-2-3-1` on 147 team-matches, `4-4-2` on 127). Roles:
1,307 goalkeepers, 4,074 defenders, 3,589 midfielders, 3,194
forwards. 612 staff entries, one per team per match, 607 `Head Coach`
and 5 `Assistant Coach`.

A player's `events` list, 6,889 entries in total:

```
{"type": "goal", "label": "Goal", "time": 90, "additionalTime": 8,
 "relatedPlayerId": "spl::Football_Player::19a2c9...", "phase": "SECOND_HALF"}

substitution-out 2393   substitution-in 2339   yellow-card 1185
goal 763   penalty-goal 102   red-card 49   own-goal 34
second-yellow-card 24
```

`relatedPlayerId` is the assist on a goal and the other half of a
substitution; it is null on cards.

`matchfacts` is flat: `stadium` (id, name, latitude, longitude),
`location.cityName`, `enviroment.numberOfSpectators` (text, present on
all 306, from 193 to 53,282, 2,328,726 in total), and `referees`, a
list of exactly 6 per match with fixed `roleLabel`s: `Referee`,
`Assistant Referee 1`, `Assistant Referee 2`, `Fourth Official`,
`VAR`, `Assistant VAR Official`. 1,836 referee entries in total. Its
own `status` field says `UPCOMING` and `phase` says `PRE_MATCH` on
every one of the 306 finished matches, and its `events` is null.

`feed` is the full event stream: `pagination` (`totalPages` is 1 on
all 306), the match envelope, and `events`, 26,038 entries over 20
types, newest first. Every event has `type`, `label`, `description`,
`eventId`, `timeStamp`, and a `home` and an `away` slot of which at
most one is filled. The filled slot carries `team` (a fat team object),
`time`, `additionalTime`, `phase` and `player`. 1,519 events have
neither slot filled: those are the match phase markers
(`first-half`, `half-time-break`, `second-half`, `end-second-half`,
`full-time`). Scoring events also carry `homeScorePush` and
`awayScorePush`, the running score after the event.

```
foul 6954   attempt-missed 4967   attempt-saved 3505   corner 3078
substitution 2471   injury-event 1219   yellow-card 1213   goal 780
full-time 306   end-second-half 306   first-half 306   second-half 301
half-time-break 300   penalty-goal 103   action-disallowed 93
red-card 50   own-goal 38   second-yellow-card 24
official-yellow-card 21   official-red-card 3
```

Two facts about `eventId`: it is text, and 2,471 of them are not
numbers (`'714_713_spl::opta::Football_Match::c24a7dc9...'`, every one
of them a `substitution`). `(matchId, eventId)` is unique across all
26,038.

Goals in the two sources, over the same 306 matches:

```
lineups player events   goal 763 + penalty-goal 102 + own-goal  34 = 899
feed events             goal 780 + penalty-goal 103 + own-goal  38 = 921
raw.matches             home_score_push + away_score_push            = 921
```
