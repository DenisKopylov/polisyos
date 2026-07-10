"""Focused behavioral checks for the GY-N10a second-domain substrate pack."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools.quality.validation import check_layer3_gy_second_domain_pack as second_domain_pack

REPO_ROOT = Path(__file__).resolve().parents[4]


def _rehash_pack_manifest(bundle: dict[str, object]) -> None:
    """Keep a pack mutation internally content-consistent for behavioral probes."""

    pack = bundle["pack"]
    bundle["pack"] = second_domain_pack._with_content_hash(
        pack,
        "manifest_content_hash",
        excluded_fields=("runtime_metrics",),
    )


def _rehash_gap_report_and_pack(bundle: dict[str, object]) -> None:
    """Keep gap and manifest hashes coherent while probing a seam witness."""

    gaps = bundle["gaps"]
    gaps["gaps"] = [
        second_domain_pack._with_content_hash(gap, "gap_content_hash")
        for gap in gaps["gaps"]
    ]
    bundle["gaps"] = second_domain_pack._with_content_hash(gaps, "gap_report_content_hash")
    bundle["pack"]["gap_report_content_hash"] = bundle["gaps"]["gap_report_content_hash"]
    _rehash_pack_manifest(bundle)


@pytest.fixture(scope="module")
def live_bundle() -> dict[str, object]:
    """Build the expensive owner-derived bundle once for this focused module."""

    return second_domain_pack.build_live_bundle(REPO_ROOT)


def test_pack_rederives_owner_facts_and_is_content_addressed(
    live_bundle: dict[str, object],
) -> None:
    """Rebuild the pack from the real DCAT/SKG/S0/N6 owners."""

    bundle = live_bundle

    assert bundle["census"]["decision"]["chosen_candidate"] == "education"
    assert bundle["pack"]["manifest_content_hash"].startswith("sha256:")
    assert not second_domain_pack.validate_bundle_payloads(bundle, REPO_ROOT)


def test_census_records_operational_query_timings(live_bundle: dict[str, object]) -> None:
    """Keep E5 query timing evidence without making the census hash time-dependent."""

    census = live_bundle["census"]
    timings = census["runtime_metrics"]["query_timings_seconds"]

    assert set(timings) == {
        "l1_candidate_aggregate",
        "l2_candidate_aggregate",
        "l2_candidate_exact_measure_names",
    }
    assert all(value >= 0.0 for value in timings.values())
    assert census["content_hash_excluded_fields"] == ["runtime_metrics"]


def test_hand_authored_entry_is_rejected(live_bundle: dict[str, object]) -> None:
    """Reject a well-shaped entry that lacks rederivable owner evidence."""

    bundle = live_bundle
    corrupted = copy.deepcopy(bundle)
    corrupted["pack"]["components"]["lever_vocabulary"]["entries"].append(
        {
            "lever_id": "hand_authored_lever",
            "instrument": "hand.authored",
            "status": "candidate_unbound",
        }
    )

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "pack_entry_not_owner_derived" in codes


def test_owner_projection_drift_is_rejected(live_bundle: dict[str, object]) -> None:
    """Reject a shape-valid entry whose copied provenance no longer binds its owner row."""

    bundle = live_bundle
    corrupted = copy.deepcopy(bundle)
    corrupted["pack"]["components"]["outcomes"]["entries"][0]["dataset_ids"] = [
        "spoofed-dataset-id"
    ]

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "pack_entry_owner_projection_drift" in codes


def test_n7_attempt_is_journal_first_but_not_pack_authority(
    live_bundle: dict[str, object],
) -> None:
    """Persist one real N7 attempt without laundering its registry projection."""

    attempt = live_bundle["pack"]["n7_acquisition"]
    receipt = live_bundle["pack"]["runtime_metrics"]["n7_acquisition"]["receipt"]

    assert attempt["receipt_count"] == 1
    assert attempt["pack_entry_eligible"] is False
    assert attempt["owner_rederive_status"] == "pass"
    assert len(receipt["journal_entries"]) == 1
    assert receipt["journal_entries"][0]["status"] == "journaled"
    assert receipt["owner_artifacts"][0]["payload"]["raw_owner_response_hash"].startswith(
        "sha256:"
    )


def test_n7_capture_time_is_operational_and_owner_evidence_is_time_stable(
    live_bundle: dict[str, object],
) -> None:
    """Keep real N7 capture time outside the content-bound owner projection."""

    pack = live_bundle["pack"]
    attempt = pack["n7_acquisition"]
    operational = pack["runtime_metrics"]["n7_acquisition"]
    first_receipt = operational["receipt"]
    second_receipt = copy.deepcopy(first_receipt)
    assert "content_hash" not in first_receipt
    second_receipt["generated_at"] = "2026-07-10T00:00:00Z"
    second_receipt["planner_report"]["generated_at"] = "2026-07-10T00:00:00Z"
    second_receipt["owner_artifacts"][0]["capture_provenance"]["captured_at"] = (
        "2026-07-10T00:00:00Z"
    )
    second_receipt["content_hash"] = ""

    first_projection = second_domain_pack._n7_owner_evidence_projection(first_receipt)
    second_projection = second_domain_pack._n7_owner_evidence_projection(second_receipt)

    assert first_projection == second_projection == attempt["receipt_content"]
    assert second_domain_pack._n7_owner_evidence_hash(first_receipt) == attempt[
        "receipt_content_hash"
    ]
    assert second_domain_pack._n7_owner_evidence_hash(first_receipt) == (
        second_domain_pack._n7_owner_evidence_hash(second_receipt)
    )
    assert "2018-2022" in json.dumps(first_projection, sort_keys=True)
    reconstructed = second_domain_pack.AcquisitionReceipt.model_validate(second_receipt)
    assert not second_domain_pack.validate_acquisition_receipt(reconstructed)

    shifted_bundle = copy.deepcopy(live_bundle)
    shifted_pack = shifted_bundle["pack"]
    shifted_operational = shifted_pack["runtime_metrics"]["n7_acquisition"]
    shifted_receipt = reconstructed.model_dump(mode="json")
    shifted_receipt.pop("content_hash")
    shifted_operational["receipt"] = shifted_receipt
    shifted_operational["receipt_generated_at"] = second_receipt["generated_at"]
    shifted_operational["planner_report_generated_at"] = second_receipt["planner_report"][
        "generated_at"
    ]
    shifted_operational["owner_capture_times"] = [
        second_receipt["owner_artifacts"][0]["capture_provenance"]["captured_at"]
    ]
    assert pack["manifest_content_hash"] == shifted_pack["manifest_content_hash"]
    assert second_domain_pack._content_bound_canonical_json(pack) == (
        second_domain_pack._content_bound_canonical_json(shifted_pack)
    )
    assert not second_domain_pack.validate_bundle_payloads(shifted_bundle, REPO_ROOT)


def test_capture_time_reentering_content_projection_is_rejected(
    live_bundle: dict[str, object],
) -> None:
    """Fail closed when a capture timestamp returns to content-bound N7 evidence."""

    corrupted = copy.deepcopy(live_bundle)
    attempt = corrupted["pack"]["n7_acquisition"]
    attempt["receipt_content"]["generated_at"] = "2026-07-10T00:00:00Z"
    attempt["receipt_content_hash"] = second_domain_pack._hash(attempt["receipt_content"])
    _rehash_pack_manifest(corrupted)

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "capture_time_content_bound" in codes


def test_source_content_hash_is_repo_relative_and_path_invariant(tmp_path: Path) -> None:
    """Preserve source identity without allowing the checkout path into the hash."""

    canonical = REPO_ROOT / "src/polisyos/runtime/quality/generation_cycle.py"
    dotted = canonical.parent / ".." / "quality" / canonical.name
    expected = second_domain_pack._source_content_hash(REPO_ROOT, canonical)

    relocated_root = tmp_path / "relocated"
    relocated = relocated_root / "src/polisyos/runtime/quality/generation_cycle.py"
    relocated.parent.mkdir(parents=True)
    relocated.write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")
    same_text_different_path = relocated_root / "other.py"
    same_text_different_path.write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")

    assert expected == second_domain_pack._source_content_hash(REPO_ROOT, dotted)
    assert expected == second_domain_pack._source_content_hash(relocated_root, relocated)
    assert expected != second_domain_pack._source_content_hash(
        relocated_root, same_text_different_path
    )


def test_all_gaps_have_resolvable_seam_witnesses(live_bundle: dict[str, object]) -> None:
    """Require a real, segment-scoped source witness for every emitted gap."""

    gap_ids = {gap["gap_id"] for gap in live_bundle["gaps"]["gaps"]}

    assert set(second_domain_pack.GAP_WITNESS_SPECS) == gap_ids
    for _gap_id, spec in second_domain_pack.GAP_WITNESS_SPECS.items():
        witness = second_domain_pack._resolve_gap_witness(REPO_ROOT, spec)
        assert witness["symbol"] == spec.symbol
        assert witness["segment_content_hash"].startswith("sha256:")
    n5 = next(gap for gap in live_bundle["gaps"]["gaps"] if gap["gap_id"] == "s0_to_n5_wmr_bridge_missing")
    assert "build_substrate_registry_from_existing_catalogs" in n5["owner_evidence"][
        "seam_witness"
    ]["observed_call_names"]


def test_missing_gap_witness_target_fails_closed_for_every_gap(
    live_bundle: dict[str, object],
) -> None:
    """Never treat an unresolved seam symbol as an empty-but-valid witness."""

    for gap_id in sorted(second_domain_pack.GAP_WITNESS_SPECS):
        corrupted = copy.deepcopy(live_bundle)
        gap = next(item for item in corrupted["gaps"]["gaps"] if item["gap_id"] == gap_id)
        gap["owner_evidence"]["seam_witness"]["symbol"] = "__gy_n10a_missing_target__"
        _rehash_gap_report_and_pack(corrupted)
        codes = {
            str(issue["code"])
            for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
        }
        assert "gap_witness_target_missing" in codes


def test_absolute_gap_witness_source_is_rejected(live_bundle: dict[str, object]) -> None:
    """Reject an absolute checkout path reintroduced into seam hash identity."""

    corrupted = copy.deepcopy(live_bundle)
    witness = corrupted["gaps"]["gaps"][0]["owner_evidence"]["seam_witness"]
    witness["source_path"] = str(REPO_ROOT / witness["source_path"])
    _rehash_gap_report_and_pack(corrupted)

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "source_hash_checkout_path_dependent" in codes


def test_gap_segment_hash_ignores_unrelated_edits_and_detects_seam_edits(tmp_path: Path) -> None:
    """Pin a seam segment, not the entire owner module, for merge stability."""

    relative = "src/polisyos/runtime/quality/generation_cycle.py"
    source = REPO_ROOT / relative
    copied_root = tmp_path / "copy"
    copied = copied_root / relative
    copied.parent.mkdir(parents=True)
    source_text = source.read_text(encoding="utf-8")
    copied.write_text(source_text, encoding="utf-8")
    spec = second_domain_pack.GAP_WITNESS_SPECS["s0_to_n5_wmr_bridge_missing"]

    original = second_domain_pack._resolve_gap_witness(copied_root, spec)
    copied.write_text(source_text + "\n# unrelated audit probe\n", encoding="utf-8")
    unrelated = second_domain_pack._resolve_gap_witness(copied_root, spec)
    copied.write_text(
        source_text.replace(
            "registry = build_substrate_registry_from_existing_catalogs(repo_root)",
            "registry = build_substrate_registry_from_existing_catalogs(repo_root)  # seam probe",
            1,
        ),
        encoding="utf-8",
    )
    seam_changed = second_domain_pack._resolve_gap_witness(copied_root, spec)

    assert original["segment_content_hash"] == unrelated["segment_content_hash"]
    assert original["segment_content_hash"] != seam_changed["segment_content_hash"]


def test_first_vertical_contamination_is_rejected(live_bundle: dict[str, object]) -> None:
    """Compute, rather than trust, the all-axis distinctness check."""

    bundle = live_bundle
    corrupted = copy.deepcopy(bundle)
    corrupted["pack"]["components"]["outcomes"]["entries"][0]["canonical_var"] = "avg_income"
    corrupted["pack"]["components"]["transport_context"]["covariates"][0][
        "canonical_var"
    ] = "state_capacity"
    corrupted["pack"]["components"]["lever_vocabulary"]["entries"][0][
        "instrument"
    ] = "policy.credit_access"

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "distinctness_outcome_overlap" in codes
    assert "distinctness_covariate_overlap" in codes
    assert "distinctness_lever_overlap" in codes


def test_crash_or_mismatch_trace_cannot_be_labeled_honest(
    live_bundle: dict[str, object],
) -> None:
    """Reject a recorded crash/mismatch that is dressed as a typed terminal."""

    bundle = live_bundle
    corrupted = copy.deepcopy(bundle)
    corrupted["cycle_trace"]["smoke_status"] = "typed_terminal_pass"
    corrupted["cycle_trace"]["generation_cycle_run"]["cycles"][0]["terminal_kind"] = "crash"

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "smoke_terminal_not_honest" in codes


def test_smoke_trace_must_bind_the_frozen_design_problem(
    live_bundle: dict[str, object],
) -> None:
    """Reject a typed trace that points at a different DesignProblem payload."""

    bundle = live_bundle
    corrupted = copy.deepcopy(bundle)
    corrupted["cycle_trace"]["generation_cycle_run"]["design_problem_ref"] = "sha256:" + "0" * 64

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "smoke_design_problem_ref_drift" in codes


def test_non_pack_diff_scope_is_rejected(live_bundle: dict[str, object]) -> None:
    """Reject a recorded change outside the declared data-only task surface."""

    bundle = live_bundle
    corrupted = copy.deepcopy(bundle)
    corrupted["pack"]["zero_engine_code"]["out_of_scope_paths"] = ["README.md"]

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "free_grow_violated_by_scope_change" in codes
