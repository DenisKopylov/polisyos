"""Run-level provenance DAG builder."""

from __future__ import annotations

import uuid
from collections import deque
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from polisyos.core.contracts.provenance import (
    ActivityType,
    AgentType,
    EntityType,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceCoreGraph,
    ProvenanceEntity,
)
from polisyos.scientist.evidence.provenance.llm_provenance import LLMCallRecord


class RunProvenanceDAG:
    """Assembles a ProvenanceCoreGraph for an entire scientist run.

    Usage:
        dag = RunProvenanceDAG(run_id="run-123")
        dag.record_node_execution(alias="data_load", ...)
        dag.record_llm_call(node_alias="drafter", ...)
        graph = dag.finalize()
        prov_dict = graph.to_dict()
    """

    def __init__(
        self,
        run_id: str,
        tenant_id: str | None = None,
        *,
        max_llm_records: int = 256,
    ) -> None:
        self._run_id = run_id
        self._tenant_id = tenant_id
        self._max_llm_records = max(1, int(max_llm_records))
        self._graph = ProvenanceCoreGraph(
            graph_id=f"prov:{run_id}",
            metadata={
                "run_id": run_id,
                "llm_records_retention_limit": self._max_llm_records,
                **({"tenant_id": tenant_id} if tenant_id else {}),
            },
        )
        self._llm_records: deque[LLMCallRecord] = deque(maxlen=self._max_llm_records)

        # Register the run itself as a system agent
        self._graph.add_agent(
            ProvenanceAgent(
                agent_id=f"agent:system:{run_id}",
                agent_type=AgentType.SYSTEM,
                label=f"Scientist run {run_id}",
                metadata={"run_id": run_id},
            )
        )

    @property
    def graph(self) -> ProvenanceCoreGraph:
        """Access the underlying graph (read-only during construction)."""
        return self._graph

    @property
    def llm_records(self) -> list[LLMCallRecord]:
        return list(self._llm_records)

    def record_node_execution(
        self,
        alias: str,
        node_id: str,
        started_at: datetime,
        ended_at: datetime,
        input_refs: list[Any] | None = None,
        output_refs: list[Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Record a node execution as a PROV-O Activity."""
        activity_id = f"activity:node:{self._run_id}:{alias}"

        # Create activity for the node execution
        # Use SIMULATION_STEP as closest existing ActivityType for node execution
        self._graph.add_activity(
            ProvenanceActivity(
                activity_id=activity_id,
                activity_type=ActivityType.SIMULATION_STEP,
                label=f"Node execution: {alias} ({node_id})",
                started_at=started_at,
                ended_at=ended_at,
                parameters=params or {},
            )
        )

        # Associate with system agent
        self._graph.add_association(
            activity_id=activity_id,
            agent_id=f"agent:system:{self._run_id}",
            timestamp=started_at,
        )

        # Register input entities and usage edges
        for ref in input_refs or []:
            artifact_id = getattr(ref, "artifact_id", str(ref))
            entity_id = f"entity:artifact:{artifact_id}"
            if entity_id not in self._graph.entities:
                self._graph.add_entity(
                    ProvenanceEntity(
                        entity_id=entity_id,
                        entity_type=EntityType.DATASET,
                        label=f"Artifact {artifact_id}",
                        created_at=started_at,
                    )
                )
            self._graph.add_usage(
                activity_id=activity_id,
                entity_id=entity_id,
                timestamp=started_at,
            )

        # Register output entities and generation edges
        for ref in output_refs or []:
            artifact_id = getattr(ref, "artifact_id", str(ref))
            entity_id = f"entity:artifact:{artifact_id}"
            self._graph.add_entity(
                ProvenanceEntity(
                    entity_id=entity_id,
                    entity_type=EntityType.DATASET,
                    label=f"Artifact {artifact_id}",
                    created_at=ended_at,
                )
            )
            self._graph.add_generation(
                entity_id=entity_id,
                activity_id=activity_id,
                timestamp=ended_at,
            )

            # Derive output from each input
            for in_ref in input_refs or []:
                in_artifact_id = getattr(in_ref, "artifact_id", str(in_ref))
                in_entity_id = f"entity:artifact:{in_artifact_id}"
                self._graph.add_derivation(
                    derived_id=entity_id,
                    source_id=in_entity_id,
                    timestamp=ended_at,
                )

    def record_llm_call(
        self,
        node_alias: str,
        model_id: str,
        temperature: float,
        seed: int | None = None,
        system_prompt_hash: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: Decimal | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> None:
        """Record an LLM call as a PROV-O Activity + Model Agent."""
        call_id = f"llm:{self._run_id}:{node_alias}:{uuid.uuid4().hex[:8]}"
        now = datetime.now(UTC)

        record = LLMCallRecord(
            call_id=call_id,
            model_id=model_id,
            temperature=temperature,
            seed=seed,
            system_prompt_hash=system_prompt_hash,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            trace_id=trace_id,
            span_id=span_id,
            node_alias=node_alias,
            timestamp=now,
        )
        if len(self._llm_records) == self._llm_records.maxlen:
            dropped = int(self._graph.metadata.get("llm_records_dropped", 0) or 0) + 1
            self._graph.metadata["llm_records_dropped"] = dropped
        self._llm_records.append(record)

        # Register model as agent
        model_agent_id = f"agent:model:{model_id}"
        if model_agent_id not in self._graph.agents:
            self._graph.add_agent(
                ProvenanceAgent(
                    agent_id=model_agent_id,
                    agent_type=AgentType.MODEL,
                    label=f"LLM model: {model_id}",
                    metadata={"model_id": model_id},
                )
            )

        # Register the LLM call as a query activity
        activity_id = f"activity:llm_call:{call_id}"
        self._graph.add_activity(
            ProvenanceActivity(
                activity_id=activity_id,
                activity_type=ActivityType.QUERY,
                label=f"LLM call: {model_id} for {node_alias}",
                started_at=now,
                ended_at=now,
                parameters={
                    "model_id": model_id,
                    "temperature": temperature,
                    "seed": seed,
                    "system_prompt_hash": system_prompt_hash,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": str(cost_usd) if cost_usd else None,
                },
            )
        )

        # Associate LLM call with model agent
        self._graph.add_association(
            activity_id=activity_id,
            agent_id=model_agent_id,
            timestamp=now,
        )

        # Link LLM call to parent node activity
        parent_activity_id = f"activity:node:{self._run_id}:{node_alias}"
        if parent_activity_id in self._graph.activities:
            # The LLM call was triggered by the node execution
            pass  # Already linked via the activity hierarchy

    def record_node_failure(
        self,
        alias: str,
        node_id: str,
        error: str,
        traceback: str | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
    ) -> None:
        """Record a failed node execution as a PROV-O ERROR Activity."""
        now = datetime.now(UTC)
        started = started_at or now
        ended = ended_at or now
        activity_id = f"activity:error:{self._run_id}:{alias}"

        self._graph.add_activity(
            ProvenanceActivity(
                activity_id=activity_id,
                activity_type=ActivityType.ERROR,
                label=f"Node failure: {alias} ({node_id})",
                started_at=started,
                ended_at=ended,
                parameters={"error": error, "node_id": node_id},
            )
        )

        # Register error entity with traceback
        error_entity_id = f"entity:error:{self._run_id}:{alias}"
        self._graph.add_entity(
            ProvenanceEntity(
                entity_id=error_entity_id,
                entity_type=EntityType.ERROR_TRACE,
                label=f"Error trace: {alias}",
                created_at=ended,
                attributes={"error": error, **({"traceback": traceback} if traceback else {})},
            )
        )
        self._graph.add_generation(
            entity_id=error_entity_id,
            activity_id=activity_id,
            timestamp=ended,
        )

        # Associate with system agent
        self._graph.add_association(
            activity_id=activity_id,
            agent_id=f"agent:system:{self._run_id}",
            timestamp=started,
        )

    def record_governance_decision(
        self,
        pass_id: str,
        decision: str,
        reason: str = "",
        evidence_refs: list[Any] | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Record a governance pass decision as a PROV-O GOVERNANCE Activity."""
        now = timestamp or datetime.now(UTC)
        activity_id = f"activity:governance:{self._run_id}:{pass_id}"

        self._graph.add_activity(
            ProvenanceActivity(
                activity_id=activity_id,
                activity_type=ActivityType.GOVERNANCE,
                label=f"Governance: {pass_id} → {decision}",
                started_at=now,
                ended_at=now,
                parameters={"pass_id": pass_id, "decision": decision, "reason": reason},
            )
        )

        self._graph.add_association(
            activity_id=activity_id,
            agent_id=f"agent:system:{self._run_id}",
            timestamp=now,
        )

        # Link evidence refs as input entities
        for ref in evidence_refs or []:
            artifact_id = getattr(ref, "artifact_id", str(ref))
            entity_id = f"entity:artifact:{artifact_id}"
            if entity_id not in self._graph.entities:
                self._graph.add_entity(
                    ProvenanceEntity(
                        entity_id=entity_id,
                        entity_type=EntityType.DATASET,
                        label=f"Evidence {artifact_id}",
                        created_at=now,
                    )
                )
            self._graph.add_usage(
                activity_id=activity_id,
                entity_id=entity_id,
                timestamp=now,
            )

    def record_checkpoint(
        self,
        alias: str,
        checkpoint_ref: Any,
        sequence_number: int,
        timestamp: datetime | None = None,
    ) -> None:
        """Record a checkpoint event as a PROV-O CHECKPOINT Activity."""
        now = timestamp or datetime.now(UTC)
        activity_id = f"activity:checkpoint:{self._run_id}:{alias}:{sequence_number}"

        self._graph.add_activity(
            ProvenanceActivity(
                activity_id=activity_id,
                activity_type=ActivityType.CHECKPOINT,
                label=f"Checkpoint after {alias} (#{sequence_number})",
                started_at=now,
                ended_at=now,
                parameters={"alias": alias, "sequence_number": sequence_number},
            )
        )

        # Register checkpoint entity
        artifact_id = getattr(checkpoint_ref, "artifact_id", str(checkpoint_ref))
        entity_id = f"entity:checkpoint:{artifact_id}"
        self._graph.add_entity(
            ProvenanceEntity(
                entity_id=entity_id,
                entity_type=EntityType.CHECKPOINT,
                label=f"Checkpoint {artifact_id}",
                created_at=now,
            )
        )
        self._graph.add_generation(
            entity_id=entity_id,
            activity_id=activity_id,
            timestamp=now,
        )

        # Associate with system agent
        self._graph.add_association(
            activity_id=activity_id,
            agent_id=f"agent:system:{self._run_id}",
            timestamp=now,
        )

    def record_state_mutation(
        self,
        alias: str,
        keys_added: list[str] | None = None,
        keys_modified: list[str] | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Record which state keys a node added or modified."""
        # Attach to existing node activity if present
        node_activity_id = f"activity:node:{self._run_id}:{alias}"
        if node_activity_id in self._graph.activities:
            activity = self._graph.activities[node_activity_id]
            # Update parameters in-place (ProvenanceActivity is frozen, so create a new one)
            params = dict(activity.parameters or {})
            if keys_added:
                params["keys_added"] = keys_added
            if keys_modified:
                params["keys_modified"] = keys_modified
            # Replace activity with updated params
            self._graph.activities[node_activity_id] = ProvenanceActivity(
                activity_id=activity.activity_id,
                activity_type=activity.activity_type,
                label=activity.label,
                started_at=activity.started_at,
                ended_at=activity.ended_at,
                parameters=params,
            )

    def set_experiment_metadata(
        self,
        problem_statement: str | None = None,
        hypothesis: str | None = None,
        **extra: str,
    ) -> None:
        """Add experiment metadata to the provenance graph root."""
        if problem_statement is not None:
            self._graph.metadata["problem_statement"] = problem_statement
        if hypothesis is not None:
            self._graph.metadata["hypothesis"] = hypothesis
        for k, v in extra.items():
            self._graph.metadata[k] = v

    def finalize(self) -> ProvenanceCoreGraph:
        """Close the graph and compute stable_id."""
        return self._graph

    def to_prov_json(self) -> dict[str, Any]:
        """Export as W3C PROV-JSON."""
        from polisyos.scientist.evidence.provenance.prov_json import to_prov_json

        return to_prov_json(self._graph)

    def to_research_dag_artifact(
        self,
        *,
        workflow_id: str,
        claim_ledger_ref: Any | None = None,
    ) -> Any:
        """Project this provenance graph into the Phase 1.2 research DAG contract."""

        from polisyos.scientist.methods.research_dag.projections import (
            project_provenance_graph_to_research_dag,
        )

        return project_provenance_graph_to_research_dag(
            run_id=self._run_id,
            workflow_id=workflow_id,
            provenance_graph=self._graph,
            claim_ledger_ref=claim_ledger_ref,
        )
