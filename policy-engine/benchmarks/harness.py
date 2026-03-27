"""Unified benchmark harness — 6-circuit testing framework.

Circuits
--------
1. SYMBOLIC      — Identification correctness against the symbolic gold suite.
                   100% accuracy required; any false positive is a blocker.
2. ESTIMATION    — Numerical estimation accuracy vs. known ground-truth DGPs.
3. DISCOVERY     — Causal discovery consistency (skeleton + orientation scores).
4. CAPABILITY    — Unique capability wins (counterfactuals, transportability, etc.)
5. REPRODUCIBILITY — Result stability across runs and seeds.
6. COMPARISON    — Head-to-head comparison with reference implementations (y0, DoWhy).

Usage
-----
    harness = BenchmarkHarness()
    harness.register(BenchmarkCase(...))
    report = harness.run(circuit=BenchmarkCircuit.SYMBOLIC)
    harness.print_report(report)
"""

from __future__ import annotations

import dataclasses
import enum
import os
import resource
import sys
import time
import traceback
from typing import Any, Callable, Sequence

_TIMEOUT_MULTIPLIER: float = float(os.environ.get("BENCH_TIMEOUT_MULTIPLIER", "1.0"))

from benchmarks.metrics import (
    AccuracyMetrics,
    CircuitScore,
    MemoryStats,
    ProofStepStats,
    TimingStats,
    compute_accuracy_metrics,
    compute_memory_stats,
    compute_proof_step_stats,
    compute_timing_stats,
)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class BenchmarkCircuit(str, enum.Enum):
    SYMBOLIC = "symbolic"           # Circuit 1 — Identification correctness
    ESTIMATION = "estimation"       # Circuit 2 — Numerical estimation accuracy
    HTE = "hte"                     # Circuit 3 — HTE / policy learning
    DISCOVERY = "discovery"         # Circuit 4 — Discovery consistency
    MISSING = "missing"             # Circuit 5 — Missing-data / recoverability
    TRANSPORT = "transport"         # Circuit 6 — Transportability / data fusion / CTF
    CAPABILITY_WINS = "capability_wins"  # Supporting demos outside the core six
    REPRODUCIBILITY = "repro"       # Supporting reproducibility / governance suite
    COMPARISON = "comparison"       # Optional reference-implementation comparison
    CAPABILITY = "capability"       # Legacy alias retained for backward compatibility


class Verdict(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"       # unexpected exception
    TIMEOUT = "TIMEOUT"   # exceeded timeout_s
    SKIP = "SKIP"         # skipped (e.g. optional dependency missing)


class BenchmarkSkip(RuntimeError):
    """Signal that a benchmark case was intentionally skipped."""


# ---------------------------------------------------------------------------
# Case definition
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class BenchmarkCase:
    """A single benchmark case registered with the harness.

    Parameters
    ----------
    name:
        Unique identifier for the case (e.g. "id::direct_dag").
    circuit:
        Which of the 6 circuits this case belongs to.
    runner:
        Zero-argument callable that executes the algorithm and returns a result.
    checker:
        Callable that receives the runner's return value and returns True if the
        result is correct.  Raise AssertionError with a descriptive message on
        failure — the harness will capture it.
    proof_step_extractor:
        Optional callable to extract a list of rule-name strings from the result
        (for proof-step statistics).
    is_identifiable_ground_truth:
        For SYMBOLIC circuit cases only: whether the ground truth is identifiable.
        Used to detect false positives (the blocker condition).
    is_identifiable_extractor:
        For SYMBOLIC circuit cases only: callable that receives the result and
        returns True if the system predicted IDENTIFIED.
    formula_correct_extractor:
        Optional callable returning True if the formula is correct (only called
        when both ground truth and predicted are identifiable).
    tags:
        Arbitrary labels for filtering (e.g. "id", "idc", "frontdoor").
    timeout_s:
        Wall-clock timeout per case run (default: 30 s).
    """

    name: str
    circuit: BenchmarkCircuit
    runner: Callable[[], Any]
    checker: Callable[[Any], bool]
    proof_step_extractor: Callable[[Any], list[str]] | None = None
    is_identifiable_ground_truth: bool | None = None
    is_identifiable_extractor: Callable[[Any], bool] | None = None
    formula_correct_extractor: Callable[[Any], bool] | None = None
    tags: tuple[str, ...] = ()
    timeout_s: float = 30.0


# ---------------------------------------------------------------------------
# Per-case result
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class CaseResult:
    """Result of running a single BenchmarkCase."""

    name: str
    circuit: BenchmarkCircuit
    verdict: Verdict
    elapsed_s: float
    memory_delta_mb: float
    proof_steps: list[str] = dataclasses.field(default_factory=list)
    error_msg: str | None = None
    result_payload: Any | None = None
    # Identification-specific fields (SYMBOLIC circuit)
    is_identifiable_gt: bool | None = None
    is_identifiable_pred: bool | None = None
    formula_correct: bool | None = None

    @property
    def passed(self) -> bool:
        return self.verdict is Verdict.PASS

    def one_line(self) -> str:
        status = self.verdict.value.ljust(7)
        t_ms = f"{self.elapsed_s * 1000:.1f}ms"
        mem = f"{self.memory_delta_mb:+.1f}MB"
        steps = f"steps={len(self.proof_steps)}" if self.proof_steps else ""
        err = f"  [{self.error_msg[:60]}]" if self.error_msg else ""
        return f"  [{status}] {self.name:<55} {t_ms:>8}  {mem:>8}  {steps}{err}"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class BenchmarkReport:
    """Aggregated results for one or more circuits."""

    circuits: list[BenchmarkCircuit]
    cases: list[CaseResult]
    circuit_scores: dict[str, CircuitScore]

    @property
    def results(self) -> list[CaseResult]:
        """Backward-compatible alias for older benchmark entrypoints."""
        return self.cases

    def n_passed(self) -> int:
        return sum(1 for c in self.cases if c.passed)

    def n_total(self) -> int:
        return len(self.cases)

    def blocker_cases(self) -> list[CaseResult]:
        """False-positive identification cases — release blockers."""
        return [
            c for c in self.cases
            if c.is_identifiable_gt is False and c.is_identifiable_pred is True
        ]


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


class BenchmarkHarness:
    """Unified benchmark runner for all 6 circuits.

    Example
    -------
    >>> harness = BenchmarkHarness()
    >>> harness.register(BenchmarkCase(
    ...     name="id::direct_dag",
    ...     circuit=BenchmarkCircuit.SYMBOLIC,
    ...     runner=lambda: id_algorithm(...),
    ...     checker=lambda r: r.status is IdentificationStatus.IDENTIFIED,
    ... ))
    >>> report = harness.run()
    >>> harness.print_report(report)
    """

    def __init__(self) -> None:
        self._cases: list[BenchmarkCase] = []

    def register(self, case: BenchmarkCase) -> None:
        """Register a single benchmark case."""
        self._cases.append(case)

    def register_many(self, cases: Sequence[BenchmarkCase]) -> None:
        """Register multiple benchmark cases."""
        for case in cases:
            self._cases.append(case)

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------

    def run(
        self,
        circuit: BenchmarkCircuit | None = None,
        tags: Sequence[str] | None = None,
    ) -> BenchmarkReport:
        """Run all registered cases (optionally filtered by circuit / tags).

        Parameters
        ----------
        circuit:
            If given, only run cases for this circuit.
        tags:
            If given, only run cases that have at least one of these tags.
        """
        selected = self._filter(circuit, tags)
        results: list[CaseResult] = []
        for case in selected:
            results.append(self._run_case(case))

        circuits_in_report = (
            [circuit] if circuit else list({c.circuit for c in selected})
        )
        scores = self._compute_scores(results, circuits_in_report)

        return BenchmarkReport(
            circuits=circuits_in_report,
            cases=results,
            circuit_scores=scores,
        )

    def _filter(
        self,
        circuit: BenchmarkCircuit | None,
        tags: Sequence[str] | None,
    ) -> list[BenchmarkCase]:
        out = self._cases
        if circuit is not None:
            out = [c for c in out if c.circuit is circuit]
        if tags:
            tag_set = set(tags)
            out = [c for c in out if tag_set.intersection(c.tags)]
        return out

    def _run_case(self, case: BenchmarkCase) -> CaseResult:
        rss_before = _get_rss_mb()
        t0 = time.perf_counter()
        result_obj: Any = None
        verdict = Verdict.PASS
        error_msg: str | None = None
        proof_steps: list[str] = []

        try:
            result_obj = case.runner()
            passed = case.checker(result_obj)
            if not passed:
                verdict = Verdict.FAIL
                error_msg = "checker returned False"
        except BenchmarkSkip as exc:
            verdict = Verdict.SKIP
            error_msg = str(exc) or "Skipped"
        except AssertionError as exc:
            verdict = Verdict.FAIL
            error_msg = str(exc) or "AssertionError"
        except Exception:
            verdict = Verdict.ERROR
            error_msg = traceback.format_exc(limit=3).strip().splitlines()[-1]

        elapsed = time.perf_counter() - t0
        rss_after = _get_rss_mb()
        memory_delta = max(0.0, rss_after - rss_before)

        effective_timeout = case.timeout_s * _TIMEOUT_MULTIPLIER
        if effective_timeout > 0 and elapsed > effective_timeout:
            verdict = Verdict.TIMEOUT
            error_msg = f"elapsed {elapsed:.1f}s > timeout {effective_timeout:.1f}s (base {case.timeout_s}s × {_TIMEOUT_MULTIPLIER})"

        if result_obj is not None and case.proof_step_extractor is not None:
            try:
                proof_steps = case.proof_step_extractor(result_obj)
            except Exception:
                proof_steps = []

        # Identification correctness fields
        is_id_gt = case.is_identifiable_ground_truth
        is_id_pred: bool | None = None
        formula_ok: bool | None = None

        if result_obj is not None and case.is_identifiable_extractor is not None:
            try:
                is_id_pred = case.is_identifiable_extractor(result_obj)
            except Exception:
                pass

        if (
            result_obj is not None
            and is_id_gt is True
            and is_id_pred is True
            and case.formula_correct_extractor is not None
        ):
            try:
                formula_ok = case.formula_correct_extractor(result_obj)
            except Exception:
                formula_ok = False

        return CaseResult(
            name=case.name,
            circuit=case.circuit,
            verdict=verdict,
            elapsed_s=elapsed,
            memory_delta_mb=memory_delta,
            proof_steps=proof_steps,
            error_msg=error_msg,
            result_payload=result_obj,
            is_identifiable_gt=is_id_gt,
            is_identifiable_pred=is_id_pred,
            formula_correct=formula_ok,
        )

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _compute_scores(
        self,
        results: list[CaseResult],
        circuits: list[BenchmarkCircuit],
    ) -> dict[str, CircuitScore]:
        scores: dict[str, CircuitScore] = {}
        for circuit in circuits:
            circuit_results = [r for r in results if r.circuit is circuit]
            if not circuit_results:
                continue
            scores[circuit.value] = self._score_circuit(circuit, circuit_results)
        return scores

    def _score_circuit(
        self, circuit: BenchmarkCircuit, results: list[CaseResult]
    ) -> CircuitScore:
        n_passed = sum(1 for r in results if r.passed)

        timing: TimingStats | None = None
        memory: MemoryStats | None = None
        proof_step_stat: ProofStepStats | None = None
        accuracy: AccuracyMetrics | None = None

        # Timing (all circuits)
        elapsed_list = [r.elapsed_s for r in results]
        timing = compute_timing_stats(elapsed_list)

        # Memory (all circuits)
        mem_list = [r.memory_delta_mb for r in results]
        memory = compute_memory_stats(mem_list)

        # Proof steps (when available)
        step_seqs = [r.proof_steps for r in results if r.proof_steps]
        if step_seqs:
            proof_step_stat = compute_proof_step_stats(step_seqs)

        # Identification accuracy (SYMBOLIC circuit)
        if circuit is BenchmarkCircuit.SYMBOLIC:
            acc_triples: list[tuple[bool, bool, bool]] = []
            for r in results:
                gt = r.is_identifiable_gt
                pred = r.is_identifiable_pred
                if gt is not None and pred is not None:
                    formula_ok = r.formula_correct if r.formula_correct is not None else True
                    acc_triples.append((gt, pred, formula_ok))
            if acc_triples:
                accuracy = compute_accuracy_metrics(acc_triples)

        return CircuitScore(
            circuit_name=circuit.value,
            n_cases=len(results),
            n_passed=n_passed,
            accuracy=accuracy,
            timing=timing,
            memory=memory,
            proof_steps=proof_step_stat,
        )

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def print_report(self, report: BenchmarkReport, *, verbose: bool = True) -> None:
        sep = "=" * 72
        print(sep)
        print("  PolicyOS Benchmark Report")
        print(sep)

        for circuit_key, score in report.circuit_scores.items():
            print(f"\n{score}\n")

        if verbose:
            print(sep)
            print("  Per-case results")
            print(sep)
            prev_circuit = None
            for r in report.cases:
                if r.circuit != prev_circuit:
                    print(f"\n  -- {r.circuit.value.upper()} --")
                    prev_circuit = r.circuit
                print(r.one_line())

        # Blocker summary
        blockers = report.blocker_cases()
        if blockers:
            print(f"\n{'!'*72}")
            print(f"  BLOCKER: {len(blockers)} false-positive identification(s)")
            for b in blockers:
                print(f"    • {b.name}")
            print(f"{'!'*72}")

        overall = report.n_passed()
        total = report.n_total()
        pct = overall / total * 100 if total else 0.0
        print(f"\n  TOTAL: {overall}/{total} passed ({pct:.1f}%)\n")
        print(sep)


# ---------------------------------------------------------------------------
# System helpers
# ---------------------------------------------------------------------------


def _get_rss_mb() -> float:
    """Current RSS memory in MB.

    Prefer psutil for current-process RSS. Fall back to ru_maxrss when psutil
    is unavailable, accepting that the fallback measures peak RSS instead.
    """
    try:
        import psutil

        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)
    except Exception:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        if sys.platform == "darwin":
            return usage.ru_maxrss / (1024 * 1024)
        return usage.ru_maxrss / 1024
