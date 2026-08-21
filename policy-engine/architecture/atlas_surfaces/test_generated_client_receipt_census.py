# ruff: noqa: S101 - behavioral tests use assertions as their failure boundary
"""Behavioral tests for the generated-client receipt denominator census."""

from __future__ import annotations

import base64
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ATLAS_DIR = Path(__file__).resolve().parent
REPO_ROOT = ATLAS_DIR.parents[1]
CENSUS_PATH = ATLAS_DIR / "generated_client_receipt_census.py"
IDENTITY_CHECKER_PATH = ATLAS_DIR / "check_frontend_disposition_register.py"


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


def _load_identity_checker() -> object:
    spec = importlib.util.spec_from_file_location(
        "generated_client_identity_checker", IDENTITY_CHECKER_PATH
    )
    if spec is None or spec.loader is None:  # pragma: no cover - import bootstrap guard
        raise AssertionError(
            f"Unable to import identity checker from {IDENTITY_CHECKER_PATH}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_blob(revision: str, relative_path: str) -> str:
    """Read one real repository blob without materializing a historical tree."""
    return subprocess.run(  # noqa: S603 - fixed system Git executable
        [
            "/usr/bin/git",
            "show",
            f"{revision}:policy-engine/{relative_path}",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _identity_payload(reference: str) -> dict[str, object]:
    """Decode a v1 identity payload for independent historical replay."""
    encoded = reference.split("#ts-identity=", 1)[1]
    return json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))


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

    def test_identity_mode_consumes_owner_qualified_role_and_rejects_mixed_mode(
        self,
    ) -> None:
        """Identity-mode anchors replay semantics while their lines only navigate."""
        census = _load_census()
        identity_checker = _load_identity_checker()
        canonical = "packages/runtime-api-client/canonicalRuntimeApiClient.ts"
        types = "packages/runtime-api-client/types.ts"
        canonical_source = (REPO_ROOT / canonical).read_text(encoding="utf-8")
        types_source = (REPO_ROOT / types).read_text(encoding="utf-8")
        symbol = "PolisyosCoreContractsRuntimeLineageRefOutput"
        discriminator = (
            "components.schemas."
            "polisyos__core__contracts__runtime__LineageRef-Output.status"
        )
        canonical_identity = identity_checker._typescript_reference_identity(
            {canonical: canonical_source},
            source_path=canonical,
            role="exported_declaration",
            discriminator=symbol,
        )["encoded_identity"]
        canonical_facts = identity_checker._typescript_reference_construct_facts(
            {canonical: canonical_source},
            source_path=canonical,
            role="exported_declaration",
            discriminator=symbol,
        )
        canonical_match = canonical_facts["matches"][0]
        canonical_lines = canonical_source.splitlines(keepends=True)
        alias_block = "".join(
            canonical_lines[
                canonical_match["startLine"] - 1 : canonical_match["endLine"]
            ]
        )
        schema_identity = identity_checker._typescript_reference_identity(
            {types: types_source},
            source_path=types,
            role="generated_schema_property",
            discriminator=discriminator,
        )["encoded_identity"]
        schema_facts = identity_checker._typescript_reference_construct_facts(
            {types: types_source},
            source_path=types,
            role="generated_schema_property",
            discriminator=discriminator,
        )
        target_index = schema_facts["matches"][0]["startLine"] - 1
        type_lines = types_source.splitlines(keepends=True)
        target_line = type_lines[target_index]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / canonical).parent.mkdir(parents=True)
            (root / canonical).write_text(canonical_source, encoding="utf-8")
            (root / types).write_text(types_source, encoding="utf-8")
            artifact_path = root / "architecture/status.json"
            artifact_path.parent.mkdir(parents=True)
            identity_anchor = {
                "export_symbol": symbol,
                "field": "status",
                "canonical_line": 999,
                "schema_line": 1000,
                "canonical_identity": canonical_identity,
                "schema_identity": schema_identity,
            }

            def report_for(entries: list[dict[str, object]]) -> dict[str, object]:
                artifact_path.write_text(
                    json.dumps(
                        {
                            "sources": {
                                "generated_client": {
                                    "canonical_path": canonical,
                                    "types_path": types,
                                }
                            },
                            "entries": entries,
                        }
                    ),
                    encoding="utf-8",
                )
                return census.build_report(
                    repo_root=root,
                    target_paths=(canonical, types),
                    candidate_paths=(Path("architecture/status.json"),),
                )

            report = report_for(
                [{"unit_id": "identity", "generated_anchor": identity_anchor}]
            )
            assert report["errors"] == []
            assert report["summary"]["identity_bindings"] == 2
            assert report["summary"]["legacy_line_bindings"] == 0
            assert report["summary"]["navigation_line_hints"] == 2
            binding = report["bindings"][0]
            assert binding["binding_mode"] == "identity"
            assert {
                item["role"] for item in binding["identity_bindings"]
            } == {"exported_declaration", "generated_schema_property"}

            moved_types = "\n" + types_source
            (root / types).write_text(moved_types, encoding="utf-8")
            moved_report = report_for(
                [{"unit_id": "identity", "generated_anchor": identity_anchor}]
            )
            assert moved_report["errors"] == []

            def replace_target_line(replacement: str) -> str:
                changed = list(type_lines)
                changed[target_index] = replacement
                return "".join(changed)

            renamed_types = replace_target_line(
                target_line.replace("status:", "state:")
            )
            (root / types).write_text(renamed_types, encoding="utf-8")
            renamed_report = report_for(
                [{"unit_id": "identity", "generated_anchor": identity_anchor}]
            )
            assert any(
                "typescript_reference_binding_missing_or_renamed" in error
                for error in renamed_report["errors"]
            )

            content_drift = replace_target_line(
                target_line.replace('"untraced"', '"unknown"')
            )
            (root / types).write_text(content_drift, encoding="utf-8")
            content_report = report_for(
                [{"unit_id": "identity", "generated_anchor": identity_anchor}]
            )
            assert any(
                "typescript_reference_content_drift" in error
                for error in content_report["errors"]
            )

            duplicated_lines = list(type_lines)
            duplicated_lines.insert(target_index + 1, target_line)
            (root / types).write_text("".join(duplicated_lines), encoding="utf-8")
            duplicate_report = report_for(
                [{"unit_id": "identity", "generated_anchor": identity_anchor}]
            )
            assert any(
                "typescript_reference_binding_ambiguous" in error
                for error in duplicate_report["errors"]
            )

            (root / types).write_text(types_source, encoding="utf-8")
            (root / canonical).write_text(
                canonical_source + "\n" + alias_block,
                encoding="utf-8",
            )
            alias_duplicate_report = report_for(
                [{"unit_id": "identity", "generated_anchor": identity_anchor}]
            )
            assert any(
                error.startswith("anchor_identity_alias_relation_ambiguous:")
                for error in alias_duplicate_report["errors"]
            )

            (root / canonical).write_text(canonical_source, encoding="utf-8")
            swapped_anchor = dict(identity_anchor)
            swapped_anchor["canonical_identity"] = schema_identity
            swapped_anchor["schema_identity"] = canonical_identity
            swapped_report = report_for(
                [{"unit_id": "swapped", "generated_anchor": swapped_anchor}]
            )
            assert any(
                error.endswith(":canonical:source_path")
                for error in swapped_report["errors"]
            )

            wrong_anchor = dict(identity_anchor)
            wrong_anchor["canonical_identity"] = (
                identity_checker._typescript_reference_identity(
                    {canonical: canonical_source},
                    source_path=canonical,
                    role="exported_declaration",
                    discriminator="RunWorkflowNodeView",
                )["encoded_identity"]
            )
            wrong_anchor["schema_identity"] = (
                identity_checker._typescript_reference_identity(
                    {types: types_source},
                    source_path=types,
                    role="generated_schema_property",
                    discriminator="components.schemas.ScenarioRef.status",
                )["encoded_identity"]
            )
            wrong_report = report_for(
                [{"unit_id": "wrong", "generated_anchor": wrong_anchor}]
            )
            assert any(
                error.endswith(":canonical:construct")
                for error in wrong_report["errors"]
            )
            assert any(
                error.endswith(":schema:construct")
                for error in wrong_report["errors"]
            )

            extra_anchor = dict(identity_anchor)
            extra_anchor["extra_line"] = 1
            extra_anchor["extra_identity"] = canonical_identity
            extra_report = report_for(
                [{"unit_id": "extra", "generated_anchor": extra_anchor}]
            )
            assert any(
                error.startswith("anchor_identity_slot_set_drift:")
                for error in extra_report["errors"]
            )

            mixed_report = report_for(
                [
                    {"unit_id": "identity", "generated_anchor": identity_anchor},
                    {
                        "unit_id": "legacy",
                        "generated_anchor": {
                            "export_symbol": "Legacy",
                            "canonical_line": 1,
                            "schema_line": 2,
                        },
                    },
                ]
            )
            assert (
                "anchor_identity_mode_mixed:architecture/status.json"
                in mixed_report["errors"]
            )

            (root / types).unlink()
            missing_source_report = report_for(
                [{"unit_id": "identity", "generated_anchor": identity_anchor}]
            )
            assert any(
                "typescript_reference_source_missing" in error
                for error in missing_source_report["errors"]
            )

            (root / types).write_text(types_source, encoding="utf-8")
            assert report_for(
                [{"unit_id": "identity", "generated_anchor": identity_anchor}]
            )["errors"] == []
            subprocess.run(  # noqa: S603 - fixed system git executable
                ["/usr/bin/git", "init", "-q", str(root)],
                check=True,
                capture_output=True,
            )
            subprocess.run(  # noqa: S603 - fixed system git executable
                [
                    "/usr/bin/git",
                    "-C",
                    str(root),
                    "add",
                    "--",
                    "architecture/status.json",
                ],
                check=True,
                capture_output=True,
            )
            direct = subprocess.run(  # noqa: S603 - fixed interpreter/checker
                [
                    sys.executable,
                    str(CENSUS_PATH),
                    "--repo-root",
                    str(root),
                    "--target",
                    canonical,
                    "--target",
                    types,
                    "--check",
                ],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            assert direct.returncode == 0, direct.stderr
            assert json.loads(direct.stdout)["summary"]["identity_bindings"] == 2

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
        assert sum(len(binding["identity_bindings"]) for binding in status) == 30
        assert all(binding["binding_mode"] == "identity" for binding in status)
        before = census._document_anchor_census(
            json.loads(
                _git_blob(
                    "34f4df5fb",
                    "architecture/atlas_surfaces/status-retirement-inventory.json",
                )
            ),
            artifact_path=(
                "architecture/atlas_surfaces/status-retirement-inventory.json"
            ),
            target_paths=(
                "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
                "packages/runtime-api-client/types.ts",
            ),
        )
        assert before.identity_bindings == 0
        assert before.legacy_line_bindings == 30
        assert before.navigation_line_hints == 0
        assert sum(
            len(binding["identity_bindings"]) for binding in status
        ) - before.identity_bindings == before.legacy_line_bindings
        assert report["summary"]["legacy_line_bindings"] == 8
        assert report["summary"]["navigation_line_hints"] == 30
        candidate_population = report["candidate_population"]
        assert candidate_population["total"] == sum(
            candidate_population["by_suffix"].values()
        )
        assert candidate_population["by_suffix"][".json"] > 0
        assert candidate_population["by_suffix"][".toml"] > 0
        assert len(candidate_population["path_sha256"]) == 64

    def test_live_status_identities_replay_across_real_client_regenerations(
        self,
    ) -> None:
        """Bind the migration to the real Task 6 and registered GAP4 movements."""
        identity_checker = _load_identity_checker()
        inventory_path = "architecture/atlas_surfaces/status-retirement-inventory.json"
        canonical_path = "packages/runtime-api-client/canonicalRuntimeApiClient.ts"
        schema_path = "packages/runtime-api-client/types.ts"
        inventory = json.loads((REPO_ROOT / inventory_path).read_text(encoding="utf-8"))
        anchors = [
            (row["unit_id"], row["generated_anchor"])
            for row in inventory["entries"]
            if row["classification"] == "lattice_derived"
        ]
        references = [
            anchor[key]
            for _unit_id, anchor in anchors
            for key in ("canonical_identity", "schema_identity")
        ]
        payloads = [_identity_payload(reference) for reference in references]

        assert len(anchors) == 15
        assert len(references) == 30
        assert all(
            not any("line" in str(key).lower() for key in payload)
            for payload in payloads
        )

        def sources_at(revision: str) -> dict[str, str]:
            return {
                canonical_path: _git_blob(revision, canonical_path),
                schema_path: _git_blob(revision, schema_path),
            }

        def facts_at(revision: str) -> list[dict[str, object]]:
            sources = sources_at(revision)
            requests = [
                {
                    "sourcePath": payload["source_path"],
                    "role": payload["role"],
                    "discriminator": payload["discriminator"],
                }
                for payload in payloads
            ]
            return identity_checker._typescript_reference_construct_facts_batch(
                sources,
                requests,
                closed_universe=True,
            )

        def replay_errors(revision: str) -> list[str]:
            return [
                error
                for payload, facts in zip(payloads, facts_at(revision), strict=True)
                if (
                    error := identity_checker._typescript_reference_match_error(
                        payload, facts
                    )
                )
                is not None
            ]

        assert replay_errors("d17ecd36e") == []
        assert replay_errors("fea50aadd") == []

        old_inventory = json.loads(_git_blob("d17ecd36e", inventory_path))
        task6_sources = sources_at("fea50aadd")
        legacy_results: list[bool] = []
        for row in old_inventory["entries"]:
            if row["classification"] != "lattice_derived":
                continue
            anchor = row["generated_anchor"]
            canonical_line = task6_sources[canonical_path].splitlines()[
                anchor["canonical_line"] - 1
            ]
            schema_line = task6_sources[schema_path].splitlines()[
                anchor["schema_line"] - 1
            ]
            legacy_results.extend(
                [
                    f'export type {anchor["export_symbol"]}' in canonical_line,
                    (
                        f'{anchor["field"]}:'
                        if anchor.get("field")
                        else f'{anchor["export_symbol"]}:'
                    )
                    in schema_line,
                ]
            )
        assert legacy_results == [False] * 30

        gap4_before = facts_at("40ef040bd")
        gap4_after = facts_at("dc3e50a90")
        movements: dict[str, list[int]] = {}
        for (unit_id, _anchor), before_pair, after_pair in zip(
            anchors,
            zip(gap4_before[::2], gap4_before[1::2], strict=True),
            zip(gap4_after[::2], gap4_after[1::2], strict=True),
            strict=True,
        ):
            movements[unit_id] = [
                int(after_pair[0]["matches"][0]["startLine"])
                - int(before_pair[0]["matches"][0]["startLine"]),
                int(after_pair[1]["matches"][0]["startLine"])
                - int(before_pair[1]["matches"][0]["startLine"]),
            ]
        assert sum(delta == [2, 7] for delta in movements.values()) == 8
        assert sum(delta == [0, 0] for delta in movements.values()) == 7
        assert replay_errors("40ef040bd") == []
        assert replay_errors("dc3e50a90") == []

        lineage_anchor = dict(
            next(anchor for unit_id, anchor in anchors if unit_id == "status-verification")
        )
        lineage_identity = lineage_anchor["schema_identity"]
        lineage_payload = _identity_payload(lineage_identity)
        lineage_facts = identity_checker._typescript_reference_construct_facts_batch(
            task6_sources,
            [
                {
                    "sourcePath": lineage_payload["source_path"],
                    "role": lineage_payload["role"],
                    "discriminator": lineage_payload["discriminator"],
                }
            ],
            closed_universe=True,
        )[0]
        target_line_index = int(lineage_facts["matches"][0]["startLine"]) - 1
        source_lines = task6_sources[schema_path].splitlines(keepends=True)
        target_line = source_lines[target_line_index]

        def changed_schema(replacement: str) -> dict[str, str]:
            changed = list(source_lines)
            changed[target_line_index] = replacement
            return {schema_path: "".join(changed)}

        renamed = changed_schema(target_line.replace("status:", "state:"))
        removed = changed_schema("")
        content_changed = changed_schema(
            target_line.replace('"untraced"', '"unknown"')
        )
        assert identity_checker._validate_typescript_reference_identity(
            {"encoded_identity": lineage_identity}, renamed
        ) == ["typescript_reference_binding_missing_or_renamed"]
        assert identity_checker._validate_typescript_reference_identity(
            {"encoded_identity": lineage_identity}, removed
        ) == ["typescript_reference_binding_missing_or_renamed"]
        assert identity_checker._validate_typescript_reference_identity(
            {"encoded_identity": lineage_identity}, content_changed
        ) == ["typescript_reference_content_drift"]


if __name__ == "__main__":  # pragma: no cover - direct unittest entry point
    unittest.main()
