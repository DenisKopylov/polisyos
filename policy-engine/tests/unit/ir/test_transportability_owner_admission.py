from __future__ import annotations

import base64
import hashlib
import json

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.foundry.methods.catalog.causal.transport_check import CheckTransportability
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.transportability import (
    TransportabilityResult,
    build_selection_diagram,
    load_transportability_result,
    persist_transportability_result,
)
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    IRRepresentationKey,
    get_ir_owner_registry_snapshot,
    register_ir_representation,
    register_schema_version,
)
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation
from polisyos.ir.registry.refs import TransportabilityResultRef
from polisyos.scientist.governance.passes.transportability_required_pass import (
    TransportabilityRequiredPass,
)


class CountingFileSystemCAS(FileSystemCAS):
    """Count calls crossing the actual filesystem CAS JSON write boundary."""

    def __init__(self, root) -> None:
        super().__init__(root)
        self.json_writes = 0

    def put_json(self, *args, **kwargs):
        self.json_writes += 1
        return super().put_json(*args, **kwargs)


def test_transportability_result_defaults_to_current_payload_version() -> None:
    assert TransportabilityResult().schema_version == "2.2"

    with pytest.raises(ValidationError):
        TransportabilityResult(schema_version="")
    with pytest.raises(ValidationError):
        TransportabilityResult(schema_version=None)


def test_current_owned_write_roundtrips_through_reopened_filesystem_cas(tmp_path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    context = ContextProfile(context_id="source", income_level=IncomeLevel.HIGH)
    diagram = build_selection_diagram(context, context.model_copy(deep=True), graph)
    producer_output = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {},
    )
    result = TransportabilityResult.model_validate(producer_output["transport_result"])

    ref = persist_transportability_result(store, result)

    assert ref.manifest_profile_sha256 is not None
    fresh_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    assert get_json_artifact(fresh_store, ref)["schema_version"] == "2.2"
    assert load_transportability_result(fresh_store, ref) == result
    issues = TransportabilityRequiredPass().validate(
        PassContext(
            ir=None,
            state={
                "params": {"transport_required": True},
                "artifacts_index": {"transportability_result_ref": ref},
                "_store": fresh_store,
            },
            registry_bundle=None,
            profile=ValidationProfile.strict(),
            run_id="transportability-owner-roundtrip",
        )
    )
    assert not any(
        issue.code in {"TRANSPORT_RESULT_INPUT_INVALID", "TRANSPORT_REQUIRED_MISSING"}
        for issue in issues
    )


def test_explicit_legacy_2_0_is_exactly_selected_and_omits_2_2_only_fields(tmp_path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    legacy = TransportabilityResult(schema_version="2.0")

    ref = persist_transportability_result(
        store,
        legacy,
        schema_version="2.0",
        return_selected_profile=True,
    )

    assert ref.manifest_profile_sha256 is not None
    fresh_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    payload = get_json_artifact(fresh_store, ref)
    assert payload["schema_version"] == "2.0"
    assert "candidate_diagnostics" not in payload
    assert load_transportability_result(fresh_store, ref) == legacy


@pytest.mark.parametrize(
    ("result", "schema_version"),
    [
        (TransportabilityResult(schema_version="2.0"), "2.2"),
        (TransportabilityResult(schema_version="2.2"), "2.0"),
    ],
)
def test_manifest_payload_version_mismatch_is_refused_before_filesystem_cas(
    tmp_path, result, schema_version
) -> None:
    cas = CountingFileSystemCAS(tmp_path)
    store = ensure_ir_artifact_store(cas)

    with pytest.raises(CanonViolation):
        persist_transportability_result(store, result, schema_version=schema_version)

    assert cas.json_writes == 0


@pytest.mark.parametrize("flag", [None, 0, 1, "true"])
def test_invalid_selected_profile_flag_is_refused_before_filesystem_cas(tmp_path, flag) -> None:
    cas = CountingFileSystemCAS(tmp_path)
    store = ensure_ir_artifact_store(cas)

    with pytest.raises(TypeError, match="return_selected_profile must be a bool"):
        persist_transportability_result(
            store,
            TransportabilityResult(),
            return_selected_profile=flag,
        )

    assert cas.json_writes == 0


def test_explicit_false_keeps_legacy_profileless_reference_projection(tmp_path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))

    ref = persist_transportability_result(
        store,
        TransportabilityResult(),
        return_selected_profile=False,
    )

    assert ref.manifest_profile_sha256 is None
    fresh_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    assert load_transportability_result(fresh_store, ref).schema_version == "2.2"


def test_unregistered_transportability_tuple_remains_opaque(tmp_path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    ref = put_json_artifact(
        store,
        {"schema_version": "9.7", "status": "identified", "transport_mode": "direct"},
        kind="ir.transportability_result",
        schema_name="ir.transportability_result",
        schema_version="9.7",
    )

    assert get_json_artifact(store, ref)["schema_version"] == "9.7"
    with pytest.raises(CanonViolation):
        load_transportability_result(store, ref)


def test_later_registered_same_owner_representation_uses_public_route(tmp_path) -> None:
    from polisyos.ir.analytics.transportability import _TRANSPORTABILITY_RESULT_OWNER

    registry_key = _TRANSPORTABILITY_RESULT_OWNER.registry_key
    schema_name = "ir.transportability_result"
    version = "9.7"
    notes = ("Test-only exact transportability row registered after owner declaration.",)
    register_schema_version(
        registry_key,
        version,
        compatibility=CompatibilityMode.NONE,
        notes=notes,
    )
    register_ir_representation(
        registry_key=registry_key,
        owner_ref=_TRANSPORTABILITY_RESULT_OWNER.contract_id,
        dto_abi=_TRANSPORTABILITY_RESULT_OWNER.dto_fqn,
        wire_policy_ref="ir.analytics.transportability_result.wire-law",
        wire_policy_revision="1",
        schema_name=schema_name,
        schema_version=version,
        payload_version=version,
        profile_ref=None,
        readable=True,
        writable=True,
        current=False,
        default_write=False,
    )
    result = TransportabilityResult(schema_version=version)
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))

    ref = persist_transportability_result(
        store,
        result,
        schema_version=version,
        return_selected_profile=True,
    )

    assert ref.manifest_profile_sha256 is not None
    fresh_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    assert load_transportability_result(fresh_store, ref) == result


def test_legacy_1_0_normalization_remains_model_only() -> None:
    assert TransportabilityResult(schema_version="1.0").schema_version == "2.0"


_PREIMAGE_SPLIT_RESULT_BASE64 = (
    "eyJhbGdvcml0aG1fdmVyc2lvbiI6InRyc29fdjIiLCJhc3N1bWVzX3RpbWVfc3RhdGlvbmFyaXR5Ijp0cnVlLCJiYXNlX2Nv"
    "bmZpZGVuY2UiOnsiX3R5cGUiOiJmbG9hdCIsInJlcHIiOiIxIn0sImJsb2NraW5nX3Nfbm9kZXMiOltdLCJjb250ZXh0X2Rp"
    "c3RhbmNlX3BlbmFsdHkiOnsiX3R5cGUiOiJmbG9hdCIsInJlcHIiOiIwIn0sImRhdGFfYXZhaWxhYmlsaXR5X3BlbmFsdHki"
    "OnsiX3R5cGUiOiJmbG9hdCIsInJlcHIiOiIwIn0sImRhdGFfZ2FwcyI6W10sImVzdGltYW5kX2FzdCI6bnVsbCwiZXhwZXJ0"
    "X3Jldmlld19yZWFzb25zIjpbXSwiZmVhc2libGUiOnRydWUsImZpbmFsX2NvbmZpZGVuY2UiOnsiX3R5cGUiOiJmbG9hdCIs"
    "InJlcHIiOiIxIn0sImhhcmRfbGVnYWxfY29uc3RyYWludHMiOltdLCJpZF9jb25maWRlbmNlX3VuZGVyX3BhZyI6bnVsbCwi"
    "aWRlbnRpZmljYXRpb25fZW5naW5lIjoic2ltcGxpZmllZF9sZWdhY3kiLCJpZGVudGlmaWNhdGlvbl90cmFjZSI6W10sImlk"
    "ZW50aWZpZWRfcmVnaW9uIjpudWxsLCJsYWdnZWRfZWRnZV9jb3VudCI6MCwibGFnZ2VkX2VkZ2VzX2luX3F1ZXJ5IjpmYWxz"
    "ZSwibGVnYWxfc19ub2RlcyI6W10sIm1ldGFkYXRhIjp7fSwibm90ZXMiOltdLCJvdXRlcl9zZWFyY2hfYmVzdF9zY29yZSI6"
    "bnVsbCwib3V0ZXJfc2VhcmNoX2NvbmZpZ3NfZXZhbHVhdGVkIjowLCJvdXRlcl9zZWFyY2hfdHJ1bmNhdGVkIjpmYWxzZSwi"
    "cF9zdGFyX3ZhbHVlcyI6e30sInBhZ19kYWdfc2FtcGxlX3NpemUiOm51bGwsInBhZ19pZGVudGlmaWNhdGlvbl9wb2xpY3ki"
    "Om51bGwsInBhZ190cmFuc3BvcnRhYmxlX2NvdW50IjpudWxsLCJwYXJ0aWFsX2lkZW50aWZpY2F0aW9uX3Jlc3VsdCI6bnVs"
    "bCwicHJveHlfcGVuYWx0aWVzIjp7fSwicHJveHlfdmFsaWRpdHkiOnt9LCJxdWVyeSI6IiIsInJlcXVpcmVkX3RhcmdldF9k"
    "YXRhIjpbXSwicmVxdWlyZXNfZXhwZXJ0X3JldmlldyI6ZmFsc2UsInJlc29sdXRpb25fcm91bmRzIjoxLCJzY2hlbWFfdmVy"
    "c2lvbiI6IjIuMCIsInNlYXJjaF9idWRnZXRfZXhoYXVzdGVkIjpmYWxzZSwic2VhcmNoX2V2ZW50cyI6W10sInNlbGVjdGlv"
    "bl9kaWFncmFtX3JlZiI6IiIsInNvdXJjZV9jb250ZXh0X2lkIjoiIiwic291cmNlX2dyYXBoX3NoYTI1NiI6bnVsbCwic291"
    "cmNlX2dyYXBoX3R5cGUiOm51bGwsInN0YXR1cyI6ImlkZW50aWZpZWQiLCJzdXR2YV9hc3N1bWVkIjp0cnVlLCJzdXR2YV92"
    "aW9sYXRpb25fcmlzayI6bnVsbCwidGFyZ2V0X2NvbnRleHRfaWQiOiIiLCJ0ZW1wb3JhbF9kaXN0YW5jZV9wZW5hbHR5Ijp7"
    "Il90eXBlIjoiZmxvYXQiLCJyZXByIjoiMCJ9LCJ0aW1lX3N0YXRpb25hcml0eV93YXJuaW5nIjpudWxsLCJ0cmFuc3BvcnRf"
    "Zm9ybXVsYSI6bnVsbCwidHJhbnNwb3J0X21vZGUiOiJkaXJlY3QiLCJ1bnN1cHBvcnRlZF9jYXNlcyI6W10sInVuc3VwcG9y"
    "dGVkX3JlYXNvbiI6bnVsbCwid2FybmluZ3MiOltdfQ=="
)


def test_source_produced_manifest_2_2_payload_2_0_roundtrips_from_fresh_cas(tmp_path) -> None:
    raw_payload = base64.b64decode(_PREIMAGE_SPLIT_RESULT_BASE64, validate=True)
    assert hashlib.sha256(raw_payload).hexdigest() == (
        "2549be5e2ecf22d69ebaf58766d36a2cfddfb3aed346ad9562781a51a5e4f489"
    )
    payload = json.loads(raw_payload)
    assert payload["schema_version"] == "2.0"
    assert "candidate_diagnostics" not in payload

    from polisyos.ir.analytics.transportability import _TRANSPORTABILITY_RESULT_OWNER

    snapshot = get_ir_owner_registry_snapshot()
    owner_rows = tuple(
        row
        for row in snapshot.representation_records
        if row.registry_key == _TRANSPORTABILITY_RESULT_OWNER.registry_key
        and row.owner_ref == _TRANSPORTABILITY_RESULT_OWNER.contract_id
    )
    split_key = IRRepresentationKey("ir.transportability_result", "2.2", "2.0")
    legacy_key = IRRepresentationKey("ir.transportability_result", "2.0", "2.0")
    current = next(row for row in owner_rows if row.current)
    split = next(row for row in owner_rows if row.key == split_key)
    assert split.readable is True
    assert split.writable is False
    assert split.current is False
    assert split.default_write is False
    assert current.key == IRRepresentationKey("ir.transportability_result", "2.2", "2.2")
    assert set(current.readable_from) == {split_key, legacy_key}
    assert len(current.readable_from) == 2

    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    raw_ref = put_json_artifact(
        store,
        payload,
        kind="ir.transportability_result",
        schema_name="ir.transportability_result",
        schema_version="2.2",
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert raw_ref["artifact_id"] == (
        "sha256:2549be5e2ecf22d69ebaf58766d36a2cfddfb3aed346ad9562781a51a5e4f489"
    )
    assert raw_ref["manifest_profile_sha256"] == (
        "sha256:dd3e45e4f1bb7a686fffe47ca054a3df1b38f0c5d87632c4e7725ff940221b26"
    )

    ref = TransportabilityResultRef.model_validate(raw_ref)
    fresh_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    typed = load_transportability_result(fresh_store, ref)
    assert typed.schema_version == "2.0"
    assert typed.status.value == "identified"
    assert typed.transport_mode.value == "direct"
    assert typed.algorithm_version == "trso_v2"
    assert get_json_artifact(fresh_store, ref)["schema_version"] == "2.0"

    malformed = dict(payload)
    malformed["candidate_diagnostics"] = {"untrusted": True}
    malformed_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "malformed"))
    malformed_ref = put_json_artifact(
        malformed_store,
        malformed,
        kind="ir.transportability_result",
        schema_name="ir.transportability_result",
        schema_version="2.2",
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    malformed_typed_ref = TransportabilityResultRef.model_validate(malformed_ref)
    with pytest.raises(CanonViolation):
        load_transportability_result(malformed_store, malformed_typed_ref)

    null_diagnostic = dict(payload)
    null_diagnostic["candidate_diagnostics"] = None
    null_store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "null-diagnostic"))
    null_ref = put_json_artifact(
        null_store,
        null_diagnostic,
        kind="ir.transportability_result",
        schema_name="ir.transportability_result",
        schema_version="2.2",
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(CanonViolation):
        load_transportability_result(
            null_store,
            TransportabilityResultRef.model_validate(null_ref),
        )
