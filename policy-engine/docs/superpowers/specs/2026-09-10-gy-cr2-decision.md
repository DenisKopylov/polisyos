# GY-CR2 — Constrained response state through durable custody

Decision date: 2026-09-10. Lane merge base: `992aa493f`. Owning package:
`polisyos.runtime.quality`. Routes: `W5-S12`, `W5-S24`. This decision precedes
source changes; the commissioning prompt authorizes execution after root commits
and reads back the complete Stage-1 package from its attached branch.

## Property, authority, and exact research basis

The deliverable is a persisted, append-only **candidate** E/X/V/C transition
engine. It validates the factored product, preserves the original event history,
and projects the existing custody status alongside coordinates. It cannot appoint
an institutional signer, authorize an external action, or treat a request as an
execution receipt. `WP-04`–`WP-08` remain withheld; `WP-08` explicitly permits the
mechanical build with the signature slot empty.

The research specification is not merely OPS-R5 §4.3. Its correction owner is
`docs/research/policy-operations/ops-r5/amendment-state-invariants.md`, finding
`AUD-F06` in `amendment-ledger.md`. The original unconstrained Cartesian-product
reading is superseded. The named forbidden conditions are:

- `FCT-01`: material patched/reissued intervention plus intact confirmation of the
  affected claim without admitted equivalence evidence.
- `FCT-02`: confirmed-unacceptable epistemic state, terminated exposure, and intact
  confirmation of the same positive claim depending on the unacceptable basis.
- `FCT-03`: rollback plus full exposure without fresh admitted restart evidence.
- `FCT-04` is a reverse case: withdrawal does not itself terminate an independently
  grounded external policy. Claim-dependent paths close; unrelated historical
  claims are not erased. The absent institutional evidence owner cannot be
  replaced by an inline `independent_basis=True` declaration.

Additional obligations bind exact claim/population/version/measurement identity,
redesign's new causal object, explicit co-transitions, event identity and time,
append-only corrections, and preservation of the external/custody distinction.
These are validation rules for candidate representation, not newly ratified
operational policy. A syntactically typed tuple is not substantive evidence.

## Owners inspected and chosen composition

| Owner | What is composed | Boundary retained |
| --- | --- | --- |
| `runtime/quality/adaptation_transition.py` (`GY-CR1`) | `AdaptationTransitionRuntime.open`, `submit`, `process`, `snapshot`; `AdaptationTransitionRequest` and candidate charter; exact durable identity, CAS, checkpoint and failed-safe decision | Source and schema unchanged. Signer/substitute remain typed-empty; no privileged private success payload widened. |
| `runtime/http/services/control_plane_store.py` | CR1's existing outbox uniqueness/recovery transitively | No SQL, new table, direct repair or new store API. |
| `core/artifacts/store.py`, `fabric/io/atomic.py` | CR1's CAS/content readback/process lock transitively | No second CAS implementation or cross-writer lock claim. |
| `runtime/quality/vocabulary_crosswalk.py` (`GY-VC1`, same lane) | Canonical E/X/V/C and SMDV source vocabularies, version binding, loss refusal | No local cause enum or duplicate factor owner. |
| `pdc.AuthorityBoundary` | CR1's candidate boundary | No local authority system. |
| `runtime/quality/case_lifecycle.py`, `core/contracts/projection_semantics.py` | Inspected to distinguish claim lifecycle from response custody status | Neither is rewritten or used to infer a new lifecycle transition from an axis alone. |
| OPS-R5 amendments and `withheld-propositions-register.md` | Explicit named invariants and non-effects | Research does not appoint a competent grant or provide valid restart/equivalence evidence. |

The delivered CR1 vocabulary was read before comparing predicted symbols. Its
request context is `dict[str, str]`, and snapshot returns those exact contexts with
the persisted request/decision refs and existing `pending`/`failed_safe` status.
That is a real public composition seam; no CR1 extension is necessary.

**Choose integration through CR1, not an independent machine.** CR2 serializes a
strict versioned candidate event/envelope into the existing request context. Each
accepted append is one CR1 request, whose identity contains the aggregate identity
and sequence. The previous ticket and previous content identity bind the chain.
An aggregate-scoped process lock serializes head discovery and append. Sequence
identity is derived solely from aggregate plus sequence, never event ID. The
existing CR1 exact-key lookup discovers known request tickets; every substantive
readback then uses its public `snapshot`. Scanning deterministic slots to the
first absent one establishes the complete head without a second cursor store.
Stale predecessors, sequence gaps, mismatched aggregate/claim/contract identity
and changed same-slot bytes refuse; a genuine duplicate reconciles exact bytes.
This documented intra-Runtime private discovery seam changes no CR1 owner code.
CR1 validates, persists, deduplicates, recovers and publishes the candidate custody
decision. CR2 reloads through `snapshot` and reconstructs the factor transition;
it never treats the write-side object as admission. An identical event reuses the
same request identity; conflicting bytes refuse. A late observation is a new
reaction referencing the prior ticket, with correction/supersession disposition;
the previous request bytes and decision remain unchanged.

This deliberately avoids a second state store or unconnected phase-8 machine.
CR1 remains the durable custody engine; CR2 is its typed state-transition consumer
and producer. A new SQLite table or detached JSONL journal would duplicate CR1's
identity/recovery protocol. Modifying CR1 to know every factor would reopen a
completed task and couple generic custody to the still-candidate operational
research. Neither alternative is justified.

## Transition admission and representation

A strict frozen event binds scenario/aggregate identity, sequence, predecessor,
contract and affected claim object (including population, intervention version and
measurement epoch), current/requested factors, observation and receipt time roles,
operation family, diagnosis, evidence references, desired claim consequence and
provenance. Intake reparses supported model construction/copy outputs; extra fields
or forged institutional slots cannot bypass validation.

No input boolean or a name is accepted as an authority-grade equivalence, restart,
or external continuation proof. Those positive authority paths remain refused
until their demanding owner supplies resolve + exact object/content binding +
independent verifier provenance + evaluation-time validity. Candidate declarations
remain visible as declarations. This is not a reason to omit the state engine:
forbidden combinations and the absence reactions are mechanically decidable now.
The FCT-04 reverse case preserves the distinction between **reported external
exposure** and an **allowed claim-dependent continuation**: an external policy may
be reported continuing while the latter is false. The engine does not terminate
another institution's policy merely because our claim is withdrawn.

The candidate transition outcome records requested coordinates separately from
admitted custody coordinates, refusal reasons, preservation of containment demand,
posterior/world/action permission (all false), and CR1 ticket/snapshot references.
No coordinate silently implies another. A material version/measurement change
cannot inherit intact confirmation by default. A restarted/expanded request without
independent evidence is refused. Unresolved cause can retain a declared high-harm
containment demand without claiming execution or causal confirmation.

Atlas projection is status preservation, not a nearest-neighbor function over
coordinates. The readback exposes CR1's existing `pending`/`failed_safe` lifecycle
status; E/X/V/C and typed limitation/reaction details travel beside it. Factor
changes cannot mint `authorized`, `executed`, `publishable`, or any new Atlas value.
GY-VC1 validates the crosswalk; its blocking loss is a refusal.

## Production callers, artifacts, and surfaces

| Mechanism | Production caller established by this task | Remaining integration |
| --- | --- | --- |
| CR1 durable custody | New `runtime/quality/constrained_response.py` calls its public `submit/process/snapshot` | CR1 is now called by a non-test module; completed CR1 bytes remain untouched. |
| CR2 factor admission/readback | New `runtime/quality/response_corpus_evaluator.py` (`GY-CR3`) invokes the same durable path; the shared executable local worker is `tools/check_response_corpus.py`, which invokes the same CR2 path | Live DDM/monitor-trigger scheduling is deferred to named not-started tasks GY-O1 and GY-O3, because this lane supplies no institution or external executor. No completed task is reopened. |
| CR2 audit projection | CR3 evaluator consumes the persisted readback and emits conformance evidence | HTTP/dashboard integration is `surface_out_of_scope`, assigned to the Atlas DS12 successor custody projection. No action affordance is exposed. |

The evaluator is a production audit module, not a test importer. Its invocation
must be demonstrated against persisted owner state. This caller does not establish
live field deployment, which remains explicitly unclaimed.

## Deciding falsifiers and red-first sequence

1. Before mechanism code, add explicit tests in
   `tests/unit/runtime/quality/test_constrained_response.py`. Run exact nodes and
   retain the full expected failure; import absence is only the first boundary.
2. Exercise every FCT-01/02/03 condition through real request admission, not only a
   constructor. Generate pairwise and three-way coordinate mutations from the
   source-owned factor domains; hold unaffected coordinates/claim identity fixed.
   Compare against an independently written truth table of the named predicates,
   not the implementation's reason helper. A changed decisive field must produce
   its own reason; shared signer absence is not a substitute for detecting FCT.
3. Demonstrate FCT-04 in both directions: withdrawn claim with declared separate
   external continuation remains representable without terminating external policy;
   claim-dependent continuation stays denied without substantive evidence. Neither
   case grants PolicyOS an external execution capability.
4. Persist a request, process/reopen through CR1, append a later-received event whose
   observation precedes the prior observation, and re-read both records. The new
   record must reference correction/supersession; previous canonical bytes, ticket,
   decision and status must remain intact. Same identity/different bytes refuses. Concurrent same-head appends, stale-head
   branch attempts, foreign predecessor tickets, and skipped sequence slots must
   also refuse; the complete durable sequence remains contiguous and single-head.
5. Enumerate the complete factor product twice (Cartesian product and independent
   nested loops), reconcile exact tuple sets and unreadability/errors. Check every
   forbidden product and all pair/triple perturbations, not a selected example.
6. Remove the invariant enforcement in an isolated imported copy while retaining
   DTO markers; the unchanged falsifier must fail. Remove chain/history binding in
   isolation; replay/late-correction negatives must fail. Retain full outputs.
7. Compare output lifecycle vocabulary to CR1's existing schema source, not a
   hand-pinned surrogate; zero additions is the binding no-lattice-extension proof.
8. Run only named test nodes, explicit CR1 importer nodes, recomputing corpus and
   crosswalk validators, and Ruff over named changed files. Root runs architecture
   guardrails once; new deep-import creep is a stop, never a sync. A freshness
   environment crash is an unrun check, never a successful stage.

## Pattern, version, and scope pass

Relevant patterns are P01/P02 (mechanism with caller), P04/P05 (factor versus
lifecycle/authority), P07/P08 (version and event time), P27/P28 (compose CR1 rather
than another machine), P29/P32/P33 (behavior, substantive evidence, mutants), and
P35/P37/P38/P40 (complete domains, predicate provenance, divergence and bucket rule).
A repeat escape of the same class triggers mechanism widening or a declared bounded
residual with its falsifier, not another instance patch.

Initial capability deficits are `bridge_missing`, `verification_missing`, and
`semantic_test_missing` for CR2; institutional execution/equivalence/restart proof
issuance is `producer_missing` and remains outside this task's authority claim.
Acceptance closes the candidate producer → CR1 persisted artifact/event → CR2
readback → CR3 consumer/audit chain. No governed epoch or artifact reissue is
planned. Any measured epoch impact is declared from `992aa493f` before writing;
no existing owner/artifact is silently reissued. Root alone owns git commits,
README/`__init__`, GY standing rows and the completion journal. DEBT/LEDGER and
already-completed mechanisms are read-only.

## Execution refinement after independent review

The read boundary applies the same generic predecessor/current-state predicate to
both genesis and successors; direct CR1 storage cannot bypass CR2 history admission.
The exact affected claim is stream-bound, so no caller boolean disables FCT-02.
Restart/expansion uses the actual exposure-coordinate change under AUD-F06, regardless
of the operation name. The shared checker entry point is the executable audit worker;
a second CR2 CLI would duplicate the same orchestration and is not built. Foreign
direct CR1 callers may persist malformed/orphan candidate requests, but no claim is
made that these become admissible CR2 history. The generic read boundary refuses them.
