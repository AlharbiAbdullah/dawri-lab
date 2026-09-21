with matches as (
    select *
    from {{ ref('stg_matches') }}
    where status = 'FINISHED'
),

team_matches as (
    select
        season_id,
        home_team_id as team_id,
        away_team_id as opponent_id,
        'home'       as venue,
        home_score   as goals_for,
        away_score   as goals_against
    from matches

    union all

    select
        season_id,
        away_team_id as team_id,
        home_team_id as opponent_id,
        'away'       as venue,
        away_score   as goals_for,
        home_score   as goals_against
    from matches
),

blocks as (
    select season_id, team_id, venue as type, goals_for, goals_against from team_matches
    union all
    select season_id, team_id, 'table' as type, goals_for, goals_against from team_matches
),

aggregated as (
    select
        season_id,
        type,
        team_id,
        count(*)                                          as played,
        count(*) filter (where goals_for > goals_against) as won,
        count(*) filter (where goals_for = goals_against) as drawn,
        count(*) filter (where goals_for < goals_against) as lost,
        sum(goals_for)                                    as goals_for,
        sum(goals_against)                                as goals_against
    from blocks
    group by season_id, type, team_id
),

scored as (
    select
        a.season_id,
        a.type,
        a.team_id,
        t.short_name                  as team_name,
        a.played,
        a.won,
        a.drawn,
        a.lost,
        a.goals_for,
        a.goals_against,
        a.goals_for - a.goals_against as goal_difference,
        3 * a.won + a.drawn           as points
    from aggregated a
    join {{ ref('stg_teams') }} t
        on t.team_id = a.team_id
       and t.season_id = a.season_id
),

head_to_head as (
    select
        s.season_id,
        s.type,
        s.team_id,
        sum(case
                when tm.goals_for > tm.goals_against then 3
                when tm.goals_for = tm.goals_against then 1
                else 0
            end)                             as h2h_points,
        sum(tm.goals_for - tm.goals_against) as h2h_goal_difference
    from scored s
    join team_matches tm
        on tm.team_id = s.team_id
       and tm.season_id = s.season_id
    join scored o
        on o.season_id = s.season_id
       and o.type    = s.type
       and o.team_id = tm.opponent_id
       and o.points  = s.points
    group by s.season_id, s.type, s.team_id
),

ranked as (
    select
        s.*,
        coalesce(h.h2h_points, 0)          as h2h_points,
        coalesce(h.h2h_goal_difference, 0) as h2h_goal_difference
    from scored s
    left join head_to_head h
        on h.season_id = s.season_id
       and h.type = s.type
       and h.team_id = s.team_id
)

select
    {{ dbt_utils.generate_surrogate_key(['season_id', 'type', 'team_id']) }} as standing_key,
    season_id,
    type,
    cast(row_number() over (
        partition by season_id, type
        order by
            points              desc,
            h2h_points          desc,
            h2h_goal_difference desc,
            goal_difference     desc,
            goals_for           desc
    ) as integer)                          as rank,
    team_id,
    team_name,
    cast(played          as integer) as played,
    cast(won             as integer) as won,
    cast(drawn           as integer) as drawn,
    cast(lost            as integer) as lost,
    cast(goals_for       as integer) as goals_for,
    cast(goals_against   as integer) as goals_against,
    cast(goal_difference as integer) as goal_difference,
    cast(points          as integer) as points
from ranked
