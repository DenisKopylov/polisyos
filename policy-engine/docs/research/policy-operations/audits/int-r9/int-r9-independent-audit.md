---
title: INT-R9 — Independent Adversarial Audit
status: delivered
kind: independent-audit
research_task: INT-R9
audit_verdict: NO_GO
repository: https://github.com/DenisKopylov/polisyos
audited_branch: research/int-r9-first-promotion-protocol
audited_commit: f5ad922377e38ee3ddbecb33293300bca25a9ad7
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-03
authoritative_for:
  - independent audit disposition of the INT-R9 research deliverable at the exact audited commit
  - evidence-backed identification of blocking, material, minor, and commendable properties across mandatory passes A through J
  - consolidation input stating what must be re-researched or corrected before INT-R9 can be adopted
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, or database contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - legal compliance or institutional competence conclusion
  - modification of the audited deliverable
  - replacement of S0-GAP-02, INT-R1, canonical N9, the confidence ledger, or the existing status lattice
research_only: true
---

# INT-R9 — Independent Adversarial Audit

## Executive verdict

**Overall verdict: `NO_GO`.**

The INT-R9 deliverable contains several unusually strong pieces of work that should survive
revision: it excludes the deeply contaminated `ua-msme-affordable-loans-2022` case from decisive
use; refuses to call the current public corpus a holdout; requires named natural-person
adjudicators rather than role strings; keeps negative outcomes publishable; sharply bounds the
claim that a first positive could support; and defers generic oracle custody to S0-GAP-02 rather
than openly appointing a second owner.

Those strengths do not rescue the load-bearing sequence claim. The protocol creates exactly
three opportunities for a positive result and repeatedly says those opportunities are governed by
one cumulative confidence budget. The canonical runtime does not currently supply that property.
N9 derives the only admissible confidence scope for an attempt from the individual
`design_problem_id`:

- `promotion_sequence.py:354-370` calls it the only N11 scope admissible for one N9 problem
  binding and sets `owner_scope_key = design-problem:<design_problem_id>`;
- `confidence_ledger.py:158-195` derives `scope_id` from that owner scope key;
- `confidence_ledger.py:1285-1368` assigns ordinals and sums prior spend only from events loaded
  in that scope; and
- `confidence_ledger.py:4005-4027` applies the Basel-square allocation inside that scope.

Three newly authored cases are three distinct design problems unless an additional, presently
unspecified and presently non-canonical sequence-level accounting relation exists. A compliant
executor can therefore open three fresh scopes, receive ordinal zero and a fresh `delta` in each,
and stop at the first positive. The protocol text saying “cumulative ledger,” “no reset,” and “no
parallel alpha budget” does not alter the canonical scope identity or provide cross-scope
arithmetic. If each slot individually controls a false-promotion event by `delta`, the only generic
family-wise statement available without further structure is the union bound, at most
`3 * delta`, not `delta`.

This is not a hypothetical future bypass and P29 does not require the audit to stop before it. It
is an actual path through the present source of truth that follows every written INT-R9 rule while
violating the protocol's central cumulative-risk representation. The bounded proposition in
section 4.2 is therefore not established as written, and `accepted_narrow_scope` is too strong.
The result must be treated as **blocked pending re-research of sequence-level multiplicity and its
relationship to the canonical per-problem confidence scopes**.

The audit also finds material, non-blocking defects: adaptive “general implementation repair” is
not distinguished from targeted learning after a failed slot; materiality decisions have no
closed pre-result decision owner; the same independent unit may author both new cases and their
answer packages; most independence dimensions still bottom out in declarations; abstention
remains a compliant dominant strategy; the 852-line YAML is a de facto executable contract rather
than a mere sketch; the INT-R1 handoff names the wrong artifact and gives an over-permissive
“narrow the claim” rung; and several repository anchors are wrong or overbroad.

The detailed evidence is split into:

- [claim/evidence ledger](int-r9-claim-evidence-ledger.md);
- [anchor and external-citation verification](int-r9-anchor-and-citation-verification.md);
- [adversarial reading](int-r9-adversarial-reading.md);
- [S0-GAP-02 and INT-R1 cross-check](int-r9-seam-and-crosscheck.md);
- [required revisions](int-r9-recommended-revision.md); and
- [orientation error ledger](int-r9-orientation-error-ledger.md).

## Audit scope and method

The audit compared three immutable states:

1. repository baseline `d152565dcc11cea457dacd61fadc6e15dc3ecc86`;
2. INT-R9 audited commit `f5ad922377e38ee3ddbecb33293300bca25a9ad7`; and
3. INT-R1 delivered commit `82e136a8d528cb24e661973ac1a8ea4fb6f1c80f`.

The audited diff contains five new documentation files and no changed pre-existing file, source,
or test. Every contamination-census repository target was inspected at the baseline SHA. The main
report was sampled under the adversarial rule recorded in the anchor ledger. All 15 adjudication
manifests were enumerated and their topology, calibration, authority level, answer-bearing fields,
and reviewer metadata extracted. Every external source named in section 3 was checked for
existence, attribution, and transfer validity. The audit then constructed both motivated actors
required by the task and traced the S0-GAP-02 and INT-R1 seams.

No test suite was run because the audited branch changes only research documents and the audit
brief expressly forbids adding code or tests. Source was executed only as a semantic reading of
existing contracts; no runtime capability is inferred from types alone.

## Finding register

| ID | Pass | Severity | Disposition | Short finding |
| --- | --- | --- | --- | --- |
| `INT-R9-A-001` | A | material | revise anchors | Every one of the thirteen adjudication citations ending in `:1-170` overruns EOF; the files support most claims, but the cited ranges do not fully exist. |
| `INT-R9-A-002` | A | material | revise anchors | `universal-policy-design-system-vision-and-organizing-rules.md:404-430` starts after the current-state facts it is cited for; the supporting block is at `:382-398`. |
| `INT-R9-A-003` | A | material | correct fact | The census says three manifests have `deep-pilot-round-1`; exact enumeration finds four, including synthetic housing. |
| `INT-R9-A-004` | A | minor | narrow wording | EU, India, and Pakistan expose labels, votes, and expected IDs, but their `gold_card` values are `null`; “gold card committed” is misleading if it means a non-null answer card. |
| `INT-R9-A-005` | A | material | revise anchor | The main report's `failure-patterns.md:200-900` range does not contain P29/P33/P34; those rows are around `:70-78`. |
| `INT-R9-A-006` | A | commendation | preserve | After re-anchoring, the 13/15 denominator, public-answer contamination, ua-msme integrated-depth finding, and zero-conversion current state are substantively correct. |
| `INT-R9-B-001` | B | commendation | preserve | Section 3 consistently distinguishes procedural transfer from statistical or legal proof and does not import population inference into the n=1 authority event. |
| `INT-R9-B-002` | B | material | re-research | Sequential-design sources are accurately cited, but the claimed cumulative lesson is not instantiated in repository-compatible arithmetic. |
| `INT-R9-B-003` | B | minor | clarify attribution | FIPS 180-4 establishes digest properties; the non-hiding conclusion follows from the commitment literature and threat model, not from FIPS alone. |
| `INT-R9-C-001` | C | blocking | re-research | Section 4.2's earliest-slot claim depends on cumulative family-wise accounting that the protocol does not define over canonical per-case scopes. |
| `INT-R9-C-002` | C | material | narrow claim | Later slots may use repaired revisions, so a later positive is selected across an adaptive development sequence, not merely three fixed looks at one implementation. |
| `INT-R9-C-003` | C | commendation | preserve | The report correctly denies population validity, legal compliance, production readiness, competence, and proof against covert collusion. |
| `INT-R9-D-001` | D | blocking | re-research | A rule-following executor can spend a fresh `delta` in each of three design-problem scopes; “no reset” is prose, not a cross-scope invariant. |
| `INT-R9-D-002` | D | material | close ambiguity | “General implementation repair” is permitted after outcome exposure but is not prospectively distinguished from result-targeted repair. |
| `INT-R9-D-003` | D | material | close decision right | Materiality determines whether a dispute halts promotion, yet the accountable, conflict-checked materiality decision owner remains unresolved. |
| `INT-R9-E-001` | E | commendation | preserve | Excluding ua-msme from both decisive and adjacent roles is repository-supported and pays the honest cost of possible non-convergence. |
| `INT-R9-E-002` | E | material | narrow contamination claim | One “independent case unit” may author both a case and its answer package; random choice inside that unit's pool does not remove pool-level tractability bias. |
| `INT-R9-E-003` | E | minor | make permanent by default | The reopening language should not suggest that fresh secrecy can erase years of case-conditioned implementation exposure; current ua-msme lineage remains public regression absent extraordinary proof. |
| `INT-R9-F-001` | F | commendation | preserve | Named accountable humans, predeclared alternates, raw dissent, and an explicit ban on synthetic adjudicators are hard blockers, not role-label decoration. |
| `INT-R9-F-002` | F | material | strengthen evidence | Seven independence dimensions are named, but many are evidenced only by disclosure and still permit friendly same-network adjudicators who comply with every written exclusion. |
| `INT-R9-G-001` | G | commendation | preserve | Section 4.14 provides real observables for forbidden useful-rate optimization rather than merely repeating Organizing Rule 5. |
| `INT-R9-G-002` | G | material | narrow heading and claim | Public positive controls and reason-coded refusals make crude constant refusal visible, but a cautious actor can pass them and refuse every unseen real case; T6 remains unresolved. |
| `INT-R9-G-003` | G | material | reconcile denominator | Narrative and YAML disagree on whether all precommitted but uninspected slots or only inspected slots enter the denominator, risking a new metric definition. |
| `INT-R9-H-001` | H | commendation | preserve | INT-R9 mostly states properties and defers commitment, key, access, rotation, challenge, and evaluator machinery to S0-GAP-02. |
| `INT-R9-H-002` | H | material | consolidation blocker | Delivered INT-R1 exports an `ObligationCoverageEnvelope`, not the named `ObligationSetDeclaration`; its `known_incomplete` and material `open_world_unresolved` states require NO-GO for the authority action, not arbitrary claim narrowing. |
| `INT-R9-H-003` | H | minor | remove escape hatch | “S0-GAP-02 or a consolidation-approved equivalent” can become permission for a parallel framework unless “equivalent” means an expressly superseding canonical decision. |
| `INT-R9-I-001` | I | material | demote to sketch | The 852-line YAML fixes identifiers, counts, vocabularies, state transitions, blockers, and fields densely enough to be loaded as a de facto contract despite its disclaimer. |
| `INT-R9-I-002` | I | commendation | preserve | The branch is additive-only, appoints no production package owner, and labels workflow states as custody phases rather than a second authority lattice. |
| `INT-R9-I-003` | I | blocking | change result standing | Because the central sequence guarantee fails, `accepted_narrow_scope` does not match what was established; the research is blocked pending multiplicity resolution. |
| `INT-R9-J-001` | J | material | correct orientation and report | Prompt orientation generalized `calibration_round_id = null`; exact set is four deep-pilot and eleven null. INT-R9 corrected only the three real deep-pilot cases and omitted synthetic housing. |
| `INT-R9-J-002` | J | material | correct orientation | `authority_level` is not uniformly `research`: exact distribution is 5 production, 6 governed, and 4 research manifests. |
| `INT-R9-J-003` | J | minor | distinguish key from value | Every manifest exposes answer-bearing labels/votes/expected IDs, but some semantic-pass adjudications carry `gold_card: null`. |
| `INT-R9-J-004` | J | commendation | preserve | The remaining supplied orientation—13 real plus 2 synthetic, ua integrated depth, 0/13, registry profile counts, GY preregistration gate, and malformed frontmatter—was verified. |

## Pass A — Repository-anchor verification

### Result

**Substance mostly verified; anchor quality materially fails the audit bar.**

The contamination census contains 43 repository-anchor occurrences collapsing to 25 distinct
path/range pairs. All 25 were opened at the exact baseline. The decisive substantive conclusions
survive, but two range patterns are systematically wrong:

1. all thirteen adjudication links use `:1-170` even though line 170 does not exist in any of the
   thirteen files; and
2. the repeated constitution link `:404-430` contains the forward-direction section, while the
   cited facts—one integrated case, twelve per-slice cases, all thirteen blockers, zero useful
   rate, shadow B, and unbuilt D3.8—are at `:382-398`.

A third wrong range appears in the main report: `failure-patterns.md:200-900` does not contain the
P29/P33/P34 definitions. The claims are true in the repository, but not at the cited location.
This distinction matters because an auditor must be able to reproduce the sentence without
searching the whole file.

The census also overstates non-null gold cards for EU, India, and Pakistan and undercounts the
calibrated deep-pilot manifests by excluding synthetic housing from the sentence “three.” Neither
changes the finding that the current corpus is visible regression material, but both must be
corrected.

### Main-report sampling rule

The main report sample was **judgmental and adversarial**, not random: every anchor carrying an
executive conclusion, current capability statement, denominator, ua-msme disposition, sequence
mechanism, independence assertion, risk-accounting assertion, S0-GAP-02 seam, INT-R1 seam, status
mapping, or final consolidation claim was included, plus at least one anchor from every numbered
section. Thirty-two anchor claims across twenty-eight distinct files were checked. The detailed
ledger records each result.

## Pass B — External-citation verification

**Result: strong transfer discipline; one load-bearing transfer remains only rhetorical.**

Every named source exists as cited. The report accurately describes adaptive holdout reuse,
prospective registration and amendments, Registered Reports, researcher degrees of freedom,
group-sequential and anytime-valid methods, regulatory corroboration, benchmark contamination,
inter-rater diagnostics, file-drawer bias, commitments, and timestamping.

The report is particularly careful not to convert those sources into an authority theorem. It
states that PolicyOS has no identified sampling population, that n=1 does not support external
validity, that agreement is not correctness, that a rebuilt test may be harder, that FDA guidance
is product-specific and nonbinding, and that commitment machinery cannot prove semantic truth.
Those limits are supported by the primary sources.

The exception is not a citation error but a transfer-completion error. Pocock, O'Brien-Fleming,
and Howard et al. support the proposition that repeated looks require aggregate control. INT-R9
then says the existing ledger provides that control. The code proves only scope-local control.
The source is correct; the bridge to this repository is not.

## Pass C — Does the protocol prove its stated claim?

### Clause-to-mechanism result

| Section 4.2 clause | Intended mechanism | Audit verdict |
| --- | --- | --- |
| exact protocol, revision, environment, case, cutoff, evaluator, basis, assumptions | preregistration plus freeze and commitments | supported as a governance requirement, not operationally present today |
| earliest eligible slot | fixed three-slot order and immutable chronology | supported for ordering only |
| canonical owner predicates satisfied | existing N9/firewall/owner receipts | correctly delegated, presently not a demonstrated real positive capability |
| procedural predicates satisfied | sealed cases, adjacent case, falsifiers, no-bespoke review, panel | substantially specified, subject to findings D-002/D-003/E-002/F-002 |
| no material unresolved dispute | panel and materiality rule | under-specified because materiality decision right remains open |
| no prohibited selection or case-specific mechanism found | provenance, pool selection, no-case-specific-code review | bounded and auditable, but cannot remove upstream pool-author bias or covert collusion |
| cumulative false-promotion risk across the earliest-positive search | confidence-ledger reference | **not established; blocking** |

The document does not generally slip into “PolicyOS works” language. Its overreach is narrower but
load-bearing: it represents the three-slot search as operating under one cumulative accounting
regime when the canonical owner supplies a budget per design-problem scope.

## Pass D — Multiplicity across three slots

**Result: blocking.**

Let `E_i` be a false positive in slot `i`. INT-R9 fixes three slots and stops on the first positive.
At baseline, each case is naturally a distinct N9 problem binding. The canonical scope key is the
case's `design_problem_id`. Each scope therefore starts with its own event history, ordinal zero,
and top-level registry `delta`.

The protocol does not name:

- a canonical sequence-level scope accepted by N9;
- a parent pool containing the three problem scopes;
- a predeclared allocation `delta_1 + delta_2 + delta_3 <= delta`;
- a cross-scope global ordinal;
- a theorem allowing the existing per-scope guarantees to compose; or
- a verifier that rejects three independently reset scopes.

The words “same cumulative ledger scope stays unchanged” are also incompatible with the present
N9 source unless all three different cases somehow share a design-problem identity, which would
create a separate identity defect and is not required anywhere in the protocol.

Consequently, a fully compliant executor can obtain three individual statements
`P(E_i | A_i) <= delta` and select the first positive. Those statements do not imply
`P(E_1 union E_2 union E_3 | A) <= delta`. Without additional structure the generic bound is
`<= 3 * delta`. The exact dependence may be better or worse for other goals, but no unproved
dependence assumption may be used to recover `delta`.

Void/refused slots do not fix this. INT-R9 says their ordinal cannot be refunded, but the next
case opens a new scope whose code-visible history contains no prior slot and therefore assigns
ordinal zero again.

## Pass E — The ua-msme horn

**Result: correct core decision, incomplete payment of the new-case cost.**

The exclusion is sound. Repository evidence confirms all four decisive facts:

- ua-msme is the only integrated-depth case;
- S12/S13/S14 development evidence names it;
- its adjudication expectations are public; and
- `CanonicalPromotionInput` carries a ua-msme G4 reference by default.

No current corpus case should re-enter as decisive primary or adjacent evidence. Public regression
and panel calibration may still include ua-msme because those uses are openly non-holdout and do
not restore freshness.

The protocol relocates one degree of freedom, however. Section 4.4 permits one independent case
unit to create six case pairs and the corresponding expectation/evaluator packages. That unit can
follow every rule and author a pool around mechanisms it expects the implementation to handle.
Public randomness then randomizes within a favorable authored pool. INT-R9 acknowledges upstream
topic-selection bias in general, so this does not refute its narrow claim, but consolidation must
not describe the new pool as uncontaminated merely because its answer keys were hidden.

## Pass F — Independence

**Result: operational definition is materially better than the repository baseline, but not a
complete construction.**

The hard requirements are commendable: real named humans, signatures, three members and two
predeclared alternates, no post-vote reviewer substitution, no unresolved material dissent,
published raw votes, and an explicit statement that a synthetic reviewer or role ID never
satisfies independence. Current role placeholders therefore cannot qualify, and the report treats
that as a blocking prerequisite.

A compliant positive-seeking insider can still nominate friendly people who are not direct line
managers, did not write the code/case/criteria, have no contingent pay, and sign complete
self-disclosures. The protocol records affiliations and interests but does not always require
independent corroboration of those facts or exclude same-funder, same-governance-network, or
non-contingent reputational alignment. This residual is partly unavoidable, and the report admits
covert collusion cannot be disproved. The material defect is that “independence satisfied” may be
computed almost entirely from declarations unless the evidence standard is made explicit.

The opposite insider can also comply: return precise owner-backed refusals on every unseen real
case, keep public known-groundable controls green, emit acquisition records, and never accept the
risk of a real positive. The protocol detects constant mechanical refusal; it does not make
well-reasoned strategic refusal non-dominant.

## Pass G — Both incentive directions

**Result: positive-rate gaming is observable; abstention dominance remains open.**

Section 4.14 is not decorative. Easier-case substitution, hidden reruns, changed thresholds,
materiality drift, attempt exclusion, denominator edits, off-rule stopping, case-specific repair,
and outcome-contingent reward are observable audit targets. The deterministic positive control is
explicitly excluded from real promotion and from the useful-rate numerator; no contrary path was
found.

Section 4.15 should be read as a partial detector, not as “preventing abstention.” Public controls
and exact refusal reasons can reveal a broken positive path or unsupported safety rhetoric. They
cannot distinguish an honestly cautious system from a strategically cautious system that refuses
all novel cases for defensible-looking reasons. The report says INT-R9 does not solve grounding
economics, which is honest; its heading and later consolidation language must remain equally
narrow.

The YAML also says the immutable denominator includes “every precommitted slot,” while the prose
says a slot enters once inspected. That is a substantive metric-definition ambiguity. INT-R9 is
not authorized to redefine the existing useful-design denominator.

## Pass H — S0-GAP-02 and INT-R1 seams

**Result: S0-GAP-02 seam mostly sound; INT-R1 seam requires consolidation correction.**

The audited files do not select a cryptographic primitive or implement key custody. They defer
canonical serialization, hiding/binding commitment, independent time evidence, least-privilege
access, dual reveal, rotation, challenge, incident response, and inter-reviewer adjudication to
S0-GAP-02. Their distinct additions—first-event chronology, finite slots, no substitution,
negative publication, no-bespoke review, and correction of the first public claim—are genuine
INT-R9 deltas.

The phrase “or a consolidation-approved equivalent” is unsafe unless the equivalent is an
explicit canonical supersession of S0-GAP-02, not a sibling implementation.

INT-R1's actual result is semantically compatible only after a stricter mapping:

- consume the delivered `ObligationCoverageEnvelope`, not a nonexistent canonical
  `ObligationSetDeclaration`;
- allow authority-band promotion only when the envelope is `bounded_complete` relative to the
  exact declared closure basis and obligation language, with the public open-world rider;
- treat `known_incomplete` as NO-GO for the affected action;
- treat `open_world_unresolved` as NO-GO whenever the unresolved remainder may be material to the
  protected action; and
- allow candidate-band work only with the ratified typed limitation, never by silently narrowing
  the same scored claim after inspection.

The anti-selection record can remain historically valid when obligation coverage blocks
promotion. That part of INT-R9 degrades correctly.

## Pass I — Scope discipline and the YAML question

**Result: repository scope is clean; YAML standing is not.**

The diff verifies five additive files, 3,708 insertions, and no edit under `src`, tests, the
outcome corpus, adjudications, or any pre-existing document. No production package, database,
canonical owner, or authority grant is appointed. The state machine is explicitly described as a
custody workflow and does not claim to replace the composed authority lattice.

The YAML nevertheless behaves like a contract. It fixes a protocol identifier, queue length,
pool and panel counts, required fields, exact literals, automatic blockers, state transitions,
quorum, vote rule, denominator membership, preconditions, and a complete executable sequence. It
even declares itself authoritative for a “research-level executable procedure.” An implementer
could load it and claim conformance without revisiting the unresolved risk scope, materiality,
INT-R1 type, denominator, and repair questions. The disclaimer
`research_shape_not_canonical_contract` does not change that functional shape.

Given the blocking multiplicity defect, the frontmatter result must not remain
`accepted_narrow_scope`. The correct standing before consolidation is `blocked` or an equivalent
research-blocked disposition.

## Pass J — Audit of supplied orientation

**Result: two supplied premises were false, one was imprecise, and INT-R9 only partly corrected
them.**

Exact enumeration yields:

- calibration/topology: four `deep-pilot-round-1` + `deep_pilot_overlap`; eleven `null` +
  `partial_disjoint`;
- authority levels: five `production`, six `governed`, four `research`;
- all reviewers are role-like IDs with `none_declared`, but the manifests are not uniform in
  authority standing;
- expected IDs, labels, and votes are visible in every manifest; non-null gold cards are not
  universal.

The prompt's null-calibration generalization was wrong. INT-R9 improved it by finding Berlin,
Boston, and EU, but omitted the synthetic housing deep-pilot manifest. The prompt's generalized
`authority_level: research` was also wrong and was not fully corrected in the report.

The other supplied premises were verified at the baseline: thirteen real cases plus two synthetic
manifests, public answers preventing sealed-holdout use, ua-msme alone at integrated depth, zero of
thirteen conversions, shadow B, unbuilt D3.8, the exact confidence-registry profile counts, the GY
pre-inspection ratification gate, and malformed unquoted revision frontmatter in the GY plan,
Atlas plan, and Wave-2 backlog.

## Commendations consolidation should preserve

1. **The ua-msme decision is honest.** The report does not choose the tractable case and then call
   the choice prospective.
2. **Current labels are not called a holdout.** Public answer-bearing material remains regression
   and calibration only.
3. **Independence is not a role string.** Named humans and raw dissent are mandatory.
4. **Negative outcomes are first-class.** Refusal, dispute, void, exhaustion, and no-attempt are
   publishable terminals.
5. **The external literature is transferred with restraint.** Statistical, regulatory, and
   editorial patterns are not represented as authority theorems.
6. **The claim boundary is unusually explicit.** Population validity, legal compliance,
   competence, readiness, and covert-collusion proof are denied.
7. **S0-GAP-02 is respected in substance.** Generic oracle custody is mostly deferred rather than
   re-owned.
8. **The branch obeys research scope.** No code, test, corpus, or existing document was changed.

## Consolidation disposition

Do not consolidate the protocol as a ratified first-promotion rule at
`f5ad922377e38ee3ddbecb33293300bca25a9ad7`.

The minimum reopening condition is not more prose asserting cumulative accounting. It is an
independently checkable research result showing how the three-slot first-positive event composes
with the canonical confidence ledger's per-design-problem scopes without budget reset, parallel
accounting, or an unratified second ledger. That result must state the exact protected probability
claim and survive the adversary who opens three distinct N9 problem scopes and stops on the first
positive.

After that blocking question is resolved, the material repairs in the recommended-revision file
must be incorporated before consolidation. Until then, the honest status is:

> **INT-R9 research direction promising; protocol not yet valid for governing the first positive;
> no positive result promised or authorized.**
