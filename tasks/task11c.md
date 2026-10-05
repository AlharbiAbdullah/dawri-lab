# L11c: a page that answers through Ossie (Streamlit)

Lesson 11 has three paths over the same Ossie document: 11a Rill,
11b Evidence, 11c Streamlit. Ossie stays the one source in every path.
This one needs no generator: the page is Python and calls `semantic.py`.

## The concept

### The problem

Lesson 10 gave Dawri one definition per metric, in the Ossie document,
and a reader for it (`semantic.py`). Nobody can look at it yet. Every
answer is a terminal command that someone has to know how to type.
Four symptoms:

1. **No one can browse the facts.** "How did Al Hilal do at home
   against away?" is a new command each time, typed by the one person
   who knows the metric names.
2. **A UI tool brings its own metric language.** Rill (11a) needs its
   own metrics-view YAML and Evidence (11b) its own SQL, so both paths
   generate a copy from Ossie and check it for drift. A Python page has
   no such layer to feed: it can ask `semantic.py` directly, the same
   function as `dawri metrics`, and there is no copy to keep in step.
3. **A reader locks out the writer.** DuckDB lets one process write a
   file or many processes read it, never both at once. A process that
   keeps a `semantic.connect()` connection open blocks the build:

   ```
   ERROR dawri build failed: dbt exited 1
   IO Error: Could not set lock on file ".../dawri.duckdb" ...
   ```

   (Seen on a scratch copy, 2026-10-05: one Python process holding a
   read-only connection, then `dawri build`.) A page you must close
   before every run is a page nobody leaves open.
4. **A UI reruns your code more often than you think.** Streamlit runs
   the whole script again on every click. Whatever the script does, it
   does on every click: open the database, load the extension, query.

### What we want

`uv run streamlit run src/dawri/app.py` opens Dawri on localhost: the
league for a season. Pick a team and the page becomes that team's page.
Every number on it comes through `semantic.py` from the Ossie document,
the same path as `dawri metrics`, so there is no second definition and
nothing to compare. `dawri build` works while the page is open, and the
next click shows the new numbers without a restart. In the hard tier
the page is tested like the rest of Dawri: offline, in pytest, in CI.

### What you will understand at the end

| Idea | In one line |
|---|---|
| Rerun model | Every click reruns the script top to bottom. A widget returns its current value; what the script draws this run is the page. |
| What shows depends | The page is Python, so an `if` on the reader's choice decides what is drawn. No template language in between. |
| One path to the numbers | The page asks the same function as the CLI and lesson 12's API, so a UI never needs its own metric language. |
| Cache with a cost | `st.cache_data` and `st.cache_resource` trade freshness, and locks, for speed. Measure the cost before you cache. |
| Single writer | An embedded database has one writer at a time. Serving and building need separate files, or turns. |
| Serving copy | The pipeline publishes what readers read, whole and in one step, so they never see half a build. |
| Testing a page (hard) | AppTest runs the script without a browser. The page's decisions get tests; the numbers keep lesson 10's. |

### Before and after

```
BEFORE                                  AFTER
answers = typed commands                a page on localhost:8501
a UI needs its own metric YAML          the page calls semantic.py (Ossie)
one view for everyone                   pick a team: its own page (mid)
page open -> dawri build fails          both run at once, no restart (mid)
the page has no tests                   AppTest suite, offline, in CI (hard)
```

Guardrails for every tier:

- Lesson 10's 2026/2027 freeze holds: no 2026/2027 ingest, so no
  `dawri run 2026/2027`. `dawri load && dawri build` is the writer.
- The numbers do not move. Lesson 10's gates still pass unchanged.
- Ossie only. Every number on the page comes from `semantic.py`. The
  app holds no SQL, no aggregate and no `import duckdb`, and never
  reads dbt's semantic layer or MetricFlow.
- Deterministic only: sums and ratios of what happened. No forecast,
  no anomaly score, no "trend" line that extrapolates.
- Streamlit is a project dependency (`uv add streamlit`).
- Streamlit collects usage statistics by default. Turn it off in a
  committed `.streamlit/config.toml`.
- No absolute path to your home folder in any committed file.
- `uv run pytest` still passes, `ruff` and `ty` clean.
- Gates: the target output of each tier.

---

## Easy: the league, through Ossie

**Target output**

```
$ uv run streamlit run src/dawri/app.py

  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
```

The page, as opened (2026/2027 is the default season):

```
Dawri

Season  [2026/2027 v]

team_name     points  goal_difference  xg_for  xg_against
Al Hilal          18               18   25.08        8.27
Al Ittihad        17                6   14.12        9.96
Al Nassr          16                9   11.96        5.70
Al Qadsiah        16                8   16.42        6.73
NEOM SC           15                7    9.46        7.81
... 18 rows
```

Season switched to 2025/2026:

```
team_name     points  goal_difference  xg_for  xg_against
Al Nassr          86               63   64.38       21.95
Al Hilal          84               58   68.05       19.76
Al Ahli           81               46   54.19       23.04
Al Qadsiah        77               49   61.64       33.66
Al Ittihad        55                7   45.44       41.58
... 18 rows
```

**Spec**

1. `uv add streamlit`. `.streamlit/config.toml` at the repo root turns
   off usage statistics. Both committed.
2. `src/dawri/app.py`:
   - the title `Dawri`;
   - a season select with the seasons in `config.SEASONS`, defaulting
     to `config.LIVE_SEASON`;
   - one table. Its header, rows and order are exactly those of
     `uv run dawri metrics <season>`. Floats show two decimals
     (`5.70`, not `5.7` and not `5.7000`).
3. The numbers come from `semantic.connect()` and
   `semantic.team_metrics()`. `app.py` writes no SQL.
4. In chat: Streamlit reruns the whole script on every click. The
   reader opens the page, then switches the season twice. How many
   times did your app open the database, and where is the 829 ms in
   Reference paid? Say what you would change if that number were 30
   seconds.

**Withheld:** when the connection is opened and closed, and whether to
cache it. How the floats get two decimals on the page.

---

## Mid: a page that depends, and a build while it is open

**Target output**

The page, season 2025/2026, team `Al Hilal` picked (the league table is
gone):

```
Al Hilal, 2025/2026

metric             value
matches_played        34
points                84
points_per_match    2.47
goals_for             85
goals_against         27
goal_difference       58
xg_for             68.05
xg_against         19.76
xg_difference      48.28
shots                544
shots_on_target      235

venue  matches_played  points  goal_difference  xg_for  xg_against
home               17      43               30   34.14        7.95
away               17      41               28   33.91       11.81
```

Team set back to `All teams`: the easy tier's league table, unchanged.

The build, with the page open and being clicked:

```
$ uv run dawri build
Processed: 17 models | 43 tests | 1 unit test
Summary: 61 total | 61 success          <- no lock error

$ (throwaway edit 1: fct_team_matches doubles xg_for)
$ uv run dawri build                    -> 61 success
  click: Al Hilal, 2026/2027, xg_for    50.15   <- was 25.08; no restart
$ (edit reverted) uv run dawri build
  click:                                25.08

$ (throwaway edit 2: fct_team_matches keeps only kickoffs before 2026-09-01)
$ uv run dawri build; echo $?
Summary: 61 total | 55 success | 1 error | 5 skipped
1
  click: Al Hilal, 2026/2027, matches_played 7, points 18
                                        <- still the last good data; the
                                           failed build holds 3 and 9
$ (edit reverted, uv run dawri build)
```

**Spec**

5. A team select under the season select. Its first option is
   `All teams`, then the teams of the selected season by name (18).
   - `All teams` draws the easy tier's league table, unchanged.
   - A team draws that team's page instead, for the selected season:
     a heading `<team>, <season>`; its eleven metrics, one row each,
     in the order of the target output; then a home and away split of
     `matches_played`, `points`, `goal_difference`, `xg_for` and
     `xg_against`, home first.
   - Floats at two decimals, as in easy.
6. The numbers still come only through `semantic.py`. Today
   `team_metrics` groups by team and filters by season. Extend
   `semantic.py`, not the app, so a caller can ask for one team and
   group by venue. Lesson 12's API and lesson 13's brief will call the
   same code, not a copy of it.
7. `dawri load` and `dawri build` succeed while the page is open and
   being clicked. Nothing in Streamlit or Dawri is stopped, restarted
   or retried by hand.
8. After a green build, the next click answers from the new data, with
   Streamlit still running. Throwaway edit 1 is the proof: Al Hilal's
   2026/27 `xg_for` is 50.15 after the edit and 25.08 after the revert.
   No dbt test reads xG, so the build stays green.
9. A reader never sees half a build. The page reads 11a mid's serving
   copy (11a, step 9), never `data/dawri.duckdb`. A failed build leaves
   the page answering from the last good data. Throwaway edit 2 is the
   proof: `dawri build` exits 1, and the page still shows Al Hilal's
   2026/27 7 played and 18 points.
   - If you skipped 11a mid, its steps 7 to 9 are the spec: the copy
     holds every table in schema `marts`, published whole, in one
     step, after a green build.
   - The Ossie document's sources are `dawri.marts.<table>`, so the
     copy must open under the catalog name `dawri`.
   - Lesson 12's API reads the same copy.

**Withheld:** where the connection lives across reruns, now that a
build runs beside the page. How `semantic.py` is pointed at the serving
copy without the app naming a file.

---

## Hard (optional): the page is tested like the rest of Dawri

**Target output**

```
$ uv run pytest tests/test_app.py -v
tests/test_app.py::test_league_table_default_season PASSED
tests/test_app.py::test_season_switch PASSED
tests/test_app.py::test_team_page_replaces_league_table PASSED
tests/test_app.py::test_team_page_order_and_decimals PASSED

$ uv run pytest
... passed in under 10s

$ git push; gh run list --limit 1
completed  success  ...

$ (branch: app.py computes points itself with a SUM, pushed)
$ gh run list --limit 1
completed  failure  ...    <- app-check: src/dawri/app.py defines a metric
(branch deleted after)
```

**Spec**

10. `tests/test_app.py`, four tests with Streamlit's `AppTest`:
    - the default season and the league table's header;
    - switching the season changes the rows;
    - picking a team removes the league table and draws the team page;
    - the team page's metric order, and floats at two decimals.

    No database and no network. Fake the Ossie reader at the boundary,
    `semantic.py`, with Latin-script team names of your own (`Team A`).
11. `pytest-socket` stays on for the whole suite. AppTest's event loop
    opens a Unix socket pair, so out of the box every AppTest fails with
    `SocketBlockedError: A test tried to use socket.socket` (checked on
    1.65.0). Allow Unix sockets only. The internet stays blocked
    (lesson 9's rule).
12. `mise run app-check` fails, and CI runs it on every push, when
    `src/dawri/app.py` defines a metric itself: an aggregate function
    (`SUM(`, `AVG(`, `COUNT(`, `MIN(`, `MAX(`), or an `import duckdb`.
    Prove it red with the branch in the target output, then delete the
    branch.
13. In chat: your tests fake `semantic.py`. Name one bug in the page
    they catch, and one they cannot. Which check from lesson 10 covers
    the second?

**Withheld:** how to fake the reader so the app's own imports see the
fake. How to allow Unix sockets and nothing else.

---

## Reference

### Versions, checked 2026-10-05

```
streamlit    1.65.0 (PyPI); 1.61 to 1.64 shipped Aug to Oct 2026
duckdb       1.5.5, as in the project
python       3.14
```

Streamlit is Apache 2.0, owned by Snowflake. `uv add streamlit` pulls
84 packages into the environment (pandas, pyarrow, tornado, watchdog,
among others).

### Running

```
uv run streamlit run <file>                  serves on localhost:8501,
                                             opens a browser tab
... --server.headless true                   no browser tab
... --server.port 8599                       another port
curl localhost:8501/_stcore/health           prints: ok
```

On start it prints `Collecting usage statistics. To deactivate, set
browser.gatherUsageStats to false.` In `.streamlit/config.toml` that is
a `[browser]` table with `gatherUsageStats = false`.

Docs: docs.streamlit.io, under develop/concepts/architecture (the
rerun model), develop/concepts/architecture/caching (`st.cache_data`,
`st.cache_resource`) and develop/api-reference/app-testing (AppTest).

### What the rerun costs here (measured on the real data)

```
first semantic.connect() in a process    829 ms  (loads the extension)
open + team_metrics + close, after that   23-25 ms
team_metrics on an open connection          3 ms
```

### DuckDB and readers (checked 2026-10-05)

```
a process holds a read-only connection    dawri build fails:
                                          "IO Error: Could not set lock
                                          on file ...dawri.duckdb"
the holder exits                          dawri build: 61 success
a read-only connection                    every database it ATTACHes is
                                          read-only too; attaching a new
                                          file fails: "Cannot open
                                          database ... in read-only mode:
                                          database does not exist"
a file renamed over another while a       that reader keeps answering
reader holds the old one open             from the old file; a new
                                          connection opens the new one
data/dawri.duckdb                         30 MB
```

A database file is attached under its file name: a copy named
`dawri.duckdb` opens as catalog `dawri`, whatever folder it sits in.

### AppTest, the parts this lesson uses

```python
from streamlit.testing.v1 import AppTest

at = AppTest.from_file("src/dawri/app.py").run()
at.exception                      # empty when the run raised nothing
at.title[0].value
at.selectbox[0].options           # what the reader can pick
at.selectbox[0].select("2025/2026").run()
at.dataframe[0].value             # a pandas DataFrame
```

AppTest runs the script in the test's own process, without a browser
and without a server.

### Numbers on the real data (landed 2026-09-25)

```
Al Hilal 2025/26        34 played, 84 pts, 2.47 per match, 85-27 (+58),
                        xG 68.05 for, 19.76 against, +48.28,
                        544 shots, 235 on target
  home                  17 played, 43 pts, +30, xG 34.14 - 7.95
  away                  17 played, 41 pts, +28, xG 33.91 - 11.81
Al Hilal 2026/27        7 played, 18 pts, +18, xG 25.08 - 8.27
  xg_for doubled        50.15 (throwaway edit 1)
  before 2026-09-01     3 played, 9 pts (what edit 2 leaves in
                        data/dawri.duckdb; the page must not show it)
edit 2 build            Summary: 61 total | 55 success | 1 error |
                        5 skipped, exit 1
teams                   18 per season, 21 across both
```

Floats come back unrounded from the `ossie` extension
(`25.0758`, `64.3775`). Two decimals is a display choice, made once.
