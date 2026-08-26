"""Contracts for the builtin decision-packet node."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CLAIM_LEDGER_V2_REF,
    ARTIFACT_CLAIMS_REF,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.scientist.evidence.claims.head_index import (
        PreparedClaimLedgerInitialization,
    )
    from polisyos.scientist.nodes.builtins.decide.decision_packet_support import ReplayReadiness
    from polisyos.scientist.orchestration.engine.state import ExperimentState


@dataclass(frozen=True)
class DecisionPacketBuildRequest:
    seed: int
    inputs_section: dict[str, object]
    artifacts_section: dict[str, object]
    readiness: ReplayReadiness
    strategy_hint: str
    policy_summary: dict[str, object]
    intervention_count: int


@dataclass(frozen=True)
class ClaimLedgerAttachment:
    """Candidate Claim bytes plus a separately promoted currentness state."""

    claims_ref: ArtifactRef | None = None
    claim_ledger_v2_ref: ArtifactRef | None = None
    preparation: PreparedClaimLedgerInitialization | None = None
    authority_status: Literal["disabled", "not_established", "prepared", "current"] = "disabled"
    limitation_code: str | None = None

    @property
    def artifacts(self) -> list[ArtifactRef]:
        return [
            artifact
            for artifact in (self.claims_ref, self.claim_ledger_v2_ref)
            if artifact is not None
        ]

    @property
    def write_paths(self) -> tuple[str, ...]:
        if self.authority_status != "current":
            return ()
        paths: list[str] = []
        if self.claims_ref is not None:
            paths.append(f"artifacts_index.{ARTIFACT_CLAIMS_REF}")
        if self.claim_ledger_v2_ref is not None:
            paths.append(f"artifacts_index.{ARTIFACT_CLAIM_LEDGER_V2_REF}")
        return tuple(paths)

    def apply_to_state(self, state: ExperimentState) -> None:
        if self.authority_status != "current":
            return
        if self.claims_ref is not None:
            state.artifacts_index[ARTIFACT_CLAIMS_REF] = self.claims_ref
        if self.claim_ledger_v2_ref is not None:
            state.artifacts_index[ARTIFACT_CLAIM_LEDGER_V2_REF] = self.claim_ledger_v2_ref

    def mark_current(self) -> ClaimLedgerAttachment:
        """Return the same sealed refs after a verified generation-zero head."""

        if self.preparation is None or self.claim_ledger_v2_ref is None:
            raise ValueError("claim_root_preparation_missing")
        return replace(
            self,
            authority_status="current",
            limitation_code=None,
        )


_DecisionPacketBuildRequest = DecisionPacketBuildRequest
_ClaimLedgerAttachment = ClaimLedgerAttachment

__all__ = [
    "ClaimLedgerAttachment",
    "DecisionPacketBuildRequest",
    "_ClaimLedgerAttachment",
    "_DecisionPacketBuildRequest",
]
