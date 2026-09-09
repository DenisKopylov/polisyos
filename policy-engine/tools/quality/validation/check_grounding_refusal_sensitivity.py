"""Declare or recompute the full L6/WMR constructed-mismatch refusal suite."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from polisyos.core import artifacts
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.grounding_calibration import (
    CalibrationFrame,
    DeclaredRefusalSuite,
    GroundingEpochScope,
    build_owner_frame_inputs,
    build_refusal_reference_scaffold,
    declare_calibration_frame,
    declare_refusal_suite,
    difficulty_tier,
    run_refusal_suite,
    source_clusters,
)
from polisyos.runtime.quality.world_model_record import load_world_model_record

OUTPUT_PATH = "architecture/policy_design_case/corr/grounding_refusal_sensitivity.json"


def declared_outputs() -> list[str]:
    """Return the run result, excluding immutable controlling declarations."""
    return [OUTPUT_PATH]


def main() -> int:
    """Keep declaration and execution as separate explicit invocations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--declare", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--world-cas", type=Path, required=True)
    parser.add_argument("--world-ref", required=True)
    parser.add_argument("--declarations", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=Path(OUTPUT_PATH))
    args = parser.parse_args()
    if sum((args.declare, args.check, args.write)) != 1:
        parser.error("choose exactly one of --declare, --write or --check")
    root = args.repo_root.resolve()
    if not args.world_cas.exists():
        from polisyos.runtime.quality.intervention_substrate import (
            production_composed_world_model_record,
        )

        # Reuse the canonical builder; never replace missing source with a fixture.
        production_composed_world_model_record(root)
    world = load_world_model_record(artifacts.FileSystemCAS(args.world_cas), args.world_ref)
    inputs, sources = build_owner_frame_inputs(root, world, domain=world.policy_domain)
    reference = build_refusal_reference_scaffold(root, world)
    paths = {name: args.declarations / f"{name}.json" for name in ("frame", "suite")}
    if args.declare:
        if any(path.exists() for path in paths.values()):
            raise ValueError("declarations_already_exist_append_a_new_campaign")
        # Deterministic input-only first eligible stratum; no CG1/CG2 decisions run here.
        eligible = sorted(
            {
                (row.operator_family, row.target_type, row.domain, difficulty_tier(row))
                for row in inputs
                if row.ambiguity is None and row.operator_family and row.target_type
            }
        )
        if not eligible:
            raise ValueError("no_eligible_input_stratum_established")
        now = datetime.now(UTC)
        frame = declare_calibration_frame(
            inputs,
            source_refs=sources,
            selected_stratum=eligible[0],
            declared_at=now,
            epoch_scope=GroundingEpochScope(
                proposer_model="owner_input_projection_no_model",
                prompt_version="no_prompt",
                atom_birth_cohort="2026-09-08-owner-inputs",
                reference_epoch=reference.reference_epoch,
            ),
        )
        suite = declare_refusal_suite(frame, reference, declared_at=now)
        args.declarations.mkdir(parents=True, exist_ok=True)
        paths["frame"].write_text(frame.model_dump_json(indent=2) + "\n")
        paths["suite"].write_text(suite.model_dump_json(indent=2) + "\n")
        print(
            json.dumps(
                {
                    "stage": "declared_not_executed",
                    "frame_hash": frame.content_hash,
                    "suite_hash": suite.content_hash,
                    "complete_input_denominator": len(inputs),
                    "source_clusters": len(source_clusters(inputs)),
                    "predeclared_mismatches": len(suite.mismatches),
                    "ambiguous_inputs": list(suite.ambiguous_inputs),
                    "limitation": suite.limitation,
                },
                sort_keys=True,
            )
        )
        return 0
    frame = CalibrationFrame.model_validate_json(paths["frame"].read_bytes())
    suite = DeclaredRefusalSuite.model_validate_json(paths["suite"].read_bytes())
    current_frame = declare_calibration_frame(
        inputs,
        source_refs=sources,
        selected_stratum=frame.selected_stratum,
        epoch_scope=frame.epoch_scope,
        declared_at=frame.declared_at,
    )
    if current_frame.content_hash != frame.content_hash:
        raise ValueError("complete_owner_frame_content_drift")
    retained = json.loads(args.report.read_bytes()) if args.check else None
    report = run_refusal_suite(
        suite,
        frame,
        reference,
        executed_at=datetime.fromisoformat(retained["executed_at"]) if retained else None,
    )
    issues = list(report["issues"])
    if args.check and retained != report:
        issues.append("persisted_refusal_result_drift")
    if args.write:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": "fail" if issues else "pass",
                "issues": issues,
                "result_path": str(args.report),
                "result_hash": gy_content_hash(report),
                "suite_hash": suite.content_hash,
                "statement": report["statement"],
            },
            sort_keys=True,
        )
    )
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
