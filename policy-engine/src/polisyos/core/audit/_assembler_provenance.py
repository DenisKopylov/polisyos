"""Provenance construction, signature collection, and public key resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.serialization import load_pem_public_key

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactManifest
from polisyos.core.artifacts.signing import (
    DEFAULT_IDENTITIES_PATH,
    DEFAULT_TRUST_DIR,
    DetachedSignature,
    compute_key_id,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon.canon_json import from_canonical_bytes
from polisyos.core.trace.record import TraceRecord
from polisyos.core.contracts.provenance import (
    ActivityType,
    AgentType,
    EntityType,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceCoreGraph,
    ProvenanceEntity,
)

__all__ = [
    "build_merged_provenance",
    "collect_public_keys",
    "collect_signatures",
]


def collect_signatures(
    cas: FileSystemCAS,
    artifact_ids: list[ArtifactID],
) -> tuple[dict[str, DetachedSignature], list[str]]:
    """Return (hex->signature, unsigned_hex_list) for each artifact."""
    signatures: dict[str, DetachedSignature] = {}
    unsigned: list[str] = []
    for artifact_id in sorted(artifact_ids, key=lambda item: item.hex):
        signature = cas.get_signature(artifact_id)
        if signature is None:
            unsigned.append(str(artifact_id))
            continue
        signatures[artifact_id.hex] = signature
    return signatures, unsigned


def collect_public_keys(
    signatures: dict[str, DetachedSignature],
) -> tuple[dict[str, bytes], dict[str, str], list[str]]:
    """Resolve public keys and identities for the given signatures."""
    key_ids = {sig.key_id for sig in signatures.values()}
    found: dict[str, bytes] = {}
    warnings: list[str] = []
    if not key_ids:
        return found, {}, warnings

    candidates = [
        DEFAULT_TRUST_DIR,
        Path(".polisyos/keys/trusted"),
        Path.home() / ".polisyos/keys/trusted",
    ]
    for directory in candidates:
        if not directory.exists() or not directory.is_dir():
            continue
        for key_file in sorted(directory.glob("*")):
            if not key_file.is_file():
                continue
            try:
                pem = key_file.read_bytes()
                public_key = load_pem_public_key(pem)
                key_id = compute_key_id(public_key)
            except Exception:
                continue
            if key_id in key_ids:
                found[key_id] = pem

    missing = sorted(key_ids - set(found))
    for key_id in missing:
        warnings.append(f"Public key not found for key_id={key_id}")

    identities: dict[str, str] = {}
    for path in (
        DEFAULT_IDENTITIES_PATH,
        Path(".polisyos/keys/identities.json"),
        Path.home() / ".polisyos/keys/identities.json",
    ):
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text("utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        for key_id, value in payload.items():
            if key_id in key_ids and isinstance(value, str):
                identities[key_id] = value
    return found, identities, warnings


def build_merged_provenance(
    cas: FileSystemCAS,
    run_id: str,
    run_dir: Path,
    artifact_ids: list[ArtifactID],
    manifests: dict[str, ArtifactManifest],
) -> ProvenanceCoreGraph:
    """Construct a unified provenance graph from artifacts, trace, and embedded provenance."""
    graph = ProvenanceCoreGraph(graph_id=f"audit_{run_id}")
    graph.add_agent(
        ProvenanceAgent(
            agent_id="agent/system",
            agent_type=AgentType.SYSTEM,
            label="Policy OS",
        )
    )

    for artifact_id in sorted(artifact_ids, key=lambda item: item.hex):
        manifest = manifests[artifact_id.hex]
        entity = ProvenanceEntity(
            entity_id=str(artifact_id),
            entity_type=EntityType.DATASET,
            label=f"{manifest.kind}:{artifact_id.hex[:12]}",
            created_at=manifest.created_at,
            attributes={
                "artifact_id": str(artifact_id),
                "kind": manifest.kind,
                "media_type": manifest.media_type,
                "byte_size": int(manifest.byte_size),
                "sha256": manifest.integrity.sha256,
            },
        )
        graph.add_entity(entity)
        for input_ref in manifest.inputs:
            graph.add_derivation(str(artifact_id), str(input_ref.artifact_id))
        if manifest.producer is not None:
            component = str(manifest.producer.component).replace("@", "_")
            agent_id = f"agent/{component}"
            graph.add_agent(
                ProvenanceAgent(
                    agent_id=agent_id,
                    agent_type=AgentType.SYSTEM,
                    label=str(manifest.producer.component),
                    metadata={"version": manifest.producer.version},
                )
            )
            graph.add_attribution(str(artifact_id), agent_id)

    trace_path = run_dir / "trace.jsonl"
    if trace_path.exists():
        for idx, line in enumerate(trace_path.read_text("utf-8").splitlines()):
            try:
                record = TraceRecord.model_validate_json(line)
            except Exception:
                continue
            activity_id = f"{run_id}/{idx:05d}/{record.phase}/{record.event}"
            activity = ProvenanceActivity(
                activity_id=activity_id,
                activity_type=_map_trace_activity(record.phase, record.event),
                label=f"{record.phase}:{record.event}",
                started_at=record.ts,
                ended_at=record.ts,
                parameters={
                    "phase": record.phase,
                    "event": record.event,
                },
            )
            graph.add_activity(activity)
            graph.add_association(activity_id, "agent/system")
            for ref in record.refs.inputs:
                graph.add_usage(activity_id, str(ref.artifact_id))
            for ref in record.refs.outputs:
                graph.add_generation(str(ref.artifact_id), activity_id)

    for artifact_id in sorted(artifact_ids, key=lambda item: item.hex):
        try:
            payload = _load_json_payload(cas, artifact_id)
        except Exception:
            continue
        prov_ref = payload.get("provenance_ref")
        prov_artifact_id = _extract_provenance_artifact_id(prov_ref)
        if prov_artifact_id is None:
            continue
        try:
            prov_payload = _load_json_payload(cas, prov_artifact_id)
            sub_graph = ProvenanceCoreGraph.from_dict(prov_payload)
        except Exception:
            continue
        for item in sub_graph.entities.values():
            graph.add_entity(item)
        for item in sub_graph.activities.values():
            graph.add_activity(item)
        for item in sub_graph.agents.values():
            graph.add_agent(item)
        for edge in sub_graph.edges:
            graph.edges.append(edge)

    return graph


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_json_payload(cas: FileSystemCAS, artifact_id: ArtifactID) -> dict[str, Any]:
    blob = cas.get_bytes(artifact_id)
    try:
        payload = from_canonical_bytes(blob)
    except Exception:
        payload = json.loads(blob.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("artifact payload is not an object")
    return payload


def _extract_provenance_artifact_id(value: Any) -> ArtifactID | None:
    if isinstance(value, dict):
        inner = value.get("artifact_id")
        if isinstance(inner, str):
            try:
                return ArtifactID.model_validate(inner)
            except Exception:
                return None
    if isinstance(value, str):
        try:
            return ArtifactID.model_validate(value)
        except Exception:
            return None
    return None


def _map_trace_activity(phase: str, event: str) -> ActivityType:
    key = f"{phase.lower()}:{event.lower()}"
    if "ingest" in key:
        return ActivityType.INGEST
    if "query" in key:
        return ActivityType.QUERY
    if "merge" in key:
        return ActivityType.MERGE
    if "sim" in key:
        return ActivityType.SIMULATION_STEP
    if "validate" in key:
        return ActivityType.VALIDATION
    if "etl" in key:
        return ActivityType.ETL
    if "aggregate" in key:
        return ActivityType.AGGREGATION
    return ActivityType.VALIDATION
