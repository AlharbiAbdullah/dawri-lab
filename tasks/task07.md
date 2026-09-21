# L7: incremental and late data

## The concept

### The problem

Every lesson so far ran against one finished season. Nothing moved:
306 matches, all `FINISHED`, every file complete the moment it
landed. The 2026/27 season is being played right now, and the
pipeline was never built for data that moves:

1. **The pull only knows "have it or not".** For a finished season
   that is enough. A live season changes every matchday: the season
   files go stale, new matches finish, and an unplayed match answers
   HTTP 200 with an empty body that must never be landed.
2. **The load rebuilds the world.** Every `uv run load.py` rereads
   250 MB and rewrites 1.4 million rows to change nothing. With a
   season that grows every week, that gets worse every week.
3. **Everything downstream assumed finished matches.** The lesson 2
   contract rejects 243 of the 306 live matches. `kickoff_utc` cannot
   cast `'2026-11-05Z'`. Scores are null. The goals test compares
   matches that have no score yet.
4. **One season was baked in.** No raw table has a `season_id`. Two
   seasons in the same tables would mix.

### What we want

Both seasons side by side in the same tables. A pull that asks only
for what it does not already have, a load that rereads only the files
that changed, and marts that are per season. The 2025/26 answers do
not move by a single row.

This task folds in two hard tiers you skipped: lesson 1's live season
and lesson 3's per-file load. They are the same problem seen twice.

### What you will understand at the end

| Idea | In one line |
|---|---|
| Incremental pull | Ask only for what changed: season files always, a match only once it is finished and missing. |
| Empty is not landed | Each family says "nothing yet" its own way. The check must be the one that is true for that family. |
| Load ledger | The load remembers what it has seen. What it remembers, and where, decides what a rerun costs. |
| Contracts evolve | A contract written for finished matches has to decide what it does with unplayed ones. |
| Null is not zero | An unplayed match is not a 0-0 draw. Nothing downstream may invent data. |
| Late data (hard) | Finished matches get corrected afterwards. A refresh window re-pulls them, and only real changes replace rows. |

Easy makes the pull incremental. Mid makes the load incremental and
repairs what the live season broke. Hard handles corrections to
matches you already landed.

### Before and after

```
BEFORE                                  AFTER
one season, all FINISHED                two seasons in the same tables, one still moving
rerun: all or nothing                   rerun: 4 season requests + newly finished matches
load.py rebuilds 1.4M rows every run    loaded: 0 files when nothing changed
contract rejects 243 live matches       contract: 369 valid, 0 rejected
marts assume one season                 season_id in every grain and key
```

Guardrails for every tier:

- Both seasons live in the same raw tables, told apart by `season_id`. No table per season, no schema per season.
- The 2025/26 answers are frozen: 306 matches, 921 goals, the league table from lesson 5. Any change to them is a defect, and the tests from lessons 4 to 6 are what catch it.
- Nothing downstream invents data for an unplayed match. A null score is a null, not a zero.
- Zero network in dbt. The pull is `ingest.py` only, 4 per second.
- `ruff` and `ty` clean, both Python files change this lesson.
- Use the tools people use. dbt has `is_incremental()` and incremental models, DuckDB has `read_json` with a filename column. If you reach for one, know what it compiles to.
- Gates: the two ingest runs, the three load runs, then `uv run dbt build` and the `dbt show` results.

---

## Easy: an incremental pull

**Target output**

Per run:

```
requests: N
2026/2027 finished: 63 of 306
2026/2027 landed: 63 teamstats, 63 playerstats, 63 lineups,
                  63 matchfacts, 63 feed
```

(63 is what the season gave on 2026-09-20. Whatever the number is when
you run it, all five families agree with the finished count.)

Two runs back to back: the second prints `requests: 4`, the four
season-level endpoints and nothing else, and the same landed counts.
`uv run load.py` still prints the 2025/26 numbers unchanged, because
the live season is not loaded yet:

```
matches: 306   lineups: 12164   feed_events: 26038   (and the rest)
```

**Spec**

1. `ingest.py` takes a season argument instead of reading the first
   entry of the `seasons` dict. Both seasons are landed side by side
   under the paths you already use, `data/{family}/{season_id}/...`.
   The 2025/26 files stay exactly where they are and are not
   re-requested.
2. The pull rule, for the live season:
   - the four season-level endpoints (`matches`, `matchdays`,
     `teams`, `standings/overall`) are re-requested on every run.
     They change as the season moves.
   - a match-level family is requested for a match only when that
     match is `FINISHED` in the matches file just pulled, and only
     when the file is not already on disk.
   - an empty payload is never written. For each of the five
     match-level families, the check is the one that is actually true
     for that family, not `home is not None`.
3. Print the three lines of the target output, per run.
4. Gate: the two back-to-back runs and the unchanged load output
   above.

**Withheld:** how the rerun knows a match-level file is missing versus
already landed, now that "already landed" can mean "landed while the
match was still unplayed".

---

## Mid: an incremental load, and the three repairs

**Target output**

```
contract: 369 valid, 0 rejected    (306 finished 2025/26 + 63 finished live)
```

Three load runs back to back, `loaded:` printed before the count
lines:

```
run 1 after the change                 every file loaded, counts unchanged
run 2                                  loaded: 0 files, same counts
delete one 2025/26 playerstats file,
uv run ingest.py (requests: 1),
then uv run load.py                    loaded: 1 files, same counts
```

After the third run that match's rows appear exactly once.

`uv run dbt build` passes with both seasons in the warehouse, and the
2025/26 answers are unchanged:

```sql
select count(*) from {{ ref('fct_goals') }} where season_id = '...0de9cda0...'
-- 921

select rank, team_name, points from {{ ref('mart_standings') }}
where season_id = '...0de9cda0...' and type = 'table' order by rank limit 3
-- 1 Al Nassr 86 / 2 Al Hilal 84 / 3 Al Ahli 81
```

And the live season answers for the first time:

```sql
select type, count(*) from {{ ref('mart_standings') }}
where season_id = '...3677a75a...' group by 1
-- table 18 / home 18 / away 18

select sum(points) from {{ ref('mart_standings') }}
where season_id = '...3677a75a...' and type = 'table'
-- equals 3 x (finished matches) + draws, check it against the API's standings
```

**Spec**

5. Every raw table grows a `season_id` column, first position. The
   season is in the file path, not in most payloads, so `load.py`
   learns which season a file belongs to from where it is. Reload
   2025/26 and the live season together. The 2025/26 counts do not
   change, the tables get taller.
6. The contract decision. `load.py` validates matches before landing
   them. Choose and defend one of these, in code:
   - validate only what the contract was written for, and say in the
     output how many rows were skipped,
   - or widen `MatchContract` so an unplayed match is valid (null
     scores, date-only kickoff) while a finished match still has to
     agree with its own score, which is the rule lesson 2 built.

   Whichever you pick, a finished match with a wrong `winTeamId` is
   still rejected. Print the `contract:` line of the target output.
   Defend the choice in chat.
7. Per-file loading. A file that has not changed since its last load
   is not read again, a file that has changed is reloaded and its old
   rows are gone, and a file that is new is added. Print
   `loaded: N files` before the count lines. Gate: the three load
   runs above.
8. dbt. The staging models now carry two seasons and unplayed
   matches. Three things break and you fix them:
   - `stg_matches.kickoff_utc` cannot cast a date-only string the way
     it casts a timestamp. Decide what an unconfirmed kickoff becomes
     and say why.
   - `home_score` and `away_score` are null on unplayed matches. They
     stay null, nothing downstream may turn a null into a 0.
   - the goals test from lesson 6 compares every match to its score.
     It must now compare only matches that have one.

   `mart_standings` and `mart_goal_source_diff` are per season from
   here: `season_id` joins the grain and their keys include it.
9. Gate: `uv run dbt build` and the `dbt show` results above.
10. In chat: your load now skips files it has already seen. Say
    exactly what it remembers about a file, where that memory lives,
    and what happens to it if someone deletes the database but not
    the files, or the files but not the database. Then: the API
    stamps every response with `apiCallRequestTime`, so two pulls of
    the same match differ. Does your memory of a file survive a
    re-pull of a match that did not actually change? Say what you
    chose and what it costs.

**Withheld:** what the load remembers about a file and where it keeps
it. How a model that was written for one season becomes per season
without rewriting every query. Whether staging stays views now that
two seasons of feed events live in it.

---

## Hard (optional): late data

A match that was `FINISHED` when you landed it can be corrected
afterwards: a goal reassigned, a card rescinded, a stat revised. Your
easy-tier rule never re-requests a finished match, so those
corrections never arrive.

**Target output**

```
refreshed: 18 matches in the last 14 days
changed: 1 file (feed), rows replaced
```

**Spec**

11. Add a refresh window: a finished match whose kickoff is inside
    the last N days is re-requested on every run even though it is
    already on disk, and the load replaces its rows when the content
    changed (not when only `apiCallRequestTime` changed). Print what
    was refreshed and what actually changed.
12. Prove it without waiting for the league. Edit one landed feed
    file by hand: drop a goal event from it, run the load, and watch
    `fct_goals` and the goals test react. Put it back, run again, and
    watch them return. Say what your ledger did on each of the four
    runs.

**Withheld:** how to tell a real content change from a new
`apiCallRequestTime`.

---

## Reference

### The live season

`spl::Football_Season::3677a75aaa514e43b2840e7fa367c91d`, the
2026/27 Saudi League, listable from
`/competitions/{competitionId}/seasons` next to the one you have.
The competition id is in the envelope of your landed matches file.

As of 2026-09-20 it looked like this, and it moves every week:

```
306 matches      63 FINISHED     243 UPCOMING
 34 matchdays     7 'Played'      27 'Fixture'
```

Three shapes in it that 2025/26 never had:

**1. Kickoff times that are not times.** 198 of the 306
`matchDateUtc` values are date only, `'2026-11-05Z'`, 11 characters.
The other 108 are the full `'2026-08-13T16:15:00Z'`. A fixture with no
confirmed kickoff carries the date alone.

**2. Null scores.** `homeScorePush` and `awayScorePush` are null on
every unplayed match, and `winTeamId` is null on all of them.

**3. Your lesson 2 contract rejects most of the season.** Run
`contracts.MatchContract` over the live matches as they come:

```
valid 63, rejected 243
  homeScorePush int_type            243
  awayScorePush int_type            243
  matchDateUtc  datetime_from_date_parsing   198
```

All 63 finished matches pass. The contract is not wrong; it was
written for finished matches. Deciding what it does now is step 6.

### What an unplayed match returns

Every match-level endpoint answers HTTP 200 for a match that has not
been played. None of them 404s, and they do not all say "empty" the
same way:

```
teamstats     177 bytes   {"stats": null, "matchId": null, ...}
playerstats   179 bytes   {"players": null, ...}
lineups      1586 bytes   home and away PRESENT, but fielded [], benched [],
                          staff [], tacticalFormation ''
matchfacts    835 bytes   referees [], events null
feed          418 bytes   events []
```

`lineups` is the trap. Your lesson 6 guard is
`if lineups_json.get("home") is not None`, and on an unplayed match
that is true. You would land 243 files holding two empty team sheets.

### Why a rerun cannot compare bytes

Every response carries `apiCallRequestTime`, stamped at the moment of
the request. Two pulls of the same finished match are never the same
bytes, so "has this file changed" cannot be answered by comparing the
file to what the API just sent, and a re-pull of everything is not
free: the finished season alone is 250 MB.
