select 
    match_set_id::varchar as matchday_id,
    name,
    short_name, 
    start_date_utc::timestamp as start_utc, 
    end_date_utc::timestamp as end_utc,
    matchday_status as status,
from 
    {{ source('raw', 'matchdays') }}
