select
    {{ dbt_utils.generate_surrogate_key(['match_id', 'role_label']) }} as official_key,
    match_id::varchar as match_id,
    referee_id::varchar as referee_id,
    role_label::varchar as role_label,
    short_name::varchar as referee_name,
    nationality::varchar as nationality
from
    {{ source('raw', 'match_officials') }}
