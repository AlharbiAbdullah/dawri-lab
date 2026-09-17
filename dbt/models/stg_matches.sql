select
    match_id::varchar as match_id, 
    match_date_utc::timestamp as kickoff_utc, 
    match_date_local::timestamp as kickoff_local,
    local_time_utc_offset::varchar as utc_offset, 
    status::varchar as status, 
    win_reason::varchar as win_reason, 
    win_team_id::varchar as win_team_id,
    home_score_push::bigint as home_score,
    away_score_push::bigint as away_score, 
    time::integer as minutes_played,  
    additional_time::integer as additional_minutes, 
    home.teamid::varchar as home_team_id,
    away.teamid::varchar as away_team_id,
    match_set.matchsetid::varchar as matchday_id, 
    stadium_name::varchar as stadium_name, 
    city_name::varchar as city_name, 
from 
    {{ source('raw', 'matches') }}