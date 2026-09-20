select
    match_id::varchar as match_id,
    stadium_id::varchar as stadium_id,
    stadium_name::varchar as stadium_name,
    city_name::varchar as city_name,
    number_of_spectators::integer as attendance,
    maps_geo_code_latitude::double as latitude,
    maps_geo_code_longitude::double as longitude
from
    {{ source('raw', 'match_facts') }}
