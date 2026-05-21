---
title: PolicyOS Evidence Spine Connectivity Remediation Plan
status: active
owner: team-runtime-quality
created: 2026-05-20
stability: draft
related:
  - ../../backlog/cloud-wave11-root-cause-diagnostic-backlog.md
  - ./POLICYOS_BEST_IN_CLASS_EVIDENCE_BINDING_AND_SCENARIO_AUTHORITY_PLAN.md
  - ../../system-design-decisions/policy-design-best-in-class-operating-model.md
  - ../../system-design-decisions/policy-design-case-decision-log.md
  - ../../../tools/ops_runners/runtime/run_canary_matrix.py
  - ../../../tools/ops_runners/runtime/canary_evidence.py
  - ../../../tools/quality/testing/local_prod_debug_probe.py
  - ../../../tools/quality/validation/inspect_evidence_bundles.py
scope:
  - runtime-quality
  - evidence-spine
  - production-data
  - fabric
  - lex
  - foundry
  - scientist
  - policy-design-case
  - authority
  - cloud-production-debug
---

# PolicyOS Evidence Spine Connectivity Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the root cause behind the 2026-05-20 cloud production-debug failures by making PolicyOS preserve one runtime-owned evidence spine from scenario contract through data, legal, method, claim, semantic, Policy Design Case, scorecard, closeout, and export surfaces.

**Architecture:** Treat `scenario_evidence_contract` as a propagated runtime carrier, not request-local metadata. Every serious producer must consume requirement ids, emit selected/rejected/blocked bindings, own its closure status, and mint its own authority envelope; closeout must verify the exact deployed producer/reader/authority combination before any API, dashboard, or public projection can rely on it.

**Tech Stack:** Python runtime quality modules, FastAPI runtime pipeline, Lex normpack, Fabric source-selection audit, Foundry method-quality validation, Scientist policy grounding and decision artifact compilers, CAS evidence bundles, Postgres-backed control-plane runs, pytest quality gates, local prod-debug probe, GCP cloud live lane, MkDocs docs gates.

---

## Why This Plan Exists

The final cloud diagnostics show a consistent connectivity failure:

- the scenario contract exists in request and bundle command;
- individual producers sometimes see it internally;
- emitted reports then lose the contract id, requirement ids, or per-claim
  selected/rejected/blocker bindings;
- downstream readers correctly fail, but some producer artifacts still say
  `pass`;
- some authority envelopes are present but semantically belong to another
  report kind;
- provider/model and prompt-tool signals are confounded by upstream evidence
  closure failures.

The fix is not to relax scorecards. The fix is to make the evidence spine the
runtime architecture.

## External Design Principles Applied

These sources shape the remediation approach:

| Source | Principle used in this plan |
| --- | --- |
| [OpenTelemetry context propagation](https://opentelemetry.io/docs/concepts/context-propagation/) | Context must cross process and service boundaries as a first-class carrier. PolicyOS uses this for `scenario_evidence_contract_id`, `requirement_ids`, and causal refs. |
| [OpenTelemetry messaging spans](https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans/) | Async producer/consumer boundaries require explicit creation context or span-link-like refs. PolicyOS uses this for NL job progress, workflow state, CAS bundle assembly, replay, and inspection. |
| [W3C Trace Context](https://www.w3.org/TR/trace-context/) | Trace carriers need stable ids and versioned propagation semantics. PolicyOS uses this pattern for evidence-spine carrier versioning. |
| [Pact can-i-deploy](https://docs.pact.io/pact_broker/can_i_deploy) | Deployed compatibility should be a versioned matrix, not assumed from isolated tests. PolicyOS adds `can-i-closeout`. |
| [OpenLineage core specification](https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md) | Separate Job, Run, Dataset, and Facets. PolicyOS separates static production-data metadata from run-level input/output and claim-bound evidence facts. |
| [OpenLineage data quality assertions](https://openlineage.io/docs/next/spec/facets/dataset-facets/data_quality_assertions/) | Data quality assertions need target dataset/column refs. PolicyOS requires source-family, dictionary, schema, freshness, missingness, outlier, lineage, and construct-validity facets. |
| [Google SRE effective troubleshooting](https://sre.google/sre-book/effective-troubleshooting/) | Diagnose component boundaries and data flow, then fix the first broken boundary. PolicyOS adds boundary probes for each serious producer. |
| [Dapper distributed tracing](https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/) | Large systems need low-friction causal tracing across services. PolicyOS adds an evidence-spine propagation graph to every serious live bundle. |
| [OpenTelemetry baggage security considerations](https://opentelemetry.io/docs/concepts/signals/baggage/) | Propagated context can leak to unintended downstream resources and lacks built-in integrity checks. PolicyOS therefore propagates only opaque refs, hashes, schema versions, and typed ids; never raw claims, prompts, DSNs, API keys, personal data, or legal text. |

## Root Cause Model

The deepest root cause is:

> The live producer path does not preserve one authoritative evidence spine
> across subsystem boundaries.

The recurring failure modes are:

- context is created but not propagated as a required runtime carrier;
- scenario obligations are not converted into producer-owned
  selected/rejected/blocked bindings;
- global evidence pools are copied forward instead of claim-bound anchors;
- invalid candidates remain in `selected` state after validation failure;
- producer status is weaker than downstream reader closure;
- authority envelope is present but attached to the wrong report kind;
- no closeout compatibility matrix verifies the deployed code/schema/reader
  combination;
- secondary provider, prompt-tool, and control-plane signals are interpreted
  before upstream evidence closure is isolated.

## Target Connectivity Invariant

Every serious live lane must satisfy this invariant:

1. `scenario_evidence_contract` is created once and propagated as a runtime
   carrier.
2. Every producer consumes explicit `requirement_id` values and emits selected,
   rejected, or blocked bindings for its slice.
3. Every major claim is compiled from producer-owned data, legal, method,
   argument, warrant, rebuttal/counter-evidence, limitation, and deficit refs.
4. Producer top-level status matches the strictest closure status known by its
   own reader contract.
5. Authority envelopes are minted by the report owner and match report kind,
   schema, phase, and validation semantics.
6. Closeout verifies the deployed combination of scenario contract, producer
   report schema, reader gate, authority profile, and code revision.

## New Runtime Contracts

### Evidence Spine Carrier

Create a small runtime carrier that can be embedded in producer reports, CAS
manifests, job progress, replay, inspection, and readiness.

```python
@dataclass(frozen=True)
class EvidenceSpineCarrier:
    schema_version: str
    spine_id: str
    trace_id: str
    parent_spine_ref: str | None
    scenario_evidence_contract_id: str
    scenario_contract_version: str
    requirement_ids: tuple[str, ...]
    producer_component: str
    producer_report_schema: str
    reader_contract: str
    authority_profile: str
    code_revision: str | None
    carrier_classification: Literal["public_ref", "internal_ref"]
    redaction_policy: str
    input_refs: tuple[str, ...]
    output_refs: tuple[str, ...]
```

### Producer Binding Result

Every serious producer emits this shape for each requirement it consumes.

```python
@dataclass(frozen=True)
class EvidenceRequirementBinding:
    requirement_id: str
    domain: Literal["data", "legal", "method", "claim", "semantic", "case"]
    status: Literal["satisfied", "blocked", "failed", "out_of_scope"]
    selected_refs: tuple[str, ...]
    rejected_refs: tuple[str, ...]
    blocker_code: str | None
    missing_facets: tuple[str, ...]
    limitation_refs: tuple[str, ...]
    authority_envelope_ref: str | None
```

### Closeout Compatibility Record

Closeout is allowed only if this record is present and passing.

```python
@dataclass(frozen=True)
class CanICloseoutRecord:
    scenario_contract_id: str
    scenario_contract_version: str
    producer_report_schemas: tuple[str, ...]
    reader_gate_versions: tuple[str, ...]
    authority_profile_version: str
    code_revision: str
    verification_status: Literal["pass", "fail", "blocked"]
    verification_refs: tuple[str, ...]
    incompatible_pairs: tuple[dict[str, str], ...]
```

## Carrier Security And Integrity Rules

The evidence spine carrier is deliberately not a free-form baggage channel.
It must obey these rules:

- Only opaque ids, CAS refs, schema names, schema versions, owner ids, and
  requirement ids may be propagated.
- Raw legal text, prompt text, user text, personal data, API keys, DSNs,
  credentials, and provider responses are forbidden in the carrier.
- Every carrier must have a payload hash or output ref that lets readers fetch
  the authoritative artifact from CAS when they are authorized to inspect it.
- Every cross-boundary carrier must be signed or integrity-checked by a
  runtime-owned authority envelope before it can be used for closeout.
- Public, dashboard, and API projections may expose only redacted carrier
  summaries and must not expose internal refs unless the projection policy
  explicitly allows them.

Add a redaction/integrity test for every new carrier-producing module. A test
must fail if a carrier contains a value that looks like a DSN, API key, bearer
token, raw prompt, raw recommendation body, or legal corpus excerpt.

## Coverage Review Matrix

This review maps the final diagnostic patterns to plan waves. A row is complete
only when the listed waves have regression tests and closeout gates.

| Diagnostic pattern | Required waves | Review status |
| --- | --- | --- |
| Context exists but becomes local metadata | Waves 0, 1, 1A, 10 | Covered after adding carrier safety and async handoff ledger. |
| Data availability confused with scenario admissibility | Waves 2, 3, 12 | Covered; must include real curated contract packaging, not only test fixtures. |
| Global evidence pools treated as claim anchors | Waves 4, 6, 7 | Covered; claim registry is the key boundary. |
| Invalid candidates remain selected | Waves 3, 5, 7 | Covered for Fabric and Foundry; Lex rejected norms handled in Wave 4. |
| Producers say `pass` when readers know closure failed | Waves 7, 8, 9, 10 | Covered; producer-side closure is mandatory. |
| Authority envelopes are borrowed across report kinds | Waves 9, 10 | Covered; no-borrowed-envelope must be closeout-blocking. |
| Deployed combination compatibility is not verified | Wave 10 | Covered; `git_sha=None` must fail serious cloud closeout. |
| Provider, prompt-tool, and control-plane signals are confounded | Wave 11 | Covered as secondary signal isolation. |
| Data Forge snapshot binding missing | Waves 2, 8A, 12 | Added in Wave 8A because it is part of the upstream source-to-case spine. |
| Scholar academic evidence missing | Waves 6, 8A, 12 | Added in Wave 8A so research evidence is not a silent PDC gap. |
| Concept and jurisdiction spine blockers | Waves 1, 8A, 10 | Added in Wave 8A and compatibility gate. |
| Legacy migration redaction gap | Waves 1A, 9, 10 | Added carrier redaction and authority checks so migration artifacts cannot leak or mint authority. |

## Files And Responsibilities

| File | Responsibility |
| --- | --- |
| `src/polisyos/runtime/quality/evidence_spine.py` | Define carrier, propagation graph, binding records, and validation helpers. |
| `tools/quality/validation/check_evidence_spine_connectivity.py` | Validate a bundle for dropped contract ids, missing requirement ids, broken parent/input/output refs, and producer/reader status divergence. |
| `src/polisyos/runtime/quality/closeout_compatibility.py` | Build and validate `can-i-closeout` records. |
| `tools/quality/validation/check_can_i_closeout.py` | CLI gate for deployed compatibility matrix. |
| `src/polisyos/runtime/http/services/control/nl_pipeline.py` | Propagate spine carrier through live NL producers and stop forcing profile-only `pass`. |
| `tools/ops_runners/runtime/canary_evidence.py` | Preserve spine graph, own authority envelopes, closeout compatibility, and no-borrowed-envelope checks in bundles. |
| `src/polisyos/runtime/quality/production_data_contract_index.py` | Enforce scenario-admissible source contracts and OpenLineage-like facets. |
| `src/polisyos/fabric/catalog/source_selection_audit.py` | Emit selected/rejected/blocked source contract bindings and fail broad bundle substitutes. |
| `src/polisyos/lex/normpack/applicability_report.py` | Preserve legal requirements and emit per-recommendation selected/rejected norm anchors. |
| `src/polisyos/foundry/validation/method_quality.py` | Reconcile selected/rejected method state with scenario method obligations. |
| `src/polisyos/scientist/validation/policy_grounding.py` | Consume claim registry and fail major claims without claim-bound evidence refs. |
| `src/polisyos/runtime/quality/claim_registry.py` | Create runtime-owned claim registry from Fabric, Lex, Foundry, and Scientist outputs. |
| `src/polisyos/runtime/quality/semantic_binding.py` | Run producer-side closure evaluation and write `runtime_report_status`. |
| `src/polisyos/runtime/quality/policy_design_case.py` | Emit record-family case from runtime evidence, not profile-only pass. |
| `src/polisyos/runtime/quality/authority.py` | Classify missing, spoofed, borrowed, packaging-only, and runtime-owned domain failures. |
| `tools/quality/testing/local_prod_debug_probe.py` | Add quick evidence-spine and can-i-closeout checks for local/cloud debug loops. |
| `src/polisyos/runtime/quality/evidence_spine_handoff.py` | Record async handoffs with parent/input/output refs, batch membership, and carrier redaction status. |
| `tools/quality/validation/check_evidence_spine_handoffs.py` | Validate NL job, control-plane, workflow, CAS, replay, inspection, readiness, and export handoffs. |
| `src/polisyos/runtime/quality/scholar_academic_evidence.py` | Emit or block Scholar research evidence in the same producer-owned spine as data/legal/method records. |

## Wave 0 - Freeze The Connectivity Regression

**Purpose:** make the cloud connectivity failure impossible to hide while the
repair work proceeds.

**Files:**

- Create: `tests/fixtures/production_quality/cloud_debug_20260520/evidence_spine_connectivity_fixture.json`
- Create: `tests/repo_quality/tools/test_evidence_spine_connectivity_regression.py`
- Modify: `docs/backlog/cloud-wave11-root-cause-diagnostic-backlog.md`

**Steps:**

- [ ] Create the compact fixture with these exact facts:
  - request scenario contract id:
    `scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1`;
  - request requirement count: `18`;
  - Fabric top-level scenario id: `null`;
  - Fabric nested scenario id:
    `scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1`;
  - Lex top-level legal requirement count: `0`;
  - Lex query-normalization legal requirement count: `4`;
  - curated contract ids:
    `us.macro.gdp_nominal`, `us.macro.unemployment_rate`,
    `agent.income.salary`;
  - missing scenario families:
    `production_msme_panel`, `credit_program_registry`,
    `regional_displacement_indicators`;
  - semantic ledger status: `pass`;
  - semantic ledger runtime report status: `null`;
  - PDC status: `pass`;
  - PDC records present: `false`;
  - PDC record families present: `false`;
  - continuous governance borrowed artifact kind:
    `runtime.production_data_quality_report`.
- [ ] Add `test_cloud_connectivity_fixture_preserves_spine_breaks`.
- [ ] Assert the fixture fails if any future compact record erases a dropped
  contract id, global-to-claim anchor gap, producer-pass/reader-fail gap, or
  borrowed-envelope finding.
- [ ] Run:

```bash
uv run pytest tests/repo_quality/tools/test_evidence_spine_connectivity_regression.py -q
```

Expected result: the regression fixture passes and describes all eight
connectivity patterns from the backlog.

## Wave 1 - Evidence Spine Carrier And Propagation Graph

**Purpose:** make `scenario_evidence_contract` a required runtime carrier, not
request-local metadata.

**Files:**

- Create: `src/polisyos/runtime/quality/evidence_spine.py`
- Create: `tools/quality/validation/check_evidence_spine_connectivity.py`
- Modify: `src/polisyos/runtime/http/services/control/nl_pipeline.py`
- Modify: `tools/ops_runners/runtime/canary_evidence.py`
- Test: `tests/unit/runtime/quality/test_evidence_spine.py`
- Test: `tests/repo_quality/tools/test_evidence_spine_connectivity.py`

**Steps:**

- [ ] Write `test_spine_carrier_requires_scenario_contract_and_requirement_ids`.
- [ ] Write `test_spine_graph_fails_when_producer_drops_consumed_contract_id`.
- [ ] Implement `EvidenceSpineCarrier`,
  `EvidenceRequirementBinding`, `EvidenceSpineNode`, and
  `build_evidence_spine_graph`.
- [ ] Thread the carrier through request context, job progress, Fabric, Lex,
  Foundry, policy grounding, semantic binding, PDC, canary evidence, replay,
  inspection, and readiness payloads.
- [ ] Add `scenario_contract_propagation_graph.json` to every serious bundle.
- [ ] Fail the graph if a producer consumes the contract internally but emits
  `scenario_evidence_contract_id=null` or drops requirement ids.
- [ ] Run:

```bash
uv run pytest tests/unit/runtime/quality/test_evidence_spine.py tests/repo_quality/tools/test_evidence_spine_connectivity.py -q
uv run python tools/quality/validation/check_evidence_spine_connectivity.py --repo-root . --bundle-dir _build/.tmp/production-quality/cloud_wave11/bundle_full --json-output _build/.tmp/production-quality/cloud_wave11/evidence_spine_connectivity.json
```

Expected result: the current cloud fixture fails with typed
`evidence_spine_contract_dropped` findings; synthetic complete fixtures pass.

## Wave 1A - Carrier Safety And Async Handoff Ledger

**Purpose:** make the carrier safe to propagate and make async/batch handoffs
diagnosable without manually searching JSON.

**Files:**

- Create: `src/polisyos/runtime/quality/evidence_spine_handoff.py`
- Create: `tools/quality/validation/check_evidence_spine_handoffs.py`
- Modify: `src/polisyos/runtime/http/services/control_worker.py`
- Modify: `src/polisyos/runtime/http/services/control_plane_store.py`
- Modify: `tools/ops_runners/runtime/canary_evidence.py`
- Test: `tests/unit/runtime/quality/test_evidence_spine_handoff.py`
- Test: `tests/repo_quality/tools/test_evidence_spine_handoffs.py`

**Steps:**

- [ ] Write `test_carrier_rejects_secret_like_and_raw_text_values` with values
  matching DSNs, bearer tokens, API-key-like strings, raw prompts, raw legal
  corpus excerpts, and raw recommendation bodies.
- [ ] Write `test_async_handoff_links_job_progress_to_cas_bundle_and_readiness`.
- [ ] Implement `EvidenceSpineHandoff` with `handoff_id`, `handoff_kind`,
  `producer_ref`, `consumer_ref`, `parent_spine_ref`, `input_refs`,
  `output_refs`, `batch_id`, `message_count`, `carrier_ref`,
  `carrier_redaction_status`, and `integrity_status`.
- [ ] Emit handoff records at NL request creation, control-plane job lease,
  workflow state persistence, CAS artifact write, canary bundle assembly,
  replay, inspection, readiness, and public/dashboard/API export.
- [ ] Fail the handoff checker if a handoff has no parent/input/output refs,
  no carrier ref, failed redaction, or mismatched producer/consumer ids.
- [ ] Run:

```bash
uv run pytest tests/unit/runtime/quality/test_evidence_spine_handoff.py tests/repo_quality/tools/test_evidence_spine_handoffs.py -q
uv run python tools/quality/validation/check_evidence_spine_handoffs.py --repo-root . --bundle-dir _build/.tmp/production-quality/cloud_wave11/bundle_full --json-output _build/.tmp/production-quality/cloud_wave11/evidence_spine_handoffs.json
```

Expected result: the current cloud fixture exposes missing async handoff refs;
future bundles preserve causal links without leaking sensitive data.

## Wave 2 - Scenario-Admissible Production Data Contracts

**Purpose:** fix the first broken source boundary by packaging and validating
scenario source families instead of broad bundle labels.

**Files:**

- Modify: `src/polisyos/runtime/quality/production_data_contract_index.py`
- Modify: `src/polisyos/runtime/http/services/control/production_data.py`
- Modify: `tools/quality/testing/local_prod_debug_probe.py`
- Create: `tools/quality/validation/check_production_data_scenario_contracts.py`
- Test: `tests/unit/runtime/quality/test_production_data_contract_index.py`
- Test: `tests/repo_quality/tools/test_local_prod_debug_probe.py`

**Steps:**

- [ ] Add a fixture that contains valid contracts for:
  - `production_msme_panel`;
  - `credit_program_registry`;
  - `regional_displacement_indicators`.
- [ ] Each fixture contract must include dataset identity, source family,
  dictionary ref, schema ref, field refs, units, geography coverage, time
  coverage, freshness ref, lineage refs, transformation refs, quality assertion
  refs, missingness refs, outlier refs, construct-validity refs, and
  claim-bindability refs.
- [ ] Add a negative fixture matching the cloud curated metadata with only
  `us.macro.gdp_nominal`, `us.macro.unemployment_rate`, and
  `agent.income.salary`.
- [ ] Extend `ProductionDataContractIndex` to report missing OpenLineage-like
  facets as `missing_facets`, not generic data-quality text.
- [ ] Extend `production-data-static` in `local_prod_debug_probe.py` so it
  fails early when scenario families are absent from curated contracts.
- [ ] Run:

```bash
uv run pytest tests/unit/runtime/quality/test_production_data_contract_index.py tests/repo_quality/tools/test_local_prod_debug_probe.py -q
uv run python tools/quality/validation/check_production_data_scenario_contracts.py --repo-root . --scenario scenario-public_golden --json-output _build/.tmp/production-quality/production_data_scenario_contracts.json
```

Expected result: broad bundle availability cannot pass scenario data
admissibility; missing scenario-family contracts are blocked before Fabric
selection.

## Wave 3 - Fabric Source Selection State Machine

**Purpose:** make Fabric choose admissible source contracts or emit blockers,
never broad selected bundles pretending to satisfy scenario families.

**Files:**

- Modify: `src/polisyos/fabric/catalog/source_selection_audit.py`
- Modify: `src/polisyos/runtime/http/services/control/nl_pipeline.py`
- Modify: `tools/quality/validation/fabric_source_contracts.py`
- Test: `tests/unit/fabric/test_source_selection_audit.py`
- Test: `tests/unit/runtime/http/test_nl_pipeline_materialization.py`

**Steps:**

- [ ] Add a failing test where Fabric consumes `production_msme_panel` but emits
  top-level `scenario_evidence_contract_id=None`.
- [ ] Add a failing test where a broad candidate family such as `datasets`
  appears in `selected_sources` while `selected_contract_binding=None`; assert
  report status is `failed` and the selected source is marked
  `non_admissible_context_only`.
- [ ] Add a passing test where a full contract-index candidate is selected and
  all rejected candidates include typed rejection reasons.
- [ ] Normalize Fabric output so `selected_sources` is context inventory and
  `selected_contract_bindings` is the claim-admissible authority surface.
- [ ] Add Fabric spine bindings for consumed requirement ids and emitted
  selected/rejected/blocked bindings.
- [ ] Run:

```bash
uv run pytest tests/unit/fabric/test_source_selection_audit.py tests/unit/runtime/http/test_nl_pipeline_materialization.py -q
uv run python tools/quality/validation/fabric_source_contracts.py --repo-root . --report _build/.tmp/production-quality/fabric_source_contracts.json
```

Expected result: Fabric cannot claim source-family satisfaction through
generic bundles and cannot drop the scenario contract id at top level.

## Wave 4 - Lex Per-Claim Legal Anchoring

**Purpose:** convert global Ukrainian legal retrieval into recommendation-level
selected/rejected norm anchors.

**Files:**

- Modify: `src/polisyos/lex/normpack/query_normalization.py`
- Modify: `src/polisyos/lex/normpack/applicability_report.py`
- Modify: `src/polisyos/runtime/http/services/control/nl_pipeline.py`
- Test: `tests/unit/lex/test_query_normalization.py`
- Test: `tests/unit/lex/test_normative_applicability_report.py`

**Steps:**

- [ ] Add a regression test where
  `query_normalization_report.legal_requirements` has 4 requirements and
  top-level `legal_requirements` is missing; normalization must preserve the
  legal requirements instead of returning 0.
- [ ] Add a test with 33 global candidate norms and 3 recommendations; each
  recommendation must produce selected and rejected norm refs or an explicit
  no-anchor rationale.
- [ ] Implement per-recommendation scoring over competence, temporal validity,
  policy instrument, beneficiary class, fiscal authority, implementation
  agency, and jurisdiction/time filters.
- [ ] Store both global candidate pools and claim-specific legal anchors, with
  separate fields and separate status semantics.
- [ ] Run:

```bash
uv run pytest tests/unit/lex/test_query_normalization.py tests/unit/lex/test_normative_applicability_report.py -q
```

Expected result: global Lex retrieval no longer masks missing per-claim
normative authority.

## Wave 5 - Foundry Method Candidate Reconciliation

**Purpose:** demote invalid generic methods and require named analytical
obligations before claims depend on method outputs.

**Files:**

- Modify: `src/polisyos/foundry/validation/method_quality.py`
- Modify: `src/polisyos/foundry/methods/catalog/mechanism/runtime.py`
- Modify: `src/polisyos/scientist/orchestration/workflows/builder.py`
- Test: `tests/unit/foundry/validation/test_method_quality.py`
- Test: `tests/unit/scientist/orchestration/workflows/test_builder_pinning.py`

**Steps:**

- [ ] Add a regression test where `foundry.execute` enters as an already
  selected method under serious expectations; assert it is moved to
  `rejected_methods` with `generic_method_not_admissible`.
- [ ] Expand method obligations to cover causal effect estimation,
  heterogeneity, uncertainty intervals, sensitivity/transportability,
  implementation feasibility, assumptions, missingness diagnostics, analytical
  proof surfaces, limitations, and objective/tradeoff refs.
- [ ] Update workflow builder so method obligations are requested and recorded
  before Scientist claim drafting.
- [ ] Run:

```bash
uv run pytest tests/unit/foundry/validation/test_method_quality.py tests/unit/scientist/orchestration/workflows/test_builder_pinning.py -q
```

Expected result: `foundry.execute` cannot remain selected when it fails serious
scenario method obligations.

## Wave 6 - Runtime Claim Registry

**Purpose:** introduce the missing bridge between producer evidence and final
claims.

**Files:**

- Create: `src/polisyos/runtime/quality/claim_registry.py`
- Modify: `src/polisyos/scientist/validation/policy_grounding.py`
- Modify: `src/polisyos/scientist/validation/decision_artifact_quality.py`
- Modify: `src/polisyos/runtime/http/services/control/nl_pipeline.py`
- Test: `tests/unit/runtime/quality/test_claim_registry.py`
- Test: `tests/unit/scientist/validation/test_policy_grounding_matrix.py`
- Test: `tests/unit/scientist/validation/test_decision_artifact_quality.py`

**Steps:**

- [ ] Define `RuntimeClaimRegistry` with `claim_id`,
  `scenario_requirement_refs`, `data_refs`, `selected_norm_refs`,
  `rejected_norm_refs`, `method_output_refs`, `portfolio_refs`,
  `argument_refs`, `warrant_refs`, `rebuttal_refs`, `counter_evidence_refs`,
  `limitation_refs`, `accepted_deficit_refs`, and `blocker_refs`.
- [ ] Add a failing test where global Lex refs and generic method refs exist,
  but a major claim has no per-claim registry entry.
- [ ] Add a passing test where one major claim binds to Fabric, Lex, Foundry,
  argument, warrant, rebuttal, counter-evidence, limitation, and accepted
  deficit refs.
- [ ] Wire NL pipeline so policy grounding and decision artifact quality consume
  the registry, not detached global evidence pools.
- [ ] Run:

```bash
uv run pytest tests/unit/runtime/quality/test_claim_registry.py tests/unit/scientist/validation/test_policy_grounding_matrix.py tests/unit/scientist/validation/test_decision_artifact_quality.py -q
```

Expected result: final policy output becomes a projection of claim-bound
runtime evidence, not free text beside detached reports.

## Wave 7 - Producer-Side Semantic Closure

**Purpose:** eliminate producer `pass` when semantic readers already know
closure failed.

**Files:**

- Modify: `src/polisyos/runtime/quality/semantic_binding.py`
- Modify: `src/polisyos/runtime/quality/claim_argument.py`
- Modify: `tests/_helpers/hds_quality.py`
- Test: `tests/unit/runtime/quality/test_semantic_binding.py`
- Test: `tests/unit/runtime/quality/test_claim_argument.py`
- Test: `tests/unit/runtime/quality/test_scorecard.py`

**Steps:**

- [ ] Add a regression test using the cloud ledger shape:
  `status=pass`, `runtime_report_status=None`, missing claim axes, and
  downstream semantic failure codes.
- [ ] Move semantic closure evaluation into the ledger builder.
- [ ] Set producer top-level status to `failed` or `blocked` when required axes
  are missing.
- [ ] Emit the same issue codes that scorecard/readiness consume, including
  missing scenario requirement, canonical concept, column, argument, warrant,
  rebuttal/counter-evidence, and limitation refs.
- [ ] Run:

```bash
uv run pytest tests/unit/runtime/quality/test_semantic_binding.py tests/unit/runtime/quality/test_claim_argument.py tests/unit/runtime/quality/test_scorecard.py -q
```

Expected result: semantic ledger status and scorecard semantic status cannot
diverge on the same evidence path.

## Wave 8 - Runtime Policy Design Case Record Families

**Purpose:** replace profile-only PDC pass with runtime-owned record-family
compilation.

**Files:**

- Modify: `src/polisyos/runtime/quality/policy_design_case.py`
- Modify: `src/polisyos/runtime/quality/pass1b_hardening.py`
- Modify: `src/polisyos/runtime/quality/case_maturity.py`
- Modify: `src/polisyos/runtime/http/services/control/nl_pipeline.py`
- Test: `tests/unit/runtime/quality/test_policy_design_case_record_registry.py`
- Test: `tests/unit/runtime/quality/test_policy_design_case_pass1b_hardening.py`
- Test: `tests/unit/runtime/quality/test_case_maturity.py`
- Test: `tests/repo_quality/tools/test_policy_design_case_wave40.py`

**Steps:**

- [ ] Add a live-path regression test that fails when `build_policy_design_case_profile`
  is followed by `profile_payload["status"] = "pass"` without `records` and
  `record_families`.
- [ ] Implement runtime record-family compilation for every minimum SDD family:
  structured judgement, consultation, implementation monitoring, DDM, human
  oversight, self-FMEA, maturity, audit, benchmarking, proportionality, formal
  invariants, substrate residual verification, partial-state consistency,
  dormant capability inventory, skip-causality ledger, freshness/policy-time
  semantics, and Pass 1B hardening.
- [ ] Each family must be `present`, `blocked`, or `out_of_scope` by typed
  authority policy and must include schema owner, producer owner, reader owner,
  readiness gate, runtime refs, and authority envelope.
- [ ] Remove forced `pass` for profile-only cases.
- [ ] Run:

```bash
uv run pytest tests/unit/runtime/quality/test_policy_design_case_record_registry.py tests/unit/runtime/quality/test_policy_design_case_pass1b_hardening.py tests/unit/runtime/quality/test_case_maturity.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_wave40.py -q
```

Expected result: PDC cannot pass without concrete runtime record families.

## Wave 8A - Residual Spine Boundaries For Snapshot, Scholar, Concept, And Jurisdiction Evidence

**Purpose:** close root-cause groups that are upstream of PDC but were not
fully owned by the data/legal/method/claim waves.

**Files:**

- Modify: `src/polisyos/runtime/quality/policy_design_case.py`
- Modify: `src/polisyos/runtime/quality/concept_spine.py`
- Modify: `src/polisyos/runtime/quality/policy_design_jurisdiction_spine.py`
- Create: `src/polisyos/runtime/quality/scholar_academic_evidence.py`
- Modify: `tools/quality/validation/inspect_evidence_bundles.py`
- Test: `tests/unit/runtime/quality/test_policy_design_case_concept_spine.py`
- Test: `tests/unit/runtime/quality/test_policy_design_jurisdiction_spine.py`
- Test: `tests/unit/runtime/quality/test_scholar_academic_evidence.py`
- Test: `tests/repo_quality/tools/test_evidence_bundle_inspection.py`

**Steps:**

- [ ] Add a regression test for `data_forge_snapshot_binding_missing` with a
  production-data contract present but no snapshot id, CAS manifest identity,
  artifact ids, quality-gate refs, freshness ref, or read-API surface.
- [ ] Add a regression test for `policy_design_scholar_academic_evidence_missing`
  where a serious claim has no research intent, query graph, provider trace,
  source scoring, snippets, citations, freshness, corpus lineage, support/conflict
  links, or typed blocker.
- [ ] Add concept and jurisdiction spine tests that fail when unresolved
  concepts or competence blockers are only visible as late PDC scorecard
  findings.
- [ ] Emit producer-owned records or typed blockers for Data Forge snapshot
  binding, Scholar academic evidence, concept spine resolution, and jurisdiction
  competence before PDC compilation.
- [ ] Run:

```bash
uv run pytest tests/unit/runtime/quality/test_policy_design_case_concept_spine.py tests/unit/runtime/quality/test_policy_design_jurisdiction_spine.py tests/unit/runtime/quality/test_scholar_academic_evidence.py -q
uv run pytest tests/repo_quality/tools/test_evidence_bundle_inspection.py -q
```

Expected result: residual runtime-quality root causes become first-class
producer records or typed blockers, not miscellaneous PDC downstream failures.

## Wave 9 - Authority Envelope Ownership And No-Borrowed-Envelope Gate

**Purpose:** preserve provenance while preventing real authority from being
attached to the wrong report kind.

**Files:**

- Modify: `src/polisyos/runtime/quality/authority.py`
- Modify: `src/polisyos/runtime/quality/scorecard.py`
- Modify: `tools/ops_runners/runtime/canary_evidence.py`
- Modify: `tools/quality/validation/inspect_evidence_bundles.py`
- Test: `tests/unit/runtime/quality/test_authority_envelope_contract.py`
- Test: `tests/unit/runtime/quality/test_authority_spoofing.py`
- Test: `tests/unit/runtime/quality/test_scorecard.py`
- Test: `tests/repo_quality/tools/test_evidence_bundle_inspection.py`

**Steps:**

- [ ] Add a regression test for continuous governance no-op reports carrying
  `runtime.production_data_quality_report` authority envelopes.
- [ ] Implement authority classification values:
  `missing_provenance`, `spoofed_provenance`, `packaging_only_projection`,
  `borrowed_authority_envelope`, and `runtime_owned_domain_failure`.
- [ ] Require every report authority envelope to match artifact kind, schema,
  phase, validation status, and runtime event.
- [ ] Mint lifecycle-specific envelopes for stale, reissue, supersede, and
  withdraw no-op reports.
- [ ] Run:

```bash
uv run pytest tests/unit/runtime/quality/test_authority_envelope_contract.py tests/unit/runtime/quality/test_authority_spoofing.py tests/unit/runtime/quality/test_scorecard.py -q
uv run pytest tests/repo_quality/tools/test_evidence_bundle_inspection.py -q
```

Expected result: operators can distinguish missing provenance from wrong-report
authority and runtime-owned domain failures.

## Wave 10 - Can-I-Closeout Compatibility Matrix

**Purpose:** verify the exact deployed combination instead of assuming isolated
unit tests cover live producer/reader/authority shapes.

**Files:**

- Create: `src/polisyos/runtime/quality/closeout_compatibility.py`
- Create: `tools/quality/validation/check_can_i_closeout.py`
- Modify: `tools/ops_runners/runtime/canary_evidence.py`
- Modify: `tools/ops_runners/runtime/run_canary_matrix.py`
- Modify: `tools/ci/check_policyos_production_quality_best_in_class.py`
- Test: `tests/unit/runtime/quality/test_closeout_compatibility.py`
- Test: `tests/repo_quality/tools/test_can_i_closeout.py`
- Test: `tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py`

**Steps:**

- [ ] Build a compatibility record from bundle command, git/code revision,
  scenario contract id/version, producer report schema versions, reader gate
  versions, authority profile version, and validation refs.
- [ ] Fail closeout when `git_sha` or code revision is missing in a serious
  cloud/live bundle.
- [ ] Fail closeout when a producer report schema consumed by readiness has not
  been verified against the active reader gate.
- [ ] Attach the compatibility record to evidence bundles and readiness output.
- [ ] Run:

```bash
uv run pytest tests/unit/runtime/quality/test_closeout_compatibility.py tests/repo_quality/tools/test_can_i_closeout.py tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q
uv run python tools/quality/validation/check_can_i_closeout.py --repo-root . --bundle-dir _build/.tmp/production-quality/cloud_wave11/bundle_full --json-output _build/.tmp/production-quality/cloud_wave11/can_i_closeout.json
```

Expected result: closeout fails with narrow compatibility blockers when the
deployed bundle cannot prove its producer/reader/authority version matrix.

## Wave 11 - Secondary Signal Isolation

**Purpose:** prevent provider, prompt-tool, and control-plane symptoms from
being treated as primary root causes while the evidence spine is incomplete.

**Files:**

- Modify: `src/polisyos/scientist/orchestration/llm/provider_quality.py`
- Modify: `tools/ops_runners/runtime/provider_quality_ledger.py`
- Modify: `tools/quality/testing/local_prod_debug_probe.py`
- Modify: `tools/ops_runners/runtime/canary_evidence.py`
- Test: `tests/unit/scientist/orchestration/llm/test_provider_quality.py`
- Test: `tests/repo_quality/tools/test_provider_quality_ledger.py`
- Test: `tests/repo_quality/tools/test_local_prod_debug_probe.py`

**Steps:**

- [ ] Gate default model promotion/demotion on controlled evidence-bound tasks,
  not a single live sample with upstream closure blockers.
- [ ] Mark live provider observations as `system_confounded` when evidence
  spine, claim registry, semantic closure, or PDC closeout is failing.
- [ ] Extend prompt/tool ledger findings with operator-readable failure reason,
  step id, validator ref, and upstream spine blocker refs.
- [ ] Keep control-plane timeouts as resilience findings unless they break
  bundle production, replay, or closeout artifact durability.
- [ ] Run:

```bash
uv run pytest tests/unit/scientist/orchestration/llm/test_provider_quality.py tests/repo_quality/tools/test_provider_quality_ledger.py tests/repo_quality/tools/test_local_prod_debug_probe.py -q
```

Expected result: provider/model quality decisions are explainable separately
from evidence-spine closure health.

## Wave 12 - Local And Cloud Revalidation

**Purpose:** prove the root repair with a light local loop first, then the
same one-lane cloud production-debug path.

**Files:**

- Modify: `docs/runbooks/local-production-debugging.md`
- Modify: `docs/runbooks/cloud-production-debugging.md`
- Modify: `docs/backlog/cloud-wave11-root-cause-diagnostic-backlog.md`
- Test: `tests/repo_quality/tools/test_docs_lifecycle.py`
- Test: `tests/repo_quality/tools/test_docs_gate.py`

**Steps:**

- [ ] Run the local quick probe with evidence-spine and can-i-closeout checks:

```bash
uv run --extra runtime --extra multi-tenant --extra ml python tools/quality/testing/local_prod_debug_probe.py \
  --repo-root . \
  --checks quick,production-data-static,docs-repro \
  --output _build/.tmp/production-quality/local_prod_debug_spine_quick.json
```

- [ ] Run the one-lane cloud live pass:

```bash
uv run python tools/ops_runners/runtime/run_canary_matrix.py \
  --deterministic \
  --only-lane profile-research__provider-live_gonka_proxy__data-canonical_production__scenario-public_golden__ui-api_only \
  --json-output _build/.tmp/production-quality/final_live_research_lane.json \
  --timeout-s 1200
```

- [ ] Inspect the emitted bundle:

```bash
uv run python tools/quality/validation/inspect_evidence_bundles.py \
  --repo-root . \
  --matrix-run-json _build/.tmp/production-quality/final_live_research_lane.json \
  --json-output _build/.tmp/production-quality/final_evidence_bundle_inspection.json
```

- [ ] Run readiness without `--require-passing`, then classify every remaining
  finding as remediated, typed blocker, accepted next-plan item, or false alarm:

```bash
uv run python tools/ci/check_policyos_production_quality_best_in_class.py \
  --repo-root . \
  --matrix-run-json _build/.tmp/production-quality/final_live_research_lane.json \
  --output _build/.tmp/production-quality/final_readiness.json \
  --output-format json
```

- [ ] Run docs gates:

```bash
uv run pytest tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
```

Expected result: the cloud lane either passes through real evidence closure or
fails with narrow typed blockers that preserve the evidence spine and cannot be
promoted by exports.

## Acceptance Checklist

- [ ] `scenario_contract_propagation_graph.json` exists in serious live bundles.
- [ ] Evidence spine carriers contain only redacted refs, typed ids, schema
  versions, and hashes; secret-like or raw text values fail carrier validation.
- [ ] Async handoff records connect NL request, control-plane job progress,
  workflow state, CAS writes, bundle assembly, replay, inspection, readiness,
  and exports.
- [ ] Every producer that consumes scenario requirements emits requirement-level
  selected/rejected/blocked bindings.
- [ ] Production data static checks fail before Fabric when scenario families
  are absent from curated contracts.
- [ ] Fabric cannot satisfy `production_msme_panel`,
  `credit_program_registry`, or `regional_displacement_indicators` with broad
  bundle labels.
- [ ] Lex top-level legal requirements cannot be erased when query
  normalization has them.
- [ ] Every major recommendation has selected/rejected legal anchors or typed
  no-anchor rationale.
- [ ] Generic `foundry.execute` cannot remain selected under serious method
  obligations.
- [ ] A runtime claim registry exists before policy grounding and public
  decision compilation.
- [ ] Semantic ledger producer status cannot be `pass` when required claim axes
  are missing.
- [ ] Policy Design Case cannot be `pass` without `records` and
  `record_families`.
- [ ] Data Forge snapshot, Scholar academic evidence, concept spine, and
  jurisdiction spine records are present, blocked, or out of scope before PDC
  closeout.
- [ ] Continuous governance reports mint lifecycle-specific authority
  envelopes.
- [ ] No authority-bearing report can borrow another report kind's envelope.
- [ ] `can-i-closeout` records code revision and producer/reader/authority
  compatibility.
- [ ] Provider demotion uses controlled evidence-bound model tasks, not one
  confounded live sample.
- [ ] Public export, dashboard, and API projections cannot promote failed
  claims, missing record families, or packaging-only authority.

## Validation Ladder

Run after each wave:

```bash
uv run pytest tests/unit/runtime/quality tests/unit/tools/test_canary_evidence.py -q
uv run pytest tests/repo_quality/tools/test_evidence_bundle_inspection.py tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q
uv run python tools/quality/validation/check_evidence_spine_connectivity.py --repo-root . --bundle-dir _build/.tmp/production-quality/cloud_wave11/bundle_full --json-output _build/.tmp/production-quality/cloud_wave11/evidence_spine_connectivity.json
uv run python tools/quality/validation/check_evidence_spine_handoffs.py --repo-root . --bundle-dir _build/.tmp/production-quality/cloud_wave11/bundle_full --json-output _build/.tmp/production-quality/cloud_wave11/evidence_spine_handoffs.json
```

Run before closeout:

```bash
uv run pytest tests/unit/fabric tests/unit/lex tests/unit/foundry tests/unit/scientist tests/unit/runtime/quality -q
uv run pytest tests/repo_quality/tools/test_canary_matrix.py tests/repo_quality/tools/test_replay_canary_bundle.py tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_public_export.py tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
uv run python tools/quality/validation/check_evidence_spine_connectivity.py --repo-root . --bundle-dir _build/.tmp/production-quality/cloud_wave11/bundle_full --json-output _build/.tmp/production-quality/cloud_wave11/evidence_spine_connectivity.json --require-passing
uv run python tools/quality/validation/check_evidence_spine_handoffs.py --repo-root . --bundle-dir _build/.tmp/production-quality/cloud_wave11/bundle_full --json-output _build/.tmp/production-quality/cloud_wave11/evidence_spine_handoffs.json --require-passing
uv run python tools/quality/validation/check_can_i_closeout.py --repo-root . --bundle-dir _build/.tmp/production-quality/cloud_wave11/bundle_full --json-output _build/.tmp/production-quality/cloud_wave11/can_i_closeout.json
```

## Execution Notes

- Start with Wave 0 and Wave 1. They define the regression fixture and
  propagation graph that make all later fixes measurable.
- Do not weaken scorecard or readiness gates to make a wave green.
- Keep broad bundle inventory and claim-admissible bindings as separate fields.
- Keep evidence spine carriers intentionally small; store authoritative payloads
  in CAS and propagate only refs, hashes, and typed ids.
- Treat `blocked` as a successful diagnostic state only when it is typed,
  owned, and propagated to readiness.
- Prefer small producer-owned blockers over late reader-only failures.
- Keep local MacBook checks light by default; run live/provider/cloud checks
  only with explicit flags or cloud runner commands.
