# DS9 human-decision integrity execution journal

Date: 2026-08-24
Branch: `codex/ds9-human-decision-integrity-plan`
Approved plan: `b9aec624c`
Execution base: `5a6de66ce123ed56ff7e2d5c7368d4869ed3b141`
Execution-main parent: `715c25f1e48859a6b1b932b3db81199c8beeadfc`

This is the durable execution receipt for C00-C08. It records implementation
and verification on the attached branch; it is not a merge or publication
claim. Root was the only writer. No merge, push, rebase, stash storage, master-
plan line-7 edit, or GY Decision Validity/Claim owner edit occurred.

## Admission gate

C00 judged the debt gate by its four declared predicates, not the checker's
composite exit:

- `source_status_conflict = 0`;
- every `*_denominator_mismatch = 0`;
- `ledger_render_drift = 0`;
- register denominator `= 55`.

All four were green on `715c25f1e`. The ten
`register_supplies_missing_standing` and one
`register_withholds_source_standing` results were retained as informational
source complementarity. They were neither suppressed nor relabelled.

## Cluster ledger

Production mechanism paths are counted once in the global ceiling. Reopened
mechanisms appear in the observed column but do not increase the cumulative
unique count. Tests, plans, this journal, registers/reports, generated
companions, release records, and visual snapshots are P39 companions.

| cluster | commit | declared / observed mechanism paths | new unique / cumulative | widening rounds / cumulative | terminal receipt |
| --- | --- | ---: | ---: | ---: | --- |
| C00 | `76be63c1ffd0cd52be16556d192ee15fe33b7d7c` | 1 / 1 | 1 / 1 | 1 / 1 | debt predicates green; writer/check/test admitted the owner plan |
| C01 | `3b1a87fd04b16db4de9dd60e60f620465538e15a` | 10 / 10 | 10 / 11 | 2 / 3 | focused backend green; SQLite CAS green; strict PostgreSQL lane retained as a non-receipt |
| C02 | `587de35992a716cfed09f78d78de031978da2b37` | 12 / 16 | 12 / 23 | 2 / 5 | 416 focused tests green in the frozen wave; signed-input and exact-exposure falsifiers green |
| C03 | `20467fceb2a2501f77f4fc7e1c31c8f3d0c8b67c` | 23 / 24 | 14 / 37 | 2 / 7 | HTTP 226, quality 104, tools 96 selected with one declared staged skip, bridge 185: green |
| C04 | `09d6b8d1aea57322b20e5378055e7ceca30f59a5` | 5 / 6 | 2 / 39 | 1 / 8 | 109 focused tests green; no second trail |
| C05 | `17a36756c46059a3ebd0ef1a3749b942dd1b04d9` | 1 / 11 | 3 / 42 | 1 / 9 | governed writers complete; runtime contract green; scratch1=scratch2=committed for all six client outputs |
| C06 | `9791abd99bd582e584291292db926f4944884d6d` | 12 / 12 | 12 / 54 | 2 / 11 | frontend lanes 28/28 and 102/102 green; dashboard typecheck green |
| C02 correction | `b7006c2b2bdbf49a96d1d0b88030cda2388b008e` | 0 / 1 reopen | 0 / 54 | 0 / 11 | production-gate GET re-bound to its signed basis; narrowing only |
| C07 | `04ec7914e0dc3fe861b1bb53dd2712c26a7756f7` | 8 / 10 | 8 / 62 | 1 / 12 | 18/18 objects adjudicated; corruption-probe checker green in 176.59 s |
| C08 | pending closeout commit | 0 / 7 | 3 / **65 of 78** | 1 / **13 of 18** | source frozen; reviews green; visual writer and comparison 4/4; closeout receipts below |

The safe-GET round in C08 is the only C08 widening. Binding an unbound value,
removing a forgeable seam, making the safe-route contract structural, and
closing visual overflow were narrowings and consumed no round.

## Exact production mechanism path sets

Paths below are relative to `policy-engine/` and are the complete observed
production mechanism sets for their clusters.

### C00

- `tools/quality/validation/check_debt_ledger.py`

### C01

- `src/polisyos/runtime/http/container.py`
- `src/polisyos/runtime/http/deployment_security.py`
- `src/polisyos/runtime/http/deployment_security_attestation.py`
- `src/polisyos/runtime/http/security.py`
- `src/polisyos/runtime/http/services/control/run_lifecycle.py`
- `src/polisyos/runtime/http/services/control_plane_store.py`
- `src/polisyos/runtime/http/services/human_decision_contracts.py`
- `src/polisyos/runtime/http/services/human_decisions.py`
- `src/polisyos/runtime/quality/agent_action_authority.py`
- `src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py`

### C02

- `ops/policy/policies/action_permission.rego`
- `src/polisyos/runtime/http/access_audit.py`
- `src/polisyos/runtime/http/app.py`
- `src/polisyos/runtime/http/authorization.py`
- `src/polisyos/runtime/http/authz_middleware.py`
- `src/polisyos/runtime/http/dependencies.py`
- `src/polisyos/runtime/http/openapi_contract.py`
- `src/polisyos/runtime/http/permissions.py`
- `src/polisyos/runtime/http/resource_binding.py`
- `src/polisyos/runtime/http/routes/__init__.py`
- `src/polisyos/runtime/http/routes/human_decisions.py`
- `src/polisyos/runtime/http/services/human_decision_contracts.py` (C01 reopen)
- `src/polisyos/runtime/http/services/human_decisions.py` (C01 reopen)
- `src/polisyos/runtime/http/step_up.py`
- `src/polisyos/runtime/quality/agent_action_authority.py` (C01 reopen)
- `src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py` (C01 reopen)

### C03

- `src/polisyos/core/contracts/control.py`
- `src/polisyos/runtime/http/container.py` (reopen)
- `src/polisyos/runtime/http/deployment_security.py` (reopen)
- `src/polisyos/runtime/http/deployment_security_attestation.py` (reopen)
- `src/polisyos/runtime/http/production_approval_binding.py`
- `src/polisyos/runtime/http/resource_binding.py` (reopen)
- `src/polisyos/runtime/http/routes/human_decisions.py` (CC-required reopen)
- `src/polisyos/runtime/http/routes/runs.py`
- `src/polisyos/runtime/http/services/control/nl_pipeline.py`
- `src/polisyos/runtime/http/services/control/response_shapes.py`
- `src/polisyos/runtime/http/services/control/run_lifecycle.py` (reopen)
- `src/polisyos/runtime/http/services/human_decision_contracts.py` (reopen)
- `src/polisyos/runtime/http/services/human_decisions.py` (reopen)
- `src/polisyos/runtime/http/step_up.py` (reopen)
- `src/polisyos/runtime/quality/__init__.py`
- `src/polisyos/runtime/quality/agent_action_authority.py` (reopen)
- `src/polisyos/runtime/quality/approval.py`
- `src/polisyos/runtime/quality/external_client_surface.py`
- `src/polisyos/runtime/quality/schema_compat.py`
- `src/polisyos/runtime/quality/status_deficits.py`
- `src/polisyos/scientist/artifacts/decision_compiler.py`
- `src/polisyos/scientist/validation/decision_artifact_quality.py`
- `tools/ops_runners/runtime/canary_evidence.py`
- `tools/ops_runners/runtime/replay_canary_bundle.py`

### C04

- `src/polisyos/runtime/http/access_audit.py` (reopen)
- `src/polisyos/runtime/http/routes/human_decisions.py` (reopen)
- `src/polisyos/runtime/http/services/human_decision_contracts.py` (reopen)
- `src/polisyos/runtime/http/services/human_decisions.py` (reopen)
- `src/polisyos/runtime/http/services/review_effectiveness.py`
- `src/polisyos/runtime/quality/human_review.py`

### C05

- `architecture/public_surface/contract.toml`
- `src/polisyos/runtime/http/openapi_contract.py` (reopen)
- `src/polisyos/runtime/http/routes/human_decisions.py` (reopen)
- `src/polisyos/runtime/http/routes/runs.py` (reopen)
- `src/polisyos/runtime/http/services/human_decision_contracts.py` (reopen)
- `src/polisyos/runtime/http/services/human_decisions.py` (reopen)
- `src/polisyos/runtime/quality/approval.py` (reopen)
- `src/polisyos/scientist/artifacts/decision_compiler.py` (reopen)
- `src/polisyos/scientist/validation/decision_artifact_quality.py` (reopen)
- `tools/devx/architecture/guardrails.py`
- `tools/ops_runners/runtime/generate_runtime_client.py`

### C06

- `apps/runtime-dashboard/src/api/queryKeys.ts`
- `apps/runtime-dashboard/src/api/validators.ts`
- `apps/runtime-dashboard/src/features/runs/api/useHumanDecisions.ts`
- `apps/runtime-dashboard/src/features/runs/components/DisputeRegistryPanel.tsx`
- `apps/runtime-dashboard/src/features/runs/components/HumanDecisionGate.tsx`
- `apps/runtime-dashboard/src/features/runs/components/HumanDecisionReviewEffectivenessPanel.tsx`
- `apps/runtime-dashboard/src/features/runs/domain/disputes.ts`
- `apps/runtime-dashboard/src/features/runs/domain/humanDecisionPresentation.ts`
- `apps/runtime-dashboard/src/features/runs/routes/CaseWorkspacePage.tsx`
- `apps/runtime-dashboard/src/shared/i18n/locales/en.json`
- `apps/runtime-dashboard/src/shared/i18n/locales/uk.json`
- `apps/runtime-dashboard/src/shared/ui/dataExport.ts`

The post-C06 C02 correction reopened only
`src/polisyos/runtime/http/routes/human_decisions.py`.

### C07

- `apps/runtime-dashboard/src/app/layout/Header.tsx`
- `apps/runtime-dashboard/src/features/artifacts/bureaucratic/BureaucraticTemplateBadge.tsx`
- `apps/runtime-dashboard/src/features/clerk/components/ControlFailurePanel.tsx`
- `apps/runtime-dashboard/src/features/runs/components/GovernanceReport.tsx`
- `apps/runtime-dashboard/src/features/runs/components/HumanDecisionGate.tsx` (reopen)
- `apps/runtime-dashboard/src/features/runs/components/HumanDecisionReviewEffectivenessPanel.tsx` (reopen)
- `apps/runtime-dashboard/src/features/runs/routes/tabs/OverviewTab.tsx`
- `apps/runtime-dashboard/src/shared/ui/AuthorityStatusPresentation.ts`
- `apps/runtime-dashboard/src/shared/ui/compounds/ExplainabilityCard.tsx`
- `architecture/atlas_surfaces/check_frontend_disposition_register.py`

### C08

- `apps/runtime-dashboard/src/features/runs/api/useCaseInspection.ts` (new)
- `apps/runtime-dashboard/src/features/runs/api/useHumanDecisions.ts` (reopen)
- `apps/runtime-dashboard/src/features/runs/components/HumanDecisionGate.tsx` (reopen)
- `apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts` (new)
- `src/polisyos/runtime/http/authorization.py` (reopen)
- `src/polisyos/runtime/http/routes/governed_projections.py` (new)
- `src/polisyos/runtime/http/routes/runs.py` (reopen)

No mechanism path lies outside `policy-engine/`. The exact GY owner-module
intersection is zero for `core/contracts/decision_validity.py`,
`scientist/validation/decision_validity.py`, and
`scientist/evidence/claims/**`.

## C08 approved path amendments

1. `useCaseInspection.ts` is required by CC09/CC17/CC21. It strips only the
   canonical DS9-owned query keys at the case-inspection consumer boundary,
   preserving all other raw bytes, duplicate order, and malformed encodings.
   Stripping `location.search` in the page would also delete the signed gate and
   appeal bindings; loosening the backend would expand the authority surface.
2. `publicationPacket.ts` is required by CC21 and protects CC17's internal-only
   boundary. The real public-route-absence negative must import the existing
   signed packet builder. Hard-coding a URL or reproducing the signer would be a
   marker test/second signer; the direct quantity leaf avoids the UI/i18n barrel
   in Playwright Node without changing packet behavior.
3. `routes/governed_projections.py` is required by CC05/CC11/CC21. The generic
   safe-route invariant found one sibling guarded GET whose bodyless semantics
   were undeclared. Exempting that route or defaulting all safe routes bodyless
   would reopen the bypass. The route-local declaration shares the one safe-GET
   widening round with `routes/runs.py`.

The four reopens are also closure-bound: `useHumanDecisions.ts` owns the one
query-key set; `HumanDecisionGate.tsx` closes the long-content overflow
falsifier; `authorization.py` installs the generic structural invariant; and
`routes/runs.py` explicitly binds the two real bodyless reads. Only the last
safe-read declaration widens permitted behavior; the other repairs are
narrowings.

## Signed-input refusal receipt

`/tmp/ds9-c08-signed-input-falsifiers-final.log` completed 7/7 in 3.33 s under
the 300 s ceiling, uptime `23:46 up 13:59` to `23:46 up 14:00`. The falsifiers
remove or invalidate each signed authority input and receive a typed refusal:

- unsigned principal binding -> `invalid_source` /
  `DS9-DECISION-SOURCE-INVALID`;
- unsigned reviewer separation -> `invalid_source` /
  `DS9-DECISION-SOURCE-INVALID`;
- unsigned action source -> `invalid_source`, with neither continuation nor
  submission;
- unsigned mandate/delegation contract -> `invalid_source`;
- unsigned presentation contract -> `invalid_source`;
- unsigned exposure session -> `invalid_source`, with neither continuation nor
  submission;
- unsigned exposure events -> `blocked` /
  `DS9-EVIDENCE-NOT-OPENED`.

The companion mismatch falsifiers also prove a signed-but-wrong principal
issuer produces `DS9-PRINCIPAL-SIGNING-KEY-MISMATCH`, and a signed reviewer
credential lacking change authority produces
`DS9-REVIEWER-INDEPENDENCE-CHANGE-AUTHORITY-MISSING`. Identifier inequality is
never used as a substitute.

## C08 verification receipts

- Final Python delta: 8/8 green in 45 s wall-clock,
  `/tmp/ds9-c08-final-python-delta.log`, uptime `23:56 up 14:09` ->
  `23:57 up 14:10`. It includes the guarded-safe invariant plus all seven CC08
  command shapes: reasoned override is
  `approve + override_reason`, reasoned blocking is
  `reject + blocking_reason`, and six cross/reasonless variants fail.
- Final frontend semantic freeze: 5 files, 27 tests, 16.47 s, uptime
  `23:30 up 13:44` -> `23:31 up 13:44`, green.
- Final dashboard static lane: typecheck plus changed-path ESLint, uptime
  `23:30 up 13:44` -> `23:32 up 13:45`, green.
- Guarded-safe route tests, query-byte tests, targeted Python tests, and Ruff
  completed green. `AuthorityStatusPresentation` re-read after removing an
  incidental `approval_ready` fixture label: 5/5 green.
- Visual writer: four real-route cases passed in 52.6 s, uptime
  `23:27 up 13:40` -> `23:28 up 13:41`. Available snapshot SHA-1 is
  `44b983c428592a9e84d87501b98be4650ddd06c6`; blocked snapshot SHA-1 is
  `5782f1863575094d607d0b6d37158b37f7e08aef`.
- Fresh no-writer visual comparison: 4/4 in 53.4 s, uptime
  `23:28 up 13:41` -> `23:29 up 13:42`; both hashes unchanged. Earlier visual
  writers were invalidated by post-review source changes and are not closure
  receipts. The first visual red suppressed the redundant second comparison.
- OpenAPI was regenerated after the guarded-safe contract change; the five
  runtime-client files and dashboard type file reproduced byte-for-byte from
  two fresh scratch roots. Runtime API contract check passed.
- Approval strangle: 3/3 in 63.78 s, uptime `23:40 up 13:54` ->
  `23:41 up 13:55`; independently enumerated
  `18 mechanisms + 47 companions + 16 retained = 81`, no unclassified and no
  classified-but-untracked path. Raw-path-list SHA-256 excluding the verifier is
  `f19e9a283e46fa05fb97b2adce24c74ecf55a595596145d3e47996afcc3b33f2`.
- Full closeout `python3 -m tools.cli workspace ci-parity --skip-browser`
  completed failure under its 1,510 s ceiling, uptime `23:30 up 13:44` ->
  `23:33 up 13:46`, solely because
  `docs/reference/ir/schema-catalog.md` was already out of date. Runtime OpenAPI,
  frontend contracts, lockfiles, and browser doctor checks were green.
- P41 replay exported exact execution base `5a6de66ce` and ran the same schema
  generator from base sources. It reproduced the same catalog drift in 29 s,
  uptime `23:39 up 13:52` -> `23:39 up 13:52`. The complete input denominator
  (`src/polisyos/ir/**`, ABI registry, snapshots, both generators, and both
  reference targets) has zero DS9 changed paths. The schema failure is inherited,
  not a DS9 green or a DS9 repair.

The tracked basedpyright/deep-import baseline was restored exactly to `HEAD`
after its receipt. Architecture generated freshness is green; the six
`deep-import-baseline-stale` edges remain the user's named inherited debt.

## C07 disposition receipt

The complete opening denominator was adjudicated once:

- `in_scope`: `route-run-governance`, `cache-local-disputes`;
- `in_scope_tombstone`: `cache-review-attention`;
- `surface_out_of_scope`: `cache-operator-craft`, `feature-evidence`,
  `api-op-list-data-promotion-candidates`, `api-op-approve-data-promotion`,
  `api-op-reject-data-promotion`, `route-compose`, `feature-composer`,
  `api-op-launch-run`, `api-op-get-governance-debug`, and
  `derivation-composer-readiness`;
- support through the private exhaustive issuer, with producer/bridge debt
  retained: `authority-presentation-badge-bureaucratic-legal-review`,
  `authority-presentation-badge-control-approval-quality`,
  `authority-presentation-badge-explainability-governance-counts`,
  `authority-presentation-badge-governance-issue-severity`, and
  `authority-presentation-badge-review-required-aggregate`.

The writer and no-writer/corruption checker accounted for all 18. None was
silently closed, removed, or promoted to family-complete.

## Closure-contract evidence before debt bookkeeping

| item | evidence |
| --- | --- |
| CC01 | approval, four-predicate C00 gate, attached-branch/staging/readback guards at every committed boundary |
| CC02 | strict `source_kind` union and complete status-permutation semantic test |
| CC03 | v2 dual read/write, durable SQLite one-winner CAS; PostgreSQL explicitly residual |
| CC04 | verified human-act input is distinct from PolicyOS custody signature; substitution negatives green |
| CC05 | frozen P37 predicate classes plus declaration/property falsifiers and concrete resolver |
| CC06 | wrong-role, expired-TTL, and search-for-data-request negatives block with stable reason and no record |
| CC07 | exact delivered bytes -> completed existing-trail exposure; cross-bound/stale/partial/replay negatives green |
| CC08 | focused reasoned override/blocking property receipt above; no new universal enum |
| CC09 | unbound appeal omitted/rejected; query-bound real-route visual proves bound navigation |
| CC10 | independently signed principal binding and reviewer separation required; removal falsifiers above |
| CC11 | one permission/resource/Rego/step-up/single-use conjunction; guarded-safe body contract structural |
| CC12 | offline/stale returns revalidation-required, no persistence and no mutation queue |
| CC13 | production approval calls the deployment-attested resolver over basis, scorecard, and current v2 record |
| CC14 | production approval and data promotion remain distinct; missing foreign trust stays typed unavailable |
| CC15 | review effectiveness scans existing `access.jsonl` only and reports malformed/retention/join coverage |
| CC16 | threshold result and advisory posture remain separate; rubber stamp cannot present pass/effective |
| CC17 | DOM and internal MACHINE export project one captured response; public-route absence visual is green |
| CC18 | all 13 root objects plus five supplemental findings adjudicated exactly once |
| CC19 | pending the post-closeout fresh-lock debt transition and its readback |
| CC20 | OpenAPI + five client outputs + dashboard types + supported-entrypoint inventory regenerated/reproduced |
| CC21 | named semantic, corruption, a11y, 320 px/200%-zoom, keyboard, long-content and visual receipts green |
| CC22 | immutable DS11 bundle below exposes status/provenance/telemetry/exact bytes, never public authority |
| CC23 | DS14 strict PA2/production adapter arms re-resolve their concrete sources and reject cross-arm fields |
| CC24 | pre-debt half green: no concurrent DV/Claim owner path and C00-C07 commits re-read; final two commit readbacks pending |

## DS11 and DS14 handoff

DS11 receives the immutable branch/base, exact status/reason precedence,
P37 provenance classes, review-coverage telemetry, exact exposure joins,
response/MACHINE equality, snapshot hashes, and the signed-input refusal list.
It receives no public-decision authority and must preserve the telemetry scope
`retained_trail_bytes_only` with provenance `institutionally_supplied`.

DS14 receives `HumanDecisionGatewayAdapterInput` as a strict `source_kind`
union. The PA2 arm re-resolves S7/v2 without a production packet; the production
arm requires the packet ref and concrete deployment-attested resolver. Both
re-resolve live inputs immediately before effect and reject missing required,
wrong-arm, stale, wrong-consumer, and cross-use fields. A DTO/projection round
trip can never be supplied as currentness.

## Residuals and out-of-focus findings

1. **PostgreSQL concurrency remains unproven.** Owner: `DS-INFRA-2`. The strict
   C08 run completed with six `DS9-PG-PROOF-NONRECEIPT` setup errors because no
   DSN exists; it was not called green. Discharge with:

   ```bash
   POLISYOS_DS9_REQUIRE_PG=1 POLISYOS_TEST_PG_DSN="$DS9_PG_DSN" uv run --extra test --extra runtime --extra multi-tenant pytest -q -rs tests/unit/runtime/http/test_runtime_postgres_linearizability.py
   ```

   Closure requires selected > 0, passed = selected, skipped = 0 against a
   disposable PostgreSQL database with create/drop-schema privilege.
2. **IR schema-catalog freshness is inherited and outside DS9.** It is already
   carried by the DS5 `abi-schema-snapshots` family, successor
   `abi-schema-reference-catalog-reconciliation`; canonical generated-artifact
   ownership is `team-polisyos`. This run is a P40 worked example, not a
   duplicate debt row. Discharge with
   `uv run --extra ml polisyos-tools diagnostics gen-schema --check`, which must
   exit zero from committed sources.
3. **`decision-validity-fixed-temp-concurrency` is new and out of scope.** Both
   authoritative visual runs produced the same fixed-`.tmp` atomic-replace
   collision at `scientist/validation/decision_validity.py:190`. It is distinct
   from GY-DEF23's caller-supplied predicate class. Owner: Scientist Decision
   Validity / GY-N12 Cluster 4 Task 4.4. Final bookkeeping registers it
   `open_unmerged` on `codex/ds9-human-decision-integrity-plan`; a landing-time
   standing transition, not DS9, may retype it `open`.
   Closure requires
   `tests/unit/scientist/validation/test_decision_validity_service.py::test_concurrent_same_packet_persistence_has_no_fixed_temp_collision`,
   the GY Task 4.4 declared suite, and the exact zero-retry DS9 visual no-writer
   command all green, with both concurrent callers returning the same valid
   persisted model and zero `FileNotFoundError`/partial/lost state.

No DS9 capability is left unimplemented. The three items above are explicit
residual/inherited/foreign-owner receipts, not hidden green claims.

## Final bookkeeping readback

Pending the C08 closeout commit, fresh register-family lock, debt writer/check/
test, bookkeeping commit, and final documentation readback. This section is
updated only after those commits exist on the attached branch.
