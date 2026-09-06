"""Behavioral tests for registry-backed capability discovery composition."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import shlex
import subprocess
from datetime import UTC, date, datetime, timedelta

import duckdb
import pytest

from polisyos.core import artifacts
from polisyos.core.contracts.capability_discovery import (
    CapabilityDiscoveryRequest,
    CapabilityTimeSemantics,
)
from polisyos.core.contracts.runtime import ApiMeta
from polisyos.core.contracts.search import SearchCandidate, SearchLedger, SearchRequest
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.services.control_registry_providers import (
    resolve_control_registry_providers,
)
from polisyos.runtime.quality.approval import (
    ProductionApprovalPacketResolver,
    ProductionApprovalResolutionError,
)
from polisyos.runtime.quality.capability_authority import (
    CAPABILITY_PURPOSE_BINDING_ARTIFACT_KIND,
    CAPABILITY_PURPOSE_BINDING_SCHEMA_NAME,
    CapabilityAuthorityContext,
    CapabilityDiscoveryAuthorityResolver,
    CapabilityPurposeBindingProducer,
    CapabilityPurposeBindingVerifier,
)
from polisyos.runtime.quality.capability_discovery import (
    CapabilityDiscoveryComposer,
    CapabilityDiscoveryProvider,
    CapabilityIndexCapabilityDiscoveryProvider,
    CapabilityIndexOwnerReceipt,
    CapabilityProviderSearchResult,
    CapabilityProviderUnavailableError,
    LexCapabilityDiscoveryProvider,
    LexOwnerReceipt,
    ScientistRegistryOwnerReceipt,
    SourceProfileOwnerReceipt,
    main,
)
from polisyos.runtime.quality.capability_index import (
    CapabilityIndexDiscoveryRow,
    FreshnessEnvelope,
    LegalNormOwnerTruth,
    ScientistCapabilityOwnerTruth,
)
from polisyos.runtime.quality.capability_index_compiler import (
    CapabilityIndexCompilerConfig,
    build_capability_discovery_snapshot,
    compile_capability_index,
    create_capability_index_fixture_inputs,
)
from polisyos.runtime.quality.capability_resolver import CapabilityExecutionResolver

NOW = datetime(2026, 8, 25, 12, tzinfo=UTC)


class _Provider(CapabilityDiscoveryProvider):
    def __init__(self, result: CapabilityProviderSearchResult, calls: list[str]) -> None:
        self._result = result
        self._calls = calls

    @property
    def resource_kind(self) -> str:
        return self._result.resource_kind

    def search(self, request: CapabilityDiscoveryRequest) -> CapabilityProviderSearchResult:
        self._calls.append(self.resource_kind)
        return self._result


class _UnavailableProvider(CapabilityDiscoveryProvider):
    @property
    def resource_kind(self) -> str:
        return "source"

    def search(self, request: CapabilityDiscoveryRequest) -> CapabilityProviderSearchResult:
        raise CapabilityProviderUnavailableError("connector_registry_outage")


def test_capability_discovery_postures_use_three_independent_producers() -> None:
    """An index hit must not establish either execution or authority."""
    calls: list[str] = []
    method = _provider_result("method", "capability:method:generated")
    response = _composer(providers=(_Provider(method, calls),)).search(
        _request(("method",)), meta=ApiMeta(request_id="http:test")
    )

    assert calls == ["method"]
    item = response.results[0]
    assert item.discovery_result.state == "discoverable"
    assert item.execution_result.state == "not_established"
    assert item.authority_result.state == "bridge_missing"
    assert "not_established" in item.authority_result.reason_codes
    assert item.authoritative_for == ()


def test_default_causal_method_index_provider_projects_owner_rows_without_execution_promotion(
    tmp_path,
    monkeypatch,
) -> None:
    """The default method bridge consumes persisted owner rows, not execution booleans."""
    build = _fixture_capability_index_build(tmp_path)
    capability_index = build.capability_index
    assert capability_index is not None
    monkeypatch.setenv("POLISYOS_CAPABILITY_INDEX_PATH", str(build.primary_duckdb_path))
    expected = tuple(
        row
        for row in build_capability_discovery_snapshot(capability_index)
        if row.resource_kind == "method"
    )
    assert expected
    request = _request(("method",)).model_copy(
        update={
            "search": _request(("method",)).search.model_copy(
                update={
                    "query_text": "*",
                    "construct_refs": ("*",),
                    "budget": {"match_all": True, "top_k": len(expected)},
                }
            )
        }
    )
    registries = resolve_control_registry_providers(
        connectors=object(),  # type: ignore[arg-type]
        source_profiles=object(),  # type: ignore[arg-type]
        binding_profiles=object(),  # type: ignore[arg-type]
        model_profiles=object(),  # type: ignore[arg-type]
        gy_catalog_graph=object(),
    )
    provider = next(
        candidate
        for candidate in registries.capability_discovery_providers
        if candidate.resource_kind == "method"
    )

    result = provider.search(request)
    response = _composer(providers=(provider,)).search(
        request,
        meta=ApiMeta(request_id="http:method-owner"),
    )

    assert isinstance(provider, CapabilityIndexCapabilityDiscoveryProvider)
    assert result.rows == expected
    assert result.owner_receipt.index_release_ref == capability_index.release_ref
    assert result.owner_receipt.search_snapshot_digest == result.ledger.corpus_snapshot_hash
    assert result.owner_receipt.result_digest.startswith("sha256:")
    assert tuple(item.capability_ref for item in response.results) == tuple(
        row.capability_ref for row in expected
    )
    assert {item.execution_result.state for item in response.results} == {"not_established"}
    assert {item.authority_result.state for item in response.results} == {"bridge_missing"}
    assert all(item.authoritative_for == () for item in response.results)


def test_owner_signed_capability_purpose_binding_joins_ds9_currentness(
    tmp_path,
    monkeypatch,
) -> None:
    """Authority needs producer signing, independent verification, and DS9 currentness."""
    capability_ref = "capability:method:owner-signed"
    content_digest = "sha256:" + "2" * 64
    authority_purpose = "review_capability_candidates"
    producer_identity = "deployment:capability-purpose-owner"
    now = datetime(2026, 8, 31, 12, tzinfo=UTC)
    packet_ref = "sha256:" + "8" * 64
    pair = artifacts.KeyPair.generate()
    signer = artifacts.Ed25519Signer(pair.private_key)
    verifier = artifacts.Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(pair.public_key, identity=producer_identity)
    store = artifacts.FileSystemCAS(tmp_path / "binding-cas")
    producer = CapabilityPurposeBindingProducer(
        artifact_store=store,
        signer=signer,
        signer_identity=producer_identity,
    )
    production = producer.issue(
        capability_ref=capability_ref,
        content_digest=content_digest,
        authority_purpose=authority_purpose,
        discovery_audience="REVIEWER",
        approval_packet_ref=packet_ref,
        tenant_id="tenant-a",
        run_id="run-a",
        approval_consumer="polisyos.runtime.capability_discovery",
        approval_audience="polisyos-runtime",
        issued_at=now,
        valid_until=now + timedelta(hours=1),
    )
    binding_verifier = CapabilityPurposeBindingVerifier(
        artifact_store=store,
        verifier=verifier,
        expected_signer_identity=producer_identity,
    )
    ds9 = object.__new__(ProductionApprovalPacketResolver)
    currentness_error: list[str] = []
    currentness_calls: list[dict[str, object]] = []

    def _require_currentness(_self, **bindings: object):
        currentness_calls.append(bindings)
        if currentness_error:
            raise ProductionApprovalResolutionError(currentness_error[-1])
        return object()

    monkeypatch.setattr(
        ProductionApprovalPacketResolver,
        "require_currentness",
        _require_currentness,
    )
    resolver = CapabilityDiscoveryAuthorityResolver(
        production_approval_resolver=ds9,
        binding_verifier=binding_verifier,
    )
    context = CapabilityAuthorityContext(
        packet_ref=packet_ref,
        tenant_id="tenant-a",
        run_id="run-a",
        expected_consumer="polisyos.runtime.capability_discovery",
        expected_audience="REVIEWER",
        approval_audience="polisyos-runtime",
        binding_ref=production.binding_ref,
    )

    admitted = resolver.resolve(
        capability_ref=capability_ref,
        content_digest=content_digest,
        authority_purpose=authority_purpose,
        audience="REVIEWER",
        context=context,
        observed_at=now + timedelta(minutes=1),
    )

    assert admitted.state == "admitted_authority"
    assert admitted.binding_ref == production.binding_ref
    assert admitted.currentness_ref == packet_ref
    assert admitted.reason_codes == ()
    assert production.signature_ref in admitted.provenance_refs
    assert currentness_calls[-1] == {
        "packet_ref": packet_ref,
        "tenant_id": "tenant-a",
        "run_id": "run-a",
        "expected_consumer": "polisyos.runtime.capability_discovery",
        "expected_audience": "polisyos-runtime",
        "evaluated_at": now + timedelta(minutes=1),
    }

    unsigned = production.binding.model_copy(
        update={"capability_ref": "capability:method:unsigned"}
    )
    unsigned_ref = store.put_json(
        unsigned.model_dump(mode="json"),
        artifacts.PutOptions(
            kind=CAPABILITY_PURPOSE_BINDING_ARTIFACT_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=CAPABILITY_PURPOSE_BINDING_SCHEMA_NAME,
                version=unsigned.schema_version,
            ),
            producer=artifacts.ProducerInfo(
                component=unsigned.producer_ref,
                version=unsigned.schema_version,
            ),
        ),
    )
    unsigned_result = resolver.resolve(
        capability_ref=unsigned.capability_ref,
        content_digest=content_digest,
        authority_purpose=authority_purpose,
        audience="REVIEWER",
        context=context.model_copy(update={"binding_ref": str(unsigned_ref.artifact_id)}),
        observed_at=now + timedelta(minutes=1),
    )
    assert unsigned_result.state == "bridge_missing"
    assert "owner_binding_unsigned" in unsigned_result.reason_codes

    wrong_identity = CapabilityDiscoveryAuthorityResolver(
        production_approval_resolver=ds9,
        binding_verifier=CapabilityPurposeBindingVerifier(
            artifact_store=store,
            verifier=verifier,
            expected_signer_identity="deployment:wrong-owner",
        ),
    ).resolve(
        capability_ref=capability_ref,
        content_digest=content_digest,
        authority_purpose=authority_purpose,
        audience="REVIEWER",
        context=context,
        observed_at=now + timedelta(minutes=1),
    )
    assert wrong_identity.state == "bridge_missing"
    assert "owner_binding_signer_identity_mismatch" in wrong_identity.reason_codes

    purpose_mismatch = resolver.resolve(
        capability_ref=capability_ref,
        content_digest=content_digest,
        authority_purpose="publish_capability",
        audience="REVIEWER",
        context=context,
        observed_at=now + timedelta(minutes=1),
    )
    assert purpose_mismatch.state == "bridge_missing"
    assert "owner_binding_purpose_mismatch" in purpose_mismatch.reason_codes

    tampered = producer.issue(
        capability_ref="capability:method:tampered",
        content_digest=content_digest,
        authority_purpose=authority_purpose,
        discovery_audience="REVIEWER",
        approval_packet_ref=packet_ref,
        tenant_id="tenant-a",
        run_id="run-a",
        approval_consumer="polisyos.runtime.capability_discovery",
        approval_audience="polisyos-runtime",
        issued_at=now,
        valid_until=now + timedelta(hours=1),
    )
    blob_path, _ = store._paths(  # noqa: SLF001
        artifacts.ArtifactID.model_validate(tampered.binding_ref)
    )
    blob_path.write_bytes(blob_path.read_bytes() + b" ")
    tampered_result = resolver.resolve(
        capability_ref=tampered.binding.capability_ref,
        content_digest=content_digest,
        authority_purpose=authority_purpose,
        audience="REVIEWER",
        context=context.model_copy(update={"binding_ref": tampered.binding_ref}),
        observed_at=now + timedelta(minutes=1),
    )
    assert tampered_result.state == "bridge_missing"
    assert "owner_binding_signature_invalid" in tampered_result.reason_codes

    currentness_error.append("DS9-APPROVAL-EXPIRED")
    stale = resolver.resolve(
        capability_ref=capability_ref,
        content_digest=content_digest,
        authority_purpose=authority_purpose,
        audience="REVIEWER",
        context=context,
        observed_at=now + timedelta(minutes=2),
    )
    assert stale.state == "revalidation_required"
    assert stale.binding_ref == production.binding_ref
    assert stale.currentness_ref is None
    assert "DS9-APPROVAL-EXPIRED" in stale.reason_codes


def test_all_layer3_providers_emit_real_rejections_and_incompleteness(
    tmp_path,
    monkeypatch,
) -> None:
    """G2, G3, and all seven GL ledgers own their complete search frontiers."""
    from tests.unit.runtime.quality.test_proving_ground_causal_forecast_search import (
        _create_minimal_skg_fixture,
        _patch_skg_paths,
    )
    from tests.unit.runtime.quality.test_proving_ground_legal_mandate_search import (
        _write_minimal_legal_kg,
    )

    g2 = importlib.import_module(
        "polisyos.runtime.quality.proving_ground.causal_forecast_search"
    )
    g2_db_path, academic_root = _create_minimal_skg_fixture(tmp_path)
    with duckdb.connect(str(g2_db_path)) as con:
        con.execute(
            """
            INSERT INTO ac_skg_edges VALUES
            ('edge-2', 'policy.credit_access', 'firm.survival', 'positive', 1,
             '["work-2"]', 'panel_fe', 0.69, now())
            """
        )
    _patch_skg_paths(monkeypatch, g2, tmp_path, g2_db_path, academic_root)
    g2_request = g2.Layer3G2CausalForecastRequest(
        request_id="g2-request:owner-frontier",
        case_id="case:g2:owner-frontier",
        cause="policy.credit_access",
        effect="firm.survival",
        support_mode="exact",
        limit=1,
    )
    g2_ledger = g2.search_l2_skg_for_forecast_candidates(g2_request, tmp_path).ledger

    g3 = importlib.import_module(
        "polisyos.runtime.quality.proving_ground.proof_carrying_analytics_search"
    )
    g3_coverage = g3.build_g3_ir_catalog_coverage(tmp_path)
    g3_request = g3.Layer3G3AnalyticsRequest(
        request_id="g3-request:owner-frontier",
        claim_id="claim:g3:owner-frontier",
        case_id="case:g3:owner-frontier",
        cause="policy.credit_access",
        effect="firm.survival",
        limit=1,
    )
    g3_ledger = g3.search_ir_analytics_catalog(g3_request, g3_coverage).ledger

    gl_root = tmp_path / "gl"
    _write_minimal_legal_kg(gl_root)
    gl_db_path = gl_root / "production_data/test_lex/finalize/lex_knowledge_graph.duckdb"
    with duckdb.connect(str(gl_db_path)) as con:
        con.execute(
            """
            INSERT INTO lex_rule_thresholds VALUES
            ('threshold-owner-frontier-2', 'fact-owner-frontier-2', 'credit_gap',
             '<=', '0.09', NULL, 'ratio', 'msme_credit_program')
            """
        )
        con.execute(
            """
            INSERT INTO lex_normative_ready_facts VALUES
            ('fact-owner-frontier-2', 'Second grounded rule.', 'UA', 'economic_policy',
             '2022-03-01', '2022-12-31', 'resolved', 'legal_kg_candidate',
             'grounded', 'canonicalized', 'resolved', 'doc-owner-frontier-2', 'section-2',
             'subsidized_credit', 'threshold', 'second_credit_support_threshold')
            """
        )
        con.execute(
            """
            INSERT INTO lex_amendments VALUES
            ('amendment-owner-frontier-2', 'doc-owner-frontier-amending-2',
             'doc-owner-frontier-2', '2022-06-01', 'section-2', 'update', 0.88,
             'owner_frontier_fixture')
            """
        )
        con.execute(
            """
            INSERT INTO lex_doc_versions VALUES
            ('version-owner-frontier-2', 'doc-owner-frontier-2', 'family-owner-frontier-2',
             'v2', 'owner-002', 'resolution', 'active')
            """
        )
        con.execute(
            """
            INSERT INTO lex_doc_temporal VALUES
            ('doc-owner-frontier-2', '2022-03-01', 'resolved', 'effective',
             '2022-03-01', '2022-12-31')
            """
        )
        con.execute(
            """
            INSERT INTO lex_reference_edges VALUES
            ('ref-owner-frontier-2', 'doc-owner-frontier-2', 'doc-owner-target-2',
             'resolved', 'section-2', 'section-3', 'references', 0.89)
            """
        )
        con.execute(
            """
            INSERT INTO lex_reference_resolution_audit VALUES
            ('ref-owner-frontier-2', 'doc-owner-frontier-2', 'resolved',
             'doc-owner-target-2', 'owner_frontier_fixture', 2)
            """
        )

    gl = importlib.import_module(
        "polisyos.runtime.quality.proving_ground.legal_mandate_search"
    )
    monkeypatch.setattr(
        gl,
        "CANONICAL_L3_LEGAL_KG_PATH",
        gl_db_path.relative_to(gl_root),
    )
    gl._cached_coverage.cache_clear()  # noqa: SLF001
    gl_request = gl.Layer3GLLegalMandateRequest(
        request_id="gl-request:owner-frontier",
        claim_id="claim:gl:owner-frontier",
        case_id="case:gl:owner-frontier",
        legal_requirement_ref="legal-requirement://owner-frontier",
        jurisdiction="UA",
        policy_domain="economic_policy",
        legal_as_of="2022-03-01",
        intervention_family="subsidized_credit",
        query_terms=("credit", "threshold"),
        limit=1,
    )
    gl_ledgers = gl.build_gl_legal_search_ledgers(gl_root, (gl_request,))

    native_ledgers = (g2_ledger, g3_ledger, *gl_ledgers)
    assert len(native_ledgers) == 9
    owner_frontiers = tuple(getattr(ledger, "owner_frontier", None) for ledger in native_ledgers)
    assert all(frontier is not None for frontier in owner_frontiers)
    assert all(frontier.requested_count == 1 for frontier in owner_frontiers)
    assert all(frontier.rejected_candidates for frontier in owner_frontiers)
    assert all(
        frontier.evaluated_count
        == len(frontier.candidates) + len(frontier.rejected_candidates)
        for frontier in owner_frontiers
    )
    assert sum(frontier.completeness_status == "budget_cutoff" for frontier in owner_frontiers) == 8
    assert sum(
        frontier.completeness_status == "complete_no_match" for frontier in owner_frontiers
    ) == 1
    assert all(
        frontier.incompleteness_reasons == ("owner_budget_cutoff",)
        for frontier in owner_frontiers
        if frontier.completeness_status == "budget_cutoff"
    )

    discovery = importlib.import_module("polisyos.runtime.quality.capability_discovery")
    project = getattr(discovery, "project_layer3_owner_frontier", None)
    assert callable(project)
    assert all(
        project(frontier).model_dump(mode="json") == frontier.model_dump(mode="json")
        for frontier in owner_frontiers
    )


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        ("index_stale", "owner_snapshot_expired"),
        ("producer_unavailable", "owner_connector_unavailable"),
        ("recall_unmeasured", "owner_recall_not_measured"),
        ("budget_cutoff", "owner_budget_cutoff"),
    ],
)
def test_incomplete_selected_row_is_not_a_discovery_positive(
    status: str,
    reason: str,
) -> None:
    calls: list[str] = []
    capability_ref = f"capability:method:{status}"
    incomplete = _provider_result(
        "method",
        capability_ref,
        completeness_status=status,
        incompleteness_reasons=(reason,),
    )
    current = _provider_result("method", capability_ref)

    response = _composer(providers=(_Provider(incomplete, calls),)).search(
        _request(("method",)), meta=ApiMeta(request_id=f"http:{status}-selected")
    )
    current_response = _composer(providers=(_Provider(current, []),)).search(
        _request(("method",)), meta=ApiMeta(request_id=f"http:{status}-current")
    )

    item = response.results[0]
    current_item = current_response.results[0]
    assert item.discovery_result.state == status
    assert item.discovery_result.reason_codes == (reason,)
    assert item.execution_result == current_item.execution_result
    assert item.execution_result.state == "not_established"
    assert item.authority_result == current_item.authority_result
    assert item.authority_result.state == "bridge_missing"


def test_agent_result_requires_exact_scientist_registry_owner_evidence() -> None:
    with pytest.raises(ValueError, match="ScientistRegistryOwnerReceipt"):
        _provider_result(
            "agent",
            "capability:agent:world-model",
            receipt_kind="capability_index",
        )

    l4_row = _row("capability:agent:world-model", "agent")
    payload = l4_row.model_dump(mode="python")
    payload["owner_truth"] = None
    payload["provenance_refs"] = ("world-model:l4-agent-row",)
    with pytest.raises(ValueError, match="ScientistCapabilityOwnerTruth"):
        CapabilityIndexDiscoveryRow.model_validate(payload)

    valid_agent = _provider_result("agent", "capability:agent:scientist-node")
    mismatched = valid_agent.model_dump(mode="python")
    mismatched["rows"][0]["owner_truth"]["registry_snapshot_digest"] = "sha256:" + "9" * 64
    with pytest.raises(ValueError, match="typed registry snapshot"):
        CapabilityProviderSearchResult.model_validate(mismatched)


def test_current_scientist_registry_receipt_admits_candidate_discovery_only() -> None:
    calls: list[str] = []
    agent = _provider_result("agent", "capability:agent:scientist-node")

    response = _composer(providers=(_Provider(agent, calls),)).search(
        _request(("agent",)), meta=ApiMeta(request_id="http:scientist-agent")
    )

    item = response.results[0]
    assert item.discovery_result.state == "discoverable"
    assert item.execution_result.state == "not_established"
    assert item.authority_result.state == "bridge_missing"


def test_lex_provider_uses_real_legal_owner_snapshot_and_admission_rows(tmp_path) -> None:
    """A Lex provider must project the real admitted legal index rather than a test row."""
    capability_index = _fixture_capability_index(tmp_path)
    expected = next(
        row
        for row in build_capability_discovery_snapshot(capability_index)
        if row.resource_kind == "legal_norm"
    )
    provider = LexCapabilityDiscoveryProvider(capability_index=capability_index)
    request = _request(("legal_norm",)).model_copy(
        update={
            "search": _request(("legal_norm",)).search.model_copy(
                update={
                    "query_text": expected.label,
                    "construct_refs": expected.construct_refs,
                }
            )
        }
    )

    result = provider.search(request)
    response = _composer(providers=(provider,)).search(
        request, meta=ApiMeta(request_id="http:lex-owner")
    )

    assert tuple(row.capability_ref for row in result.rows) == (expected.capability_ref,)
    assert tuple(candidate.candidate_ref for candidate in result.ledger.candidates) == (
        expected.capability_ref,
    )
    assert result.ledger.rejected_candidates == ()
    assert result.completeness_status == "complete"
    assert result.owner_receipt.lex_snapshot_ref == expected.snapshot_ref
    assert result.owner_receipt.verifier_ref in result.owner_receipt.provenance_refs
    assert response.results[0].capability_ref == expected.capability_ref
    assert response.results[0].resource_kind == "legal_norm"
    assert response.results[0].discovery_result.state == "discoverable"
    assert response.results[0].authority_result.state == "bridge_missing"


def test_lex_provider_empty_query_searches_the_complete_owner_index(tmp_path) -> None:
    """An explicit empty query is match-all, never a magic authored token."""
    capability_index = _fixture_capability_index(tmp_path)
    expected_refs = tuple(
        sorted(
            row.capability_ref
            for row in build_capability_discovery_snapshot(capability_index)
            if row.resource_kind == "legal_norm"
        )
    )
    request = _request(("legal_norm",)).model_copy(
        update={
            "search": _request(("legal_norm",)).search.model_copy(
                update={
                    "query_text": "*",
                    "construct_refs": ("*",),
                    "budget": {
                        "match_all": True,
                        "top_k": len(expected_refs),
                    },
                }
            )
        }
    )

    result = LexCapabilityDiscoveryProvider(capability_index=capability_index).search(request)

    assert tuple(row.capability_ref for row in result.rows) == expected_refs
    assert tuple(candidate.candidate_ref for candidate in result.ledger.candidates) == expected_refs
    assert result.ledger.no_hit_frontier == ()
    assert result.completeness_status == "complete"


def test_lex_provider_rejects_unbound_match_all_proxy(tmp_path) -> None:
    """A punctuation-only query cannot imply match-all without the explicit intent."""
    request = _request(("legal_norm",)).model_copy(
        update={
            "search": _request(("legal_norm",)).search.model_copy(
                update={
                    "query_text": "*",
                    "construct_refs": ("*",),
                    "budget": {"top_k": 5},
                }
            )
        }
    )

    with pytest.raises(
        CapabilityProviderUnavailableError,
        match="lex_owner_query_terms_missing",
    ):
        LexCapabilityDiscoveryProvider(capability_index=_fixture_capability_index(tmp_path)).search(
            request
        )


def test_lex_provider_records_budget_rejection_and_no_hit_frontier(tmp_path) -> None:
    """A real owner query records omitted matches instead of hiding the cutoff."""
    capability_index = _fixture_capability_index(tmp_path)
    legal_row = next(
        row
        for row in build_capability_discovery_snapshot(capability_index)
        if row.resource_kind == "legal_norm"
    )
    request = _request(("legal_norm",)).model_copy(
        update={
            "search": _request(("legal_norm",)).search.model_copy(
                update={
                    "query_text": legal_row.label,
                    "construct_refs": legal_row.construct_refs,
                    "budget": {"top_k": 0},
                }
            )
        }
    )

    result = LexCapabilityDiscoveryProvider(capability_index=capability_index).search(request)

    assert result.rows == ()
    assert result.actual_cutoff == 0
    assert result.completeness_status == "budget_cutoff"
    assert result.incompleteness_reasons == ("lex_owner_budget_cutoff",)
    assert result.ledger.no_hit_frontier == ("legal_norm",)
    assert tuple(candidate.candidate_ref for candidate in result.ledger.rejected_candidates) == (
        legal_row.capability_ref,
    )
    assert result.ledger.rejected_candidates[0].limitation_refs == ("lex_owner_budget_cutoff",)


def test_lex_provider_stale_snapshot_stays_a_typed_discovery_negative(tmp_path) -> None:
    """A stale legal release cannot turn discoverable because its row still matches."""
    capability_index = _fixture_capability_index(tmp_path)
    legal = next(
        capability
        for capability in capability_index.capabilities
        if "lex_norm" in capability.modality
    )
    stale_legal = legal.model_copy(
        update={
            "freshness_envelope": FreshnessEnvelope(
                freshness_class="stale_legal_release",
                source_release_ref=legal.freshness_envelope.source_release_ref,
            )
        }
    )
    stale_index = capability_index.model_copy(
        update={
            "capabilities": tuple(
                stale_legal if capability.capability_id == legal.capability_id else capability
                for capability in capability_index.capabilities
            )
        }
    )
    stale_row = next(
        row
        for row in build_capability_discovery_snapshot(stale_index)
        if row.resource_kind == "legal_norm"
    )
    request = _request(("legal_norm",)).model_copy(
        update={
            "search": _request(("legal_norm",)).search.model_copy(
                update={
                    "query_text": stale_row.label,
                    "construct_refs": stale_row.construct_refs,
                }
            )
        }
    )

    response = _composer(
        providers=(LexCapabilityDiscoveryProvider(capability_index=stale_index),)
    ).search(request, meta=ApiMeta(request_id="http:lex-stale"))

    assert response.results[0].discovery_result.state == "index_stale"
    assert response.results[0].discovery_result.reason_codes == (
        "lex_owner_snapshot_stale",
        "index_snapshot_stale",
    )


def test_lex_provider_malformed_owner_index_is_typed_unavailable() -> None:
    """Opaque input cannot be recast as an empty legal-index success."""
    response = _composer(
        providers=(LexCapabilityDiscoveryProvider(capability_index=object()),)  # type: ignore[arg-type]
    ).search(_request(("legal_norm",)), meta=ApiMeta(request_id="http:lex-invalid"))

    assert response.results == ()
    assert response.frontier.completeness_status == "producer_unavailable"
    assert response.frontier.incompleteness_reasons == ("legal_norm:lex_owner_index_invalid",)


def test_mixed_status_provider_permutation_does_not_change_composed_packet() -> None:
    """Mixed-status precedence is request-owned, not mapping-insertion-owned."""
    first_calls: list[str] = []
    second_calls: list[str] = []
    method = _provider_result(
        "method",
        "capability:method:generated",
        completeness_status="index_stale",
        incompleteness_reasons=("method_snapshot_expired",),
    )
    dataset = _provider_result("dataset", "capability:dataset:generated")
    request = _request(("method", "dataset"))
    first = _composer(
        providers=(_Provider(method, first_calls), _Provider(dataset, first_calls))
    ).search(request, meta=ApiMeta(request_id="http:test"))
    second = _composer(
        providers=(_Provider(dataset, second_calls), _Provider(method, second_calls))
    ).search(request, meta=ApiMeta(request_id="http:test"))

    assert first_calls == second_calls == ["method", "dataset"]
    assert first.frontier.completeness_status == "index_stale"
    assert first.results[0].discovery_result.state == "index_stale"
    assert first.results[1].discovery_result.state == "discoverable"
    assert first.model_dump(mode="json", exclude={"meta": {"generated_at"}}) == (
        second.model_dump(mode="json", exclude={"meta": {"generated_at"}})
    )


def test_complete_federation_with_one_no_hit_and_one_hit_is_complete() -> None:
    calls: list[str] = []
    method = _provider_result("method", "capability:method:generated")
    dataset = _provider_result(
        "dataset",
        None,
        completeness_status="complete_no_match",
        incompleteness_reasons=(),
    )

    response = _composer(providers=(_Provider(method, calls), _Provider(dataset, calls))).search(
        _request(("method", "dataset")),
        meta=ApiMeta(request_id="http:mixed-complete"),
    )

    assert response.frontier.completeness_status == "complete"
    assert tuple(item.capability_ref for item in response.results) == (
        "capability:method:generated",
    )


def test_case_provider_missing_is_typed_and_frontier_is_incomplete() -> None:
    """The absent global case index is not converted into an empty success."""
    response = _composer(providers=()).search(
        _request(("case",)), meta=ApiMeta(request_id="http:case")
    )

    assert response.results == ()
    assert response.frontier.completeness_status == "producer_missing"
    assert response.frontier.incompleteness_reasons == ("case:producer_missing",)
    assert response.frontier.no_hit_frontier == ("case",)
    replay = subprocess.run(  # noqa: S603
        shlex.split(response.frontier.replay_command),
        check=True,
        capture_output=True,
        text=True,
    )
    assert replay.stdout.strip() == response.frontier.replay_expected_output_hash


def test_distinct_no_hit_recall_stale_cutoff_and_outage_results_survive() -> None:
    """Federation must preserve distinct owner frontier failures."""
    cases = (
        ("complete_no_match", (), "complete_no_match"),
        ("recall_unmeasured", ("recall_not_measured",), "recall_unmeasured"),
        ("index_stale", ("snapshot_expired",), "index_stale"),
        ("budget_cutoff", ("row_budget_exhausted",), "budget_cutoff"),
        ("producer_unavailable", ("provider_outage",), "producer_unavailable"),
    )
    for source_status, reasons, expected in cases:
        calls: list[str] = []
        result = _provider_result(
            "method",
            None,
            completeness_status=source_status,
            incompleteness_reasons=reasons,
        )
        response = _composer(providers=(_Provider(result, calls),)).search(
            _request(("method",)), meta=ApiMeta(request_id=f"http:{source_status}")
        )
        assert response.frontier.completeness_status == expected
        assert response.frontier.incompleteness_reasons == reasons
        assert response.results == ()


def test_provider_outage_is_typed_instead_of_an_empty_success() -> None:
    response = _composer(providers=(_UnavailableProvider(),)).search(
        _request(("source",)), meta=ApiMeta(request_id="http:outage")
    )

    assert response.results == ()
    assert response.frontier.completeness_status == "producer_unavailable"
    assert response.frontier.incompleteness_reasons == ("source:connector_registry_outage",)


def test_selected_rejected_cutoff_index_freshness_and_incompleteness_are_owner_values() -> None:
    """The federation projects the actual owner ledger rather than rebuilding it."""
    calls: list[str] = []
    result = _provider_result(
        "dataset",
        "capability:dataset:selected",
        rejected_ref="capability:dataset:rejected",
        completeness_status="budget_cutoff",
        incompleteness_reasons=("owner_budget_cutoff",),
        actual_cutoff=1,
    )
    response = _composer(providers=(_Provider(result, calls),)).search(
        _request(("dataset",)), meta=ApiMeta(request_id="http:frontier")
    )

    assert tuple(row.candidate_ref for row in response.frontier.candidates) == (
        "capability:dataset:selected",
    )
    assert tuple(row.candidate_ref for row in response.frontier.rejected_candidates) == (
        "capability:dataset:rejected",
    )
    assert response.frontier.actual_cutoff == 1
    assert response.frontier.indexes_used == ("index:dataset:owner",)
    assert response.frontier.index_freshness == {
        "index:dataset:owner": {"state": "current", "observed_at": NOW.isoformat()}
    }
    assert response.frontier.incompleteness_reasons == ("owner_budget_cutoff",)


def test_replay_rebuilds_complete_frontier_and_binds_every_owner_field(capsys) -> None:
    calls: list[str] = []
    result = _provider_result(
        "dataset",
        "capability:dataset:selected",
        rejected_ref="capability:dataset:rejected",
        completeness_status="budget_cutoff",
        incompleteness_reasons=("owner_budget_cutoff",),
        actual_cutoff=1,
    )
    response = _composer(providers=(_Provider(result, calls),)).search(
        _request(("dataset",)), meta=ApiMeta(request_id="http:replay-complete")
    )
    payload_hex = shlex.split(response.frontier.replay_command)[-1]
    packet = json.loads(bytes.fromhex(payload_hex).decode("utf-8"))

    owner = packet["provider_results"][0]
    assert owner["ledger"]["candidates"][0]["candidate_ref"] == ("capability:dataset:selected")
    assert owner["ledger"]["rejected_candidates"][0]["candidate_ref"] == (
        "capability:dataset:rejected"
    )
    assert owner["actual_cutoff"] == 1
    assert owner["completeness_status"] == "budget_cutoff"

    assert main(["--replay-frontier", payload_hex]) == 0
    baseline = capsys.readouterr().out.strip()
    assert baseline == response.frontier.replay_expected_output_hash

    mutations = (
        ("request", ("request", "search", "query_text"), "mutated query"),
        ("row", ("provider_results", 0, "rows", 0, "label"), "mutated label"),
        (
            "selected",
            ("provider_results", 0, "ledger", "candidates", 0, "score"),
            0.7,
        ),
        (
            "rejected",
            ("provider_results", 0, "ledger", "rejected_candidates", 0, "score"),
            0.6,
        ),
        (
            "no-hit",
            ("provider_results", 0, "ledger", "no_hit_frontier"),
            ["dataset"],
        ),
        (
            "indexes",
            ("provider_results", 0, "ledger", "indexes_used", 0),
            "index:dataset:mutated",
        ),
        (
            "freshness",
            (
                "provider_results",
                0,
                "ledger",
                "index_freshness",
                "index:dataset:owner",
                "state",
            ),
            "stale",
        ),
        ("cutoff", ("provider_results", 0, "actual_cutoff"), 2),
        ("requested-count", ("provider_results", 0, "requested_count"), 6),
        ("evaluated-count", ("provider_results", 0, "evaluated_count"), 3),
        (
            "completeness",
            ("provider_results", 0, "completeness_status"),
            "index_stale",
        ),
        (
            "reasons",
            ("provider_results", 0, "incompleteness_reasons", 0),
            "mutated_reason",
        ),
    )
    for label, path, replacement in mutations:
        mutated = copy.deepcopy(packet)
        target = mutated
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = replacement
        mutated_hex = json.dumps(mutated, sort_keys=True, separators=(",", ":")).encode().hex()

        try:
            main(["--replay-frontier", mutated_hex])
        except (ValueError, TypeError):
            continue
        assert capsys.readouterr().out.strip() != baseline, label


def _composer(*, providers: tuple[CapabilityDiscoveryProvider, ...]) -> CapabilityDiscoveryComposer:
    policy = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="embedded",
        state_store_backend="sqlite",
        sqlite_path=":memory:",
        postgres_dsn=None,
    )
    return CapabilityDiscoveryComposer(
        providers=providers,
        execution_resolver=CapabilityExecutionResolver(
            operation_registry=None,
            conformance_verifier=None,
            policy_resolver=policy,
        ),
        authority_resolver=CapabilityDiscoveryAuthorityResolver(production_approval_resolver=None),
        observed_at=lambda: NOW,
    )


def _fixture_capability_index(tmp_path):
    """Build the real fixture owner index used by Lex-provider tests."""
    result = _fixture_capability_index_build(tmp_path)
    assert result.capability_index is not None
    return result.capability_index


def _fixture_capability_index_build(tmp_path):
    """Build the persisted fixture release used by default-provider tests."""
    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    return compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "capability-index",
            mode="fixture",
            generated_at="2026-05-25T00:00:00Z",
        )
    )


def _request(resource_kinds: tuple[str, ...]) -> CapabilityDiscoveryRequest:
    return CapabilityDiscoveryRequest(
        search=SearchRequest(
            request_id="search:generated",
            query_text="generated capability",
            construct_refs=("construct:generated",),
            intent="capability_discovery",
            required_layers=("runtime_registry",),
            authority_purpose="review_capability_candidates",
            allowed_modes=("exact",),
            budget={"top_k": 5},
            rule_version="policyos.ds10.discovery.v1",
        ),
        resource_kinds=resource_kinds,
        audience="REVIEWER",
    )


def _provider_result(
    resource_kind: str,
    selected_ref: str | None,
    *,
    rejected_ref: str | None = None,
    completeness_status: str = "complete",
    incompleteness_reasons: tuple[str, ...] = (),
    actual_cutoff: int | None = None,
    receipt_kind: str | None = None,
) -> CapabilityProviderSearchResult:
    selected = (_candidate(selected_ref, resource_kind),) if selected_ref else ()
    rejected = (_candidate(rejected_ref, resource_kind),) if rejected_ref else ()
    search_snapshot_ref = f"snapshot:{resource_kind}:owner"
    profile_snapshot_ref = "source-profile-registry:snapshot:test"
    connector_snapshot_ref = "connector-registry:snapshot:test"
    node_snapshot_ref = "scientist:node-registry:snapshot:test"
    tool_snapshot_ref = "scientist:tool-registry:snapshot:test"
    verifier_ref = "lex:grounding-verifier:test"
    if resource_kind == "source":
        search_snapshot_digest = "sha256:" + _test_digest(
            {
                "profile_registry_snapshot_ref": profile_snapshot_ref,
                "profile_registry_snapshot_digest": "sha256:" + "4" * 64,
                "connector_snapshot_ref": connector_snapshot_ref,
                "connector_snapshot_digest": "sha256:" + "5" * 64,
            }
        )
    elif resource_kind == "agent":
        search_snapshot_digest = "sha256:" + _test_digest(
            {
                "node_registry_snapshot_ref": node_snapshot_ref,
                "node_registry_snapshot_digest": "sha256:" + "7" * 64,
                "tool_registry_snapshot_ref": tool_snapshot_ref,
                "tool_registry_snapshot_digest": "sha256:" + "8" * 64,
            }
        )
    elif resource_kind == "legal_norm":
        search_snapshot_digest = "sha256:" + "6" * 64
    else:
        search_snapshot_digest = "sha256:" + "1" * 64
    ledger = SearchLedger(
        request_ref="search:generated",
        query_plan={"match": "owner_defined"},
        corpus_ref=f"corpus:{resource_kind}:owner",
        corpus_path=f"owner/{resource_kind}",
        corpus_snapshot_hash=search_snapshot_digest,
        corpus_kind="canonical",
        indexes_used=(f"index:{resource_kind}:owner",),
        index_version_refs=(f"snapshot:{resource_kind}:owner",),
        index_freshness={
            f"index:{resource_kind}:owner": {
                "state": "current",
                "observed_at": NOW.isoformat(),
            }
        },
        candidates=selected,
        rejected_candidates=rejected,
        no_hit_frontier=(() if selected else (resource_kind,)),
        incompleteness={"status": completeness_status},
        replay_key=f"replay:{resource_kind}:owner",
        replay_command=f"owner-search --kind {resource_kind}",
        replay_expected_output_hash="sha256:" + "2" * 64,
    )
    rows = (_row(selected_ref, resource_kind),) if selected_ref else ()
    payload = {
        "resource_kind": resource_kind,
        "producer_ref": f"producer:{resource_kind}:owner",
        "rows": rows,
        "ledger": ledger,
        "requested_count": 5,
        "evaluated_count": len(selected) + len(rejected),
        "actual_cutoff": actual_cutoff,
        "completeness_status": completeness_status,
        "incompleteness_reasons": incompleteness_reasons,
    }
    payload_json = {
        **payload,
        "rows": [row.model_dump(mode="json") for row in rows],
        "ledger": ledger.model_dump(mode="json"),
    }
    result_digest = "sha256:" + _test_digest(payload_json)
    owner_kind = receipt_kind or resource_kind
    provenance_refs = [
        f"provenance:{resource_kind}:owner",
        payload["producer_ref"],
        search_snapshot_ref,
    ]
    if owner_kind in {"method", "dataset", "capability_index"}:
        provenance_refs.append(f"release:{resource_kind}:owner")
    elif owner_kind == "source":
        provenance_refs.extend((profile_snapshot_ref, connector_snapshot_ref))
    elif owner_kind == "legal_norm":
        provenance_refs.append(verifier_ref)
    elif owner_kind == "agent":
        provenance_refs.extend((node_snapshot_ref, tool_snapshot_ref))
    common = {
        "owner_producer_ref": payload["producer_ref"],
        "search_snapshot_ref": search_snapshot_ref,
        "search_snapshot_digest": ledger.corpus_snapshot_hash,
        "result_digest": result_digest,
        "provenance_refs": tuple(provenance_refs),
    }
    if owner_kind in {"method", "dataset", "capability_index"}:
        receipt = CapabilityIndexOwnerReceipt(
            resource_kind=(resource_kind if resource_kind in {"method", "dataset"} else "method"),
            index_release_ref=f"release:{resource_kind}:owner",
            **common,
        )
    elif owner_kind == "source":
        receipt = SourceProfileOwnerReceipt(
            profile_registry_snapshot_ref=profile_snapshot_ref,
            profile_registry_snapshot_digest="sha256:" + "4" * 64,
            connector_snapshot_ref=connector_snapshot_ref,
            connector_snapshot_digest="sha256:" + "5" * 64,
            **common,
        )
    elif owner_kind == "legal_norm":
        receipt = LexOwnerReceipt(
            lex_snapshot_ref=search_snapshot_ref,
            lex_snapshot_digest=search_snapshot_digest,
            verifier_ref=verifier_ref,
            **common,
        )
    elif owner_kind == "agent":
        receipt = ScientistRegistryOwnerReceipt(
            node_registry_snapshot_ref=node_snapshot_ref,
            node_registry_snapshot_digest="sha256:" + "7" * 64,
            tool_registry_snapshot_ref=tool_snapshot_ref,
            tool_registry_snapshot_digest="sha256:" + "8" * 64,
            **common,
        )
    else:
        raise AssertionError(f"unsupported owner kind: {owner_kind}")
    return CapabilityProviderSearchResult(**payload, owner_receipt=receipt)


def _candidate(ref: str, resource_kind: str) -> SearchCandidate:
    return SearchCandidate(
        candidate_ref=ref,
        source_layer="owner",
        match_mode="exact",
        score=0.8,
        evidence_refs=(f"evidence:{resource_kind}:owner",),
        authority_boundary={"authoritative_for": []},
        may_not_use_for=("publication_authority",),
    )


def _row(ref: str, resource_kind: str) -> CapabilityIndexDiscoveryRow:
    owner_truth = None
    if resource_kind == "legal_norm":
        owner_truth = LegalNormOwnerTruth(
            legal_norm_ref=ref,
            normative_fact_ref="lex:fact:test",
            source_document_ref="lex:document:test",
            provision_citation="Art. 1",
            grounding_status="grounded",
            hallucination_status="verified_clear",
            jurisdiction="UA",
            effective_from=date(2026, 1, 1),
            effective_to=None,
            temporal_state="effective",
            temporal_resolution_status="resolved",
            temporal_snapshot_at=NOW,
            temporal_audit_ref="lex:temporal-audit:test",
            provenance_refs=("provenance:legal_norm:owner",),
        )
    elif resource_kind == "agent":
        owner_truth = ScientistCapabilityOwnerTruth(
            capability_ref=ref,
            registry_kind="node_registry",
            registry_schema_ref="scientist.node_registry.v1",
            registry_entry_ref="scientist:node:test",
            registry_snapshot_ref="scientist:node-registry:snapshot:test",
            registry_snapshot_digest="sha256:" + "7" * 64,
            provenance_refs=("provenance:agent:owner",),
        )
    return CapabilityIndexDiscoveryRow(
        capability_ref=ref,
        content_digest="sha256:" + "3" * 64,
        resource_kind=resource_kind,
        construct_refs=("construct:generated",),
        label="Generated owner row",
        description="Owner-projected row for federation tests.",
        producer_ref=f"producer:{resource_kind}:owner",
        snapshot_ref=f"snapshot:{resource_kind}:owner",
        freshness_ref=f"freshness:{resource_kind}:owner",
        provenance_refs=(f"provenance:{resource_kind}:owner",),
        owner_truth=owner_truth,
        may_not_use_for=("publication_authority",),
        time=CapabilityTimeSemantics(
            observed_at=NOW,
            valid_from=NOW,
            valid_until=NOW + timedelta(hours=1),
            freshness="current",
        ),
    )


def _test_digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
