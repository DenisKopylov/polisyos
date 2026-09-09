"""Pre-outcome grounding frames and constructed-mismatch refusal sensitivity.

This owner composes the existing L6/WMR, CG1 and CG2 producers. A frame contains
no labels and a refusal result contains no accepted-binding correctness claim.
Reference scaffolding and mismatch derivatives are explicitly synthetic.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import artifacts
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.credal_reference import (
    CREDAL_REFERENCE_SCHEMA_VERSION,
    CredalReference,
    _iter_l6_edges,
    _iter_wmr_edges,
)
from polisyos.runtime.quality.grounding_bind import (
    GroundingBindGate,
    resolve_grounding_decision_promotability,
)
from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
from polisyos.runtime.quality.intervention_substrate import (
    InterventionSubstrateError,
    load_l6_intervention_substrate,
    resolve_intervention_lever,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.world_model_record import WorldModelRecord

REFUSAL_LIMITATION = (
    "A high refusal rate on constructed mismatches is not evidence that accepted bindings "
    "are correct."
)
PROOF_WORLD_INPUT_PATH = "architecture/policy_design_case/corr/grounding_proof_world_input.json"
PROOF_WORLD_INPUT_SCHEMA_VERSION = "policyos.runtime.grounding_proof_world_input.v1"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GroundingProofWorldInput(_StrictModel):
    """Bind a structural proof to one original WMR byte identity and source time."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal["policyos.runtime.grounding_proof_world_input.v1"] = (
        PROOF_WORLD_INPUT_SCHEMA_VERSION
    )
    synthetic: Literal[True]
    purpose: Literal["structural_grounding_proof_only"]
    source_ref: artifacts.ArtifactRef
    cas_root: str = Field(min_length=1)
    source_schema_version: str = Field(min_length=1)
    world_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    world_created_at: str
    declared_at: str
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("synthetic", mode="before")
    @classmethod
    def _synthetic_marker_is_boolean(cls, value: object) -> object:
        if value is not True:
            raise ValueError("proof_world_input_must_be_explicitly_synthetic")
        return value

    @model_validator(mode="after")
    def _verify(self) -> GroundingProofWorldInput:
        _verify_hash(self)
        _require_aware(datetime.fromisoformat(self.world_created_at))
        _require_aware(datetime.fromisoformat(self.declared_at))
        if Path(self.cas_root).is_absolute() or ".." in Path(self.cas_root).parts:
            raise ValueError("proof_world_cas_locator_must_be_repo_relative")
        return self


def _world_matches_proof_input(
    declaration: GroundingProofWorldInput,
    manifest: artifacts.ArtifactManifest,
    world: WorldModelRecord,
) -> bool:
    from polisyos.pdc import (
        WORLD_MODEL_RECORD_ARTIFACT_KIND,
        WORLD_MODEL_RECORD_SCHEMA_NAME,
        WORLD_MODEL_RECORD_SCHEMA_VERSION,
    )

    schema = manifest.artifact_schema
    return (
        str(manifest.artifact_id) == str(declaration.source_ref.artifact_id)
        and manifest.kind == declaration.source_ref.kind == WORLD_MODEL_RECORD_ARTIFACT_KIND
        and manifest.media_type == declaration.source_ref.media_type == "application/json"
        and schema is not None
        and schema.name == WORLD_MODEL_RECORD_SCHEMA_NAME
        and schema.version == declaration.source_schema_version
        == world.schema_version == WORLD_MODEL_RECORD_SCHEMA_VERSION
        and world.content_hash == declaration.world_content_hash
        and world.created_at == declaration.world_created_at
    )


def resolve_grounding_proof_world_input(
    repo_root: Path, declaration: GroundingProofWorldInput,
) -> WorldModelRecord:
    """Resolve complete declared source bytes and reject metadata substitutions."""
    from polisyos.runtime.quality.world_model_record import load_world_model_record

    declaration = GroundingProofWorldInput.model_validate_json(declaration.model_dump_json())
    root = repo_root.resolve()
    location = (root / declaration.cas_root).resolve()
    if not location.is_relative_to(root):
        raise ValueError("proof_world_cas_locator_escapes_repo")
    if not location.is_dir():
        raise FileNotFoundError(f"grounding_proof_world_source_unavailable:{location}")
    store = artifacts.FileSystemCAS(location)
    # Core verifies the entire original blob/manifest identity. No fresh builder
    # can substitute an equal logical hash with a different genuine creation time.
    manifest = store.get_manifest(declaration.source_ref.artifact_id)
    world = load_world_model_record(store, declaration.source_ref)
    if not _world_matches_proof_input(declaration, manifest, world):
        raise ValueError("grounding_proof_world_binding_mismatch")
    return world


def produce_grounding_proof_world_input(
    repo_root: Path, *, world_cas: Path, world_ref: str,
) -> GroundingProofWorldInput:
    """Emit a synthetic proof-input declaration from an existing verified source."""
    from polisyos.runtime.quality.world_model_record import load_world_model_record

    root = repo_root.resolve()
    location = world_cas.resolve()
    if not location.is_dir():
        raise FileNotFoundError(f"grounding_proof_world_source_unavailable:{location}")
    store = artifacts.FileSystemCAS(location)
    manifest = store.get_manifest(world_ref)
    world = load_world_model_record(store, world_ref)
    schema = manifest.artifact_schema
    if schema is None:
        raise ValueError("grounding_proof_world_schema_missing")
    payload = {
        "schema_version": PROOF_WORLD_INPUT_SCHEMA_VERSION,
        "synthetic": True,
        "purpose": "structural_grounding_proof_only",
        "source_ref": {
            "artifact_id": str(manifest.artifact_id),
            "kind": manifest.kind, "media_type": manifest.media_type,
        },
        "cas_root": location.relative_to(root).as_posix(),
        "source_schema_version": schema.version,
        "world_content_hash": world.content_hash,
        "world_created_at": world.created_at,
        "declared_at": datetime.now(UTC).isoformat(),
    }
    declaration = GroundingProofWorldInput.model_validate(
        {**payload, "content_hash": gy_content_hash(payload)}
    )
    resolve_grounding_proof_world_input(root, declaration)
    return declaration


def load_grounding_proof_world_input(
    repo_root: Path, *, binding_path: Path | None = None,
) -> tuple[GroundingProofWorldInput, WorldModelRecord]:
    """Read the sole proof-source declaration and resolve its original WMR."""
    path = binding_path or repo_root / PROOF_WORLD_INPUT_PATH
    declaration = GroundingProofWorldInput.model_validate_json(path.read_bytes())
    return declaration, resolve_grounding_proof_world_input(repo_root, declaration)


def grounding_proof_world_input_evidence(
    repo_root: Path,
) -> tuple[dict[str, Any], WorldModelRecord]:
    """Recompute exact-input replay and the decisive source-matching transition."""
    from datetime import timedelta
    from unittest.mock import patch

    declaration, world = load_grounding_proof_world_input(repo_root)
    repeated = resolve_grounding_proof_world_input(repo_root, declaration)
    changed = declaration.model_dump(mode="json")
    changed["world_created_at"] = (
        datetime.fromisoformat(world.created_at) + timedelta(microseconds=1)
    ).isoformat()
    changed.pop("content_hash")
    invalid = GroundingProofWorldInput.model_validate(
        {**changed, "content_hash": gy_content_hash(changed)}
    )
    refused = False
    try:
        resolve_grounding_proof_world_input(repo_root, invalid)
    except ValueError as exc:
        if str(exc) != "grounding_proof_world_binding_mismatch":
            raise
        refused = True
    with patch(f"{__name__}._world_matches_proof_input", lambda *_args: True):
        removed = resolve_grounding_proof_world_input(repo_root, invalid)
    replay_equal = world.model_dump(mode="json") == repeated.model_dump(mode="json")
    removal_accepts_mismatch = removed.created_at != invalid.world_created_at
    packet = {
        "schema_version": PROOF_WORLD_INPUT_SCHEMA_VERSION,
        "packet_type": "StrangleReceipt",
        "owner": "polisyos.runtime.quality.grounding_calibration",
        "replaced_path": "fresh_composed_WMR_for_each_structural_proof",
        "default_path": "declared_exact_WMR_bytes_schema_logical_hash_and_creation_time",
        "predicate_provenance": "recomputed",
        "binding_ref": f"repo:{PROOF_WORLD_INPUT_PATH}",
        "binding_content_hash": declaration.content_hash,
        "source_artifact_id": str(declaration.source_ref.artifact_id),
        "repeat_source_bytes_and_time_equal": replay_equal,
        "rehashed_wrong_source_time_refused": refused,
        "matching_predicate_removal_accepts_wrong_time": removal_accepts_mismatch,
        "default_flipped": replay_equal and refused and removal_accepts_mismatch,
    }
    evidence = {
        "binding_ref": f"repo:{PROOF_WORLD_INPUT_PATH}",
        "binding_content_hash": declaration.content_hash,
        "synthetic": declaration.synthetic, "purpose": declaration.purpose,
        "source_ref": declaration.source_ref.model_dump(mode="json"),
        "source_schema_version": declaration.source_schema_version,
        "world_content_hash": world.content_hash, "world_created_at": world.created_at,
        "strangle_receipt": {**packet, "content_hash": gy_content_hash(packet)},
    }
    return evidence, world


def grounding_proof_world_input_evidence_issues(evidence: Mapping[str, Any]) -> list[str]:
    """Validate an emitted source-transition packet; live owners produce its facts."""
    receipt = evidence.get("strangle_receipt")
    if not isinstance(receipt, dict):
        return ["grounding_proof_world_input_strangle_missing"]
    body = {key: value for key, value in receipt.items() if key != "content_hash"}
    if (
        receipt.get("content_hash") != gy_content_hash(body)
        or receipt.get("schema_version") != PROOF_WORLD_INPUT_SCHEMA_VERSION
        or receipt.get("binding_content_hash") != evidence.get("binding_content_hash")
        or receipt.get("binding_ref") != evidence.get("binding_ref")
        or receipt.get("source_artifact_id")
        != dict(evidence.get("source_ref") or {}).get("artifact_id")
        or evidence.get("synthetic") is not True
        or evidence.get("purpose") != "structural_grounding_proof_only"
        or receipt.get("default_flipped") is not True
        or not all(
            receipt.get(field) is True for field in (
                "repeat_source_bytes_and_time_equal",
                "rehashed_wrong_source_time_refused",
                "matching_predicate_removal_accepts_wrong_time",
            )
        )
    ):
        return ["grounding_proof_world_input_strangle_invalid"]
    return []


class CalibrationFrameInput(_StrictModel):
    """One label-free input, including unresolved input cases in the denominator."""

    input_id: str
    synthetic: bool
    operator_family: str | None
    target_type: str | None
    domain: str
    signature: dict[str, Any]
    source_units: tuple[str, ...]
    ambiguity: str | None = None


class GroundingEpochScope(_StrictModel):
    """Candidate-generation churn stales certificates, not calibration strata."""

    proposer_model: str
    prompt_version: str
    atom_birth_cohort: str
    reference_epoch: str


class CalibrationFrame(_StrictModel):
    """Dated full input denominator and input-only pre-declared campaign scope."""

    schema_version: Literal["policyos.runtime.grounding_calibration_frame.v1"] = (
        "policyos.runtime.grounding_calibration_frame.v1"
    )
    synthetic: bool
    declared_at: datetime
    input_source_refs: dict[str, str]
    inputs: tuple[CalibrationFrameInput, ...]
    selected_stratum: tuple[str, str, str, str]
    epoch_scope: GroundingEpochScope
    source_cluster_unit: Literal["connected_component_of_shared_support_source_refs"] = (
        "connected_component_of_shared_support_source_refs"
    )
    sampling_rule: Literal["at_most_one_observation_per_source_cluster"] = (
        "at_most_one_observation_per_source_cluster"
    )
    label_status: Literal["not_collected"] = "not_collected"
    correctness_bound: None = None
    content_hash: str

    @model_validator(mode="after")
    def _verify(self) -> CalibrationFrame:
        _verify_hash(self)
        _require_aware(self.declared_at)
        identities = [row.input_id for row in self.inputs]
        if len(set(identities)) != len(identities):
            raise ValueError("calibration_frame_duplicate_identity")
        if self.synthetic != any(row.synthetic for row in self.inputs):
            raise ValueError("calibration_frame_synthetic_provenance_mismatch")
        return self


class AdversarialMismatch(_StrictModel):
    """One construction guaranteed to disagree with a definite source sign."""

    case_id: str
    synthetic: Literal[True] = True
    atom_id: str
    source_input_hash: str
    transform: Literal["opposite_sign"] = "opposite_sign"
    original_sign: Literal["increase", "decrease"]
    mismatched_sign: Literal["increase", "decrease"]


class DeclaredRefusalSuite(_StrictModel):
    """Immutable, pre-execution complete constructed-mismatch denominator."""

    schema_version: Literal["policyos.runtime.grounding_refusal_suite.v1"] = (
        "policyos.runtime.grounding_refusal_suite.v1"
    )
    synthetic: Literal[True] = True
    declared_at: datetime
    frame_hash: str
    reference_scaffold_hash: str
    original_input_source_refs: dict[str, str]
    mismatches: tuple[AdversarialMismatch, ...]
    ambiguous_inputs: tuple[str, ...]
    limitation: str = REFUSAL_LIMITATION
    content_hash: str

    @model_validator(mode="after")
    def _verify(self) -> DeclaredRefusalSuite:
        _verify_hash(self)
        _require_aware(self.declared_at)
        if self.limitation != REFUSAL_LIMITATION:
            raise ValueError("refusal_sensitivity_limitation_missing")
        if len({row.case_id for row in self.mismatches}) != len(self.mismatches):
            raise ValueError("refusal_suite_duplicate_identity")
        if any(row.original_sign == row.mismatched_sign for row in self.mismatches):
            raise ValueError("refusal_suite_not_a_constructed_mismatch")
        return self


def difficulty_tier(value: CalibrationFrameInput) -> str:
    """Derive difficulty solely from input target arity and modal structure.

    Neither the binding result nor any calibration label is accepted by this
    function. `admissibility` and other computed outcome fields are ignored.
    """
    targets = value.signature.get("X_do")
    modalities = value.signature.get("modal_claims")
    if not isinstance(targets, (list, tuple)) or not targets:
        return "ambiguous"
    if len(targets) > 1:
        return "compound_target"
    if isinstance(modalities, Mapping) and len(modalities) > 1:
        return "cross_modal"
    return "atomic"


def source_clusters(inputs: Sequence[CalibrationFrameInput]) -> tuple[tuple[str, ...], ...]:
    """Collapse the complete input set by transitive shared support sources."""
    if len({row.input_id for row in inputs}) != len(inputs):
        raise ValueError("calibration_frame_duplicate_identity")
    if any(not row.source_units for row in inputs):
        raise ValueError("calibration_source_independence_not_established")
    pending = {row.input_id: set(row.source_units) for row in inputs}
    clusters: list[tuple[str, ...]] = []
    while pending:
        first = min(pending)
        sources = pending.pop(first)
        members = {first}
        changed = True
        while changed:
            neighbours = {key for key, refs in pending.items() if sources.intersection(refs)}
            changed = bool(neighbours)
            for key in neighbours:
                sources.update(pending.pop(key))
                members.add(key)
        clusters.append(tuple(sorted(members)))
    return tuple(sorted(clusters))


def _validated_frame(frame: CalibrationFrame) -> CalibrationFrame:
    """Recompute full content and detach mutable nested inputs at the common intake."""
    return CalibrationFrame.model_validate_json(frame.model_dump_json())


def calibration_frame_scope(
    frame: CalibrationFrame,
    *,
    epoch_scope: GroundingEpochScope,
    stratum: tuple[str, str, str, str],
) -> dict[str, Any]:
    """Consume the frozen frame without mistaking unlabeled inputs for calibration."""
    frame = _validated_frame(frame)
    reason = "calibration_labels_not_collected"
    if frame.epoch_scope != epoch_scope:
        reason = "certificate_epoch_scope_stale"
    elif stratum != frame.selected_stratum:
        reason = "stratum_outside_predeclared_campaign"
    elif frame.synthetic:
        reason = "synthetic_frame_cannot_grant_authority"
    return {
        "synthetic": frame.synthetic,
        "authority_band": "candidate",
        "correctness_bound": None,
        "reason": reason,
        "frame_hash": frame.content_hash,
    }


def declare_calibration_frame(
    inputs: Sequence[CalibrationFrameInput],
    *,
    source_refs: Mapping[str, str],
    epoch_scope: GroundingEpochScope,
    selected_stratum: tuple[str, str, str, str],
    declared_at: datetime | None = None,
) -> CalibrationFrame:
    """Freeze all supplied owner inputs before any binding outcome is produced."""
    payload = {
        "schema_version": "policyos.runtime.grounding_calibration_frame.v1",
        "synthetic": any(row.synthetic for row in inputs),
        "declared_at": (declared_at or datetime.now(UTC)).isoformat().replace("+00:00", "Z"),
        "input_source_refs": dict(source_refs),
        "inputs": [
            row.model_dump(mode="json") for row in sorted(inputs, key=lambda row: row.input_id)
        ],
        "selected_stratum": list(selected_stratum),
        "epoch_scope": epoch_scope.model_dump(mode="json"),
        "source_cluster_unit": "connected_component_of_shared_support_source_refs",
        "sampling_rule": "at_most_one_observation_per_source_cluster",
        "label_status": "not_collected",
        "correctness_bound": None,
    }
    return CalibrationFrame.model_validate({**payload, "content_hash": gy_content_hash(payload)})


def build_owner_frame_inputs(
    repo_root: Path,
    world: WorldModelRecord,
    *,
    domain: str,
) -> tuple[tuple[CalibrationFrameInput, ...], dict[str, str]]:
    """Enumerate every real L6 operator through the existing lever/WMR resolver."""
    bundle = load_l6_intervention_substrate(repo_root)
    sources = {
        **{
            key: f"{bundle.source_refs[key]}@{value}"
            for key, value in bundle.source_content_hashes.items()
        },
        "world_model_record": f"{world.world_model_record_id}@{world.content_hash}",
    }
    rows: list[CalibrationFrameInput] = []
    for operator, raw in sorted(bundle.knob_dictionary.items()):
        ambiguity = None
        signature: dict[str, Any] = {}
        target_type = None
        try:
            if not isinstance(raw, Mapping) or "default" not in raw:
                raise ValueError("input_parameter_value_not_established")
            resolved = resolve_intervention_lever(
                bundle,
                operator_kind=operator,
                parameter_value=raw["default"],
                world_model_record=world,
            )
            signature = {
                "X_do": list(resolved.target_world_slots),
                "params": resolved.domain.model_dump(mode="json"),
                "modal_claims": {
                    "L6": {"operator": operator},
                    "WMR": {"targets": list(resolved.target_world_slots)},
                },
            }
            target_type = resolved.domain.value_type
        except (ValueError, InterventionSubstrateError) as exc:
            ambiguity = str(exc)
        rows.append(
            CalibrationFrameInput(
                input_id=operator,
                synthetic=False,
                operator_family=operator,
                target_type=target_type,
                domain=domain,
                signature=signature,
                source_units=(
                    sources["intervention_knob_dictionary"],
                    sources["world_model_record"],
                ),
                ambiguity=ambiguity,
            )
        )
    # Independent input identity enumeration from the actual original JSON owner source.
    import json

    path = repo_root / bundle.source_refs["intervention_knob_dictionary"].removeprefix("repo:")
    pairs = json.loads(path.read_bytes(), object_pairs_hook=lambda pairs: pairs)
    original_ids = {key for key, _value in pairs}
    if original_ids != {row.input_id for row in rows} or len(pairs) != len(rows):
        raise ValueError("calibration_frame_owner_denominator_mismatch")
    return tuple(rows), sources


def build_refusal_reference_scaffold(repo_root: Path, world: WorldModelRecord) -> CredalReference:
    """Lift actual L6/WMR inputs into a marked structural-only test reference.

    L2/L3 and legal correspondence are deliberately outside this scaffold's
    claim. It cannot grant governed authority. Existing owners derive all edges.
    """
    edges = [
        edge
        for edge in _iter_l6_edges(repo_root, world_model_record=world)
        if edge.modality in {"L6_KNOB_OPERATOR", "L6_KNOB_WORLD_SLOT"}
    ]
    edges.extend(_iter_wmr_edges(world))
    marked = tuple(
        replace(
            edge,
            provenance={
                **edge.provenance,
                "synthetic": True,
                "purpose": "constructed_mismatch_refusal_scaffold_not_calibration",
            },
        ).with_content_hash()
        for edge in edges
    )
    payload = {
        "synthetic": True,
        "as_of": world.created_at,
        "edges": [edge.to_payload() for edge in sorted(marked, key=lambda edge: edge.key)],
    }
    digest = gy_content_hash(payload)
    return CredalReference(
        schema_version=CREDAL_REFERENCE_SCHEMA_VERSION,
        reference_epoch=f"synthetic-refusal:{digest.removeprefix('sha256:')[:16]}",
        reference_hash=digest,
        as_of=str(world.created_at),
        component_versions={
            "L6": digest,
            "WMR": world.content_hash,
            "L2": "out_of_scope",
            "L3": "out_of_scope",
        },
        essential_edges={edge.key: edge for edge in marked},
    )


def declare_refusal_suite(
    frame: CalibrationFrame,
    reference: CredalReference,
    *,
    declared_at: datetime | None = None,
) -> DeclaredRefusalSuite:
    """Declare every definite-sign mismatch before running CG1 or CG2 decisions."""
    frame = _validated_frame(frame)
    atoms = GroundingRelationEngine(reference).reference_atoms
    cases: list[AdversarialMismatch] = []
    ambiguous: list[str] = []
    # The source denominator is the complete actual L6 assignment frame. CG1's
    # wider Cartesian candidate universe is not a declaration of interventions.
    for row in frame.inputs:
        targets = set(row.signature.get("X_do", ()))
        matched = [
            atom
            for atom in atoms
            if atom.signature.op == row.operator_family and set(atom.signature.X_do) == targets
        ]
        if row.ambiguity or not targets or len(matched) != 1:
            ambiguous.append(row.input_id)
            continue
        atom = matched[0]
        sign = atom.signature.sign
        if sign not in {"increase", "decrease"}:
            ambiguous.append(row.input_id)
            continue
        cases.append(
            AdversarialMismatch(
                case_id=f"{row.input_id}:{atom.atom_id}:opposite_sign",
                atom_id=atom.atom_id,
                source_input_hash=gy_content_hash(atom.signature.model_dump(mode="json")),
                original_sign=sign,
                mismatched_sign="increase" if sign == "decrease" else "decrease",
            )
        )
    if len(cases) + len(ambiguous) != len(frame.inputs):
        raise ValueError("refusal_suite_owner_input_partition_incomplete")
    payload = {
        "schema_version": "policyos.runtime.grounding_refusal_suite.v1",
        "synthetic": True,
        "declared_at": (declared_at or datetime.now(UTC)).isoformat().replace("+00:00", "Z"),
        "frame_hash": frame.content_hash,
        "reference_scaffold_hash": reference.reference_hash,
        "original_input_source_refs": dict(frame.input_source_refs),
        "mismatches": [
            case.model_dump(mode="json") for case in sorted(cases, key=lambda row: row.case_id)
        ],
        "ambiguous_inputs": sorted(ambiguous),
        "limitation": REFUSAL_LIMITATION,
    }
    return DeclaredRefusalSuite.model_validate(
        {**payload, "content_hash": gy_content_hash(payload)}
    )


def run_refusal_suite(
    suite: DeclaredRefusalSuite,
    frame: CalibrationFrame,
    reference: CredalReference,
    *,
    executed_at: datetime | None = None,
) -> dict[str, Any]:
    """Run the frozen full mismatch set, preserving each decisive refusal reason."""
    frame = _validated_frame(frame)
    suite = DeclaredRefusalSuite.model_validate_json(suite.model_dump_json())
    now = executed_at or datetime.now(UTC)
    _require_aware(now)
    if now <= suite.declared_at or now <= frame.declared_at:
        raise ValueError("refusal_suite_not_declared_before_execution")
    if (
        suite.frame_hash != frame.content_hash
        or suite.reference_scaffold_hash != reference.reference_hash
    ):
        raise ValueError("refusal_suite_input_binding_mismatch")
    declared = declare_refusal_suite(frame, reference, declared_at=suite.declared_at)
    if declared.content_hash != suite.content_hash:
        raise ValueError("refusal_suite_complete_denominator_drift")
    engine = GroundingRelationEngine(reference)
    gate = GroundingBindGate(reference)
    atoms = {atom.atom_id: atom for atom in engine.reference_atoms}
    outcomes: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    for case in suite.mismatches:
        atom = atoms[case.atom_id]
        signature = atom.signature.model_dump(mode="json")
        original = engine.certificate_for(
            {"signature": signature, "synthetic": True}, proposal_id=f"control:{case.case_id}"
        )
        control = gate.certificate_for(original)
        controls.append(
            {
                "case_id": case.case_id,
                "synthetic": True,
                "relation": original.selected_relation,
                "reason": control.decisive_reason,
                "production_promotable": control.production_promotable,
            }
        )
        mismatch = copy.deepcopy(signature)
        mismatch["sign"] = case.mismatched_sign
        relation = engine.certificate_for(
            {"signature": mismatch, "synthetic": True}, proposal_id=case.case_id
        )
        decision = gate.certificate_for(relation)
        resolution = resolve_grounding_decision_promotability(decision, reference)
        declared_pairs = [
            row
            for row in relation.relation_set["candidate_results"]
            if row["atom_id"] == case.atom_id
        ]
        detected = bool(declared_pairs) and all(
            any(
                w["axis"] == "sign" and w["relation"] == "contradiction"
                for w in row["axis_witnesses"]
            )
            for row in declared_pairs
        )
        outcomes.append(
            {
                "case_id": case.case_id,
                "synthetic": True,
                "refused": decision.decision != "bind",
                "mismatch_detected": detected,
                "decision_reason": decision.decisive_reason,
                "governed_authority": resolution.promotable,
                "certificate_hash": decision.content_hash,
            }
        )
    n = len(outcomes)
    refused = sum(row["refused"] for row in outcomes)
    issues = []
    if not n:
        issues.append("no_predeclared_mismatch")
    if any(
        not row["mismatch_detected"]
        or not row["refused"]
        or row["decision_reason"] != "false_analog_hard_abstain"
        for row in outcomes
    ):
        issues.append("constructed_mismatch_not_structurally_refused")
    if any(row["governed_authority"] for row in outcomes):
        issues.append("synthetic_input_reached_authority")
    if any(row["relation"] not in {"exact", "certified-specialization"} for row in controls):
        issues.append("matched_control_not_structurally_supported")
    return {
        "schema_version": "policyos.runtime.grounding_refusal_sensitivity.v1",
        "synthetic": True,
        "name": "refusal_sensitivity",
        "suite_hash": suite.content_hash,
        "executed_at": now.isoformat(),
        "predeclared_mismatches": n,
        "binder_refused": refused,
        "limitation": REFUSAL_LIMITATION,
        "statement": f"On a pre-declared adversarial suite of {n} deliberate mismatches, "
        f"the binder refused {refused}. {REFUSAL_LIMITATION}",
        "outcomes": outcomes,
        "matched_controls_outside_denominator": controls,
        "issues": issues,
        "correctness_bound": None,
    }


def _verify_hash(value: BaseModel) -> None:
    payload = value.model_dump(mode="json")
    supplied = payload.pop("content_hash")
    if gy_content_hash(payload) != supplied:
        raise ValueError("grounding_declaration_content_hash_mismatch")


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("grounding_declaration_requires_aware_time")


__all__ = [
    "PROOF_WORLD_INPUT_PATH",
    "PROOF_WORLD_INPUT_SCHEMA_VERSION",
    "CalibrationFrame",
    "CalibrationFrameInput",
    "DeclaredRefusalSuite",
    "GroundingEpochScope",
    "GroundingProofWorldInput",
    "build_owner_frame_inputs",
    "build_refusal_reference_scaffold",
    "calibration_frame_scope",
    "declare_calibration_frame",
    "declare_refusal_suite",
    "difficulty_tier",
    "grounding_proof_world_input_evidence",
    "grounding_proof_world_input_evidence_issues",
    "load_grounding_proof_world_input",
    "produce_grounding_proof_world_input",
    "resolve_grounding_proof_world_input",
    "run_refusal_suite",
    "source_clusters",
]
