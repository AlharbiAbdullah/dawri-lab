# Lesson 2 build task: a contract at the boundary

Lesson 1 landed the raw season. Lesson 3 loads it into DuckDB, and
everything after that trusts what it loads. This lesson puts a
contract between the two: a Pydantic model that says what a valid
match is, so bad data stops here, loudly, instead of turning into a
wrong standings table three stages later.

The raw files stay exactly as landed. The contract reads them; it
never rewrites them.

## Input

The landed season file from lesson 1:

```
data/matches/0de9cda0d297418699a8357a8825d46c.json
```

One match has 36 keys. Parts that matter here, from the first match
in the file:

```python
{
  "matchId": "spl::Football_Match::ca8c6f7ba4b74c93813a2a393c52e9ad",
  "matchDateUtc": "2025-08-28T16:05:00Z",
  "home": {"teamId": "spl::Football_Team::2c0af0b9b0f0474f8742b5427dc351c6",
           "shortName": "Damac", ...},
  "away": {"teamId": "spl::Football_Team::...", "shortName": "Al Hazem", ...},
  "homeScorePush": 1,
  "awayScorePush": 1,
  "winTeamId": None,                 # None on all 70 draws
  "winReason": "Draw",               # or "RegularTime"
  "time": "90",                      # a string
  "additionalTime": "13",            # a string, 2 to 24 across the season
  "matchSet": {"matchSetId": "spl::Football_MatchDay::b51ca594...",
               "name": "Matchday 1", ...},   # an object, 14 keys
  "roundId": None,
  ...
}
```

Facts read off all 306 landed matches:

- No match has the same team at home and away.
- Scores run 0 to 6. None is negative.
- `winTeamId` is `None` exactly when the scores are level, and
  otherwise it is the `teamId` of the side that scored more.
- Every `matchDateUtc` ends in `Z`.

Playerstats, for the hard tier only. `data/playerstats/{season}/*.json`,
306 files. Each entry in `players` has a `player`, a `team` and a
`stats` list. `player.role` is `1` to `4` with `roleLabel`
`Goalkeeper`, `Defender`, `Midfielder`, `Forward`.

## Easy tier (start here)

1. Model one match with Pydantic and validate the first match in the
   landed file.
2. Print one line built from the validated model, not from the dict:

```
Damac 1-1 Al Hazem | Matchday 1 | 2025-08-28 16:05 UTC | 90+13
```

**Withheld:** which of the 36 keys the model declares, and what Python
type each one becomes. That decision is the lesson.

## Mid tier (builds on easy)

3. Validate all 306 landed matches against the same model.
4. Validate eight planted records. Each one is a copy of a real match
   with exactly one change:

| label | start from | change |
| ----- | ---------- | ------ |
| p1 | first match (Damac 1-1 Al Hazem) | `winTeamId` set to Damac's `teamId`, `spl::Football_Team::2c0af0b9b0f0474f8742b5427dc351c6` |
| p2 | first match | `away` replaced by a copy of `home` |
| p3 | first match | `additionalTime` set to `"13+2"` |
| p4 | first match | `homeScorePush` set to `-1` |
| p5 | first match | `matchDateUtc` set to `"2025-08-28T16:05:00"` |
| p6 | first match | the `matchId` key removed |
| p7 | first match with a winner (Al Ahli 1-0 NEOM SC, `spl::Football_Match::ff995f1389cb4c93b0e5513a46ef2ec3`) | `winTeamId` set to Al Fateh's `teamId`, `spl::Football_Team::02f22b11aa604566a1858f96addb669c` |
| p8 | first match | a new key added: `"attendance": 21450` |

5. Print:

```
landed: 306 valid, 0 rejected
planted: 1 valid, 7 rejected
rejected: p1 p2 p3 p4 p5 p6 p7
accepted: p8
```

6. Answer here, in words, not in the file: p5 is a real timestamp,
   the same instant as the first match, minus the `Z`. Why must the
   contract reject it, and what goes wrong downstream if it gets in?

**Withheld:** which rules belong in the contract beyond plain types,
and where a rule that needs two fields at once lives.

## Hard tier (optional)

Lesson 5 ranks the best players per position. That needs a position
on every player row.

180 playerstats entries across 50 match files carry `role: 0`,
`roleLabel: None`, `bibNumber: None`, and no name. They belong to 43
distinct `playerId`s, and none of those ids ever appears with a real
role. 115 of those 180 rows have `minsPlayed` above 0, so they played.

7. Model a playerstats entry and validate every entry in all 306
   files. Count known-role rows, and the unknown-role rows as rows,
   distinct players, and rows with minutes:

```
entries: 12164
known role: 11984
unknown role: 180 rows, 43 players, 115 rows with minutes
```

8. Say in words what the contract does with a `role: 0` row, and why
   that choice is the right one for a best-per-position ranking.

## Constraints

- Read only from `data/`. Zero network requests: everything this
  lesson needs is already landed.
- The raw files are never modified.
- Model field names are snake_case. The JSON keys stay as the source
  sent them. Lesson 3's tables use snake_case columns.
- A rejected record never stops the run. All 306 and all eight
  planted records are checked every time.

## Rules

- No skeleton on purpose. The design decisions are the lesson.
- `pydantic` is the real dependency and is already added. Standard
  library for everything else.
- Write it in `contracts.py` at the repo root. Do not change
  `ingest.py`.
- Three gates: `uv run ruff check`, `uv run ty check`, then
  `uv run contracts.py`.
- Answer step 6 here in words, not in the file.
- When it runs and the output matches, tell me and I will review
  your code.
