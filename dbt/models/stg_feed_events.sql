select
    {{ dbt_utils.generate_surrogate_key(['match_id', 'event_id']) }} as feed_event_key,
    match_id::varchar as match_id,
    event_id::varchar as event_id,
    type::varchar as event_type,
    label::varchar as event_label,
    side::varchar as side,
    team_id::varchar as team_id,
    player_id::varchar as player_id,
    related_player_id::varchar as related_player_id,
    time::integer as minute,
    additional_time::integer as additional_minutes,
    phase::varchar as phase,
    home_score_push::integer as home_score_after,
    away_score_push::integer as away_score_after,
    time_stamp::timestamp as event_utc
from
    {{ source('raw', 'feed_events') }}
