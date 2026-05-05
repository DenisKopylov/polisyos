# Scientist Builtin Nodes

Related explanation: [Governance Model](../../explanation/governance-model.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/nodes/__init__.py`, `src/polisyos/scientist/nodes/builtins/**`, `src/polisyos/scientist/engine/protocol.py`, `src/polisyos/scientist/nodes/builtins/state_keys.py`, `tests/unit/scientist/nodes/**`, and `tests/unit/scientist/causal/test_causal_evaluation_node.py`

> Owner lane: `L6 Scientist`  
> Type: Manual reference (not generated).  
> Source of truth: `src/polisyos/scientist/nodes/__init__.py`, `src/polisyos/scientist/nodes/builtins/**`, `src/polisyos/scientist/engine/protocol.py`, `src/polisyos/scientist/nodes/builtins/state_keys.py`, `tests/unit/scientist/nodes/**`, and `tests/unit/scientist/causal/test_causal_evaluation_node.py`.

`polisyos.scientist.nodes` exposes a single stable root export:
`builtin_nodes()`. Every concrete builtin node lives under
`polisyos.scientist.nodes.builtins.*` and is referenced from workflows by the
node component id declared in its `NodeSpec`.

## Node Contract

| Type            | Source                         | Contract                                                                                                           |
| --------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| `NodeSpec`      | `engine/protocol.py`           | Declares component metadata, `state_reads`, `state_writes`, and logical `produces` keys.                           |
| `NodeOutcome`   | `engine/protocol.py`           | Returns `status`, updated `ExperimentState`, emitted artifact refs/events, and an error only when `status="fail"`. |
| `NodeError`     | `engine/protocol.py`           | Typed machine-readable failure payload.                                                                            |
| `NodeEvent`     | `engine/protocol.py`           | Structured event stream for tracing and diagnostics.                                                               |
| `state_keys.py` | `nodes/builtins/state_keys.py` | Canonical input/artifact/report aliases used by builtin nodes and downstream decision surfaces.                    |

## Registry Snapshot

`builtin_nodes()` currently instantiates 44 builtin nodes across seven families.

| Family       | Current members                                                                                                                                                                                                                                                                                                                                                                                       | What they publish                                                                                                         |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `data`       | `BuildDataSnapshotNode`, `BindFoundryInputsNode`, `EnrichKnowledgeNode`                                                                                                                                                                                                                                                                                                                               | Data snapshot, bound inputs, knowledge enrichment artifacts.                                                              |
| `planning`   | `PlanPolicyRequestNode`, `BuildExecutionPlanNode`, `BuildMethodCatalogSnapshotNode`, `AssembleLegalCandidatePackNode`, `ExpandLegalSourcePackNode`, `RunSourceVerificationNode`, `RunSourceGapReviewNode`, `DraftPolicyOptionsNode`, `RunPreflightNode`, `ReadyToRunNode`, `CompileCrossGraphEvidenceNode`, `RunHierarchicalPolicySearchNode`, `RunEvaluatorNode`, `RunDiscoveryBlueprintRuntimeNode` | Execution-plan, verified-source, search, evaluator, and discovery artifacts.                                              |
| `compile`    | `LinkTrinityNode`, `FormalizeVerifiedPolicyNode`, `CompileFoundryNode`                                                                                                                                                                                                                                                                                                                                | Trinity link report, formalized policy input, compile/link/program-graph artifacts.                                       |
| `causal`     | `BuildLiteraturePriorNode`, `ReconcileCausalGraphNode`, `RunCausalReadinessNode`, `ResolveParametersNode`, `RunCausalQueriesNode`, `RunCausalEnsembleNode`, `RunABMConsistencyCheckNode`, `RunTransportabilityNode`, `RunCausalContractExecutionNode`, `CounterfactualIdentificationGateNode`                                                                                                         | Literature prior, reconciled graph, readiness, causal query/ensemble/ABM/transportability, and counterfactual-gate state. |
| `simulate`   | `RunSimulationNode`, `RunCausalEvaluationNode`, `RunDistributionalAnalysisNode`, `PropagateUncertaintyNode`                                                                                                                                                                                                                                                                                           | Simulation, causal-effect, distributional, and uncertainty artifacts.                                                     |
| `governance` | `DataPlaneGateNode`, `LegalCheckNode`, `RunNormativeArbitrationNode`, `RunGovernanceNode`                                                                                                                                                                                                                                                                                                             | Data-plane, legal, arbitration, and governance report artifacts.                                                          |
| `decide`     | `BuildVerifiedPolicyReportNode`, `RunPolicyBlueprintRuntimeNode`, `RunPolicyTranslationNode`, `RunTranslatorComplianceNode`, `BuildPolicyOutputBundleNode`, `BuildDecisionPacketNode`                                                                                                                                                                                                                 | Verified-policy report, blueprint/translation outputs, policy output bundle, and final decision packet.                   |

## Current High-Signal Node IDs

The workflow specs currently depend on these node ids for the key L6 surfaces:

| Capability                 | `node_id`                                                 |
| -------------------------- | --------------------------------------------------------- |
| Baseline simulation        | `scientist.node_run_simulation@1.0.1`                     |
| Causal evaluation          | `scientist.node_run_causal_evaluation@1.2.0`              |
| Causal readiness           | `scientist.node_run_causal_readiness@1.0.0`               |
| Counterfactual gate        | `scientist.node_counterfactual_identification_gate@1.0.0` |
| Hierarchical policy search | `scientist.node_run_hierarchical_policy_search@1.0.0`     |
| Governance runtime         | `scientist.node_run_governance@1.2.0`                     |
| Decision packet            | `scientist.node_build_decision_packet@1.5.0`              |

## What This Page Does Not Duplicate

This page does not restate every `state_reads`/`state_writes` list inline,
because the authoritative contract already lives in each node's `NodeSpec`.
When a node contract changes, update the node class first and then confirm the
workflow/reference impact with the tests below.

## Phase Evidence

| D1 phase | Node-facing evidence                                                                                                                |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Phase 0  | Retry, idempotency, budget, masking, and containment regressions documented through the Phase 0 gate.                               |
| Phase 1  | Branch-local state mutation, builder pinning, workflow reliability scenarios, and decision-packet publication rules.                |
| Phase 2  | Runtime-path benchmarks and the Phase 2 maintainability ratchet on selected hot paths.                                              |
| Phase 3  | `RunCausalEvaluationNode`, governance nodes, policy-output nodes, and decision packet surfacing of causal/accountability artifacts. |
| Phase 4  | Frontier/distributed behavior remains separately gated and is not implied by builtin node presence alone.                           |

## Validation

```bash
uv run pytest tests/unit/scientist/nodes -q
uv run pytest tests/unit/scientist/nodes/builtins -q
uv run pytest tests/unit/scientist/causal/test_causal_evaluation_node.py tests/unit/scientist/nodes/test_decision_packet_node_v3.py -q
```

## API Reference

::: polisyos.scientist.nodes

::: polisyos.scientist.nodes.builtins

::: polisyos.scientist.engine.protocol
