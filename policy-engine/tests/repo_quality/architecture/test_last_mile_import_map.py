from __future__ import annotations

import json
import tomllib
from pathlib import Path

from tools.quality.validation import repository_last_mile_shim_callers

REPO_ROOT = Path(__file__).resolve().parents[3]

EXPECTED_PLANNED_MOVES = {
    "polisyos.scientist.decision_validity",
    "polisyos.scientist.error_semantics",
    "polisyos.scientist.evidence_sources",
    "polisyos.scientist.feedback_utils",
    "polisyos.scientist.frontier_runtime",
    "polisyos.scientist.latent_separation",
    "polisyos.scientist.llm_cycle",
    "polisyos.scientist.publisher",
    "polisyos.scientist.reliability_scorecard",
    "polisyos.scientist.remediation_status",
    "polisyos.scientist.replay_backend",
    "polisyos.fabric._connector_bridge",
    "polisyos.fabric._numeric_parsing",
    "polisyos.fabric.compatibility",
    "polisyos.fabric.config",
    "polisyos.fabric.connectors.sdk",
    "polisyos.fabric.connectors_ingestion",
    "polisyos.fabric.decision_data",
    "polisyos.fabric.evidence",
    "polisyos.fabric.extensions",
    "polisyos.fabric.fact_writer",
    "polisyos.fabric.finite",
    "polisyos.fabric.fitness_report",
    "polisyos.fabric.ingestion_providers",
    "polisyos.fabric.manifest",
    "polisyos.fabric.observability",
    "polisyos.fabric.processing_guarantees",
    "polisyos.fabric.product_integration",
    "polisyos.fabric.registry",
    "polisyos.fabric.safety",
    "polisyos.fabric.segment_manifest",
    "polisyos.fabric.tabular",
    "polisyos.fabric.temporal",
    "polisyos.fabric.trust",
    "polisyos.fabric.trust_adapter",
    "polisyos.fabric.world_query",
    "polisyos.ir._internal",
    "polisyos.ir._lazy_facade",
    "polisyos.ir.canon",
    "polisyos.ir.citations",
    "polisyos.ir.connectors",
    "polisyos.ir.fact_log",
    "polisyos.ir.loaders",
    "polisyos.ir.migration_report",
    "polisyos.ir.model_spec",
    "polisyos.ir.norm_pack",
    "polisyos.ir.portfolio",
    "polisyos.ir.predicate",
    "polisyos.ir.public_surface",
    "polisyos.ir.queries",
    "polisyos.ir.references",
    "polisyos.ir.refs",
    "polisyos.ir.registry_fragments",
    "polisyos.ir.schema_catalog",
    "polisyos.ir.schemas",
    "polisyos.ir.trinity",
    "polisyos.ir.types",
    "polisyos.ir.units",
    "polisyos.ddm_15_7",
    "polisyos.synthetic_world",
}


def test_phase_0_3_import_map_covers_every_planned_move() -> None:
    shims = _read_toml("architecture/shims.toml")
    header = shims["last_mile_import_compatibility_map"]
    entries = shims["planned_source_move"]
    by_source = {entry["source_fqn"]: entry for entry in entries}

    assert header["phase"] == "0.3"
    assert header["status"] == "active"
    assert header["caller_report"] == "_build/.tmp/last-mile/shim_callers.json"
    assert header["report"] == (
        "docs/archive/reports/REPOSITORY_BEST_IN_CLASS_LAST_MILE_IMPORT_MAP.md"
    )
    assert set(by_source) == EXPECTED_PLANNED_MOVES
    assert len(by_source) == len(entries)

    for entry in entries:
        assert entry["decision"] in {
            "removed",
            "moved_with_reexport_shim",
            "retained_with_dated_exception",
        }
        if entry["decision"] != "removed":
            for field in ("owner", "reason", "test", "release_note", "sunset"):
                assert entry.get(field), entry["source_fqn"]


def test_phase_0_3_import_map_covers_registered_shell_package_exceptions() -> None:
    layout = _read_toml("architecture/packages/layout.toml")
    shims = _read_toml("architecture/shims.toml")
    exception_paths = {
        entry["path"].rstrip("/")
        for entry in layout["single_file_shell_package_exception"]
    }
    planned_source_paths = {
        entry["source_path"].rstrip("/") for entry in shims["planned_source_move"]
    }

    assert exception_paths <= planned_source_paths


def test_phase_0_3_shim_callers_report_matches_retained_compatibility_paths(
    tmp_path: Path,
) -> None:
    shims = _read_toml("architecture/shims.toml")
    retained_entries = {
        entry["id"]: entry
        for entry in shims["planned_source_move"]
        if entry["decision"] != "removed"
    }
    output_path = tmp_path / "shim_callers.json"
    assert (
        repository_last_mile_shim_callers.main(
            ["--repo-root", str(REPO_ROOT), "--json-output", str(output_path), "--check"]
        )
        == 0
    )
    report = json.loads(output_path.read_text(encoding="utf-8"))

    assert set(report["shims"]) == set(retained_entries)
    assert report["schema_version"] == repository_last_mile_shim_callers.SCHEMA_VERSION
    assert report["phase"] == "0.3"
    assert report["scan"]["ast_imports"] is True
    assert report["scan"]["text_fallback_dynamic_strings"] is True
    assert report["removal_policy"]["phase_2_3"] == (
        "A shim may be removed only when caller_count is zero or all remaining callers "
        "are examples/tests intentionally exercising compatibility."
    )

    for shim_id, entry in retained_entries.items():
        shim_report = report["shims"][shim_id]
        assert shim_report["source_fqn"] == entry["source_fqn"]
        assert shim_report["migration_target"] == entry["target_fqn"]
        assert shim_report["caller_count"] == len(shim_report["callers"])
        for caller in shim_report["callers"]:
            assert caller["importer_path"]
            assert caller["import_kind"] in {
                "import",
                "from_import",
                "from_import_submodule",
                "dynamic_string",
            }
            assert caller["migration_target"] == entry["target_fqn"]


def test_phase_0_3_shim_caller_generator_scans_ast_and_dynamic_strings(
    tmp_path: Path,
) -> None:
    architecture = tmp_path / "architecture"
    architecture.mkdir()
    (architecture / "shims.toml").write_text(
        "\n".join(
            (
                "[last_mile_import_compatibility_map]",
                'phase = "0.3"',
                "",
                "[[planned_source_move]]",
                'id = "demo-legacy"',
                'source_fqn = "polisyos.demo.legacy"',
                'target_fqn = "polisyos.demo.canonical"',
                'decision = "moved_with_reexport_shim"',
                'owner = "team-demo"',
                'reason = "synthetic test"',
                'test = "tests/unit/demo/test_shim.py"',
                'release_note = "docs/demo.md"',
                'sunset = "2026-12-31"',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    source_file = tmp_path / "src" / "polisyos" / "demo" / "caller.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(
        "\n".join(
            (
                "import polisyos.demo.legacy",
                "from polisyos.demo.legacy import value",
                "DYNAMIC = 'polisyos.demo.legacy'",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    report = repository_last_mile_shim_callers.collect_shim_callers(tmp_path)
    callers = report["shims"]["demo-legacy"]["callers"]

    assert {caller["import_kind"] for caller in callers} >= {
        "import",
        "from_import",
        "dynamic_string",
    }
    assert all(caller["migration_target"] == "polisyos.demo.canonical" for caller in callers)


def _read_toml(path: str) -> dict:
    return tomllib.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
