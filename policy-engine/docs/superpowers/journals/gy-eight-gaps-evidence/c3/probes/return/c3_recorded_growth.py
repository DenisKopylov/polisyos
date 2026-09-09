"""Exercise data-only period growth through real recorded and method consumers.

The measured population is the canonical recipe's entity/family/metric basis,
over every recorded period. This is not a census of unrelated entities or a
claim of guarded causal-node or institutional admission.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import traceback
from collections import defaultdict
from datetime import date, datetime
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    import duckdb
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.dataset as ds

    from polisyos.core import artifacts, canon
    from polisyos.foundry.data_plane import materialize_method_contract
    from polisyos.pdc import OperationClass
    from polisyos.runtime.quality import data_forge_binding as owner
    from polisyos.runtime.quality.workspace.foundry_consumption import FoundryMethodOutputConsumer
    from polisyos.scientist.compute import MethodBackend
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    owner_hash = hashlib.sha256(Path(owner.__file__).read_bytes()).hexdigest()
    recipe = owner.RecordedPanelRecipe()
    source, source_hash, source_size, manifest_hash = owner._validated_recorded_source(None)
    parameters = [str(source.parquet_path), recipe.family, recipe.metric_id, list(recipe.entity_ids)]
    predicate = """FROM read_parquet(?) WHERE family = ? AND metric_id = ?
        AND observed_value IS NOT NULL
        AND CAST(entity_id AS VARCHAR) IN (SELECT UNNEST(?))"""
    with duckdb.connect(database=":memory:") as connection:
        grouped = connection.execute(
            "SELECT CAST(entity_id AS VARCHAR), CAST(period_start AS DATE), COUNT(*) "
            + predicate + " GROUP BY 1,2", parameters,
        ).fetchall()
        independent_complete = {
            row[0] for row in connection.execute(
                "SELECT CAST(period_start AS DATE) " + predicate
                + " GROUP BY 1 HAVING COUNT(DISTINCT CAST(entity_id AS VARCHAR)) = ?",
                [*parameters, len(recipe.entity_ids)],
            ).fetchall()
        }
        raw_count = connection.execute("SELECT COUNT(*) " + predicate, parameters).fetchone()[0]
    raw_groups = defaultdict(list)
    null_count = 0
    for batch in ds.dataset(source.parquet_path, format="parquet").scanner(
        columns=["entity_id", "period_start", "observed_value"],
        filter=(ds.field("family") == recipe.family) & (ds.field("metric_id") == recipe.metric_id),
        batch_size=65536, use_threads=False,
    ).to_batches():
        selected = batch.filter(pc.is_in(pc.cast(batch.column("entity_id"), pa.string()), value_set=pa.array(recipe.entity_ids)))
        columns = [pc.cast(selected.column("entity_id"), pa.string()).to_pylist(), selected.column("period_start").to_pylist(), pc.cast(selected.column("observed_value"), pa.float64()).to_pylist()]
        for entity, period, value in zip(*columns, strict=True):
            if isinstance(period, datetime): period = period.date()
            elif isinstance(period, str): period = date.fromisoformat(period[:10])
            if not isinstance(period, date): raise ValueError((entity, repr(period), "unreadable_period"))
            if value is None: null_count += 1; continue
            if not math.isfinite(value): raise ValueError((entity, str(period), "nonfinite_value"))
            raw_groups[(entity, period)].append(value)
    primary = {(entity, period): count for entity, period, count in grouped}
    independent = {key: len(values) for key, values in raw_groups.items()}
    assert primary == independent, "complete grouped identity/count population differs from raw Arrow rows"
    independent_row_count = sum(independent.values())
    assert sum(primary.values()) == independent_row_count == raw_count
    assert {entity for entity, _ in primary} == set(recipe.entity_ids)
    # Exact arithmetic over every raw group, independent of the production helper.
    exact_values = {
        key: float(round(sum(map(Fraction.from_float, values), Fraction(0)), 6))
        for key, values in raw_groups.items()
    }
    complete = set.intersection(*(
        {period for entity, period in primary if entity == selected}
        for selected in recipe.entity_ids
    ))
    assert complete == independent_complete
    baseline_periods = sorted(p for p in complete if recipe.period_start <= p <= recipe.period_end)
    assert len(baseline_periods) == recipe.period_count
    new_periods = sorted(p for p in complete if p > recipe.period_end)
    if not new_periods:
        raise RuntimeError("recorded_population_has_no_additional_complete_period")
    grown_recipe = owner.RecordedPanelRecipe.model_validate({
        **recipe.model_dump(), "period_end": new_periods[0], "period_count": recipe.period_count + 1,
    })
    temp_root = Path("_build/gy-gaps/c3/recorded-growth")
    temp_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="actual-", dir=temp_root) as directory:
        store = artifacts.FileSystemCAS(Path(directory))
        receipts = []
        for name, selected_recipe in (("canonical", recipe), ("additional_recorded_period", grown_recipe)):
            binding = owner.produce_recorded_panel_method_input(
                store=store, method_fqn="causal.inference.synthetic_control@2.0.0",
                source=source, recipe=selected_recipe,
            )
            assert owner.verify_recorded_panel_method_input(
                store=store, binding_receipt_ref=binding.binding_receipt_ref,
            ) == binding
            payload = binding.contract_payload
            for entity, outcomes in zip(payload["unit_ids"], payload["outcome"], strict=True):
                expected = [exact_values[(entity, period)] for period in sorted(complete)
                            if selected_recipe.period_start <= period <= selected_recipe.period_end]
                assert outcomes == expected
            method_input = materialize_method_contract(
                contract_target=binding.contract_target, contract_payload=payload,
            )
            params = {"n_placebo_runs": 0}
            execution = MethodBackend().run(
                cas_root=store.root, method_fqn=binding.receipt.method_fqn,
                method_version=None, input_state=method_input, method_params=params, seed=17,
                input_refs={"observations": binding.observational_data_ref,
                            "recorded_input_binding": binding.binding_receipt_ref},
            )
            state = ExperimentState(
                run_id="c3-data-only-growth-" + name,
                observational_data_ref=binding.observational_data_ref,
                causal_method_fqn=binding.receipt.method_fqn, causal_method_params=params,
                params={"random_seed": 17},
                artifacts_index={"causal_method_result_ref": execution.exec_artifacts.result_ref,
                                 "causal_method_evidence_ref": execution.exec_artifacts.evidence_ref},
            )
            readback = {}
            for role, ref in (("result", execution.exec_artifacts.result_ref), ("evidence", execution.exec_artifacts.evidence_ref)):
                raw = store.get_bytes(ref.artifact_id)
                assert hashlib.sha256(raw).hexdigest() == str(ref.artifact_id).removeprefix("sha256:")
                readback[role] = {
                    "ref": ref.model_dump(mode="json"), "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    "manifest": store.get_manifest(ref.artifact_id).model_dump(mode="json"),
                    "payload": canon.from_canonical_bytes(raw),
                }
            case = {"case": name, "recipe": selected_recipe.model_dump(mode="json"),
                    "binding": binding.receipt.model_dump(mode="json"), "method_readback": readback}
            consumer = FoundryMethodOutputConsumer(store=store)
            try:
                consumed = consumer.consume_from_state(
                    workspace_id="ws-c3-data-only-growth-" + name,
                    operation_invocation_id="invoke-c3-data-only-growth-" + name,
                    operation_class=OperationClass.ESTIMATE, state=state,
                    measurement_root_ref=binding.observational_data_ref,
                    binding_receipt_ref=binding.binding_receipt_ref,
                )
                persisted = consumer.persist_consumption(store=store, consumption=consumed)
                case.update({"consumer_status": "accepted", "consumption": consumed.model_dump(mode="json"),
                             "persisted": persisted.model_dump(mode="json")})
            except Exception as exc:
                case.update({"consumer_status": "refused", "error_type": type(exc).__name__,
                             "error": str(exc), "traceback": traceback.format_exc()})
            receipts.append(case)
        assert receipts[0]["binding"]["observational_data_ref"] != receipts[1]["binding"]["observational_data_ref"]
        assert hashlib.sha256(Path(owner.__file__).read_bytes()).hexdigest() == owner_hash
        assert owner._recorded_file_sha256(source.parquet_path) == source_hash
        assert hashlib.sha256(source.manifest_path.read_bytes()).hexdigest() == manifest_hash
        print(json.dumps({
            "owner_source_sha256": owner_hash,
            "source": str(source.parquet_path), "source_sha256": source_hash,
            "source_size_bytes": source_size, "manifest_sha256": manifest_hash,
            "population": {"entity_ids": recipe.entity_ids, "family": recipe.family,
                           "metric_id": recipe.metric_id, "periods": "all recorded periods",
                           "null_values": "excluded by the unchanged recorded recipe owner"},
            "raw_row_denominator": raw_count, "independent_raw_row_denominator": independent_row_count,
            "entity_period_denominator": len(primary), "independent_entity_period_denominator": len(independent),
            "complete_periods": sorted(map(str, complete)),
            "independent_complete_periods": sorted(map(str, independent_complete)),
            "identity_delta": {"missing": [], "extra": []}, "null_count": null_count, "arithmetic": "Every raw binary64 accumulated as exact Fraction, then one half-even round6 and float conversion; no tolerance.", "cases": receipts,
            "authority_limit": "Recorded-value custody and direct method replay only; no guarded-node, institutional or accuracy admission.",
        }, indent=2), flush=True)
        if "--aggregation-removal" in sys.argv:
            from _build.gy_gaps.c3_recorded_aggregation_removal import main as removal_main
            removal_status = removal_main()
            assert removal_status != 0, "aggregation_removal_did_not_turn_real_owner_test_red"
        assert all(case["consumer_status"] == "accepted" for case in receipts), "actual_recorded_growth_consumer_refused"


if __name__ == "__main__":
    main()
