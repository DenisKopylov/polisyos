"""Phase-0 seed benchmark for truth-centric synthetic worlds."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_BENCH_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _BENCH_ROOT / "src"
for _path in (str(_SRC), str(_BENCH_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from benchmarks.harness import BenchmarkCase, BenchmarkCircuit, BenchmarkHarness
from benchmarks.reporting import build_preflight, build_report_payload, print_preflight
from benchmarks.runtime import resolve_mode, resolve_tier
from polisyos.synthetic_world import (
    SyntheticWorld,
    SyntheticWorldDGP,
    WorldFamily,
    phase0_seed_benchmark_binding,
    phase0_seed_world_specs,
)

SUITE_ID = "synthetic_world_seed"
BENCHMARK_FAMILY = "synthetic_world"
LITERATURE_ANCHOR = [
    "Phase 0 / Track 23.1 — ground-truth synthetic worlds (seed benchmark infra).",
    "Synthetic-world contract: observed artifact + truth manifest + deterministic replay surface.",
]


def _required_targets(spec: SyntheticWorldDGP) -> set[str]:
    if spec.family is WorldFamily.CROSS_SECTIONAL:
        return {
            "causal.ate",
            "bayesian.exact_posterior",
            "bayesian.prior_params",
            "bayesian.latent_states_true",
            "survey.base_weights",
            "survey.design_variance",
            "distributional.quantile.p90",
            "ml.classification.probability",
        }
    if spec.family is WorldFamily.SURVEY_REPEATED_CROSS_SECTION:
        return {
            "survey.design_effect",
            "survey.design_variance",
            "survey.response_probabilities",
            "survey.calibrated_weights",
            "econometrics.wave_effects",
            "forecast.h1.mean",
            "bayesian.reference_posterior",
            "bayesian.posterior_predictive_reference",
        }
    if spec.family is WorldFamily.PANEL_DYNAMIC:
        return {
            "causal.dynamic_ate",
            "causal.dynamic_regime_value",
            "econometrics.panel_fe",
            "econometrics.iv_late",
            "econometrics.irf",
            "forecast.h3.mean",
            "distributional.quantile.p90",
            "bayesian.reference_posterior",
            "bayesian.posterior_predictive_reference",
        }
    return {
        "causal.spatial_ate",
        "forecast.h3.mean",
        "distributional.pdf",
        "distributional.quantile.p90",
        "regime.labels",
        "bayesian.reference_posterior",
        "bayesian.latent_states_true",
    }


def _run_case(spec: SyntheticWorldDGP) -> dict[str, Any]:
    world = SyntheticWorld.from_spec(spec)
    sample = world.sample(split="train")
    truth = world.truth()
    replay = SyntheticWorld.from_spec(spec)
    replay_sample = replay.sample(split="train")
    replay_truth = replay.truth()

    deterministic_replay = (
        sample.model_dump(mode="json") == replay_sample.model_dump(mode="json")
        and truth.model_dump(mode="json") == replay_truth.model_dump(mode="json")
    )
    required = _required_targets(spec)
    available = set(truth.available_targets)
    missing_targets = sorted(required - available)

    return {
        "world_id": spec.world_id,
        "family": spec.family.value,
        "config_hash": spec.config_hash(),
        "metadata": dict(spec.metadata),
        "sample_rows": int(sample.row_count),
        "available_targets": list(truth.available_targets),
        "required_targets": sorted(required),
        "missing_targets": missing_targets,
        "all_required_targets_present": not missing_targets,
        "deterministic_replay": deterministic_replay,
        "measurement_summary": sample.metadata.get("measurement", {}),
        "missingness_summary": sample.metadata.get("missingness", {}),
    }


def _check_case(payload: dict[str, Any]) -> bool:
    if int(payload.get("sample_rows") or 0) <= 0:
        raise AssertionError("synthetic world emitted zero observed rows")
    if not bool(payload.get("all_required_targets_present")):
        raise AssertionError(
            f"missing truth targets: {', '.join(payload.get('missing_targets') or [])}"
        )
    if not bool(payload.get("deterministic_replay")):
        raise AssertionError("synthetic world failed deterministic replay under the same seed")
    return True


def _build_report(mode: str, *, quiet: bool) -> dict[str, Any]:
    binding = phase0_seed_benchmark_binding()
    harness = BenchmarkHarness()
    for case_id, spec in zip(binding.case_ids, phase0_seed_world_specs(), strict=True):
        harness.register(
            BenchmarkCase(
                name=case_id,
                circuit=BenchmarkCircuit.ESTIMATION,
                runner=lambda spec=spec: _run_case(spec),
                checker=_check_case,
                tags=("phase0", BENCHMARK_FAMILY, spec.family.value),
                timeout_s=15.0,
            )
        )

    report = harness.run(circuit=BenchmarkCircuit.ESTIMATION)
    preflight = build_preflight(
        mode=mode,
        benchmark_tier=resolve_tier(mode=resolve_mode(mode)).value,
        data_source="synthetic_suite",
        dataset_family=BENCHMARK_FAMILY,
    )
    if not quiet:
        print_preflight(preflight)

    case_payloads = [
        case.result_payload for case in report.cases if isinstance(case.result_payload, dict)
    ]
    aggregate_metrics = {
        "target_coverage_rate": float(
            sum(1 for payload in case_payloads if payload.get("all_required_targets_present"))
            / max(len(case_payloads), 1)
        ),
        "deterministic_replay_rate": float(
            sum(1 for payload in case_payloads if payload.get("deterministic_replay"))
            / max(len(case_payloads), 1)
        ),
    }

    return build_report_payload(
        report,
        suite_id=SUITE_ID,
        mode=mode,
        preflight=preflight,
        sub_circuit="synthetic_world",
        benchmark_family=BENCHMARK_FAMILY,
        proof_class="publication_benchmark",
        literature_anchor=LITERATURE_ANCHOR,
        aggregate_metrics=aggregate_metrics,
        case_details_builder=lambda case: case.result_payload if isinstance(case.result_payload, dict) else {},
        extra={
            "binding": binding.model_dump(mode="json"),
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase-0 synthetic-world seed benchmark")
    parser.add_argument("--mode", default="smoke")
    parser.add_argument("--json", default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    payload = _build_report(args.mode, quiet=args.quiet)
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.json:
        Path(args.json).write_text(rendered + "\n", encoding="utf-8")
    if not args.quiet:
        print(rendered)
    return 0 if payload.get("overall_status") in {"passed", "over_budget", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
