with cte as (

        select
            {{ dbt_utils.generate_surrogate_key(['type', 'team_id']) }} as standing_key,
            type, 
            team_id, 
            short_name as team_name, 
            unnest(stats) as stats
        from 
            {{ source('raw', 'standings') }}
)

select
    standing_key,
    type,
    team_id,
    team_name,
    max(case when stats.statsid = 'rank'            then stats.statsvalue end)::integer as rank,
    max(case when stats.statsid = 'points'          then stats.statsvalue end)::integer as points,
    max(case when stats.statsid = 'matches-played'  then stats.statsvalue end)::integer as played,
    max(case when stats.statsid = 'win'             then stats.statsvalue end)::integer as won,
    max(case when stats.statsid = 'draw'            then stats.statsvalue end)::integer as drawn,
    max(case when stats.statsid = 'lose'            then stats.statsvalue end)::integer as lost,
    max(case when stats.statsid = 'goals-for'       then stats.statsvalue end)::integer as goals_for,
    max(case when stats.statsid = 'goals-against'   then stats.statsvalue end)::integer as goals_against,
    max(case when stats.statsid = 'goal-difference' then stats.statsvalue end)::integer as goal_difference,
    max(case when stats.statsid = 'movement'        then trim(stats.statsvalue, '"') end)::varchar as movement,
    max(case when stats.statsid = 'form'            then stats.statsvalue end)::varchar as form
from cte
group by 1, 2, 3, 4
