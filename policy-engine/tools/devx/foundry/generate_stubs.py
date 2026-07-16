"""Generate Foundry method stubs through the canonical tools surface."""

from __future__ import annotations

import argparse
import ast
import re
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from tools.lib.fs import atomic_write_text
from tools.lib.imports import repo_root_from
from tools.lib.runner import run_command

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
TARGETS: tuple[str, ...] = (
    "polisyos.foundry.methods.base",
    "polisyos.foundry.methods.registry",
    "polisyos.foundry.methods.composer",
)
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
}
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
    launcher = (
        (str(stubgen),)
        if stubgen.is_file()
        else (sys.executable, "-m", "mypy.stubgen")
    )
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
    if not candidate.exists():
        print(f"  Expected stub not found: {candidate}", file=sys.stderr)
        return None
    if verbose:
        print(f"  stubgen -> {candidate}")
    return candidate


def _remove_private_exports(content: str) -> str:
    """Drop private data exports without orphaning definition bodies.

    Private classes and functions remain non-exported by normal ``.pyi``
    semantics.  Keeping their complete blocks is safer than deleting only a
    definition header, which can silently re-parent members or produce an
    invalid stub.
    """

    cleaned: list[str] = []
    for line in content.splitlines():
        if re.match(r"^_\w+\s*:", line) and not line.startswith("__"):
            continue
        cleaned.append(line)
    return "\n".join(cleaned) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print actions without writing files"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show generated stub paths")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))

    print("Generating type stubs for Foundry Methods public API ...")
    failed: list[str] = []
    with tempfile.TemporaryDirectory(prefix="foundry_stubs_") as tmpdir:
        out_dir = Path(tmpdir)
        for module in TARGETS:
            print(f"\n  Processing {module} ...")
            reexport_stub = REEXPORT_STUBS.get(module)
            if reexport_stub is not None:
                cleaned = reexport_stub
            else:
                stub_path = _run_stubgen(module, out_dir, verbose=args.verbose)
                if stub_path is None:
                    print(f"  SKIP: could not generate stub for {module}")
                    failed.append(module)
                    continue
                cleaned = _remove_private_exports(stub_path.read_text(encoding="utf-8"))
            target = OUTPUT_MAP[module]
            try:
                ast.parse(cleaned, filename=str(target))
            except SyntaxError as exc:
                print(f"  Invalid generated stub for {module}: {exc}", file=sys.stderr)
                failed.append(module)
                continue
            if args.dry_run:
                print(f"  [dry-run] Would write {len(cleaned)} chars to {target}")
            else:
                atomic_write_text(target, cleaned, encoding="utf-8")
                print(f"  Wrote -> {target}")

    if failed:
        print(f"\nStub generation failed for: {', '.join(failed)}", file=sys.stderr)
        return 1
    if args.dry_run:
        print("\n[dry-run] No files written.")
    else:
        print("\nStubs generated. Run 'mypy --strict polisyos.foundry.methods' to validate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
