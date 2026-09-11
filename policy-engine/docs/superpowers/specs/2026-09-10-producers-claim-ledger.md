# Claim supersession: verify the delivered chain and retain its authority limit

Status: Stage 1 decision proposal; source and test changes have not started.
Scope: `claim-ledger-supersession-owner-event-producer-missing` and its exact
`DS11-CLAIM-LIFECYCLE-ORCHESTRATION` witness. The scope-adjudication object and closed
epoch-batch work are excluded.

Source baseline: `a534024ee28dfd9ac4fd21be1ff769b253722d8e` on
`codex/producers-verification`. All paths below are relative to `policy-engine/`.
The complete debt rows were read as requirements. Neither the debt register nor
`LEDGER.md` supplies evidence about the implementation.

## Decision

Reuse the September 7 owner-event implementation. Do not build another producer,
resolver, replay schema, or signing configuration. Verify its real HTTP caller with
explicit test-only authority dependencies, and add a default-HTTP negative proving
that absent authority and caller-authored replacement assertions remain visible
without advancing a current Claim head.

The implementation supports a signed, content-bound supersession relation through
an injected repository owner. The default deployment does not construct that owner:
it constructs `UnappointedClaimLedgerOwner`. Its candidate operation returns
`claim_head_absent`, and its owner-event append returns
`claim_owner_event_authority_unappointed`. The existing target test invokes the real
monitor bridge directly with a fixture-owned repository owner, not the HTTP caller.
Consequently a green target alone would not prove default positive deployment or an
institutional appointment.

This slice must finish the verification it can establish. It must not claim the
whole institutional closure condition met. The remaining root trust/admission
composition is engineering work; its absence must not be relabelled as an
appointment or used to pretend the already-built candidate mechanism is missing.
No new configurable-root task identifier is invented here: the architect must
register that specific obligation and assign its owner before a handoff can name
it as an existing successor.

Alternatives considered:

| Alternative | Decision |
| --- | --- |
| Verify existing producer/owner via HTTP with explicit test trust, plus default refusal | Selected: closes the route-verification gap without inventing authority. |
| Add another owner-event schema or producer | Rejected: CL-01 establishes both already exist and are consumed. |
| Replace the default owner with a repository owner behind a key-loading shell | Rejected in this slice: root policy and issuance verification remain unsatisfied; key presence is not root authority. |
| Restore metadata-only supersession or promote the successor on relation admission | Rejected: crosses the authority boundary and loses the independently issued successor requirement. |

## Requirements and pattern pass

The target requires a real CAS `append_verified_owner_event`, an independently
verified event produced by an appointed owner, and
`tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py::test_monitor_event_persists_claim_supersession_without_in_place_edit`
through production code with predecessor bytes unchanged.

`S0-K03` requires separating institutional appointment, persisted candidate,
verification/admission, lifecycle reaction, and projection. `S0-K06` and the
principal rulings in identity decision §9 items 5–6 require that absence constrain
authority while the candidate mechanism remains demonstrable. These are requirement
citations to `docs/system-design-decisions/stage0-custody-kernel-ratification.md` and
`docs/system-design-decisions/policyos-identity-and-custody-boundary.md` at the source
baseline, not evidence that a particular chain is deployed.

| Pattern | Observed risk and chosen closure |
| --- | --- |
| P01/P02/P27 | Rebuilding a producer because an old missing-state description survives would duplicate delivered code. Follow the actual HTTP → bridge → owner chain. |
| P03/P05/P15 | The monitor projection remains advisory `review_required`; only the separately verified owner event changes the authoritative current head. A successor is still a separately referenced candidate, not automatically publishable. |
| P29/P32/P33 | Run genuine wrong-signature/content-binding negatives and remove the enforcing source predicate while leaving the negative unchanged. Fixture signatures demonstrate mechanics, not institutional appointment. |
| P35/P38 | AST call presence is not dynamic dispatch. The real default factory resolves to the negative owner, while the positive test supplies another implementation. State this divergence explicitly. |
| P37 | Monitor proposal is `consumer_asserted`; content hashes and source relationships are `recomputed`; signature identity/scope verification is `independently_reconciled` relative to configured trust. The real-world appointment itself is `not_established` in this verification. |
| P40 | The direct-test/default-caller gap is the existing orchestration class one level deeper. The absent root trust composition is a bounded prerequisite, not a new series of per-method repairs. |

## Findings from the pinned tree

### CL-01: producer and distinct replay vocabulary were delivered

`37caf67c35a3a24db15f8e9263b32bd18ad8ee7b` introduced
`owner_events.py`, the owner implementation, the candidate request, the bridge
handshake, the separate C4 profile, and the new test witness.
`git merge-base --is-ancestor 37caf67c3 a534024ee` returned exit 0. The commit's
source changes, rather than its message or a debt note, establish this history.

The vocabulary is:

- `SupersessionCandidateRequest`: predecessor id, persisted successor ref, effective
  time, carried by a persisted `GovernanceMonitorEvent`.
- `ClaimSupersessionOwnerEvent`: candidate-only, purpose `claim_supersession`, rule
  `claim-supersession.v1`, exact monitor/prior-ledger/successor/legal-evidence bindings.
- `ClaimSupersessionAppointment` and `ClaimSupersessionAuthority`: externally supplied
  grant and distinct grant/event verifiers; no implicit trust default.
- `ClaimSupersessionBridgeStatement` and C4 `claim_owner_event_bridge`: a distinct
  owner-event replay record binding appointment, event, packet, prior and next ledger.
  It does not reuse or alter the epoch-shaped `claim_bridge_result` profile.

Evidence: `owner_events.py:55–136,196–335` [S1]; `monitors.py:159–201` [S4];
`c4_persisted_profiles.py:472–491` [S5].

### CL-02: production caller exists, but its default receiver is unappointed

Backward trace from the external entry and forward trace to the producer agree:

`POST /api/v1/control/decision-validity/events`
→ route `publish_decision_validity_event`
→ `ControlPlaneService.publish_decision_validity_event`
→ `_publish_monitor_decision_validity_event`
→ `EpochClaimLifecycleBridgeService.bridge_monitor_event`
→ `claim_owner.produce_owner_event_candidate`
→ `_RepositoryClaimLedgerOwner.produce_owner_event_candidate`
→ `produce_claim_supersession_owner_event`.

The last two arrows require the repository implementation as receiver. The default
`RuntimeServiceContainer.build` and direct `ControlPlaneService.__init__` call
`build_default_claim_ledger_owner`, which returns `UnappointedClaimLedgerOwner`.
The container accepts an explicit `RuntimeContainerOverrides.claim_ledger_owner`
and verifies same-store composition; this is a usable embedding seam, not evidence
that an appointed owner is installed by a deployment.

The candidate producer resolves the monitor, actual successor bytes and prior
ledger before CAS persistence. The bridge enumerates same-store candidates for the
exact monitor and passes the sole candidate into `append_verified_owner_event`.
Multiple candidates yield an explicit nonreceipt in the persisted advisory result.
The monitor result itself never substitutes for owner-event evidence.

Evidence: route `control.py:534–555` [S8]; `run_lifecycle.py:1353–1371,3354–3365,
3428–3576` [S7]; `container.py:203–235` [S6];
`lifecycle_bridge.py:114–216` [S3]; `head_index.py:2718–2744,3848–3888,4150–4153`
[S2]. This is an HTTP lifecycle operation with authz and step-up dependencies.
A new `polisyos-tools` command would duplicate the admission surface; the registered
HTTP operation is its appropriate runnable terminus.

### CL-03: admission, immutable persistence, replay and export share the owner

`resolve_claim_supersession_owner_event` exact-reads the event and appointment,
verifies their actual signatures with strict identities and distinct keys, checks
owner/purpose/time scope, and recomputes source bindings. The repository owner
rechecks the event's prior ledger against the current head, applies an append-only
`SUPERSEDED` event, persists the new ledger and owner bridge, and compare-and-advances
the locked head. The predecessor ClaimRecord is retained. The successor is
referenced, not appended as a self-authorized publication.

Backward trace from the reader is `ClaimLedgerExportService.export`
→ `claim_owner.export_current` → locked head resolution → `_verify_closed_head`.
Replay resolves the original appointment and event, checks exact prior/next bytes,
and recomputes the append before formatting the current ledger. Changing the
appointment for a prior accepted event therefore invalidates resolution.

Evidence: `owner_events.py:296–371` [S1];
`head_index.py:2386–2413,2909–2977,3890–4050` [S2].

### CL-04: the default positive is a separate missing composition

The repository owner's required policy resolver and optional root issuer, issuance
verifier, root index, packet repository, independent walk and evidence index are
load-bearing. `head_index.py:1316–1384` defines the policy/issuer/verifier ports and
the explicit negative policy resolver; `2770–2784` declares the dependencies;
`2802–2808` refuses head verification without an issuance verifier. Supplying a
supersession event key does not create a verified initial root.

The public-verification configuration loader [S11] is a useful comparison only: it
loads already-defined report signing and verification semantics. Copying that
loader for supersession would leave the Claim root policy/issuance/verifier
contract unsatisfied or would invent its evidence. No shell factory or fixture
verifier should be installed as a default to hide this gap.

The complete independent AST walk over **2,654 tracked `src/**/*.py` files** at the
baseline parsed without failures and found these direct calls:

| Callee | Calls in the complete source denominator | Interpretation |
| --- | ---: | --- |
| `_RepositoryClaimLedgerOwner` | 0 | Positive receiver has no source constructor. |
| `ClaimSupersessionAuthority` | 0 | No source construction of event authority. |
| `persist_claim_supersession_appointment` | 0 | No source issuance of an institutional appointment. |
| `persist_claim_supersession_successor` | 0 | Persistence helper is available; no automatic source caller was found. |
| `produce_claim_supersession_owner_event` | 1 | Repository owner's candidate method at `head_index.py:3875`. |
| `produce_owner_event_candidate` | 1 | Bridge at `lifecycle_bridge.py:156`; receiver matters. |
| `append_verified_owner_event` | 1 | Bridge at `lifecycle_bridge.py:177`; receiver matters. |
| `resolve_claim_supersession_owner_event` | 2 | Repository owner replay and append at `head_index.py:2936,3936`. |

Method: obtain `git ls-files src`, filter `.py`, parse each complete file with
`ast.parse`, visit `FunctionDef`, `AsyncFunctionDef`, `ClassDef` and `Call`, retain
enclosing qualified class/function and Name/Attribute call expression; manually
resolve the receiver through the constructors above. These are syntactic counts,
not an assertion about arbitrary dynamic Python dispatch. The coordinator's
existing `production_invocation.py` census is an independent second measurement.

Readback of that receipt reconciles the same **2,654 source files** within **5,669
tracked Python files across `src/`, `tools/` and `tests/`**. It reports the producer
and repository owner methods as `uninvoked`, retains the producer's source caller,
and records `runtime_invocation_established: false`. Its explicit limitations cover
receiver types and HTTP route execution. The manually resolved bridge call above
therefore refines a bounded static diagnostic; an exit-0, zero-regression result
with no source delta cannot prove runtime wiring. Receipt:
`docs/superpowers/journals/producers/verification/raw/base-invocation.json@sha256:d85dd870812f1655103135454c3bf1cbfdcc86602b182448664424801100b099`.

A full literal scan of **90 tracked `docs/plans/active/**/*.md` files**, excluding
`DEBT-REGISTER.md` and `LEDGER.md`, found no occurrence of this exact debt id,
`ClaimSupersessionAuthority`, `produce_owner_event_candidate`,
`claim_owner_event_authority_unappointed`, or the inspected Claim-root-issuance
phrases. Nearby GY-GAP8 addresses completed epoch batches; Scientist Phase 2.1
addresses ledger primitives. Neither supplies the specific configurable root-trust
task sought here. This is not an exhaustive semantic proof that no prose could
describe it; it is sufficient reason to mark registration owed rather than invent
a task destination.

### CL-05: current tests prove a narrower path than their location suggests

The exact integration target [S9] delegates to
`_assert_signed_owner_event_round_trip` in [S10]. Its fixture constructs
`_RepositoryClaimLedgerOwner` using `_FixturePolicyResolver`, `_FixtureRootIssuer`
and `_FixtureIssuanceVerifier`; `_signed_authority` creates independent test keys.
It uses the real CAS producer, bridge, owner append, replay and export, including
an initial unsigned rejection and idempotent retry. This is substantive mechanism
coverage with explicit synthetic prerequisites. It does not invoke HTTP.

The parent of `37caf67c3` contained a live HTTP target that asked monitor metadata
alone to produce `SUPERSEDED`; that was an invalid authority expectation. Restoring
that expectation is prohibited. Restore the route coverage while retaining the
correct signed-event boundary.

Existing HTTP test
`tests/unit/runtime/http/test_decision_validity_api.py::test_live_monitor_ref_reloads_bytes_and_persists_lifecycle_and_epoch_bindings`
already exercises the POST and persisted advisory `review_required` result, but
does not propose supersession or test an appointed owner-event append.

## Acceptance and bounded execution plan

No tests were run during Stage 1. Freeze and commit this decision with the other
decision documents before Stage 2 edits or verification. Retain complete gate and
removal-probe output in the coordinator's gitignored raw receipt directory.

1. Run the unchanged exact integration target and
   the exact negative nodes in step 4 first (each selected explicitly; never a whole file).
   Record the source baseline and elapsed time; do not infer success from history.
2. Extend the existing integration target to enter the registered HTTP route with
   the same explicit test-only root and appointment dependencies installed through
   the existing same-store container/service seam. Produce the candidate from the
   persisted monitor request, sign that exact CAS candidate with the separate test
   grantee key, retry the HTTP monitor request, resolve its persisted bridge result,
   and export the current owner head. Assert superseded predecessor, unchanged old
   bytes, excluded unissued successor, advisory monitor projection, one head
   generation increment, and retry idempotence. Do not replace the current HTTP
   service, producer, verifier, owner, or CAS with a stub.
3. Add the proposed node
   `tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py::test_default_http_supersession_request_preserves_unappointed_owner_limit`.
   Use the actual default container. Submit an exact persisted monitor with a real
   successor candidate and `supersession_candidate`; read the persisted bridge and
   assert `owner_event_production_result.code == "claim_head_absent"`, advisory
   `review_required`, unchanged prior bytes and no authority head advance. Repeat
   with caller metadata claiming a verified/superseded successor: declarations
   cannot supply authority. This must return a typed limit, not fabricate root
   authority to make the demonstration positive. Add the separate proposed node
   `tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py::test_http_supersession_rejects_unresolved_monitor_before_owner_effect`:
   an absent or wrong-vocabulary monitor artifact submitted to the same POST must
   be rejected by exact monitor resolution before any bridge/owner effect. Assert
   the runtime's 422 `monitor_event_unresolvable`, unchanged predecessor bytes and
   no returned bridge receipt. This establishes fake-input rejection at the real
   resolver, rather than mistaking an unappointed-owner refusal for content validation.
4. Run the existing negative nodes in [S10]:
   `test_monitor_metadata_cannot_advance_current_claim_head`,
   `test_unsigned_candidate_reaches_consumer_with_empty_appointment`,
   `test_current_head_replay_cannot_substitute_a_new_matching_appointment`, and
   `test_owner_event_verification_rejects_present_but_unproven_evidence`
   (`unsigned`, `wrong_scope`, `revoked`, `fake_successor`, `wrong_vocabulary`).
5. In a bounded isolation, remove the predicate
   `successor.claim_id != event.successor_claim_id` from
   `owner_events._validate_candidate_content` only. Keep the existing
   `...[fake_successor]` test unchanged. It must turn red because a signed event
   with invented successor identity now advances instead of returning its expected
   nonreceipt. Restore exact source bytes and prove it returns green. A separate
   signature-removal probe may remove the signature/identity admission conditional
   from the resolver while retaining exact source checks; unchanged `[unsigned]`
   must turn red. Removing only the signature-status term is insufficient because
   the key/identity checks also reject an unsigned event.
6. For the production-caller negative, remove the bridge's call to
   `produce_owner_event_candidate` and its result-handling block while retaining
   candidate discovery, append and persisted result paths. The unchanged proposed
   default-HTTP negative must turn red at its missing typed production outcome.
   This proves the request reached the production candidate boundary even though
   the honest default result is a refusal. Restore exact bytes and rerun. Also
   removing owner-event append/application must break the unchanged HTTP positive
   at its authoritative export assertion, not merely at a call counter.
7. After reviews freeze source, run affected owner/bridge/API/importer tests, Ruff
   and architecture guardrails. No directory-wide, backend-wide or CI-parity run
   is permitted, including at closeout; every selected test node is explicit. A failing gate is inherited only after the slice-base replay and
   denominator isolation required by P41; otherwise record `not_established`.

The HTTP request/reader/candidate/append mechanism can be verified with a declared
authority limit. The exact row's appointed-owner conjunct remains unmet: code and
test keys cannot appoint an institution. The default positive additionally remains
`implemented_but_not_orchestrated` relative to the repository owner and
`verification_missing` at the HTTP supersession witness until the planned tests
run. Root trust composition is an explicit engineering residual, not a fabricated
closure or an unnamed assignment to a closed task.

## Review stop rule and scope

P40 bucket before repair: another example of absent/default root trust is the same
declared prerequisite class, not a new repair round. The smallest closing capability
is an actual production root policy/issuance verification and owner composition,
plus deployment-supplied independently trusted authority. The measured missing
constructor and inspected root ports establish why a supersession-only key loader
does not close it. If route testing reveals a different concrete bypass in the
supersession producer/resolver/replay, classify it as a new class and batch its
smallest structural repair before the expensive wave. No iterative expansion into
initial issuance, scope adjudication, legal interpretation, or notifications.

## Source anchors

Every `[S#]` denotes the full path at the source baseline above and the listed Git
blob. These are tree facts, independent of the debt narrative.

| ID | Path | Blob |
| --- | --- | --- |
| S1 | `src/polisyos/scientist/evidence/claims/owner_events.py` | `3e83ddeac81e889a7289e703b0253e3a04b652d4` |
| S2 | `src/polisyos/scientist/evidence/claims/head_index.py` | `631fcfeeeb2dfc29b6308fd4259f433e132a1b40` |
| S3 | `src/polisyos/scientist/governance/continuous/lifecycle_bridge.py` | `bdd9c24f2baaf8c80badcfe05e8d6762c3776298` |
| S4 | `src/polisyos/scientist/governance/continuous/monitors.py` | `8fe83d14dda67a91b5655761ca3be3f5eb11f6d6` |
| S5 | `src/polisyos/core/contracts/c4_persisted_profiles.py` | `59623501f71f545276f132f42d6d343cdbd41187` |
| S6 | `src/polisyos/runtime/http/container.py` | `d6638eb8e85420d1e528a025895d792da76cd4d7` |
| S7 | `src/polisyos/runtime/http/services/control/run_lifecycle.py` | `9f8f81f227c43207d745b2cf0af6ba883b14bcc2` |
| S8 | `src/polisyos/runtime/http/routes/control.py` | `f1331c7da27c1d65688d484539063bda66b9357b` |
| S9 | `tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py` | `4d035ced7b62e6d84d1ca11bc59a464ab3c859e7` |
| S10 | `tests/unit/scientist/governance/continuous/test_owner_event_producer.py` | `69178e7aac605836e5f960b2805082a88393bd08` |
| S11 | `src/polisyos/runtime/http/services/public_decision_verification_configuration.py` | `c1ceff3eacb59d6fa45ed6aa946ee829029f67e5` |

Architecture: `architecture/imports/policy.toml@a534024ee` (blob
`3ba18adb3a7d69dafe7c87ee5686968de0994ad4`) permits runtime → Scientist; the
candidate/owner logic stays within Scientist and shared C4 vocabulary within core.
`architecture/public_surface/contract.toml@a534024ee` (blob
`11bf31254e4bb5a83b7eddec586a6dfd946b33a9`) keeps HTTP subpackages internal.
This proposal introduces no facade or public API contract.
