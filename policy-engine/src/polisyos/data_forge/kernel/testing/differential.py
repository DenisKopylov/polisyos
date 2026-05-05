"""Differential comparison helpers for Data Forge migration gates."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel
from polisyos.data_forge.kernel.io import sha256_file


class DifferentialComparison(DataForgeModel):
    """Result of comparing one legacy artifact with its Data Forge candidate."""

    name: str = Field(min_length=1)
    passed: bool
    expected_path: str = ""
    observed_path: str = ""
    expected_sha256: str = Field(default="", pattern=r"^$|[0-9a-f]{64}$")
    observed_sha256: str = Field(default="", pattern=r"^$|[0-9a-f]{64}$")
    message: str = ""


def compare_file_sha256(
    expected_path: str | Path,
    observed_path: str | Path,
    *,
    name: str | None = None,
) -> DifferentialComparison:
    """Compare two files by SHA-256 digest."""
    expected = Path(expected_path)
    observed = Path(observed_path)
    comparison_name = name or expected.name or "artifact"
    if not expected.exists() or not observed.exists():
        return DifferentialComparison(
            name=comparison_name,
            passed=False,
            expected_path=str(expected),
            observed_path=str(observed),
            message="expected and observed files must both exist",
        )

    expected_hash = sha256_file(expected)
    observed_hash = sha256_file(observed)
    return DifferentialComparison(
        name=comparison_name,
        passed=expected_hash == observed_hash,
        expected_path=str(expected),
        observed_path=str(observed),
        expected_sha256=expected_hash,
        observed_sha256=observed_hash,
        message="" if expected_hash == observed_hash else "sha256 mismatch",
    )


def compare_json_files(
    expected_path: str | Path,
    observed_path: str | Path,
    *,
    ignored_top_level_keys: tuple[str, ...] = (),
    name: str | None = None,
) -> DifferentialComparison:
    """Compare JSON object files, optionally ignoring volatile top-level keys."""
    expected = Path(expected_path)
    observed = Path(observed_path)
    comparison_name = name or expected.name or "json"
    if not expected.exists() or not observed.exists():
        return DifferentialComparison(
            name=comparison_name,
            passed=False,
            expected_path=str(expected),
            observed_path=str(observed),
            message="expected and observed JSON files must both exist",
        )

    expected_payload = _without_ignored_keys(_read_json_object(expected), ignored_top_level_keys)
    observed_payload = _without_ignored_keys(_read_json_object(observed), ignored_top_level_keys)
    expected_bytes = _canonical_json_bytes(expected_payload)
    observed_bytes = _canonical_json_bytes(observed_payload)
    expected_hash = _sha256_bytes(expected_bytes)
    observed_hash = _sha256_bytes(observed_bytes)
    return DifferentialComparison(
        name=comparison_name,
        passed=expected_payload == observed_payload,
        expected_path=str(expected),
        observed_path=str(observed),
        expected_sha256=expected_hash,
        observed_sha256=observed_hash,
        message="" if expected_payload == observed_payload else "json payload mismatch",
    )


def _read_json_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return {str(key): value for key, value in payload.items()}


def _without_ignored_keys(
    payload: dict[str, object],
    ignored_top_level_keys: tuple[str, ...],
) -> dict[str, object]:
    ignored = set(ignored_top_level_keys)
    return {key: value for key, value in payload.items() if key not in ignored}


def _canonical_json_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _sha256_bytes(payload: bytes) -> str:
    from polisyos.data_forge.kernel.io import sha256_bytes

    return sha256_bytes(payload)


__all__ = [
    "DifferentialComparison",
    "compare_file_sha256",
    "compare_json_files",
]
