"""CLI sub-module: lex normpack build and impact analysis commands."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS

__all__ = [
    "_cmd_lex_normpack_build",
    "_cmd_lex_impact",
]


def _validate_output_extension(output_path: str | None, output_format: str) -> None:
    if not output_path:
        return
    expected = ".json" if output_format == "json" else ".md"
    suffix = Path(output_path).suffix.lower()
    if suffix and suffix != expected:
        raise ValueError(
            f"output extension '{suffix}' does not match --format {output_format!r} "
            f"(expected '{expected}')"
        )


def _cmd_lex_normpack_build(args: Any) -> int:
    lex_api = importlib.import_module("polisyos.lex.api")
    lex_types = importlib.import_module("polisyos.lex.types")
    assemble_norm_pack = lex_api.assemble_norm_pack
    NormPackBuildRequest = lex_types.NormPackBuildRequest

    cas = FileSystemCAS(Path(args.cas_root))
    fact_log_root = Path(args.fact_log_root)
    request = NormPackBuildRequest(
        jurisdiction=args.jurisdiction,
        as_of=args.as_of,
        domain=args.domain,
    )

    result = assemble_norm_pack(
        cas=cas,
        fact_log_root=fact_log_root,
        request=request,
    )
    print(f"norm_pack_artifact_id={result.norm_pack_artifact_id}")
    print(f"norm_pack_world_id={result.norm_pack_world_id}")
    print(f"built_by={result.built_by}")
    return 0


def _cmd_lex_impact(args: Any) -> int:
    try:
        _validate_output_extension(args.output, args.format)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    lex_sim = importlib.import_module("polisyos.lex.simulator")
    lex_sim_cli = importlib.import_module("polisyos.lex.simulator.cli")
    governance_profiles = importlib.import_module("polisyos.scientist.governance.profiles")

    ValidationProfile = governance_profiles.ValidationProfile
    profile = getattr(ValidationProfile, args.profile)()

    pass_ids = tuple(
        token.strip()
        for token in str(args.passes).split(",")
        if token.strip()
    )
    if not pass_ids:
        print("ERROR: --passes cannot be empty", file=sys.stderr)
        return 2

    cas = FileSystemCAS(Path(args.cas_root))
    try:
        old_pack = lex_sim_cli.load_norm_pack(cas, args.old_ref)
        new_pack = lex_sim_cli.load_norm_pack(cas, args.new_ref)
    except Exception as exc:
        print(f"ERROR: failed to load NormPack(s): {exc}", file=sys.stderr)
        return 1

    analyzer = lex_sim.NormImpactAnalyzer(
        cas=cas,
        profile=profile,
        passes=pass_ids,
    )
    report = analyzer.analyze(old_pack, new_pack)

    rendered: str
    if args.format == "json":
        rendered = report.model_dump_json(indent=2)
    else:
        rendered = lex_sim_cli.render_impact_markdown(report)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"impact_report={args.output}")
    else:
        print(rendered)
    return 0
