with scored as (
    select
        season_id,
        match_id,
        count(*) filter (scoring_side = 'home') as home_goals,
        count(*) filter (scoring_side = 'away') as away_goals
    from {{ ref('fct_goals') }}
    group by season_id, match_id
)

select
    m.season_id,
    m.match_id,
    coalesce(s.home_goals, 0) as fact_home_goals,
    m.home_score,
    coalesce(s.away_goals, 0) as fact_away_goals,
    m.away_score
from {{ ref('stg_matches') }} m
left join scored s
    on s.season_id = m.season_id
   and s.match_id = m.match_id
where m.home_score is not null
  and m.away_score is not null
  and (
       coalesce(s.home_goals, 0) <> m.home_score
    or coalesce(s.away_goals, 0) <> m.away_score
  )
