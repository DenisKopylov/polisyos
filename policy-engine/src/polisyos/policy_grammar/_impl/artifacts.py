"""CAS persistence helpers for W6.A universal policy grammar artifacts."""

from __future__ import annotations

import json

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
                version=UNIVERSAL_POLICY_DESIGN_CASE_SCHEMA_VERSION,
            ),
            producer=ProducerInfo(component=_PRODUCER_COMPONENT, version=_PRODUCER_VERSION),
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
    payload = json.loads(store.get_bytes(artifact_ref.artifact_id))
    case = UniversalPolicyDesignCase.model_validate(payload)
    return case.model_copy(update={"persisted_artifact_ref": artifact_ref})


__all__ = [
    "UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND",
    "UNIVERSAL_POLICY_DESIGN_CASE_SCHEMA_VERSION",
    "load_universal_policy_design_case",
    "persist_universal_policy_design_case",
]
