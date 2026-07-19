# Atlas DS20 Server Authorization Enforcement Closure

## Disposition

**Writable-fence implementation: complete. Merge/deployment disposition: NO-GO
pending architect review and the cross-fence policy/consumer repairs below.**

DS20 closes the measured HTTP-layer security floor: every live unsafe operation is
admitted only through verified identity, one exact server-owned action permission,
a concrete resource bound before OPA, and—where high stakes—one fresh, request-bound,
single-use step-up assertion. Absence, ambiguity, dependency tampering, audit failure,
and unverifiable resource authority all fail closed. No UI state, fixture fallback,
coarse role, offline path, or coarse OPA allow substitutes for the action proof.

The branch is intentionally unmerged. Canonical Rego/Helm policies and two production
tool consumers have not yet adopted the DS20 contract; claiming production readiness
would therefore be false even though unauthorized HTTP mutation is structurally
blocked.

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
- Changed-file Ruff: passed.
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

Remaining capability labels are explicit: policy adoption is `bridge_missing` plus
`semantic_test_missing`; production tools are `consumer_missing` plus
`verification_missing`; promotion compare-and-set is `bridge_missing`; scorecard
verifier provenance and DS9 decision-integrity artifacts are `artifact_missing`.

## Cross-fence blockers and required handoffs

### Architect/policy owner — blocks production admission

OPA 1.15.2 against both `ops/policy/policies/**` and the Helm bundle denies truthful
DS20 inputs for ingestion, same-tenant run launch, and promotion. The old policies do
not consume the new action/resource/tenant-authority contract. Fabricating resource
ownership in HTTP or bypassing the deny is forbidden. The policy lane must implement
the vocabulary/resource contract and add exact allow/deny semantic tests.

### Production tooling owner — blocks existing canaries

- `tools/ops_runners/runtime/local_production_canary.py:2375` and `:2538` request
  development fixture identity in production and now fail before network I/O.
- `tools/quality/testing/local_prod_debug_probe.py:536` constructs a production app
  without a step-up verifier and now fails at bootstrap.
- Update the corresponding tests and
  `docs/runbooks/local-production-debugging.md:199` with genuine identity and verifier
  wiring; do not restore fixtures or optional verification.

### Fabric/quality producer owners — authority limitations

- Promotion retrieval lacks expected-digest/version compare-and-set, leaving a
  content-resolved-unscoped post-OPA race that HTTP cannot atomically close.
- Persisted production scorecards expose CAS identity but not verifier provenance.
  A producer/contract repair must prove quality authority; CAS presence or
  self-attestation is insufficient.
- PostgreSQL replay/scenario paths require a real-DSN execution receipt; only the
  shared SQLite semantics ran locally.

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
- Writable paths remained inside runtime HTTP, schema/generated client, scoped HTTP
  tests, and DS20 plan/journal/closure documents.
- `apps/**`, runtime quality, policy bundles, production tools, architecture baselines,
  and the DS19 register were read-only.
- Closeout `main` remains `d5f83a26b`; N13b is `72e20ff8b` with zero branch-only
  runtime HTTP paths.
- The current-base `git merge-tree` preview emitted no conflict output.
- Final fence stat: `57 files changed, 14958 insertions(+), 867 deletions(-)`.
- No merge, push, or pull request is authorized by this slice.
