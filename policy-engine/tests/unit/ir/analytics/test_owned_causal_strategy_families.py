from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

import polisyos.ir.migrations.base as ir_migrations
from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics import proximal as proximal_api
from polisyos.ir.analytics import recoverability as recoverability_api
from polisyos.ir.analytics import strategic as strategic_api
from polisyos.ir.analytics import welfare as welfare_api
from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation,
    declare_model_owner,
    owner_profile_for_spec,
)
from polisyos.ir.analytics.proximal import (
    BridgeFunctionSpec,
    IdentifiedFunctional,
    ProximalIdentificationCertificate,
    ProximalQuerySpec,
    ProxyAnnotation,
    load_proximal_identification_certificate,
    persist_proximal_identification_certificate,
)
from polisyos.ir.analytics.recoverability import (
    RecoverabilityCertificate,
    RecoverabilityCertificateStatus,
    RecoveryScope,
    load_recoverability_certificate,
)
from polisyos.ir.analytics.strategic import (
    FiniteStrategicPayoffTable,
    load_strategic_payoff_table,
)
from polisyos.ir.analytics.welfare import (
    ChannelDecompositionArtifact,
    ChannelDecompositionTargetKind,
    ChannelIdentificationStatus,
    ChannelPolicyClass,
    build_channel_decomposition_ref,
    load_channel_decomposition_artifact,
)
from polisyos.ir.artifacts import put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation
from polisyos.ir.registry.refs import ArtifactRefModel

if TYPE_CHECKING:
    from polisyos.ir.artifacts import ArtifactStore


class _CountingStore:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store
        self.manifest_reads = 0
        self.payload_reads = 0
        self.put_calls = 0

    def get_manifest_bytes(self, selector: object) -> bytes:
        self.manifest_reads += 1
        return self.store.get_manifest_bytes(selector)

    def get_manifest(self, selector: object) -> object:
        self.manifest_reads += 1
        return self.store.get_manifest(selector)

    def get_bytes(self, selector: object) -> bytes:
        self.payload_reads += 1
        return self.store.get_bytes(selector)

    def put_json(
        self,
        obj: object,
        opts: object,
        canon_spec: object = None,
        *,
        return_selected_profile: bool = False,
    ) -> object:
        self.put_calls += 1
        return self.store.put_json(
            obj,
            opts=opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )


def _store(root: Path) -> ArtifactStore:
    return ensure_ir_artifact_store(FileSystemCAS(root))


def _proximal(treatment: str = "A") -> ProximalIdentificationCertificate:
    return ProximalIdentificationCertificate(
        query=ProximalQuerySpec(treatment=(treatment,), outcome=("Y",)),
        proxies=ProxyAnnotation(treatment_inducing=("Z",), outcome_inducing=("W",)),
        bridge_functions=(
            BridgeFunctionSpec(
                name="h",
                role="outcome_bridge",
                domain=("W", treatment),
                equation_type="conditional_expectation",
                equation=f"E[Y - h(W, {treatment}) | Z, {treatment}] = 0",
            ),
        ),
        identified_functionals=(
            IdentifiedFunctional(
                target="ATE",
                expression=f"E[h(W, {treatment}) - h(W, 0)]",
                preferred=True,
            ),
        ),
    )


def _ref(char: str, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id="sha256:" + char * 64,
        kind=kind,
        media_type="application/json",
    )


def _channel() -> ChannelDecompositionArtifact:
    return ChannelDecompositionArtifact(
        target_kind=ChannelDecompositionTargetKind.NET_REVENUE,
        policy_class=ChannelPolicyClass.LOCAL_AFFINE_TAX_TRANSFER,
        basis_labels=("rate",),
        step_vector=(0.1,),
        identification_status=ChannelIdentificationStatus.BLOCKED,
        blocking_reasons=["basis_not_admitted"],
        baseline_microdata_ref=_ref("a", "ir.baseline_microdata"),
        policy_basis_ref=_ref("b", "ir.policy_basis"),
        mechanical_inputs_ref=_ref("c", "ir.mechanical_inputs"),
    )


def _payoff() -> FiniteStrategicPayoffTable:
    return FiniteStrategicPayoffTable(
        agent="mayor",
        strategic_agents=("mayor",),
        action_spaces={"mayor": ("retain",)},
        payoffs={"mayor=retain": 1.0},
    )


def _family_cases() -> list[tuple[str, object, BaseModel, object]]:
    proximal = _proximal()
    recoverability = RecoverabilityCertificate(
        target_query="P(Y|do(A))",
        mgraph_fingerprint="sha256:demo",
        status=RecoverabilityCertificateStatus.RECOVERABLE,
        recovery_scope=RecoveryScope.CAUSAL_QUERY,
    )
    strategic = _payoff()
    welfare = _channel()
    return [
        (
            "proximal",
            proximal_api._PROXIMAL_IDENTIFICATION_CERTIFICATE_OWNER,
            proximal,
            load_proximal_identification_certificate,
        ),
        (
            "recoverability",
            recoverability_api._RECOVERABILITY_CERTIFICATE_OWNER,
            recoverability,
            load_recoverability_certificate,
        ),
        (
            "strategic",
            strategic_api._STRATEGIC_OWNER_BY_MODEL[type(strategic)],
            strategic,
            load_strategic_payoff_table,
        ),
        (
            "welfare",
            welfare_api._CHANNEL_DECOMPOSITION_OWNER,
            welfare,
            load_channel_decomposition_artifact,
        ),
    ]


@pytest.mark.parametrize(
    ("family", "owner", "payload", "loader"),
    _family_cases(),
    ids=("proximal", "recoverability", "strategic", "welfare"),
)
def test_foreign_tuple_is_rejected_before_payload_fetch(
    tmp_path: Path,
    family: str,
    owner: object,
    payload: BaseModel,
    loader: object,
) -> None:
    del family
    store = _store(tmp_path / "cas")
    owner_ref = owner
    raw_ref = put_json_artifact(
        store,
        payload.model_dump(mode="json"),
        kind=owner_ref.kind,
        schema_name=f"{owner_ref.registry_key}.unregistered",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    counted = _CountingStore(store)

    with pytest.raises(CanonViolation, match="ir_owned_artifact_representation_unregistered"):
        loader(counted, ArtifactRefModel.model_validate(raw_ref))

    assert counted.manifest_reads >= 1
    assert counted.payload_reads == 0


def test_malformed_and_unknown_writer_tuples_refuse_before_cas(tmp_path: Path) -> None:
    owner = proximal_api._PROXIMAL_IDENTIFICATION_CERTIFICATE_OWNER
    counted = _CountingStore(_store(tmp_path / "cas"))

    with pytest.raises(CanonViolation, match="ir_owned_artifact_write_override_invalid"):
        persist_proximal_identification_certificate(
            counted,
            _proximal(),
            schema_name="",
            schema_version="1.0",
        )
    assert counted.put_calls == 0

    with pytest.raises(CanonViolation, match="ir_owned_artifact_write_override_unregistered"):
        persist_proximal_identification_certificate(
            counted,
            _proximal(),
            schema_name=owner.registry_key,
            schema_version="9.9",
        )
    assert counted.put_calls == 0


def test_new_resource_values_use_existing_family_grammar_without_registry_growth(
    tmp_path: Path,
) -> None:
    before = ir_migrations.get_ir_owner_registry_snapshot()
    owner = proximal_api._PROXIMAL_IDENTIFICATION_CERTIFICATE_OWNER
    for index, treatment in enumerate(("A", "new-policy-resource")):
        root = tmp_path / f"cas-{index}"
        writer = _store(root)
        candidate = _proximal(treatment)
        ref = persist_proximal_identification_certificate(writer, candidate)
        loaded = load_proximal_identification_certificate(_store(root), ref)
        assert loaded == candidate
    after = ir_migrations.get_ir_owner_registry_snapshot()

    assert after.revision == before.revision
    assert owner.registry_key == "ir.proximal_identification_certificate"


def test_registered_nondefault_tuple_rebinds_the_full_owner_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = proximal_api._PROXIMAL_IDENTIFICATION_CERTIFICATE_OWNER
    before = ir_migrations.get_ir_owner_registry_snapshot()
    matching = tuple(
        row
        for row in before.representation_records
        if row.registry_key == original.registry_key and row.owner_ref == original.contract_id
    )
    assert len(matching) == 1
    current = matching[0]
    current_rule = ir_migrations.get_schema_rule(original.registry_key, current.schema_version)
    assert current_rule is not None

    current_row = OwnedJSONRepresentation(
        schema_name=current.schema_name,
        schema_version=current.schema_version,
        payload_version=current.payload_version,
        wire_policy_ref=current.wire_policy_ref,
        wire_policy_revision=current.wire_policy_revision,
        profile_ref=current.profile_ref,
        compatibility=current_rule.mode,
        notes=current_rule.notes,
        readable=current.readable,
        writable=current.writable,
        current=current.current,
        default_write=current.default_write,
        readable_from=current.readable_from,
    )
    wire_policy_ref, wire_policy_revision = original.accepted_wire_policies[0]
    nondefault_row = OwnedJSONRepresentation(
        schema_name=original.registry_key,
        schema_version="1.2",
        payload_version="1.2",
        wire_policy_ref=wire_policy_ref,
        wire_policy_revision=wire_policy_revision,
        profile_ref=None,
        compatibility=current_rule.mode,
        notes=("Exact owner-bound analytics tuple; unknown history remains opaque.",),
        readable=True,
        writable=True,
        current=False,
        default_write=False,
        readable_from=(),
    )
    monkeypatch.setattr(
        ir_migrations,
        "_SCHEMA_REGISTRY",
        {key: dict(rows) for key, rows in ir_migrations._SCHEMA_REGISTRY.items()},
    )
    rebound = declare_model_owner(
        ProximalIdentificationCertificate,
        contract_id=original.contract_id,
        dto_fqn=original.dto_fqn,
        abi_key=original.abi_key,
        registry_key=original.registry_key,
        kind=original.kind,
        media_type=original.media_type,
        purpose=original.purpose,
        policy_revision=f"{original.policy_revision}.test-extension-1-2",
        accepted_wire_policies=original.accepted_wire_policies,
        payload_version_field="schema_version",
        validate_profile=owner_profile_for_spec(
            CanonSpec(forbid_floats=False),
            profile_ref=None,
        ),
        representations=(current_row, nondefault_row),
    )
    monkeypatch.setattr(proximal_api, "_PROXIMAL_IDENTIFICATION_CERTIFICATE_OWNER", rebound)

    rebound_snapshot = ir_migrations.get_ir_owner_registry_snapshot()
    rebound_rows = tuple(
        row
        for row in rebound_snapshot.representation_records
        if row.registry_key == rebound.registry_key and row.owner_ref == rebound.contract_id
    )
    assert {row.schema_version for row in rebound_rows} == {current.schema_version, "1.2"}

    evolved = ProximalIdentificationCertificate.model_validate(
        {**_proximal().model_dump(mode="json"), "schema_version": "1.2"}
    )
    root = tmp_path / "cas"
    ref = persist_proximal_identification_certificate(
        _store(root),
        evolved,
        schema_name=rebound.registry_key,
        schema_version="1.2",
    )
    loaded = load_proximal_identification_certificate(_store(root), ref)

    assert loaded == evolved
    assert loaded.schema_version == "1.2"


def _persist_mapping(
    store: ArtifactStore,
    payload: dict[str, object],
    *,
    kind: str,
) -> ArtifactRefModel:
    return ArtifactRefModel.model_validate(
        put_json_artifact(
            store,
            payload,
            kind=kind,
            schema_name=kind,
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
        )
    )


def test_welfare_role_consumer_produces_owned_artifact_readable_by_fresh_cas(
    tmp_path: Path,
) -> None:
    root = tmp_path / "welfare-cas"
    store = _store(root)
    baseline = _persist_mapping(
        store,
        {"overlap_ok": True, "overlap_stats": {"min_propensity": 0.11}},
        kind="ir.baseline_microdata",
    )
    policy_basis = _persist_mapping(
        store,
        {
            "basis_labels": ["rate"],
            "step_vector": [0.02],
            "policy_rank_ok": True,
        },
        kind="ir.policy_basis",
    )
    mechanical = _persist_mapping(
        store,
        {"mechanical_vector": [0.6]},
        kind="ir.mechanical_inputs",
    )
    instrument = _persist_mapping(
        store,
        {"overid_ok": True, "timing_ok": True},
        kind="ir.instrument_set",
    )

    channel_ref = build_channel_decomposition_ref(
        store,
        target_kind=ChannelDecompositionTargetKind.NET_REVENUE,
        baseline_microdata_ref=baseline,
        policy_basis_ref=policy_basis,
        mechanical_inputs_ref=mechanical,
        instrument_set_ref=instrument,
        total_vector=(0.6,),
    )
    channel = load_channel_decomposition_artifact(_store(root), channel_ref)

    assert channel.policy_basis_ref == policy_basis
    assert channel.mechanical_inputs_ref == mechanical
    assert channel.identification_status in (
        ChannelIdentificationStatus.BOUNDED,
        ChannelIdentificationStatus.BLOCKED,
    )
