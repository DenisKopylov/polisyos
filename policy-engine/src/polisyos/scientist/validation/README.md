# Validation (`polisyos.scientist.validation`)

## Purpose

`polisyos.scientist.validation` owns Scientist decision-grade validation:
metric diagnostics, fairness audits, phase publication preflight, decision
validity, verified-policy contracts, reliability scoring, and proof-carrying
verification.

## Where to Start

- Stable package facade: [`__init__.py`](__init__.py)
- Decision lifecycle validity: [`decision_validity.py`](decision_validity.py)
- Verified policy models and services: [`policy_verified/`](policy_verified/)
- IC and implementation-conformance verification: [`verification/`](verification/)
- Metric and fairness validation: [`metrics.py`](metrics.py), [`benchmarks.py`](benchmarks.py), and [`fairness_audit.py`](fairness_audit.py)

## Phase-5 publication selection

An analyst-facing Phase-5 publication requires an owner-selected six-judge attempt.
Inline verdicts and archived history are retained as reported data; neither
establishes that attempt. The current preflight reports
`judge_selection_status=not_established` and blocks publication until a completed
staged composition connects the verified body, governance assessment, judges,
and final governance result. Historical artifact readers remain available.

An explicitly selected protected Engine attempt can run all six judges with
restricted candidate inputs and persist a `candidate_diagnostic` bound to the
actual body, candidate, governance, judge attempts, and threshold snapshot. It
rechecks the live registry after evaluation and refuses missing, invalid, or
changed snapshots. Its `current_at_evaluation` status is historical: a later
consumer must recheck currentness. The candidate diagnostic is available in the
production builtin registry, but no production workflow selects it yet. The
staged production workflow and shared completion publication remain
`implemented_but_not_orchestrated` and
`bridge_missing`; this diagnostic is not a publication decision. Neither a typed
verdict nor the snapshot supplies calibration or human appointment authority.

The search owner's `judge_threshold_basis` adapter can persist and recheck the
selected live registry snapshot, including its source and resolver implementation.
Its frozen view preserves every captured entry. It is wired to the candidate
diagnostic, but staged publication remains `implemented_but_not_orchestrated`:
the snapshot alone does not prove that all required thresholds exist, that they
are calibrated, or that a named approver has authority.

## Policy request scope

The request producer records the caller's target jurisdiction and the field that
supplied it in `PolicyRequestFrame` v1.1. A Scholar research jurisdiction is a
source-search scope and does not supply the policy target. Missing, conflicting,
invalid or unprofiled request inputs refuse before legal retrieval. Historical
v1 frames remain readable, but their jurisdiction alone cannot show whether it
was declared or supplied by the former default; legal retrieval reports that
scope provenance as not established. The v1.1 source is caller-asserted context,
not institutional authority. Candidate body and report intake also require the
option and source-verification artifacts to bind the exact selected request, and
the option to bind that source report, by full manifest profile. Those joins do
not establish producer provenance or legal authority; unbound historical artifacts
remain readable.

## Legal claim candidates

`SourceVerificationReport` v1.1 carries retrieved facts and model-proposed
interpretations as canonical `ClaimRecord` candidates, with their proposed text,
source facets and raw model fields retained. A quotation, search-candidate label,
or model response does not independently verify a legal conclusion. These
claims are context-only, not evaluable or publishable, and the report records
`legal_claim_verification_not_established` as a critical gap requiring expert
review. Policy options may remain hypotheses; verified legal findings and options
are not admitted by this producer. Packet and review projections preserve the
limitation rather than infer legal basis from a populated section. In newly
generated reports, `verifier_calls_total` counts LLM candidate-extraction
attempts plus any carried-forward historical count; it is telemetry, not evidence
of independent legal verification. New source-producer events expose the
candidate count and `legal_verification_status`; their `verified_claims` value is
the string `not_established`, so consumers must not treat it as a number. A
human-review packet retains any caller-supplied checklist, but the public review
summary labels a positive legal-documentation flag `consumer_asserted` and keeps
that item unresolved for public-sector risk without independent admission.

Historical v1 reports remain readable and retain their original recorded labels;
those labels are unbound to an independent semantic verifier and cannot be
promoted into current legal findings. New v1.1 artifacts require readers that
understand the candidate fields. An institutional legal verifier and reviewer
appointment are not supplied by this change.

## Compatibility

The old first-level packages `polisyos.scientist.decision_validity`,
`polisyos.scientist.reliability_scorecard`, `policy_verified`, and
`verification` were removed after reaching zero non-compat callers. New code
should import from this validation hub.

## Epoch-validity owner intake

`DecisionValidityService` admits an epoch transition only through its configured verifier. It
reconciles the complete owner target denominator, persists the complete pending freeze before the
first packet mutation, resumes idempotently after a crash, and exposes completed evidence only by
content-bound receipt ref. Generic dependency events cannot admit or clear semantic-epoch state.
Runtime can configure canonical production and independent origin verification on this same
owner. Empty deployments retain `NoEpochTransitionVerifier`; the HTTP request cannot supply a
verifier or authority. A signature never substitutes for canonical producer provenance.

Scientist can also persist and exact-read a strict semantic-epoch impact snapshot from the same
nullable owner walk used by the legacy denominator resolver. Strict materialization refuses a
missing or non-CAS owner artifact id without changing legacy resolver behavior. A lazy write-once
owner index is available for reconciliation admission bindings and creates no directory until a
sidecar-aware admission writes its first binding. When an explicit Runtime reader is configured,
first admission validates the exact sidecar and freezes its handle before the unchanged v1 pending
batch; restart replay resolves only that frozen handle and never consults the live owner index.
An entirely unconfigured owner has a typed unavailable reconciliation reader. An explicitly
injected legacy verifier with no reader retains its previous behavior. Runtime production
composition installs a producing reader which delegates admission to the existing strict reader.

`epoch_certificate_issuance.py` is a neutral internal protocol and sealed canonical completion
witness. The real decision-packet builder invokes this port before and after persistence; Runtime
owns the concrete complete-basis resolver and admission index. A missing resolver persists a typed
nonreceipt, and arbitrary invocation labels cannot become a semantic-epoch dependency.

## Common Commands

Run from the repository root (`policy-engine/`).

- Import smoke: `uv run python -c "from polisyos.scientist.validation import DecisionValidityService, PolicyRequestFrame, verify_incentive_compatibility; print(DecisionValidityService.__name__, PolicyRequestFrame.__name__, callable(verify_incentive_compatibility))"`
- Focused validation tests: `uv run pytest tests/unit/scientist/validation tests/unit/scientist/governance/test_ic_verification.py tests/unit/scientist/governance/test_ic_conformance.py -q`

## Last Updated

- Last updated: 2026-05-05


## Registered materialization admission (source profile v1)

The existing `DecisionValidityService` owns a single immutable source-registration,
occurrence, admission-epoch, selection, event and dedupe quantity. It publishes a
constant-sized root under its existing `decision_validity/epoch_batch.lock` fence.
Immutable radix-index parts are reused; a transition or fresh source read does not
copy or parse every unrelated head/history. Unreachable staging objects have no
current-use authority. Replacing the root followed by a failed directory `fsync`
is an uncertain operation, resolved by the original committed event and actual
durability reconciliation before acknowledgement or a current-positive read.

Registration issues a stable source incarnation for a protected configured key.
Admit records an actual captured acquisition occurrence and never changes default
selection. Supersede explicitly selects a carrier; withdraw targets one exact
revision/use; readmit creates a new epoch without reviving any old carrier. Global
generation changes from independent sources do not revoke unaffected carriers.

The neutral private port `source_admission_port.py` accepts only factory-registered
identities and canonical producer captures. It does **not** itself establish an
installed Runtime grant or a live Fabric SQL capture. C106 must wire those actual
trusted construction and producer closures; caller DTOs, arbitrary callbacks,
manifest shapes, issuer strings and boolean authorize methods are insufficient.
The unconfigured producer path fails closed. Store tests seed the private owner
state explicitly and prove storage/CAS/read behavior only; they are not real SQL
or Runtime factory acceptance.

Intake reuses the complete actual DataSnapshotOwnerBound field/role requirements,
including present optional evidence/warnings refs. Every required artifact is an
exact selected-profile ref and raw content is checked; binary payloads are not
forced through JSON canonicalization. The real producer capture is separately
persisted and content-bound. CAS work happens outside the short owner fence, then
one fresh durable root is selected for decisive current use. Empty, legacy,
uncovered or inconsistent bases remain `unknown`.

`read_source_current_use` is a bounded internal admission projection at
`owner_fence_linearization_point`. It does not claim external SQL currentness or
scientific/legal admissibility, and is not a promise until network delivery.
C106 must bind actual Foundry consumed inputs to immutable carriers and call this
same owner for both default and explicit/cache API selection. No protected refs
are added to the public Research DAG. Existing packet/epoch stores remain
unchanged; covered packet migration is still bridge work, not dual source authority.

The optional `SourceAdmissionReadBudget` threads a caller-owned aggregate through
current-use revalidation. Every exact tenant/cell-scoped selected CAS manifest
and member read is bounded and charged from the Core owner receipt, including
known transfers on refusal; unmeasured transfer marks the aggregate unestablished.
An exhausted or unestablished budget yields `unknown`, without changing the owner
state. This selected-CAS transfer cap excludes owner root/trie state I/O, other
DB work, external SQL and OS/device I/O; it is not a full-request byte cap.
Unbudgeted legacy callers retain their existing behavior. The Runtime protected
consumer must provide its shared budget and combine it with its terminal trace
accounting before emitting a bounded claim.

The first source profile reuses concrete local `FileSystemCAS.for_tenant` selected
view ownership, bound to the verified issuer or the committed registration. A
foreign-only view, changed CAS root, unsupported backend or missing ownership
cannot satisfy current use. The kernel does not trust a manifest tenant string
as ownership proof. POSIX local filesystem locking/link/rename/fsync semantics
must be qualified in the actual deployment; no NFS/distributed durability or
backend-wide performance claim is made. Existing Core CAS ownership-index cost
is not claimed by the bounded source-index oracle.
