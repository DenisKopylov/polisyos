# GY-CR3 — Sealed response sequences and independent conformance evaluation

Decision date: 2026-09-10. Lane merge base: `992aa493f`. Owning package:
`polisyos.runtime.quality`. Routes: `W5-S14`, `W5-S26`; paired-proxy rule `W4-K04`.
The commissioning prompt authorizes Stage 2 after root commits and reads back all
Stage-1 decisions. This document does not authorize external response operations.

## Required result and research correction

Build the OPS-R5 response corpus as actual immutable event sequences, sealed
transition expectations, an independently implemented evaluator, and a persisted
runtime replay. Its audit result is candidate-mechanism conformance. It is not a
field benchmark passage, a signer appointment or an external execution receipt.

The binding research correction is `AUD-F08` in
`docs/research/policy-operations/ops-r5/amendment-ledger.md`, expanded by
`amendment-response-corpus-gap.md`. It explicitly rejects twenty thin labels as a
corpus. Each packet must bind initial state and exact contract/claim/version,
ordered events, observation/valid/transaction time, observation health and maturity,
SMDV-1 or declared unresolved diagnosis, blocking/contributing lanes, waiting and
premature harm, reversibility/blast radius, authority absence, clocks, requested
versus admitted versus executed transitions, forbidden alternatives, restart,
duplicates, late correction and public-history consequences.

The source family distribution is OPS-R5 §6.1: A0 observe has two packets; A1
investigate, A2 contain, A3 refresh, A4 adjust, A5 pause/rollback and A6
terminate/redesign have three each, giving twenty. The corpus checker enumerates
all records twice by independent parsers and reconciles identities, family totals,
operation coverage and file types; unreadable/malformed is an error, never zero.
This source count is a specification, not a claim that packets already exist.

## Existing owners and narrow composition

| Existing owner | Reuse and boundary |
| --- | --- |
| `runtime/quality/adaptation_transition.py` (`GY-CR1`) | Durable request/decision/snapshot, clocks, duplicate and recovery semantics; called through CR2. Source stays unchanged. |
| New `runtime/quality/constrained_response.py` (`GY-CR2`) | Sole runtime under evaluation; production evaluator submits real packets through it and reads persisted receipts. |
| New `runtime/quality/vocabulary_crosswalk.py` (`GY-VC1`) | Production parser's source vocabulary; oracle does not import its decoder or runtime comparison helpers. |
| `core/artifacts/store.py`, control outbox, Fabric process lock | Transitively through CR1. No benchmark-only shadow database or claimed fake kill proof. |
| OPS-R5 §6.3 and amendments `AUD-F06/AUD-F08` | Sealed specification inputs for evaluator-owned expectations and named guardrails; not an operational authority grant. |
| `withheld-propositions-register.md` `WP-04`–`WP-08` | Institutional slots stay empty. A missing signer cannot make all semantic negatives vacuously identical. |

`AUD-F08` asks for grounded event inputs. Here that means concrete persisted
candidate owner events with exact values and causal discriminators, derived from
the specified refusal scenarios, not invented empirical population outcomes. The
surface scope is explicitly **local mechanical conformance**, `surface_out_of_scope`
for live field performance, production latency thresholds and external authorization.
No corpus score is promoted to general policy assurance.

## Oracle independence before implementation tuning

Corpus inputs and expected transition records are separate versioned artifacts
under `docs/reference/response-corpus/`. Expectations are sealed before runtime
implementation tuning. Every expected record binds the packet bytes by SHA-256,
specification finding IDs, the evaluator owner identity and expected reason family.
The evaluator owns an independent input interpretation and transition calculation;
it imports neither the CR2 decoder, its fixture loader, nor its comparison helper.
Runtime JSON decoding uses Pydantic-core `model_validate_json`; oracle packet
decoding uses the separate standard-library JSON parser and independently
validates primitive structure. Sealed expectations use TOML and `tomllib`. Runtime
does not import the oracle decoder or standard-library JSON. SHA-256 is shared
cryptographic infrastructure, not a decoder, loader or semantic comparison. Runtime observation is a transport object crossing the
boundary; the oracle receives raw packet bytes and independently produces expected
facts. Oracle expected values are never populated by copying a runtime run.

A callable with an independent-looking name is insufficient. The checker validates
the reachable callable/module identity closure and refuses a forbidden import or
shared helper, including aliases. A dependency-poisoning test changes runtime
decoding semantics and proves oracle interpretation does not change. The removal probe installs the runtime decoder/loader/comparator at
the oracle seam while leaving declared owner strings and seals intact; evaluation
must become red before it can grade. The second probe corrupts one expected
semantic field without changing its seal and must be refused. A valid new seal over
an incorrect expected result must fail independent recomputation. Thus checksum
integrity does not stand in for correctness or independence.

The independence criterion is engineering independence of the parser, expectation
logic and comparison code, not independent institutional appointment. Appointments
remain typed-empty. This distinction is carried in the evaluator result so an audit
consumer cannot re-label a local conformance check as an externally appointed grade.

## Corpus and operation design

Each family contains meaningful multi-event sequences rather than a family string:

- A0: immature/quiet follow-up and later matured observation; no quiet-window harm
  clearance. An explicit provider absence retains unknown observation health.
- A1: threshold investigation, exploratory/FDR subgroup alarm, and unresolved
  low-harm investigation. Discovery never grants cause, learning or world write.
- A2: unresolved high waiting harm, good-average/blocked-subgroup divergence, and
  absent owner after hours. Predeclared containment demand is retained with no
  authority expansion and escalation; no external action is claimed executed.
- A3: measurement-invalid refresh, denominator/definition correction and
  recalibration/recompute; policy-effect learning remains off and measurement
  epoch/claim history cannot silently inherit confirmation.
- A4: delivery adjustment, narrow-scope request, and material partial reissue. A
  patch cannot inherit the affected intact claim without substantive equivalence.
- A5: duplicate pause, rollback with unresolved residue, and alert disappearance
  versus restart evidence. At-most-once own custody publication is distinguished
  from external execution, which stays unestablished.
- A6: confirmed-unacceptable termination request, redesign/new causal identity,
  and unresolved legal/safety clock. Late amendments open correction/supersession;
  withdrawal does not mechanically terminate an externally continuing policy.

Counterparts within a packet or across a paired packet keep the observed numeric
movement identical while changing exactly a decisive context: maturity, health,
waiting harm, premature-action loss, reversibility/blast radius, affected identity,
clock, duplicate identity, restart evidence, or requested/applied distinction.
Authority contrast is unsigned versus merely owner-stamped/forged authority: both
are refused with different substantive failure provenance, not fake appointment.
No positive authority witness is manufactured while WP-08 is typed-empty.

Every operation named by `AUD-F08` has an explicit event/expected record: observe,
early warning, diagnose, refresh, recompute, recalibrate, adjust implementation,
narrow scope, partial reissue, pause, rollback, redesign, terminate, and restart or
remain-contained. A pause witness cannot close rollback coverage; labels alone do
not satisfy operation coverage.

## Guardrail arithmetic and high-harm obligation

The deciding result reports each OPS-R5 §6.3 guardrail separately:

| Counter | Observable escape checked independently |
| --- | --- |
| `threshold_auto_action_escape_count` | Numeric crossing becomes action permission without substantive basis. |
| `diagnosis_bypass_count` | Cause-requiring request lacks admitted diagnosis yet passes its semantic gate. |
| `unauthorized_transition_count` | Protected transition becomes authorized with no competent appointment. |
| `protective_action_missed_count` | Predeclared high-harm custody containment demand or conservative posture disappears. |
| `posterior_learning_bypass_count` | Non-admitted learning claim becomes permitted. |
| `world_write_bypass_count` | Candidate monitoring/discovery becomes world-write permission. |
| `restart_without_evidence_count` | Alert quietness or unverified restart payload reopens exposure. |
| `silent_version_reuse_count` | Material treatment/measurement change silently inherits the exact old claim identity. |
| `duplicate_irreversible_action_count` | Duplicate identity repeats custody publication or asserts a second external effect. |
| `historical_rewrite_count` | A late event overwrites earlier request/decision rather than referencing a new reaction. |
| `subgroup_or_spillover_mask_count` | Aggregate benefit clears an independent blocked subgroup/spillover. |
| `owner_absence_treated_as_approval_count` | Owner silence/team string becomes appointment or approval. |

The zero-escape result is bounded to this complete corpus. The declared high-harm
containments are preserved **as custody no-expansion and containment requests**.
Actual protective operations remain withheld; counting them as performed would be
an authority escape. Guardrails are computed from runtime observations and sealed
expectations, not stored counter values supplied by the implementation. A
mechanism-removal mutant for each guarded behavior must make its counter nonzero
or cause a specific conformance failure; broad `failed_safe` alone cannot earn zero.
Latency measures are retained only as observations; no performance threshold is
invented.

## Production callers and delivery surface

`runtime/quality/response_corpus_evaluator.py` is an executable production audit
consumer of CR2, and CR2 is the non-test production caller of CR1. A command-line
checker under `tools/` invokes the evaluator against real temporary owner stores,
verifies immutable corpus and oracle seals, and emits a strict audit report. The
checker is the non-test caller of the evaluator and its independently owned oracle.
Test code calls the same paths; it is not the only importer.

The local evaluator/report is the audit surface. HTTP/Atlas presentation is
`surface_out_of_scope`, deferred to the Atlas DS12 successor custody projection.
Live telemetry scheduling is deferred explicitly to not-started tasks GY-O1 and
GY-O3; their receiving callers do not yet exist. Closed tasks are not edited. The caller chain makes the mechanical capability
inspectable without pretending that field deployment already exists.

## Files, red-first order, and falsifiers

Mechanism paths: `src/polisyos/runtime/quality/response_corpus_evaluator.py`, an
independently owned `tools/check_response_corpus.py`, and the versioned packet/oracle
artifacts under `docs/reference/response-corpus/`. If separating pure oracle logic
into `tools/response_transition_oracle.py` makes forbidden dependency closure
smaller, do so; runtime must not import this tool. Tests mirror runtime at
`tests/unit/runtime/quality/test_response_corpus_evaluator.py`. Shared README,
`__init__`, git and plan/journal changes are root-serialized.

1. Materialize substantive packets and seal independently calculated expectations
   before implementing CR2 runtime behavior. Verify the source family denominator
   and all operation records via two independently written enumerations.
2. Run named red tests for complete replay, all twelve counters, paired distinct
   reason assertions, high-harm preservation, corrupted corpus/oracle refusal,
   oracle-independence removal, duplicate/late persistence, and proxy mutants.
3. Implement runtime transport/parser and independent oracle/evaluator logic with
   no semantic-helper sharing. Reconcile every expected and forbidden transition
   against a real CR1-backed CR2 readback.
4. For every paired proxy case, replace the property with its named proxy while
   retaining markers; the pair fails for that context-specific reason. A common
   absent-signer failure is inadequate. Retain complete mutant and removal outputs.
5. Run checker `--check`; corrupt a deciding report/oracle field in scratch and
   invoke the same checker, which must exit nonzero. Preserve outputs separately.
6. Run only explicitly named test nodes/importer tests and exact-file Ruff. Root
   runs the architecture gate; no baseline synchronization, broad test suite or
   debt-ledger compiler. Guardrail environment failure is an unrun check.

## Pattern, version, and residual pass

P01/P02/P03: corpus → real runtime → independent evaluator → audit report and caller.
P04/P05/P15: candidate coordinates never become lifecycle or authority. P29/P32/P33:
sealed inputs plus independent recomputation and semantic mutant failure. P35:
complete two-way enumeration. P37/P38: decisive context versus measured proxy named
per pair. P14: engineering independence is not institutional independence. P40:
reviewers classify escapes as new or same class; a second same-class finding
widens the mechanism or becomes a bounded limitation with an executed falsifier.

Before execution the corpus is `artifact_missing`, the evaluator is
`producer_missing`, and semantic evidence is `verification_missing`. Closure is
only the declared mechanical conformance chain. Institutional external execution,
empirical harm validity, live production latency and appointed benchmark authority
remain refused with named missing owners; they are not supplied by these fixtures.
No governed epoch or existing artifact reissue is planned. Any discovered transition
must be declared against lane merge base `992aa493f`, not CR3's start. Incidental
findings are handed to root for a named architect route; DEBT/LEDGER stays untouched.

## Execution refinement after independent review

The production replay producer is `runtime/quality/response_corpus_evaluator.py`;
the independent conformance consumer is `tools/check_response_corpus.py`, with
`tools/response_transition_oracle.py` owning separate raw decoding and expectations.
No Runtime module imports the tools-owned oracle. Operation coverage is checked
against actual factor/version/epoch changes or observation discriminators; retaining
operation labels after removing those effects fails the checker. FCT-04 continuation
is represented with claim-dependent permission still false. Consumer-boundary mutants
reuse one frozen real-owner replay and independently reconcile the complete persisted
publication set; no mutant alters the retained owner artifacts.

The independently adjudicated AUD-F06 expansion correction and the complete operation
coverage pass revised pre-delivery v1 inputs/expectations. These are construction
changes relative to `992aa493f`, not a governed epoch reissue. Exact pre/post hashes
and the local construction helper reference are retained in
`../journals/gy-lattice/cr3/oracle-revision.json`. External execution, field performance
and institutional appointment remain unestablished; these are the declared bounded
residual, not a reason to add operational authority to the corpus.
