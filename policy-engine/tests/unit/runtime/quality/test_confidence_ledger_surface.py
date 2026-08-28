"""Red-first semantic boundary tests for the DS17 ledger projection surface.

Each witness invokes the planned C01 owner inside its test body. It therefore
remains a collection-safe red today, while an empty or marker-only owner still
fails once the module path exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

import pytest

_OVER_SPEND_ALLOWSET = frozenset(
    {
        "semantic_forged_spend_row",
        "semantic_total_spend_drift",
        "semantic_budget_status_drift",
        "semantic_deterministic_spend_nonzero",
        "deterministic_real_run_spend_nonzero",
    }
)


def _surface_module():
    """Load the planned C01 owner only while executing a C00 red witness."""
    return import_module("polisyos.runtime.quality.confidence_ledger_surface")


def _projection_module():
    """Load the C02 owner of source-blocked over-spend semantics on execution."""
    return import_module(
        "polisyos.runtime.http.services.confidence_ledger_risk_spend_projection"
    )


def _dump(value: object) -> dict[str, object]:
    """Require a strict DTO projection rather than a caller-authored dictionary."""
    model_dump = value.model_dump  # type: ignore[attr-defined]
    return model_dump(mode="json")


def _n11_inputs():
    """Load the typed N11 ledger and its canonical registry; never a raw row."""
    from polisyos.runtime.quality.confidence_ledger import (
        ConfidenceLedgerRegistry,
        ConfidenceLedgerSemanticReceiptProjection,
    )
    from tools.quality.validation.check_layer3_gy_confidence_ledger import (
        FrozenConfidenceLedgerContract,
    )

    contract = FrozenConfidenceLedgerContract.model_validate_json(
        Path("architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json").read_text()
    )
    projection = contract.registry_projection
    registry = ConfidenceLedgerRegistry(
        schema_version=projection.registry_schema_version,
        policy=projection.policy,
        schedule_profiles=projection.schedule_profiles,
        obligation_pools=projection.obligation_pools,
        proof_profiles=projection.proof_profiles,
        instruments=projection.instruments,
        certificate_class_routes=projection.certificate_class_routes,
    )
    semantic_ledger = ConfidenceLedgerSemanticReceiptProjection.model_validate(
        contract.real_ledger_projection.model_dump(mode="json")
    )
    return registry, semantic_ledger


def _stale_over_spend_ledger(semantic_ledger):
    """Construct a typed but stale mutation that C02 source admission must reject."""
    checks = list(semantic_ledger.checks)
    mutated_check = type(checks[0]).model_validate(
        {
            **checks[0].model_dump(mode="json"),
            "spend": {"numerator": 2, "denominator": 100},
        }
    )
    checks[0] = mutated_check
    return type(semantic_ledger).model_validate(
        {
            **semantic_ledger.model_dump(mode="json"),
            "checks": tuple(checks),
            "total_spend": {"numerator": 1, "denominator": 50},
            "total_spend_decimal": "0.02",
            "within_budget": True,
        }
    )


@dataclass(frozen=True)
class _CoherentOverSpendOwnerSourceAdapter:
    """C02 test-only owner adapter for a scratch artifact with all bindings rebuilt."""

    frozen_semantic_ledger: object
    check_id: str
    spend_numerator: int
    spend_denominator: int
    keep_display_markers: bool = True


def test_ds17_reason_algebra_matches_every_emitter() -> None:
    """Reject a missing or cross-slot reason while reconciling seven C01 emitters."""
    surface = _surface_module()
    algebra = surface.derive_ds17_reason_algebra()
    rows = _dump(algebra)["rows"]
    assert {(row["slot"], row["value"]) for row in rows} == {
        ("coverage_assessment", "known_incomplete"),
        ("coverage_assessment", "open_world_unresolved"),
        ("instrument_blocker", "coverage_argument_missing"),
        ("instrument_blocker", "non_anytime_valid"),
        ("instrument_blocker", "owner_theorem_unavailable"),
        ("instrument_blocker", "other_runtime_refusal"),
        ("appointment_posture", "institutional_authority_unappointed"),
    }
    with pytest.raises((TypeError, ValueError), match=r"slot|reason|DS17"):
        surface.validate_ds17_reason_algebra(
            rows=tuple(
                row
                for row in rows
                if row["value"] != "institutional_authority_unappointed"
            )
        )


def test_ds17_over_spend_allowset_matches_every_owner_diagnostic() -> None:
    """Reject a partial diagnostic set rather than normalizing it into an allowset."""
    projection = _projection_module()
    derived = projection.derive_over_spend_allowset()
    assert set(derived) == _OVER_SPEND_ALLOWSET
    with pytest.raises((TypeError, ValueError), match=r"allowset|diagnostic|DS17"):
        projection.validate_over_spend_allowset(
            derived_codes=tuple(
                code
                for code in derived
                if code != "deterministic_real_run_spend_nonzero"
            )
        )


def test_over_spend_recomputes_blocker_when_display_markers_stay_constant() -> None:
    """Select over-spend only from coherent worker evidence; reject stale bindings."""
    projection = _projection_module()
    registry, semantic_ledger = _n11_inputs()
    stale_ledger = _stale_over_spend_ledger(semantic_ledger)
    worker_receipt = projection.build_content_bound_worker_receipt(
        registry=registry,
        semantic_ledger=stale_ledger,
    )
    with pytest.raises((TypeError, ValueError), match=r"source|hash|binding|DS17"):
        projection.classify_content_bound_over_spend(
            registry=registry,
            semantic_ledger=stale_ledger,
            worker_receipt=worker_receipt,
        )

    source_adapter = _CoherentOverSpendOwnerSourceAdapter(
        frozen_semantic_ledger=semantic_ledger,
        check_id=semantic_ledger.checks[0].request_key,
        spend_numerator=2,
        spend_denominator=100,
    )
    blocked = _dump(
        projection.classify_content_bound_over_spend(
            registry=registry,
            owner_source_adapter=source_adapter,
        )
    )
    assert blocked["status"] == "source_blocked"
    assert blocked["reason"] == "over_spend"
    assert blocked["recomputed_total_spend"] == {"numerator": 1, "denominator": 50}


def test_bayesian_interval_without_coverage_never_enters_positive_register() -> None:
    """Map caller-eligible Bayesian input to a coverage blocker, never a certificate."""
    surface = _surface_module()
    registry, semantic_ledger = _n11_inputs()
    projection = _dump(
        surface.project_confidence_ledger_risk_spend(
            registry=registry,
            semantic_ledger=semantic_ledger,
            caller_eligibility_by_instrument={"bayesian_credible_interval": True},
        )
    )
    assert projection["positive_register"]["entries"] == []
    assert projection["instrument_blockers"] == ["coverage_argument_missing"]


def test_valid_zero_positive_register_is_not_missing_or_loading() -> None:
    """Emit the governed empty register rather than a missing/loading sentinel."""
    surface = _surface_module()
    registry, semantic_ledger = _n11_inputs()
    projection = _dump(
        surface.project_confidence_ledger_risk_spend(
            registry=registry,
            semantic_ledger=semantic_ledger,
        )
    )
    assert projection["positive_register"] == {
        "entries": [],
        "population_state": "valid_zero",
        "authority_posture": "institutional_authority_unappointed",
    }
