# L8: one entrypoint

## The concept

### The problem

Dawri works, but it is a pile of scripts, not a program. The thing
holding it together is you. Three symptoms:

1. **You are the glue.** Four commands, right order, right folder,
   never twice at once. None of that is written anywhere except your
   head. On 2026-09-20 it slipped: two `ingest.py 2026/2027` runs
   overlapped, both wrote the same feed file, and it came out as one
   response with the tail of another glued on
   (`JSONDecodeError: Extra data`).
2. **The same fact is spelled in four places.** The data folder is
   typed by hand in `ingest.py` (nine times), `load.py`,
   `contracts.py` and `dbt/profiles.yml`. Change one and the others
   quietly disagree. The profile's `../data/dawri.duckdb` only works
   if your shell stands in `dbt/`.
3. **A run leaves no record.** 16 `print(` calls, all to the terminal.
   The first live pull made 319 requests and said nothing for
   minutes. When it crashed, the only evidence was a traceback in a
   terminal that is now closed.

### What we want

One command that a person, a scheduler, or a test can run from
anywhere and trust: `dawri run 2026/2027`. Same numbers as today,
nothing about the data changes. Only how the pipeline is run.

### What you will understand at the end

| Idea | In one line |
|---|---|
| Entrypoint | A project becomes a program when it installs a command. The order of steps lives in code, not in your memory. |
| One source of truth | Every setting is defined once. Python and dbt both read that one definition. |
| The program's contract | Arguments in. Results on stdout, chatter on stderr, history in a log file, success or failure in the exit code. Other programs rely on each of the four. |
| Safe under concurrency (hard) | Two runs cannot overlap, and a file is never seen half-written. |

Each tier fixes one symptom: easy fixes 1, mid fixes 2 and 3, hard
closes the incident for good.

### Before and after

```
BEFORE                              AFTER
uv run ingest.py 2026/2027          uv run dawri run 2026/2027
uv run load.py
cd dbt
uv run dbt build

settings in 4 files                 src/dawri/config.py
16 print() calls, no record         stdout = results, logs/dawri.log = the rest
two ingests can overlap             second ingest refused (hard tier)
```

Guardrails for every tier:

- The numbers do not move. Every count in lesson 7's gates is the same after this lesson: 369 valid, 612 matches, 921 goals for 2025/26, 50 of 50 in dbt. A change to any of them is a defect.
- The pull is still `ingest` only, 4 requests per second.
- No command needs `cd`. Every gate runs from the repo root.
- `ruff` and `ty` clean across `src/`.
- Use the tools people use: Typer for the commands, the standard `logging` module, `pydantic-settings` if you want typed settings from the environment, dbt's `env_var()` in the profile. If you reach for one, know what it does underneath.
- Gates: the target output of each tier, run from the repo root.

---

## Easy: `dawri ingest` and `dawri load`

**Target output**

```
$ uv run dawri ingest 2026/2027
requests: 4
2026/2027 finished: 63 of 306
2026/2027 landed: 63 teamstats, 63 playerstats, 63 lineups, 63 matchfacts, 63 feed

$ uv run dawri ingest 2025/2026
requests: 0
2025/2026 finished: 306 of 306
2025/2026 landed: 306 teamstats, 306 playerstats, ...

$ uv run dawri --help
(lists ingest and load)

$ uv run dawri ingest 2024/2025
(names the valid seasons, exit 2)

$ uv run dawri load
loaded: 4 files            <- not 1,853
contract: 369 valid, 0 rejected
(rest identical to load.py today)

$ uv run dawri load
loaded: 0 files
```

**Spec**

1. The code moves into a package, `src/dawri/`: `__init__.py`,
   `cli.py` (the commands, and nothing else), `ingest.py`, `load.py`,
   `contracts.py` (the last three moved from the repo root). The
   three root scripts are gone after the move.
2. `pyproject.toml` declares one console script, `dawri`, and the
   project becomes installable so `uv run dawri` works from the repo
   root.
3. `cli.py` is a Typer app (`uv add typer`) with two commands.
   `argparse` leaves `ingest.py`.

   ```
   dawri ingest SEASON     SEASON is 2025/2026 or 2026/2027, required
   dawri load              no arguments
   ```

   A season that is not one of the two exits with code 2 and names
   the valid choices.
4. Ingest counts are for the asked season, not everything on disk.
   This is lesson 7 step 3, never built: `ingest.py` still prints
   `teamstats: 369`, both seasons added together. It belongs to this
   lesson now.
5. `dawri load` prints exactly what `uv run load.py` prints today.
   The first load after the move says `loaded: 4 files`: the four
   season-level files the live ingest just re-pulled. Moving the code
   must not make the load think 1,853 files are new.

**Withheld:** the path from `pyproject.toml` to your function. What in
the ledger could turn a pure move into 1,853 new files.

---

## Mid: config, `build`, `run`, logging

**Target output**

```
$ uv run dawri run 2026/2027
(three ingest lines)
(load lines)
Processed: 14 models | 36 tests
Summary: 50 total | 50 success
  stderr: empty
  logs/dawri.log grew: 4 request lines, 4 loaded-file lines,
                       start + end for run, ingest, load, build

$ uv run dawri run 2026/2027 > out.txt      out.txt = result lines only
$ DAWRI_DATA_DIR=/tmp/empty uv run dawri load
loaded: 0 files, all counts 0, data/dawri.duckdb untouched
$ (mart_standings count set to 107) uv run dawri run 2026/2027
exit code not 0, log names the failed step. Restore after.
```

**Spec**

6. One settings module, `src/dawri/config.py`. After this step a
   search of `src/` for the string `"data` finds it in `config.py`
   only:

   ```
   data_dir       data                     env DAWRI_DATA_DIR
   db_path        {data_dir}/dawri.duckdb  derived
   base_url       the API base
   request_gap    0.25
   seasons        the two season ids
   live_season    2026/2027
   ```

   Every value in the "scattered today" table (see Reference) is
   defined there once and imported everywhere else. `DAWRI_DATA_DIR`
   exists because lesson 9 tests must run the whole load against a
   folder of recorded JSON without touching `data/`.

7. `dbt/profiles.yml` stops using `../data/dawri.duckdb`. It reads the
   same database path `config.py` resolves, and it works whichever
   folder the shell is in.
8. Two more commands, both run from the repo root, no `cd`:

   ```
   dawri build             runs dbt build on the project in dbt/
   dawri run SEASON        ingest SEASON, then load, then build
   ```

   `dawri build` ends with dbt's own last two lines. `dawri run`
   stops at the first step that fails and exits with that step's exit
   code. A later step never runs after an earlier one failed.
9. Logging. The result lines of ingest, load and build stay on
   stdout, character for character: they are the output of the
   command. Everything else a run has to say goes through `logging`:

   ```
   stderr              INFO with --verbose, WARNING without it
   logs/dawri.log      always INFO, appended, never truncated
   per ingest request  one INFO line: family + match id or season id
   per loaded file     one INFO line: table name + file path
   per command         one INFO line at start, one at end,
                       with the command name, and seconds on the end line
   every line          starts with a UTC timestamp and the level
   ```

   `--verbose` is an option on the `dawri` app itself, before the
   command: `dawri --verbose ingest 2026/2027`.
10. In chat: a result line goes to stdout and a log line goes to
    stderr. Say what breaks for the person running
    `dawri load > counts.txt`, or piping `dawri ingest` into `grep`,
    if you send both to stdout. Then: `dawri run` returns an exit
    code. Name one thing outside Python that reads it, and say what
    that thing would do with a `dawri run` that printed an error but
    exited 0.

**Withheld:** one env value reaching Python and dbt. How `build`
learns dbt failed. One app option reaching every command. Configuring
logging once.

---

## Hard (optional): the 2026-09-20 incident

**Target output**

```
$ rm -r data/feed/<live season>; uv run dawri ingest 2026/2027 &
$ uv run dawri ingest 2026/2027
ingest already running (pid 12345)       <- stderr, exit 1, 0 requests, 0 files
$ kill -9 12345
$ uv run dawri ingest 2026/2027
(completes, all 63 feed files parse as JSON)
```

**Spec**

11. One ingest at a time. A second `dawri ingest` started while one
    is running exits with code 1 and prints one line to stderr saying
    an ingest is already running, with the process id of the one that
    holds it. It makes 0 requests and writes 0 files before exiting.
    A run that is killed (`kill -9`) does not block the next run
    forever.
12. Whole files only. A file under `data/` is either absent or
    complete. A reader that opens it at any moment during a run never
    sees a partial body.
13. Prove it with the session in the target output: delete the live
    season's feed folder, start an ingest, start a second while the
    first is running, show the refusal and its exit code, `kill -9`
    the first, then run a third and show it completes with all 63
    feed files parsing as JSON.

**Withheld:** what holds the claim and survives a crash. How a write
becomes all or nothing.

---

## Reference

### What is scattered today

The same facts live in more than one file, each spelled by hand:

```
data root      ingest.py   nine "data/{family}" strings
               load.py     DATA_GLOB = Path("data")
               contracts.py  DIR = "data/matches"
               dbt/profiles.yml  path: ../data/dawri.duckdb
database path  load.py     DB_PATH = Path("data/dawri.duckdb")
               dbt/profiles.yml  (again, relative to dbt/)
seasons        ingest.py   SEASONS dict, LIVE_SEASON
API            ingest.py   BASE, REQUEST_GAP = 0.25
```

`dbt/profiles.yml` is the sharp one: `../data/dawri.duckdb` only
resolves when the shell is standing in `dbt/`.

### What a run says today

16 `print(` calls across the three files, all to stdout. The first
live pull of lesson 7 made 319 requests over several minutes and
printed nothing until the end. When it crashed, the only record was
the traceback in a terminal that has since been closed.

### What `dawri load` prints

```
loaded: 0 files
contract: 369 valid, 0 rejected
skipped: 243 unplayed
matches: 612
matchdays: 68
(and the other nine count lines, unchanged)
```
