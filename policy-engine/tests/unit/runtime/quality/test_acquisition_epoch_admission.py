"""The operational admission CLI consumes the persisted epoch owner result."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from polisyos.core import artifacts
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.runtime.quality import semantic_epoch, substrate_registry
from tests.unit.runtime.quality.test_acquisition_executor import _fixture


@pytest.fixture
def admission_request(tmp_path: Path) -> tuple[Path, artifacts.FileSystemCAS]:
    """Build real isolated owners without changing the production composition."""

    _, store, authority, _, raw_ref = _fixture(tmp_path / "acquisition")
    root = authority.repo_root
    source_root = Path(__file__).resolve().parents[4]
    owner_paths = (
        Path("architecture/policy_design_case/layer3_gy_epoch_boundary_source_registry.json"),
        Path("architecture/policy_design_case/layer3_gy_semantic_facet_registry.json"),
        substrate_registry.DEFAULT_EPOCH_L5_REGIME_REGISTRY_PATH,
        substrate_registry.DEFAULT_EPOCH_L5_SCOPE_REGISTRY_PATH,
    )
    for relative in owner_paths:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / relative, destination)
    l5_paths = substrate_registry.default_substrate_catalog_paths(root)
    l5_paths.identification_mode_registry_path.write_text("{}", encoding="utf-8")
    l5_paths.schema_regime_registry_path.write_text("{}", encoding="utf-8")
    lex_path = root / substrate_registry.DEFAULT_L3_LEX_KG_PATH
    lex_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(lex_path)) as con:
        con.execute(
            "CREATE TABLE lex_amendments (amendment_id VARCHAR, amended_doc_id VARCHAR, "
            "target_anchor VARCHAR, effective_from VARCHAR, created_at TIMESTAMP)"
        )
        con.execute(
            "CREATE TABLE lex_facts (doc_id VARCHAR, jurisdiction VARCHAR, top_domain VARCHAR)"
        )

    def put(payload: bytes, *, kind: str) -> artifacts.ArtifactRef:
        return store.put_bytes(
            payload,
            artifacts.PutOptions(kind=kind, media_type="application/vnd.polisyos.epoch+json"),
        )

    registry = semantic_epoch.load_facet_registry(root / owner_paths[1])
    facet_refs = {}
    for registration in registry.registrations:
        ref = put(
            epoch_contract.canonical_epoch_bytes({"semantic_value": registration.facet_id}),
            kind="epoch.semantic_facet_source.v1",
        )
        assert str(ref.artifact_id) == registration.source_binding_ref
        facet_refs[registration.source_binding_ref] = ref.model_dump(mode="json")
    request = {
        "repo_root": str(root),
        "authority_repo_root": str(root),
        "baseline_path": str(authority.baseline_path),
        "cas_root": str(tmp_path / "acquisition/cas"),
        "overlay_path": str(tmp_path / "overlay.duckdb"),
        "epoch_history_root": str(tmp_path / "epoch-history"),
        "epoch_id": 1,
        "raw_evidence_ref": raw_ref.model_dump(mode="json"),
        "epoch_scope_identity": semantic_epoch.build_epoch_scope_identity(
            schema_profile="polisyos.epoch.policy-scope.v1",
            identity_bytes=epoch_contract.canonical_epoch_bytes(
                {"domain": "public-finance", "jurisdiction": "UA"}
            ),
        ).model_dump(mode="json"),
        "authority_purpose": "publication",
        "valid_effect_coordinate_evidence_ref": put(
            b"2025-01-01", kind="epoch.coordinate.valid-date.v1"
        ).model_dump(mode="json"),
        "visibility_knowledge_cutoff_evidence_ref": put(
            b"2025-02-01T00:00:00Z", kind="epoch.coordinate.knowledge-time.v1"
        ).model_dump(mode="json"),
        "purpose_admission_cutoff_evidence_ref": put(
            b"2025-02-02T00:00:00Z", kind="epoch.coordinate.admission-time.v1"
        ).model_dump(mode="json"),
        "facet_source_refs": facet_refs,
    }
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    return path, store


def _assert_owner_negative(stdout: str, store: artifacts.FileSystemCAS) -> None:
    payload = json.loads(stdout)
    receipt = semantic_epoch.PersistedSemanticEpochProductionReceipt.model_validate(payload)
    statement = epoch_contract.load_verified_epoch_statement(
        store=store,
        ref=receipt.receipt_ref,
        expected_kind="epoch.production_receipt",
        expected_media_type="application/vnd.polisyos.epoch-production-receipt+json",
    )
    assert statement == {
        field: payload[field]
        for field in epoch_contract.SemanticEpochProductionReceiptStatement.model_fields
    }
    assert statement["status"] == "not_established"
    assert statement["failure_codes"] == ["policy_admission_missing"]
    assert statement["production_mode"] == "acquisition_finalization"
    assert statement["prepared_epoch_ref"] is not None
    assert statement["admitted_boundary_evidence_ref"] is not None
    assert statement["history_append_receipt_ref"] is None
    assert statement["chronology_bundle_ref"] is None


def test_cli_consumes_actual_persisted_policy_refusal(admission_request, capsys) -> None:
    """The unchanged negative is green only after a complete producer invocation."""

    from polisyos.runtime.quality import acquisition_epoch_admission as cli

    request_path, store = admission_request
    status = cli.main(["--request", str(request_path)])
    output = capsys.readouterr()
    assert status == 1, output.err
    assert output.err == ""
    _assert_owner_negative(output.out, store)


def test_python_module_is_runnable_terminus(admission_request) -> None:
    """A fresh interpreter reaches the same producer and persisted audit consumer."""

    request_path, store = admission_request
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "polisyos.runtime.quality.acquisition_epoch_admission",
            "--request",
            str(request_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 1, result.stderr
    _assert_owner_negative(result.stdout, store)


@pytest.mark.parametrize("mutation", ["extra", "missing_coordinate", "missing_authority"])
def test_cli_rejects_invalid_owner_inputs_without_receipt(
    admission_request, capsys, mutation: str
) -> None:
    from polisyos.runtime.quality import acquisition_epoch_admission as cli

    request_path, _ = admission_request
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if mutation == "extra":
        request["qualification_status"] = "qualified"
    elif mutation == "missing_coordinate":
        request.pop("valid_effect_coordinate_evidence_ref")
    else:
        request["baseline_path"] = str(request_path.parent / "missing.duckdb")
    request_path.write_text(json.dumps(request), encoding="utf-8")
    assert cli.main(["--request", str(request_path)]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err)["error"]


def test_cli_rejects_corrupt_persisted_receipt(admission_request, capsys, monkeypatch) -> None:
    """Typed return shape cannot replace the owner's persisted statement bytes."""

    from polisyos.runtime.quality import acquisition_epoch_admission as cli
    from polisyos.runtime.quality import acquisition_executor

    request_path, store = admission_request
    original = acquisition_executor.admit_acquisition_with_production_semantic_epoch

    def corrupt_after_production(**kwargs):
        receipt = original(**kwargs)
        blob_path, _ = store.get_paths(receipt.receipt_ref.artifact_id)
        blob_path.write_bytes(b"present-but-fake")
        return receipt

    monkeypatch.setattr(
        acquisition_executor,
        "admit_acquisition_with_production_semantic_epoch",
        corrupt_after_production,
    )
    assert cli.main(["--request", str(request_path)]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err)["error"]
