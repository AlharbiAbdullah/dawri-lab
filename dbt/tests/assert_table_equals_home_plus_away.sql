with s as (
    select * from {{ ref('mart_standings') }}
),

t as (select * from s where type = 'table'),
h as (select * from s where type = 'home'),
a as (select * from s where type = 'away')

select
    t.team_id,
    t.played, h.played + a.played as ha_played,
    t.won,    h.won    + a.won    as ha_won,
    t.drawn,  h.drawn  + a.drawn  as ha_drawn,
    t.lost,   h.lost   + a.lost   as ha_lost,
    t.goals_for,     h.goals_for     + a.goals_for     as ha_goals_for,
    t.goals_against, h.goals_against + a.goals_against as ha_goals_against,
    t.points, h.points + a.points as ha_points
from t
join h on h.team_id = t.team_id and h.season_id = t.season_id
join a on a.team_id = t.team_id and a.season_id = t.season_id
where t.played        <> h.played        + a.played
   or t.won           <> h.won           + a.won
   or t.drawn         <> h.drawn         + a.drawn
   or t.lost          <> h.lost          + a.lost
   or t.goals_for     <> h.goals_for     + a.goals_for
   or t.goals_against <> h.goals_against + a.goals_against
   or t.points        <> h.points        + a.points