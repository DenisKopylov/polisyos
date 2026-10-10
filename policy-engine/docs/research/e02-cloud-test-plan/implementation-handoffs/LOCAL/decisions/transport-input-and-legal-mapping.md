# Transport input and legal-mapping decision packet

## Scope and disposition

This packet records a candidate source repair in the existing transportability owner. It does
not ratify legal-to-DAG target semantics, establish a legal rule, or claim that a transport result
is scientifically current. The exercised code has no joined external issuer/authority evidence
for the fixture or legal mapping.

The input finding is **P40 same P38 class, deeper**: explicit malformed values were normalized
into defaults or lower-precedence values. The transport input parser now rejects malformed
non-null values at the node boundary, instead of silently continuing to a report value, alias,
default solver, or arbitrary PAG policy. Malformed explicit privacy candidates, wrong-type path
inputs, and present empty/whitespace path strings also fail there across the four registry/legal/
SKG fields; actual `None` remains omission and configured-but-missing files retain their existing
degraded-source behavior. Existing finite range clamps remain, with their exact normalization
written to the persisted `TransportabilityResult.warnings`. This is a generic normalization change
across the consumed transport inputs, not a one-field special case.

The latest numeric finding is the same P40/P38 class, deeper at canonical input admission. The
`ExperimentState.params` contract admits `Decimal`, and Pydantic normalizes supplied numeric
thresholds to that representation; the previous shared finite-number helper rejected this valid
form. It now admits finite `Decimal` values for all its callers while continuing to reject bool,
non-finite Decimal values, and non-numeric objects. The PAG threshold and treatment-value paths are
both covered so the shared parser, not just one consumer, accepts the contract representation.

The legal-target finding is **P40 same P38 class, deeper**: graph membership was used as a proxy
for mapping intent. The old helper selected the first graph-resident endpoint even when the
mapping carried a named mechanism candidate. The current branch is a review-required projection
prototype: it emits a candidate only for selected field shapes, records typed reasons when it
cannot project a target, and does not silently choose a fallback endpoint. The shape rules are
not ratified legal semantics; ADR-0051 remains Proposed.

## Reconstructed input and consumer path

`RunTransportabilityNode.spec.state_reads` names source/target context, query treatment/outcome,
`policy_spec`, PAG identification policy/sample limit/threshold/seed, solver mode, degraded-mode
permission, privacy inputs, registry paths, and typed report/capability/ensemble/graph refs.
`RunTransportabilityNode.execute` loads the report and graph, derives the query, constructs the
resolution loop, persists the transport result, then links the updated report to that result.
Query treatment takes its candidate precedence from node params, then report method parameters,
then report metadata, then its existing literal default. Query outcome uses node params, report
method parameters, then its literal default. Conditional treatment value reads
`query_treatment_value`, `treatment_value`, `value`, then `dose`. Solver and PAG policy select
backend behavior; PAG sample count, threshold, and seed affect the probabilistic path.

The falsifying cases that motivated the repair were present in the maintained mirror: a malformed
high-priority treatment-value alias (`value="invalid"`) plus valid lower-priority `dose=3` had
returned `3.0`; an unsupported explicit solver (`fastest`) had returned `auto`; and unknown PAG
policy strings were accepted as policies. These now raise `InvalidTransportInput`, while all
declared `PAGIdentificationPolicy` enum members including `optimistic` remain admitted. At the node
boundary the malformed-input outcome is `ERROR_INVALID_STATE`. Oversized sample count and
out-of-range finite threshold are still clamped, but the result carries the exact values and
supported ranges in its warnings. The node-path regression inputs cover invalid solver, non-object
policy spec, unknown PAG policy, malformed context/query, privacy candidate, wrong-type and
empty/whitespace paths across all four path fields, and conditional treatment-value controls.
Those paths are preflighted by one path coercer before capability persistence or null-adapter
selection. `None` still selects the omission behavior; the existing fixture also exercises valid
dataset and SKG adapters. Explicit PAG seed values are restricted to the unsigned 32-bit range
consumed by `transport_check._sample_dag_candidates_from_pag` through
`numpy.random.RandomState(seed)`; tests admit both endpoints and reject out-of-range seeds before
backend dispatch.

The reviewed optional raw fields still use `None` as the existing omission/default convention.
Their type contract is not declared in a request schema, so this packet does not reinterpret every
nullable field as an invalid explicit value. A future request-schema decision should distinguish
absent, null, and malformed-present for the whole transport input record before changing that
compatibility behavior. The smallest input-side falsifier is a paired call with
`policy_spec={"dose": 3}` versus `policy_spec={"value": null, "dose": 3}`. The current helper
selects the lower alias in both cases; whether explicit null should block that fallback is
`not_established` until the transport request schema names presence/null semantics.

## Legal target semantics remain a G choice

The source model in `lex/legal_evaluation/transport_constraints.py` declares three mapping types,
`affected_edges`, optional `new_node_name`, and `requires_expert_review`. Proposed ADR-0051 describes
`effect_modifier` as changing an existing edge, `mechanism_node` as blocking/introducing a
mediating node, and `intervention_redef` as redefining the intervention. It does not define a
typed target-resolution rule. The current `LegalConstraintBridge.map_constraints_to_dag` emits
every graph edge for each candidate mapping and synthesizes a new-node name for mechanism
mappings. The consumer's `SNode` projection has only a target variable; it cannot add and connect
a mediating node or express intervention redefinition. Thus an absent named mechanism node could
mean either “new slot awaiting graph integration” or “stale/contradictory mapping”; these inputs
are not distinguishable from the current artifact fields.

The source change uses the following conservative *candidate projection*, not a new legal rule.
The implementation and tests do not make these field-shape choices normative:

- In this prototype, a mechanism name already in the graph can produce an SNode candidate;
  otherwise it produces no SNode and the reason that the name is absent from the current graph.
  Because the source fields do not say whether a missing name is a proposed graph addition or a
  stale target, this is an unresolved projection, not a finding that the rule or mapping is
  invalid.
- In this prototype, an effect modifier with one graph-resident edge and no named node produces an
  SNode candidate for that edge's destination. Other shapes remain unresolved. The producer
  currently copies *all* graph edges into each candidate mapping, so one edge may simply mean the
  current graph has one edge; this is not evidence that the legal producer selected it. The
  node-level SNode contract also cannot represent which edge's slope changes.
- An intervention redefinition remains unresolved because the current mapping/result contract has
  no field that binds it to the queried intervention variable.
- Existing `requires_expert_review=True` is carried into the result, including for a coherent
  target. Unresolved candidates also carry a reason through `TransportabilityResult`'s typed
  `requires_expert_review` and `expert_review_reasons` fields.

There are existing review projection points: decision-packet diagnostics derive
`human_review_needed` from transport `requires_expert_review` (`decision_packet/basis_sections.py`),
and validity emits a `REQUIRES_HUMAN_REVIEW` trigger (`decision_packet/validation.py`). When a
governance human-review gate request is being built, its reason selector can label an already
requested gate `expert_review_required_for_transportability`
(`governance_gate_requests.py::_human_review_reason`). This source does not establish that every
transport result automatically causes a gate request, or that a review decision is completed and
bound to the candidate mapping. The transport artifact itself can remain `IDENTIFIED`/`DIRECT`; no
legal authority or closure is claimed.

The synthetic fixture uses `jurisdiction="synthetic-fixture"` and
`legal_source="test-fixture:synthetic-non-issuer"`; its description explicitly says it is not a
real legal rule or issuer fact. No UA law or production legal register was read. The exact
candidate-shape controls are: a named mechanism target in the graph; one graph-resident edge in an
effect-modifier mapping; a mechanism name absent from the graph despite valid edge endpoints; an
effect-modifier carrying both an edge list and a mechanism name; missing/ambiguous edge data; and
an intervention redefinition with no represented target. They test current projection and review
reason behavior only. In particular, the “one-edge” control does not validate edge intent. The
direct loop control checks that unresolved mapping reasons reach the final typed review fields.

The remaining G choice is whether the legal bridge should (a) emit a typed proposed-node record
with graph-addition inputs, then wait for fresh graph integration; (b) bind a mechanism or edge
modifier to an exact existing graph identity; (c) bind an intervention redefinition to the typed
queried treatment; or (d) leave unsupported/ambiguous shapes unresolved pending expert review. The
choice needs the legal producer and transport consumer owners and a versioned mapping contract.
The smallest positive/negative discriminator is an issuer-backed mapping paired with a fresh
graph readback that distinguishes a proposed intermediary from a stale named target, plus an
edge-identity witness that distinguishes a deliberately selected edge from the bridge's current
all-edges list. The consumer must bind the review decision to that mapping and graph version before
any authority-bearing use. None of those source bindings is demonstrated here.

## Verification boundary

The earlier composed mirror run at
`LOCAL/raw/native-helper-mirrors/second-combined/stdout.txt` reported 50 passed and one failed. Its
sole failure passed an IR `TransportabilityResultRef` directly to the raw Core artifact store on
fresh readback, causing `artifact_lease` to receive a dictionary instead of an artifact ID. The
mirror now uses `ensure_ir_artifact_store` for both persistence and fresh read, and asserts the
typed result-ref kind and lineage equality. That adapter correction was not a product failure.

The later independent replay output at
`LOCAL/raw/transport-input-projection-review/stdout.txt` reported 13 passed and 12 failed before
the current corrections; the reviewer packet at
`LOCAL/reviews/transport-input-projection-independent.md` analyzed that run. Its single product
escape was present empty/whitespace paths collapsing
to omission; `_coerce_path` now rejects those values for all four declared path fields before
capability persistence or null-adapter selection. The other failures were test issues: assertions
for shared PAG defaults/ranges/seeds were nested in the parameterized test, `optimistic` was
incorrectly classified as unsupported despite being a `PAGIdentificationPolicy` member, a branch
test supplied `MagicMock` instead of a typed causal report, and one assertion used the old
mechanism-target diagnostic. The tests now move the shared checks to standalone tests, admit all
declared PAG enum members and both seed endpoints, use a typed report fixture, and expect the
current diagnostic. A root focused replay then collected 32 cases and reported 31 passed and one
failure: a valid `Decimal('1.5')` threshold emitted by the actual `ExperimentState` normalization
was rejected by `_read_finite_number`; the full output is
`LOCAL/raw/current-light-delta/stdout.txt@sha256:8388709038fd92d06546612fbd23360110891fbf8adf40b3c2b5ae705e6147a8`.
The shared helper now admits finite Decimal inputs and the dedicated test covers its threshold and
treatment-value callers plus bool, non-finite Decimal, and wrong-shape refusals. Only that focused
numeric test was replayed after this repair; the composed three-file suite remains pending. A
no-storage direct probe through `_resolve_transport_execution_inputs` did
exercise all 12 blank/whitespace string and `Path` combinations over the four fields, `None` on all
four fields, every PAG enum value, and both seed endpoints; all expected outcomes were observed.

The input source and three transport test files changed for this repair; no legal producer or
legal-target semantics were changed. Static verification is Ruff with the workspace-root config,
C901 at 12, `py_compile`, TOML parsing, and `git diff --check`. The focused selector
`test_finite_numeric_inputs_accept_decimal_contract_values_and_reject_invalids` passed after the
Decimal delta; the composed three-file suite has not been rerun after it.

Current source/test SHA-256:

| Path | SHA-256 |
| --- | --- |
| `src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py` | `c675be08d419f6b81dfe8ef76ffc669672ef453c5bac37ea49165ee5b39d7bb9` |
| `src/polisyos/scientist/nodes/builtins/causal/transport_resolution_inputs.py` | `1f69c926191df8d2884a1ad228dbf320d2e32649cbac1339aad0b0fa6c80bf4b` |
| `src/polisyos/scientist/nodes/builtins/causal/transport_resolution_results.py` | `af895ed6cd2b16e52873a76dea1d7efc4bb48bf577d6abadd04eb291218eb76b` |
| `tests/unit/scientist/nodes/builtins/causal/test_resolve_transport.py` | `4454789c6ed1515bfda699e3febe0b477c6a26ca983b957d977779c4326d4b4f` |
| `tests/unit/scientist/nodes/builtins/causal/test_transport_resolution_inputs.py` | `bb881cc5d2188f3aec415aa1cdcc0783bcb2a3687336dd2b990f49851a7dbea0` |
| `tests/unit/scientist/nodes/builtins/causal/test_transport_resolution_results.py` | `8f03ecfaa5b3fe51136c1548f38797403f421f7ea6251169258edef48dcb4a87` |
| `release-fragments/unreleased/2026-10-10-e02-transport-input-and-legal-mapping-review.toml` | `9ac0d25074b5b51ddea3a72167ab411508b22f5461c809cb0f74dbfa50b7fc6d` |

The independent review packet is
`LOCAL/reviews/transport-input-projection-independent.md@sha256:fead1b3c2fea1dc26f411c2afe350bab129a7f9a9c6905600dc965760fb93829`;
its pre-fix replay output is
`LOCAL/raw/transport-input-projection-review/stdout.txt@sha256:e014a6f6335512641f18cc74ddb0b56c70bff23b5e07b3317265b75b78f5f407`.
Latest Ruff check passed with the workspace-root config
`architecture/tooling/ruff/workspace_root.toml`; C901 at 12, `py_compile`, TOML parsing, and
`git diff --check` also passed. Source counts using non-empty, non-comment lines are 999 for
`resolve_transport.py`, 490 for `transport_resolution_inputs.py`, and 586 for
`transport_resolution_results.py`. The focused Decimal regression passed; the composed three-file
suite has not been rerun after that delta.
