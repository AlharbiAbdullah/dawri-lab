with finished as (
    select * from {{ ref('stg_matches') }}
    where status = 'FINISHED'
),

sides as (
    select match_id, season_id, matchday_id, kickoff_utc,
           'home' as venue, home_team_id as team_id, away_team_id as opponent_id,
           home_score as goals_for, away_score as goals_against
    from finished
    union all
    select match_id, season_id, matchday_id, kickoff_utc,
           'away', away_team_id, home_team_id, away_score, home_score
    from finished
),

scored as (
    select *,
        case when goals_for > goals_against then 'W'
             when goals_for = goals_against then 'D'
             else 'L' end as result,
        case result when 'W' then 3 when 'D' then 1 else 0 end as points
    from sides
),

team_stats as (
    select match_id,
        max(case when stat_id = 'expected-goals' then home_value end) as home_xg,
        max(case when stat_id = 'expected-goals' then away_value end) as away_xg,
        max(case when stat_id = 'shots'          then home_value end) as home_shots,
        max(case when stat_id = 'shots'          then away_value end) as away_shots,
        max(case when stat_id = 'shots-on-goal'  then home_value end) as home_sot,
        max(case when stat_id = 'shots-on-goal'  then away_value end) as away_sot
    from {{ ref('stg_teamstats') }}
    group by match_id
)

select
    {{ dbt_utils.generate_surrogate_key(['s.match_id', 's.team_id']) }} as team_match_key,
    s.season_id,
    s.match_id,
    s.matchday_id,
    s.kickoff_utc,
    s.venue,
    s.team_id,
    s.opponent_id,
    s.goals_for::integer     as goals_for,
    s.goals_against::integer as goals_against,
    s.result,
    s.points::integer        as points,
    (case when s.venue = 'home' then t.home_xg    else t.away_xg    end)::double  as xg_for,
    (case when s.venue = 'home' then t.away_xg    else t.home_xg    end)::double  as xg_against,
    (case when s.venue = 'home' then t.home_shots else t.away_shots end)::integer as shots,
    (case when s.venue = 'home' then t.home_sot   else t.away_sot   end)::integer as shots_on_target
from scored s
left join team_stats t
    on t.match_id = s.match_id