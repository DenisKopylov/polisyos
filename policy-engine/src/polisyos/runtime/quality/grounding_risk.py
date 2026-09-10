"""Durable CG2 admission accounting beneath the sole grounding bind owner.

The amounts here are the architect's configured admission ceilings, never
calibrated correctness claims. Candidate exploration creates no spend event.
Core CAS owns immutable bytes and Fabric owns locking and atomic cache writes;
this module supplies only the run-bound CG2 admission semantics.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts
from polisyos.fabric import atomic_write_json, file_lock
from polisyos.pdc import gy_content_hash

try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - an unsupported authority station
    _fcntl = None

RUN_PLANNING_CEILING = 0.05
RELATION_ADMISSION_ALLOWANCE = 0.04
RELATION_ADMISSION_CEILING = 0.01
CONSTRUCTION_RESERVE = 0.01
_KIND = "runtime.grounding_risk_admission"
_SCHEMA = "policyos.runtime.grounding_risk_admission.v1"


class GroundingRiskStateError(ValueError):
    """Established durable admission state cannot be reconciled."""


class GroundingRunAdmission(BaseModel):
    """A run admission or explicit continuation in the candidate band."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.runtime.grounding_run_admission.v1"] = (
        "policyos.runtime.grounding_run_admission.v1"
    )
    run_id: str | None = None
    synthetic: bool
    status: Literal["admitted", "candidate", "exhausted", "unavailable"]
    reason: str
    authority_band: Literal["authority", "candidate"] = "candidate"
    event_ref: str | None = None
    binding_key: str | None = None
    charged_this_attempt: float = Field(0.0, ge=0.0)
    admitted_spend: float | None = Field(None, ge=0.0)
    run_continues: Literal[True] = True
    custody_rule: Literal["INT-K06"] = "INT-K06"
    correctness_bound: None = None


class _AdmissionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.runtime.grounding_risk_admission.v1"] = _SCHEMA
    run_id: str
    synthetic: bool
    sequence: int = Field(ge=1)
    predecessor_ref: str | None
    binding_key: str
    cg1_content_hash: str
    reference_hash: str
    bound_atom_id: str
    calibration_anchor_hash: str
    # Fixed by the ratified policy, not supplied as an admission premise.
    configured_charge: Literal[0.01] = RELATION_ADMISSION_CEILING


class GroundingRunBudget:
    """One canonical, durable run scope for CG2 authority admissions.

    Recreating the owner never resets spend. The head is only a cache: each
    admission replays the complete dedicated CAS chain under the same lock.
    The public constructor without persistence is deliberately candidate-only.
    """

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("grounding_run_budget_is_final")

    def __init__(self, *, run_id: str) -> None:
        if not run_id.strip():
            raise ValueError("grounding_run_id_missing")
        self.run_id = run_id
        self._root: Path | None = None
        self._store: artifacts.FileSystemCAS | None = None
        self._synthetic = False

    @classmethod
    def from_repo(cls, repo_root: Path, *, run_id: str) -> GroundingRunBudget:
        """Open the canonical production run namespace in this deployment."""
        root = Path(repo_root).resolve()
        if root != Path(__file__).resolve().parents[4]:
            raise ValueError("grounding_run_deployment_mismatch")
        return cls._open(root / ".polisyos/runtime/grounding_risk", run_id=run_id, synthetic=False)

    @classmethod
    def for_contract_testing(cls, state_root: Path, *, run_id: str) -> GroundingRunBudget:
        """Open a separate, permanently synthetic mechanical test namespace."""
        return cls._open(Path(state_root) / "synthetic", run_id=run_id, synthetic=True)

    @classmethod
    def _open(cls, root: Path, *, run_id: str, synthetic: bool) -> GroundingRunBudget:
        owner = cls(run_id=run_id)
        owner._root = root.resolve() / gy_content_hash(run_id).removeprefix("sha256:")
        owner._synthetic = synthetic
        # No destruction, recovery reset, or caller-selected production root.
        try:
            owner._root.mkdir(parents=True, exist_ok=True)
            owner._store = artifacts.FileSystemCAS(owner._root / "cas")
        except (OSError, ValueError):
            # An unusable persistence boundary cannot turn into a fresh balance.
            owner._store = None
        return owner

    @property
    def synthetic(self) -> bool:
        """Return whether this is a non-authoritative mechanical simulation."""
        return self._synthetic

    def _candidate(self, *, synthetic: bool, reason: str) -> GroundingRunAdmission:
        """Observe current admitted spend without writing a candidate spend event."""
        snapshot = self.to_payload()
        return GroundingRunAdmission(
            run_id=self.run_id,
            synthetic=synthetic or self._synthetic,
            status="candidate" if snapshot["status"] == "current" else "unavailable",
            reason=reason if snapshot["status"] == "current" else str(snapshot["reason"]),
            admitted_spend=snapshot["admitted_spend"],
        )

    def _admit(
        self,
        *,
        cg1_content_hash: str,
        reference_hash: str,
        bound_atom_id: str,
        calibration_anchor_hash: str,
        synthetic: bool,
    ) -> GroundingRunAdmission:
        """Commit an already owner-verified binding, under the pre-emptive cap.

        Only GroundingBindGate calls this transition after its real reference,
        relation and calibration checks. This is bookkeeping, not a calibration
        authority constructor. Synthetic production inputs never enter it.
        """
        if synthetic and not self._synthetic:
            return self._candidate(synthetic=True, reason="synthetic_input_candidate_only")
        if self._root is None or self._store is None or _fcntl is None:
            return GroundingRunAdmission(
                run_id=self.run_id,
                synthetic=synthetic or self._synthetic,
                status="unavailable",
                reason="durable_run_budget_unavailable",
            )
        binding_key = gy_content_hash(
            {
                "run_id": self.run_id,
                "cg1_content_hash": cg1_content_hash,
                "reference_hash": reference_hash,
                "bound_atom_id": bound_atom_id,
                "calibration_anchor_hash": calibration_anchor_hash,
            }
        )
        try:
            with file_lock(self._root / "admission.lock"):
                chain = self._read_chain()
                previous = next((row for row in chain if row[1].binding_key == binding_key), None)
                if previous is not None:
                    return self._receipt(previous[0], previous[1], charge=0.0, count=len(chain))
                # Integer admission units avoid a floating-point fifth-bind escape.
                if not _budget_has_capacity(len(chain)):
                    return GroundingRunAdmission(
                        run_id=self.run_id,
                        synthetic=synthetic or self._synthetic,
                        status="exhausted",
                        reason="risk_budget_exhausted_candidate_custody",
                        binding_key=binding_key,
                        admitted_spend=RELATION_ADMISSION_ALLOWANCE,
                    )
                event = _AdmissionEvent(
                    run_id=self.run_id,
                    synthetic=self._synthetic,
                    sequence=len(chain) + 1,
                    predecessor_ref=chain[-1][0] if chain else None,
                    binding_key=binding_key,
                    cg1_content_hash=cg1_content_hash,
                    reference_hash=reference_hash,
                    bound_atom_id=bound_atom_id,
                    calibration_anchor_hash=calibration_anchor_hash,
                )
                ref = self._store.put_bytes(
                    _json_bytes(event.model_dump(mode="json")),
                    artifacts.ArtifactWriteOptions(
                        kind=_KIND,
                        media_type="application/json",
                        schema=artifacts.SchemaInfo(name=_SCHEMA, version="1.0"),
                        producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
                    ),
                )
                event_ref = str(ref.artifact_id)
                # A crash here leaves the event charged on the next complete replay.
                self._write_head(event_ref, event.sequence)
                return self._receipt(
                    event_ref, event, charge=RELATION_ADMISSION_CEILING, count=event.sequence
                )
        except (OSError, ValueError, KeyError) as exc:
            return GroundingRunAdmission(
                run_id=self.run_id,
                synthetic=synthetic or self._synthetic,
                status="unavailable",
                reason=f"grounding_run_state_unavailable:{type(exc).__name__}",
            )

    def _receipt(
        self, event_ref: str, event: _AdmissionEvent, *, charge: float, count: int
    ) -> GroundingRunAdmission:
        return GroundingRunAdmission(
            run_id=self.run_id,
            synthetic=event.synthetic,
            status="admitted",
            reason="synthetic_mechanical_admission"
            if event.synthetic
            else "owner_binding_admitted",
            authority_band="candidate" if event.synthetic else "authority",
            event_ref=event_ref,
            binding_key=event.binding_key,
            charged_this_attempt=charge,
            admitted_spend=round(count * RELATION_ADMISSION_CEILING, 12),
        )

    def _read_chain(self) -> list[tuple[str, _AdmissionEvent]]:
        if self._root is None or self._store is None:
            raise GroundingRiskStateError("grounding_run_persistence_missing")
        rows: list[tuple[str, _AdmissionEvent]] = []
        identities = self._store.iter_artifact_ids()
        expected = {
            path for artifact_id in identities for path in self._store.get_paths(artifact_id)
        }
        observed: set[Path] = set()

        def unreadable(exc: OSError) -> None:
            raise exc

        for directory, children, names in os.walk(self._store.base, onerror=unreadable):
            parent = Path(directory)
            if any((parent / name).is_symlink() for name in (*children, *names)):
                raise GroundingRiskStateError("grounding_run_cas_indirection_unresolved")
            observed.update(parent / name for name in names)
        if observed != expected:
            raise GroundingRiskStateError("grounding_run_cas_denominator_ambiguous")
        for artifact_id in identities:
            manifest = self._store.get_manifest(artifact_id)
            if manifest.kind != _KIND or manifest.artifact_schema is None:
                raise GroundingRiskStateError("grounding_run_artifact_kind_invalid")
            if manifest.artifact_schema.name != _SCHEMA:
                raise GroundingRiskStateError("grounding_run_artifact_schema_invalid")
            report = self._store.verify(artifact_id)
            if not report.ok:
                raise GroundingRiskStateError("grounding_run_artifact_integrity_invalid")
            row = _AdmissionEvent.model_validate_json(self._store.get_bytes(artifact_id))
            if row.run_id != self.run_id or row.synthetic != self._synthetic:
                raise GroundingRiskStateError("grounding_run_artifact_scope_invalid")
            if row.binding_key != gy_content_hash(
                {
                    "run_id": row.run_id,
                    "cg1_content_hash": row.cg1_content_hash,
                    "reference_hash": row.reference_hash,
                    "bound_atom_id": row.bound_atom_id,
                    "calibration_anchor_hash": row.calibration_anchor_hash,
                }
            ):
                raise GroundingRiskStateError("grounding_run_binding_key_invalid")
            rows.append((str(artifact_id), row))
        rows.sort(key=lambda item: item[1].sequence)
        seen: set[str] = set()
        for index, (_ref, row) in enumerate(rows):
            expected_predecessor = rows[index - 1][0] if index else None
            if row.sequence != index + 1 or row.predecessor_ref != expected_predecessor:
                raise GroundingRiskStateError("grounding_run_chain_invalid")
            if row.binding_key in seen:
                raise GroundingRiskStateError("grounding_run_duplicate_charge")
            seen.add(row.binding_key)
        if round(len(rows) * RELATION_ADMISSION_CEILING, 12) > RELATION_ADMISSION_ALLOWANCE:
            raise GroundingRiskStateError("grounding_run_cap_violated")
        head_path = self._root / "head.json"
        if head_path.exists():
            head = json.loads(head_path.read_text())
            expected = {"run_id", "sequence", "event_ref", "synthetic"}
            if set(head) != expected or head["run_id"] != self.run_id:
                raise GroundingRiskStateError("grounding_run_head_invalid")
            seq = head["sequence"]
            if type(seq) is not int or seq < 1 or seq > len(rows):
                raise GroundingRiskStateError("grounding_run_head_lost_event")
            if rows[seq - 1][0] != head["event_ref"] or head["synthetic"] != self._synthetic:
                raise GroundingRiskStateError("grounding_run_head_mismatch")
        return rows

    def _write_head(self, event_ref: str, sequence: int) -> None:
        if self._root is None:
            raise GroundingRiskStateError("grounding_run_persistence_missing")
        atomic_write_json(
            self._root / "head.json",
            {
                "run_id": self.run_id,
                "synthetic": self._synthetic,
                "event_ref": event_ref,
                "sequence": sequence,
            },
        )

    def to_payload(self) -> dict[str, Any]:
        """Recompute an audit snapshot; unknown state is never a zero balance."""
        base: dict[str, Any] = {
            "schema_version": "policyos.runtime.grounding_run_budget.v1",
            "run_id": self.run_id,
            "synthetic": self._synthetic,
            "correctness_bound": None,
            "run_continues": True,
            "custody_rule": "INT-K06",
        }
        if self._root is None or self._store is None or _fcntl is None:
            return {
                **base,
                "status": "unavailable",
                "reason": "durable_run_budget_unavailable",
                "admitted_spend": None,
                "admission_count": None,
            }
        try:
            with file_lock(self._root / "admission.lock"):
                rows = self._read_chain()
            return {
                **base,
                "status": "current",
                "reason": "complete_admission_chain_recomputed",
                "admitted_spend": round(len(rows) * RELATION_ADMISSION_CEILING, 12),
                "admission_count": len(rows),
            }
        except (OSError, ValueError, KeyError) as exc:
            return {
                **base,
                "status": "unavailable",
                "reason": type(exc).__name__,
                "admitted_spend": None,
                "admission_count": None,
            }

    def contains(
        self,
        receipt: GroundingRunAdmission,
        *,
        cg1_content_hash: str,
        reference_hash: str,
        bound_atom_id: str,
        calibration_anchor_hash: str,
    ) -> bool:
        """Resolve a production receipt against the complete canonical event chain."""
        if receipt.synthetic or self._synthetic or receipt.run_id != self.run_id:
            return False
        return self.binding_evidence_matches(
            receipt,
            cg1_content_hash=cg1_content_hash,
            reference_hash=reference_hash,
            bound_atom_id=bound_atom_id,
            calibration_anchor_hash=calibration_anchor_hash,
        )

    def binding_evidence_matches(
        self,
        receipt: GroundingRunAdmission,
        *,
        cg1_content_hash: str,
        reference_hash: str,
        bound_atom_id: str,
        calibration_anchor_hash: str,
    ) -> bool:
        """Reconcile bookkeeping evidence; a match alone grants no authority."""
        if receipt.run_id != self.run_id or receipt.synthetic != self._synthetic:
            return False
        if self._root is None or self._store is None or _fcntl is None:
            return False
        try:
            with file_lock(self._root / "admission.lock"):
                return any(
                    ref == receipt.event_ref
                    and row.binding_key == receipt.binding_key
                    and row.cg1_content_hash == cg1_content_hash
                    and row.reference_hash == reference_hash
                    and row.bound_atom_id == bound_atom_id
                    and row.calibration_anchor_hash == calibration_anchor_hash
                    for ref, row in self._read_chain()
                )
        except (OSError, ValueError, KeyError):
            return False


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _budget_has_capacity(admission_count: int) -> bool:
    return round((admission_count + 1) * RELATION_ADMISSION_CEILING, 12) <= (
        RELATION_ADMISSION_ALLOWANCE
    )


__all__ = ["GroundingRiskStateError", "GroundingRunAdmission", "GroundingRunBudget"]
