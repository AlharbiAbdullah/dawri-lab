select
    {{ dbt_utils.generate_surrogate_key([
        'season_id', 'match_id', 'player_id', 'type', 'time', 'additional_time'
    ]) }} as lineup_event_key,
    season_id::varchar as season_id,
    match_id::varchar as match_id,
    team_id::varchar as team_id,
    player_id::varchar as player_id,
    type::varchar as event_type,
    label::varchar as event_label,
    time::integer as minute,
    additional_time::integer as additional_minutes,
    related_player_id::varchar as related_player_id,
    phase::varchar as phase
from
    {{ source('raw', 'lineup_events') }}
