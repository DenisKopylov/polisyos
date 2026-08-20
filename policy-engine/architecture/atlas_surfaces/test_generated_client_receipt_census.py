# ruff: noqa: S101 - behavioral tests use assertions as their failure boundary
"""Behavioral tests for the generated-client receipt denominator census."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ATLAS_DIR = Path(__file__).resolve().parent
REPO_ROOT = ATLAS_DIR.parents[1]
CENSUS_PATH = ATLAS_DIR / "generated_client_receipt_census.py"


def _load_census() -> object:
    if not CENSUS_PATH.exists():
        raise AssertionError("generated-client receipt census module is missing")
    spec = importlib.util.spec_from_file_location(
        "generated_client_receipt_census", CENSUS_PATH
    )
    if spec is None or spec.loader is None:  # pragma: no cover - import bootstrap guard
        raise AssertionError(f"Unable to import receipt census from {CENSUS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GeneratedClientReceiptCensusTests(unittest.TestCase):
    """Prove receipt discovery is derived from the full structured population."""

    def test_discovers_unlisted_artifacts_and_reconciles_independent_counts(
        self,
    ) -> None:
        """A new governed artifact cannot disappear behind a remembered filename list."""
        census = _load_census()
        canonical = "generated/canonical.ts"
        types = "generated/types.ts"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status_path = root / "architecture/status.json"
            waist_path = root / "architecture/waist.json"
            navigation_path = root / "architecture/navigation.json"
            unrelated_path = root / "architecture/unrelated.json"
            status_path.parent.mkdir(parents=True)
            status_path.write_text(
                json.dumps(
                    {
                        "sources": {
                            "generated_client": {
                                "canonical_path": canonical,
                                "types_path": types,
                            }
                        },
                        "entries": [
                            {
                                "unit_id": "first",
                                "generated_anchor": {
                                    "export_symbol": "First",
                                    "canonical_line": 10,
                                    "schema_line": 20,
                                },
                            },
                            {
                                "unit_id": "second",
                                "generated_anchor": {
                                    "export_symbol": "Second",
                                    "canonical_line": 30,
                                    "schema_line": 40,
                                },
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            waist_path.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "debt_id": "third",
                                "generated_client_anchor": {
                                    "canonical_path": canonical,
                                    "canonical_line": 50,
                                    "types_path": types,
                                    "types_start_line": 60,
                                    "symbol": "Third",
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            navigation_path.write_text(
                json.dumps({"evidence_refs": [f"{types}:70"]}),
                encoding="utf-8",
            )
            unrelated_path.write_text(
                json.dumps({"source": types, "count": 999}),
                encoding="utf-8",
            )

            report = census.build_report(
                repo_root=root,
                target_paths=(canonical, types),
                candidate_paths=(
                    Path("architecture/status.json"),
                    Path("architecture/waist.json"),
                    Path("architecture/navigation.json"),
                    Path("architecture/unrelated.json"),
                ),
            )

        assert report["errors"] == []
        observed_summary = {
            key: report["summary"][key]
            for key in (
                "binding_artifacts",
                "navigation_artifacts",
                "primary_anchor_records",
                "independent_anchor_records",
                "line_bindings",
                "independent_line_bindings",
                "navigation_references",
            )
        }
        assert observed_summary == {
            "binding_artifacts": 2,
            "navigation_artifacts": 1,
            "primary_anchor_records": 3,
            "independent_anchor_records": 3,
            "line_bindings": 6,
            "independent_line_bindings": 6,
            "navigation_references": 1,
        }
        assert report["candidate_population"]["by_suffix"] == {
            ".json": 4,
            ".toml": 0,
        }
        observed_bindings = [
            (binding["artifact_path"], binding["pointer"], binding["record_id"])
            for binding in report["bindings"]
        ]
        assert observed_bindings == [
            ("architecture/status.json", "/entries/0/generated_anchor", "first"),
            ("architecture/status.json", "/entries/1/generated_anchor", "second"),
            (
                "architecture/waist.json",
                "/entries/0/generated_client_anchor",
                "third",
            ),
        ]
        assert (
            sum(len(binding["line_bindings"]) for binding in report["bindings"])
            == 6
        )
        assert report["navigation_references"] == [
            {
                "artifact_path": "architecture/navigation.json",
                "line": 70,
                "pointer": "/evidence_refs/0",
                "target_path": types,
            }
        ]

    def test_fails_closed_when_the_independent_population_finds_a_new_shape(
        self,
    ) -> None:
        """A differently named symbol/line binding becomes an error, never an omission."""
        census = _load_census()
        canonical = "generated/canonical.ts"
        types = "generated/types.ts"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "architecture/future.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "sources": {
                            "generated_client": {
                                "canonical_path": canonical,
                                "types_path": types,
                            }
                        },
                        "future_binding": {
                            "type_name": "Future",
                            "canonical_line": 1,
                            "schema_line": 2,
                        },
                    }
                ),
                encoding="utf-8",
            )
            report = census.build_report(
                repo_root=root,
                target_paths=(canonical, types),
                candidate_paths=(Path("architecture/future.json"),),
            )

        assert (
                "anchor_population_mismatch:architecture/future.json:"
                "/future_binding:primary=absent:independent=present"
            ) in report["errors"]

    def test_live_denominator_reconciles_without_remembered_artifact_paths(
        self,
    ) -> None:
        """The repository census derives and reconciles every current binding artifact."""
        census = _load_census()
        report = census.build_repository_report(repo_root=REPO_ROOT)

        assert report["errors"] == []
        assert (
            report["summary"]["primary_anchor_records"]
            == report["summary"]["independent_anchor_records"]
        )
        assert (
            report["summary"]["line_bindings"]
            == report["summary"]["independent_line_bindings"]
        )
        status = [
            binding
            for binding in report["bindings"]
            if binding["artifact_path"]
            == "architecture/atlas_surfaces/status-retirement-inventory.json"
        ]
        assert len(status) == 15
        assert sum(len(binding["line_bindings"]) for binding in status) == 30
        candidate_population = report["candidate_population"]
        assert candidate_population["total"] == sum(
            candidate_population["by_suffix"].values()
        )
        assert candidate_population["by_suffix"][".json"] > 0
        assert candidate_population["by_suffix"][".toml"] > 0
        assert len(candidate_population["path_sha256"]) == 64


if __name__ == "__main__":  # pragma: no cover - direct unittest entry point
    unittest.main()
