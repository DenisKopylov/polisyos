---
title: PAO-R4 independent audit — recommended revision register
audit_id: PAO-R4
artifact_role: recommended-revision
status: independent-audit
research_only: true
verified_commit: a27c3da9942b03881dbee1005a8a1e44e5ac44b4
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
authoritative_for:
  - independent executable revision recommendations for PAO-R4
  - separation of standing-required remediation from optional improvement
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
  - modification of the audited branch
---

# PAO-R4 recommended revision

## 1. Use rule

This is a revision register, not replacement research. Each item states the exact defect, the exact
change required in the research artifacts, and evidence by which an independent reviewer can decide
whether the change landed. Items R1–R10 are required before the audit would reconsider the current
`NO_GO` for adoption. R11–R13 are improvements and do not independently control standing.

## 2. Required for standing

### R1 — separate empirical population claims from normative general rules

**Defect:** `P=(R_B,B,Φ,θ,L)` and `P ∧ C_B(x)=1 ⊭ I_x` are applied to a class that includes empirical
summaries, predictive probabilities, causal population effects, and general rule statements.
Normative universal rules can be individually applicable; the universal non-entailment is false.

**Required change:** revise primary §3 and §4 to define at least these semantic classes in prose/formal
notation:

1. empirical population summary/probability/effect;
2. normative general rule under a competent external authority;
3. individual or pointwise-recoverable artifact;
4. synthetic/non-case example.

State the non-entailment only for class 1 absent a separately justified individual inference. State
that class 2 can be applied only by the external case procedure using competent authority and case
facts; PolicyOS still does not make the determination.

**Evidence of execution:** the revised formal statement is valid for each class; Artifact C in the
formal audit no longer contradicts it; the crossing/refusal tables name the class distinction.

### R2 — make pointwise recoverability part of the formal boundary

**Defect:** singleton cells and deterministic partitions satisfy the delivered population tuple and
nevertheless determine an individual.

**Required change:** add an explicit pointwise-recoverability/individualizability condition over the
artifact plus declared history/auxiliary model. A subject-resolvable singleton, complete deterministic
partition, differencing query family, or equivalent function must be classified as individual even
when encoded as an aggregate.

**Evidence of execution:** both constructed artifacts A and B receive a deterministic
`individualizable`/refusal disposition under the formal rule, without relying on field names or an
“aggregate” label.

### R3 — state what is observed and what remains declared in `B`, `L`, and material contribution

**Defect:** completeness and truth of the basis/limitations and the counterfactual “would the action
change?” are not derived by the specified interface. Content binding preserves a record, not its
truth.

**Required change:** for every load-bearing predicate, label it as one of:

- recomputed from a controlled artifact/history;
- independently reconciled observation;
- consumer assertion;
- institutionally supplied premise;
- not established.

Replace the assertion that material contribution is “observable” with either a conservative
observable use rule (for example, consultation/invocation in a protected action) or a bounded method
for validating the counterfactual. State the residual false-negative boundary.

**Evidence of execution:** Scenarios S-1 and S-2 produce bounded, non-positive results; no complete
firewall claim rests on an unverified consumer counterfactual.

### R4 — refine and scope the detection partition

**Defect:** `export-time` combines artifact-local facts with model-relative resolution,
executability and composition; the headline is broader than the declared integration boundary.

**Required change:** replace the three headings with at least:

1. artifact-local observable;
2. export-context observable with named history/auxiliary model;
3. downstream use-context observable;
4. outside-declared-boundary/not observable.

For every predicate, name its required inputs and incomplete-input verdict. Bound every positive
firewall proposition to the governed technical/institutional boundary it actually observes.

**Evidence of execution:** each primary-report item maps to exactly one class; unknown auxiliary
information never appears as artifact-time certainty; S-1 is explicitly outside the positive claim.

### R5 — rewrite the commissioned falsifier as silent purpose drift

**Defect:** F-01 asks for `individual_eligibility_determination` explicitly. It can pass at request
export while the actual downstream-use gate is absent.

**Required change:** split F-01 into a single exact scenario:

1. request/import is for an allowed population-planning purpose and is admitted;
2. later, a resolved subject and eligibility action materially use the artifact;
3. the mandatory **consumer/use gate** returns `BLOCK_PURPOSE` before action;
4. any bypass returns one exact violation record.

Do not allow “export or request gate” or “at least one gate” to satisfy the case.

**Evidence of execution:** removing the consumer gate while keeping request-time fields causes the
fixture to fail. The exact commission sentence—statistical rule consumed as eligibility rule and no
gate red—is the negative.

### R6 — make every falsifier one world with one exact outcome and add missing attacks

**Defect:** F-01, F-02, F-05 and F-07 contain conditionals/disjunctions; reference-class shopping,
semantic-purpose synonyms, counterfactual-reliance laundering and multi-hop relay are untested.

**Required change:** split each conditional world into its own fixture. Add A-15 through A-18 or
property-equivalent cases. Each case must name detector, input, one expected verdict, and forbidden
outcome.

**Evidence of execution:** suite manifest has no `if_*`, `with_*`/`without_*`, “at least one,” or
multi-verdict expected field; all four new attack families have exact red/`not_established` results.

### R7 — narrow the refusal list around rule authority

**Defect:** every executable general rule is refused, conflating official/normative rule application
with statistical individualization.

**Required change:** revise §4.2–§4.3, F-03 and the comparison table to distinguish:

- PolicyOS empirical predictor/score or disguised pointwise mapping—refuse for case use;
- normative rule from a competent external authority—may be transported only as rule-level input,
  never as PolicyOS case authority, and only with external fact-finding/procedure evidence;
- unknown/mixed object—`not_established`/refuse.

Do not appoint the authority or design the case workflow.

**Evidence of execution:** Artifact C is no longer rejected merely because it is executable, while a
statistical decision tree with identical syntax remains refused because its semantic class and
purpose differ.

### R8 — complete and correct the orientation census

**Defect:** the all-source `anonymi*` file count is seven, not six, and positive
`may_not_use_for` line/occurrence totals were not executed.

**Required change:** run a complete raw-tree census at the pin over all decodable files under
`policy-engine/src`. Record separately for every token/family: file universe, files, matching lines,
occurrences, exact case/stem semantics, and the 67/12/27 partition. Correct the CSV omission.

**Evidence of execution:** command output is included or content-bound; totals reproduce under an
independent checkout; no Python-only value is presented as all-source.

### R9 — correct external-source currentness and comparison strength

**Defect:** Canadian sources are mutable and unversioned; OMB M-24-10 is presented without noting
that M-25-21 rescinded/replaced it; “PAO-R4 is not weaker” exceeds the compared dimension.

**Required change:** pin the Directive and AIA to version/date/archive; mark M-24-10 historical and
superseded or replace it with a current M-25-21 transfer analysis; label the Dawid transfer as an
inference; replace “not weaker” with “not narrower on the material-reliance/formal-finality trigger,”
while preserving non-compliance limits.

**Evidence of execution:** every mutable source has date/version; currentness is explicit; no global
legal dominance claim remains.

### R10 — reopen canonical owner placement for the case-handoff boundary

**Defect:** the handoff infers that `public_export.py` is the canonical owner for a non-public,
purpose-bound case-system handoff because it is the adjacent real exporter.

**Required change:** keep the denied-use and projection owners as established, but classify the
policy-to-case emission chokepoint placement as an open consolidation decision. Present alternatives
by existing responsibility and evidence; do not appoint a new owner.

**Evidence of execution:** no “no second exporter” or canonical-placement claim remains without a
pinned owner decision; the capability itself remains `absent/unallocated`.

## 3. Improvements, not standing gates

### R11 — preserve narrower value from voluntary evidence

**Defect:** the report says voluntary reporting reduces to terms of use, overlooking incident,
lower-bound and sampled claims.

**Improvement:** add a claim lattice in prose: complete non-use claim unavailable; observed-incident,
lower-bound, and sampled-audit claims may be available if accurately scoped.

**Evidence:** F-06 still blocks the firewall positive, while a separate example allows only the
narrow observed claim.

### R12 — make the final delivery verification durable

**Defect:** `delivery-readback.md` is accurate for the seven-file payload head but delegates final
self-inclusive verification to the completion report.

**Improvement:** use a separate immutable audit/receipt object or second repository record that names
the final head and the first receipt blob without attempting impossible self-digestion.

**Evidence:** final branch head, file set and blob identities are retrievable from durable repository
content. This item does not affect research standing.

### R13 — add a claim-boundary summary table

**Defect:** headline prose can be read institution-wide while detailed sections are boundary-scoped.

**Improvement:** add one table for each positive/negative claim: subject, governed boundary,
observable, completeness premise, residual channel, and exact allowed wording.

**Evidence:** an auditor can determine from one row whether a claim is artifact-local,
integration-boundary, institution-wide, or unavailable.

## 4. Reconsideration rule

The audit would reconsider `NO_GO` only when R1–R10 are evidenced at a new exact commit and the
delta is independently checked. Completion requires substance, not marker presence:

- the revised formal rule must survive A/B/C;
- the material-contribution procedure must survive S-1/S-2;
- the suite must fail when its real consumer-use property is removed but marker strings remain;
- the census and primary-source changes must be reproducible;
- no capability or owner claim may be upgraded by the revision itself.
