"""Standard evaluation metrics for PolicyOS benchmark results.

All functions operate on plain Python types — no framework dependencies.
"""

from __future__ import annotations

import dataclasses
import math
import statistics
from typing import Sequence


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class TimingStats:
    n: int
    mean_s: float
    std_s: float
    min_s: float
    max_s: float
    p50_s: float
    p95_s: float

    def __str__(self) -> str:
        return (
            f"n={self.n}  mean={self.mean_s*1000:.2f}ms  "
            f"p50={self.p50_s*1000:.2f}ms  p95={self.p95_s*1000:.2f}ms  "
            f"min={self.min_s*1000:.2f}ms  max={self.max_s*1000:.2f}ms"
        )


def compute_timing_stats(elapsed_times: Sequence[float]) -> TimingStats:
    """Compute timing statistics from a sequence of elapsed times (seconds)."""
    if not elapsed_times:
        return TimingStats(n=0, mean_s=0.0, std_s=0.0, min_s=0.0, max_s=0.0, p50_s=0.0, p95_s=0.0)
    samples = sorted(elapsed_times)
    n = len(samples)
    mean = statistics.mean(samples)
    std = statistics.stdev(samples) if n > 1 else 0.0
    p50 = _percentile(samples, 50)
    p95 = _percentile(samples, 95)
    return TimingStats(
        n=n,
        mean_s=mean,
        std_s=std,
        min_s=samples[0],
        max_s=samples[-1],
        p50_s=p50,
        p95_s=p95,
    )


def _percentile(sorted_data: list[float], pct: float) -> float:
    """Linear-interpolation percentile on sorted data."""
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    rank = (pct / 100.0) * (n - 1)
    lo = int(rank)
    hi = min(lo + 1, n - 1)
    frac = rank - lo
    return sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo])


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class MemoryStats:
    n: int
    mean_mb: float
    peak_mb: float
    std_mb: float

    def __str__(self) -> str:
        return (
            f"n={self.n}  mean={self.mean_mb:.2f}MB  "
            f"peak={self.peak_mb:.2f}MB  std={self.std_mb:.2f}MB"
        )


def compute_memory_stats(memory_deltas_mb: Sequence[float]) -> MemoryStats:
    """Compute memory statistics from a sequence of RSS deltas (MB)."""
    if not memory_deltas_mb:
        return MemoryStats(n=0, mean_mb=0.0, peak_mb=0.0, std_mb=0.0)
    samples = list(memory_deltas_mb)
    n = len(samples)
    return MemoryStats(
        n=n,
        mean_mb=statistics.mean(samples),
        peak_mb=max(samples),
        std_mb=statistics.stdev(samples) if n > 1 else 0.0,
    )


# ---------------------------------------------------------------------------
# Accuracy / identification correctness
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class AccuracyMetrics:
    """Binary accuracy for identification correctness.

    Positive class = "system declares IDENTIFIED".
    Negative class = "system declares non-identifiable (HEDGE_FOUND etc.)".

    False positive: system says IDENTIFIED, ground truth says non-identifiable.
    False negative: system says non-identifiable, ground truth says IDENTIFIED.
    """

    n_total: int
    n_true_positive: int
    n_true_negative: int
    n_false_positive: int    # claimed identified, ground truth: non-identifiable — blocker
    n_false_negative: int    # claimed non-identifiable, ground truth: identifiable
    n_wrong_formula: int     # status correct but estimand formula mismatch

    @property
    def n_correct(self) -> int:
        return self.n_true_positive + self.n_true_negative

    @property
    def accuracy(self) -> float:
        return self.n_correct / self.n_total if self.n_total else 0.0

    @property
    def false_positive_rate(self) -> float:
        """FP / (FP + TN) — fraction of truly non-identifiable cases wrongly called identified."""
        denominator = self.n_false_positive + self.n_true_negative
        if denominator <= 0:
            return 0.0
        return self.n_false_positive / denominator

    def is_blocker(self) -> bool:
        """Phase 15 bar: any false positive is a blocker."""
        return self.n_false_positive > 0

    def __str__(self) -> str:
        pct = self.accuracy * 100
        fp = self.n_false_positive
        fn = self.n_false_negative
        wf = self.n_wrong_formula
        blocker = " [BLOCKER: FALSE POSITIVES]" if self.is_blocker() else ""
        return (
            f"{self.n_correct}/{self.n_total} correct ({pct:.1f}%)"
            f"  FP={fp}  FN={fn}  wrong_formula={wf}{blocker}"
        )


def compute_accuracy_metrics(
    cases: Sequence[tuple[bool, bool, bool]],
) -> AccuracyMetrics:
    """Compute identification accuracy.

    Parameters
    ----------
    cases:
        Each element is (ground_truth_identifiable, predicted_identifiable, formula_correct).
        ``formula_correct`` is only meaningful when both ground truth and predicted are
        identifiable; pass ``True`` otherwise.
    """
    n_total = len(cases)
    n_true_positive = 0
    n_true_negative = 0
    n_false_positive = 0
    n_false_negative = 0
    n_wrong_formula = 0

    for gt_id, pred_id, formula_ok in cases:
        if gt_id and pred_id:
            if formula_ok:
                n_true_positive += 1
            else:
                n_wrong_formula += 1
        elif (not gt_id) and (not pred_id):
            n_true_negative += 1
        elif pred_id and (not gt_id):
            n_false_positive += 1
        else:
            n_false_negative += 1

    return AccuracyMetrics(
        n_total=n_total,
        n_true_positive=n_true_positive,
        n_true_negative=n_true_negative,
        n_false_positive=n_false_positive,
        n_false_negative=n_false_negative,
        n_wrong_formula=n_wrong_formula,
    )


# ---------------------------------------------------------------------------
# Proof-step complexity
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ProofStepStats:
    n_cases: int
    mean_steps: float
    max_steps: int
    step_distribution: dict[str, int]  # rule_name -> total count across all cases

    def __str__(self) -> str:
        top = sorted(self.step_distribution.items(), key=lambda kv: -kv[1])[:5]
        top_str = "  ".join(f"{k}:{v}" for k, v in top)
        return (
            f"cases={self.n_cases}  mean_steps={self.mean_steps:.1f}  "
            f"max={self.max_steps}  top_rules=[{top_str}]"
        )


def compute_proof_step_stats(
    proof_step_sequences: Sequence[list[str]],
) -> ProofStepStats:
    """Aggregate proof-step statistics across multiple identification runs."""
    if not proof_step_sequences:
        return ProofStepStats(n_cases=0, mean_steps=0.0, max_steps=0, step_distribution={})

    counts: dict[str, int] = {}
    step_counts: list[int] = []
    for seq in proof_step_sequences:
        step_counts.append(len(seq))
        for rule in seq:
            counts[rule] = counts.get(rule, 0) + 1

    return ProofStepStats(
        n_cases=len(proof_step_sequences),
        mean_steps=statistics.mean(step_counts),
        max_steps=max(step_counts),
        step_distribution=counts,
    )


# ---------------------------------------------------------------------------
# Composite benchmark score
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class CircuitScore:
    """Aggregate score for one benchmark circuit."""

    circuit_name: str
    n_cases: int
    n_passed: int
    accuracy: AccuracyMetrics | None
    timing: TimingStats | None
    memory: MemoryStats | None
    proof_steps: ProofStepStats | None

    @property
    def pass_rate(self) -> float:
        return self.n_passed / self.n_cases if self.n_cases else 0.0

    def __str__(self) -> str:
        lines = [
            f"Circuit: {self.circuit_name}",
            f"  Pass rate : {self.n_passed}/{self.n_cases} ({self.pass_rate*100:.1f}%)",
        ]
        if self.accuracy is not None:
            lines.append(f"  Accuracy  : {self.accuracy}")
        if self.timing is not None:
            lines.append(f"  Timing    : {self.timing}")
        if self.memory is not None:
            lines.append(f"  Memory    : {self.memory}")
        if self.proof_steps is not None:
            lines.append(f"  ProofSteps: {self.proof_steps}")
        return "\n".join(lines)
