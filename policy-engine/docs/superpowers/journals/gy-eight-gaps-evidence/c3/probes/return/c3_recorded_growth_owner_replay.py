"""Actual uncached recorded owner over every complete canonical-basis period."""
from __future__ import annotations
import hashlib
import json
import math
from collections import defaultdict
from datetime import date, datetime
from fractions import Fraction
from pathlib import Path


def main():
    import duckdb
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.dataset as ds
    from polisyos.runtime.quality import data_forge_binding as owner

    baseline = owner.RecordedPanelRecipe()
    source, source_hash, source_size, manifest_hash = owner._validated_recorded_source(None)
    source_owner_hash = hashlib.sha256(Path(owner.__file__).read_bytes()).hexdigest()
    groups = defaultdict(list)
    nulls = 0
    for batch in ds.dataset(source.parquet_path, format="parquet").scanner(
        columns=["entity_id", "period_start", "observed_value"],
        filter=(ds.field("family") == baseline.family) & (ds.field("metric_id") == baseline.metric_id),
        batch_size=65536, use_threads=False,
    ).to_batches():
        selected = batch.filter(pc.is_in(pc.cast(batch.column("entity_id"), pa.string()), value_set=pa.array(baseline.entity_ids)))
        columns = [pc.cast(selected.column("entity_id"), pa.string()).to_pylist(), selected.column("period_start").to_pylist(), pc.cast(selected.column("observed_value"), pa.float64()).to_pylist()]
        for entity, period, value in zip(*columns, strict=True):
            if isinstance(period, datetime): period = period.date()
            elif isinstance(period, str): period = date.fromisoformat(period[:10])
            if not isinstance(period, date): raise ValueError((entity, period, "unreadable_period"))
            if value is None: nulls += 1; continue
            if not math.isfinite(value): raise ValueError((entity, str(period), "nonfinite_value"))
            groups[(entity, str(period))].append(value)
    with duckdb.connect(database=":memory:") as connection:
        counted = connection.execute("""SELECT CAST(entity_id AS VARCHAR), CAST(period_start AS VARCHAR), COUNT(*)
            FROM read_parquet(?) WHERE family=? AND metric_id=? AND observed_value IS NOT NULL
            AND CAST(entity_id AS VARCHAR) IN (SELECT UNNEST(?)) GROUP BY1,2""".replace("BY1", "BY 1"),
            [str(source.parquet_path), baseline.family, baseline.metric_id, list(baseline.entity_ids)]).fetchall()
    count_map = {(str(e), str(p)[:10]): n for e,p,n in counted}
    assert count_map == {key: len(values) for key,values in groups.items()}, "full_raw_identity_or_count_difference"
    complete = set.intersection(*({p for e,p in groups if e == entity} for entity in baseline.entity_ids))
    complete = sorted(p for p in complete if p >= str(baseline.period_start))
    recipe = owner.RecordedPanelRecipe.model_validate({**baseline.model_dump(), "period_end": complete[-1], "period_count": len(complete)})
    args = (str(source.parquet_path), source_hash, manifest_hash, recipe.model_dump_json())
    first = owner._extract_recorded_panel_rows.__wrapped__(*args)
    second = owner._extract_recorded_panel_rows.__wrapped__(*args)
    first_map = {(e,p):v for e,p,v in first}
    second_map = {(e,p):v for e,p,v in second}
    expected = {}
    exact_strings = {}
    for key, values in groups.items():
        if key[1] not in complete: continue
        exact = sum((Fraction.from_float(v) for v in values), Fraction(0))
        rounded = round(exact, 6)
        expected[key] = float(rounded)
        exact_strings[key] = str(rounded)
    expected_ids = set(expected)
    identity_delta = {
        "first_missing": sorted(expected_ids-first_map.keys()), "first_extra": sorted(first_map.keys()-expected_ids),
        "second_missing": sorted(expected_ids-second_map.keys()), "second_extra": sorted(second_map.keys()-expected_ids),
    }
    repeated_delta = [{"entity_id":e,"period":p,"first":first_map[(e,p)],"second":second_map[(e,p)],"exact_final_round6":exact_strings[(e,p)],"raw_row_count":len(groups[(e,p)])} for e,p in sorted(first_map.keys()&second_map.keys()) if first_map[(e,p)] != second_map[(e,p)]]
    arithmetic_delta = [{"entity_id":e,"period":p,"actual":first_map[(e,p)],"exact_final_round6":exact_strings[(e,p)],"expected_float":expected[(e,p)],"raw_row_count":len(groups[(e,p)])} for e,p in sorted(expected_ids & first_map.keys()) if first_map[(e,p)] != expected[(e,p)]]
    digest = lambda rows: hashlib.sha256(json.dumps(rows, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    raw_after = owner._recorded_file_sha256(source.parquet_path)
    manifest_after = hashlib.sha256(source.manifest_path.read_bytes()).hexdigest()
    assert raw_after == source_hash and manifest_after == manifest_hash
    assert hashlib.sha256(Path(owner.__file__).read_bytes()).hexdigest() == source_owner_hash
    report = {
        "source_sha256_before":source_hash,"source_sha256_after":raw_after,"source_size_bytes":source_size,
        "manifest_sha256":manifest_hash,"owner_source_sha256":source_owner_hash,"recipe":recipe.model_dump(mode="json"),
        "raw_population":{"arrow_rows":sum(map(len,groups.values())),"sql_rows":sum(count_map.values()),"arrow_groups":len(groups),"sql_groups":len(count_map),"nulls":nulls},
        "owner_population":{"expected_groups":len(expected),"first_groups":len(first),"second_groups":len(second),"complete_periods":complete},
        "identity_delta":identity_delta,"first_rows":first,"first_sha256":digest(first),"second_sha256":digest(second),
        "repeated_value_delta":repeated_delta,"first_vs_exact_value_delta":arithmetic_delta,
        "scope":"Actual uncached extraction calls and complete raw source identities; no producer code change, no tolerance or cache."}
    print(json.dumps(report, indent=2, allow_nan=False), flush=True)
    assert not any(identity_delta.values()), "owner_identity_population_changed"
    assert len(first)==len(second)==len(expected), "duplicate_or_missing_owner_member"
    assert not repeated_delta, "unchanged_source_actual_owner_round6_not_reproducible"
    assert not arithmetic_delta, "actual_owner_differs_from_exact_binary64_sum_final_round6"

if __name__ == "__main__": main()
