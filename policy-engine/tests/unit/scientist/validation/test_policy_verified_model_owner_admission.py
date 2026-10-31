from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import BaseModel

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    ArtifactRef,
    CanonInfo,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
    resolve_manifest_by_profile,
)
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.scientist import (
    LegalCandidatePackRef,
    LegalSourcePackRef,
    PolicyOptionSetRef,
    PolicyRequestFrameRef,
    SourceVerificationReportRef,
    VerifiedPolicyReportRef,
)
from polisyos.scientist.validation.policy_verified.models import (
    LegalCandidatePack,
    LegalRetrievalStatus,
    LegalSourcePack,
    PolicyOptionSet,
    PolicyRequestFrame,
    SourceVerificationReport,
    VerifiedPolicyReport,
    load_legal_candidate_pack,
    load_legal_source_pack,
    load_policy_option_set,
    load_policy_request_frame,
    load_source_verification_report,
    load_verified_policy_body,
    load_verified_policy_report,
    persist_legal_candidate_pack,
    persist_legal_source_pack,
    persist_policy_option_set,
    persist_policy_request_frame,
    persist_source_verification_report,
    persist_verified_policy_body,
    persist_verified_policy_report,
)

_CANON_SPEC = CanonSpec(forbid_floats=False)

_CASES: list[
    tuple[
        str,
        BaseModel,
        Callable[..., BaseModel],
        Callable[..., BaseModel],
        type[BaseModel],
        str,
        str,
    ],
    ...,
] = [
    (
        "policy_request_frame",
        PolicyRequestFrame(request_id="synthetic-request", policy_question="A synthetic question?"),
        persist_policy_request_frame,
        load_policy_request_frame,
        PolicyRequestFrameRef,
        "polisyos.scientist.PolicyRequestFrame",
        "1.0",
    ),
    (
        "policy_option_set",
        PolicyOptionSet(request_id="synthetic-request"),
        persist_policy_option_set,
        load_policy_option_set,
        PolicyOptionSetRef,
        "polisyos.scientist.PolicyOptionSet",
        "1.0",
    ),
    (
        "legal_source_pack",
        LegalSourcePack(request_id="synthetic-request"),
        persist_legal_source_pack,
        load_legal_source_pack,
        LegalSourcePackRef,
        "polisyos.scientist.LegalSourcePack",
        "1.0",
    ),
    (
        "legal_candidate_pack",
        LegalCandidatePack(
            request_id="owner-admission-legal",
            legal_retrieval_status=[
                LegalRetrievalStatus(
                    query="licensing",
                    route="provisions",
                    limitation_code="issuer_currentness_not_established",
                )
            ],
        ),
        persist_legal_candidate_pack,
        load_legal_candidate_pack,
        LegalCandidatePackRef,
        "polisyos.scientist.LegalCandidatePack",
        "1.1",
    ),
    (
        "source_verification_report",
        SourceVerificationReport(
            request_id="owner-admission-source-report",
            needs_expert_review=True,
        ),
        persist_source_verification_report,
        load_source_verification_report,
        SourceVerificationReportRef,
        "polisyos.scientist.SourceVerificationReport",
        "1.0",
    ),
    (
        "verified_policy_body",
        VerifiedPolicyReport(
            request_id="synthetic-body",
            executive_summary="Synthetic candidate; source authority not established.",
            needs_expert_review=True,
        ),
        persist_verified_policy_body,
        load_verified_policy_body,
        ArtifactRef,
        "polisyos.scientist.VerifiedPolicyReport",
        "1.0",
    ),
    (
        "verified_policy_report",
        VerifiedPolicyReport(
            request_id="owner-admission-policy-report",
            executive_summary="Evidence remains limited.",
            needs_expert_review=True,
            missing_evidence=["issuer_currentness_not_established"],
        ),
        persist_verified_policy_report,
        load_verified_policy_report,
        VerifiedPolicyReportRef,
        "polisyos.scientist.VerifiedPolicyReport",
        "1.0",
    ),
]


@pytest.mark.parametrize(
    "name,payload,persist,load,ref_type,schema_name,schema_version",
    _CASES,
    ids=[case[0] for case in _CASES],
)
def test_owned_writers_return_selected_refs_and_readers_reopen_them(
    tmp_path,
    name: str,
    payload: BaseModel,
    persist: Callable[..., BaseModel],
    load: Callable[..., BaseModel],
    ref_type: type[BaseModel],
    schema_name: str,
    schema_version: str,
) -> None:
    del name
    store = FileSystemCAS(tmp_path / "cas")
    source_artifact = store.put_json(
        {"source": "owner-admission-test"},
        PutOptions(
            kind="test.owner_admission_source",
            media_type="application/json",
            schema=SchemaInfo(name="test.owner_admission.Source", version="1.0"),
        ),
        return_selected_profile=True,
    )
    input_ref = input_ref_from_artifact_ref(
        source_artifact,
        role="test.owner_admission.source",
    )

    ref = persist(store, payload, inputs=[input_ref])

    assert ref.manifest_profile_sha256 is not None
    reopened = FileSystemCAS(store.root)
    manifest = resolve_manifest_by_profile(
        reopened,
        ref.artifact_id,
        ref.manifest_profile_sha256,
    )
    assert manifest.kind == ref.kind
    assert manifest.media_type == ref.media_type == "application/json"
    assert manifest.artifact_schema == SchemaInfo(name=schema_name, version=schema_version)
    assert manifest.inputs == [input_ref]
    assert load(reopened, ref) == payload

    # Old typed references may omit the selected-profile digest. The strict owner
    # reader still resolves and checks the one stored canonical view.
    historical_ref = ref_type.model_validate(
        ref.model_copy(update={"manifest_profile_sha256": None}).model_dump()
    )
    assert load(reopened, historical_ref) == payload


@pytest.mark.parametrize(
    "name,payload,persist,load,ref_type,schema_name,schema_version",
    _CASES,
    ids=[case[0] for case in _CASES],
)
@pytest.mark.parametrize("counterfeit", ["kind", "media_type", "schema_name", "schema_version"])
def test_owner_readers_reject_same_bytes_under_counterfeit_manifest_profiles(
    tmp_path,
    name: str,
    payload: BaseModel,
    persist: Callable[..., BaseModel],
    load: Callable[..., BaseModel],
    ref_type: type[BaseModel],
    schema_name: str,
    schema_version: str,
    counterfeit: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    producer_ref = persist(store, payload)
    schema = SchemaInfo(name=schema_name, version=schema_version)
    kind = producer_ref.kind
    media_type = producer_ref.media_type
    expected_code = "canon_profile_owned_artifact_schema_mismatch"

    if counterfeit == "kind":
        kind = "scientist.counterfeit"
        expected_code = "canon_profile_owned_artifact_kind_mismatch"
    elif counterfeit == "media_type":
        media_type = "application/problem+json"
        expected_code = "canon_profile_owned_artifact_media_type_mismatch"
    elif counterfeit == "schema_name":
        schema = SchemaInfo(name="polisyos.counterfeit.Payload", version=schema_version)
    elif counterfeit == "schema_version":
        schema = SchemaInfo(
            name=schema_name,
            version="1.0" if name == "legal_candidate_pack" else "9.9",
        )
        if name == "legal_candidate_pack":
            expected_code = "canon_profile_owned_payload_schema_version_mismatch"

    options = PutOptions(
        kind=kind,
        media_type=media_type,
        schema=schema,
        canon=CanonInfo.from_spec(_CANON_SPEC),
    )
    if counterfeit == "media_type":
        selected = store.put_bytes(
            to_canonical_bytes(payload, _CANON_SPEC),
            options,
            return_selected_profile=True,
        )
    else:
        selected = store.put_json(
            payload,
            options,
            canon_spec=_CANON_SPEC,
            return_selected_profile=True,
        )
    counterfeit_ref = ref_type.model_validate(selected.model_dump())

    assert counterfeit_ref.artifact_id == producer_ref.artifact_id
    assert counterfeit_ref.manifest_profile_sha256 is not None
    assert counterfeit_ref.manifest_profile_sha256 != producer_ref.manifest_profile_sha256
    with pytest.raises(CanonicalProfileRefusalError) as refusal:
        load(store, counterfeit_ref)
    assert refusal.value.code == expected_code


def test_legal_candidate_reader_preserves_historical_profileless_v1_0_pack(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    historical = store.put_json(
        {"schema_version": "1.0", "request_id": "legacy-pack"},
        PutOptions(
            kind="scientist.legal_candidate_pack",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.LegalCandidatePack", version="1.0"),
        ),
        canon_spec=_CANON_SPEC,
        return_selected_profile=True,
    )
    historical_ref = LegalCandidatePackRef.model_validate(
        historical.model_copy(update={"manifest_profile_sha256": None}).model_dump()
    )

    loaded = load_legal_candidate_pack(FileSystemCAS(store.root), historical_ref)

    assert loaded.schema_version == "1.0"
    assert loaded.request_id == "legacy-pack"
    assert loaded.legal_retrieval_status == []
