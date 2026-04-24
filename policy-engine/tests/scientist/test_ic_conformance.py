from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.ic_verification import (
    ICImplementationConformanceRequest,
    IncentiveCompatibilityCertificate,
)
from polisyos.ir.governance.mechanism_semantics import (
    Envelope1DPointSpec,
    Envelope1DSemanticsSpec,
    FiniteOutcomeRuleEntry,
    FiniteOutcomeSpec,
    FiniteValueTableEntry,
    MechanismSemanticFragment,
    MechanismSemanticsSpec,
    MechanismUtilityModelKind,
    MechanismUtilityModelSpec,
)
from polisyos.scientist.verification.ic import (
    load_ic_conformance_report,
    promote_ic_certificate_to_runtime,
    verify_ic_implementation_conformance,
)


def _persist_semantics(store: FileSystemCAS, semantics: MechanismSemanticsSpec) -> ArtifactRef:
    artifact = store.put_json(
        semantics.model_dump(mode="json"),
        PutOptions(
            kind="ir.mechanism_semantics",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.governance.mechanism_semantics.MechanismSemanticsSpec",
                version=str(semantics.schema_version),
            ),
        ),
    )
    return ArtifactRef.model_validate(artifact.model_dump(mode="json"))


def test_verify_ic_implementation_conformance_accepts_matching_envelope_allocations(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    authored_ref = _persist_semantics(
        store,
        MechanismSemanticsSpec(
            semantics_id="authored_envelope",
            fragment=MechanismSemanticFragment.ENVELOPE_1D,
            envelope_1d=Envelope1DSemanticsSpec(
                player_id="buyer",
                points=[
                    Envelope1DPointSpec(type_label="low", type_value="1", allocation="0"),
                    Envelope1DPointSpec(type_label="high", type_value="3", allocation="1"),
                ],
            ),
        ),
    )
    implementation_ref = _persist_semantics(
        store,
        MechanismSemanticsSpec(
            semantics_id="impl_envelope",
            fragment=MechanismSemanticFragment.ENVELOPE_1D,
            envelope_1d=Envelope1DSemanticsSpec(
                player_id="buyer",
                points=[
                    Envelope1DPointSpec(
                        type_label="low", type_value="1", allocation="0", payment="0"
                    ),
                    Envelope1DPointSpec(
                        type_label="high", type_value="3", allocation="1", payment="1"
                    ),
                ],
            ),
        ),
    )

    result = verify_ic_implementation_conformance(
        store,
        ICImplementationConformanceRequest(
            authored_semantics_ref=authored_ref,
            implementation_semantics_ref=implementation_ref,
        ),
    )

    report = load_ic_conformance_report(store, result.report_ref)

    assert result.ok is True
    assert report.verdict == "conformant"
    assert "payment_rule_not_compared" in report.notes


def test_verify_ic_implementation_conformance_reports_finite_mismatch(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    authored_ref = _persist_semantics(
        store,
        MechanismSemanticsSpec(
            semantics_id="authored_finite",
            finite_outcomes=[
                FiniteOutcomeSpec(outcome_id="lose"),
                FiniteOutcomeSpec(outcome_id="win"),
            ],
            allocation_rule=[
                FiniteOutcomeRuleEntry(report_profile={"buyer": "low"}, outcome_id="lose"),
                FiniteOutcomeRuleEntry(
                    report_profile={"buyer": "high"},
                    outcome_id="win",
                    payments_by_player={"buyer": "5"},
                ),
            ],
            utility_model=MechanismUtilityModelSpec(
                kind=MechanismUtilityModelKind.QUASI_LINEAR_SCALAR,
                value_table=[
                    FiniteValueTableEntry(
                        player_id="buyer",
                        type_label="low",
                        outcome_values={"lose": "0", "win": "1"},
                    ),
                    FiniteValueTableEntry(
                        player_id="buyer",
                        type_label="high",
                        outcome_values={"lose": "0", "win": "10"},
                    ),
                ],
            ),
        ),
    )
    implementation_ref = _persist_semantics(
        store,
        MechanismSemanticsSpec(
            semantics_id="impl_finite",
            finite_outcomes=[
                FiniteOutcomeSpec(outcome_id="lose"),
                FiniteOutcomeSpec(outcome_id="win"),
            ],
            allocation_rule=[
                FiniteOutcomeRuleEntry(report_profile={"buyer": "low"}, outcome_id="lose"),
                FiniteOutcomeRuleEntry(
                    report_profile={"buyer": "high"},
                    outcome_id="win",
                    payments_by_player={"buyer": "6"},
                ),
            ],
            utility_model=MechanismUtilityModelSpec(
                kind=MechanismUtilityModelKind.QUASI_LINEAR_SCALAR,
                value_table=[
                    FiniteValueTableEntry(
                        player_id="buyer",
                        type_label="low",
                        outcome_values={"lose": "0", "win": "1"},
                    ),
                    FiniteValueTableEntry(
                        player_id="buyer",
                        type_label="high",
                        outcome_values={"lose": "0", "win": "10"},
                    ),
                ],
            ),
        ),
    )

    result = verify_ic_implementation_conformance(
        store,
        ICImplementationConformanceRequest(
            authored_semantics_ref=authored_ref,
            implementation_semantics_ref=implementation_ref,
        ),
    )

    report = load_ic_conformance_report(store, result.report_ref)

    assert result.ok is False
    assert report.verdict == "mismatch"
    assert report.mismatch_witness["kind"] == "allocation_mismatch"


def test_promote_ic_certificate_to_runtime_attaches_conformance_ref() -> None:
    certificate = IncentiveCompatibilityCertificate(
        property="dominant_strategy_ic",
        backend="finite_exact",
        input_digest="sha256:test",
        arithmetic="rational_string",
        witness={"kind": "zero_regret_exhaustive"},
    )
    promoted = promote_ic_certificate_to_runtime(
        certificate,
        ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            kind="scientist.ic_conformance_report",
            media_type="application/json",
        ),
    )

    assert certificate.scope == "semantic"
    assert promoted.scope == "runtime"
    assert promoted.implementation_conformance_ref is not None
