"""Actual production epoch wrapper fixtures with bounded WDI transport evidence."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb
import pytest

from polisyos.core import artifacts, contracts
from polisyos.data_forge import read_api
from polisyos.runtime.quality import acquisition_executor, semantic_epoch, substrate_registry
from polisyos.runtime.quality.semantic_epoch_store import FileSemanticEpochHistoryRepository
from tests._helpers.semantic_epoch_native import sign_native_epoch_scenario
from tests.unit.runtime.quality.test_live_acquisition_executor import _run


def production_admission_inputs(
    tmp_path: Path,
    *,
    store: artifacts.FileSystemCAS,
    authority: Any,
    overlay_path: Path,
    epoch_history_root: Path,
) -> dict[str, Any]:
    """Prepare owner files and semantic selectors before a real port fetch."""
    del tmp_path
    root = authority.repo_root
    source_root = Path(__file__).resolve().parents[2]
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
            "CREATE TABLE IF NOT EXISTS lex_amendments (amendment_id VARCHAR, "
            "amended_doc_id VARCHAR, target_anchor VARCHAR, effective_from VARCHAR, "
            "created_at TIMESTAMP)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS lex_facts "
            "(doc_id VARCHAR, jurisdiction VARCHAR, top_domain VARCHAR)"
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
            contracts.epoch.canonical_epoch_bytes({"semantic_value": registration.facet_id}),
            kind="epoch.semantic_facet_source.v1",
        )
        if str(ref.artifact_id) != registration.source_binding_ref:
            raise AssertionError("fixture semantic source differs from canonical registry")
        facet_refs[registration.source_binding_ref] = ref
    return {
        "repo_root": root,
        "epoch_id": 1,
        "artifact_store": store,
        "authority": authority,
        "overlay_path": overlay_path,
        "epoch_history_root": epoch_history_root,
        "epoch_scope_identity": semantic_epoch.build_epoch_scope_identity(
            schema_profile="polisyos.epoch.policy-scope.v1",
            identity_bytes=contracts.epoch.canonical_epoch_bytes(
                {"domain": "public-finance", "jurisdiction": "UA"}
            ),
        ),
        "authority_purpose": "publication",
        "valid_effect_coordinate_evidence_ref": put(
            b"2025-01-01", kind="epoch.coordinate.valid-date.v1"
        ),
        "visibility_knowledge_cutoff_evidence_ref": put(
            b"2025-02-01T00:00:00Z", kind="epoch.coordinate.knowledge-time.v1"
        ),
        "purpose_admission_cutoff_evidence_ref": put(
            b"2025-02-02T00:00:00Z", kind="epoch.coordinate.admission-time.v1"
        ),
        "facet_source_refs": facet_refs,
    }


def build_production_admission_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    store: artifacts.FileSystemCAS | None = None,
    authority: Any = None,
    evidence: Any = None,
) -> SimpleNamespace:
    """Prepare/sign the exact full-wrapper basis; the caller performs activation.

    The default uses the real bounded live acquisition executor with the
    existing network-free Fabric observer/sink fixture. Optional supplied
    evidence lets caller tests retain their independently executed transport.
    No qualification, producer, activation, or readback function is patched.
    """
    if any(value is not None for value in (store, authority, evidence)):
        if any(value is None for value in (store, authority, evidence)):
            raise ValueError("supply store, authority and live evidence together")
    else:
        authority, evidence, _transport, _journal_path = _run(tmp_path / "live", monkeypatch)
        store = artifacts.FileSystemCAS(tmp_path / "live" / "cas")
    if store is None:
        raise AssertionError("fixture artifact store absent")
    overlay_path = tmp_path / "overlay.duckdb"
    history_root = tmp_path / "epoch-history"
    call_args = production_admission_inputs(
        tmp_path,
        store=store,
        authority=authority,
        overlay_path=overlay_path,
        epoch_history_root=history_root,
    )
    call_args.update(raw_evidence_ref=evidence.raw_evidence_ref, live_source_execution=evidence)
    negative = acquisition_executor.admit_acquisition_with_production_semantic_epoch(**call_args)
    if not isinstance(
        negative, semantic_epoch.PersistedSemanticEpochProductionReceipt
    ) or negative.failure_codes != ("policy_admission_missing",):
        raise AssertionError(f"unallocated real wrapper did not reach policy admission: {negative}")
    ref = negative.prepared_epoch_ref
    if ref is None:
        raise AssertionError("real wrapper omitted prepared epoch basis")
    statement = contracts.epoch.load_verified_epoch_statement(
        store=store, ref=ref, expected_kind="epoch.prepared"
    )
    prepared = semantic_epoch.PreparedSemanticEpoch(
        **statement,
        prepared_epoch_ref=ref,
        prepared_content_hash=semantic_epoch._model_hash(
            b"polisyos.epoch.prepared.v1\0", statement
        ),
    )
    history = FileSemanticEpochHistoryRepository(root=history_root, artifacts=store)
    scenario = SimpleNamespace(
        store=store, prepared=prepared, query=prepared.query, history=history, service=None
    )
    native = sign_native_epoch_scenario(scenario, tmp_path / "native-policy")
    return SimpleNamespace(
        call_args=call_args,
        deployment=native.deployment,
        config=native.config,
        native=native,
        store=store,
        authority=authority,
        evidence=evidence,
        negative=negative,
        prepared=prepared,
        query=prepared.query,
        overlay_path=overlay_path,
        epoch_history_root=history_root,
        overlay=read_api.catalog.CatalogAcquisitionOverlay(authority.baseline_path, overlay_path),
    )
