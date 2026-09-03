# Extraction-Strength Vocabulary Split Investigation and Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task by task. Start every behavioral change
> with its named red test. The data-production phases below are conditional and require a separate,
> explicitly authorized run; never point a writer at the pinned production snapshot.

**Goal:** Stop one generic `strength` field from mixing claim confidence, evidence/design class,
and study design; make the existing corpus honest without inventing claim-level designs; and keep
all future producer, persistence, graph, API, Foundry, Scientist, and Runtime paths semantically
separate.

**Architecture:** Reuse the distinct axes already visible in `CausalClaim`, but remove its unsafe
legacy defaults at the transport boundary. Every producer must emit a typed/versioned claim and
the common serialization/store admission boundary must reject generic `strength`; every reader
must consume a status- and provenance-bearing projection. Neither an extractor hint nor a row in
the receipt-less slim adjudication table is method authority. Nor is a shape-valid
`AdmittedClaimAdjudicationBatch` authority by itself: the current holder checks self-consistency
but does not replay the champion/evaluation/policy chain or establish non-producer verifier
provenance. The current champion replay is not an independent evaluation boundary either:
`persist_benchmark_evaluation` self-stamps a producer-component string over caller-authored
metrics/guardrails, and `admit_champion` trusts that string. Historical missing design is a
typed, countable `not_established`, not a guessed enum member. The no-data close is deliberately
fail-closed: it can expose candidate/audit data and invalidate or refuse authority-bearing legacy
artifacts, but it cannot reissue clean graph, prior, capability-index, or world-model-reference
artifacts, including the intermediate prior-knowledge, cross-graph, parameter, search, and policy
output bundles.

**Tech stack:** Python 3.14, strict/frozen Pydantic contracts, DuckDB opened `read_only=True`,
canonical JSON and SHA-256, pytest, Ruff, and the existing academic Data Forge/Scientist/Runtime
owners.

**Source basis:** branch `codex/debt-b-extraction-vocabulary`, HEAD and merge base
`fac07ffc6281e53e5a58c8a30c3b848a6b60e0e5`; 10,508 tracked paths, including 2,618 tracked
`src/**/*.py` files and 2,490 tracked `tests/**/*.py` files. All measurements below are from that
tree and the pinned snapshot, not from a search index.

## Executive Decision

The register's current phrase **“split at extraction time” is too narrow**. Extraction already has
the correct rich contract: `CausalClaim` carries `design_family_hint`, `evidence_strength`, and
numeric `claim_extraction_confidence` separately. The collapse occurs after and around that
contract:

1. the deterministic and selective-LLM producers still emit a different, untyped five-key claim;
2. the rich serializer renames `evidence_strength` to generic `strength`;
3. `WorkRecord.causal_claims: list[dict]` lets both shapes share one bridge;
4. the raw/final stores persist a generic `strength` column;
5. the graph consumer converts `causal_credibility` into an evidence/design class when it does not
   recognize the adjudication's design label;
6. the separate span-grounded SKG writer ignores `publish_to_graph=False` and promotes extractor
   candidate fields into `design_tier_authority`; and
7. public and Runtime consumers preserve or act on mislabeled categories, tainted confidence, and
   a categorical dissent field parsed as a number;
8. the sole adjudication-result loader treats forgeable manifest labels and self-declared lineage
   as authority, while champion replay accepts a coherently forged, self-stamped passing benchmark
   evaluation, so present-but-fake evaluation/pointer/batch chains can drive publication;
9. literal-free profile/index consumers can turn a stale `CrossGraphEvidenceProfile` or bare
   `CapabilityIndex` into parameter confidence, search rank, uncertainty, source availability,
   output lineage, or capability binding without resolving the academic projection epoch.

The **primary enforcement layer** is therefore the common claim serialization/store ingress, the
first boundary through which all producer variants must pass. Closure is nevertheless end to end:
the three producer paths must stop emitting the ambiguous key, every graph writer and snapshot
copy/promote path must pass the same admission boundary, the store must refuse it for new schema versions, and every consumer must
use explicit typed fields or the one provenance-bound legacy projection. Authority-bearing
adjudication is a second, narrower choke point: a candidate batch is resolved and content-bound,
then a named non-producing verifier authenticates an independently appointed evaluator receipt,
recomputes benchmark metrics/guardrails/promotion from its bound observation set, and replays the
complete champion/result predicate before Data Forge may materialize a publishability projection.
A producer-only repair
would leave the present snapshot and downstream API wrong; a consumer-only repair would allow the
next build to recreate the defect.

### Selected semantic model

Keep these properties separate:

| Property | Honest type | Authority at each stage |
| --- | --- | --- |
| Extraction reliability | `claim_extraction_confidence: float | None` plus basis status | candidate producer score; a paper score is not a claim score |
| Extractor's design guess | `design_family_hint: DesignFamily | None` plus basis status | candidate only |
| Extractor's evidence/ranking class | `evidence_strength: EvidenceStrength | None` plus basis status | candidate only; independent of design unless a separately admitted rule says otherwise |
| Adjudication's design output | `design_family: DesignFamily | None` plus receipt and authority purpose | candidate method label in the batch; even a verified publishability receipt expressly forbids use for `method_validity` |
| Adjudicated causal credibility | `causal_credibility: CausalCredibility | None` plus receipt | separately typed; never a methodology or evidence proxy |
| Edge publishability | `publishable_edge: bool | None` plus status and a resolved `ClaimAdjudicationBatchVerificationReceipt` that content-binds the candidate batch and an authenticated evaluation receipt | the batch declares only `academic_claim_edge_publishability`; authority remains `not_established` until the appointed non-producer verifier validates the evaluator appointment/signature, recomputes benchmark metrics/guards/promotion and the full batch result, and the holder verifies its provenance |
| Direction agreement | `dominant_direction_agreement: float | None` plus evidence/admission basis | existing producer-owned numeric agreement; never derived by parsing categorical dissent strength |
| Historical ambiguous word | `legacy_strength_label: str | None` in audit/provenance only | non-authoritative legacy evidence |

For the current 69,798 unique legacy claim identities, use:

```text
design_family_hint = null
design_family_status = not_established
evidence_strength = null
evidence_strength_status = not_established
claim_extraction_confidence = null
claim_extraction_confidence_status = not_established
source_basis = null
source_basis_status = not_established
legacy_strength_label = moderate
legacy_strength_producer_status = not_established
publishable_edge = null
publishability_status = not_established
may_publish = false
authority_effect = none
```

Use absence, not `DesignFamily.UNCLEAR` or `EvidenceStrength.UNKNOWN`, because either enum member
could mean that a producer actually evaluated the axis and returned an inconclusive result. The
status is load-bearing. `CausalClaim` currently defaults missing `source_basis` to `FULLTEXT`, so a
legacy adapter must not construct that contract and silently assert a source; it must carry an
optional value plus `not_established`. Likewise, `graph_builder.py` currently copies the enclosing
record's extraction confidence into every raw claim, which is not a claim-specific observation.
`may_publish=false` is an operational fail-closed decision, not a fabricated negative adjudication.
The literal `moderate` is retained only as a historical observation. It is not promoted to
`CausalCredibility.MODERATE` and is not mapped to any design or evidence enum.

For the 67,791 enriched identities, the payload's distinct hint, evidence class, claim confidence,
source basis, and spans may be preserved as **candidate observations**. The matching
`ac_claim_adjudications` rows prove structural coverage only: the slim table has no batch receipt,
CAS reference, rule version, or verifier provenance. The current candidate batch contract declares
only edge publishability and expressly not method validity, but the holder lacks complete-chain
verification even for that declared purpose. Therefore all
67,791 historical adjudication rows are `authority_not_established` in this snapshot. The 7,868
already-materialized graph claims and their derived artifacts must fail closed at authority-bearing
reads until a holder-verified, content-bound verification receipt and compatible projection rule
are resolved.

The current result loader does not yet provide that proof. A repository test helper constructs an
arbitrary batch, uses a non-promotable evaluation with no required guardrails/sample metrics,
chooses `"a" * 64` as the pointer digest, self-stamps the expected producer and lineage, and is
accepted through graph and conflict consumers. A deeper paired witness is also constructible:
`BenchmarkEvaluation` accepts caller-authored passing metrics, guardrails, sample counts, and
`promotable=True`; `persist_benchmark_evaluation` then stamps the expected evaluator component, and
a matching pointer can repeat those same values. `admit_champion` checks the component string and
internal equality, not an appointment, signature, bound per-item observation set, or independent
metric replay. CAS byte identity and ordered-denominator equality are useful recomputations, but
they prove only self-consistency. They do not establish producer identity, champion currentness,
evaluator provenance, promotion-policy application, result recomputation, or authority purpose.
The no-data safety close must therefore land a trusted evaluator-receipt intake plus the complete
batch verifier, or refuse every current evaluation and v1 batch; it may not call either one
"resolved" and continue.

The architect's position against projecting `ac_works.study_design` is correct. That field is a
paper-level classification; a paper may contain several claims with different identification
bases, reviews, theory, and descriptive results. The current claim-adjudication input carries the
paper methodology and the individual claim evidence separately precisely so an adjudicator can
resolve them. Copying the parent field would make an unrecorded paper-to-claim adjudication and
repeat the substitution this debt is meant to close.

## Verified Snapshot Integrity and Measurements

All database connections used `duckdb.connect(path, read_only=True)`. No producer was run. The
snapshot was mode `-r--r--r--`, 2,390,503,424 bytes, and remained at:

```text
sha256:583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967
```

Snapshot path:

```text
production_data/policyos_academic_runtime_slim_20260411T112032Z/
academic/graph/scholar_knowledge.duckdb
```

### Relational claim and adjudication population

`ac_causal_claims_raw` has 137,589 rows, 137,589 distinct nonblank IDs, and 65,335 distinct work
IDs. The exact partition is:

The schema census confirms that `strength` and `design_family_hint` are separate columns alongside
`strong_design_evidence`, `design_quality_tier`, `claim_extraction_confidence`, `mechanism`, and
`span_contamination_detected`. That syntactic split is real, but the generic `strength` column
still carries two vocabularies and therefore is not yet a semantic split.

| Cohort | Unique claim identities | `design_family_hint` | `strength` |
| --- | ---: | --- | --- |
| Enriched | 67,791 | populated | design/evidence-valued |
| Legacy | 69,798 | blank | exactly `moderate` |
| Total | 137,589 | — | — |

The intersection of `strength='moderate'` and a real design hint is zero. The intersection of a
non-`moderate` strength and a blank hint is also zero. The measured `strength` distribution is:

| Value | Rows |
| --- | ---: |
| `moderate` | 69,798 |
| `observational` | 41,521 |
| `theoretical` | 17,688 |
| `meta_analysis` | 3,499 |
| `quasi_natural` | 2,109 |
| `unknown` | 1,813 |
| `rct` | 899 |
| `panel_fe` | 255 |
| `cross_sectional` | 7 |
| **Total** | **137,589** |

The populated hint distribution is `unclear` 33,600; `theoretical` 17,172; `iv` 7,197; `ols`
4,608; `meta_analysis` 1,409; `panel_fe` 1,357; `rct` 855;
`quasi_experimental_other` 851; `structural_model` 415; `did` 246; `event_study` 41;
`rdd` 20; `review` 12; `synthetic_control` 7; and `time_series_cointegration` 1, plus the
69,798 blanks. Those counts sum to the table total.

`ac_claim_adjudications` has exactly 67,791 rows. Every claim ID matches an enriched raw claim;
there are zero extra adjudications, zero enriched raw claims without adjudication, and zero
legacy/blank-hint claims with adjudication. `design_family`, `causal_credibility`, `risk_of_bias`,
`support_status`, `claim_validity_score`, and `adjudication_confidence` are populated in all 67,791
rows. This proves structural coverage, not admission or semantic independence:
`consensus_passes`, `consensus_stability`, and the three component confidence fields are constant
at `1`/`1.0` in this assembled snapshot, and the table contains no receipt/rule/CAS columns. The
complete type-aware 25-column profile has zero nulls except `design_quality_tier` (35,443 nulls);
among text columns, blanks occur only in `publish_blockers` (7,333) and `adjudication_notes` (4).
These optional-field gaps do not change the six populated fields above, but prevent the broader
claim that every adjudication column is complete. The
source contract `AdmittedClaimAdjudicationBatch` would bind such results only to
`academic_claim_edge_publishability` and explicitly bars `method_validity`; the corresponding
batch receipt is absent from the slim bundle.

### The 137,714-versus-137,589 denominator and the 125

There are two correct denominators because they count different objects:

| Denominator | Count | Use |
| --- | ---: | --- |
| JSON claim occurrences in `ac_article_extractions.extraction_json` | 137,714 | payload/occurrence migration and array preservation |
| Distinct reconstructed or explicit stable claim IDs | 137,589 | relational claim, adjudication, graph, and consumer impact |

The reconciliation is exact:

```text
69,923 legacy JSON occurrences - 125 duplicate-ID excess
+ 67,791 enriched JSON occurrences
= 137,589 relational identities
```

The 125 are **not filtered or missing claims**. They are stable-ID collision occurrences:

- 111 duplicate stable-ID groups contain 236 JSON objects and materialize as 111 raw IDs;
- group sizes are 100 groups of two, eight groups of three, and three groups of four;
- 121 excess occurrences in 107 groups are byte-identical duplicate JSON objects;
- four excess occurrences are case-only cause/effect variants collapsed by lower-case stable-ID
  normalization; and
- in every group the relational raw row equals the final matching JSON array occurrence.

The current graph writer declares a primary key and uses `INSERT OR REPLACE`, which explains and
reproduces the observed retained-last result. The assembled slim table itself has lost PK/NOT NULL
constraints through `CREATE TABLE AS`, and the original run's writer receipt is absent, so the
historical execution of this exact source revision is `not_established`; the occurrence/identity
reconciliation itself is recomputed.

The four non-identical normalized collisions are:

| Work | Stable claim ID | Variant |
| --- | --- | --- |
| `W4393066931` | `9a0aba64224b7be7bea30be7` | `urban rail can` / `Urban rail can` |
| `W2558200472` | `a8752206e03f3417e553dacb` | `work motivation → teacher` / title-case variant |
| `W2100062349` | `d69d9a64b12f04d58bba8499` | `Counseling on Exclusive Breastfeeding → Nursing Mothers` / lower-case variant |
| `W2229403548` | `fdc5267da68791741a610d09` | `Cowdung manure and vermicompost` / lower-case variant |

There are zero reconstructed JSON IDs absent from `ac_causal_claims_raw`, zero raw IDs absent from
JSON, zero JSON claim objects on retracted works, and zero objects without an `ac_works` row.
Therefore candidate **b** cannot copy the relational table over the JSON array: doing so would
silently discard 125 occurrences and their order. A future migration must walk all 137,714 JSON
occurrences and emit a new, versioned artifact with an occurrence-to-stable-ID reconciliation.

### Producer provenance correction

The pinned payload contains exactly two JSON key sets:

- 69,923 five-field objects: `cause`, `effect`, `direction`, `strength`, `mechanism`;
- 67,791 enriched 23-field objects including `claim_id`, `claim_text`,
  `design_family_hint`, claim-specific confidence, evidence spans, source basis, and the same
  ambiguous `strength` key.

By record-level extraction mode:

| Mode | Shape | `strength` vocabulary | Occurrences |
| --- | --- | --- | ---: |
| `deterministic` | five fields | only `moderate` | 58,671 |
| `resolve_extract` | five fields | only `moderate` | 11,252 |
| `resolve_extract` | enriched | `EvidenceStrength` values | 67,791 |
| `llm_enriched` | any | — | 0 |

Thus the architect's two-producer explanation does not describe this pinned run. The deterministic
parser at `parser.py:369-400` hard-codes `"strength": "moderate"`; it accounts for the legacy
shape. The 11,252 five-field occurrences carried by `resolve_extract` are consistent with legacy
claims being carried forward, but the slim snapshot has no per-claim producer receipt, so that
carry-forward mechanism is an inference rather than an established fact. The selective LLM prompt
at `llm_extractor.py:24-63` is a real future-write risk, but the snapshot contains zero
`llm_enriched` rows.

The rich path constructs distinct fields and then collapses one at
`article_extractor.py:1943-1973` by serializing `claim.evidence_strength.value` under `strength`.
The untyped `WorkRecord` bridge and `graph_builder.py:1192-1232` preserve the ambiguity.

## Enum-Relation Finding: Three Categorical Vocabularies, Plus a Numeric Score

The exact enum census is:

| Type | Cardinality | Members |
| --- | ---: | --- |
| `EvidenceStrength` | 10 | `rct`, `quasi_natural`, `quasi_natural_event`, `meta_analysis`, `panel_fe`, `structural`, `observational`, `cross_sectional`, `theoretical`, `unknown` |
| `DesignFamily` | 20 | `rct`, `iv`, `did`, `rdd`, `synthetic_control`, `event_study`, `quasi_experimental_other`, `quasi_experimental_did`, `quasi_experimental_rdd`, `panel_fe`, `ols`, `ols_cross_sectional`, `meta_analysis`, `review`, `review_narrative`, `review_meta_analysis`, `theoretical`, `structural_model`, `time_series_cointegration`, `unclear` |
| `CausalCredibility` | 5 | `strong`, `moderate`, `weak`, `not_causal`, `unclear` |

`EvidenceStrength ∩ DesignFamily` is only `{meta_analysis, panel_fe, rct, theoretical}`.
`EvidenceStrength` first appeared on 2026-02-28 in commit `4c79120c6`; `DesignFamily` was added on
2026-03-08 in `d5dbfabe2` while the same `CausalClaim` retained `evidence_strength` and gained
numeric `claim_extraction_confidence`. This is strong evidence that the later type did not rename
or replace the older one.

The exact relation established by the tree is narrower than the current helpers imply:

- `DesignFamily` is the larger, more granular claim-method vocabulary.
- `EvidenceStrength` is older and is used by the graph as an evidence/ranking taxonomy.
- the contract deliberately retained both fields in parallel; neither enum definition declares
  that one derives from the other;
- current graph helpers attempt lossy `DesignFamily → EvidenceStrength` conversions, but those
  helpers disagree and then fall back to `CausalCredibility`; implementation behavior is not an
  admitted semantic relation;
- `CausalCredibility` is a separately typed categorical claim judgment and is not a methodology
  proxy; and
- `claim_extraction_confidence` is a fourth, numeric axis: confidence that extraction itself is
  correct.

Thus the answer is: **`EvidenceStrength` is historically older, but the two contract fields are
independent axes; no complete coarsening is established.** The legacy free key `strength` is a
union: its `moderate` cohort uses a credibility-like adjective while the rich serializer stores
`EvidenceStrength`. Value spelling alone cannot establish the producer or property. There is no
safe mapping in either direction.

Do not ratify a design-to-evidence table in this implementation plan. Any such compatibility rule
would be new policy. Restoring authority-bearing evidence weighting requires an explicitly owned,
versioned rule (or a direct evidence-strength adjudication), an approved semantic oracle/fixtures,
an admitted authority purpose such as academic evidence ranking, and mixed/future-enum negatives.
Until then, keep both observations separate and exclude every row without a resolved
evidence-ranking-purpose receipt from the authority aggregate denominator, floor, and
multi-article bonus; an extraction basis or publishability receipt is not enough. Do **not**
globally change `EvidenceStrength.UNKNOWN=0.15`: status/provenance distinguishes unestablished
legacy absence from an observed `unknown`, while a ranking receipt independently decides whether
either may carry authority weight.

## Consumer Census and Live Defects

Across all 2,618 tracked source Python files, the pinned-ref census found 39 semantic-token files
and 15 table-literal files, with eight overlapping: their union is 46. A targeted generic-key
search adds `parser.py` and `llm_extractor.py`, yielding 48 unique lexical candidates. Appendix A
lists and classifies the 46-file union (producer 10, store/materializer 8, semantic consumer 13,
administrative 2, unrelated 13), names the two additions, and follows literal-free wrappers. Token
search is the complete lexical denominator, not a call-graph oracle; behavioral closure therefore
also reruns every registered producer/writer and the named downstream routes.

A second pinned, complete-tree carrier census closes the literal-free gap rather than treating the
first token set as exhaustive. Across the same 2,618 source Python files, 20 files mention the
exact `CrossGraphEvidenceProfile` type name, 27 mention the type/ref/persist/load/artifact-key
family, and 29 are in that union after adding the lowercase `cross_graph_profile` carrier. The last
set includes contracts and administrative constants as well as consumers; Appendix A classifies
all 29. A separate Runtime capability-index census has seven lexical candidates. Its direct
`CapabilityBindingResult` and data-requirement descendants are call-chain extensions because they
retain only an index-ref string today. These counts are independently replayed below; they differ
from a narrower 17/26/28 review count because the pinned `git grep` includes the IR registry,
duck-typed `_CrossGraphEvidenceProfileLike`, and current carrier sites instead of silently dropping
them.

### Materialization chain

| Stage | Current behavior | Defect/impact |
| --- | --- | --- |
| `batch/graph_builder.py:1192-1235` | writes raw `claim["strength"]` and seeds the curated value | generic mixed store |
| `graph_builder.py:638-671` | maps raw `moderate → observational` | executable defect, but **0 current promotions** because graph publication requires adjudication |
| `graph_builder.py:369-395` | maps the adjudication's design label, then falls back from credibility | **live defect: 342 curated claims** |
| `graph_builder.py:1289-1319` | writes projected category into `ac_causal_claims.strength` while retaining raw `design_family_hint` | design source mislabeled; 566/7,868 hints differ from adjudication |
| `graph_builder.py:1593-1690` | uses the same bad projection for exact evidence and confidence aggregation | 342 evidence rows / 341 exact edges |
| `knowledge/skg_store.py:313-517` | weights `observational=0.30`, `theoretical/unknown=0.15` | bad category enters edge confidence |
| `knowledge/skg_store.py:640-852` | direct span-grounded ingest ignores `publish_to_graph=False` and writes extractor hint/evidence into `design_tier_authority` | sibling-writer authority bypass; its table is absent from this snapshot, so current-row impact is zero/not materialized |
| `batch/best_snapshot.py:100-145,614-768` | copies claim/SKG and derived tables, clones non-SKG tables with `CREATE TABLE AS`, then promotes the snapshot | writer/migration bypass that can preserve legacy schema, lost constraints, and receipt-less authority |
| `batch/edge_synthesize.py:360-610` | aggregates exact evidence into family/contested rows | 341 family rows / 9 contested rows |
| `batch/transport_score.py:567-651` | carries exact confidence into transport scores | 341 transport rows |
| `knowledge/skg_versioning.py:115-162` | normalizes/reaggregates stored category during retraction | replay preserves the misclassification |
| `scientist/methods/autotune/models.py:138-155,398-428` → `claim_adjudication_runtime.py:194-237` | accepts caller-authored passing evaluation fields, self-stamps the expected evaluator component, and admits a matching pointer by string/field equality | **live authority-path defect:** a coherent fake evaluation+pointer is self-consistent but has no authenticated evaluator appointment, bound observation set, or independent metric/guardrail replay |
| `batch/claim_adjudicator.py:285-320` | accepts a result CAS object after kind/schema/producer-string, self-lineage, and raw-denominator checks | **live authority-path defect:** it never resolves the champion pointer, candidate/evaluation semantics, promotion policy, result predicate, or non-producer verifier provenance |
| `batch/admitted_claim_adjudications.py:35-57` → graph/conflict consumers | projects that object as “verified” rows | a present-but-fake, self-stamped batch is accepted by the current unit witness and can authorize publication; the pinned snapshot has no such receipt, so current materialized impact is zero |

The direct `moderate → observational` branch affects zero current materialized rows because all
69,798 legacy identities lack adjudications and the graph publication loop requires an admitted
`publishable_edge` field. It is still a future-write defect and must be removed. “Admitted” cannot
be inferred from the slim row itself: all historical adjudication authority is unestablished until
an authenticated evaluator receipt establishes its benchmark observation lineage, an appointed
non-producing verifier independently recomputes evaluation/promotion and the complete batch
lineage, and the holder verifies the resulting purpose-bound receipt.

The live `_legacy_strength_from_adjudication` fallback affects 342/7,868 curated claims (4.347%):

| Adjudicated design | Credibility | Wrong emitted category | Rows |
| --- | --- | --- | ---: |
| `unclear` | `moderate` | `observational` | 163 |
| `unclear` | `strong` | `observational` | 24 |
| `theoretical` | `moderate` | `observational` | 127 |
| `theoretical` | `strong` | `observational` | 4 |
| `review` | `moderate` | `observational` | 24 |
| **Total** | — | — | **342** |

The P38 divergent witness is not hypothetical: `design_family=theoretical` plus
`causal_credibility=moderate` means theoretical evidence with a moderate claim judgment, yet 127
current rows are emitted as observational. The 342 rows' raw `strength` values range across
`observational` 150, `theoretical` 80, `quasi_natural` 62, `unknown` 46, `meta_analysis` 2, and
`rct` 2, so raw `strength` is not a safe substitute either.

Propagation is exact:

| Materialized table | Complete rows | Rows containing affected lineage |
| --- | ---: | ---: |
| `ac_causal_claims` | 7,868 | 342 |
| `ac_skg_edge_evidence` | 7,868 | 342 |
| `ac_skg_edges` | 7,607 | 341 |
| `ac_skg_family_edges` | 15,945 | 341 |
| `ac_skg_contested_edges` | 723 | 9 |
| `ac_skg_transport_scores` | 7,607 | 341 |

Among the 341 exact edges, the stored strongest category is `observational` for 334,
`quasi_natural` for four, `rct` for two, and `meta_analysis` for one. All 341 aggregate confidence
computations consumed the wrong observational weight even when another item won the final category.
Their stored confidence bands are 334 below 0.35, six from 0.35 to below 0.75, and one at least
0.75. This plan does not assert the exact counterfactual confidence/status without a rebuild.
Moreover, because the snapshot has no admission receipt, the no-data read strangle must mark 7,868
claim lineages represented by 7,868 curated rows and 7,868 edge-evidence rows
`authority_not_established`; the 342/341 set remains the exact additional vocabulary-fallback
defect within that wider fail-closed cohort.

Forty `ac_skg_simulation_parameters` rows are linked to affected claim IDs, but direct strength
contamination of those parameter values is not established. They are an audit set, not part of the
342-row assertion.

### Data Forge, API, Foundry, and Scientist consumers

| Consumer | Read/effect |
| --- | --- |
| `knowledge/store.py:239-293` and `knowledge/types.py:47-60` | returns `ac_causal_claims.strength` through `CausalClaimResult.strength`, documented as `strong/moderate/weak`; all 7,868 current values are outside that documented scale. This is a second live mislabel. |
| `knowledge/search.py:220-252`, `scientist/agent/knowledge_tools.py:164-194`, `data_forge/read_api/academic.py:44-53` | expose the mislabeled claim DTO through the Scholar and public read APIs. |
| `knowledge/skg_query.py:1027-1219,2470-2664` | exposes exact/family/contested evidence strength and ranks/filter results by already-tainted confidence. |
| `foundry/methods/catalog/causal/literature_prior.py:193-258` | validates returned labels as `EvidenceStrength` and builds the literature causal prior. |
| `scientist/nodes/builtins/causal/build_literature_prior.py:183-289` and `reconcile_causal_graph.py:820-835` | persists the prior and reconciles it into the causal graph; wired by `policy_design.py` and `causal_full.py`. |
| `scientist/methods/discovery/prior_miner.py:93-189` → `priors.py:106-128,254-283` → `methods/search/readiness.py:1020-1062` and decision/promotion nodes | materializes SKG confidence/evidence into `PriorKnowledgeBundle`, then reloads a version/ref-only artifact into advanced-evidence readiness and policy promotion. |
| `scientist/nodes/builtins/planning/compile_cross_graph_evidence.py:121-122,304-305` → governance/decision loaders | reuses and persists direct-SKG-derived `CrossGraphEvidenceProfile`; its strict IR contract has no projection receipt/epoch, so an existing ref bypasses currentness. |
| `scientist/nodes/builtins/causal/reconcile_causal_graph.py:561-573` and canonical causal-graph persist/load | can early-return an existing literature-derived `CausalGraphModel`; `skg_version_id` and a free-form snapshot ref do not content-bind the projection rule or establish currentness. |
| `scientist/cross_graph/gatherers/academic.py:176-250` | carries category and confidence into cross-graph evidence. |
| `scientist/cross_graph/compiler.py:927-990` and `scientist/cross_graph/feedback.py:159-188` | directly rank `query_edge_support` and count `find_causal_evidence` results; both must consume the typed limitation rather than treating presence as support. |
| `scientist/nodes/builtins/causal/resolve_transport.py:499-504,840-874` → `data_forge/domains/catalog/knowledge/proxy_resolver.py:194-218,262-301` | converts `query_claims().trust_score` into transport-proxy confidence, so the public-DTO fix alone does not close the authority path. |
| `batch/benchmark.py` and `batch/qc.py` | benchmark uses SKG confidence to classify causal support; QC directly reads edge confidence and bare adjudication publishability to emit check outcomes. Both are semantic consumers, not administrative readers. |
| `knowledge/parameter_selector.py:34-57,112-132,176-215,276-309` | consumes a bare `CrossGraphEvidenceProfile`; legal/observability/evidence/transport statuses can veto a parameter and change its penalty, confidence, selected value, and uncertainty multiplier. This file's lexical `strength` hit is unrelated, but this literal-free route is not. |
| `scientist/policy_design/objectives.py:100-141,241-260,330-342,525-556` → `nodes/builtins/planning/run_hierarchical_policy_search.py:741-780,834-872,1090-1141` | turns a bare profile into transportability/evidence-depth channels and a legacy scalar proxy used for search ranking and persisted frontier selection. |
| `scientist/methods/search/judge_stack.py:198,374-379,561-579,878-904,1415-1488,1732-1778` and `methods/search/funnel/level5_refutation_governance.py:130-141,271-300,460-560` | uses a bare or model-validated profile to change blockers, readiness, composite verdict, transport uncertainty, and persisted actionable side information. |
| `scientist/nodes/builtins/causal/resolve_parameters.py:93-207,264-276` → `ir/analytics/parameters.py:43-86` → Foundry `protocols.py:725-740` / `parameter_transfer.py:95-125` | silently turns stale/load failure into `None`, short-circuits on any existing ref, then persists and accepts a `ContextAdaptiveParameterBundle` carrying only SKG ref/version; it can set parameter uncertainty and `phase15_runtime_ready` without a current projection binding. |
| `scientist/nodes/builtins/decide/build_policy_output_bundle.py:252-260,307-322,651-690`, `policy_runtime_request.py:40-51,89-97`, `run_policy_blueprint_runtime.py:248-269,320-425,600-626,852-880,1618-1658`, `policy_design/output.py:435-635,930-983,1568-1614`, and `run_policy_translation.py:258-300` | stale/load failure can collapse to absence, path presence can then restore `available`, and unresolved profile values/statuses enter evaluation, promotion metadata, transportability reports, and policy outputs. |
| `scientist/cross_graph/conflict_materializer.py:38-96`, `nodes/builtins/decide/decision_packet/{validation.py:96-117,serialization.py:241-243}`, and `nodes/builtins/planning/assemble_legal_candidate_pack.py:90-95` | a duck-typed profile or mere unresolved ref can create conflict/portfolio/closeout records, satisfy a serious-decision presence check, or be serialized/bound as lineage. These are carrier and gate consumers, not proof of current evidence. |
| `scientist/methods/search/pareto_registry.py:49-115,132-363,527-577` → `methods/search/controller.py:592-754` → `policy_design/search.py:955-1064` | persists and reloads `PolicyEvaluationVector`, publishes it to a cross-domain transfer catalog, accepts a model/dict or collapses parse failure to `None`, and reuses it as warm-start ranking evidence. A stale academic binding can therefore survive beyond the original frontier producer. |
| `scientist/validation/phase5_preflight.py:283-327,967-1025` → `ir/governance/validation.py:64-88,164-190` | model-validates an arbitrary existing `JudgeVerdict`, republishes it with unbound inputs, derives `publishable`, and persists a `ValidationReport` with no academic projection binding. This is a publication-authority descendant, not merely a report. |
| `scientist/policy_design/translator.py:48-61,188-310` and `scientist/evidence/claims/projections.py:245-299` | accept a bare `DecisionReadinessContract`; the translator may create/persist a public `PolicyBrief`, while the claim projection turns readiness-ref presence into a source-quality claim without resolving currentness. |
| `scientist/methods/search/funnel/level4_full.py:57-143` | is a second `ActionableSideInformation` producer and persists it with no input lineage. It is evidence-independent only when its inputs have no academic binding; the generic lineage guard must propagate a binding whenever they do. |

### Runtime consumers

| Consumer | Read/effect |
| --- | --- |
| `runtime/quality/credal_reference.py:833-908,1096-1225,1387-1434` | reads all exact/family/claim/contested rows, publishes evidence strength in provenance or value, and uses tainted edge confidence for `incomplete`/`contested`/`confirmed` status. |
| `runtime/quality/design_generation.py:957-970` and `grounding_relation.py:708-727` | consume the credal projection downstream. |
| `runtime/quality/capability_index_compiler.py:872-1038` | selects `e.evidence_strength` but drops it from the emitted capability; tainted edge and transport confidences enter `QualityScore`. It also parses categorical `strongest_dissent_strength` through numeric `_score`, so all 155 nonblank current dissent labels become zero. |
| `runtime/quality/proving_ground/causal_forecast_search.py:1120-1210` | calls `SKGQuery.query_edge_support`, which filters/ranks by confidence and carries evidence strength in `EdgeSupportRecord`. Its direct SQL at 6042-6067 checks only edge/transport existence. |
| `runtime/quality/data_state_substrate.py:474-592,1321-1342` → `runtime/quality/world_model_record.py:762-813` → `pdc/_impl/world_model_record.py:111-119` | constructs `SkgCausalPriorRef` from version/ref fields, validates no projection receipt or source epoch, and admits it into simulation. Presence of a reference is therefore another live P37/P38 authority bypass. |
| `runtime/quality/generation_cycle.py:4451-4455` | independently constructs another version/ref-only `SkgCausalPriorRef`; it is a sibling production path, not a fixture-only exception. |
| `runtime/quality/capability_resolver.py:400-576,652-675` → `capability_authority.py:501-535,906-924` → `data_requirement/compiler.py:570-575,817-834` | accepts a bare `CapabilityIndex` or mapping, has a direct DuckDB factory that bypasses the canonical loader, and reduces lineage to a release-ref string in `CapabilityBindingResult` and data-requirement outputs. A stale academic-derived index can therefore affect selection/authority without its projection binding. |
| `runtime/quality/substrate_registry.py` | checks required table presence only; it is not a semantic strength consumer. |

`strongest_dissent_strength` is part of this row's vocabulary-by-shape class and is in scope, not
deferred. `ac_skg_contested_edges` contains 723 rows: 568 blank values and 155 categorical values
(`observational` 57, `meta_analysis` 35, `quasi_natural` 29, `panel_fe` 13, `rct` 11,
`quasi_natural_event` 6, `unknown` 3, `theoretical` 1); none casts to `DOUBLE`. The production
compiler therefore treats every populated dissent category as numeric zero, while its unit fixture
misdeclares the column as `DOUBLE`. Keep the category for audit and use the existing producer-owned
`dominant_direction_agreement` scalar as the numeric quality component only when its evidence and
admission basis resolves; otherwise emit a limitation. Do not invent a numeric conversion from the
category.

The repeated persisted-consumer escape is one class, not a list of isolated patches (P40). The
pinned tree's direct academic-derived set starts with `PriorKnowledgeBundle`, literature-derived
`CausalGraphModel`, `CrossGraphEvidenceProfile`, `ContextAdaptiveParameterBundle`,
`CapabilityIndex`, and `SkgCausalPriorRef`; the latter has two production constructors. Its current
descendant set also includes policy evaluation/frontier records, judge/readiness/actionable-side-
information outputs, promotion evidence, transportability/policy output artifacts, and
`CapabilityBindingResult` wherever their producer consumed one of those inputs. Widen the
mechanism to the property: every persisted artifact/reference whose resolved CAS input lineage
consumed the academic projection embeds an
`academic_projection_binding: SourceEpochBinding` (source owner/snapshot/SKG epoch,
projection-rule version, authority purpose, and content-bound admission receipt), and every
canonical loader or early-return/promotion/simulation
admission requires a consumer-side currentness check before use. The Data Forge owner appends the
persisted SKG projection epoch/admission event without importing Runtime or Scientist. Consumers
resolve it through the academic read boundary and refuse a missing/mismatched binding. The
capability loader preserves manifest input fingerprints and its process cache keys on the resolved
epoch. Persistence derives the obligation and propagates the binding from resolved CAS input
lineage, not from `discovery_method`, free-form metadata, field presence, or a caller assertion.
This set-level invariant covers readiness, governance, promotion, reconciliation, parameter
selection, search ranking, uncertainty, output assembly, capability binding, and simulation
without cross-boundary push invalidation; a new artifact type is admitted only by
embedding the same binding and passing the generic stale-binding falsifier.

The fixed point is defined by lineage, not by these class names: starting from a resolved academic
projection, every persisted output becomes a new root until no new producer, loader, registry,
catalog, transfer, translator, claim projection, or authority gate is reachable. The pinned lexical
candidate census over the currently known descendant symbols contains 83 files; intersecting with
persistence/load/ref/registry/catalog/publication terms leaves 79 candidates. Those numbers are a
complete search denominator, **not** a claim that all 79 are academic consumers: common names such
as `ValidationReport` also occur in unrelated domains. The implementation must classify all 79 and
record the exact `semantic`, `carrier`, `administrative`, or `evidence_independent` disposition.
More importantly, closure does not depend on that hand list: a generic persistence-lineage guard
walks actual CAS inputs and automatically requires/propagates the binding on every output; a
generic authority loader rejects any descendant whose recursive lineage consumed an academic
projection but whose current binding is missing or stale. Every non-CAS registry/catalog write
must either route through that guarded artifact owner or remain non-authoritative. The paired
falsifier is an unlisted synthetic descendant with a bound input: it must acquire the binding or be
rejected without adding its class name. This is the P40 stopping point; a later newly named sink is
a worked example of the same generic rule, not another per-file repair round.

## Adjudication Runnability and the Missing Half

There is a separate Scientist command at
`scientist/methods/autotune/claim_adjudication_cli.py:23-74`, and the Data Forge pipeline can invoke
it through an injected Scientist runner. It is **not independently runnable against the slim
DuckDB or only the 69,798-row anti-join**:

- Data Forge's direct stage intentionally refuses at `batch/cli.py:232-237`.
- The producer reads `resolve_extract_final_results.jsonl`, otherwise
  `article_extraction_results.jsonl`, and strictly parses `ArticleExtractionResult`; it never reads
  `ac_causal_claims_raw`.
- It selects every claim in its input, except claims from retracted works; it has no
  unadjudicated-only selector.
- It freezes source/retraction bytes into a CAS input artifact. The producer-side Runtime attempts
  to replay a non-seeded champion, candidate/evaluation lineage, promotion policy, and guardrails,
  but `admit_champion` itself trusts the evaluation manifest's producer-component string and
  caller-authored metric/guardrail/promotable fields. The downstream holder then fails to
  independently replay even that chain. Neither boundary authenticates an appointed evaluator or
  recomputes the evaluation from a content-bound per-item observation set.
- It requires Gonka credentials/network. With no keys, the current provider pool waits rather than
  failing early.
- The 23-file slim bundle contains none of the two extraction NDJSON inputs, adjudication CAS,
  champion, candidate, or evaluation artifacts.

`ClaimAdjudicationInputItem` requires claim text, methodology, source basis, design hint,
supporting/method spans, extraction model/timestamp/confidence, and other claim fields. Every one of
the 69,923 legacy JSON occurrences has exactly five fields and lacks claim text, claim-specific
confidence, source basis, design hint, and both span sets. The raw table's nonzero extraction
confidence was copied from the enclosing paper record by `graph_builder.py:1214-1217`; it is not a
claim-specific observation.

Even an optimistic model response could not legitimately publish these rows under the current
policy, which independently requires full text, supporting and method spans, a strong design,
acceptable bias/support, and score thresholds. Running an LLM on cause/effect labels alone would
be P15/P38 laundering, not adjudication. A deterministic no-model receipt may record
`not_established`/insufficient/non-publishable; it may not manufacture a design.

The source baseline defaults to three passes, which would mean 209,394 model calls for 69,798
identities **if** the eventual admitted champion retained that setting. Its actual configuration
and key count are missing. The adjudicator uses `GonkaMultiKeyPool` at the article-extraction
default of 8 requests/second **per key**, not the selective extractor's 5 requests/second. More
importantly, the current loop awaits claims sequentially, has no missing-only mode, checkpoint, or
admitted incremental resume, and publishes only after the full list completes. Consequently no
honest elapsed-time bound follows from the rate limiter alone; request latency, retries, champion
passes, and keys must be measured by a bounded pilot.

The existing 67,791 adjudications all record `consensus_passes=1`. The original adjudication
manifest/logs, authenticated evaluation receipt, and batch admission receipt are absent, so the adjudication's own historical elapsed
time, why persisted pass count differs from the current baseline, and whether those rows were ever
emitted inside the current candidate-batch schema remain **unanswered from available evidence**.
This does not block the safety decisions.

## Candidate Evaluation and Elapsed-Time Order

These are engineering/run-time estimates, not authority claims. Measure the first implementation
slice and any data pilot before tightening them.

| Candidate | Verdict | Elapsed-time shape | Reason |
| --- | --- | --- | --- |
| **a. Consumers read `design_family_hint` and `strength` as the two distinct fields they already are** | Reject as written; retain only after typed/status repair | 2–4 engineering days for a central read strangle, audit/public surfaces, and top-level authority refusal | `strength` is still a union; raw hint and enriched evidence are candidate observations; the receipt-less adjudication table is not method authority; and the current public DTO labels all 7,868 rows with the wrong vocabulary. |
| **b. Backfill JSON from relational table** | Conditional data build; authority form is currently `artifact_missing` | 1–2 engineering days for migration code/tests; versioned build wall time unmeasured; no model calls | Raw identity rows cannot recreate 125 replaced occurrences. Walk all 137,714 JSON occurrences and preserve order. Without the omitted historical producer/schema receipt, enriched values may be preserved only as unverified legacy observations, not authoritative typed facts. |
| **c. Split the key at both producers** | Required but underscoped | 2–3 engineering days, atomic with transport/store adaptation | There are three defective producer paths—parser, selective LLM, rich serializer—plus the untyped `WorkRecord`, batch graph writer, direct span-grounded writer, and best-snapshot copier/promoter. The latter two are sibling-bypass negatives. |
| **d. Type 69,798 as declared absence** | Required now | Hours once the typed compatibility projection exists | Honest and immediately countable. Design, evidence class, claim confidence, and source basis are all absent/not-established; `moderate` remains audit-only. |
| **e. Adjudicate the other half** | No-go on current inputs; conditional after evidence-bearing extraction and purpose admission | Delta bridge/pilot engineering plus an unmeasured model and authenticated-evaluation run | Current stage cannot read the DB anti-join, lacks required artifacts, and the claims lack evidence. Three passes would imply 209,394 calls only if the future champion kept the default; elapsed time is not derivable. The present evaluation is self-stamped, and even a future verified publishability receipt cannot authorize method/evidence ranking. |
| **f. Re-extract the missing half** | Optional for safety; prerequisite for grounded design/publication | 49,241 distinct works; total time unmeasured, so run a bounded pilot and extrapolate p50/p95 | Produces the missing claim text, source basis, spans, and design evidence. It improves completeness but is not required to stop semantic substitution. |

Fastest containment is **d + the fail-closed read/invalidation part of corrected a**: current
authority surfaces refuse or report a typed limitation without any corpus write. Full vocabulary
closure then adds **c** and the remaining consumer/public/replay tests so the next write cannot
recreate the defect. Neither milestone restores an authority-grade graph. Candidate b may later
produce an occurrence-preserving historical release without model work, but cannot manufacture
missing receipts. Candidate f precedes e if the objective changes from honest absence to grounded
classifications/publication.

The elapsed-time plan has two no-data milestones. A **two-to-four-day containment** can make the
receipt-less snapshot and every top-level authority admission refuse unbound academic-derived
artifacts with a typed limitation; it restores
no availability. After the persisted-descendant census, the full no-data closure is estimated at
**ten to fifteen engineering days**: one atomic typed seam/producer/store change, graph and
snapshot-copy admission, central read/audit surface, retraction epoch/cascade, reusable binding and
currentness checks across bundle/graph/profile/parameter/search/output/index/binding/world-model
artifacts, an appointed evaluator receipt plus non-producer adjudication verifier, public
compatibility, and cross-layer tests. Because the evaluator trust chain, verifier, and newly
enumerated sibling sinks enlarge the original estimate, measure the
two-to-four-day containment first and re-estimate the full wave before treating ten-to-fifteen
days as a commitment. The
unmeasured 49,241-work data run is not on either safety path.

## What Can Close Without Data Production

### Can close now

- Future producer output no longer contains a generic `strength` key.
- The common `WorkRecord`/graph-store ingress is typed, schema-versioned, and rejects ambiguous new
  writes; the direct span-grounded sibling writer cannot bypass it.
- A candidate adjudication batch can grant publishability only after the appointed non-producing
  verifier authenticates a separately appointed evaluator receipt, recomputes metrics, guards,
  promotability, promotion, and the full batch result from its content-bound inputs, and the Data
  Forge holder verifies the final receipt. Present-but-fake evaluations/pointers/batches and all v1
  artifacts fail closed without writing pointers, projections, reports, graph rows, or conflict
  rows. The no-data close wires this refusal; it does not mint a positive evaluation receipt.
- A typed raw-lineage audit query/surface classifies all 69,798 identities with null
  claim-design/evidence/confidence/source-basis values and `not_established` statuses, while
  retaining `moderate` only in audit provenance.
- The 69,798 continue to have zero graph/publication effect.
- The credibility-to-evidence fallback is removed; `causal_credibility` cannot alter design or the
  evidence bucket when design is held fixed.
- The receipt-less snapshot marks 7,868 claim lineages represented by 7,868 curated rows and 7,868
  edge-evidence rows `authority_not_established`; the exact 342/341 fallback-contaminated subset
  remains separately countable. No row enters aggregate confidence or its multi-article bonus
  merely because its enum spells `unknown` or its extraction basis is populated.
- `CausalClaimResult` and all public/read surfaces use names and types that match their values.
- Categorical `strongest_dissent_strength` is no longer parsed as a number; it stays an audit
  category, while the existing producer-owned `dominant_direction_agreement` supplies a numeric
  quality component only with resolved evidence/ranking admission. Otherwise the 155 populated
  current values yield a typed limitation.
- Every newly issued academic-derived persisted artifact — the prior-knowledge bundle,
  literature-derived causal graph, cross-graph profile, context-adaptive parameter bundle,
  capability index, world-model SKG reference, and current search/policy/capability descendants —
  including registry/transfer, Phase-5 validation, brief/claim projection, and actionable side
  information — carries the reusable projection binding. Consumers resolve currentness through the
  Data Forge read boundary; existing artifacts cannot acquire a binding retroactively, become
  stale, cannot be silently reused, and cached processes reload or refuse.
- Retraction appends a new SKG epoch and invalidates span-grounded and exact evidence plus family,
  contested, transport, prior, profile, parameter, search/output, index/binding, world-model
  reference, and cache descendants; it no longer mutates one table while leaving the old epoch
  apparently current.
- Behavioral tests prove the complete producer → artifact → bridge → consumer chain and its
  negative cases.

This is sufficient to close the **vocabulary/substitution safety debt**. Closure does not mean
every historical claim acquires a design or that an authority graph remains available; it means
absence/candidate status is visible, stale outputs fail closed, and no vocabulary is upgraded by
shape or spelling.

### Cannot close without data production

- Rewriting/backfilling `ac_article_extractions.extraction_json` or any DuckDB table.
- Persistently correcting the 342 curated/evidence rows, 341 exact/family/transport rows, or nine
  contested rows; no-data code quarantines them rather than claiming counterfactual values. The
  wider 7,868-row receipt gap also needs an admitted reissue before authority use.
- Reissuing clean SKG or any academic-derived prior/bundle/graph/profile/parameter/search/output/
  registry/validation/brief/claim/index/binding/world-model-reference artifact after old versions
  are invalidated. Code can refuse stale artifacts without producing their replacements.
- Replacing `not_established` with grounded designs for the 69,798 identities.
- Making those legacy claims publishable; claim text, full-text source basis, supporting spans, and
  method spans must first be produced.
- Proving total re-extraction/adjudication elapsed time; the bundle contains neither run-local logs
  nor the omitted source artifacts. A bounded pilot is required.
- Treating historical `design_family` as method/evidence-ranking authority. That requires a new
  purpose-scoped admission and semantic oracle; even a future verified publishability receipt does
  not grant it.
- Issuing a positive adjudication publishability receipt from the current evaluation artifacts.
  They lack a trusted evaluator appointment/signature and content-bound dataset, split, per-item
  observations, and execution identity. Those inputs must be produced in an authorized evaluation
  run (or the exact benchmark must be independently rerun); no-data code can only refuse them.

## Pattern Pass and Capability Reality

Relevant failure patterns:

- **P01/P12:** `CausalClaim` has the right contract, but the deterministic/selective producers,
  rich serializer, and `WorkRecord` bridge do not handshake with it.
- **P03:** the relational/raw/adjudication richness is hidden behind a mislabeled public DTO.
- **P04/P09:** historical absence has no distinct status/warning lifecycle; `unclear`, blank, and
  missing are conflated.
- **P05/P14/P15:** extractor hints, receipt-less adjudication fields, or credibility are laundered
  into evidence/design authority and then into graph confidence; the direct span-grounded writer
  is a sibling bypass.
- **P07/P08:** neither the projection rule nor legacy JSON vocabulary is version-bound; the current
  adjudication receipt omits model/temperature from resumable execution identity; retraction
  mutates one table without a new epoch/cascade; and assembled non-SKG tables lose source PK/NOT
  NULL constraints through `CREATE TABLE AS`.
- **P10/P32/P38:** a field name/value shape is used as the property; the 127
  theoretical/moderate rows are one concrete divergent witness. The other is the existing unit
  helper that self-stamps a shape-valid batch with a fabricated pointer digest and invalid
  evaluation, yet reaches graph/conflict publication. A coordinated self-stamped passing
  evaluation plus matching pointer is the deeper P32/P37 witness: internally consistent fields
  still do not prove that an appointed evaluator observed or scored the benchmark.
- **P27/P31:** do not add a second enum owner or repair each consumer independently; extend the IR
  types and one Data Forge admission/projection choke point, including every graph writer,
  snapshot copy/promote path, retraction replay, profile/index carrier, and authority sink.
- **P28:** producer repair alone leaves an unstrangled legacy snapshot.
- **P29/P33/P35:** tests must execute the semantic path and enumerate producer/table populations;
  marker strings and sampled rows are insufficient.
- **P37:** the assembled slim adjudication table is `not_established` because its batch
  verification receipt is absent. A bare/current CAS batch remains `not_established`: artifact
  bytes and the ordered raw denominator are `recomputed`, while equality of its manifest lineage
  to its own refs is only recomputed self-consistency. The generic evaluation manifest's producer
  component and its metrics, guards, sample counts, and `promotable` flag are likewise
  `consumer_asserted`, not evaluator evidence. Producer identity, champion currentness, evaluator
  provenance, promotion-policy application, result execution, and authority purpose are all
  `not_established` at the holder today. A future evaluator identity becomes
  `independently_reconciled` only when a trusted appointment resolver authenticates a signature
  over the candidate, suite, dataset, split, per-item observations, and execution identity.
  Metrics, guards, promotability, promotion, and publishability remain `recomputed` by the named
  non-producing batch verifier from those bound inputs. It then emits a content-bound provenance
  receipt, which the Data Forge holder independently verifies. Evaluator and batch-verifier
  appointment records are `institutionally_supplied`, so their existence cannot turn the gate on;
  a trust-root-backed resolver must independently reconcile signature, validity interval, purpose,
  and role separation. Caller strings cannot appoint either role. Even then, the receipt is
  authoritative only for edge publishability, not method
  validity or evidence ranking. Extraction hint is candidate output; paper methodology is supplied
  at the wrong plane for a claim; legacy five-field design, claim confidence, and source basis are
  `not_established`. For descendant currentness, the Data Forge epoch, CAS content hashes, and
  binding comparison are `recomputed`; method strings, metadata, ref presence, path availability,
  and caller roles remain `consumer_asserted` and cannot turn the gate on.
- **P40:** the 342 credibility fallback, direct span-grounded bypass, and numeric dissent coercion
  are sibling instances of vocabulary/authority substitution. The second review finding of stale
  persisted descendants is likewise the same currentness class one level deeper, so the repair is
  widened to a reusable projection binding, recursive input-manifest propagation, and generic
  consumer-side verifier over every carrier/sink and descendant, not another list of per-call
  invalidations. Registry/transfer, validation, translator, and claim-ledger escapes therefore
  fold into the same fixed-point rule and the unlisted-descendant falsifier. The later evaluation
  finding is the same self-attested-receipt class below the batch, not a new class: widen once to an
  end-to-end appointed-evaluator + authenticated-observation + independent-recomputation intake.
  No intermediate `ProducerInfo` string or self-declared positive field can carry authority.
  Close both classes at their structural boundaries.

Capability state now:

| Capability | State |
| --- | --- |
| Canonical rich claim contract | implemented, but downstream is `bridge_missing` |
| Deterministic/selective producer compliance | `producer_missing` |
| Versioned persisted evidence/design split | `artifact_missing` |
| Common claim-store and read projection | `bridge_missing` |
| Correct public/API/Runtime vocabulary | `surface_missing` |
| Cross-layer negative and E2E proof | `verification_missing`, `semantic_test_missing` |
| Adjudication on full typed artifacts | whole-input candidate producer exists; authenticated evaluator observation/receipt and consumer-side complete-chain verification are `artifact_missing`/`verification_missing`; the appointed evaluator and non-producer batch verifier are `absent/unallocated`; coherent-evaluation and present-but-fake-batch negatives are `semantic_test_missing`; the slim batch is not an authority artifact; a missing-only selector is `producer_missing`; authority beyond edge publishability is `absent/unallocated` |
| Meaningful adjudication directly from the 69,798 raw identities | `absent/unallocated` |
| Safe raw-lineage limitation/audit surface | `surface_missing` |
| Academic-derived persisted-artifact currentness and reissue | generic consumer-side currentness is `consumer_missing` across profile/index/parameter/search/output/registry/validation/brief/claim/binding sinks; reusable binding, recursive lineage guard, and persisted projection epoch are `artifact_missing`; the 83/79 candidate census awaits explicit dispositions; clean reissue is `artifact_missing` |

Target correct pattern:

```text
typed producer claim (candidate)
→ versioned occurrence artifact
→ typed store ingress
→ content-bound benchmark suite/dataset/split/per-item observations (candidate)
→ authenticated receipt from a separately appointed evaluator
→ authority-neutral adjudication candidate batch
→ named non-producer resolve + content-bind + independent metric/guard/promotion/result replay
→ holder-verified, purpose-scoped publishability receipt (or explicit not_established)
→ independently admitted evidence-ranking rule/artifact, if ranking is requested
→ persisted/query projection
→ Foundry/Scientist/Runtime consumer
→ audit/API surface
```

The negative path is equally load-bearing:

```text
legacy moderate or absent claim evidence
→ recorded legacy label + null values + not_established bases
→ null / not_established authority confidence; operational contribution zero
→ exclusion from graph confidence denominator/bonus and publication promotion
→ visible limitation
```

## Red-First Claim-to-Test Map

Each normative claim in this plan has one primary behavioral test. Measurement claims above have
the replay commands in the following section; they are not frozen as growing scalar constants in
unit tests.

| ID | Plan claim | Primary red test / acceptance signal |
| --- | --- | --- |
| C01 | Every claim-producing path emits a versioned envelope with separately named axes and no generic `strength` | `tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py::test_every_claim_producer_emits_versioned_explicit_axes`; execute parser, selective LLM, and rich serializer. |
| C02 | Both producing graph writers share one admission boundary | `...::test_span_grounded_writer_cannot_bypass_claim_admission`; cover both `publish_to_graph=False` and a forged `True` with no holder-verified purpose-bound receipt. Neither may create authority-tier rows; an explicitly candidate/audit span row is allowed. |
| C03 | Strict transport rejects ambiguous new writes without breaking legacy reads | `...::test_v2_work_record_rejects_generic_strength_and_v1_uses_explicit_adapter`; real JSON round trip, not source-token inspection. |
| C04 | Legacy `moderate` establishes no axis | `...::test_legacy_moderate_is_audited_but_establishes_no_design_evidence_confidence_source_or_publishability`; assert null values, five `not_established` bases, operational `may_publish=False`, and producer status not established. |
| C05 | Paper design and record confidence cannot fill claim fields | `...::test_parent_fields_cannot_fill_claim_axes`; metamorphically vary paper `study_design` and record confidence while holding the claim fixed; output stays absent. |
| C06 | The two enums are independent absent an admitted rule | `tests/unit/ir/test_literature_contract.py::test_design_family_does_not_implicitly_derive_evidence_strength`; changing either axis does not mutate the other, and no name-based coercion accepts a shared spelling. |
| C07 | Credibility cannot control design/evidence | `tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py::test_credibility_change_cannot_change_design_or_evidence`; hold all other inputs fixed across every credibility member. |
| C08 | `theoretical/moderate` and `unclear/strong` never become observational | `...::test_adjudication_labels_do_not_fall_back_to_observational`; current code is red for both. |
| C09 | Evidence without ranking-purpose admission is excluded before aggregation | `tests/unit/data_forge/domains/academic/knowledge/test_skg_store.py::test_multiple_rows_without_ranking_receipt_cannot_raise_confidence_floor_or_bonus`; include populated extraction basis and an independently verified publishability receipt to prove neither grants ranking authority. |
| C10 | Typed fields and absence survive producer → transport → raw/store round trip | `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py::test_claim_axes_round_trip_without_alias_or_false_defaults`; include disagreeing axes and missing source/confidence. |
| C11 | A bare historical adjudication row grants no authority | `...::test_adjudication_row_without_batch_receipt_is_authority_not_established`; cover method, ranking, and publishability uses. |
| C12 | Even an independently verified current batch receipt is scoped only to publishability | `...::test_publishability_receipt_cannot_authorize_method_or_evidence_ranking`; first reject a bare/self-stamped batch, then validate the real verifier-returned `authoritative_for`/`may_not_use_for` contract and prove neither a checkpoint nor an assembled result can widen that purpose. |
| C13 | Invalid `moderate` cannot escape normalization/strongest selection | `tests/unit/data_forge/domains/academic/knowledge/test_skg_store.py::test_non_evidence_label_fails_closed_before_strongest_selection`; current `strongest_strength(["moderate"])` returns `moderate`. |
| C14 | Current legacy lineage is centrally limited, with the 342 defect separately countable | `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py::test_receiptless_snapshot_is_limited_and_fallback_subset_is_audited`; fixture exact/family/contested/transport paths. |
| C15 | Public claim DTO names, values, basis, and compatibility behavior agree | `tests/unit/data_forge/domains/academic/knowledge/test_store.py::test_public_claim_result_v2_separates_axes_and_v1_returns_only_typed_limitation`; import through `polisyos.data_forge.read_api.academic`, with no generic field on v2 and no guess on v1. |
| C16 | Raw-lineage audit makes declared absence visible through both public routes | `tests/unit/data_forge/domains/academic/knowledge/test_knowledge_tools.py::test_public_raw_claim_audit_pages_unadjudicated_legacy_identities`; exercise the read API and Scholar tool, and snapshot-recompute 69,798 while generic fixtures derive their denominator. |
| C17 | Foundry/Scientist cannot reuse or falsely cite a stale prior | `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py::test_projection_change_invalidates_prior_across_build_reconcile_and_cross_graph_compile`; cover presence-only build reuse, reconciliation load failure, and planning cross-graph compilation; a failed load cannot remain in provenance. |
| C18 | Runtime credal paths cannot confirm receipt-less/tainted graph evidence | `tests/unit/runtime/quality/test_credal_reference.py::test_vocabulary_or_receipt_limitation_cannot_confirm`; cover exact, family, claim, and contested paths. |
| C19 | Capability compilation never parses dissent category as numeric | `tests/unit/runtime/quality/test_capability_index_compiler.py::test_categorical_dissent_uses_admitted_direction_agreement_or_limitation`; use the production `VARCHAR` category and existing numeric agreement column. |
| C20 | Forecast search cannot rank/select limited evidence | `tests/unit/runtime/quality/test_proving_ground_causal_forecast_search.py::test_forecast_search_excludes_unestablished_or_vocabulary_tainted_edges`. |
| C21 | Retraction creates a new epoch and invalidates every derivative | `tests/unit/data_forge/domains/academic/knowledge/test_skg_versioning.py::test_retraction_epoch_invalidates_span_exact_family_contested_transport_and_emits_currentness_event`; then the cross-layer integration fixture proves prior, profile, parameter bundle, search/output descendant, index/binding result, world-model ref, and cache refusal. No in-place mutation may leave an old release apparently current. |
| C22 | A JSON migration preserves occurrence and identity denominators | `tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_migration.py::test_migration_preserves_duplicate_occurrences_and_stable_id_reconciliation`; include exact duplicates and a case-only collision. Conditional on candidate b. |
| C23 | A migrated enriched label without its historical receipt remains an unverified observation | `...::test_migration_cannot_mint_missing_producer_or_admission_receipt`; conditional on b. |
| C24 | Delta adjudication selects typed evidence-bearing items lacking an admitted receipt | `tests/unit/data_forge/domains/academic/batch/test_claim_adjudicator.py::test_delta_input_is_content_bound_to_typed_items_without_receipts`; it is not an anti-join over old IDs or a caller count. Conditional on e. |
| C25 | Missing source/champion/credentials fail before provider work | `tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py::test_missing_prerequisite_blocks_before_first_provider_call`; conditional on e. |
| C26 | Missing claim evidence cannot be overcome by an optimistic model answer | `...::test_absent_claim_text_and_spans_remain_nonpublishable_after_optimistic_response`; conditional on e. |
| C27 | A data run resumes only within the same content-bound execution without upgrading checkpoint authority | `...::test_adjudication_resume_reuses_only_matching_execution_items_after_failure`; prove matching candidates are reused, but any raw-input, champion/pointer/config/passes, model, temperature, prompt/schema/code/rule-version mismatch invalidates them before assembly, and resumed items remain candidate. Required before any large e run. |
| C28 | Re-extraction preserves lineage without forcing old stable IDs | `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py::test_reextraction_supersedes_legacy_occurrences_with_new_content_bound_ids`; conditional on f/e. |
| C29 | Best-snapshot promotion cannot copy around admission | `tests/unit/data_forge/domains/academic/batch/test_best_snapshot.py::test_snapshot_copy_refuses_legacy_or_receiptless_claim_tables`; execute clone, dynamic copy, and promotion paths. |
| C30 | Capability artifact, canonical loader, every resolver factory, and cache preserve and compare the admitted projection/input epoch | `tests/unit/runtime/quality/test_capability_discovery.py::test_academic_projection_invalidation_refuses_cached_index_until_matching_reissue`; assert `CapabilityIndex` carries the binding, the loader preserves manifest fingerprints, `RequirementToCapabilityResolver` cannot accept a bare model/mapping or bypass through direct DuckDB, a consumer-side currentness resolver sees a newer persisted Data Forge event, and the default HTTP provider evicts/refuses rather than caching forever. |
| C31 | Benchmark and QC cannot turn receipt-less confidence/publishability into a passing gate | `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py::test_receiptless_claim_evidence_cannot_pass_benchmark_or_qc_gate`; execute both real consumers. |
| C32 | Runtime downstream design paths preserve the credal limitation | `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py::test_academic_evidence_limitation_survives_design_generation_and_grounding`; exercise both real consumers and prove an unresolved capability binding cannot replace the limitation. |
| C33 | A future admitted ranking policy purpose-binds the entire numeric calculus and does not globally redefine observed `unknown` | Add owner-selected semantic fixtures with Task 5 for classification, weights, floors, direction weighting, penalties, noisy-OR aggregation, and multi-article bonus; prove only a matching resolved ranking receipt activates that versioned calculus and mixed admitted/unadmitted rows do not earn a bonus. Conditional on Task 5. |
| C34 | Future parser/selective-LLM provenance binds the claim to the source actually seen | `tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py::test_abstract_producers_bind_actual_abstract_and_invocation_provenance`; alter the abstract or invocation and require a different binding, assert `ABSTRACT_ONLY`, and prove the historical adapter stays null/`not_established`. |
| C35 | Derived graph writers consume the admitted typed fields, not a generic category | `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py::test_edge_synthesis_and_transport_score_preserve_typed_limitation`; execute the real `edge_synthesize` and `transport_score` paths after an admitted and a limited graph build. |
| C36 | Literal-free downstream routes cannot treat a reference, count, or trust score as admitted evidence | `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py::test_cross_graph_feedback_transport_proxy_and_world_model_ref_fail_closed`; execute cross-graph compiler/feedback, transport proxy, Runtime substrate/world-model validation, and the PDC contract against a stale or receipt-less source epoch. |
| C37 | Every persisted artifact derived from academic evidence carries and resolves the same projection binding | `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py::test_every_academic_derived_artifact_rejects_missing_or_stale_projection_binding`; derive the obligation generically from resolved CAS input lineage and parameterize the current direct set (`PriorKnowledgeBundle`, literature-derived `CausalGraphModel`, `CrossGraphEvidenceProfile`, `ContextAdaptiveParameterBundle`, `CapabilityIndex`, both `SkgCausalPriorRef` constructors) plus current evaluation/frontier, judge/readiness/actionable-side-information, promotion, transportability/policy-output, and `CapabilityBindingResult` descendants; then remove/change the binding while keeping method strings, refs, paths, and metadata intact. |
| C38 | Both production SKG-reference constructors bind the admitted current epoch | `tests/unit/runtime/quality/test_cycle_substrate.py::test_every_production_skg_prior_ref_binds_current_academic_projection`; exercise both data-state and generation-cycle constructors and reject a version/ref-only or stale reference before simulation. |
| C39 | Stale academic-derived artifacts cannot make readiness, governance, parameter/runtime readiness, search rank, output, capability binding, or policy promotion green | `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py::test_stale_prior_profile_and_graph_fail_closed_at_authority_consumers`; exercise every existing-ref early return, readiness, cross-graph/literature governance, runtime support, parameter selection, objective/judge/funnel rank, output/translation, capability resolution, and policy promotion. |
| C40 | A present-but-fake self-stamped adjudication batch cannot become a holder receipt or mutate any projection | `tests/unit/data_forge/domains/academic/batch/test_admitted_claim_adjudication_consumers.py::test_present_but_fake_self_stamped_batch_cannot_materialize_or_replace_pointer`; keep correct kind/schema/expected producer/self-lineage/purpose/denominator but use a fabricated pointer, invalid evaluation, and arbitrary publishability; assert receipt pointer, JSONL projection, report, and stage state remain absent or byte-identical. |
| C41 | The appointed adjudication verifier resolves and content-binds the complete chain | `tests/unit/scientist/methods/autotune/test_claim_adjudication_verifier.py::test_verifier_replays_complete_chain_and_rejects_each_bound_mutation`; vary batch/raw/candidate/evaluator appointment/evaluation receipt/suite/dataset/split/per-item observations/pointer/policy/execution/result/provenance and producer==verifier; only the authenticated current chain whose derived values recompute yields a verification receipt. |
| C42 | Every cross-graph semantic sink rejects a bare, stale, mismatched, or present-but-forged profile wrapper | `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py::test_every_cross_graph_semantic_sink_requires_current_resolved_profile`; parameterize compiler/feedback/conflict materializer, parameter selector, objective/hierarchical search, judge/readiness/funnel, governance, runtime-support, policy verification, and promotion entry points. |
| C43 | Parameter resolution/transfer cannot reuse or reconstruct a stale academic-derived bundle | `tests/unit/scientist/nodes/builtins/causal/test_resolve_parameters.py::test_existing_or_new_parameter_bundle_requires_current_projection_binding`; cover the existing-ref short circuit, failed profile load, new selection, IR loader, Foundry raw-dict coercion, and `phase15_runtime_ready`; no failure collapses to `None` or an unbound mapping. |
| C44 | Blueprint/output/translation cannot turn failed currentness into path-based availability and must propagate the binding | `tests/unit/scientist/search/test_policy_blueprint_runtime_guards.py::test_stale_profile_cannot_override_source_status_or_fallback_to_path_available`; continue through runtime request, policy-objective/output assembly, translation, transportability report, and persisted policy output. |
| C45 | All capability-index resolver routes require a current wrapper and preserve it in downstream binding/data-requirement lineage | `tests/unit/runtime/quality/test_capability_resolver.py::test_resolver_factories_reject_bare_or_stale_index_and_preserve_current_binding`; exercise model, mapping, direct-DuckDB, canonical-loader, `CapabilityBindingResult`, and data-requirement compilation routes. |
| C46 | Presence of a profile ref alone satisfies no serious-decision or lineage gate | `tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_serious_decision_requires_current_profile_not_ref_presence`; continue through decision-packet serialization and legal-candidate-pack lineage, preserving candidate-only refs without authority or rejecting authority use. |
| C47 | A coherent self-stamped passing evaluation and matching pointer establish no evaluator provenance | `tests/unit/scientist/methods/autotune/test_claim_adjudication_verifier.py::test_coherent_self_stamped_evaluation_and_pointer_fail_without_appointed_evaluator_receipt`; keep suite/candidate/pointer IDs, passing metrics, guards, sample count, `promotable=True`, and producer-component strings mutually consistent, omit the trust-root-verified appointment/signature and bound observations, and assert no verification receipt or downstream mutation. |
| C48 | A stale/bare/forged evaluation descendant cannot enter registry, catalog, transfer, or warm-start ranking | `tests/unit/scientist/search/test_pareto_transfer.py::test_academic_bound_evaluation_requires_current_binding_across_registry_catalog_and_warm_start`; continue through controller model/dict normalization and hierarchical search, and prove parse/currentness failure is typed rather than `None`. |
| C49 | A stale or reconstructed judge descendant cannot authorize Phase-5 publication or be republished as current | `tests/unit/scientist/validation/test_phase5_preflight.py::test_stale_judge_verdict_cannot_authorize_or_be_republished`; keep all six judge markers while breaking the academic binding, then assert no green `ValidationReport`, publishability, or unbound replacement artifact. |
| C50 | Stale readiness cannot create or persist a public brief | `tests/unit/scientist/policy_design/test_phase_b_policy_workers.py::test_translator_rejects_stale_readiness_before_brief_persistence`; exercise both LLM and fallback paths with the same stale binding. |
| C51 | Readiness-ref presence alone cannot create a source-quality ledger claim | `tests/unit/scientist/evidence/claims/test_projections.py::test_readiness_ref_presence_cannot_create_source_quality_claim`; change/reforge the bound readiness while retaining the ref and require a typed limitation rather than a positive claim. |
| C52 | Persisted academic lineage is enforced generically, including every actionable-side-information producer and an unlisted descendant type | `tests/unit/ir/artifacts/test_lineage.py::test_recursive_academic_binding_propagates_without_schema_allowlist`; exercise Level-4 and Level-5 producers, CAS and non-CAS registry attempts, then define a new local artifact class whose input is bound and prove it is bound or rejected without editing a class-name list. |

No canonical academic producer/writer registry exists, so this plan does not pretend to derive one.
C01/C02/C21/C29/C35–C52 collectively execute every current producing, verification, derivation, copy, replay,
persisted-reuse, and literal-free authority path found by the pinned census, while acceptance requires every storage
mutation to pass the common store API so unadmitted writes are impossible regardless of caller.
The implementation close reruns the explicit
lexical and call-chain census. A future design-to-evidence mapping has no unconditional red test
here because no authority owner or semantic oracle has ratified one; that is an explicit decision
gate, not a contract to invent.

## Implementation Tasks

Tasks 2 and 3 are one atomic activation cluster. Their separate headings divide ownership and
review, not commits: do not activate or commit v2 writers before dual-schema readers, public
compatibility, invalidation, and Runtime refusal paths are present. An acceptable alternative is to
land the inactive DTO/dual-reader seam first, then atomically activate writers after every consumer
is compatible. No intermediate branch state may write v2 while hard-querying `c.strength`.

For the fastest containment, finish Task 1's additive DTO/adapter and then land only Task 3's
legacy read refusal, raw audit, and stale academic-derived artifact/cache rejection against the
unchanged v1 schema, including refusal of a stale world-model SKG reference. That is a clean, reversible state
and the two-to-four-day milestone above. Freeze the source
again before activating the remaining Task 2+3 write/read migration.

### Task 1: Add the typed envelope and legacy absence adapter without activating it

**Files:**

- Modify: `src/polisyos/ir/analytics/literature.py`
- Modify: `src/polisyos/ir/artifacts/lineage.py`
- Modify: `src/polisyos/data_forge/domains/academic/knowledge/types.py`
- Create: `tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py`
- Create: `tests/unit/ir/artifacts/test_lineage.py`
- Modify: `tests/unit/ir/test_literature_contract.py`

**Interfaces:**

- Reuse the IR enums; do not create a second owner or assert a relation between them.
- Add a versioned claim-envelope discriminator and explicit optional value + basis/status for
  design hint, evidence class, claim extraction confidence, and source basis.
- Extend the existing IR lineage owner with one strict, reusable `SourceEpochBinding`: source
  owner/snapshot/epoch, projection-rule version, authority purpose, and content-addressed admission
  **verification** receipt. Academic artifacts use the explicitly named
  `academic_projection_binding` field. Define `ResolvedAcademicProjection[T]` here as the strict
  result of the canonical resolver, with distinct `resolved_current`, `source_absent`,
  `stale`, and `verification_failed` outcomes; callers cannot model-validate or dict-coerce a green
  wrapper. It is additive here and becomes mandatory for academic-derived artifacts in Task 3.
  Add one common lineage resolver used by their persist/load functions: it walks resolved CAS
  input manifests, propagates the binding, compares the current Data Forge event, and refuses an
  academic input without one; it never infers the obligation from a producer-supplied label,
  method string, path, or ref presence.
- Make `AdmittedClaimAdjudicationBatch` authority-neutral and remove its positive
  `admission_predicate`/purpose defaults. Add strict authority-neutral
  `ClaimAdjudicationEvaluationVerificationReceipt` and
  `ClaimAdjudicationBatchVerificationReceipt`/resolved-handle contracts. The evaluation receipt
  binds a trust-root-verified evaluator appointment, candidate, benchmark suite, dataset, split
  manifest, ordered per-item gold/prediction observations, predictor execution identity, and the
  recomputed metrics/guards/sample counts/promotability. The batch receipt additionally binds the
  candidate batch ref+hash, raw input, authenticated evaluation receipt, immutable champion-pointer
  snapshot, promotion-policy ref+hash/rule, batch execution identity, ordered claim denominator,
  authority purpose, and appointed non-producer batch-verifier provenance ref+hash. Contract
  construction and generic `BenchmarkEvaluation` persistence never establish verification; Task
  2's appointed verifier is the only green batch-receipt producer.
- Remove default promotion at this boundary: absent source may not become `FULLTEXT`, absent design
  may not become `UNCLEAR`, and record confidence may not become claim confidence.
- Keep legacy conversion outside the strict v2 contract. A v2 payload containing generic
  `strength` is invalid.
- Add the contract and adapter additively; do **not** switch `WorkRecord.causal_claims` yet, so the
  repository remains runnable until all producers and writers move atomically in Task 2.

- [ ] Write C03–C06 RED, including parent-paper and record-confidence metamorphic negatives.
- [ ] Implement the additive envelope and explicitly named legacy adapter.
- [ ] Preserve the five-field label and record extraction mode as observations, while marking
  producer provenance `not_established`; do not label all 69,798 as deterministic.
- [ ] Permit a historical enriched label to become a typed candidate only with a content-bound
  schema/source receipt; otherwise retain it as an unverified legacy observation.
- [ ] Run the two focused test modules and Ruff on the changed files.

### Task 2: Prepare all producers, transport, graph writers, and snapshot copier for atomic switch

**Files:**

- Modify: `src/polisyos/data_forge/domains/academic/batch/parser.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/llm_extractor.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/article_extractor.py`
- Modify as required by the typed handoff: `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_api.py`
- Modify as required by the typed handoff: `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_providers.py`
- Modify as required by the typed handoff: `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py`
- Modify as required by persistence: `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_io.py`
- Modify as required by finalization: `src/polisyos/data_forge/domains/academic/batch/resolve_finalize.py`
- Modify as required by prompt schema: `src/polisyos/data_forge/domains/academic/batch/prompts/causal_claims.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/claim_adjudicator.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/admitted_claim_adjudications.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/pipeline.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/conflict_resolve.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/publish.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/graph_builder.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/edge_synthesize.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/transport_score.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/best_snapshot.py`
- Modify: `src/polisyos/data_forge/domains/academic/knowledge/skg_store.py`
- Modify: `src/polisyos/scientist/methods/autotune/models.py`
- Modify: `src/polisyos/scientist/methods/autotune/claim_adjudication.py`
- Modify: `src/polisyos/scientist/methods/autotune/claim_adjudication_runtime.py`
- Create: `src/polisyos/scientist/methods/autotune/claim_adjudication_verifier.py`
- Modify: `tests/unit/data_forge/domains/academic/batch/test_admitted_claim_adjudication_consumers.py`
- Modify: `tests/unit/data_forge/domains/academic/batch/test_pipeline_streaming.py`
- Modify: `tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py`
- Modify: `tests/unit/data_forge/domains/academic/batch/test_best_snapshot.py`
- Modify: `tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_autotune.py`
- Create: `tests/unit/data_forge/domains/academic/knowledge/test_skg_store.py`
- Modify: `tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py`
- Create: `tests/unit/scientist/methods/autotune/test_claim_adjudication_verifier.py`
- Create: `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py`

**Interfaces:**

- Future parser/selective-LLM claims bind their actual abstract input as
  `source_basis=ABSTRACT_ONLY` and bind producer provenance to the invocation. They do not inherit
  the historical cohort's missing lineage. Design/evidence/confidence remains absent or explicitly
  candidate; no hard-coded confidence or unknown enum label.
- Selective LLM prompt/result parser emits candidate typed fields; raw LLM output remains candidate.
- Rich serializer keeps the field name `evidence_strength`.
- Switch `WorkRecord.causal_claims` and all three producers in the same activation cluster; do not
  land a strict transport that current five-field producers cannot construct, and do not commit
  the activated writer schema until Task 3's dual readers are present.
- The batch graph builder and direct span-grounded ingest call the same admission function, and
  best-snapshot copy/promotion validates every copied claim/SKG table against that schema and
  admission receipt instead of cloning around it.
  A grounded span is not method/evidence authority, and `publish_to_graph=False` is binding.
- Graph DDL uses explicit candidate fields and basis statuses. Persist a separately named
  adjudication design observation, credibility, publishability result, verification receipt/rule,
  and authority purpose; absence of the verified receipt fails closed.
- Reuse only `ClaimAdjudicationRuntime.admit_champion`'s parsing and policy primitives; do **not**
  reuse its producer-component string as evaluator provenance. Widen one separately appointed
  `ClaimAdjudicationBatchVerifier` to the complete authority predicate. `ClaimGoldEvaluator` first
  emits a candidate, content-addressed observation artifact binding the suite, dataset bytes, split
  manifest, candidate, ordered per-item gold/prediction outputs, and predictor execution identity.
  An evaluator appointed through a trust-root-backed resolver signs a receipt over those exact
  refs/hashes. Generic `persist_benchmark_evaluation` output remains candidate and can never stand
  in for this receipt.
- The batch verifier accepts only the candidate batch ref plus authenticated evaluation receipt.
  It verifies the evaluator appointment/signature with the existing artifact-signature trust
  mechanism, resolves all bound bytes, independently recomputes selection/holdout metrics,
  sample counts, guardrails, `promotable`, and promotion-policy outcome from the observation set,
  snapshots/resolves the current registry pointer, then recomputes every `_policy_publishable`
  result against the frozen raw input and verifies the ordered denominator/execution identity.
  Self-declared evaluation fields are comparison diagnostics, never gate predicates. Any mismatch
  fails before emission. Only then may it emit the content-bound non-producer batch verification
  receipt. Candidate producer, appointed evaluator, and batch verifier identities must be distinct;
  merely changing `ProducerInfo.component`, co-editing evaluation and pointer, or supplying an
  appointment-shaped object is not verification. If a future owner chooses full independent
  benchmark rerun instead, that run is data production and must bind the same inputs and execution
  identity; it is not part of this no-data close.
- Make `claim_adjudicator.py` the single intake/emission holder. Before it writes the result pointer,
  compatibility JSONL, consensus report, stage manifest, graph rows, or conflict rows, it resolves
  the candidate batch and verification receipt, verifies every bound hash plus the appointed
  verifier provenance/signature, and checks the requested purpose. Data Forge does not import
  Scientist (the import policy forbids that direction); the Scientist runner returns the IR
  verified handle through the existing injected bridge. Change the pipeline runner result so the
  exact handle reaches conflict and graph stages in-process. Standalone/replay consumers must use
  the same appointed verification port; without it they fail closed. No consumer accepts a bare
  batch, preconstructed green wrapper, caller callback, or compatibility-file path.
- V1 candidate batches and the pinned receipt-less snapshot remain readable only as
  `not_established` audit evidence. If the verifier/appointment is unavailable, reject authority
  use now; do not defer the safety strangle to Task 7.
- Delete both credibility fallbacks. Do not add a `DesignFamily → EvidenceStrength` mapping in
  this task; keep independent observations or withhold authority ranking.
- Exclude every row lacking a resolved **evidence-ranking-purpose** receipt from the authority
  confidence denominator, floor, and multi-article bonus. A populated extraction basis or valid
  publishability receipt is insufficient. Do not globally change weights for properly observed
  `EvidenceStrength.UNKNOWN`; its authority use remains unavailable until Task 5 supplies a
  ratified ranking purpose.

- [ ] Write C01/C02, C07–C13, C29, C34, C40, C41, and C47 RED. Keep the present-but-fake fixture's
  correct kind/schema/expected producer/self-lineage/purpose/denominator so the real missing
  property—not a malformed marker—causes rejection. The C47 variant must keep a passing evaluation
  and pointer internally consistent while omitting only authenticated evaluator authority.
- [ ] Prepare producer, typed transport, graph-writer, and snapshot-copy changes, then activate them
  only in the atomic Task 2+3 repository state.
- [ ] Round-trip a disagreement case and an absence case through the real DuckDB writer.
- [ ] Assert `ac_causal_claims`, `ac_skg_edge_evidence`, and aggregate tables keep enum-valid
  candidate evidence separate from authority-weighted evidence; the latter requires a resolved
  ranking receipt. Persist separately named design/credibility/purpose fields.
- [ ] Prove two or more rows with candidate basis and/or publishability admission but no ranking
  receipt retain `authority_confidence=null` / `not_established`, are excluded from the authority
  denominator, and make only an operational contribution of zero.
- [ ] Run focused producer, graph-builder, SKG-store, and integration tests; run Ruff and architecture
  guardrails.

### Task 3: Strangle the pinned legacy snapshot, replay paths, and persisted consumers

**Files:**

- Modify: `src/polisyos/data_forge/domains/academic/knowledge/skg_query.py`
- Modify: `src/polisyos/data_forge/domains/academic/knowledge/store.py`
- Modify: `src/polisyos/data_forge/domains/academic/knowledge/search.py`
- Modify: `src/polisyos/data_forge/domains/academic/knowledge/types.py`
- Modify: `src/polisyos/data_forge/domains/academic/knowledge/parameter_selector.py`
- Modify: `src/polisyos/data_forge/read_api/academic.py`
- Modify: `src/polisyos/scientist/agent/knowledge_tools.py`
- Modify: `src/polisyos/data_forge/domains/academic/knowledge/skg_versioning.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/benchmark.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/qc.py`
- Modify: `src/polisyos/ir/analytics/causal_graph.py`
- Modify: `src/polisyos/ir/analytics/cross_graph.py`
- Modify: `src/polisyos/ir/analytics/parameters.py`
- Modify: `src/polisyos/foundry/methods/catalog/causal/literature_prior.py`
- Modify: `src/polisyos/foundry/methods/catalog/causal/graph_reconciliation.py`
- Modify: `src/polisyos/foundry/methods/catalog/causal/protocols.py`
- Modify: `src/polisyos/foundry/methods/catalog/causal/parameter_transfer.py`
- Modify: `src/polisyos/scientist/nodes/builtins/causal/build_literature_prior.py`
- Modify: `src/polisyos/scientist/nodes/builtins/causal/reconcile_causal_graph.py`
- Modify: `src/polisyos/scientist/nodes/builtins/causal/resolve_parameters.py`
- Modify: `src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py`
- Modify: `src/polisyos/scientist/nodes/builtins/planning/compile_cross_graph_evidence.py`
- Modify: `src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py`
- Modify: `src/polisyos/scientist/nodes/builtins/planning/assemble_legal_candidate_pack.py`
- Modify: `src/polisyos/scientist/cross_graph/compiler.py`
- Modify: `src/polisyos/scientist/cross_graph/conflict_materializer.py`
- Modify: `src/polisyos/scientist/cross_graph/feedback.py`
- Modify: `src/polisyos/data_forge/domains/catalog/knowledge/proxy_resolver.py`
- Modify: `src/polisyos/scientist/methods/discovery/priors.py`
- Modify: `src/polisyos/scientist/methods/discovery/prior_miner.py`
- Modify: `src/polisyos/scientist/methods/search/judge_stack.py`
- Modify: `src/polisyos/scientist/methods/search/actionable_side_information.py`
- Modify: `src/polisyos/scientist/methods/search/promotion_evidence.py`
- Modify: `src/polisyos/scientist/methods/search/adversarial.py`
- Modify: `src/polisyos/scientist/methods/autotune/models.py`
- Modify: `src/polisyos/scientist/methods/search/funnel/level5_refutation_governance.py`
- Modify: `src/polisyos/scientist/methods/search/funnel/level6_promotion.py`
- Modify: `src/polisyos/scientist/methods/search/funnel/level4_full.py`
- Modify: `src/polisyos/scientist/methods/search/pareto_registry.py`
- Modify: `src/polisyos/scientist/methods/search/controller.py`
- Modify: `src/polisyos/scientist/methods/search/readiness.py`
- Modify: `src/polisyos/scientist/cross_graph/gatherers/academic.py`
- Modify: `src/polisyos/scientist/governance/passes/cross_graph_evidence_pass.py`
- Modify: `src/polisyos/scientist/governance/passes/literature_gate_pass.py`
- Modify: `src/polisyos/scientist/governance/passes/transportability_required_pass.py`
- Modify: `src/polisyos/scientist/validation/policy_verified/service.py`
- Modify: `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py`
- Modify: `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_request.py`
- Modify: `src/polisyos/scientist/nodes/builtins/decide/build_policy_output_bundle.py`
- Modify: `src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py`
- Modify: `src/polisyos/scientist/nodes/builtins/decide/run_policy_promotion.py`
- Modify: `src/polisyos/scientist/nodes/builtins/decide/run_policy_translation.py`
- Modify: `src/polisyos/scientist/nodes/builtins/decide/decision_packet/validation.py`
- Modify: `src/polisyos/scientist/nodes/builtins/decide/decision_packet/serialization.py`
- Modify: `src/polisyos/scientist/policy_design/objectives.py`
- Modify: `src/polisyos/scientist/policy_design/search.py`
- Modify: `src/polisyos/scientist/policy_design/translator.py`
- Modify: `src/polisyos/scientist/policy_design/output.py`
- Modify: `src/polisyos/scientist/validation/phase5_preflight.py`
- Modify: `src/polisyos/ir/governance/validation.py`
- Modify: `src/polisyos/scientist/evidence/claims/projections.py`
- Modify: `src/polisyos/runtime/quality/credal_reference.py`
- Modify: `src/polisyos/runtime/quality/capability_index.py`
- Modify: `src/polisyos/runtime/quality/capability_index_compiler.py`
- Modify: `src/polisyos/runtime/quality/capability_discovery.py`
- Modify: `src/polisyos/runtime/quality/capability_resolver.py`
- Modify: `src/polisyos/runtime/quality/capability_authority.py`
- Modify: `src/polisyos/runtime/quality/data_state_substrate.py`
- Modify: `src/polisyos/runtime/quality/generation_cycle.py`
- Modify: `src/polisyos/runtime/quality/world_model_record.py`
- Modify: `src/polisyos/pdc/_impl/world_model_record.py`
- Modify: `src/polisyos/runtime/http/services/control_registry_providers.py`
- Modify: `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py`
- Modify: `src/polisyos/data_requirement/compiler.py`
- Modify: `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py`
- Modify: `tests/unit/data_forge/domains/academic/batch/test_benchmark.py`
- Modify: `tests/unit/data_forge/domains/academic/batch/test_qc.py`
- Create: `tests/unit/data_forge/domains/academic/knowledge/test_store.py`
- Modify: `tests/unit/data_forge/domains/academic/knowledge/test_parameter_selector.py`
- Create: `tests/unit/data_forge/domains/academic/knowledge/test_skg_versioning.py`
- Modify: `tests/unit/data_forge/domains/academic/knowledge/test_knowledge_tools.py`
- Modify: `tests/unit/data_forge/domains/catalog/knowledge/test_proxy_resolver.py`
- Modify: `tests/unit/ir/test_causal_graph_contract.py`
- Modify: `tests/unit/ir/test_context_adaptive_parameter_bundle_contract.py`
- Modify: `tests/unit/ir/artifacts/test_lineage.py`
- Modify: `tests/unit/scientist/cross_graph/test_cross_graph_evidence.py`
- Modify: `tests/unit/scientist/cross_graph/test_conflict_materializer.py`
- Modify: `tests/unit/scientist/cross_graph/test_cross_graph_feedback.py`
- Modify: `tests/unit/scientist/nodes/builtins/causal/test_resolve_transport.py`
- Modify: `tests/unit/scientist/nodes/builtins/causal/test_resolve_parameters.py`
- Modify: `tests/unit/scientist/discovery/test_prior_miner.py`
- Modify: `tests/unit/scientist/discovery/test_priors.py`
- Modify: `tests/unit/scientist/methods/causal/test_readiness.py`
- Modify: `tests/unit/scientist/search/test_phase_b_policy_runtime.py`
- Modify: `tests/unit/scientist/search/test_adversarial.py`
- Modify: `tests/unit/scientist/search/test_promotion_evidence.py`
- Modify: `tests/unit/scientist/discovery/test_output.py`
- Create: `tests/unit/scientist/search/funnel/test_level5_refutation_governance.py`
- Modify: `tests/unit/scientist/search/funnel/test_level4_full.py`
- Modify: `tests/unit/scientist/search/test_pareto_transfer.py`
- Modify: `tests/unit/scientist/search/test_controller_api.py`
- Modify: `tests/unit/scientist/governance/test_cross_graph_evidence_pass.py`
- Modify: `tests/unit/scientist/governance/test_literature_gate_pass.py`
- Modify: `tests/unit/scientist/governance/test_transportability_required_pass.py`
- Modify: `tests/unit/scientist/policy_design/test_policy_verified_workflow_e2e.py`
- Modify: `tests/unit/scientist/nodes/builtins/decide/test_policy_runtime_support.py`
- Create: `tests/unit/scientist/nodes/builtins/decide/test_run_policy_promotion.py`
- Modify: `tests/unit/scientist/nodes/builtins/decide/test_policy_translation.py`
- Modify: `tests/unit/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py`
- Modify: `tests/unit/scientist/nodes/builtins/planning/test_assemble_legal_candidate_pack.py`
- Modify: `tests/unit/scientist/nodes/test_build_policy_output_bundle.py`
- Modify: `tests/unit/scientist/nodes/test_decision_packet_node_v3.py`
- Modify: `tests/unit/scientist/policy_design/test_phase_b_policy_design.py`
- Modify: `tests/unit/scientist/policy_design/test_phase_b_hierarchical_search.py`
- Modify: `tests/unit/scientist/policy_design/test_phase_b_policy_workers.py`
- Modify: `tests/unit/scientist/policy_design/test_phase_b_output.py`
- Modify: `tests/unit/scientist/search/test_policy_blueprint_runtime_guards.py`
- Modify: `tests/unit/foundry/methods/catalog/causal/test_parameter_transfer.py`
- Modify: `tests/unit/runtime/quality/test_credal_reference.py`
- Create: `tests/unit/runtime/quality/test_capability_index.py`
- Modify: `tests/unit/runtime/quality/test_capability_index_compiler.py`
- Modify: `tests/unit/runtime/quality/test_capability_discovery.py`
- Modify: `tests/unit/runtime/quality/test_capability_resolver.py`
- Modify: `tests/integration/runtime_quality/test_data_state_substrate.py`
- Modify: `tests/unit/runtime/quality/test_cycle_substrate.py`
- Modify: `tests/unit/runtime/quality/test_world_model_record.py`
- Modify: `tests/unit/pdc/test_world_model_record_contract.py`
- Modify: `tests/unit/runtime/quality/test_design_generation.py`
- Modify: `tests/unit/runtime/quality/test_grounding_relation.py`
- Modify: `tests/unit/runtime/quality/test_proving_ground_causal_forecast_search.py`
- Modify: `tests/unit/scientist/validation/test_phase5_preflight.py`
- Modify: `tests/unit/scientist/evidence/claims/test_projections.py`

**Interfaces:**

- Extend `SKGQuery`/the academic read owner with one safe projection used by Data Forge and Runtime;
  do not reproduce ID lists or fallback logic at each consumer. Authority-bearing methods return a
  `ResolvedAcademicProjection[T]` carrying the verified current `SourceEpochBinding`, not bare rows;
  the raw/audit route remains explicitly candidate. Every profile/index/parameter carrier and
  semantic or presence-only sink accepts only that resolved wrapper (or a typed non-green outcome),
  not the underlying model, mapping, ref, path, or caller-constructed lookalike. Persisted
  descendants accept only the resolved wrapper, so the binding obligation comes from a recomputed
  read, not a caller's role string.
- Put the recursive propagation/currentness rule in the existing IR lineage owner, and require
  every authority-bearing persist/load helper to use it. It walks actual CAS input manifests to a
  fixed point: if any recursive input carries an academic binding, the output must carry that exact
  current binding or persistence fails. The rule is generic over artifact schemas, not an enum of
  known class names. Non-CAS stores such as the Pareto registry/catalog may not serialize a bound
  evaluation as plain JSON; move the authority-bearing snapshot behind the guarded artifact owner
  and keep only a resolved ref/index locally, or treat the local copy as candidate and refuse it for
  warm-start/ranking. A typed `evidence_independent` input set must be empty of recursively bound
  academic lineage; a caller declaration cannot establish that predicate.
- On the current legacy schema, absence of a holder-verified, content-bound adjudication
  verification receipt marks all 7,868 curated/evidence rows `authority_not_established`.
  Separately compute the 342 claim / 341
  edge fallback-contamination subset for diagnosis. Propagate the limitation to family, contested,
  transport, retraction replay, prior, capability, and forecast consumers. This is a computed read
  limitation, not a write to the substrate.
- Add `ClaimLineageAuditRecord` and paginated `ClaimLineageAuditPage` under the academic knowledge
  owner, with snapshot/input receipt, occurrence and identity totals, axis values/bases,
  authority/limitation status, and occurrence-to-identity refs. Expose
  `ScholarKnowledgeStore.audit_claim_lineage(status=..., cursor=..., limit=...)` through
  `polisyos.data_forge.read_api.academic` and a read-only Scholar knowledge-tool method. This makes
  all 69,798 legacy identities visible as declared absence without loading them into the curated
  claim API.
- Replace `CausalClaimResult.strength` with typed `evidence_strength`, `design_family`,
  `causal_credibility`, basis/status, and provenance fields. Compatibility **is required** because
  this is a public read-API export: add an explicitly versioned v2 DTO and migrate internal
  consumers. The deprecated v1 **audit read** returns `strength=None` plus a typed
  `ambiguous_legacy_vocabulary` limitation; it never guesses. Authority-bearing operations refuse
  that limited result, and no internal semantic consumer may use v1.
- Replace numeric coercion of `strongest_dissent_strength` with the existing producer-owned
  `dominant_direction_agreement` scalar as the numeric quality component, while retaining dissent
  strength as a category. If its evidence/ranking admission is absent, expose a limitation rather
  than assigning a score.
- At the Data Forge owner boundary, persist an append-only SKG projection epoch/admission event
  whose receipt is queryable through the academic read API; do not import Runtime or Scientist to
  push invalidations across the architecture boundary. Make the reusable
  `academic_projection_binding: SourceEpochBinding` mandatory on `PriorKnowledgeBundle`, every
  literature-derived `CausalGraphModel`, `CrossGraphEvidenceProfile`,
  `ContextAdaptiveParameterBundle`, `CapabilityIndex`, and `SkgCausalPriorRef`. Generically
  propagate the same binding into every evaluation/frontier, judge/readiness/actionable-side-
  information, promotion, transportability/policy-output, and `CapabilityBindingResult` artifact
  whose resolved CAS inputs carry it; maintain an enumerated current-set semantic fixture so a new
  descendant cannot silently escape. Canonical loaders/early-return paths produce a resolved
  wrapper only after comparing the binding to the current event; readiness, governance, parameter
  selection/transfer, objectives/search/judges, blueprint/output/translation, decision packets,
  promotion/reconciliation, capability discovery/resolution, data-requirement compilation, and
  simulation accept that resolved form rather than a bare artifact. Missing legacy bindings fail
  closed. A stale/verification-failed input is not `None` or source absence and cannot fall back to
  path-based `available`. Preserve manifest input fingerprints through the capability loader. Its provider cache key is
  `(index_release_ref, academic_projection_receipt_ref, source_skg_epoch)`; on mismatch it clears
  the cached object and refuses until its loader returns a matching reissue. Exercise the default
  HTTP provider, not only the compiler. Reissue is a separate data/artifact-production step.
- Retraction must append a new SKG epoch/event rather than mutate the current edge in place. It
  removes/recomputes `ac_skg_span_grounded_claims` and exact evidence, then invalidates family,
  contested, transport, prior-knowledge bundle, literature-derived causal graph, cross-graph
  profile, capability index, world-model SKG reference, and process-cache descendants. Until
  rebuilt, every descendant refuses the stale source epoch.
- Direct Runtime SQL must route through the safe owner projection or independently fail closed on
  the same typed receipt. A hidden direct read reopens P31.
- Cross-graph compiler/feedback, transport resolution/proxy conversion, and Runtime
  substrate/world-model/PDC reference validation are mandatory consumers even though they contain
  no `strength` token: a count, trust score, or ref/version pair cannot substitute for the resolved
  admission and current epoch.
- `ParameterSelector`, objective/hierarchical search, judge/funnel, conflict materialization,
  runtime-request/output/translation, and decision-packet/legal-pack paths are the same literal-free
  class. `resolve_parameters` must validate an existing parameter-bundle ref before early return;
  its new bundle and Foundry transfer preserve the binding, and raw-dict reconstruction cannot
  strip it. `RequirementToCapabilityResolver` must strangle both bare model/mapping input and its
  `from_duckdb` bypass through the canonical currentness loader, then carry the binding in
  `CapabilityBindingResult` and data-requirement lineage rather than only a release-ref string.
- Pareto registry/controller/policy-search warm starts, Phase-5 judge republish and validation,
  standalone translator/brief persistence, readiness-derived claim projection, and both Level-4
  and Level-5 actionable-side-information producers are mandatory fixed-point descendants. They
  resolve/propagate the binding or return a typed non-green outcome; model/dict coercion, parse
  failure to `None`, ref presence, and unbound JSON/catalog writes cannot restore authority.

- [ ] Write C14–C21, C30–C32, C35–C39, C42–C46, and C48–C52 RED.
- [ ] Implement the single projection and route every semantic consumer enumerated above.
- [ ] Run the synthetic legacy fixture and assert no receipt-less or fallback-tainted result reaches
  authority-bearing query, prior, credal, capability, or forecast consumers.
- [ ] Run the snapshot census read-only and confirm 7,868 receipt-less curated/evidence rows, with
  the diagnostic fallback subset exactly 342 claim/evidence, 341 exact/family/transport, and nine
  contested rows. Do not bake mutable totals into the generic unit contract.
- [ ] Query the raw audit surface and confirm exactly 69,798 identities expose null values and
  `not_established` bases, not silent absence.
- [ ] Prove an old literature prior and process-cached capability index are rejected/reloaded after
  a projection-rule version change.
- [ ] Prove a stale world-model SKG reference is rejected before simulation and that cross-graph
  feedback and transport-proxy confidence cannot recover authority from counts or trust scores.
- [ ] Parameterize the generic currentness falsifier over the full declared
  `academic_projection_binding` artifact set; prove existing-ref early returns and direct CAS decodes
  cannot bypass it, and exercise `ContextAdaptiveParameterBundle`, current policy/search/capability
  descendants, both production `SkgCausalPriorRef` constructors, and every bare profile/index
  factory.
- [ ] Re-run and classify the complete 83-file descendant-symbol / 79-file persistence-load
  candidate census. Then inject a new unlisted derived artifact type: the generic lineage guard
  must propagate/reject it without a source-code allowlist change.
- [ ] Prove stale prior/profile/causal-graph/parameter/index artifacts cannot make readiness,
  governance, parameter/runtime readiness, objective or judge rank, policy verification/output,
  capability binding, data requirements, or promotion green; a failed currentness check cannot
  collapse to `None`, path availability, ref presence, or a raw mapping.
- [ ] Prove a retraction epoch and a failed prior load cannot leave derivative bytes or a prior ref
  presented as current.
- [ ] Run importer tests, public-surface checks, Runtime API contract, Ruff, and architecture
  guardrails.

### Task 4: Prove the full no-data safety close

**Files:**

- Modify: `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py`
- Do not modify: `production_data/**`

- [ ] Run one E2E fixture from each producer through graph build, safe query, Foundry prior,
  Scientist persistence/reconciliation, and Runtime credal projection.
- [ ] Run the negative legacy fixture and prove no generic `moderate`, parent paper design, raw hint,
  or credibility can change design, evidence weight, graph confidence, publication, or Runtime
  status.
- [ ] Run the direct span-grounded sibling writer, retraction replay, prior reuse, and cached-index
  paths; each must resolve the same admission/limitation state. Present the current
  present-but-fake adjudication fixture with every expected marker intact and prove it mutates no
  pointer, projection, report, graph, or conflict output.
- [ ] Present a coherent passing `BenchmarkEvaluation` plus a matching pointer and producer strings;
  without a trust-root-verified evaluator appointment, signature, and bound observation set it must
  yield no evaluation/batch verification receipt and mutate no holder state.
- [ ] Re-present stale `PriorKnowledgeBundle`, literature-derived `CausalGraphModel`,
  `CrossGraphEvidenceProfile`, `ContextAdaptiveParameterBundle`, `CapabilityIndex`, current
  policy/search/capability descendants, and both production `SkgCausalPriorRef` variants; canonical
  loaders and every early-return/authority consumer must refuse before reuse.
- [ ] Run real edge synthesis and transport-score materialization, cross-graph compiler/feedback,
  transport proxy resolution, and Runtime substrate → world-model/PDC admission; none may recover
  authority from an unadmitted category, count, trust score, or reference.
- [ ] Run best-snapshot clone/promotion, benchmark, and QC; none may turn a missing receipt into an
  authoritative snapshot or passing support gate.
- [ ] Exercise the v1/v2 read API, Scholar audit tool, design generation, and grounding relation;
  the typed limitation must survive every wrapper.
- [ ] Exercise every one of the 29 profile carrier candidates and seven capability-index lexical
  candidates from the pinned census. Every contract/carrier/semantic/presence-only site must use
  the current wrapper or have an explicit candidate-only/administrative/out-of-scope ruling;
  parameter selection/transfer, objective/hierarchical ranking, judge/funnel uncertainty,
  blueprint/output/translation, decision packet/legal lineage, capability binding, and data
  requirements are mandatory semantic paths.
- [ ] Classify all 83 descendant-symbol and 79 persistence/load lexical candidates, then exercise
  registry/catalog warm starts, Phase-5 judge/validation publication, translator/brief and
  readiness-claim projections, both actionable-side-information producers, and the generic
  unlisted-descendant falsifier. No allowlist edit may be required for the synthetic descendant.
- [ ] Run an invalid/future-enum fixture and prove the failure is typed and visible.
- [ ] Run blast-radius tests, Ruff, architecture guardrails, runtime API contract, and
  `git diff --check`.
- [ ] Re-run the complete source consumer census and show every semantic reader routes through the
  central typed projection.
- [ ] Recheck the pinned snapshot hash; it must remain exactly
  `583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`.

**Acceptance:** Future writes are explicit and strict; every current authority surface either
resolves a holder-verified, purpose-bound receipt whose evaluator identity is authenticated and
whose benchmark/promotion/result predicates are independently recomputed, or refuses with a typed
limitation; a coherent self-stamped evaluation/pointer, a shape-valid/self-stamped batch, and every
bare/stale profile or index are negative controls; the raw audit
surface makes all 69,798 visibly `not_established`; the receipt-less and specifically tainted
aggregates are quarantined; stale persisted consumers cannot reuse old bytes; and the E2E negative
test proves no authority upgrade. Authority-grade bundle/graph/profile/parameter/search/output/
index/binding/reference availability remains blocked
until an admitted claim classification, an admitted and version-matched numeric ranking calculus,
and matching downstream reissue all exist, but the vocabulary/substitution safety debt can close
without a data build.

### Task 5: Conditional authority restoration decision for evidence ranking

This is **not** part of the no-data safety close and must not be silently decided by an
implementer. Before any claim design or evidence class contributes authority-bearing graph weight,
the academic evidence owner must ratify one of two classification mechanisms:

1. directly adjudicate `EvidenceStrength` with a purpose-scoped, evaluated admission; or
2. ratify a versioned `DesignFamily → EvidenceStrength` policy with an approved semantic oracle,
   mixed-outcome fixtures, future-enum failure, and authority purpose that permits evidence ranking.

Classification is necessary but not sufficient. The same owner must also purpose-admit and version
the **complete numeric ranking calculus**: enum weights, evidence floors, direction weighting,
penalties, noisy-OR aggregation, and the multi-article bonus, with fixtures for each operation and
their composition. The receipt binds the classification mechanism, calculus version, inputs, and
authority purpose; changing any one invalidates the result. The existing
`AdmittedClaimAdjudicationBatch` is insufficient because it merely declares
`academic_claim_edge_publishability`, lacks an authenticated evaluation receipt and holder
verification, and bars method-validity use.
Record both decisions in their
canonical architecture/policy owner before adding code. If either decision is missing, retain
candidate values for audit/search, keep `authority_confidence=null` / `not_established`, and give
the row only an operational contribution of zero. Safety closure does not wait for these choices;
restored availability does. The ratified mechanism must add C33's component and mixed-row tests and
show that an independently verified publishability receipt without the new ranking-purpose receipt still cannot
produce authority confidence.

### Task 6: Conditional occurrence-preserving JSON/snapshot migration (candidate b)

Do not execute as part of the no-data close. Use a new output root and version; never modify or
`chmod` the pinned snapshot.

**Files:**

- Create or extend the existing academic migration owner after a reuse census; do not place a
  one-off writer in `tools/` if the batch owner can express the migration.
- Create: `tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_migration.py`

- [ ] Write C22/C23 RED with exact duplicate, case-only collision, and missing-receipt fixtures.
- [ ] Walk the 137,714 occurrence array, assign a stable identity plus occurrence index, and emit
  explicit fields. Legacy occurrences get declared absence. Because the slim bundle lacks the
  enriched cohort's historical producer/schema receipt, preserve those values only as unverified
  legacy observations unless the omitted source artifact is supplied and content-bound.
- [ ] Emit a content-addressed reconciliation report with input hash, output hash, occurrence total,
  unique-ID total, duplicate groups, exact duplicates, normalization collisions, and rejected rows.
- [ ] Prove `137,714` occurrences and `137,589` identities survive, with all 125 excess occurrences
  accounted for and zero silent replacement.
- [ ] Build and validate a new snapshot; leave the pinned input byte-identical.

### Task 7: Conditional evidence growth and adjudication (candidates f then e)

Do not execute until a separate data-production task is authorized and source artifacts are
available. Re-extraction precedes adjudication for the legacy cohort.

**Files:**

- Modify: `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_api.py`
- Modify as required: `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_providers.py`
- Modify as required: `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/resolve_finalize.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/config.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/claim_adjudicator.py`
- Modify: `src/polisyos/scientist/methods/autotune/claim_adjudication_runtime.py`
- Modify: provider pool fail-fast handling only if still needed
- Modify: corresponding unit/integration tests named C24–C28

- [ ] Select a bounded pilot over source works, not arbitrary claim rows. Record p50/p95 end-to-end
  elapsed time, claim yield, source/fulltext receipt rate, spans per claim, failures, retries, and
  provider call count.
- [ ] Require a content-bound selected-work artifact, resolvable full-text/abstract source receipts,
  configured provider keys/network policy, and a versioned output root. Missing inputs or zero
  usable keys must fail before work begins, not return a successful zero-work run.
- [ ] Re-extract evidence-bearing claims into a new versioned artifact. Do **not** force the old
  stable ID: `stable_claim_id` binds supporting-span IDs, or claim text when spans are absent, so a
  grounded re-extraction will normally change identity. Persist occurrence-level
  `reextraction_of`/`supersedes_legacy_claim_id` lineage and allow explicit split/merge mappings.
- [ ] Add a content-bound missing-only selector over new typed evidence-bearing items that lack an
  admitted adjudication receipt; do not anti-join on old raw IDs or trust a caller-supplied count.
- [ ] Fail before the first provider call when source, champion, candidate/evaluation, lineage,
  credentials, or policy is absent.
- [ ] Add checkpoint/resume with content-bound **candidate** per-item results before a large run.
  Define one execution identity that binds raw input, champion refs/pointer/config/passes, provider
  model, temperature, prompt, output schema, code/rule version, and ordered claim IDs. A resume
  invalidates candidates on any mismatch; final assembly records and verifies the same identity.
  Checkpoint artifacts and the assembled batch remain candidate permanently. The champion itself
  is admissible only through Task 2's trust-root-verified evaluator appointment/receipt over a
  content-bound benchmark observation set; the batch verifier independently recomputes its
  metrics, guards, promotability, and promotion before considering the batch. Only that named
  non-producer verifier may then resolve the entire frozen chain, replay the publishability
  predicates, and issue the holder-verifiable receipt; self-declared evaluation and final-batch
  artifacts grant nothing.
  Each field is authoritative only for that verified receipt's declared purpose. The current v1
  batch grants no holder authority, cannot upgrade method or ranking fields, and does not bind
  model/temperature, so it is insufficient until extended. A shard/composition admission would be
  a separate design.
- [ ] Run adjudication only on typed, evidence-bearing claims; optimistic responses with absent
  evidence remain non-publishable.
- [ ] If evidence ranking is required, consume only the Task 5 ratified purpose; publishability
  admission alone cannot authorize method/design weights.
- [ ] Publish a new snapshot and replay all downstream graph/Runtime tests. Report how many of the
  former 69,798 remain `not_established`; zero is not required for honesty.

## Reproduction Commands and Receipts

All commands were run from:

```bash
cd /Users/deniskopylov/polisyos/.worktrees/debt-b-extraction-vocabulary/policy-engine
```

### Branch, complete file denominator, and integrity

```bash
git status -sb
git symbolic-ref -q HEAD
git rev-parse HEAD
git rev-parse main
git merge-base HEAD fac07ffc6281e53e5a58c8a30c3b848a6b60e0e5
git ls-tree -r --name-only fac07ffc6281e53e5a58c8a30c3b848a6b60e0e5 |
  awk 'BEGIN{s=0;t=0;all=0} {all++} /^src\/.*\.py$/ {s++} /^tests\/.*\.py$/ {t++}
       END{print "tracked",all,"src_py",s,"tests_py",t,"total_py",s+t}'
```

`main` is recorded only as an orientation receipt; every census is pinned to the immutable full
commit above. The fail-closed hash bracket is inside the database command below.

Receipt:

```text
refs/heads/codex/debt-b-extraction-vocabulary
fac07ffc6281e53e5a58c8a30c3b848a6b60e0e5
main-at-measurement fac07ffc6281e53e5a58c8a30c3b848a6b60e0e5
merge-base fac07ffc6281e53e5a58c8a30c3b848a6b60e0e5
tracked 10508 src_py 2618 tests_py 2490 total_py 5108
```

### Relational, JSON, adjudication, and live-fallback census

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B - <<'PY'
from collections import Counter
import hashlib
import json
from pathlib import Path
import duckdb

p = Path(
    "production_data/policyos_academic_runtime_slim_20260411T112032Z/"
    "academic/graph/scholar_knowledge.duckdb"
)
expected_sha256 = "583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967"

def snapshot_sha256() -> str:
    with p.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()

before_sha256 = snapshot_sha256()
print("snapshot_sha256_before", before_sha256)
if before_sha256 != expected_sha256:
    raise SystemExit("STOP: pinned snapshot hash changed before census")

con = None
try:
    con = duckdb.connect(str(p), read_only=True)
    print("table_counts", con.execute("""
      SELECT (SELECT count(*) FROM ac_article_extractions),
             (SELECT count(*) FROM ac_causal_claims_raw),
             (SELECT count(*) FROM ac_claim_adjudications),
             (SELECT count(*) FROM ac_causal_claims),
             (SELECT count(*) FROM ac_skg_edges),
             (SELECT count(*) FROM ac_skg_edge_evidence),
             (SELECT count(*) FROM ac_skg_family_edges),
             (SELECT count(*) FROM ac_skg_contested_edges),
             (SELECT count(*) FROM ac_skg_transport_scores),
             (SELECT count(*) FROM ac_skg_simulation_parameters),
             (SELECT count(*) FROM information_schema.tables
              WHERE table_name='ac_skg_span_grounded_claims')
    """).fetchone())
    print("raw_schema", con.execute("""
      SELECT column_name FROM information_schema.columns
      WHERE table_name='ac_causal_claims_raw' ORDER BY ordinal_position
    """).fetchall())
    print("raw_identities", con.execute("""
      SELECT count(*),count(DISTINCT id),
        count(*) FILTER (WHERE nullif(trim(id),'') IS NULL),count(DISTINCT work_id)
      FROM ac_causal_claims_raw
    """).fetchone())
    print("raw_partition", con.execute("""
      SELECT count(*),
        count(*) FILTER (WHERE nullif(trim(design_family_hint),'') IS NOT NULL),
        count(*) FILTER (WHERE nullif(trim(design_family_hint),'') IS NULL),
        count(*) FILTER (WHERE strength='moderate'),
        count(*) FILTER (WHERE strength='moderate'
                         AND nullif(trim(design_family_hint),'') IS NOT NULL),
        count(*) FILTER (WHERE strength<>'moderate'
                         AND nullif(trim(design_family_hint),'') IS NULL)
      FROM ac_causal_claims_raw
    """).fetchone())
    print("raw_strength", con.execute(
      "SELECT strength,count(*) FROM ac_causal_claims_raw GROUP BY 1 ORDER BY 2 DESC,1"
    ).fetchall())
    print("raw_hint_strength_joint", con.execute("""
      SELECT coalesce(nullif(trim(design_family_hint),''),'<BLANK>'),
             coalesce(nullif(trim(strength),''),'<BLANK>'),count(*)
      FROM ac_causal_claims_raw GROUP BY 1,2 ORDER BY 1,2
    """).fetchall())
    print("adjudication_join", con.execute("""
      SELECT count(*) raw, count(a.claim_id) adjudicated,
        count(*) FILTER (WHERE a.claim_id IS NULL) unadjudicated,
        count(*) FILTER (WHERE a.claim_id IS NULL AND r.strength='moderate'),
        count(*) FILTER (WHERE a.claim_id IS NOT NULL
                         AND nullif(trim(r.design_family_hint),'') IS NULL),
        count(*) FILTER (WHERE a.claim_id IS NULL
                         AND nullif(trim(r.design_family_hint),'') IS NOT NULL)
      FROM ac_causal_claims_raw r
      LEFT JOIN ac_claim_adjudications a ON a.claim_id=r.id
    """).fetchone())
    print("unadjudicated_works", con.execute("""
      SELECT count(DISTINCT r.work_id)
      FROM ac_causal_claims_raw r
      LEFT JOIN ac_claim_adjudications a ON a.claim_id=r.id
      WHERE a.claim_id IS NULL
    """).fetchone())
    print("required_adjudication_fields", con.execute("""
      SELECT count(*),
        count(*) FILTER (WHERE nullif(trim(design_family),'') IS NOT NULL),
        count(*) FILTER (WHERE nullif(trim(causal_credibility),'') IS NOT NULL),
        count(*) FILTER (WHERE nullif(trim(risk_of_bias),'') IS NOT NULL),
        count(*) FILTER (WHERE nullif(trim(support_status),'') IS NOT NULL),
        count(claim_validity_score), count(adjudication_confidence)
      FROM ac_claim_adjudications
    """).fetchone())
    print("adjudication_reverse_gap", con.execute("""
      SELECT count(*) FROM ac_claim_adjudications a
      LEFT JOIN ac_causal_claims_raw r ON r.id=a.claim_id WHERE r.id IS NULL
    """).fetchone())
    adjudication_columns = con.execute("""
      SELECT column_name,data_type FROM information_schema.columns
      WHERE table_name='ac_claim_adjudications' ORDER BY ordinal_position
    """).fetchall()
    print("adjudication_columns", adjudication_columns)
    adjudication_profile = []
    for column_name, data_type in adjudication_columns:
        quoted = '"' + column_name.replace('"', '""') + '"'
        null_count = con.execute(
            f"SELECT count(*) FILTER (WHERE {quoted} IS NULL) "
            "FROM ac_claim_adjudications"
        ).fetchone()[0]
        blank_count = None
        if data_type in {"VARCHAR", "CHAR", "TEXT"}:
            blank_count = con.execute(
                f"SELECT count(*) FILTER (WHERE {quoted} IS NOT NULL "
                f"AND trim({quoted})='') FROM ac_claim_adjudications"
            ).fetchone()[0]
        adjudication_profile.append(
            (column_name, data_type, null_count, blank_count)
        )
    print("adjudication_field_profile", adjudication_profile)
    print("adjudication_constants", con.execute("""
      SELECT min(consensus_passes),max(consensus_passes),count(DISTINCT consensus_passes),
        min(consensus_stability),max(consensus_stability),count(DISTINCT consensus_stability),
        min(claim_type_confidence),max(claim_type_confidence),
          count(DISTINCT claim_type_confidence),
        min(design_family_confidence),max(design_family_confidence),
          count(DISTINCT design_family_confidence),
        min(direction_confidence),max(direction_confidence),
          count(DISTINCT direction_confidence)
      FROM ac_claim_adjudications
    """).fetchone())
    print("json_container_validity", con.execute("""
      SELECT count(*),
        count(*) FILTER (WHERE json_valid(extraction_json)),
        count(*) FILTER (WHERE json_type(CAST(extraction_json AS JSON))='OBJECT'),
        count(*) FILTER (
          WHERE json_type(json_extract(extraction_json,'$.causal_claims'))='ARRAY'
        )
      FROM ac_article_extractions
    """).fetchone())
    print("json_shapes_modes", con.execute("""
      WITH claims AS (
        SELECT e.extraction_mode, j.value claim
        FROM ac_article_extractions e,
             LATERAL json_each(e.extraction_json, '$.causal_claims') j
      )
      SELECT extraction_mode,
        array_length(json_keys(claim)),
        array_to_string(list_sort(json_keys(claim)),'|'),
        json_extract_string(claim,'$.strength'), count(*)
      FROM claims GROUP BY 1,2,3,4 ORDER BY 1,2,4
    """).fetchall())
    print("json_work_integrity", con.execute("""
      WITH claim_works AS (
        SELECT e.work_id FROM ac_article_extractions e,
             LATERAL json_each(e.extraction_json,'$.causal_claims') j
      )
      SELECT count(*),count(*) FILTER (WHERE w.id IS NULL),
        count(*) FILTER (WHERE coalesce(w.is_retracted,FALSE))
      FROM claim_works c LEFT JOIN ac_works w ON w.id=c.work_id
    """).fetchone())
    print("json_id_reconciliation", con.execute(r"""
      WITH claims AS MATERIALIZED (
        SELECT e.work_id, j.value claim_json,
          CASE WHEN nullif(trim(json_extract_string(j.value,'$.claim_id')),'') IS NOT NULL
            THEN trim(json_extract_string(j.value,'$.claim_id'))
            ELSE substr(sha256(
              lower(trim(e.work_id)) || '|' ||
              lower(trim(coalesce(json_extract_string(j.value,'$.cause'),''))) || '|' ||
              lower(trim(coalesce(json_extract_string(j.value,'$.effect'),''))) || '|' ||
              lower(trim(coalesce(json_extract_string(j.value,'$.direction'),''))) || '||'
            ),1,24)
          END stable_claim_id
        FROM ac_article_extractions e,
             LATERAL json_each(e.extraction_json,'$.causal_claims') j
      )
      SELECT count(*), count(DISTINCT stable_claim_id),
             count(*)-count(DISTINCT stable_claim_id),
             count(*) FILTER (WHERE r.id IS NULL), count(DISTINCT r.id)
      FROM claims c LEFT JOIN ac_causal_claims_raw r ON r.id=c.stable_claim_id
    """).fetchone())
    print("raw_without_json", con.execute(r"""
      WITH claims AS MATERIALIZED (
        SELECT CASE
          WHEN nullif(trim(json_extract_string(j.value,'$.claim_id')),'') IS NOT NULL
            THEN trim(json_extract_string(j.value,'$.claim_id'))
          ELSE substr(sha256(
            lower(trim(e.work_id)) || '|' ||
            lower(trim(coalesce(json_extract_string(j.value,'$.cause'),''))) || '|' ||
            lower(trim(coalesce(json_extract_string(j.value,'$.effect'),''))) || '|' ||
            lower(trim(coalesce(json_extract_string(j.value,'$.direction'),''))) || '||'
          ),1,24) END stable_claim_id
        FROM ac_article_extractions e,
             LATERAL json_each(e.extraction_json,'$.causal_claims') j
      )
      SELECT count(*) FROM ac_causal_claims_raw r
      LEFT JOIN (SELECT DISTINCT stable_claim_id FROM claims) c
        ON c.stable_claim_id=r.id
      WHERE c.stable_claim_id IS NULL
    """).fetchone())
    occurrence_cte = r"""
      WITH claims AS MATERIALIZED (
        SELECT e.extraction_id,e.work_id,cast(j.key AS INTEGER) claim_index,
          cast(j.value AS VARCHAR) claim_json,j.value claim,
          CASE
            WHEN nullif(trim(json_extract_string(j.value,'$.claim_id')),'') IS NOT NULL
              THEN trim(json_extract_string(j.value,'$.claim_id'))
            ELSE substr(sha256(
              lower(trim(e.work_id)) || '|' ||
              lower(trim(coalesce(json_extract_string(j.value,'$.cause'),''))) || '|' ||
              lower(trim(coalesce(json_extract_string(j.value,'$.effect'),''))) || '|' ||
              lower(trim(coalesce(json_extract_string(j.value,'$.direction'),''))) || '||'
            ),1,24)
          END stable_claim_id
        FROM ac_article_extractions e,
             LATERAL json_each(e.extraction_json,'$.causal_claims') j
      ), groups AS (
        SELECT stable_claim_id,count(*) group_size,
          count(DISTINCT claim_json) distinct_json,max(claim_index) retained_index,
          count(DISTINCT extraction_id) extraction_count
        FROM claims GROUP BY stable_claim_id HAVING count(*)>1
      )
    """
    print("duplicate_summary", con.execute(occurrence_cte + """
      SELECT count(*),sum(group_size),sum(group_size-1),
        sum(group_size-distinct_json),sum(distinct_json-1),histogram(group_size)
      FROM groups
    """).fetchone())
    dropped_occurrences = con.execute(occurrence_cte + """
      SELECT c.stable_claim_id,c.extraction_id,c.work_id,c.claim_index,
        g.retained_index,g.group_size,
        CASE WHEN g.distinct_json=1 THEN 'byte_identical'
             ELSE 'case_normalization_collision' END
      FROM claims c JOIN groups g USING (stable_claim_id)
      WHERE c.claim_index<>g.retained_index
      ORDER BY c.stable_claim_id,c.claim_index
    """).fetchall()
    print("dropped_occurrences", len(dropped_occurrences), dropped_occurrences)
    print("retained_last_match", con.execute(occurrence_cte + """
      , retained AS (
        SELECT c.* FROM claims c JOIN groups g USING (stable_claim_id)
        WHERE c.claim_index=g.retained_index
      )
      SELECT count(*),count(*) FILTER (WHERE
        r.work_id IS NOT DISTINCT FROM x.work_id AND
        r.cause IS NOT DISTINCT FROM json_extract_string(x.claim,'$.cause') AND
        r.effect IS NOT DISTINCT FROM json_extract_string(x.claim,'$.effect') AND
        r.direction IS NOT DISTINCT FROM json_extract_string(x.claim,'$.direction') AND
        r.strength IS NOT DISTINCT FROM json_extract_string(x.claim,'$.strength') AND
        r.mechanism IS NOT DISTINCT FROM json_extract_string(x.claim,'$.mechanism')),
        max(g.extraction_count)
      FROM retained x JOIN groups g USING (stable_claim_id)
      JOIN ac_causal_claims_raw r ON r.id=x.stable_claim_id
    """).fetchone())
    print("public_claim_strength_contract", con.execute("""
      SELECT count(*),
        count(*) FILTER (WHERE strength IN ('strong','moderate','weak')),
        count(*) FILTER (WHERE strength NOT IN ('strong','moderate','weak'))
      FROM ac_causal_claims
    """).fetchone())
    print("credibility_fallback_rows", con.execute("""
      SELECT a.design_family,a.causal_credibility,c.strength,count(*)
      FROM ac_causal_claims c
      JOIN ac_claim_adjudications a ON a.claim_id=c.id
      WHERE lower(trim(a.design_family)) NOT IN
        ('rct','iv','did','rdd','synthetic_control','event_study',
         'quasi_experimental_other','quasi_experimental_did','quasi_experimental_rdd',
         'meta_analysis','panel_fe','system_gmm','gmm','structural_model',
         'time_series_cointegration','ols','ols_cross_sectional')
        AND lower(trim(a.causal_credibility)) IN ('strong','moderate','weak')
      GROUP BY 1,2,3 ORDER BY 4 DESC,1,2
    """).fetchall())
    print("legacy_curated_promotions", con.execute("""
      SELECT count(*) FROM ac_causal_claims c
      JOIN ac_causal_claims_raw r ON r.id=c.id
      WHERE r.strength='moderate' AND nullif(trim(r.design_family_hint),'') IS NULL
    """).fetchone())
    print("curated_hint_adjudication_disagreements", con.execute("""
      SELECT count(*) FROM ac_causal_claims c
      JOIN ac_claim_adjudications a ON a.claim_id=c.id
      WHERE lower(trim(c.design_family_hint))<>lower(trim(a.design_family))
    """).fetchone())

    fallback_sql = """
      SELECT c.id FROM ac_causal_claims c
      JOIN ac_claim_adjudications a ON a.claim_id=c.id
      WHERE lower(trim(a.design_family)) NOT IN
        ('rct','iv','did','rdd','synthetic_control','event_study',
         'quasi_experimental_other','quasi_experimental_did',
         'quasi_experimental_rdd','meta_analysis','panel_fe','system_gmm','gmm',
         'structural_model','time_series_cointegration','ols','ols_cross_sectional')
        AND lower(trim(a.causal_credibility)) IN ('strong','moderate','weak')
    """
    fallback_claim_ids = {row[0] for row in con.execute(fallback_sql).fetchall()}
    print("fallback_raw_strength", con.execute(
        "WITH fallback AS (" + fallback_sql + ") "
        "SELECT r.strength,count(*) FROM fallback f "
        "JOIN ac_causal_claims_raw r ON r.id=f.id "
        "GROUP BY 1 ORDER BY 2 DESC,1"
    ).fetchall())
    edge_evidence = con.execute(
      "SELECT edge_id,claim_id FROM ac_skg_edge_evidence"
    ).fetchall()
    affected_evidence = [row for row in edge_evidence if row[1] in fallback_claim_ids]
    affected_edge_ids = {row[0] for row in affected_evidence}

    def rows_with_claim_refs(table_name: str) -> int:
        total = 0
        for (raw_refs,) in con.execute(
            f"SELECT claim_refs FROM {table_name}"
        ).fetchall():
            refs = set(json.loads(raw_refs or "[]"))
            total += bool(refs & fallback_claim_ids)
        return total

    family_count = rows_with_claim_refs("ac_skg_family_edges")
    contested_count = rows_with_claim_refs("ac_skg_contested_edges")
    transport_count = sum(
        edge_id in affected_edge_ids
        for (edge_id,) in con.execute("SELECT edge_id FROM ac_skg_transport_scores").fetchall()
    )
    simulation_count = 0
    for (raw_refs,) in con.execute(
        "SELECT linked_claim_ids_json FROM ac_skg_simulation_parameters"
    ).fetchall():
        simulation_count += bool(set(json.loads(raw_refs or "[]")) & fallback_claim_ids)
    affected_edges = [
        row for row in con.execute(
            "SELECT edge_id,evidence_strength,confidence FROM ac_skg_edges"
        ).fetchall()
        if row[0] in affected_edge_ids
    ]
    edge_categories = Counter(row[1] for row in affected_edges)
    confidence_bands = Counter(
        "lt_0_35" if row[2] < 0.35 else "lt_0_75" if row[2] < 0.75 else "gte_0_75"
        for row in affected_edges
    )
    print(
        "fallback_propagation",
        len(fallback_claim_ids),len(affected_evidence),len(affected_edge_ids),
        family_count,contested_count,transport_count,simulation_count,
    )
    print("fallback_edge_categories", sorted(edge_categories.items()))
    print("fallback_confidence_bands", sorted(confidence_bands.items()))
    print("dissent_strength", con.execute("""
      SELECT coalesce(nullif(strongest_dissent_strength,''),'<BLANK>'),count(*)
      FROM ac_skg_contested_edges GROUP BY 1 ORDER BY 2 DESC,1
    """).fetchall())
    print("dissent_numeric_shape", con.execute("""
      SELECT count(*),
        count(*) FILTER (WHERE nullif(strongest_dissent_strength,'') IS NOT NULL),
        count(*) FILTER (WHERE try_cast(strongest_dissent_strength AS DOUBLE) IS NOT NULL)
      FROM ac_skg_contested_edges
    """).fetchone())
finally:
    if con is not None:
        con.close()
    after_sha256 = snapshot_sha256()
    print("snapshot_sha256_after", after_sha256)
    if after_sha256 != expected_sha256:
        raise SystemExit("STOP: pinned snapshot hash changed during census")
PY
```

Headline receipt:

```text
snapshot_sha256_before 583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967
table_counts (310829,137589,67791,7868,7607,7868,15945,723,7607,5124,0)
raw_identities (137589,137589,0,65335)
raw_partition (137589,67791,69798,69798,0,0)
adjudication_join (137589,67791,69798,69798,0,0)
unadjudicated_works (49241,)
required_adjudication_fields (67791,67791,67791,67791,67791,67791,67791)
adjudication_reverse_gap (0,)
adjudication_field_profile: all 25 columns have zero NULL except
  design_quality_tier=35443; all text columns have zero blanks except
  publish_blockers=7333 and adjudication_notes=4
adjudication_constants: each of consensus_passes, consensus_stability,
  claim_type_confidence, design_family_confidence, direction_confidence has one value;
  passes=1 and all four confidence/stability values=1.0
json_container_validity (310829,310829,310829,310829)
json modes/keysets: deterministic 5-key moderate 58671;
                    resolve_extract 5-key moderate 11252;
                    resolve_extract exact 23-key enriched 67791
json_work_integrity (137714,0,0)
json_id_reconciliation (137714,137589,125,0,137589)
raw_without_json (0,)
duplicate_summary (111,236,125,121,4,{2:100,3:8,4:3})
dropped_occurrences: 125 exact occurrence rows; four carry reason case_normalization_collision
retained_last_match (111,111,1)
public_claim_strength_contract (7868,0,7868)
credibility fallback: 163 + 127 + 24 + 24 + 4 = 342
fallback raw strength: observational 150, theoretical 80, quasi_natural 62,
  unknown 46, meta_analysis 2, rct 2
legacy_curated_promotions (0,)
curated_hint_adjudication_disagreements (566,)
fallback_propagation 342 342 341 341 9 341 40
fallback edge categories: meta_analysis 1, observational 334, quasi_natural 4, rct 2
fallback confidence bands: below .35 334, [.35,.75) 6, at least .75 1
dissent_numeric_shape (723,155,0)
snapshot_sha256_after 583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967
```

### Duplicate-group classification

The following complete query is runnable on the same read-only connection; it does not depend on a
session-local view. It prints both the aggregate and the exact 125 occurrence rows that did not
become the retained identity row:

```sql
WITH claims AS MATERIALIZED (
  SELECT e.extraction_id,e.work_id,cast(j.key AS INTEGER) AS claim_index,
    cast(j.value AS VARCHAR) AS claim_json,j.value AS claim,
    CASE
      WHEN nullif(trim(json_extract_string(j.value,'$.claim_id')),'') IS NOT NULL
        THEN trim(json_extract_string(j.value,'$.claim_id'))
      ELSE substr(sha256(
        lower(trim(e.work_id)) || '|' ||
        lower(trim(coalesce(json_extract_string(j.value,'$.cause'),''))) || '|' ||
        lower(trim(coalesce(json_extract_string(j.value,'$.effect'),''))) || '|' ||
        lower(trim(coalesce(json_extract_string(j.value,'$.direction'),''))) || '||'
      ),1,24)
    END AS stable_claim_id
  FROM ac_article_extractions e,
       LATERAL json_each(e.extraction_json,'$.causal_claims') j
), groups AS (
  SELECT stable_claim_id,count(*) AS group_size,
    count(DISTINCT claim_json) AS distinct_json,max(claim_index) AS retained_index
  FROM claims GROUP BY stable_claim_id HAVING count(*)>1
)
SELECT count(*) AS duplicate_groups,sum(group_size) AS objects_in_groups,
  sum(group_size-1) AS total_excess,
  sum(group_size-distinct_json) AS byte_identical_excess,
  sum(distinct_json-1) AS normalized_nonidentical_excess,
  histogram(group_size) AS group_size_histogram
FROM groups;

WITH claims AS MATERIALIZED (
  SELECT e.extraction_id,e.work_id,cast(j.key AS INTEGER) AS claim_index,
    cast(j.value AS VARCHAR) AS claim_json,
    CASE
      WHEN nullif(trim(json_extract_string(j.value,'$.claim_id')),'') IS NOT NULL
        THEN trim(json_extract_string(j.value,'$.claim_id'))
      ELSE substr(sha256(
        lower(trim(e.work_id)) || '|' ||
        lower(trim(coalesce(json_extract_string(j.value,'$.cause'),''))) || '|' ||
        lower(trim(coalesce(json_extract_string(j.value,'$.effect'),''))) || '|' ||
        lower(trim(coalesce(json_extract_string(j.value,'$.direction'),''))) || '||'
      ),1,24)
    END AS stable_claim_id
  FROM ac_article_extractions e,
       LATERAL json_each(e.extraction_json,'$.causal_claims') j
), groups AS (
  SELECT stable_claim_id,count(*) AS group_size,
    count(DISTINCT claim_json) AS distinct_json,max(claim_index) AS retained_index
  FROM claims GROUP BY stable_claim_id HAVING count(*)>1
)
SELECT c.stable_claim_id,c.extraction_id,c.work_id,c.claim_index AS dropped_index,
  g.retained_index,g.group_size,
  CASE WHEN g.distinct_json=1 THEN 'byte_identical'
       ELSE 'case_normalization_collision' END AS reason
FROM claims c JOIN groups g USING (stable_claim_id)
WHERE c.claim_index<>g.retained_index
ORDER BY c.stable_claim_id,c.claim_index;
```

Receipt: aggregate `(111, 236, 125, 121, 4)`; group sizes
`[(2,100),(3,8),(4,3)]`; the second query returns exactly 125 rows. A companion comparison of all
six stored claim fields returned `(111 duplicate identities, 111 matching the greatest array
index)`. All duplicate groups belong to one extraction record, so the greatest index is
unambiguous. The companion query is:

```sql
WITH claims AS MATERIALIZED (
  SELECT e.extraction_id,e.work_id,cast(j.key AS INTEGER) AS claim_index,j.value AS claim,
    CASE WHEN nullif(trim(json_extract_string(j.value,'$.claim_id')),'') IS NOT NULL
      THEN trim(json_extract_string(j.value,'$.claim_id'))
      ELSE substr(sha256(lower(trim(e.work_id)) || '|' ||
        lower(trim(coalesce(json_extract_string(j.value,'$.cause'),''))) || '|' ||
        lower(trim(coalesce(json_extract_string(j.value,'$.effect'),''))) || '|' ||
        lower(trim(coalesce(json_extract_string(j.value,'$.direction'),''))) || '||'),1,24)
    END AS stable_claim_id
  FROM ac_article_extractions e,
       LATERAL json_each(e.extraction_json,'$.causal_claims') j
), groups AS (
  SELECT stable_claim_id,max(claim_index) AS retained_index,
         count(DISTINCT extraction_id) AS extraction_count
  FROM claims GROUP BY stable_claim_id HAVING count(*)>1
), retained AS (
  SELECT c.* FROM claims c JOIN groups g USING (stable_claim_id)
  WHERE c.claim_index=g.retained_index
)
SELECT count(*) AS duplicate_identities,
  count(*) FILTER (WHERE
    r.work_id IS NOT DISTINCT FROM x.work_id AND
    r.cause IS NOT DISTINCT FROM json_extract_string(x.claim,'$.cause') AND
    r.effect IS NOT DISTINCT FROM json_extract_string(x.claim,'$.effect') AND
    r.direction IS NOT DISTINCT FROM json_extract_string(x.claim,'$.direction') AND
    r.strength IS NOT DISTINCT FROM json_extract_string(x.claim,'$.strength') AND
    r.mechanism IS NOT DISTINCT FROM json_extract_string(x.claim,'$.mechanism')
  ) AS retained_last_matches,
  max(g.extraction_count) AS max_extractions_per_duplicate_id
FROM retained x
JOIN groups g USING (stable_claim_id)
JOIN ac_causal_claims_raw r ON r.id=x.stable_claim_id;
```

### Enum and history census

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B - <<'PY'
import ast
from pathlib import Path

tree = ast.parse(Path('src/polisyos/ir/analytics/literature.py').read_text())
found = {}
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name in {
        'EvidenceStrength', 'DesignFamily', 'CausalCredibility'
    }:
        found[node.name] = [
            stmt.value.value for stmt in node.body
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant)
        ]
for name, values in found.items():
    print(name, len(values), values)
print(sorted(set(found['EvidenceStrength']) & set(found['DesignFamily'])))
PY
git log --reverse --format='%H %aI %s' -S'class EvidenceStrength' -- \
  src/polisyos/ir/analytics/literature.py | head -1
git log --reverse --format='%H %aI %s' -S'class DesignFamily' -- \
  src/polisyos/ir/analytics/literature.py | head -1
git show -s --format='%H %aI %s' 4c79120c6b7f584a1baebf26c57237ed98686c68
git show -s --format='%H %aI %s' d5dbfabe2cd5bcf31824c52bdc4ea4099283350a
git show d5dbfabe2cd5bcf31824c52bdc4ea4099283350a:policy-engine/src/polisyos/ir/analytics/literature.py |
  sed -n '/class DesignFamily/,/class SourceBasis/p;/class CausalClaim/,/class LiteratureStudy/p'
```

Receipt: enum cardinalities `10`, `20`, `5`; four-way overlap
`meta_analysis,panel_fe,rct,theoretical`; introduction dates 2026-02-28 and 2026-03-08.

### Producer and consumer census

```zsh
revision=fac07ffc6281e53e5a58c8a30c3b848a6b60e0e5
semantic_re='EvidenceStrength|evidence_strength|design_family_hint'
table_re='ac_article_extractions|ac_claim_adjudications|ac_causal_claims(_raw)?|ac_skg_edge_evidence|ac_skg_edges|ac_skg_family_edges|ac_skg_contested_edges|ac_skg_transport_scores|ac_skg_span_grounded_claims'

git ls-tree -r --name-only "$revision" |
  awk 'BEGIN{all=0;src=0;srcpy=0} {all++} /^src\// {src++}
       /^src\/.*\.py$/ {srcpy++}
       END {print "tracked",all,"src_paths",src,"src_py",srcpy}'

git grep -l -I -E "$semantic_re" "$revision" -- 'src/**/*.py' |
  sed 's#^[^:]*:##' | sort
git grep -l -I -E "$table_re" "$revision" -- 'src/**/*.py' |
  sed 's#^[^:]*:##' | sort
comm -12 \
  <(git grep -l -I -E "$semantic_re" "$revision" -- 'src/**/*.py' |
    sed 's#^[^:]*:##' | sort) \
  <(git grep -l -I -E "$table_re" "$revision" -- 'src/**/*.py' |
    sed 's#^[^:]*:##' | sort)
git grep -l -I -E "$semantic_re|$table_re" "$revision" -- 'src/**/*.py' |
  sed 's#^[^:]*:##' | sort

git grep -n -E \
  '"strength"[[:space:]]*:[[:space:]]*(claim\.evidence_strength\.value|"moderate"|"strong\|moderate\|weak")|claim\.get\("strength"|\["strength"\]' \
  "$revision" -- 'src/polisyos/**/*.py'

# Pinned literal-free consumer extensions (the ranges are the cited witnesses above).
git show "$revision:./src/polisyos/scientist/cross_graph/compiler.py" |
  sed -n '927,990p'
git show "$revision:./src/polisyos/scientist/cross_graph/feedback.py" |
  sed -n '159,188p'
git show "$revision:./src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py" |
  sed -n '499,504p;840,874p'
git show "$revision:./src/polisyos/data_forge/domains/catalog/knowledge/proxy_resolver.py" |
  sed -n '194,218p;262,301p'
git show "$revision:./src/polisyos/runtime/quality/data_state_substrate.py" |
  sed -n '474,592p;1321,1342p'
git show "$revision:./src/polisyos/runtime/quality/world_model_record.py" |
  sed -n '762,813p'
git show "$revision:./src/polisyos/pdc/_impl/world_model_record.py" |
  sed -n '111,119p'
git show "$revision:./src/polisyos/scientist/methods/discovery/prior_miner.py" |
  sed -n '93,111p;134,189p'
git show "$revision:./src/polisyos/scientist/methods/discovery/priors.py" |
  sed -n '106,128p;254,283p'
git show "$revision:./src/polisyos/scientist/methods/search/readiness.py" |
  sed -n '1020,1062p'
git show "$revision:./src/polisyos/scientist/nodes/builtins/planning/compile_cross_graph_evidence.py" |
  sed -n '121,122p;304,305p'
git show "$revision:./src/polisyos/ir/analytics/cross_graph.py" |
  sed -n '952,967p;1083,1110p'
git show "$revision:./src/polisyos/scientist/nodes/builtins/causal/reconcile_causal_graph.py" |
  sed -n '561,573p'
git show "$revision:./src/polisyos/ir/analytics/causal_graph.py" |
  sed -n '137,150p;359,386p'
git show "$revision:./src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py" |
  sed -n '814,859p;1169,1265p'
git show "$revision:./src/polisyos/scientist/nodes/builtins/decide/run_policy_promotion.py" |
  sed -n '183,212p'
git show "$revision:./src/polisyos/scientist/governance/passes/cross_graph_evidence_pass.py" |
  sed -n '185,199p'
git show "$revision:./src/polisyos/scientist/governance/passes/literature_gate_pass.py" |
  sed -n '104,169p'
git show "$revision:./src/polisyos/scientist/validation/policy_verified/service.py" |
  sed -n '706,720p'
git show "$revision:./src/polisyos/runtime/quality/generation_cycle.py" |
  sed -n '4451,4455p'
```

Receipts: `tracked=10508`, `src_paths=2828`, `src_py=2618`; semantic-token files `39`, table-literal
files `15`, overlap `8`, union `46`. The final targeted command returns six sites across four files:
the rich serializer, graph builder's three generic reads, the selective LLM prompt, and the
deterministic parser write. `parser.py` and `llm_extractor.py` are outside the 46-file union, so the
expanded lexical set is 48 files. Appendix A classifies the union and names the literal-free
call-chain extensions; it does not pretend grep proves a negative.

### Profile/index carrier and adjudication-verifier census

```zsh
revision=fac07ffc6281e53e5a58c8a30c3b848a6b60e0e5
profile_exact_re='CrossGraphEvidenceProfile'
profile_owner_re='CrossGraphEvidenceProfile|CrossGraphEvidenceProfileRef|load_cross_graph_evidence_profile|persist_cross_graph_evidence_profile|ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF'
profile_carrier_re="$profile_owner_re|cross_graph_profile"
capability_re='CapabilityIndex|load_capability_index_release|from_capability_index|from_duckdb'

printf 'profile_exact=%s profile_owner_union=%s profile_plus_carrier=%s\n' \
  "$(git grep -l -I -E "$profile_exact_re" "$revision" -- 'src/**/*.py' | wc -l | tr -d ' ')" \
  "$(git grep -l -I -E "$profile_owner_re" "$revision" -- 'src/**/*.py' | wc -l | tr -d ' ')" \
  "$(git grep -l -I -E "$profile_carrier_re" "$revision" -- 'src/**/*.py' | wc -l | tr -d ' ')"
git grep -l -I -E "$profile_carrier_re" "$revision" -- 'src/**/*.py' |
  sed 's#^[^:]*:##' | sort
printf 'capability_candidates=%s\n' \
  "$(git grep -l -I -E "$capability_re" "$revision" -- \
    'src/polisyos/runtime/**/*.py' 'src/polisyos/scientist/**/*.py' \
    'src/polisyos/data_forge/**/*.py' 'src/polisyos/foundry/**/*.py' |
    wc -l | tr -d ' ')"
git grep -l -I -E "$capability_re" "$revision" -- \
  'src/polisyos/runtime/**/*.py' 'src/polisyos/scientist/**/*.py' \
  'src/polisyos/data_forge/**/*.py' 'src/polisyos/foundry/**/*.py' |
  sed 's#^[^:]*:##' | sort

# Resolve/content-bind/verify gap and its present-but-fake witness.
git show "$revision:./src/polisyos/ir/analytics/literature.py" | sed -n '750,792p'
git show "$revision:./src/polisyos/scientist/methods/autotune/models.py" |
  sed -n '138,155p;398,428p'
git show "$revision:./src/polisyos/scientist/methods/autotune/claim_adjudication.py" |
  sed -n '116,145p;276,354p'
git show "$revision:./src/polisyos/data_forge/domains/academic/batch/claim_adjudicator.py" |
  sed -n '285,383p'
git show "$revision:./src/polisyos/data_forge/domains/academic/batch/admitted_claim_adjudications.py" |
  sed -n '35,57p'
git show "$revision:./src/polisyos/scientist/methods/autotune/claim_adjudication_runtime.py" |
  sed -n '135,244p;349,449p'
git show "$revision:./tests/unit/data_forge/domains/academic/batch/test_admitted_claim_adjudication_consumers.py" |
  sed -n '59,149p;177,204p;231,269p'

# Literal-free semantic/profile sinks and persisted descendants.
git show "$revision:./src/polisyos/scientist/policy_design/objectives.py" |
  sed -n '100,141p;241,260p;330,342p;525,556p'
git show "$revision:./src/polisyos/data_forge/domains/academic/knowledge/parameter_selector.py" |
  sed -n '34,57p;112,132p;176,215p;276,309p'
git show "$revision:./src/polisyos/scientist/methods/search/judge_stack.py" |
  sed -n '198p;374,379p;561,579p;878,904p;1415,1488p;1732,1778p'
git show "$revision:./src/polisyos/scientist/nodes/builtins/causal/resolve_parameters.py" |
  sed -n '93,207p;264,276p'
git show "$revision:./src/polisyos/ir/analytics/parameters.py" | sed -n '43,86p'
git show "$revision:./src/polisyos/foundry/methods/catalog/causal/protocols.py" |
  sed -n '725,740p'
git show "$revision:./src/polisyos/foundry/methods/catalog/causal/parameter_transfer.py" |
  sed -n '95,125p'
git show "$revision:./src/polisyos/scientist/nodes/builtins/decide/build_policy_output_bundle.py" |
  sed -n '252,260p;307,322p;651,690p'
git show "$revision:./src/polisyos/scientist/nodes/builtins/decide/policy_runtime_request.py" |
  sed -n '40,51p;89,97p'
git show "$revision:./src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py" |
  sed -n '248,269p;320,371p;393,425p;600,626p;852,880p;1618,1658p'
git show "$revision:./src/polisyos/scientist/policy_design/output.py" |
  sed -n '435,453p;474,635p;930,983p;1568,1614p'
git show "$revision:./src/polisyos/runtime/quality/capability_resolver.py" |
  sed -n '400,415p;443,576p;652,675p'
git show "$revision:./src/polisyos/runtime/quality/capability_authority.py" |
  sed -n '501,535p;906,924p'
git show "$revision:./src/polisyos/data_requirement/compiler.py" |
  sed -n '570,575p;817,834p'
```

Receipt: `profile_exact=20 profile_owner_union=27 profile_plus_carrier=29` and
`capability_candidates=7` over the pinned 2,618-file denominator. Appendix A classifies the full
29-file profile carrier set and seven capability candidates. The code witnesses show that the
generic evaluation writer accepts caller-authored result fields and self-stamps the expected
component; champion admission checks that component and internal equalities rather than an
authenticated evaluator appointment/receipt or bound observation replay. The current adjudication
holder then checks only CAS shape/self-consistency before materialization; the existing test
supplies a fabricated pointer and invalid evaluation yet reaches graph/conflict publication. They
also prove the newly enumerated profile/index paths change parameter confidence,
search/objective/judge outcomes, source status, persisted descendants, or capability binding.

### Persisted-descendant fixed-point census

```zsh
revision=fac07ffc6281e53e5a58c8a30c3b848a6b60e0e5
descendant_re='PolicyEvaluation(Vector|Bundle)|PolicyFrontierReport|DecisionReadinessContract|ActionableSideInformation|PromotionEvidenceBundle|TransportabilityReport|PolicyArtifactBundle|PlatformMetaEvaluationReport|BenchmarkEvaluation|JudgeVerdict|ValidationReport|PolicyBrief|CapabilityBindingResult'
io_re='persist_|load_|put_json|model_validate|from_[a-z_]*dict|artifact_ref|_ref|registry|catalog|publish'

git grep -l -I -E "$descendant_re" "$revision" -- 'src/**/*.py' |
  sed 's#^[^:]*:##' | sort > /tmp/debt-b-descendant-symbol-files.txt
comm -12 \
  /tmp/debt-b-descendant-symbol-files.txt \
  <(git grep -l -I -E "$io_re" "$revision" -- 'src/**/*.py' |
    sed 's#^[^:]*:##' | sort) \
  > /tmp/debt-b-descendant-io-files.txt
printf 'descendant_symbol_files=%s descendant_io_candidates=%s\n' \
  "$(wc -l < /tmp/debt-b-descendant-symbol-files.txt | tr -d ' ')" \
  "$(wc -l < /tmp/debt-b-descendant-io-files.txt | tr -d ' ')"
cat /tmp/debt-b-descendant-symbol-files.txt
cat /tmp/debt-b-descendant-io-files.txt

# Confirmed fixed-point escapes, not samples used to infer the denominator.
git show "$revision:./src/polisyos/scientist/methods/search/pareto_registry.py" |
  sed -n '49,115p;132,192p;200,363p;527,577p'
git show "$revision:./src/polisyos/scientist/methods/search/controller.py" |
  sed -n '592,754p'
git show "$revision:./src/polisyos/scientist/policy_design/search.py" |
  sed -n '955,1064p'
git show "$revision:./src/polisyos/scientist/validation/phase5_preflight.py" |
  sed -n '283,327p;967,1025p'
git show "$revision:./src/polisyos/ir/governance/validation.py" |
  sed -n '64,88p;164,190p'
git show "$revision:./src/polisyos/scientist/policy_design/translator.py" |
  sed -n '48,61p;188,310p'
git show "$revision:./src/polisyos/scientist/evidence/claims/projections.py" |
  sed -n '245,299p'
git show "$revision:./src/polisyos/scientist/methods/search/funnel/level4_full.py" |
  sed -n '57,143p'
```

Receipt: `descendant_symbol_files=83 descendant_io_candidates=79`, over the same pinned 2,618
tracked Python-source denominator. The files are printed in full by both commands; no search-index
result is used. The regex is deliberately a candidate census, not an authority classification:
common artifact names occur in evidence-independent domains. The confirmed routes above are live
semantic/carrier descendants and are named in the consumer table. Task 3 must classify all 79 and
then pass the schema-agnostic recursive-lineage falsifier; the latter, not an enumerated allowlist,
is the closure mechanism.

### Missing adjudication inputs in the slim bundle

```bash
find production_data/policyos_academic_runtime_slim_20260411T112032Z -type f \
  \( -name 'resolve_extract_final_results.jsonl' \
     -o -name 'article_extraction_results.jsonl' \
     -o -name 'claim_adjudication*.jsonl' \
     -o -name '*claim*champion*' \
     -o -name '*claim*candidate*' \
     -o -name '*claim*evaluation*' \) -print
find production_data/policyos_academic_runtime_slim_20260411T112032Z -type f -print | sort
find production_data/policyos_academic_runtime_slim_20260411T112032Z -type f | wc -l
```

Receipt: the first command returns zero; the second enumerates the complete 23-file bundle, none of
which is an extraction input, adjudication CAS/batch receipt, champion, candidate, or evaluation
artifact.

## Appendix A: Complete Lexical Candidate Inventory and Call-Chain Extension

This is the classified 46-file union produced by the commands above. `S` means semantic-token hit;
`T` means relevant table-literal hit. Counts use each file's primary role for this debt.

### Producer (10)

- `S` `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_api.py`
- `S` `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_providers.py`
- `S` `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py`
- `S` `src/polisyos/data_forge/domains/academic/batch/article_extractor.py`
- `S` `src/polisyos/data_forge/domains/academic/batch/claim_adjudicator.py`
- `S` `src/polisyos/data_forge/domains/academic/batch/prompts/causal_claims.py`
- `S` `src/polisyos/data_forge/domains/academic/batch/resolve_finalize.py`
- `S` `src/polisyos/ir/analytics/literature.py`
- `S` `src/polisyos/scientist/methods/autotune/claim_adjudication_runtime.py`
- `S` `src/polisyos/scientist/cross_graph/compiler.py` (its lexical `strength` hit is unrelated,
  but its profile production from SKG evidence is in scope)

### Store, materializer, or snapshot copier (8)

- `S` `src/polisyos/data_forge/domains/academic/batch/_resolve_extract_io.py`
- `T` `src/polisyos/data_forge/domains/academic/batch/best_snapshot.py`
- `S,T` `src/polisyos/data_forge/domains/academic/batch/edge_synthesize.py`
- `S,T` `src/polisyos/data_forge/domains/academic/batch/graph_builder.py`
- `T` `src/polisyos/data_forge/domains/academic/batch/transport_score.py`
- `S,T` `src/polisyos/data_forge/domains/academic/knowledge/skg_store.py`
- `S,T` `src/polisyos/data_forge/domains/academic/knowledge/skg_versioning.py`
- `S` `src/polisyos/scientist/methods/discovery/priors.py`

### Semantic consumer (13)

- `S,T` `src/polisyos/data_forge/domains/academic/batch/benchmark.py`
- `T` `src/polisyos/data_forge/domains/academic/batch/qc.py`
- `S` `src/polisyos/data_forge/domains/academic/knowledge/search.py`
- `S,T` `src/polisyos/data_forge/domains/academic/knowledge/skg_query.py`
- `T` `src/polisyos/data_forge/domains/academic/knowledge/store.py`
- `S` `src/polisyos/foundry/methods/catalog/causal/graph_reconciliation.py`
- `S` `src/polisyos/foundry/methods/catalog/causal/literature_prior.py`
- `S,T` `src/polisyos/runtime/quality/capability_index_compiler.py`
- `S,T` `src/polisyos/runtime/quality/credal_reference.py`
- `T` `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py`
- `S` `src/polisyos/scientist/cross_graph/gatherers/academic.py`
- `S` `src/polisyos/scientist/methods/discovery/prior_miner.py`
- `S` `src/polisyos/data_forge/domains/academic/knowledge/parameter_selector.py` (the lexical hit is
  unrelated; the profile-driven confidence/selection path is semantic)

`benchmark.py` acts on SKG confidence and `qc.py` emits confidence-derived checks, so they are
semantic rather than administrative. `best_snapshot.py` also consumes those metrics, but its
load-bearing role here is stronger: it copies and promotes tables, so it is classified as a writer.

### Administrative only (2)

- `T` `src/polisyos/data_forge/domains/academic/batch/cli.py` (row counts only)
- `T` `src/polisyos/runtime/quality/substrate_registry.py` (table presence only)

### Unrelated use of “strength” (13)

- `S` `src/polisyos/core/contracts/foundry.py`
- `S` `src/polisyos/data_forge/domains/academic/batch/numeric_extract.py`
- `S` `src/polisyos/data_forge/domains/academic/batch/prompts/empirical_parameters.py`
- `S` `src/polisyos/data_forge/domains/academic/batch/table_extractor.py`
- `S` `src/polisyos/data_forge/domains/catalog/knowledge/variable_alignment.py`
- `S` `src/polisyos/foundry/analysis/attractors.py`
- `S` `src/polisyos/foundry/methods/catalog/bayesian/pmd_hmc.py`
- `S` `src/polisyos/foundry/methods/catalog/bayesian/protocols.py`
- `S` `src/polisyos/runtime/http/openapi_contract.py`
- `S` `src/polisyos/runtime/quality/concept_spine.py`
- `S` `src/polisyos/runtime/quality/nl_replay_orchestration.py`
- `S` `src/polisyos/runtime/quality/producer_pipeline.py`
- `S` `src/polisyos/runtime/quality/semantic_fixtures.py`

The targeted generic-key search adds two producers outside that union:
`src/polisyos/data_forge/domains/academic/batch/parser.py` and
`src/polisyos/data_forge/domains/academic/batch/llm_extractor.py`. The authority-side call graph
further adds
`scientist/methods/autotune/{models.py,claim_adjudication.py,claim_adjudication_runtime.py}`: its
generic `BenchmarkEvaluation` producer stamp is a candidate observation, not authenticated
evaluator provenance. The proposed verifier must route this whole class through the appointed,
signed, content-bound evaluation receipt and independent derived-value replay. Other literal-free
bridges and surfaces include `batch/resolve_extract.py`,
`data_forge/read_api/academic.py`, the Scientist literature-prior build/reconciliation nodes,
`scientist/cross_graph/compiler.py` (its lexical `strength` hit above is unrelated, but its
`query_edge_support` path is not), `scientist/cross_graph/feedback.py`,
`scientist/nodes/builtins/causal/resolve_transport.py` →
`data_forge/domains/catalog/knowledge/proxy_resolver.py`, Runtime capability-index
contract/discovery/HTTP provider, `runtime/quality/data_state_substrate.py` →
`runtime/quality/world_model_record.py` → `pdc/_impl/world_model_record.py`, the second
`runtime/quality/generation_cycle.py` constructor, and the `PriorKnowledgeBundle`, literature
`CausalGraphModel`, and `CrossGraphEvidenceProfile` persist/load/early-return chains through
readiness, governance, policy verification, and promotion. Downstream design/grounding consumers
complete the path. These do not change the 46-file literal-search denominator; they are mandatory
in Tasks 2–4 and C30/C32/C36–C46 because an unsearched wrapper can preserve or reactivate a tainted
artifact.

### Literal-free profile carrier set (29)

The second complete-tree census is a different denominator from the 46 lexical strength/table
files. Its 29 candidates classify as follows:

- **Contracts/producers (4):** `ir/analytics/cross_graph.py`, `ir/registry/refs.py`,
  `scientist/cross_graph/compiler.py`, and
  `scientist/nodes/builtins/planning/compile_cross_graph_evidence.py`.
- **Administrative/non-semantic (2):** `scientist/nodes/builtins/state_keys.py` owns the artifact
  key; `scientist/governance/remediation_status.py` contains only a test-name string. Neither can
  make evidence current.
- **Semantic consumers, carriers, or presence gates (23):**
  `data_forge/domains/academic/knowledge/parameter_selector.py`;
  `scientist/cross_graph/conflict_materializer.py` and `feedback.py`;
  `scientist/governance/passes/{cross_graph_evidence_pass.py,literature_gate_pass.py,transportability_required_pass.py}`;
  `scientist/methods/search/{judge_stack.py,readiness.py,funnel/level5_refutation_governance.py}`;
  `scientist/nodes/builtins/causal/resolve_parameters.py`;
  `scientist/nodes/builtins/decide/{build_policy_output_bundle.py,policy_runtime_request.py,policy_runtime_support.py,run_policy_blueprint_runtime.py,run_policy_promotion.py,run_policy_translation.py}`;
  `scientist/nodes/builtins/decide/decision_packet/{serialization.py,validation.py}`;
  `scientist/nodes/builtins/planning/{assemble_legal_candidate_pack.py,run_hierarchical_policy_search.py}`;
  `scientist/policy_design/{objectives.py,output.py}`; and
  `scientist/validation/policy_verified/service.py`.

All 23 must accept a `ResolvedAcademicProjection`/typed non-green outcome, propagate its binding,
or carry an explicit candidate-only ruling. None may model-validate a caller mapping into a green
profile, swallow stale/verification failure as ordinary absence, infer `available` from a path, or
treat a ref as current. The generic persist/load invariant then covers each output descendant; the
enumerated tests keep today's concrete set visible.

### Capability-index lexical set (7) and descendants

- `runtime/quality/capability_index.py` is the contract and
  `capability_index_compiler.py` the producer.
- `runtime/quality/capability_discovery.py` and
  `runtime/http/services/control_registry_providers.py` are canonical load/cache/discovery routes.
- `runtime/quality/capability_resolver.py` is a semantic authority consumer; its bare model,
  mapping, and direct-DuckDB factories are all in scope.
- `runtime/quality/__init__.py` is a facade only.
- `runtime/quality/capability_white_space.py` reads failure/acquisition records for an operator
  report, not academic evidence-bearing capability selections; it is `surface_out_of_scope` for
  this repair unless that input changes, at which point the same binding rule applies.

`runtime/quality/capability_authority.py` and `data_requirement/compiler.py` are literal-free
descendants: they currently retain only the release-ref string in `CapabilityBindingResult` and
compiled requirements. C45 requires the resolved binding to survive both. This is why a green
canonical loader alone would not close the consumer class.

### Persisted-descendant fixed point (83 symbol / 79 I/O candidates)

The complete lists are emitted by the reproduction commands above. Their purpose is to stop a
class-name census from masquerading as semantic closure: `ValidationReport`, `BenchmarkEvaluation`,
and causal/evaluation types also occur in evidence-independent subsystems. For this debt, the
confirmed additional authority-changing routes are:

- evaluation/frontier registry and transfer: `methods/search/{controller.py,pareto_registry.py}`
  and `policy_design/search.py`;
- judge-to-publication: `validation/phase5_preflight.py` and `ir/governance/validation.py`;
- readiness-to-public-bytes/claims: `policy_design/translator.py` and
  `evidence/claims/projections.py`;
- the second actionable-side-information producer: `methods/search/funnel/level4_full.py`.

The other candidates receive an explicit disposition during Task 3, but no disposition is a gate
predicate merely because it is written in a list. The recursive input-manifest rule decides the
property at runtime: any output with academic lineage carries the current binding or fails before
persistence/use. C52's unlisted-descendant test proves the mechanism does not depend on this
appendix remaining complete as the repository grows.

## Exact Transcriber-Ready Register Prose

The readable field source below keeps data completeness separate from semantic closure. The exact
single-line table row to paste follows it.

```markdown
## `extraction-strength-mixes-confidence-and-design`

**Consumer.** All academic claim producers and persistence, graph writers and snapshot copier,
exact/family/contested/transport materialization and retraction replay, benchmark/QC/best-snapshot gates, the
academic audit/read APIs, Foundry literature priors, Scientist causal-graph/cross-graph/transport,
parameter, objective/search/judge, readiness, governance, output/translation/decision, and
promotion consumers—including Pareto registry/transfer warm starts, Phase-5 validation,
brief/claim projection, and every actionable-side-information producer—and Runtime
credal/capability/binding/forecast/world-model simulation consumers including persisted
bundle/graph/profile/parameter/search/output/index/reference caches.

**What is required.** Keep claim extraction confidence, extractor design hint, extractor evidence
class, adjudication design output, causal credibility, publishability authority, and numeric
direction agreement as separately named, typed, basis- and provenance-bearing properties. A
missing claim-level value is a countable `not_established`, not an enum sentinel, paper-level
projection, value-name guess, record-level confidence, or default `FULLTEXT` source.

**Status `present_wrong_vocabulary`.** Recomputed 2026-09-02 against snapshot
`sha256:583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`. There are two exact
denominators: 137,714 JSON claim occurrences and 137,589 distinct relational claim identities. The
JSON population is 69,923 legacy five-field `strength="moderate"` occurrences plus 67,791 enriched
occurrences whose `strength` actually contains `EvidenceStrength`; the 125 difference is 121
byte-identical duplicate occurrences plus four case-only variants reconciling into 111 stable-ID
groups. The current writer's `INSERT OR REPLACE` explains and reproduces the observed retained-last
rows, but the original writer receipt is absent. The relational population partitions with zero
overlap into 69,798 blank-hint/`moderate` identities and 67,791 populated-hint/design-valued
identities; all and only the latter have claim adjudications.

There are three categorical vocabularies plus a numeric score. `DesignFamily` is the larger, more granular method
taxonomy; `EvidenceStrength` is an older evidence/ranking taxonomy; `CausalCredibility` supplies
`strong|moderate|weak|not_causal|unclear`; and `claim_extraction_confidence` is numeric. The two
enum fields coexist in the contract and overlap on only four literals; no declared coarsening or
safe mapping exists. Current graph helpers attempt inconsistent lossy mappings, which are behavior,
not admitted policy. The snapshot's legacy cohort has the deterministic parser's hard-coded
`moderate` shape: 58,671 occurrences are record-labeled `deterministic` and 11,252 carry the same
five-field shape under `resolve_extract`; there are zero `llm_enriched` rows. Per-claim producer
lineage for the 11,252 is absent, so carry-forward is an inference. The rich contract already has
separate fields, but its serializer writes `evidence_strength` under generic `strength` and the
untyped `WorkRecord`/store preserve the collapse.

This is a live consumer defect, not only a future risk. `graph_builder.py` falls back from an
unmapped adjudication design label to `causal_credibility`, turning 342 materialized curated claims
into `observational`: 187 `unclear`, 131 `theoretical`, and 24 `review`. They feed 342 edge-evidence
rows, 341 exact edges, 341 family edges, nine contested rows, and 341 transport rows; their wrong
`observational` weight enters aggregate confidence. Separately, the public
`CausalClaimResult.strength` is documented as `strong|moderate|weak` but all 7,868 current values
are evidence/design labels. The direct raw `moderate → observational` branch currently promotes
zero of the 69,798 because graph publication requires adjudication, but it remains an executable
future-write defect. A sibling span-grounded writer ignores `publish_to_graph=False` and writes
extractor candidate fields into `design_tier_authority`; its target table is absent from this
snapshot, so current materialized impact is zero. Runtime also parses categorical
`strongest_dissent_strength` as a number: 155/723 rows are populated categories and none casts to
`DOUBLE`, so every populated dissent label becomes numeric zero. Finally, the slim
`ac_claim_adjudications` table carries no batch receipt/rule/CAS provenance. Its 67,791 rows prove
coverage, not authority. Worse, the current holder will accept a shape-valid candidate batch after
checking only forgeable producer text, self-declared lineage, CAS integrity, and denominator: the
existing unit witness fabricates the pointer, uses an invalid evaluation, and drives graph/conflict
publication. One level deeper, `BenchmarkEvaluation` accepts caller-authored passing metrics,
guards, sample counts, and `promotable=True`; its generic writer stamps the expected evaluator
component, which champion admission trusts. A coherent fake evaluation and matching pointer thus
remain self-consistent without any appointed evaluator observation. The candidate contract
declares only edge publishability and expressly not method validity, but even that purpose remains
`not_established` until an authenticated evaluator receipt binds the suite/dataset/split/per-item
observations/execution, a non-producing verifier independently recomputes metrics, guards,
promotion and the complete batch result, and the holder verifies its provenance. The snapshot is therefore
`authority_not_established` for 7,868
claim lineages represented by 7,868 curated rows and 7,868 edge-evidence rows, with the 342/341 set
the additional measured vocabulary-fallback defect. Literal-free paths also rank/count those
results, turn claim trust into transport-proxy/parameter/search confidence, accept stale profiles
or indexes through bare model/mapping/ref/path carriers, and admit a version/ref-only SKG prior into
world-model simulation without a projection receipt or source epoch.

**What would satisfy it (corrected closure signal).** Enforce the split at the common claim
serialization/store **admission boundary and every authority-bearing consumer**, not merely “at
extraction time.” Atomically move every producer, graph writer, and snapshot copy/promote path to
an explicit versioned envelope bound to the actual source and invocation; reject generic
`strength` on new `WorkRecord`, JSON, and relational writes; preserve
design, evidence class, credibility, publishability purpose, and numeric confidence independently;
and remove credibility/name-based fallbacks. The 69,798 legacy identities must appear on a typed
raw-lineage audit surface with null design/evidence/claim-confidence/source-basis values and
`not_established` statuses, retaining `moderate` only as non-authoritative audit provenance. No
paper-to-claim projection is permitted. Generic evaluation artifacts and producer-component
strings remain candidate too. Require a trust-root-verified appointment and signed evaluator
receipt binding candidate/suite/dataset/split/ordered per-item observations/execution; then a
distinct appointed non-producer batch verifier must resolve those bytes, independently recompute
metrics, guards, sample counts, promotability and promotion, content-bind the batch/raw/pointer/
policy/execution/denominator chain, recompute every publishability result, and emit a purpose-bound
receipt. The Data Forge holder verifies that receipt before any pointer, projection, report, graph,
or conflict write; all current evaluations, v1 batches, and coherent present-but-fake chains fail
closed. Rows
without an evidence-ranking-purpose receipt are
excluded before the authority denominator, confidence floors, and multi-article bonuses; their
authority confidence stays null/`not_established`, with only the operational contribution set to
zero. The global enum weight table is not silently redefined. Restored availability requires both
an owner-ratified classification and a purpose-bound/versioned complete numeric calculus (weights,
floors, direction weighting, penalties, noisy-OR, and bonus) with semantic fixtures.

The legacy-aware read projection must cover exact/family/contested/transport/retraction paths and
all public/Foundry/Scientist/Runtime consumers; v2 is the semantic API, while a deprecated v1 audit
read returns `strength=None` plus `ambiguous_legacy_vocabulary` and authority operations refuse it.
Data Forge appends a queryable projection epoch/admission event. Every academic-derived
prior-knowledge bundle, literature causal graph, cross-graph profile, context-adaptive parameter
bundle, capability index, world-model SKG reference, and search/policy/capability descendant binds
that epoch or becomes stale. A schema-agnostic recursive input-manifest guard propagates the
binding through every CAS descendant; non-CAS registry/catalog writes retain only a resolved ref or
remain candidate, and an unlisted descendant is bound/rejected without an allowlist edit.
Canonical loaders, profile/index carriers, parameter/objective/judge/
output/decision/capability sinks, early-return paths, and cached processes reload or refuse without
cross-layer push imports; stale/error is never collapsed to absence, path availability, ref
presence, or a dict. Retraction appends an epoch and
invalidates span-grounded/exact evidence and all derived tables/artifacts/caches.
Categorical dissent remains categorical; only admitted `dominant_direction_agreement` supplies its
numeric quality component. Negative end-to-end tests must exercise all producers, sibling
writers/copy, replay, stored artifacts, registry/transfer, Phase-5, translator/claim projection,
the coherent fake evaluation chain, and Runtime, proving that `moderate`, paper design, record confidence, default source,
raw hint, credibility, or a missing receipt cannot establish an axis, add graph confidence,
authorize publication, or upgrade Runtime status. This no-data close is allowed to end in a typed
authority refusal; reissuing available bundle/graph/profile/parameter/search/output/index/binding/
world-model-reference artifacts and replacing absence with grounded claim-level classification require later data production, while
restored authority also requires the separately admitted classification and numeric calculus.
```

The structured text above is the readable source. This is the exact single-line table row to paste
into `DEBT-REGISTER.md`, including unchanged ownership/status and the corrected closure cell:

```markdown
| `extraction-strength-mixes-confidence-and-design` | **Consumer.** All academic claim producers and persistence; every adjudication, graph-writer, and snapshot copy/promote path; exact, family, contested, transport, and retraction materialization; benchmark, QC, and best-snapshot gates; the academic audit/read APIs; Foundry literature and parameter bridges; Scientist causal-graph, cross-graph, transport, parameter, objective/search/judge, readiness, governance, output/translation/decision, promotion, Pareto registry/transfer, Phase-5 validation, brief/claim-projection, and actionable-side-information consumers; and Runtime credal, capability/binding, design, grounding, forecast, and world-model simulation consumers including persisted caches. **What is required.** Extraction confidence, design hint, evidence class, adjudication design, causal credibility, publishability authority, and numeric direction agreement remain separately named, typed, status- and provenance-bearing properties; missing claim-level values are countable `not_established`, never enum sentinels, paper-level projections, record confidence, value-name guesses, path/ref presence, or default `FULLTEXT`. **Status `present_wrong_vocabulary`.** Recomputed 2026-09-02 on snapshot `sha256:583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`: 137,714 JSON occurrences reconcile to 137,589 relational identities because 125 occurrences (121 byte-identical and four case-only variants) collapse into 111 stable-ID groups. The identities partition exactly into 69,798 blank-hint `moderate` rows and 67,791 populated-hint design/evidence-valued rows; all and only the latter have adjudication rows. `EvidenceStrength` is older, but it and `DesignFamily` coexist as parallel axes with only four shared literals and no admitted coarsening; `CausalCredibility` is a separate categorical vocabulary and `claim_extraction_confidence` is numeric. The legacy occurrence cohort is 58,671 record-labeled `deterministic` plus 11,252 five-field `resolve_extract`; the rich 67,791 serialize `evidence_strength` under generic `strength`. Live defects: the credibility fallback mislabels 342 curated claims as `observational`, propagating through 342 evidence rows, 341 exact/family/transport rows and nine contested rows; public `CausalClaimResult.strength` misnames all 7,868 values; Runtime coerces 155 populated categorical dissent values to numeric zero; direct span-grounded ingest can ignore `publish_to_graph=False`; best-snapshot copy/promotion can clone around schema/admission; generic benchmark evaluations are caller-authored and self-stamped, champion admission trusts their producer string, and the adjudication holder accepts a present-but-fake batch, so a coherent fake evaluation/pointer/batch chain can pass without authenticated evaluator provenance; and bare profile/index/ref/path carriers can reactivate tainted evidence in parameter, search, output, capability, transport-proxy, and world-model consumers. The slim adjudication table has no batch receipt/rule/CAS provenance, so 7,868 claim lineages represented by 7,868 curated rows and 7,868 edge-evidence rows are `authority_not_established`; the 342/341 cohort is the additional measured vocabulary defect, while the forged-receipt path has zero current materialized rows because this snapshot has no receipt. | unallocated; producer is the academic extraction pipeline | `open` | **Corrected closure signal.** Enforce the vocabulary split at the common claim serialization/store admission boundary and every authority-bearing consumer, not merely at extraction time: atomically move every producer, graph writer, and snapshot copy/promote path to a versioned explicit envelope bound to the actual source and invocation; reject generic `strength` for new writes; preserve each axis, basis, authority purpose, and numeric confidence independently; remove credibility/name/paper/record-default substitutions; expose all 69,798 legacy identities through a typed raw-lineage audit with null design, evidence, claim-confidence, source-basis, and publishability values plus `not_established` statuses and operational `may_publish=false`; and retain `moderate` only as audit provenance. Treat every generic benchmark evaluation and adjudication batch as candidate. Require a trust-root-verified evaluator appointment and signed receipt binding the candidate, suite, dataset, split, ordered per-item observations, and execution identity; then a distinct appointed non-producing batch verifier resolves those bytes, independently recomputes metrics, guards, sample counts, promotability, promotion, the batch/raw/pointer/policy/execution/denominator chain, and every publishability result, emits a purpose-bound provenance receipt, and the Data Forge holder verifies it before any pointer, projection, report, graph, or conflict write. All current evaluations, v1 batches, and coherent present-but-fake chains fail closed. Rows without a separately resolved evidence-ranking-purpose receipt keep null/`not_established` authority confidence, are excluded before the denominator, floors, and multi-article bonuses, and make only an operational contribution of zero; the global enum weights are not silently changed. No design-to-evidence rule or numeric authority calculus is accepted without owner ratification, semantic fixtures, a versioned complete weights/floors/direction/penalty/noisy-OR/bonus policy, and an admitted evidence-ranking purpose. One legacy-aware projection plus a persisted Data Forge epoch/admission event and reusable `academic_projection_binding: SourceEpochBinding` must cover read, retraction epoch/cascade, cross-graph, transport proxy, prior, profile, context-adaptive parameter, objective/search/judge, readiness/governance, registry/transfer, Phase-5 validation, brief/claim projection, output/translation/decision, capability/binding, forecast, world-model simulation, deprecated v1 audit (`strength=None` plus typed limitation)/v2 semantic migration, artifact staleness, canonical load/early-return currentness, and cache reload for every academic-derived descendant. A schema-agnostic recursive input-manifest guard propagates the binding through every CAS descendant; non-CAS registry/catalog writes retain only a resolved ref or remain candidate, and an unlisted descendant must bind or fail without an allowlist edit. Every semantic/carrier/presence-only sink accepts only the resolved-current wrapper or a typed non-green outcome; stale/error cannot become absence, path availability, ref presence, or a dict. Categorical dissent remains categorical and only admitted `dominant_direction_agreement` supplies its numeric quality component. Negative E2E tests exercise all producers, evaluation/batch verification, sibling writer/copy paths, replay, current profile/index carriers, persisted descendants, registry/transfer, Phase-5, brief/claim projection, an unlisted descendant, and Runtime and prove no ambiguous label, parent field, hint, credibility, default, fake/missing receipt, stale wrapper, path, ref, or mapping can establish an axis, add graph confidence, authorize publication, improve rank/readiness, or upgrade status. A no-data close may end in typed authority refusal; clean bundle/graph/profile/parameter/search/output/index/binding/world-model-reference reissue and grounded classification remain later data production, while restored authority also requires admitted classification and the complete numeric calculus. |
```

P36 dependent correction: the adjacent
`docs/reference/data-capability-requirements.md#causal-claim-current-contract-vocabulary` currently
says all 137,714 objects have the five-field shape. A transcriber must update it in the same
change; otherwise the authoritative records immediately contradict. Exact replacement prose:

```markdown
## `causal-claim-current-contract-vocabulary`

**Consumer.** `CausalClaim` and every academic extraction/graph admission path, including
`ingest_openalex_span_grounded_claims`.

**What is required.** Versioned stored claim occurrences whose extraction confidence, design hint,
evidence class, source basis, and authority status are explicit and whose provenance is bound.

**Status `present_wrong_vocabulary`.** Recomputed 2026-09-02 against
`sha256:583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`: all 310,829 extraction
payloads parse and contain 137,714 claim occurrences, but they have two exact shapes. 69,923 are
legacy five-field `{cause,direction,effect,mechanism,strength}` objects with
`strength="moderate"`; 67,791 are enriched 23-field objects with distinct design, extraction,
source, and span fields but still serialize `evidence_strength` under generic `strength`. They
reconcile to 137,589 stable identities because 125 occurrences collide into 111 IDs. The legacy
objects lack claim text, claim-specific confidence, source basis, design hint, and span evidence;
the enriched cohort's historical producer/admission receipt is absent from the slim bundle.

**What would satisfy it.** Use the common versioned claim serialization/store admission boundary
described by `extraction-strength-mixes-confidence-and-design`: reject generic new writes, migrate
legacy observations without inventing axes or receipts, preserve all occurrences and their
identity reconciliation, and expose missing values as typed `not_established`. Re-extraction is
required to create grounded values for the legacy cohort, but is not required for the fail-closed
vocabulary safety repair.
```

## Plan Closeout Sequence

For this investigation branch only:

1. Re-open `docs/reference/policy-design-case-failure-patterns.md` and confirm the final plan still
   closes P01/P03/P04/P05/P07/P08/P09/P10/P12/P14/P15/P27/P28/P29/P31/P32/P35/P37/P38/P40 rather than
   merely renaming a field.
2. Verify that this plan is the only changed path and `docs/plans/active/**`, source, tests,
   schemas, apps, and `production_data/**` are byte-untouched.
3. Stage only this plan, then run `git diff --cached --check`; unstaged `git diff --check` does not
   inspect an untracked plan. Confirm the cached name list is exactly this one path.
4. Check branch attachment, commit this one plan, then read the path and commit back from `HEAD`.
5. Run the bound debt checker **exactly once** on that committed, quiescent tree with stdout and
   stderr redirected to an external scratch file; inspect the file and record the exit in the task
   handoff without modifying the plan.
6. Hash the pinned DuckDB after the checker. Any hash other than
   `583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967` is a stop, not a repair.

The one-shot checker command for this branch is:

```zsh
debt_b_receipt_dir=$(mktemp -d /tmp/policyos-debt-b-check.XXXXXX)
debt_b_receipt_path="$debt_b_receipt_dir/check-debt-ledger.txt"
set +e
/usr/bin/env PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$PWD/src:$PWD" \
  /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python \
  "$PWD/tools/quality/validation/check_debt_ledger.py" --check \
  >"$debt_b_receipt_path" 2>&1
debt_b_checker_exit=$?
set -e
echo "receipt=$debt_b_receipt_path exit=$debt_b_checker_exit"
wc -l -c "$debt_b_receipt_path"
/usr/bin/shasum -a 256 "$debt_b_receipt_path"
tail -40 "$debt_b_receipt_path"
debt_b_expected_snapshot_sha=583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967
debt_b_snapshot_path="$PWD/production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb"
debt_b_actual_snapshot_sha=$(/usr/bin/shasum -a 256 "$debt_b_snapshot_path" | awk '{print $1}')
echo "snapshot_sha256=$debt_b_actual_snapshot_sha"
if [[ "$debt_b_actual_snapshot_sha" != "$debt_b_expected_snapshot_sha" ]]; then
  echo "STOP: pinned snapshot hash changed" >&2
  exit 90
fi
if (( debt_b_checker_exit != 0 )); then
  echo "debt checker failed with exit $debt_b_checker_exit" >&2
  exit "$debt_b_checker_exit"
fi
```
