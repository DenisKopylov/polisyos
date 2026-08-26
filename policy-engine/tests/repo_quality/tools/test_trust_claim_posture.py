"""Red-first repository-semantic tests for DS11 trust-claim posture tooling.

C00 pins collected failures only. C01 owns the compiler/checker implementation
that will turn these named behavior gaps into executable semantic assertions.
"""

from __future__ import annotations

import importlib.util

import pytest


def _posture_compiler_required(test_name: str, mutation: str) -> None:
    """Fail as a collected behavioral red until C01 provides the posture compiler."""
    if importlib.util.find_spec("polisyos.scientist.evidence.claims.posture") is None:
        pytest.fail(
            "DS11 posture behavior is absent for "
            f"{test_name}. Production mutation caught: {mutation}. "
            "C01 must provide the source compiler and independent checker."
        )


def test_source_partition_matches_ast_and_tokenize_file_for_file() -> None:
    """Catch a compiler mutation that drops or reclassifies a source file."""
    _posture_compiler_required(
        "source partition reconciliation",
        "AST and tokenize derivations disagree without emitting an ambiguous file/line row",
    )


def test_new_authority_producer_grows_register_without_register_edit() -> None:
    """Catch a producer mutation that requires a central subject-map edit."""
    _posture_compiler_required(
        "free-growth producer",
        "a new valid source producer cannot add exactly one blocked posture row without registry edit",
    )


def test_identity_parser_derives_seven_anti_roles_including_crm() -> None:
    """Catch an identity-parser mutation that omits a binding anti-role."""
    _posture_compiler_required(
        "seven anti-role derivation",
        "identity parsing omits CRM or any other ratified binding anti-role",
    )


def test_unbound_manages_your_cases_copy_fails_identity_check() -> None:
    """Catch a copy-checker mutation that permits an unbound capability assertion."""
    _posture_compiler_required(
        "unbound capability copy",
        "the posture feature accepts raw 'manages your cases' copy without a bound source row",
    )


def test_internal_a11y_evidence_cannot_mint_external_certification() -> None:
    """Catch a state mutation that promotes internal evidence to certification."""
    _posture_compiler_required(
        "internal-versus-external accessibility evidence",
        "internal a11y evidence alone produces an external certification posture",
    )


def test_metadata_without_independent_source_basis_cannot_support() -> None:
    """Catch a P37 mutation that treats declared metadata as an established predicate."""
    _posture_compiler_required(
        "independent source basis",
        "self-attested posture metadata composes to supported without content-bound evidence",
    )


def test_declared_scope_assumption_is_limitation_not_support() -> None:
    """Catch a scope mutation that promotes an unadjudicated assumption."""
    _posture_compiler_required(
        "scope-assumption limitation",
        "a declared but unadjudicated scope assumption contributes to supported",
    )


def test_generator_is_byte_deterministic_and_scratch_bounded() -> None:
    """Catch a generator mutation that writes outside scratch or varies artifact bytes."""
    _posture_compiler_required(
        "deterministic scratch generation",
        "the posture generator changes bytes across equal inputs or writes outside its output root",
    )


def test_runtime_producer_evidence_binding_cannot_enter_posture_compiler() -> None:
    """Catch an adapter mutation that reuses per-run bindings as posture source rows."""
    _posture_compiler_required(
        "CC09 runtime-registry-to-posture rejection",
        "the posture compiler admits a per-run producer/evidence binding as a posture artifact",
    )
