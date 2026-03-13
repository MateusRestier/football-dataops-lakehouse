import dagster as dg

# Full end-to-end job: ingest → validate → transform
lakehouse_job = dg.define_asset_job(
    name="lakehouse_full_pipeline",
    selection=dg.AssetSelection.groups("ingestion", "validation", "transformation"),
    description="Full medallion pipeline: raw ingestion → GX validation → Parquet transform",
)

# Ingestion-only job (useful for scheduled raw refreshes without re-running transforms)
ingestion_job = dg.define_asset_job(
    name="ingestion_only",
    selection=dg.AssetSelection.groups("ingestion"),
    description="Ingest raw StatsBomb JSON to MinIO raw-data bucket",
)
