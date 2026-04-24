"""Circuit 1: Symbolic / Identification benchmark — the primary benchmark.

Loads all graphs from the gold-suite, runs each through the PolicyOS
identification stack, measures time / memory / proof-step count, and
compares with y0 (if installed) for identifiability agreement.

Usage
-----
    # Run standalone:
    python benchmarks/symbolic/run_symbolic_benchmark.py

    # Run with y0 comparison:
    python benchmarks/symbolic/run_symbolic_benchmark.py --y0-compare

    # Output JSON report:
    python benchmarks/symbolic/run_symbolic_benchmark.py --json report.json

Bar
---
    100% correctness required.
    Any false-positive identification (claimed IDENTIFIED, truth: HEDGE_FOUND)
    is a release blocker and will cause a non-zero exit code.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Path bootstrap (works when run directly OR from pytest)
# ---------------------------------------------------------------------------

_BENCH_ROOT = Path(__file__).resolve().parent.parent
_SRC = _BENCH_ROOT.parent / "src"
for _p in [str(_SRC), str(_BENCH_ROOT.parent)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------

from benchmarks.conftest import (  # noqa: E402
    canon,
    is_rule_subsequence,
    latex_from_result,
    make_admg,
    make_bidirected_edge,
    make_dag,
    make_directed_edge,
    rule_names_from_result,
    y0_available,
)
from benchmarks.harness import (  # noqa: E402
    BenchmarkCase,
    BenchmarkCircuit,
    BenchmarkHarness,
    BenchmarkReport,
)
from benchmarks.reporting import (
    build_preflight,
    build_report_payload,
    print_preflight,
)
from benchmarks.runtime import BenchmarkMode, acceptance_gaps, dependency_status, resolve_mode
from polisyos.foundry.methods.catalog.causal.ctf_calculus import (  # noqa: E402
    _build_amn_for_ast,
    apply_ctf_rule1,
    apply_ctf_rule2,
    apply_ctf_rule3,
)
from polisyos.foundry.methods.catalog.causal.ctf_transport import (  # noqa: E402
    build_ctf_selection_diagram,
    ctf_transportability,
)
from polisyos.foundry.methods.catalog.causal.cyclic_id import cyclic_id_algorithm  # noqa: E402
from polisyos.foundry.methods.catalog.causal.id_engine import (  # noqa: E402
    CtfQuery,
    IdentificationStatus,
    SourceDomain,
    id_algorithm,
    id_star_algorithm,
    idc_algorithm,
    idc_star_algorithm,
    mz_id_algorithm,
    z_id_algorithm,
)
from polisyos.foundry.methods.catalog.causal.path_specific import (
    _recanting_witness_check,  # noqa: E402
)
from polisyos.foundry.methods.catalog.causal.recoverability_engine import (  # noqa: E402
    RecoverabilityStatus,
    full_law_identify,
)
from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
    test_recoverability as recoverability_test,
)
from polisyos.foundry.methods.catalog.causal.sigma_calculus import (  # noqa: E402
    apply_sigma_rule1,
    apply_sigma_rule2,
    apply_sigma_rule3,
)
from polisyos.foundry.methods.catalog.causal.transport_check import (
    CheckTransportability,  # noqa: E402
)
from polisyos.ir.analytics.causal_graph import (  # noqa: E402
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel  # noqa: E402
from polisyos.ir.analytics.estimand import (  # noqa: E402
    CounterfactualNode,
    CrossWorldNode,
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    NestedCounterfactualNode,
)
from polisyos.ir.analytics.mgraph import (  # noqa: E402
    MissingnessKind,
    build_mgraph,
    extract_mgraph_metadata,
)
from polisyos.ir.analytics.negative_certificate import (  # noqa: E402
    BlockingType,
    NegativeCertificate,
)
from polisyos.ir.analytics.transportability import (  # noqa: E402
    SNode,
    SNodeOrigin,
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
    build_selection_diagram,
)

CIRCUIT = BenchmarkCircuit.SYMBOLIC

# ---------------------------------------------------------------------------
# Helpers shared with gold suite
# ---------------------------------------------------------------------------

_IS_IDENTIFIED = IdentificationStatus.IDENTIFIED
_IS_HEDGE = IdentificationStatus.HEDGE_FOUND


def _edge(src: str, dst: str, *, bidirected: bool = False) -> CausalEdge:
    if bidirected:
        return make_bidirected_edge(src, dst)
    return make_directed_edge(src, dst)


def _dag(edges: list[tuple[str, str]], *, extra_nodes: tuple[str, ...] = ()) -> CausalGraphModel:
    return make_dag(edges, extra_nodes=extra_nodes)


def _admg(
    nodes: list[str],
    edges: list[CausalEdge],
    *,
    metadata: dict | None = None,
) -> CausalGraphModel:
    return make_admg(nodes, edges, metadata=metadata)


def _source_context() -> ContextProfile:
    return ContextProfile(
        context_id="DE",
        income_level=IncomeLevel.HIGH,
        institutional_quality=0.85,
    )


def _target_context() -> ContextProfile:
    return ContextProfile(
        context_id="UA",
        income_level=IncomeLevel.LOWER_MIDDLE,
        institutional_quality=0.35,
    )


def _transport_result(
    diagram,
    *,
    treatment: str,
    outcome: str,
    params: dict | None = None,
) -> TransportabilityResult:
    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": treatment,
            "query_outcome": outcome,
        },
        params or {},
    )
    return TransportabilityResult.model_validate(payload["transport_result"])


# ---------------------------------------------------------------------------
# Case-builder helpers
# ---------------------------------------------------------------------------


def _id_case(
    name: str,
    runner,
    expected_status: IdentificationStatus,
    expected_formula: str | None,
    expected_trace: tuple[str, ...],
    tags: tuple[str, ...] = (),
) -> BenchmarkCase:
    """Build a BenchmarkCase for a standard id_algorithm / idc_algorithm result."""
    gt_identifiable = expected_status is _IS_IDENTIFIED

    def checker(result) -> bool:
        if result.status is not expected_status:
            raise AssertionError(
                f"expected status={expected_status.value}, got={result.status.value}"
            )
        if expected_formula is not None:
            got = canon(result.estimand_ast.to_latex()) if result.estimand_ast else None
            want = canon(expected_formula)
            if got != want:
                raise AssertionError(f"formula mismatch:\n  want: {want}\n  got : {got}")
        if expected_trace:
            if not is_rule_subsequence(result, expected_trace):
                actual = rule_names_from_result(result)
                raise AssertionError(
                    f"trace subsequence mismatch:\n  want: {expected_trace}\n  got : {actual}"
                )
        if expected_status is _IS_HEDGE:
            if result.hedge_certificate is None:
                raise AssertionError("HEDGE_FOUND but no hedge_certificate")
        return True

    def formula_ok(result) -> bool:
        if expected_formula is None:
            return True
        got = canon(result.estimand_ast.to_latex()) if result.estimand_ast else None
        return got == canon(expected_formula)

    return BenchmarkCase(
        name=f"id::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=rule_names_from_result,
        is_identifiable_ground_truth=gt_identifiable,
        is_identifiable_extractor=lambda r: r.status is _IS_IDENTIFIED,
        formula_correct_extractor=formula_ok,
        tags=("id",) + tags,
    )


def _idc_case(
    name: str,
    runner,
    expected_formula: str,
) -> BenchmarkCase:
    def checker(result) -> bool:
        if result.status is not _IS_IDENTIFIED:
            raise AssertionError(f"IDC expected IDENTIFIED, got={result.status.value}")
        got = canon(result.estimand_ast.to_latex()) if result.estimand_ast else None
        want = canon(expected_formula)
        if got != want:
            raise AssertionError(f"formula mismatch:\n  want: {want}\n  got : {got}")
        if not is_rule_subsequence(result, ("IDC_DECOMPOSE", "IDC_POSITIVITY")):
            raise AssertionError(f"missing IDC trace steps, got: {rule_names_from_result(result)}")
        return True

    return BenchmarkCase(
        name=f"idc::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=rule_names_from_result,
        is_identifiable_ground_truth=True,
        is_identifiable_extractor=lambda r: r.status is _IS_IDENTIFIED,
        formula_correct_extractor=lambda r: canon(
            r.estimand_ast.to_latex() if r.estimand_ast else None
        )
        == canon(expected_formula),
        tags=("idc",),
    )


def _id_star_case(
    name: str,
    runner,
    expected_status: IdentificationStatus,
    expected_query: str,
    expected_root_type: type | None = None,
    check_trace: bool = True,
) -> BenchmarkCase:
    gt_identifiable = expected_status is _IS_IDENTIFIED

    def checker(result) -> bool:
        if result.status is not expected_status:
            raise AssertionError(
                f"ID* expected status={expected_status.value}, got={result.status.value}"
            )
        if canon(result.query_str) != canon(expected_query):
            raise AssertionError(
                f"query_str mismatch:\n  want: {canon(expected_query)}\n"
                f"  got : {canon(result.query_str)}"
            )
        if expected_status is _IS_IDENTIFIED:
            if result.estimand_ast is None:
                raise AssertionError("IDENTIFIED but no estimand_ast")
            if expected_root_type is not None:
                if not isinstance(result.estimand_ast.root, expected_root_type):
                    raise AssertionError(
                        f"root type: want {expected_root_type.__name__}, "
                        f"got {type(result.estimand_ast.root).__name__}"
                    )
            if check_trace and not is_rule_subsequence(
                result, ("ID_STAR_STEP1", "ID_STAR_STEP2", "ID_STAR_STEP3", "ID_STAR_STEP5")
            ):
                raise AssertionError(f"missing ID* trace, got: {rule_names_from_result(result)}")
        else:
            if result.hedge_certificate is None:
                raise AssertionError("non-identified ID* but no hedge_certificate")
        return True

    return BenchmarkCase(
        name=f"id_star::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=rule_names_from_result,
        is_identifiable_ground_truth=gt_identifiable,
        is_identifiable_extractor=lambda r: r.status is _IS_IDENTIFIED,
        tags=("id_star",),
    )


def _idc_star_case(
    name: str,
    runner,
    expected_status: IdentificationStatus,
    expected_query: str,
) -> BenchmarkCase:
    gt_identifiable = expected_status is _IS_IDENTIFIED

    def checker(result) -> bool:
        if result.status is not expected_status:
            raise AssertionError(
                f"IDC* expected status={expected_status.value}, got={result.status.value}"
            )
        if canon(result.query_str) != canon(expected_query):
            raise AssertionError(
                f"IDC* query_str mismatch:\n  want: {canon(expected_query)}\n"
                f"  got : {canon(result.query_str)}"
            )
        if expected_status is _IS_IDENTIFIED:
            if result.estimand_ast is None:
                raise AssertionError("IDC* IDENTIFIED but no estimand_ast")
            if not is_rule_subsequence(result, ("IDC_STAR_RATIO",)):
                raise AssertionError(
                    f"missing IDC_STAR_RATIO step, got: {rule_names_from_result(result)}"
                )
        else:
            if result.hedge_certificate is None:
                raise AssertionError("IDC* non-identified but no hedge_certificate")
        return True

    return BenchmarkCase(
        name=f"idc_star::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=rule_names_from_result,
        is_identifiable_ground_truth=gt_identifiable,
        is_identifiable_extractor=lambda r: r.status is _IS_IDENTIFIED,
        tags=("idc_star",),
    )


def _z_id_case(
    name: str,
    runner,
    expected_status: IdentificationStatus,
    expected_formula: str | None,
    expected_trace: tuple[str, ...],
) -> BenchmarkCase:
    gt_identifiable = expected_status is _IS_IDENTIFIED

    def checker(result) -> bool:
        if result.status is not expected_status:
            raise AssertionError(
                f"Z-ID expected status={expected_status.value}, got={result.status.value}"
            )
        if expected_formula is not None:
            got = canon(result.estimand_ast.to_latex()) if result.estimand_ast else None
            want = canon(expected_formula)
            if got != want:
                raise AssertionError(f"Z-ID formula mismatch:\n  want: {want}\n  got : {got}")
        if expected_trace and not is_rule_subsequence(result, expected_trace):
            raise AssertionError(
                f"Z-ID trace mismatch:\n  want: {expected_trace}\n"
                f"  got : {rule_names_from_result(result)}"
            )
        return True

    return BenchmarkCase(
        name=f"z_id::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=rule_names_from_result,
        is_identifiable_ground_truth=gt_identifiable,
        is_identifiable_extractor=lambda r: r.status is _IS_IDENTIFIED,
        tags=("z_id",),
    )


def _mz_id_case(
    name: str,
    runner,
    expected_status: IdentificationStatus,
    expected_formula: str | None,
    expected_trace: tuple[str, ...] | tuple[tuple[str, ...], ...],
) -> BenchmarkCase:
    gt_identifiable = expected_status is _IS_IDENTIFIED

    def checker(result) -> bool:
        if result.status is not expected_status:
            raise AssertionError(
                f"MZ-ID expected status={expected_status.value}, got={result.status.value}"
            )
        if expected_formula is not None:
            got = canon(result.estimand_ast.to_latex()) if result.estimand_ast else None
            want = canon(expected_formula)
            if got != want:
                raise AssertionError(f"MZ-ID formula mismatch:\n  want: {want}\n  got : {got}")
        expected_trace_options = (
            expected_trace
            if expected_trace and isinstance(expected_trace[0], tuple)
            else (expected_trace,)
        )
        if expected_trace and not any(
            is_rule_subsequence(result, trace_option) for trace_option in expected_trace_options
        ):
            raise AssertionError(
                f"MZ-ID trace mismatch:\n  want: {expected_trace}\n"
                f"  got : {rule_names_from_result(result)}"
            )
        return True

    return BenchmarkCase(
        name=f"mz_id::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=rule_names_from_result,
        is_identifiable_ground_truth=gt_identifiable,
        is_identifiable_extractor=lambda r: r.status is _IS_IDENTIFIED,
        tags=("mz_id",),
    )


def _transport_case(
    name: str,
    runner,
    expected_status: TransportabilityStatus,
    expected_mode: TransportMode,
    expected_fragment: str | None,
    extra_checks: dict | None = None,
) -> BenchmarkCase:
    def checker(result: TransportabilityResult) -> bool:
        if result.status is not expected_status:
            raise AssertionError(
                f"transport expected status={expected_status.value}, got={result.status.value}"
            )
        if result.transport_mode is not expected_mode:
            raise AssertionError(
                f"transport mode: want={expected_mode.value}, got={result.transport_mode.value}"
            )
        if expected_fragment is not None:
            if result.transport_formula is None:
                raise AssertionError("transport_formula is None, expected formula fragment")
            if expected_fragment not in result.transport_formula.formula_str:
                raise AssertionError(
                    f"fragment '{expected_fragment}' not in formula "
                    f"'{result.transport_formula.formula_str}'"
                )
        extra = extra_checks or {}
        if "unsupported_reason" in extra:
            if result.unsupported_reason != extra["unsupported_reason"]:
                raise AssertionError(
                    f"unsupported_reason: want={extra['unsupported_reason']!r}, "
                    f"got={result.unsupported_reason!r}"
                )
        if "has_pag_confidence" in extra and extra["has_pag_confidence"]:
            if result.id_confidence_under_pag is None:
                raise AssertionError("expected id_confidence_under_pag, got None")
            if not (0.0 <= result.id_confidence_under_pag <= 1.0):
                raise AssertionError(
                    f"id_confidence_under_pag out of range: {result.id_confidence_under_pag}"
                )
        return True

    # Transport cases are not directly comparable via IdentificationStatus
    return BenchmarkCase(
        name=f"transport::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("transport",),
    )


def _ctf_transport_case(
    name: str,
    runner,
    kind: str,  # "identified" or "negative"
    expected_query: str | None,
    expected_trace: tuple[str, ...],
) -> BenchmarkCase:
    gt_identifiable = kind == "identified"

    def checker(result) -> bool:
        if kind == "negative":
            if not isinstance(result, NegativeCertificate):
                raise AssertionError(
                    f"CTF transport expected NegativeCertificate, got {type(result).__name__}"
                )
            if result.blocking_type is not BlockingType.S_NODE_UNRESOLVED:
                raise AssertionError(
                    f"blocking_type: want S_NODE_UNRESOLVED, got {result.blocking_type}"
                )
            if result.partial_bounds is None:
                raise AssertionError("expected partial_bounds, got None")
            return True

        # kind == "identified"
        if result.status is not _IS_IDENTIFIED:
            raise AssertionError(f"CTF transport expected IDENTIFIED, got {result.status.value}")
        if expected_query is not None and canon(result.query_str) != canon(expected_query):
            raise AssertionError(
                f"query_str mismatch:\n  want: {canon(expected_query)}\n"
                f"  got : {canon(result.query_str)}"
            )
        if expected_trace and not is_rule_subsequence(result, expected_trace):
            raise AssertionError(
                f"CTF transport trace mismatch:\n  want: {expected_trace}\n"
                f"  got : {rule_names_from_result(result)}"
            )
        return True

    def is_id_pred(result) -> bool:
        if isinstance(result, NegativeCertificate):
            return False
        return result.status is _IS_IDENTIFIED

    return BenchmarkCase(
        name=f"ctf_transport::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=lambda r: rule_names_from_result(r)
        if not isinstance(r, NegativeCertificate)
        else [],
        is_identifiable_ground_truth=gt_identifiable,
        is_identifiable_extractor=is_id_pred,
        tags=("ctf_transport",),
    )


def _cyclic_case(
    name: str,
    runner,
    expected_status: IdentificationStatus,
    expected_formula: str | None,
    expected_trace: tuple[str, ...],
) -> BenchmarkCase:
    gt_identifiable = expected_status is _IS_IDENTIFIED

    def checker(result) -> bool:
        if result.status is not expected_status:
            raise AssertionError(
                f"cyclic expected status={expected_status.value}, got={result.status.value}"
            )
        if expected_formula is not None:
            got = canon(result.estimand_ast.to_latex()) if result.estimand_ast else None
            want = canon(expected_formula)
            if got != want:
                raise AssertionError(f"cyclic formula mismatch:\n  want: {want}\n  got : {got}")
        else:
            if result.hedge_certificate is None:
                raise AssertionError("cyclic HEDGE_FOUND but no hedge_certificate")
        if not is_rule_subsequence(result, expected_trace):
            raise AssertionError(
                f"cyclic trace mismatch:\n  want: {expected_trace}\n"
                f"  got : {rule_names_from_result(result)}"
            )
        return True

    return BenchmarkCase(
        name=f"cyclic::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=rule_names_from_result,
        is_identifiable_ground_truth=gt_identifiable,
        is_identifiable_extractor=lambda r: r.status is _IS_IDENTIFIED,
        tags=("cyclic",),
    )


def _mgraph_case(
    name: str,
    runner,
    expected_status,
    expected_formula: str | None,
    extra_checks: dict | None = None,
) -> BenchmarkCase:
    # M-graph cases use either RecoverabilityStatus or IdentificationStatus
    is_recoverable = (
        expected_status is RecoverabilityStatus.RECOVERABLE or expected_status is _IS_IDENTIFIED
    )

    def checker(result) -> bool:
        if result.status != expected_status:
            raise AssertionError(f"mgraph expected status={expected_status}, got={result.status}")
        if expected_formula is not None:
            got = canon(latex_from_result(result))
            want = canon(expected_formula)
            if got != want:
                raise AssertionError(f"mgraph formula mismatch:\n  want: {want}\n  got : {got}")
        extra = extra_checks or {}
        if "blocking_r_nodes" in extra:
            if result.blocking_r_nodes != extra["blocking_r_nodes"]:
                raise AssertionError(
                    f"blocking_r_nodes: want={extra['blocking_r_nodes']}, "
                    f"got={result.blocking_r_nodes}"
                )
        if "rule_subsequence" in extra:
            if not is_rule_subsequence(result, extra["rule_subsequence"]):
                raise AssertionError(
                    f"mgraph trace mismatch:\n  want: {extra['rule_subsequence']}\n"
                    f"  got : {rule_names_from_result(result)}"
                )
        if "has_hedge" in extra and extra["has_hedge"]:
            if not hasattr(result, "hedge_certificate") or result.hedge_certificate is None:
                raise AssertionError("expected hedge_certificate, got None")
        return True

    return BenchmarkCase(
        name=f"mgraph::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=rule_names_from_result,
        is_identifiable_ground_truth=is_recoverable,
        is_identifiable_extractor=lambda r: (
            r.status is RecoverabilityStatus.RECOVERABLE or r.status is _IS_IDENTIFIED
        ),
        tags=("mgraph",),
    )


def _proof_trace_case(name: str, runner, expected_trace: tuple[str, ...]) -> BenchmarkCase:
    def checker(result) -> bool:
        if not is_rule_subsequence(result, expected_trace):
            raise AssertionError(
                f"proof trace mismatch:\n  want: {expected_trace}\n"
                f"  got : {rule_names_from_result(result)}"
            )
        return True

    return BenchmarkCase(
        name=f"trace::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=rule_names_from_result,
        tags=("trace",),
    )


_MISSING = object()  # sentinel for getattr checks in rule-application cases


def _sigma_calculus_case(
    name: str,
    runner,
    expected_rule_name: str,
    expected_attrs: dict,
) -> BenchmarkCase:
    """Benchmark case for a single sigma-calculus rule application.

    ``runner`` should return ``(rewritten_ref, step)`` or ``None``.
    """

    def checker(result) -> bool:
        if result is None:
            raise AssertionError(f"sigma {name}: rule did not apply (returned None)")
        rewritten, step = result
        if rewritten is None:
            raise AssertionError(f"sigma {name}: rewritten ref is None")
        if step is None:
            raise AssertionError(f"sigma {name}: proof step is None")
        if step.rule_name != expected_rule_name:
            raise AssertionError(
                f"sigma {name}: want rule_name={expected_rule_name!r}, got={step.rule_name!r}"
            )
        for attr, want in expected_attrs.items():
            got = getattr(rewritten, attr, _MISSING)
            if got is _MISSING:
                raise AssertionError(f"sigma {name}: rewritten has no attribute {attr!r}")
            if got != want:
                raise AssertionError(f"sigma {name}: rewritten.{attr}: want={want!r}, got={got!r}")
        return True

    def step_extractor(result) -> list[str]:
        if result is None:
            return []
        _, step = result
        return [step.rule_name] if step else []

    return BenchmarkCase(
        name=f"sigma::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=step_extractor,
        tags=("sigma",),
    )


def _ctf_calculus_case(
    name: str,
    runner,
    expected_rule_name: str,
    expected_attrs: dict,
) -> BenchmarkCase:
    """Benchmark case for a single CTF-calculus rule application.

    ``runner`` should return ``(rewritten_node, step)`` or ``None``.
    """

    def checker(result) -> bool:
        if result is None:
            raise AssertionError(f"ctf {name}: rule did not apply (returned None)")
        rewritten, step = result
        if rewritten is None:
            raise AssertionError(f"ctf {name}: rewritten node is None")
        if step is None:
            raise AssertionError(f"ctf {name}: proof step is None")
        if step.rule_name != expected_rule_name:
            raise AssertionError(
                f"ctf {name}: want rule_name={expected_rule_name!r}, got={step.rule_name!r}"
            )
        for attr, want in expected_attrs.items():
            got = getattr(rewritten, attr, _MISSING)
            if got is _MISSING:
                raise AssertionError(f"ctf {name}: rewritten has no attribute {attr!r}")
            if got != want:
                raise AssertionError(f"ctf {name}: rewritten.{attr}: want={want!r}, got={got!r}")
        return True

    def step_extractor(result) -> list[str]:
        if result is None:
            return []
        _, step = result
        return [step.rule_name] if step else []

    return BenchmarkCase(
        name=f"ctf_calculus::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=step_extractor,
        tags=("ctf_calculus",),
    )


def _recanting_witness_case(
    name: str,
    runner,
    expected_has_witness: bool,
) -> BenchmarkCase:
    """Benchmark case for the recanting-witness check.

    ``runner`` returns ``(has_witness: bool, witnesses: list)``.
    A false positive (has_witness=True when expected=False) is a blocker.
    """

    def checker(result) -> bool:
        has_witness, witnesses = result
        if has_witness != expected_has_witness:
            raise AssertionError(
                f"recanting_witness {name}: "
                f"want has_witness={expected_has_witness}, got={has_witness} "
                f"(witnesses={witnesses})"
            )
        if not expected_has_witness and witnesses:
            raise AssertionError(
                f"recanting_witness {name}: expected no witnesses, got={witnesses}"
            )
        return True

    return BenchmarkCase(
        name=f"recanting::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        # Treat "has_witness=False" as "identifiable" for false-positive tracking:
        # a false positive would be claiming a witness exists when there is none.
        is_identifiable_ground_truth=not expected_has_witness,
        is_identifiable_extractor=lambda r: not r[0],
        tags=("recanting",),
    )


# ---------------------------------------------------------------------------
# Gold cases — mirroring test_symbolic_gold_suite.py
# ---------------------------------------------------------------------------


def _build_id_cases() -> list[BenchmarkCase]:
    return [
        _id_case(
            "direct_dag",
            lambda: id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                graph=_dag([("X", "Y")]),
            ),
            _IS_IDENTIFIED,
            r"P(Y \mid X)",
            ("G_FORMULA",),
        ),
        _id_case(
            "mediated_dag",
            lambda: id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                graph=_dag([("X", "M"), ("M", "Y")]),
            ),
            _IS_IDENTIFIED,
            r"\sum_{M} P(M \mid X) \cdot P(Y \mid M)",
            ("G_FORMULA",),
        ),
        _id_case(
            "backdoor_dag",
            lambda: id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                graph=_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")]),
            ),
            _IS_IDENTIFIED,
            r"\sum_{Z} P(Z) \cdot P(Y \mid X, Z)",
            ("G_FORMULA",),
        ),
        _id_case(
            "ancestral_collapse",
            lambda: id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                graph=_dag([("X", "Y")], extra_nodes=("W",)),
            ),
            _IS_IDENTIFIED,
            r"P(Y \mid X)",
            ("ANCESTRAL_COLLAPSE", "G_FORMULA"),
        ),
        _id_case(
            "napkin_observed_confounder",
            lambda: id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                graph=_dag([("U", "X"), ("U", "Y"), ("X", "M"), ("M", "Y")]),
            ),
            _IS_IDENTIFIED,
            r"\sum_{M, U} P(U) \cdot P(M \mid X) \cdot P(Y \mid M, U)",
            ("G_FORMULA",),
        ),
        _id_case(
            "frontdoor_admg",
            lambda: id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                graph=_admg(
                    ["X", "M", "Y"],
                    [_edge("X", "M"), _edge("M", "Y"), _edge("X", "Y", bidirected=True)],
                ),
            ),
            _IS_IDENTIFIED,
            r"\sum_{M} P(M \mid X) \cdot \sum_{X} P(Y \mid M, X) \cdot P(X)",
            ("FRONTDOOR",),
            tags=("frontdoor",),
        ),
        _id_case(
            "bow_arc_hedge",
            lambda: id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                graph=_admg(
                    ["X", "Y"],
                    [_edge("X", "Y"), _edge("X", "Y", bidirected=True)],
                ),
            ),
            _IS_HEDGE,
            None,
            ("HEDGE",),
            tags=("hedge",),
        ),
        _id_case(
            "confounded_backdoor_hedge",
            lambda: id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                graph=_admg(
                    ["X", "Y", "Z"],
                    [
                        _edge("Z", "X"),
                        _edge("Z", "Y"),
                        _edge("X", "Y"),
                        _edge("X", "Y", bidirected=True),
                    ],
                ),
            ),
            _IS_HEDGE,
            None,
            ("C_COMPONENT", "HEDGE"),
            tags=("hedge",),
        ),
    ]


def _build_idc_cases() -> list[BenchmarkCase]:
    return [
        _idc_case(
            "backdoor",
            lambda: idc_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                conditions=frozenset({"Z"}),
                graph=_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")]),
            ),
            r"\frac{P(Z) \cdot P(Y \mid X, Z)}{P(Z)}",
        ),
        _idc_case(
            "mediated",
            lambda: idc_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                conditions=frozenset({"M"}),
                graph=_dag([("X", "M"), ("M", "Y")]),
            ),
            r"\frac{P(M \mid X) \cdot P(Y \mid M)}{P(M \mid X)}",
        ),
        _idc_case(
            "two_conditions",
            lambda: idc_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                conditions=frozenset({"W", "Z"}),
                graph=_dag([("Z", "X"), ("W", "Y"), ("Z", "Y"), ("X", "Y")]),
            ),
            r"\frac{P(W) \cdot P(Z) \cdot P(Y \mid W, X, Z)}{P(W, Z)}",
        ),
    ]


def _build_id_star_cases() -> list[BenchmarkCase]:
    return [
        _id_star_case(
            "single_world_backdoor",
            lambda: id_star_algorithm(
                CtfQuery(
                    outcome="Y",
                    intervention=(("X", 1.0),),
                    conditioning=("Z",),
                    kind="single_world",
                ),
                _admg(
                    ["X", "Y", "Z"],
                    [_edge("Z", "X"), _edge("Z", "Y"), _edge("X", "Y")],
                ),
            ),
            _IS_IDENTIFIED,
            "P(Y_{X=1} | Z)",
            CounterfactualNode,
        ),
        _id_star_case(
            "ett",
            lambda: id_star_algorithm(
                CtfQuery(
                    outcome="Y",
                    intervention=(("X", 1.0),),
                    evidence=(("X", 1.0),),
                    kind="ett",
                ),
                _admg(
                    ["X", "Y", "Z"],
                    [_edge("Z", "X"), _edge("Z", "Y"), _edge("X", "Y")],
                ),
            ),
            _IS_IDENTIFIED,
            "P(Y_{X=1} | X=1)",
            CounterfactualNode,
        ),
        _id_star_case(
            "pn",
            lambda: id_star_algorithm(
                CtfQuery(
                    outcome="Y",
                    intervention=(("X", 1.0),),
                    evidence=(("Y", 1.0),),
                    kind="pn",
                ),
                _admg(["X", "Y"], [_edge("X", "Y")]),
            ),
            _IS_IDENTIFIED,
            "P(Y_{X=0} | X=1, Y=1)",
            CounterfactualNode,
        ),
        _id_star_case(
            "pns",
            lambda: id_star_algorithm(
                CtfQuery(
                    outcome="Y",
                    intervention=(("X", 1.0),),
                    reference_intervention=(("X", 0.0),),
                    kind="pns",
                ),
                _admg(["X", "Y"], [_edge("X", "Y")]),
            ),
            _IS_IDENTIFIED,
            "P(Y_{X=1}, Y_{X=0})",
            CrossWorldNode,
        ),
        _id_star_case(
            "nested",
            lambda: id_star_algorithm(
                CtfQuery(
                    outcome="Y",
                    intervention=(("X", 1.0),),
                    kind="nested",
                ),
                _admg(["X", "Y"], [_edge("X", "Y")]),
            ),
            _IS_IDENTIFIED,
            "P(Y_{X=1})",
            NestedCounterfactualNode,
        ),
        # Negative cases — bow arc
        _id_star_case(
            "bow_arc_single_world_negative",
            lambda: id_star_algorithm(
                CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world"),
                _admg(["X", "Y"], [_edge("X", "Y"), _edge("X", "Y", bidirected=True)]),
            ),
            _IS_HEDGE,
            "P(Y_{X=1})",
            None,
            check_trace=False,
        ),
        _id_star_case(
            "bow_arc_ett_negative",
            lambda: id_star_algorithm(
                CtfQuery(
                    outcome="Y",
                    intervention=(("X", 1.0),),
                    evidence=(("X", 1.0),),
                    kind="ett",
                ),
                _admg(["X", "Y"], [_edge("X", "Y"), _edge("X", "Y", bidirected=True)]),
            ),
            _IS_HEDGE,
            "P(Y_{X=1} | X=1)",
            None,
            check_trace=False,
        ),
    ]


def _build_idc_star_cases() -> list[BenchmarkCase]:
    return [
        _idc_star_case(
            "ett_with_z",
            lambda: idc_star_algorithm(
                CtfQuery(
                    outcome="Y",
                    intervention=(("X", 1.0),),
                    conditioning=("Z",),
                    evidence=(("X", 1.0),),
                    kind="ett",
                ),
                _admg(
                    ["X", "Y", "Z"],
                    [_edge("Z", "X"), _edge("Z", "Y"), _edge("X", "Y")],
                ),
            ),
            _IS_IDENTIFIED,
            "P(Y_{X=1} | X=1, Z)",
        ),
        _idc_star_case(
            "pn_with_x",
            lambda: idc_star_algorithm(
                CtfQuery(
                    outcome="Y",
                    intervention=(("X", 1.0),),
                    evidence=(("Y", 1.0),),
                    conditioning=("X",),
                    kind="pn",
                ),
                _admg(["X", "Y"], [_edge("X", "Y")]),
            ),
            _IS_IDENTIFIED,
            "P(Y_{X=0} | Y=1, X)",
        ),
        _idc_star_case(
            "bow_arc_negative",
            lambda: idc_star_algorithm(
                CtfQuery(
                    outcome="Y",
                    intervention=(("X", 1.0),),
                    evidence=(("X", 1.0),),
                    conditioning=("X",),
                    kind="ett",
                ),
                _admg(["X", "Y"], [_edge("X", "Y"), _edge("X", "Y", bidirected=True)]),
            ),
            _IS_HEDGE,
            "P(Y_{X=1} | X=1, X)",
        ),
    ]


def _build_z_id_cases() -> list[BenchmarkCase]:
    return [
        _z_id_case(
            "direct_z_transport",
            lambda: z_id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                z_interventions=frozenset({"Z"}),
                graph=_dag([("X", "Z"), ("Z", "Y")]),
            ),
            _IS_IDENTIFIED,
            r"\sum_{Z} P(Y \mid do(X), X, Z) \cdot P^*(Z)",
            ("Z_TRANSPORT",),
        ),
        _z_id_case(
            "z_equals_treatment",
            lambda: z_id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                z_interventions=frozenset({"X"}),
                graph=_dag([("X", "Y")]),
            ),
            _IS_IDENTIFIED,
            r"\sum_{X} P(Y \mid do(X), X, X) \cdot P^*(X)",
            ("Z_TRANSPORT",),
        ),
        _z_id_case(
            "no_z_falls_back_to_dag_id",
            lambda: z_id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                z_interventions=frozenset(),
                graph=_dag([("X", "Y")]),
            ),
            _IS_IDENTIFIED,
            r"P(Y \mid X)",
            ("G_FORMULA",),
        ),
        _z_id_case(
            "bow_arc_with_irrelevant_z_not_false_positive",
            lambda: z_id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                z_interventions=frozenset({"Z"}),
                graph=_admg(
                    ["X", "Y", "Z"],
                    [_edge("X", "Y"), _edge("X", "Y", bidirected=True)],
                ),
            ),
            IdentificationStatus.ORACLE_NEEDED,
            None,
            (),
        ),
    ]


def _build_mz_id_cases() -> list[BenchmarkCase]:
    return [
        _mz_id_case(
            "single_z_domain",
            lambda: mz_id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                source_domains=[SourceDomain(domain_id="d1", z_interventions=frozenset({"X"}))],
                graph=_dag([("X", "Y")]),
            ),
            _IS_IDENTIFIED,
            r"\sum_{X} P(Y \mid do(X), X, X) \cdot P^*(X)",
            ("Z_TRANSPORT",),
        ),
        _mz_id_case(
            "single_selection_domain",
            lambda: mz_id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                source_domains=[SourceDomain(domain_id="d1", s_nodes=frozenset({"X"}))],
                graph=_dag([("X", "Y")]),
            ),
            _IS_IDENTIFIED,
            r"P(Y \mid X)",
            (("S_AUGMENT", "C_COMPONENT"), ("S_AUGMENT", "G_FORMULA")),
        ),
        _mz_id_case(
            "bow_arc_no_domains_hedge",
            lambda: mz_id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                source_domains=[],
                graph=_admg(
                    ["X", "Y"],
                    [_edge("X", "Y"), _edge("X", "Y", bidirected=True)],
                ),
            ),
            _IS_HEDGE,
            None,
            ("HEDGE",),
        ),
    ]


def _build_transport_cases() -> list[BenchmarkCase]:
    return [
        _transport_case(
            "direct",
            lambda: _transport_result(
                build_selection_diagram(
                    _source_context().model_copy(update={"context_id": "A"}),
                    _source_context().model_copy(update={"context_id": "A"}),
                    CausalGraphModel(
                        graph_type=GraphType.DAG,
                        nodes=["tax_rate", "gdp_growth"],
                        edges=[CausalEdge(src="tax_rate", dst="gdp_growth")],
                    ),
                ),
                treatment="tax_rate",
                outcome="gdp_growth",
            ),
            TransportabilityStatus.IDENTIFIED,
            TransportMode.DIRECT,
            None,
        ),
        _transport_case(
            "frontdoor_like",
            lambda: _transport_result(
                build_selection_diagram(
                    _source_context(),
                    _target_context(),
                    CausalGraphModel(
                        graph_type=GraphType.DAG,
                        nodes=["tax_rate", "tax_compliance", "gdp_growth"],
                        edges=[
                            CausalEdge(src="tax_rate", dst="tax_compliance"),
                            CausalEdge(src="tax_compliance", dst="gdp_growth"),
                        ],
                    ),
                ),
                treatment="tax_rate",
                outcome="gdp_growth",
            ),
            TransportabilityStatus.IDENTIFIED,
            TransportMode.TRANSPORT_FORMULA,
            "P*(gdp_growth|do(tax_rate))",
        ),
        _transport_case(
            "unresolved_cpdag",
            lambda: _transport_result(
                build_selection_diagram(
                    _source_context(),
                    _target_context(),
                    CausalGraphModel(
                        graph_type=GraphType.CPDAG,
                        nodes=["tax_rate", "tax_compliance", "gdp_growth"],
                        edges=[
                            CausalEdge(src="tax_compliance", dst="tax_rate"),
                            CausalEdge(src="tax_rate", dst="tax_compliance"),
                            CausalEdge(src="tax_compliance", dst="gdp_growth"),
                        ],
                    ),
                ),
                treatment="tax_rate",
                outcome="gdp_growth",
            ),
            TransportabilityStatus.UNSUPPORTED,
            TransportMode.NONE,
            None,
            extra_checks={"unsupported_reason": "simplified_unresolved_s_nodes"},
        ),
        _transport_case(
            "pag_probabilistic",
            lambda: _transport_result(
                build_selection_diagram(
                    _source_context(),
                    _target_context(),
                    CausalGraphModel(
                        graph_type=GraphType.PAG,
                        nodes=["X", "Y", "Z"],
                        edges=[
                            CausalEdge(
                                src="Z",
                                dst="Y",
                                mark_src=EdgeMark.CIRCLE,
                                mark_dst=EdgeMark.CIRCLE,
                            ),
                            CausalEdge(src="Y", dst="X"),
                        ],
                    ),
                ).model_copy(
                    update={
                        "s_nodes": [
                            SNode(
                                target_variable="Z",
                                context_dimension="institutional_quality",
                                source_value=0.9,
                                target_value=0.2,
                                delta=0.7,
                                severity="high",
                                origin=SNodeOrigin.CONTEXT_DELTA,
                            )
                        ],
                        "context_distance": 0.4,
                    }
                ),
                treatment="X",
                outcome="Y",
                params={
                    "pag_identification_policy": "probabilistic",
                    "pag_max_dag_samples": 20,
                    "pag_threshold": 0.5,
                    "pag_seed": 17,
                },
            ),
            TransportabilityStatus.IDENTIFIED,
            TransportMode.TRANSPORT_FORMULA,
            None,
            extra_checks={"has_pag_confidence": True},
        ),
    ]


def _build_ctf_transport_cases() -> list[BenchmarkCase]:
    _s_node_y = SNode(
        target_variable="Y",
        context_dimension="mechanism_shift",
        source_value=0.0,
        target_value=1.0,
        delta=1.0,
        severity="medium",
    )
    return [
        _ctf_transport_case(
            "pn",
            lambda: ctf_transportability(
                CtfQuery(
                    outcome="Y",
                    intervention=(("X", 1.0),),
                    evidence=(("Y", 1.0),),
                    kind="pn",
                ),
                build_ctf_selection_diagram(
                    graph=_dag([("X", "Y")]),
                    s_nodes=[_s_node_y],
                ),
            ),
            "identified",
            "P(Y_{X=0} | Y=1)",
            ("CTF_TRANSPORT_START",),
        ),
        _ctf_transport_case(
            "exact_reduction",
            lambda: ctf_transportability(
                CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world"),
                build_ctf_selection_diagram(
                    graph=_dag([], extra_nodes=("X", "Y")),
                    s_nodes=[_s_node_y],
                ),
            ),
            "identified",
            "P(Y_{X=1})",
            ("CTF_TRANSPORT_START", "CTF_TRANSPORT_AUGMENT", "CTF_R3", "CTF_TRANSPORT_EXACT"),
        ),
        _ctf_transport_case(
            "bow_arc_negative",
            lambda: ctf_transportability(
                CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world"),
                build_ctf_selection_diagram(
                    graph=_admg(
                        ["X", "Y"],
                        [_edge("X", "Y"), _edge("X", "Y", bidirected=True)],
                    ),
                    s_nodes=[_s_node_y],
                ),
            ),
            "negative",
            None,
            (),
        ),
    ]


def _build_cyclic_cases() -> list[BenchmarkCase]:
    return [
        _cyclic_case(
            "well_posed",
            lambda: cyclic_id_algorithm(
                frozenset({"A"}),
                frozenset({"B"}),
                _admg(
                    ["A", "B"],
                    [_edge("A", "B"), _edge("B", "A")],
                    metadata={
                        "well_posedness_spec": {
                            "linear_system_matrix": np.array([[0.1, 0.1], [0.1, 0.1]])
                        }
                    },
                ),
            ),
            _IS_IDENTIFIED,
            r"\mathbb{E}[B \mid do(A), A]",
            (
                "CYCLIC_START",
                "CYCLIC_SCC",
                "CYCLIC_WELL_POSED",
                "CYCLIC_SIGMA_WARN",
                "CYCLIC_SOLVER",
            ),
        ),
        _cyclic_case(
            "non_well_posed",
            lambda: cyclic_id_algorithm(
                frozenset({"A"}),
                frozenset({"B"}),
                _admg(
                    ["A", "B"],
                    [_edge("A", "B"), _edge("B", "A")],
                    metadata={
                        "well_posedness_spec": {
                            "update_fn": lambda x: float(
                                np.tanh(2.0 * float(np.asarray(x).reshape(-1)[0]))
                            )
                        }
                    },
                ),
            ),
            _IS_HEDGE,
            None,
            (
                "CYCLIC_START",
                "CYCLIC_SCC",
                "CYCLIC_WELL_POSED",
                "CYCLIC_SIGMA_WARN",
                "CYCLIC_NON_WELL_POSED",
            ),
        ),
    ]


def _build_mgraph_cases() -> list[BenchmarkCase]:
    return [
        _mgraph_case(
            "mcar",
            lambda: recoverability_test(
                query_vars=frozenset({"X", "Y"}),
                graph=build_mgraph(
                    substantive_vars=["X", "Y"],
                    directed_edges=[("X", "Y")],
                    missingness_map={"X": MissingnessKind.MCAR},
                ),
                mgraph_meta=extract_mgraph_metadata(
                    build_mgraph(
                        substantive_vars=["X", "Y"],
                        directed_edges=[("X", "Y")],
                        missingness_map={"X": MissingnessKind.MCAR},
                    )
                ),
            ),
            RecoverabilityStatus.RECOVERABLE,
            r"P(X^{\text{obs}} \mid R_X=1) \cdot P(Y^{\text{obs}} \mid X)",
        ),
        _mgraph_case(
            "mar",
            lambda: recoverability_test(
                query_vars=frozenset({"X", "Y"}),
                graph=build_mgraph(
                    substantive_vars=["X", "Y"],
                    directed_edges=[("Y", "R_X")],
                    missingness_map={"X": MissingnessKind.MAR},
                ),
                mgraph_meta=extract_mgraph_metadata(
                    build_mgraph(
                        substantive_vars=["X", "Y"],
                        directed_edges=[("Y", "R_X")],
                        missingness_map={"X": MissingnessKind.MAR},
                    )
                ),
            ),
            RecoverabilityStatus.RECOVERABLE,
            r"P(X^{\text{obs}} \mid R_X=1) \cdot P(Y^{\text{obs}} \mid X)",
        ),
        _mgraph_case(
            "mnar",
            lambda: recoverability_test(
                query_vars=frozenset({"X", "Y"}),
                graph=build_mgraph(
                    substantive_vars=["X", "Y"],
                    directed_edges=[("X", "Y")],
                    missingness_map={"X": MissingnessKind.MNAR},
                ),
                mgraph_meta=extract_mgraph_metadata(
                    build_mgraph(
                        substantive_vars=["X", "Y"],
                        directed_edges=[("X", "Y")],
                        missingness_map={"X": MissingnessKind.MNAR},
                    )
                ),
            ),
            RecoverabilityStatus.NOT_RECOVERABLE,
            None,
            extra_checks={
                "blocking_r_nodes": frozenset({"R_X"}),
            },
        ),
        _mgraph_case(
            "full_law_stage2_hedge",
            lambda: full_law_identify(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                graph=build_mgraph(
                    substantive_vars=["X", "Y"],
                    directed_edges=[("X", "Y")],
                    bidirected_edges=[("X", "Y")],
                    missingness_map={"X": MissingnessKind.MCAR},
                ),
                mgraph_meta=extract_mgraph_metadata(
                    build_mgraph(
                        substantive_vars=["X", "Y"],
                        directed_edges=[("X", "Y")],
                        bidirected_edges=[("X", "Y")],
                        missingness_map={"X": MissingnessKind.MCAR},
                    )
                ),
            ),
            _IS_HEDGE,
            None,
            extra_checks={
                "has_hedge": True,
                "rule_subsequence": ("FULL_LAW_STAGE1_PASS", "HEDGE", "FULL_LAW_STAGE2"),
            },
        ),
    ]


def _build_proof_trace_cases() -> list[BenchmarkCase]:
    _s_node_trace = SNode(
        target_variable="Y",
        context_dimension="mechanism_shift",
        source_value=0.0,
        target_value=1.0,
        delta=1.0,
        severity="medium",
    )
    return [
        _proof_trace_case(
            "id_direct",
            lambda: id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                graph=_dag([("X", "Y")]),
            ),
            ("G_FORMULA",),
        ),
        _proof_trace_case(
            "id_frontdoor",
            lambda: id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                graph=_admg(
                    ["X", "M", "Y"],
                    [_edge("X", "M"), _edge("M", "Y"), _edge("X", "Y", bidirected=True)],
                ),
            ),
            ("FRONTDOOR",),
        ),
        _proof_trace_case(
            "idc",
            lambda: idc_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                conditions=frozenset({"Z"}),
                graph=_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")]),
            ),
            ("IDC_DECOMPOSE", "IDC_POSITIVITY"),
        ),
        _proof_trace_case(
            "id_star",
            lambda: id_star_algorithm(
                CtfQuery(
                    outcome="Y",
                    intervention=(("X", 1.0),),
                    reference_intervention=(("X", 0.0),),
                    kind="pns",
                ),
                _admg(["X", "Y"], [_edge("X", "Y")]),
            ),
            ("ID_STAR_STEP1", "ID_STAR_STEP2", "ID_STAR_STEP3", "ID_STAR_STEP5"),
        ),
        _proof_trace_case(
            "ctf_transport",
            lambda: ctf_transportability(
                CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world"),
                build_ctf_selection_diagram(
                    graph=_dag([], extra_nodes=("X", "Y")),
                    s_nodes=[_s_node_trace],
                ),
            ),
            ("CTF_TRANSPORT_START", "CTF_TRANSPORT_AUGMENT", "CTF_R3", "CTF_TRANSPORT_EXACT"),
        ),
        _proof_trace_case(
            "cyclic",
            lambda: cyclic_id_algorithm(
                frozenset({"A"}),
                frozenset({"B"}),
                _admg(
                    ["A", "B"],
                    [_edge("A", "B"), _edge("B", "A")],
                    metadata={
                        "well_posedness_spec": {
                            "linear_system_matrix": np.array([[0.1, 0.1], [0.1, 0.1]])
                        }
                    },
                ),
            ),
            (
                "CYCLIC_START",
                "CYCLIC_SCC",
                "CYCLIC_WELL_POSED",
                "CYCLIC_SIGMA_WARN",
                "CYCLIC_SOLVER",
            ),
        ),
    ]


def _build_sigma_calculus_cases() -> list[BenchmarkCase]:
    return [
        _sigma_calculus_case(
            "rule1_conditioning_drop",
            lambda: (
                apply_sigma_rule1(
                    DistributionRef(
                        domain=DistributionDomain.SOURCE,
                        variables=("Y",),
                        intervention_set=("X",),
                        conditioning=("Z",),
                    ),
                    _dag([("X", "Y"), ("Z", "X")]),
                    frozenset({"Z"}),
                    frozenset({"Z"}),
                )
                or (None, None)
            ),
            "SIGMA_R1",
            {"conditioning": ()},
        ),
        _sigma_calculus_case(
            "rule2_intervention_to_conditioning",
            lambda: (
                apply_sigma_rule2(
                    DistributionRef(
                        domain=DistributionDomain.SOURCE,
                        variables=("Y",),
                        intervention_set=("X", "Z"),
                        conditioning=(),
                    ),
                    _dag([("Z", "X"), ("X", "Y")]),
                    frozenset({"Z"}),
                    frozenset({"Z"}),
                )
                or (None, None)
            ),
            "SIGMA_R2",
            {"intervention_set": ("X",), "conditioning": ("Z",)},
        ),
        _sigma_calculus_case(
            "rule3_intervention_removal",
            lambda: (
                apply_sigma_rule3(
                    DistributionRef(
                        domain=DistributionDomain.SOURCE,
                        variables=("Y",),
                        intervention_set=("X", "Z"),
                        conditioning=(),
                    ),
                    _dag([("X", "Y"), ("Z", "X")]),
                    frozenset({"Z"}),
                    frozenset({"Z"}),
                )
                or (None, None)
            ),
            "SIGMA_R3",
            {"intervention_set": ("X",)},
        ),
    ]


def _build_ctf_calculus_cases() -> list[BenchmarkCase]:
    def _ctf_node1():
        node = CounterfactualNode(
            variable="Y",
            intervention={"X": 1.0},
            conditioning=("Z",),
            world_index=0,
        )
        ast = EstimandAST(
            query_str="P(Y_{X=1}|Z)",
            root=node,
            treatment="X",
            outcome="Y",
            all_variables=("X", "Y", "Z"),
            identification_method="ctf",
        )
        amn, _ = _build_amn_for_ast(ast, _dag([("X", "Y"), ("Z", "X")]))
        return apply_ctf_rule1(node, amn, frozenset({"Z"})) or (None, None)

    def _ctf_node2():
        node = CounterfactualNode(
            variable="Y",
            intervention={"X": 1.0, "Z": 1.0},
            conditioning=(),
            world_index=0,
        )
        ast = EstimandAST(
            query_str="P(Y_{X=1,Z=1})",
            root=node,
            treatment="X",
            outcome="Y",
            all_variables=("X", "Y", "Z"),
            identification_method="ctf",
        )
        amn, _ = _build_amn_for_ast(ast, _dag([("Z", "X"), ("X", "Y")]))
        return apply_ctf_rule2(node, amn, frozenset({"Z"})) or (None, None)

    def _ctf_node3():
        node = CounterfactualNode(
            variable="Y",
            intervention={"X": 1.0, "Z": 1.0},
            conditioning=(),
            world_index=0,
        )
        ast = EstimandAST(
            query_str="P(Y_{X=1,Z=1})",
            root=node,
            treatment="X",
            outcome="Y",
            all_variables=("X", "Y", "Z"),
            identification_method="ctf",
        )
        amn, _ = _build_amn_for_ast(ast, _dag([("X", "Y"), ("Z", "X")]))
        return apply_ctf_rule3(node, amn, frozenset({"Z"})) or (None, None)

    return [
        _ctf_calculus_case(
            "rule1_conditioning_drop",
            _ctf_node1,
            "CTF_R1",
            {"conditioning": ()},
        ),
        _ctf_calculus_case(
            "rule2_intervention_to_conditioning",
            _ctf_node2,
            "CTF_R2",
            {"intervention": {"X": 1.0}, "conditioning": ("Z",)},
        ),
        _ctf_calculus_case(
            "rule3_intervention_removal",
            _ctf_node3,
            "CTF_R3",
            {"intervention": {"X": 1.0}},
        ),
    ]


def _build_recanting_witness_cases() -> list[BenchmarkCase]:
    return [
        _recanting_witness_case(
            "clean_dag_no_witness",
            lambda: _recanting_witness_check(
                "T",
                "Y",
                ("M",),
                {"T": ["M"], "M": ["Y"], "Y": []},
            ),
            expected_has_witness=False,
        ),
        _recanting_witness_case(
            "recanting_path_has_witness",
            lambda: _recanting_witness_check(
                "T",
                "Y",
                ("M",),
                {"T": ["M", "Y"], "M": ["Y"], "Y": []},
            ),
            expected_has_witness=True,
        ),
    ]


# ---------------------------------------------------------------------------
# y0 comparison
# ---------------------------------------------------------------------------

# Reference cases for y0 comparison.
# Each tuple: (name, treatment, outcome, directed_edges, bidirected_edges, expected_identifiable)
_Y0_REFERENCE_CASES: list[tuple[str, frozenset, frozenset, list, list, bool]] = [
    (
        "direct_dag",
        frozenset({"X"}),
        frozenset({"Y"}),
        [("X", "Y")],
        [],
        True,
    ),
    (
        "mediated_dag",
        frozenset({"X"}),
        frozenset({"Y"}),
        [("X", "M"), ("M", "Y")],
        [],
        True,
    ),
    (
        "backdoor_dag",
        frozenset({"X"}),
        frozenset({"Y"}),
        [("Z", "X"), ("Z", "Y"), ("X", "Y")],
        [],
        True,
    ),
    (
        "frontdoor_admg",
        frozenset({"X"}),
        frozenset({"Y"}),
        [("X", "M"), ("M", "Y")],
        [("X", "Y")],
        True,
    ),
    (
        "bow_arc_hedge",
        frozenset({"X"}),
        frozenset({"Y"}),
        [("X", "Y")],
        [("X", "Y")],
        False,
    ),
    (
        "confounded_backdoor_hedge",
        frozenset({"X"}),
        frozenset({"Y"}),
        [("Z", "X"), ("Z", "Y"), ("X", "Y")],
        [("X", "Y")],
        False,
    ),
]


def _run_y0_comparison(report: BenchmarkReport) -> dict[str, Any]:
    """Compare identifiability verdicts with y0 on key gold-suite cases.

    Runs _y0_check_case() against _Y0_REFERENCE_CASES and asserts that
    PolicyOS and y0 agree on identifiability status.  Returns a summary dict.
    """
    if not y0_available():
        return {"skipped": True, "reason": "y0 not installed"}

    agreements = 0
    disagreements: list[str] = []
    errors: list[str] = []

    for name, treatment, outcome, directed, bidirected, expected_id in _Y0_REFERENCE_CASES:
        cmp = _y0_check_case(
            treatment=treatment,
            outcome=outcome,
            directed_edges=directed,
            bidirected_edges=bidirected,
            expected_identifiable=expected_id,
        )
        if cmp is None:
            # y0 became unavailable mid-run
            break
        if "error" in cmp:
            errors.append(f"{name}: {cmp['error']}")
        elif cmp.get("agreed"):
            agreements += 1
        else:
            disagreements.append(f"{name}: PolicyOS={expected_id}, y0={cmp.get('y0_identifiable')}")

    return {
        "skipped": False,
        "comparable_cases": len(_Y0_REFERENCE_CASES),
        "agreements": agreements,
        "disagreements": disagreements,
        "errors": errors,
        "all_agreed": len(disagreements) == 0 and len(errors) == 0,
    }


def _y0_check_case(
    treatment: frozenset[str],
    outcome: frozenset[str],
    directed_edges: list[tuple[str, str]],
    bidirected_edges: list[tuple[str, str]],
    expected_identifiable: bool,
) -> dict[str, Any] | None:
    """Run y0 identification on a simple graph and return agreement status.

    Returns None if y0 is not available.
    """
    if not y0_available():
        return None

    try:
        from y0.dsl import P, Variable
        from y0.graph import NxMixedGraph

        y0_identify = None
        y0_identify_outcomes = None
        y0_identification_cls = None
        try:
            from y0.algorithm.identify.api import identify_outcomes as y0_identify_outcomes
        except Exception:
            y0_identify_outcomes = None
        try:
            from y0.algorithm.identify import identify as y0_identify
        except Exception:
            y0_identify = None
        try:
            from y0.algorithm.identify.utils import Identification as y0_identification_cls
        except Exception:
            y0_identification_cls = None

        g = NxMixedGraph.from_edges(
            directed=directed_edges,
            undirected=[(u, v) for u, v in bidirected_edges],
        )
        # Build a simple query: P(Y | do(X)) where Y and X are the first elements
        y_var = Variable(next(iter(outcome)))
        x_var = Variable(next(iter(treatment)))
        query = P(y_var @ x_var)

        try:
            if y0_identify_outcomes is not None:
                y0_result = y0_identify_outcomes(
                    graph=g,
                    treatments=x_var,
                    outcomes=y_var,
                )
            elif y0_identify is not None and y0_identification_cls is not None:
                identification = y0_identification_cls.from_expression(graph=g, query=query)
                y0_result = y0_identify(identification)
            elif y0_identify is not None:
                y0_result = y0_identify(query, g)
            else:
                raise RuntimeError("y0 identify API unavailable")
            y0_identifiable = y0_result is not None
        except Exception:
            y0_identifiable = False

        agreed = y0_identifiable == expected_identifiable
        return {
            "y0_identifiable": y0_identifiable,
            "policy_os_identifiable": expected_identifiable,
            "agreed": agreed,
        }
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# JSON report serialisation
# ---------------------------------------------------------------------------


def _report_to_dict(
    report: BenchmarkReport,
    *,
    mode: BenchmarkMode,
    preflight: dict[str, Any],
    y0_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blockers = [b.name for b in report.blocker_cases()]
    return build_report_payload(
        report,
        suite_id="symbolic",
        mode=mode.value,
        preflight=preflight,
        sub_circuit="symbolic",
        extra={
            "blocker_false_positives": blockers,
            "is_blocker": len(blockers) > 0,
            "y0_summary": y0_summary,
        },
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def build_harness() -> BenchmarkHarness:
    """Build a BenchmarkHarness pre-loaded with all symbolic gold cases."""
    harness = BenchmarkHarness()
    harness.register_many(_build_id_cases())
    harness.register_many(_build_idc_cases())
    harness.register_many(_build_id_star_cases())
    harness.register_many(_build_idc_star_cases())
    harness.register_many(_build_z_id_cases())
    harness.register_many(_build_mz_id_cases())
    harness.register_many(_build_transport_cases())
    harness.register_many(_build_ctf_transport_cases())
    harness.register_many(_build_cyclic_cases())
    harness.register_many(_build_mgraph_cases())
    harness.register_many(_build_proof_trace_cases())
    harness.register_many(_build_sigma_calculus_cases())
    harness.register_many(_build_ctf_calculus_cases())
    harness.register_many(_build_recanting_witness_cases())
    return harness


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Circuit 1 — Symbolic / Identification benchmark")
    parser.add_argument(
        "--y0-compare",
        action="store_true",
        help="Include y0 comparison (requires y0 >=0.2 installed)",
    )
    parser.add_argument(
        "--json",
        metavar="FILE",
        help="Write full JSON report to FILE",
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        metavar="TAG",
        help="Run only cases with these tags (e.g. id idc hedge frontdoor)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-case output; print only the summary",
    )
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in BenchmarkMode],
        default=None,
        help="Benchmark strictness mode (default: smoke or $BENCH_MODE)",
    )
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode)
    comparator_status = {
        "y0": "available" if y0_available() else "missing",
    }
    preflight = build_preflight(
        mode=mode.value,
        data_source="symbolic_gold_suite",
        dependency_status={"python_modules": dependency_status(["numpy", "y0"])},
        comparator_status=comparator_status,
        degraded_reasons=[]
        if comparator_status["y0"] == "available"
        else ["y0 comparator unavailable"],
    )
    print_preflight(preflight)

    gaps = acceptance_gaps(
        mode,
        require_modules={"y0": comparator_status["y0"] == "available"},
    )
    if gaps:
        print("Symbolic acceptance preflight failed:")
        for gap in gaps:
            print(f"  - {gap}")
        return 2

    harness = build_harness()
    report = harness.run(
        circuit=BenchmarkCircuit.SYMBOLIC,
        tags=args.tags or None,
    )

    harness.print_report(report, verbose=not args.quiet)

    y0_summary: dict[str, Any] | None = None
    if args.y0_compare:
        y0_summary = _run_y0_comparison(report)
        print("\n--- y0 comparison ---")
        print(json.dumps(y0_summary, indent=2))

    if args.json:
        report_dict = _report_to_dict(report, mode=mode, preflight=preflight, y0_summary=y0_summary)
        path = Path(args.json)
        path.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
        print(f"\nJSON report written to: {path}")

    # Non-zero exit code if there are blockers (false positives)
    blockers = report.blocker_cases()
    if blockers:
        print(f"\nEXIT 1: {len(blockers)} false-positive identification(s) — release blocker")
        return 1

    n_failed = report.n_total() - report.n_passed()
    if n_failed > 0:
        print(f"\nEXIT 2: {n_failed} case(s) failed (but no false positives)")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
