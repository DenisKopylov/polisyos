---
title: "INT-R8 semantic contract and loss-typing boundary"
research_id: INT-R8
artifact_role: semantic-contract
status: accepted_narrow_scope
amendment_conformance: pending_independent_verification
research_only: true
repository: DenisKopylov/polisyos
baseline_ref: main
baseline_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
audited_head: 90b372964d29a9e97605a6ef733ef03ffe7938d2
prepared_at: 2026-08-04
amended_after_audit: research/int-r8-independent-audit@f45f338f9d9b0de94edc16efbc334789e70e34e2
may_not_use_for:
  - production_implementation_authorization
  - final_wire_schema_package_database_serialization_or_api_contract
  - canonical_owner_appointment
  - authority_grant
  - capability_claim
  - benchmark_passage
  - legal_compliance_or_institutional_competence_conclusion
  - permission_to_publish_a_governed_result
  - automatic_amendment_of_any_plan_or_system_design_decision
  - signature_algorithm_or_key_policy_selection
  - numeric_disclosure_bound
---

# INT-R8 semantic contract and loss-typing boundary

## 0. Controlling amendment notice

This artifact executes R7, R8, R10, and the semantic part of R13. It preserves audit
commendations `INT-R8-V-001`, `V-005`, `VII-001`, `VII-002`, and `VIII-001` while correcting
findings `INT-R8-V-002`, `V-003`, `V-004`, and `VIII-002`.

The audited version remains immutable at
`research/int-r8-compression-loss-and-disclosure@90b372964d29a9e97605a6ef733ef03ffe7938d2`.
This version controls where the two differ.

## 1. Decision and authority boundary

`CompressionLossReceipt` is a research-level semantic extension of the canonical projection and
public-export substrate. Its two outcomes are:

- `lossy_but_safe`; and
- `blocked_material_omission`.

They are verifier dispositions, not a new PolicyOS status lattice. A safe receipt does not grant
approval, publication, closeout, compliance, competence, truth, or current authority. A blocked,
missing, wrong-revision, model-inconsistent, timed-out, or otherwise not-established receipt
fails the protected publication gate. No third favorable outcome is implied.

The receipt remains:

- `authority_role = projection_only`;
- `authoritative_for = []`; and
- subject to every applicable source and projection denied use.

## 2. Exact reuse surface

The receipt must consume canonical identifiers and facts rather than reproduce them in a parallel
projection system.

### 2.1 Base projection carriers reused

The base projection in `runtime/quality/projection_semantics.py` emits or derives:

- `closeout_truth`, including blocker and limitation codes;
- `projection_gaps`;
- `omission_manifest`;
- `contested_records`;
- `recourse_pointer`;
- `deficit_register`;
- `participation_requirements`;
- `invariant_summary`;
- `redaction_summary`;
- `audit_refs` and source-authority references;
- `may_not_be_used_for`;
- the four canonical audience values; and
- the projection-only authority boundary.

Surface-specific S10-S14 enrichment may add named limitation fields or a `limitations` list. The
base projection does **not** establish one universal top-level limitations collection. The
receipt normalizes semantic effect across concrete carriers without claiming an existing unified
storage shape.

### 2.2 Public-export behavior reused

`runtime/quality/public_export.py` already:

- consumes projection semantics;
- runs projection and S9-S14 checks;
- rejects omitted claim IDs absent from the omission manifest;
- runs candidate-firewall and replay-drift checks;
- emits canonical scanner transformation reasons for email, keyed secret, and general secret/PII
  findings; and
- preserves projection-only official-use limits.

The receipt adds materiality, retained/dropped classification, exact rendered-object identity,
model identity, and transcript findings. It does not replace these checks.

## 3. Semantic inventory and dispositions

For a fixed source revision and declared use package, every source semantic item receives exactly
one disposition:

- `retained_exact`;
- `retained_faithful_condensation`;
- `dropped_manifested`; or
- `not_applicable_to_declared_projection`.

An item with zero or multiple dispositions yields `compression_item_disposition_invalid` and
blocks.

The inventory covers at least:

1. claim identity and claim type;
2. declared basis, subject, jurisdiction, time, envelope, and assumptions;
3. limitations, conditions, uncertainty, and conditionality;
4. attacks, rebuttals, counterexamples, and unresolved defeaters;
5. denied uses;
6. counterevidence and conflicting evidence;
7. contest/dispute state;
8. dissent/minority position and its material issue;
9. recourse and competent correction route;
10. refusal, void, terminal no-attempt, exhaustion, and other negative terminals;
11. constitutive procedural events and ordering;
12. currentness, supersession, withdrawal, and correction;
13. provenance/audit references; and
14. privacy-sensitive content and release-channel observations.

## 4. Governed materiality relation

The audit correctly found that “material,” “faithful,” and “constitutive” cannot remain free-text
judgments. The controlling relation is versioned and evidence-bound.

For each source item `x`, define a materiality record:

`Mat(x, U, D) -> (basis, effects, affected_claims, condensation_relation, disposition)`

where:

- `U` is the declared use and denied-use package;
- `D` is the governed decision/materiality predicate package;
- `basis` identifies the competent rule, source finding, authority boundary, or institutional
  disposition that makes the effect governable;
- `effects` is a nonempty subset of the effect classes below when `x` is material;
- `affected_claims` binds existing claim identifiers;
- `condensation_relation` identifies which summary representation, if any, preserves those
  effects; and
- `disposition` is one of `material`, `non_material_for_declared_use`, or `not_established`.

### 4.1 Governed effect classes

- `truth_condition` — changes the proposition that is true or false;
- `scope_or_basis` — changes population, subject, jurisdiction, time, envelope, obligation set,
  assumptions, or relative basis;
- `authority_or_status` — changes claim type, authority role, outcome, currentness, or
  supersession;
- `permitted_or_denied_use` — changes a permission or prohibition;
- `contestability_or_recourse` — changes whether material evidence, dissent, dispute, reasons, or
  a real challenge route is visible;
- `history_or_currentness` — changes prospectivity, firstness, ordering, substitution,
  adjudication, negative publication, correction, or current head; and
- `privacy_or_reconstruction` — changes a protected predicate or the declared coalition's ability
  to reconstruct it.

### 4.2 Materiality outcomes

| Materiality disposition | Required evidence | Compression consequence |
|---|---|---|
| `material` | Bound basis, effect class, affected claims, and predicate package | Item or faithful condensation is mandatory. |
| `non_material_for_declared_use` | Bound basis proves every governed effect unchanged for the declared use | Item may be dropped with manifested reason. |
| `not_established` | Missing basis, unresolved claim mapping, unsupported predicate, conflict, or timeout | `blocked_material_omission`. |

An editor's statement that an item is “obvious,” “minor,” “technical,” or “non-material” is not
valid evidence.

## 5. Faithful condensation relation

A condensation is not validated by string similarity. It is a mapping from source semantic items
to visible summary items under `U` and `D`.

`Condense(x_set, s, U, D) = pass`

only when:

1. every source item in `x_set` has one summary representative or is proved semantic duplicate;
2. every bound effect in section 4 is preserved;
3. claim identity and claim type remain resolvable;
4. no source proposition becomes broader, more favorable, more certain, less contested, more
   current, or more authoritative;
5. denied uses are equal or more restrictive;
6. omitted detail is manifested through the canonical reason relation;
7. the exact rendered object remains understandable for its declared audience and accessible
   representation; and
8. the controlled transcript passes the reconstruction check.

The relation returns:

- `faithful_condensation_established`;
- `condensation_effect_changed`; or
- `condensation_not_established`.

Only the first can support `retained_faithful_condensation`.

## 6. Constitutive procedural-step relation

A no-number custody claim is defined by a versioned constitutive event and order package, not by
an unbounded sentence such as “the process was proper.”

For claim `c`, declare:

`Procedure(c) = (E_c, <_c, uniqueness, allowed_normalizations, basis)`

where:

- `E_c` is the finite set of constitutive event classes;
- `<_c` contains required partial-order relations;
- `uniqueness` identifies first/earliest/single governing events;
- `allowed_normalizations` identifies duplicate prose or storage details that may be collapsed;
  and
- `basis` binds the governing custody rule and source records.

Candidate event classes include:

- commitment or rule sealing before result-bearing execution;
- first qualifying attempt and the qualifying population;
- prohibited-substitution policy and actual substitution/deviation record;
- execution chronology;
- adjudication/evaluator disposition;
- dissent preservation;
- negative/refusal publication; and
- correction/supersession history.

### 6.1 Mechanical check

A summary preserves the procedural claim only when:

- every unique constitutive event has a visible or proof-bound faithful representative;
- every required order relation remains decidable from the public object and bound proof inputs;
- no prohibited substitution is converted into silence;
- every negative and dissent event required by the package remains visible at safe granularity;
- duplicate prose removal is explicitly identified by `allowed_normalizations`; and
- the summary does not generalize the bounded history into legal compliance, competence,
  efficacy, or production readiness.

Removing one constitutive event yields `compression_procedural_step_missing`. Reversing or
obscuring an order relation yields `compression_procedural_order_not_established`. An absent or
unresolved `Procedure(c)` package yields `compression_procedural_basis_not_established`. All
block.

## 7. One canonical transformation-and-omission reason relation

The receipt does not create a third reason vocabulary. It consumes one approved relation:

`Reason = transformation_reason -> omission_semantic_class -> affected_claims -> governed_effects -> safe_public_explanation`.

### 7.1 Relation roles

- `transformation_reason` is the canonical source reason. Scanner-detected email, keyed-secret,
  and general secret/PII removal reuse the existing scanner reason identifiers.
- `omission_semantic_class` maps the transformation into an approved claim/basis/limitation/
  attack/denied-use/counterevidence/dissent/negative/history/provenance/privacy class.
- `affected_claims` uses canonical claim IDs already present in projection/omission machinery.
- `governed_effects` uses the effect classes in section 4.
- `safe_public_explanation` states enough to prevent misleading silence without disclosing the
  protected value.

### 7.2 Extension boundary

A non-scanner semantic omission may require a new approved relation row, but not a receipt-local
identifier that competes with an existing scanner or projection reason. Before any implementation
claims one live registry, a complete duplicate/overlap census must show:

- no same identifier with conflicting meaning;
- no two identifiers with the same meaning and different gate effects unless an explicit alias
  relation exists;
- every scanner reason maps to an omission semantic class where it affects a claim;
- every projection omission reason maps to affected claim IDs and governed effects; and
- every public explanation is checked as a release channel.

### 7.3 Blocking reason findings

- `compression_redaction_reason_missing`;
- `compression_redaction_reason_noncanonical`;
- `compression_redaction_reason_mismatch`;
- `compression_reason_duplicate_conflict`;
- `compression_affected_claim_missing`; and
- `compression_reason_self_disclosing`.

Each is atomic in suite v2.

## 8. Semantic parity

For full governed record `R`, exact summary object `S`, declared use package `U`, governed
predicate package `D`, and controlled transcript `T`, parity is use-relative conservative
observational equivalence:

1. every surfaced claim in `S` resolves to a source claim in `R`;
2. claim type, basis, scope, assumptions, material conditions, and limitations pass the
   materiality/condensation relation;
3. every `d in D` returns the same result on `S` and `R` or a more conservative result on `S`;
4. `may_not_use_for(S, c)` is a superset of `may_not_use_for(R, c)` for every retained claim and
   for the projection as a whole;
5. negative outcomes, material dissent, contest, recourse, and currentness are preserved;
6. every dropped item has one valid reason relation;
7. the exact rendered/exported object passes accessible-representation checks; and
8. the declared controlled transcript passes exact or proved-conservative reconstruction.

This permits shorter language. It does not permit a truth-changing rider to disappear.

## 9. Derived minimum retained set

The minimum remains derived from the governed effect classes. Every summary carries directly or
by faithful condensation:

1. source record/revision, release identity, and current/superseded state;
2. actual outcome and existing status, without a local approval proxy;
3. claim identity and claim type;
4. subject, jurisdiction, material time/envelope, and declared basis;
5. for `delta`, the declared obligation set, maintained assumptions, and visible relative-basis
   rider;
6. for no-number custody, the version-bound constitutive event and order package;
7. every material limitation, condition, and numerical conditionality;
8. every active denied use;
9. material counterevidence, attack, dissent, contest, and disposition at safe granularity;
10. a competent recourse/correction pointer where one exists;
11. typed omission class, canonical reason relation, affected claims, and governed effect;
12. public-safe provenance, source binding, current-head reference, and transcript head; and
13. receipt outcome, issue codes, declared models, completeness disposition, and verifier status.

A full-record pointer is necessary for authorized audit and insufficient to cure false visible
meaning.

## 10. Total fail-closed decision procedure

The procedure is total over its declared executable input contract because every unresolved or
nonterminating subcheck has a blocking disposition.

### Gate 1 — identity, inventory, and model completeness

Require source revision, audience, exact rendered object, semantic inventory version, use and
predicate packages, record model, protected predicates, channel/release family, coalition and
background models, transcript head, and authority boundary.

Missing input -> `compression_input_package_incomplete` -> blocked.

### Gate 2 — categorical semantics

Always block:

- bare `delta` missing obligation set, assumptions, or rider;
- hidden refusal, void, dispute, terminal no-attempt, or exhaustion;
- narrowed denied use;
- hidden currentness/supersession; and
- missing declared constitutive event or order relation.

No materiality override applies to `INT-K02` or `INT-K08` anchors.

### Gate 3 — materiality and condensation

Evaluate every retained or dropped source item under sections 4-6. Changed effect or
`not_established` -> blocked.

### Gate 4 — reason relation

Require one canonical reason relation for every dropped/redacted item. Missing, conflicting,
mismatched, or self-disclosing relation -> blocked.

### Gate 5 — exact/proved-conservative transcript reconstruction

Use the dispositions in `reconstruction-composition-and-threat-model.md`. Reconstructed, empty,
timeout, unsupported, unowned approximation, incomplete controlled history, or out-of-model
channel -> blocked.

### Gate 6 — authority and final outcome

Reject any receipt that mints authority or a number. Only if Gates 1-5 pass and the candidate is
actually shorter may the receipt return `lossy_but_safe`. Every other terminal returns
`blocked_material_omission` with exact issue codes and affected IDs.

## 11. Calibration anchors

### 11.1 `INT-K02`: bare `delta`

Full claim carries `delta`, declared obligation set, maintained assumptions, and relative-basis
rider. Dropping any one changes `scope_or_basis` and broadens the statement. Always
`blocked_material_omission` with `compression_delta_basis_missing`.

### 11.2 `INT-K08`: hidden negative completion

Replacing refusal, void, dispute, terminal no-attempt, or exhaustion with blank, unavailable, or
pending converts a completed outcome into ambiguity. Always `blocked_material_omission` with
`compression_negative_terminal_hidden`.

### 11.3 `INT-K06`: constitutive no-number history

A source claim declares sealing before execution, first qualifying attempt, no prohibited
substitution, chronology, adjudication, dissent, negative publication, and correction. A summary
saying “the process was properly followed” without the declared event mapping fails. Dropping one
unique event returns `compression_procedural_step_missing`; losing order returns
`compression_procedural_order_not_established`; missing the constitutive package returns
`compression_procedural_basis_not_established`.

A shorter form may pass only when it visibly preserves every constitutive event/order predicate,
retains the no-compliance/no-competence boundary, and drops only declared duplicate prose or
low-level paths.

## 12. Safe-loss controls preserved

Potentially `lossy_but_safe`, after all gates pass:

- five duplicate citations become one while support, source class, conflict, independence, and
  affected claim remain;
- a protected personal name becomes a role when identity is proved non-material for the declared
  use and dissent, mandate, issue, date/status, conflict, and recourse remain;
- low-level storage paths become public-safe references;
- raw confidential cells become a disclosure-controlled aggregate while population/time,
  conditionality, uncertainty, local rule, reason, denied uses, and prior-output checks remain;
- repeated procedural prose is normalized while every unique event and order relation remains;
  and
- the summary adds a denied use or returns a more conservative result without altering source
  truth.

These examples are green-control purposes, not self-executing verdicts. Suite v2 supplies exact
fixtures and prerequisite statuses.

## 13. INT-R7 proof interface

INT-R8 requires proof binding or typed disposition for:

- source record/revision;
- audience and surface;
- exact rendered/exported public object identifiers;
- retained semantic-item set;
- omitted class, affected claim IDs, reason relation, and governed effects;
- loss outcome and rule version;
- declared uses and denied uses;
- materiality/decision predicate package;
- semantic inventory version and completeness;
- constitutive procedure package where applicable;
- record/consistency model and protected-predicate family;
- channel registry and declared release-family version;
- coalition/delegation model;
- auxiliary/background-information assumptions and incompleteness;
- transcript predecessor/current head and completeness disposition;
- exact, empty, timeout, unsupported, abstraction, or approximation verifier status;
- current/superseded state; and
- unchanged projection-only authority boundary.

INT-R7 owns canonicalization, algorithms, key lifecycle, timestamps, transparency, witnesses,
archival preservation, offline verification, and proof representation.

A failed or absent INT-R8 relation blocks public projection faithfulness and public-current
positive reliance. It does not imply that an authentic issuer-side source issuance never
occurred. Issuer issuance authenticity, projection faithfulness, public-history establishment,
durable verifiability, and current authority remain separately reportable. This requirement is
anchored to audit finding `INT-R7-VIII-003`; no unverified INT-R7 amendment conclusion is adopted.

## 14. Result standing

**`accepted_narrow_scope`, retained pending independent conformance verification.**

The amendment supplies a checkable materiality relation, a constitutive procedural relation, a
single reason relation, concrete reuse carriers, a total fail-closed procedure over declared
executable inputs, and the complete semantic proof interface. It appoints no owner, fixes no
schema, and authorizes no implementation, publication, legal conclusion, or numerical bound.
