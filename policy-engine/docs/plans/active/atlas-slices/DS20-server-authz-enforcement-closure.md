# Atlas DS20 Server Authorization Enforcement Closure

## Disposition

**HTTP floor and DS20-B implementation: complete. Merge/deployment disposition:
NO-GO pending architect review of the B3 typed limitation, the B5
environment-blocked PostgreSQL proof, and the out-of-fence Helm policy mirror.**

DS20 closes the measured HTTP-layer security floor: every live unsafe operation is
admitted only through verified identity, one exact server-owned action permission,
a concrete resource bound before OPA, and—where high stakes—one fresh, request-bound,
single-use step-up assertion. Absence, ambiguity, dependency tampering, audit failure,
and unverifiable resource authority all fail closed. No UI state, fixture fallback,
coarse role, offline path, or coarse OPA allow substitutes for the action proof.

The branch is intentionally unmerged. Canonical Rego and both production-tool
consumers now adopt the DS20 contract through genuine deployment identity. The Helm
chart's separate policy mirror is still stale because it was explicitly outside the
extended fence. Promotion still lacks an atomic Fabric compare-and-set producer, and
the durable PostgreSQL properties have executable proofs but no real-DSN receipt in
this environment. Claiming full production readiness would therefore still be false.

| DS20-B blocker | Verdict |
|---|---|
| B1 Rego bridge | `closed` — exact 33-value vocabulary and behavioral server/Rego parity |
| B2 ops identity | `closed` — genuine minimal-grant deployment principals for both probes |
| B3 promotion CAS | `typed-limitation` — N13b owns the missing public Fabric CAS producer |
| B4 verifier provenance | `closed` — factory-only non-development composition and documented IdP provenance |
| B5 PostgreSQL proof | `environment-blocked` — executable real-PG harness, no local DSN/daemon |

## Live denominator and structural proof

Application-router introspection on the final branch yields 29 unsafe operations:
29 `POST`, zero `PUT`, zero `PATCH`, and zero `DELETE`.

| Property | Receipt |
|---|---:|
| One exact direct typed action dependency | 29/29 |
| Exact-permission denial | 29/29 return 403 |
| Absent-identity denial | 29/29 return 401 |
| Authorized real-handler admission | 29/29 return 200 |
| Fresh step-up required where mapped | 6/6 |

The final denominator is:

1. `get_runs_batch`
2. `create_run_production_approval`
3. `create_run_scenario`
4. `get_fabric_quality_batch`
5. `get_fabric_trust_batch`
6. `analyze_fabric_impact`
7. `get_artifact_batch`
8. `render_bureaucratic_artifact`
9. `analyze_attractors`
10. `analyze_lyapunov_diagnostics`
11. `persist_basin_map`
12. `persist_continuation_branch`
13. `get_lineage_batch`
14. `estimate_mobility`
15. `compute_mobility_bounds`
16. `launch_run`
17. `evaluate_run_feedback`
18. `launch_nl_run`
19. `reissue_run`
20. `publish_decision_validity_event`
21. `ingest_data`
22. `resolve_data_needs`
23. `discover_data_sources`
24. `preview_fetch_plan`
25. `estimate_causal_frontier_sae`
26. `approve_data_promotion`
27. `reject_data_promotion`
28. `trigger_lex_pipeline`
29. `search_lex_graph`

The guarantee is structural, not an enumerated allowlist. Tests walk the live FastAPI
router and reject a missing, duplicate, nested-only, marker-only, mismatched, or
non-executable dependency. App construction/lifespan and late-route preflight apply
the same contract. A synthetic new unsafe route lacking exactly one valid requirement
cannot serve. Permission denial tests are parameterized from the live routes; adding
a route without a deny witness fails the contract suite.

## Single permission vocabulary

Before DS20, the server hand-authored 12 `_ROLE_PERMISSIONS` strings while the
dashboard separately hand-authored 15 `PERMISSION_KEYS`. After DS20:

- `RuntimePermission` is the sole server-authored action vocabulary, with 33 values;
- immutable role grants refer only to enum members;
- route requirements accept only enum members;
- `/auth/me` and OpenAPI project the enum rather than restating literals;
- `components.schemas.RuntimePermission` is the generated-client authority contract;
- the canonical runtime client reproduces the exact server enum; and
- a contract test fails if the generated union and OpenAPI/server enum diverge.

The read-only dashboard still contains three literals with no server counterpart:
`collaboration.comment`, `collaboration.share`, and `collaboration.view`. DS20 did not
edit `apps/**` or promote those strings into authority. They are a DS5/DS4
`consumer_missing` lint/strangle finding.

## Step-up coverage

Five declared high-stakes classes map to six live operations:

| Class | Live operation(s) |
|---|---|
| Acquisition approval | `ingest_data` |
| Promotion | `approve_data_promotion`, `reject_data_promotion` |
| Publication | `publish_decision_validity_event` |
| Revocation | `reissue_run` |
| Production approval | `create_run_production_approval` |

Acquisition approval is declared and live on the current ingestion/acquisition
operation; the structural map is ready for later N13b acquisition-execution approval
routes. Each mapped route declares the action dependency first and a distinct direct
step-up dependency second.

The verifier binds issuer, audience, trusted algorithm/key ID, subject, tenant,
method, canonical route, permission, resource identity/digest/kind/authority, exact
body hash, assurance class, freshness window, MFA, and assertion ID. Production
approval additionally binds the exact persisted scorecard reference and digest.
The durable replay store consumes the assertion exactly once. Missing, stale,
expired, future-issued, not-yet-valid (`nbf`), replayed, mismatched, wrong-key, or
verifier-unavailable assertions deny before handler execution.

## Identity, resource binding, and execution integrity

- Explicit or environment-requested fixture identity aborts every non-development
  profile at application startup. Reserved fixture issuers are also rejected when
  presented through an identity provider or review WebSocket.
- `/auth/me` has no route-local or UI-facing identity fallback. Missing genuine
  claims return 401; verified empty roles stay empty.
- Every unsafe request resolves and freezes a concrete resource before OPA. Unknown,
  malformed, cross-tenant, unscoped-as-owned, or unresolved selectors deny before
  policy evaluation. The OPA probe proves no unbound-resource evaluation is reachable.
- Binding authority is explicit: `ownership_verified`, content-resolved but unscoped,
  logical target, and other sources are never collapsed into caller-owned truth.
- Scenario lineage freezes the durable head/manifest before OPA and rechecks the head
  afterward. Scenario writes use the existing dual-backend compare-and-set head.
- The middleware seals the exact route requirement, frozen resource, action proof,
  and step-up proof before dispatch. Direct, nested, bulk, dependency-override, and
  route-application replacement probes cannot reach a handler side effect. The state
  and nested resource are non-`dict` mapping wrappers backed by read-only protected
  storage, so base-`dict` descriptors cannot bypass their mutators.
- Slow binders, OPA, key retrieval, replay storage, and durable audit I/O execute off
  the ASGI event loop while retaining their fail-closed semantics.

`POST /runs/{run_id}/production-approval` now has the same action enforcement as
every other mutation, plus production-approval step-up. It resolves a durable
run-matching scorecard before OPA, rejects client-authored signatures and foreign
override identities, binds exact bytes into the step-up context, and cannot persist
an approval packet after any deny.

## Audience denials and authorization audit

Server tests prove PUBLIC-class principals cannot retrieve REVIEWER/EXPERT-only data;
UI hiding is irrelevant to the result. Per-audience and per-operation negatives
exercise the server boundary directly.

Every terminal authorization admission/denial appends one strict
`polisyos.runtime.authorization_audit.v1` event to the existing append-only
`http/access_audit.py` trail. No second log was added. Events contain the sealed
permission/resource/principal/policy/step-up context but exclude bearer tokens,
step-up assertions, and request-body values. An allow-path append failure blocks the
handler with 503; denial-audit failure preserves the original denial. An allow event
means authorization admission, not handler success. These events are the DS9
review-effectiveness input.

## DS1 N009-N013 disposition

| Negative | DS20 status | Remaining owner/state |
|---|---|---|
| N009 generic mutation authorization | Server half closed | 29/29 structural dependency and three-way matrix |
| N010 UI/fallback identity path | Server half closed | DS5/DS4 UI rebinding remains `consumer_missing` |
| N011 production fixture identity | Closed | Startup/provider/WebSocket negatives pass |
| N012 production approval integrity | HTTP authorization half closed | Verifier provenance and DS9 mandate/dissent/exposure/signature artifacts remain `artifact_missing`/`consumer_missing` |
| N013 fresh step-up | Closed | Six live operations, five classes, replay/freshness/context negatives pass |

DS19 register proposal: mark the server-negative portions of N009, N011, and N013
closed; mark only the server half of N010 and N012 closed; preserve their downstream
labels above. The 29 operation wire/rebind/retire dispositions remain unchanged
because server authorization is orthogonal to their destination-surface lifecycle.
The authoritative register is outside the DS20 fence and was not edited.

## Verification receipts

- Focused DS20 gate: 268 tests, all passed.
- Scoped HTTP collection: 699 tests.
- Final repeat scoped run: exactly the six pre-edit failures and two inherited skips,
  with no additional failure. An earlier read-only SSE timing failure passed alone,
  in its complete module, and in this repeat; it is not added to the baseline.
- Thirty-one legacy mutation tests were converted to authenticated/step-up-aware or
  explicit early-deny expectations. No auth check was weakened to make them green.
- Changed-file Ruff: baseline-relative passed. The only strict findings are two
  inherited `SIM114` branches in the canary, both blamed to `5c4823ee7c`; all task
  Python files pass with that inherited rule excluded.
- Canonical runtime API contract checker: passed.
- Generated runtime client TypeScript typecheck: passed.
- Generated runtime client architecture check: passed.
- Enum projection, two-run byte reproducibility, and committed package-pipeline
  contract tests: 3/3 passed.
- Focused authorization/step-up basedpyright error gate: 0 errors. Including
  `dependencies.py` reports only its two pre-existing artifact-store cast errors.
- `git diff --check`: passed.
- Final independent review: no Critical or Important finding remains. Its two
  Important witnesses (base-`dict` seal bypass and premature `nbf`) were red before
  repair and green afterward; sibling mutator/type/skew/window probes also pass.
- Architecture guardrail: baseline-red, not DS20-green. Five inherited DS3 additions
  remain, while DS20 removes three stale baseline edges. No DS20-added deep-import
  edge remains; baseline sync is outside the fence.

DS20-B's fresh closeout receipts add:

- OPA 1.15.2 strict check and canonical Rego harness: 45/45 passed.
- Rego/server vocabulary parity: exact equality with all 33 canonical permissions.
- Rego/server decision parity: live server inputs and the principal × operation ×
  resource matrix agree, including unknown-value and no-contract denials.
- DS20-B focused gate: 75 selected, 70 passed, five explicit skips. Four skips are
  the real-PostgreSQL proofs below; one is the pre-existing optional debug-probe
  PostgreSQL integration.
- Focused DS20 denominator after the final import-boundary repair: 268/268 passed.
- Scoped HTTP denominator after the same repair: exactly the six inherited failures
  and two inherited skips listed below; no SSE recurrence and no new failure.
- Runtime contract checker: passed. Runtime client TypeScript, architecture, four
  JavaScript tests, and ESLint: passed.
- Task enforcement/deployment/test basedpyright gate: zero errors. A deliberately
  wider scan of the two modified legacy probe scripts reports 26 diagnostics, every
  one blamed to pre-DS20 lines; no diagnostic lands in a DS20-B hunk.
- Schema and generated-client bytes are unchanged from `9b5e4f69c`; regeneration was
  therefore neither required nor performed in DS20-B. The six hashes below remain
  exact.

The six inherited scoped failures are unchanged:

1. `test_runtime_never_imports_concrete_cas_write_implementation`
2. `test_feedback_endpoint_returns_feedback_loop`
3. `test_equilibria_endpoint_returns_multiplicity_report`
4. `test_evaluate_feedback_endpoint_persists_monitoring_report`
5. `test_reissue_endpoint_fails_closed_without_durable_control_plane`
6. `test_feedback_evaluate_mutation_is_audited`

The OpenAPI/client pipeline was run twice serially and produced identical bytes:

```text
f94c87d56cf1cc3658c3c9330bd202fc2061fc2debad16a407d0aabf322cb0cb  schemas/runtime_api_v1.openapi.json
137ba30652cc89ff37317d055ab63704e0ccdfdb705e618851fb7ed2f015e644  packages/runtime-api-client/types.ts
82e61027952eaad307a9f1685e23449c8911235ed269203969025ec34dc0ad94  packages/runtime-api-client/runtimeApiClient.ts
7a1094444cf72ab1ba7b6daf11bc85f4e07c289ac21c84b516724cff0f8e3945  packages/runtime-api-client/runtimeApiClient.js
45a31882719cc949f6e1d453b8a6033ee2047f76deec1f184cb8ce95a9bcdd2d  packages/runtime-api-client/canonicalRuntimeApiClient.ts
6d7465160421459492cbef22102f4f9abc1e777803706b9730e2ebfe511e9568  packages/runtime-api-client/canonicalRuntimeApiClient.js
```

## Pattern closeout

- P05/P10/P26: authority and audience enforcement now occurs at the server boundary.
- P29: the verifier imports and executes the live router/dependencies and adversarially
  removes/replaces execution while retaining markers; marker inspection alone cannot
  pass.
- P31: shared middleware/dependencies close the mutation class rather than patching
  29 handlers independently.
- P32: unresolved/unscoped resources are never labeled owned; scorecard CAS identity
  is not claimed as verifier provenance.
- P33/P34: malformed, synonymous, marker-complete, nested, bulk, sibling-consumer,
  and race probes are retained, and excluded failures were rerun in isolation before
  classification.

Remaining capability labels are explicit: the out-of-fence Helm mirror is
`bridge_missing` plus `verification_missing`; promotion compare-and-set remains
`bridge_missing`; the local real-PostgreSQL receipt is `verification_missing`; and
DS9 decision-integrity/scorecard-authority artifacts remain `artifact_missing`.
Canonical policy adoption, deployment verifier composition, and both production
probe consumers are closed in DS20-B.

## Cross-fence blockers and required handoffs

### B1 canonical policy bridge — closed; Helm deployment mirror limited

Canonical `ops/policy/policies/**` now consumes the exact action permission,
resource class, binding authority, authorization source, tenant, and principal grant
contract. Unknown permissions, resources, authorities, sources, or principal grants
deny by default. The Rego vocabulary is exactly equal to the 33-value server enum,
and the behavioral decision-parity suite exercises live server envelopes rather than
marker strings.

The chart mirror under `ops/cloud/helm/polisyos-cell/policies/**` was explicitly
read-only and is now stale relative to canonical Rego. Deployment remains a typed
`bridge_missing`/`verification_missing` limitation until the chart owner mirrors and
tests the canonical bundle; DS20-B neither edits it nor claims it green.

### B2 production probe identity — closed

The canary and local-production debug probe no longer request fixture identity or an
allow-all policy. Both compose the strict deployment security factory and require a
deployment-injected short-lived bearer for dedicated service principals. The canary
principal is limited to `runs.launch` and `runs.view`; the debug principal is limited
to `runs.view`. Behavioral tests prove bad signature returns 401, a genuine principal
without the exact grant returns 403, and the exact debug grant reaches the protected
missing-run witness and returns 404 after canonical OPA evaluation.

### B4 verifier provenance — closed

Non-development application construction accepts only the exact factory-produced
deployment bundle. Issuer, audience, algorithms, JWKS/key rotation, cell routing,
OPA endpoint, service-principal grants, replay storage, freshness bounds, and
non-secret configuration provenance resolve through the typed deployment path.
Protocol-shaped/test verifiers are structurally refused outside development. The
runbook records the external IdP contract, including Keycloak role claims and MFA
`acr`/`amr`; a client-authored MFA boolean is not authority.

### B3 Fabric promotion CAS — typed limitation

- N13b ref `72e20ff8b` owns the exact Fabric producer
  `src/polisyos/fabric/retrieval/service.py`, so the mandated owner-overlap stop fired
  before any Fabric edit. Both merge-tree previews are textually clean, but textual
  cleanliness does not waive owner discipline.
- Promotion retrieval still lacks expected-digest/version compare-and-set. The race
  begins when HTTP copies the candidate for pre-OPA binding and ends only when the
  retrieval service acquires its mutation lock. It spans OPA, step-up, scheduling,
  and has no enforced upper bound; the lock also releases before downstream
  persistence. No HTTP-only post-check can make that mutation atomic.
- Verdict: `typed-limitation` / `bridge_missing`. The Fabric/N13b owner must expose a
  generic revision-CAS primitive at its public facade before authorize→mutate can be
  claimed atomic.

### B5 real PostgreSQL proof — environment-blocked

- Four real-PostgreSQL-only tests use independent store/app instances and unique
  schemas. They prove exactly one step-up replay winner, one scenario mutation plus
  one 409, corrupted-head denial before OPA, and rejection of an unheaded CAS artifact
  by a fresh app. There is no SQLite fallback in these tests.
- This host has no `POLISYOS_TEST_PG_DSN`, no `pg_isready`, and no reachable Docker
  daemon. All four tests therefore skip explicitly as `environment_blocked`; no
  PostgreSQL property is claimed true without execution.
- Reproduction command:
  `POLISYOS_TEST_PG_DSN='postgresql://...' uv run --extra test --extra runtime --extra multi-tenant pytest -q tests/unit/runtime/http/test_runtime_postgres_linearizability.py`.

### Remaining quality/decision-integrity authority limitation

- Persisted production scorecards expose CAS identity but not verifier provenance.
  A producer/contract repair must prove quality authority; CAS presence or
  self-attestation is insufficient.

### DS5 and DS4

Consume `components.schemas.RuntimePermission` and the generated
`@polisyos/runtime-api-client` union. Map audiences to the server vocabulary, remove
the dashboard-authored duplicate, and lint client literals—especially the three
collaboration strings—against the generated contract. UI hiding remains presentation,
never authorization.

### DS9

Consume `polisyos.runtime.authorization_audit.v1` admissions/denials and step-up
outcomes for review-effectiveness telemetry and mandate/dissent UX. DS20 does not
claim mandate/dissent artifacts, exposure receipts, authoritative scorecard
provenance, or final server signing.

### Public surface/release owner

The Runtime API v1 OpenAPI enum and operation extensions are a `public_stable` change.
A release fragment and public-surface migration note are required outside this fence.
The new internal Python modules were not added to the package public facade.

## Fence, branch, and merge disposition

- Worktree: `/Users/deniskopylov/polisyos/.worktrees/atlas-ds20`
- Branch: `codex/atlas-ds20-server-authz`
- Base at worktree creation: `d5f83a26b`
- Writable paths remained inside the original runtime HTTP/DS20 test/doc fence and
  the amendment's exact canonical Rego, probe, runbook, and PostgreSQL-test list.
  The two middleware re-export files are existing-HTTP-fence wiring paths recorded
  in the amendment's guardrail addendum; they add no new core edge.
- `apps/**`, runtime quality, Fabric, GY artifacts/validators, Helm, architecture
  baselines, and the DS19 register were read-only.
- Closeout `main` remains `d5f83a26b`; N13b is `72e20ff8b` with zero branch-only
  runtime HTTP paths.
- `git merge-tree --write-tree HEAD main` and the corresponding N13b preview both
  exit zero. N13b has no textual path overlap with DS20-B, while its semantic
  ownership of the Fabric CAS producer is preserved as B3's stop condition.
- DS20-B changes no schema/client bytes and makes no Fabric, Helm, app, GY, or
  architecture-baseline edit.
- Final fence stat: `72 files changed, 19062 insertions(+), 912 deletions(-)`.
- No merge, push, or pull request is authorized by this slice.
