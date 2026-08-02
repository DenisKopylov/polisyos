---
title: INT-R9 — First-Promotion Fixture and Falsifier Specifications
status: delivered
kind: deep-research-support
research_task: INT-R9
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r9-first-promotion-protocol
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-02
authoritative_for:
  - research-level properties and adversarial fixture specifications for the first-promotion protocol
  - bounded interpretation of source-flip, obligation-removal, adjacent-unseen, sealing, and no-case-specific-code probes
  - edge-case fixtures required by INT-R9
may_not_use_for:
  - production implementation authorization
  - final code, test, or wire contract
  - canonical fixture ownership or package placement
  - authority grant
  - capability claim
  - promise that a positive promotion is achievable
  - benchmark passage
  - proof of open-world obligation completeness
  - legal compliance conclusion
research_only: true
---

# INT-R9 — First-Promotion Fixture and Falsifier Specifications

## 1. Fixture doctrine

A fixture samples a property; it is not the property itself. PolicyOS's failure register warns
against treating a witness or probe as the specification (P33) and against declaring premature
green by excluding a failing run before completing an isolation proof (P34)
([`policy-engine/docs/reference/policy-design-case-failure-patterns.md:350-900`](../../../reference/policy-design-case-failure-patterns.md)).
The ratified custody kernel likewise requires observable predicates, semantically equivalent
implementations, memorization resistance, dissent preservation, committed evaluator packages,
mutations, an adjacent unseen case, and immutable failed-run history
([`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:90-109`](../../../system-design-decisions/stage0-custody-kernel-ratification.md)).

Every fixture below therefore specifies:

- the **property** under test;
- the **construction** and controlled differences;
- the **expected relation**, not an implementation-specific enum or graph;
- evidence needed to decide the probe;
- the bounded inference allowed by a pass;
- an adversarial implementation that would appear green if the fixture were misread.

No fixture changes an existing canonical threshold, denominator, validator, obligation class,
or governance number. Runtime outcomes remain owned by the existing promotion sequence,
waist contracts, firewall, and confidence ledger
([`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:1-270`](../../../../src/polisyos/runtime/quality/promotion_sequence.py);
[`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:120-310`](../../../../src/polisyos/pdc/_impl/gy_waist.py);
[`policy-engine/src/polisyos/runtime/quality/candidate_firewall.py:1-260`](../../../../src/polisyos/runtime/quality/candidate_firewall.py)).

## 2. Fixture matrix

| ID | Property | Minimum construction | Required relation | Pass supports | Pass does not support |
| --- | --- | --- | --- | --- | --- |
| FP-F01 | Prospective registration | Commit protocol, all slot identities/order, case packages, expectations, criteria, stopping, adjudicators, and publication rule; establish independent transaction visibility before any inspection. | `transaction_visible_at < first_inspection_at`, accounting for clock accuracy. | This attempt was governed prospectively. | Absence of secret collusion or completeness of criteria. |
| FP-F02 | Fixed selection/order | Precommit a finite ordered queue; make a later unregistered case produce a superficially better result. | Only the next committed slot can be scored; unregistered success is exploratory. | No post-result case substitution occurred. | The committed selection rule was substantively representative. |
| FP-F03 | Public regression conformance | Run all 13 real cases, 2 synthetic adjudications, and public mutations with the frozen implementation. | All predeclared visible predicates pass before holdout reveal. | No named public regression under that revision. | Holdout validity or generalization. |
| FP-F04 | Sealed answer custody | Separate input and answer/evaluator packages; hiding commitment, independent custody, access log, dual-control reveal. | No prohibited answer access before candidate-output freeze; commitment verifies on reveal. | The answer package was not observably available through governed channels. | Impossibility of covert leakage or correctness of the answer. |
| FP-F05 | Source-dependency sensitivity | Flip/revoke/supersede one predesignated material dependency while preserving transport shape and unrelated facts. | Same positive authority claim cannot survive unchanged. | Sensitivity for the sampled dependency relation. | Sensitivity to every possible source or obligation. |
| FP-F06 | Obligation monotonicity | Remove, invalidate, or make unknown one predesignated material required obligation/certificate. | Positive promotion under the same authority claim is impossible. | Monotone response for the sampled material obligation. | Open-world obligation completeness. |
| FP-F07 | Identifier independence | Consistently replace case, source, claim, artifact, and delivery IDs with opaque values. | Semantically equivalent terminal decision and trace relations. | No dependence on sampled literal identifiers. | Absence of semantic fingerprinting or hidden case-specific aliases. |
| FP-F08 | Delivery-order robustness | Permute admissible arrival order without changing source facts or temporal semantics. | Equivalent authoritative outcome after canonical ordering/replay semantics. | Robustness to sampled delivery order. | Correctness under every late-data scenario. |
| FP-F09 | Wrong-scope sensitivity | Create a surface-similar case with changed jurisdiction, validity interval, purpose, delegation, or authority scope. | Original positive authority is not silently reused. | Scope sensitivity for sampled boundary change. | Full legal or institutional scope correctness. |
| FP-F10 | No case-specific code | Freeze all executable/configuration assets; scan IDs/fingerprints; inspect provenance; opaque-ID mutation; same-binary adjacent run. | No direct or indirect case-conditioned branch, binding, prompt, registry entry, or adapter. | No detected case-specific mechanism under the stated audit. | Mathematical proof that no semantic shortcut exists. |
| FP-F11 | Adjacent transfer | Pair a separately authored, separately sealed case in the same declared mechanism/problem family but materially different context. | Same frozen binary/configuration reaches the sealed-oracle-correct terminal behavior. | One bounded transfer check. | Population external validity or requirement that both cases promote. |
| FP-F12 | Nontrivial abstention | Public deterministic positive control plus known-groundable public seeds; retain owner floors. | System can traverse the technical positive path on the control and does not invariantly refuse known-groundable seeds. | Refusal is not mechanically constant on named controls. | Existence of a promotable real policy case. |
| FP-F13 | No hidden rerun / best-run selection | Instrument run IDs, seeds, source snapshots, and execution ordinals; inject an initially unfavorable output followed by a favorable rerun. | First result-bearing run is scored; later run cannot replace it. | No observed best-run selection. | Full protection against fabricated logs. |
| FP-F14 | Result-independent publication | Produce a refusal/void/dispute outcome. | Same durable public record, raw votes, deviations, denominator, and review visibility as promotion. | Negative outcome was not put in the file drawer. | Organizational absence of informal career penalties. |
| FP-F15 | Post-promotion correction | After a promotion record, reveal a material source invalidation or custody defect. | Append-only challenge and canonical suspension/correction/withdrawal/supersession; original retained. | Current and historical truth remain reconstructable. | That the initial decision was reasonable ex ante. |
| FP-F16 | Pre-inspection amendment | Discover an error before any input, output, answer, or result-bearing access. | Old version retired only with affirmative no-inspection proof; new version gets new commitment and public diff. | Prospective correction without outcome tuning. | Cleanliness when access evidence is incomplete. |
| FP-F17 | Criterion ambiguity | Reveal a case for which a sealed criterion has two materially different reasonable readings. | Dispute; no favorable interpretation chosen for the scored run; clarification applies only prospectively. | Ambiguity cannot be resolved by outcome preference. | That all criteria are unambiguous. |
| FP-F18 | Adjudicator succession | Remove one panel member after partial review. | Only a predeclared clean alternate may substitute; otherwise dispute. | No outcome-conditioned reviewer shopping. | Absolute independence from undisclosed ties. |
| FP-F19 | Simultaneous qualifiers | Two slots appear qualifying in overlapping wall-clock time. | Earlier committed slot and canonical transaction order determine firstness. | “First” was not selected by attractiveness. | Comparative quality of the two candidates. |
| FP-F20 | Old hand-coded binding | Introduce a binding authored in an earlier slice whose author has left, without a literal current case ID. | Automatic NO-GO when provenance shows heldout-case conditioning. | Contributor departure does not cleanse contamination. | Detection of every undocumented historical binding. |

## 3. Detailed falsifier specifications

### 3.1 FP-F05 — source flip

**Property.** A positive authority-bearing claim must remain dependent on its admitted material
sources. A source change that removes the justification cannot leave the same claim green merely
because transport, signature, or payload shape still validates.

**Pre-registration fields.** Before candidate inspection, the expectation package identifies:

1. the source artifact and canonical owner relationship;
2. why it is material to the candidate authority claim;
3. the mutation type: `revoked`, `superseded`, `reversed`, `scope_changed`,
   `effective_time_changed`, or `credibility_invalidated`;
4. controlled fields that remain unchanged;
5. acceptable terminal relations after the flip, expressed semantically rather than as one
   enum name;
6. the owner whose output decides the consequence.

**Construction.** Start from the sealed primary input. Change one material source fact while
preserving unrelated evidence, identifiers where possible, transport validity, and input shape.
Examples include:

- an authority instrument remains cryptographically authentic but is revoked before the
  relevant validity interval;
- a source that supported an effect estimate is replaced by a valid correction reversing the
  direction;
- jurisdiction changes while payload text remains identical;
- a dependency is superseded by a later instrument whose scope excludes the candidate.

**Required relation.** The canonical system must not issue the same positive authority claim
with the same scope and maintained assumptions. Depending on existing owner semantics, acceptable
responses include refusal, typed unknown, limitation, revalidation requirement, suspension, or a
narrower claim.

**NO-GO.** Any unchanged positive promotion; a trace that never references the changed dependency;
or a post hoc declaration that the source “was not material” contrary to the sealed package.

**Adversarial pass-by-probe implementation.** Code recognizes the fixture's source ID and refuses
only that ID. FP-F07 opaque identities and the independently authored sealed mutation are therefore
required companions. The property is dependency sensitivity, not recognition of a known red-team
string.

**Bounded inference.** A pass is evidence for one sampled material dependency under one frozen
revision. It is not proof that all external-source changes propagate correctly.

### 3.2 FP-F06 — obligation removal

**Property.** Removing or making unknown a required material obligation cannot make a candidate
more promotable or leave a positive authority claim unchanged.

**INT-R1 seam.** INT-R1 supplies the versioned obligation-set declaration and the honest strength
of its completeness claim. INT-R9 selects one obligation already declared material; it does not
infer that the declaration exhausts the open world.

**Construction.** Preserve the candidate, sources, outputs, and unrelated obligations. For one
precommitted required obligation, perform exactly one mutation:

- remove the obligation artifact;
- replace its verification with `unknown`;
- invalidate its certificate;
- change applicability so that satisfaction is no longer established;
- withdraw the owner theorem/assumption needed to treat it as discharged.

**Required relation.** The canonical owner cannot produce a positive promotion under the same
scope. The trace must identify the missing/unknown obligation or its owner-backed consequence.

**NO-GO.** Promotion remains green; the obligation silently disappears from the denominator; a
new threshold is chosen; or the fixture is excluded after failure without a completed isolation
proof.

**Adversarial pass-by-probe implementation.** Refuse only when a field is physically absent, while
accepting an invalid or unknown certificate. The fixture family must vary the semantic removal
mechanism and evaluate owner state, not one serialization.

**Bounded inference.** One monotonicity sample. No claim of obligation completeness.

### 3.3 FP-F10 — no-case-specific-code check

**Property.** The result arises from general discovery, grounding, evidence admission, and owner
predicates, not a branch or binding conditioned on the heldout case or its semantic fingerprint.
Organizing Rule 12 requires free growth without production hard-coding
([`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:145-230`](../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md)).

**Freeze scope.** Before primary input reveal, bind:

- source tree, generated source, build outputs, dependency lock and resolved artifacts;
- models, prompts, templates, feature flags, environment variables, and random-seed policy;
- adapters, aliases, registries, lookup tables, bindings, evidence dictionaries, and source
  fingerprints;
- query code, source cutoff, caches, and evaluator executable;
- infrastructure image and declared nondeterministic dependencies.

**Evidence bundle.** A passing check requires all of:

1. pre-reveal/post-run equality receipts for frozen assets;
2. literal case/source/claim identifier scan;
3. semantic fingerprint and alias review;
4. binding provenance: author, first commit, purpose, source inputs, case exposure, later edits;
5. registry/adapter delta proof;
6. opaque-identity mutation;
7. same-binary, same-configuration adjacent case;
8. signed declarations from responsible maintainers, treated as evidence but not sufficient
   alone;
9. investigation of prior case-conditioned development, including departed contributors.

**Automatic failure.** A direct branch, hidden fixture, hand-coded binding, case-only adapter,
post-reveal prompt/configuration change, or an older case-conditioned mapping whose provenance
predates the current author.

**Why literal scans are insufficient.** A case can be selected by source URL, claim phrase,
domain alias, vector fingerprint, evidence-family combination, or an indirectly activated
registry. The check is provenance- and behavior-based.

**Adversarial pass-by-probe implementation.** Replace `if case_id == X` with a hash, source URL,
or semantically equivalent alias. FP-F07, FP-F11, provenance review, and registry audit close
this obvious loophole but cannot prove absence of every hidden semantic shortcut.

### 3.4 FP-F11 — adjacent unseen case

**Property.** The frozen implementation's behavior is not unique to one concealed case.

**Construction.** The independent case-author team creates the primary/adjacent pair before
implementation-side reveal and commits both. The adjacency declaration names:

- shared mechanism or policy-problem family;
- the dimensions intentionally held comparable;
- at least two material differences, chosen from jurisdiction, time, source family, affected
  population, administrative form, implementation context, or evidence quality;
- why the adjacent case is not a paraphrase, field-order mutation, or identifier substitution;
- separate authorship and custody evidence.

**Execution.** The adjacent case is run with the exact same frozen source, build, dependencies,
model/prompt, configuration, adapters, evaluator executable, and rule versions. No adjacent-case
patch is permitted.

**Required relation.** The sealed oracle determines the correct terminal **behavior**, which may
be promotion, limitation, refusal, or unknown. Requiring a second positive would optimize the
forbidden useful-design rate and could reward overclaiming. A correct refusal on the adjacent case
can be the right transfer result.

**NO-GO.** Different binary/configuration; material case-specific binding; incorrect sealed-oracle
behavior; the adjacent case was public or previously developed against; or adjacency was declared
only after seeing both results.

**Bounded inference.** Evidence of one adjacent transfer, not representativeness or domain-wide
external validity.

### 3.5 FP-F04 — sealed-holdout construction and leak test

All 13 current real cases and both synthetic adjudications are public, with expected claim IDs,
labels, gold cards, and reviewer votes in the git tree; they are therefore regression/calibration
material, not a sealed holdout
([`policy-engine/docs/research/universal-policy-design/outcome-corpus/README.md:1-48`](../../universal-policy-design/outcome-corpus/README.md);
[`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/README.md:1-52`](../../universal-policy-design/outcome-corpus/adjudications/README.md)).

**Required construction.** Reuse S0-GAP-02 for:

- independent input and expectation/evaluator packages;
- canonical serialization;
- hiding and binding commitment with high-entropy randomness or another approved hiding
  mechanism;
- custodian signatures and independently verifiable transaction/proof-of-existence;
- least-privilege access, immutable access logs, dual-control reveal, rotation, succession,
  challenge, and incident response;
- reveal verification and retained raw expectations.

A plain hash of a small predictable answer space can prove later change detection but may be
brute-forced and does not itself establish secrecy. NIST FIPS 180-4 describes hash digests as a
way to detect message changes; commitment literature distinguishes hiding from binding; RFC 3161
provides a proof-of-existence time-stamp building block. Mechanism choice remains with S0-GAP-02.

**Leak injection.** Before candidate-output freeze, grant one unauthorized implementation-side
principal access to any answer-bearing content or provide a side channel that narrows a
promotion-critical expectation.

**Required relation.** The slot becomes `void` or `disputed`; no favorable result survives; the
slot remains in history, denominator, and chronological risk scope.

**Adversarial pass-by-probe implementation.** Log only formal file downloads while exposing the
answer in issue text, branch names, model context, screenshots, reviewer comments, or metadata.
The access model must cover all governed disclosure channels, and incident attestation cannot be
limited to one storage service.

## 4. Insider adversaries

### 4.1 FP-A01 — insider wants a positive result and follows every literal rule

**Attack.** Before sealing, the insider authors an “unseen” case that closely mirrors known
ua-msme bindings; chooses three easy strata; writes vague materiality rules; appoints friendly
nominally external reviewers; commits a queue but encodes the likely winner first; uses an
unsalted hash of a tiny answer key; and rewards the team when useful-design rate rises. No rule
that merely says “preregister, seal, use an independent reviewer” is literally broken.

**Required protections.** The protocol passes this adversary only if it requires:

- case authors independent of implementation and case selection;
- explicit population and exclusion rules plus independently reviewed queue selection;
- all primary/adjacent cases and answers sealed before first inspection;
- operational human independence and conflict disclosures;
- hiding commitment and access proof, not “a hash exists”;
- criteria calibrated and materiality resolved before sealing;
- no-case-specific-code provenance review;
- immutable order and result-independent publication;
- observable useful-design-rate firewall and no output-contingent incentives;
- bounded public claim and challenge route.

**Residual impossibility.** No governance record proves the absence of secret collusion or
fabricated custody evidence. The protocol closes observable and opportunistic degrees of freedom;
it does not make fraud mathematically impossible.

### 4.2 FP-A02 — insider wants to avoid blame and refuses everything

**Attack.** The system returns a generic blocker for every case. Because abstention is praised as
honest, no individual risks issuing the first positive claim. Useful-design rate remains zero and
every NO-GO is technically “safe.” This realizes tradeoff T6: the incentive gradient points away
from expensive grounding
([`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:300-455`](../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md)).

**Required protections.** Without promising a real positive, the protocol requires:

- owner-backed, evidence-linked refusal reasons rather than generic safety prose;
- public contract-level positive control demonstrating that the technical path is not locked;
- known-groundable public seeds to measure false abstention/search recall;
- acquisition/repair records where existing owners support them;
- no domain-ceiling claim while search recall, index freshness, or evidence acquisition is
  inadequate;
- identical publication visibility for refusal and promotion;
- review of invariant refusal across semantically different cases.

**Boundary.** The positive control is not a real promotion, does not enter the useful-design-rate
numerator, and does not prove a positive real case exists. It distinguishes technical paralysis
from honest refusal only within its specified contract surface.

### 4.3 FP-A03 — departed author left a hand-coded binding

**Attack.** Three slices earlier, a contributor wrote a source-to-lever mapping for what later
became a sealed case. The current team did not select the case after seeing a result and nobody
currently remembers the code's purpose.

**Required relation.** Provenance, source fingerprints, historical commit context, and behavior
show case conditioning; FP-F10 fails automatically. Employment status and current intent are
irrelevant.

## 5. Required edge-case fixtures

### FP-E01 — registered case fails; unregistered case succeeds

- **Setup:** slot 1 refuses; a developer runs an unregistered case and obtains a positive owner
  receipt.
- **Expected:** slot 1 remains refused; unregistered run is labeled development/exploratory and
  cannot become first promotion; slot 2 is the only next scored case.
- **Falsifier:** any public wording treating the unregistered result as governed first promotion.

### FP-E02 — adjudicator unavailable mid-adjudication

- **Setup:** one panel member becomes unavailable after other votes are recorded.
- **Expected:** use only the predeclared clean alternate, with no outcome-conditioned choice;
  otherwise dispute.
- **Falsifier:** appointing a replacement after inspecting vote direction or candidate result.

### FP-E03 — criterion ambiguous after sealing

- **Setup:** two reasonable interpretations lead to different outcomes.
- **Expected:** material ambiguity produces dispute; no interpretation is retroactively chosen;
  a clarified v2 applies only to fresh cases.
- **Falsifier:** “clarification” that rescues the current positive.

### FP-E04 — sealed holdout leaks

- **Setup:** answer-bearing information is exposed before candidate-output freeze.
- **Expected:** void/dispute; slot retained; no substitute inserted; incident published.
- **Falsifier:** rotating the answer key and pretending the same case is unseen.

### FP-E05 — promotion later found unjustified

- **Setup:** later evidence establishes source invalidity, hidden binding, or oracle error.
- **Expected:** append-only challenge and canonical correction/suspension/withdrawal/supersession;
  original record preserved; public currentness changes.
- **Falsifier:** deleting the first record or leaving the public claim unqualified.

### FP-E06 — two candidates qualify simultaneously

- **Setup:** asynchronous execution makes slots 1 and 2 appear positive at similar times.
- **Expected:** this situation itself is nonconforming if slot 2 began before slot 1 was terminal;
  firstness follows committed order and canonical transaction order, not finish time or quality.
- **Falsifier:** selecting the more impressive case.

### FP-E07 — preregistration mis-specified before any result is seen

- **Setup:** an unambiguous clerical/schema defect is found before any case or answer access.
- **Expected:** old version may be retired only with affirmative no-inspection proof; publish diff,
  new commitment, and new transaction time.
- **Falsifier:** relying on participant memory where access logs are incomplete.

### FP-E08 — hidden rerun

- **Setup:** first result-bearing execution refuses; a second succeeds after nondeterministic
  variation.
- **Expected:** first run is scored; second is retained but cannot replace it; retry is permitted
  only under a predeclared infrastructure-failure rule proving no result was exposed.
- **Falsifier:** “best of N” under an undeclared seed policy.

### FP-E09 — exclusion after failure without isolation proof

- **Setup:** a failed fixture is called irrelevant or corrupt after the outcome is known.
- **Expected:** retain failure; exclusion can affect later protocol versions only after a completed,
  owner-backed isolation proof independent of the desired result.
- **Falsifier:** removing it from denominator, regression set, or public record immediately.

### FP-E10 — earlier slot disputed; later slot appears positive

- **Setup:** slot 1 enters material dispute; slot 2 has already been run or is proposed for reveal.
- **Expected:** halt. Slot 2 cannot become first until slot 1 is resolved; initiating slot 2 while
  the rule required a halt is itself a process violation.
- **Falsifier:** calling slot 2 “first uncontested promotion.”

## 6. Public regression battery

The visible battery may include all 13 canonical real cases, both synthetic adjudications, and
public metamorphic mutations. It must be run before any sealed holdout reveal. The current corpus
README limits annotation authority to evaluation and explicitly denies runtime/claim authority
([`policy-engine/docs/research/universal-policy-design/outcome-corpus/README.md:1-48`](../../universal-policy-design/outcome-corpus/README.md)).
The S14 assurance manifest similarly carries a narrow `authoritative_for`/`may_not_use_for`
boundary and development evidence involving ua-msme and other cases
([`policy-engine/architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json:1-340`](../../../../architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json)).

Minimum public mutations:

1. opaque IDs;
2. admissible delivery-order permutations;
3. semantically equivalent encodings;
4. wrong-scope look-alikes;
5. source flip;
6. obligation removal/unknown;
7. stale-but-cryptographically-valid source;
8. one deterministic contract-level positive control;
9. known-groundable seeds for false-abstention/search-recall monitoring;
10. one visible case carrying intentionally hand-coded binding, expected to fail the
    no-case-specific-code check.

A public battery failure is an automatic NO-GO before sealed answer reveal. Passing it supports
only named regression predicates.

## 7. Sealed primary and adjacent package template

```yaml
SealedCasePairPackage:
  package_id: opaque
  package_version: exact
  authors_and_conflicts: [signed identity/disclosure refs]
  selection_rule_ref: exact
  primary:
    input_commitment: hiding/binding commitment ref
    expectation_evaluator_commitment: hiding/binding commitment ref
    declared_domain_stratum: text
    source_and_time_scope_commitment: ref
  adjacent:
    input_commitment: hiding/binding commitment ref
    expectation_evaluator_commitment: hiding/binding commitment ref
    adjacency_declaration_commitment: ref
  falsifiers:
    source_flip_commitment: ref
    obligation_removal_commitment: ref
    wrong_scope_commitment: ref
  custody:
    custodian: accountable identity
    received_at: CTM R5
    transaction_visible_at: CTM R6
    access_policy_ref: ref
    access_log_ref: ref
    dual_control_reveal_rule_ref: ref
  disclosure_order:
    - freeze implementation/environment/source cutoff/evaluator executable
    - reveal primary input
    - freeze candidate output
    - reveal primary expectation/evaluator package
    - if primary otherwise qualifies, reveal and run paired adjacent input with same freeze
    - freeze adjacent output
    - reveal adjacent expectation/evaluator package
  authority_boundary:
    authoritative_for:
      - exact heldout input/expectation relation and sealed evaluation instructions
    may_not_use_for:
      - legal truth beyond cited sources
      - domain representativeness
      - proof a positive result exists
      - production authorization
```

## 8. Acceptance table

A slot can reach procedural `promoted` only when every applicable row is green and every
underlying existing owner receipt independently permits promotion.

| Gate family | Pass condition | Refusal/void/dispute trigger |
| --- | --- | --- |
| Prospectivity | FP-F01 strict order proven. | Missing/ambiguous order, late seal, unlogged access. |
| Selection | FP-F02 next slot; no substitution or hidden prior slot. | Wrong case, omitted attempt, best-case selection. |
| Public regression | FP-F03 complete green on frozen revision. | Any predeclared visible regression failure. |
| Sealing | FP-F04 commitment verifies; no prohibited access. | Leak, unverifiable commitment, custodian breach. |
| Canonical owners | Existing promotion/obligation/firewall/confidence receipts valid and in scope. | Any fail, unknown, scope insufficiency, bypass, or invalid receipt. |
| Falsification | FP-F05 and FP-F06 produce required authority downgrade/refusal. | Same positive claim survives. |
| Generality | FP-F07/08/09 and FP-F10 pass. | Identifier, order, scope, or case-specific dependence. |
| Adjacent transfer | FP-F11 sealed-oracle-correct with same freeze. | Wrong behavior or changed implementation/configuration. |
| Non-paralysis | FP-F12 controls behave as declared. | Invariant refusal or technically locked positive path. |
| Run custody | FP-F13 first result-bearing run retained. | Hidden rerun or seed selection. |
| Adjudication | Named panel, quorum, no dispute/material dissent, calibrated criteria. | Role-only identity, conflicts, quorum loss, material ambiguity. |
| Publication | FP-F14 complete regardless of sign. | Negative result hidden, delayed, or demoted. |
| Claim boundary | Named revision/case/environment/evaluator/assumptions only. | Legal, production, population, or competence overclaim. |

## 9. Fixture kill rules

A fixture family is killed or redesigned prospectively when:

- it depends on one literal runtime enum, graph topology, scheduler, or state machine rather
  than the semantic property;
- the expected answer becomes implementation-visible before the relevant freeze;
- its case or mutation has been used for tuning;
- the oracle/evaluator package cannot be reconstructed and versioned;
- a material ambiguity has no prospectively declared resolution;
- the fixture only distinguishes a known hard-coded string and fails under semantic aliases;
- it changes an existing canonical owner threshold or denominator;
- it rewards invariant refusal or presupposes a positive real-policy outcome;
- a passing result would be advertised beyond the bounded inference listed here.

A killed fixture is never silently removed from a completed scored run. The old run and reason
remain public; redesigned fixtures apply only to a new protocol version.

## 10. Primary-source orientation for the fixtures

The fixture design borrows narrowly from several external regimes:

- Dwork et al. formalize adaptive holdout reuse; INT-R9 takes the warning that repeated
  feedback makes a holdout part of development, but does not claim their distributional theorem
  for an n=1 authority decision.
- Registered Reports bind review and publication before results and use outcome-neutral quality
  checks; INT-R9 transfers prospective acceptance, deviation retention, negative-result
  publication, and positive controls, not randomized-study inference.
- Simmons et al. and Gelman/Loken identify outcome-relevant researcher degrees of freedom even
  without conscious fraud; INT-R9 therefore binds selection, stopping, exclusions, criteria,
  adjudicators, runs, and publication, not only thresholds.
- Recht et al. and later contamination work motivate fresh one-time cases and semantic, not only
  string, decontamination; INT-R9 still treats adjacent evidence as bounded.
- Cohen and Krippendorff supply agreement diagnostics; INT-R9 does not treat agreement as truth.
- Rosenthal and Registered-Report evidence motivate result-independent publication; the
  protocol still cannot by itself remove every informal career incentive.

Full references and transfer limits appear in the primary INT-R9 report.
