"""Run and persist the existing epoch custody provider as a local audit CLI.

Run ``python -m polisyos.runtime.quality.epoch_custody_audit --request PATH
--cas-root PATH`` with an ``AnchorAcceptanceRequest`` JSON document. The saved
observation reports the provider's outcome; it does not admit the request's
opaque history references or appoint an independent holder.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict

from polisyos.core import artifacts, contracts, security
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.runtime.quality.chronology_custody import (
    build_production_epoch_anchor_custody_provider,
)

_Model = TypeVar("_Model", bound=BaseModel)
_MEDIA_TYPE = "application/octet-stream"


class EpochCustodyAuditReceipt(BaseModel):
    """An exact provider observation with candidate input and bounded authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.epoch-custody-audit.v1"] = (
        "polisyos.runtime.epoch-custody-audit.v1"
    )
    audit_rule_version: Literal["polisyos.runtime.epoch-custody-audit-rule.v1"] = (
        "polisyos.runtime.epoch-custody-audit-rule.v1"
    )
    provider: Literal[
        "polisyos.runtime.quality.chronology_custody.build_production_epoch_anchor_custody_provider"
    ] = (
        "polisyos.runtime.quality.chronology_custody.build_production_epoch_anchor_custody_provider"
    )
    authority_scope: Literal["custody_provider_invocation_only"] = (
        "custody_provider_invocation_only"
    )
    request_reference_verification: Literal["not_established"] = "not_established"
    observed_at: AwareDatetime
    request_ref: artifacts.ArtifactRef
    result: contracts.AnchorCustodyVerification


def _persist_exact(
    *,
    store: artifacts.ArtifactStore,
    record: _Model,
    model: type[_Model],
    kind: str,
    inputs: list[artifacts.InputRef] | None = None,
) -> tuple[artifacts.ArtifactRef, _Model]:
    payload = security.canonical_statement_bytes(record)
    ref = store.put_bytes(
        payload,
        artifacts.ArtifactWriteOptions(
            kind=kind,
            media_type=_MEDIA_TYPE,
            producer=artifacts.ProducerInfo(component="runtime.epoch_custody_audit", version="1"),
            inputs=inputs,
        ),
    )
    persisted = store.get_bytes(ref.artifact_id)
    if persisted != payload or str(ref.artifact_id) != security.raw_content_hash(payload):
        raise ValueError("epoch_custody_audit_readback_mismatch")
    return ref, security.parse_canonical_statement(persisted, model)


def audit_epoch_custody(
    *, request: contracts.AnchorAcceptanceRequest, store: artifacts.ArtifactStore
) -> tuple[artifacts.ArtifactRef, EpochCustodyAuditReceipt]:
    """Invoke the existing provider and read back its persisted audit result.

    Args:
        request: Candidate epoch request whose references remain owner-resolved.
        store: CAS receiving the exact request and resulting audit observation.

    Returns:
        The content-addressed result reference and its read-back typed receipt.

    Raises:
        ValueError: The request is misrouted or persisted bytes differ.
        TypeError: The provider did not produce a typed custody result.
    """
    request = contracts.AnchorAcceptanceRequest.model_validate(request.model_dump(mode="python"))
    if request.expected_domain.family != "epoch":
        raise ValueError("epoch_custody_audit_family_mismatch")
    if request.expected_domain.authority_purpose != request.authority_purpose:
        raise ValueError("epoch_custody_audit_purpose_mismatch")
    request_ref, persisted_request = _persist_exact(
        store=store,
        record=request,
        model=contracts.AnchorAcceptanceRequest,
        kind="chronology.custody_audit_request",
    )
    provider = build_production_epoch_anchor_custody_provider()
    result = provider.evaluate_acceptance_and_custody(request=persisted_request)
    if not isinstance(result, contracts.AnchorCustodyVerification):
        raise TypeError("custody_provider_result_missing_or_invalid")
    result = contracts.AnchorCustodyVerification.model_validate(result.model_dump(mode="python"))
    receipt = EpochCustodyAuditReceipt(
        observed_at=datetime.now(UTC),
        request_ref=request_ref,
        result=result,
    )
    return _persist_exact(
        store=store,
        record=receipt,
        model=EpochCustodyAuditReceipt,
        kind="chronology.custody_audit",
        inputs=[artifacts.InputRef(artifact_id=request_ref.artifact_id, role="audit_request")],
    )


def main(argv: list[str] | None = None) -> int:
    """Run a local custody audit and print its persisted reference and statuses.

    Args:
        argv: Explicit command arguments, or the process arguments when omitted.

    Returns:
        Zero after persistence/readback; two when no completed audit can be emitted.
        A zero exit code does not mean acceptance or custody is established.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--cas-root", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        request = contracts.AnchorAcceptanceRequest.model_validate_json(
            arguments.request.read_bytes()
        )
        ref, receipt = audit_epoch_custody(
            request=request, store=build_artifact_store(
                ArtifactStoreConfig(
                    backend="filesystem",
                    root=str(arguments.cas_root),
                ),
            )
        )
    except (OSError, TypeError, ValueError) as exc:
        sys.stderr.write(f"epoch_custody_audit_failed: {exc}\n")
        return 2
    sys.stdout.write(
        json.dumps(
            {
                "receipt_ref": ref.model_dump(mode="json"),
                "authority_scope": receipt.authority_scope,
                "status": receipt.result.status,
                "acceptance": receipt.result.acceptance.status,
                "retention": receipt.result.retention.status,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
