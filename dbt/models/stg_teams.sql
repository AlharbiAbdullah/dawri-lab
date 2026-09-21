select
    season_id::varchar as season_id,
    team_id,
    short_name,
    official_name,
    acronym_name as acronym,
    country_code,
    stadium.name as stadium_name,
    stadium.cityName as city_name,
    stadium.capacity as stadium_capacity,
    imagery.teamLogo as logo_path
from
    {{ source('raw', 'teams') }}
