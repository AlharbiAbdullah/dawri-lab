# L12: serve the facts over HTTP (FastAPI)

## The concept

### The problem

Dawri's facts can be read by a person at this machine: a terminal, a
dashboard on localhost. Nothing else can ask. Three symptoms:

1. **Every consumer needs a shell here.** A phone, a teammate's
   script, lesson 13's actuator, an AI agent: each would have to run
   `dawri metrics`, `mf query` or `rill query` on this machine and
   parse a terminal table or a CSV.
2. **Every consumer opens the database itself.** Lesson 11 showed what
   that costs: one open reader and `dawri build` fails on the lock. Each
   new direct reader is one more process to keep out of the builder's
   way.
3. **Nothing promises a shape.** `dawri metrics` prints CSV. Add a
   column and every script that split on commas by position reads the
   wrong number, silently. A consumer has no document that says what
   comes back, what the types are, or what an error looks like.

### What we want

`dawri serve` starts an HTTP API. Every answer is JSON, validated by a
Pydantic response model, and described by an OpenAPI document the app
publishes itself. Standings come from `mart_standings`, metrics from
the lesson 10 definitions (same numbers as `dawri metrics`, `mf` and
Rill), match detail from the facts of lesson 6. `dawri build` works
while the API is serving. Errors are part of the contract: a wrong season is
404, a wrong parameter is 422, and a request never gets a 500 because a
build is running.

### What you will understand at the end

| Idea | In one line |
|---|---|
| Resource | A thing with an address (`/seasons/2025-2026/standings`). The URL names it, the method says what to do with it. |
| Response model | The type of what goes out. Validated on the way out, the same way lesson 2 validated what came in. |
| Status code | The first thing a client reads. 200, 404 and 422 mean different things to a program, not to a person. |
| OpenAPI | The API's own description, generated from the code, readable by people and by tools that write clients. |
| Contract test (hard) | A test that fails when the published shape changes, so a change is a decision, not an accident. |

### Before and after

```
BEFORE                                  AFTER
facts reachable from a shell here       GET http://127.0.0.1:8000/...
CSV and terminal tables                 JSON, one Pydantic model per answer
each consumer opens dawri.duckdb        consumers ask the API
no published shape                      /openapi.json, /docs
shape changes silently                  docs/openapi.json snapshot test (hard)
```

Guardrails for every tier:

- The numbers do not move. Every number the API returns equals what
  lessons 5, 6 and 10 return for the same question.
- Read only. No endpoint writes, deletes, triggers a run or accepts a
  body. `GET` only.
- Lesson 10's 2026/2027 freeze holds: no 2026/2027 ingest.
- From mid on, `dawri load && dawri build` succeeds while `dawri serve`
  is running and being queried (lesson 11's rule, now for the API).
- Tests never open a socket (lesson 9's rule): the app is called in
  process, and the suite stays under 10 seconds.
- `data/` and `logs/dawri.log` untouched by `uv run pytest`.
- Deterministic facts only. No endpoint for predictions, odds or
  "form rating".
- `ruff` and `ty` clean. Use FastAPI, Pydantic, uvicorn,
  `fastapi.testclient.TestClient`. Know what TestClient does instead of
  a socket.
- Gates: the target output of each tier.

---

## Easy: seasons and standings

**Target output**

```
$ uv run dawri --verbose serve          (second terminal)
...Z INFO uvicorn.error Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)

$ curl -s localhost:8000/health
{"status":"ok"}

$ curl -s localhost:8000/seasons
[{"season":"2025/2026","season_id":"0de9cda0d297418699a8357a8825d46c","finished":306,"upcoming":0},
 {"season":"2026/2027","season_id":"3677a75aaa514e43b2840e7fa367c91d","finished":63,"upcoming":243}]

$ curl -s "localhost:8000/seasons/2025-2026/standings?type=table" | jq '.[0]'
{"rank":1,"team_name":"Al Nassr","played":34,"won":28,"drawn":2,"lost":4,
 "goals_for":91,"goals_against":28,"goal_difference":63,"points":86}

$ curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/seasons/2024-2025/standings
404
$ curl -s localhost:8000/seasons/2024-2025/standings
{"detail":"unknown season: 2024-2025"}

$ curl -s -o /dev/null -w "%{http_code}\n" "localhost:8000/seasons/2025-2026/standings?type=all"
422

$ uv run pytest
50 passed
```

(The `/seasons` answer is one line; it is wrapped here to fit.)

**Spec**

1. `uv add fastapi uvicorn`. `src/dawri/api.py` holds the app.
2. `dawri serve`, a new command: runs the app with uvicorn on
   `127.0.0.1`, port 8000, `--port` to change it. Logging goes through
   lesson 8's setup, not a second one: uvicorn's lines come out in
   lesson 8's format, go to `logs/dawri.log`, and reach stderr only
   with `--verbose`, like every other INFO line.
3. Seasons in URLs are written `2025-2026`. The config names stay
   `2025/2026`; the JSON shows the config name.
4. Endpoints:

   ```
   GET /health
       200 {"status": "ok"}

   GET /seasons
       200, one object per season in config, config order:
       season     "2025/2026"
       season_id  the SPL id
       finished   FINISHED matches in stg_matches for that season (0 if none)
       upcoming   UPCOMING matches (0 if none)

   GET /seasons/{season}/standings?type=table|home|away
       type defaults to table. 200, mart_standings rows of that season and
       type, ordered by rank, fields in this order:
       rank, team_name, played, won, drawn, lost,
       goals_for, goals_against, goal_difference, points
       404 {"detail": "unknown season: <as written>"}   season not in config
       422                                              type not one of the three
   ```

   Every 200 body goes through a Pydantic response model. Integers are
   integers in the JSON, not strings.
5. `tests/test_api.py`, all through TestClient on a database built from
   the recorded fixtures (lesson 9):

   ```
   test_health                  200, {"status": "ok"}
   test_seasons                 2025/2026 finished 0 upcoming 0,
                                2026/2027 finished 2 upcoming 1
   test_standings_table         4 rows; first: NEOM SC, played 1, won 1,
                                goals 2-0, points 3; last: Al Faisaly, 0
   test_standings_home          2 rows: Diriyah 1, Al Faisaly 0
   test_unknown_season_404      detail "unknown season: 2024-2025"
   test_bad_type_422            type=all
   ```

   44 + 6 = 50 tests.

**Withheld:** how the tests get a database with the marts built from
recorded data without running dbt in every test, and still under 10
seconds. How one database connection (or none) serves many requests.
How uvicorn is kept from setting up its own logging.

---

## Mid: metrics, match detail, and serving during a build

**Target output**

```
$ curl -s "localhost:8000/seasons/2025-2026/metrics?metric=points&metric=xg_for" | jq '.[0:3]'
[{"team_name":"Al Nassr","points":86,"xg_for":64.38},
 {"team_name":"Al Hilal","points":84,"xg_for":68.05},
 {"team_name":"Al Ahli","points":81,"xg_for":54.19}]

$ curl -s "localhost:8000/seasons/2025-2026/metrics?metric=elo"
{"detail":"unknown metric: elo. Known: goal_difference, goals_against, goals_for,
 matches_played, points, points_per_match, shots, shots_on_target, xg_against,
 xg_difference, xg_for"}                                                   (422)

$ curl -s localhost:8000/matches/cb556acbac334114887ef91fcb725e0c
{"match_id":"cb556acbac334114887ef91fcb725e0c","season":"2026/2027",
 "kickoff_utc":"2026-08-21T18:00:00Z","status":"FINISHED",
 "stadium":"Al Majma'a Sport City Stadium",
 "home":{"team_name":"Al Faisaly","score":0},
 "away":{"team_name":"NEOM SC","score":2},
 "goals":[{"minute":51,"additional_minutes":0,"side":"away","team_name":"NEOM SC",
           "player_name":"A. Lacazette","goal_type":"goal"},
          {"minute":60,"additional_minutes":0,"side":"away","team_name":"NEOM SC",
           "player_name":"A. Lacazette","goal_type":"goal"}]}

$ (with dawri serve running and a loop requesting /seasons every 0.1 s)
$ (uv run dawri load && uv run dawri build) > /dev/null; echo $?
0                     <- and the loop saw only 200s

$ uv run pytest
56 passed
```

**Spec**

6. `GET /seasons/{season}/metrics?metric=<name>&metric=<name>...`
   - One or more `metric` values, each a metric in
     `semantic/dawri.ossie.yaml` (eleven today). The answer comes from
     the same code as `dawri metrics --metric` (lesson 10), not a copy
     of it. No metric expression or metric name is written in
     `api.py`.
   - 200: one object per team with a finished match in that season:
     `team_name`, then each metric in the order asked. Ordered by the
     first metric descending, then team name. Floats rounded to two
     decimals, integers stay integers.
   - 422 `unknown metric: <name>. Known: <every metric in the document,
     sorted, comma separated>` for any unknown name. 422 when no metric
     is given.
     404 for an unknown season, same as standings.
7. `GET /matches/{match_id}`, the 32-character hex id (the part after
   `spl::Football_Match::`):
   - 200 with the shape in the target output. `kickoff_utc` in ISO 8601
     with `Z`. For a match that is not FINISHED, both scores are `null`
     and `goals` is `[]`.
   - `goals` from `fct_goals`, ordered by minute then additional
     minutes. `team_name` is the team the goal counts for;
     `player_name` from `stg_lineups`, `null` when there is none.
   - 404 `unknown match: <id>` for a well-formed id that is not in the
     data. 422 for anything that is not 32 lowercase hex characters.
8. Serving during a build: the target output's loop sees only 200s
   while `dawri load && dawri build` runs, and it exits 0. A request
   during the build answers from the last good data.
   - Easy read `data/dawri.duckdb`. From here the API reads lesson 11
     mid's serving copy, and never `data/dawri.duckdb`.
   - The copy now also carries `staging.stg_matches` and
     `staging.stg_lineups`, the two staging tables the API reads.
   - The metrics endpoint reads the copy under the catalog name
     `dawri`, because the Ossie document's sources are
     `dawri.marts.<table>`.
   - If you skipped lesson 11 mid, its steps 7 to 9 are the spec.
9. Six more tests in `tests/test_api.py`:

   ```
   test_metrics_recorded        2026-2027, metric=points&metric=xg_for:
                                NEOM SC 3 1.30, Al Kholood 1 1.41,
                                Diriyah 1 0.56, Al Faisaly 0 0.60
   test_metrics_unknown_422     metric=elo, detail lists every metric
                                in the document, read from the document
   test_match_finished          cb556: the target output's body exactly
   test_match_upcoming          a10a6: status UPCOMING, scores null,
                                goals [], kickoff "2026-10-09T13:50:00Z"
   test_match_unknown_404       ffffffffffffffffffffffffffffffff
   test_match_malformed_422     "cb556" (too short)
   ```

   50 + 6 = 56 tests. Note the order in `test_metrics_recorded`:
   Al Kholood before Diriyah (name order), while `mart_standings`
   ranks Diriyah 2nd and Al Kholood 3rd. `test_standings_table` pins
   only the first and last row on purpose.
10. In chat: Diriyah and Al Kholood drew each other 1-1 and are level
    on points, head-to-head, goal difference and goals for. Read the
    `order by` that computes `rank` in `mart_standings.sql`. Is
    "Diriyah 2nd" a fact about the data? What should the API tell a
    client about two teams in that position, and what would you change,
    and where, so the answer is the same on every build?

**Withheld:** how the metrics endpoint and `dawri metrics` share one
implementation. How a path parameter is constrained to 32 hex
characters so that FastAPI answers 422 before your code runs.

---

## Hard (optional): the contract and the cache

**Target output**

```
$ uv run pytest tests/test_api.py -k contract
1 passed

$ (a field renamed in one response model)
$ uv run pytest tests/test_api.py -k contract
1 failed      <- docs/openapi.json no longer matches: run mise run openapi
$ (rename reverted)

$ curl -si localhost:8000/seasons/2025-2026/standings | grep -i etag
etag: "..."
$ curl -si -H 'If-None-Match: "<that etag>"' localhost:8000/seasons/2025-2026/standings | head -1
HTTP/1.1 304 Not Modified

$ uv run pytest
60 passed
```

**Spec**

11. `docs/openapi.json`, committed: the app's OpenAPI document,
    written by `mise run openapi`, formatted so a diff is readable.
    `test_openapi_contract` fails when `app.openapi()` differs from the
    committed file, and its message says which command updates it.
12. Every 200 on `/seasons...` and `/matches...` carries an `ETag`. The
    ETag is the same for the same answer on the same data, and changes
    when a load changes the data. A request with a matching
    `If-None-Match` gets `304` with an empty body.
13. Three more tests:

    ```
    test_etag_stable               two requests, same ETag
    test_if_none_match_304         304, empty body
    test_etag_changes_after_load   a changed fixture file loaded between
                                   two requests: different ETags
    ```

    56 + 1 + 3 = 60 tests.
14. In chat: which of your hard-tier changes would a client notice if
    you deleted it tomorrow, and how?

**Withheld:** what the ETag is computed from. Whether it is per
response or per data version.

---

## Reference

### Numbers on the real data (landed 2026-09-25)

```
seasons     2025/2026  306 finished,   0 upcoming
            2026/2027   63 finished, 243 upcoming

standings 2025/26 table, first 3
  1 Al Nassr    34  28  2  4   91 28  63  86
  2 Al Hilal    34  25  9  0   85 27  58  84
  3 Al Ahli     34  25  6  3   71 25  46  81

metrics 2025/26, points and xg_for, first 3
  Al Nassr 86 64.38    Al Hilal 84 68.05    Al Ahli 81 54.19
```

### Numbers on the recorded data (the test database)

```
seasons     2025/2026   0 finished, 0 upcoming
            2026/2027   2 finished, 1 upcoming

standings 2026/27 table            standings 2026/27 home
  1 NEOM SC     1 1 0 0  2 0  2 3    1 Diriyah     1
  2 Diriyah     1 0 1 0  1 1  0 1    2 Al Faisaly  0
  3 Al Kholood  1 0 1 0  1 1  0 1
  4 Al Faisaly  1 0 0 1  0 2 -2 0

matches
  cb556...  FINISHED  2026-08-21 18:00Z  Al Faisaly 0-2 NEOM SC
            51' A. Lacazette (NEOM SC), 60' A. Lacazette (NEOM SC)
            Al Majma'a Sport City Stadium
  fed56...  FINISHED  2026-08-26 18:00Z  Diriyah 1-1 Al Kholood
            71' Al Elewa (Al Kholood), 83' Al Nemr (Diriyah)
            Al-Awwal Park
  a10a6...  UPCOMING  2026-10-09 13:50Z  Al Kholood v Al Qadsiah
            Al Hazem Club Stadium
```

`fct_goals.goal_type` values: `goal`, `penalty-goal`, `own-goal`. For
an own goal, the team the goal counts for is not the scorer's team
(`scoring_team_id` against `scorer_team_id`, lesson 6).

### FastAPI facts to look up, not to copy

- Path and query parameters with types, `Literal` or `Enum` for a
  fixed set, `Annotated[..., Path(pattern=...)]`, `Query()` for a
  repeated parameter (`list[str]`).
- `response_model` on the route, `HTTPException(status_code, detail)`.
- `app.openapi()` returns the document as a dict; `/docs` renders it.
- `TestClient(app)` calls the app through httpx's ASGI transport: no
  socket, so `pytest-socket` does not block it.
- uvicorn: `uvicorn.run(app, host=..., port=...)` from Python.
