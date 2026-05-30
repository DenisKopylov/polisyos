from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

import duckdb

from tools.quality.validation import build_policy_evidence_capability_index as builder
from tools.quality.validation import export_policy_evidence_capability_dcat as dcat
from tools.quality.validation import export_policy_evidence_capability_prov as prov
from tools.quality.validation import generate_policy_evidence_capability_cards as cards
from tools.quality.validation import inspect_policy_evidence_capability_index as inspect

REPO_ROOT = Path(__file__).resolve().parents[3]
WAVE12_ARCHIVE_DIFF_PATH = (
    REPO_ROOT
    / "architecture/policy_design_case/wave12_capability_graph_archive_diff_manifest.json"
)


def test_capability_index_exports_dcat_prov_inspection_and_cards(tmp_path: Path) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0
    index_path = index_dir / "capability_index_v1.duckdb"

    inspection = inspect.build_capability_index_inspection_report(index_path)
    assert inspection["schema_version"] == inspect.SCHEMA_VERSION
    assert inspection["status"] == "pass"
    assert inspection["counts"]["capability_count"] >= 1
    assert inspection["counts"]["active_capability_count"] == _active_capability_count(index_path)
    assert inspection["construct_coverage"]["covered_construct_count"] >= 1
    assert inspection["authority_posture_counts"]["production"]
    assert inspection["white_space_counts"]["total"] >= 1

    dcat_payload = dcat.build_dcat_export(index_path)
    dcat_validation = dcat.validate_dcat_export(dcat_payload)
    assert dcat_validation["status"] == "pass", dcat_validation["issues"]
    assert dcat_validation["rdf_graph_triple_count"] > 0
    assert dcat_validation["dcat_dataset_triple_count"] == _active_capability_count(
        index_path
    )
    assert dcat_payload["@type"] == "dcat:Catalog"
    assert "dcat" in dcat_payload["@context"]
    assert len(dcat_payload["dcat:dataset"]) == _active_capability_count(index_path)
    assert all(dataset["dct:identifier"] for dataset in dcat_payload["dcat:dataset"])
    assert all(dataset["dcat:distribution"] for dataset in dcat_payload["dcat:dataset"])

    prov_ttl = prov.build_prov_export(index_path)
    prov_validation = prov.validate_prov_turtle(prov_ttl)
    assert prov_validation["status"] == "pass", prov_validation["issues"]
    assert prov_validation["rdf_graph_triple_count"] > 0
    assert prov_validation["prov_entity_triple_count"] >= _active_capability_count(
        index_path
    )
    assert "prov:Entity" in prov_ttl
    assert "prov:Activity" in prov_ttl
    assert "prov:Agent" in prov_ttl
    assert "prov:wasGeneratedBy" in prov_ttl
    assert "prov:wasAssociatedWith" in prov_ttl

    card_manifest = cards.generate_capability_cards(
        capability_index_path=index_path,
        output_dir=tmp_path / "cards",
    )
    assert card_manifest["status"] == "pass"
    assert card_manifest["card_count"] == _active_capability_count(index_path)
    for card_ref in card_manifest["cards"]:
        card_text = (tmp_path / "cards" / card_ref["filename"]).read_text(encoding="utf-8")
        for section in (
            "## What This Proves",
            "## What This Does Not Prove",
            "## Known Limitations",
            "## Authority Envelope",
            "## Owner",
            "## Reviewer Notes",
            "## Acquisition Alternatives",
        ):
            assert section in card_text


def test_capability_cards_remove_stale_markdown_files(tmp_path: Path) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0
    index_path = index_dir / "capability_index_v1.duckdb"
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir()
    stale = cards_dir / "capability_stale__000000000000.md"
    stale.write_text("# stale\n", encoding="utf-8")

    manifest = cards.generate_capability_cards(
        capability_index_path=index_path,
        output_dir=cards_dir,
    )

    assert manifest["card_count"] == _active_capability_count(index_path)
    assert not stale.exists()
    assert len(list(cards_dir.glob("*.md"))) == _active_capability_count(index_path)


def test_prov_validation_rejects_malformed_turtle() -> None:
    validation = prov.validate_prov_turtle("@prefix prov: <http://www.w3.org/ns/prov#> .\n<bad")

    assert validation["status"] == "fail"
    assert {
        issue["code"] for issue in validation["issues"]
    } >= {"prov_turtle_parse_error"}


def test_export_clis_write_phase7_artifacts(tmp_path: Path) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0
    index_path = index_dir / "capability_index_v1.duckdb"

    dcat_path = tmp_path / "capability_index_v1.dcat.jsonld"
    prov_path = tmp_path / "capability_index_v1.prov.ttl"
    inspect_path = tmp_path / "inspection.json"
    cards_dir = tmp_path / "cards"

    assert dcat.main(["--capability-index", str(index_path), "--output", str(dcat_path)]) == 0
    assert prov.main(["--capability-index", str(index_path), "--output", str(prov_path)]) == 0
    assert (
        inspect.main(["--capability-index", str(index_path), "--output", str(inspect_path)])
        == 0
    )
    assert (
        cards.main(["--capability-index", str(index_path), "--output-dir", str(cards_dir)])
        == 0
    )

    assert json.loads(dcat_path.read_text(encoding="utf-8"))["@type"] == "dcat:Catalog"
    assert "prov:Entity" in prov_path.read_text(encoding="utf-8")
    assert json.loads(inspect_path.read_text(encoding="utf-8"))["status"] == "pass"
    assert len(list(cards_dir.glob("*.md"))) == _active_capability_count(index_path)


def test_wave12_capability_graph_archive_diff_manifest_references_required_artifacts() -> None:
    manifest = json.loads(WAVE12_ARCHIVE_DIFF_PATH.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == (
        "policyos.policy_evidence_capability_graph.wave12_archive_diff.v1"
    )
    assert manifest["status"] == "implemented"
    refs = manifest["artifact_refs"]
    for key in (
        "pre_plan_baseline",
        "w12a_after_capability_graph",
        "w12d_corpus_stub_after_capability_graph",
        "w12d_real_producer_after_capability_graph",
        "capability_index_full",
        "dcat_export",
        "prov_export",
        "capability_cards",
    ):
        assert refs[key].startswith(("repo://", "artifact://")), key
    assert "production_data_scenario_contracts_missing" in manifest["baseline_diff"][
        "removed_generic_blockers"
    ]
    assert "w12d_producer_pipeline_blocked" in manifest["baseline_diff"][
        "replaced_generic_blockers"
    ]
    assert {
        "blocked_acquisition_required",
        "blocked_construct_validity_below_floor",
        "blocked_sample_size_below_floor",
        "blocked_rights_boundary",
        "blocked_authority_boundary",
    } <= set(manifest["known_remaining_typed_blockers"])


def _active_capability_count(index_path: Path) -> int:
    with duckdb.connect(str(index_path), read_only=True) as con:
        return int(
            con.execute(
                """
                SELECT count(*)
                FROM capabilities
                WHERE json_extract_string(capability_json, '$.capability_lifecycle.state')
                  = 'active'
                """
            ).fetchone()[0]
        )
