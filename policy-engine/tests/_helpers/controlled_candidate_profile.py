"""Shared controlled candidate-scenario inputs for served N4→N5 tests.

The fixture remains candidate-only: the replay changes one integer parameter and
records its exact target/outcome path; the configured model is a declared synthetic
SCM and does not establish empirical grounding, source time, S8, or N9 authority.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.ir.artifacts import ArtifactStore
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.design_problem import (
    DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
    AuthorityProfile,
    CandidateLever,
    CandidateLeverSpace,
    DesignConstraint,
    DesignObjective,
    DesignProblem,
    DesignStakeholder,
    EvidenceAcquisitionNeeds,
    EvidenceNeed,
    JurisdictionTimeSemantics,
    NLProvenance,
    OutcomeOfInterest,
)
from polisyos.runtime.quality.generation_cycle import CandidateGroundingObservation
from polisyos.runtime.quality.intervention_atom_binding import InterventionAtomBinding
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tools.quality.validation import (
    check_layer3_gy_design_generation_contract as n4_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class ControlledCandidateGateway:
    """Small OpenAI-compatible local gateway for the real traced-client factory."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recording: dict[str, object] | None = None
        self._problem: dict[str, object] | None = None
        self._n4_cursor = 0

        class Handler(BaseHTTPRequestHandler):
            owner: ControlledCandidateGateway

            def do_GET(self) -> None:  # noqa: N802
                if self.path != "/v1/models":
                    self._send_json(404, {"error": "not_found"})
                    return
                with self.owner._lock:
                    recording = self.owner._recording
                if recording is None:
                    self._send_json(503, {"error": "fixture_not_selected"})
                    return
                with self.owner._lock:
                    self.owner._n4_cursor = 0
                self._send_json(
                    200,
                    {"data": [{"id": recording["model_id"], "object": "model"}]},
                )

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/v1/chat/completions":
                    self._send_json(404, {"error": "not_found"})
                    return
                try:
                    request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    self._send_json(400, {"error": "malformed_request"})
                    return
                if not isinstance(request, dict):
                    self._send_json(400, {"error": "malformed_request"})
                    return
                compiler_name = self._compiler_tool_name(request)
                if compiler_name is not None:
                    with self.owner._lock:
                        problem = self.owner._problem
                        self.owner._n4_cursor = 0
                    if problem is None:
                        self._send_json(503, {"error": "fixture_not_selected"})
                        return
                    completion = {
                        "id": "synthetic-design-problem-completion",
                        "object": "chat.completion",
                        "model": request.get("model"),
                        "provider": "controlled_local_gateway",
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [
                                        {
                                            "id": "synthetic-design-problem-tool-call",
                                            "type": "function",
                                            "function": {
                                                "name": compiler_name,
                                                "arguments": json.dumps(
                                                    problem,
                                                    sort_keys=True,
                                                    separators=(",", ":"),
                                                ),
                                            },
                                        }
                                    ],
                                },
                                "finish_reason": "tool_calls",
                            }
                        ],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    }
                    self._send_json(200, completion)
                    return

                with self.owner._lock:
                    recording = self.owner._recording
                    if recording is None:
                        response = None
                    else:
                        responses = recording.get("responses")
                        if not isinstance(responses, list) or self.owner._n4_cursor >= len(
                            responses
                        ):
                            response = None
                        else:
                            response = responses[self.owner._n4_cursor]
                            self.owner._n4_cursor += 1
                if not isinstance(response, dict):
                    self._send_json(502, {"error": "synthetic_response_exhausted"})
                    return
                if response.get("status") == "error":
                    error = response.get("error")
                    error_payload = error if isinstance(error, dict) else {}
                    self._send_json(
                        502,
                        {
                            "error": {
                                "type": error_payload.get("type") or "synthetic_gateway_error",
                                "code": error_payload.get("code"),
                                "message": error_payload.get("message")
                                or "controlled fixture provider error",
                            }
                        },
                    )
                    return
                content = response.get("raw_response")
                if not isinstance(content, str):
                    self._send_json(502, {"error": "synthetic_response_malformed"})
                    return
                usage = response.get("usage")
                usage_payload = usage if isinstance(usage, dict) else {}
                self._send_json(
                    200,
                    {
                        "id": "synthetic-candidate-completion",
                        "object": "chat.completion",
                        "model": request.get("model"),
                        "provider": "controlled_recorded_response",
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": content},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": usage_payload.get("prompt_tokens") or 0,
                            "completion_tokens": usage_payload.get("completion_tokens") or 0,
                            "total_tokens": usage_payload.get("total_tokens") or 0,
                        },
                    },
                )

            @staticmethod
            def _compiler_tool_name(request: dict[str, object]) -> str | None:
                tools = request.get("tools")
                if not isinstance(tools, list):
                    return None
                for tool in tools:
                    if not isinstance(tool, dict):
                        continue
                    function = tool.get("function")
                    if not isinstance(function, dict):
                        continue
                    name = function.get("name")
                    if name == "emit_design_problem":
                        return name
                return None

            def _send_json(self, status: int, payload: object) -> None:
                body = json.dumps(payload, sort_keys=True).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *args: object) -> None:
                del args

        Handler.owner = self
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        """Return this test server's ephemeral OpenAI-compatible API root."""
        host, port = self._server.server_address
        return f"http://{host}:{port}/v1"

    def __enter__(self) -> ControlledCandidateGateway:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def set_fixture(
        self,
        recording: dict[str, object],
        *,
        problem: object,
    ) -> None:
        """Select one immutable synthetic overlay and its compiler product."""
        self._validate_recording(recording)
        model_dump = getattr(problem, "model_dump", None)
        if not callable(model_dump):
            raise TypeError("controlled_gateway_problem_untyped")
        problem_payload = model_dump(mode="json")
        if not isinstance(problem_payload, dict):
            raise TypeError("controlled_gateway_problem_untyped")
        with self._lock:
            self._recording = copy.deepcopy(recording)
            self._problem = copy.deepcopy(problem_payload)
            self._n4_cursor = 0

    @staticmethod
    def _validate_recording(recording: dict[str, object]) -> None:
        n4_contract._validate_recording_fixture(recording)  # type: ignore[arg-type]


def _current_compiler_problem(recording: dict[str, object]):
    """Build honest current-schema compiler arguments without rewriting replay bytes."""

    historical = n4_contract._design_problem(recording)
    source_text = "all proposals remain candidate-only"
    assert source_text in historical.nl_provenance.raw_request
    constraints = [
        constraint.model_copy(
            update={
                "description": "All proposals remain candidate-only.",
                "source_text": source_text,
            }
        )
        if constraint.constraint_id == "no_authority_without_a"
        else constraint
        for constraint in historical.constraints
    ]
    return historical.model_copy(
        update={
            "schema_version": DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
            "constraints": constraints,
        }
    )


def _controlled_procurement_recording(
    recording: dict[str, object], *, outcome_variable: str, intensity: int = 1
) -> dict[str, object]:
    """Return a new synthetic fixture identity for a controlled N4 replay overlay."""

    from polisyos.pdc import gy_content_hash

    controlled = copy.deepcopy(recording)
    base_recording_id = str(controlled.get("recording_id") or "recording")
    base_content_hash = str(controlled.get("recording_content_hash") or "")
    responses = controlled.get("responses")
    assert isinstance(responses, list)
    for index in (4, 8):
        response = responses[index]
        assert isinstance(response, dict)
        raw = response.get("raw_response")
        assert isinstance(raw, str)
        trinity = json.loads(raw)
        interventions = trinity["policy_spec"]["interventions"]
        procurement = next(
            item for item in interventions if item.get("kind") == "procurement_shock_intensity"
        )
        procurement["params"] = {"intensity": intensity}
        procurement["notes"] = [
            "do.target=cells.distress_score sign=decrease "
            f"outcome={outcome_variable} "
            f"effect_path=cells.distress_score,{outcome_variable}"
        ]
        rewritten = json.dumps(trinity, sort_keys=True, separators=(",", ":"))
        response["raw_response"] = rewritten
        response["raw_response_hash"] = gy_content_hash(rewritten)

    # Edited provider bytes are a synthetic test fixture, not the historical
    # provider capture. Give the overlay an identity derived from its changed
    # bytes and retain an explicit lineage pointer to the immutable source.
    identity_seed = gy_content_hash(
        {
            "base_recording_id": base_recording_id,
            "base_content_hash": base_content_hash,
            "response_hashes": [
                item.get("raw_response_hash") for item in responses if isinstance(item, dict)
            ],
            "outcome_variable": outcome_variable,
            "intensity": intensity,
        }
    ).removeprefix("sha256:")[:20]
    fixture_id = f"synthetic_controlled_n4_{identity_seed}"
    controlled["fixture_id"] = fixture_id
    controlled["recording_id"] = fixture_id
    controlled["recording_source"] = "synthetic_controlled_overlay_of_recorded_capture"
    controlled["derived_from_recording_id"] = base_recording_id
    controlled["derived_from_content_hash"] = base_content_hash

    controlled["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in controlled.items() if key != "recording_content_hash"}
    )
    n4_contract._validate_recording_fixture(controlled)
    return controlled


_CONTROLLED_SLOT_ALIASES = {
    "agents_income": "agents.income",
    "agents_is_employed": "agents.is_employed",
    "cells_distress_score": "cells.distress_score",
    "employment_retention": "cells.employment",
    "employment_retention_rate": "cells.employment",
    "global_tax_rate": "global.tax_rate",
    "government_balance": "government.balance",
}


@dataclass(frozen=True)
class ControlledSKGSourceSelection:
    """Exact owner-resolved identity for one read-only controlled SKG source."""

    db_path: Path
    version_id: int
    snapshot_ref: str
    sha256: str
    schema_sha256: str


def _controlled_skg_source_observation(db_path: Path) -> tuple[int, str, str, str]:
    """Observe version, ref, bytes, and schema through read-only owner APIs."""
    import duckdb

    from polisyos.data_forge.read_api.academic import SKGQuery

    resolved_path = db_path.resolve()
    if not resolved_path.is_file():
        raise ValueError("controlled_selected_skg_source_missing")
    if resolved_path.with_name(resolved_path.name + ".wal").exists():
        raise ValueError("controlled_selected_skg_source_wal_unbound")
    before_stat = resolved_path.stat()
    before_identity = (
        before_stat.st_dev,
        before_stat.st_ino,
        before_stat.st_size,
        before_stat.st_mtime_ns,
    )
    before_sha256 = hashlib.sha256(resolved_path.read_bytes()).hexdigest()
    try:
        with duckdb.connect(str(resolved_path), read_only=True) as connection:
            schema_rows = tuple(
                (str(table), str(column), str(data_type))
                for table, column, data_type in connection.execute(
                    "SELECT table_name, column_name, data_type "
                    "FROM information_schema.columns "
                    "WHERE table_catalog=current_database() AND table_schema='main' "
                    "ORDER BY table_name, ordinal_position"
                ).fetchall()
            )
            versions = tuple(
                int(row[0])
                for row in connection.execute(
                    "SELECT version_id FROM main.ac_skg_versions ORDER BY version_id"
                ).fetchall()
            )
    except (duckdb.Error, OSError, TypeError, ValueError) as exc:
        raise ValueError("controlled_selected_skg_source_schema_unresolved") from exc
    required_columns = {
        ("ac_skg_edges", "edge_id"),
        ("ac_skg_edges", "src"),
        ("ac_skg_edges", "dst"),
        ("ac_skg_variables", "canonical_name"),
        ("ac_skg_versions", "version_id"),
    }
    if not required_columns.issubset({(table, column) for table, column, _ in schema_rows}):
        raise ValueError("controlled_selected_skg_source_schema_incomplete")
    if versions != (7,):
        raise ValueError("controlled_selected_skg_source_version_set_mismatch")
    query = SKGQuery(db_path=resolved_path, index_dir=resolved_path.parent / "index")
    try:
        version_id = query.latest_skg_version_id()
        if version_id is None or not query.has_skg_version_id(version_id=version_id):
            raise ValueError("controlled_selected_skg_source_version_unresolved")
        snapshot_ref = query.skg_snapshot_ref(version_id=version_id)
    finally:
        query.close()
    if version_id != 7 or snapshot_ref is None:
        raise ValueError("controlled_selected_skg_source_version_unresolved")
    after_stat = resolved_path.stat()
    after_identity = (
        after_stat.st_dev,
        after_stat.st_ino,
        after_stat.st_size,
        after_stat.st_mtime_ns,
    )
    after_sha256 = hashlib.sha256(resolved_path.read_bytes()).hexdigest()
    if before_identity != after_identity or before_sha256 != after_sha256:
        raise ValueError("controlled_selected_skg_source_changed_during_read")
    schema_sha256 = hashlib.sha256(
        json.dumps(schema_rows, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return version_id, snapshot_ref, before_sha256, schema_sha256


def _capture_controlled_skg_source(db_path: Path) -> ControlledSKGSourceSelection:
    """Bind the new controlled source only after its real reader resolves it."""
    version_id, snapshot_ref, sha256, schema_sha256 = _controlled_skg_source_observation(db_path)
    return ControlledSKGSourceSelection(
        db_path=db_path.resolve(),
        version_id=version_id,
        snapshot_ref=snapshot_ref,
        sha256=sha256,
        schema_sha256=schema_sha256,
    )


def _validate_controlled_skg_source(
    selected_source: ControlledSKGSourceSelection,
) -> ControlledSKGSourceSelection:
    """Refuse any changed, malformed, or differently versioned selected source."""
    from polisyos.runtime.quality.world_model_record import _parse_skg_snapshot_ref

    if type(selected_source) is not ControlledSKGSourceSelection:
        raise TypeError("controlled_selected_skg_source_untyped")
    parsed = _parse_skg_snapshot_ref(selected_source.snapshot_ref)
    if (
        parsed.db_path.resolve() != selected_source.db_path.resolve()
        or parsed.version_id != selected_source.version_id
    ):
        raise ValueError("controlled_selected_skg_source_ref_mismatch")
    version_id, snapshot_ref, sha256, schema_sha256 = _controlled_skg_source_observation(
        selected_source.db_path
    )
    if version_id != selected_source.version_id or snapshot_ref != selected_source.snapshot_ref:
        raise ValueError("controlled_selected_skg_source_version_mismatch")
    if schema_sha256 != selected_source.schema_sha256:
        raise ValueError("controlled_selected_skg_source_schema_mismatch")
    if sha256 != selected_source.sha256:
        raise ValueError("controlled_selected_skg_source_bytes_mismatch")
    return selected_source


def _materialize_controlled_world_model_record(
    *,
    source_world_model_record: Any,
    artifact_store: ArtifactStore,
    tmp_path: Path,
    substrate_registry: Any,
    selected_registry_entry_hashes: Sequence[str],
    substrate_registry_ref: Any,
    policy_slot_ids: Sequence[str],
    selected_skg_source: ControlledSKGSourceSelection,
    tenant_id: str,
    cell_id: str,
) -> Any:
    """Build a source-bound, limited WMR from real local owner artifacts.

    The synthetic fixture aliases its explicit controlled variables onto existing
    canonical runtime paths. It never represents an empirical or live source.
    """
    source_root = tmp_path / "controlled-candidate-source"
    expected_skg_path = source_root / "academic-skg.duckdb"
    if selected_skg_source.db_path.resolve() != expected_skg_path.resolve():
        raise ValueError("controlled_selected_skg_source_path_mismatch")
    _validate_controlled_skg_source(selected_skg_source)

    from polisyos.core.artifacts import (
        ArtifactRef,
        PutOptions,
        input_ref_from_artifact_ref,
    )
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts import DataSnapshot
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.data_forge.kernel.pipeline.manifests import write_publish_manifest
    from polisyos.data_forge.kernel.snapshot import finalize_snapshot
    from polisyos.fabric.world import (
        WorldSnapshotFactWrite,
        WorldSnapshotNodeWrite,
        WorldSnapshotWriteRequest,
        write_world_snapshot,
    )
    from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.pdc import WorldModelLimitations
    from polisyos.runtime.quality.substrate_registry import SubstrateRegistry
    from polisyos.runtime.quality.world_model_record import (
        BranchMode,
        FabricWorldRef,
        SkgCausalPriorRef,
        build_world_model_record,
        load_world_model_record,
        world_model_record_content_hash,
    )

    if not selected_registry_entry_hashes:
        raise ValueError("controlled_wmr_selected_registry_entries_missing")
    registry = SubstrateRegistry.model_validate(substrate_registry.model_dump(mode="json"))
    selected_hashes = tuple(dict.fromkeys(str(item) for item in selected_registry_entry_hashes))
    selected_entries = tuple(
        entry for entry in registry.entries if entry.entry_content_hash in selected_hashes
    )
    if {entry.entry_content_hash for entry in selected_entries} != set(selected_hashes):
        raise ValueError("controlled_wmr_selected_registry_entry_unresolved")
    supplied_registry_ref = ArtifactRef.model_validate(
        substrate_registry_ref.model_dump(mode="python")
    )

    aliases: list[tuple[str, str]] = []
    for slot_id in dict.fromkeys(str(item) for item in policy_slot_ids):
        canonical_id = _CONTROLLED_SLOT_ALIASES.get(slot_id, slot_id)
        if canonical_id not in DEFAULT_SLOT_REGISTRY.slots:
            raise ValueError("controlled_wmr_slot_alias_not_established:" + slot_id)
        aliases.append((slot_id, canonical_id))
    if not aliases:
        raise ValueError("controlled_wmr_policy_slots_missing")
    canonical_slot_ids = tuple(dict.fromkeys(canonical for _, canonical in aliases))

    source_root = tmp_path / "controlled-candidate-source"
    snapshot_id = "controlled-candidate-source-v1"
    fabric_root = source_root / "fabric-world"
    fabric_db = source_root / "fabric-world.duckdb"
    data_forge_root = source_root / "data-forge" / snapshot_id
    academic_artifact = data_forge_root / "academic" / "academic.jsonl"
    academic_artifact.parent.mkdir(parents=True, exist_ok=True)
    academic_artifact.write_text(
        '{"snapshot_id":"' + snapshot_id + '"}\n',
        encoding="utf-8",
    )
    write_publish_manifest(
        manifest_path=data_forge_root / "academic" / "publish" / "manifest.json",
        pipeline="academic",
        artifacts=(academic_artifact,),
        published_at="2026-05-24T08:30:00+00:00",
        extra={
            "corpus_id": "controlled-candidate-source",
            "builder_revision": "fixture:controlled-candidate-source-v1",
            "lineage_refs": ["fixture://controlled-candidate-source"],
        },
    )
    finalize_snapshot(
        data_forge_root,
        update_latest_symlink=False,
        pipelines=("academic",),
    )

    visible_time = "2026-05-24T00:00:00+00:00"
    transaction_time = "2026-05-24T12:00:00+00:00"
    node_id = "world.controlled.candidate-fixture"
    write_world_snapshot(
        fabric_db,
        WorldSnapshotWriteRequest(
            snapshot_root=fabric_root,
            snapshot_id=snapshot_id,
            branch_name="main",
            as_of_valid_time=visible_time,
            as_of_tx_time=transaction_time,
            provenance={"source": "controlled_candidate_fixture"},
            nodes=(
                WorldSnapshotNodeWrite(
                    node_id=node_id,
                    kind="claim",
                    label="Controlled candidate fixture",
                    artifact_id=None,
                    props_ref=None,
                ),
            ),
            facts=(
                WorldSnapshotFactWrite(
                    fact_id=f"fact:{snapshot_id}:controlled-candidate",
                    schema_version="1.0",
                    subject_id=node_id,
                    predicate_id="world.kind",
                    object_value="claim",
                    target_id=None,
                    valid_time=visible_time,
                    tx_time=transaction_time,
                    provenance_json={"source": "controlled_candidate_fixture"},
                    trust_json=None,
                    legal_json=None,
                    segment_id=f"seg:{snapshot_id}:controlled-candidate",
                ),
            ),
        ),
    )

    from polisyos.core.security.tenant_context import tenant_scope

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        payload_ref = artifact_store.put_json(
            {
                "agents": {
                    "income": [1200.0],
                    "is_employed": [True],
                },
                "cells": {
                    "distress_score": [0.0],
                    "employment": [1.0],
                },
                "government_balance": 0.0,
                "tax_rate": 0.0,
            },
            PutOptions(kind="fabric.world_payload", media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        data_snapshot_ref = artifact_store.put_json(
            DataSnapshot(
                data_ref=payload_ref,
                stats={"snapshot_id": snapshot_id},
                notes=["snapshot_id:" + snapshot_id, "controlled_candidate_only"],
            ),
            PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        # Preserve the DataSnapshot's typed payload relationship in its own manifest.
        snapshot_manifest = artifact_store.get_manifest(data_snapshot_ref)
        if not snapshot_manifest.inputs:
            data_snapshot_ref = artifact_store.put_bytes(
                artifact_store.get_bytes(data_snapshot_ref),
                PutOptions(
                    kind=snapshot_manifest.kind,
                    media_type=snapshot_manifest.media_type,
                    schema=snapshot_manifest.artifact_schema,
                    inputs=(input_ref_from_artifact_ref(payload_ref, role="input.data_ref"),),
                ),
            )
        registry_bundle = build_default_registry_bundle(artifact_store)

    model_spec = ModelSpec(
        model_id="model_controlled_candidate_source",
        data_snapshot_ref=str(data_snapshot_ref.artifact_id),
        registry_bundle_ref=str(registry_bundle.bundle_ref.artifact_id),
        calibrated=False,
        notes=["controlled candidate-only source fixture"],
    )

    skg_version_id = selected_skg_source.version_id
    skg_snapshot_ref = selected_skg_source.snapshot_ref

    selected_sources = tuple(dict.fromkeys(entry.source_id for entry in selected_entries))
    selected_families = tuple(dict.fromkeys(entry.family_id for entry in selected_entries))
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        built = build_world_model_record(
            artifact_store,
            fabric_world_ref=FabricWorldRef(
                snapshot_root=str(fabric_root),
                snapshot_id=snapshot_id,
                branch="main",
                as_of_valid_time=visible_time,
                as_of_tx_time=transaction_time,
                world_query_policy="default_allow_public",
                provenance_manifest_ref="fixture://controlled-candidate-source-v1",
            ),
            data_forge_snapshot_binding_path=(data_forge_root / "data_forge_snapshot_binding.json"),
            data_snapshot_ref=ArtifactRef.model_validate(
                data_snapshot_ref.model_dump(mode="python")
            ),
            model_spec=model_spec,
            skg_causal_prior_ref=SkgCausalPriorRef(
                skg_snapshot_ref=skg_snapshot_ref,
                skg_version_id=str(skg_version_id),
                source_data_snapshot_id=snapshot_id,
            ),
            substrate_registry=registry,
            region_or_jurisdiction=source_world_model_record.region_or_jurisdiction,
            population_scope=source_world_model_record.population_scope,
            policy_domain=source_world_model_record.policy_domain,
            valid_time_scope=source_world_model_record.valid_time_scope,
            tx_time_scope=source_world_model_record.tx_time_scope,
            resolution=source_world_model_record.resolution,
            branch_mode=BranchMode.SCENARIO,
            policy_slot_ids=canonical_slot_ids,
            producer_ref=(
                "tests._helpers.controlled_candidate_profile."
                "materialize_controlled_world_model_record"
            ),
            required_substrate_sources=selected_sources,
            required_substrate_families=selected_families,
            substrate_registry_artifact_ref=supplied_registry_ref,
            registry_bundle_artifact_ref=registry_bundle.bundle_ref,
            ncm_view_refs=(),
            limitations=WorldModelLimitations(
                admissibility_blockers=("causal_coupling_not_established",)
            ),
            candidate_only=True,
        )
        if load_world_model_record(artifact_store, built.record_ref) != built.record:
            raise ValueError("controlled_wmr_source_reader_mismatch")

    canonical_bindings = {item.slot_id: item for item in built.record.policy_slot_map}
    alias_bindings = tuple(
        canonical_bindings[canonical_id].model_copy(
            update={"slot_id": alias, "unit": "synthetic_score"}
        )
        for alias, canonical_id in aliases
    )
    foundry_binding_ref = built.record.foundry_binding_ref.model_copy(
        update={
            "state_slot_digest": gy_content_hash(
                {
                    "bound_state_snapshot_ref": str(
                        built.record.foundry_binding_ref.bound_state_snapshot_ref
                    ),
                    "policy_slot_map": [item.model_dump(mode="json") for item in alias_bindings],
                }
            )
        }
    )
    draft = built.record.model_copy(
        update={
            "policy_slot_map": alias_bindings,
            "foundry_binding_ref": foundry_binding_ref,
            "producer_ref": (
                "tests._helpers.controlled_candidate_profile.candidate_only_slot_alias_projection"
            ),
        }
    )
    content_hash = world_model_record_content_hash(draft)
    payload = draft.model_dump(mode="python")
    payload.update(
        {
            "world_model_record_id": (
                "world_model_record_" + content_hash.removeprefix("sha256:")[:16]
            ),
            "content_hash": content_hash,
        }
    )
    return type(built.record).model_validate(payload)


def _configured_procurement_profile(
    *,
    recorded_problem: object,
    artifact_store: ArtifactStore,
    tenant_id: str,
    cell_id: str,
):
    """Return a configured candidate profile and its explicit synthetic SCM."""

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.analytics.ncm import (
        ExogenousSpec,
        NCMSpec,
        StructuralEquation,
        persist_ncm_spec,
    )
    from polisyos.pdc import gy_content_hash, world_model_record_content_hash
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioN5Config,
        CandidateScenarioSetToRule,
        CandidateSimulationContextInputs,
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_cycle import (
        _build_boundary_world_model_record,
    )
    from polisyos.runtime.quality.intervention_substrate import (
        load_l6_intervention_substrate,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec

    base_problem, base_context = _controlled_profile_cycle_basis(recorded_problem)
    outcome_variable = recorded_problem.outcome_of_interest.target_variable
    ncm = NCMSpec(
        endogenous_vars=["cells.distress_score", outcome_variable],
        exogenous_specs=[
            ExogenousSpec(
                variable="u_distress",
                associated_endogenous="cells.distress_score",
                distribution_params={"mean": 0.0, "std": 0.01},
            ),
            ExogenousSpec(
                variable="u_output",
                associated_endogenous=outcome_variable,
                distribution_params={"mean": 0.0, "std": 0.01},
            ),
        ],
        structural_equations=[
            StructuralEquation(
                variable="cells.distress_score",
                parents=[],
                exogenous="u_distress",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            ),
            StructuralEquation(
                variable=outcome_variable,
                parents=["cells.distress_score"],
                exogenous="u_output",
                equation_type="linear",
                equation_params={
                    "intercept": 0.0,
                    "coefficients": {"cells.distress_score": 0.5},
                },
            ),
        ],
        is_acyclic=True,
        markov_condition_verified=True,
        independence_model="dag_markov",
        fit_method="synthetic_candidate_profile_fixture",
    )
    with tenant_scope(
        None,
        tenant_id=tenant_id,
        cell_id=cell_id,
    ):
        ncm_ref = persist_ncm_spec(_ensure_ir_artifact_store(artifact_store), ncm)

    candidate_slots = tuple(
        dict.fromkeys(
            [lever.target_slot for lever in recorded_problem.candidate_lever_space.candidate_levers]
            + ["global.tax_rate", "cells.distress_score", outcome_variable]
        )
    )
    world = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=base_problem,
        outcome=outcome_variable,
        policy_slot_ids=candidate_slots,
        substrate_registry=base_context.substrate_registry,
        selected_registry_entry_hashes=base_context.selected_registry_entry_hashes,
    )
    bindings = tuple(
        item.model_copy(update={"unit": "synthetic_score"}) for item in world.policy_slot_map
    )
    foundry = world.foundry_binding_ref.model_copy(
        update={
            "state_slot_digest": gy_content_hash(
                {
                    "boundary": "state_slots",
                    "slots": [item.model_dump(mode="json") for item in bindings],
                }
            )
        }
    )
    draft = world.model_copy(update={"policy_slot_map": bindings, "foundry_binding_ref": foundry})
    world = draft.model_copy(
        update={
            "content_hash": world_model_record_content_hash(draft),
            "world_model_record_id": (
                "world_model_record_"
                + world_model_record_content_hash(draft).removeprefix("sha256:")[:16]
            ),
        }
    )
    world = _record_with_selected_ncm_ref(world, str(ncm_ref.artifact_id))
    context_inputs = CandidateSimulationContextInputs(
        substrate_registry=base_context.substrate_registry,
        selected_registry_entry_hashes=base_context.selected_registry_entry_hashes,
        world_model_record=world,
        intervention_substrate=load_l6_intervention_substrate(REPO_ROOT),
        source_pack_content_hash=base_context.source_pack_content_hash,
        substrate_input_content_hash=base_context.substrate_input_content_hash,
    )
    rule = CandidateScenarioSetToRule(
        operator_kind="procurement_shock_intensity",
        parameter_id="intensity",
        target_world_slot="cells.distress_score",
        unit_id="synthetic_score",
        minimum=0,
        maximum=1,
    )
    n5 = CandidateScenarioN5Config(
        budget_ref="budget://r1/controlled-candidate-n5",
        horizon=HorizonSpec(start=0, end=0, step=1),
        baseline_state={"cells.distress_score": 0.0, outcome_variable: 0.0},
        seed=11,
        replications=2,
    )
    fields = {
        "schema_version": "policyos.runtime.candidate_simulation_profile.v2",
        "profile_id": "r1.controlled.synthetic.procurement",
        "profile_selection_ref": cycle_job_profile_selection_ref(recorded_problem),
        "context_inputs": context_inputs,
        "rule": rule,
        "n5": n5,
        "limitations": (
            "scenario_only",
            "real_profile_not_established",
            "real_time_not_established",
            "grounding_not_established",
            "s8_blocked",
            "n9_not_admitted",
        ),
    }
    draft_profile = CandidateSimulationScenarioProfile.model_construct(
        **fields,
        content_hash="sha256:" + "0" * 64,
    )
    profile = CandidateSimulationScenarioProfile.model_validate(
        {
            **fields,
            "content_hash": gy_content_hash(
                draft_profile.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    declaration_fields = {
        "schema_version": ("policyos.runtime.candidate_simulation.synthetic_model_declaration.v1"),
        "profile_config_ref": candidate_simulation_profile_ref(profile),
        "profile_content_hash": profile.content_hash,
        "profile_selection_ref": profile.profile_selection_ref,
        "target_world_slot": rule.target_world_slot,
        "outcome_variable": outcome_variable,
        "target_unit_id": rule.unit_id,
        "outcome_unit_id": rule.unit_id,
        "target_baseline": 0.0,
        "outcome_baseline": 0.0,
        "outcome_per_target_unit": 0.5,
        "outcome_noise_stddev": 0.01,
        "assumption": "declared_candidate_scm_not_empirically_grounded",
    }
    declaration_draft = CandidateSimulationSyntheticModelDeclarationV1.model_construct(
        **declaration_fields,
        content_hash="sha256:" + "0" * 64,
    )
    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {
            **declaration_fields,
            "content_hash": gy_content_hash(
                declaration_draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    return profile, declaration


@dataclass(frozen=True)
class _Atom:
    intervention_id: str
    content_hash: str
    status: str = "candidate_unverified"
    world_model_record_ref: str | None = "world_model_record_test"
    target_world_slots: tuple[str, ...] = ("firm_survival",)
    problem_frame_ref: str | None = None


@dataclass(frozen=True)
class _Candidate:
    candidate_id: str
    atom: _Atom | InterventionAtomBinding
    diversity_key: tuple[str, str, str, str]
    status: str = "candidate_unverified"


@dataclass(frozen=True)
class _Ranking:
    candidate_id: str
    score: float
    voi_estimate: float
    trust_level: str = "search_guiding"
    promotion_allowed: bool = False


@dataclass(frozen=True)
class _GenerationResult:
    status: str
    candidates: tuple[_Candidate, ...]
    surrogate_rankings: tuple[_Ranking, ...]
    grounding_dispositions: tuple[Any, ...] = ()
    design_problem_ref: str | None = None


@dataclass(frozen=True)
class _CertificateChain:
    cg1_certificate_id: str = "cg1_cert_test"
    cg1_content_hash: str = "sha256:" + "a" * 64
    cg2_certificate_id: str = "cg2_cert_test"
    cg2_content_hash: str = "sha256:" + "b" * 64
    cg3_certificate_id: str = "cg3_cert_test"
    cg3_content_hash: str = "sha256:" + "c" * 64
    cg4_proxy_gap_risk_id: str | None = None
    cg4_proxy_gap_content_hash: str | None = None
    cg4_quarantine_handoff_id: str | None = None
    cg4_quarantine_handoff_hash: str | None = None
    cg5_action_certificate_id: str | None = None
    cg5_action_content_hash: str | None = None
    cg5_ticket_id: str | None = None
    cg5_ticket_hash: str | None = None


@dataclass(frozen=True)
class _GroundingDisposition:
    proposal_id: str
    candidate_id: str | None
    raw_candidate_hash: str
    disposition: str
    selected_relation: str
    shadow_atom_content_hash: str | None = None
    identified_atom_id: str | None = "atom_test"
    cg2_decision: str | None = "shadow_frozen"
    cg2_reason: str | None = "cg2_frozen_until_cg6"
    cg3_decision: str | None = "shadow"
    cg3_reason: str | None = "cg3_shadow_only"
    rejected_cause: dict[str, Any] | None = None
    certificate_chain: _CertificateChain = _CertificateChain()
    bridge_missing_records: tuple[dict[str, Any], ...] = ()


class _SameCandidateNewBasisGenerator:
    """Return one candidate identity with a distinct content occurrence per cycle."""

    def __init__(self) -> None:
        self.problems: list[DesignProblem] = []

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        self.problems.append(problem)
        candidate = _Candidate(
            candidate_id="candidate_same_subject",
            atom=_Atom(
                "candidate_same_subject",
                "sha256:" + ("1" if cycle_index == 0 else "2") * 64,
            ),
            diversity_key=("grant", "firms", "same_subject", f"cycle_{cycle_index}"),
        )
        return _GenerationResult(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(
                _Ranking(
                    candidate_id=candidate.candidate_id,
                    score=0.93 if cycle_index == 0 else 0.31,
                    voi_estimate=0.82 if cycle_index == 0 else 0.41,
                ),
            ),
        )


class _AlwaysLowGrounding:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del problem, generation_result
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounding_gap",
            grounding_score=0.2 if cycle_index == 0 else 0.68,
            issue_codes=("missing_supporting_data",) if cycle_index == 0 else (),
            evidence_refs=() if cycle_index == 0 else ("evidence://supporting-data",),
            current_valid=False,
        )


class _StableShadowGrounding:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del problem, cycle_index, generation_result
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounded_shadow",
            grounding_score=0.8,
            evidence_refs=("evidence://b29/stable-shadow",),
            current_valid=False,
            report_ref="grounding://b29/stable-shadow",
            grounding_source="cgf_firewall",
            grounding_disposition="shadow_bound",
        )


class _CgfGenerationPort:
    def __init__(
        self,
        *,
        missing_owner_target: bool = False,
        proxy_gap: bool = False,
        target_world_slots: tuple[str, ...] = ("firm_survival",),
    ) -> None:
        self._missing_owner_target = missing_owner_target
        self._proxy_gap = proxy_gap
        self._target_world_slots = target_world_slots

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        del cycle_index
        problem_ref = gy_content_hash(problem.model_dump(mode="json"))
        candidate = _Candidate(
            candidate_id="candidate_cgf_shadow",
            atom=_Atom(
                "candidate_cgf_shadow",
                "sha256:" + "4" * 64,
                target_world_slots=() if self._missing_owner_target else self._target_world_slots,
                problem_frame_ref=problem_ref,
            ),
            diversity_key=("grant", "firms", "cgf_shadow", "baseline"),
        )
        chain = _CertificateChain(
            cg4_proxy_gap_risk_id="cg4_proxy_gap_deadbeefdeadbeef" if self._proxy_gap else None,
            cg4_proxy_gap_content_hash="sha256:" + "d" * 64 if self._proxy_gap else None,
            cg4_quarantine_handoff_id="cg4_quarantine_deadbeefdeadbeef"
            if self._proxy_gap
            else None,
            cg4_quarantine_handoff_hash="sha256:" + "e" * 64 if self._proxy_gap else None,
            cg5_action_certificate_id="cg5_action_deadbeefdeadbeef" if self._proxy_gap else None,
            cg5_action_content_hash="sha256:" + "f" * 64 if self._proxy_gap else None,
        )
        disposition = _GroundingDisposition(
            proposal_id="proposal.cgf_shadow",
            candidate_id=candidate.candidate_id,
            raw_candidate_hash="sha256:" + "5" * 64,
            disposition="shadow_bound",
            selected_relation="exact",
            shadow_atom_content_hash=candidate.atom.content_hash,
            certificate_chain=chain,
            bridge_missing_records=(
                {
                    "pattern": "bridge_missing",
                    "owner": "CG4",
                    "integration_status": "handoff_artifact_n6_direct_intake_not_wired",
                },
            )
            if self._proxy_gap
            else (),
        )
        return _GenerationResult(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(
                _Ranking(candidate_id=candidate.candidate_id, score=0.91, voi_estimate=0.6),
            ),
            grounding_dispositions=(disposition,),
            design_problem_ref=problem_ref,
        )


def _problem(problem_id: str = "generic_cycle_problem") -> DesignProblem:
    return DesignProblem(
        design_problem_id=problem_id,
        problem_statement="Improve firm survival with grounded support under fiscal constraints.",
        domain="generic_policy",
        nl_provenance=NLProvenance(
            raw_request="Improve firm survival with grounded support.",
            source_surface="test_generation_cycle",
        ),
        authority_profile=AuthorityProfile(
            requester_authority="research_lab",
            requested_authority_level="research",
            mandate="test-only research mandate",
        ),
        jurisdiction_time=JurisdictionTimeSemantics(
            region="UA",
            valid_time="2026",
            as_of="2026-06-29",
            policy_time="2026",
            data_time="2026",
        ),
        objectives=[
            DesignObjective(
                objective_id="firm_survival",
                description="Improve firm survival",
                metric_id="firm_survival",
            )
        ],
        constraints=[
            DesignConstraint(
                constraint_id="shadow_only",
                description="Generated candidates remain shadow until A/N9 certification.",
                hard=True,
                admissibility_basis="request_text",
                source_text="Do not promote generated candidates.",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="firms",
                name="Firms",
                role="target_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable="firm_survival",
            metric_id="firm_survival",
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["grant", "tax_relief"],
            candidate_levers=[
                CandidateLever(
                    lever_id="grant",
                    operator_kind="grant",
                    instrument="Targeted grant",
                    target_slot="government_balance",
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(
            needs=[
                EvidenceNeed(
                    need_id="supporting_data",
                    question="Which data grounds this effect?",
                    required_for="A-side grounding",
                )
            ]
        ),
    )


def _record_with_selected_ncm_ref(record: Any, ncm_ref: str) -> Any:
    """Rebind a fixture WMR to one selected NCM artifact without changing other fields."""

    from polisyos.runtime.quality.world_model_record import world_model_record_content_hash

    simulation_model_ref = record.simulation_model_ref.model_copy(update={"ncm_refs": (ncm_ref,)})
    draft = record.model_copy(update={"simulation_model_ref": simulation_model_ref})
    content_hash = world_model_record_content_hash(draft)
    payload = draft.model_dump(mode="python")
    payload["content_hash"] = content_hash
    payload["world_model_record_id"] = (
        f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}"
    )
    return type(record).model_validate(payload)


def _budget(max_usd: str = "5.0") -> BudgetState:
    return BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal(max_usd))},
    )


def _controlled_profile_cycle_basis(
    problem_seed: DesignProblem,
    *,
    runtime_hints: dict[str, Any] | None = None,
) -> tuple[DesignProblem, Any]:
    """Build only the owner-bound cycle context consumed by the profile fixture."""
    from polisyos.runtime.quality.cycle_substrate import build_cycle_substrate_context
    from polisyos.runtime.quality.generation_cycle import _build_boundary_world_model_record
    from polisyos.runtime.quality.substrate_registry import (
        SubstrateCoverage,
        SubstrateLayer,
        SubstrateRegistration,
        SubstrateSchemaRegime,
        SubstrateTrustTier,
        build_substrate_registry,
        build_substrate_registry_entry,
    )

    hints: dict[str, Any] = {
        "joint_simulation_budget_ref": f"budget://cyc-01/{uuid4().hex}/n5",
        "joint_simulation_horizon": {"start": 0, "end": 3, "step": 1},
        "joint_simulation_resource": "ncm_parallel_worlds",
    }
    if runtime_hints:
        hints.update(runtime_hints)
    problem = problem_seed.model_copy(update={"runtime_hints": hints})
    domain = problem.domain
    registration = SubstrateRegistration(
        source_id="l2_cyc:serializable_n5_builder.duckdb",
        family_id=f"{domain}_causal_priors",
        layer=SubstrateLayer.L2,
        coverage=SubstrateCoverage(
            coverage_score=0.74,
            coverage_kind="lane0.causal_claim_coverage",
            coverage_rule_ref=f"lane0://{domain}/coverage",
            observation_count=7,
            metric_binding_count=3,
        ),
        trust_tier=SubstrateTrustTier(
            tier="derived_proxy",
            trust_cap=0.5,
            trust_multiplier=0.6,
            min_coverage=0.0,
            max_coverage=1.0,
            authority_ref=f"lane0://{domain}/trust",
        ),
        identification_mode="causal_prior_candidate",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id=f"{domain}_schema_v1",
            authority_ref=f"lane0://{domain}/schema",
            source_version="1",
        ),
        data_version=f"{domain}-data-v1",
        snapshot_id=f"{domain}-snapshot-v1",
        source_snapshot_id=f"{domain}-snapshot-v1",
        provenance_refs=(f"lane0://{domain}/causal-claims",),
        authority_refs=(f"lane0://{domain}/registry-owner",),
    )
    registry = build_substrate_registry(
        (build_substrate_registry_entry(registration),),
        producer_ref="tests.unit.runtime.quality.test_generation_cycle",
        source_catalog_refs=registration.authority_refs,
    )
    selected_hash = registry.entries[0].entry_content_hash
    world = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=problem,
        outcome="firm_survival",
        policy_slot_ids=("agents.income", "government.balance", "firm_survival"),
        substrate_registry=registry,
        selected_registry_entry_hashes=(selected_hash,),
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    substrate_input_hash = gy_content_hash(
        {"domain": problem.domain, "registry": registry.content_hash}
    )
    context = build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=(selected_hash,),
        world_model_record=world,
        intervention_substrate=None,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=gy_content_hash("cyc-n5-builder-pack"),
        substrate_input_content_hash=substrate_input_hash,
    )
    return problem, context
