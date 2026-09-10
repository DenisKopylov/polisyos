"""Reconcile the complete recorded entity/period identity set for a novel binding."""
import json
import sys
import time
_started = time.monotonic()
print("growth_census_start", file=sys.stderr, flush=True)
import duckdb
from polisyos.runtime.quality.data_forge_binding import _recorded_panel_bundle_dir, RecordedPanelRecipe


def main():
    path = _recorded_panel_bundle_dir() / "observation_panel_monthly.parquet"
    recipe = RecordedPanelRecipe()
    print(f"owner_imported elapsed={time.monotonic()-_started:.3f}", file=sys.stderr, flush=True)
    with duckdb.connect(database=":memory:") as con:
        rows = con.execute("SELECT CAST(entity_id AS VARCHAR), CAST(period_start AS DATE), COUNT(*) FROM read_parquet(?) WHERE family = ? AND metric_id = ? AND observed_value IS NOT NULL GROUP BY 1, 2", [str(path), recipe.family, recipe.metric_id]).fetchall()
        primary = {(entity, period) for entity, period, count in rows}
        raw_count = sum(count for entity, period, count in rows)
        print(f"primary_enumerated elapsed={time.monotonic()-_started:.3f}", file=sys.stderr, flush=True)
        independent = set(con.execute("SELECT DISTINCT CAST(entity_id AS VARCHAR), CAST(period_start AS DATE) FROM read_parquet(?) WHERE family = ? AND metric_id = ? AND observed_value IS NOT NULL", [str(path), recipe.family, recipe.metric_id]).fetchall())
        independent_raw_count = con.execute("SELECT COUNT(*) FROM read_parquet(?) WHERE family = ? AND metric_id = ? AND observed_value IS NOT NULL", [str(path), recipe.family, recipe.metric_id]).fetchone()[0]
        assert raw_count == independent_raw_count
    assert primary == independent
    per_entity = {entity: {period for item, period in primary if item == entity} for entity in recipe.entity_ids}
    complete = set.intersection(*per_entity.values())
    independent_complete = {period for _, period in independent if all((entity, period) in independent for entity in recipe.entity_ids)}
    assert complete == independent_complete
    next_periods = sorted(period for period in complete if period > recipe.period_end)
    assert next_periods
    print(json.dumps({
        "source": str(path), "predicate": "family/metric equal default recipe, observed_value non-null",
        "raw_row_denominator": raw_count, "independent_raw_row_denominator": independent_raw_count, "entity_period_identity_denominator": len(primary),
        "independent_entity_period_identity_denominator": len(independent),
        "default_entity_ids": recipe.entity_ids,
        "complete_periods": [str(p) for p in sorted(complete)],
        "independent_complete_period_count": len(independent_complete),
        "new_period": str(next_periods[0]),
        "recipe": recipe.model_copy(update={"period_end": next_periods[0], "period_count": recipe.period_count + 1}).model_dump(mode="json"),
    }, indent=2, sort_keys=True))

if __name__ == "__main__": main()
