"""Contracts for the builtin decision-packet node."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CLAIM_LEDGER_V2_REF,
    ARTIFACT_CLAIMS_REF,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import ArtifactRef
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
    claims_ref: ArtifactRef | None = None
    claim_ledger_v2_ref: ArtifactRef | None = None

    @property
    def artifacts(self) -> list[ArtifactRef]:
        return [
            artifact
            for artifact in (self.claims_ref, self.claim_ledger_v2_ref)
            if artifact is not None
        ]

    @property
    def write_paths(self) -> tuple[str, ...]:
        paths: list[str] = []
        if self.claims_ref is not None:
            paths.append(f"artifacts_index.{ARTIFACT_CLAIMS_REF}")
        if self.claim_ledger_v2_ref is not None:
            paths.append(f"artifacts_index.{ARTIFACT_CLAIM_LEDGER_V2_REF}")
        return tuple(paths)

    def apply_to_state(self, state: ExperimentState) -> None:
        if self.claims_ref is not None:
            state.artifacts_index[ARTIFACT_CLAIMS_REF] = self.claims_ref
        if self.claim_ledger_v2_ref is not None:
            state.artifacts_index[ARTIFACT_CLAIM_LEDGER_V2_REF] = self.claim_ledger_v2_ref


_DecisionPacketBuildRequest = DecisionPacketBuildRequest
_ClaimLedgerAttachment = ClaimLedgerAttachment

__all__ = [
    "ClaimLedgerAttachment",
    "DecisionPacketBuildRequest",
    "_ClaimLedgerAttachment",
    "_DecisionPacketBuildRequest",
]
