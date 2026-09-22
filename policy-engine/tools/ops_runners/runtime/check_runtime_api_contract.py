#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from tools.lib.imports import repo_root_from


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Runtime API contract drift and OpenAPI hardening invariants."
    )
    parser.add_argument(
        "--openapi",
        type=Path,
        default=Path("schemas/runtime_api_v1.openapi.json"),
        help="Committed OpenAPI JSON file to verify.",
    )
    parser.add_argument(
        "--skip-client-drift",
        action="store_true",
        help=(
            "Compatibility flag; generated client freshness is owned by the "
            "package generated-artifact guard."
        ),
    )
    parser.add_argument(
        "--max-diff-lines",
        type=int,
        default=120,
        help="Maximum number of unified diff lines to print for OpenAPI drift.",
    )
    return parser.parse_args()


def _ensure_src_on_path(repo_root: Path) -> None:
    src_root = repo_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _check_openapi_drift(*, repo_root: Path, openapi_path: Path, max_diff_lines: int) -> list[str]:
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.openapi_contract import validate_runtime_openapi_contract

    app = create_runtime_api_app(enable_security_middlewares=False)
    rendered = app.openapi()
    generated = _canonical_json(rendered)

    violations: list[str] = []
    if not openapi_path.exists():
        violations.append(f"Missing OpenAPI file: {openapi_path.as_posix()}")
    else:
        committed = openapi_path.read_text(encoding="utf-8")
        if committed != generated:
            violations.append(
                f"OpenAPI drift detected for {openapi_path.as_posix()}."
                " Regenerate with tools/ops_runners/runtime/export_runtime_openapi.py."
            )
            diff = list(
                difflib.unified_diff(
                    committed.splitlines(),
                    generated.splitlines(),
                    fromfile=f"{openapi_path.as_posix()} (committed)",
                    tofile=f"{openapi_path.as_posix()} (generated)",
                    lineterm="",
                )
            )
            for line in diff[:max_diff_lines]:
                print(line)
            if len(diff) > max_diff_lines:
                print(f"... truncated {len(diff) - max_diff_lines} additional diff lines ...")

    contract_violations = validate_runtime_openapi_contract(rendered)
    violations.extend(contract_violations)
    return violations


def _check_runtime_client_family_drift(
    *, repo_root: Path, openapi_path: Path
) -> list[str]:
    """Verify the package-owned generated family without a committed raw twin."""

    package_root = repo_root / "packages" / "runtime-api-client"
    expected_outputs = (
        "packages/runtime-api-client/types.ts",
        "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
        "packages/runtime-api-client/canonicalRuntimeApiClient.js",
    )
    violations: list[str] = []
    with tempfile.TemporaryDirectory(prefix="runtime_client_contract_") as tmp_dir_name:
        output_root = Path(tmp_dir_name)
        result = subprocess.run(
            [
                "corepack",
                "pnpm",
                "--dir",
                str(package_root),
                "run",
                "generate",
                "--",
                "--openapi",
                str(openapi_path),
                "--output-root",
                str(output_root),
            ],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            violations.append(
                "Runtime API client generation failed during family drift check"
                + (f": {detail}" if detail else ".")
            )
            return violations

        observed = {
            path.relative_to(output_root).as_posix()
            for path in output_root.rglob("*")
            if path.is_file()
        }
        expected = set(expected_outputs)
        if observed != expected:
            missing = sorted(expected - observed)
            extra = sorted(observed - expected)
            if missing:
                violations.append(f"Missing generated runtime client outputs: {missing}")
            if extra:
                violations.append(f"Unexpected generated runtime client outputs: {extra}")

        for relative in expected_outputs:
            committed = repo_root / relative
            generated = output_root / relative
            if not committed.exists():
                violations.append(f"Missing generated client file: {relative}")
                continue
            if generated.exists() and committed.read_bytes() != generated.read_bytes():
                violations.append(f"Runtime API client drift detected: {relative} is outdated.")
    return violations


def main() -> int:
    args = _parse_args()
    repo_root = repo_root_from(__file__)
    _ensure_src_on_path(repo_root)
    openapi_path = args.openapi if args.openapi.is_absolute() else (repo_root / args.openapi)

    violations = _check_openapi_drift(
        repo_root=repo_root,
        openapi_path=openapi_path,
        max_diff_lines=args.max_diff_lines,
    )
    if not args.skip_client_drift:
        violations.extend(
            _check_runtime_client_family_drift(
                repo_root=repo_root,
                openapi_path=openapi_path,
            )
        )
    if violations:
        print("Runtime API contract check FAILED:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("Runtime API contract check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
