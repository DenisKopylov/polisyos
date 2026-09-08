# Data Capability Requirements

Freshness: 2026-09-07
Owner: `architect`
Source of truth: this file; every row's evidence lives in the journal or register entry it cites

## Why this file exists

PolicyOS is built to reach the point where it stops being limited by code and starts being limited
by data. That is not a failure mode — it is the intended destination. The system's real work is
producing the best policy design for a user's request, and once the code capability for that exists,
the remaining growth is in **how much data we have and what shape it is in**.

This file is the standing answer to one question: *what data does the system need, in what form, to
use a capability we have already built?* It is filled progressively, from measurement. When a code
capability is examined, this file should already say what data that capability is waiting for.

It is deliberately **not** a wishlist, a collection backlog, or a data-source catalogue. It records
requirements that a real consumer in this repository already imposes, discovered by a real
encounter.

## The rules that keep it honest

1. **Every row carries a measured basis** — a count, a date, and where it was measured. A row with
   no measurement is not a requirement; it is a guess, and guesses belong in the research backlog.
2. **Every row names its consumer** with a code anchor. "The system needs better data" is not a row.
   "`CausalClaim` at `ir/analytics/literature.py:437` rejects the stored vocabulary" is.
3. **Absent data and wrong-shaped data are different problems.** Most of what we have hit is the
   second. Collecting more of the same data does not fix a vocabulary collision.
4. **Preprocessing is part of the requirement, not an implementation detail.** A judgment that is
   recomputed at read time instead of persisted is a different artifact from one that is stored, and
   only one of them can be replayed.
5. **`unmeasured` is a legitimate status** and is always better than a confident guess. Say what has
   not been looked at.
6. Rows are **append-only in spirit**: when a status changes, record the change and its new basis
   rather than overwriting the old one, so the history of what we believed stays readable.
7. **A missing dataset never stops the capability from being built.** This is the same ruling that
   governs institutional absence: an absence binds the **authority of the output**, never the
   permission to build. Where developing, testing or debugging a capability needs data we do not
   have, build it against **structurally similar synthetic data**, marked as synthetic in the
   artifact itself and not only in a journal, and record the real requirement here. A capability
   that exists and waits for data is worth more than a correct plan for one that does not, because
   nobody adopts a system they cannot run. The marking is not a formality: an unmarked synthetic
   input that reaches a governed surface is a fabricated record, which is a different and much
   worse thing than an honest placeholder.
8. **Usefulness is a requirement, not a concession.** When the data will not support the claim we
   wanted, lower the ambition, the authority and the focus of the claim until it is one the
   evidence carries — and then ship that. A narrower honest output still beats the intuition that
   policy-making runs on today; refusing to output anything does not.

## Status vocabulary

| status | meaning |
| --- | --- |
| `absent` | the data does not exist in any production artifact |
| `present_wrong_vocabulary` | the data exists, but its meaning does not match the consumer's contract |
| `present_wrong_preprocessing` | right vocabulary, wrong form — typically a judgment that was never persisted |
| `present_stale` | the data exists but predates the schema that defines what it must contain |
| `present_insufficient` | correct and current, but below a threshold the consumer requires |
| `satisfied` | production data meets the consumer's requirement, measured |
| `unmeasured` | nobody has looked yet |

## Summary

| id | consumer | status |
| --- | --- | --- |
| `span-grounded-claims-with-persisted-entailment` | first governed promotion (N7 admission) | `absent` |
| `causal-claim-current-contract-vocabulary` | `CausalClaim` / academic SKG ingest | `present_wrong_vocabulary` |
| `extraction-strength-mixes-confidence-and-design` | any consumer of `extraction_json` | `present_wrong_vocabulary` |
| `cg2-calibration-observations-per-stratum` | CG2 grounding calibration | `absent` |
| `snapshot-schema-generation-discriminator` | Academic shadow consumer of a pinned snapshot | `present_stale` |
| `lex-amendment-effective-from` | Lex chronology valid-effect carrier | `present_insufficient` |
| `claim-level-evidence-axis` | the whole academic confidence layer | `absent` |
| `lever-legal-subject-key-in-the-norm-namespace` | `GY-S3` law-to-lever recognition rule | `absent` |

---

## `span-grounded-claims-with-persisted-entailment`

**Consumer.** The first governed promotion: N7 admission consumes span-grounded claims, and CG2
resolves calibration against them.

**What is required.** Claims bound to specific text spans in specific papers, each carrying a
**persisted positive entailment verdict** — the judgment that the span actually supports the claim,
stored as an artifact rather than recomputed when read.

**Status `absent`.** Measured 2026-09-02 (GY-PR1a closeout): no persisted positive span-entailment
receipt exists anywhere in the substrate. `span_support_client=None` is not a bypass — it attempts
the real gateway and fails closed — but the only positive path in the tree injects a deterministic
test client, which is not production authority.

**What would satisfy it.** Run the entailment judge against the corpus and persist its verdict per
claim. This is the preprocessing requirement in its purest form: the data cannot be collected, only
produced, and producing it without storing the verdict leaves the requirement unmet.

---

## `causal-claim-current-contract-vocabulary`

**Consumer.** `CausalClaim` at `src/polisyos/ir/analytics/literature.py:437`
(`ConfigDict(extra="forbid")`), and `ingest_openalex_span_grounded_claims` at
`src/polisyos/data_forge/domains/academic/knowledge/skg_store.py:640`, which takes claims as input.

**What is required.** Stored claims in the vocabulary the contract accepts.

**Status `present_wrong_vocabulary`.** Measured 2026-09-02 by complete census: all 310,829
`ac_article_extractions` payloads parse, yielding **137,714** claims, and every one uses the legacy
shape `{cause, direction, effect, mechanism, strength}`. `_normalize_causal_claim_payload` already
maps `cause` -> `cause_variable` and `effect` -> `effect_variable`, so the contract *almost* accepts
the stored form; `strength` and `mechanism` are unmapped and `extra="forbid"` rejects them.
`mechanism` is empty on 130,101 of 137,714.

**What would satisfy it.** Re-extraction into the current contract, or an explicit migration that
maps each legacy key to a field it genuinely means. **A two-line alias is not that migration** — see
the next row for why.

**Second consumer added 2026-09-08 — `CORR-R4`, and it wants a different thing from the same
rows.** The constructibility census asked whether an external causal claim can be bound to a typed
causal atom *by construction*, without an adjudicator. Package-reported and unaudited: **0 of
7,868** canonical independent causal claims and **0 of 137,589** raw claims can, because the stored
shape carries no typed intervention expression, no estimand and no identification plan — the three
things a construction would have to compare. The internal seam is **3 of 3** constructible, so the
mechanism works exactly where an adjudicator was never needed. This is not a volume problem and
more rows of the same shape will not move it: it is `present_wrong_vocabulary` for a second,
stricter consumer.

**What would satisfy that consumer.** Claims carrying a typed `InterventionExpr`, an estimand and
an identification plan, with the producer independent of the binding claim. **Build it on marked
synthetic claims first** — the producer, its `unresolved` path and its falsifier can all be
developed and tested against structurally similar synthetic input, and that work does not wait on
the corpus. Routed as `CORR-B2`; **no owner exists** for the semantic producer.

---

## `extraction-strength-mixes-confidence-and-design`

This row is not about the first governed promotion and outlives it. It affects any consumer that
reads `ac_article_extractions.extraction_json`.

**What is required.** One field, one measure.

**Status `present_wrong_vocabulary`.** Measured 2026-09-02 over the complete population of 137,714
claims. The stored `strength` key mixes a **confidence scale** and a **study-design vocabulary**
under one name:

| value | claims | is it a study design? |
| --- | ---: | --- |
| `moderate` | 69,923 | no — a confidence adjective, not an enum member at all |
| `observational` | 41,521 | yes |
| `theoretical` | 17,688 | no — an enum-accepted fallback, not one of the eight design labels |
| `meta_analysis` | 3,499 | yes |
| `quasi_natural` | 2,109 | yes |
| `unknown` | 1,813 | fallback |
| `rct` | 899 | yes |
| `panel_fe` | 255 | yes |
| `cross_sectional` | 7 | yes |

`EvidenceStrength` is a study-design vocabulary: `rct`, `quasi_natural`, `quasi_natural_event`,
`meta_analysis`, `panel_fe`, `structural`, `observational`, `cross_sectional`. Aliasing `strength`
onto it would **outright reject** the 69,923 `moderate` claims and **silently misclassify** the
17,688 `theoretical` ones — 87,611 affected, 63.6% of the population.

**The general lesson, which is the reason this row is here:** a field name does not identify a
vocabulary. The only safe reading of this column is to treat the name as meaningless and the values
as evidence.

**What would satisfy it.** Separate the two measures into two fields **at extraction time** —
a design classification and a confidence judgment — so no consumer has to guess which one a value
belongs to. No name-based mapping over the existing column is safe.

---

## `cg2-calibration-observations-per-stratum`

**Consumer.** CG2 grounding calibration in `src/polisyos/runtime/quality/grounding_bind.py`.

**What is required.** At least **20** observations per
`operator_family | reference_region | relation_type` stratum, from a production-owned source.

**Status `absent`.** Production resolution returns an empty calibration ledger; the only admitted
anchor is `cg2_contract_seed_anchor` with `authority_scope="contract_testing"`, which is
deliberately not production evidence. CG6 was checked as an alternative and is a **proven-closed
door**: ten anchors against a twenty-per-stratum requirement, with incompatible provenance.

**What would satisfy it.** A genuine production-owned calibration source. Whether one can exist at
all was never established — that measurement was the first act GY-PR1a never reached.

**Requirement restated 2026-09-08 after the CORR wave, and it grew by more than an order of
magnitude.** The **20 per stratum** above was never derived from a target error rate. Under an
exact one-sided binomial bound with zero observed confident-wrong events, a `0.01` ceiling at
`alpha=0.05` needs **`n = 299`** adjudicated positives per stratum. Two things follow and both are
harder than the number. First, CGF appendix E.4 declares the minimal stratum as seven keys —
`operator_family, target_type, domain, proposer_model, prompt_version, atom_birth_cohort,
reference_epoch` — so the cross-product at 299 per cell is unaffordable, and `proposer_model` and
`prompt_version` mean **a model or prompt change invalidates the stratum**. Second, positives
require an adjudicator this project does not have; constructed negatives are free but calibrate
a different quantity. The eligible frame itself is also missing: no enumerable population with
source-cluster identity and an **outcome-blind** difficulty tier exists, and a stratum chosen after
seeing which bindings succeeded is blocked by `INT-K07` regardless of engineering.

**What would satisfy it, in the order the work actually goes.** A dated pre-outcome manifest naming
the eligible frame with its complete denominator, the source-cluster unit, and the difficulty tier
declared without looking at outcomes — that part is buildable now and needs no adjudicator. Then a
stratification coarse enough to afford and demonstrably not vacuous across that tier. Only then the
adjudicated labels. **The refusal-sensitivity suite is not a substitute and must not be counted
here**: constructed mismatches bound the sensitivity of refusal, never the correctness of
acceptance. Register rows `delta-ground-composition-and-stratum-budget` and
`adversarial-refusal-sensitivity-is-publishable-today` carry the decisions.

**Architect decision applied by CORR, 2026-09-08.** The preceding seven-key
stratum description is superseded by `delta-ground-composition-and-stratum-budget`:
the stratum is `operator_family × target_type × domain × difficulty_tier`, with
the tier derived from inputs before outcomes. Proposer model, prompt version,
atom birth cohort and reference epoch scope the certificate; a change stales it.
The run's configured relation-admission reserve is 0.04, with a per-admission
ceiling of 0.01; candidate exploration consumes none. These are planning
parameters, not calibrated correctness bounds. The remaining construction
reserve is shared, without a new component allocation in this lane. The frame
and refusal-sensitivity mechanism are engineering deliverables; neither supplies
the missing adjudicated positive observations. Execution evidence is maintained
in `docs/superpowers/journals/2026-09-08-corr-a.md`.

---

## `snapshot-schema-generation-discriminator`

This is a metadata requirement rather than a content one, and it is the generalisation of the most
expensive thing measured this week.

**Consumer.** Every consumer of a pinned production snapshot.

**What is required.** A snapshot must record the schema generation it was built under, so a
consumer can detect drift **as drift** instead of encountering it as a missing table.

**Historical status `absent`.** Measured 2026-09-02: the pinned Academic SKG snapshot was built 2026-04-11; the
table a consumer required entered the schema on 2026-06-28, two and a half months later. Because
`ensure_skg_schema` creates tables `IF NOT EXISTS`, the absence was indistinguishable from a
deletion, and nothing anywhere detected the divergence. A related instance is registered separately
as `trust-claim-posture-receipt-stale-on-any-src-change`.

**Status `present_stale`; discriminator capability implemented for the Academic shadow boundary
(2026-09-02).** Graph load now persists, in the same run that materializes the schema, a canonical
content-bound generation basis over `SKG_DDL` and its compatibility alters. Publish carries that
receipt unchanged and refuses to mint one when the graph-stage receipt is absent. The graph receipt
also binds the materialized `ac_skg_%` table/column structure; publish and the shadow consumer each
recompute that live structural identity before accepting readiness. Missing, malformed, changed, or
structurally mismatched bases set
`schema_generation_current=false`, make `consumer_ready=false`, and name both the recorded and
current generation and rule version. The historical pinned fixture is deliberately not
retroactively blessed: it now reports
`recorded_generation=unrecorded` rather than failing later as a missing table. Reissuing the
read-only production snapshot through the repaired producer would move this data requirement to
`satisfied`; other snapshot families must adopt the same producer/consumer discipline for their own
boundary.

---

## `lex-amendment-effective-from`

**Consumer.** Lex chronology's valid-effect carrier (registered as
`gy-n12-lex-amendment-valid-effect-carrier`).

**What is required.** A non-empty `effective_from` — when an amendment takes effect, as distinct
from when the row was written.

**Status `present_insufficient`.** Complete production census: **156,196** `lex_amendments` rows, of
which **152,636** carry no non-empty `effective_from`. All 156,196 have `created_at`.

**What would satisfy it.** Collection or derivation of the valid-time window at ingest. The
consumer's current behaviour is correct and should not change to accommodate the gap: chronology
keeps every row in the owner denominator and reports
`amendment_valid_effect_window_unresolved` rather than substituting transaction time for valid time.

---

## `lever-legal-subject-key-in-the-norm-namespace`

**Consumer.** The `GY-S3` law-to-lever recognition rule, and the intervention bundle at
`production_data/ukraine_agent_simulation_baseline_20260410/production_bundle/bundles/intervention_bundle_v1/lex_intervention_map.json`.

**What is required.** A legal-subject identity on the **lever** side, in the **same namespace** as
the legal norm's own subject identity, versioned and temporally scoped, so that a declared mapping
such as `budget_law -> budget_allocation_multiplier` can be checked against the subject the statute
actually regulates.

**Status `absent`.** Measured 2026-09-08. L3 carries legal-subject semantics; the L6 lever bundle
carries none, and the native L3 store holds no intervention, mapping, crosswalk or adjudication
table. The consequence is measurable rather than theoretical: transposing real budget and tax
threshold targets, while preserving registry uniqueness and every declaration, still returns
`admissible` for the wrong legal subject, because the check that admitted the mapping was *the
provision exists and carries a threshold*. Units, ranges, thresholds and registry uniqueness
**cannot repair a missing semantic dimension** — they are the wrong kind of fact. Package-reported
and unaudited: **0 of 3** executable law-to-lever pairs and **0 of 374,516** L3 threshold rows can
complete a subject-aware proof against the current lever schema.

**What would satisfy it, and the trap that makes this harder than a schema change.** The key must be
**independently authoritative** — minted by the party that owns legal-subject identity, not by the
producer whose declaration it is supposed to verify. A `legal_subject_id` the mapping's own author
writes is circular and closes nothing; it would authenticate the assertion without establishing it.
The mechanical comparison is ownable today by `GY-S3 / foundry`; the semantic authority that mints
the identity has **no owner**, routed as `CORR-B1`.

**Buildable now, on marked synthetic.** The recognition rule, the subject-aware comparison and the
transposition falsifier can all be developed and tested against a synthetic subject spine, clearly
marked as synthetic in the artifact, before any authoritative source exists. That work is what
turns the eventual data acquisition into a wiring task instead of a design task — and the falsifier
is the deliverable that proves the rule rejects a transposed pair rather than merely accepting a
correct one.

---

## Adding a row

Write the consumer and its code anchor first, then the measurement, then the status. If you cannot
write the measurement, the status is `unmeasured` and the row says so. If a status changes, append
the new basis under the row rather than editing the old one away.

---

## `claim-level-evidence-axis`

**Consumer.** `_infer_edge_strength` at
`src/polisyos/data_forge/domains/academic/batch/graph_builder.py:659`, which reads only an explicit
`evidence_strength` / `evidence_strength_status`, and `aggregate_edge_confidence` at
`src/polisyos/data_forge/domains/academic/knowledge/skg_store.py:519`, which filters any claim whose
class carries no positive base weight **before** noisy-OR and before the replication bonus. Every
academic edge confidence in the substrate flows through those two.

**What is required.** Stored claims carrying an explicit evidence class, supplied by the extractor
rather than inferred downstream from an adjudicated design — the axis B-1 and B-2 made mandatory.

**Status `absent`.** Measured 2026-09-05/06 (historical-cohorts lane, Events 1-23). A complete walk
of all **310,829** `ac_article_extractions` documents and all **137,714** embedded claims finds
**zero** claims carrying `evidence_strength` or its status; the 5,133 keys that do exist are in the
**parameter** namespace under `metadata.simulation_ready_numeric_estimates`. The consequence is
total, not partial: a current-rule computation over each stored aggregate's retained membership
differs for **every** row in **every** layer — exact **7,607/7,607**, family **15,945/15,945**,
contested **723/723** — with exact and family confidences computing to `0.0` and contested rows
failing emission entirely. The pinned snapshot's academic confidence layer is therefore historical
in full: no value in it is reproducible under the rule the system now holds.

**What would satisfy it.** Re-extraction with the current rich route, which **does** ask for the
axis — `CAUSAL_CLAIMS_SCHEMA_HINT` interpolated at `article_extractor.py:1558` requests one of six
evidence classes with worked examples — and whose transport was measured end-to-end to a confidence
of 0.55 on a controlled response.

**The input is already held, and this is the actionable part.** **310,710** of 310,829 works retain
a non-blank abstract, and the rich route accepts an abstract: `_fetch_full_text` returns it as
`abstract_fallback` at `:1529`, the `if not full_text.strip(): return None` gate at `:1786`
therefore passes, and `:1803` **downgrades rather than rejects** — `source_basis` ->
`ABSTRACT_ONLY`, warning `abstract_only_fallback`, extraction confidence x0.8 (x1.0 with a strong
design), citation tagged `[fallback:abstract_only]`. So re-extraction is runnable **today, on bytes
we already hold**, for essentially the whole corpus, at a quality the code marks honestly.

**Fulltext is the upgrade, not the precondition.** **67,262** of 137,589 raw claims were
fulltext-derived (529 abstract-only; 69,798 record no basis and are `ambiguous`, not zero), and no
fulltext is retained in the snapshot. Re-acquiring it would raise extraction quality above the
abstract-only band; it is a separate, separately ownable requirement, and nothing waits on it.

**Not measured.** The cost of a full re-extraction pass. It involves at least a screening call and
an extraction call per work plus a self-verification pass, and the lane was explicitly forbidden to
estimate it so that whoever plans the pass is not anchored by a number produced here. The 69,798
unrecorded `source_basis` cells are also unexplained.

**Known defect on the satisfying route, measured 2026-09-06.** Before any re-extraction runs,
`evidence-class-normalizer-zeroes-two-canonical-classes` must be repaired. The live ask requests all
ten evidence classes, but `_normalize_evidence_strength` at `article_extractor.py:396` has no alias
for the canonical `quasi_natural_event` or `structural` and maps both to `unknown` — weight 0.60 and
0.45 respectively, both to 0.0. A pass run today would therefore zero every study the model correctly
places in those two classes, across the whole corpus, and the result would be indistinguishable from
an absent axis. This is cheap now and becomes another historical layer afterwards.

**Register cross-reference.** `historical-confidence-carries-a-withdrawn-contribution` in
`docs/plans/active/DEBT-REGISTER.md`, whose two original closes — re-derivation from retained bytes,
or a per-row marker — are both dead: the first yields zero everywhere, and the second would be true
of all 24,275 rows and so would carry no information. Full measurement:
`docs/superpowers/journals/2026-09-05-historical-cohorts.md`.

**Registration, 2026-09-07.** This existing `absent` requirement is the registered re-extraction
requirement for `historical-confidence-carries-a-withdrawn-contribution`. Its execution owner
remains **unallocated**; registration appoints no owner and does not claim a completed data pass.
The accepted input basis is **310,710 nonblank abstracts / 310,829 works** (HC-F20), and
**67,262 fulltext-derived raw claims / 137,589 raw claims**, with fulltext not retained. The
architect's correction in the closure brief supersedes HC-F21/HC-D06's route inference:
`PolicyArticleExtractor` accepts held abstracts with the declared downgrade described above.
Fulltext reacquisition is a separate quality upgrade, not a prerequisite for abstract-only
re-extraction. These are accepted measurements, not a new census or a claim that every abstract
will yield an admissible claim.

**Acceptance for the data pass.** Persist each emitted claim's explicit candidate evidence class
and status, separately from extraction confidence and adjudicated design, together with source
basis, downgrade warnings, input provenance, and applicable schema/rule version. Exercise the
existing claim ingestion and exact/family/contested reassembly consumers against those artifacts,
and validate both admitted and rejected outcomes under the current vocabulary and publication
rules. No restoration of historical numbers, memberships, or edge identities is promised;
contested non-emission remains distinct from a zero final confidence. Preserve the sharper
**342 adjudication-contradicting rows / 7,868 published evidence rows** (HC-F06/HC-F07) as a
distinct subset, not merely instances of general unreproducibility.

**Limits and pattern pass.** Re-extraction cost remains `unmeasured`. The normalizer defect named
above remains a separate prerequisite repair, outside this registration. P01/P15 require persisted
candidate artifacts and demonstrated downstream consumption; P04 preserves absence, candidate
status, and non-emission; P35/P36 preserve the cited denominators; P29/P38 require behavioral
validation of the vocabulary and consumer outcome, rather than field-name presence. The data
requirement remains `absent` (`artifact_missing`) until the pass supplies and validates the
claim-level axis; registering it does not supply those artifacts.

**CORR correction before the bounded pass, 2026-09-08.** The normalizer prerequisite
above is historical: `evidence-class-normalizer-zeroes-two-canonical-classes` is
closed at `f876c26f2`, and its current owner tests passed on the CORR base. No
normalizer repair is included in this lane. The full held-work frame was
reconciled by a Python walk and independent SQL selection: 310,710 nonblank
abstracts out of 310,829 works, with equal eligible identity sets and no unreadable
cases in that measurement. A dated subset declaration freezes six input-selected
works before provider calls; it does not replace the complete corpus denominator.
The bounded pipeline and its cost measurement belong to `GY-PR1 / CORR-C1`;
authorization for a full pass remains a separate architect budget decision.
The declaration and current-normalizer evidence are linked from
`docs/superpowers/journals/2026-09-08-corr-c.md`. This correction does not claim
that re-extraction has supplied the corpus-wide missing axis.
