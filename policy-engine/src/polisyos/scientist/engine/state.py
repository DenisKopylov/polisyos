"""Typed state container exchanged between Scientist nodes and workflow runners.

`ExperimentState` is the primary boundary object for the engine DAG: builtin
nodes declare which keys they read/write, governance nodes materialize verdicts
into `params` and `reports_index`, and decision nodes persist the final packet
into `artifacts_index`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef

JsonPrimitive = str | int | bool | Decimal | None
JsonValue = JsonPrimitive | list[Any] | dict[str, Any]
JsonScalar = JsonPrimitive


class ExperimentState(BaseModel):
    """Carry workflow inputs, produced artifacts, reports, and mutable run params.

    Instances are copied between node executions and validated with
    `extra="forbid"`, so user-facing entrypoints must migrate unknown fields into
    `params`, `inputs`, `artifacts_index`, or `reports_index` instead of adding new
    top-level keys. Node implementations may mutate a copied state object only on
    keys declared by their `NodeSpec.state_writes`.

    Attributes:
        schema_version: Version of the state envelope contract.
        run_id: Stable run identifier shared with CAS manifests, checkpoints,
            and provenance records.
        inputs: Boundary artifact refs supplied by the caller or upstream nodes.
        artifacts_index: CAS refs for machine-readable artifacts produced during the DAG.
        reports_index: CAS refs for human/audit reports such as governance outputs.
        params: JSON-compatible orchestration state, planner hints, and governance flags.
        budgets: Named Decimal budgets consumed by execution and governance layers.
        last_checkpoint_ref: Latest replay checkpoint emitted by the executor.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.3", pattern=r"^\d+\.\d+$")
    run_id: str

    inputs: dict[str, ArtifactRef] = Field(default_factory=dict)
    artifacts_index: dict[str, ArtifactRef] = Field(default_factory=dict)
    reports_index: dict[str, ArtifactRef] = Field(default_factory=dict)

    params: dict[str, JsonValue] = Field(default_factory=dict)
    budgets: dict[str, Decimal] = Field(default_factory=dict)
    last_checkpoint_ref: ArtifactRef | None = None

    observational_data_ref: ArtifactRef | None = None
    execution_plan_ref: ArtifactRef | None = None
    method_catalog_snapshot_ref: ArtifactRef | None = None
    capability_manifest_ref: ArtifactRef | None = None
    causal_capability_contract_ref: ArtifactRef | None = None
    preflight_report_ref: ArtifactRef | None = None
    evaluator_report_ref: ArtifactRef | None = None
    iteration_state_ref: ArtifactRef | None = None
    reproducibility_manifest_ref: ArtifactRef | None = None
    control_job_id: str | None = None
    execution_profile: str | None = None
    causal_method_fqn: str | None = None
    causal_method_params: dict[str, JsonValue] = Field(default_factory=dict)
    critic_knowledge_base_ref: ArtifactRef | None = None
    constitution_hash: str | None = Field(default=None, min_length=64, max_length=64)
    policy_request_ref: ArtifactRef | None = None
    legal_candidate_pack_ref: ArtifactRef | None = None
    legal_source_pack_ref: ArtifactRef | None = None
    source_verification_report_ref: ArtifactRef | None = None
    policy_option_set_ref: ArtifactRef | None = None
    verified_policy_report_ref: ArtifactRef | None = None
    policy_output_bundle_ref: ArtifactRef | None = None
    policy_brief_ref: ArtifactRef | None = None
    champion_policy_dossier_ref: ArtifactRef | None = None
    memory_index_ref: ArtifactRef | None = None
