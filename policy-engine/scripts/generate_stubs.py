#!/usr/bin/env python3
"""
Generate type stub (.pyi) files for the Foundry Methods public API.

This script:
1. Runs ``mypy.stubgen`` on the three most-used modules.
2. Post-processes the output to remove private ``_*`` exports.
3. Copies the cleaned stubs alongside the source modules.

Usage::

    cd policy-engine
    python scripts/generate_stubs.py [--dry-run] [--verbose]

Requirements:
    mypy must be installed: pip install mypy

Output files:
    src/polisyos/foundry/methods/base.pyi
    src/polisyos/foundry/methods/registry.pyi
    src/polisyos/foundry/methods/composer.pyi
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_SRC = _REPO_ROOT / "src"
_TARGETS = [
    "polisyos.foundry.methods.base",
    "polisyos.foundry.methods.registry",
    "polisyos.foundry.methods.composer",
]

# Output location mirrors the source tree
_OUTPUT_MAP = {
    "polisyos.foundry.methods.base": _SRC / "polisyos" / "foundry" / "methods" / "base.pyi",
    "polisyos.foundry.methods.registry": _SRC / "polisyos" / "foundry" / "methods" / "registry.pyi",
    "polisyos.foundry.methods.composer": _SRC / "polisyos" / "foundry" / "methods" / "composer.pyi",
}


def _run_stubgen(module: str, out_dir: Path, verbose: bool) -> Path | None:
    """Run stubgen for *module*, return the generated .pyi path or None."""
    cmd = [
        sys.executable, "-m", "mypy.stubgen",
        "-m", module,
        "-o", str(out_dir),
        "--no-analysis",
        "--export-less",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  stubgen failed for {module}:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return None

    # Stubgen writes to out_dir/<module/path>.pyi
    relative = module.replace(".", os.sep) + ".pyi"
    candidate = out_dir / relative
    if not candidate.exists():
        print(f"  Expected stub not found: {candidate}", file=sys.stderr)
        return None

    if verbose:
        print(f"  stubgen → {candidate}")
    return candidate


def _remove_private_exports(content: str) -> str:
    """
    Strip lines that:
    - define ``_*`` names (private helpers, internal state)
    - import private names from other modules

    Keeps type aliases and ``__all__``.
    """
    cleaned: list[str] = []
    for line in content.splitlines():
        # Remove private assignment stubs: _FOO: int = ...
        if re.match(r"^_\w+\s*:", line) and not line.startswith("__"):
            continue
        # Remove private def stubs: def _foo(...):
        if re.match(r"^def _\w+", line) and not line.startswith("def __"):
            continue
        # Remove private class stubs
        if re.match(r"^class _\w+", line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    # Ensure src is on sys.path
    sys.path.insert(0, str(_SRC))

    print("Generating type stubs for Foundry Methods public API ...")

    with tempfile.TemporaryDirectory(prefix="foundry_stubs_") as tmpdir:
        out_dir = Path(tmpdir)

        for module in _TARGETS:
            print(f"\n  Processing {module} ...")
            stub_path = _run_stubgen(module, out_dir, verbose=args.verbose)
            if stub_path is None:
                print(f"  SKIP: could not generate stub for {module}")
                continue

            raw_content = stub_path.read_text()
            cleaned = _remove_private_exports(raw_content)

            target = _OUTPUT_MAP[module]
            if args.dry_run:
                print(f"  [dry-run] Would write {len(cleaned)} chars to {target}")
            else:
                target.write_text(cleaned, encoding="utf-8")
                print(f"  Wrote → {target}")

    if not args.dry_run:
        print("\nStubs generated. Run 'mypy --strict polisyos.foundry.methods' to validate.")
    else:
        print("\n[dry-run] No files written.")


if __name__ == "__main__":
    main()
