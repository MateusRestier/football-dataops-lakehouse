"""
Validation layer — runs Great Expectations checks on raw event data before
promoting it to the trusted layer.

Expectations:
- event_id must not be null (primary key integrity)
- period must not be null (required game context)
- loc_x must be in [0, 120] for events that have a location (mostly=0.99
  because ~5% of events are administrative with no location)
- loc_y must be in [0, 80] (same reasoning)

If validation fails, this asset raises Failure, stopping the pipeline before
any data reaches the trusted bucket.
"""

import pandas as pd
import dagster as dg
import great_expectations as gx

from pipeline.resources import MinIOResource
from pipeline.assets.ingestion import (
    RAW_BUCKET,
    TARGET_COMPETITION_ID,
    TARGET_SEASON_ID,
    events_raw,
)

# Number of matches to validate as a representative sample
VALIDATION_SAMPLE_SIZE = 5


def _flatten_events(events: list[dict]) -> list[dict]:
    """Extract key scalar fields from a list of StatsBomb event dicts."""
    rows = []
    for ev in events:
        loc = ev.get("location")
        rows.append(
            {
                "event_id": ev.get("id"),
                "event_type": (ev.get("type") or {}).get("name"),
                "period": ev.get("period"),
                "minute": ev.get("minute"),
                "loc_x": loc[0] if loc else None,
                "loc_y": loc[1] if loc else None,
                "player_id": (ev.get("player") or {}).get("id"),
            }
        )
    return rows


def _run_gx_validation(df: pd.DataFrame, context: dg.AssetExecutionContext) -> None:
    """
    Runs a Great Expectations 1.x validation against a pandas DataFrame.
    Uses an ephemeral (in-memory) context — no config files needed.
    Raises dagster.Failure if any expectation fails.
    """
    gx_ctx = gx.get_context(mode="ephemeral")

    # 1. Register the DataFrame as a data source
    data_source = gx_ctx.data_sources.add_pandas("statsbomb_events")
    data_asset = data_source.add_dataframe_asset(name="events_df")
    batch_definition = data_asset.add_batch_definition_whole_dataframe("full_batch")

    # 2. Define the expectation suite
    suite = gx_ctx.suites.add(gx.ExpectationSuite(name="events_suite"))

    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="event_id")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="period")
    )
    # ~5% of StatsBomb events are administrative (half starts, subs, etc.) and
    # have no location — mostly=0.99 accommodates that without false failures.
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="loc_x", min_value=0.0, max_value=120.0, mostly=0.99
        )
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="loc_y", min_value=0.0, max_value=80.0, mostly=0.99
        )
    )

    # 3. Wire suite + batch into a validation definition and run
    vd = gx_ctx.validation_definitions.add(
        gx.ValidationDefinition(
            name="events_validation",
            data=batch_definition,
            suite=suite,
        )
    )

    result = vd.run(batch_parameters={"dataframe": df})

    context.log.info(f"GX validation success={result.success}")

    if not result.success:
        raise dg.Failure(
            description="Great Expectations validation FAILED — pipeline halted.",
            metadata={"gx_result": dg.MetadataValue.text(str(result))},
        )


@dg.asset(
    key_prefix=["validated"],
    group_name="validation",
    deps=[events_raw],
    description=(
        "Validates event data using Great Expectations (coordinate bounds, "
        "non-null keys). Fails fast if checks do not pass."
    ),
)
def events_validated(
    context: dg.AssetExecutionContext,
    minio: MinIOResource,
) -> dg.Output[None]:
    # Resolve match IDs from the stored match list
    matches_key = f"statsbomb/matches/{TARGET_COMPETITION_ID}/{TARGET_SEASON_ID}.json"
    matches = minio.get_json(RAW_BUCKET, matches_key)
    sample_ids = [m["match_id"] for m in matches[:VALIDATION_SAMPLE_SIZE]]

    context.log.info(
        f"Validating a sample of {len(sample_ids)} matches "
        f"(out of {len(matches)} total)"
    )

    all_events: list[dict] = []
    for match_id in sample_ids:
        raw = minio.get_json(RAW_BUCKET, f"statsbomb/events/{match_id}.json")
        all_events.extend(_flatten_events(raw))

    df = pd.DataFrame(all_events)
    context.log.info(f"Loaded {len(df)} events for validation")

    _run_gx_validation(df, context)

    return dg.Output(
        value=None,
        metadata={
            "rows_validated": dg.MetadataValue.int(len(df)),
            "matches_sampled": dg.MetadataValue.int(len(sample_ids)),
        },
    )
