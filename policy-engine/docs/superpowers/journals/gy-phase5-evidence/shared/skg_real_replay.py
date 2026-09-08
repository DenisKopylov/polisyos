"""Run retained production source through the real N8-request/N7-refusal bridge.

The request/world fixture is the exact avg_income owner test's current request;
it supplies no empirical treatment assignment or relation-calibration authority.
"""
import hashlib
import json
import time
from pathlib import Path

from polisyos.core import artifacts
from polisyos.data_forge.read_api import academic
from polisyos.runtime.quality import acquisition_planner as acquisition
from polisyos.runtime.quality.generation_cycle import GenerationCycleController
from polisyos.runtime.quality.production_grounding_calibration import (
    ProductionCG2CalibrationSource, SourceGroundingRequest,
)
from polisyos.runtime.quality.substrate_registry import DEFAULT_L2_SCHOLAR_KG_PATH
from tests.unit.runtime.quality.test_value_gate import (
    _avg_income_candidate, _avg_income_problem, _world_record,
)


def main():
    started = time.monotonic()
    scratch = Path("_build/gy_phase5_shared/pa1_n7_real")
    source = academic.SourceSnapshot(
        path=DEFAULT_L2_SCHOLAR_KG_PATH,
        reference=str(DEFAULT_L2_SCHOLAR_KG_PATH.resolve()),
        sha256="583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967",
    )
    candidate, problem, world_record = _avg_income_candidate(), _avg_income_problem(), _world_record()
    gap = acquisition.value_input_world_knowledge_requirement_gap(
        claim_ref=f"value-claim:{candidate.candidate_id}"
    )
    request = {"cycle_index": 0, "requirement_gap": gap.model_dump(mode="json")}
    controller = GenerationCycleController(repo_root=scratch)
    specs = controller._n7_data_requirement_specs(problem, acquisition_request=request)
    assert len(specs) == 1 and specs[0] == gap
    world = acquisition.AcquisitionWorldSnapshot(
        world_ref=world_record.content_hash,
        world_model_record_ref=world_record.world_model_record_id,
        known_slots=("avg_income",),
    )
    receipt = acquisition.run_acquisition_closed_loop(
        run_id="pa1-real-source-avg-income", acquisition_request=request,
        data_requirement_specs=specs, world_snapshot=world, design_problem=problem,
        owner_gateway=acquisition.RealAcquisitionOwnerGateway(
            repo_root=scratch, skg_source_snapshot=source
        ),
    )
    assert not acquisition.validate_acquisition_receipt(receipt)
    assert receipt.real_grounding_result_count == 0
    assert len(receipt.owner_artifacts) == 1
    response = receipt.owner_artifacts[0].payload["owner_response"]
    ref = artifacts.ArtifactRef.model_validate(response["resolution_ref"])
    owner = ProductionCG2CalibrationSource(
        source=source, store=artifacts.FileSystemCAS(scratch / ".n7-live-cas"),
        scratch=scratch / ".n7-live-cas" / "source-query-scratch",
    )
    expected_request = SourceGroundingRequest(
        requirement_ref=gap.compiled_requirement_ref, claim_ref=gap.claim_ref,
        compiled_requirement=gap.model_dump(mode="json"),
        design_problem=problem.model_dump(mode="json"), world_snapshot=world.model_dump(mode="json"),
    )
    result = owner.replay(ref=ref, request=expected_request)
    assert result.target_variable == "avg_income" and result.n8_admission == "blocked"
    receipt_bytes = json.dumps(receipt.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    receipt_path = scratch / "n7-receipt.json"
    receipt_path.write_bytes(receipt_bytes)
    population = result.source_population
    output = {
        "request_source": "test_value_gate exact avg_income candidate/problem/world fixture",
        "source_sha256": source.sha256,
        "resolution_ref": ref.model_dump(mode="json"),
        "resolution_bytes": len(owner._store.get_bytes(ref.artifact_id)),
        "request": result.request.model_dump(mode="json"),
        "request_sha256": result.request_sha256,
        "population_status": population.status,
        "row_count": population.row_count,
        "distinct_numeric_id_count": population.distinct_numeric_id_count,
        "distinct_variable_name_count": population.distinct_variable_name_count,
        "literal_target_match_count": len(population.literal_target_row_indices),
        "semantic_target_coverage": population.semantic_target_coverage,
        "projection_sha256": population.projection_sha256,
        "relation_acceptance": result.relation_acceptance.model_dump(mode="json"),
        "cg2_status": result.cg2_status,
        "cg2_owner_ledger_id": result.cg2_owner_ledger_id,
        "refusal_reasons": result.refusal_reasons,
        "receipt_status": receipt.status,
        "world_write_statuses": [row.status for row in receipt.world_write_outcomes],
        "real_grounding_result_count": receipt.real_grounding_result_count,
        "n8_admission": result.n8_admission,
        "network_calls": receipt.network_call_count,
        "receipt_path": str(receipt_path),
        "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "elapsed_seconds": time.monotonic() - started,
    }
    Path("_build/gy_phase5_shared/pa1-n7-real-replay-output.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({key: value for key, value in output.items() if key != "request"}), flush=True)


if __name__ == "__main__":
    main()
