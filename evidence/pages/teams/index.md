---
title: Teams
---

```sql teams
select distinct team_name
from dawri.team_metrics
order by team_name
```

{#each teams as team}

- <a href="/teams/{encodeURIComponent(team.team_name)}">{team.team_name}</a>

{/each}
