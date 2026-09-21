select
    m.season_id,
    m.type,
    m.team_id,
    m.rank as mart_rank,
    s.rank as api_rank
from {{ ref('mart_standings') }} m
join {{ ref('stg_standings') }} s
    on s.season_id = m.season_id
   and s.type = m.type
   and s.team_id = m.team_id
where m.season_id = '0de9cda0d297418699a8357a8825d46c'
  and m.rank <> s.rank
