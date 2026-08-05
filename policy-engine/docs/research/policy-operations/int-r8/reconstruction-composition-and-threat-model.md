---
title: "INT-R8 cross-view reconstruction, composition refusal, and release-channel threat model"
research_id: INT-R8
artifact_role: formal-analysis-and-threat-model
status: accepted_narrow_scope
research_only: true
repository: DenisKopylov/polisyos
baseline_ref: main
baseline_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
prepared_at: 2026-08-04
composition_result: procedural_no_number
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

# INT-R8 cross-view reconstruction, composition refusal, and release-channel threat model

## 1. Composition result stated explicitly

**INT-R8 does not establish a numeric composition budget.**

The delivered composition result is the `INT-K06` alternative: a **binding, falsifiable procedural claim about disclosure discipline carrying no probability or leakage number**.

A numerical claim is refused because the repository and the release mechanism do not satisfy the premises needed by any surveyed theorem:

1. no canonical disclosure-budget owner exists in `policy-engine/src`;
2. no adjacency relation defines what two protected records differ by;
3. no randomized release mechanism with a per-release privacy guarantee is specified or enforced;
4. no distribution over full records, secrets, adversary knowledge or editorial choices is fixed;
5. ordinary publication choices are adaptive — a later release is selected after earlier outputs, reactions, requests, corrections or discovered omissions are known;
6. no owner evaluates the actual history-selected mechanism and proves a pathwise aggregate bound;
7. the quantity at issue mixes several incomparable harms: personal-data reconstruction, confidential evidence disclosure, identity inference, scope inference and authority distortion.

Attaching an epsilon-like scalar to curated summaries under those conditions would repeat the exact failure prohibited by `INT-K04` and `INT-K07`: prose would assert composition without prospectively enforced local guarantees and reproducible custody (`policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:143-218`).

This refusal is a completed governed result, not an unfinished placeholder.

## 2. Formal reconstruction model

### 2.1 Record and release process

Let:

- `𝓡` be the set of full PolicyOS records compatible with the declared record contract and public background knowledge;
- `R ∈ 𝓡` be the actual full record at a revision;
- `A = {PUBLIC, REVIEWER, EXPERT, MACHINE}` be the canonical audience set;
- `H_{i-1}` be the complete release history available before event `i`;
- `P_i` be the content projection/editorial procedure chosen at event `i`;
- `C_i` be all non-body channels emitted with that release;
- `Y_i = P_i(R, H_{i-1})` be visible content;
- `M_i = C_i(R, Y_i, H_{i-1})` be metadata and side channels;
- `T_n = ((a_i, Y_i, M_i))_{i=1}^{n}` be the complete disclosure transcript through event `n`.

`M_i` includes, when present:

- omission/redaction metadata;
- raw or generated diffs;
- content hashes and ETags;
- list ordering, rank and pagination gaps;
- precise timestamps, latency and update cadence;
- provenance snippets and joinable references;
- deep-link path or payload;
- downloadable/exported representation;
- screenshot/print-visible material;
- accessibility tree, hidden DOM, embedded metadata and source maps;
- HTTP headers, cache keys, content length, logs, analytics/referrer data and error messages;
- current/superseded/version pointers.

Analyzing only `Y_i` is therefore an invalid denominator.

### 2.2 Consistency set

For observed transcript `t`, define the adversary's consistency set:

`C(t) = { r ∈ 𝓡 : Release(r) is observationally consistent with t }`.

The release process in this definition includes all audience projections and channels that the threat actor can obtain, not merely the public prose.

For a withheld predicate `q : 𝓡 → Q`, the transcript reconstructs `q` exactly when:

`| { q(r) : r ∈ C(t) } | = 1`.

This definition is distribution-free. It captures reconstruction even when the system is deterministic and no probability model is defensible.

For approximate/high-confidence inference, a future research task may add a declared prior or gain function. INT-R8 does not silently assume one.

### 2.3 Cross-view reconstruction

Let `t_a` be the current projection transcript obtainable from audience `a`. A **strict cross-view reconstruction** exists for predicate `q` when:

- `q` is not constant on any single-view consistency set `C(t_a)`; but
- `q` is constant on `C(⋃_{a∈A'} t_a)` for an obtainable audience coalition `A' ⊆ A`, `|A'| ≥ 2`.

Equivalently, each view leaves at least two possible values of `q`, while the intersection of their constraints leaves one.

This is the precise form of the required falsifier “two individually safe projections reconstruct a withheld claim.” Per-view validation cannot detect it; the gate must evaluate the coalition transcript that the threat model declares obtainable.

### 2.4 Temporal reconstruction

Let `T_i` and `T_j`, `i < j`, be releases of the same logical record or linked revisions. A temporal reconstruction exists when a withheld predicate is not determined from either snapshot alone but is determined from their pair or sequence:

`|q(C(T_i))| > 1`, `|q(C(T_j))| > 1`, but `|q(C(T_i ∪ T_j))| = 1`.

Typical mechanisms are:

- one cell/claim removed between versions;
- a redacted row inserted at a stable sorted position;
- count, content length or contributor threshold changing by one;
- a timestamp revealing when a confidential event occurred;
- an unchanged low-entropy hash showing that a hidden value persisted;
- a “correction” whose before/after text discloses the protected original;
- a provenance reference appearing in one audience before another.

The release unit for safety is therefore the **entire retained history**, not the latest view.

### 2.5 Information-theoretic diagnostic, not current authority

If a future task declares random variables and a probability space, exact reconstruction of secret `Z=q(R)` implies `H(Z | T_n)=0`. Cross-view synergy can be expressed as:

- `H(Z | Y_a) > 0` for each individual view; and
- `H(Z | (Y_a)_{a∈A'}) = 0` for their union.

Maximal leakage supplies an operational guessing-gain measure when a valid joint distribution/channel is supplied. It is useful for comparing candidate mechanisms and adversary objectives, but it does not become a repository budget merely because the formula exists. INT-R8 imports the **question structure**, not a scalar guarantee.

## 3. Executable reconstruction check

### 3.1 Inputs

A future verifier needs:

- source revision and declared full-record model/fixture family;
- candidate release content and all candidate channels;
- every retained historical release reachable by the declared adversary;
- audience-coalition policy;
- a versioned set of withheld predicates and inference attacks;
- public background knowledge and allowed auxiliary datasets;
- a completeness disposition for the attack set.

### 3.2 Verdict

For each attack/predicate pair the verifier returns:

- `not_reconstructed_under_declared_model`;
- `reconstructed`; or
- `not_established`.

These are verifier findings inside the receipt, not a new global status lattice. At the INT-R8 gate:

- `reconstructed` → `blocked_material_omission`;
- `not_established` → `blocked_material_omission` for publication, because safety was not proved;
- only all required `not_reconstructed_under_declared_model` results permit the privacy limb of `lossy_but_safe`.

The wording “under declared model” is mandatory. A finite attack set does not prove that no inference exists in the world.

### 3.3 Candidate-state enumeration

For finite fixtures, the strongest executable method is exhaustive consistency-set enumeration:

1. enumerate all full-record candidates allowed by the fixture and background-knowledge contract;
2. run the same projection/channel functions on each candidate;
3. retain candidates observationally equal to the proposed actual transcript;
4. evaluate every withheld predicate on the retained set;
5. fail when any predicate is constant or only one candidate remains where more than one protected state must remain possible.

For large/infinite spaces, use sound symbolic constraints, SAT/SMT, database reconstruction queries, property-based adversarial generators or approved over-approximations. An approximation may safely over-report risk; it may not declare safe after an incomplete under-approximation.

## 4. No reconstruction through named channels

### 4.1 Diff channel

**Attack.** Two safe snapshots reveal a confidential removal or exact changed value through a raw patch, semantic diff, line number, count delta or unchanged context.

**Required invariant.** The gate evaluates the released diff as content. It must reject raw before/after material whose intersection reconstructs a withheld item. A public change notice may state typed categories and affected public claims without revealing the protected old/new value.

**Red test.** Full records differ only in one protected claim. Public snapshots suppress it, but the exported diff names the claim or shows the deleted text. Verdict: `compression_temporal_reconstruction`.

### 4.2 Hash channel

**Attack.** A deterministic hash of a low-entropy secret, hidden claim set or redacted cell is tested against a dictionary; equality of hashes across releases becomes a membership or persistence oracle.

**Required invariant.** A public hash may bind only the approved public object or an INT-R7 construction proven not to disclose the redacted content. INT-R8 does not choose that construction. Raw hashes of protected low-entropy values and joinable per-item fingerprints fail.

**Important repository fact.** The current frontend uses a stable 32-bit FNV-like hash over serialized packet content, and the deep-link `signedId` contains an encoded packet and hash-derived suffix (`publicationPacket.ts:913-1174`). DS12 treats this only as frontend integrity, not authority. INT-R8 additionally treats it as release metadata that must be privacy-reviewed.

### 4.3 Ordering and rank channel

**Attack.** Suppressed records retain their sort slots; pagination totals, rank gaps, stable IDs or “top N” boundaries reveal a hidden item's category or score.

**Required invariant.** Public ordering is computed from public-safe keys after suppression, or the transcript verifier proves that order/rank does not narrow a protected predicate. Hidden score order may not survive as visible gaps.

### 4.4 Timing channel

**Attack.** Exact event/release timestamps, delays, update cadence or response latency identify a confidential event, reviewer or threshold crossing.

**Required invariant.** Distinguish two cases:

- when chronology is part of an `INT-K06` custody claim, disclose the minimum ordered facts needed to make that claim falsifiable;
- when precise time is not semantically material, reduce precision/bucket or withhold it under a typed reason and test the temporal transcript.

Generic removal of all times is not the answer: it can itself destroy a procedural claim or hide a negative chronology.

### 4.5 Provenance-join channel

**Attack.** Two audiences receive different snippets with the same private artifact ID, row key, reviewer ID or CAS reference; joining them reconstructs identity/content.

**Required invariant.** Audience projections receive public/audience-scoped references that remain resolvable for authorized audit but are not unauthorized cross-view join keys. Whether and how proof references can be scoped without anti-equivocation failure is an INT-R7 dependency.

### 4.6 Omission-manifest channel

**Attack.** A manifest truthfully says “one allegation of type X was removed from person Y's record,” revealing the very fact being protected.

**Required invariant.** Manifested omission is mandatory, but its granularity and reason must be safe. It must disclose semantic class and effect sufficient to prevent misleading silence without acting as a value oracle. This is why the receipt records affected public claim IDs and reason classes rather than necessarily the hidden item's exact identity.

## 5. Composition survey and theorem analysis

### 5.1 Differential privacy transfer test

Differential privacy composes because each mechanism is evaluated against an explicit neighboring-dataset relation and a probability distribution over its randomized output. Sequential/adaptive composition theorems reason about mechanisms that satisfy local `(ε_i, δ_i)` guarantees, including conditional choices when the local guarantee remains valid for the history-selected mechanism.

The current PolicyOS publication process is a curated deterministic/editorial transformation. There is no established:

- neighboring-record relation;
- randomization law;
- local `(ε_i, δ_i)` verifier;
- prospective privacy parameter allocation;
- canonical accountant;
- pathwise guarantee for an editor choosing release `i` after observing history.

Therefore DP composition **does not transfer as a theorem**. DP remains a candidate mechanism family for narrowly specified statistical releases, but adopting it would require a separate research/design decision and cannot retroactively certify ordinary summaries.

### 5.2 Statistical disclosure-control transfer test

National statistical institutes apply suppression, contributor thresholds, perturbation and output checking, including differencing checks across outputs. The transferable result is procedural and strong: release is an output-checking event, prior outputs matter, and “request only what is needed” is safer than uncontrolled accumulation.

What does not transfer automatically:

- a rule-of-N for tabular cells does not protect legal reasons, confidential narrative evidence, dissent or claim scope;
- passing a cell threshold does not establish semantic parity;
- a statistical output checker does not resolve authority/status distortion.

SDC supplies attack classes and release discipline, not a universal scalar budget for PolicyOS records.

### 5.3 Information-theoretic leakage transfer test

Mutual information, maximal leakage and gain-function leakage can measure inference once a secret, adversary objective, distribution and channel are declared. They are useful for:

- detecting synergy between views;
- comparing mechanism variants;
- making the adversary's guessing task explicit.

They do not currently yield one canonical number because PolicyOS has multiple secret predicates, no justified prior and deterministic editorial channels. Worst-case exact reconstruction is still testable through consistency sets and is the chosen current formalism.

### 5.4 Access-control transfer test

Audience separation limits ordinary access, but it assumes no credential overlap, delegation, screenshots, exports, copied links, logs or collusion. The canonical audiences are semantic projections, not mutually exclusive security principals. Access control is necessary but cannot substitute for safe content transformation or transcript analysis.

### 5.5 Redaction-with-manifest transfer test

This model is closest to the repository and is adopted as the receipt base. It makes silent loss detectable and supports reasons/counterevidence/denied-use preservation. Alone, it does not stop manifests, hashes, diffs or multiple views from reconstructing content, so it must be paired with transcript checking.

### 5.6 Provenance-completeness transfer test

A pointer to the full record supports audit, version binding and correction. It cannot cure a public summary that affirmatively broadens a claim or hides a refusal. Provenance is adopted as a required binding/pointer layer, not as a substitute for the minimum retained set.

### 5.7 Legal reasons-giving transfer test

Reasons-giving practice identifies material findings, conclusions, reasons and counterpositions as public-administration semantics, not optional explanatory detail. It supports the materiality test: an omission is blocked when it prevents a person/reviewer from understanding the real basis or contesting a material issue. It does not demand publication of every confidential detail and therefore composes naturally with typed redaction.

### 5.8 Unstructured editorial summary

Unstructured summary with no receipt is rejected. It has no complete source inventory, no checkable retained/dropped mapping, no denied-use monotonicity, no materiality decision, no coalition/temporal transcript and no fail-closed verdict. A fluent summary can silently turn conditional into unconditional, disputed into agreed, refusal into absence and no-number custody into generalized process approval.

## 6. Procedural composition alternative

### 6.1 Declared disclosure discipline

For each governed record, the disclosure process must maintain an append-only logical transcript containing:

- exact release membership and chronology;
- source/current heads and rule versions;
- audience and delivery channels;
- retained/dropped semantic inventory and reasons;
- the actual candidate bytes/representation or a proof-bindable public object reference;
- verifier findings for materiality and declared reconstruction attacks;
- decision and competent human/owner disposition where required;
- supersession/correction linkage.

Before release `i`, the gate evaluates the **entire candidate prefix** `T_i`, not only event `i`.

### 6.2 Prefix-safety proposition

Let `Safe_F(T)` be a deterministic predicate stating that transcript `T` passes a fixed, versioned set `F` of materiality and reconstruction checks. Suppose:

1. `Safe_F(T_0)` holds for the empty/base transcript;
2. before every release `r_i`, one canonical enforcement path constructs the actual candidate prefix `T_i = T_{i-1} ⧺ r_i` including all known channels;
3. release occurs only if the verifier returns `Safe_F(T_i)`;
4. history cannot be removed or rewritten without a new correction/supersession event;
5. the owner can reproduce membership, chronology, current heads, inputs and verifier version.

Then every released prefix satisfies `Safe_F`.

**Proof.** By induction. The base case is premise 1. For step `i`, premise 3 permits release only after `Safe_F(T_i)` is established for the complete candidate prefix. Therefore the released prefix is safe under `F`. Append-only custody preserves the evaluated prefix for reproduction. ∎

### 6.3 What the proposition does and does not establish

It establishes a falsifiable procedural statement:

> Every released prefix was evaluated prospectively against the declared check family and actual known transcript; no post-hoc narrowing or silent removal was used to manufacture a pass.

It does **not** establish:

- a probability of non-disclosure;
- differential privacy;
- completeness of the attack family;
- protection against unknown auxiliary information;
- legal compliance;
- institutional competence;
- publication authority.

The frontmatter and public rendering must carry those limits.

### 6.4 Adaptation

Adaptive choice of the next disclosure is permitted under this no-number discipline because the verifier checks the actual history-selected release against the complete prefix. Adaptation does not invalidate a deterministic prefix predicate.

It would invalidate a numeric theorem unless the chosen mechanism had a local guarantee valid conditional on that history and the aggregate bound were pathwise — exactly the premise required by `INT-K07`. No such guarantee is claimed here.

## 7. Screenshot, deep-link and export threat model

### 7.1 Protected assets

- confidential/personal evidence and identities;
- withheld claims, cells, attacks and counterevidence;
- reviewer/expert deliberation and dissent details;
- private provenance/CAS/tenant references;
- embargoed material and sealed/gold payloads;
- the honest scope, limitations, denied uses, negative outcomes and chronology of public claims.

The last category is integrity rather than secrecy: losing it creates authority distortion.

### 7.2 Threat actors

- unauthenticated public observer;
- user with one legitimate audience role;
- user with several roles or delegated access;
- colluding PUBLIC/REVIEWER/EXPERT/MACHINE recipients;
- insider with logs, analytics, cache or export access;
- crawler, archive, search index or link-preview service;
- recipient of a copied deep link, screenshot, printout or downloaded file;
- temporal observer comparing versions;
- adversary with public auxiliary datasets and dictionaries.

### 7.3 Deep-link finding

The current frontend serializes the complete public packet, base64url-encodes it, and places it inside the URL path before client-side verification (`publicationPacket.ts:1019-1174`). That means the URL is itself a copy of the release, not merely a locator.

Consequences:

- browser history, copied URLs, referrer headers, server/proxy logs, analytics, support tickets and link previews may receive the packet;
- a UI-hidden field remains recoverable from the URL;
- URL-length and changes can become side channels;
- revoking a page does not recall copied payload-bearing links.

INT-R8's semantic requirement is that every deep-link representation be included in the release transcript and contain only approved public content. A future architecture may use an opaque handle, but this research does not fix route or proof mechanics.

### 7.4 Screenshot/print requirements

A screenshot or printout detaches visible prose from hover text, collapsible panels, linked receipts and later corrections. Therefore every self-contained capture of a claim must visibly preserve or repeat:

- record/release identity and version/currentness;
- claim type and outcome, including negative terminal;
- material scope/basis and `delta` rider where applicable;
- material limitations/conditionality;
- denied uses;
- contest/dissent indicator where material;
- omission/redaction indicator;
- stable route/reference for current status and fuller authorized record.

A caveat available only through hover, another tab or a link is not screenshot-safe. Responsive layouts, print CSS and accessibility views must not drop these elements.

### 7.5 Export requirements

Every HTML/PDF/DOCX/JSON/CSV/clipboard export is a separate release event and must:

- consume an already accepted receipt for the exact rendered content;
- preserve the minimum retained set and authority boundary;
- include version/current/superseded state;
- remove hidden DOM, comments, document properties, revision history, embedded attachments, source maps and private refs unless explicitly approved;
- be checked together with prior exports for differencing;
- use canonical redaction reasons;
- fail when the export renderer drops a limitation, denied use, dissent indicator or negative terminal.

“Same data, different format” is not assumed: pagination, truncation, alt text, metadata and formula cells can change the disclosure channel.

### 7.6 Cache, archive and correction

A corrected page does not erase an archived/screenshot/exported predecessor. The transcript retains both. A current release must visibly identify supersession and avoid silent overwrite. Correction notices must not reconstruct the protected original through an unrestricted before/after diff.

## 8. Gate matrix

| Candidate event | Required check | Blocking result |
|---|---|---|
| First PUBLIC projection | Semantic parity + single-view reconstruction + all delivery channels | Any material omission or reconstructed predicate |
| REVIEWER/EXPERT/MACHINE projection | Per-view contract + declared coalition transcript with existing releases | Joint reconstruction |
| Revision/correction | Full temporal prefix, before/after notice and current-head integrity | Differencing or hidden negative/superseded state |
| Deep link | Decode/inspect the actual URL representation as content | Unapproved field or joinable private reference |
| Screenshot/print layout | Viewport/print fixture preserves visible minimum set | Limitation/use/status disappears |
| Download/export | Rendered bytes and metadata scan; transcript append | Hidden metadata, private ref, loss of mandatory semantics |
| Hash/ETag change | Dictionary/equality-oracle tests under declared threat model | Protected membership/persistence inferred |
| New provenance pointer | Cross-audience join analysis | Protected identity/content joined |

## 9. INT-R7 interface dependency

INT-R8 requires INT-R7 to make the following verifiable without choosing the construction:

- a release proof binds source revision, audience, retained-item set, typed omission classes/reasons, loss verdict, rule version and transcript head;
- redaction is a well-defined transformation of the bound object;
- the proof remains verifiable after permitted redaction;
- the proof does not expose dropped content through raw hashes, identifiers or commitments susceptible to the declared inference attacks;
- current/superseded state and anti-equivocation can be checked.

Algorithms, keys, rotation, revocation, long-term validation and anti-equivocation design are outside INT-R8.

## 10. Result standing

**`accepted_narrow_scope`.** Cross-view and temporal reconstruction are formally specified using consistency sets and actual transcripts. A deterministic, owner-verifiable prefix discipline is available now as a no-number procedural claim. A numeric repeated-disclosure budget is expressly refused until a future task supplies and enforces a valid mechanism-specific theorem.
