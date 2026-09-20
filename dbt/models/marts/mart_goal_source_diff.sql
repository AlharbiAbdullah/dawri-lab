-- the matches where the goals on the lineup sheets do not add up to the score.
-- a lineup event hangs off the scoring player, so the side comes from his lineup
-- row, and an own goal counts for the other side.
with lineup_goals as (
    select
        e.match_id,
        case
            when e.event_type = 'own-goal' and l.side = 'home' then 'away'
            when e.event_type = 'own-goal' then 'home'
            else l.side
        end as scoring_side
    from {{ ref('stg_lineup_events') }} e
    join {{ ref('stg_lineups') }} l
        on l.match_id = e.match_id
       and l.player_id = e.player_id
    where e.event_type in ('goal', 'penalty-goal', 'own-goal')
),

lineup_counts as (
    select
        match_id,
        count(*) filter (scoring_side = 'home') as home_goals,
        count(*) filter (scoring_side = 'away') as away_goals
    from lineup_goals
    group by match_id
),

feed_counts as (
    select
        match_id,
        count(*) filter (scoring_side = 'home') as home_goals,
        count(*) filter (scoring_side = 'away') as away_goals
    from {{ ref('fct_goals') }}
    group by match_id
)

select
    m.match_id,
    coalesce(l.home_goals, 0)::integer as lineup_home_goals,
    coalesce(l.away_goals, 0)::integer as lineup_away_goals,
    coalesce(f.home_goals, 0)::integer as feed_home_goals,
    coalesce(f.away_goals, 0)::integer as feed_away_goals,
    m.home_score::integer as home_score,
    m.away_score::integer as away_score
from {{ ref('stg_matches') }} m
left join lineup_counts l on l.match_id = m.match_id
left join feed_counts f on f.match_id = m.match_id
where coalesce(l.home_goals, 0) <> m.home_score
   or coalesce(l.away_goals, 0) <> m.away_score
