---
title: Team
---

# {params.team}

```sql team_seasons
select s.season, t.matches_played, t.points, t.points_per_match,
       t.goal_difference, t.xg_for, t.xg_against
from dawri.team_metrics t
join dawri.seasons s on s.season_id = t.season_id
where t.team_name = '${params.team}'
order by s.season
```

<DataTable data={team_seasons} rows=all>
  <Column id=season />
  <Column id=matches_played />
  <Column id=points />
  <Column id=points_per_match fmt="0.00" />
  <Column id=goal_difference />
  <Column id=xg_for fmt="0.00" />
  <Column id=xg_against fmt="0.00" />
</DataTable>
