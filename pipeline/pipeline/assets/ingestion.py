"""
Raw layer assets — fetches StatsBomb Open Data JSON files and stores them in
the MinIO raw-data bucket, preserving the original format without any
transformation.

Default scope: La Liga 2020/21 (competition_id=11, season_id=90).
~380 matches, ~1M events. Change the constants below to ingest a different
competition.
"""

import requests
import dagster as dg

from pipeline.resources import MinIOResource

STATSBOMB_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
RAW_BUCKET = "raw-data"

# Default competition scope — override in Dagster UI via run config
TARGET_COMPETITION_ID = 11  # La Liga
TARGET_SEASON_ID = 90       # 2020/21


def _fetch(path: str) -> list | dict:
    url = f"{STATSBOMB_BASE}/{path}"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


@dg.asset(
    key_prefix=["raw"],
    group_name="ingestion",
    description="Fetches the StatsBomb competitions catalog and stores raw JSON in MinIO.",
)
def competitions_raw(
    context: dg.AssetExecutionContext,
    minio: MinIOResource,
) -> dg.Output[None]:
    minio.ensure_bucket(RAW_BUCKET)
    data = _fetch("competitions.json")

    key = "statsbomb/competitions.json"
    minio.put_json(RAW_BUCKET, key, data)

    context.log.info(f"Stored {len(data)} competitions → s3://{RAW_BUCKET}/{key}")
    return dg.Output(
        value=None,
        metadata={
            "competition_count": dg.MetadataValue.int(len(data)),
            "s3_key": dg.MetadataValue.text(key),
        },
    )


@dg.asset(
    key_prefix=["raw"],
    group_name="ingestion",
    deps=[competitions_raw],
    description="Fetches match list for the target competition/season.",
)
def matches_raw(
    context: dg.AssetExecutionContext,
    minio: MinIOResource,
) -> dg.Output[None]:
    path = f"matches/{TARGET_COMPETITION_ID}/{TARGET_SEASON_ID}.json"
    data = _fetch(path)

    key = f"statsbomb/matches/{TARGET_COMPETITION_ID}/{TARGET_SEASON_ID}.json"
    minio.put_json(RAW_BUCKET, key, data)

    context.log.info(
        f"Stored {len(data)} matches → s3://{RAW_BUCKET}/{key} "
        f"(competition={TARGET_COMPETITION_ID}, season={TARGET_SEASON_ID})"
    )
    return dg.Output(
        value=None,
        metadata={
            "match_count": dg.MetadataValue.int(len(data)),
            "competition_id": dg.MetadataValue.int(TARGET_COMPETITION_ID),
            "season_id": dg.MetadataValue.int(TARGET_SEASON_ID),
            "s3_key": dg.MetadataValue.text(key),
        },
    )


@dg.asset(
    key_prefix=["raw"],
    group_name="ingestion",
    deps=[matches_raw],
    description=(
        "Fetches per-match event streams from StatsBomb and stores one JSON "
        "file per match in MinIO. Idempotent: already-uploaded files are skipped."
    ),
)
def events_raw(
    context: dg.AssetExecutionContext,
    minio: MinIOResource,
) -> dg.Output[None]:
    matches_key = f"statsbomb/matches/{TARGET_COMPETITION_ID}/{TARGET_SEASON_ID}.json"
    matches = minio.get_json(RAW_BUCKET, matches_key)
    match_ids = [m["match_id"] for m in matches]

    context.log.info(f"Fetching events for {len(match_ids)} matches…")
    ingested, skipped = 0, 0

    for match_id in match_ids:
        key = f"statsbomb/events/{match_id}.json"
        if minio.object_exists(RAW_BUCKET, key):
            skipped += 1
            continue

        events = _fetch(f"events/{match_id}.json")
        minio.put_json(RAW_BUCKET, key, events)
        ingested += 1

        if ingested % 20 == 0:
            context.log.info(f"  {ingested}/{len(match_ids) - skipped} new files uploaded")

    context.log.info(f"Done — ingested={ingested}, skipped={skipped}")
    return dg.Output(
        value=None,
        metadata={
            "ingested": dg.MetadataValue.int(ingested),
            "skipped_existing": dg.MetadataValue.int(skipped),
            "total_matches": dg.MetadataValue.int(len(match_ids)),
        },
    )
