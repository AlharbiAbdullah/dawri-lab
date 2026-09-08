# Lesson 1 build task: land the raw season

Dawri is a Saudi Pro League data product. Over this track it grows
into raw landing, DuckDB, dbt staging and marts, a metrics layer,
an API and a dashboard. This lesson is the first stage only: get
raw match data from the source onto disk, unchanged, in a way the
next stages can trust.

The source is the Saudi Pro League's own API, the backend of
spl.com.sa. No key, no auth. It is Opta-fed: every object carries
its `providerId`, so the ids you land here join to the wider
football data world later.

```
BASE = https://api-sdp.spl.com.sa/v1/spl/football
```

Ids are URNs and the `::` must be percent-encoded as `%3A%3A` in
the path. Every endpoint takes `?locale=en-GB`. `ar-SA` also works
and is a later lesson.

## The endpoints

Season level, one request each:

```
{BASE}/seasons/{seasonId}/matches
{BASE}/seasons/{seasonId}/matchdays
{BASE}/seasons/{seasonId}/teams
{BASE}/seasons/{seasonId}/standings/overall
```

Match level, one request each, per match:

```
{BASE}/seasons/{seasonId}/match/{matchId}/teamstats
{BASE}/seasons/{seasonId}/match/{matchId}/playerstats
```

There are more (`matches/{matchId}/header`, `match/{matchId}/matchfacts`,
`match/{matchId}/momentum`). They are not in this lesson. Note the
inconsistency you will hit later: `header` sits under `matches/`,
the stats sit under `match/`.

## The ids

Competition, the only one:

```
spl::Football_Competition::47d9987fd5044e0dba6c6c1df7d6cfa8
```

Seasons, all 16, prefix each with `spl::Football_Season::`

```
2026/2027  3677a75aaa514e43b2840e7fa367c91d   2018/2019  c28fd1dc2d6e4beda73a0d0cb19e3bfb
2025/2026  0de9cda0d297418699a8357a8825d46c   2017/2018  d624352d5aa24c338eb23f2cfa31e94a
2024/2025  5611fb3c5304461094180713b9b89c77   2016/2017  135d5ee0f68843eabccd356c7da05786
2023/2024  657b89b26f124ae7be101db557e2bc97   2015/2016  1d29d52309f24d3b96a5ab9a4e3fbc36
2022/2023  c1352d5302ec455594b8bf14de98da5e   2014/2015  8249b5564b064aa5bd66226b1bc60ac2
2021/2022  d070d10294524cae929a61bc8f2bfaad   2013/2014  1f26f803f99a4f6d828fb78bc86963bc
2020/2021  abb5ce4634584e79894e1d4e2b20a815   2012/2013  c4f5ae379f4348b1b2e3b8e538172cc4
2019/2020  0865193328eb4736b571cd3af4f70ce5   2011/2012  6710919ce9ce41ac9b28968922504bd1
```

You can also read this list from
`{BASE}/competitions/{competitionId}/seasons`. Whether you hardcode
or fetch is yours.

## Input

Response shapes, the parts you need. Everything else stays in the
file untouched.

`/matches` returns the whole season in one response, no paging, no
date windows:

```python
{
  "competition": {...},
  "matches": [
    {
      "matchId": "spl::Football_Match::ca8c6f7b...",
      "providerId": "opta:Match:4utj1vojyl6us12yevkgmvv9w",
      "seasonId": "spl::Football_Season::0de9cda0...",
      "status": "FINISHED",          # or UPCOMING
      "phase": "FULL_TIME",          # or PRE_MATCH
      "matchDateUtc": "2025-08-28T16:05:00Z",
      "matchDateLocal": "2025-08-28T19:05:00",
      "homeScorePush": 1, "awayScorePush": 1,
      "matchSet": "spl::Football_MatchDay::b51ca594...",
      "roundId": None, "roundName": None,
      "stadiumName": "...", "cityName": "...",
      "home": {"teamId": "spl::Football_Team::...", "shortName": "Damac", ...},
      "away": {"teamId": "spl::Football_Team::...", "shortName": "Al Hazem", ...},
    },
  ],
  "apiCallRequestTime": "2026-09-08T07:10:11.259Z",
}
```

`/playerstats` is the reason you are here. One response is roughly
780 KB: 40 players, 108 stats each, drawn from a pool of ~250
distinct `statsId` values including `expected-goals`,
`distance-covered-sprinting` and `average-speed-high-intensity-running`.

```python
{
  "players": [
    {
      "player": {"playerId": "spl::Football_Player::392aec7c...",
                 "providerId": "opta:Player:3948j6ya5agm0g8xbw0ob7v85",
                 "shortName": "Kewin", "roleLabel": "Goalkeeper",
                 "nationality": "Brazil", "bibNumber": "1", ...},
      "team": {"teamId": "spl::Football_Team::2c0af0b9...", "shortName": "Damac", ...},
      "stats": [
        {"statsId": "pass-attempts", "statsLabel": "Pass Attempts",
         "statsUnit": None, "statsValue": 33},
      ],
    },
  ],
  "matchId": "spl::Football_Match::ca8c6f7b...",
  "apiCallRequestTime": "...",
}
```

`/teamstats` is the same idea, one `stats` list with
`statsValueHome` and `statsValueAway` per entry.

The 2025/26 season has 306 matches and all 306 are FINISHED.

## Easy tier (start here)

1. Fetch `/matches` for 2025/2026.
2. Save the response body to disk under `data/`, byte for byte as
   received. No reshaping, no filtering.
3. Print one line:

```
landed 306 matches for 2025/2026
```

4. Then open the saved file and answer here, in words: the season
   has 34 matchdays, but every match's `roundId` is null and so is
   every matchday's `roundId`. Which field on a match points at
   which field on a matchday? Say how you found it, not just the
   answer.

**Withheld:** what identifies one raw pull on disk, and so what
its path and name are. That decision is the lesson.

## Mid tier (builds on easy)

5. Land the whole 2025/26 season: the four season-level endpoints,
   then `teamstats` and `playerstats` for every match. That is 616
   requests and roughly 250 MB on disk. Do not hammer the source:
   no more than four requests per second.
6. Running it a second time must make zero requests. The easy-tier
   code stays as it is and gets called, not rewritten.
7. After each run, read the landed files back from disk (not the
   responses you just got) and print:

```
requests: N
matches: 306
distinct: 306
teamstats: 306
playerstats: 306
```

`N` is yours to report. It is above 0 on the first run and exactly
0 on the second. `matches` counts match objects in the landed
season file. `distinct` counts distinct `matchId`. `teamstats` and
`playerstats` count landed files that actually carry data. All
four numbers are exact.

**Withheld:** what "already landed" means. Note before you decide:
every response carries `apiCallRequestTime`, set to the moment you
asked. Two pulls of an unchanged match are never the same bytes.

## Hard tier (optional)

The 2026/27 season is live right now: 306 matches, of which some
are FINISHED and the rest are UPCOMING. That split moves every
matchday, and a match's stats only exist once it has been played.

The source does not 404 for a match with no stats yet. It returns
HTTP 200 and this:

```json
{"stats": null, "matchId": null, "status": null,
 "apiCallRequestTime": "2026-09-08T07:10:11.259Z"}
```

`playerstats` does the same with `"players": null`. A 200 is not
proof you have data.

8. Land 2026/27. A rerun must re-request the season-level
   endpoints, and of the match-level ones only those whose match
   was not FINISHED the last time you landed it. Print which
   matches it refreshed.

Pass condition: two runs back to back; the second one requests the
season-level endpoints plus only the unfinished matches, and says
so. No exact output here.

## Constraints

- The saved body is the exact bytes the source sent. Later stages
  need to re-parse it, and a repaired or reshaped raw file cannot
  be re-parsed for something you did not think of today.
- Every match appears once in the landed data. `distinct: 306` is
  the check.
- Four requests per second, at most.
- A null-stats 200 is never stored as if it were a landed match.

## Rules

- No skeleton on purpose. The design decisions are the lesson.
- `httpx` is the real dependency and is already added. Standard
  library for everything else.
- Write it in `ingest.py` at the repo root. Where files live later
  is a later lesson.
- `data/` is gitignored. Everything you land goes under it.
- Three gates: `uv run ruff check`, `uv run ty check`, then
  `uv run ingest.py`.
- Answer step 4 here in words, not in the file.
- When it runs and the output matches, tell me and I will review
  your code.
