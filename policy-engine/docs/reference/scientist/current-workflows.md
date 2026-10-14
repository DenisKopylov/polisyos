# Current Scientist Workflows and Evidence Handoffs

Owner: `@scientist-owners`
Source of truth: `src/polisyos/scientist/api.py`, `src/polisyos/scientist/orchestration/engine/**/*.py`,
  `src/polisyos/scientist/orchestration/workflows/**/*.py`,
  `src/polisyos/scientist/nodes/builtins/**/*.py`,
  `src/polisyos/scientist/evidence/claims/**/*.py`, `src/polisyos/scientist/validation/policy_grounding.py`,
  `src/polisyos/scientist/validation/__init__.py`, `src/polisyos/scientist/evidence/source_quality.py`,
  `src/polisyos/scientist/methods/research_dag/invalidation.py`,
  `src/polisyos/scientist/methods/research_dag/projections.py`,
  `src/polisyos/runtime/http/services/control/nl_pipeline.py`.
Source pin: bafca83bff9ff49eef1466bc491a8420b5cd1dbb
Evidence level: implementation and test sources were inspected at this pin; tests were not executed for
this docs-only update. The source-binding checker compares only the leading `Source of truth` paths;
test paths named in the body are not automatically scanned. This metadata does not prove prose truth or
complete claim coverage. The direct-reference policy-grounding source census was `recomputed` by this
documentation author with the command below: 628 Python files under
`policy-engine/src/polisyos/scientist`.

This page records observed runtime paths and their current boundaries. The inspected implementation is
not a demonstrated end-to-end policy-proof system: the request-to-Trinity producer is missing, the
builtin workflow does not consume the grounding matrix, and default Claim-owner currentness is not
established. A typed component or focused test does not establish a complete
producer/artifact/bridge/consumer/surface chain. It complements [the Scientist index](index.md), [the
workflow engine reference](workflows.md), and [the claim spine reference](claims.md), plus [Claim Ledger
lifecycle](claim-ledger.md), [Research DAG replay](research-dag-replay.md), [source quality
calibration](source-quality-calibration.md), and [Foundry compile and
execute](../foundry/compile-execute.md). The workflow reference remains the deeper DAG catalog; this page
focuses on state transitions, evidence handoffs, freshness boundaries, and integration status.

## Run routing and state machines

`run_experiment()` accepts the strict `ExperimentState` envelope, resolves a workflow, assembles the
execution context and node registry, and delegates to the workflow executor. The current selector priority
in `src/polisyos/scientist/orchestration/workflows/selection.py` is:

1. Matching explicit `workflow_id` values for `scientist_discovery`, `scientist_policy_design`, and
   `scientist_policy_verified`.
2. Discovery signals: a discovery profile or mode, or both discovery data and variable names.
3. Explicit `scientist_causal_full`, then automatic causal escalation for transport/context differences,
   external-evidence markers, cross-context reuse, enabled cross-graph evidence configuration, configured
   evidence sources, an expected cross-graph result, or a knowledge-bundle input.
4. Serious execution profiles (`research`, `governed`, or `production`) select `scientist_causal_full`.
5. Verified-answer mode/profile selects `scientist_policy_verified`.
6. Policy-design profile, boolean `policy_mode=true`, a truth-token string (`1`, `true`, `yes`, `on`), or
   request/design/research-intent signals select `scientist_policy_design`; otherwise routing falls back to
   `scientist_default`. A supplied boolean or string `policy_mode` is resolved directly, so any value other
   than boolean `true` or one of those truth tokens suppresses later signal inference. The
   `policy_design` execution profile is checked first.

An unrecognized explicit workflow id does not force a route. `scientist_default` also has no special
explicit-selector branch, so other qualifying inputs can route the run elsewhere. Every builtin spec
requires `run_id` and `inputs.registry_bundle_ref`; `scientist_default` and `scientist_causal_full`
additionally require `inputs.trinity_bundle_ref`. `scientist_policy_design` and `scientist_policy_verified`
do not require that input at bind validation, so explicit route selection does not itself validate their
downstream evidence requirements.

| Workflow | Runtime shape observed in the builtin spec |
| --- | --- |
| `scientist_default` | Baseline data/Foundry/simulation path, then legal, causal, distributional, welfare, uncertainty, governance, and decision-packet work. |
| `scientist_discovery` | Discovery blueprint runtime without the Foundry/governance execution path. |
| `scientist_causal_full` | Adds literature/graph reconciliation, causal readiness and transportability work before downstream governance. |
| `scientist_policy_verified` | Builds a policy request and legal/source packs, verifies and repairs source gaps, drafts options, then reaches a formalizer that checks for a caller-supplied Trinity-reference key before compile/simulation and report/packet work. The guard does not resolve or validate the referenced artifact. |
| `scientist_policy_design` | Adds the same request/source chain, hierarchical search, causal readiness and counterfactual gate, then simulation, translation, policy-output packaging, and a decision packet. |

These are separate from the iterative plan lifecycle.
`src/polisyos/scientist/orchestration/engine/iteration_state_machine.py` models `plan_created →
preflight_running → ready_to_run → executing → evaluating`, with explicit `preflight_failed`, `replanning`,
and terminal `approved`, `stopped_budget`, `stopped_no_delta`, and `stopped_guardrail` outcomes. A workflow
report status is not an iteration-state verdict.

Every builtin workflow spec sets `error_policy="continue"`. At node level, a failed prerequisite causes
dependent nodes to be skipped with an upstream-failure blocker; independent branches can continue. The
workflow report is `fail` if any node failed and otherwise `ok`; skipped nodes alone do not make it fail.
`run_experiment()` returns the final state and its workflow-report ref when node execution completes, so a
report-level `fail` is recorded in the result rather than converted into an exception. Setup/execution
exceptions can still propagate. Read `src/polisyos/scientist/orchestration/engine/executor.py`,
`src/polisyos/scientist/orchestration/engine/state.py`, and `src/polisyos/scientist/api.py` for these
distinct contracts. These are local execution outcomes, not policy or evidence authority: a node-level
`ok` means only that the node returned `ok` under its implementation, and a report-level `ok` means the
execution recorded no failed node. Neither establishes that a referenced artifact was resolved and bound,
that a claim is publishable, or that a current Claim head was issued. In particular, the formalizer's `ok`
is only the caller-ref key-presence guard described below; Claim readiness and Claim-owner currentness are
separate.

## Policy request, grounding, and packaging

The policy DAGs carry typed artifacts through a source chain rather than treating a drafted answer as
verified evidence:

1. `PlanPolicyRequestNode` creates the request frame; legal candidate/source pack nodes produce the source
   inputs.
2. `RunSourceVerificationNode` verifies the source pack and persists a report bound to the request frame and
   both source packs. `RunSourceGapReviewNode` consumes those refs, recovers gaps, and persists updated
   candidate/source packs and a new report.
3. `DraftPolicyOptionsNode` consumes the request frame and verification report and persists a typed option
   set. Its candidate/hypothesis distinction remains evidence status, not legal authority.
4. The specs in `src/polisyos/scientist/orchestration/workflows/policy_design.py` and
   `src/polisyos/scientist/orchestration/workflows/policy_verified.py` place `FormalizeVerifiedPolicyNode`
   after option drafting. At this source pin, the implementation in
   `src/polisyos/scientist/nodes/builtins/compile/formalize_verified_policy.py` is a guard for a
   caller-supplied `inputs.trinity_bundle_ref`: `execute` discards `ctx` and returns `ok` only when
   `INPUT_TRINITY_BUNDLE_REF` is a key in `state.inputs`; it does not resolve the reference or validate an
   artifact in CAS. If the key is absent it fails with `POLICY_VERIFIED_HARDCODED_FORMALIZER_STRANGLED`.
   It does not translate the drafted options into Trinity. Neither policy workflow lists the Trinity ref in
   `required_binds`, so a request can route successfully and fail at this later node; dependent
   search/compile/simulation nodes then skip. The
   docstring in `src/polisyos/scientist/orchestration/workflows/policy_verified.py` still describes
   formalization as occurring, but the node implementation is the observed runtime behavior.
5. `BuildPolicyOutputBundleNode` in
   `src/polisyos/scientist/nodes/builtins/decide/build_policy_output_bundle.py` is a downstream consumer,
   not a request-to-policy producer. In policy mode it requires a candidate or Trinity input and at least
   one evaluation vector, promotion result, or decision-readiness contract. It resolves available typed
   reports, applies the Phase 3 certificate gate, delegates packaging to `PolicyArtifactBuilder`, then runs
   Phase 5 artifact preflight and publication enforcement. A Phase 5 block returns a failing node outcome
   with validation evidence; otherwise the policy-design DAG makes the bundle an input to decision-packet
   construction. A bundle or decision-card projection is not itself proof of Claim-owner currentness.

### Source freshness and invalidation

`build_source_quality_report()` assesses the supplied source metadata when a caller builds the report. It
uses `page_age_days`, or `published_at`/`fetched_at`, against the TTL for the normalized claim family and
source class; an exceeded TTL is `stale`, while missing machine-readable age is `unknown`. A non-publishable
freshness, invalidation, or conflict state fails the report, while its composite score remains advisory. The
documented runtime consumer is the serious HTTP natural-language path in
`src/polisyos/runtime/http/services/control/nl_pipeline.py`; this does not establish that every builtin
Scientist DAG runs or consumes source-quality assessment. The report can surface a refresh or review need,
but it is not a scheduled fetch or an automatic Claim update. See
[Source Quality Calibration](source-quality-calibration.md) for TTL and decision-state details.

Source invalidation is a separate handoff. A caller-supplied `SourceInvalidationEvent` must name a
`source_ref` present in the Research DAG; propagation then identifies downstream nodes and dependent
claims. `stale`/`unavailable` map to `marked_stale`, while `withdrawn`/`contradicted` map to `invalidated`.
The invalidation helpers can construct typed lifecycle events, but the linked Research DAG reference
describes its replay/invalidation controls as shadow/read-only and Phase 2.6 as a later consumer of reports
for review and reissue triggers. The propagation helper itself processes a supplied event; it does not
fetch a replacement source, issue a Claim root, or advance a current Claim head. See [Research DAG
replay](research-dag-replay.md) and [Claim Ledger lifecycle](claim-ledger.md).

The grounding matrix has substantive claim-bound behavior in
`src/polisyos/scientist/validation/policy_grounding.py`: it checks claim-registry membership, required
grounding by claim family, evidence/analytics bindings, and major-claim support. The package facade at
`src/polisyos/scientist/validation/__init__.py` re-exports its report builder and normalizer. The focused
suite `tests/unit/scientist/validation/test_policy_grounding_matrix.py` includes content-level rejection
and warning cases. A complete direct-symbol scan of the 628 Python files under
`policy-engine/src/polisyos/scientist` finds implementation/internal normalization references and those
facade re-exports, but no direct reference in builtin workflow or node modules. This supports a bounded
statement: the matrix is implemented and has a focused test suite, while no direct-name built-in
Scientist workflow/node consumer was found in that source denominator. It does not establish absence of
indirect/dynamic calls, callers outside that tree, or non-Python consumers. For the inspected builtin
runtime, the capability is `implemented_but_not_orchestrated`; the matrix report also has
`surface_missing` from the builtin workflow/packet path because no inspected built-in consumer produces or
attaches it.

To reproduce the source census from the repository root:

```bash
cd policy-engine
python3 - <<'PY'
from pathlib import Path

root = Path("src/polisyos/scientist")
files = sorted(path for path in root.rglob("*.py") if path.is_file())
print(f"denominator: {len(files)} Python files under {root}")
for symbol in (
    "build_policy_grounding_matrix_report",
    "normalize_policy_grounding_matrix",
):
    print(f"{symbol}:")
    for path in files:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if symbol in line:
                print(f"{path}:{line_number}")
PY
```

At the source pin above, the denominator is 628; both names occur in
`src/polisyos/scientist/validation/policy_grounding.py` and as lazy facade exports in
`src/polisyos/scientist/validation/__init__.py`. The command reports direct textual references; it is not
a proof against dynamic lookup or indirect aliases.

The counterfactual gate in
`src/polisyos/scientist/nodes/builtins/causal/counterfactual_identification_gate.py` is on the policy-design
path before simulation. Its intended property is that every required counterfactual is identified before
simulation; it fails when selected result rows are not `identified`. The implementation turns on available
rows and an optional `params.required_counterfactual_query_ids` list. The query membership predicate is
`consumer_asserted`; completeness of the requested set is `not_established`. A missing readiness ref returns
`status="skipped"`, `blocked=false`. An empty result set also skips. With a non-empty required-query list,
the implementation filters to matching result rows but does not compare the matched IDs back to the full
requested set: if all requested IDs are absent it skips, while a partial match checks only the rows that
were found and can pass when those rows are identified. If the required-query list is empty, the gate checks
all rows in the bundle. Because skip cases return node outcome `ok`, the gate itself does not stop dependent
simulation; simulation can proceed if its other prerequisites succeed. A divergent `P38` case is a bundle
containing one identified result while the non-empty request names that result and another absent query: the
implementation can report `pass` even though not every requested query has an identified result. The test
source `tests/unit/scientist/nodes/builtins/causal/test_counterfactual_identification_gate.py` covers
identified and unidentified supplied rows and load/assertion failures, but does not pin missing-ref,
missing-query, or partial-match behavior. For those cases the correct current label is
`semantic_test_missing`; the gate is wired, but its boundary behavior is not shown to be a strict
fail-closed completeness gate.

## Research sidecar

`src/polisyos/scientist/orchestration/engine/executor.py` can project selected `scientist_policy_design`,
`scientist_policy_verified`, and `scientist_causal_full` executions to a persisted Research DAG sidecar and
place its ref in the final state's `artifacts_index`. The projection flag
`scientist.best_in_class.wave1.phase1_2.research_dag` defaults off; `require_research_dag_for_publication`
also defaults off. An enabled projection failure is degraded and does not itself fail the workflow report.
`tests/unit/scientist/methods/research_dag/test_workflow_integration.py` covers enabled persistence;
`tests/unit/scientist/methods/research_dag/test_projections.py` covers the default-off setting. This is a
wired optional sidecar, not an always-present publication prerequisite.

## Claim and evidence handshakes

`ClaimRecord` separates support (`unsupported`, `weakly_supported`, `supported`, `contested`, `refuted`,
`not_evaluable`), publishability (`draft`, `internal_only`, `review_required`, `publishable`, `blocked`),
and decision readiness. It carries evidence and counterevidence refs, uncertainty and provenance refs,
source attribution, reviewer refs, and blocked reasons. `assess_claim_readiness()` makes refutation or
explicit blockers `blocked`; counterevidence, weak/contested support, unsupported decision-bearing claims,
missing high-stakes evidence, and certain externally ready claims without attribution require review. A
publishable high-stakes claim must be supported, carry evidence, and have no unresolved counterevidence or
blocked reasons. Comparison option records separately carry raw and effective independent-support counts; a
raw tally is not the effective support count (`P14`). Read
`src/polisyos/scientist/evidence/claims/models.py` and `src/polisyos/scientist/evidence/claims/readiness.py`
for the exact rules.

LLM-produced content remains a candidate. The typed `ClaimSourceClass` includes LLM candidate/critic/drafter
classes, and `ClaimFamilyAssignment` requires any LLM-sourced assignment to use `context-only`.
`ClaimRecord` applies the same restriction when both decomposition source class and claim use are supplied.
Policy option drafting and source verification provide candidate options and source-bound evidence; neither
the model's prose nor a candidate artifact is a substitute for an admitted producer record. This is the
`P15` boundary, not an LLM authority grant.

The currentness handshake is a separate authority step. The workflow builder in
`src/polisyos/scientist/orchestration/workflows/builder.py` installs `build_default_claim_ledger_owner()`,
whose production composition is `UnappointedClaimLedgerOwner`. That owner can persist/project a candidate
ledger, but initial-root prepare/finalize and current-head resolution return typed `not_established`
non-receipts (`claim_root_issuance_not_established` / `claim_head_absent`). Thus a CAS blob or packet's
`claims_ref` may describe a candidate projection; it does not establish an owner-approved current Claim
head. `src/polisyos/scientist/evidence/README.md` states that the production appointment slot remains empty.
Claim currentness is therefore `not_established` in this default composition; the institutional owner
appointment is `absent/unallocated`, not an implicit success.

When configured, root issuance is a two-phase handshake: prepare the root basis, persist the decision
packet, then finalize the root/current-head pointer against that packet. The owner also resolves current
heads for downstream exports and independently reconciles claim dependency membership before epoch-driven
mutations. The append-only v2 lifecycle artifact records actor, time, reason, prior/next refs, and typed
actions such as stale, review-required, reissued, invalidated, superseded, and withdrawn; events stay
ordered and claims referenced by events remain visible. Supersession records the predecessor/successor
relation only. It does not issue the successor: the successor needs its own issuance authority before it
becomes current. See `src/polisyos/scientist/evidence/claims/head_index.py`,
`src/polisyos/scientist/evidence/claims/lifecycle.py`, and
`src/polisyos/scientist/evidence/claims/owner_events.py`.

The legacy claim sidecar is enabled by default, while fail-on-naked-claims defaults off. For selected
policy/causal workflows, a missing claim projection can therefore be reported as a warning rather than a
blocking failure unless the fail-on-naked flag is enabled. Claim Ledger v2 is a separate feature-flagged
lifecycle sidecar. These are distinct from the readiness status of individual claims and from owner
currentness. Relevant readers include `src/polisyos/scientist/evidence/claims/validators.py`,
`src/polisyos/scientist/evidence/claims/lifecycle.py`,
`src/polisyos/scientist/nodes/builtins/decide/decision_packet/enrichment.py`, and
`src/polisyos/scientist/evidence/claims/export.py`.

Decision-card and audience exports are projections.
`src/polisyos/scientist/orchestration/orchestrator/decision_card.py` turns a packet/export into a
presentation-friendly card; it does not execute a workflow or mutate the run. A projection can surface trust
summaries and limitations, but it cannot appoint the Claim owner or advance a head (`P05`).

## Observed gaps and failure consequences

| Boundary | Observed state at this pin | Lifecycle consequence |
| --- | --- | --- |
| Request/options → executable Trinity | `producer_missing` for the internal bridge; the formalizer checks for caller input but emits no Trinity artifact. | Request-only policy routes can fail at formalization; dependent search/compile/simulation skip and the workflow report records a failure. |
| Policy-grounding matrix → builtin workflow | `implemented_but_not_orchestrated` and `surface_missing` for the bounded builtin path. | Matrix semantics are available in a component and focused unit suite, but no inspected builtin consumer produces or attaches its report. |
| Claim-root authority in default runtime composition | `not_established`; production owner appointment is `absent/unallocated`. | Candidate ledger data and summaries may persist, while currentness, root issuance, and owner-resolved publication status remain unavailable. |
| Counterfactual gate denominator | `semantic_test_missing` for absent/empty/partial-match cases; completeness of requested query IDs is `not_established`. | An empty set can skip and a partial set can pass, so the gate does not demonstrate that every requested query was identified before simulation. |
| Research DAG | Implemented, persisted, and wired behind an off-by-default flag; publication requirement is also off by default. | Most runs need not carry a Research DAG ref; projection persistence failure is degraded, not a workflow failure. |
| Naked-claim closeout | `FAIL_ON_NAKED_CLAIMS_FLAG` defaults false. | Missing claims can remain a warning on selected workflows unless callers enable fail-closed behavior. |

The pattern pass for this reference is `P01`/`P02` (capability and orchestration reality), `P04`
(node/report/iteration status composition), `P05`/`P15` (projection and LLM authority boundaries), `P09`
(warning lifecycle), `P10`/`P37`/`P38` (semantic adequacy and gate predicates), `P12` (typed producer
handshakes), and `P14` (do not inflate raw evidence counts into independent support). The existing
failure/repair register remains the source for those patterns:
`docs/reference/policy-design-case-failure-patterns.md`.

## Evidence inspected, not executed

The following test sources were read as behavioral evidence; this documentation pass did not execute them:
`tests/unit/scientist/orchestration/workflows/test_workflow_specs.py`,
`tests/unit/scientist/orchestration/workflows/test_workflow_selection.py`,
`tests/unit/scientist/policy_design/test_policy_verified_workflow_guard.py`,
`tests/unit/scientist/policy_design/test_policy_verified_workflow_e2e.py`,
`tests/unit/scientist/nodes/builtins/causal/test_counterfactual_identification_gate.py`,
`tests/unit/scientist/methods/research_dag/test_workflow_integration.py`,
`tests/unit/scientist/methods/research_dag/test_projections.py`,
`tests/unit/scientist/validation/test_policy_grounding_matrix.py`,
`tests/unit/scientist/evidence/claims/test_readiness.py`,
`tests/unit/scientist/evidence/claims/test_lifecycle.py`, and
`tests/unit/scientist/evidence/claims/test_head_index.py`. Code inspection supports the behavior described
above; test execution status is **not run**.
