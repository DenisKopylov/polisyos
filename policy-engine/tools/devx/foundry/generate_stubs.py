"""Generate or compare the complete Foundry method stub family."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from tools.lib.fs import (
    atomic_write_text,
    measure_file_reads,
    measured_is_file,
    measured_read_bytes,
    measured_read_text,
)
from tools.lib.imports import repo_root_from
from tools.lib.runner import run_command

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
OUTPUT_MAP: dict[str, Path] = {
    "polisyos.foundry.methods.base": SRC_ROOT / "polisyos" / "foundry" / "methods" / "base.pyi",
    "polisyos.foundry.methods.registry": SRC_ROOT
    / "polisyos"
    / "foundry"
    / "methods"
    / "registry.pyi",
    "polisyos.foundry.methods.composer": SRC_ROOT
    / "polisyos"
    / "foundry"
    / "methods"
    / "composer.pyi",
    "polisyos.foundry.methods.components.composer": SRC_ROOT
    / "polisyos"
    / "foundry"
    / "methods"
    / "components"
    / "composer.pyi",
}
TARGETS: tuple[str, ...] = tuple(OUTPUT_MAP)
REEXPORT_STUBS: dict[str, str] = {
    "polisyos.foundry.methods.registry": (
        "from polisyos.foundry.methods.selection.registry import *\n"
    ),
    "polisyos.foundry.methods.composer": (
        "from polisyos.foundry.methods.components.composer import *\n"
    ),
}


def _run_stubgen(module: str, out_dir: Path, *, verbose: bool) -> Path | None:
    stubgen = Path(sys.executable).with_name("stubgen")
    launcher = (str(stubgen),) if stubgen.is_file() else (sys.executable, "-m", "mypy.stubgen")
    cmd = (
        *launcher,
        "-m",
        module,
        "-o",
        str(out_dir),
        "--no-analysis",
        "--export-less",
    )
    result = run_command(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(f"  stubgen failed for {module}:", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return None
    candidate = out_dir / (module.replace(".", "/") + ".pyi")
    if not measured_is_file(candidate):
        print(f"  Expected stub not found: {candidate}", file=sys.stderr)
        return None
    if verbose:
        print(f"  stubgen -> {candidate}")
    return candidate


def _remove_private_exports(content: str) -> str:
    """Drop private data exports without orphaning definition bodies."""
    cleaned: list[str] = []
    for line in content.splitlines():
        if re.match(r"^_\w+\s*:", line) and not line.startswith("__"):
            continue
        cleaned.append(line)
    return "\n".join(cleaned) + "\n"


def _render_stubs(out_dir: Path, *, verbose: bool) -> dict[Path, str] | None:
    """Render every declared output before any committed or staged write."""
    rendered: dict[Path, str] = {}
    failed: list[str] = []
    for module, target in OUTPUT_MAP.items():
        print(f"  Processing {module}")
        cleaned = REEXPORT_STUBS.get(module)
        if cleaned is None:
            stub_path = _run_stubgen(module, out_dir, verbose=verbose)
            if stub_path is None:
                failed.append(module)
                continue
            try:
                cleaned = _remove_private_exports(measured_read_text(stub_path))
            except (OSError, UnicodeError) as exc:
                print(f"  Unable to read generated stub for {module}: {exc}", file=sys.stderr)
                failed.append(module)
                continue
        try:
            ast.parse(cleaned, filename=str(target))
        except SyntaxError as exc:
            print(f"  Invalid generated stub for {module}: {exc}", file=sys.stderr)
            failed.append(module)
            continue
        rendered[target] = cleaned
    if failed:
        print(f"Stub generation failed for: {', '.join(failed)}", file=sys.stderr)
        return None
    return rendered


def _execute(args: argparse.Namespace) -> tuple[int, str]:
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))
    output_root = args.output_root.resolve() if args.output_root is not None else REPO_ROOT
    print(f"Foundry stub family: {len(OUTPUT_MAP)} declared outputs; root={output_root}")
    with tempfile.TemporaryDirectory(prefix="foundry_stubs_") as tmpdir:
        rendered = _render_stubs(Path(tmpdir), verbose=args.verbose)
        if rendered is None:
            return 1, "ERROR"
        if args.dry_run:
            for target in rendered:
                print(f"  [dry-run] Would write {output_root / target.relative_to(REPO_ROOT)}")
            print("Generation completed; freshness comparison UNRUN; no output files written.")
            return 0, "UNRUN"
        if args.check:
            stale: list[Path] = []
            unreadable: list[Path] = []
            for target, content in rendered.items():
                comparison = output_root / target.relative_to(REPO_ROOT)
                try:
                    actual = measured_read_bytes(comparison)
                except OSError as exc:
                    print(f"  UNREADABLE {comparison}: {type(exc).__name__}", file=sys.stderr)
                    unreadable.append(comparison)
                    continue
                if actual != content.encode("utf-8"):
                    print(f"  STALE {comparison}", file=sys.stderr)
                    stale.append(comparison)
                else:
                    print(f"  CURRENT {comparison}")
            if unreadable:
                print(
                    "Freshness comparison ERROR: declared outputs could not all be read.",
                    file=sys.stderr,
                )
                return 1, "ERROR"
            if stale:
                print("Freshness comparison FAIL: generated bytes differ.", file=sys.stderr)
                return 1, "FAIL"
            print("Freshness comparison PASS: every declared output is byte-identical.")
            return 0, "PASS"
        for target, content in rendered.items():
            destination = output_root / target.relative_to(REPO_ROOT)
            atomic_write_text(destination, content, encoding="utf-8")
            print(f"  Wrote {destination}")
        print("Stubs generated; freshness comparison UNRUN.")
        return 0, "UNRUN"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the existing stub owner in write, staged-write, dry-run or check mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="Render without writes or comparison")
    modes.add_argument(
        "--check", action="store_true", help="Regenerate and compare all output bytes"
    )
    parser.add_argument(
        "--output-root", type=Path, help="Stage outputs, or compare that staged tree"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show generated stub paths")
    args = parser.parse_args(list(argv) if argv is not None else None)
    outcome = "ERROR"
    with measure_file_reads(REPO_ROOT) as reads:
        try:
            result, outcome = _execute(args)
            return result
        finally:
            measurement = reads.snapshot(complete_verdict=outcome in {"PASS", "FAIL"})
            measurement["freshness_outcome"] = outcome
            measurement["selection"] = {
                "modules": list(OUTPUT_MAP),
                "declared_output_paths": [
                    str(path.relative_to(REPO_ROOT)) for path in OUTPUT_MAP.values()
                ],
                "denominator": len(OUTPUT_MAP),
                "output_root": str(args.output_root.resolve() if args.output_root else REPO_ROOT),
            }
            measurement["unresolved_by_construction"].append(
                "Stubgen subprocess source/import reads and dependency versions are not observed; "
                "byte equality covers only OUTPUT_MAP, not unlisted stubs or semantic type "
                "correctness."
            )
            print("Measurement: " + json.dumps(measurement, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
