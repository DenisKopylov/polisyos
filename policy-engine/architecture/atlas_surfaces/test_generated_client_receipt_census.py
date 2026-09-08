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

    def test_non_anchor_source_records_do_not_claim_client_bindings(self) -> None:
        """Neutral DS18/DS17 source facts stay visible without becoming anchors."""
        census = _load_census()
        artifact_path = (
            "architecture/atlas_surfaces/frontend-disposition-register.json"
        )
        document = json.loads((REPO_ROOT / artifact_path).read_text(encoding="utf-8"))
        roots = [
            root
            for row in document["ds18_time_semantics_coverage"]["files"]
            for root in row["roots"]
        ]

        result = census._document_anchor_census(
            document,
            artifact_path=artifact_path,
            target_paths=census.DEFAULT_TARGET_PATHS,
        )

        pointer_prefix = "/ds18_time_semantics_coverage/files/"
        assert len(roots) == 759
        assert not any(
            binding["pointer"].startswith(pointer_prefix)
            for binding in result.independent.values()
        )
        assert not any(pointer_prefix in error for error in result.errors)
        assert result.errors == []

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

    def test_identity_emitter_writes_reproducible_source_sensitive_anchor(
        self,
    ) -> None:
        """The census writes only identities minted from the live declarations."""
        census = _load_census()
        canonical = "generated/canonical.ts"
        types = "generated/types.ts"
        canonical_source = 'export type DecisionGrade = "a" | "b";\n'
        types_source = (
            "export interface components {\n"
            "  schemas: {\n"
            '    DecisionGrade: "a" | "b";\n'
            "  };\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / canonical).parent.mkdir(parents=True)
            (root / canonical).write_text(canonical_source, encoding="utf-8")
            (root / types).write_text(types_source, encoding="utf-8")
            artifact = Path("architecture/waist.json")
            artifact_path = root / artifact
            artifact_path.parent.mkdir(parents=True)
            artifact_path.write_text(
                json.dumps(
                    {
                        "register_id": "test-waist",
                        "entries": [
                            {
                                "debt_id": "decision-grade",
                                "generated_client_anchor": {
                                    "anchor_kind": "missing_export",
                                    "absence_scope": (
                                        "canonical_module_exports_and_schema_owners"
                                    ),
                                    "canonical_path": canonical,
                                    "types_path": types,
                                    "symbol": "DecisionGrade",
                                },
                                "untouched": "surrounding bytes",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            first = census.emit_present_projection_anchor(
                repo_root=root,
                artifact_path=artifact,
                record_id="decision-grade",
            )
            first_bytes = artifact_path.read_bytes()
            repeated = census.emit_present_projection_anchor(
                repo_root=root,
                artifact_path=artifact,
                record_id="decision-grade",
            )

            assert repeated == first
            assert artifact_path.read_bytes() == first_bytes
            assert set(first) == {
                "anchor_kind",
                "canonical_path",
                "canonical_line",
                "canonical_identity",
                "types_path",
                "schema_line",
                "schema_identity",
                "symbol",
            }
            assert first["canonical_line"] == 1
            assert first["schema_line"] == 3
            assert artifact_path.read_text(encoding="utf-8").endswith(
                '"untouched": "surrounding bytes"\n    }\n  ]\n}\n'
            )

            (root / canonical).write_text(
                canonical_source.replace('"b"', '"b" | "c"'),
                encoding="utf-8",
            )
            (root / types).write_text(
                types_source.replace('"b"', '"b" | "c"'),
                encoding="utf-8",
            )
            changed = census.emit_present_projection_anchor(
                repo_root=root,
                artifact_path=artifact,
                record_id="decision-grade",
            )

            assert changed["canonical_identity"] != first["canonical_identity"]
            assert changed["schema_identity"] != first["schema_identity"]
            assert json.loads(artifact_path.read_text(encoding="utf-8"))["entries"][0][
                "generated_client_anchor"
            ] == changed

    def test_missing_export_recomputes_ast_absence_without_a_construct_identity(
        self,
    ) -> None:
        """Absence binds complete export/schema-owner sets, never a nearby line."""
        census = _load_census()
        identity_checker = _load_identity_checker()
        canonical = "packages/runtime-api-client/canonicalRuntimeApiClient.ts"
        types = "packages/runtime-api-client/types.ts"
        bridge = "packages/runtime-api-client/bridge.ts"
        canonical_source = (
            'export type Present = components["schemas"]["Present"];\n'
        )
        types_source = (
            "export interface components {\n"
            "  schemas: {\n"
            "    Present: { value: string };\n"
            "  };\n"
            "}\n"
        )
        anchor = {
            "anchor_kind": "missing_export",
            "absence_scope": "canonical_module_exports_and_schema_owners",
            "canonical_path": canonical,
            "types_path": types,
            "symbol": "DecisionGrade",
        }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact_path = root / "architecture/waist.json"
            artifact_path.parent.mkdir(parents=True)
            (root / canonical).parent.mkdir(parents=True)

            def report_for(
                canonical_text: str = canonical_source,
                types_text: str = types_source,
            ) -> dict[str, object]:
                (root / canonical).write_text(canonical_text, encoding="utf-8")
                (root / types).write_text(types_text, encoding="utf-8")
                artifact_path.write_text(
                    json.dumps(
                        {
                            "entries": [
                                {
                                    "debt_id": "missing",
                                    "generated_client_anchor": anchor,
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                return census.build_report(
                    repo_root=root,
                    target_paths=(canonical, types),
                    candidate_paths=(Path("architecture/waist.json"),),
                )

            report = report_for()
            assert report["errors"] == []
            assert report["summary"] == {
                "binding_artifacts": 1,
                "navigation_artifacts": 0,
                "primary_anchor_records": 1,
                "independent_anchor_records": 1,
                "line_bindings": 0,
                "independent_line_bindings": 0,
                "identity_bindings": 0,
                "absence_predicates": 2,
                "semantic_bindings": 2,
                "legacy_line_bindings": 0,
                "navigation_line_hints": 0,
                "navigation_references": 0,
            }
            binding = report["bindings"][0]
            assert binding["binding_mode"] == "recomputed_absence"
            assert binding["absence_bindings"] == [
                {
                    "slot": "canonical",
                    "predicate": "module_export_absent",
                    "symbol": "DecisionGrade",
                },
                {
                    "slot": "schema",
                    "predicate": "generated_schema_owner_absent",
                    "symbol": "DecisionGrade",
                },
            ]

            moved = report_for(
                "\n\n" + canonical_source,
                "\n\n\n" + types_source,
            )
            assert moved["errors"] == []

            comment_and_string = report_for(
                canonical_source
                + '\nconst note = "DecisionGrade"; // DecisionGrade is absent\n',
                types_source + "\n// DecisionGrade is absent\n",
            )
            assert comment_and_string["errors"] == []

            direct = report_for(
                canonical_source + "\nexport type DecisionGrade = string;\n"
            )
            assert any(
                error.endswith(":canonical:DecisionGrade")
                for error in direct["errors"]
            )

            reexport = report_for(
                canonical_source + '\nexport { DecisionGrade } from "./types.js";\n',
                types_source + "\nexport type DecisionGrade = string;\n",
            )
            assert any(
                error.endswith(":canonical:DecisionGrade")
                for error in reexport["errors"]
            )

            unresolved_star = report_for(
                canonical_source + '\nexport * from "./missing.js";\n'
            )
            assert any(
                "canonical_reexport_unresolved" in error
                for error in unresolved_star["errors"]
            )

            malformed_dependency = (
                identity_checker._typescript_generated_client_absence_facts(
                    {
                        canonical: canonical_source
                        + '\nexport * from "./bridge.js";\n',
                        types: types_source,
                        bridge: "export type Other = ;\n",
                    },
                    canonical_path=canonical,
                    types_path=types,
                )
            )
            assert any(
                "source_invalid:dependency:" in error
                for error in malformed_dependency["errors"]
            )

            script_dependency = (
                identity_checker._typescript_generated_client_absence_facts(
                    {
                        canonical: canonical_source
                        + '\nexport * from "./bridge.js";\n',
                        types: types_source,
                        bridge: "type Other = string;\n",
                    },
                    canonical_path=canonical,
                    types_path=types,
                )
            )
            assert any(
                "canonical_reexport_target_scope_missing" in error
                for error in script_dependency["errors"]
            )

            script_mode = report_for("type LocalOnly = string;\n")
            assert any(
                error.endswith(":canonical")
                and "anchor_absence_scope_missing" in error
                for error in script_mode["errors"]
            )

            schema_owner = report_for(
                types_text=types_source.replace(
                    "    Present: { value: string };",
                    "    Present: { value: string };\n    DecisionGrade: string;",
                )
            )
            assert any(
                error.endswith(":schema:DecisionGrade")
                for error in schema_owner["errors"]
            )

            computed_schema_owner = report_for(
                types_text=types_source.replace(
                    "    Present: { value: string };",
                    '    Present: { value: string };\n    ["DecisionGrade"]: string;',
                )
            )
            assert any(
                error.endswith(":schema:DecisionGrade")
                for error in computed_schema_owner["errors"]
            )

            unsupported_schema_scope = report_for(
                types_text=types_source.replace(
                    "  schemas: {",
                    "  schemas(): void;\n  schemas: {",
                )
            )
            assert any(
                "schema_scope_shape_unsupported" in error
                for error in unsupported_schema_scope["errors"]
            )

            missing_scope = report_for(
                types_text="export interface components { parameters: never; }\n"
            )
            assert any(
                "anchor_absence_scope_missing" in error
                for error in missing_scope["errors"]
            )

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
        waist = [
            binding
            for binding in report["bindings"]
            if binding["artifact_path"]
            == "architecture/atlas_surfaces/ds4-waist-debt-register.json"
        ]
        assert len(waist) == 3
        assert sum(len(binding["line_bindings"]) for binding in waist) == 6
        assert sum(len(binding["identity_bindings"]) for binding in waist) == 6
        assert sum(len(binding["absence_bindings"]) for binding in waist) == 0
        assert [binding["binding_mode"] for binding in waist] == [
            "identity",
            "identity",
            "identity",
        ]
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
        waist_before = census._document_anchor_census(
            json.loads(
                _git_blob(
                    "34f4df5fb",
                    "architecture/atlas_surfaces/ds4-waist-debt-register.json",
                )
            ),
            artifact_path=(
                "architecture/atlas_surfaces/ds4-waist-debt-register.json"
            ),
            target_paths=(
                "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
                "packages/runtime-api-client/types.ts",
            ),
        )
        assert waist_before.identity_bindings == 0
        assert waist_before.absence_predicates == 0
        assert waist_before.legacy_line_bindings == 8
        assert report["summary"]["primary_anchor_records"] == 18
        assert report["summary"]["identity_bindings"] == 36
        assert report["summary"]["absence_predicates"] == 0
        assert report["summary"]["semantic_bindings"] == 36
        assert report["summary"]["legacy_line_bindings"] == 0
        assert report["summary"]["navigation_line_hints"] == 36
        candidate_population = report["candidate_population"]
        assert candidate_population["total"] == sum(
            candidate_population["by_suffix"].values()
        )
        assert candidate_population["by_suffix"][".json"] > 0
        assert candidate_population["by_suffix"][".toml"] > 0
        assert len(candidate_population["path_sha256"]) == 64

    def test_live_waist_receipts_replay_task6_and_reject_semantic_drift(
        self,
    ) -> None:
        """Use the real Task 6 movement for the last three DEF21 anchors."""
        identity_checker = _load_identity_checker()
        waist_path = "architecture/atlas_surfaces/ds4-waist-debt-register.json"
        canonical_path = "packages/runtime-api-client/canonicalRuntimeApiClient.ts"
        types_path = "packages/runtime-api-client/types.ts"
        waist = json.loads((REPO_ROOT / waist_path).read_text(encoding="utf-8"))
        present = [
            row["generated_client_anchor"]
            for row in waist["entries"]
            if row["generated_client_anchor"]["anchor_kind"]
            == "present_projection"
        ]
        historical_present = [
            anchor for anchor in present if anchor["symbol"] != "DecisionGrade"
        ]
        references = [
            anchor[key]
            for anchor in historical_present
            for key in ("canonical_identity", "schema_identity")
        ]
        payloads = [_identity_payload(reference) for reference in references]

        assert len(present) == 3
        assert len(references) == 4
        assert all(anchor["anchor_kind"] == "present_projection" for anchor in present)

        current_sources = {
            canonical_path: (REPO_ROOT / canonical_path).read_text(encoding="utf-8"),
            types_path: (REPO_ROOT / types_path).read_text(encoding="utf-8"),
        }
        decision_grade = next(
            anchor for anchor in present if anchor["symbol"] == "DecisionGrade"
        )
        for slot, role, discriminator in (
            ("canonical", "exported_declaration", "DecisionGrade"),
            ("schema", "type_property", "components.DecisionGrade"),
        ):
            identity = decision_grade[f"{slot}_identity"]
            facts = identity_checker._typescript_reference_construct_facts(
                current_sources,
                source_path=(canonical_path if slot == "canonical" else types_path),
                role=role,
                discriminator=discriminator,
            )
            assert len(facts["matches"]) == 1
            assert decision_grade[f"{slot}_line"] == facts["matches"][0]["startLine"]
            assert identity_checker._validate_typescript_reference_identity(
                {"encoded_identity": identity},
                current_sources,
            ) == []

        def sources_at(revision: str) -> dict[str, str]:
            return {
                canonical_path: _git_blob(revision, canonical_path),
                types_path: _git_blob(revision, types_path),
            }

        def replay_errors(revision: str) -> list[str]:
            sources = sources_at(revision)
            requests = [
                {
                    "sourcePath": payload["source_path"],
                    "role": payload["role"],
                    "discriminator": payload["discriminator"],
                }
                for payload in payloads
            ]
            facts = identity_checker._typescript_reference_construct_facts_batch(
                sources,
                requests,
                closed_universe=True,
            )
            return [
                error
                for payload, fact in zip(payloads, facts, strict=True)
                if (
                    error := identity_checker._typescript_reference_match_error(
                        payload, fact
                    )
                )
                is not None
            ]

        assert replay_errors("d17ecd36e") == []
        assert replay_errors("fea50aadd") == []

        for revision in ("d17ecd36e", "fea50aadd"):
            facts = identity_checker._typescript_generated_client_absence_facts(
                sources_at(revision),
                canonical_path=canonical_path,
                types_path=types_path,
            )
            assert facts["errors"] == []
            assert "DecisionGrade" not in facts["canonicalExports"]
            assert "DecisionGrade" not in facts["schemaOwners"]

        old_waist = json.loads(_git_blob("d17ecd36e", waist_path))
        task6_sources = sources_at("fea50aadd")
        legacy_meaning: list[bool] = []
        for row in old_waist["entries"]:
            anchor = row["generated_client_anchor"]
            if anchor["anchor_kind"] != "present_projection":
                continue
            symbol = anchor["symbol"]
            canonical_line = task6_sources[canonical_path].splitlines()[
                anchor["canonical_line"] - 1
            ]
            facts = identity_checker._typescript_reference_construct_facts(
                {types_path: task6_sources[types_path]},
                source_path=types_path,
                role="type_property",
                discriminator=f"components.{symbol}",
            )
            match = facts["matches"][0]
            legacy_meaning.extend(
                [
                    f"export type {symbol}" in canonical_line,
                    match["startLine"] == anchor["types_start_line"],
                    match["endLine"] == anchor["types_end_line"],
                ]
            )
        assert legacy_meaning == [False] * 6

        old_missing = next(
            row["generated_client_anchor"]
            for row in old_waist["entries"]
            if row["generated_client_anchor"]["anchor_kind"] == "missing_export"
        )
        for coordinate in ("export_block_start_line", "export_block_end_line"):
            old_line = sources_at("d17ecd36e")[canonical_path].splitlines()[
                old_missing[coordinate] - 1
            ]
            moved_line = task6_sources[canonical_path].splitlines()[
                old_missing[coordinate] - 1
            ]
            assert old_line != moved_line
        legacy_absence_verdicts = [
            all(
                "DecisionGrade" not in source
                for source in sources_at(revision).values()
            )
            for revision in ("d17ecd36e", "fea50aadd")
        ]
        assert legacy_absence_verdicts == [True, True]

        canonical_reference = present[0]["canonical_identity"]
        canonical_payload = _identity_payload(canonical_reference)
        canonical_facts = identity_checker._typescript_reference_construct_facts(
            {canonical_path: task6_sources[canonical_path]},
            source_path=canonical_path,
            role=str(canonical_payload["role"]),
            discriminator=str(canonical_payload["discriminator"]),
        )
        canonical_match = canonical_facts["matches"][0]
        canonical_lines = task6_sources[canonical_path].splitlines(keepends=True)
        del canonical_lines[
            int(canonical_match["startLine"]) - 1 : int(canonical_match["endLine"])
        ]
        assert identity_checker._validate_typescript_reference_identity(
            {"encoded_identity": canonical_reference},
            {canonical_path: "".join(canonical_lines)},
        ) == ["typescript_reference_binding_missing_or_renamed"]

        schema_reference = present[0]["schema_identity"]
        schema_payload = _identity_payload(schema_reference)
        schema_facts = identity_checker._typescript_reference_construct_facts(
            {types_path: task6_sources[types_path]},
            source_path=types_path,
            role=str(schema_payload["role"]),
            discriminator=str(schema_payload["discriminator"]),
        )
        start = int(schema_facts["matches"][0]["startLine"]) - 1
        source_lines = task6_sources[types_path].splitlines(keepends=True)

        renamed_lines = list(source_lines)
        renamed_lines[start] = renamed_lines[start].replace(
            "GenerationCycleDispositionPayload:",
            "RenamedGenerationCycleDispositionPayload:",
            1,
        )
        assert identity_checker._validate_typescript_reference_identity(
            {"encoded_identity": schema_reference},
            {types_path: "".join(renamed_lines)},
        ) == ["typescript_reference_binding_missing_or_renamed"]

        content_lines = list(source_lines)
        content_index = next(
            index
            for index in range(start, len(content_lines))
            if "bridge_artifacts:" in content_lines[index]
        )
        content_lines[content_index] = content_lines[content_index].replace(
            "bridge_artifacts:", "bridge_receipts:", 1
        )
        assert identity_checker._validate_typescript_reference_identity(
            {"encoded_identity": schema_reference},
            {types_path: "".join(content_lines)},
        ) == ["typescript_reference_content_drift"]

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
