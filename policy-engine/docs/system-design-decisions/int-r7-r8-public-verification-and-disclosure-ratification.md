---
title: Public Verification And Disclosure — Ratification Record (PV-K01–PV-K09)
status: ratified design decision — the nine public-verification and disclosure invariants
owner: team-architecture
created: 2026-08-05
last_reviewed: 2026-08-05
decision_status: accepted — ratified by the human principal (owner decision, 2026-08-05); this document is the acceptance record for all nine statements, for the refutation list, and for the three architect corrections applied to the consolidation
supersedes: nothing (it ratifies research statements; it amends neither the constitution, the Stage-0 custody kernel, nor the INT-wave claim-semantics kernel)
source_kernel: docs/research/policy-operations/consolidation/int-r7-r8/int-r7-r8-ratification-candidates.md
parent_lens: docs/system-design-decisions/stage0-custody-kernel-ratification.md
research_scope: [INT-R7, INT-R8]
int_r7_controlling_head: 3883b45476aed138beface8c8ca817191c7e273e
int_r8_controlling_head: 286ade1057c9abb95bb1cf2c962479906f764667
informs:
  - docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
  - docs/plans/active/layer3-slices/GY-engine-subordination.md
  - docs/research/policy-operations-and-real-world-runtime-backlog.md
related:
  - docs/system-design-decisions/stage0-custody-kernel-ratification.md
  - docs/system-design-decisions/int-wave-claim-semantics-ratification.md
  - docs/system-design-decisions/policyos-identity-and-custody-boundary.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
authoritative_for: [public_verification_dispositions, disclosure_semantics_rulings, int_r7_int_r8_current_standing, rfr_06_correction]
may_not_use_for: [capability_claim, production_schema, code_contract, wire_format, status_lattice, canonical_owner_assignment, vendor_or_authority_appointment, authority_grant, legal_compliance_conclusion, implementation_authorization, benchmark_passage, publication_permission, first_public_gate_opening, numerical_disclosure_bound]
---

# Public Verification And Disclosure — Ratification Record

## 1. What is ratified

Nine statements, `PV-K01`–`PV-K09`, all ratified as written. They come from the consolidation of
two research threads and their independent audits, amendments, remediations and conformance
verifications: `INT-R7` (the lifecycle of a public cryptographic proof) and `INT-R8` (what is lost
in compression and what can be reconstructed across projections). They map one-to-one from the
consolidation's candidates `RC-01`–`RC-09`.

Also ratified, and equally binding: the **refutation list** in §5, and the **three architect
corrections** in §6.

### Why a third act

Three ratification records now exist, and each has its own subject:

- **Stage 0** ratified the **custody of claims** — who owns what, and what does not silently become
  something else.
- **The INT wave** ratified **what a number may mean** — δ's basis, when numbers compose, and what
  survives when no number may be issued.
- **This act** ratifies **what a public proof and a public projection may mean** — when a signature
  amounts to a public result, what a shorter public object may drop, and what a release history may
  claim.

Amending either prior kernel for a third subject would blur all three. The records are related by
inheritance, not revision.

## 2. The lens, inherited

The evaluation instrument is unchanged from the Stage-0 record
(`stage0-custody-kernel-ratification.md:46-88`, binding application note at `:164-176`):

> **Does the statement bind only the authority band, or does it leak into the candidate band?**

Its instantiation here is narrower than in either prior act, and worth stating exactly because the
temptation differs again. Stage 0 risked forbidding *action*; the INT wave risked forbidding
*arithmetic*. This act risks forbidding **construction** — declaring that because a public claim is
unavailable, the mechanism behind it is illegitimate. It is not. Every statement below constrains
what may be **issued, represented or relied upon as governed authority**. None forbids computing a
signature, prototyping an aggregate display, generating a summary, running a heuristic, exploring a
cryptographic construction, or measuring leakage under an explicit model. `PV-K06` blocks a
heuristic from carrying governed safety, not from running. `PV-K08` blocks a canonical number, not
the research that might one day justify one.

All nine passed on that test. None was amended.

## 3. Dispositions

| ID | Statement | Disposition |
| --- | --- | --- |
| **PV-K01** | Public verification is a separately reportable vector | Ratified as written |
| **PV-K02** | Historical authenticity and current authority are non-erasing and distinct | Ratified as written |
| **PV-K03** | Proof binds content semantics but cannot choose content or mint authority | Ratified as written |
| **PV-K04** | Semantic parity is use-relative conservative protected-query parity | Ratified as written |
| **PV-K05** | Three categorical omissions always block the governed claim | Ratified as written |
| **PV-K06** | Reconstruction safety requires exact or proved-conservative evaluation | Ratified as written |
| **PV-K07** | Prefix discipline is the accepted no-number composition claim | Ratified as written; blocked in practice by `GY-GAP3` (§6.2) |
| **PV-K08** | No canonical numerical disclosure-composition claim is currently justified | Ratified as written; registers `NXR-02` dormant |
| **PV-K09** | Proof metadata belongs to the disclosure channel | Ratified as written; registers `NXR-01` dormant |

## 4. The statements

### 4.1 Public verification semantics — what a proof establishes

**`PV-K01` — Public verification is a separately reportable vector.**

> A mathematically valid signature may support issuer-issuance authenticity but may not by itself be
> represented as an unqualified public `Verified` result. Governed public verification reports
> issuer issuance, projection faithfulness, public-history establishment, durable verifiability at
> the verification time, current authority at the query cutoff, status-snapshot selection, and
> public evidence obtainability as separately falsifiable dimensions. Any composite positive is
> bounded to the exact evidence package and cutoff it evaluates.

The controlling decomposition is at
`docs/research/policy-operations/int-r7/threat-model-and-verification-predicates.md:775` (§15) and
`:966` (§15.10, which controls the predicate split *inside* §15). Note the word "separately
reportable" and not "independent": the dimensions have dependency relations, and claiming logical
independence was itself corrected during the chain.

**`PV-K02` — Historical authenticity and current authority are non-erasing and distinct.**

> Historical authenticity and current authority are distinct governed propositions. Authenticated
> withdrawal, revocation, supersession, loss of mandate, or stale currentness may make current
> authority false without rewriting or erasing a historically authentic record. Conversely,
> historical authenticity never establishes current authority. A current positive must bind an
> authenticated currentness/status snapshot and its `as_of` cutoff; absent or indeterminate
> currentness is not a current positive.

This is `S0-K08`'s append-only law reaching the public surface, and it is the statement the research
chain most nearly lost. INT-R7's own predicate algebra initially allowed a projection failure, a
lost witness or a broken archive to retroactively negate that an issuer authentically issued a
record — *what happened* being edited by *what we can currently prove*. Two independent
verifications and two remediation passes were spent restoring the separation. GY-N12 remains the
sole epoch/currentness owner; this act creates no second one.

**`PV-K03` — Proof binds content semantics but cannot choose content or mint authority.**

> A public proof may bind source and projection identities, retained semantic items, typed omissions
> and outcomes, declared uses and denied uses, model and rule versions, transcript state, verifier
> disposition, authority evidence and successor/currentness references. The proof layer must not
> decide which content is retained, declare an omission non-material, broaden permitted use, upgrade
> projection-only authority, or turn cryptographic possession, projection, transport, preservation or
> observation into institutional authority.

This is the seam invariant, and the direct application of `S0-K05` and `S0-K07` to a public proof.
Both sides state it: `int-r7/repository-integration-and-dependencies.md:206` (§7.3) and
`int-r8/semantic-contract-and-loss-boundary.md:429` (§13).

### 4.2 Projection semantics — what a shorter public object may be

**`PV-K04` — Semantic parity is use-relative conservative protected-query parity.**

> Governed semantic parity between a source record and a shorter public object is not byte equality.
> It is use-relative conservative protected-query parity: surfaced claims remain source-resolvable;
> claim type, basis, scope, assumptions, material conditions and limitations are preserved; governed
> decisions are equal or more conservative; denied uses do not shrink; active negative terminals,
> dissent, contest, recourse and currentness remain visible; every dropped item has a governed
> reason/effect relation; and unresolved inputs block. Projection may reduce detail but may not
> amplify truth, certainty, authority, currency or permission.

The operative asymmetry is **reduce but never amplify**. Byte equality was rejected in both
directions: it over-blocks legitimate shortening and under-detects a misleading omission that
preserves every byte it keeps.

**`PV-K05` — Three categorical omissions always block the governed claim.**

> For the governed claim classes already ratified, the following omissions are categorically
> material and may not be overridden by editorial judgment: (1) a `delta` without its declared
> obligation set, maintained assumptions and visible relative-basis rider; (2) a hidden refusal,
> void, dispute, terminal no-attempt, exhaustion or equivalent completed negative; and (3) a
> no-number custody claim missing a unique constitutive event or required order relation. Any such
> omission returns a blocking result rather than a more favorable compressed claim.

Each anchor is an already-ratified statement reaching the public surface: `INT-K02`, `INT-K08` and
`INT-K06` respectively. The third is the frontier — a no-number custody claim's content *is* a
history, so dropping one constitutive step silently broadens the proposition. This act does not
enumerate every material omission; it fixes three that editorial judgment may never reach.

**`PV-K06` — Reconstruction safety requires exact or proved-conservative evaluation.**

> A governed non-reconstruction or semantic-safety result may rely only on exact evaluation over a
> declared finite/enumerable or declared-decidable model, or on an abstraction with a proved
> no-false-safe direction for the exact obligation it discharges. Reconstruction, model/observation
> inconsistency, empty consistency set, timeout, unsupported theory, incomplete controlled history,
> out-of-model channel, heuristic, sampling result or unproved approximation cannot inherit a safe
> verdict and must return a typed blocking or not-established result.

The controlling fixtures are at
`docs/research/policy-operations/int-r8/falsifier-suite-and-integration-handoff.md:145-149` — the
`F21` family, where a timeout, an empty consistency set and an unproved sampled evaluator each
return a blocking disposition rather than a safe one. Absence of proof is not proof of safety, and
this statement makes that total: **0 of 78** suite rows admit a path by which an unproved
approximation inherits safety.

### 4.3 Composition and channel — what a release history may claim

**`PV-K07` — Prefix discipline is the accepted no-number composition claim.**

> For a versioned declared release family under custody, a governed system may issue a Boolean
> procedural claim that each controlled candidate disclosure prefix was evaluated prospectively
> against the declared semantic-loss and exact-or-proved-conservative reconstruction obligations;
> membership, chronology, current heads, model versions, inputs and dispositions are reproducible;
> and deletion, reclassification or post-hoc narrowing of controlled history cannot manufacture a
> pass. The claim carries no numerical privacy, risk, performance, compliance or universal-channel
> guarantee.

This is `INT-K06` — a binding falsifiable procedural claim carrying no probability — applied to
adaptive disclosure. It survived the hardest attack put to this wave: an audit instructed to
determine whether it is a budget with the number left implicit found that under a bounded exact
model the question *does the protected predicate retain at least two possible values* is **Boolean**,
consumes no allocation, and handles adaptive next-release choice without any independence
assumption.

The declared release-family registry is explicitly **open**: unknown and uncontrolled channels
remain visible limitations, never silently-complete history. And see §6.2 — this statement is
ratified but currently **not issuable**, because the repository has no owner for the controlled
transcript it presupposes.

**`PV-K08` — No canonical numerical disclosure-composition claim is currently justified.**

> No canonical numerical disclosure-composition claim may be projected as PolicyOS authority for the
> current release path under any model established in the pinned repository. A number becomes
> eligible only after a declared secret/channel/support or prior/gain model, locally valid measures,
> applicable composition rule, prospectively enforced custody, selection-valid local validity where
> adaptation occurs, canonical owner and named protected consumer are independently established.
> Determinism alone is neither a proof of safety nor a reason numerical analysis is impossible.

The last sentence is the wave's sharpest correction and it was made **against** the research by its
own auditor. INT-R8 originally refused a number because the public projection is a deterministic
editorial transformation. Randomization is necessary for differential privacy, but not for every
numerical leakage framework — maximal-leakage, maximal-alpha, statistic-maximal, min-entropy and
generalized-gain quantitative-information-flow models value **deterministic** channels once a
secret, channel, support and gain model is supplied. Determinism was never the obstruction; the
missing premises are.

The refusal is therefore **premise-relative, not an impossibility theorem**. Stated the original way
it would have foreclosed a legitimate research direction — precisely the leak from authority band
into candidate band that §2 exists to prevent. Registers `NXR-02` dormant.

**`PV-K09` — Proof metadata belongs to the disclosure channel.**

> Public-proof metadata and topology are part of the governed disclosure channel. Key identifiers,
> credential or certificate paths, commitment identifiers, transparency-log positions, witness sets,
> proof-object sizes, linkage patterns and related auxiliary data may bind evidence, but they may not
> be treated as harmless by default or become oracles for protected record values. A governed proof
> candidate must include them in the declared reconstruction/channel analysis while preserving the
> proof/content authority boundary.

This is the wave's cross-seam finding, and neither task anticipated it: content can leak through the
**proof machinery itself**. INT-R8's audit constructed the join; INT-R8 recorded it as a content-side
channel without designing a mitigation; INT-R7 answers at requirement level at
`int-r7/public-verification-profile.md:622` (§18) by requiring privacy-safe addressing and
forbidding proof metadata from becoming an oracle. The obligation is established; no mitigation is.
Registers `NXR-01` dormant.

## 5. What this act refutes

Ratified as binding negatives. None is available for downstream reliance, and none may be
reintroduced without superseding this record.

1. `SignatureValid` means public `Verified`.
2. Timeless current revocation proves historical legitimacy.
3. Semantic parity means byte equality.
4. Determinism makes quantitative disclosure analysis impossible.
5. A solver status alone is durable offline proof.
6. Timeout, unsupported theory, empty consistency set or unproved approximation defaults to safe.
7. A link to the full record repairs a misleading visible summary.
8. Proof or projection can mint authority.
9. The public-export producer is absent — it exists; the proof, evaluator and production bridge do not.
10. A numerical confidence or disclosure ledger is needed now.
11. This wave creates a third constitutional outcome kind.
12. Proof-metadata leakage is solved.
13. A named CA, log operator, witness, custodian, archive, timestamp service or vendor is established by research.
14. Legal sufficiency in any jurisdiction is established.
15. Either first-public gate may open.

## 6. Current standing and three architect corrections

### 6.1 Standing

- **INT-R7 — `GO_WITH_REVISIONS`, closure gate met.** Controlling head
  `3883b45476aed138beface8c8ca817191c7e273e`. The audit required `R1`–`R15` executed **and
  independently verified**; the consolidation's bounded preflight supplied the missing independent
  check, closing blocking finding `INT-R7-RV-001` and reproducing the 47-pair semantic-displacement
  register by walking the artifacts rather than reading the closure ledger.
- **INT-R8 — `accepted_narrow_scope`, gate met.** Controlling head
  `286ade1057c9abb95bb1cf2c962479906f764667`, verified `CONFORMS` with 0 blocking, 0 material,
  0 minor and 8 commendation.

Across the wave, six independent registers hold **106** findings — 4 blocking, 32 material, 11
minor, 59 commendation. Every blocking finding is closed.

### 6.2 Correction 1 — `RFR-06` is `absent/unallocated`, and becomes `GY-GAP3`

The consolidation's repository register classifies the absent controlled release-family transcript
as **`contract_only`** and routes it to "GY-PA3 plus custody integration". Both are corrected here.

**The label.** `contract_only` presupposes a real admitted type or contract with no producer,
consumer or workflow. A complete search of `policy-engine/src` for `release_family`,
`release_transcript`, `disclosure_transcript` and `controlled_release` returns **zero files**. No
admitted contract exists; INT-R8 *proposes* one. The correct classification is
**`absent/unallocated`** — the same vocabulary discipline whose violation produced the single
blocking finding in each of this wave's two audits.

**The owner.** GY-PA3 is scoped in the GY plan as a **compression-loss ledger producer**, not a
release-history transcript carrying membership, chronology and current heads. Routing an unowned
capability to a lane that does not own it leaves it unowned. It is therefore registered as
**`GY-GAP3`** with a named owner: the **GY-N12 lane** for the append-only transcript primitive —
N12 already owns append-only epoch, currentness and reissue, which is the same shape — with **GY-PA3
as consumer**. No new owner is created (`INT-K05`, `P27`/`P28`).

**The consequence, stated plainly:** without `GY-GAP3`, **`PV-K07` is not issuable.** This act
ratifies a statement the repository cannot yet make. That is the honest position and it is recorded
rather than hidden.

### 6.3 Correction 2 — a dead citation in `RC-06`

The candidates file cites
`policy-engine/docs/research/policy-operations/int-r8/frozen-falsifier-suite.md:1020-1115` in support
of `RC-06`. That path does not exist: `frozen-falsifier-suite.md` is INT-R7's filename, and INT-R8's
suite is `falsifier-suite-and-integration-handoff.md` at 264 lines, so the range is impossible as
well. The substance is unaffected — the reconstruction dispositions are real. `PV-K06` above cites
the verified anchor `:145-149` instead.

### 6.4 Correction 3 — the seam holds *by construction*, and that is worth saying

The consolidation adjudicates the seam item by item and finds no unmatched item among the six
INT-R7 requests and the eighteen INT-R8 binding requirements. Eight of the eighteen are classified
`naming_difference`, satisfied because INT-R7 commits to binding **the complete semantic statement** —
so producibility is generic over whatever INT-R8 can express.

That reasoning is sound, and its consequence should be stated in one sentence rather than left
implicit across three documents:

> The seam cannot fail at the contract layer, because binding is generic. It can fail only
> **institutionally** — nobody competent owns materiality (`INST-04`) — or at the **candidate
> layer** — a concrete proof cannot bind these inputs without leaking (`PV-K09`).

"The seam holds" must therefore never be read as "the seam is safe."

### 6.5 The pinned artifacts are not edited

None of the seven consolidation files, the audit bundles, or the verification records is modified by
these corrections. They stand as delivered, at their pinned heads. Editing another agent's pinned
artifact to agree with a later fact destroys the evidence of what was known when — the precedent set
when INT-R9's `verified_pending` standing was superseded in the INT-wave act rather than in the
artifact that carried it.

## 7. Prices accepted

**No public `Verified` Boolean.** Every consumer that wanted one gets a vector. Under `PV-K01` that
is a more useful surface, not a degraded one — it tells a citizen *which* dimension failed.

**No numerical disclosure claim, and no path to one that this act opens.** `PV-K08` is a refusal
with a specified route out, not a wall.

**`PV-K07` is ratified but unissuable** until `GY-GAP3` closes. This is a new registered gap on the
path to a capability ratified in the same document.

**Both first-public gates stay closed.** DS12's four named research inputs — `INT-R1`, `INT-R9`,
`INT-R7`, `INT-R8` — are closeable **as research inputs**. That is not implementation readiness,
custody, institutional competence, or publication authority.

**Two research commissions are registered dormant**, both with explicit triggers, both off any
critical path:

- **`NXR-01`** — candidate-specific proof-metadata mitigation. Activates only when a concrete DS12
  proof candidate fails `PV-K09`. Designing it before a candidate exists would be speculative.
- **`NXR-02`** — model-specific numerical disclosure composition. Activates only after the architect
  names a protected product decision that no-number prefix discipline cannot serve.

**What is not a price:** no active research remains. Nine engineering items sit in existing lanes,
five institutional items need accountable actors and evidence that no code can supply, and five
decisions belong to the architect. Combined with the INT wave's result — the critical path to a
first governed *promotion* is `GY-GAP1` plus institutional facts — **research is now finished for
both first-milestone paths.**

## 8. The outcome vocabulary is unchanged — §8 is not activated

The INT-wave act's §8 recorded that the vocabulary of outcomes had gained two entries in three days
and instructed that a **third** warrants one consolidated constitutional amendment rather than a
third separate ruling.

**This wave produces no third element, and the count remains three.**

- Prefix discipline (`PV-K07`) is an application of the existing `INT-K06` — a binding procedural
  claim carrying no probability — to adaptive disclosure. New domain, same claim kind.
- `model_observation_inconsistent`, timeout, unsupported theory, incomplete history and unproved
  approximation are typed negative and non-establishment results under the existing `INT-K08`. They
  are not a new favorable claim kind.
- `lossy_but_safe` and `blocked_material_omission` are projection-only verifier dispositions, not a
  global status lattice.

The constitution is therefore not amended, and the §8 trigger stays armed for a genuine third
element.

## 9. What this does not ratify

No mechanism, algorithm, key suite, certificate policy, witness count, log operator, timestamp
service, archive, preservation format, wire representation, schema, enum, package, database table or
API. No status lattice — coverage, verification and loss outcomes feed the **existing** one. No
canonical owner, vendor, custodian or institutional appointment. No legal-sufficiency or
jurisdictional conclusion. No claim that a `CompressionLossReceipt` producer, public proof producer,
verifier, controlled transcript, GY-N12 currentness output or OPS-R14 replay capability exists. No
permission to publish, promote or open a gate. No assertion that proof-metadata leakage has been
mitigated. No general decidability or tractability claim — `PV-K06`'s executable class is
deliberately bounded.

## 10. Impact note (constitution §12 form)

- **Status lattice:** unchanged. `PV-K04`–`PV-K06` constrain what a projection may *carry*;
  `PV-K01`–`PV-K03` constrain what a proof may *mean*. No statement creates a status.
- **Authority boundaries:** narrowed, not reshaped. `PV-K01`, `PV-K03` and `PV-K08` remove issuance
  paths that were never implemented. No authority slot is added.
- **Replay behavior:** unchanged. `PV-K02` restates the append-only discipline already in force.
  Rule-version reference: this document's `created` date. Work closed before 2026-08-05 is
  interpreted under the prior, unratified standing; no closed task is reopened by this act.
- **Affected destinations:** the GY plan (`GY-GAP3`, a GY-N12 rider), the Atlas plan (DS12
  consumption constraints and research-input closure), and the Wave-2 backlog (completion ledger,
  two dormant Group-D rows). DS13, DS14 and GY-PA3 are named consumers in the routing map but are
  deliberately left unannotated until their contracts are nearer.
- **Failure-pattern register:** unchanged. `P35` and `P36` already cover this wave's analysis
  failures. The delivery failure is an execution rule, recorded in `AGENTS.md`, not a pattern — one
  occurrence does not meet the register's own recurrence bar.

## 11. Revisit conditions

Each statement carries its own supersession trigger, adopted from the candidates:

- a later architecture proves a smaller report is logically equivalent for every protected use,
  preserves every dimension's falsifier, and cannot turn a failed or unknown dimension into positive
  authority (`PV-K01`);
- a ratified currentness model preserves append-only history, all negative terminals and the same
  non-erasure semantics in a different representation (`PV-K02`);
- a ratified architecture reallocates semantic-content and proof responsibilities while preserving
  `S0-K05`, `S0-K07`, denied-use monotonicity and independent authority evidence (`PV-K03`);
- a validated parity relation proves equal or stronger anti-amplification and contestability
  protections while admitting a strictly broader safe candidate set (`PV-K04`);
- `INT-K02`, `INT-K06` or `INT-K08` change semantics, or an alternate representation preserves the
  identical basis, terminal or constitutive relation without exposing the omitted text (`PV-K05`);
- a reviewed decision procedure establishes a broader executable class with a proof that no newly
  admitted disposition can produce a false safe result (`PV-K06`);
- a ratified composition theorem supplies prospectively enforced local validity, selection-valid
  composition, canonical custody and a named consumer for a strictly stronger claim (`PV-K07`);
- a named product use establishes the complete model, local validity, composition theorem, canonical
  owner, custody and protected consumer, independently verified under `INT-K04`/`INT-K07` (`PV-K08`);
- a verified proof construction establishes that a class of metadata is information-theoretically or
  cryptographically independent of every protected predicate under the declared auxiliary-information
  and coalition model (`PV-K09`).

A demonstration that any refuted item in §5 is in fact available reopens this record immediately,
independently of the triggers above.
