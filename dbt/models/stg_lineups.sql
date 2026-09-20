select
    {{ dbt_utils.generate_surrogate_key(['match_id', 'player_id']) }} as lineup_key,
    match_id::varchar as match_id,
    team_id::varchar as team_id,
    side::varchar as side,
    selection::varchar as selection,
    tactical_formation::varchar as formation,
    player_id::varchar as player_id,
    bib_number::integer as shirt_number,
    role::integer as role,
    role_label::varchar as role_label,
    short_name::varchar as player_name,
    shirt_name::varchar as shirt_name,
    nationality::varchar as nationality,
    nationality_iso_code::varchar as nationality_iso,
    is_captain::boolean as is_captain,
    is_goalkeeper::boolean as is_goalkeeper,
    tactical_x_position::double as tactical_x,
    tactical_y_position::double as tactical_y
from
    {{ source('raw', 'lineups') }}
