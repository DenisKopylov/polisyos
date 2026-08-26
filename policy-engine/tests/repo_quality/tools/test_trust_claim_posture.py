"""Repository-semantic tests for DS11 trust-claim posture tooling."""

from __future__ import annotations

import importlib
import json
import shutil
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from polisyos.runtime.quality.claim_registry import build_runtime_claim_registry

REPO_ROOT = Path(__file__).resolve().parents[3]
FROZEN_AS_OF = date(2026, 8, 26)
IDENTITY_PATH = "docs/system-design-decisions/policyos-identity-and-custody-boundary.md"


def _owner(module_name: str) -> Any:
    """Load one required C01 owner or fail at the intended missing seam."""
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name or (
            exc.name is not None and module_name.startswith(f"{exc.name}.")
        ):
            pytest.fail(f"C01 owner module is absent: {module_name}")
        raise


def _sources() -> Any:
    return _owner("tools.quality.validation.trust_claim_posture_sources")


def _checker() -> Any:
    return _owner("tools.quality.validation.check_trust_claim_posture")


def _copy_compiler_inputs(destination: Path, *, full_source: bool = False) -> None:
    source_root = REPO_ROOT / "src"
    target_source = destination / "src"
    if full_source:
        shutil.copytree(source_root, target_source)
    else:
        probe = target_source / "polisyos/example.py"
        probe.parent.mkdir(parents=True)
        probe.write_text(
            '"""Scratch posture source."""\n\n'
            "class ExampleClaim:\n"
            '    authoritative_for = ("example_claim",)\n'
            '    may_not_use_for = ("publication_authority",)\n',
            encoding="utf-8",
        )
    identity = destination / IDENTITY_PATH
    identity.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO_ROOT / IDENTITY_PATH, identity)


def _valid_runtime_registry(binding_ref: str) -> dict[str, object]:
    """Build a real full-axis runtime registry binding for CC09 probes."""
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
    """Catch incomplete walks, count-only agreement, or hidden derivation disagreement."""
    sources = _sources()
    checker = _checker()
    ast_result = sources.derive_ast_sources(REPO_ROOT)
    token_result = checker.derive_token_sources(REPO_ROOT)
    reconciled = checker.reconcile_source_derivations(ast_result, token_result)

    assert ast_result.receipt.scanned_python_count == 2580
    assert token_result.receipt.scanned_python_count == 2580
    assert ast_result.receipt.raw_candidate_count == 105
    assert token_result.receipt.raw_candidate_count == 105
    assert (
        ast_result.receipt.role_counts
        == token_result.receipt.role_counts
        == {
            "declares_only": 66,
            "carries_only": 5,
            "consumes_only": 5,
            "declares_and_consumes": 28,
            "substring_collision": 1,
            "ambiguous": 0,
        }
    )
    assert ast_result.receipt.exact_field_file_count == 104
    assert ast_result.receipt.declaring_file_count == 94
    assert ast_result.receipt.consuming_file_count == 33
    assert not reconciled.disagreements
    posture = next(row for row in reconciled.rows if row.path.endswith("claims/posture.py"))
    assert posture.role == "declares_and_consumes"
    assert posture.declaration_coordinates[0].line > 0
    entry_roles = dict(ast_result.receipt.role_counts)
    entry_roles["declares_and_consumes"] -= 1
    assert entry_roles == {
        "declares_only": 66,
        "carries_only": 5,
        "consumes_only": 5,
        "declares_and_consumes": 27,
        "substring_collision": 1,
        "ambiguous": 0,
    }
    assert ast_result.receipt.scanned_python_count - 1 == 2579
    assert ast_result.receipt.raw_candidate_count - 1 == 104
    assert ast_result.receipt.exact_field_file_count - 1 == 103
    collision = next(row for row in reconciled.rows if row.role == "substring_collision")
    assert collision.path.endswith("data_forge/domains/academic/batch/best_snapshot.py")
    assert collision.issue_codes == ("DS11-SOURCE-COLLISION",)
    witness = next(row for row in token_result.rows if row.role == "declares_only")
    mutated_rows = tuple(
        row.model_copy(update={"role": "carries_only"}) if row.path == witness.path else row
        for row in token_result.rows
    )
    disagreement = checker.reconcile_source_derivations(
        ast_result,
        token_result.model_copy(update={"rows": mutated_rows}),
    )
    ambiguous = next(row for row in disagreement.rows if row.path == witness.path)
    assert disagreement.disagreements == (witness.path,)
    assert ambiguous.role == "ambiguous"
    assert ambiguous.resolution == "ambiguous"
    assert ambiguous.issue_codes == ("DS11-SOURCE-DERIVATION-DISAGREEMENT",)
    assert (
        min(
            coordinate.line
            for coordinate in (
                *ambiguous.declaration_coordinates,
                *ambiguous.carrier_coordinates,
                *ambiguous.consumer_coordinates,
            )
        )
        > 0
    )


def test_literal_censuses_reconcile_for_both_complete_walks() -> None:
    """Catch a compiler mutation that drops wrappers, empty sites, or denied purposes."""
    ast_receipt = _sources().derive_ast_sources(REPO_ROOT).receipt
    token_receipt = _checker().derive_token_sources(REPO_ROOT).receipt

    for receipt in (ast_receipt, token_receipt):
        assert (
            receipt.direct_literal_site_count,
            receipt.direct_literal_file_count,
            receipt.direct_literal_subject_count,
            receipt.direct_empty_site_count,
        ) == (35, 13, 21, 5)
        assert (
            receipt.wrapper_literal_site_count,
            receipt.wrapper_literal_file_count,
            receipt.wrapper_literal_subject_count,
        ) == (59, 24, 28)
        assert (
            receipt.may_not_use_for_raw_file_count,
            receipt.may_not_use_for_literal_site_count,
            receipt.may_not_use_for_literal_file_count,
            receipt.may_not_use_for_literal_subject_count,
        ) == (117, 34, 22, 44)
        assert receipt.may_not_use_for_raw_file_count - 1 == 116


def test_new_authority_producer_grows_both_complete_walks_without_register_edit(
    tmp_path: Path,
) -> None:
    """Catch subject-map coupling or a walk that ignores a new real Python producer."""
    scratch = tmp_path / "repo"
    _copy_compiler_inputs(scratch, full_source=True)
    sources = _sources()
    checker = _checker()
    before_ast = sources.derive_ast_sources(scratch)
    before_token = checker.derive_token_sources(scratch)
    probe = scratch / "src/polisyos/scientist/evidence/claims/ds11_growth_probe.py"
    probe.write_text(
        '"""Scratch-only free-growth producer."""\n\n'
        "class DS11GrowthProbe:\n"
        '    authoritative_for = ("ds11_free_growth_probe",)\n'
        '    may_not_use_for = ("publication_authority",)\n',
        encoding="utf-8",
    )
    after_ast = sources.derive_ast_sources(scratch)
    after_token = checker.derive_token_sources(scratch)
    reconciled = checker.reconcile_source_derivations(after_ast, after_token)
    bindings = sources.compile_source_claim_bindings(reconciled, package_owners={})

    for before, after in (
        (before_ast.receipt, after_ast.receipt),
        (before_token.receipt, after_token.receipt),
    ):
        assert after.scanned_python_count == before.scanned_python_count + 1
        assert after.raw_candidate_count == before.raw_candidate_count + 1
        assert after.exact_field_file_count == before.exact_field_file_count + 1
        assert after.declaring_file_count == before.declaring_file_count + 1
        assert after.direct_literal_site_count == before.direct_literal_site_count + 1
        assert after.direct_literal_subject_count == before.direct_literal_subject_count + 1
    assert not reconciled.disagreements
    growth = [binding for binding in bindings if binding.subject == "ds11_free_growth_probe"]
    assert len(growth) == 1
    assert growth[0].coordinate.path.endswith("ds11_growth_probe.py")
    assert growth[0].coordinate.symbol == "DS11GrowthProbe"
    assert growth[0].may_not_use_for == ("publication_authority",)
    assert growth[0].content_digest == "sha256:" + sha256(probe.read_bytes()).hexdigest()
    assert growth[0].source_state == "not_established"


def test_identity_parser_derives_seven_anti_roles_including_crm() -> None:
    """Catch a parser mutation that samples or hand-enumerates the anti-role paragraph."""
    boundary = _checker().derive_identity_boundary(REPO_ROOT)
    assert tuple(item.display_label for item in boundary.anti_roles) == (
        "administrator",
        "executor",
        "case-management system",
        "court",
        "notification channel",
        "payment system",
        "CRM",
    )
    assert boundary.paragraph_start_line <= 88 <= boundary.paragraph_end_line


def test_unbound_manages_your_cases_copy_fails_identity_check() -> None:
    """Catch a copy mutation that accepts capability prose outside the sole renderer."""
    assert _checker().validate_claim_copy("manages your cases", source_row=None) == (
        "DS11-IDENTITY-COPY-UNBOUND",
    )


def test_internal_a11y_evidence_cannot_mint_external_certification() -> None:
    """Catch promotion of internal historical evidence to current certification."""
    result = _checker().evaluate_accessibility_evidence(
        evidence_kind="internal_pre_audit",
        requested_purpose="external_accessibility_certification",
        source_as_of=FROZEN_AS_OF,
        countersign_ref=None,
    )
    assert result.state == "blocked"
    assert "DS11-A11Y-CERTIFICATION-NOT-EARNED" in result.issue_codes


def test_declared_scope_assumption_is_limitation_not_support() -> None:
    """Catch a scope mutation that promotes an unadjudicated declaration."""
    result = _checker().evaluate_scope_assumption(
        scope_assumption="jurisdiction_neutral", adjudication_ref=None
    )
    assert result.state == "blocked"
    assert result.establishment_class == "not_established"
    assert result.limitations == ("Declared scope assumption: jurisdiction_neutral",)


def test_generator_is_byte_deterministic_and_fixed_target_scratch_bounded(
    tmp_path: Path,
) -> None:
    """Catch nondeterministic bytes, arbitrary filenames, or output-root escape."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    checker = _checker()
    first, first_bytes = checker.compile_claim_posture_register(repo, register_as_of=FROZEN_AS_OF)
    second, second_bytes = checker.compile_claim_posture_register(repo, register_as_of=FROZEN_AS_OF)
    assert first == second
    assert first_bytes == second_bytes

    output_root = tmp_path / "output"
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()}
    written = checker.write_claim_posture_register(first, output_root=output_root)
    after = {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()}
    assert (
        written == output_root / "apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json"
    )
    assert after - before == {
        Path("output/apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json")
    }
    assert written.read_bytes() == first_bytes


def test_valid_runtime_registry_is_outside_posture_compiler_denominator(tmp_path: Path) -> None:
    """Catch admission of valid per-run producer evidence into posture rows or bytes."""
    repo = tmp_path / "repo"
    _copy_compiler_inputs(repo)
    checker = _checker()
    baseline_register, baseline_bytes = checker.compile_claim_posture_register(
        repo, register_as_of=FROZEN_AS_OF
    )
    runtime_dir = repo / "ops/migrations/runtime_state/run_records"
    runtime_dir.mkdir(parents=True)
    first = _valid_runtime_registry("deficit.first-runtime-binding")
    assert first["status"] == "pass"
    (runtime_dir / "claim-registry.json").write_text(json.dumps(first), encoding="utf-8")
    first_register, first_bytes = checker.compile_claim_posture_register(
        repo, register_as_of=FROZEN_AS_OF
    )
    second = _valid_runtime_registry("deficit.second-runtime-binding")
    assert second["status"] == "pass"
    (runtime_dir / "claim-registry.json").write_text(json.dumps(second), encoding="utf-8")
    second_register, second_bytes = checker.compile_claim_posture_register(
        repo, register_as_of=FROZEN_AS_OF
    )
    assert baseline_register == first_register == second_register
    assert baseline_bytes == first_bytes == second_bytes
    assert b"runtime-final-claim" not in second_bytes
    assert b"deficit.second-runtime-binding" not in second_bytes


def test_runtime_registry_payload_is_rejected_as_source_adapter() -> None:
    """Catch a generic-adapter mutation that accepts the distinct runtime schema."""
    runtime_registry = _valid_runtime_registry("deficit.runtime-only")
    assert runtime_registry["status"] == "pass"
    with pytest.raises(ValueError, match=r"RuntimeClaimRegistry|per-run|unsupported"):
        _sources().compile_source_adapter(runtime_registry)
