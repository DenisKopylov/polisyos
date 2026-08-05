---
title: "INT-R7 / INT-R8 — Authority-band ratification candidates"
status: delivered
kind: research-ratification-candidates
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r7-r8-consolidation
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
int_r7_controlling_head: 3883b45476aed138beface8c8ca817191c7e273e
int_r8_controlling_head: 286ade1057c9abb95bb1cf2c962479906f764667
inspection_date: 2026-08-05
research_only: true
authoritative_for:
  - proposed authority-band statements from the pinned INT-R7 and INT-R8 wave
  - band-bound limitation and supersession analysis for each proposed statement
  - explicit propositions considered and deliberately not proposed
may_not_use_for:
  - treating any candidate below as ratified before an architect acts
  - production implementation authorization
  - candidate-band algorithm mechanism vendor format schema enum API or service selection
  - owner operator custodian witness log archive timestamp service or certificate-authority appointment
  - legal sufficiency or jurisdictional compliance conclusion
  - permission to publish or open either first-public gate
  - numerical disclosure privacy leakage confidence or safety bound
  - automatic amendment of a plan backlog system-design decision failure-pattern register or AGENTS.md
execution_environment: connected_exact_ref_only_due_to_unavailable_ordinary_github_dns
---

# INT-R7 / INT-R8 ratification candidates

## 1. Lens and disposition

The binding lens is finding-level architecture from `stage0-custody-kernel-ratification.md:46-88`:

> Does the statement bind only the authority band, or does it leak into the candidate band?

All nine candidates below constrain only what may be issued, represented, relied upon, or promoted as governed authority. They do not forbid candidate computations, experimental cryptographic constructions, editorial exploration, private diagnostics, or research evaluation. Every candidate therefore qualifies for architect consideration under the inherited lens.

The candidates are deliberately construction-neutral. They do not form a wire contract or a status lattice. They may be ratified separately, although RC-01 through RC-03 and RC-04 through RC-09 are semantically related.

## 2. Candidate register

### RC-01 — Public verification is a separately reportable vector

**Precise wording**

> A mathematically valid signature may support issuer-issuance authenticity but may not by itself be represented as an unqualified public `Verified` result. Governed public verification reports issuer issuance, projection faithfulness, public-history establishment, durable verifiability at the verification time, current authority at the query cutoff, status-snapshot selection, and public evidence obtainability as separately falsifiable dimensions. Any composite positive is bounded to the exact evidence package and cutoff it evaluates.

**Band bound:** **authority band only.** Candidate-band code may calculate signature validity or prototype aggregate displays. The statement constrains only governed issuance, presentation and reliance.

**Supporting sources**

- `policy-engine/docs/research/policy-operations/int-r7-public-verification-lifecycle.md:35-69`
- `policy-engine/docs/research/policy-operations/int-r7/threat-model-and-verification-predicates.md:793-824,966-1024`
- `policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md:26-55`
- findings `S0-K07`, `S0-K12`, `INT-K08`

**Known limitation:** the research does not select a public result vocabulary, UI grammar, enum, schema, serialization, signer, verifier, or evidence package.

**Constrains:** any public or machine claim that a record is verified; DS12's forged-packet negative control; later currentness and history presentation.

**Does not decide:** whether a candidate implementation uses one display card or several; how dimensions are encoded; which cryptographic suite or verifier is used.

**Supersession trigger:** a later independently verified architecture demonstrates that a smaller report is logically equivalent for every protected use, preserves every dimension's falsifier, and cannot turn a failed/unknown dimension into positive authority.

### RC-02 — Historical authenticity and current authority are non-erasing and distinct

**Precise wording**

> Historical authenticity and current authority are distinct governed propositions. Authenticated withdrawal, revocation, supersession, loss of mandate, or stale currentness may make current authority false without rewriting or erasing a historically authentic record. Conversely, historical authenticity never establishes current authority. A current positive must bind an authenticated currentness/status snapshot and its `as_of` cutoff; absent or indeterminate currentness is not a current positive.

**Band bound:** **authority band only.** Candidate analysis may inspect old records and alternate timelines. The statement constrains only the meaning and presentation of governed history/currentness results.

**Supporting sources**

- `policy-engine/docs/research/policy-operations/int-r7-public-verification-lifecycle.md:154-180,397-445`
- `policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md:360-399`
- `policy-engine/docs/research/policy-operations/int-r7/threat-model-and-verification-predicates.md:966-1024`
- findings `S0-K08`, `INT-K08`

**Known limitation:** GY-N12 is the sole intended epoch/currentness owner and remains contract-only/planned; institutional withdrawal and succession rules are not supplied by this wave.

**Constrains:** current/superseded/withdrawn rendering, historical replay, correction, preservation and status-snapshot use.

**Does not decide:** currentness event schema, expiry policy, legal effect of withdrawal, organization succession, retention duration, or UI styling.

**Supersession trigger:** an independently ratified currentness model proves a different representation preserves append-only history, all negative terminals and the same non-erasure semantics without minting authority.

### RC-03 — Proof binds content semantics but cannot choose content or mint authority

**Precise wording**

> A public proof may bind source and projection identities, retained semantic items, typed omissions and outcomes, declared uses and denied uses, model and rule versions, transcript state, verifier disposition, authority evidence and successor/currentness references. The proof layer must not decide which content is retained, declare an omission non-material, broaden permitted use, upgrade projection-only authority, or turn cryptographic possession, projection, transport, preservation or observation into institutional authority.

**Band bound:** **authority band only.** Candidate proofs and content transformations remain free to explore any construction; the restriction applies when their result is represented or relied on as governed authority.

**Supporting sources**

- `policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md:103-119,649-670`
- `policy-engine/docs/research/policy-operations/int-r7/repository-integration-and-dependencies.md:206-220,401-414`
- `policy-engine/docs/research/policy-operations/int-r8/semantic-contract-and-loss-boundary.md:429-459`
- `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:89-114`, findings `S0-K05`, `S0-K07`

**Known limitation:** the seam is a semantic contract, not a delivered proof producer, receipt producer, verifier, bridge, owner assignment or institutional authority package.

**Constrains:** all proof/content integrations, receipt binding, public projection, preservation and later machine verification.

**Does not decide:** hash, commitment, signature, certificate, timestamp, log, witness, package, storage or transport construction; materiality rules; retained content.

**Supersession trigger:** a later ratified architecture changes the allocation of semantic-content and proof responsibilities while preserving `S0-K05`, `S0-K07`, denied-use monotonicity and independent authority evidence.

### RC-04 — Semantic parity is use-relative conservative protected-query parity

**Precise wording**

> Governed semantic parity between a source record and a shorter public object is not byte equality. It is use-relative conservative protected-query parity: surfaced claims remain source-resolvable; claim type, basis, scope, assumptions, material conditions and limitations are preserved; governed decisions are equal or more conservative; denied uses do not shrink; active negative terminals, dissent, contest, recourse and currentness remain visible; every dropped item has a governed reason/effect relation; and unresolved inputs block. Projection may reduce detail but may not amplify truth, certainty, authority, currency or permission.

**Band bound:** **authority band only.** Candidate editors and models may generate any summary. The statement constrains only a summary admitted as a governed public projection.

**Supporting sources**

- `policy-engine/docs/research/policy-operations/int-r8-compression-loss-and-disclosure.md:147-199`
- `policy-engine/docs/research/policy-operations/int-r8/semantic-contract-and-loss-boundary.md:270-317`
- `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:89-114`, finding `S0-K07`
- `policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:96-131`, findings `INT-K02`, `INT-K08`

**Known limitation:** materiality is use-, basis- and institution-dependent. The research supplies the relation shape and categorical anchors, not every competent rule or jurisdictional predicate package.

**Constrains:** public summaries, redactions, compression receipts, screenshot/print/export semantics, cross-audience projections and denied-use handling.

**Does not decide:** editorial wording, audience layout, accessibility implementation, source-specific confidentiality decision, or legal disclosure rule.

**Supersession trigger:** a later independently validated parity relation proves equal or stronger anti-amplification and contestability protections for all governed uses while allowing a strictly broader safe candidate set.

### RC-05 — Three categorical omissions always block the governed claim

**Precise wording**

> For the governed claim classes already ratified, the following omissions are categorically material and may not be overridden by editorial judgment: (1) a `delta` without its declared obligation set, maintained assumptions and visible relative-basis rider; (2) a hidden refusal, void, dispute, terminal no-attempt, exhaustion or equivalent completed negative; and (3) a no-number custody claim missing a unique constitutive event or required order relation. Any such omission returns a blocking result rather than a more favorable compressed claim.

**Band bound:** **authority band only.** Candidate summaries may be generated and studied despite these omissions; they may not be promoted as preserving the governed claim.

**Supporting sources**

- `policy-engine/docs/research/policy-operations/int-r8/semantic-contract-and-loss-boundary.md:318-397`
- `policy-engine/docs/research/policy-operations/int-r8-compression-loss-and-disclosure.md:166-199`
- `policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:96-131,185-234`, findings `INT-K02`, `INT-K06`, `INT-K08`

**Known limitation:** this candidate does not enumerate every material omission. It establishes only three categorical anchors; other items still require the governed materiality relation.

**Constrains:** compression/materiality adjudication and public projection for `delta`, negative terminal and no-number custody claims.

**Does not decide:** the substantive correctness of a `delta`, refusal or procedure; which additional items are material under a competent rule; safe public granularity for protected details.

**Supersession trigger:** a later ratification changes the semantics of `INT-K02`, `INT-K06` or `INT-K08`, or proves an alternate representation preserves the identical basis, terminal or constitutive relation without exposing the omitted text.

### RC-06 — Reconstruction safety requires exact or proved-conservative evaluation

**Precise wording**

> A governed non-reconstruction or semantic-safety result may rely only on exact evaluation over a declared finite/enumerable or declared-decidable model, or on an abstraction with a proved no-false-safe direction for the exact obligation it discharges. Reconstruction, model/observation inconsistency, empty consistency set, timeout, unsupported theory, incomplete controlled history, out-of-model channel, heuristic, sampling result or unproved approximation cannot inherit a safe verdict and must return a typed blocking or not-established result.

**Band bound:** **authority band only.** Candidate-band heuristics, approximations and experiments remain permitted. They simply do not carry governed safety authority without a proved direction and exact scope.

**Supporting sources**

- `policy-engine/docs/research/policy-operations/int-r8-compression-loss-and-disclosure.md:201-247`
- `policy-engine/docs/research/policy-operations/int-r8/reconstruction-composition-and-threat-model.md:109-205`
- `policy-engine/docs/research/policy-operations/int-r8/frozen-falsifier-suite.md:1020-1115`
- finding `INT-K08`

**Known limitation:** the wave does not establish general decidability, tractability, a solver, an abstraction family, a model owner, or operational transcript completeness.

**Constrains:** any public assertion of non-reconstruction or material-loss safety and any receipt that consumes solver/evaluator output.

**Does not decide:** solver implementation, resource limits, protected predicate selection, coalition model, background-information model or channel inventory.

**Supersession trigger:** an independently reviewed decision procedure establishes a broader executable class with a proof that no newly admitted disposition can produce a false safe result.

### RC-07 — Prefix discipline is the accepted no-number composition claim

**Precise wording**

> For a versioned declared release family under custody, a governed system may issue a Boolean procedural claim that each controlled candidate disclosure prefix was evaluated prospectively against the declared semantic-loss and exact-or-proved-conservative reconstruction obligations; membership, chronology, current heads, model versions, inputs and dispositions are reproducible; and deletion, reclassification or post-hoc narrowing of controlled history cannot manufacture a pass. The claim carries no numerical privacy, risk, performance, compliance or universal-channel guarantee.

**Band bound:** **authority band only.** Candidate-band release simulation and adaptive exploration remain unrestricted. The statement constrains only the authority attached to an admitted release history.

**Supporting sources**

- `policy-engine/docs/research/policy-operations/int-r8-compression-loss-and-disclosure.md:45-85,248-315`
- `policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:185-234`, finding `INT-K06`
- findings `INT-K04`, `INT-K07`, `INT-K08`

**Known limitation:** the declared release-family registry is explicitly open; unknown and uncontrolled channels remain limitations, not magically covered history. No custody producer or chronology verifier is delivered.

**Constrains:** the strongest no-number claim a controlled release sequence may issue; prospective checking; correction and transcript non-rewrite.

**Does not decide:** a numerical budget, secret model, channel list, release schedule, custody owner, storage representation, user consent, legal compliance or attack completeness.

**Supersession trigger:** a later ratified composition theorem supplies prospectively enforced local validity, selection-valid composition, canonical custody and a named consumer for a strictly stronger claim without weakening this procedural guarantee.

### RC-08 — No canonical numerical disclosure-composition claim is currently justified

**Precise wording**

> No canonical numerical disclosure-composition claim may be projected as PolicyOS authority for the current release path under any model established in the pinned repository. A number becomes eligible only after a declared secret/channel/support or prior/gain model, locally valid measures, applicable composition rule, prospectively enforced custody, selection-valid local validity where adaptation occurs, canonical owner and named protected consumer are independently established. Determinism alone is neither a proof of safety nor a reason numerical analysis is impossible.

**Band bound:** **authority band only.** Research and candidate-band diagnostics may compute any leakage, information-flow or privacy quantity under explicit assumptions. The prohibition is on canonical governed issuance without its premises.

**Supporting sources**

- `policy-engine/docs/research/policy-operations/int-r8-compression-loss-and-disclosure.md:45-78,102-146`
- `policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:132-184`, findings `INT-K04`, `INT-K05`, `INT-K07`
- `policy-engine/docs/research/policy-operations/int-r8/reconstruction-composition-and-threat-model.md:206-286`

**Known limitation:** this is a current premise-relative refusal, not an impossibility theorem. A future bounded statistical or QIF use case may satisfy the missing model and ownership conditions.

**Constrains:** public epsilon, leakage score, percentage, remaining budget, cumulative safety score or equivalent canonical number.

**Does not decide:** whether a team may research differential privacy or QIF; which model would be best; whether a future product needs a number; candidate diagnostics.

**Supersession trigger:** a named product use establishes the complete model, local validity, composition theorem, canonical owner, custody and protected consumer, followed by independent verification under `INT-K04`/`INT-K07`.

### RC-09 — Proof metadata belongs to the disclosure channel

**Precise wording**

> Public-proof metadata and topology are part of the governed disclosure channel. Key identifiers, credential or certificate paths, commitment identifiers, transparency-log positions, witness sets, proof-object sizes, linkage patterns and related auxiliary data may bind evidence, but they may not be treated as harmless by default or become oracles for protected record values. A governed proof candidate must include them in the declared reconstruction/channel analysis while preserving the proof/content authority boundary.

**Band bound:** **authority band only.** Candidate proof constructions may expose metadata for experimentation. The statement constrains admission as a governed public proof and the claims made about its disclosure safety.

**Supporting sources**

- `policy-engine/docs/research/policy-operations/int-r8-compression-loss-and-disclosure.md:318-355`
- `policy-engine/docs/research/policy-operations/int-r8/reconstruction-composition-and-threat-model.md:425-436`
- `policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md:649-670`
- finding `S0-K07`

**Known limitation:** no mitigation, padding policy, batching construction, privacy-preserving status mechanism, identifier design or proof-size policy is established. The channel registry remains open.

**Constrains:** proof design admission, channel enumeration, coalition reconstruction tests and claims that a proof is privacy-safe.

**Does not decide:** whether any listed field must be removed, encrypted, padded, batched or redesigned; which trade-off a candidate should choose.

**Supersession trigger:** an independently verified proof construction establishes that a class of metadata is information-theoretically or cryptographically independent of every protected predicate under the declared auxiliary-information and coalition model.

## 3. Candidate reconciliation with existing ratifications

| Candidate | Existing ratified base | New authority-band contribution |
| --- | --- | --- |
| RC-01 | `S0-K07`, `S0-K12`, `INT-K08` | applies non-laundering and negative completion to public verification dimensions |
| RC-02 | `S0-K08`, `INT-K08` | separates historical authenticity from current authority and binds snapshot selection |
| RC-03 | `S0-K05`, `S0-K07`, `INT-K05` | fixes the proof/content seam without a parallel owner |
| RC-04 | `S0-K07`, `INT-K02`, `INT-K08` | defines non-amplifying semantic parity for shorter public objects |
| RC-05 | `INT-K02`, `INT-K06`, `INT-K08` | records three categorical compression blockers |
| RC-06 | `INT-K08` | makes non-establishment and approximation outcomes total and non-positive |
| RC-07 | `INT-K06`, `INT-K04`, `INT-K07`, `INT-K08` | applies the existing no-number claim kind to adaptive disclosure prefixes |
| RC-08 | `INT-K04`, `INT-K05`, `INT-K07` | premise-relative current refusal of a canonical numerical disclosure claim |
| RC-09 | `S0-K07` | extends the channel boundary to proof metadata and topology |

## 4. Outcome-vocabulary determination

This wave does **not** produce a third outcome-vocabulary element beyond the ratified vocabulary.

- Prefix discipline is an application of the already-ratified `INT-K06` binding procedural claim carrying no probability.
- `model_observation_inconsistent`, timeout, unsupported theory, incomplete history and unproved approximation are typed negative/non-establishment results under `INT-K08`; they are not a new favorable claim kind.
- `lossy_but_safe` and `blocked_material_omission` are projection-only verifier dispositions, not a global PolicyOS status lattice (`semantic-contract-and-loss-boundary.md:34-49`).

Accordingly, the §8 instruction in `int-wave-claim-semantics-ratification.md` to use one consolidated constitutional amendment upon a future third vocabulary addition is **not activated by this wave**.

## 5. Deliberately not proposed

| Considered proposition | Why it is not proposed for ratification |
| --- | --- |
| one public `Verified` Boolean | would hide which authority-band proposition passed and permit a signature or projection to launder the rest |
| a wire format, schema, enum, package, database table or API | candidate-band architecture; not required to bind authority semantics |
| a new public status lattice | conflicts with the one-owner/no-parallel-lattice discipline; receipt outcomes are projection-only dispositions |
| a named signer, CA, timestamp authority, log, witness, archive, custodian, service, vendor or quorum size | institutional or candidate-band choice; not established by research |
| a mandatory deterministic projection generator | INT-R8 requires a deterministic/well-defined proof relation for supplied objects, not one canonical deterministic production algorithm |
| a canonical numerical disclosure budget | premises and owner absent; RC-08 is the authority-band refusal instead |
| randomization as a necessary condition for quantitative disclosure analysis | mathematically refuted by deterministic-channel QIF families |
| exact byte equality as semantic parity | both overrestrictive and unsafe; RC-04 supplies the protected-query relation |
| a new third outcome kind | no new kind exists; `INT-K06` and `INT-K08` already cover the results |
| legal sufficiency, institutional competence or universal jurisdictional transfer | outside the research evidence and authority of this consolidation |
| permission to open either first-public gate | implementation, custody and institutional conditions remain absent |
| a parallel confidence, currentness, projection or loss owner | would duplicate existing owners and violate `INT-K05`/GY-N12 allocation |
| a claim that proof-metadata leakage is solved | the attack and obligation are established; no candidate mitigation has passed |
| a general tractability or decidability claim | the executable result is deliberately bounded to declared finite/decidable/proved-conservative models |
| a fixed channel registry | the registry is explicitly open; unknown channels must remain visible limitations |

## 6. Ratification boundary

These are proposals, not decisions. Ratification would constrain authority-band claims and representations only. It would not authorize implementation, select a candidate, appoint an institution, establish repository capability, open a gate, or amend a plan automatically.
