# L3: raw JSON into DuckDB

## The concept

### The problem

Lesson 1 landed the season as 616 raw files. Lesson 2 put a contract
on the matches file. Lesson 4's dbt models need tables to query, and
files are not tables:

1. **You cannot ask a folder a question.** "How many goals did Al
   Hilal score at home" means opening 306 files in Python. SQL needs
   rows.
2. **The JSON is not row shaped.** Every file is an envelope around a
   list. Stats rows carry no match id, the envelope does. One
   standings `statsValue` is an int in one row, a string in another,
   a list in a third and null in a fourth.
3. **A load that rebuilds everything is wasteful.** 250 MB read and
   1.4 million rows written to change nothing (hard tier).

### What we want

Six raw tables in one DuckDB file, `data/dawri.duckdb`, built from
the landed files. The raw files stay exactly as landed. The database
can be thrown away and rebuilt at any time.

### What you will understand at the end

| Idea | In one line |
|---|---|
| Files are truth, the database is derived | Delete the `.duckdb` file and nothing is lost. |
| Envelope to rows | One file becomes many rows, and each row must carry the ids its envelope held. |
| Column types are decisions | What stays nested, what becomes a column, and what type holds a value that is not one type. |
| Rerunnable load | A second run gives the same tables, not doubled ones. |
| Per-file load (hard) | A load can remember what it has seen and skip it. |

Easy loads one table. Mid loads all six behind the contract. Hard
makes the load per file.

### Before and after

```
BEFORE                              AFTER
616 JSON files under data/          6 tables in data/dawri.duckdb
questions answered by Python loops  questions answered by SQL
contract runs on its own            contract gates the load
```

Guardrails for every tier:

- Read only from `data/`. Zero network requests from `load.py`. The hard tier's single request is made by `ingest.py`, unchanged.
- The raw files are never modified. `ingest.py` and `contracts.py` are never modified.
- The database is one file, `data/dawri.duckdb`, gitignored with the rest of `data/`.
- Column names are snake_case. JSON keys stay as the source sent them, the rename happens at load.
- Stat values land as numbers, not text. The long shape is kept as landed: no pivot at load (decided in `docs/api-model.md`, the pivot is lesson 4's job).
- Every count printed comes from a query against the database, not from the objects you loaded.
- Code goes in `load.py` at the repo root. You add `duckdb` (Python package only, no CLI). pyarrow, pandas, polars are allowed: add what you use, know why. `pydantic` comes in through `contracts.py`.
- Gates: `uv run ruff check`, `uv run ty check`, then `uv run load.py`.

---

## Easy: one table

**Target output**

```
matches: 306
```

**Spec**

1. Add `duckdb` to the project. Load the landed matches file into a
   table called `matches` in `data/dawri.duckdb`, one row per match.
2. Print the line above, from a query against the table, not from a
   Python `len`.
3. In chat: run `DESCRIBE matches`. `matchDateUtc` comes out of the
   source as `"2025-08-28T16:05:00Z"`. Lesson 2 rejected that same
   string without its `Z`. Look at the type your `matches` table
   gives that column and the value it holds. Did the `Z` survive the
   load? If not, where does "this is UTC" live now, and what does
   that mean for the tables lesson 4 builds on top?

**Withheld:** how one file wrapped in an envelope becomes one row per
match, and whether `home`, `away` and `matchSet` stay nested objects
or become columns. Also which of the 36 keys become columns at all.
The raw file is still on disk, so a column you left out is one reload
away. That decision is the lesson.

---

## Mid: six tables, behind the contract

**Target output**

```
contract: 306 valid, 0 rejected
matches: 306
matchdays: 34
teams: 18
standings: 54
teamstats: 76648
playerstats: 1387916
```

Run twice: the second run prints exactly the same seven lines.

**Spec**

4. Before anything is written, run the lesson 2 contract over the 306
   matches. Import it from `contracts.py`, do not copy it. If any
   match is rejected the run stops before writing a row and says
   which.
5. Load the rest. One table per file family, six tables in all:

   - `matchdays`, one row per matchday
   - `teams`, one row per team
   - `standings`, one row per team per block, so the row knows
     whether it is `table`, `home` or `away`
   - `teamstats`, one row per stat per match, as landed
   - `playerstats`, one row per stat per player per match, as landed

   Every stats row must carry the id of the match it came from.
6. Print the seven lines above, every number from a query against the
   database.
7. Run it twice. Same seven lines.

**Withheld:** where a stats row gets its match id from, since the row
itself has none. What a rerun does to a table that already exists.
What column type holds a standings `statsValue` that is `1` in one
row, `"stable"` in another, a list in a third and `None` in a fourth.
And which columns each table declares.

---

## Hard (optional): load per file

The mid tier rebuilds everything on every run. That is 250 MB read
and 1.4 million rows written to change nothing.

**Target output**

Three runs back to back, `loaded:` printed before the seven counts:

```
run 1                                  loaded: 616 files
run 2                                  loaded: 0 files, same seven counts
delete one playerstats file,
uv run ingest.py (requests: 1),
then the load                          loaded: 1 file, same seven counts
```

After the third run that match's stat rows appear exactly once.

**Spec**

8. Make the load per file. A file that has not changed since it was
   last loaded is not read again. A file that has changed is reloaded
   and its old rows are gone.

**Withheld:** what the load remembers about a file to know it has
changed, and where it remembers it. Recall from lesson 1 that two
pulls of the same match are never the same bytes.

---

## Reference

DuckDB can read JSON files by itself (`read_json`), and it can also
take rows you hand it from Python. Both are open to you.

Everything under `data/`, 616 files, landed by lesson 1:

```
data/matches/0de9cda0d297418699a8357a8825d46c.json       306 matches
data/matchdays/0de9cda0d297418699a8357a8825d46c.json      34 matchdays
data/teams/0de9cda0d297418699a8357a8825d46c.json          18 teams
data/standings/0de9cda0d297418699a8357a8825d46c.json     3 blocks x 18
data/teamstats/0de9cda0d297418699a8357a8825d46c/*.json    306 files
data/playerstats/0de9cda0d297418699a8357a8825d46c/*.json  306 files
```

Every season-level file is an envelope around a list. The list key
is the entity, plural:

```python
{"competition": {...}, "matches": [ {36 keys}, ... ], "apiCallRequestTime": "..."}
{"competition": {...}, "matchdays": [ {14 keys}, ... ], "apiCallRequestTime": "..."}
{"competition": {...}, "teams": [ {15 keys}, ... ], "apiCallRequestTime": "..."}
```

Standings is three blocks in one file, `table`, `home` and `away`,
each with 18 team rows. A team row is a team object plus 12 stats
in the long form you met in lesson 1. The 12 `statsValue`s are not
one type:

```python
{"standings": [
   {"type": "table", "teams": [
      {"teamId": "spl::Football_Team::...", "shortName": "Al Hilal", ...,
       "stats": [
         {"statsId": "rank",        "statsValue": 1},
         {"statsId": "team",        "statsValue": None},
         {"statsId": "points",      "statsValue": 86},
         {"statsId": "movement",    "statsValue": "stable"},
         {"statsId": "form",        "statsValue": [{"formLabel": "Win", ...}, ...]},
         ...]},
      ...]},
   {"type": "home", "teams": [...]},
   {"type": "away", "teams": [...]}],
 "apiCallRequestTime": "..."}
```

A teamstats file is one match. Its `stats` rows carry no match id;
the envelope does. Files hold 218 to 271 stats each, 76,648 rows in
total across 322 distinct `statsId`s. Values are ints, with some
floats.

```python
{"stats": [
   {"statsId": "last15-possession-perc", "statsLabel": "Last 15 Possession %",
    "statsLabelAbbreviation": None, "statsUnit": None,
    "statsUnitAbbreviation": None, "statsValueHome": 0, "statsValueAway": 0},
   ...],
 "matchId": "spl::Football_Match::ca8c6f7ba4b74c93813a2a393c52e9ad",
 "providerId": "opta:Match:...", "status": "FINISHED",
 "home": {"teamId": "...", "shortName": "Damac", ...},
 "away": {"teamId": "...", "shortName": "Al Hazem", ...},
 "apiCallRequestTime": "..."}
```

A playerstats file is one match, 12,164 player entries across the
306 files, 67 to 188 stats per entry, 1,387,916 stat rows in total
across 324 distinct `statsId`s. Exactly one stat per entry has a
null value, always `average-position`. Every other value is a
number.

```python
{"players": [
   {"player": {"playerId": "spl::Football_Player::...", "role": 1,
               "roleLabel": "Goalkeeper", "shortName": "Kewin", ...},
    "team": {"teamId": "spl::Football_Team::...", "shortName": "Damac", ...},
    "stats": [
      {"statsId": "pass-attempts", "statsLabel": "Pass Attempts",
       "statsValue": 33, ...},
      ...]},
   ...],
 "matchId": "spl::Football_Match::ca8c6f7ba4b74c93813a2a393c52e9ad",
 "home": {...}, "away": {...}, "apiCallRequestTime": "..."}
```
