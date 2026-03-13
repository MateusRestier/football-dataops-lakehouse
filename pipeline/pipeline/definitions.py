import dagster as dg
from dagster_duckdb import DuckDBResource

from pipeline.resources import MinIOResource
from pipeline.assets.ingestion import competitions_raw, matches_raw, events_raw
from pipeline.assets.validation import events_validated
from pipeline.assets.transformation import events_trusted, matches_trusted
from pipeline.jobs import lakehouse_job, ingestion_job

all_assets = [
    competitions_raw,
    matches_raw,
    events_raw,
    events_validated,
    events_trusted,
    matches_trusted,
]

defs = dg.Definitions(
    assets=all_assets,
    jobs=[lakehouse_job, ingestion_job],
    resources={
        # dg.EnvVar reads the env variable at runtime (not import time),
        # so Docker env vars are picked up correctly.
        "minio": MinIOResource(
            endpoint=dg.EnvVar("MINIO_ENDPOINT"),
            access_key=dg.EnvVar("MINIO_ACCESS_KEY"),
            secret_key=dg.EnvVar("MINIO_SECRET_KEY"),
        ),
        # DuckDB runs in-memory per run; persistence lives in MinIO Parquet files.
        "duckdb": DuckDBResource(database=":memory:"),
    },
    schedules=[
        dg.ScheduleDefinition(
            name="weekly_ingest",
            cron_schedule="0 6 * * 1",  # Every Monday at 06:00 UTC
            target=dg.AssetSelection.groups("ingestion"),
            description="Weekly refresh of raw StatsBomb data",
        )
    ],
)
