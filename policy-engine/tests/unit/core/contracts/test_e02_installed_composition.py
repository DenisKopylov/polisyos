"""Installed consumer checks for the E02 source-to-wheel packaging wave.

These tests deliberately read only the public-surface source contract from the
frozen checkout. Product behavior is exercised through the imported package,
which the installed-wave origin plugin verifies came from site-packages.
"""

from __future__ import annotations

import importlib
import json
import os
import tomllib
from pathlib import Path

import pytest


def _source_root() -> Path:
    configured = os.environ.get("E02_SOURCE_ROOT")
    if configured:
        return Path(configured).resolve(strict=True)
    return Path(__file__).resolve().parents[4]


def test_public_surface_entrypoints_resolve_declared_exports(record_testsuite_property) -> None:
    """Resolve every supported entry point and its runtime-declared exports."""
    root = _source_root()
    contract = tomllib.loads(
        (root / "architecture/public_surface/contract.toml").read_text(encoding="utf-8")
    )["package"]
    inventory = json.loads(
        (root / "architecture/public_surface/inventory.json").read_text(encoding="utf-8")
    )["packages"]

    entrypoints = [name for row in contract for name in row["supported_entrypoints"]]
    unresolved_inventory_rows = sum(
        row.get("facade_mode_observed") == "unresolved_exports" for row in inventory
    )
    assert len(contract) == len(inventory) == 20
    assert len(entrypoints) == len(set(entrypoints)) == 38
    assert [row["module"] for row in contract] == [row["module"] for row in inventory]
    assert unresolved_inventory_rows == 20

    resolved_export_count = 0
    for module_name in entrypoints:
        module = importlib.import_module(module_name)
        exports = getattr(module, "__all__", None)
        assert isinstance(exports, (list, tuple)), f"{module_name} has no explicit __all__"
        assert all(isinstance(name, str) for name in exports), module_name
        assert len(exports) == len(set(exports)), f"{module_name} repeats an export"
        for export_name in exports:
            getattr(module, export_name)
        resolved_export_count += len(exports)

    record_testsuite_property("source_contract_package_definitions", len(contract))
    record_testsuite_property("source_contract_supported_entrypoints", len(entrypoints))
    record_testsuite_property("ast_inventory_unresolved_package_rows", unresolved_inventory_rows)
    record_testsuite_property("runtime_declared_exports_resolved", resolved_export_count)


def test_workflow_request_rejects_wrong_typed_intake_ref_kind_or_media_type() -> None:
    """The typed production intake arm rejects refs that name a different artifact."""
    from pydantic import ValidationError

    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.contracts import WorkflowRunRequest

    artifact_id = ArtifactID.from_sha256_hex("a" * 64)
    base = {"data_source": {"data_snapshot_ref": "sha256:" + "b" * 64}}
    wrong_kind = ArtifactRef(
        artifact_id=artifact_id,
        kind="unrelated.artifact",
        media_type="application/json",
    )
    wrong_media_type = ArtifactRef(
        artifact_id=artifact_id,
        kind="gy.loop.proof.root",
        media_type="text/plain",
    )
    valid_ref = ArtifactRef(
        artifact_id=artifact_id,
        kind="gy.loop.proof.root",
        media_type="application/json",
    )

    for invalid_ref in (wrong_kind, wrong_media_type):
        with pytest.raises(
            ValidationError, match="production_case_intake_ref_kind_or_media_type_invalid"
        ):
            WorkflowRunRequest(**base, production_case_intake_ref=invalid_ref)

    accepted = WorkflowRunRequest(**base, production_case_intake_ref=valid_ref)
    assert accepted.production_case_intake_ref == valid_ref


def test_gate_request_selected_replay_requirement_is_versioned() -> None:
    """Current requests require a selected replay view while the legacy schema remains readable."""
    from pydantic import ValidationError

    from polisyos.ir.governance import GateRequest

    base = {
        "request_id": "gate.e02.installed",
        "run_id": "run.e02.installed",
        "reason": "review selected replay evidence",
        "context": {"workflow_id": "workflow.e02", "node_alias": "review", "phase": "gate"},
    }
    with pytest.raises(ValidationError, match="requires selected_replay_refs"):
        GateRequest(**base, schema_version="1.2")

    current = GateRequest(
        **{
            **base,
            "context": {**base["context"], "selected_replay_refs": {}},
        },
        schema_version="1.2",
    )
    legacy = GateRequest(**base, schema_version="1.1")
    assert current.context.selected_replay_refs == {}
    assert legacy.context.selected_replay_refs is None


def test_cas_nondefault_manifest_profile_round_trips_through_fresh_reader(tmp_path: Path) -> None:
    """A selected nondefault manifest profile keeps its content and typed metadata on read."""
    from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import content_hash

    cas_root = tmp_path / "cas"
    writer = FileSystemCAS(cas_root)
    payload = b"installed nondefault profile payload\n"
    default_ref = writer.put_bytes(
        payload,
        ArtifactWriteOptions(kind="e02.default", media_type="text/plain"),
    )
    selected_ref = writer.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="e02.selected",
            media_type="application/octet-stream",
            schema=SchemaInfo(name="e02.selected-payload", version="2.0"),
            producer=ProducerInfo(component="e02.installed-consumer", version="1.0.0"),
        ),
    )
    assert selected_ref.artifact_id == default_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None

    reader = FileSystemCAS(cas_root)
    assert reader.get_bytes(selected_ref) == payload
    assert content_hash(payload) == selected_ref.artifact_id.hex
    manifest = reader.get_manifest(selected_ref)
    assert manifest.kind == "e02.selected"
    assert manifest.media_type == "application/octet-stream"
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == "e02.selected-payload"
    assert manifest.artifact_schema.version == "2.0"
    assert manifest.producer is not None
    assert manifest.producer.component == "e02.installed-consumer"
    assert reader.get_manifest(default_ref).kind == "e02.default"


def test_small_monte_carlo_report_is_consumed_from_fresh_cas(tmp_path: Path) -> None:
    """A completed Monte Carlo producer report remains typed and content-bound on read."""
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec, from_canonical_bytes
    from polisyos.foundry.uncertainty import MonteCarloPropagator
    from polisyos.foundry.uncertainty.config import PropagationConfig
    from polisyos.ir.analytics.uncertainty import (
        DistributionFamily,
        IntervalSemantics,
        PropagationMethod,
        UncertaintyEnvelope,
        UncertaintySource,
    )

    cas_root = tmp_path / "monte-carlo-cas"
    writer = FileSystemCAS(cas_root)
    input_envelope = UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-1.96, 1.96),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
        metadata={"param_name": "x"},
    )
    produced = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=100,
            mc_batch_size=20,
            mc_seed=194,
            mc_min_valid_samples=10,
            compute_sensitivity=False,
        )
    ).propagate(
        lambda x: {"workers": float(x)},
        {"x": 0.0},
        {"x": input_envelope},
        ["workers"],
    )[0]
    provenance = produced.diagnostics["draw_outcome_provenance"]
    assert produced.diagnostics["output_coverage_complete"] is True
    assert provenance["requested_draw_count"] == 100
    assert provenance["attempted_draw_count"] == 100
    assert provenance["successful_draw_count"] == 100
    assert provenance["failure_records"] == []

    report_ref = writer.put_json(
        {
            "schema_version": "1.1",
            "output_envelopes": {"workers": produced.envelope.model_dump(mode="json")},
            "diagnostics": produced.diagnostics,
        },
        ArtifactWriteOptions(
            kind="foundry.propagation_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.PropagationReport", version="1.1"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    reader = FileSystemCAS(cas_root)
    report = from_canonical_bytes(reader.get_bytes(report_ref))
    consumed_envelope = UncertaintyEnvelope.model_validate(report["output_envelopes"]["workers"])
    assert report["schema_version"] == "1.1"
    assert report["diagnostics"]["draw_outcome_provenance"] == provenance
    assert consumed_envelope.model_dump(mode="json") == produced.envelope.model_dump(mode="json")


def test_scholar_raw_source_binding_survives_fresh_cas_read_and_rejects_invented_quote(
    tmp_path: Path,
) -> None:
    """Persisted citations bind to raw bytes and a fresh reader refuses a fabricated span."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.canon import content_hash, from_canonical_bytes
    from polisyos.scholar.search.cache import UrlFetchCache
    from polisyos.scholar.search.fetcher import _extract_title_and_text, source_id_from_url
    from polisyos.scholar.search.models import (
        FetchResult,
        QueryGraph,
        ResearchBrief,
        WebEvidenceBundle,
        WebSearchHit,
    )
    from polisyos.scholar.search.scoring import build_source_metadata, compress_page_to_snippets
    from polisyos.scholar.search.security import sanitize_untrusted_text
    from polisyos.scholar.search.service import ScholarDeepSearchService
    from polisyos.scholar.search.source_binding import validate_web_evidence_source_binding
    from polisyos.scientist.evidence.verifier import verify_web_evidence_bundle

    cas_root = tmp_path / "scholar-cas"
    writer = FileSystemCAS(cas_root)
    url = "https://agency.gov/minimum-wage"
    raw_bytes = (
        b"<html><body><p>Minimum wage increased earnings for low-wage workers.</p></body></html>"
    )
    title, extracted_text = _extract_title_and_text(
        raw_bytes,
        mime="text/html",
        final_url=url,
    )
    extracted_text = sanitize_untrusted_text(extracted_text)
    raw_digest = content_hash(raw_bytes)
    fetched = FetchResult(
        url=url,
        final_url=url,
        title=title,
        text=extracted_text,
        content_type="text/html",
        content_sha256=raw_digest,
        byte_size=len(raw_bytes),
        status="ok",
        source_type="government",
    )
    fetched = UrlFetchCache(cas=writer).put(fetched, raw_bytes=raw_bytes).to_fetch_result()
    source_id = source_id_from_url(url, raw_digest)
    hit = WebSearchHit(
        url=url,
        provider="fixture",
        query="minimum wage earnings",
        rank=1,
        source_type="government",
    )
    source = build_source_metadata(source_id=source_id, hit=hit, fetch=fetched)
    snippets = compress_page_to_snippets(
        source_id=source_id,
        url=url,
        text=extracted_text,
        query_node_id="q1",
        perspective="overview",
        query_terms=["earnings"],
        max_snippets=1,
        window_chars=len(extracted_text),
    )
    assert len(snippets) == 1
    brief = ResearchBrief(question="minimum wage earnings")
    produced_bundle = WebEvidenceBundle(
        bundle_id="bundle.e02.installed-source-binding",
        brief=brief,
        query_graph=QueryGraph(brief=brief),
        sources=[source],
        snippets=snippets,
    )
    bundle_ref = ScholarDeepSearchService(cas=writer).persist_bundle(produced_bundle)
    assert source.raw_artifact_ref is not None
    assert writer.get_bytes(source.raw_artifact_ref) == raw_bytes
    assert source.raw_artifact_ref.artifact_id.hex == raw_digest

    reader = FileSystemCAS(cas_root)
    persisted_bytes = reader.get_bytes(bundle_ref)
    consumed_bundle = WebEvidenceBundle.model_validate(from_canonical_bytes(persisted_bytes))
    bound = validate_web_evidence_source_binding(consumed_bundle, cas=reader)
    assert bound.passed is True
    assert bound.source_text_by_id[source_id] == extracted_text
    assert verify_web_evidence_bundle(consumed_bundle, cas=reader).passed is True

    invented_snippet = consumed_bundle.snippets[0].model_copy(update={"text": "invented quote"})
    invented_bundle = consumed_bundle.model_copy(update={"snippets": [invented_snippet]})
    refusal = validate_web_evidence_source_binding(invented_bundle, cas=reader)
    assert refusal.passed is False
    assert any(item.startswith("span_text_mismatch:") for item in refusal.violations)
    assert verify_web_evidence_bundle(invented_bundle, cas=reader).passed is False
