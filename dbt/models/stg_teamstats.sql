

select
    {{ dbt_utils.generate_surrogate_key(['season_id', 'match_id', 'stats_id']) }} as team_stat_key,
    season_id,
    match_id,
    stats_id as stat_id, 
    stats_label as stat_label,
    stats_unit as stat_unit, 
    stats_value_home as home_value,
    stats_value_away as away_value
from 
    {{ source('raw', 'teamstats') }}