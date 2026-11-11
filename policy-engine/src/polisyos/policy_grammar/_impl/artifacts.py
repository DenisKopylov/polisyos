"""CAS persistence helpers for W6.A universal policy grammar artifacts."""

from __future__ import annotations

from polisyos.core import artifacts, canon, contracts

from .schema import CompiledUniversalPolicyDesignCaseArtifact

ArtifactRef = artifacts.ArtifactRef
CanonSpec = canon.CanonSpec
FileSystemCAS = artifacts.FileSystemCAS
ProducerInfo = artifacts.ProducerInfo
PutOptions = artifacts.PutOptions
SchemaInfo = artifacts.SchemaInfo
UniversalPolicyDesignCase = contracts.UniversalPolicyDesignCase

UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND = "policyos.universal_policy_design_case"
UNIVERSAL_POLICY_DESIGN_CASE_SCHEMA_VERSION = "policyos.universal_policy_design_case.v1"
_PRODUCER_COMPONENT = "polisyos.policy_grammar.compiler"
_PRODUCER_VERSION = "w6a.v1"


def persist_universal_policy_design_case(
    *,
    store: FileSystemCAS,
    case: UniversalPolicyDesignCase,
) -> CompiledUniversalPolicyDesignCaseArtifact:
    """Persist a compiled universal policy design case as a canonical JSON artifact."""
    payload = case.model_dump(mode="json", exclude={"persisted_artifact_ref"})
    artifact_ref = store.put_json(
        payload,
        PutOptions(
            kind=UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND,
                version=case.schema_version,
            ),
            producer=ProducerInfo(
                component=_PRODUCER_COMPONENT,
                version=(
                    _PRODUCER_VERSION
                    if case.schema_version == UNIVERSAL_POLICY_DESIGN_CASE_SCHEMA_VERSION
                    else "w6a.v2"
                ),
            ),
        ),
        canon_spec=CanonSpec(),
    )
    return CompiledUniversalPolicyDesignCaseArtifact(
        case=case.model_copy(update={"persisted_artifact_ref": artifact_ref}),
        artifact_ref=artifact_ref,
    )


def load_universal_policy_design_case(
    store: FileSystemCAS,
    artifact_ref: ArtifactRef,
) -> UniversalPolicyDesignCase:
    """Load and validate a persisted universal policy design case artifact."""
    from polisyos.core.artifacts import load_core_json_artifact

    payload = load_core_json_artifact(store, artifact_ref)
    case = UniversalPolicyDesignCase.model_validate(payload)
    manifest = store.get_manifest(artifact_ref)
    extended_profile = case.schema_version == "policyos.universal_policy_design_case.v2" or (
        manifest.artifact_schema is not None
        and manifest.artifact_schema.version == "policyos.universal_policy_design_case.v2"
    )
    if extended_profile and (
        manifest.kind != UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND
        or manifest.artifact_schema.version != case.schema_version
    ):
        raise ValueError("policy_grammar_component_artifact_schema_mismatch")
    return case.model_copy(update={"persisted_artifact_ref": artifact_ref})


__all__ = [
    "UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND",
    "UNIVERSAL_POLICY_DESIGN_CASE_SCHEMA_VERSION",
    "load_universal_policy_design_case",
    "persist_universal_policy_design_case",
]
