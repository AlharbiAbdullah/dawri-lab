---
title: Dawri
---

```sql seasons
select season_id, season
from dawri.seasons
order by season desc
```

<Dropdown data={seasons} name=season value=season_id label=season title="Season" />

```sql standings
select team_name, points, goal_difference, xg_for, xg_against
from dawri.team_metrics
where season_id = '${inputs.season.value}'
order by points desc, goal_difference desc, team_name
```

<DataTable data={standings} rows=all>
  <Column id=team_name />
  <Column id=points />
  <Column id=goal_difference />
  <Column id=xg_for fmt="0.00" />
  <Column id=xg_against fmt="0.00" />
</DataTable>
