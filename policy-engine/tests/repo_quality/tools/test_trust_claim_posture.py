"""Red-first repository-semantic tests for DS11 trust-claim posture tooling."""

from __future__ import annotations

import importlib

import pytest

from polisyos.runtime.quality.claim_registry import build_runtime_claim_registry


def _owner_api(module_name: str, name: str):
    """Load one required C01 owner API or fail with the guarded behavior."""
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        pytest.fail(f"C01 owner module is absent: {module_name}; required API: {name}")
    api = getattr(module, name, None)
    if not callable(api):
        pytest.fail(f"C01 owner module lacks required semantic API: {module_name}.{name}")
    return api


def _sources_api(name: str):
    """Return a source-compiler API from its approved C01 owner."""
    return _owner_api("tools.quality.validation.trust_claim_posture_sources", name)


def _checker_api(name: str):
    """Return a checker API from its approved C01 owner."""
    return _owner_api("tools.quality.validation.check_trust_claim_posture", name)


def _contract_api(name: str):
    """Return a DTO/calculus API from its approved C01 owner."""
    return _owner_api("polisyos.scientist.evidence.claims.posture", name)


def _valid_runtime_registry(binding_ref: str) -> dict[str, object]:
    """Build a real full-axis runtime registry binding for CC09 separation probes."""
    return build_runtime_claim_registry(
        claims=[
            {
                "claim_id": "runtime-final-claim",
                "claim_family": "recommendation",
                "major": True,
                "text": "Bind a runtime-only final claim to its complete evidence axes.",
                "scenario_requirement_refs": ["scenario.req.credit_support"],
                "data_refs": ["source.msme_panel"],
                "selected_norm_refs": ["norm.ua.credit_guarantee"],
                "rejected_norm_refs": ["norm.ua.unrelated"],
                "method_output_refs": ["foundry.did.msme_survival"],
                "portfolio_refs": ["portfolio.rec_credit_guarantee"],
                "argument_refs": ["argument.rec_credit_guarantee"],
                "warrant_refs": ["warrant.rec_credit_guarantee"],
                "rebuttal_refs": ["rebuttal.rec_credit_guarantee"],
                "counter_evidence_refs": ["counter.rec_credit_guarantee"],
                "limitation_refs": ["limitation.rec_credit_guarantee"],
                "accepted_deficit_refs": [binding_ref],
                "assumption_gate_refs": ["assumption-gate.runtime-final-claim"],
                "independence_refs": ["independence.runtime-final-claim"],
                "synthesis_refs": ["synthesis.runtime-final-claim"],
                "scholar_deficit_refs": ["scholar-deficit.runtime-final-claim"],
                "objective_tradeoff_refs": ["objective-tradeoff.runtime-final-claim"],
                "uncertainty_refs": ["uncertainty.runtime-final-claim"],
                "numerical_semantics_refs": ["num-semantics.runtime-final-claim"],
                "monitoring_refs": ["monitoring.runtime-final-claim"],
                "specification_curve_refs": ["spec-curve.runtime-final-claim"],
                "claim_ref": "sha256:" + "d" * 64,
                "runtime_event_ref": "event://runtime_claim_registry/runtime-final-claim",
            }
        ],
        run_id="ds11-cc09-probe",
    )


def test_source_partition_matches_ast_and_tokenize_file_for_file() -> None:
    """Catch a reconciliation mutation that loses a disagreement instead of surfacing it."""
    reconcile = _sources_api("reconcile_ast_and_tokenize_partitions")

    assert reconcile({"a.py": "declares_only"}, {"a.py": "consumes_only"}) == {
        "a.py": "ambiguous"
    }


def test_new_authority_producer_grows_register_without_register_edit() -> None:
    """Catch a compiler mutation that requires a central subject-map edit for growth."""
    compile_rows = _sources_api("compile_posture_rows")
    rows = compile_rows(
        source_rows=(
            {
                "path": "scientist/new_source.py",
                "symbol": "new_authority_producer",
                "authoritative_for": ("ds11_free_growth_probe",),
                "may_not_use_for": ("publication_authority",),
            },
        )
    )

    assert [row["subject"] for row in rows] == ["ds11_free_growth_probe"]
    assert rows[0]["effective_state"] == "blocked"


def test_identity_parser_derives_seven_anti_roles_including_crm() -> None:
    """Catch an identity-parser mutation that omits a binding anti-role."""
    parse_roles = _checker_api("parse_binding_anti_roles")

    roles = parse_roles(
        "not an administrator, executor, case-management system, court, "
        "notification channel, payment system, or CRM"
    )

    assert len(roles) == 7
    assert "CRM" in roles


def test_unbound_manages_your_cases_copy_fails_identity_check() -> None:
    """Catch a copy-checker mutation that permits an unbound capability assertion."""
    validate_copy = _checker_api("validate_claim_copy")

    assert validate_copy("manages your cases", source_row=None) == ["unbound_claim_copy"]


def test_internal_a11y_evidence_cannot_mint_external_certification() -> None:
    """Catch a state mutation that promotes internal evidence to certification."""
    evaluate_a11y = _checker_api("evaluate_accessibility_evidence")

    assert (
        evaluate_a11y(
            {
                "evidence_kind": "internal_pre_audit",
                "requested_purpose": "external_certification",
                "countersign_ref": None,
            }
        )
        == "blocked"
    )


def test_metadata_without_independent_source_basis_cannot_support() -> None:
    """Catch a P37 mutation that treats declared metadata as an established predicate."""
    compose = _contract_api("compose_effective_state")

    assert (
        compose(
            ("supported",),
            establishment_classes=("institutionally_supplied",),
        )
        == "blocked"
    )


def test_declared_scope_assumption_is_limitation_not_support() -> None:
    """Catch a scope mutation that promotes an unadjudicated assumption."""
    evaluate_scope = _contract_api("evaluate_scope_assumption")

    assert evaluate_scope({"scope_assumption": "declared", "adjudication": None}) == "blocked"


def test_generator_is_byte_deterministic_and_scratch_bounded() -> None:
    """Catch a generator mutation that varies equal bytes or escapes its output root."""
    generate = _checker_api("generate_posture_bytes")
    rows = ({"subject": "identity", "effective_state": "blocked"},)

    inside_root = "/tmp/ds11-output"
    assert generate(rows=rows, output_root=inside_root, output_path="posture.json") == generate(
        rows=rows,
        output_root=inside_root,
        output_path="posture.json",
    )
    with pytest.raises(ValueError, match=r"output_root|traversal"):
        generate(rows=rows, output_root=inside_root, output_path="../escape.json")


def test_runtime_producer_evidence_binding_cannot_enter_posture_compiler() -> None:
    """Catch compiler admission of a per-run binding as a posture source row."""
    first_binding = _valid_runtime_registry("deficit.first-runtime-binding")
    second_binding = _valid_runtime_registry("deficit.second-runtime-binding")

    assert first_binding["status"] == "pass"
    assert second_binding["status"] == "pass"
    compile_artifact = _sources_api("compile_posture_artifact")
    source_rows = (
        {
            "subject": "ratified_identity",
            "authoritative_for": ("identity",),
            "may_not_use_for": (),
        },
    )
    baseline = compile_artifact(source_rows=source_rows)
    assert compile_artifact(source_rows=source_rows) == baseline
    with pytest.raises(ValueError, match=r"RuntimeClaimRegistry|per-run|unsupported"):
        compile_artifact(source_rows=(first_binding,))
    with pytest.raises(ValueError, match=r"RuntimeClaimRegistry|per-run|unsupported"):
        compile_artifact(source_rows=(second_binding,))
