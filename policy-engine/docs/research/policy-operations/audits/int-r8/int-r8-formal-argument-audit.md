---
title: "INT-R8 — Formal argument, loss boundary, and falsifier audit"
audit_id: INT-R8-INDEPENDENT-AUDIT
verified_commit: 90b372964d29a9e97605a6ef733ef03ffe7938d2
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
authoritative_for:
  - independent Pass III through Pass VI audit of INT-R8
  - mathematical adjudication of numeric refusal and prefix discipline
  - reconstruction-model decidability and threat-channel analysis
  - loss-boundary and falsifier-suite findings INT-R8-III-001 through INT-R8-VI-003
may_not_use_for:
  - adoption amendment or ratification of INT-R8
  - production implementation authorization
  - final wire schema package database serialization or API contract
  - canonical owner appointment
  - authority grant capability claim or benchmark passage
  - legal sufficiency compliance or institutional competence conclusion
  - permission to publish a governed record
  - automatic amendment of any plan or system-design decision
  - signature algorithm key policy or numeric disclosure-bound selection
research_only: true
---

# INT-R8 formal argument audit

## 1. Executive formal verdict

The work contains one genuinely strong theorem-shaped result and two overstatements that must be
separated from it.

**Strong result.** For a declared finite or symbolically decidable record model, a declared
Boolean safety family and the complete controlled release transcript, exact reconstruction is a
Boolean predicate. Checking every actual adaptive prefix is genuinely number-free; it is not a
budget with a hidden epsilon. The prefix-induction argument is valid.

**First overstatement.** A randomized mechanism is necessary for differential privacy, but not
for every numerical information-leakage framework. Deterministic channels can have maximal,
maximal-alpha, statistic-maximal, min-entropy or other quantitative-information-flow leakage
values once the secret/channel/gain model is supplied. INT-R8 correctly refuses a **current
canonical PolicyOS number**; it does not establish that determinism makes every defensible number
impossible.

**Second overstatement.** The general `C(T)` construction is mathematically definable but is not
shown to be decidable or tractable for arbitrary PolicyOS records, renderers, auxiliary knowledge
and channels. “Executable” is established only for a declared bounded model whose consistency
predicate terminates or whose conservative abstraction has a proved soundness direction.

These defects justify revision, not rejection. The no-number current standing survives after its
premises are narrowed.

## 2. Pass III — attack on the composition refusal

### 2.1 Premise-by-premise audit

| Stated premise for a numeric theorem | Repository state | Mathematical adjudication |
| --- | --- | --- |
| Defined adjacency relation over records | No canonical source contract names an INT-R8 adjacency relation. | Absent **in the repository**, not conceptually impossible. A future bounded record family could define one. |
| Randomized mechanism | Current public packet/projection path is curated and largely deterministic; no DP mechanism is established. | Required for a nontrivial DP guarantee, but not for every quantitative leakage measure. |
| Valid local guarantees | No source component emits a per-release INT-R8 privacy/leakage guarantee. | Genuinely absent and indispensable for composing any mechanism-specific local guarantee. |
| Prospective budget allocation | No named source owner allocates per-release disclosure parameters before release. | Genuinely absent for a budget claim. Post-hoc arithmetic would not satisfy `INT-K04`. |
| Canonical adaptive accountant | No owner reproduces the disclosure family, history-selected mechanisms, current heads and aggregate parameter. | Genuinely absent for a numerical adaptive-composition claim. |
| Declared secret/channel/gain/background model | INT-R8 proposes protected predicates and a consistency set, but no canonical probability/channel/gain model exists. | Genuinely absent for maximal-leakage or Bayesian/information-theoretic numbers. |

### 2.2 Is the refusal correct?

#### Correct conclusion

The repository cannot currently issue a justified numerical repeated-disclosure guarantee. A
number would have no canonical object, local producer, selection-valid guarantee, prospective
allocation, accountant or authority boundary. The audited work is right to reject:

- an epsilon-like value imported from differential privacy;
- a generic percentage “safe” score;
- a “remaining disclosure budget” inferred from prose; and
- a number whose heterogeneous harms—identity, confidential evidence, dissent, scope and
  authority distortion—have been collapsed without a declared model.

This is exactly the authority-band discipline required by `INT-K04` and `INT-K07`.

#### Over-strict argument

The statement that numerical composition needs a randomized mechanism is too broad. Primary
information-leakage literature supplies counterexamples:

- maximal leakage is a channel quantity and remains defined when the release channel is
  deterministic;
- maximal-alpha leakage has data-processing and sub-additivity properties that support a weak
  composition result under its own assumptions; and
- statistic maximal leakage has composition/post-processing properties and has been studied for
  deterministic release mechanisms.

None of those papers supplies a ready PolicyOS number. They require a declared secret, channel,
prior or support, gain/loss function and release family. They do establish that
“deterministic/editorial” is not an eliminating property by itself.

The defensible conclusion is therefore:

> No canonical numerical disclosure-composition claim is justified for the current PolicyOS
> release path under any model established in the repository.

The indefensible stronger conclusion is:

> A numerical disclosure framework cannot apply because the release is deterministic.

The first survives; the second must be removed.

### 2.3 Is prefix discipline a hidden budget?

Let `F` be the declared family of unauthorized protected predicates and semantic-loss rules, and
let `T_n` be the complete controlled transcript after `n` releases. Define:

```text
Safe_F(T_n) = true
```

iff every predicate/rule in `F` passes on the actual transcript prefix.

For exact reconstruction of a predicate `q`, one valid member test is:

```text
|q(C(T_n))| >= 2
```

where `q(C(T_n))` is the set of values taken by `q` over records consistent with the transcript.
The release is unsafe when that cardinality is 1.

That is a **Boolean property**, not an expenditure. It has no threshold chosen from a continuum,
no amount consumed and no “remaining” quantity. If `C(T_n)` and `q` are exactly decidable, prefix
discipline is genuinely number-free. `INT-K04` does not bite merely because a Boolean check is
repeated.

The same remains true if safety is expressed as a finite collection of exact SAT/SMT
non-uniqueness obligations. Solver resource limits can produce `unknown`, but `unknown` maps to
blocked rather than to a numerical approximation.

### 2.4 Where an implicit quantity can re-enter

The audited work allows practical checkers to use enumeration, symbolic solving or conservative
over-approximation. The following substitutions would reintroduce unowned quantities:

- a posterior-probability threshold for “inferable”;
- a classifier confidence threshold;
- a minimum consistency-set size larger than one without a declared theorem;
- a timeout treated as approximate safety;
- an abstraction whose false-negative rate is estimated rather than proved absent;
- a sampling-based search over candidate records; or
- a heuristic “materiality score.”

At that point the check is no longer the exact predicate proved in the research. The threshold,
estimator, calibration, error direction and composition semantics would need their own owner and
validity argument. INT-R8 notes `unknown -> blocked`, but it does not make this boundary explicit
enough to prevent an implementation from substituting a heuristic while retaining the theorem's
language.

### 2.5 Adaptivity under `INT-K07`

Suppose release `Y_n` is chosen after observing `T_{n-1}`. Prefix discipline evaluates:

```text
Safe_F(T_{n-1} || Y_n)
```

on the **actual history-selected candidate**, not on a preselected marginal release. If every
accepted candidate satisfies the same fixed, version-bound Boolean family `F`, induction gives:

```text
Safe_F(T_0)
and for every accepted n: Safe_F(T_n)
therefore every accepted actual prefix satisfies F.
```

No independence or non-adaptive selection assumption is used. The adaptivity is handled rather
than inherited silently. This is a substantive strength.

The guarantee is still narrow:

- it says nothing about predicates outside `F`;
- it says nothing about unknown future auxiliary information;
- it says nothing about releases not present in the controlled transcript; and
- a change to `F`, the record model or the observer model creates a new rule version and must not
  retroactively manufacture passage.

### 2.6 Controlled versus universal transcript

“Complete actual transcript” is overbroad unless scoped. A PolicyOS custody owner can reproduce
only a declared release universe, for example:

- server responses and registered exports;
- version/currentness history;
- generated deep links;
- registered screenshots/print artifacts;
- known caches and delivery metadata under its control; and
- imported external copies that have been observed and admitted to the transcript.

It cannot prove completeness over:

- private screenshots copied by recipients;
- browser/history caches outside administrative control;
- third-party search-engine snippets not observed by the system;
- litigation or FOI disclosures made through another institution;
- covert insider exfiltration; or
- unknown auxiliary datasets.

The research acknowledges unknown auxiliary information but still uses unqualified “complete
actual transcript” and “every actual prefix.” The claim must name the controlled release family
and carry a completeness disposition for external channels. Otherwise reproducible membership
is aspirational.

## 3. Pass III findings

### INT-R8-III-001 — commendation — refusing a current canonical number is correct

The source and architecture have none of the local guarantees or accounting custody needed for a
numerical authority claim. The refusal is a positive result, not missing work.

### INT-R8-III-002 — material — randomization is incorrectly treated as necessary for every numerical framework

**Evidence:** audited primary report `int-r8-compression-loss-and-disclosure.md:30-48,154-220`;
`reconstruction-composition-and-threat-model.md:25-75`; MAX-LEAKAGE-2020 and maximal-alpha
leakage primary literature.

Narrow the claim to absence of a justified **current canonical** number. Add deterministic
quantitative-information-flow models to the comparative survey and state why their secret,
channel, gain and composition premises are not established here.

### INT-R8-III-003 — commendation — the exact singleton reconstruction test is genuinely number-free

For a finite/decidable consistency model, “at least two protected values remain possible” is a
Boolean predicate. No implicit budget is needed.

### INT-R8-III-004 — material — heuristic or approximate reconstruction would introduce unowned validity quantities

The research names over-approximation and solver approaches but does not bind termination,
soundness direction or the prohibition on calibrated/thresholded substitutes. State that only an
exact decision or a proved conservative abstraction inherits the no-number result; everything
else returns `unknown` or requires separate research.

### INT-R8-III-005 — commendation — actual-prefix checking correctly handles adaptive release choice

A fixed versioned predicate family evaluated on every actual history-selected candidate needs no
selection-valid numerical theorem. The induction is valid and `INT-K07` is not silently bypassed.

### INT-R8-III-006 — material — transcript completeness is not scoped to a reproducible controlled release universe

Replace universal “complete actual transcript” wording with a declared release-family boundary,
external-channel completeness disposition and fail-closed treatment of missing controlled
history. Unknown uncontrolled disclosures cannot be claimed reproduced.

## 4. Pass IV — consistency-set model

### 4.1 Well-definedness

The mathematical definitions are conditionally correct. Given:

- a nonempty model class `R`;
- a fully specified release observation relation;
- an observed transcript `t`; and
- a total predicate `q` on the model class,

```text
C(t) = {r in R : Release(r) is observationally consistent with t}
```

is a set, and exact reconstruction is correctly characterized by:

```text
|{q(r) : r in C(t)}| = 1.
```

The strict cross-view definition is also correct:

- for each single available view `a`, at least two `q` values remain possible; and
- for an available coalition `K`, exactly one `q` value remains possible.

That captures synergy rather than merely duplicate leakage.

### 4.2 Missing model obligations

The research does not establish, in general, that:

1. `R` is finite or recursively enumerable;
2. `C(t)` is nonempty;
3. observational consistency is decidable;
4. rendering, timestamps, caches and third-party channels have computable semantics;
5. the auxiliary-information closure is representable;
6. the relevant `q` family is finite;
7. the candidate enumeration terminates; or
8. the symbolic theory lies in a decidable fragment.

An empty `C(t)` is especially important. Vacuous set cardinality is not “safe”; it means the
model and observed transcript are inconsistent. The required outcome should be a typed model or
inventory failure, not `lossy_but_safe`.

### 4.3 Scale and tractability

The proposed executable check enumerates candidate full records or runs symbolic constraints.
For realistic policy records, possible combinations include claims, evidence graphs, hidden
values, revisions, renderers, roles and auxiliary facts. Naive enumeration is exponential or
infinite.

The research mentions SAT/SMT and conservative over-approximation, which is the right direction,
but does not state:

- the finite abstraction boundary;
- solver theory and termination expectation;
- witness requirements for “two values remain possible”;
- proof/certificate requirements for `reconstructed`;
- how an over-approximation may create false blocks but never false safe results; or
- resource-exhaustion behavior beyond generic `unknown`.

Therefore the exact model is executable for bounded fixtures, not yet established as an
operational general verifier.

### 4.4 Channel enumeration — strengths and omissions

The audited enumeration is unusually broad. It includes visible content, omissions, diffs,
hashes, order, pagination, timestamps, cadence, provenance joins, URLs, screenshots, print,
accessibility tree, hidden DOM, metadata, source maps, headers, cache keys, lengths, logs,
analytics, referrers, errors and currentness.

At least five material channel classes are missing or not explicit:

1. **Locale and translation channels.** One language can retain a caveat while a fallback,
   translation memory or machine-generated locale drops it; comparing languages can reveal
   protected wording or status.
2. **Notification and syndication channels.** Email, push, webhook, RSS/Atom, social-card/Open
   Graph previews and chat integrations can publish a shorter object than the page/export.
3. **Network/compression oracles.** TLS record count, packet size, content-encoding ratio, range
   responses and conditional-request behavior can distinguish low-entropy hidden states even when
   nominal content length is normalized.
4. **Discovery/index channels.** Sitemap entries, search/autocomplete suggestions, search-engine
   snippets, result counts and cache invalidation can reveal the existence/category of a hidden
   record.
5. **Proof metadata channels.** Signature key identifier, certificate chain, transparency-log
   position, witness set or proof-object size can join audiences or identify a protected issuer,
   reviewer or revision.

No finite list can prove attack completeness. The required control is a registered channel
family with an `unknown_channel`/out-of-model disposition, not a claim that the prose list is
complete.

## 5. Pass IV findings

### INT-R8-IV-001 — commendation — `C(T)` and strict cross-view reconstruction are correctly stated

The set-based definitions capture exact inference and coalition synergy without pretending a
probability model exists.

### INT-R8-IV-002 — material — general decidability and realistic-scale executability are not established

The work moves from a mathematical set definition to “executable” without proving finite,
decidable or soundly abstracted inputs. Bound the claim to finite/symbolic fixtures and require
empty-set, timeout and abstraction outcomes explicitly.

### INT-R8-IV-003 — material — the threat-channel family is not complete enough for its own breadth claim

Locale/translation, notification/syndication, network-compression, discovery/index and proof
metadata channels are absent. Add them as declared families and state that the family is open,
versioned and capable of an out-of-model block.

### INT-R8-IV-004 — commendation — the existing channel model is far stronger than body-text-only review

Deep links, hidden metadata, screenshot/print, accessibility tree, hashes, timing and provenance
joins are all treated as first-class observations. This should survive consolidation.

## 6. Pass V — loss boundary and receipt

### 6.1 Is the decision procedure total?

The two-valued result surface is total only **after** every sub-check terminates with a valid
input. The research correctly maps missing inventory, unknown materiality and unavailable inputs
to blocked. It does not fully resolve three predicate families:

- what makes a limitation “material” for a declared use;
- what counts as a “faithful condensation”; and
- which procedural history steps are constitutive/load-bearing.

Those are not incidental prose judgments. They decide whether a candidate is safe. The work
places them in a governed semantic inventory/predicate family, but leaves the competent basis,
selection procedure, versioning and falsification standard open. That is an honest open
institutional question, but it means the decision procedure is a contract skeleton rather than
a self-sufficient algorithm.

### 6.2 Calibration anchors

#### Bare `delta`

This anchor is exact and correctly absolute. Removing the declared obligation set, maintained
assumptions or relative-basis rider changes the proposition. No materiality override or full
record link can restore green. `INT-K02` is applied without an exception path.

#### Hidden refusal/void/dispute/no-attempt/exhaustion

This anchor is also exact. Replacing a completed negative with absence changes outcome and can
launder success pressure. The suite requires the same red result for all named terminals.

#### Constitutive step removed from no-number custody

Direction is correct but the frontier is underdefined. The full record may contain dozens of
events. The research names prospectivity, sealing, firstness, substitutions, adjudication,
dissent, negatives and correction, but does not define:

- whether every member is mandatory for every claim subtype;
- how an event is linked to the proposition it constitutes;
- when two events may be faithfully condensed into one;
- who or what classifies an omitted event as non-constitutive; or
- the mutation that proves the classifier is sensitive to one decisive step while ignoring
  redundant event prose.

Without a versioned constitutive-step relation, `compression_procedural_step_missing` is a
reviewer judgment, not a checkable invariant.

### 6.3 Reuse-point audit

| Named reuse point | Exists | Used as claimed | Audit result |
| --- | --- | --- | --- |
| `omission_manifest` | Yes | Base projection emits it; public export checks omitted claim IDs against it. | Genuine reuse. |
| `redaction_summary` | Yes | Base projection emits it; public export emits canonical scanner reasons. | Genuine base, but reason coverage is narrower than INT-R8's semantic classes. |
| `projection_gaps` | Yes | Base projection emits and consumer contracts inspect relevant truth/gaps. | Genuine reuse. |
| `contested_records` | Yes | Base projection emits them and consumer contract checks contested IDs. | Genuine reuse. |
| `recourse_pointer` | Yes | Base projection derives it and public export validates publication recourse. | Genuine reuse. |
| `deficit_register` | Yes | Base projection emits it; S9 adaptation preserves relevant deficits. | Genuine reuse. |
| `audit_refs` | Yes | Base projection emits them; public export enriches/preserves them. | Genuine reuse. |
| `may_not_use_for` / `may_not_be_used_for` | Yes | Live across 106 source Python files; projection/public export enforce denied uses. | Genuine reuse and correct monotonicity target. |
| S9-S14 checks | Yes | Public export invokes the verifier family and fails on red status. | Genuine reuse. |
| projection-only authority boundary | Yes | Base projection assertion and public-export official-use limits enforce it. | Genuine reuse. |

The receipt is therefore not merely a parallel structure wearing familiar names. Its intended
inputs and consumer are anchored in existing code.

### 6.4 Remaining duplication risk: canonical reason vocabulary

Current public-export scanner reasons cover email, keyed secret and general secret/PII. INT-R8
requires reasons for material limitation removal, protected dissent detail, confidential
identity, redundant citation, audience inapplicability, policy basis and more.

The research says existing scanner reasons are reused “where applicable” and prohibits a second
scanner vocabulary. It does not settle whether non-scanner omission reasons extend the existing
`omission_manifest` reason owner, a redaction-policy owner, or a new receipt-local vocabulary.
This is the precise P27/P28 seam where a future implementation could create:

- scanner reasons;
- projection omission reasons; and
- receipt materiality reasons

as three partially overlapping registries. The research must state one canonical relation and
an explicit `not_scanner_reason` boundary without appointing an institutional owner.

### 6.5 Minor anchor overstatement: “limitations”

The base projection has blocker/limitation codes, projection gaps, deficit rows and
surface-specific limitation fields. It does not expose one universal top-level `limitations`
collection in every base projection. Some S10-S14 enrichments add such a list. The audited reuse
language should name the concrete existing carriers rather than imply a universal field.

## 7. Pass V findings

### INT-R8-V-001 — commendation — bare delta and negative-terminal anchors are categorical and correct

They are not delegated to an editor, probability or generic materiality score. This is the
clearest part of the loss boundary.

### INT-R8-V-002 — material — “constitutive/load-bearing/material” semantics are not operationalized enough to be checkable

The third calibration anchor and general parity test require a versioned relation from source
items to truth, scope, authority, use, contestability and procedure. State the required evidence
for that relation and a decisive-step mutation criterion; otherwise the key verdict remains
institutional judgment wearing a deterministic code.

### INT-R8-V-003 — material — canonical reason reuse is not reconciled across scanner, projection and receipt semantics

The research prohibits a second vocabulary but does not specify the single canonical relation
or how non-scanner semantic omissions attach to it. Tighten the ownership boundary and require a
complete cross-registry duplication census before implementation planning.

### INT-R8-V-004 — minor — the report overstates a universal existing `limitations` field

Replace generic “existing limitations” with the actual carriers: closeout limitation codes,
projection gaps, deficit rows and surface-specific limitation fields.

### INT-R8-V-005 — commendation — the receipt genuinely extends existing projection/public-export machinery

All named core reuse points exist, and the receipt outcomes are explicitly local verdicts rather
than a new global status lattice or authority source.

## 8. Pass VI — falsifier-suite audit

### 8.1 Executability standard

A fixture is executable by an equality harness only when it identifies:

- one baseline fixture;
- one mutation or one explicitly parameterized mutation family;
- one exact expected loss outcome;
- an exact required issue-code set or exact per-parameter code;
- exact affected/retained/dropped identifiers; and
- exact prerequisite local and transcript statuses.

“Red,” “A or B,” “and/or,” and several semantically distinct mutations under one ID are useful
human specifications but not frozen machine fixtures.

### 8.2 Case-by-case audit

| ID | Specification verdict | Reason |
| --- | --- | --- |
| F01 | `not_exact_as_written` | One mutation permits either of two issue codes. Split truth-condition change from retained-limitation absence or define precedence. |
| F02 | `parameterizable_after_expansion` | Three independent basis removals share one exact outcome/code; enumerate three fixtures. Strong semantic target. |
| F03 | `parameterizable_after_expansion` | Five terminal classes plus several hiding transformations are bundled. Exact code is stable, but cases must be explicit. |
| F04 | `executable_multistage` | Local PUBLIC, local REVIEWER and joint statuses are exact. Strongest formal falsifier. |
| F05 | `not_exact_as_written` | Four mutations and a one-of-four code set are bundled without mutation-to-code mapping. |
| F06 | `not_exact_as_written` | Drops firstness **or** substitution and expects `A and/or B`. Split by missing constitutive step and define precedence. |
| F07 | `parameterizable` | Three denied-use mutations share one exact code and property. |
| F08 | `not_exact_as_written` | Expected code is one of two; dissent omission and false-consensus wording need separate cases. |
| F09 | `executable_after_fixture_binding` | Exact code; candidate-universe/effective-diversity inputs need fixed IDs. |
| F10 | `not_exact_as_written` | Expected value is only “Red”; no exact issue code or affected IDs. |
| F11 | `parameterizable` | Four diff-channel mutations share one exact code. |
| F12 | `executable_after_dictionary_fixture` | Exact code and attack; finite dictionary must be committed in the fixture. |
| F13 | `executable_after_model_binding` | Exact code; missing row/category inference constraints need fixed values. |
| F14 | `not_exact_as_written` | Two opposite timestamp tests are placed under one ID. They must be separate fixtures. |
| F15 | `executable_after_fixture_binding` | Exact code; audience coalition and join identifiers must be fixed. |
| F16 | `executable_after_fixture_binding` | Exact code; protected value and safe manifest baseline must be fixed. |
| F17 | `parameterizable` | Viewport/hover/collapse/print variants can share exact code if rendered artifacts are enumerated. |
| F18 | `parameterizable` | Export formats and metadata attacks can share exact code, but each output byte fixture must be named. |
| F19 | `executable` | One deep-link mutation and exact code. Strong repository-grounded case. |
| F20 | `not_exact_as_written` | Screenshot, export and cache are distinct channels bundled into one mutation. |
| F21 | `not_exact_as_written` | Timeout, missing rule, mapping and inventory failures map to one of two codes without precedence. |
| F22 | `not_exact_as_written` | Requires an existing authority-gate failure plus a new code but does not state exact combined code set. |
| F23 | `not_exact_as_written` | Expected `prefix_not_checked` and/or reconstruction; local-only check and joint leak should be split. |
| F24 | `executable` | One history-rewrite mutation and exact code. |
| F25 | `executable_as_family` | Several unauthorized scalar labels share one exact code and premise set. |
| G01 | `executable_after_reason_binding` | Exact safe outcome; canonical duplicate reason and retained relation must be fixed. |
| G02 | `not_exact_without_materiality_fixture` | “Identity is non-material” is a required source predicate, not a self-proving premise. |
| G03 | `executable_after_threshold_fixture` | Exact safe outcome once source cells, prior transcript and local rule are fixed. |
| G04 | `not_exact_without_constitutive_relation` | Safe condensation depends on the underdefined constitutive-step relation. |
| G05 | `needs_split` | Adding a denied use and returning insufficient are different controls under one ID. |

The suite is a high-quality semantic test plan, but not an executable frozen fixture set as
written. This is the same defect class recorded as `INT-R7-V-001` in the parallel INT-R7 audit;
that finding is used only as a comparison, not as authority for this result.

### 8.3 Property invariants

P1, P2, P4, P7, P8, P9, P11 and P12 are crisp once canonical IDs and authority types are bound.
P3 and P6 depend on the governed materiality/decision-predicate package. P10 depends on the
bounded decidable reconstruction model. Their conditionality should be explicit in the fixture
manifest.

The green controls are essential. They prevent a reject-all implementation and demonstrate that
loss can be safe without claiming the full record was preserved byte-for-byte.

### 8.4 Constructed attacks not caught by F01-F25

#### Attack A — cross-locale qualifier split

- Ukrainian PUBLIC text preserves “only for municipalities with complete 2025 reporting.”
- English fallback drops the condition.
- Neither same-locale screenshot mutation nor current parity cases compare locale variants.
- An English recipient receives a broadened claim; comparing locale hashes can also reveal that a
  hidden section exists.

Expected new family: locale/translation semantic parity and coalition transcript.

#### Attack B — notification/webhook shadow publication

- The page and JSON export pass.
- An email subject, push notification, webhook payload or Open Graph preview says “approved” and
  omits dispute/currentness.
- The notification is copied and indexed without the page caveat.

F18 covers document/export metadata, not independent notification/syndication renderers.

#### Attack C — compression/TLS length oracle

- Visible body and declared content length are padded.
- Brotli/gzip compressed length or TLS record count differs for two low-entropy hidden statuses.
- Repeated conditional/range requests reveal the state.

F12 covers explicit hashes and F13/F14 cover ordering/timing, but no network-compression oracle.

#### Attack D — discovery-index existence leak

- A protected dissent record is not in PUBLIC content.
- Sitemap, autocomplete, search-result count or cache-invalidation timing exposes the hidden
  record's existence/category.

No F01-F25 case exercises search/index infrastructure.

#### Attack E — proof-metadata join

- PUBLIC and EXPERT content use unlinkable projection references.
- Both proofs carry the same key ID, certificate-chain leaf, transparency-log index or unusual
  proof size, joining the views to a protected reviewer/revision.

F15 covers provenance IDs but not cryptographic proof metadata. This is also an INT-R7 seam
requirement.

At least A-C are required by the commission's “construct three” instruction; D-E show that the
channel registry must remain open rather than claiming completeness.

## 9. Pass VI findings

### INT-R8-VI-001 — material — the 30-case suite is not equality-harness executable as written

At least F01, F05, F06, F08, F10, F14, F20, F21, F22, F23, G02, G04 and G05 use disjunction,
multiple semantic mutations or unbound judgment premises. Split them into atomic fixture rows,
define issue-code precedence and bind exact expected sets.

### INT-R8-VI-002 — commendation — the suite contains unusually strong red and green controls

F04, F12, F19, F24 and F25 attack the central model rather than a keyword probe. G01-G05 prevent
reject-all passage. The rendered-artifact requirement in F17/F18 and local-before-joint proof in
F04 should survive unchanged.

### INT-R8-VI-003 — material — five realistic channel attacks have no falsifier

Add atomic red cases for locale/translation, notification/syndication, network-compression,
discovery/index and proof-metadata channels, or mark those channels explicitly out of model and
block claims that purport to cover them.

## 10. Formal conclusion

The mathematical core supports `accepted_narrow_scope` after revision:

- exact reconstruction and strict coalition synergy are correctly defined;
- exact prefix discipline is genuinely no-number and handles adaptive release choice;
- refusal of a current canonical scalar is justified; and
- the loss boundary correctly treats conditional numbers and negative outcomes as semantic
  content.

It does **not** yet support:

- a universal claim that deterministic publication precludes numerical leakage analysis;
- a general executable reconstruction verifier over arbitrary records/channels;
- a mechanically total materiality/constitutive-step classifier; or
- a claim that F01-F25/G01-G05 are frozen machine fixtures as written.

Those are repairable research-contract defects rather than a reason to discard the core.