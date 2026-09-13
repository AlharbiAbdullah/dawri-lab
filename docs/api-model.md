# SPL API data model

What the Saudi Pro League API actually is, and how its entities connect.
Derived by calling every season-level endpoint on 2026-09-11 and extracting
every ID field from the real responses. Not guesswork.

## What this API is

`https://api-sdp.spl.com.sa` is a **Deltatre Sport Data Platform** tenant.
SPL is not a bespoke API, it is an off-the-shelf sports platform, which is why
the paths carry a `{projectCode}` segment. Ours is `spl`.

- Base: `https://api-sdp.spl.com.sa/v1/spl/football`
- Spec: `https://api-sdp.spl.com.sa/swagger/v1/swagger.json` (**91 endpoints**, saved as `docs/spl-swagger.json`)
- Auth: none
- All calls take `?locale=en-GB`

The spec is not linked from anywhere. It exists but is undocumented publicly.

### It is not a tree

Each URL is a separate query returning a separate document. A parent never
embeds its children: `/seasons/{id}` returns 11 fields about the season and no
matches. What connects resources is **IDs, not nesting**. Same idea as foreign
keys between tables. The tree is something you reconstruct by joining.

Every ID is self-describing:

```
spl::Football_Season::0de9cda0d297418699a8357a8825d46c
     ^^^^^^^^^^^^^^^ entity type is in the value
```

So you can always tell what an ID points at without documentation.

## ERD

```mermaid
erDiagram
    COMPETITION ||--o{ SEASON     : "season.competitionId"
    SEASON      ||--o{ STAGE      : "stages envelope seasonId"
    SEASON      ||--o{ MATCHDAY   : "matchdays.seasonId"
    STAGE       ||--o{ MATCHDAY   : "matchdays.stageId"
    SEASON      ||--o{ MATCH      : "match.seasonId"
    MATCHDAY    ||--o{ MATCH      : "match.matchSet.matchSetId"
    TEAM        ||--o{ MATCH      : "match.home.teamId / away.teamId"
    STADIUM     ||--o{ MATCH      : "match.stadiumId"
    TEAM        ||--|| STADIUM    : "teams.stadium.id"
    TEAM        ||--o{ PLAYER     : "roster envelope team.teamId"
    TEAM        ||--o{ OFFICIAL   : "roster.officials.staffId"
    SEASON      ||--o{ STANDING   : "one row per team"
    TEAM        ||--|| STANDING   : "standings.teams.teamId"
    SEASON      ||--o{ TEAMSTAT   : "199 rows per team"
    TEAM        ||--o{ TEAMSTAT   : "stats.teams.teamId"
    SEASON      ||--o{ PLAYERSTAT : "205 rows per player"
    PLAYER      ||--o{ PLAYERSTAT : "stats.players.playerId"
    TEAM        ||--o{ PLAYERSTAT : "stats.players.team.teamId"

    COMPETITION {
        string competitionId PK
        string providerId "opta:Competition:..."
        string name
        string officialName
        string shortName
        string acronymName
        object imagery "empty object here"
    }
    SEASON {
        string seasonId PK
        string competitionId FK
        string providerId "opta:Competition:... not a season id"
        string name "competition name, not season"
        string officialName
        string shortName
        string acronymName
        string seasonName "2025/2026"
        string startDateUtc "null on this endpoint"
        string endDateUtc "null on this endpoint"
        object imagery "empty here, seasonLogo appears in match envelopes"
    }
    STAGE {
        string stageId PK
        string name "2025/2026"
        string startDate
        string endDate
        string seasonId FK "envelope level, not on the row"
        string competitonId FK "envelope level, typo is theirs"
    }
    MATCHDAY {
        string matchSetId PK "entity is matchday, key is matchSet"
        string providerId
        string name "Matchday 1"
        string shortName
        string seasonId FK
        string competitionId FK
        string stageId FK
        string roundId FK "null, flat league"
        int    index "null"
        string matchSetFormatId "null"
        string type "null"
        string startDateUtc
        string endDateUtc
        string matchdayStatus
    }
    MATCH {
        string matchId PK
        string providerId
        string seasonId FK
        string stadiumId FK
        string winTeamId FK "null on the 70 draws"
        string home_teamId FK "full TEAM object inlined"
        string away_teamId FK "full TEAM object inlined"
        string matchSet_matchSetId FK "full MATCHDAY object inlined"
        string previousLegId FK "empty string, league has no legs"
        string status "FINISHED on all 306"
        string providerStatus "Played"
        string phase "FULL_TIME"
        string scheduleStatus "UNKNOWN on all 306"
        string matchDateUtc
        string matchDateLocal
        string localTimeUtcOffset
        bool   isUnknownKickOffTime
        int    providerHomeScore
        int    providerAwayScore
        int    homeScorePush
        int    awayScorePush
        int    providerPenaltyScoreHome "null, no shootouts"
        int    providerPenaltyScoreAway "null"
        string winReason "Draw or RegularTime"
        string aggregate "empty string"
        string previousLegsResult "null"
        string time "90 on all 306"
        string additionalTime
        string stadiumName "denormalized"
        string cityName "denormalized"
        string group "null"
        string groupId FK "null"
        string groupName "null"
        string roundId FK "null"
        string roundName "null"
        string subLeague "empty string"
    }
    TEAM {
        string teamId PK
        string providerId
        string shortName
        string officialName
        string acronymName
        string acronymNameLocalized
        string mediaName
        string mediaShortName
        string countryCode "null inside standings rows"
        string teamType
        bool   isTeamFake
        string overallSummary "null everywhere seen"
        string stadium_id FK "full STADIUM inlined on /teams, null elsewhere"
        string imagery_stadiumImage
        string imagery_teamImage
        string imagery_teamLogo
        string imagery_teamLogoLight
        array  allSeasonImagery "always empty"
        string editorial_websiteUrl "stats/teams only"
        string editorial_shopUrl "stats/teams only"
        string editorial_ticketsUrl "stats/teams only"
        string editorial_clubPrimaryColour "stats/teams only"
        string editorial_clubSecondaryColour "stats/teams only"
        string editorial_clubTextColour "stats/teams only"
        string editorial_social_facebook "stats/teams only"
        string editorial_social_instagram "stats/teams only"
        string editorial_social_x "stats/teams only"
        string editorial_social_tikTok "stats/teams only"
        string editorial_social_youTube "stats/teams only"
        string editorial_social_linkedIn "stats/teams only"
    }
    STADIUM {
        string id PK "id, not stadiumId"
        string providerId
        string name
        string cityName
        string country
        string address
        int    capacity
        int    yearOfConstruction
        string mapsGeoCodeLatitude "string, not float"
        string mapsGeoCodeLongitude "string, not float"
        string imagery_stadiumImage
    }
    PLAYER {
        string playerId PK
        string providerId
        string team_teamId FK "stats/players only, roster puts it on the envelope"
        string bibNumber "string, not int"
        int    role "1 to 4"
        string roleLabel "Goalkeeper Defender Midfielder Forward"
        string mediaFirstName
        string mediaLastName
        string shirtName
        string shortName
        string displayName
        string nationality
        string nationalityIsoCode
        string editorial_playerRoleWithinTeam
        string dateOfBirth "roster only"
        string height "roster only, string"
        string weight "roster only, string"
        string playerStatus "roster only"
        string leaveDate "roster only"
        array  info "roster only, player jersey position age"
        string imagery_playerImage_home_celeb "stats/players only"
        string imagery_playerImage_home_left "stats/players only"
        string imagery_playerImage_home_middle "stats/players only"
        string apiCallRequestTime "leaked 0001-01-01, ignore"
    }
    OFFICIAL {
        string staffId PK
        string providerId
        string teamId FK "envelope level"
        string roleLabel "Head Coach or Assistant Coach, 0 to 2 per team"
        string status
        string shortName
        string displayName
        string mediaFirstName
        string mediaLastName
        string nationality
        string nationalityIsoCode
        string dateOfBirth
        object imagery "empty object"
    }
    STANDING {
        string seasonId FK "envelope level"
        string teamId FK "row is a full TEAM object plus stats"
        int    rank "arrives as stats.statsId rank"
        int    points
        int    matches_played
        int    win
        int    draw
        int    lose
        int    goals_for
        int    goals_against
        int    goal_difference
        string movement
        array  form "6 objects: formLabel formLabelAbbreviation formType"
        string team "label only, statsValue is null"
        int    qualification_qualificationId "always 0"
        string qualification_qualificationLabel "ACL Elite, ACL 2, Relegation, null"
        array  achievementStatuses "always empty"
        string note "null"
    }
    TEAMSTAT {
        string seasonId FK "envelope level"
        string teamId FK "row is a full TEAM object plus stats"
        string statsId PK "199 distinct, EAV not columns"
        string statsLabel
        string statsLabelAbbreviation
        int    statsValue "number in every row seen"
        string statsUnit "always null"
        string statsUnitAbbreviation "always null"
        string rankLabel "null"
    }
    PLAYERSTAT {
        string seasonId FK "envelope level"
        string playerId FK "row is a full PLAYER object plus stats"
        string team_teamId FK "full TEAM object inlined"
        string statsId PK "205 distinct, EAV not columns"
        string statsLabel
        string statsLabelAbbreviation
        int    statsValue "number or null"
        string statsUnit "always null"
        string statsUnitAbbreviation "always null"
        string rankLabel "null"
    }
```

Reading it: nested JSON paths are flattened with `_`, so `stadium.id` becomes
`stadium_id` and `matchSet.matchSetId` becomes `matchSet_matchSetId`. Hyphenated
stat ids become underscores too (`goals-for` to `goals_for`). Fields marked
"envelope level" sit on the response root, not on the row, so you have to stamp
them onto each row at ingest. Fields marked "inlined" mean the API ships a full
copy of the child entity inside the row; the ERD lists the key and drops the
duplicated columns.

Attributes and null behavior were read off live responses on 2026-09-12, one
call per endpoint, plus all 306 rows of the landed matches file. A field noted
as always null is null in every row of that call, not just the first.



`matches` **is the fact table.** One row per match, six foreign keys, and the
measures (scores, time). Everything else is a dimension or a pre-aggregate.

## Endpoints that resolve, with grain

Season ID for 2025/26: `spl::Football_Season::0de9cda0d297418699a8357a8825d46c`


| endpoint                                     | grain      | rows              | notes                                 |
| -------------------------------------------- | ---------- | ----------------- | ------------------------------------- |
| `/seasons/{id}`                              | 1 season   | 1                 | name, competitionId, nothing else     |
| `/seasons/{id}/matches`                      | 1 match    | 306               | the fact table                        |
| `/seasons/{id}/standings`                    | 1 team     | 18                | 12 stats per team, EAV like the rest  |
| `/seasons/{id}/teams`                        | 1 team     | 18                | team dimension, includes home stadium |
| `/seasons/{id}/stadiums`                     | 1 stadium  | 18                | stadium dimension                     |
| `/seasons/{id}/matchdays`                    | 1 matchday | 34                | matchday dimension                    |
| `/seasons/{id}/stages`                       | 1 stage    | 1                 | single stage, flat league             |
| `/seasons/{id}/stats/teams`                  | 1 team     | 18                | **199 distinct stats**                |
| `/seasons/{id}/stats/players`                | 1 player   | 30/page, 23 pages | **205 distinct stats**                |
| `/seasons/{id}/transfers`                    | -          | 0                 | returns empty                         |
| `/v2/.../seasons/{id}/teams/{teamId}/roster` | 1 player   | 24-166 per team   | squad history, staff in `officials`    |
| `/competitions/{id}/seasons`                 | 1 season   | -                 | how to find other seasons             |


404 at season level: `players`, `rounds`, `statistics`, `squads`, `venues`,
`officials`. Use the paths in the table instead.

## Facts that shape the ingest

**The 2025/26 season is complete.** All 306 matches are `FINISHED`,
18 teams x 17 opponents x 2 legs. Team stats show 34 games played. Nothing in
this dataset is live or provisional, which suits a facts-only product.

**Stats come back long, not wide.** Both stats endpoints return an array per
entity, not columns:

```json
{"statsId": "goals", "statsLabel": "Goals", "statsValue": 1, "statsUnit": null}
```

That is entity-attribute-value. 205 stat types for players, 199 for teams,
and `standings` uses the same envelope for its 12 columns.
Land it as-is, pivot in DuckDB. Do not try to flatten at ingest time.

**The roster is not the season squad.** Per-team counts run 24 to 166, 1,896
rows across the 18 teams, against roughly 690 players in `stats/players`, and
ages inside one roster reach 53. The `seasonId` in the path does not scope it.
There is no flag to filter on either: in the two teams checked every row is
`playerStatus: Active` with an empty `leaveDate`, and `bibNumber` is blank on
44 of 166. Treat `stats/players` as the list of who actually played, and the
roster as biographical lookup only. Officials sit in a separate `officials`
array, 0 to 2 per team, Head Coach and sometimes an Assistant Coach.

`stats/players` **is paginated, nothing else is.** `{"totalPages": 23, "currentPage": 1, "isLastPage": false}` at 30 per page, roughly 690 players.
Every other endpoint returns the full set in one call.

**Position lives on** `roleLabel`**, and it is already on the stats rows.**
`1 Goalkeeper, 2 Defender, 3 Midfielder, 4 Forward`. Since `stats/players`
carries `role`, `roleLabel` and `team`, "best per position" needs that one
endpoint. No roster join required.

**Envelopes are inconsistent.** `/seasons/{id}` returns `{"season": {...}}`
singular while `/competitions/{id}` returns `{"competitions": ...}` plural for a
single record. `stadiums` keys its ID as `id`, everything else uses
`<entity>Id`. Endpoints that go through the competition include a `competition`
block; `/seasons/{id}` does not. `/stages` misspells its envelope key as
`competitonId`. Rows from `/stats/players` and the roster carry their own
`apiCallRequestTime` set to `0001-01-01`, a leaked base-class field, not data.
Assume nothing is uniform, check each one.

## Reading the spec

```bash
# all endpoints
jq -r '.paths | keys[]' docs/spl-swagger.json

# schema names
jq -r '.components.schemas | keys[]' docs/spl-swagger.json

# one endpoint's shape
jq '.paths["/v1/{projectCode}/football/seasons/{seasonId}/standings"]' docs/spl-swagger.json
```



## Finding IDs in any response

```bash
curl -s "$URL" | jq -r '
  [paths(type=="string") as $p
   | select(getpath($p)|test("^spl::"))
   | {k: ($p|map(select(type=="string"))|join(".")),
      t: (getpath($p)|split("::")[1])}]
  | group_by(.k) | map({key:.[0].k, type:.[0].t}) | .[]
  | "\(.key) -> \(.type)"' | sort -u
```

This is how the ERD above was built. Run it against any new endpoint and it
prints that endpoint's foreign keys.