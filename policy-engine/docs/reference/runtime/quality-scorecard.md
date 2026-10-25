# Runtime Quality Scorecard

Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/quality/scorecard.py`, `tools/ops_runners/runtime/canary_evidence.py`, and `tests/unit/runtime/quality/test_scorecard.py`
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Validation status: Source and test-reference inspection only for this documentation update; the scorecard producer and tests were not run.

The runtime quality scorecard is the additive approval-readiness contract for
production, governed, research, staging, and dev canaries. It keeps
`schema_version: policyos.quality_scorecard.v1` stable while adding fields that
help operators distinguish execution failure, quality failure, warning-only
quality, performance override needs, and approval-ready runs.

The scorecard reports evidence and approval readiness. A passing status does
not manufacture missing evidence, convert candidate output into authority, or
sign/authorize a public policy claim; approval and custody remain separate
consumers.

Canary-generated public exports remain persisted at the existing bundle path and are passed to
scorecard candidate-firewall and audit consumers through a separate projection channel. Replay
continuity freezes selected caller/loaded input surfaces before any canary-local report or
projection is built. Request context, workflow state, job progress, and quality evidence are
`consumer_asserted` diagnostic candidates, not admitted authority. Replay manifest, bundle,
inspection, readiness, and export are observations: their refs stay in `surface_coverage`, and
refs absent from the selected source candidates are reported as unbound. These observations cannot
supply required or summarized refs. Consequently, an observation-only required ref causes the
diagnostic continuity status to fail; G must adjudicate that observable status meaning before a
public compatibility claim. A public-export schema or projection-only object on a source surface is
refused, while its label never establishes producer provenance. A continuity-shaped record on a
source surface contributes only its fixed artifact ref; on an observation surface its summary refs
remain observations. Content-shape and fingerprint checks do not establish who emitted the record.
Malformed embedded continuity data fails with a typed finding. Arbitrary markerless ref maps outside
a known continuity slot remain a bounded diagnostic residual and cannot establish authority.

## Compatibility

Existing readers may continue to use these original fields:

- `schema_version`
- `generated_at`
- `canary_kind`
- `job_id`
- `run_id`
- `execution_status`
- `quality_status`
- `overall_score`
- `stage_scores`
- `quality_gates`
- `blocking_quality_failures`
- `evidence_refs`
- `quality_scorecard_ref`
- `quality_evidence_bundle_path`

Phase 0.3 adds only new fields:

- `performance_status`
- `approval_state`
- `warnings`
- `soft_gate_telemetry`
- `override_evidence`
- `approval_eligibility`

Consumers must ignore unknown fields and must not infer approval readiness from
`quality_status` alone.

The selected-BERL claim-argument path also adds the optional
`policy_design_claim_argument_validation_diagnostic` field when the existing
serious-canary validation applies to a case with final major claims. It serializes
the same validation result used to produce the claim-argument gates. The selected
CAS bundle supplies each method's requested/effective identity, fallback details,
scope, and explicit field-presence flags; embedded copies cannot replace a supplied
bundle reference that fails to resolve. Canary assembly persists this diagnostic
in `quality_evidence/quality_scorecard.json`.

This diagnostic does not supply missing claim/run subject resolution, conditional
law, production currentness, or policy authority. Its presence does not establish
that the overall canary is admissible or approval-ready.

## Stage Scores

`stage_scores` is a map from stage name to a normalized score in `[0.0, 1.0]`.
The current stages are:

- `llm`
- `fabric`
- `materialization`
- `foundry`
- `scientist`
- `lex`
- `policy_output`
- `ops`

Each gate contributes `1.0` for `pass`, `0.5` for `warn`, and `0.0` for `fail`.
Stages without gates score `1.0`. `overall_score` is the average of all stage
scores and remains informational; approval readiness is derived from gates and
readiness fields.

## Gates And Warnings

`quality_gates` records every gate with:

- `name`
- `stage`
- `code`
- `status`
- `layer`
- `phase`
- `message`
- `evidence_ref`
- `next_action`
- `blocking`

`blocking_quality_failures` contains the sanitized subset of blocking failed
gates. Serious canary kinds (`production`, `governed`, `research`) fail closed
when runtime-owned quality refs are missing:

- `normative_applicability_report_ref`
- `fabric_retrieval_trace_ref`
- `foundry_method_report_ref`
- `policy_grounding_matrix_ref`
- `conflict_check_ref`

Dev or staging fixtures may warn only when `optional_runtime_quality_refs`
explicitly explains why a missing runtime ref is optional for that profile.
`warnings` mirrors non-blocking warning gates in a compact sanitized form and
adds the soft-gate lifecycle fields required by W2.D:

- `owner`
- `first_observed_at`
- `age_seconds`
- `ttl_seconds`
- `escalation_after_seconds`
- `escalates_at`
- `ttl_expires_at`
- `lifecycle_status`
- `accepted_deficit_policy`
- `closeout_effect`
- `publication_effect`

Warnings are advisory while active, escalate to the named owner after the
escalation window, and expire under TTL. Expired warnings require resolution or
an owner-reviewed accepted deficit before serious closeout/publication.

## Soft-Gate Telemetry

`soft_gate_telemetry` is the W2.D runtime surface for self-FMEA and soft-gate
observability. It is derived from existing runtime telemetry, not from a manual
ceremony form. The payload uses
`schema_version: policyos.runtime.soft_gate_telemetry.v1` and includes:

- `warning_lifecycle`: the same owner/TTL records projected in `warnings`
- `bounded_liveness_hooks`: finite producer deadline/retry resolutions from
  governed bounded-liveness config
- `repair_decision_fmea`: prompt/tool repair decisions and their FMEA
  annotations, plus `machinery_failures` rows for non-not-applicable repair
  decisions. Each machinery failure carries `failure_mode`, `severity`,
  `cause`, `recommended_mitigation`, `residual_risk`, evidence ref, owner, and
  risk-priority metadata.
- `advisory_review_telemetry`: human-review effectiveness telemetry with the
  current advisory authority boundary
- `complexity_budget_telemetry`: gate, warning, tool, repair, review, elapsed,
  and cost measurements derived from runtime telemetry, plus advisory
  prune/merge decisions when a budget is exceeded

The soft-gate telemetry surface is authoritative for observability and owner
follow-up only. It does not provide claim support, evidence admissibility, or a
standalone closeout decision.

Prompt/tool repair machinery failures also project to the scorecard-level
`operator_machinery_failures` dashboard/operator surface and to the optional
`prompt_tool_repair_fmea` closeout reader record. Missing FMEA refs fail the
prompt/tool parser authority ledger; annotated repair failures are surfaced as
limitations or warnings, not as new producer authority.

The control-plane job response projection also enforces these runtime-owned refs
for completed jobs. A stale or fixture-authored scorecard that marks the gates
as passing cannot promote a research, governed, or production job to
`quality_status: pass` unless the refs are present in job progress.

## Generated projection audit boundary

`build_quality_scorecard` keeps its existing public signature and accepts evidence only through the
ordinary selected-input/ref-validation path. Canary assembly persists its generated public export at
`quality_evidence/public_export_bundle.json` for audit consumers; it does not feed that generated
output back into scorecard evidence. Diagnostic SLO and evidence-spine consumers receive an audit
view to measure redaction coverage and record the projection handoff, but neither view supplies an
authority ref. Caller-supplied projection-shaped content remains ordinary `quality_evidence` and is
validated there; a `projection_only` label does not bypass admission.

## Phase-barrier owner and intent limits

The live NL control-job producer persists an owner binding only after reconciling the admitted
creation event and active lease. One store-owned terminal policy rederives it under the same worker
fence and carries only typed candidate projections that exist on the current row: matching
`RunIntentBinding`, runtime quality ref and selected-artifact maps, the projection-only marker,
attestation records, flattened role refs, and diagnostic summary projections. Conflicting caller
copies are refused; absent fields stay absent, and previous phase/details payloads are not merged.
The private local-canary assembler recomputes this owner from the current job row, creation scope,
terminal lifecycle event and completion outbox, indexed Core run, and a fresh typed job GET inside
the active runtime-client lifespan for each serious scorecard decision. Its owner-scope gate can pass
only when those sources match the mapping being scored. The public `build_quality_scorecard` API
remains mapping-only and keeps `phase_barrier_owner_scope_not_established`; matching fields do not
prove a fresh terminal read. Carried refs and attestations remain candidates for existing consumer
validation, and diagnostic summaries remain projections. The owner proof does not supply a typed
policy-time reference, same-input closure, or required phase-barrier ledger. The normal NL run still
has absent `time_context_ref` and `same_input_closure_ref`, so dependent intent and serious readiness
remain blocked.

## Refs

`evidence_refs` points to scorecard-readable evidence only. Report files use
`quality_evidence/<file>.json`; runtime-owned refs preserve their artifact ref
strings when present. The scorecard does not embed raw report payloads,
reviewer deliberation, secrets, or full request bodies.

## Approval States

`approval_state` is one of:

| State               | Meaning                                                                                                          |
| ------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `execution_failed`  | The control job did not complete. Quality evidence cannot approve it.                                            |
| `quality_failed`    | Execution completed but at least one blocking quality gate failed and no accepted override is present.           |
| `quality_warn`      | Execution completed with warning gates and no blocking quality failure.                                          |
| `override_required` | Execution and quality are otherwise acceptable, but serious performance/readiness evidence requires an override. |
| `approval_ready`    | Execution completed and the run is eligible for approval, either cleanly or with an accepted override trail.     |

`performance_status` is derived from runtime performance evidence. A
`budget_summary.over_budget_count > 0` or any `phase_budgets[*].status` of
`over_budget`, `fail`, `failed`, `error`, `blocked`, or `timeout` yields
`fail`. Warning statuses yield `warn`; missing evidence yields `missing`.

## Override Evidence

`override_evidence` is intentionally small:

- `status`: `missing`, `pending`, `accepted`, `rejected`, or `invalid`
- `accepted`: boolean
- `decision_ref`: optional sanitized artifact ref
- `packet_ref`: optional sanitized artifact ref

Accepted override evidence requires an override/overridden/approved status or
override action plus a decision ref or signature marker. Reviewer ids, free-text
rationale, private deliberation, and secret-like values are not copied into the
scorecard.

## Approval Eligibility

`approval_eligibility` summarizes the state machine:

- `state`: mirrors `approval_state`
- `eligible`: true only for `approval_ready`
- `requires_override`: true when approval depends on accepted override evidence
- `override_accepted`: true when sanitized override evidence is accepted
- `missing_override`: true when an override is required but not accepted
- `execution_status`
- `quality_status`
- `performance_status`
- `blocking_gate_count`
- `warning_count`
- `reasons`: stable gate or readiness codes

Production approval consumers should require `approval_eligibility.eligible ==
true` and should surface `reasons`, `warnings`, `blocking_quality_failures`, and
`evidence_refs` when it is false.

## Verification

```bash
uv run pytest tests/unit/runtime/quality/test_scorecard.py -q
uv run ruff check --select F,I,E501 src/polisyos/runtime/quality/scorecard.py
```
