"""CLI entrypoint for the Ukraine Part B production build stack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from polisyos.ukraine_data.models import StageId
from polisyos.ukraine_data.orchestrator import UkraineDataOrchestrator, load_pipeline_config


def _parse_stage(value: str) -> StageId:
    normalized = value.strip().lower().replace("-", "_")
    if normalized == "full":
        return StageId.FULL
    if normalized == "release":
        return StageId.RELEASE
    try:
        return StageId(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"unknown stage: {value}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ukraine-data",
        description="Server-only production data/build stack for Ukraine Part B.",
    )
    parser.add_argument("--config", type=Path, default=None, help="Path to JSON pipeline config.")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Override build root for manifests and artifacts.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser(
        "bootstrap-server", help="Prepare server layout and capability manifests."
    )
    bootstrap.add_argument(
        "--write-capabilities",
        action="store_true",
        help="Write the server capability manifest during bootstrap.",
    )

    subparsers.add_parser("validate-part-a", help="Run the server-side Part A integration gate.")

    build = subparsers.add_parser("build", help="Build one Part B stage or the full pipeline.")
    build.add_argument(
        "stage", type=_parse_stage, help="Stage id: d0-p0, d1, d2, d3, d4, d5, full."
    )
    build.add_argument(
        "--resume", action="store_true", help="Reuse a completed stage if outputs still exist."
    )

    resume = subparsers.add_parser("resume", help="Resume one stage from an existing manifest.")
    resume.add_argument("stage", type=_parse_stage, help="Stage id: d0-p0, d1, d2, d3, d4, d5.")

    validate = subparsers.add_parser(
        "validate", help="Validate outputs recorded by a completed stage manifest."
    )
    validate.add_argument("stage", type=_parse_stage, help="Stage id: d0-p0, d1, d2, d3, d4, d5.")

    release = subparsers.add_parser("release", help="Build or resume the final D5 release bundle.")
    release.add_argument(
        "--resume", action="store_true", help="Reuse an existing completed D5 build."
    )

    return parser


def _emit(payload: object) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_pipeline_config(args.config, root=args.root)
    orchestrator = UkraineDataOrchestrator(config)

    if args.command == "bootstrap-server":
        summary = orchestrator.bootstrap_server(write_capabilities=args.write_capabilities)
        _emit(summary.manifest.model_dump(mode="json"))
        return 0 if summary.status == "completed" else 1

    if args.command == "validate-part-a":
        summary = orchestrator.validate_part_a()
        _emit(summary.manifest.model_dump(mode="json"))
        return 0 if summary.status == "passed" else 1

    if args.command == "build":
        if args.stage == StageId.FULL:
            summaries = orchestrator.build_full(resume=args.resume)
            _emit([summary.manifest.model_dump(mode="json") for summary in summaries])
            return 0 if summaries and summaries[-1].status == "completed" else 1
        summary = orchestrator.build_stage(args.stage, resume=args.resume)
        _emit(summary.manifest.model_dump(mode="json"))
        return 0 if summary.status == "completed" else 1

    if args.command == "resume":
        summary = orchestrator.build_stage(args.stage, resume=True)
        _emit(summary.manifest.model_dump(mode="json"))
        return 0 if summary.status == "completed" else 1

    if args.command == "validate":
        summary = orchestrator.validate_stage_outputs(args.stage)
        _emit(summary.manifest.model_dump(mode="json"))
        return 0 if summary.status == "completed" else 1

    if args.command == "release":
        summary = orchestrator.release(resume=args.resume)
        _emit(summary.manifest.model_dump(mode="json"))
        return 0 if summary.status == "completed" else 1

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
