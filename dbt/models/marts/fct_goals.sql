-- one row per goal, from the event feed.
-- the filled slot (home or away) is the side the goal COUNTS FOR, but the team
-- object inside that slot names the team the SCORER plays for. on an own goal
-- the two are different, so the credited team comes from the match, not the slot.
select
    e.feed_event_key as goal_key,
    e.match_id,
    e.event_id,
    e.side as scoring_side,
    case when e.side = 'home' then m.home_team_id else m.away_team_id end as scoring_team_id,
    e.player_id,
    e.team_id as scorer_team_id,
    e.event_type as goal_type,
    e.minute,
    e.additional_minutes,
    e.phase,
    e.home_score_after,
    e.away_score_after
from {{ ref('stg_feed_events') }} e
join {{ ref('stg_matches') }} m on m.match_id = e.match_id
where e.event_type in ('goal', 'penalty-goal', 'own-goal')
