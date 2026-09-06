# Evidence-class vocabulary reachability — 2026-09-06

## EC-J01 — scope and measurement plan (before measurements)

The first repository read was the two `mechanism_unmeasured` rows in
`docs/plans/active/DEBT-REGISTER.md`: `literature-infers-evidence-class-from-a-sentence`
and `extraction-ask-offers-six-of-ten-evidence-classes`. Their prose is a hypothesis,
not a receipt. The worktree is
`/Users/deniskopylov/polisyos/.worktrees/debt-evidence-class-reachability/policy-engine`.
Entry `git status -sb` was clean and attached to
`codex/debt-evidence-class-vocabulary-reachability`; entry HEAD was
`8ad8d20957362b93e38b773c1ed33d9305bfb5cc` (the task's base).

This journal is append-only. Active plans, the selective `llm_extractor.py` and its
tests, production data, historical layers, B-1/B-2, parameter provenance and the
488 hint-cell row are outside the edit scope. No extraction, model, producer
pipeline or data-production pass is authorized. Pure prompt rendering, pure
normalizer/classifier probes on synthetic inputs, source enumeration and read-only
snapshot queries are the measurement instruments. They are not evidence that a
model obeys an enum or that a producer has run on the corpus.

Sequence: enumerate all files under `src/` and `tools/`, reconcile independent
enumerations, classify all claim-strength assignment/intake/transport sites, render
the actual outgoing text, execute the complete two-vocabulary alias matrix, then
trace the sentence route and measure its pinned-snapshot footprint. Decide the two
rows independently. A refuted range or dead path stops repair of the affected row;
rewriting prompt examples/calibration requires stopping; at most one repair round.
Other findings are candidates recorded here only. No directory-wide test run.

Pattern pass: `P35`/`P36` require complete path and file-type denominators and
finding IDs; `P29`/`P38` require rendered prompts and actual helper behavior rather
than substring/shape proofs; `P14`/`P15` distinguish candidate class from evidence
authority; `P01`/`P02` require a real reachability/persistence bridge; `P40` prevents
adjacent findings from turning into further repairs. The register was opened before
measurement. Missing capability labels and acceptance signals will be assigned
from the census, not from the two inherited paragraphs.

Contended resource: the pinned DuckDB, opened only with `read_only=True`; reads
will be serialized. The read-only production-data symlink resolves to the main
workspace's `policy-engine/production_data`. The required closeout digest is
`sha256:583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`
for `policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb`.
Scratch instruments/outputs live in ignored `.tmp/evidence-class-reachability/`.
The worktree had no `.venv`; pure Python 3.14 and the existing dependency runtime
can be used with this worktree's `src` explicitly selected, without changing data.

The bound debt checker runs once, redirected to a file, only if governed inputs
change. A journal-only lane records `git diff --name-only 8ad8d2095..HEAD` and skips
the checker, as expressly instructed. Delivery requires a commit followed by a
readback from the attached branch.

## EC-F01 — complete census and independent reconciliation

The denominator is the entire worktree `src/` plus `tools/`, all file types,
including hidden/ignored source files, excluding only `__pycache__`, `.pyc` and
`.pyo`. A Python `Path.rglob` walk and an independent
`rg --files --hidden --no-ignore src tools` walk produced identical path sets:
**3,355 files**, of which **3,052 are Python**. Every Python file parsed, with zero
syntax errors. The file-type totals are:

```text
.py 3052; .md 200; .sh 27; .json 18; .csv 15; .ts 12; .yaml 11;
.tmpl 7; .pyi 5; .typed 2; .cypher 2; .toml 2; .sql 1; .txt 1.
Sum = 3355.
```

A complete text walk found `evidence_strength` on **301 lines in 47 files**; all
47 are Python. The broader navigation search (`evidence_strength|EvidenceStrength|
EVIDENCE_WEIGHTS|_legacy_strength_from_adjudication`) returned 459 lines; it is
not the assignment denominator. The AST pass enumerated keyword arguments,
dictionary keys, annotated fields, attribute/subscript writes, `setattr` and
`setdefault`/`update`/`__setitem__` calls: **63 candidate field-write/declaration
sites in 23 files**, subsequently classified in EC-A01. These include parameters,
non-claim namesakes, schema declarations and transports; they are not 63 producers.

An independently derived lexical write census found **91 candidate lines in
31 files**. Context classification removes 19 embedded prompt/example lines,
7 local intermediate-variable assignments, 2 exception messages, 1 SQL UPDATE,
and 1 function parameter; the multiline `setdefault` search adds 2 sites.
**91 − 19 − 7 − 2 − 1 − 1 + 2 = 63**, with exact `(path, line)` set equality
against the AST result, not just equal counts. The removed prompt/SQL/local sites
were still inspected and are accounted for in EC-F02/EC-A02. During instrument
calibration, an overbroad lexical `evidence_strength\s*=` filter also excluded
keyword arguments; the AST-set mismatch exposed this, and the final reconciliation
classifies spaced local assignments separately. No conclusion used that failed pass.

The independent top-down pass walked typed claim/transport constructors, aggregate
`ArticleExtractionResult` validations, public exports, imports and callable
references. It resolves to **three explicit claim-value selection sites**:
`article_extractor._normalize_causal_claim:973`,
`literature.extract_span_grounded_claims_from_openalex_work:1097`, and
`literature._gold_record_to_causal_claim:1362`; plus the `CausalClaim` default at
`literature:555`. The constructor pass independently finds the corresponding
`CausalClaim.model_validate` at `article_extractor:996` and two constructors at
`literature:1088,1353`. The three sites plus the default account for every direct
claim assignment in the 63-site census. Prompt origins, external validation,
absence adapters, persistence and aggregate projections are additional paths,
listed separately below rather than conflated with those three assignments.
No renamed imports were found for the enumerated claim/transport/producer symbols.

**Instrument limits.** This is an exhaustive current-tree census, not a proof
about arbitrary external Python callers, plugins, future code or historical
executions. A public class remaining importable is not globally uncallable.
`model_copy`, generic JSON/mapping transports, nested Pydantic validation and
SQL tuple inserts need the top-down trace because a field-name search alone does
not see them. The resolve/extract facade mutates implementation globals and
creates delegates: its actual `_prompt_for_bundle` delegate was resolved and
rendered, rather than treating four copied constants as four producers. Text
inside an abstract is input, not an enum declaration. Rendered claim sections
were separated from parameter sections. A prompt's offered vocabulary is not an
enforced model-output range. No model compliance, external caller absence or
real producer execution is claimed.

## EC-F02 — producer, intake and transport reachability

Path abbreviations in this journal: `A/` =
`src/polisyos/data_forge/domains/academic/`; `L` =
`src/polisyos/ir/analytics/literature.py`. `W` means the complete ten-member
`EvidenceStrength`/`EVIDENCE_WEIGHTS` vocabulary listed in EC-F03. Absence (`None`
or its edge encoding `not_established`) is **not** an eleventh evidence class.
“Wired” below means a repository caller/entrypoint was traced; no producer was run.

| Path / owner | Expressible range and out-of-range behavior | Reachability / consumer |
| --- | --- | --- |
| `A/batch/_resolve_extract_transformers.py:1247` `_prompt_for_bundle` → `_resolve_extract_api.py:1358,1367,1517` → `article_extractor.py:1158,973` | Actual main prompt offers **W, 10/10**. Shared normalizer accepts a 24-key alias vocabulary whose image is all W, but only **8/10 canonical spellings survive**. Missing/unrecognized input becomes `unknown`. The two losses are in EC-F03. | **Wired production route**: `A/batch/cli.py:255,289`; `pipeline.py:93,125,140`; facade `resolve_extract.py:92`; API `:2123,2138`. Main all/claim lanes use this renderer. Context-only B and moderation C prompts render with zero evidence-strength fields and no causal-claim arrays. |
| `A/batch/article_extractor.py:1531` `PolicyArticleExtractor._extract` → same normalizer | Exact f-string RHS renders successfully and offers **6** claim classes and **11** design hints. The normalizer can nevertheless accept other aliases; the six-choice hint is not a validator. | **Not on the wired batch route**. Complete census: zero `PolicyArticleExtractor(...)` constructions in `src/`/`tools/`; its sole external-to-class call is the static abstract reconstruction helper at `:2050`. `_extract` is called by `_process_one:1789`, called by `process_batch`, but no entrypoint creates the class. `run_article_extract:2167` explicitly delegates to `run_resolve_extract`. Exported public class remains callable by external users; that use is not established. Label relative to batch: `implemented_but_not_orchestrated`. |
| `L:1097` / `_infer_evidence_strength:1600` | Exactly **5**: `rct`, `quasi_natural`, `panel_fe`, `meta_analysis`, `unknown`. No recognized design keyword → `unknown`; matching precedence comes from `_infer_design_family`. Arbitrary sentences are accepted, not a ten-class enum. | Callable and referenced by the recorded-fixture validator `tools/quality/validation/check_layer3_gy_openalex_artifacts.py:329,405,442`. No batch/CLI caller. `L:1208` also contains an evaluator fallback; default `extractor=None` returns through gold evaluation at `:1203` first, so that fallback is not the default execution. Persistence and footprint: EC-F04. |
| `L:1362` `_gold_record_to_causal_claim` | **1**, hardcoded `observational`, regardless of sentence/design. No class-valued input to reject. | Private accuracy-fixture adapter, called by `_evaluate_gold_span_support_accuracy:1293`, reached by public `evaluate_openalex_claim_extractor_accuracy` with default extractor. Claim is passed to span-support validation, counters and `ExtractorAccuracyReport`; no ingestion/persistence call in that route. `publish_to_graph=False`. This is not a corpus class producer. |
| `A/batch/llm_extractor.py:403` selective `EXTRACTION_PROMPT.format` | **No outgoing text/range at the bound revision**: pure template rendering raises `KeyError` for the literal JSON `estimates` block before the model call/try. Its serializer accepts W or absent, rejects unsupported enum/status and generic `strength`. | Model call unreachable under the observed format failure. Read/render-only census exclusion; file and its test untouched. The separate dead-prompt row is not reopened. |
| `A/batch/parser.py:376,409,646` deterministic claims → vocabulary envelope | **No evidence class**: sets `None/not_established` through the envelope default. A supplied evidence axis or generic `strength` is rejected by the serializer, not inferred from the deterministic sentence. | Wired `parse_raw_sources` → work records → graph builder. An absence producer, not a six/ten-class judge. |
| `L:555` `CausalClaim` and nested `ArticleExtractionResult` validation / loaders | W; omitted field defaults internally to `unknown`; unsupported value raises Pydantic `ValidationError`. `CausalClaim.from_payload` uses the same validation. Directly omitted fields remain absent in rich vocabulary serialization because the field was not supplied. | Public typed intake, and existing result loading at `A/batch/claim_adjudicator.py:87`, `numeric_extract.py:35`, `resolve_finalize.py:140`, `L:1806`. Loading/copying is not a new judgment. Rich/API normalization uses its alias rule **before** this validation. |
| `L:187,236` envelope / legacy absence adapter; `A/knowledge/types.py:221` legacy transport adapter | W + absent at the envelope; legacy adapter always **absent**, retaining the generic historical strength separately. Invalid v2 enum/status combinations reject; a legacy occurrence cannot declare itself v2. | Active ingestion/query compatibility boundary. No design-to-class inference. |
| `A/batch/graph_builder.py:408` `_legacy_strength_from_adjudication` | **Zero evidence classes**; one encoding, `not_established`, for every input. Pure probes across every current `DesignFamily` return that sentinel. | Zero callers in complete `src/`/`tools/` census. The hypothesized **8** is not its current range. Retired stub left untouched; B-2 not reopened. |
| `A/knowledge/skg_store.py:341` `EVIDENCE_WEIGHTS` | Scores all W; unknown/noncatalogue strength contributes zero base weight at scoring. | Consumer catalogue, **not an assigning producer**. Its size alone says nothing about which prompt is live. |

The three explicit selection sites reconcile independently with the top-down
constructor trace (EC-F01); the two model-facing extraction origins share one of
those sites. Deterministic/legacy absence and typed intake are explicit additional
rows so an omitted/defaulted field cannot disappear from the census.

| Assignment / copy bridge | Range; outside-range handling; wired consumer |
| --- | --- |
| `A/batch/article_extractor.py:1901,1949,2010`; `A/knowledge/types.py:170,187,205`; deterministic/selective serializers above | Rich serializer copies explicitly supplied W with candidate status, or absence for an unsupplied field. Common transport revalidates and content-binds occurrence/sidecar; invalid values reject. In-memory JSON round-trip and the real persisted-field layout were exercised in EC-V01. |
| `A/batch/graph_builder.py:372,562,597,1207,1297,1634,1671`; `_infer_edge_strength:659` | Current raw/published claim inserts carry W/None + status; edge evidence uses W or `not_established`. Invalid explicit class/status rejects through `candidate_claim_vocabulary_store_values` and the edge encoder. Connected to batch graph build; no adjudication-derived fallback. Tuple SQL writes are included even though they are not direct AST keyword/dict sinks. |
| `A/knowledge/skg_store.py:711,727,827,851,874,893` `ingest_openalex_span_grounded_claims` | Same serializer and encoder. All input candidates can be retained in article JSON before publication gating; edge/span rows require `publish_to_graph is True` and validated support. Unsupported explicit values reject. Sole `src/`/`tools/` call is the fixture validator at `:342`; EC-F04 distinguishes retained JSON from graph publication. |
| `A/knowledge/store.py:503,531,560,646,651,659,681,990,997`; `types.py:319` | Claim query projects validated W/None, with legacy absence. Edge summary recomputes the strongest decoded class from bound physical rows and verifies the supplied value matches; unsupported/mismatched values raise `ClaimTableSchemaError`. API/audit consumers are wired; aggregate selection is not an independent study-design judgment. |
| `A/knowledge/skg_query.py:217,1072,1130,1182,1239,2599,2662,2725` | Preserves decoded W/None or chooses strongest by weights. Unsupported persisted value rejects at decoder; absent values stay absent. Feeds claim/edge/prior queries. |
| `A/knowledge/skg_store.py:1153,1170,1199,1213`; `A/batch/edge_synthesize.py:590,604`; `A/knowledge/skg_versioning.py:141,152` | Edge encoder/decoder: W plus absence, invalid explicit value rejects. Legacy `normalize_strength`/`strongest_strength`: W plus absence encoding; unknown spelling → `unknown`, empty set → `unknown`. Synthesis writes family/contested summaries; retraction normalization can rewrite an edge's class. Public/batch edge paths, not claim-extraction producers. |
| `src/polisyos/runtime/quality/credal_reference.py:1120,1217,1413,1445`; `src/polisyos/foundry/methods/catalog/causal/literature_prior.py:237`, `graph_reconciliation.py:350`; `L:903,992`; `src/polisyos/scientist/methods/discovery/prior_miner.py:149`, `priors.py:71`; `src/polisyos/scientist/cross_graph/gatherers/academic.py:232` | Claim/edge/prior projections copy existing values, some into unconstrained report strings/metadata; the typed `LiteratureEdgePrior` admits W/None with status validation. `setdefault` leaves preexisting metadata unchanged. These consumers do not generate a study's evidence class; do not use their storage shape as an independent class judgment. |
| `tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py:332,353,407,425` | Read-only census output copies database strings (`None` → `""`) or parameter values. No class validation and no write back to a claim. Included in the sink census, excluded from producers. |

## EC-F03 — complete normalizer matrix and rendered-text measurements

Both renderers used the same synthetic bundle:
`{"title": "Synthetic census input", "text": "Synthetic placeholder; no corpus extraction."}`.
For `PolicyArticleExtractor._extract`, the exact AST RHS of `extraction_prompt`
was evaluated with the module's actual imported constants and `json.dumps`; the
method/class/client was **not invoked**. For the wired route, the facade's pure
`_prompt_for_bundle` was executed and its delegate resolved to
`_resolve_extract_transformers._prompt_for_bundle`. Four copied schema constants
are not four sends: `resolve_extract._sync_implementation_globals` supplies the
shared state, and the actual callable was the measurement target.

| Rendered text | Characters | SHA-256 | Claim enum |
| --- | ---: | --- | --- |
| Unwired `PolicyArticleExtractor._extract` | 11,391 | `32b2a543e173a2b607ab6df38192b63006ac0fe3a0e82bc5a839cb4e17eefd72` | `rct, quasi_natural, meta_analysis, observational, theoretical, unknown` — 6 |
| Wired `_prompt_for_bundle` | 8,554 | `f6a7a4117751138f90251d0d9825911ee07e06ff5601678f55203f9c340af4bc` | `rct, quasi_natural, quasi_natural_event, panel_fe, structural, observational, cross_sectional, meta_analysis, theoretical, unknown` — 10 |

The first rendering contains the two worked examples and the entire calibration
guide. No prompt content, example or calibration text is changed. In particular,
this lane does **not** propose extending a model-facing enum: the actual wired
ask already has all W, so the prerequisite argument for a prompt edit fails on
reachability. A speculative edit to the old class would not change that ask.

Complete measured `_normalize_evidence_strength` behavior for W:

| Input weighted class | Input base weight | Returned class | Returned base weight |
| --- | ---: | --- | ---: |
| `rct` | 1.00 | `rct` | 1.00 |
| `meta_analysis` | 0.95 | `meta_analysis` | 0.95 |
| `quasi_natural` | 0.70 | `quasi_natural` | 0.70 |
| `quasi_natural_event` | 0.60 | `unknown` | 0.00 |
| `panel_fe` | 0.50 | `panel_fe` | 0.50 |
| `structural` | 0.45 | `unknown` | 0.00 |
| `observational` | 0.30 | `observational` | 0.30 |
| `cross_sectional` | 0.20 | `cross_sectional` | 0.20 |
| `theoretical` | 0.15 | `theoretical` | 0.15 |
| `unknown` | 0.00 | `unknown` | 0.00 |

Complete measured behavior for the **11 design hints in the rendered old ask**
when, specifically, supplied as an `evidence_strength` answer (this is not a rule
converting design hints into evidence classes):

| Input design hint | Returned class | Returned base weight |
| --- | --- | ---: |
| `rct` | `rct` | 1.00 |
| `iv` | `unknown` | 0.00 |
| `did` | `unknown` | 0.00 |
| `rdd` | `unknown` | 0.00 |
| `synthetic_control` | `unknown` | 0.00 |
| `panel_fe` | `panel_fe` | 0.50 |
| `ols` | `unknown` | 0.00 |
| `meta_analysis` | `meta_analysis` | 0.95 |
| `review` | `unknown` | 0.00 |
| `theoretical` | `theoretical` | 0.15 |
| `unclear` | `unknown` | 0.00 |

Every one of the alias table's **24 input keys** was also executed. Its complete
output image is W. The two canonical losses remain expressible through
`event_study`/`event-study` → `quasi_natural_event` and
`structural_model`/`time_series_cointegration` → `structural`.
Thus **zero weighted classes are absolutely unreachable from a wired producer
when all accepted aliases count**, **zero are absent from its actual ask**, but
**two of the ten offered canonical answers lose their class**. The old prompt
omits four names; two (`panel_fe`, `cross_sectional`) survive if volunteered,
and two (`quasi_natural_event`, `structural`) collapse to `unknown` if volunteered
in canonical form. “The extractor cannot report panel_fe” is refuted.

This distinction is preserved after the real pure claim normalizer, rich
serializer, in-memory JSON round-trip, transport re-admission and persisted-field
layout: canonical `structural`/`quasi_natural_event` are `unknown/candidate`;
the alternative aliases retain their respective class/candidate values. No
filesystem/database persistence or extraction producer was invoked for this probe.

## EC-F04 — per-row footprint in the pinned snapshot

Pinned file:
`production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb`.
Initial binary SHA-256 matched the task pin. All connections used
`duckdb.connect(..., read_only=True, config={"threads": 1, "memory_limit": "1GB", ...})`;
the configured spill directory was under this worktree's ignored scratch.

The schema census walked **all 27 tables** and their columns. It found no
`ac_skg_span_grounded_claims`, `ac_skg_query_traces` or `ac_skg_no_hit_frontier`
table. A generic scan of **all 195 VARCHAR columns**, **17,485,193 row/column
positions including nulls**, found **zero** occurrences of each of:
`openalex.claim.`, `openalex_span_grounded`, and
`OpenAlex span-grounded L2 ingest`. These are corroboration, not the sole oracle:
the route's writer creates the absent tables, generated IDs have the first
prefix, its serializer supplies the second mode, and its version uses the third
string. All columns, rather than a sampled ID column, were searched.

Independently, a recursive Python walk parsed every `extraction_json` document
in each article table, with SQL document/key-marker counts as a cross-check:

| Complete population | Documents | Invalid JSON | Claim occurrences | Claim evidence-strength keys | Any-strength documents | Any-strength keys |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `ac_article_extractions.extraction_json` | 310,829 | 0 | 137,714 | 0 | 1,577 | 5,133 |
| `ac_skg_articles.extraction_json` | 310,829 | 0 | 137,714 | 0 | 1,577 | 5,133 |

These are two physical-table walks, **not independent evidence populations**.
Every strength key in both is at
`metadata.simulation_ready_numeric_estimates.[].evidence_strength`, the parameter
namespace. There are zero `evidence_strength_status` or `record_extraction_mode`
keys, zero top-level `source="openalex"` records, zero OpenAlex-writer `claims`
arrays, and zero generated sentence-route IDs in either walk. SQL independently
returns 310,829 documents, 1,577 literal-key-containing documents and zero ID-prefix
hits for each table. Claim shapes sum to the full 137,714 denominator:
69,923 exact legacy five-field occurrences + 67,791 richer occurrences. The
137,589 raw-table rows and 7,868 published-table rows are separate denominators;
both physical tables lack an `evidence_strength` column in this snapshot.

The article extraction-mode counts are **252,136 deterministic + 58,693
resolve_extract = 310,829**. The works census independently confirms
**310,710 nonempty abstracts / 310,829 works**. This measures retained text,
not eligibility for the current fulltext-first route and not authorization to
re-extract. No acquisition/eligibility work was opened.

**Sentence row.** The range hypothesis (five classes) is confirmed by executing
pure classifier witnesses and deriving the complete set of its return expressions.
`review` and even `Preview only, without a synthesis study.` produce `meta_analysis`;
`No randomized design was used.` produces `rct`. These are failures of sentence
keyword adequacy, not evidence that a weighted production edge was emitted.
The actual producer constructs `publish_to_graph=False` at `L:1104`. Its only
explicit harness caller hands its results to
`ingest_openalex_span_grounded_claims`; that function can retain their typed
candidate value in `ac_skg_articles.extraction_json` **before** it rejects every
unpublished claim at `skg_store:814`. The edge and span-grounded inserts come after
that gate. The golden-record adapter also has `publish_to_graph=False` and is
consumed only by accuracy reporting. No producer/ingester/validator was invoked
in this lane, so a fresh write is not claimed; this is the current call/SQL trace
plus a zero measured persistent footprint. The producer is **reachable in a
validation harness**, not globally dead, while its batch bridge is absent
(`implemented_but_not_orchestrated` relative to that route). The row's explicit
zero-footprint closure clause supports `folded`, with these measurements attached.

The stored 1,095 `meta_analysis` edge-evidence rows among 7,868 are **not** counted
as this sentence route's footprint. The complete schema/identifier/JSON evidence
above establishes no such lineage; historical class provenance and B-2 stay out
of scope. Aggregate base weights alone cannot identify a producer.

**Ask row.** The old class's rendered 6-of-10 count is correct; its description
as the working batch ask is refuted. The complete caller census establishes zero
batch constructions, while the current entrypoints render 10-of-10. The snapshot
has no retained claim-axis values to bind to the old prompt, and its extraction
mode is not a prompt-version receipt. Therefore no historical cohort is attributed
to that six-choice prompt. The unsupported-scale prediction does not justify an
enum edit. Stop rules 1/2 apply to this row on the measured live-route correction.

## EC-D01 — independent stops, candidate only, no repair round

1. `extraction-ask-offers-six-of-ten-evidence-classes`: stop with a corrected
   basis. The named prompt is six-choice but not wired into the current batch
   entrypoint; the wired prompt is ten-choice. Recommend `folded` for this row,
   with EC-F01–EC-F03/EC-F04 attached. No source/test/prompt change.
2. `literature-infers-evidence-class-from-a-sentence`: stop on the row's
   zero-footprint clause; recommend `folded` with EC-F04 attached. Retain the
   distinction between validator reachability, raw candidate retention capability
   and publication gating. No claim of a licensed evidence-class inference, and
   no claim that the public helper is uncallable.

**Candidate row, not opened or repaired:**
`live-extraction-canonical-evidence-classes-normalize-to-unknown` — the actual
`_prompt_for_bundle` asks for `quasi_natural_event` and `structural`, but the shared
`_normalize_evidence_strength` maps those canonical answers to `unknown` at base
weight 0.0 while accepting alternative aliases for both. Pure real normalizer →
serializer → JSON round-trip → persistence-layout probes confirm the loss and
candidate status. Suggested owner: `data_forge/domains/academic`. A future
acceptance signal would measure identity preservation for **every class actually
offered by the wired prompt** through that same boundary, including invalid-input
behavior. This is normalization loss, not an ask-width defect. The task explicitly
requires adjacent findings to remain candidates, so this lane does not repair it,
change parameter provenance, or reopen B-1/B-2.

No additional capability is claimed. The targeted repair phase used **zero** fix
rounds. The bound range/caller evidence stops both rows independently; neither
row was used as a reason to leave the other's measurement incomplete. Prompt
examples/calibration remain byte-identical; no prompt-design decision was made.

## EC-V01 — executed measurements and negative/positive receipts

All pure-code probes used Python 3.14.0 from the existing
`/Users/deniskopylov/polisyos/policy-engine/.venv/bin/python`, with this worktree's
`src` inserted first in `sys.path` and `PYTHONDONTWRITEBYTECODE=1`. Module
`__file__` receipts confirm the worktree paths for the normalizer, literature and
weights. No main-worktree source module was used as the subject of measurement.

| Command / instrument in `.tmp/evidence-class-reachability/` | Result |
| --- | --- |
| `python3 census.py` | 3,355 file paths independently reconciled; 3,052 Python parses; 63 candidate sinks. Exit 0. |
| `python3 reconcile_writes.py` | Independent lexical 91 → 63 reconciliation; exact set equality. Exit 0 after the instrument calibration described in EC-F01. |
| `.../.venv/bin/python probe.py` | Actual old f-string renders, 10 weighted and 11 design inputs measured; all current retired-helper probes yield absence. Exit 0. |
| `.../.venv/bin/python live_prompt.py` | Facade renderer offers 10/10; B/C prompts have zero class fields. Exit 0. |
| `python3 selective_render_only.py` | Expected `KeyError: '\n  "estimates"'` before any outgoing text; captured as a census observation. Exit 0, no producer called. |
| `.../.venv/bin/python semantic_probes.py` | All 24 aliases executed; all ten canonical class inputs plus aliases/invalid/missing values traversed the pure claim/transport boundary; return-derived five-class sentence range covered. Exit 0. |
| `.../.venv/bin/python snapshot_schema.py` | Required digest verified; complete table/column/row census. Exit 0. |
| `.../.venv/bin/python footprint.py` | All 195 text columns and both complete JSON populations scanned; independent SQL counts agree. Exit 0; measured wall time 69.717 seconds. |

The negative hypothesis checks are **red as hypotheses**, not failed product
regressions hidden by a repair: `live_ask_is_six = False` and
`all_canonical_classes_survive_normalizer = False`. Positive checks establish the
corrected properties: live offered set equals W; the exact losses are
`{quasi_natural_event, structural}`; the complete alias output set equals W;
the sentence return range has five members. Invalid class input is rejected by
all three typed boundaries exercised (`CausalClaim`, edge encoder, edge decoder),
while the article alias normalizer intentionally falls back to `unknown`.
The semantic probes exercised actual functions and in-memory serialization;
they do not assert only marker presence. There is **no repair red/green cycle**
to report because no repair was authorized by the measured outcome.

No pytest suite, directory-wide test run, architecture/full-backend wave, extraction
run, producer invocation or model call was made. For this measurement-only delivery,
those are not receipts of an implemented capability. The checker skip, closeout
hash and branch readback are recorded below after final journal verification.

## EC-A01 — complete field-write/declaration inventory

Every one of the 63 reconciled sites is below. **C** = direct claim selection/default; **T** = transport, query/prior/report projection or its field declaration; **P** = parameter namespace; **N** = unrelated same-name field; **D** = schema/validator descriptor. Ranges and rejection behavior for C/T are in EC-F02; P/N/D are not claim-class producers.

Computed category totals: C=4, D=2, N=9, P=12, T=36; sum=63.

| Site | Owner | Kind | Class |
| --- | --- | --- | --- |
| `src/polisyos/core/contracts/foundry.py:1099` | `AttractorCertificate` | annotated | N |
| `A/batch/_resolve_extract_transformers.py:1486` | `_deterministic_numeric_rescue_parameters` | dict | P |
| `A/batch/_resolve_extract_transformers.py:1538` | `_merge_numeric_parameter_lists` | dict | P |
| `A/batch/_resolve_extract_transformers.py:1652` | `_build_numeric_rescue_prompt` | dict | P |
| `A/batch/article_extractor.py:875` | `_normalize_empirical_parameter` | dict | P |
| `A/batch/article_extractor.py:973` | `_normalize_causal_claim` | dict | C |
| `A/batch/article_extractor.py:1949` | `serialize_rich_claim_occurrence_vocabulary` | keyword | T |
| `A/batch/llm_extractor.py:62` | `serialize_llm_claim_occurrence_vocabulary` | dict | T |
| `A/batch/llm_extractor.py:85` | `serialize_llm_claim_occurrence_vocabulary` | keyword | T |
| `A/batch/numeric_extract.py:84` | `_raw_numeric_rows` | dict | P |
| `A/batch/resolve_finalize.py:270` | `_merge_parameters` | dict | P |
| `A/batch/resolve_finalize.py:730` | `_curated_numeric_rows` | dict | P |
| `A/batch/resolve_finalize.py:884` | `_simulation_ready_parameters` | dict | P |
| `A/batch/table_extractor.py:160` | `tables_to_parameters` | dict | P |
| `A/knowledge/skg_query.py:80` | `EdgeSupportRecord` | annotated | T |
| `A/knowledge/skg_query.py:217` | `SKGQuery.query_claims` | keyword | T |
| `A/knowledge/skg_query.py:411` | `SKGQuery._query_simulation_parameter_candidates` | dict | P |
| `A/knowledge/skg_query.py:1072` | `SKGQuery._query_edge_support_for_names` | keyword | T |
| `A/knowledge/skg_query.py:1130` | `SKGQuery._query_exact_edge_support` | keyword | T |
| `A/knowledge/skg_query.py:1182` | `SKGQuery._query_contested_edge_support` | keyword | T |
| `A/knowledge/skg_query.py:1239` | `SKGQuery._query_family_edge_support` | keyword | T |
| `A/knowledge/skg_query.py:1836` | `SKGQuery._to_evidence_parameter` | keyword | P |
| `A/knowledge/skg_query.py:2599` | `SKGQuery.query_prior_for_variables` | dict | T |
| `A/knowledge/skg_query.py:2662` | `SKGQuery._query_prior_rows_from_exact` | dict | T |
| `A/knowledge/skg_query.py:2725` | `SKGQuery._query_prior_rows_from_family` | dict | T |
| `A/knowledge/store.py:531` | `ScholarKnowledgeStore._project_claim_row` | dict | T |
| `A/knowledge/store.py:560` | `ScholarKnowledgeStore._project_claim_row` | keyword | T |
| `A/knowledge/store.py:651` | `ScholarKnowledgeStore.project_edge_summary` | keyword | T |
| `A/knowledge/store.py:659` | `ScholarKnowledgeStore.project_edge_summary` | dict | T |
| `A/knowledge/store.py:681` | `ScholarKnowledgeStore.project_edge_summary` | keyword | T |
| `A/knowledge/store.py:852` | `ScholarKnowledgeStore._explicit_v2_invalid_predicate` | dict | D |
| `A/knowledge/store.py:997` | `ScholarKnowledgeStore.audit_claim_lineage` | keyword | T |
| `A/knowledge/types.py:39` | `<module>` | dict | D |
| `A/knowledge/types.py:205` | `candidate_claim_vocabulary_store_values` | dict | T |
| `A/knowledge/types.py:319` | `CausalClaimResultV2` | annotated | T |
| `src/polisyos/foundry/analysis/attractors.py:1017` | `_certificate_for_regime` | keyword | N |
| `src/polisyos/foundry/analysis/attractors.py:1033` | `_certificate_for_regime` | keyword | N |
| `src/polisyos/foundry/analysis/attractors.py:1078` | `_fixed_point_attractor_from_state` | keyword | N |
| `src/polisyos/foundry/methods/catalog/bayesian/pmd_hmc.py:1087` | `assess_pmd_hmc_multimodality` | keyword | N |
| `src/polisyos/foundry/methods/catalog/bayesian/protocols.py:222` | `MultimodalityStatus` | annotated | N |
| `src/polisyos/foundry/methods/catalog/causal/graph_reconciliation.py:350` | `_add_literature_edges` | method | T |
| `src/polisyos/foundry/methods/catalog/causal/literature_prior.py:237` | `BuildLiteraturePrior.pure_step` | keyword | T |
| `L:187` | `VersionedClaimVocabularyEnvelope` | annotated | T |
| `L:504` | `EvidenceParameter` | annotated | P |
| `L:555` | `CausalClaim` | annotated | C |
| `L:903` | `LiteratureEdgePrior` | annotated | T |
| `L:992` | `LiteratureCausalPrior.to_causal_graph_model` | method | T |
| `L:1097` | `extract_span_grounded_claims_from_openalex_work` | keyword | C |
| `L:1362` | `_gold_record_to_causal_claim` | keyword | C |
| `src/polisyos/runtime/http/openapi_contract.py:2042` | `<module>` | dict | N |
| `src/polisyos/runtime/http/openapi_contract.py:2128` | `<module>` | dict | N |
| `src/polisyos/runtime/quality/credal_reference.py:1120` | `_derive_l2_causal_edge` | dict | T |
| `src/polisyos/runtime/quality/credal_reference.py:1217` | `_derive_l2_family_edge` | dict | T |
| `src/polisyos/runtime/quality/credal_reference.py:1413` | `_derive_l2_causal_claim` | dict | T |
| `src/polisyos/runtime/quality/credal_reference.py:1445` | `_derive_l2_causal_claim` | dict | T |
| `src/polisyos/scientist/cross_graph/gatherers/academic.py:232` | `_assess_literature_prior_baseline` | dict | T |
| `src/polisyos/scientist/methods/discovery/prior_miner.py:149` | `PriorMiner.mine` | keyword | T |
| `src/polisyos/scientist/methods/discovery/priors.py:71` | `PriorKnowledgeSupport` | annotated | T |
| `tools/ops_runners/experiments/run_msme_final_fresg_suite.py:945` | `policy_world_score` | dict | N |
| `tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py:332` | `main` | dict | T |
| `tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py:353` | `main` | dict | T |
| `tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py:407` | `main` | dict | T |
| `tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py:425` | `main` | dict | T |

## EC-A02 — every literal-bearing file and nonliteral boundaries

This is the complete 47-file literal census from EC-F01, with the number of matching lines. It includes consumer-only and namesake files; no hit is silently discarded. The 63-site table above covers explicit field sinks; the remaining prompt/local/SQL write forms are addressed by EC-F02. Counts sum to 301.

| File | Literal-bearing lines |
| --- | ---: |
| `src/polisyos/core/contracts/foundry.py` | 1 |
| `A/batch/_resolve_extract_api.py` | 3 |
| `A/batch/_resolve_extract_io.py` | 3 |
| `A/batch/_resolve_extract_providers.py` | 3 |
| `A/batch/_resolve_extract_transformers.py` | 15 |
| `A/batch/article_extractor.py` | 10 |
| `A/batch/benchmark.py` | 1 |
| `A/batch/best_snapshot.py` | 1 |
| `A/batch/edge_synthesize.py` | 3 |
| `A/batch/graph_builder.py` | 24 |
| `A/batch/llm_extractor.py` | 5 |
| `A/batch/numeric_extract.py` | 1 |
| `A/batch/parser.py` | 2 |
| `A/batch/prompts/causal_claims.py` | 3 |
| `A/batch/prompts/empirical_parameters.py` | 3 |
| `A/batch/resolve_finalize.py` | 16 |
| `A/batch/table_extractor.py` | 1 |
| `A/knowledge/parameter_selector.py` | 1 |
| `A/knowledge/search.py` | 2 |
| `A/knowledge/skg_query.py` | 49 |
| `A/knowledge/skg_store.py` | 23 |
| `A/knowledge/skg_versioning.py` | 4 |
| `A/knowledge/store.py` | 23 |
| `A/knowledge/types.py` | 12 |
| `src/polisyos/data_forge/domains/catalog/knowledge/variable_alignment.py` | 5 |
| `src/polisyos/foundry/analysis/attractors.py` | 3 |
| `src/polisyos/foundry/methods/catalog/bayesian/pmd_hmc.py` | 2 |
| `src/polisyos/foundry/methods/catalog/bayesian/protocols.py` | 1 |
| `src/polisyos/foundry/methods/catalog/causal/graph_reconciliation.py` | 3 |
| `src/polisyos/foundry/methods/catalog/causal/literature_prior.py` | 3 |
| `L` | 19 |
| `src/polisyos/runtime/http/openapi_contract.py` | 2 |
| `src/polisyos/runtime/quality/capability_index_compiler.py` | 3 |
| `src/polisyos/runtime/quality/concept_spine.py` | 1 |
| `src/polisyos/runtime/quality/credal_reference.py` | 12 |
| `src/polisyos/runtime/quality/nl_replay_orchestration.py` | 1 |
| `src/polisyos/runtime/quality/producer_pipeline.py` | 3 |
| `src/polisyos/runtime/quality/semantic_fixtures.py` | 2 |
| `src/polisyos/scientist/cross_graph/compiler.py` | 1 |
| `src/polisyos/scientist/cross_graph/gatherers/academic.py` | 1 |
| `src/polisyos/scientist/methods/discovery/prior_miner.py` | 6 |
| `src/polisyos/scientist/methods/discovery/priors.py` | 8 |
| `tools/ops_runners/data/build_academic_gold_candidates.py` | 1 |
| `tools/ops_runners/experiments/run_msme_discovery_addendum_20260501.py` | 2 |
| `tools/ops_runners/experiments/run_msme_final_fresg_suite.py` | 1 |
| `tools/ops_runners/experiments/run_msme_final_fresg_suite_v2.py` | 5 |
| `tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py` | 7 |

The nonliteral generic intake/transport boundary trace additionally inspected `A/batch/claim_adjudicator.py:87`, `resolve_finalize.py:140,173`, `A/knowledge/types.py:170,221`, `L:236,593,1806`, the facade `A/batch/resolve_extract.py:52,62,80,92`, and the entrypoint/validator calls in EC-F02. `CausalClaim.model_copy` uses in canonization, reconciliation and finalization preserve the strength; parameter mergers with the same field name are P, not C. Runtime manifests/concept/producer pipelines, academic gold-candidate selection and MSME addendum/v2 scripts are reads or reports; catalog variable-alignment, attractor certificates and Bayesian multimodality use unrelated strength meanings.


## EC-E01 — readback anchor corrections (append-only)

Readback corrected navigation anchors without changing any measurement: in
EC-F04, `publish_to_graph=False` is **L:1103**, not L:1104 (the constructor's
closing parenthesis); the publication predicate is **skg_store.py:813**, with
rejection recorded at :814. The legacy transport adapter begins at
**A/knowledge/types.py:220** (:221 is its first parameter). The explicit
`CausalClaim.from_payload` intake is **L:587**, with validation at :590; L:593
in EC-A02 is the following post-validator, not that intake. These exact anchors
supersede their nearby navigation references above.

## EC-A03 — reproducible measurement instruments

These are the actual scratch instrument sources, included in the single durable
journal so the receipts do not depend on untracked files surviving merge. Save
the named blocks into `.tmp/evidence-class-reachability/`, create that directory,
and run from `policy-engine` with Python 3.14 and the existing project dependencies.
Run `census.py`, `lexical_writes.py`, `reconcile_writes.py`, `probe.py`,
`live_prompt.py`, `selective_render_only.py`, `semantic_probes.py`,
`snapshot_schema.py`, then `footprint.py`; use `PYTHONDONTWRITEBYTECODE=1`.
Redirect outputs to scratch files. These scripts do not call extraction producers,
models or database writers. The DuckDB scripts reject a wrong snapshot hash and
open the database read-only. Replaying source enumeration may change file-type
denominators on a later branch; this journal's measurements bind the task base.

**census.py**

```python
import ast
import collections
import json
from pathlib import Path
import subprocess

out=Path('.tmp/evidence-class-reachability')
def included(p):
    return '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}
fs=sorted(p.as_posix() for root in ('src','tools') for p in Path(root).rglob('*') if p.is_file() and included(p))
rg=sorted(p for p in subprocess.check_output(['rg','--files','--hidden','--no-ignore','src','tools'],text=True).splitlines() if included(Path(p)))
assert fs==rg, (set(fs)-set(rg),set(rg)-set(fs))
counts=collections.Counter(Path(p).suffix or '<none>' for p in fs)
sinks=[];intakes=[];tokens=[];errors=[]
models={'CausalClaim','ArticleExtraction','ArticleExtractionResult','VersionedClaimVocabularyEnvelope','ClaimResult','ClaimEvidenceResult','ClaimOccurrenceRecord','OpenAlexWorkText'}
for path in fs:
    raw=Path(path).read_bytes()
    try: text=raw.decode()
    except UnicodeDecodeError: continue
    hits=[i for i,line in enumerate(text.splitlines(),1) if 'evidence_strength' in line]
    if hits: tokens.append({'path':path,'lines':hits})
    if not path.endswith('.py'): continue
    try: tree=ast.parse(text,filename=path)
    except SyntaxError as e: errors.append((path,str(e)));continue
    class Walker(ast.NodeVisitor):
        def __init__(self): self.context=[]
        def visit_ClassDef(self,node):
            self.context.append(node.name);self.generic_visit(node);self.context.pop()
        def visit_FunctionDef(self,node):
            self.context.append(node.name);self.generic_visit(node);self.context.pop()
        visit_AsyncFunctionDef=visit_FunctionDef
        def add(self,node,kind,value):
            sinks.append({'path':path,'line':node.lineno,'owner':'.'.join(self.context),'kind':kind,'value':ast.unparse(value) if value is not None else None})
        def visit_keyword(self,node):
            if node.arg=='evidence_strength': self.add(node,'keyword',node.value)
            self.generic_visit(node)
        def visit_Dict(self,node):
            for k,v in zip(node.keys,node.values):
                if isinstance(k,ast.Constant) and k.value=='evidence_strength':self.add(k,'dict',v)
            self.generic_visit(node)
        def visit_AnnAssign(self,node):
            if ast.unparse(node.target).split('.')[-1]=='evidence_strength':self.add(node,'annotated',node.value)
            self.generic_visit(node)
        def visit_Assign(self,node):
            for t in node.targets:
                if any(isinstance(n,ast.Attribute) and n.attr=='evidence_strength' and isinstance(n.ctx,ast.Store) or isinstance(n,ast.Subscript) and isinstance(n.slice,ast.Constant) and n.slice.value=='evidence_strength' and isinstance(n.ctx,ast.Store) for n in ast.walk(t)):
                    self.add(node,'write',node.value)
            self.generic_visit(node)
        def visit_Call(self,node):
            name=ast.unparse(node.func)
            if any(m in name.split('.') for m in models): intakes.append({'path':path,'line':node.lineno,'owner':'.'.join(self.context),'call':name,'code':ast.get_source_segment(text,node)})
            if isinstance(node.func,ast.Attribute) and node.func.attr in {'setdefault','update','__setitem__'} and node.args and isinstance(node.args[0],ast.Constant) and node.args[0].value=='evidence_strength':self.add(node,'method',node.args[1] if len(node.args)>1 else None)
            if name in {'setattr','object.__setattr__'} and len(node.args)>1 and isinstance(node.args[1],ast.Constant) and node.args[1].value=='evidence_strength':self.add(node,'setattr',node.args[2])
            self.generic_visit(node)
    Walker().visit(tree)
report={'files':len(fs),'file_types':dict(counts),'python_files':counts['.py'],'independent_rg_files':len(rg),'fs_rg_equal':True,'literal_files':len(tokens),'literal_lines':sum(len(t['lines']) for t in tokens),'parse_errors':errors,'sink_count':len(sinks),'sink_files':len({s['path'] for s in sinks}),'intake_count':len(intakes),'intake_files':len({i['path'] for i in intakes})}
(out/'census-summary.json').write_text(json.dumps(report,indent=2)+'\n')
(out/'census-files.json').write_text(json.dumps(fs,indent=2)+'\n')
(out/'census-sinks.json').write_text(json.dumps(sinks,indent=2)+'\n')
(out/'census-intakes.json').write_text(json.dumps(intakes,indent=2)+'\n')
(out/'census-literals.json').write_text(json.dumps(tokens,indent=2)+'\n')
print(json.dumps(report,indent=2))
for s in sinks: print(f"{s['path']}:{s['line']} {s['owner']} [{s['kind']}] = {s['value']}")
```

**lexical_writes.py**

```python
import json,re
from pathlib import Path
out=Path('.tmp/evidence-class-reachability')
files=json.loads((out/'census-files.json').read_text())
patterns=[r'''["']evidence_strength["']\s*:''',r'\bevidence_strength\s*=',r'\bevidence_strength\s*:(?!\s*["\'])']
hits=[]
for path in files:
    try:lines=Path(path).read_text().splitlines()
    except UnicodeDecodeError:continue
    for i,line in enumerate(lines,1):
        if any(re.search(p,line) for p in patterns):hits.append((path,i,line.strip()))
(out/'independent-write-lines.json').write_text(json.dumps(hits,indent=2)+'\n')
print('lexical possible writes',len(hits),'files',len({x[0] for x in hits}))
```

**reconcile_writes.py**

```python
import json,re
from pathlib import Path
out=Path('.tmp/evidence-class-reachability')
files=json.loads((out/'census-files.json').read_text())
hits=json.loads((out/'independent-write-lines.json').read_text())
category_counts={};kept=set();excluded=[]
for p,n,line in hits:
    if '/prompts/' in p or '_resolve_extract_' in p and n in {522,549,617} or p.endswith('/llm_extractor.py') and n==123:
        category='embedded_prompt'
    elif re.match(r'evidence_strength\s+=',line):category='local_variable'
    elif 'raise ValueError' in line:category='error_message'
    elif line.startswith('SET '):category='sql_update'
    elif p.endswith('/knowledge/store.py') and n==587:category='function_parameter'
    else:
        kept.add((p,n));continue
    category_counts[category]=category_counts.get(category,0)+1
    excluded.append({'path':p,'line':n,'category':category})
methods=[]
for p in files:
    if not p.endswith('.py'):continue
    txt=Path(p).read_text()
    for m in re.finditer(r'\.setdefault\(\s*["\']evidence_strength["\']\s*,',txt):
        # Anchor at the opening method call, as in the independent AST pass.
        methods.append((p,txt.count('\n',0,m.start())+1))
kept.update(methods)
sinks=json.loads((out/'census-sinks.json').read_text())
ast_sites={(s['path'],s['line']) for s in sinks}
assert kept==ast_sites, {'lexical_only':sorted(kept-ast_sites),'ast_only':sorted(ast_sites-kept)}
report={'lexical_possible_writes':len(hits),'excluded_categories':category_counts,'multiline_setdefault_additions':methods,'remaining_sites':len(kept),'ast_sites':len(ast_sites),'set_equality':True,'excluded_sites':excluded}
(out/'write-reconciliation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='excluded_sites'},indent=2))
```

**probe.py**

```python
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path('src').resolve()))
from polisyos.ir.analytics import literature
from polisyos.data_forge.domains.academic.batch import article_extractor as ae
from polisyos.data_forge.domains.academic.knowledge import skg_store
from polisyos.data_forge.domains.academic.batch.graph_builder import _legacy_strength_from_adjudication

out=Path('.tmp/evidence-class-reachability')
p=Path(ae.__file__)
tree=ast.parse(p.read_text())
cl=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='PolicyArticleExtractor')
method=next(n for n in cl.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='_extract')
stmt=next(n for n in method.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='extraction_prompt' for t in n.targets))
# Evaluate the exact AST RHS the method passes to chat; no extractor object or call.
prompt=eval(compile(ast.Expression(stmt.value),str(p),'eval'),dict(vars(ae)),{'evidence_bundle':{'title':'Synthetic census input','text':'Synthetic placeholder; no corpus extraction.'}})
(out/'rich-prompt-before.txt').write_text(prompt)
claim_section=prompt.split('"causal_claims": [{',1)[1]
classes=re.search(r'"evidence_strength": "([^"]+)"',claim_section).group(1).split('|')
designs=re.search(r'"design_family_hint": "([^"]+)"',claim_section).group(1).split('|')
weighted=[{'input':k,'weight':v,'output':ae._normalize_evidence_strength(k),'output_weight':skg_store.EVIDENCE_WEIGHTS[ae._normalize_evidence_strength(k)]} for k,v in skg_store.EVIDENCE_WEIGHTS.items()]
design_map=[{'input':k,'output':ae._normalize_evidence_strength(k),'output_weight':skg_store.EVIDENCE_WEIGHTS[ae._normalize_evidence_strength(k)]} for k in designs]
sentences=['Randomized allocation improves outcomes.','Difference-in-differences reduces emissions.','Regression discontinuity improves earnings.','Panel fixed effects show gains.','This review improves reporting.','A meta-analysis reports gains.','An event study reports gains.','A structural model reports gains.','Ordinary words without a design.']
classifiers=[{'sentence':s,'design':literature._infer_design_family(s).value,'evidence':literature._infer_evidence_strength(s).value} for s in sentences]
alias_range=sorted(set(ae._EVIDENCE_STRENGTH_ALIASES.values()))
report={'runtime':sys.executable,'module_files':{'article_extractor':ae.__file__,'literature':literature.__file__,'skg_store':skg_store.__file__},'rendered_prompt_chars':len(prompt),'rendered_prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'rendered_claim_classes':classes,'rendered_claim_class_count':len(classes),'rendered_designs':designs,'rendered_design_count':len(designs),'weighted_count':len(weighted),'weighted_mapping':weighted,'design_mapping':design_map,'alias_output_range':alias_range,'alias_output_count':len(alias_range),'pure_sentence_probes':classifiers,'legacy_current_outputs':[_legacy_strength_from_adjudication({'design_family':d,'publish_to_graph':True,'design_quality_tier':1}) for d in [e.value for e in literature.DesignFamily]],'unknown_probe':ae._normalize_evidence_strength('not-a-class')}
(out/'probe-before.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
```

**live_prompt.py**

```python
import hashlib,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path('src').resolve()))
from polisyos.data_forge.domains.academic.batch import resolve_extract as rext
bundle={'title':'Synthetic census input','text':'Synthetic placeholder; no corpus extraction.'}
text=rext._prompt_for_bundle(bundle,topic_display_names=[])
Path('.tmp/evidence-class-reachability/live-prompt.txt').write_text(text)
claim=text.split('Each causal_claim object',1)[1]
classes=re.search(r'"evidence_strength": "([^"]+)"',claim).group(1).split('|')
report={'rendered_chars':len(text),'rendered_sha256':hashlib.sha256(text.encode()).hexdigest(),'classes':classes,'class_count':len(classes),'all_embedded_class_ranges':re.findall(r'"evidence_strength": "([^"]+)"',text),'delegate_target_module':rext._DELEGATES['_prompt_for_bundle'].__module__,'delegate_target_file':rext._DELEGATES['_prompt_for_bundle'].__code__.co_filename,'sync_modules':[m.__name__ for m in rext._IMPLEMENTATION_MODULES]}
for name,args in [('_build_track_b_prompt',(bundle,[])),('_build_track_c_prompt',(bundle,[]))]:
    prompt=getattr(rext,name)(*args)
    Path('.tmp/evidence-class-reachability/'+name+'.txt').write_text(prompt)
    report[name]={'chars':len(prompt),'evidence_strength_occurrences':prompt.count('evidence_strength'),'claim_array_declarations':len(re.findall(r'"causal_claims"\s*:',prompt))}
Path('.tmp/evidence-class-reachability/live-prompt.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
```

**selective_render_only.py**

```python
import ast,json
from pathlib import Path
p=Path('src/polisyos/data_forge/domains/academic/batch/llm_extractor.py')
t=ast.parse(p.read_text())
stmt=next(n for n in t.body if isinstance(n,ast.Assign) and any(isinstance(k,ast.Name) and k.id=='EXTRACTION_PROMPT' for k in n.targets))
template=eval(compile(ast.Expression(stmt.value),str(p),'eval'),{})
try:
    text=template.format(topic='Synthetic census topic',abstract='Synthetic census text')
except Exception as exc:
    result={'actual_format_result':'raised','exception':type(exc).__name__,'message':str(exc),'producer_invoked':False,'model_called':False}
else:
    result={'actual_format_result':'rendered','text':text,'producer_invoked':False,'model_called':False}
Path('.tmp/evidence-class-reachability/selective-render-only.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
```

**semantic_probes.py**

```python
import ast,collections,json,sys
from pathlib import Path
sys.path.insert(0,str(Path('src').resolve()))
from polisyos.data_forge.domains.academic.batch import article_extractor as ae
from polisyos.ir.analytics import literature as lit
from polisyos.data_forge.domains.academic.knowledge import skg_store as skg
from polisyos.data_forge.domains.academic.knowledge.types import candidate_claim_vocabulary_store_values
out=Path('.tmp/evidence-class-reachability')
weights=skg.EVIDENCE_WEIGHTS
aliases={k:ae._normalize_evidence_strength(k) for k in ae._EVIDENCE_STRENGTH_ALIASES}
assert set(aliases.values())==set(weights)
claim_results=[]
for supplied in [*weights,'event_study','structural_model','time_series_cointegration','not-a-class',None]:
    payload={'cause_variable':'labor.reform','effect_variable':'labor.employment','claim_text':'A reform changed employment.','evidence_strength':supplied,'supporting_spans':[{'section':'results','text':'A reform changed employment.'}]}
    claim=ae._normalize_causal_claim(payload,work_id='synthetic:census',evidence_bundle={},default_source_basis='fulltext')
    assert claim is not None
    expected=ae._normalize_evidence_strength(supplied)
    assert claim.evidence_strength.value==expected
    transport=ae.serialize_rich_claim_occurrence_vocabulary(claim,record_extraction_mode='synthetic_measurement')
    # In-memory real serializer and persisted-field layout, not a store/producer call.
    restored=type(transport).model_validate_json(transport.model_dump_json())
    columns=candidate_claim_vocabulary_store_values(restored)
    assert columns['evidence_strength']==expected
    assert columns['evidence_strength_status']=='candidate'
    claim_results.append({'input':supplied,'claim_value':expected,'roundtrip_field':columns['evidence_strength'],'status':columns['evidence_strength_status']})
# Function range is derived from all return statements, not from only the witnesses.
tree=ast.parse(Path(lit.__file__).read_text())
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_infer_evidence_strength')
ret=[ast.unparse(n.value) for n in ast.walk(fn) if isinstance(n,ast.Return)]
expected_ret={eval(v,vars(lit)).value for v in ret}
sentences=['Randomized allocation.','Difference-in-differences.','Regression discontinuity.','Fixed effects.','review','Ordinary words.','Preview only, without a synthesis study.','No randomized design was used.']
sentence_rows=[{'text':s,'evidence':lit._infer_evidence_strength(s).value} for s in sentences]
assert set(x['evidence'] for x in sentence_rows)==expected_ret
negative='not-a-class'
rejected=[]
for name,fn in [('typed CausalClaim',lambda:lit.CausalClaim(cause_variable='x',effect_variable='y',evidence_strength=negative)),('edge encoder',lambda:skg.encode_edge_evidence_strength(negative)),('edge decoder',lambda:skg.decode_edge_evidence_strength(negative))]:
    try:fn()
    except ValueError:rejected.append(name)
    else:raise AssertionError(name+' admitted invalid class')
assert len(rejected)==3
report={'aliases':aliases,'alias_count':len(aliases),'alias_output_count':len(set(aliases.values())),'claim_normalizer_roundtrip':claim_results,'sentence_return_range':sorted(expected_ret),'sentence_probes':sentence_rows,'invalid_rejected_by':rejected,'original_hypothesis_checks':{'current_weighted_count_is_10':len(weights)==10,'live_ask_is_six':len(json.loads((out/'live-prompt.json').read_text())['classes'])==6,'all_canonical_classes_survive_normalizer':all(ae._normalize_evidence_strength(k)==k for k in weights)},'corrected_measurement_checks':'PASS: live ask has all 10; exact two canonical losses; alias image all 10; sentence range 5; three invalid-class rejections'}
(out/'semantic-probes.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
```

**snapshot_schema.py**

```python
import hashlib
import json
from pathlib import Path
import duckdb
p=Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
with p.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
assert digest=='583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967',digest
con=duckdb.connect(str(p),read_only=True,config={'threads':1,'memory_limit':'1GB','temp_directory':str(Path('.tmp/evidence-class-reachability/duckdb-tmp').resolve())})
tables=con.execute("SELECT table_schema,table_name,table_type FROM information_schema.tables ORDER BY 1,2").fetchall()
rows=[]
for schema,table,kind in tables:
    q='"'+schema.replace('"','""')+'"."'+table.replace('"','""')+'"'
    cols=con.execute('DESCRIBE '+q).fetchall()
    count=con.execute('SELECT count(*) FROM '+q).fetchone()[0]
    rows.append({'schema':schema,'table':table,'kind':kind,'rows':count,'columns':[(x[0],x[1]) for x in cols]})
con.close()
report={'snapshot':str(p),'resolved_snapshot':str(p.resolve()),'sha256':digest,'bytes':p.stat().st_size,'tables':rows}
Path('.tmp/evidence-class-reachability/snapshot-schema.json').write_text(json.dumps(report,indent=2)+'\n')
for r in rows:print(r)
```

**footprint.py**

```python
import collections
import json
from pathlib import Path
import time
import duckdb
start=time.monotonic()
p=Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
con=duckdb.connect(str(p),read_only=True,config={'threads':1,'memory_limit':'1GB','temp_directory':str(Path('.tmp/evidence-class-reachability/duckdb-tmp').resolve())})
schema=json.loads(Path('.tmp/evidence-class-reachability/snapshot-schema.json').read_text())['tables']
def quote(v):return '"'+v.replace('"','""')+'"'
markers=['openalex.claim.','openalex_span_grounded','OpenAlex span-grounded L2 ingest']
text_scans=[]
for t in schema:
    cols=[name for name,typ in t['columns'] if typ in {'VARCHAR','JSON'}]
    if not cols:continue
    query='SELECT '+', '.join('count(*) FILTER (WHERE contains('+quote(c)+', ?))' for c in cols for _ in markers)+' FROM '+quote(t['table'])
    vals=con.execute(query,[m for _ in cols for m in markers]).fetchone()
    for i,c in enumerate(cols):text_scans.append({'table':t['table'],'column':c,'rows':t['rows'],'hits':dict(zip(markers,vals[i*len(markers):(i+1)*len(markers)]))})
reports=[]
for table in ['ac_article_extractions','ac_skg_articles']:
    counts=collections.Counter();paths=collections.Counter();strengths=collections.Counter();modes=collections.Counter();claim_shapes=collections.Counter();malformed=0;docs=0;docs_with=0;claim_n=0
    cur=con.execute('SELECT extraction_json FROM '+quote(table))
    while batch:=cur.fetchmany(2048):
        for (text,) in batch:
            docs+=1
            try:obj=json.loads(text)
            except (TypeError,ValueError):malformed+=1;continue
            seen=False
            stack=[((),obj)]
            while stack:
                path,x=stack.pop()
                if isinstance(x,dict):
                    for key,val in x.items():
                        loc=(*path,key)
                        if key in {'evidence_strength','evidence_strength_status'}:
                            paths['.'.join(loc)]+=1;strengths[str(val)]+=1
                            if key=='evidence_strength':seen=True
                        if key=='record_extraction_mode':modes[str(val)]+=1
                        stack.append((loc,val))
                elif isinstance(x,list):stack.extend(((*path,'[]'),v) for v in x)
                elif isinstance(x,str):
                    for marker in markers:
                        if marker in x:counts[marker]+=1
            if seen:docs_with+=1
            if isinstance(obj,dict):
                counts['source_openalex']+=obj.get('source')=='openalex'
                if isinstance(obj.get('claims'),list):counts['openalex_claims_array']+=1
                for claim in obj.get('causal_claims',[]):
                    claim_n+=1
                    if isinstance(claim,dict):claim_shapes[','.join(sorted(claim))]+=1
    sql=con.execute('SELECT count(*), count(*) FILTER (WHERE contains(extraction_json, ?)), count(*) FILTER (WHERE contains(extraction_json, ?)) FROM '+quote(table),['"evidence_strength"','openalex.claim.']).fetchone()
    reports.append({'table':table,'documents':docs,'invalid_json':malformed,'documents_with_strength':docs_with,'strength_paths':dict(paths),'strength_values':dict(strengths),'record_modes':dict(modes),'marker_or_source_counts':dict(counts),'claim_occurrences':claim_n,'claim_shapes':dict(claim_shapes),'independent_sql_documents':sql[0],'independent_sql_strength_key_docs':sql[1],'independent_sql_id_docs':sql[2]})
typed=[]
for t in schema:
    names=[c for c,_ in t['columns']]
    if 'evidence_strength' in names:
        dist=con.execute('SELECT evidence_strength,count(*) FROM '+quote(t['table'])+' GROUP BY 1 ORDER BY 1').fetchall()
        assert sum(n for _,n in dist)==t['rows']
        typed.append({'table':t['table'],'rows':t['rows'],'distribution':dist})
report={'table_count':len(schema),'varchar_column_count':len(text_scans),'varchar_cell_denominator':sum(t['rows'] for t in text_scans),'all_string_marker_scan':text_scans,'json_walks':reports,'typed_evidence_columns':typed,'extraction_modes':con.execute('SELECT extraction_mode,count(*) FROM ac_article_extractions GROUP BY 1 ORDER BY 1').fetchall(),'nonempty_abstracts':con.execute("SELECT count(*),count(*) FILTER (WHERE length(trim(coalesce(abstract,'')))>0) FROM ac_works").fetchone(),'elapsed_seconds':round(time.monotonic()-start,3)}
con.close()
Path('.tmp/evidence-class-reachability/footprint.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='all_string_marker_scan'},indent=2))
print('marker totals', {m:sum(t['hits'][m] for t in text_scans) for m in markers})
```

## EC-T01 — transcriber-ready paragraphs (one per debt row)

**`extraction-ask-offers-six-of-ten-evidence-classes` — recommend `folded`, basis
corrected.** At the bound source revision, rendering the exact
`PolicyArticleExtractor._extract` f-string confirms six evidence classes and eleven
design hints, but the complete 3,355-file `src/` + `tools/` census (3,052 Python)
finds no construction of that class on a repository batch route. The compatibility
entrypoint and current CLI/pipeline delegate to `resolve_extract`, whose actual
facade renderer offers all ten weighted classes. The complete ten-class and
eleven-design alias matrices are measured in EC-F03; `panel_fe` and
`cross_sectional` survive, while canonical `quasi_natural_event` and `structural`
become `unknown` (base weight 0.0), though alternative aliases can express both.
The current-ask-width allegation is therefore refuted and no prompt is changed.
The live canonical-normalization loss is recorded only as a separate candidate
in EC-D01, not repaired or silently included in this closure. Full enumeration,
rendered-prompt hashes, alias behavior and footprint limitations: EC-F01–EC-F04.

**`literature-infers-evidence-class-from-a-sentence` — recommend `folded` under its
measured-zero-footprint closure clause.** EC-F02/EC-F04 confirm the pure helper's
five-class range, including `review`/`Preview` → `meta_analysis`, but the full
caller trace finds a recorded-fixture validator route, not a batch producer. The
helper is not globally dead: its candidates can be retained by the SKG ingester
in article JSON, while their explicit `publish_to_graph=False` prevents its edge
and span-grounded inserts. The pinned snapshot has no span-grounded/query-trace/
no-hit-frontier tables, and a complete scan of 195 VARCHAR columns across all
27 tables (17,485,193 row/column positions) finds zero route IDs, modes or version
markers. Recursive walks of all 310,829 extraction JSON documents in **each**
article table find zero claim evidence-strength keys and zero route records;
independent SQL counts agree. The :1362 `observational` assignment is a separate
accuracy-gold adapter consumed only by span-support scoring, with no persistence
route. No inference rule is licensed, no producer is run and no source is repaired.
This folds the row on the attached measured snapshot footprint, not on an
unqualified claim that the helper cannot be called.

## EC-V02 — journal verification and commit scope

Fresh `check_journal.py` read the completed journal and checked all nine embedded
Python instruments both parse and match their executed scratch sources; it
compared every row of the ten-class and eleven-design mappings to measured JSON,
recounted all 63 categorized sink rows and all 47 literal-bearing files/301 lines,
reconciled snapshot denominators, checked no governed input differs from the task
base, and verified attachment to the expected branch. Result: **PASS**, exit 0.
The lexical census/reconciliation was replayed and remained **91 → 63**, exact
set equality. `git diff --check` also returned clean; staged validation follows
before commit.

The shared installed pre-commit hook points at the main repository's hooks and a
binary from another worktree. There is no repository/worktree-root Lefthook
configuration here (only an unrelated dashboard configuration). Commits for this
journal use `LEFTHOOK=0`; no applicable backend test or debt check is represented
as having run. The task's measurement-only checker exemption governs the explicit
receipt below. Source/tests/tools/plans/schemas and the excluded selective file
and test remain untouched.
