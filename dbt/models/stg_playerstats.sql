select
    {{ dbt_utils.generate_surrogate_key(['season_id', 'match_id', 'player_id', 'stats_id']) }} as player_stat_key,
    season_id,
    match_id,
    player_id,
    team_id,
    stats_id as stat_id,
    stats_label as stat_label,
    stats_unit as stat_unit,
    stats_value as value
from
    {{ source('raw', 'playerstats') }}
qualify row_number() over (
    partition by season_id, match_id, player_id, stats_id
    order by
        case
            when stats_label is null then 2                      -- no label loses
            when stats_label = lower(stats_label) then 1          -- all-lowercase loses
            else 0                                               -- display casing wins
        end,
        stats_label                                              -- byte order, breaks any remainder
) = 1