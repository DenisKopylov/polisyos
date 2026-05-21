#!/usr/bin/env python3
"""Validate Policy Design Case formal invariant specs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.formal_invariants import (  # noqa: E402
    FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH,
    build_formal_invariant_spec_report,
    dump_formal_invariant_report_json,
    render_formal_invariant_report_text,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--registry",
        type=Path,
        default=FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH,
        help="Path to architecture/policy_design_case/formal_invariant_specs.toml",
    )
    parser.add_argument(
        "--output-format",
        choices=("json", "text"),
        default="text",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = build_formal_invariant_spec_report(
        repo_root=args.repo_root,
        registry_path=args.registry,
    )
    rendered = (
        dump_formal_invariant_report_json(report)
        if args.output_format == "json"
        else render_formal_invariant_report_text(report)
    )
    if args.output is not None:
        atomic_write_text(args.output, rendered)
    else:
        sys.stdout.write(rendered)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
