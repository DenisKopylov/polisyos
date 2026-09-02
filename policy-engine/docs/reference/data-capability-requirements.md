# Data Capability Requirements

Freshness: 2026-09-02
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
| `snapshot-schema-generation-discriminator` | every consumer of a pinned snapshot | `absent` |
| `lex-amendment-effective-from` | Lex chronology valid-effect carrier | `present_insufficient` |

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

**Status `absent`.** Measured 2026-09-02: the pinned Academic SKG snapshot was built 2026-04-11; the
table a consumer required entered the schema on 2026-06-28, two and a half months later. Because
`ensure_skg_schema` creates tables `IF NOT EXISTS`, the absence was indistinguishable from a
deletion, and nothing anywhere detected the divergence. A related instance is registered separately
as `trust-claim-posture-receipt-stale-on-any-src-change`.

**What would satisfy it.** A recorded schema generation per snapshot, and a consumer-side check that
compares it rather than discovering the mismatch through a failing query. This is cheap to add and
would have converted a stopped task into a one-line diagnosis.

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
