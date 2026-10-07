"""Reproduce the existing DoE producer and fresh-process sensitivity reader packet."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
from polisyos.scientist.methods.autotune.sensitivity_bridge import SensitivityBridge
from polisyos.scientist.methods.doe._receipt import _load_analysis
from polisyos.scientist.methods.search.sensitivity_adapter import SensitivityAwareCandidateGenerator
from tests._helpers.artifacts import put_json_artifact


class _FixtureGenerator:
    """Supply candidates at the existing reader seam, without another search runtime."""

    def generate(
        self, history: list[object], current_best: object, context: dict[str, object]
    ) -> dict[str, float]:
        return {"x": 0.5, "z": 0.5}

    def generate_batch(
        self,
        history: list[object],
        current_best: object,
        context: dict[str, object],
        batch_size: int,
    ) -> list[dict[str, float]]:
        return [self.generate(history, current_best, context) for _ in range(batch_size)]


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def main() -> None:
    """Exercise producer or freshly resolve its persisted experiment and negative."""
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["produce", "read"])
    parser.add_argument("--cas-root", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    args = parser.parse_args()
    store = FileSystemCAS(args.cas_root)
    if args.mode == "produce":
        calls = 0

        def evaluator(parameters: dict[str, float]) -> float:
            nonlocal calls
            calls += 1
            x, z = parameters["x"], parameters["z"]
            return x + z + 2 * x * z

        produced = SensitivityBridge().analyze_search_space(
            [
                {"name": name, "lower": 0.0, "upper": 1.0, "unit": "dimensionless"}
                for name in ["x", "z"]
            ],
            evaluator,
            method="sobol",
            n_trajectories=1024,
            seed=31,
            input_law="independent",
            store=store,
            max_estimated_runs=6144,
        )
        result = produced["result"]
        _require(calls == result.total_runs == result.successful_runs == 6144, "Draw denominator")
        _require(result.failed_runs == 0, "Unexpected failed callback")
        # Independent ANOVA: Y=1.5+2Xc+2Zc+2XcZc. Orthogonal variances
        # 1/3,1/3,1/36 give total variance 25/36, without reading sampler results.
        truth = {"S1": 12 / 25, "S2": 1 / 25, "ST": 13 / 25}
        for name in ["x", "z"]:
            _require(math.isclose(result.s1[name], truth["S1"], abs_tol=0.01), "S1 ANOVA truth")
            _require(math.isclose(result.st[name], truth["ST"], abs_tol=0.01), "ST ANOVA truth")
        _require(math.isclose(result.s2["x"]["z"], truth["S2"], abs_tol=0.01), "S2 ANOVA truth")
        packet = {
            "analysis_ref": produced["analysis_ref"].model_dump(mode="json"),
            "callback_count": calls,
            "s1": result.s1,
            "s2": result.s2,
            "st": result.st,
            "truth": truth,
            "absolute_numerical_tolerance": 0.01,
            "design_id": result.metadata["design_id"],
            "analysis_id": result.metadata["analysis_id"],
            "ordered_samples_sha256": result.metadata["ordered_samples_sha256"],
            "ordered_outputs_sha256": result.metadata["ordered_outputs_sha256"],
            "analyzer": result.metadata["analyzer"],
            "denominator": {"requested": 6144, "observed": 6144, "failed": 0},
            "authority_purpose": "exploratory_parameter_experiment",
            "population_law_status": "not_established",
            "default_search": "bridge_missing; canonical owner D",
        }
        args.packet.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
        sys.stdout.write(json.dumps(packet, indent=2) + "\n")
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "read",
            "--cas-root",
            str(args.cas_root),
            "--packet",
            str(args.packet),
        ]
        subprocess.run(command, check=True)  # noqa: S603 - current interpreter and this saved script.
        return
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    ref = ArtifactRef.model_validate(packet["analysis_ref"])
    result = _load_analysis(store, ref)
    _require(result.metadata["analysis_id"] == packet["analysis_id"], "Fresh analysis identity")
    reader = SensitivityAwareCandidateGenerator.from_artifact(_FixtureGenerator(), store, ref)
    metadata = reader.generate([], None, {})["_sensitivity"]
    _require(metadata["analysis_ref"] == packet["analysis_ref"], "Consumed reference")
    _require(metadata["analysis_id"] == packet["analysis_id"], "Consumed analysis identity")
    _require(
        all(
            candidate["_sensitivity"] == metadata
            for candidate in reader.generate_batch([], None, {}, 2)
        ),
        "Batch consumer identity",
    )
    payload = json.loads(store.get_bytes(ref))
    payload["result"]["s2"]["x"]["z"] = 0.99
    fake_ref = put_json_artifact(store, payload, kind="doe_sensitivity_analysis")
    _require(store.verify(fake_ref).ok, "Forged artifact must have valid content integrity")
    try:
        SensitivityAwareCandidateGenerator.from_artifact(_FixtureGenerator(), store, fake_ref)
    except ValueError as exc:
        _require("does not reproduce" in str(exc), "Refusal must come from recomputation")
        sys.stdout.write(
            json.dumps({"fresh_process_readback": "PASS", "forged_interaction_refusal": str(exc)})
            + "\n"
        )
    else:
        raise AssertionError("Integrity-valid forged S2 was consumed")


if __name__ == "__main__":
    main()
