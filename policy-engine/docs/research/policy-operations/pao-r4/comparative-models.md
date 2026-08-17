---
title: PAO-R4 — Comparative firewall models
research_id: PAO-R4
artifact_role: comparative-models
status: research
research_only: true
repository: DenisKopylov/polisyos
baseline_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
result_standing: GO_WITH_REVISIONS
authoritative_for:
  - research comparison of policy-to-individual boundary controls
  - selection and rejection reasons for the PAO-R4 contract
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
---

# Comparative models — breadth before selection

## 1. Selection criterion

A model is sufficient only if it makes the commission's failure observable:

> a policy-level statistical rule is consumed as an individual eligibility rule and no gate goes red.

The decisive properties are:

1. **export decidability** — unsafe structure can be rejected from the artifact and request;
2. **use visibility** — a prohibited material contribution inside an external case system becomes an
   observable event;
3. **restriction monotonicity** — derivation, projection, correction, and re-export cannot weaken a
   denied use;
4. **complete denominator** — silence cannot be interpreted as compliance;
5. **fail-closed unknowns** — incomplete auxiliary-information or release-history models return
   `not_established` or refusal;
6. **anti-role fit** — PolicyOS owns the boundary contract, not the individual decision system.

No single required comparator satisfies all six. The selected result is a composition.

## 2. Model survey

| # | Model | What it contributes | Eliminating property when used alone | Disposition |
|---:|---|---|---|---|
| 1 | Artifact-class allow-list | Creates a finite, reviewable export surface and makes unknown classes fail closed. | Class name alone cannot detect executable parameters, joins, later derivatives, or prohibited downstream use. | **Selected as the first gate, never alone.** |
| 2 | Form-based transformation gates — aggregate-only, k-anonymized, rule-level without parameters | Detects row-level material, small cells, identifiers, and some mechanically applicable forms. | A safe-looking aggregate can be re-identified by composition; `k` does not establish semantic non-resolution under auxiliary information; a rule can remain individually actionable without an obvious parameter field. | **Selected as necessary evidence, rejected as a complete firewall.** |
| 3 | Contract-based denied-use declarations enforced by the consumer, with attestation | Reuses the live `may_not_use_for` pattern and moves the check to the point where individual purpose is known. | A voluntary, sampled, or self-attested consumer can omit the use; contract prose without a complete evidence denominator is observationally equivalent to no enforcement. | **Selected only with mandatory returning evidence and reconciliation.** |
| 4 | Provenance-carried restriction that travels with the artifact and is machine-checkable downstream | Preserves source basis and denied uses across derivation; composes with `PV-K04`. | A carrier can be stripped, copied into an uncontrolled medium, or ignored by a consumer; it does not reveal actual use by itself. | **Selected as the monotonicity carrier.** |
| 5 | Purpose binding at request time | Makes the proposed use known before disclosure and blocks an explicitly denied request. | A truthful planning purpose can later drift; an operator can apply the artifact manually or through a derivative; declared purpose is not evidence of actual purpose. | **Selected as an intake condition, never as proof of use.** |
| 6 | Human-in-the-loop boundary control | Preserves a human decision opportunity and may support review or explanation duties. | A human can rubber-stamp, receive a default/rank, or rely materially on the same population inference. Formal finality does not erase material contribution. | **Rejected as the firewall; retained only as an external safeguard.** |
| 7 | Returning-evidence audit as the only real detection layer, with export permissive | Can reveal actual downstream use and supports after-the-fact reconciliation. | It permits harm before detection, cannot cure voluntary silence, and cannot make off-ledger use visible. | **Rejected alone; selected as mandatory evidence for otherwise safe crossing classes.** |
| 8 | Refusal to export the class at all | Eliminates the downstream observability problem for the refused bytes/class. | Overbroad refusal would block useful, non-individual population planning and leak authority-band strictness into candidate work. | **Selected for individually actionable or non-observable classes only.** |
| 9 | Current state: live `may_not_use_for`, no individual-decision concept or export gate | Supplies the generic denial carrier and examples of consumer-side enforcement. | It cannot name individual use, classify a policy-to-case crossing, inspect composition, or require returning evidence. | **Negative comparator; rejected.** |

## 3. Selected composite

The PAO-R4 contract is:

```text
allow-listed class
AND export-time subject-resolution/non-executability gate
AND declared basis preserved
AND union of denied uses preserved
AND purpose bound before receipt
AND named consumer enforces at actual use
AND complete returning evidence reconciles every protected action
ELSE refuse or not_established
```

The composition has two distinct enforcement locations.

### 3.1 Export boundary

The PolicyOS-side gate evaluates:

- class allow-list;
- subject and case resolvability;
- individual scores, rows, keys, and recommendations;
- executable parameters, thresholds, lookup surfaces, and complete rule functions;
- basis, limitations, purpose, consumer, and denied-use preservation;
- release-history composition and auxiliary-information assumptions.

Its possible outputs are `ALLOW_NON_INDIVIDUAL`, `REFUSE_EXPORT`, `BLOCK_PURPOSE`,
`BLOCK_PERMISSION_AMPLIFICATION`, `BLOCK_COMPOSITION`, or `NOT_ESTABLISHED`.

### 3.2 Consumer boundary and return path

The named case-system consumer evaluates actual purpose and material contribution before a protected
case action. It returns complete evidence of imports, derivatives, use attempts, and case actions.
A denied purpose yields `BLOCK_PURPOSE`; missing or unreconciled evidence yields
`FIREWALL_CLAIM_NOT_ESTABLISHED` and cannot be interpreted as non-use.

The contract does not design the consumer's case workflow or data model.

## 4. Why form-based anonymization does not win

Anonymization is not a syntactic state. It is a claim relative to:

- the released fields and granularity;
- the declared auxiliary-information model;
- every prior and concurrent export in the controlled release family;
- linkage, uniqueness, and small-cell behavior;
- the protected predicate that must remain unresolved.

A `k>=5` marker can be useful evidence for one attack model. It is not a proof that the artifact
cannot resolve a person after joins, differencing, repeated queries, or outside information. Under
**`PV-K06`**, a heuristic, sampling result, timeout, incomplete history, or unproved approximation
cannot inherit a safe verdict. Therefore an unproved “anonymized” artifact is treated as
person-resolvable and refused.

## 5. Why human review does not win

The relevant event is not “machine made the final click.” It is whether the exported policy artifact
materially supplied, defaulted, ranked, thresholded, recommended, evidentially weighted, explained,
or routed the individual action. A human review step can coexist with every one of those effects.

The human-review model also fails the commission's silent-use falsifier: an operator can reasonably
apply a population threshold, then approve the suggested result, while every system reports that a
human decided. No firewall gate goes red unless material contribution is itself observed.

## 6. Why permissive export plus audit does not win

Audit-only control is structurally retrospective. Three observations defeat it:

1. the protected action may already have occurred;
2. a voluntary or selectively sampled return channel makes prohibited use plus silence identical to
   compliant non-use;
3. off-ledger reading, screenshots, memory, and uncontrolled derivatives may produce no event at all.

Audit is therefore a necessary reconciliation layer for crossing classes already safe enough to
export. It cannot make an individually actionable class exportable.

## 7. Current-state negative comparator

The pinned repository has a real denial mechanism, projection-only enforcement, and a public export
producer. It has zero source files containing the exact concepts `individual_decision`,
`export_gate`, or `prohibited_use`. The operator-visible result for the PAO-R4 fixtures is:

| Fixture | What the pinned state evaluates | What an operator sees | Current-state verdict |
|---|---|---|---|
| Population statistical rule requested for one person's eligibility | Generic authority limits may be present, but no individual-purpose vocabulary is evaluated. | Export/consumption can appear structurally ordinary; no individual-use red signal is required. | **silent false pass** |
| Two separately permitted aggregates joined to identify a person | Each object is considered independently; no complete policy-to-case release-history check exists. | Both exports may remain permitted; join risk is invisible at this boundary. | **silent false pass** |
| Rule-level export with complete thresholds/parameters | Existing projection checks prevent authority minting but do not classify per-case executability. | Projection-only label remains; no individual-rule gate is required. | **silent false pass** |
| Projection removes an existing denied use | Existing `PV-K04`-aligned projection checks can reject bounded permission amplification where the denial is in the governed carrier. | A red projection-contract result is possible. | **detected only for existing named denials** |
| Sequence of compliant queries reconstructs an individual determination | No complete transcript/composition owner is bound to this use class. | Each query may pass; reconstructed determination has no PAO-R4 event. | **silent false pass** |
| Voluntary returning evidence is absent | No PAO-R4 denominator or reconciliation obligation exists. | Silence is simply silence. | **not observable** |
| Manual use of a displayed aggregate | No instrumented use event is required. | Human decision appears independent even when materially influenced. | **not observable** |

The one bounded success—projection preservation of an already named denied use—is the substrate the
firewall extends. It is not evidence that the policy-to-individual firewall exists.

## 8. Refusal frontier

Refusal is required when any of the following holds:

- subject or case resolution is possible;
- the artifact is individually executable or already contains a score/rank/recommendation;
- composition safety is not established over the complete controlled history;
- actual individual use can be known only through voluntary, sampled, or unverifiable reporting;
- uncontrolled copies or manual use remain a material route and the artifact is individually
  actionable through that route.

This is narrower than refusing all population analysis. Candidate-band computation, research, and
programme planning remain allowed. What is refused is a crossing whose prohibited use cannot be
made visible.

## 9. Decision

**Selected: composite firewall plus refusal frontier.**

**Rejected:** any single comparator as sufficient; human-in-the-loop as the boundary; permissive
export with audit as the only enforcement; form labels as proof of non-individual meaning; and the
current state as a firewall capability.

The exact result standing remains `GO_WITH_REVISIONS`: the research contract is coherent, while the
repository lacks the vocabulary, export gate, named case consumer, and mandatory returning-evidence
chain required to claim implementation.
