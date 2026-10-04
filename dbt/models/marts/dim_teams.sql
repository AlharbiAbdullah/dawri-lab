select distinct
    team_id,
    short_name as team_name
from {{ ref('stg_teams') }}