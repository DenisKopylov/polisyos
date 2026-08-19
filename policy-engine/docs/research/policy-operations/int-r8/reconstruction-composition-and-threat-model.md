---
title: "INT-R8 cross-view reconstruction, composition refusal, and release-channel threat model"
research_id: INT-R8
artifact_role: formal-analysis-and-threat-model
status: accepted_narrow_scope
amendment_conformance: pending_independent_verification
research_only: true
repository: DenisKopylov/polisyos
baseline_ref: main
baseline_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
audited_head: 90b372964d29a9e97605a6ef733ef03ffe7938d2
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

# INT-R8 cross-view reconstruction, composition refusal, and release-channel threat model

## 0. Controlling amendment notice

This artifact executes R3-R6. It preserves audit commendations
`INT-R8-III-001`, `III-003`, `III-005`, `IV-001`, and `IV-004`, while correcting the scope defects
in `III-002`, `III-004`, `III-006`, `IV-002`, and `IV-003`.

The audited version remains available at commit
`90b372964d29a9e97605a6ef733ef03ffe7938d2`. This version controls where the two differ.

## 1. Composition result, corrected

**INT-R8 establishes no numerical disclosure-composition guarantee.**

The controlling conclusion is:

> No canonical numerical disclosure-composition claim is justified for the current PolicyOS
> release path under any model established in the repository.

This conclusion does not rely on deterministic publication being mathematically incapable of
quantitative leakage. Deterministic channels can be assigned maximal-leakage, maximal-alpha,
statistic-maximal-leakage, min-entropy, or generalized-gain values when the required model exists.
The pinned repository establishes none of the complete models required to issue such a value.

### 1.1 Premise audit by model family

| Family | Required premises | Pinned PolicyOS state | Verdict |
|---|---|---|---|
| Differential privacy | Neighbor relation; randomized mechanism; local `(epsilon, delta)` guarantee; prospective allocation; history-valid accountant | None established for the editorial projection | No DP theorem transfer. |
| Maximal leakage | Secret/random variable or support; channel; adversarial guessing objective; local channel value; applicable composition relation | No canonical secret/channel/value owner | No current scalar. |
| Maximal-alpha leakage | Secret/channel; alpha-loss objective; support/prior treatment; local alpha-leakage; weak-composition premises | None established | Candidate future research only. |
| Statistic maximal leakage | Named protected statistic; prior/support treatment; deterministic or randomized channel; local value and composition rule | None established | Candidate future research only. |
| Min-entropy / g-leakage | Secret distribution/support; vulnerability or gain function; channel; local and composed analysis | None established | Candidate diagnostic family only. |
| Exact consistency sets | Declared nonempty model; observation relation; total protected predicate; exact or proved-conservative decision | Research contract supplied here for bounded models | Adopt as Boolean gate, not scalar budget. |

Primary mathematical anchors and transfer limits are in
`external-source-and-transfer-ledger.md`: DOI `10.1109/TIT.2019.2962804`, DOI
`10.1109/TIT.2019.2935768`, DOI `10.3390/e28070819`, DOI
`10.1007/978-3-642-00596-1_21`, and DOI `10.1109/CSF.2012.26`.

### 1.2 Why no present number is justified

The pinned repository has no canonical:

1. protected secret/statistic family;
2. release channel including side channels and accumulated history;
3. prior/support or worst-case support semantics;
4. adversarial gain/loss package;
5. locally valid per-release leakage quantity;
6. prospective acceptance/allocation rule;
7. composition theorem for the actual history-selected sequence;
8. accountant reproducing membership, chronology, current heads, model versions, local values,
   and aggregate result; or
9. authority boundary for the number.

A differently named scalar would have the same defect. This artifact authorizes none.

## 2. Declared record and observation model

Let:

- `M` be a versioned record-model identifier;
- `R_M` be the nonempty set of full records admitted by `M`;
- `A = {PUBLIC, REVIEWER, EXPERT, MACHINE}` be the canonical audience set;
- `F` be a versioned declared release family under custody;
- `K` be a versioned coalition/delegation model stating which audiences and channels an
  adversary may obtain;
- `B` be a versioned auxiliary/background-information model with an explicit incompleteness
  statement;
- `P_i` be the content transformation selected at event `i` after observing prior controlled
  history;
- `O_i(r)` be the complete observation emitted for record `r` by the controlled event, including
  its registered side channels;
- `T_i` be the controlled transcript prefix through event `i`; and
- `Q` be a finite or otherwise exactly decidable protected-predicate family.

The model does not assume that every possible external observation is controlled. That boundary
is stated explicitly in `F` and the transcript-completeness disposition.

## 3. Declared release family under custody

`F` partitions disclosure observations into three classes.

### 3.1 Controlled registered releases

These are events for which the designated custody path must reproduce membership, ordering,
source/current heads, exact public object or observation, rule/model versions, and verifier
result. Candidate classes include:

- server/API responses registered for release;
- PUBLIC, REVIEWER, EXPERT, and MACHINE projections;
- generated deep links;
- registered HTML/PDF/DOCX/JSON/CSV/clipboard exports;
- registered screenshots and print objects;
- controlled notification/syndication outputs;
- controlled cache, header, length, and error behavior included by the channel registry;
- correction, withdrawal, supersession, and currentness notices; and
- proof objects and proof metadata emitted for that release.

Missing, deleted, or reclassified controlled history yields
`compression_transcript_membership_not_reproducible` and blocks.

### 3.2 Observed external copies

A third-party cache, copied screenshot, external archive, search snippet, FOI release, litigation
disclosure, or other external copy becomes part of the transcript when it is discovered and
admitted with a source, observation, and uncertainty disposition. Admission extends the history;
it never deletes the controlled predecessor.

### 3.3 Uncontrolled or unknown channels

Unobserved recipient copies, covert exfiltration, unknown institutional disclosures, unknown
archives, and unknown auxiliary datasets cannot be reproduced by a PolicyOS owner. They are not
silently treated as absent. The transcript carries one of:

- `complete_for_declared_controlled_release_family`;
- `bounded_to_declared_release_family`;
- `observed_external_history_included`; or
- `external_history_not_established`.

Only the first is a complete statement about controlled membership. None is a universal claim
about everything anyone has ever observed.

## 4. Consistency set and exact reconstruction

For observed controlled transcript `t`, model `M`, release family `F`, coalition model `K`, and
background model `B`, define:

`C_{M,F,K,B}(t) = { r in R_M : Obs_{F,K,B}(r) = t }`.

Observational equality is part of the versioned model. It must cover every registered channel in
`F`, not only body text.

For total protected predicate `q : R_M -> V_q`, define the remaining-value set:

`V_q(t) = { q(r) : r in C_{M,F,K,B}(t) }`.

Exact reconstruction occurs when `|V_q(t)| = 1`.

### 4.1 Empty consistency set

If `C_{M,F,K,B}(t)` is empty, the model and observed transcript are inconsistent. This is neither
safe nor reconstructed. Required finding:

`model_observation_inconsistent` -> `blocked_material_omission`.

An empty set may indicate an incomplete model, an unregistered channel, a wrong source revision,
a renderer mismatch, or corrupted transcript custody.

### 4.2 Strict cross-view reconstruction

For each individually obtainable audience transcript `t_a`, strict cross-view reconstruction of
`q` by coalition `S`, `|S| >= 2`, requires:

- `|V_q(t_a)| >= 2` for every `a in S`; and
- `|V_q(union_{a in S} t_a)| = 1`.

This is the exact local-safe/joint-unsafe property preserved by family F04.

### 4.3 Temporal reconstruction

For linked versions `t_i` and `t_j`, `i < j`, temporal reconstruction occurs when each snapshot
alone leaves at least two values possible but their combined retained history leaves one. A later
correction does not erase the prior observation.

## 5. Executability boundary

The set definition is mathematically meaningful more broadly than it is executable. An
operational pass is available only in one of these cases:

1. `R_M` is finite and exhaustively enumerable with a terminating observation function; or
2. `R_M` and observational consistency lie in a declared decidable symbolic fragment; or
3. a conservative abstraction has a proved **no-false-safe** direction for the exact obligation
   it is authorized to discharge.

No claim is made that arbitrary PolicyOS records, renderers, or auxiliary knowledge satisfy those
conditions.

### 5.1 Required verifier dispositions

| State | Exact meaning | Required finding | Loss outcome |
|---|---|---|---|
| `|V_q(t)| >= 2` decided exactly | Predicate not uniquely determined | `not_reconstructed_under_declared_model` | May pass privacy limb. |
| `|V_q(t)| = 1` decided exactly | Predicate uniquely determined | `reconstructed` | Blocked. |
| Consistency set empty | Model/observation mismatch | `model_observation_inconsistent` | Blocked. |
| Solver timeout/resource exhaustion | Exact result unavailable | `not_established_timeout` | Blocked. |
| Unsupported or undecidable theory | Model not executable by declared verifier | `not_established_unsupported_theory` | Blocked. |
| Proved-conservative abstraction reports risk | Possible or certain reconstruction under safe over-reporting | `conservative_risk_found` | Blocked. |
| Proved-conservative abstraction discharges its exact obligation | No false-safe direction is proved and obligation passes | `not_reconstructed_under_proved_conservative_abstraction` | May pass only in stated scope. |
| Sampling, classifier, posterior threshold, heuristic search, or unproved approximation | Error direction/calibration unowned | `not_established_unowned_approximation` | Blocked. |
| Registered channel absent from model | Observation family incomplete | `release_channel_out_of_model` | Blocked. |

### 5.2 No hidden estimator

The number-free theorem does not survive replacement by:

- a posterior-confidence threshold;
- a classifier score;
- sampled candidate-state coverage;
- “large enough” consistency-set cardinality other than exact non-uniqueness;
- a timeout interpreted as likely safe;
- an estimated false-negative rate; or
- a materiality score.

Each introduces a quantity, calibration, or error direction requiring separate validity and
ownership. Without that work, the result is `not_established`, not safe.

## 6. Information-theoretic diagnostic boundary

If a future research task declares random variables and a probability space, exact
reconstruction of `Z = q(R)` implies `H(Z | T) = 0`. Maximal, maximal-alpha, statistic-maximal,
min-entropy, and generalized-gain leakage may then be evaluated under their own definitions.

This observation does not supply a canonical PolicyOS distribution, gain function, statistic,
alpha value, channel, or composition rule. Those choices are substantive policy and threat-model
inputs, not formatting parameters.

## 7. Number-free prefix discipline

Let `G` be a fixed, versioned family of:

- semantic parity/materiality predicates;
- categorical `INT-K02` and `INT-K08` checks;
- exact or proved-conservative reconstruction obligations;
- controlled release-family completeness checks; and
- authority-boundary checks.

Let `Safe_G(T_i)` be a Boolean predicate stating that controlled transcript prefix `T_i` passes
all required checks with no `not_established` result.

### 7.1 Proposition

Suppose:

1. `Safe_G(T_0)` holds for the empty/base controlled transcript;
2. before every controlled release `r_i`, one canonical enforcement path constructs the actual
   history-selected prefix `T_i = T_{i-1} append r_i` with every registered observation;
3. release occurs only when `Safe_G(T_i)` is true;
4. controlled history is append-only logically, with correction/supersession events rather than
   deletion or reclassification;
5. membership, chronology, source/current heads, exact observations, model/rule versions, and
   verifier dispositions are reproducible; and
6. changes to `M`, `F`, `K`, `B`, `Q`, or `G` create a new version and do not retroactively
   manufacture passage.

Then every released controlled prefix satisfied `Safe_G` when released.

**Proof.** Base case is premise 1. At step `i`, premise 2 constructs the actual selected
candidate prefix, and premise 3 permits release only if that prefix satisfies `G`. Premise 4
preserves the evaluated prefix, and premise 5 permits reproduction. Therefore each released
controlled prefix passed. The argument is induction and does not assume non-adaptive release
selection. QED.

### 7.2 What the proposition proves

It proves:

- actual-prefix prospective checking;
- no local-only reuse after adaptive selection;
- no post-hoc removal of controlled history to manufacture a pass; and
- reproducible enforcement of the declared Boolean family.

It does not prove:

- completeness of the attack/channel family;
- secrecy against unknown external disclosures or auxiliary datasets;
- a probability of confidentiality;
- differential privacy or quantitative leakage bounds;
- legal compliance or institutional competence; or
- permission to publish.

### 7.3 Why it is not a budget

The exact privacy member asks whether at least two protected values remain possible. It has no
amount consumed, no remaining balance, and no threshold selected from a continuum. Repetition of
a Boolean predicate does not convert it into a budget. `INT-K04` applies only if a composed number
is later attached.

## 8. Open release-channel registry

The registry is versioned and open. A fixed prose list is not a completeness proof. Every channel
must be registered, deliberately out of model with a blocking disposition, or covered by a
proved general observation rule.

### 8.1 Existing channel families preserved

- visible projection/summary content;
- omission and redaction metadata;
- raw, semantic, or generated diffs;
- hashes, ETags, fingerprints, and commitments;
- ordering, rank, pagination, totals, and gaps;
- exact time, latency, and update cadence;
- provenance snippets and joinable identifiers;
- deep-link path, query, fragment, and encoded payload;
- screenshots, print, clipboard, and downloadable files;
- HTML/PDF/DOCX/JSON/CSV formulas, comments, revisions, attachments, and properties;
- accessibility tree, alt text, hidden DOM, embedded data, and source maps;
- HTTP headers, cache keys, lengths, logs, analytics, referrers, and errors; and
- current, stale, corrected, withdrawn, and superseded presentation.

### 8.2 Added channel family: locale and translation

**Attack.** The source language preserves a limiting rider while a translated/fallback locale
drops it, or translation-memory identifiers allow cross-locale reconstruction of protected text.

**Required observation.** Every released locale, fallback string, translation-memory reference,
alt-language export, and language negotiation outcome is a separate registered observation.

**Blocking finding.** `compression_locale_translation_channel`.

### 8.3 Added channel family: notification and syndication

**Attack.** Email, push, webhook, RSS/Atom, social/Open Graph card, chat integration, or link
preview publishes a shorter object that drops a caveat or reveals a hidden field.

**Required observation.** Inspect the exact outbound payload and metadata for every registered
syndication surface.

**Blocking finding.** `compression_syndication_channel`.

### 8.4 Added channel family: network and compression oracle

**Attack.** Content-encoding ratio, packet length, TLS record count, range behavior, or
conditional-request response distinguishes low-entropy protected states.

**Required observation.** Register the observable transport/encoding classes in the declared
threat model or return out-of-model. No universal traffic-analysis protection is claimed.

**Blocking finding.** `compression_network_oracle_channel`.

### 8.5 Added channel family: discovery and indexing

**Attack.** Sitemap entries, search index state, autocomplete, snippets, result counts, archive
status, or cache invalidation reveals existence/category/currentness of a protected record.

**Required observation.** Registered discovery outputs and known third-party observations enter
the transcript; unknown external indexing limits completeness.

**Blocking finding.** `compression_discovery_index_channel`.

### 8.6 Added channel family: proof metadata

**Attack.** Key ID, certificate path, transparency-log position, witness set, proof size,
commitment identifier, or renewal pattern joins audiences or reveals issuer/reviewer/revision
identity.

**Required observation.** INT-R7 proof artifacts and metadata are content-side disclosure
channels. They must be included in the candidate observation and must not reconstruct a protected
predicate.

**Blocking finding.** `compression_proof_metadata_channel`.

INT-R8 states the requirement only. INT-R7 owns the construction and mitigation.

## 9. Threat actors and assets

### Assets

- confidential or personal evidence and identities;
- withheld claims, cells, attacks, and counterevidence;
- reviewer/expert deliberation and dissent detail;
- private provenance, tenant, artifact, and custody identifiers;
- embargoed, sealed, hidden, or gold payloads;
- honest scope, limitations, denied uses, negative outcomes, chronology, and currentness; and
- semantic model identities whose substitution could manufacture a safe verdict.

### Actors

- unauthenticated public observer;
- one-role authorized recipient;
- multi-role/delegated recipient;
- colluding audience recipients;
- insider with logs, cache, analytics, proof, or export access;
- crawler, search index, archive, preview, translation, notification, or syndication service;
- recipient of copied deep link, screenshot, printout, or file;
- temporal observer comparing versions; and
- adversary with dictionaries or public auxiliary datasets.

## 10. Gate matrix

| Candidate event | Required check | Blocking result |
|---|---|---|
| First controlled projection | Semantic parity, single-view reconstruction, registered channels | Material omission, reconstruction, or not-established model |
| Additional audience view | Per-view checks plus coalition prefix | Joint reconstruction |
| Revision/correction | Full temporal prefix and currentness | Differencing, history deletion, or false currentness |
| Deep link | Decoded full representation | Unapproved hidden field or join key |
| Screenshot/print | Exact rendered object and accessible representation | Missing minimum semantic |
| Export | Bytes, formulas, comments, metadata, and prior-export differencing | Hidden protected value or dropped qualifier |
| Locale/translation | Every language/fallback object | Semantic divergence or cross-locale join |
| Notification/syndication | Exact outbound payload | Dropped caveat or hidden field |
| Transport/encoding | Declared observable network class | Low-entropy state oracle or out-of-model |
| Discovery/index | Registered search/sitemap/preview output | Protected existence/category inference |
| Proof object | Proof bytes and metadata | Protected identity/content join |
| Unknown channel | Channel-registry classification | `release_channel_out_of_model` |

## 11. INT-R7 interface implication

The proof side must be able to bind the semantic model identities and exact transformed objects
without choosing content. It must also avoid turning hashes, commitments, key identifiers,
certificate chains, log positions, witness sets, or proof sizes into protected-value oracles.

A failed INT-R8 relation blocks public projection faithfulness. It does not negate an otherwise
established issuer-side issuance event. Issuance authenticity, projection faithfulness,
public-history establishment, durable verifiability, and current authority are separately
reportable dimensions. This is aligned with audit finding `INT-R7-VIII-003`, not with unverified
adjacent prose.

## 12. Formal standing

The formal result remains `accepted_narrow_scope`:

- exact consistency-set reconstruction is valid for declared finite/decidable models;
- a proved no-false-safe abstraction may inherit only its exact authorized obligation;
- all other approximation returns blocked/not-established;
- prefix discipline is adaptive and number-free over the declared controlled release family;
- uncontrolled external history limits rather than falsifies the scoped claim; and
- no numerical quantity is issued or owed.
