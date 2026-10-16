"""Semantic integration tests for the candidate-only Legal discovery bridge."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

import polisyos.runtime.quality.capability_discovery as capability_discovery_module
from polisyos.core.contracts.capability_discovery import (
    CapabilityDiscoveryRequest,
    CapabilityTimeSemantics,
)
from polisyos.core.contracts.runtime import ApiMeta
from polisyos.core.contracts.search import SearchRequest
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.services.control_registry_providers import (
    resolve_control_registry_providers,
)
from polisyos.runtime.quality.capability_authority import (
    CapabilityDiscoveryAuthorityResolver,
)
from polisyos.runtime.quality.capability_discovery import (
    CapabilityDiscoveryComposer,
    CapabilityProviderUnavailableError,
    LexCandidateCapabilityDiscoveryProvider,
    LexCandidateOwnerReceipt,
    LexCapabilityDiscoveryProvider,
    LexOwnerReceipt,
    load_capability_index_release,
)
from polisyos.runtime.quality.capability_index import (
    CapabilityIndex,
    CapabilityIndexDiscoveryRow,
    LegalNormCandidateEvidence,
    LegalNormCandidateSourceProfileAsset,
    LegalNormOwnerTruth,
)
from polisyos.runtime.quality.capability_index_compiler import (
    CapabilityIndexCompilerConfig,
    _build_legal_candidate_snapshot,
    build_capability_discovery_snapshot,
    compile_capability_index,
    create_capability_index_fixture_inputs,
)
from polisyos.runtime.quality.capability_resolver import CapabilityExecutionResolver


class _EmptyRegistry:
    def query_entries(self, *args: object, **kwargs: object) -> list[object]:
        return []

    def get(self, *args: object, **kwargs: object) -> None:
        return None

    def list_all(self, *args: object, **kwargs: object) -> list[object]:
        return []

    def list_by_family(self, *args: object, **kwargs: object) -> list[object]:
        return []


def _request() -> CapabilityDiscoveryRequest:
    return CapabilityDiscoveryRequest(
        search=SearchRequest(
            request_id="search:legal-threshold-candidate",
            query_text="employee count",
            construct_refs=("construct:employee_count",),
            intent="capability_discovery",
            required_layers=("runtime_registry",),
            authority_purpose="review_capability_candidates",
            allowed_modes=("exact", "lexical"),
            budget={"top_k": 5},
            rule_version="policyos.ds10.discovery.v1",
        ),
        resource_kinds=("legal_norm",),
        audience="REVIEWER",
    )


def test_selected_legal_candidate_persists_and_composes_without_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run compiler → persisted read → default provider → composer and falsifiers."""
    production_data = create_capability_index_fixture_inputs(tmp_path / "production_data")
    build = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=production_data,
            output_dir=tmp_path / "release",
            mode="fixture",
            generated_at="2026-05-25T00:00:00Z",
        )
    )
    assert build.capability_index is not None
    emitted = build.capability_index.metadata["legal_norm_candidate_index_snapshot"]
    assert emitted["selected_candidate_count"] == emitted["source_candidate_count"] == 1
    assert emitted["completeness"] == "complete"

    monkeypatch.setenv("POLISYOS_CAPABILITY_INDEX_PATH", str(build.primary_duckdb_path))
    loaded = load_capability_index_release(build.primary_duckdb_path)
    snapshot = loaded.metadata["legal_norm_candidate_index_snapshot"]
    assert snapshot["source_profile_id"] == "l3_lex_kg"
    assert snapshot["source_root_ref"] == f"production-data:{production_data.name}"
    assert snapshot["source_profile_digest"].startswith("sha256:")
    assert snapshot["source_path_ref"] == snapshot["source_profile_assets"][0]["path"]
    assert snapshot["source_selection_rule_version"] == "lex_kg_first_sorted_path.v1"
    assert snapshot["generation_basis_digest"].startswith("sha256:")
    assert snapshot["source_selection_digest"].startswith("sha256:")

    registry = _EmptyRegistry()
    bundle = resolve_control_registry_providers(
        connectors=registry,
        source_profiles=registry,
        binding_profiles=registry,
        model_profiles=registry,
        gy_catalog_graph=object(),
    )
    legal = tuple(
        p for p in bundle.capability_discovery_providers if p.resource_kind == "legal_norm"
    )
    assert len(legal) == 1
    assert type(legal[0]) is LexCandidateCapabilityDiscoveryProvider
    request = _request()
    provider_result = legal[0].search(request)
    assert provider_result.completeness_status == "complete"
    assert len(provider_result.rows) == 1
    assert type(provider_result.rows[0].owner_truth) is LegalNormCandidateEvidence
    assert type(provider_result.owner_receipt) is LexCandidateOwnerReceipt
    assert not hasattr(provider_result.owner_receipt, "verifier_ref")
    assert provider_result.owner_receipt.source_relation_refusal_status == "verification_missing"
    assert provider_result.owner_receipt.candidate_inventory_digest.startswith("sha256:")

    policy = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="embedded",
        state_store_backend="sqlite",
        sqlite_path=":memory:",
        postgres_dsn=None,
    )
    composer = CapabilityDiscoveryComposer(
        providers=bundle.capability_discovery_providers,
        execution_resolver=CapabilityExecutionResolver(
            operation_registry=None,
            conformance_verifier=None,
            policy_resolver=policy,
        ),
        authority_resolver=CapabilityDiscoveryAuthorityResolver(production_approval_resolver=None),
        observed_at=lambda: datetime(2026, 8, 25, tzinfo=UTC),
    )
    response = composer.search(request, meta=ApiMeta(request_id="http:legal-candidate"))
    assert len(response.results) == 1
    item = response.results[0]
    assert item.discovery_result.state == "discoverable"
    assert item.execution_result.state != "executable"
    assert item.authority_result.state == "bridge_missing"
    assert item.authoritative_for == ()
    assert "legal_source_relation_verification_not_established" in item.may_not_use_for

    candidate_provider = LexCandidateCapabilityDiscoveryProvider(
        capability_index_loader=lambda: loaded
    )

    def rejects(snapshot_payload: dict[str, object]) -> None:
        damaged = loaded.model_copy(
            update={
                "metadata": {
                    **loaded.metadata,
                    "legal_norm_candidate_index_snapshot": snapshot_payload,
                }
            }
        )
        with pytest.raises(CapabilityProviderUnavailableError) as raised:
            LexCandidateCapabilityDiscoveryProvider(capability_index_loader=lambda: damaged).search(
                request
            )
        assert raised.value.reason_code == "lex_candidate_inventory_invalid"

    changed_bytes = deepcopy(snapshot)
    changed_bytes["records"][0]["threshold"]["value_decimal"] = "999"
    rejects(changed_bytes)

    missing_candidate = deepcopy(snapshot)
    missing_candidate["records"] = []
    rejects(missing_candidate)

    absent_metadata = {
        key: value
        for key, value in loaded.metadata.items()
        if key != "legal_norm_candidate_index_snapshot"
    }
    absent_index = CapabilityIndex.model_validate(
        {**loaded.model_dump(mode="python"), "metadata": absent_metadata}
    )
    with pytest.raises(CapabilityProviderUnavailableError) as absent:
        LexCandidateCapabilityDiscoveryProvider(
            capability_index_loader=lambda: absent_index
        ).search(request)
    assert absent.value.reason_code == "lex_candidate_inventory_invalid"

    wrong_root = deepcopy(snapshot)
    wrong_root["source_root_ref"] = "production-data:other-root"
    rejects(wrong_root)

    wrong_profile = deepcopy(snapshot)
    wrong_profile["source_profile_assets"][0]["fingerprint"] = "0" * 64
    rejects(wrong_profile)

    wrong_member = deepcopy(snapshot)
    wrong_member["generation_basis_digest"] = "sha256:" + "0" * 64
    rejects(wrong_member)

    source_record = provider_result.rows[0].owner_truth
    assert type(source_record) is LegalNormCandidateEvidence
    payload = source_record.model_dump(mode="json", exclude={"source_content_digest"})
    payload["fact_binding_status"] = "fact_missing"
    payload["source_fact_refs"] = ()
    payload["selection_disposition"] = "excluded"
    payload["selection_reasons"] = ("legal_candidate_fact_missing",)
    payload["source_asset_refs"] = tuple(
        ref for ref in payload["source_asset_refs"] if ":lex_normative_facts:" not in ref
    )
    # Build a valid candidate row whose fact binding is explicitly incomplete.
    from polisyos.runtime.quality.capability_index import (
        _legal_candidate_content_digest,
    )

    def index_with_candidate_snapshot(
        snapshot_payload: dict[str, object],
    ) -> CapabilityIndex:
        return CapabilityIndex.model_validate(
            {
                **loaded.model_dump(mode="python"),
                "metadata": {
                    **loaded.metadata,
                    "legal_norm_candidate_index_snapshot": snapshot_payload,
                },
            }
        )

    payload["source_content_digest"] = _legal_candidate_content_digest(payload)
    incomplete_record = LegalNormCandidateEvidence.model_validate_json(
        json.dumps(payload, ensure_ascii=False)
    )
    profile_assets = tuple(
        LegalNormCandidateSourceProfileAsset.model_validate(asset)
        for asset in snapshot["source_profile_assets"]
    )
    common = {
        "compiler_release_ref": snapshot["compiler_release_ref"],
        "source_release_ref": snapshot["source_release_ref"],
        "source_path_ref": snapshot["source_path_ref"],
        "source_root_ref": snapshot["source_root_ref"],
        "source_profile_digest": snapshot["source_profile_digest"],
        "source_profile_assets": profile_assets,
        "source_table_present": True,
        "source_candidate_count": 1,
        "candidate_limit": 1,
    }
    incomplete = _build_legal_candidate_snapshot(
        **common,
        records=(incomplete_record,),
        incompleteness_reasons=("legal_candidate_fact_binding_incomplete",),
    ).model_dump(mode="json")
    fact_limited = LexCandidateCapabilityDiscoveryProvider(
        capability_index_loader=lambda: index_with_candidate_snapshot(incomplete)
    ).search(request)
    assert fact_limited.completeness_status == "recall_unmeasured"
    assert fact_limited.incompleteness_reasons == ("legal_candidate_fact_binding_incomplete",)
    assert fact_limited.rows == ()
    assert fact_limited.evaluated_count == 0

    empty = _build_legal_candidate_snapshot(
        **{**common, "candidate_limit": 0},
        records=(),
        incompleteness_reasons=("legal_candidate_budget_cutoff",),
    ).model_dump(mode="json")
    empty_result = LexCandidateCapabilityDiscoveryProvider(
        capability_index_loader=lambda: index_with_candidate_snapshot(empty)
    ).search(request)
    assert empty_result.completeness_status == "recall_unmeasured"

    budget_request = request.model_copy(
        update={"search": request.search.model_copy(update={"budget": {"top_k": 0}})}
    )
    assert candidate_provider.search(budget_request).completeness_status == "budget_cutoff"

    # This synthetic typed sibling exercises the existing verified-owner consumer
    # beside a real persisted candidate row; it does not attest source currentness.
    candidate_rows = build_capability_discovery_snapshot(loaded)
    verified_ref = "legal:verified-sibling:employee-count"
    verified_truth = LegalNormOwnerTruth(
        legal_norm_ref=verified_ref,
        normative_fact_ref="lex:fact:verified-sibling",
        source_document_ref="lex:document:verified-sibling",
        provision_citation="Art. 1",
        grounding_status="grounded",
        hallucination_status="verified_clear",
        jurisdiction="UA",
        effective_from=date(2026, 1, 1),
        temporal_state="effective",
        temporal_resolution_status="resolved",
        temporal_snapshot_at=datetime(2026, 8, 25, tzinfo=UTC),
        temporal_audit_ref="lex:audit:verified-sibling",
        provenance_refs=(
            "lex:fact:verified-sibling",
            "lex:audit:verified-sibling",
            "lex:reference:verified-sibling",
        ),
    )
    verified_row = CapabilityIndexDiscoveryRow(
        capability_ref=verified_ref,
        content_digest="sha256:" + "1" * 64,
        resource_kind="legal_norm",
        construct_refs=("construct:employee_count",),
        label="employee count owner row",
        description="Synthetic sibling for the verified-owner consumer seam.",
        producer_ref=loaded.release_ref,
        snapshot_ref="lex:verified-owner-fixture:snapshot",
        freshness_ref="lex:verified-owner-fixture:release",
        provenance_refs=verified_truth.provenance_refs,
        owner_truth=verified_truth,
        may_not_use_for=("publication_authority",),
        time=CapabilityTimeSemantics(
            observed_at=datetime(2026, 8, 25, tzinfo=UTC),
            valid_from=datetime(2026, 8, 25, tzinfo=UTC),
            valid_until=None,
            freshness="current",
        ),
    )
    monkeypatch.setattr(
        capability_discovery_module,
        "build_capability_discovery_snapshot",
        lambda _index: (*candidate_rows, verified_row),
    )
    verified_owner_result = LexCapabilityDiscoveryProvider(capability_index=loaded).search(request)
    assert tuple(row.capability_ref for row in verified_owner_result.rows) == (verified_ref,)
    assert type(verified_owner_result.rows[0].owner_truth) is LegalNormOwnerTruth
    assert type(verified_owner_result.owner_receipt) is LexOwnerReceipt
    assert verified_owner_result.owner_receipt.verifier_ref
    candidate_only_result = candidate_provider.search(request)
    assert tuple(row.capability_ref for row in candidate_only_result.rows) == (
        provider_result.rows[0].capability_ref,
    )
    assert type(candidate_only_result.owner_receipt) is LexCandidateOwnerReceipt
    assert not hasattr(candidate_only_result.owner_receipt, "verifier_ref")
