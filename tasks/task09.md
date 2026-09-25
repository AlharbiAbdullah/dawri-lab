# L9: tests that never touch the network

## The concept

### The problem

Every check Dawri has ever passed was a live run and a person reading
numbers. Three symptoms:

1. **The only test is a live run.** Every gate since lesson 1 either
   asks the SPL API or reads the 404 MB in `data/`. A check that needs
   the network fails whenever the network does. A check that reads
   `data/` proves nothing on a machine that doesn't have it: a fresh
   clone, a CI runner, a colleague's laptop.
2. **The decisions are not written down as checks.** Lesson 2's
   planted records, lesson 7's "never write an empty body", lesson 7's
   ledger: each was proved once in a terminal and then lived only in
   the code. Change `has_lineups_data` back to `home is not None` and
   nothing fails. The first finished match whose lineups come back
   empty would be written to disk, counted as landed, and never asked
   for again.
3. **dbt only knows one dataset.** Four of the 36 tests pin facts of
   the real season: 108 standings rows, 17 goal-source rows, the API's
   own table, the 2025/26 ranks. On a smaller dataset they fail by
   design, so dbt cannot run on anything smaller. The head-to-head
   rule in `mart_standings` is checked only by comparing against the
   API's full 2025/26 ranks.

One more fact from lesson 8's review: a run with `DAWRI_DATA_DIR`
pointed elsewhere still appends to the real `logs/dawri.log`.

### What we want

`uv run pytest` on a fresh clone with the network blocked checks the
decisions of lessons 1 to 8 in a few seconds. It runs against real API
responses, recorded once and committed. It leaves `data/` and `logs/`
exactly as they were.

### What you will understand at the end

| Idea | In one line |
|---|---|
| Recorded fixture | A real response, saved once and replayed forever. The test is exactly as true as the recording. |
| Test isolation | A test owns its world: its own folder, its own fake API, its own log. Nothing leaks into `data/`, `logs/` or the next test. |
| Unit test vs data test | A unit test checks logic on rows you wrote by hand. A data test checks facts about the rows you have. They answer different questions. |
| CI (hard) | The same checks, run by a machine on every push, with nobody watching. |

### Before and after

```
BEFORE                                AFTER
checks = live runs + reading numbers  uv run pytest, sockets blocked
needs the API and data/ (404 MB)      tests/fixtures/ (2.2 MB, committed)
decisions proved once in a terminal   one named test per decision
dbt runs on the full season only      dbt unit test, full-data tests tagged (hard)
nobody runs the checks on push        GitHub Actions on every push (hard)
```

Guardrails for every tier:

- The numbers do not move. `uv run dawri run 2026/2027` on the real
  data still prints lesson 8's lines and ends
  `50 total | 50 success` (`51` after the hard tier adds its unit
  test). Production code may change to make it testable. Name every
  such change in chat.
- No test touches the network. The whole suite runs with sockets
  blocked.
- `data/` and `logs/dawri.log` are byte-identical before and after
  `uv run pytest`.
- The whole suite runs in under 10 seconds.
- Every test passes alone, and the suite passes in any order:
  `uv run pytest tests/test_pipeline.py::test_second_load_loads_nothing`
  works on its own.
- `ruff` and `ty` clean across `src/` and `tests/`.
- Use the tools people use: `pytest`, `pytest-socket`, `respx` or
  `pytest-httpx`, `typer.testing.CliRunner`, pytest's `tmp_path` and
  `monkeypatch`, dbt unit tests, GitHub Actions with
  `astral-sh/setup-uv`. If you reach for one, know what it does
  underneath.
- Gates: the target output of each tier, run from the repo root.

---

## Easy: recorded fixtures and the pure checks

**Target output**

```
$ du -sh tests/fixtures
2.2M

$ uv run pytest
34 passed

$ uv run pytest tests/test_network.py
1 passed          <- passes because the request is refused

$ git status --short data logs
(nothing)
```

**Spec**

1. `uv add --dev pytest pytest-socket`. `pyproject.toml` configures
   pytest so that every run blocks sockets without anyone typing a
   flag.
2. Recorded fixtures, committed, in the same layout as `data/`, all
   for the live season `3677a75aaa514e43b2840e7fa367c91d` (`<sid>`
   below):

   ```
   tests/fixtures/recorded/
     matches/<sid>.json        the real file, "matches" list cut to the
                               three matches in Reference, envelope kept
     matchdays/<sid>.json      copied from data/ unchanged
     teams/<sid>.json          copied unchanged
     standings/<sid>.json      copied unchanged
     teamstats/<sid>/cb556acbac334114887ef91fcb725e0c.json
     teamstats/<sid>/fed56d6495e048d6aa008ecec45017b2.json
     (same two files for playerstats, lineups, matchfacts, feed)
   tests/fixtures/unplayed/
     teamstats.json  playerstats.json  lineups.json
     matchfacts.json  feed.json
   ```

   14 files under `recorded/`, 5 under `unplayed/`. The `unplayed/`
   files are recorded live, once, with the fetch functions `ingest.py`
   already has, for the upcoming match
   `a10a6c353d734675b6e000b253df6335`. Save the bodies exactly as
   returned. That is 5 requests, made by hand, outside the test suite.
   **Record them before its kickoff on 2026-10-09**, because a played
   match returns data.
3. `tests/test_network.py`, one test:

   ```
   test_network_is_blocked   httpx.get on the API base raises
                             pytest_socket.SocketBlockedError
   ```

4. `tests/test_ingest_checks.py`:

   ```
   test_cleaned_match_id   "spl::Football_Match::cb556..." -> "cb556..."
   test_has_data           10 cases, one per family and fixture:
                           recorded cb556 file      -> True  (5 families)
                           unplayed/ file           -> False (5 families)
   ```

5. `tests/test_contract.py`, lesson 2's planted records rebuilt on the
   recorded matches (the eight cases in Reference):

   ```
   test_contract                    10 cases: the two FINISHED matches
                                    as recorded (accepted), plus the 8
                                    cases in Reference
   test_classify_recorded_matches   classify_matches on the recorded
                                    file -> 2 valid, 0 rejected, 1 skipped
   ```

6. `tests/test_unpack.py`:

   ```
   test_unpack_rows   11 cases, one per raw table: rows that
                      unpack_json_pattern returns, summed over every
                      recorded file of that table's family, equal the
                      count in Reference
   ```

   1 + 11 + 11 + 11 = 34 tests.

**Withheld:** how one test function becomes ten cases. How a test
finds its fixture file without depending on the folder pytest runs
from.

---

## Mid: the pipeline on recorded data

**Target output**

```
$ uv run pytest
44 passed in <10s

$ git status --short data logs
(nothing)
```

**Spec**

7. Two pytest fixtures in `tests/conftest.py`:

   ```
   data_dir   an empty folder under tmp_path. Every dawri command a
              test runs reads and writes there instead of data/, and
              its log goes to <data_dir>/../dawri.log, never logs/.
   fake_api   answers every URL ingest asks for with the matching
              file under tests/fixtures/recorded/. A request for a
              URL with no recording fails the test. It records the
              URLs it was asked for, in order.
   ```

8. `tests/test_pipeline.py`, every command run through
   `typer.testing.CliRunner` on the real `dawri` app:

   ```
   test_first_ingest              ingest 2026/2027: exit 0, stdout is the
                                  three lines in Reference, the 14 landed
                                  files equal the recorded ones byte for byte
   test_second_ingest             ingest again: requests: 4, and those 4
                                  URLs are the four season-level ones
   test_unplayed_never_requested  no URL asked for contains a10a6c35...
   test_empty_body_not_written    fake_api serves unplayed/feed.json for
                                  fed56's feed: first run requests: 14 and
                                  "... 2 matchfacts, 1 feed", no feed file
                                  for fed56 on disk; second run requests: 5
   test_bad_season_exits_2        ingest 2024/2025: exit 2, 0 requests
   test_first_load                ingest, then load: stdout is the load
                                  block in Reference, loaded: 18 files
   test_second_load_loads_nothing load again: loaded: 0 files
   test_changed_file_reloads_one  rewrite cb556's playerstats file with the
                                  same JSON, different bytes (indented):
                                  loaded: 1 files, playerstats: 8946
   test_deleted_file_is_pruned    delete fed56's playerstats file:
                                  loaded: 0 files, playerstats: 4505
   test_log_lines                 after one ingest, the test's log has
                                  14 INFO "request" lines, one ingest start
                                  and one ingest end line with seconds
   ```

   34 + 10 = 44 tests.

9. In chat: every test in this lesson replays a recording. Name one way
   the live API could change that these 44 tests would never notice,
   and say what in Dawri would be the first to show it.

**Withheld:** how a test points dawri at its own folder and its own log
file. How a request is answered without a socket. How 14 requests take
no time when the code waits 0.25 s between them.

---

## Hard (optional): dbt and CI

**Target output**

```
$ uv run dawri build                          real data
Processed: 14 models | 36 tests | 1 unit test
Summary: 51 total | 51 success

$ (recorded data loaded into a temp folder, dbt without full-data tests)
Processed: 14 models | 32 tests | 1 unit test
Summary: 47 total | 47 success

$ git push; gh run list --limit 1
completed  success  ...

$ (branch with mart_standings' two h2h order lines removed, pushed)
$ gh run list --limit 1
completed  failure  ...    <- fails on head_to_head_beats_goal_difference
(branch deleted after)
```

**Spec**

10. One dbt unit test on `mart_standings`,
    `head_to_head_beats_goal_difference`, with the inputs and expected
    rows in Reference. It must fail when the two `h2h_*` lines are
    removed from the `order by` in `mart_standings.sql`. Check that it
    does before you trust it.
11. The four full-data tests get the tag `full_data`:
    `expect_table_row_count_to_equal` 108 on `mart_standings`,
    `expect_table_row_count_to_equal` 17 on `mart_goal_source_diff`,
    `dbt_utils.equality` on `mart_standings`, and
    `assert_finished_season_ranks_match_api`. On the real data nothing
    changes: all 51 run.
12. `.github/workflows/ci.yml`, on every push and pull request, runs
    in this order: install with uv, `ruff check`, `ty check`,
    `pytest`, then dbt on the recorded data without the `full_data`
    tests (second block of the target output). The dbt packages are
    not in git, so CI must fetch them.
13. Prove it both ways with the session in the target output: one green
    run on the pushed commit, one red run on a throwaway branch that
    breaks the h2h order.

**Withheld:** how a test is tagged and how a run leaves tagged tests
out. How CI gets a database when it has no `data/`.

---

## Reference

### The three recorded matches (2026/27, live season)

```
match id                          status    kickoff (UTC)      score
cb556acbac334114887ef91fcb725e0c  FINISHED  2026-08-21 18:00   Al Faisaly 0-2 NEOM SC
fed56d6495e048d6aa008ecec45017b2  FINISHED  2026-08-26 18:00   Diriyah 1-1 Al Kholood
a10a6c353d734675b6e000b253df6335  UPCOMING  2026-10-09 13:50   Al Kholood v Al Qadsiah
```

Kept in API order. The two finished matches have all five
match-level files in `data/`. Together they are about 2 MB. Most of
that is playerstats.

### Unplayed responses (recorded 2026-09-25 for a10a6...)

All five come back HTTP 200. Every `has_*_data` returns False on them.

```
teamstats    176 bytes   every key null, "stats": null
playerstats  179 bytes   every key null, "players": null
lineups      1.6 KB      matchId set, "home"/"away" are objects with empty lineups
matchfacts   835 bytes   stadium and location set, "referees": []
feed         418 bytes   match header set, "events": []
```

### Contract cases (step 5)

Built from the recorded matches. "win" is cb556 (away win, 0-2) and
"draw" is fed56 (1-1).

```
case                 base  change                                  result
winner is the loser  win   winTeamId = home team id                rejected
same team twice      win   away = copy of home                     rejected
time as text         win   additionalTime = "13+2"                 rejected
negative score       win   homeScorePush = -1                      rejected
no Z                 win   matchDateUtc without the trailing Z     rejected
no id                win   matchId removed                         rejected
draw with winner     draw  winTeamId = home team id                rejected
extra field          win   attendance = 21450 added                accepted
```

### Rows per raw table on the recorded data (step 6, and the load)

```
table            rows   from
matches             3   matches/<sid>.json
matchdays          34   matchdays/<sid>.json
teams              18   teams/<sid>.json
standings          54   standings/<sid>.json   (3 blocks x 18)
teamstats         484   239 cb556 + 245 fed56
playerstats      8946   4505 cb556 + 4441 fed56
lineups            80   40 + 40
lineup_events      37   20 + 17
match_facts         2   1 + 1
match_officials    12   6 + 6
feed_events       134   62 + 72
```

### Command output on the recorded data (step 8)

```
ingest 2026/2027, empty folder     requests: 14
                                   2026/2027 finished: 2 of 3
                                   2026/2027 landed: 2 teamstats, 2 playerstats, 2 lineups, 2 matchfacts, 2 feed
ingest again                       requests: 4   (same two lines after)

load, after the first ingest       loaded: 18 files
                                   contract: 2 valid, 0 rejected
                                   skipped: 1 unplayed
                                   matches: 3
                                   (then the other ten tables, counts above)
```

14 requests = 4 season-level + 2 finished matches x 5 families. 18
files loaded = 4 season-level + 2 matches x 7 match-level tables
(lineups and matchfacts feed two tables each).

### The head-to-head unit test (step 10)

Given `stg_matches` (only the columns the mart reads):

```
season_id  match_id  status    home  away  home_score  away_score
s1         m1        FINISHED  A     B     1           0
s1         m2        FINISHED  C     B     0           5
s1         m3        FINISHED  C     D     0           0
s1         m4        UPCOMING  D     A     null        null
```

Given `stg_teams`: `s1` with A Alpha, B Beta, C Gamma, D Delta.

Expected rows (the columns to compare: type, rank, team_id, points,
goal_difference):

```
type   rank  team  points  gd
table  1     A     3        1    <- A beat B, so A is above B despite gd
table  2     B     3        4
table  3     D     1        0    <- C and D drew, gd decides
table  4     C     1       -5
home   1     A     3        1
home   2     C     1       -5
away   1     B     3        4
away   2     D     1        0
```

m4 is upcoming and must not count. Without the h2h lines, B ranks
first in the table block and the test fails. Checked on 2026-09-25.

### dbt on the recorded data (step 11)

On the three recorded matches, a plain `dbt build` passes 48 of 51.
The failing three are the two row counts and `dbt_utils.equality`,
since the API's full live table cannot equal a table built from two
matches. `assert_finished_season_ranks_match_api` passes only because
it pins 2025/26 and the fixture has none. That is why it is tagged
too. With `full_data` left out, the result is `47 total | 47 success`.

Not yet checked: dbt Fusion on a GitHub `ubuntu-latest` runner. Its
first run downloads the DuckDB driver, which is cached in `~/.dbt`
locally.
