-- Generated from semantic/dawri.ossie.yaml and dawri.config by scripts/evidence_sync.py. Do not edit.
SELECT
    fct_team_matches.season_id AS season_id,
    dim_teams.team_name AS team_name,
    SUM(fct_team_matches.goals_for) - SUM(fct_team_matches.goals_against) AS goal_difference,
    SUM(fct_team_matches.goals_against) AS goals_against,
    SUM(fct_team_matches.goals_for) AS goals_for,
    SUM(1) AS matches_played,
    SUM(fct_team_matches.points) AS points,
    (SUM(fct_team_matches.points)) / (SUM(1)) AS points_per_match,
    SUM(fct_team_matches.shots) AS shots,
    SUM(fct_team_matches.shots_on_target) AS shots_on_target,
    SUM(fct_team_matches.xg_against) AS xg_against,
    SUM(fct_team_matches.xg_for) - SUM(fct_team_matches.xg_against) AS xg_difference,
    SUM(fct_team_matches.xg_for) AS xg_for
FROM read_parquet('../data/serving/fct_team_matches.parquet') AS fct_team_matches
LEFT JOIN read_parquet('../data/serving/dim_teams.parquet') AS dim_teams
    ON dim_teams.team_id = fct_team_matches.team_id
GROUP BY 1, 2
ORDER BY 1, 2
