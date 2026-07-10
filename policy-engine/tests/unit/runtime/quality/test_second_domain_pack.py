"""Focused behavioral checks for the GY-N10a second-domain substrate pack."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from tools.quality.validation import check_layer3_gy_second_domain_pack as second_domain_pack

REPO_ROOT = Path(__file__).resolve().parents[4]


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
    receipt = attempt["receipt"]

    assert attempt["receipt_count"] == 1
    assert attempt["pack_entry_eligible"] is False
    assert attempt["owner_rederive_status"] == "pass"
    assert len(receipt["journal_entries"]) == 1
    assert receipt["journal_entries"][0]["status"] == "journaled"
    assert receipt["owner_artifacts"][0]["payload"]["raw_owner_response_hash"].startswith(
        "sha256:"
    )


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
