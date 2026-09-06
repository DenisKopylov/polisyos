# Data Capability Requirements

Freshness: 2026-09-06
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
