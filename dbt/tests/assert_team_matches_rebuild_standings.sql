with team_matches as (
    select * from {{ ref('fct_team_matches') }}
),

rebuilt as (
    select season_id, team_id, 'table' as type,
           count(*) as played, sum(points) as points,
           sum(goals_for) as goals_for, sum(goals_against) as goals_against
    from team_matches
    group by all
    union all
    select season_id, team_id, venue as type,
           count(*), sum(points), sum(goals_for), sum(goals_against)
    from team_matches
    group by all
),

standings as (
    select season_id, team_id, type, played, points, goals_for, goals_against
    from {{ ref('mart_standings') }}
)

select
    coalesce(r.season_id, s.season_id) as season_id,
    coalesce(r.team_id, s.team_id)     as team_id,
    coalesce(r.type, s.type)           as type,
    r.played as rebuilt_played,  s.played as standings_played,
    r.points as rebuilt_points,  s.points as standings_points,
    r.goals_for, s.goals_for as standings_goals_for,
    r.goals_against, s.goals_against as standings_goals_against
from rebuilt r
full outer join standings s
    on  r.season_id = s.season_id
    and r.team_id   = s.team_id
    and r.type      = s.type
where r.played        is distinct from s.played
   or r.points        is distinct from s.points
   or r.goals_for     is distinct from s.goals_for
   or r.goals_against is distinct from s.goals_against