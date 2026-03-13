"""
Trusted layer assets — reads raw JSON from MinIO, transforms to columnar
Parquet using DuckDB, and writes to the trusted-data bucket.

DuckDB's httpfs extension handles S3-compatible endpoints natively, so no
local file I/O is needed. MinIO requires path-style URLs and SSL disabled.
"""

import dagster as dg
from dagster_duckdb import DuckDBResource

from pipeline.resources import MinIOResource
from pipeline.assets.ingestion import (
    RAW_BUCKET,
    TARGET_COMPETITION_ID,
    TARGET_SEASON_ID,
)

TRUSTED_BUCKET = "trusted-data"


def _configure_s3(conn, minio: MinIOResource) -> None:
    """
    Configure DuckDB httpfs to talk to MinIO.
    s3_url_style='path' is required — MinIO doesn't support virtual-hosted style.
    s3_use_ssl=false because docker-compose runs without TLS.
    """
    conn.execute("INSTALL httpfs; LOAD httpfs;")
    conn.execute(f"SET s3_endpoint='{minio.endpoint}';")
    conn.execute(f"SET s3_access_key_id='{minio.access_key}';")
    conn.execute(f"SET s3_secret_access_key='{minio.secret_key}';")
    conn.execute("SET s3_url_style='path';")
    conn.execute("SET s3_use_ssl=false;")


@dg.asset(
    key_prefix=["trusted"],
    group_name="transformation",
    deps=["validated/events_validated"],
    description=(
        "Reads all raw event JSON files from MinIO, flattens nested fields, "
        "and writes a single Parquet file to the trusted bucket."
    ),
)
def events_trusted(
    context: dg.AssetExecutionContext,
    duckdb: DuckDBResource,
    minio: MinIOResource,
) -> dg.Output[None]:
    minio.ensure_bucket(TRUSTED_BUCKET)

    raw_path = f"s3://{RAW_BUCKET}/statsbomb/events/*.json"
    trusted_path = f"s3://{TRUSTED_BUCKET}/statsbomb/events/events.parquet"

    sql = f"""
    COPY (
        SELECT
            id::VARCHAR                              AS event_id,
            index::INTEGER                           AS event_index,
            period::INTEGER                          AS period,
            minute::INTEGER                          AS minute,
            second::INTEGER                          AS second,
            timestamp::VARCHAR                       AS timestamp,
            type.name::VARCHAR                       AS event_type,
            possession::INTEGER                      AS possession,
            possession_team.name::VARCHAR            AS possession_team,
            play_pattern.name::VARCHAR               AS play_pattern,
            team.id::INTEGER                         AS team_id,
            team.name::VARCHAR                       AS team_name,
            player.id::INTEGER                       AS player_id,
            player.name::VARCHAR                     AS player_name,
            position.name::VARCHAR                   AS position_name,
            -- StatsBomb location is a JSON array [x, y]; DuckDB arrays are 1-indexed
            TRY_CAST(location[1] AS DOUBLE)          AS loc_x,
            TRY_CAST(location[2] AS DOUBLE)          AS loc_y,
            duration::DOUBLE                         AS duration_s,
            -- Shot sub-object
            shot.statsbomb_xg::DOUBLE               AS xg,
            shot.outcome.name::VARCHAR              AS shot_outcome,
            -- Pass sub-object
            pass.length::DOUBLE                     AS pass_length,
            pass.angle::DOUBLE                      AS pass_angle_rad,
            pass.outcome.name::VARCHAR              AS pass_outcome
        FROM read_json_auto('{raw_path}', union_by_name=true, maximum_object_size=33554432)
    ) TO '{trusted_path}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """

    context.log.info(f"Transforming {raw_path} → {trusted_path}")
    with duckdb.get_connection() as conn:
        _configure_s3(conn, minio)
        conn.execute(sql)

    context.log.info("events_trusted materialized")
    return dg.Output(
        value=None,
        metadata={
            "trusted_path": dg.MetadataValue.text(trusted_path),
            "format": dg.MetadataValue.text("Parquet/ZSTD"),
        },
    )


@dg.asset(
    key_prefix=["trusted"],
    group_name="transformation",
    deps=["validated/events_validated"],
    description="Reads raw match JSON and writes a structured Parquet to the trusted bucket.",
)
def matches_trusted(
    context: dg.AssetExecutionContext,
    duckdb: DuckDBResource,
    minio: MinIOResource,
) -> dg.Output[None]:
    minio.ensure_bucket(TRUSTED_BUCKET)

    raw_path = (
        f"s3://{RAW_BUCKET}/statsbomb/matches/"
        f"{TARGET_COMPETITION_ID}/{TARGET_SEASON_ID}.json"
    )
    trusted_path = f"s3://{TRUSTED_BUCKET}/statsbomb/matches/matches.parquet"

    sql = f"""
    COPY (
        SELECT
            match_id::INTEGER                         AS match_id,
            match_date::DATE                          AS match_date,
            kick_off::VARCHAR                         AS kick_off,
            home_team.team_name::VARCHAR              AS home_team,
            away_team.team_name::VARCHAR              AS away_team,
            home_score::INTEGER                       AS home_score,
            away_score::INTEGER                       AS away_score,
            match_week::INTEGER                       AS match_week,
            competition.competition_name::VARCHAR     AS competition_name,
            season.season_name::VARCHAR               AS season_name,
            stadium.name::VARCHAR                     AS stadium_name,
            referee.name::VARCHAR                     AS referee
        FROM read_json_auto('{raw_path}')
    ) TO '{trusted_path}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """

    with duckdb.get_connection() as conn:
        _configure_s3(conn, minio)
        conn.execute(sql)

    context.log.info(f"matches_trusted materialized → {trusted_path}")
    return dg.Output(
        value=None,
        metadata={"trusted_path": dg.MetadataValue.text(trusted_path)},
    )
