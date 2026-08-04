---
title: "INT-R8 — Compression Loss and Disclosure Composition"
research_id: INT-R8
artifact_role: primary-report
result_standing: accepted_narrow_scope
amendment_conformance: pending_independent_verification
research_only: true
repository: DenisKopylov/polisyos
baseline_ref: main
baseline_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
audited_head: 90b372964d29a9e97605a6ef733ef03ffe7938d2
research_branch: research/int-r8-amendment
prepared_at: 2026-08-04
composition_result: procedural_no_number
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

# INT-R8 — Compression Loss and Disclosure Composition

## 0. Controlling amendment notice

This is the controlling amended primary report. It executes the revision register in
`audits/int-r8/int-r8-recommended-revision.md` after audit
`research/int-r8-independent-audit@f45f338f9d9b0de94edc16efbc334789e70e34e2`.
The audited version remains immutable at
`research/int-r8-compression-loss-and-disclosure@90b372964d29a9e97605a6ef733ef03ffe7938d2`.
Where this report or an amended supporting artifact conflicts with that version, the amendment
controls. Unchanged conclusions are preserved because the audit commended them, not because the
author reasserts them.

Ordinary GitHub clone access was unavailable in the amendment environment because DNS resolution
for `github.com` failed. Exact-ref reads and ordinary Markdown commits used the connected GitHub
interface. No workflow, upload fragment, staging directory, base64 payload, or self-executing
repository mechanism was added.

## 1. Amended executive decision

### Result standing: `accepted_narrow_scope`

The standing is retained **after execution of R1-R13 and pending independent conformance
verification**.

INT-R8 settles, at research-contract level:

1. `CompressionLossReceipt` semantics as an extension of the existing projection, omission,
   redaction, contest, recourse, denied-use, and audit substrate;
2. use-relative conservative semantic parity for legitimately shorter records;
3. a derived minimum retained set for public-policy records;
4. the boundary between `lossy_but_safe` and `blocked_material_omission`;
5. exact cross-view and temporal reconstruction for a declared finite or decidable model;
6. an adaptive, number-free prefix discipline over a declared release family under custody;
7. an open release-channel threat registry;
8. atomic equality-ready falsifier requirements; and
9. a construction-neutral semantic interface to INT-R7.

INT-R8 does **not** establish a numerical repeated-disclosure guarantee. The controlling reason
is narrower than the audited wording:

> No canonical numerical disclosure-composition claim is justified for the current PolicyOS
> release path under any model established in the repository.

The obstruction is not determinism. Differential privacy, maximal leakage, maximal-alpha
leakage, statistic maximal leakage, min-entropy leakage, and generalized-gain quantitative
information flow each require their own declared secret, channel, support or prior assumptions,
gain/loss function, local validity conditions, composition rule, and canonical accounting owner.
None of those complete models is established in the pinned repository. Therefore no epsilon,
percentage, leakage value, remaining budget, or cumulative safety score may be issued now.

The accepted composition result remains the `INT-K06` procedural claim:

> For a versioned declared release family under custody, every controlled candidate disclosure
> prefix is evaluated prospectively against a fixed semantic-loss and exact-or-proved-conservative
> reconstruction family; membership, chronology, current heads, model versions, inputs, and
> verifier dispositions are reproducible; no deletion, reclassification, or post-hoc narrowing
> of controlled history manufactures a pass.

This is a Boolean custody claim, not a scalar budget. It is falsifiable and adaptive. It proves
only enforcement of the declared checks over the declared custody boundary.

## 2. Preserved audit-confirmed strengths

The amendment preserves all commendation-backed positions:

- the branch orientation identifies substantial existing projection and public-export substrate;
- the four audiences remain exactly PUBLIC, REVIEWER, EXPERT, and MACHINE;
- denied-use semantics remain first-class and monotone under compression;
- a bare `delta` is always blocked under `INT-K02`;
- hidden refusal, void, dispute, terminal no-attempt, and exhaustion are always blocked under
  `INT-K08`;
- exact consistency-set reconstruction and strict coalition synergy are mathematically correct
  under their declared premises;
- the exact singleton/non-uniqueness test is genuinely number-free;
- actual-prefix evaluation handles adaptive next-release choice without a numerical theorem;
- the existing threat model is materially stronger than body-text-only review;
- the receipt extends existing owners and creates no fifth audience, global status lattice, or
  confidence ledger;
- the public-administration minimum set is grounded in reasons, contestability, dissent,
  accessibility, deletion indication, and output checking;
- differential-privacy composition is not imported by analogy;
- the strongest red cases and all five reject-all-preventing green purposes remain;
- INT-R8 remains on the content side of the INT-R7 seam;
- existing projection and public-export capabilities are not erased; and
- every artifact remains research-only and non-authorizing.

The full 35-finding disposition, including each of 19 commendations, is in
`int-r8/amendment-ledger.md`.

## 3. Corrected repository capability reality

Missing-state labels are used only when their prerequisites are evidenced. Plan text is not a
consumer, endpoint, wired chain, or capability.

| Capability or surface | Pinned evidence | Amended reality statement |
|---|---|---|
| Four-audience projection semantics | `runtime/quality/projection_semantics.py` producer, contracts, and tests | `implemented` for the existing projection substrate only. |
| Public-export bundle producer | `runtime/quality/public_export.py::build_public_export_bundle`, tests, and tooling callers | Existing producer is present and remains projection-only. |
| Public-export producer to intended public/runtime route | Existing producer plus existing runtime/public surfaces, with no caller binding the producer into that route | `bridge_missing`; both sides exist, the connection does not. |
| Compression-loss semantic contract | This amended research contract; no source producer or admitted wired consumer | `contract_only`. |
| Compression-loss runtime producer / GY-PA3 | GY-PA3 is plan text only | Absent and unallocated at the pinned commit; no downstream maturity label is assigned. |
| Material-loss publication gate | No receipt producer, admitted receipt artifact, or wired consumer chain | Absent and unallocated at the pinned commit. |
| Cross-view/temporal transcript custody and verifier | No approved owner, artifact, consumer, or wired chain | Absent and unallocated at the pinned commit. |
| Atlas receipt rendering | Existing packet/viewer render other data; no owner-issued receipt endpoint or artifact | Existing rendering surface is present; INT-R8 receipt integration is absent and unallocated. |
| Screenshot/print/export semantic tests | Real rendering/export surfaces exist; INT-R8 cases do not | `semantic_test_missing` for those existing scoped surfaces. |
| INT-R7 proof relation | Parallel research contract, not implementation | `contract_only`; current first-public-record gate remains closed. |
| Numerical disclosure accountant | No authorized model or consumer; current result refuses a number | Not a missing implementation capability. It is an optional future research direction only after a model and consumer are competently established. |

No row appoints an owner. Any future implementation must re-run prerequisite classification at
its own exact commit.

## 4. Comparative model selection after R3

| Model family | What it can establish | Required premises | Current disposition |
|---|---|---|---|
| Statistical disclosure control | Suppression, contributor thresholds, differencing review, and release checking | Output class, local rule, underlying evidence, prior-output inventory, competent checker | Adopt as release discipline and attack source, not a universal semantic theorem. |
| Differential privacy | Per-mechanism probabilistic privacy and adaptive composition | Neighbor relation, randomized mechanism, local `(epsilon, delta)` validity, prospective allocation, history-valid accountant | No current transfer; retain as a future bounded statistical mechanism family. |
| Maximal / maximal-alpha leakage | Guessing-gain or alpha-loss leakage, with data-processing and model-specific composition properties | Secret/channel model, support or prior assumptions, adversary objective, local leakage evaluation, applicable composition theorem | Mathematically available for deterministic or randomized channels; no current PolicyOS value because its model and owner are absent. |
| Statistic maximal leakage | Leakage about a specified statistic, including computation for deterministic releases in the cited model | Named statistic/secret, prior/support treatment, deterministic channel semantics, local value and composition conditions | Candidate future model; not established for editorial policy records. |
| Min-entropy and generalized-gain QIF | Posterior guessing advantage under a declared vulnerability or gain function | Secret distribution/support, gain function, channel, observation relation, local and composed analysis | Candidate diagnostic/research family; no current canonical quantity. |
| Exact consistency-set reconstruction | Whether a protected predicate becomes uniquely determined | Declared nonempty model, observational equivalence, protected predicate, exact or proved-conservative decision | Adopt now for bounded Boolean decisions. It is not a scalar budget. |
| Access control | Ordinary role separation | Principal/role mapping and enforcement | Perimeter only; authorized views may still be joined. |
| Redaction with manifest | Detectable typed removal | Canonical reason relation and safe granularity | Canonical base, extended by the receipt and transcript checks. |
| Provenance completeness | Binding, currentness, and authorized full-record access | Non-leaking references and proof relation | Required layer, not a cure for misleading visible prose. |
| Administrative reasons-giving | Material reasons, findings, evidence, dissent, and contestability classes | Jurisdiction/procedure-specific competence and confidentiality limits | Materiality layer with explicit transfer limits. |
| Unstructured editorial summary without receipt | Readability only | None capable of proving material safety | Rejected as a governed publication basis. |

## 5. Semantic parity and the minimum retained set

Semantic parity remains **use-relative conservative observational equivalence**. For source
record `R`, summary plus receipt `S`, declared use package `U`, governed predicate package `D_U`,
and authority order `<=`, parity requires:

1. every surfaced claim resolves to `R`;
2. claim type, basis, scope, assumptions, conditions, and material limitations are preserved;
3. every governed decision from `S` equals the decision from `R` or is more conservative;
4. `may_not_use_for(S)` is a superset of `may_not_use_for(R)` at claim and projection level;
5. negative terminals, contest, material dissent, recourse, supersession, and correction remain
   visible when their governed effects are active;
6. every dropped inventory item has a canonical transformation/semantic reason relation;
7. the exact rendered object and declared delivery channels pass the transcript check; and
8. unresolved model, materiality, history, or verifier input blocks.

The minimum retained set is derived by asking whether removal changes truth, scope, authority,
use, contestability, history/currentness, or privacy. It contains:

- source record/revision, release identity, and current/superseded state;
- actual existing outcome and status, without a local approval proxy;
- claim identity and claim type;
- subject, jurisdiction, material time/envelope, and declared basis;
- for `delta`, the obligation set, maintained assumptions, and visible relative-basis rider;
- for no-number custody, the version-bound constitutive event set and order relation;
- material limitations and conditionality;
- every active denied use;
- material counterevidence, attacks, dissent, contest, and disposition at safe granularity;
- a competent recourse/correction pointer where one exists;
- typed omission/redaction class, reason relation, affected public claims, and semantic effect;
- public-safe provenance/current-head/full-record binding; and
- the receipt verdict, model identities, issue codes, and verifier disposition.

A full-record link remains necessary for authorized audit and insufficient to cure a misleading
visible summary.

## 6. Bounded reconstruction model and explicit outcomes

Let `R_model` be a declared nonempty finite record family or a record family represented in a
decidable symbolic fragment. Let `Obs_F(r)` be the observations generated for declared release
family `F`, and let `t` be the observed controlled transcript. Define:

`C_F(t) = { r in R_model : Obs_F(r) is observationally equal to t }`.

For total protected predicate `q`, exact reconstruction occurs when:

`| { q(r) : r in C_F(t) } | = 1`.

Strict cross-view reconstruction occurs when every single obtainable audience transcript leaves
at least two `q` values possible, while one declared obtainable coalition leaves exactly one.
Temporal reconstruction is the same condition over successive releases.

The executable claim is bounded as follows:

| Evaluation state | Required verifier disposition | Publication loss outcome |
|---|---|---|
| At least two protected values remain possible | `not_reconstructed_under_declared_model` | Privacy limb may pass if all other gates pass. |
| Exactly one protected value remains possible | `reconstructed` | `blocked_material_omission`. |
| `C_F(t)` is empty | `model_observation_inconsistent` | Blocked; never interpreted as safe. |
| Exact solver times out or exhausts resources | `not_established_timeout` | Blocked. |
| Symbolic theory is unsupported or undecidable for the supplied instance | `not_established_unsupported_theory` | Blocked. |
| Abstraction has a proved no-false-safe direction and reports possible reconstruction | `conservative_risk_found` | Blocked. |
| Abstraction has a proved no-false-safe direction and discharges the exact obligation it is authorized to decide | `not_reconstructed_under_proved_conservative_abstraction` | May pass only within that exact abstraction scope. |
| Sampling, classifier, posterior threshold, heuristic search, or unproved approximation | `not_established_unowned_approximation` | Blocked; it does not inherit the number-free theorem. |

This contract does not claim tractability for arbitrary PolicyOS records. A general operational
verifier remains absent and unallocated.

## 7. Declared release family and prefix discipline

A release-family declaration is versioned and separates:

1. **controlled registered releases** — server responses, registered audience projections,
   generated deep links, known exports, registered screenshots/print objects, controlled caches,
   delivery metadata, and corrections whose membership and observation must be reproducible;
2. **observed external copies** — third-party or recipient copies that have been discovered and
   admitted to the transcript with provenance and observation limits; and
3. **uncontrolled or unknown channels** — unobserved screenshots, external institutional
   disclosures, covert exfiltration, unknown archives, and unknown auxiliary datasets.

Missing or rewritten controlled history blocks. Observed external copies extend the transcript.
Uncontrolled or unknown channels do not disappear: they set the completeness disposition to
`bounded_to_declared_release_family` or `external_history_not_established` and prevent any
unqualified claim of universal disclosure safety.

For fixed versioned Boolean rule family `G`, let `Safe_G(T_i)` mean that the complete controlled
candidate prefix passes every required semantic-loss and exact/proved-conservative reconstruction
obligation. If the base prefix passes, one canonical enforcement path constructs each actual
history-selected candidate prefix, release occurs only after `Safe_G(T_i)`, and controlled
history is append-only except by appended correction/supersession, then every released controlled
prefix passed `G` when released. The proof is induction and uses no non-adaptive selection
premise.

This proves enforcement, not attack completeness, legal compliance, competence, or secrecy
against unknown external channels.

## 8. Materiality, constitutive procedure, and canonical reasons

### 8.1 Materiality relation

Every source semantic item binds to one or more governed effects:

- `truth_condition`;
- `scope_or_basis`;
- `authority_or_status`;
- `permitted_or_denied_use`;
- `contestability_or_recourse`;
- `history_or_currentness`; or
- `privacy_or_reconstruction`.

It also binds the competent basis, affected claim IDs, predicate package version, and allowed
condensation relation. Removal is material when it changes any bound effect under a declared use.
An unresolved basis or effect returns `compression_materiality_not_established` and blocks.

### 8.2 Constitutive no-number steps

A no-number custody claim must declare its constitutive event classes and order constraints, such
as prospective sealing, first qualifying attempt, prohibited-substitution rule, deviations,
adjudication, dissent, negative publication, and correction. A shorter rendering is safe only if
it preserves every unique constitutive event and order predicate. Duplicate prose may disappear;
a unique step may not.

The verifier does not decide constitution by free-text similarity. It compares the declared
constitutive relation and the summary's faithful-event mapping. Removing one decisive event must
turn the relevant predicate red; removing duplicate wording must not.

### 8.3 One reason relation

The receipt does not create a third reason vocabulary. It consumes one approved relation:

`transformation_reason -> omission_semantic_class -> affected_claims -> governed_effect -> safe_public_explanation`.

- canonical scanner reasons remain the transformation reasons for scanner-detected email,
  keyed-secret, and secret/PII removal;
- canonical projection omission reasons remain source omission identifiers where applicable;
- receipt-level semantics add typed effect and affected-claim bindings through an approved
  extension relation, not a competing identifier with the same meaning;
- the public explanation must not expose the protected value; and
- missing, unknown, mismatched, duplicate-conflicting, or self-disclosing reason relations block.

A future implementation requires a complete duplicate/overlap census before claiming one
canonical live registry. This amendment appoints none.

## 9. Open release-channel registry

The channel registry is versioned and explicitly open. Existing classes remain: body content,
omission manifests, diffs, hashes/ETags, ordering/rank/pagination, timing/cadence, provenance
joins, deep links, screenshots, print, clipboard, PDF/DOCX/HTML/JSON/CSV, hidden DOM,
accessibility tree, embedded metadata, source maps, headers, caches, logs, analytics, referrers,
errors, and currentness.

The amendment adds:

1. locale, translation, fallback-language, and translation-memory divergence;
2. email, push, webhook, RSS/Atom, social-card/Open Graph, and chat syndication;
3. compression-ratio, content-encoding, packet-length, TLS-record-count, range-response, and
   conditional-request oracles;
4. sitemap, indexing, autocomplete, search-snippet, result-count, and cache-invalidation
   discovery channels; and
5. proof metadata, including key identifiers, certificate paths, transparency-log positions,
   witness sets, proof-object sizes, and commitment/linkage identifiers.

An unclassified channel yields `release_channel_out_of_model` and cannot inherit a broad safe
verdict. INT-R7 must ensure that its proof construction and metadata do not reconstruct protected
content; INT-R8 does not choose the mitigation.

## 10. INT-R7 semantic proof interface

The content-side relation requires proof binding or typed disposition for:

- source record and revision;
- audience and surface;
- exact transformed/rendered/exported public object identifiers;
- retained semantic-item set;
- omission classes, affected claims, reason relation, and governed effects;
- loss verdict and rule version;
- declared uses and denied uses;
- materiality/decision-predicate package;
- semantic-inventory version and completeness disposition;
- record/consistency model;
- protected-predicate family;
- channel-registry and declared-release-family version;
- coalition/delegation availability model;
- auxiliary/background-information assumptions and incompleteness statement;
- predecessor/current transcript head and transcript-completeness disposition;
- empty-set, timeout, unsupported-theory, exact, or abstraction verifier status;
- current/superseded state; and
- the unchanged projection-only authority boundary.

INT-R7 remains free to select canonicalization, signature, commitment, key, rotation, revocation,
witness, transparency, archival, and offline-verification construction.

A failed or missing INT-R8 relation means that public projection faithfulness/loss safety is not
established and no public-current positive may rely on it. It does **not** imply that the issuer
never authentically issued the source record. Issuer issuance authenticity, projection
faithfulness, public-history establishment, durable verifiability, and current authority remain
separately reportable dimensions. This aligns with audit finding `INT-R7-VIII-003`; it does not
adopt the unverified INT-R7 amendment as authority.

## 11. Falsifier and handoff status

Suite v1 remains immutable at the audited commit. The controlling amended specification is
`INT-R8-COMPRESSION-FALSIFIERS-v2` in
`int-r8/falsifier-suite-and-integration-handoff.md`. It preserves F01-F25 and G01-G05 as family
identities, splits them into atomic subfixtures, adds exact evaluation-status fields, and adds
five channel families required by R6.

No suite has run and no capability is inferred from the specification.

## 12. Updated standing and non-authorization

**Amended standing: `accepted_narrow_scope`, retained pending independent conformance
verification.**

The central result remains:

> Safe compression is a conservative, receipt-bearing transformation checked against the
> declared controlled release transcript. Exact or proved-conservative reconstruction is a
> Boolean gate. A public summary is blocked when it loses a truth-changing basis, material
> limitation, denied use, counterposition, dissent, negative outcome, constitutive procedural
> step, currentness fact, or when a declared obtainable coalition or temporal transcript uniquely
> reconstructs protected information.

The amendment does not authorize implementation, publication, a canonical owner, a final schema,
a proof construction, a legal conclusion, or any numerical disclosure claim. The first public
governed-record gate remains closed.
