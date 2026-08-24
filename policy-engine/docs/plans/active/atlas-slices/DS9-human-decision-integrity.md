---
plan_id: atlas-ds9-human-decision-integrity
title: "DS9 - Human Decision Integrity"
type: slice-plan
status: execution_authorized_in_progress
created: 2026-08-23
last_verified: 2026-08-24
stability: execution_in_progress
slice: DS9
baseline_commit: 3c89f008f83f50461d1eb364b502925e2d1b4a13
execution_base_commit: 5a6de66ce123ed56ff7e2d5c7368d4869ed3b141
execution_main_commit: 715c25f1e48859a6b1b932b3db81199c8beeadfc
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
identity_boundary: ../../../system-design-decisions/policyos-identity-and-custody-boundary.md
failure_register: ../../../reference/policy-design-case-failure-patterns.md
ds8_plan: ./DS8-case-evidence-workspace.md
ds20_closure: ./DS20-server-authz-enforcement-closure.md
debt_register: ../DEBT-REGISTER.md
disposition_register: ../../../../architecture/atlas_surfaces/frontend-disposition-register.json
audiences: [REVIEWER, EXPERT, MACHINE]
backend_co_owner: team-runtime
feature_flags: none
review_cycles_used: 3_of_3
branch: codex/ds9-human-decision-integrity-plan
depends_on:
  - ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
  - ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
  - ../../../system-design-decisions/policyos-identity-and-custody-boundary.md
  - ../../../reference/policy-design-case-failure-patterns.md
  - ./DS8-case-evidence-workspace.md
  - ./DS20-server-authz-enforcement-closure.md
---

# DS9 - Human Decision Integrity

## For agentic workers

This is an approval-gated implementation plan, not authorization to implement.
Planning branch `codex/ds9-human-decision-integrity-plan` was attached and clean
at immutable main base `3c89f008f83f50461d1eb364b502925e2d1b4a13` before this
document became its sole change. Root alone writes; verify attachment before
every commit. Before approval: no production code, writer, register lock,
regeneration, visual lane, merge, push, rebase, stash storage, or master-plan
line-7 edit. The absent frontmatter `branch:` keeps the unapproved plan projected
as `planned`; C00 adds the execution branch only after approval.

After approval, C00 starts only from a newly attached execution branch cut from a
then-current `main` that contains this approved plan and passes the debt checker;
record that commit in `execution_base_commit`. Execute red-first with
`corepack pnpm`, fixed ceilings, exact path fences, and one resource at a time.
The register-family lock, regeneration token, and visual lane never overlap. A
completed failure is a receipt; a kill or missing tool is not.

## Mission and boundary

DS9 makes approval, override, blocking, and contestation actions attributable to
a principal. It extends the existing `HumanDecisionRecord`; adds run-bound
read/write and review-effectiveness HTTP surfaces; uses the existing
`RuntimeDataAccessAuditTrail`; renders GY-PA2 as a pre-action gate; enforces DS20
step-up; and makes the existing production-approval operation consume the same
live decision record. REVIEWER/EXPERT see mandate, evidence exposure, dissent,
reason, rights, TTL, and accountability before action. MACHINE receives the exact
same authenticated response bytes.

The authority predicate is M34/M37: verified identity ∩ exact permission ∩
mandate-bounded delegation ∩ operation inside envelope ∩ live accountability.
DS9 owns verified intake, custody, and effects on PolicyOS approval claims. It
does not become an administrator, case system, court, appeal outcome, notification
channel, or foreign scorecard/mandate producer. Missing producers yield typed
refusal; no fixture, builder, or inferred role supplies production authority.

## Canonical Closure Contract

DS9 closes only when every checkbox below has its named receipt. No cluster may
define a second closure contract.

- [ ] **CC01** Approval, a debt-gate-green execution base, attached branch,
      root-only writer, and every path fence are re-read before each commit.
- [ ] **CC02** One strict source union resolves signed GY-PA2 or production input;
      its complete status-permutation test never defaults a missing arm green.
- [ ] **CC03** Existing `HumanDecisionRecord` is dual-read/write-v2, and durable
      SQLite/PostgreSQL race tests admit exactly one live record per action key;
      the PostgreSQL receipt selects tests and reports zero skips.
- [ ] **CC04** V2 separates verified human-act evidence from PolicyOS custody
      signing; forged actor/custodian substitution tests fail.
- [ ] **CC05** Every gate predicate has a frozen P37 class/source; falsifying a
      declaration while keeping its shape cannot admit authority.
- [ ] **CC06** Wrong role, expired TTL, and search authority reused for
      `data_request` each render `blocked` with stable reason and no record.
- [ ] **CC07** Exact delivered evidence bytes create completed exposure events in
      the existing trail; cross-request/run/basis, stale, partial, and replay fail.
- [ ] **CC08** Approval/override/blocking reuse `approve`/`reject` plus typed mode
      and mandatory reason; no universal action enum is added.
- [ ] **CC09** An unbound `Appeal here` control neither renders nor submits.
- [ ] **CC10** Issuer-qualified principal binding and separately signed reviewer
      separation are required; raw identifier inequality/equality proves neither.
- [ ] **CC11** The POST has one Python/Rego permission, owned-run resource,
      pre-OPA digest binding, structural step-up, and single-use replay protection.
- [ ] **CC12** Offline/stale submission returns revalidation-required, persists
      nothing, and never enters the frontend mutation queue.
- [ ] **CC13** Production approval freshly resolves scorecard, signed production
      basis, and current v2 record; stale raw fields/refs cannot emit `approved*`.
- [ ] **CC14** Production approval and `approve_data_promotion` remain distinct;
      absent foreign producers remain typed unavailable.
- [ ] **CC15** Review effectiveness scans only the existing access trail and
      reports parsed/schema/malformed/retention coverage without treating allow as success.
- [ ] **CC16** `human_review.py` keeps threshold result separate from advisory
      posture; rubber-stamp `fail + advisory` never renders effective/pass.
- [ ] **CC17** REVIEWER/EXPERT DOM and internal MACHINE export are projections of
      one response; response/export hash equality is green.
- [ ] **CC18** The generic frontend checker adjudicates 13 root objects plus five
      supplemental findings once each from the complete opening denominator.
- [ ] **CC19** C00/C08 debt writes produce exactly the claimed, split, declined,
      and retained rows below; writer/check/test and ledger diff are green.
- [ ] **CC20** OpenAPI, five runtime-client files, dashboard types, and Python
      public-surface inventory regenerate once and reproduce from scratch; the
      generic supported-entrypoint inventory contains the changed quality export.
- [ ] **CC21** Named semantic, mixed-status, corruption, a11y, and visual tests
      complete under their fixed command ceilings.
- [ ] **CC22** DS11 receives the immutable status/provenance/telemetry/exact-byte
      receipt bundle without public-decision authority.
- [ ] **CC23** DS14 receives a strict `source_kind` adapter union: its PA2 arm
      re-resolves the S7/v2 chain without a production packet, while its
      production arm requires the packet ref and concrete resolver; both
      re-resolve before effect and reject cross-arm fields.
- [ ] **CC24** DS9 never crosses GY-N12's DV/Claim transaction; closeout and final
      bookkeeping commits, changed-file sets, and all 24 receipts are read back.

## Measured entry receipts

### Base and dependency gates

| input | reverified receipt |
| --- | --- |
| main / execution base | current `main` `715c25f1e48859a6b1b932b3db81199c8beeadfc` merged append-only into attached branch at clean execution base `5a6de66ce123ed56ff7e2d5c7368d4869ed3b141`; branch-only delta before C00 was this approved plan |
| debt gate | On exact main parent `715c25f1e`, semantic predicates are green: zero `source_status_conflict`, zero `*_denominator_mismatch`, zero `ledger_render_drift`, register=55. Strict exit 1 is non-authoritative because it also reports the planless DS9 owner and informational complementarity: ten `register_supplies_missing_standing` plus one `register_withholds_source_standing`. The clean merge commit adds only this plan to the ledger input, so its pre-C00 render drift is the admission C00 must reconcile, not a foreign baseline defect. |
| DS8 | `c8fff1e0b` is an ancestor; its typed DesignRecord unavailable arm stays honest |
| DS20 | `03ebc1ce8` is an ancestor; structural step-up/authz is available |
| GY-PA2 | `82474845a` is an ancestor; both S7 JSON packets exist |
| downstream | DS11 and DS14 wait on DS9; DS14 also waits on the Phase-6 O-block |

Before C00 spends a round or acquires the register lock, replay the checker on
the exact current-main parent and adjudicate its findings by predicate, never by
composite exit. Any `source_status_conflict`, `*_denominator_mismatch`, or
`ledger_render_drift`, or register count other than 55, stops with zero writes.
Informational standing complementarity does not fail that gate and DS9 may not
suppress or reclassify it. Opening receipt is `published=observed=55`,
`indexed=34`, and `ambiguous=1, blocked=8, closed=21, folded=2, foreign=6,
open=17`; otherwise remeasure and obtain an owner-approved amendment. The ten
register-supplies rows are `GY-DEF14`, `GY-DEF15`, `GY-DEF19`, `GY-DEF22`,
`GY-DEF23`, `GY-DEFC-1`, `GY-GAP5`, `GY-GAP6`, `GY-GAP7`, and `GY-GAP8`;
register-withholds remains `GY-DEF9`.

### Corrected complete census

The denominator is all 5,589 tracked Python files: 2,569 `src/`, 2,404 `tests/`,
616 elsewhere. The approval strangle later uses all 6,756 tracked code files,
not a search-index sample.

| supplied input | remeasurement and correction |
| --- | --- |
| `HumanDecisionRecord` | **confirmed, denominator corrected:** the exact symbol reaches 5 source files and 7 test artifacts (4 Python + 3 JSON), not 7 Python tests. The broader record/builder vocabulary reaches one additional Python test only because it asserts that generated source does **not** contain `record_human_decision`; that negative source-text witness is not an additional record test. The strict class and builder exist; the builder has no deployed external caller. |
| `access_audit` | **confirmed:** intended vocabulary reaches 18 source and 6 test Python files. A loose case-insensitive spelling reaches 20 source files only because `fabric/security/__init__.py` and `fabric/security/access_control.py` are false positives. Canonical writer: `runtime/http/access_audit.py`. |
| step-up | **corrected false zero:** real spellings `step_up|StepUp` reach 14 source and 11 test Python files; structural map is `runtime/http/step_up.py`, with live declarations in `routes/control.py` and `routes/runs.py`. |
| production approval | **corrected false zero:** the literal full path is absent because router prefix and decorator compose `POST /api/v1/runs/{run_id}/production-approval`; operation `create_run_production_approval` is real. `approve_data_promotion` serves `/api/v1/control/data/promotion/{promotion_id}/approve`; `runtime.evidence.promotion.approve` is its resource kind. They are not DS9's endpoint. |
| GY-PA2 | **confirmed:** `architecture/policy_design_case/layer2_s7_delegation_manifest.json` and `architecture/policy_design_case/layer3_gl_s7_delegation_consumer_gate.json` exist. The bounded gateway is `implemented_but_not_orchestrated`. |

Reproduction vocabulary:

```bash
git ls-files | awk '/\.py$/ {all++} /^src\/.*\.py$/ {src++} /^tests\/.*\.py$/ {tests++} END {printf "all=%d src=%d tests=%d other=%d\n", all, src, tests, all-src-tests}'
git grep -l 'HumanDecisionRecord' -- src tests
git grep -n -E 'HumanDecisionRecord|record_human_decision|HUMAN_DECISION_ARTIFACT_KIND' -- src tests
git grep -n -i -E 'access_audit|record_data_access|authorization_audit|AuthorizationAudit'
git grep -n -E 'step_up|StepUp|require_step_up|HIGH_STAKES_PERMISSION_CLASSES'
git grep -n -E 'production-approval|create_run_production_approval|approve_data_promotion'
git grep -n -E 'GY-PA2|layer2_s7_delegation|agent_action_authority'
```

Opening capability is `producer_missing + artifact_missing + bridge_missing +
consumer_missing + surface_missing + semantic_test_missing`. The existing pure
record builder is not a deployed producer. The S7 resolver also equates artifact
signer with human actor; DS9 must split authenticated actor evidence from the
PolicyOS custody signature. `RuntimeDataAccessAuditTrail` is substantial and
append-only; DS9 adds a strict event to it, not another log. `human_review.py`
already evaluates separation/dissent/rubber-stamping but currently conflates a
failed threshold with advisory top-level `pass`.

### Explicit debt ownership

| row | decision and reason |
| --- | --- |
| `ds8-approval-authority` | **CLAIM.** DS9 supplies the bounded producer, artifact/event, bridge, consumer, surface, and semantic negatives. It becomes closure-eligible only after the pre-debt set CC01-CC18 + CC20-CC23 and CC24's closeout-commit readback; the debt write then proves CC19 and final bookkeeping readback completes CC24. |
| `ds8-local-reviewer-note-persistence` | **DECLINE.** Generic notes are case-management/CRM state, not facts needed to keep a PolicyOS signature honest; row remains `absent/unallocated`. |
| `DS20-B scorecard producer provenance` | **CLAIM integration; DECLINE producer.** C00 splits it into `DS20-B-scorecard-provenance-intake-effect` (`DS9/open`) and `DS20-B-scorecard-provenance-producer-trust` (`ops/foreign`). The intake child uses the same pre-debt eligibility rule; only the verified integration/effect child closes. |
| `ds8-signed-public-decision-surface` | **DECLINE.** Internal MACHINE twin is not public rendering; DS12 owns the row. |
| DS5 successor aggregate | **CLAIM DS9 denominator only.** C00 changes 11/27 planless rows to 6/27 and five planless slices to four; all other successors retain owners. |

### Ambiguous and typed-missing inputs

| state | input | exact terms searched / execution rule |
| --- | --- | --- |
| `ambiguous` | authoritative scorecard producer identity and deployment verifier/config owner | `runtime.quality_scorecard`, `policyos.quality_scorecard.v1`, `quality_scorecard_ref`, `producer`, `ProducerInfo`, `signer`, `authority_role`, `provenance_kind`, `scorecard_identity_verified`; C03 adds fail-closed verified intake and never guesses the identity. |
| `producer_missing` | production decision request/mandate | `HumanDecisionRequest`, `build_human_decision_request`, `production_approval`, `mandate_record_ref`, `decision_rights_matrix_ref`; class/builder exist but neither occurs in `runtime/http`. |
| `producer_missing` | principal-to-governance-key binding | `issuer`, `audience`, `subject`, `tenant_id`, `mandate_owner_ref`, `signer_identity`, `principal_grants`, `identity_key`; add strict intake, not values. |
| `producer_missing` | reviewer separation credential | `reviewer_independent`, `separation_of_duty_attested`, `requester_principal`, `producer_principal`, `authorized_subject`, `independence`; unequal IDs prove nothing. |
| `producer_missing` | presentation-policy contract | `right_format_channel`, `renderer_id`, `representation`, `channel_id`, `accessibility_profile`, `presentation_contract`; free text cannot green the gate. |
| `implemented_but_not_orchestrated` | universal PA2 effect intake | `dispatch_agent_external_action`, `produce_agent_action_authority_decision`, `agent_action_authority_scope`; DS14 owns external-effect orchestration. |

The proposed symbols `HumanDecisionPrincipalBinding`,
`ReviewerSeparationCredential`, `HumanDecisionPresentationContract`, and
`ProductionHumanDecisionBasis` have zero source/test/architecture/ops occurrences
at entry. They are explicit inbound contracts, never alleged producers.

## Producer and packet design

Use one run-bound surface; do not add a global case/decision index:

```text
GET  /api/v1/runs/{run_id}/human-decision-gate?source_kind={agent_action_authority|production_approval}[&source_ref=sha256:...][&decision_request_ref=sha256:...]
POST /api/v1/runs/{run_id}/human-decisions
GET  /api/v1/runs/{run_id}/human-decisions?record_ref=sha256:...
GET  /api/v1/runs/{run_id}/human-decisions/review-effectiveness
GET  /api/v1/runs/{run_id}/human-decision-evidence/{artifact_id}/content
```

All GETs use existing `RUNS_REVIEW` with distinct owned-run resource kinds:
`runtime.run.human_decision_gate`, `runtime.run.human_decision_record`,
`runtime.run.human_decision_review_effectiveness`, and
`runtime.run.human_decision_evidence` (the last
also binds the canonical artifact selector). POST alone adds
`runs.human_decisions.create` × `runtime.run.human_decision`, granted only to
ADMIN/ANALYST, and structurally binds body/source/request/basis/exposure digests
before OPA and `StepUpClass.HUMAN_DECISION`. VIEWER/SERVICE/SYSTEM deny.

Every public DTO is strict/frozen and uses `Literal` discriminants.
`HumanDecisionGateResponse` has exactly six phase-ordered statuses:

| precedence | status | meaning |
| ---: | --- | --- |
| 1 | `invalid_source` | supplied bytes/schema/signature/identity/binding are invalid |
| 2 | `artifact_missing` | an exact supplied ref does not resolve |
| 3 | `producer_missing` | no verified producer/ref/trust policy exists |
| 4 | `revalidation_required` | v1/client basis/verifier epoch/session/proof/record/packet is stale or consumed |
| 5 | `blocked` | inputs resolve, but an admissibility predicate is false, including source/request/envelope TTL |
| 6 | `available` | all authority predicates pass |

Evaluate all reasons, then choose the first present status; permutation cannot
change it. GET uses 200 for all typed states; auth remains 401/403. POST uses 201
only after durable v2 readback, 409 for a non-available gate, 422 for malformed
caller DTO, and 503 for audit/CAS/custody non-receipt. `not_established` is a
reason/capability label, never a seventh status.

`source_kind` is required. PA2 requires caller-selected signed `source_ref`; its
embedded request is authoritative and an optional request ref can only constrain
exact match. Production approval resolves run-bound producer refs; absent verified
production request/basis is `producer_missing`, not query 422. Supplied missing
refs are `artifact_missing`; supplied mismatches are `invalid_source`.

The strict inbound schema IDs are
`policyos.runtime.human_decision_principal_binding.v1`,
`policyos.runtime.reviewer_separation_credential.v1`,
`policyos.runtime.human_decision_presentation_contract.v1`, and
`policyos.runtime.production_human_decision_basis.v1`; each uses canonical JSON,
content-bound manifest/ref, configured producer identity, validity, and verifier epoch.

Freeze every gate predicate at admission:

| predicate | authoritative source | green P37 class | failure |
| --- | --- | --- | --- |
| identity / permission | DS20 canonical principal; route+OPA+Rego | `recomputed` | 401/403/invalid |
| PA2 role / mandate | attested principal-key binding + signed S7 contract/request | `independently_reconciled` | producer-missing/invalid/blocked |
| production role / basis | signed `ProductionHumanDecisionBasis` + trust policy | `independently_reconciled` | producer-missing |
| operation / accountability | exact action/resource/basis plus source/request/envelope interval | `recomputed` | blocked |
| currentness | exact v1/client/epoch/session/proof/record/packet at observed time | `recomputed` | revalidation-required |
| right decision / time | signed offered action and requested/due/decidable window | `recomputed` | blocked |
| right person / independence / change | attested binding + separately signed separation credential | `independently_reconciled` | producer-missing/blocked |
| right information | complete exact delivered-content event set | `independently_reconciled` | blocked |
| right format/channel | signed presentation contract + served representation receipt | `independently_reconciled` | producer-missing/blocked |
| scorecard producer | content-bound signature/manifest + deployment trust identity/epoch | `independently_reconciled` | producer-missing/invalid |

No `consumer_asserted`, `institutionally_supplied`, or `not_established` predicate
can green the gate. `human_review.py` is retrospective telemetry, not authority.

Keep artifact kind `runtime_quality.agent_action_human_decision` and the existing
class. Read strict v1
`policyos.policy_design_case.layer2_s7_delegation.v1` as historical and write
strict v2 `policyos.runtime.human_decision_record.v2` under manifest
`polisyos.runtime.HumanDecisionRecord`/`2.0`. V1 and unknown versions cannot
authorize. V2 binds immutable attempt/action key; exact source/request/basis and
predicate receipts; canonical actor; custody signer; action, mode, dissent/reason;
exposure events; rule/schema/verifier versions; requested/observed/decided/
recorded/valid times; reservation ID/version; and separate human-act
`authority_boundary` versus PolicyOS `custody_boundary`. Caller input contains
only bindings, exposure token, existing action, mode, accountability, dissent,
and applicable reason; actor/role/time/rights/provenance/signature fields are forbidden.

Use existing actions: ordinary approval = `approve`; override = `approve` plus
eligible typed `override_reason`; blocking = `reject` plus `blocking_reason`;
`request_evidence`, `revise_scope`, and `escalate` remain unchanged. One
`(tenant_id, governed_action_key)` has at most one live v2 record. A durable
`ControlPlaneStore` table uses SQLite `BEGIN IMMEDIATE`/unique key and a
PostgreSQL conflict-safe transaction. Commit the reservation only after signed
artifact, existing event log, reconciliation, and readback agree. Crash state is
`recovery_required`; signed orphans are historical. Conditional replacement
requires committed expiry. Do not add a mutable latest index.

The gate signs `HumanDecisionExposureSession` under schema
`policyos.runtime.human_decision_exposure_session.v1` over actor/tenant/run/request/
basis, required artifact digests, exact presentation contract and renderer/
channel/representation, validity, and server session ID. It travels only in
`X-PolicyOS-Human-Decision-Exposure`. The dedicated evidence route verifies the
session and exact bytes, preflights signing/trail before response bytes, wraps
ASGI send, and appends a top-level, custody-signed
`HumanDecisionExposureAuditEvent` with schema
`policyos.runtime.human_decision_exposure_event.v1` and discriminant
`runtime.human_decision.exposure` to the existing trail only after final-body
completion. It is a sibling of unchanged `RuntimeAuthorizationAuditEvent`, not a
nested payload. Partial/cancelled/final-append failure creates no completed
receipt, so POST remains blocked. Full content is required unless the signed
presentation contract admits that exact redacted/truncated projection. The event
proves transport completion, never comprehension.

Production approval writes `policyos.production_approval_packet.v2` with manifest
`polisyos.runtime.ProductionApprovalPacket`/`2.0` and persists refs/digests for scorecard, signed production
basis, current human record, and request; validity; rule/schema versions;
verifier epoch; producer identities; limitations; and historical-only-after-
expiry boundary. One concrete final `ProductionApprovalPacketResolver` in
`runtime/quality/approval.py`, installed only by the attested runtime composition
root with real CAS/verifier/trust/clock/epoch, re-resolves the packet and all three
inputs on every operational use. Routes, scientist compiler/quality, NL, canary,
and replay accept packet ref plus that concrete resolver—not a DTO, boolean,
mapping, callback, or structural protocol. Public/generated
`ProductionApprovalCurrentnessProjection` is `projection_only` with
`may_not_use_for`; direct construction or round-trip proves nothing. A generic
single-issuer/callsite guard plus forged/stale/wrong-consumer tests enforce this.

Review effectiveness strictly scans existing `access.jsonl`, exposing total,
parsed, schema-valid, malformed, time-range, retention, and coverage counts. It
deduplicates exact exposure events, joins tenant/actor/run/request/basis/session/
record, then calls existing `build_human_review_calibration_report`. Threshold
and advisory posture remain separate.

## Strangle denominator and scope decision

The raw approval semantic family spans all 6,756 tracked code files (5,589 Py,
463 TS, 658 TSX, 5 JS, 32 MJS, 9 CJS). The complete base command returns 445
lines in 81 paths:

```bash
git grep -n -E 'approval_ready|approval_state|approval_decision|approval_packet_ref|approval_packet|approvalReady|approvalState|approvalDecision|approvalPacketRef|approvalPacket' -- '*.py' '*.ts' '*.tsx' '*.js' '*.mjs' '*.cjs'
```

Disposition is exactly **18 mechanism + 47 generated/test companion + 16
retained candidate/fail-only = 81**. The 18 raw-hit mechanisms, all in C03/C07,
are `apps/runtime-dashboard/src/features/clerk/components/ControlFailurePanel.tsx`;
`src/polisyos/core/contracts/control.py`;
`src/polisyos/runtime/http/openapi_contract.py`;
`src/polisyos/runtime/http/routes/runs.py`;
`src/polisyos/runtime/http/services/control/nl_pipeline.py`;
`src/polisyos/runtime/http/services/control/response_shapes.py`;
`src/polisyos/runtime/http/services/control/run_lifecycle.py`;
`src/polisyos/runtime/http/services/control_plane_store.py`;
`src/polisyos/runtime/quality/__init__.py`;
`src/polisyos/runtime/quality/approval.py`;
`src/polisyos/runtime/quality/external_client_surface.py`;
`src/polisyos/runtime/quality/schema_compat.py`;
`src/polisyos/runtime/quality/status_deficits.py`;
`src/polisyos/runtime/quality/tenant_cas_approval_governance.py`;
`src/polisyos/scientist/artifacts/decision_compiler.py`;
`src/polisyos/scientist/validation/decision_artifact_quality.py`;
`tools/ops_runners/runtime/canary_evidence.py`; and
`tools/ops_runners/runtime/replay_canary_bundle.py`.
The 47 companions are generated
`apps/runtime-dashboard/src/api/types.ts`,
`packages/runtime-api-client/runtimeApiClient.ts`, and
`packages/runtime-api-client/types.ts`, plus all 44 returned test/e2e paths.
The 16 retained paths are
`src/polisyos/runtime/http/services/control/workspace_loop_transition.py`;
`src/polisyos/runtime/quality/assurance_case.py`;
`src/polisyos/runtime/quality/attestation.py`;
`src/polisyos/runtime/quality/diagnostic_events.py`;
`src/polisyos/runtime/quality/invariants.py`;
`src/polisyos/runtime/quality/projection_semantics.py`;
`src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py`;
`src/polisyos/runtime/quality/run_state.py`;
`src/polisyos/runtime/quality/scorecard.py`;
`src/polisyos/scientist/orchestration/engine/executor.py`;
`tools/ci/check_policyos_production_quality_best_in_class.py`; and
`tools/quality/validation/build_policy_design_case_pass2_diagnostics.py`,
`tools/quality/validation/build_policy_design_case_wave35a.py`,
`tools/quality/validation/build_policy_design_case_wave35e.py`,
`tools/quality/validation/check_runtime_quality_schema_compatibility.py`, and
`tools/quality/validation/pass2_wave34_common.py`.
A generic tracked-set test derives current hits, requires one disposition for
each, and fails any new path. Retained-path behavioral tests prove they only
weaken/block or carry candidate/schema vocabulary.

The dashboard has 1,041 tracked TS/TSX files and 172,762 physical lines; DS9 is
not a whole-dashboard rewrite. Its register opening denominator is 18 objects:
13 root entries plus five supplemental authority-presentation findings. Root
rulings: `route-run-governance` and `cache-local-disputes` are `in_scope`;
`cache-review-attention` is `in_scope_tombstone`; `cache-operator-craft`,
`feature-evidence`, `api-op-list-data-promotion-candidates`,
`api-op-approve-data-promotion`, `api-op-reject-data-promotion`, `route-compose`,
`feature-composer`, `api-op-launch-run`, `api-op-get-governance-debug`, and
`derivation-composer-readiness` are `surface_out_of_scope` with their existing
owner/exit signal. The five supplemental findings are
`authority-presentation-badge-bureaucratic-legal-review`,
`authority-presentation-badge-control-approval-quality`,
`authority-presentation-badge-explainability-governance-counts`,
`authority-presentation-badge-governance-issue-severity`, and
`authority-presentation-badge-review-required-aggregate`; they are support work
through one private exhaustive issuer. C07 updates all 18 under the family lock;
no family-complete claim is made beyond them.

```bash
git ls-files ':(glob)apps/runtime-dashboard/**/*.ts' ':(glob)apps/runtime-dashboard/**/*.tsx' |
while IFS= read -r ds9_dashboard_path; do wc -l < "$ds9_dashboard_path"; done |
awk '{files += 1; lines += $1} END {printf "files=%d lines=%d\n", files, lines}'
```

## Red-first semantic tests

Backend identities (real CAS/resolver/middleware paths, never constructor markers):

- `test_human_decision_status_precedence_is_permutation_invariant`
- `test_human_decision_v1_replays_as_revalidation_required`
- `test_human_decision_rubber_stamp_without_mandate_or_evidence_is_blocked`
- `test_human_decision_wrong_role_is_blocked_with_reason`
- `test_human_decision_expired_request_is_blocked_with_reason`
- `test_human_decision_rejects_search_authority_for_data_request`
- `test_human_decision_requires_attested_principal_to_signing_key_binding`
- `test_human_decision_requires_signed_separation_and_change_authority`
- `test_human_decision_unbound_appeal_is_blocked`
- `test_human_decision_free_text_format_requirement_cannot_pass`
- `test_exposure_manifest_only_cross_run_cross_basis_stale_and_replay_block`
- `test_exposure_partial_or_cancelled_send_never_emits_completed_receipt`
- `test_human_decision_requires_fresh_single_use_step_up`
- `test_human_decision_stale_basis_requires_online_revalidation`
- `test_human_decision_concurrent_reservation_has_one_sqlite_winner`
- `test_human_decision_concurrent_reservation_has_one_postgres_winner`
- `test_human_decision_crash_reservation_requires_reconciliation_before_reuse`
- `test_human_decision_persists_custody_signature_not_actor_signature`
- `test_production_approval_requires_matching_live_human_decision_record`
- `test_production_approval_blocks_unverified_scorecard_producer`
- `test_production_approval_step_up_binds_all_three_input_digests`
- `test_currentness_projection_direct_construction_cannot_satisfy_resolver`
- `test_signed_packet_stale_replayed_or_wrong_consumer_is_rejected`
- `test_currentness_projection_round_trip_cannot_feed_operational_consumer`
- `test_production_packet_resolver_has_single_attested_issuer`
- `test_raw_approval_semantic_denominator_classifies_complete_tracked_set`
- `test_canary_publishable_artifact_requires_typed_approval_currentness`
- `test_replay_raw_approval_is_historical_and_cannot_construct_currentness`
- `test_agent_gateway_re_resolves_v2_record_and_currentness_before_effect`
- `test_agent_gateway_pa2_arm_re_resolves_s7_without_production_packet`
- `test_agent_gateway_production_arm_requires_packet_ref_and_concrete_resolver`
- `test_agent_gateway_rejects_cross_arm_fields`
- `test_review_effectiveness_does_not_count_authorization_allow_as_success`
- `test_review_effectiveness_surfaces_malformed_or_retained_audit_gap`
- `test_review_effectiveness_keeps_fail_separate_from_advisory_posture`

Frontend/browser identities:

- `HumanDecisionGate > shows mandate evidence rights and TTL before actions`
- `HumanDecisionGate > surfaces rubber-stamp blocked reason without mutation`
- `HumanDecisionGate > renders wrong-role expired-TTL and cross-authority reasons`
- `HumanDecisionGate > omits contestability control without case and source binding`
- `HumanDecisionGate > stale/offline submit requires online revalidation`
- `CaseWorkspacePage > authorizes before human-decision query and mutation`
- `CaseWorkspacePage MACHINE > export bytes equal the one response bytes`
- `HumanDecisionReviewEffectivenessPanel > allow without record is incomplete`
- `AuthorityStatusPresentation > weakest mixed outcome wins and novelty is unrecognized`
- `DS9 register coverage > all 18 opening objects have one checked disposition`
- `DS9 visual > blocked and available pre-action gates retain readable hierarchy`

At least one test corrupts valid-looking CAS bytes while preserving markers; one
falsifies an exposure declaration; one adds a sibling unsafe route; one replaces
persistence with an allow event; and one seeds stale approved/ref/packet fields
across the complete 81-path family.

Exact first red lanes (C00 records selected count, exit, elapsed, and ceiling):

```bash
uv run pytest tests/unit/runtime/http/test_human_decision_service.py tests/unit/runtime/http/test_human_decision_api.py tests/unit/runtime/http/test_review_effectiveness_projection.py tests/unit/runtime/quality/test_agent_action_authority.py tests/unit/runtime/quality/test_design_axes_mandate_bounded_delegation.py -q
uv run pytest tests/unit/runtime/http/test_runtime_step_up_authz.py tests/unit/runtime/http/test_runtime_rego_authorization_parity.py tests/unit/runtime/http/test_runtime_authorization_access_audit.py tests/unit/runtime/http/test_runtime_api_observability.py tests/unit/runtime/http/test_ds20_seeded_negatives.py -q
corepack pnpm --filter @polisyos/runtime-dashboard exec vitest run src/features/runs/api/useHumanDecisions.test.tsx src/features/runs/domain/humanDecisionPresentation.test.ts src/features/runs/components/HumanDecisionGate.test.tsx src/features/runs/routes/CaseWorkspacePage.test.tsx
```

## Clustered execution plan

Caps count production mechanism paths. Tests, this plan/journal, generated and
release files, register/debt/ledger records, and snapshots are P39 companions
outside the cap. Each implementation cluster gets one implementation and one
widening round; C00/C05 get one transaction round and C08 none: **14 total**.
Second finding of one class triggers P40 widening or a bounded residual/falsifier.

| cluster | property | cap | rounds |
| --- | --- | ---: | ---: |
| C00 | Admit the approved owner plan and pin real red witnesses. | 1 | 1 |
| C01 | Version record/trust contracts; compose existing writer/event; reserve one live action durably. | 10 | 2 |
| C02 | Add strict routes, exact exposure, permission/resource/Rego, pre-OPA bind, and step-up. | 10 | 2 |
| C03 | Bind production approval to record/basis/scorecard, install one attested resolver, and strangle raw derivatives. | 23 | 2 |
| C04 | Derive review effectiveness from existing trail and records. | 5 | 2 |
| C05 | Make supported-entrypoint inventory real, then regenerate frozen ABI and public facade atomically. | 1 | 1 |
| C06 | Land Case Workspace gate, contestability, telemetry, and MACHINE twin. | 12 | 2 |
| C07 | Rebind presentation and adjudicate all 18 register objects. | 8 | 2 |
| C08 | Freeze/review/visual/closeout/readback, then close receipt-backed debts. | 0 | 0 |

### C00 — approved admission and red bind

**Modify (mechanism):** `tools/quality/validation/check_debt_ledger.py`.

**Modify (P39):** `docs/plans/active/DEBT-REGISTER.md`, generated
`docs/plans/active/LEDGER.md`, `tests/repo_quality/tools/test_debt_ledger_checker.py`,
and `docs/plans/active/atlas-slices/DS9-human-decision-integrity.md`
status/base/branch fields. **Add (P39):**
`tests/unit/runtime/http/test_human_decision_service.py`,
`tests/unit/runtime/http/test_human_decision_api.py`,
`tests/unit/runtime/http/test_review_effectiveness_projection.py`,
`apps/runtime-dashboard/src/features/runs/api/useHumanDecisions.test.tsx`,
`apps/runtime-dashboard/src/features/runs/domain/humanDecisionPresentation.test.ts`,
`apps/runtime-dashboard/src/features/runs/components/HumanDecisionGate.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/HumanDecisionGate.a11y.test.tsx`,
and `apps/runtime-dashboard/src/features/runs/components/HumanDecisionReviewEffectivenessPanel.test.tsx`.
**Modify (P39 tests):**
`tests/unit/runtime/quality/test_agent_action_authority.py`,
`tests/unit/runtime/quality/test_design_axes_mandate_bounded_delegation.py`,
`tests/unit/runtime/http/test_runtime_step_up_authz.py`,
`tests/unit/runtime/http/test_runtime_authorization_access_audit.py`,
`tests/unit/runtime/http/test_runtime_api_observability.py`,
`tests/unit/runtime/http/test_runtime_rego_authorization_parity.py`, and
`tests/unit/runtime/http/test_ds20_seeded_negatives.py`; also modify
`apps/runtime-dashboard/src/features/runs/routes/CaseWorkspacePage.test.tsx` to
pin the red MACHINE/authorization behavior before C06.

**Named red:** the pre-lock `DS9-DEBT-BASE-NOT-GREEN` predicate, then
`test_human_decision_wrong_role_is_blocked_with_reason`,
`test_human_decision_expired_request_is_blocked_with_reason`,
`test_human_decision_rejects_search_authority_for_data_request`,
`test_human_decision_rubber_stamp_without_mandate_or_evidence_is_blocked`, and
`CaseWorkspacePage MACHINE > export bytes equal the one response bytes`.
**Acceptance:** on exact main parent, the pre-lock checker has zero source-status
conflicts, denominator mismatches, and ledger drift, with register=55; its strict
exit is ignored because informational classes share that exit. The clean merge
commit's plan-only render drift is then admitted by C00. Under one later
post-approval register lock, plan discovery overrides the static
planless fallback; debts split/claim exactly as measured; DS5 aggregate
recomputes; `PUBLISHED_DENOMINATORS["register"]` and
`test_real_census_replays_published_invariants` move 55→56. The generated ledger
must report published=observed=56, indexed=35, and
exact distribution `ambiguous=1, blocked=7, closed=21, folded=2, foreign=6,
open=19`. Writer/readback/test and the semantic predicate gate pass; strict mode
retains informational exit 1 as architect-owned debt. Release lock before bootstrap. Red failures
reach the real seams and the sole mechanism edit is the owner-census checker.

```bash
uv run python tools/quality/validation/check_debt_ledger.py --write
uv run python tools/quality/validation/check_debt_ledger.py --check
uv run pytest tests/repo_quality/tools/test_debt_ledger_checker.py -q
```

Release the register-family lock, then bootstrap ordinary lanes:

```bash
python3 -m tools.cli workspace bootstrap
python3 -m tools.cli workspace doctor
corepack pnpm install --frozen-lockfile
```

### C01 — record and trusted-source service

**Add:** `src/polisyos/runtime/http/services/human_decision_contracts.py`,
`src/polisyos/runtime/http/services/human_decisions.py`.

**Modify:** `src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py`,
`src/polisyos/runtime/quality/agent_action_authority.py`,
`src/polisyos/runtime/http/services/control/run_lifecycle.py`,
`src/polisyos/runtime/http/container.py`,
`src/polisyos/runtime/http/deployment_security.py`,
`src/polisyos/runtime/http/deployment_security_attestation.py`,
`src/polisyos/runtime/http/security.py`, and
`src/polisyos/runtime/http/services/control_plane_store.py`.

**Modify (P39):** `src/polisyos/runtime/http/services/README.md`,
`tests/unit/runtime/http/test_control_service_di.py`,
`tests/unit/runtime/http/test_runtime_deployment_security.py`,
`tests/unit/runtime/http/test_control_plane_store.py`, and
`tests/unit/runtime/http/test_runtime_postgres_linearizability.py`.
**Add (P39):** `tests/unit/runtime/http/test_runtime_service_container.py`;
reuse the C00 service/quality tests.

**Named red:** `test_human_decision_v1_replays_as_revalidation_required`,
`test_human_decision_persists_custody_signature_not_actor_signature`,
`test_agent_gateway_pa2_arm_re_resolves_s7_without_production_packet`,
`test_agent_gateway_rejects_cross_arm_fields`,
`test_human_decision_concurrent_reservation_has_one_sqlite_winner`,
`test_human_decision_concurrent_reservation_has_one_postgres_winner`, and
`test_human_decision_crash_reservation_requires_reconciliation_before_reuse`.
**Acceptance:** exact
resolve→classify→build→existing CAS/event→verify/readback works; the public narrow
`ControlPlaneService` sink owns its existing private event log; durable reservation
prevents overlap and missing foreign producers remain one typed refusal. The
PostgreSQL fixture adds test-only `POLISYOS_DS9_REQUIRE_PG=1`: absent DSN/driver,
connection, or isolated-schema provisioning fails instead of skipping; the
receipt records DSN redacted, selected > 0, passed = selected, skipped = 0.
The strict `HumanDecisionGatewayAdapterInput` is a `source_kind`-discriminated
union: its PA2 arm cannot carry production-packet fields and its production arm
cannot carry S7-only fields.

```bash
POLISYOS_DS9_REQUIRE_PG=1 POLISYOS_TEST_PG_DSN="$DS9_PG_DSN" uv run --extra test --extra runtime --extra multi-tenant pytest -q -rs tests/unit/runtime/http/test_runtime_postgres_linearizability.py
```

### C02 — HTTP, authz, evidence exposure, and step-up

**Add:** `src/polisyos/runtime/http/routes/human_decisions.py`.

**Modify:** `src/polisyos/runtime/http/app.py`,
`src/polisyos/runtime/http/routes/__init__.py`,
`src/polisyos/runtime/http/permissions.py`,
`src/polisyos/runtime/http/step_up.py`,
`src/polisyos/runtime/http/resource_binding.py`,
`src/polisyos/runtime/http/openapi_contract.py`,
`src/polisyos/runtime/http/dependencies.py`,
`src/polisyos/runtime/http/access_audit.py`, and
`ops/policy/policies/action_permission.rego`.

**Modify (P39):** `src/polisyos/runtime/http/routes/README.md`,
`tests/unit/runtime/http/test_runtime_permission_vocabulary.py`,
`tests/unit/runtime/http/test_runtime_api_authz.py`,
`tests/unit/runtime/http/test_authorization_audience_denials.py`,
`tests/unit/runtime/http/test_runtime_step_up_authz.py`,
`tests/unit/runtime/http/test_runtime_rego_authorization_parity.py`,
`tests/unit/runtime/http/test_runtime_authorization_access_audit.py`,
`tests/unit/runtime/http/test_runtime_api_observability.py`,
`tests/unit/runtime/http/test_artifact_inspector_api.py`, and
`tests/unit/runtime/http/test_artifact_surface_safety.py`; reuse C00 API tests.

**Named red:** `test_human_decision_requires_fresh_single_use_step_up`,
`test_exposure_manifest_only_cross_run_cross_basis_stale_and_replay_block`,
`test_exposure_partial_or_cancelled_send_never_emits_completed_receipt`, and
`test_human_decision_stale_basis_requires_online_revalidation`.
**Acceptance:** live-router introspection
and Rego prove the exact POST conjunction; four GET bindings are exact; only the
dedicated route can append a completed top-level exposure event to the existing
trail after exact-byte delivery. Existing generic artifact reads are unchanged.

### C03 — production approval convergence

**Modify (23):** `src/polisyos/core/contracts/control.py`,
`src/polisyos/runtime/http/production_approval_binding.py`,
`src/polisyos/runtime/http/resource_binding.py`,
`src/polisyos/runtime/http/routes/runs.py`,
`src/polisyos/runtime/http/step_up.py`,
`src/polisyos/runtime/http/openapi_contract.py`,
`src/polisyos/runtime/http/container.py`,
`src/polisyos/runtime/http/deployment_security.py`,
`src/polisyos/runtime/http/deployment_security_attestation.py`,
`src/polisyos/runtime/http/services/control/run_lifecycle.py`,
`src/polisyos/runtime/http/services/control_plane_store.py`,
`src/polisyos/runtime/http/services/control/response_shapes.py`,
`src/polisyos/runtime/http/services/control/nl_pipeline.py`,
`src/polisyos/runtime/quality/approval.py`,
`src/polisyos/runtime/quality/schema_compat.py`,
`src/polisyos/runtime/quality/__init__.py`,
`src/polisyos/runtime/quality/external_client_surface.py`,
`src/polisyos/runtime/quality/status_deficits.py`,
`src/polisyos/runtime/quality/tenant_cas_approval_governance.py`,
`src/polisyos/scientist/artifacts/decision_compiler.py`,
`src/polisyos/scientist/validation/decision_artifact_quality.py`,
`tools/ops_runners/runtime/canary_evidence.py`, and
`tools/ops_runners/runtime/replay_canary_bundle.py`.

**Add (P39):** `tests/repo_quality/tools/test_ds9_approval_semantic_strangle.py`.
**Modify (P39):** `tests/unit/runtime/http/test_control_api.py`,
`tests/unit/runtime/http/test_runtime_step_up_authz.py`,
`tests/unit/runtime/http/test_ds20_seeded_negatives.py`,
`tests/unit/runtime/http/test_control_service_di.py`,
`tests/unit/runtime/http/test_control_plane_store.py`,
`tests/unit/runtime/http/test_runs_api.py`,
`tests/unit/runtime/http/test_workspace_loop_transition.py`,
`tests/unit/runtime/http/test_nl_pipeline_materialization.py`,
`tests/unit/runtime/http/test_runtime_service_container.py`,
`tests/unit/runtime/http/test_runtime_deployment_security.py`,
`tests/unit/runtime/quality/test_schema_compat.py`,
`tests/unit/runtime/quality/test_approval.py`,
`tests/unit/runtime/quality/test_external_client_surface.py`,
`tests/unit/runtime/quality/test_status_deficits.py`,
`tests/unit/runtime/quality/test_tenant_cas_approval_governance.py`,
`tests/unit/scientist/artifacts/test_decision_compiler.py`, and
`tests/unit/scientist/validation/test_decision_artifact_quality.py`; tool tests
`tests/unit/tools/test_canary_evidence.py`,
`tests/unit/tools/test_canary_evidence_authority.py`,
`tests/repo_quality/tools/test_replay_canary_bundle.py`,
`tests/repo_quality/tools/test_policy_design_case_pass2_diagnostics.py`,
`tests/repo_quality/tools/test_policy_design_case_wave35e.py`,
`tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py`, and
`tests/repo_quality/tools/test_runtime_quality_schema_compatibility.py`.

**Named red:** `test_production_approval_requires_matching_live_human_decision_record`,
`test_production_approval_blocks_unverified_scorecard_producer`,
`test_production_approval_step_up_binds_all_three_input_digests`,
`test_agent_gateway_production_arm_requires_packet_ref_and_concrete_resolver`,
`test_currentness_projection_direct_construction_cannot_satisfy_resolver`,
`test_signed_packet_stale_replayed_or_wrong_consumer_is_rejected`,
`test_production_packet_resolver_has_single_attested_issuer`, and
`test_raw_approval_semantic_denominator_classifies_complete_tracked_set`.
**Acceptance:** only the attested concrete resolver can produce operational
currentness; deployment attestation content-binds its issuer/config/epoch and the
container is its sole production installer; packet v2 is self-limiting; every
listed consumer invokes it; retained paths cannot authorize; canary/replay are
draft/historical when unresolved. Deployed production arm stays
`producer_missing` until ops trust exists. `approve_data_promotion` is unchanged.

### C04 — review-effectiveness projection

**Add:** `src/polisyos/runtime/http/services/review_effectiveness.py`.

**Modify:** `src/polisyos/runtime/http/services/human_decision_contracts.py`,
`src/polisyos/runtime/http/routes/human_decisions.py`,
`src/polisyos/runtime/http/compliance.py`, and
`src/polisyos/runtime/quality/human_review.py`.

**Modify (P39):** `tests/unit/runtime/http/test_review_effectiveness_projection.py`,
`tests/unit/runtime/http/test_runtime_authorization_access_audit.py`,
`tests/unit/runtime/http/test_runtime_api_observability.py`, and
`tests/unit/runtime/quality/test_human_review.py`.
**Named red:** `test_review_effectiveness_does_not_count_authorization_allow_as_success`,
`test_review_effectiveness_surfaces_malformed_or_retained_audit_gap`, and
`test_review_effectiveness_keeps_fail_separate_from_advisory_posture`.
**Acceptance:** real JSONL plus persisted records yields explicit coverage and
advisory report; deleting a record while preserving allow lowers completeness;
threshold and posture cannot collapse; no second append path exists.

### C05 — ABI freeze and regeneration token

**Modify (mechanism):** `tools/devx/architecture/guardrails.py`.

**Add (P39):**
`release-fragments/unreleased/2026-08-23-ds9-human-decision-integrity.toml` and
`tests/repo_quality/architecture/test_public_surface_supported_entrypoint_inventory.py`.
**Regenerate (P39):** `schemas/runtime_api_v1.openapi.json`,
`packages/runtime-api-client/types.ts`,
`packages/runtime-api-client/runtimeApiClient.ts`,
`packages/runtime-api-client/runtimeApiClient.js`,
`packages/runtime-api-client/canonicalRuntimeApiClient.ts`,
`packages/runtime-api-client/canonicalRuntimeApiClient.js`,
`apps/runtime-dashboard/src/api/types.ts`,
`architecture/public_surface/inventory.json`, and
`docs/reference/public-surface.md`.
**Modify (P39 tests):**
`tests/unit/runtime/http/test_runtime_api_contract_hardening.py`,
`tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py`,
`tests/repo_quality/tools/test_release_notes_tooling.py`,
`tests/repo_quality/architecture/test_repository_structure_phase7_closeout.py`,
and `tests/repo_quality/architecture/test_public_surface_snapshot.py`.

**Named red:** `test_openapi_exposes_strict_human_decision_unions`,
`test_public_surface_inventory_enumerates_every_supported_entrypoint_facade`,
`test_supported_entrypoint_inventory_resolves_module_and_package_facades`,
`test_supported_entrypoint_inventory_rejects_missing_or_ambiguous_facade`,
`test_runtime_quality_inventory_contains_human_decision_record`, and
`test_public_surface_inventory_corrupt_supported_entrypoint_fails_check`, plus
generated compile, one-output corruption, and two scratch-root probes.
**Acceptance:** the generator derives every declared `supported_entrypoint` and
resolves exactly one façade source from `src/<dotted>.py` or
`src/<dotted>/__init__.py`; missing or simultaneous matches fail. The generic
complete-set test covers both forms, including the existing `ir.api`,
`fabric.api`, and `foundry.api` module façades. JSON/Markdown retain each resolved
source path and name `polisyos.runtime.quality`, its package façade, and
`HumanDecisionRecord`. Removing that export while retaining manifest markers
makes `--check` fail. After C01-C04
product API freeze and C05 generator-test green, hold only the regeneration token
for the four governed writers below,
then release it; scratch1=scratch2=committed for all six client outputs, and the
OpenAPI/public-surface checkers recompute cleanly. No hand edits.

The release fragment carries top-level `compatibility`, `change_class`,
`surface_classification`, `migration`, `api`, `limitations`,
`generated_client_compatibility="requires_regeneration"`, and
`public_surface_inventory_reviewed=true`. Its `[[compatibility_change]]` rows
separately cover the breaking dual-read/write-v2
`public_experimental: polisyos.runtime.quality` Python surface and additive
OpenAPI/runtime-client/dashboard surfaces, each with exact `impact`, `surface`,
`owner`, `version_owner`, `deprecation_window`, `release_note`,
`generated_client_compatibility`, `migration_docs`, and `runbook_docs`.

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
corepack pnpm --filter @polisyos/runtime-api-client run generate
corepack pnpm --filter @polisyos/runtime-dashboard run generate:api
uv run polisyos-tools quality public-surface snapshot --all
```

After releasing the token, run the no-governed-write check/probe block:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
uv run polisyos-tools architecture guardrails check
ds9_probe_root="$(mktemp -d)"
corepack pnpm --filter @polisyos/runtime-api-client run generate -- --output-root "$ds9_probe_root/runtime-client-1"
corepack pnpm --filter @polisyos/runtime-api-client run generate -- --output-root "$ds9_probe_root/runtime-client-2"
corepack pnpm --filter @polisyos/runtime-dashboard run generate:api -- --output-root "$ds9_probe_root/dashboard-1"
corepack pnpm --filter @polisyos/runtime-dashboard run generate:api -- --output-root "$ds9_probe_root/dashboard-2"
for ds9_generated_path in packages/runtime-api-client/types.ts packages/runtime-api-client/runtimeApiClient.ts packages/runtime-api-client/runtimeApiClient.js packages/runtime-api-client/canonicalRuntimeApiClient.ts packages/runtime-api-client/canonicalRuntimeApiClient.js; do
  cmp -- "$ds9_generated_path" "$ds9_probe_root/runtime-client-1/$ds9_generated_path"
  cmp -- "$ds9_probe_root/runtime-client-1/$ds9_generated_path" "$ds9_probe_root/runtime-client-2/$ds9_generated_path"
done
cmp -- apps/runtime-dashboard/src/api/types.ts "$ds9_probe_root/dashboard-1/apps/runtime-dashboard/src/api/types.ts"
cmp -- "$ds9_probe_root/dashboard-1/apps/runtime-dashboard/src/api/types.ts" "$ds9_probe_root/dashboard-2/apps/runtime-dashboard/src/api/types.ts"
```

### C06 — Case Workspace and MACHINE twin

**Add:** `apps/runtime-dashboard/src/features/runs/api/useHumanDecisions.ts`,
`apps/runtime-dashboard/src/features/runs/domain/humanDecisionPresentation.ts`,
`apps/runtime-dashboard/src/features/runs/components/HumanDecisionGate.tsx`, and
`apps/runtime-dashboard/src/features/runs/components/HumanDecisionReviewEffectivenessPanel.tsx`.

**Modify:** `apps/runtime-dashboard/src/features/runs/routes/CaseWorkspacePage.tsx`,
`apps/runtime-dashboard/src/features/runs/components/DisputeRegistryPanel.tsx`,
`apps/runtime-dashboard/src/features/runs/domain/disputes.ts`,
`apps/runtime-dashboard/src/api/queryKeys.ts`,
`apps/runtime-dashboard/src/api/validators.ts`,
`apps/runtime-dashboard/src/shared/ui/dataExport.ts`,
`apps/runtime-dashboard/src/shared/i18n/locales/en.json`, and
`apps/runtime-dashboard/src/shared/i18n/locales/uk.json`.

**Modify (P39):** C00 frontend tests plus
`apps/runtime-dashboard/src/features/runs/routes/CaseWorkspacePage.test.tsx`,
`apps/runtime-dashboard/src/features/runs/routes/CaseWorkspacePage.parity.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/DisputeRegistryPanel.test.tsx`,
`apps/runtime-dashboard/src/features/runs/domain/disputes.test.ts`,
`apps/runtime-dashboard/src/api/hooks/mutationHooks.test.tsx`,
`apps/runtime-dashboard/src/api/validators.test.ts`,
`apps/runtime-dashboard/src/app/offline/authorityLocalState.test.ts`,
`apps/runtime-dashboard/src/shared/ui/dataExport.test.ts`, and
`apps/runtime-dashboard/src/shared/i18n/parity.test.ts`.
**Named red:** `HumanDecisionGate > shows mandate evidence rights and TTL before actions`,
`HumanDecisionGate > omits contestability control without case and source binding`,
`HumanDecisionGate > stale/offline submit requires online revalidation`,
`CaseWorkspacePage > authorizes before human-decision query and mutation`, and
`CaseWorkspacePage MACHINE > export bytes equal the one response bytes`.
**Acceptance:** controls project only the live server packet; the view renders
read-only S7 contract→rights→mandate/envelope pre-action; no local/offline bytes
can create or present authority; DOM equals packet and MACHINE equals captured
response bytes.

### C07 — presentation and register closure

**Add:** `apps/runtime-dashboard/src/shared/ui/AuthorityStatusPresentation.ts`.

**Modify:** `apps/runtime-dashboard/src/app/layout/Header.tsx`,
`apps/runtime-dashboard/src/features/artifacts/bureaucratic/BureaucraticTemplateBadge.tsx`,
`apps/runtime-dashboard/src/features/clerk/components/ControlFailurePanel.tsx`,
`apps/runtime-dashboard/src/shared/ui/compounds/ExplainabilityCard.tsx`,
`apps/runtime-dashboard/src/features/runs/components/GovernanceReport.tsx`,
`apps/runtime-dashboard/src/features/runs/routes/tabs/OverviewTab.tsx`, and
`architecture/atlas_surfaces/check_frontend_disposition_register.py`.

**Modify under lock (P39):** disposition JSON and generated Markdown report.
Exact paths:
`architecture/atlas_surfaces/frontend-disposition-register.json` and
`docs/reference/frontend/atlas-frontend-disposition-register.md`.
**Add (P39 tests):**
`apps/runtime-dashboard/src/shared/ui/AuthorityStatusPresentation.test.ts`,
`apps/runtime-dashboard/src/app/layout/Header.test.tsx`,
`apps/runtime-dashboard/src/features/artifacts/bureaucratic/BureaucraticTemplateBadge.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/GovernanceReport.test.tsx`, and
`apps/runtime-dashboard/src/features/runs/routes/tabs/OverviewTab.test.tsx`.
**Modify (P39 tests):**
`apps/runtime-dashboard/src/features/clerk/components/ControlFailurePanel.test.tsx`
and `apps/runtime-dashboard/src/shared/ui/compounds/ExplainabilityCard.a11y.test.tsx`.
**Named red:** `AuthorityStatusPresentation > weakest mixed outcome wins and novelty is unrecognized`
and `DS9 register coverage > all 18 opening objects have one checked disposition`.
**Acceptance:** private exhaustive
issuer renders unknown values `unrecognized`; ControlFailurePanel consumes only
projection; surgical writer then no-writer/corruption checker accounts for all
13+5 objects. Release lock before C08; debts remain open.

```bash
.venv/bin/python architecture/atlas_surfaces/check_frontend_disposition_register.py --write-ds9-human-decision-integrity
.venv/bin/python architecture/atlas_surfaces/check_frontend_disposition_register.py --write-report
.venv/bin/python architecture/atlas_surfaces/check_frontend_disposition_register.py --check --verify-baseline-source-bytes --corruption-probes
```

### C08 — visual lane, closeout, and debt transition

**Modify (P39):**
`apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts` and
`docs/plans/active/atlas-slices/DS9-human-decision-integrity.md` execution/receipt
fields. **Add (P39):**
`apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/ds9-human-decision-gate-available-chromium-darwin.png`,
`apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/ds9-human-decision-gate-blocked-chromium-darwin.png`, and
`docs/superpowers/journals/2026-08-23-ds9-human-decision-integrity.md`.
**Modify after closeout readback under a fresh lock (P39):**
`docs/plans/active/DEBT-REGISTER.md` and generated
`docs/plans/active/LEDGER.md`.

**Named red:** `DS9 visual > blocked and available pre-action gates retain readable hierarchy`
plus its 320px/200%-zoom, keyboard/focus, long-reason/TTL/provenance, and
public-route-absence variants. **Acceptance:** freeze source/reviews;
under visual lane run one writer derivation and two fresh no-writer comparisons,
then release. Run closeout once, commit/read back full file set, then lock and
only after CC01-CC18 + CC20-CC23 and the pre-debt half of CC24 are evidenced,
close `ds8-approval-authority` and
`DS20-B-scorecard-provenance-intake-effect`; preserve ops,
notes, and DS12 rows. Writer/check/test ledger, commit bookkeeping, read back
again, and require published=observed=56, indexed=33, with `closed=23` and
`open=17` while every other C00 distribution count is unchanged. The debt write
proves CC19; final readback proves CC24; only then check all 24.

Final debt transition repeats C00's exact debt writer/check/test commands; no
other writer runs. First visual red suppresses the second no-writer comparison.

Serialized resources and ceilings:

| resource | cluster / fixed ceiling |
| --- | --- |
| register-family lock | C00, C07, C08 as three separate acquisitions; DS-INFRA-2 119.66s → 240s each |
| regeneration token | C05 governed writers only; DS-INFRA-2 supplies a completed timing for every exact writer, post-release checker, scratch generator, and comparison loop before C05, each frozen at `max(30s, 2x measured)`; absent command receipt blocks C05 |
| visual lane | C08 only; DS-INFRA-2-supplied Playwright ceilings: per-test 90s, invocation 240s; exactly one writer then two no-writers |
| PostgreSQL proof lane | C01; DS-INFRA-2 supplies a reachable disposable database with create/drop-schema privilege and a completed timing before the proof; freeze at `max(60s, 2x measured)`; absent DSN/timing or any skip blocks CC03 |
| focused dashboard | ordinary lane; DS-INFRA-2 14.417s → 30s |
| backend decision/auth | DS-INFRA-2 supplies 300s for each of the two exact C00 backend commands; after each first completion, its later runs freeze at `max(30s, 2x measured)` |
| full closeout | `python3 -m tools.cli workspace ci-parity --skip-browser`; DS-INFRA-2 754.20s → 1,510s |

The register lock, regeneration token, visual lane, and PostgreSQL proof allocation
never co-hold; lint, typecheck, logic tests, and read-only censuses may run in
parallel. No ceiling widens mid-run. Exact visual
commands are the same except the first alone adds `--update-snapshots`:

```bash
CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 corepack pnpm --filter @polisyos/runtime-dashboard exec playwright test --config=playwright.visual.config.ts --project=chromium --grep 'DS9 human decision gate' --workers=1 --timeout=90000 --global-timeout=240000 --update-snapshots
CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 corepack pnpm --filter @polisyos/runtime-dashboard exec playwright test --config=playwright.visual.config.ts --project=chromium --grep 'DS9 human decision gate' --workers=1 --timeout=90000 --global-timeout=240000
CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 corepack pnpm --filter @polisyos/runtime-dashboard exec playwright test --config=playwright.visual.config.ts --project=chromium --grep 'DS9 human decision gate' --workers=1 --timeout=90000 --global-timeout=240000
```

## File Map

| role | planned home |
| --- | --- |
| existing record/action and S7 consumer | `runtime/quality/design_axes/mandate_bounded_delegation.py`, `runtime/quality/agent_action_authority.py` |
| strict DTO/service | `runtime/http/services/human_decision_contracts.py`, `human_decisions.py` |
| persistence/reservation | `services/control_plane_store.py`, composed by `services/control/run_lifecycle.py` |
| custody/trust composition | `deployment_security.py`, attestation, `security.py`, `container.py` |
| HTTP/authz/step-up | `routes/human_decisions.py`, `app.py`, `permissions.py`, `resource_binding.py`, `step_up.py`, Rego |
| exposure/audit | dedicated decision-evidence route and top-level event in existing `access_audit.py` trail |
| production currentness | `production_approval_binding.py`, `routes/runs.py`, `runtime/quality/approval.py`, C03 consumers |
| review telemetry | `services/review_effectiveness.py`, `compliance.py`, `quality/human_review.py` |
| public/generated ABI | OpenAPI, five runtime-client files, dashboard types, generic supported-entrypoint inventory in `tools/devx/architecture/guardrails.py`, and generated inventory/reference |
| workspace/MACHINE | `useHumanDecisions.ts`, presentation domain, gate/panel, `CaseWorkspacePage.tsx` |
| contestability | `DisputeRegistryPanel.tsx`, `domain/disputes.ts` |
| presentation/register | private issuer plus six consumers; disposition checker/register/report |
| governance records | debt checker/register, generated ledger, DS9 journal and this plan |

An unlisted production path requires a stopped, owner-approved cap/path amendment.
Never split one mechanism across commits to fit its cap.

## Issue Codes

| code | result |
| --- | --- |
| `DS9-DECISION-PRODUCER-MISSING` | verified request/mandate absent; typed unavailable |
| `DS9-DECISION-SOURCE-INVALID` | bytes/schema/signature/run/tenant/binding invalid; block |
| `DS9-DECISION-V1-REVALIDATION` | historical readable record cannot authorize |
| `DS9-WRONG-ROLE` / `DS9-AUTHORITY-CROSS-USE` | wrong principal/action authority; block with reason |
| `DS9-DECISION-TTL-EXPIRED` | authoritative interval false; blocked, not stale |
| `DS9-PRINCIPAL-BINDING-MISSING` | canonical binding producer absent |
| `DS9-REVIEW-INDEPENDENCE-MISSING` | separation not established; block |
| `DS9-PRESENTATION-CONTRACT-MISSING` | free text cannot establish format/channel |
| `DS9-MANDATE-NOT-SHOWN` / `DS9-EVIDENCE-NOT-OPENED` | exact completed exposure set absent; block |
| `DS9-EXPOSURE-SESSION-INVALID` | forged/stale/replayed/cross-bound session/event |
| `DS9-RUBBER-STAMP` | mandate/exposure/effective review absent; block and surface |
| `DS9-CONTESTABILITY-UNBOUND` | no case/source binding; omit/reject control |
| `DS9-OFFLINE-REVALIDATION` | no queue/persistence; fresh online gate required |
| `DS9-OVERLAPPING-REISSUE` | one live action reservation already exists |
| `DS9-RESERVATION-RECOVERY-REQUIRED` | partial attempt must reconcile before reuse |
| `DS9-PG-PROOF-NONRECEIPT` | DSN/provisioning/test absent or skipped; CC03 remains open |
| `DS9-SCORECARD-PROVENANCE-MISSING` | foreign trust unverified; production approval blocked |
| `DS9-PRODUCTION-PACKET-STALE` | v1/expired/drifted packet is historical only |
| `DS9-RAW-APPROVAL-NOT-AUTHORITY` | raw field/ref/projection lacks fresh resolver; refuse |
| `DS9-AUDIT-NONRECEIPT` | trail append/read incomplete; no success claim |
| `DS9-AUTHZ-ALLOW-NOT-SUCCESS` | allow lacks persisted record; review incomplete |
| `DS9-MACHINE-BYTE-DRIFT` | export differs from supplying response; fail |
| `DS9-REGISTER-DRIFT` / `DS9-GENERATED-FRESHNESS` | complete set or derived bytes differ; fail |
| `DS9-DEBT-BASE-NOT-GREEN` | pre-C00 main-parent check has a source conflict, denominator mismatch, ledger drift, or register != 55; informational standing rows alone do not fail |

## DS11/DS14 testable handoff

Both consumers receive one immutable commit and receipt bundle: branch/base,
dirty paths, exact command/selected count/exit/elapsed/ceiling, host/runtime,
source/request/record refs+digests, durable event IDs, verifier epoch, response/
DOM/MACHINE hashes, serialized-lane receipt, and carried limitations.

DS11 may consume status, provenance, telemetry, and trust posture only after the
wrong-role/TTL/cross-use negatives, exact exposure join, signed record, offline
refusal, production typed refusal/currentness, and byte parity reproduce. It
receives no public-decision authority.

DS14 receives strict `HumanDecisionGatewayAdapterInput` variants sharing
tenant/run, request ref, record ref/digest, source ref/digest, basis digest,
rule/schema/verifier epoch, valid interval, and expected consumer/operation/
audience. The `source_kind="agent_action_authority"` arm carries the signed S7
request/record/contract/envelope refs and re-resolves that S7/v2 chain before
effect; it forbids a production-packet ref and never invokes the production
resolver. The `source_kind="production_approval"` arm requires a production-
packet ref and the concrete `ProductionApprovalPacketResolver`, then re-resolves
the packet, request, current v2 record, production basis, scorecard trust, and
action before effect; it forbids PA2-only fields. Missing required arm fields,
wrong-arm fields, and cross-use are typed blocked/refused negatives. No
currentness projection/DTO enters either arm; bare ref or UI state is never
authority.

GY-N12 has no current path collision, but its Cluster 4 later performs Decision
Validity owner work followed by Claim Ledger bridging. DS9 must not enter those
paths or a same-owner transaction while that interval is open; pause only the
contended transaction. General perturbation-cascade consumption remains
`bridge_missing` and outside DS9.

## Pattern pass and capability state

| patterns | opening risk | smallest correct closure signal |
| --- | --- | --- |
| P01/P02/P03/P12 | strict class without deployed chain | source→gate→CAS record/event→approval/PA2 consumer→API/UI/MACHINE→negative |
| P04/P05/P09/P15/P26 | boolean approval, server-as-human, hidden rubber stamp | typed precedence, split authority layers, signed exposure, surfaced reason |
| P07/P08 | v1/latest/stale queue/mixed times | dual-read/write-v2, exact basis, revalidation, distinct times |
| P10/P14/P29/P32 | ref/shape/caller provenance as authority | resolve+bind+verifier provenance; corrupt-marker and forged-projection probes |
| P13/P31/P33/P40 | site patches and review ladder | one intake/emission; generated variants; widen on second class finding |
| P35/P36 | guessed spellings/sample denominators | complete tracked walkers and cited M34/M37/S0 findings |
| P37/P38 | request/read/allow/raw-ready proxies | exact signed event join and concrete currentness resolver |
| P39/P41 | record-counted cap/inherited red guess | companions outside cap; exact slice-base replay and disjoint denominator |

At approval the HTTP capability remains `producer_missing + artifact_missing +
bridge_missing + consumer_missing + surface_missing + semantic_test_missing`;
bounded PA2 is `implemented_but_not_orchestrated`; review telemetry is
`consumer_missing`; scorecard admission is `verification_missing`; foreign
principal/separation/presentation/production-basis arms are `producer_missing`
and `not_established`. Approved implementation can close enforcement while those
positive arms stay typed unavailable. No capability is complete before all 24
closure items pass.

## Commit Sequence

1. `docs(atlas): bind DS9 measured slice plan` — this document only.
2. `chore(governance): admit DS9 owner plan and pin red controls` — C00, after approval.
3. `feat(runtime): persist custodied human decision records` — C01.
4. `feat(runtime): enforce human decision routes and step-up` — C02.
5. `fix(runtime): bind production approval to decision integrity` — C03.
6. `feat(runtime): project review effectiveness from access audit` — C04.
7. `fix(architecture): inventory and regenerate DS9 public surfaces` — C05
   generic entrypoint owner plus atomic generated set.
8. `feat(atlas): land accountable human decision workspace` — C06.
9. `fix(atlas): close DS9 authority presentation and register scope` — C07.
10. `docs(atlas): record DS9 verification and consumer handoff` — C08 closeout.
11. `chore(governance): close receipt-backed DS9 debts` — C08 fresh-lock bookkeeping.

Before every commit run `git status -sb` and `git symbolic-ref -q HEAD`. No
merge/push/rebase/stash storage. History remains append-only under repository rules.

## Non-Negotiables

- Before approval: no implementation, writer, regeneration, lock, or visual lane.
- No second audit trail, decision log, shadow record, global index, or client authority cache.
- No caller-authored authority/role/exposure/rights/independence/time/signature.
- No PolicyOS custody signature is presented as the human's signature.
- No v1, fixture signer, request ID, manifest read, ref, projection, or raw field gains authority.
- No missing producer is repaired with a mock, builder replay, inference, coarse role, or local storage.
- No authorization allow is treated as handler/review success; no mutation queues offline.
- No unbound contestability control and no universal `override`/`block` enum.
- No public rendering/signing, generic notes, or promotion-approval convergence.
- No universal GY-PA2 coverage claim; DS14 retains outward orchestration.
- No DV/Claim edit during GY-N12 Cluster 4's owner transaction.
- No unlisted production path, mid-run ceiling widening, hand-edited generated output, or dual resource hold.
- No DS9 edit suppresses or reclassifies the baseline GY debt findings; C00 starts only after their owner supplies a green base.
- No master-plan line-7 edit/revision bump; no merge or push to main.

## Explicit non-closure

1. DS9 does not publicly render or sign decisions; DS12 retains `ds8-signed-public-decision-surface`.
2. DS9 does not persist generic reviewer/case notes; `ds8-local-reviewer-note-persistence` remains unallocated.
3. DS9 does not create the foreign authoritative scorecard producer or operational credentials.
4. DS9 does not invent production requests, principal bindings, presentation contracts, separation credentials, roles, or change mandates; missing arms stay `producer_missing`.
5. DS9 does not orchestrate every external agent action; DS14 owns the outward bridge.
6. DS9 does not administer delegation, mandates, permissions, appeals, notifications, payments, or cases.
7. DS9 does not close DS8's missing run-bound DesignRecord producer.
8. DS9 does not change data-promotion, run-launch, composer, evidence, debug, or readiness producers.
9. DS9 does not make review telemetry causal, independent, or blocking by default.
10. DS9 does not upgrade `access.jsonl` into a hash-chained/tamper-evident ledger.
11. DS9 does not claim authorization allow proves handler success or retention proves historical absence.
12. DS9 does not make pre-action challenge controls an institutional appeal/remedy/reissue system.
13. DS9 does not build a general perturbation cascade; that bridge remains missing.
14. DS9 does not touch GY-N12 Decision Validity/Claim Ledger work or resolve `claim_bridge_pending`.
