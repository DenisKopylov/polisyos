"""CAS persistence helpers for ResearchDAGArtifact."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.methods.research_dag.models import ResearchDAGArtifact

RESEARCH_DAG_KIND = "scientist.research_dag"
RESEARCH_DAG_SCHEMA_NAME = "polisyos.scientist.methods.research_dag.ResearchDAGArtifact"
RESEARCH_DAG_SCHEMA_VERSION = "1.0"


def research_dag_inputs(
    *,
    node_artifact_refs: Iterable[ArtifactRef] = (),
    claim_ledger_ref: ArtifactRef | None = None,
) -> list[InputRef]:
    """Build lineage inputs for a persisted research DAG."""

    inputs: list[InputRef] = []
    seen: set[tuple[str, str]] = set()

    def add(ref: ArtifactRef, role: str) -> None:
        key = (str(ref.artifact_id), role)
        if key in seen:
            return
        seen.add(key)
        inputs.append(InputRef(artifact_id=ref.artifact_id, role=role))

    if claim_ledger_ref is not None:
        add(claim_ledger_ref, "claim_ledger")
    for index, ref in enumerate(node_artifact_refs):
        add(ref, f"research_node_artifact[{index}]")
    return inputs


def persist_research_dag(
    store: Any,
    dag: ResearchDAGArtifact,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a ResearchDAGArtifact as a CAS artifact."""

    refs: list[ArtifactRef] = []
    for node in dag.nodes:
        refs.extend(node.artifact_refs)
    manifest_inputs = (
        list(inputs)
        if inputs is not None
        else research_dag_inputs(
            node_artifact_refs=refs,
            claim_ledger_ref=dag.claim_ledger_ref,
        )
    )
    return store.put_json(
        dag,
        PutOptions(
            kind=RESEARCH_DAG_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=RESEARCH_DAG_SCHEMA_NAME,
                version=RESEARCH_DAG_SCHEMA_VERSION,
            ),
            inputs=manifest_inputs or None,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_research_dag(store: Any, ref: ArtifactRef) -> ResearchDAGArtifact:
    """Load a persisted research DAG from CAS."""

    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return ResearchDAGArtifact.model_validate(payload)


__all__ = [
    "RESEARCH_DAG_KIND",
    "RESEARCH_DAG_SCHEMA_NAME",
    "RESEARCH_DAG_SCHEMA_VERSION",
    "load_research_dag",
    "persist_research_dag",
    "research_dag_inputs",
]
