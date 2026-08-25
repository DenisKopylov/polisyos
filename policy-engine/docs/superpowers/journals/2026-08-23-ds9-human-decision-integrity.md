# DS9 human-decision integrity execution journal

Date: 2026-08-25
Branch: `codex/ds9-human-decision-integrity-plan`
Approved plan: `b9aec624c`
Execution base: `5a6de66ce123ed56ff7e2d5c7368d4869ed3b141`
Execution-main parent: `715c25f1e48859a6b1b932b3db81199c8beeadfc`

This is the durable execution receipt for C00-C08. It records implementation
and verification on the attached branch; it is not a merge or publication
claim. Root was the only writer. No merge, push, rebase, stash storage, master-
plan line-7 edit, or GY Decision Validity/Claim owner edit occurred after the
authorized execution-base merge. No merge or push to `main` occurred.

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
| C08 | `8697fe1aaf190a56eaa03c0bdd9916480d191ed2` + bookkeeping receipts below | 0 / 8 | 3 / **65 of 78** | 1 / **13 of 18** | source frozen; reviews green; visual writer/comparison 4/4; debt transition and exhaustive signed-input falsifiers read back |

The safe-GET round in C08 is the only C08 widening. Binding an unbound value,
removing a forgeable seam, making the safe-route contract structural, and
closing visual overflow were narrowings and consumed no round.

## Per-cluster ceiling and uptime receipts

The durable logs below are the terminal cluster receipts. `not_established`
means the run completed but that metadata was not written durably; it is never
back-filled from commit time or a later guess.

| cluster | terminal receipt | fixed ceiling | elapsed | uptime pair |
| --- | --- | ---: | ---: | --- |
| C00 | four admission predicates plus writer/check/test; final prose correction `/tmp/ds9-final-register-prose-{writer,check,tests}.log` | register 240s; backend lanes 300s | original not established; final writer 1.82s, check 1.01s, tests 6.73s | original not established; final `0:37 up 14:50` → `0:38 up 14:51` |
| C01 | `/tmp/ds9-c01-final-focused-refrozen.log`: 181 pass, six PostgreSQL skips; strict lane is a named non-receipt | 300s backend; PostgreSQL dynamic ceiling not established without DSN | exact focused elapsed not established | `12:29 up 2:42` → `12:30 up 2:43`; strict PG `12:30 up 2:43` → `12:31 up 2:44` |
| C02 | `/tmp/ds9-c02-final-post-format-wave-1.log`: 416 pass; correction `/tmp/ds9-c02-production-get-full-tests-final.log`: 63 pass | 300s each | exact elapsed not established | `15:31 up 5:44` → `15:34 up 5:47`; correction `20:41 up 10:54` → `20:43 up 10:56` |
| C03 | parallel final HTTP 226, quality 104, bridge 185, tools 96 selected/one declared skip; strangle 3/3 | 300s each; strangle 60s | 77s / 30s / 77s / 85s; strangle 32s | all start `17:21 up 7:34`; finish `17:21 up 7:34` or `17:22 up 7:35`; strangle `17:23 up 7:36` → same minute |
| C04 | `/tmp/ds9-c04-final-focused.log`: 109 pass | 120s | 52s | `17:56 up 8:09` → `17:57 up 8:10` |
| C05 | four writers, runtime contract, and two scratch roots; all byte-stable | DS-INFRA-2 formula `max(30s, 2× measured)`; resolved numeric values not durably recorded (`not_established`, a process-metadata residual) | OpenAPI 34s, clients 3s, dashboard 4s, public-surface 13s, contract suite 112s, runtime contract 61s, scratch roots 8s each | public surface `18:43 up 8:57` → `18:44 up 8:57`; other writers `19:08 up 9:22` → `19:09 up 9:22`; contract `19:10 up 9:23` → `19:12 up 9:25`; scratch roots remain in `19:12 up 9:25` minute |
| C06 | final frontend lanes 28/28 and 102/102; typecheck and lint green | focused tests 30s; static-command ceilings not durably recorded (`not_established`) | tests 4.71s / 8.18s; exact static elapsed not established | tests `20:29 up 10:42` → same minute; typecheck `20:29 up 10:42` → `20:30 up 10:43`; lint → `20:31 up 10:44` |
| C07 | writer replay 18 objects; corruption checker; frontend 36 pass; typecheck | 240s / 240s / 30s / 30s | 54.12s / 176.59s / 8.13s / 21.84s | writer `22:19 up 12:32` → `22:20 up 12:33`; checker `22:21 up 12:34` → `22:23 up 12:37`; frontend and typecheck `22:21 up 12:34` → same minute |
| C08 | Python delta, frontend/static, visual writer/comparison, strangle, CI parity, debt family, signed-input falsifiers | 300s backend; 30s focused frontend; visual 240s invocation/90s test; strangle 120s; CI 1,510s; debt 240s | see detailed C08 section; final honest strangle 72.07s, full service 86.40s, Ruff 0.19s | detailed pairs below; final post-P33 lanes `0:42 up 14:55` → `0:43 up 14:56` |

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

### Final bookkeeping (C00 mechanism reopen)

- `tools/quality/validation/check_debt_ledger.py` (CC19 denominator 56→58;
  zero new unique paths and zero widening rounds)

No mechanism path lies outside `policy-engine/`. The exact GY owner-module
intersection is zero for `core/contracts/decision_validity.py`,
`scientist/validation/decision_validity.py`, and
`scientist/evidence/claims/**`.

## Exact committed path-set readback

For every row, the exact full path set (mechanisms plus P39 companions) is the
newline-delimited output of
`git diff-tree --no-commit-id --name-only -r <commit> | LC_ALL=C sort` from the
repository root. The SHA-256 is over that output with one trailing newline.
Reading the immutable commit back produced the following counts and digests;
comparison with the composed cluster fence found zero paths outside it.

| boundary | commit | full paths | sorted path-set SHA-256 |
| --- | --- | ---: | --- |
| approved plan | `b9aec624c259195e7627ec90102723a6d645da2c` | 1 | `c3bb72985fd562205d5a22b2ab1a42e82d1f8a27dcd346b12c1c9758a86a448b` |
| C00 | `76be63c1ffd0cd52be16556d192ee15fe33b7d7c` | 21 | `b86e9bf5d1271d6d087c53febd08a2a88bd57c56507dfe4cf6148d329b6944c5` |
| C01 | `3b1a87fd04b16db4de9dd60e60f620465538e15a` | 19 | `6f33d50ae82b83426920fd4fad16ca1033ca8c7e4a87ec4d17ed48def9cda3f6` |
| C02 | `587de35992a716cfed09f78d78de031978da2b37` | 27 | `8264a44590bad5e2f761119837118347907b5cbf4d3c1f93d4f94eb67f653759` |
| C03 | `20467fceb2a2501f77f4fc7e1c31c8f3d0c8b67c` | 35 | `7bb6d4bd15770b3789206e8d41729568e23a29a56e76b1ce1bd5027050a77fe7` |
| C04 | `09d6b8d1aea57322b20e5378055e7ceca30f59a5` | 9 | `368e00d220a2e52d1f220a6d980c3ddb006dbbc9ee9a162c02abae7b9f844ba9` |
| C05 | `17a36756c46059a3ebd0ef1a3749b942dd1b04d9` | 32 | `966d91cdc1a7a9a69c6918fcd46fe64cb3573a5a9ec5eba4176606ca51126dab` |
| C06 | `9791abd99bd582e584291292db926f4944884d6d` | 26 | `968802615f97d902e573a78d03de5b7962fd5fed350dc94c334afb2752e4fee7` |
| C02 correction | `b7006c2b2bdbf49a96d1d0b88030cda2388b008e` | 3 | `8aafc05bfa0b22b47ebfe2470d3e6d42d60b813e695adba13f497e8b8427f15a` |
| C07 | `04ec7914e0dc3fe861b1bb53dd2712c26a7756f7` | 21 | `8857eb0aeacf98e5b327b1aad02ebb183e431a1883c31e24cc94caf8884a9d81` |
| C08 closeout | `8697fe1aaf190a56eaa03c0bdd9916480d191ed2` | 17 | `6efbd919152b456bff9f2c87a66ecc5bc10e4b188b75d4ba402da67e7429b3c8` |
| debt transition | `2c798e620fb55aaac17e98ff273a78f40c69c7c5` | 4 | `fcde4543d77b82cabdfaf721ebc5220776cb02415f4fa10cd10cb31f60dc1e83` |
| debt provenance | `ea1a886f522ba1ebad77e1e208bc061ac0524117` | 1 | `2e941ddfe37d473179a992f78a1c505bd0e322a67402bd5f496e5ace4908f1a8` |
| debt `closed_by` | `6555ce7b00adcdecc67e8643c47aaca57746f00d` | 1 | `2e941ddfe37d473179a992f78a1c505bd0e322a67402bd5f496e5ace4908f1a8` |
| signature falsifiers | `60ed5de5f02a69b1cce86c52e4095c58052c03d2` | 1 | `4b6723eb6ee2d07b42499858407dc7cbc0f3155a36bb8c3cc89ae752cae221df` |
| superseded P33 token-hiding rename | `fa6845af1be67be573e0b22290c8ba0f548e096f` | 1 | `4b6723eb6ee2d07b42499858407dc7cbc0f3155a36bb8c3cc89ae752cae221df` |
| live debt-denominator prose | `33334e8f25ee8be3c25bf2d9dc7a3f21288c9d35` | 1 | `2e941ddfe37d473179a992f78a1c505bd0e322a67402bd5f496e5ace4908f1a8` |
| honest companion classification | `63de3e82c7cb35f3aeda144b97d687a4d7869977` | 2 | `6fcd6b96aac814ab793d43493a8dbe90254c0dd80f17fed7bd2ef2b348282320` |
| final receipt commit | self-referential hand-back boundary | 2 expected: this plan and journal | re-read and reported after commit |

The execution-base merge `5a6de66ce` is not collapsed into one misleading
set: versus its first parent it carries the 36-path incoming-main set
`39d39f88b36c0827b072a3441aebe5c91b220675f89492a7564a2c42267c867f`;
versus its second parent it carries the one-path approved-plan set
`c3bb72985fd562205d5a22b2ab1a42e82d1f8a27dcd346b12c1c9758a86a448b`.

## CC-required path amendments

These are every production-path observation outside a cluster's original
one-pass list, including reopens. Each names the closure item and the existing
seam rejected under the approved amendment rule. Repeated observations do not
increase the 65-path unique denominator.

| cluster | CC-required path(s) | CC | rejected seam and reason |
| --- | --- | --- | --- |
| C02 | `src/polisyos/runtime/http/services/human_decision_contracts.py`; `src/polisyos/runtime/http/services/human_decisions.py` | CC07, CC10, CC12 | Tenant/run-only exposure plus service-local inference left the authenticated subject unbound and `revalidation_required` dead; bind the subject in the signed session and emit the typed state. |
| C02 | `src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py`; `src/polisyos/runtime/quality/agent_action_authority.py` | CC05, CC23 | Caller-constructible `FiveRightsCheck`/projection or in-memory decision plus unrelated receipt cannot prove independently reconciled signed predicates; reload and content-bind persisted authority before effect. |
| C03 | `src/polisyos/runtime/http/container.py`; `src/polisyos/runtime/http/deployment_security.py`; `src/polisyos/runtime/http/deployment_security_attestation.py` | CC13, CC23 | Caller-supplied/currentness-shaped resolver is forgeable; only the factory-installed resolver bound to custody, deployment identity, and issuer epoch may resolve. |
| C03 | `src/polisyos/runtime/http/resource_binding.py`; `src/polisyos/runtime/http/step_up.py` | CC11, CC13 | Scorecard-only/body-field binding leaves basis and V2 record swappable after auth; pre-OPA and step-up bind all three refs/digests. |
| C03 | `src/polisyos/runtime/http/routes/human_decisions.py` | CC07, CC13 | PA2-only exposure issuance left production unable to establish exact evidence exposure; both source arms use the signed session gate. |
| C03 | `src/polisyos/runtime/http/services/control/run_lifecycle.py` | CC13 | Persisted `approval_ready` is historical projection, not live authority; require the resolver and re-resolve before use. |
| C03 | `src/polisyos/runtime/http/services/human_decision_contracts.py`; `src/polisyos/runtime/http/services/human_decisions.py` | CC02, CC03, CC05, CC13, CC23 | Raw refs/DTO currentness and packet round-trip are forgeable; strict arms read signed basis/scorecard/current V2 record, persist the custody packet, and resolve it fresh. |
| C03 | `src/polisyos/runtime/quality/agent_action_authority.py` | CC23 | A projection or arbitrary resolver could otherwise feed an effect; require the concrete attested resolver and exact production adapter bindings. |
| C04 | `src/polisyos/runtime/http/access_audit.py` | CC15 | A second log or generic append path would fork custody; scan the existing trail read-only with malformed/retention counts. |
| C04 | `src/polisyos/runtime/http/routes/human_decisions.py` | CC15 | A route-local counter/second trail cannot establish joins; resolve the existing trail and service, then project the typed report. |
| C04 | `src/polisyos/runtime/http/services/human_decision_contracts.py`; `src/polisyos/runtime/http/services/human_decisions.py` | CC15, CC16 | Implicit coverage or allow-as-success launders missing/malformed records; expose typed denominators and signed-record read failures. |
| C05 | `architecture/public_surface/contract.toml` | CC20 | The former regeneration command did not exist and module/package facade ownership was ambiguous; declare the real sync command and exact quality facade. |
| C05 | `tools/ops_runners/runtime/generate_runtime_client.py` | CC07, CC17, CC20 | Hand-coded header plumbing/JSON decoding changes evidence bytes; derive header parameters and `ArrayBuffer` mode from OpenAPI. |
| C05 | `src/polisyos/runtime/http/routes/human_decisions.py` | CC07, CC17, CC20 | Manual header lookup is invisible to ABI generation and permits mismatch; make the exposure ref a required typed header and return identity bytes. |
| C05 | `src/polisyos/runtime/http/services/human_decision_contracts.py`; `src/polisyos/runtime/http/services/human_decisions.py` | CC02, CC07, CC12, CC17, CC20 | Caller/raw replay selectors can be fed back as authority; emit non-authoritative selectors reconstructed from verified CAS refs, and expose submission only on available gates. |
| C05 | `src/polisyos/runtime/http/openapi_contract.py` | CC20 | Marker schemas do not prove the strict DTO surface; project real V2 records and operation responses into canonical OpenAPI. |
| C05 | `src/polisyos/runtime/http/routes/runs.py` | CC13, CC20 | Constructing a response around an internal artifact bypasses generated response validation; validate the public response mapping. |
| C05 | `src/polisyos/runtime/quality/approval.py`; `src/polisyos/scientist/artifacts/decision_compiler.py`; `src/polisyos/scientist/validation/decision_artifact_quality.py` | CC20, CC23 | Private deep imports bypass facade ownership; export/import the resolver contract through `polisyos.runtime.quality`. |
| C02 correction | `src/polisyos/runtime/http/routes/human_decisions.py` | CC05, CC13 | `basis_ref=None` turned the production gate on an unbound proxy; bind it to the exact signed production `source_ref`. |
| C07 | `apps/runtime-dashboard/src/features/runs/components/HumanDecisionGate.tsx`; `apps/runtime-dashboard/src/features/runs/components/HumanDecisionReviewEffectivenessPanel.tsx` | CC18, CC21 | Local badge/tone decisions let siblings reinterpret unknown states; all use the private exhaustive issuer, unknown→`unrecognized`. |
| C08 | `apps/runtime-dashboard/src/features/runs/api/useCaseInspection.ts`; `apps/runtime-dashboard/src/features/runs/api/useHumanDecisions.ts` | CC09, CC17, CC21 | Clearing all `location.search` deletes signed bindings, while backend loosening expands authority; strip only DS9-owned replay keys and preserve raw order/duplicates/malformed bytes. |
| C08 | `apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts` | CC17, CC21 | Hard-coded URL or reproduced signer is a marker/second signer; import the existing packet builder through its side-effect-free quantity leaf. |
| C08 | `apps/runtime-dashboard/src/features/runs/components/HumanDecisionGate.tsx` | CC21 | Fixture text shortening hides overflow; structural `min-w-0`/word-breaking closes long content at 320px/200% zoom. |
| C08 | `src/polisyos/runtime/http/authorization.py`; `src/polisyos/runtime/http/routes/governed_projections.py`; `src/polisyos/runtime/http/routes/runs.py` | CC05, CC11, CC21 | Route exemption or global bodyless default reopens guarded-GET bypasses; use a generic invariant plus route-local `allow_empty_body=True` for the three real bodyless reads. |
| final bookkeeping | `tools/quality/validation/check_debt_ledger.py` | CC19, CC24 | Leaving the published denominator at 56 would make a 58-row receipt self-contradictory; update the governed constant and replay writer/check/test/readback. |

No C02 edit touched the amendment's allowed `container.py` or
`deployment_security.py`; those first reopened in C03. The table has 39 path
occurrences because legitimate reopens recur; the unique mechanism total stays
65/78 and the widening total stays 13/18.

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

The original pre-action log
`/tmp/ds9-c08-signed-input-falsifiers-final.log` completed 7/7 in 3.33s under
the 300s ceiling, uptime `23:46 up 13:59` → `23:46 up 14:00`. Final audit then
found that its “each input” wording excluded the production chain. P39 commit
`60ed5de5f` adds the missing direct basis, V2 record, and packet falsifiers.
The post-partition replay `/tmp/ds9-c08-post-partition-test-receipt.log`
completed **20/20** in 40.55s under the 300s ceiling, uptime
`0:31 up 14:44` → `0:32 up 14:45`. That receipt preceded the P33 naming
correction. The current full service replay
`/tmp/ds9-final-honest-service-post-ruff.log` passed **71/71**, including all
listed falsifiers, in 86.40s under the 300s ceiling, uptime
`0:42 up 14:55` → `0:43 up 14:56`; Ruff check and format check are green.

| signed input type | exact falsifier | typed result |
| --- | --- | --- |
| `HumanDecisionPrincipalBinding` | `test_human_decision_requires_attested_principal_to_signing_key_binding` | unsigned → `invalid_source` / `DS9-DECISION-SOURCE-INVALID`; record set unchanged. Signed wrong issuer → `DS9-PRINCIPAL-SIGNING-KEY-MISMATCH`. |
| `ReviewerSeparationCredential` | `test_human_decision_requires_signed_separation_and_change_authority` | unsigned → `invalid_source` / `DS9-DECISION-SOURCE-INVALID`; record set unchanged. Signed without change authority → `blocked` / `DS9-REVIEWER-INDEPENDENCE-CHANGE-AUTHORITY-MISSING`. |
| `AgentActionAuthorityDecision` | `test_human_decision_rejects_unsigned_source` | `invalid_source` / `DS9-DECISION-SOURCE-INVALID`; continuation and submission absent. |
| `DelegationContract` | `test_human_decision_rejects_unsigned_contract` | `invalid_source` / `DS9-DECISION-SOURCE-INVALID`. |
| `HumanDecisionPresentationContract` | `test_human_decision_rejects_unsigned_presentation_contract` | `invalid_source` / `DS9-DECISION-SOURCE-INVALID`. |
| `HumanDecisionExposureSession` | `test_human_decision_rejects_unsigned_exposure_session` | `invalid_source` / `DS9-DECISION-SOURCE-INVALID`; continuation and submission absent. |
| `HumanDecisionExposureAuditEvent` | `test_human_decision_rejects_unsigned_exposure_events` | intentionally `blocked` / `DS9-EVIDENCE-NOT-OPENED`, not a false invalid-source. |
| `ProductionHumanDecisionBasis` | `test_production_gate_rejects_unsigned_basis_with_typed_refusal`; `test_production_resolver_rejects_unsigned_basis_with_zero_packet` | pre-action `invalid_source` with no record; final resolver `DS9-DECISION-SOURCE-INVALID` with packet set unchanged. |
| signed quality scorecard | `test_production_approval_blocks_unverified_scorecard_producer` | operational `DS9-DECISION-SOURCE-INVALID`. |
| V2 `HumanDecisionRecord` custody signature | `test_production_resolver_rejects_unsigned_record_with_zero_packet` | operational `DS9-DECISION-SOURCE-INVALID`; packet set unchanged. |
| V2 `ProductionApprovalPacket` custody signature | `test_production_packet_without_custody_signature_is_typed_refusal` | concrete resolver returns `DS9-DECISION-SOURCE-INVALID`. |
| step-up JWT signature | `test_signed_step_up_assertion_fails_closed_for_invalid_authenticity_or_assurance`, parameter `case="invalid_signature"` | `step_up_signature_invalid`. Endpoint absence separately proves `step_up_required` and unchanged packet set; no broader endpoint signature-removal claim is made. |

Nested request/envelope fields are content-bound inside their containing signed
source/basis/contract; exact evidence bytes are CAS-digest-bound rather than
separately signed. The table is exhaustive by signed input type, not by every
common-input × source-arm cross-product. Identifier inequality is never used as
a substitute for signed independence.

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
- Approval strangle at C08 closeout: 3/3 in 72s by the durable UTC pair, uptime
  `23:40 up 13:53` -> `23:41 up 13:54`; independently enumerated
  `18 mechanisms + 47 companions + 16 retained = 81`, no unclassified and no
  classified-but-untracked path. The later P39 signature-falsifier edit made
  `tests/unit/runtime/http/test_human_decision_service.py` the 48th companion.
  An attempted rename then hid the token and produced a false 81-path green;
  it is preserved as the superseded P33 finding at `fa6845af1`. The honest
  current replay is 3/3 in 72.07s under the 120s ceiling, uptime
  `0:42 up 14:55` -> `0:43 up 14:56`, and proves
  `18 mechanisms + 48 companions + 16 retained = 82`. Current code denominator is 6,788
  (5,605 Py + 469 TS + 668 TSX + 5 JS + 32 MJS + 9 CJS). Raw token search
  returns 83 paths; the generic verifier genuinely self-exempts only itself,
  `tests/repo_quality/tools/test_ds9_approval_semantic_strangle.py`. Product
  raw-path-list SHA-256 excluding that verifier is
  `952ca9517ae1a38d8f2c9d38b6a6148406e33d7b17120410e70c680579e74dba`.
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

## Retained labels and exact retained set

The retained product partition is exactly these 16 candidate/fail-only paths:

- `src/polisyos/runtime/http/services/control/workspace_loop_transition.py`
- `src/polisyos/runtime/quality/assurance_case.py`
- `src/polisyos/runtime/quality/attestation.py`
- `src/polisyos/runtime/quality/diagnostic_events.py`
- `src/polisyos/runtime/quality/invariants.py`
- `src/polisyos/runtime/quality/projection_semantics.py`
- `src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py`
- `src/polisyos/runtime/quality/run_state.py`
- `src/polisyos/runtime/quality/scorecard.py`
- `src/polisyos/scientist/orchestration/engine/executor.py`
- `tools/ci/check_policyos_production_quality_best_in_class.py`
- `tools/quality/validation/build_policy_design_case_pass2_diagnostics.py`
- `tools/quality/validation/build_policy_design_case_wave35a.py`
- `tools/quality/validation/build_policy_design_case_wave35e.py`
- `tools/quality/validation/check_runtime_quality_schema_compatibility.py`
- `tools/quality/validation/pass2_wave34_common.py`

The inherited label `deep-import-baseline-stale` names these six exact edges:

- `polisyos.runtime.http.services.channel_contracts -> polisyos.core.artifacts.manifest`
- `polisyos.runtime.http.services.channel_contracts -> polisyos.core.contracts.decision_validity`
- `polisyos.runtime.http.services.control.lex_pipeline -> polisyos.lex.knowledge.store`
- `polisyos.runtime.http.services.control.lex_search_projection -> polisyos.core.contracts.runtime`
- `polisyos.runtime.http.services.control.lex_search_projection -> polisyos.lex.knowledge.types`
- `polisyos.scientist.orchestration.engine.checkpoint -> polisyos.core.security.tenant_context`

The 13 inherited status diagnostics retain exact stderr SHA-256
`511bfd68fea9232d15e33a577859121ca61501a4824a8535ccfd16551ffa17f9`.
Other exact retained labels are `DS9-PG-PROOF-NONRECEIPT`, `producer_missing`,
`implemented_but_not_orchestrated`, `bridge_missing`, `absent/unallocated`, and
`surface_out_of_scope`. None is converted to green by this slice.

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

## Final closure-contract evidence

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
| CC19 | `2c798e620`: fresh-lock writer/check/test yields 58/58, indexed 35, exact distribution; `ea1a886f5` corrects P41 wording and `6555ce7b0` binds the unmerged `closed_by` receipts; all read back attached |
| CC20 | OpenAPI + five client outputs + dashboard types + supported-entrypoint inventory regenerated/reproduced |
| CC21 | named semantic, corruption, a11y, 320 px/200%-zoom, keyboard, long-content and visual receipts green |
| CC22 | immutable DS11 bundle below exposes status/provenance/telemetry/exact bytes, never public authority |
| CC23 | DS14 strict PA2/production adapter arms re-resolve their concrete sources and reject cross-arm fields |
| CC24 | zero GY DV/Claim owner paths; every commit/path digest above read back from the attached branch; final plan/journal commit is the self-referential two-path boundary re-read before hand-back |

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
4. **`case-workspace-route-bypasses-feature-barrel` is base-reproduced and out
   of scope; P41 ownership is `not_established`.** The exact edge is
   `apps/runtime-dashboard/src/app/routes/routes.tsx -> @/features/runs/routes/CaseWorkspacePage`.
   It exists at the execution base
   and closeout, but DS9 changed another file in the checker denominator, so it
   is not labelled inherited. Owner: `team-frontend`. It is registered
   `open_unmerged`; DS9 does not expand the feature barrel/app-route surface.
   Discharge with
   `cd apps/runtime-dashboard && corepack pnpm run check:architecture`, which
   must exit zero after the app imports only through `features/runs/index.ts`
   while a direct-subpath negative fixture remains rejected.
5. **Left undone with reason: historical ceiling metadata is incomplete, not a
   product residual or a product green.** C00's
   original elapsed/uptime, C01/C02 exact elapsed, C05 resolved numeric caps,
   and C06 static-command caps were not written durably; the table labels every
   field `not_established`. Owner: DS9 execution process / DS-INFRA-2 timing
   harness. Historical values cannot be reconstructed, and no command can
   discharge a receipt that was not captured at the historical source state.
   Replaying a named terminal command now with `date -u`, `uptime`, a literal
   ceiling, `/usr/bin/time -p`, and its exit would create replacement evidence
   for the current immutable head; it would not recover or discharge history.

No DS9 capability is left unimplemented. Items 1-4 are explicit
residual/inherited/foreign-owner receipts with discharge commands; item 5 is
the irrecoverable execution-metadata item left undone for the reason stated.
None is hidden as green.

## Final bookkeeping readback

Closeout `8697fe1aaf190a56eaa03c0bdd9916480d191ed2` was read back attached with
exactly 17 paths (7 mechanisms + 10 P39 companions). Under the final fresh
register-family lock, the live-denominator prose was corrected 55→58 and the
writer and check both completed with only the unchanged
ten `register_supplies_missing_standing` plus one
`register_withholds_source_standing` informational classes. The semantic gate
was green: zero `source_status_conflict`, zero `*_denominator_mismatch`, zero
`ledger_render_drift`, and register=58. Writer: 1.82s, uptime
`0:37 up 14:50` → same minute. Check: 1.01s, uptime `0:38 up 14:51` → same
minute. The checker suite passed 31/31 in 6.73s, uptime
`0:38 up 14:51` → same minute. The one-path correction commit
`33334e8f25ee8be3c25bf2d9dc7a3f21288c9d35` was re-read attached.

Debt transition `2c798e620fb55aaac17e98ff273a78f40c69c7c5` was re-read with its
exact four-path fence. Register state is published=observed=58, indexed=35:
`ambiguous=1, blocked=7, closed=23, folded=2, foreign=6, open=17,
open_unmerged=2`. It closes `ds8-approval-authority` and
`DS20-B-scorecard-provenance-intake-effect`; preserves
`ds8-local-reviewer-note-persistence`, `ds8-signed-public-decision-surface`,
and `DS20-B-scorecard-provenance-producer-trust`; and registers the two §C
rows above. `ea1a886f5` corrects route-edge P41 wording, and `6555ce7b0` binds
both unmerged `closed_by: branch receipt 2c798e620` tokens. Each is an attached
one-path readback.

P39 signature commit `60ed5de5f02a69b1cce86c52e4095c58052c03d2` was read back as one
test path. Its honest helper name made that file the 48th raw-token companion,
and the generic partition test correctly went red at 18+48+16=82. Commit
`fa6845af1be67be573e0b22290c8ba0f548e096f` then hid the token and produced a
false 81-path green; it is retained as a superseded P33 finding, not a closure
receipt. Append-only correction `63de3e82c7cb35f3aeda144b97d687a4d7869977`
restores semantic helper, kind, and builder names and updates the generic
expected partition to 82. Its two-path fence was re-read attached. The current
strangle passed 3/3 in 72.07s, the full service file passed 71/71 in 86.40s,
and Ruff check/format are green. The current debt-ledger plus generic strangle
gate passed 34/34 in 58.87s under a 240s ceiling, uptime
`0:47 up 15 hrs` → `0:48 up 15:01`. The superseded 34/34 result from the hidden
token state is retained only as the falsifier for the P33 correction. The
register-family lock, regeneration token, and visual lane were released before
the next resource; none overlapped. All 24 closure items are evidenced. The
final two-path plan/journal commit is re-read after creation and reported in the
hand-back because it cannot contain its own hash without another commit.
