-- ============================================================
-- Football DataOps Lakehouse — Analytical Queries
-- Run these in a local DuckDB CLI session:
--   duckdb
-- Then paste the SET statements below, followed by any query.
-- ============================================================

-- 1. Configure DuckDB to connect to local MinIO
INSTALL httpfs; LOAD httpfs;
SET s3_endpoint='localhost:9000';
SET s3_access_key_id='minioadmin';
SET s3_secret_access_key='minioadmin';
SET s3_url_style='path';
SET s3_use_ssl=false;

-- ── Match results ────────────────────────────────────────────────────────────

-- 2. Season standings snapshot
SELECT
    home_team AS team,
    SUM(CASE WHEN home_score > away_score THEN 3
             WHEN home_score = away_score THEN 1
             ELSE 0 END) AS home_pts,
    SUM(home_score)      AS home_gf,
    SUM(away_score)      AS home_ga
FROM read_parquet('s3://trusted-data/statsbomb/matches/matches.parquet')
GROUP BY home_team
ORDER BY home_pts DESC;

-- ── Shots & xG ───────────────────────────────────────────────────────────────

-- 3. xG per team (attacking contribution)
SELECT
    team_name,
    COUNT(*)                              AS shots,
    ROUND(SUM(xg), 2)                    AS total_xg,
    ROUND(AVG(xg), 4)                    AS avg_xg_per_shot
FROM read_parquet('s3://trusted-data/statsbomb/events/events.parquet')
WHERE event_type = 'Shot'
GROUP BY team_name
ORDER BY total_xg DESC;

-- 4. Shot map — individual shots with coordinates
SELECT
    player_name,
    team_name,
    loc_x,
    loc_y,
    xg,
    shot_outcome
FROM read_parquet('s3://trusted-data/statsbomb/events/events.parquet')
WHERE event_type = 'Shot'
  AND xg IS NOT NULL
ORDER BY xg DESC
LIMIT 50;

-- ── Pass network ─────────────────────────────────────────────────────────────

-- 5. Pass density heatmap (12×10 grid — each cell = 10m × 8m on a 120×80 pitch)
SELECT
    FLOOR(loc_x / 10)::INT  AS grid_x,
    FLOOR(loc_y / 8)::INT   AS grid_y,
    COUNT(*)                 AS pass_count
FROM read_parquet('s3://trusted-data/statsbomb/events/events.parquet')
WHERE event_type = 'Pass'
  AND loc_x IS NOT NULL
  AND loc_y IS NOT NULL
GROUP BY grid_x, grid_y
ORDER BY pass_count DESC;

-- 6. Average pass length per team
SELECT
    team_name,
    COUNT(*)                        AS passes,
    ROUND(AVG(pass_length), 1)      AS avg_length_m,
    ROUND(AVG(pass_angle_rad), 3)   AS avg_angle_rad
FROM read_parquet('s3://trusted-data/statsbomb/events/events.parquet')
WHERE event_type = 'Pass'
  AND pass_length IS NOT NULL
GROUP BY team_name
ORDER BY avg_length_m DESC;

-- ── Pressing intensity ───────────────────────────────────────────────────────

-- 7. Top pressers (high pressing = many Pressure events in opponent half, loc_x > 60)
SELECT
    player_name,
    team_name,
    COUNT(*)                        AS pressures,
    ROUND(AVG(loc_x), 1)           AS avg_press_x,
    ROUND(AVG(loc_y), 1)           AS avg_press_y
FROM read_parquet('s3://trusted-data/statsbomb/events/events.parquet')
WHERE event_type = 'Pressure'
  AND loc_x > 60  -- opponent half
GROUP BY player_name, team_name
ORDER BY pressures DESC
LIMIT 20;

-- ── Event type distribution ──────────────────────────────────────────────────

-- 8. Overall event taxonomy
SELECT
    event_type,
    COUNT(*) AS total,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM read_parquet('s3://trusted-data/statsbomb/events/events.parquet')
GROUP BY event_type
ORDER BY total DESC;
