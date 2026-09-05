# Unknown evidence weight — append-only journal

## Event 1 — Phase-1 measurement and scope stop, 2026-09-05

Task: `academic-unknown-evidence-contributes-nonzero-weight`. The dated filename is the
requested one; this measurement/closeout continued on September 5. **Phase 1 only. No design
has been adopted, no repair has been attempted, and the row remains open.**

### UW-F01 — binding, custody, and measurement boundary

The register row was read before task actions. Attached branch:
`codex/debt-unknown-evidence-weight`; supplied and verified base:
`2a26fa6108034105bba2e276184d2d6bc77f9832`. Product worktree:
`/Users/deniskopylov/polisyos/.worktrees/debt-unknown-evidence-weight/policy-engine`.
No merge/rebase/stash, source change, production writer, extraction, adjudication, or data
re-derivation was performed. `docs/plans/active/` is not edited.

Pinned database, relative to the product worktree:
`production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb`.
Initial SHA-256: `583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`.
The linked database is 2,390,503,424 bytes, mode `-r--r--r--`. Every snapshot connection uses
`duckdb.connect(..., read_only=True)`, including the inspected `SKGQuery` and
`ScholarKnowledgeStore` constructors. Synthetic benchmark rows use only `:memory:`.
The temporary constant-zero diagnostic changes an in-process dictionary, restores it in
`finally`, and never changes source or database bytes.

The complete snapshot file walk finds 23 files: 16 JSON, two JSONL, one DuckDB, one NPZ,
one HNSW, and two extensionless `.DS_Store` files. The database has 27 tables and one SKG
version. There is no span-grounded table or persisted prior/credal-result table. Prior and
credal figures below are read-time projections, not claims that those outputs were deployed.

Method: complete tracked-file census, source-to-terminal inspection, complete SQL/JSON
population walks, and pure/read-only real-function replay. The supplied B2-F03 map and its
Event-3 corrections were re-read; B-2's D03 edge-absence contract is the baseline, not a
substitution seam to reopen. Reproduction commands and the actual diagnostic programs are
included below instead of a separate notebook, respecting the requested single journal.

Pattern pass: `P04` (absence and unknown are distinct), `P14` (support inflation), `P31`
(one constant is not the whole contribution class), `P35` (complete denominators), `P36`
(reproduce B2-F03 rather than inherit its prose), `P37` (calibration provenance is not
established), `P38` (weight-map ownership is not contribution ownership), and `P40` (stop
before a cross-package repair ladder). These are existing patterns; no new pattern row is
needed. The measurement is `recomputed`; a content-bound calibration producer licensing
unknown's weight is `not_established`. Neither a repair nor its semantic verification is
claimed complete.

### UW-F02 — retained footprint, including the genuine zeros

Each distribution is over the complete named table, not a ranked query or sample. Confidence
sums are descriptive sums across rows, **not** additive probabilities or causal-attribution
estimates. Decimal results are rounded below to avoid immaterial floating-point sum order.

| Population / consumer input | Complete denominator | Recorded `unknown` | Recorded `not_established` | Measured consequence |
| --- | ---: | ---: | ---: | --- |
| `ac_skg_edge_evidence` | 7,868 claim-evidence rows | 0 | 0 | No current exact-evidence unknown contribution. |
| `ac_skg_edges` | 7,607 exact edges | 0 | 0 | No current exact-edge unknown contribution. |
| `ac_skg_family_edges` | 15,945 family edges | 440 | 0 | Confidence min 0.009811872, mean 0.067174773, max 0.183199924; sum 29.556900223. |
| `ac_skg_contested_edges.evidence_strength` | 723 contested edges | 18 | 0 | All 18 have confidence 0.15; sum 2.7. |
| Same table, `strongest_dissent_strength` | 723 dissent slots | 3 | 0 | All three are within the 18 unknown-strongest rows; not three additional edges. |
| `ac_skg_transport_scores`, joined to exact edges | 7,607 transport rows | 0 | 0 | All 7,607 resolve exact edges; no orphan or unknown-labelled source edge. |
| `ac_skg_simulation_parameters` | 5,124 numeric rows | 0 | 0 | All labels recognized; zero uses of the unrecognized-key default in this pinned table. |
| `ac_skg_parameters.parameter_json` | 51,908 raw numeric rows | No stored strength field in any row | No stored strength field in any row | Current real reader accepts 51,883 as typed `UNKNOWN`; rejects 25 malformed payloads. |

The full 7,868 evidence distribution is meta-analysis 1,095; observational 374; panel-FE 793;
quasi-natural 4,122; quasi-natural-event 526; RCT 954; structural 4. It sums to 7,868.
The 5,124 simulation labels are observational 2,936; meta-analysis 1,088; RCT 736;
quasi-natural 328; panel-FE 35; cross-sectional 1. The corpus program prints the other
complete distributions and all 27 table counts.

The 440 unknown family rows retain 444 distinct raw claim references from 223 distinct works;
every referenced raw claim has generic `strength='unknown'`. None of these 444 claims is in
the current `ac_skg_edge_evidence`, and none of the referenced exact edge IDs is in the
current exact-edge table. Their current exact-table footprint is zero, not 444. The 18
unknown contested rows reference 21 distinct unknown raw claims from 18 works; those 21
are within the 444 family references and likewise absent from current exact evidence.
Their stored direction-weight sums are positive 0.148389, negative 0.146450, mixed 1.044507.

This is a retained-projection discrepancy, not evidence that B-2 just generated unknown
family rows. Exact edges have April 6 update timestamps (17:21:13–17:22:31); family rows
April 8 (12:06:03–12:08:34); contested rows April 8 (12:08:34–12:08:43), in the April 11
assembly. The source generations differ. No historical projection was rewritten.

Mixed-label lineage was also counted rather than discarded: all 15,945 family rows have
16,658 distinct claim references, none missing from the raw table. Of the family rows,
1,030 reference at least one raw generic unknown (440 unknown-strongest, 590 other-strongest),
covering 1,046 distinct unknown raw claims. Of those claims, 583 are in current exact evidence
with a concrete recorded class. All 723 contested rows have 965 distinct references, none
missing from raw; 48 rows reference raw unknown (18 unknown-strongest, 30 other-strongest),
covering 53 distinct raw unknown claims, of which 29 are in current exact evidence.
**These are lineage-overlap counts, not 0.15-contribution counts.** Raw generic strength
and historically projected evidence strength differ. The missing historical per-evidence
generation prevents exact numerical attribution of unknown's component inside each mixed
family/contested confidence. Claiming all 1,030/48 as measured 0.15 contributions would
repeat the axis/provenance error. This is an explicit limit of the pinned footprint.

Transport confidence spans 0–0.977527565; its source base confidence spans
0.0315–0.997540833. There is no current transport row deriving from an unknown exact edge.
Context rewards can independently raise a zero base; that is not the unknown evidence
weight and is not silently included in this defect's measured contribution.

### UW-F03 — complete consumer disposition and absence behavior

The complete tracked application/tool denominator is **4,781 paths under `src/`, `tools/`,
`apps/`, `packages/`**, including 3,055 Python, 507 TypeScript, 716 TSX, and one SQL file.
The Python AST walk has zero parse errors. A separate source/tool/test AST walk covers
**5,549 Python files** (2,619 source, 433 tools, 2,497 tests), zero parse errors.
The exact-table literal census reproduces B2-F03's 20 files; named API calls were then
followed, so the table search is not offered as a call-graph proof.

Six application files reference `EVIDENCE_WEIGHTS`: academic `batch/benchmark.py`, and
`knowledge/{skg_store,skg_query,store,search,parameter_selector}.py`. A separate AST walk
over string-keyed dictionaries containing `unknown` and at least two evidence-class keys
finds the extractor alias map and **two independent numeric maps**: Scientist cross-graph
compiler and Catalog variable alignment. This separate census is why a six-file map-import
search cannot establish that the contribution is academic-only.

Paths below are relative to `src/polisyos/`, unless explicitly under `tools/`. Line numbers
are at the measured base; ranges are reading coordinates, not an expanded repair remit.

| Consumer chain | What `unknown` does | What declared edge absence does / terminal footprint |
| --- | --- | --- |
| Academic `knowledge/skg_store.py:341–599`; `batch/graph_builder.py`; `batch/edge_synthesize.py:369–575`; `knowledge/skg_versioning.py:113–165` | Base 0.15 enters noisy-OR, strongest-class floors, replication count, direction weights and dissent. Synthesis consumes each per-evidence strength; retraction approximates remaining evidence using the retained strongest class. | Normalized reserved token is excluded from valid articles, weights, floors, replication, and dissent; rank -1 versus unknown rank 0. All-absent input has confidence 0. No writer/retraction/synthesis was invoked. Snapshot footprint is UW-F02. |
| Academic `knowledge/skg_query.py:1112–1245,1648–1664,2522–2734` -> `knowledge/store.py:575–779` -> V2 claim/read API | Unknown remains an enum-valued candidate. Hybrid strongest-class selection uses the weight map, separately from confidence merging. | Decode yields `None` + `not_established` before ranking/enum construction; malformed non-reserved labels reject. Mixed strongest selection omits absence. Existing row and confidence predicates remain intact. |
| Prior query -> `scientist/methods/discovery/prior_miner.py:103–190` -> `priors.py` -> `methods/search/readiness.py:1021–1062` and `judge_stack.py:317–321` | PriorMiner retains the candidate label/confidence; matched rows can count as resolved support. Readiness uses resolved-edge coverage, not an evidence weight. Judge state can expose the support JSON; no model counterfactual was run. | Value/status pair survives without token leakage. Absence does not itself delete a row or lower coverage. Read-only full queries at min confidence 0 return exact 7,607/0 unknown, family 15,945/440, hybrid 16,569/440. Default PriorMiner min 0 permits unknown family rows for matching requests, subject to its limit 256. No claim that all 440 enter one default run. |
| Prior query -> `foundry/methods/catalog/causal/literature_prior.py:198–263` -> IR `LiteratureEdgePrior` -> `graph_reconciliation.py:303–352,451–477` -> Scientist `cross_graph/gatherers/academic.py:176–249` | Enum/metadata is retained; numeric confidence and work/edge inclusion determine support and reconciliation. No new unknown weight is computed here. | Explicit absent value/status is accepted. Default confidence threshold 0.2 excludes all 440 retained unknown family rows (max 0.1832); lower configured thresholds expose them. Constructor defaults must not be confused with decoded absence. |
| Academic `knowledge/skg_query.py:242–419,1624–1647,1760–1849` | Raw numeric payload omissions default to `EvidenceParameter.UNKNOWN`; parameter ordering uses the map. 51,883 accepted current rows become unknown; 25 reject. | **This is not the B-2 edge encoding.** Parameter fallback converts invalid `not_established` or arbitrary labels to unknown. Reserved-token exclusion is proven for the edge contract, not for all unrelated string slots. |
| Academic `knowledge/search.py:132–217` -> Scientist `agent/knowledge_tools.py:139–166`, academic `batch/cli.py:351–362` | Weighted mean/std use 0.15 for unknown. Actual `demographic.female_share` query yields 36 unknown raw candidates and a prior mean 61.960777778, std 22.454180236, `best_design='unknown'`. | If all weights become zero, current code replaces them with ones: changing the constant alone still produces a prior. Legacy `ac_parameter_estimates` fallback weights trust, a separate axis. Returned prior/API/CLI payload is the terminal here; no calibration run was invoked. |
| Academic `knowledge/parameter_selector.py:34–214` -> Scientist `nodes/builtins/causal/resolve_parameters.py:139–206` -> Foundry `methods/catalog/causal/parameter_transfer.py:96–162` | Unknown multiplies ranking score, but eligibility filters adjusted transport confidence, not that score. Selected values/uncertainty can enter a context-adaptive parameter bundle and literature-prior bridge. | Parameter schema has no edge-absence pair. A zero strength weight alone need not make a candidate ineligible. Transfer consumes selected numbers and applicability/uncertainty, not another evidence-strength map. Source reachability inspected; no workflow/bundle producer or simulation was run. |
| Academic `batch/benchmark.py:674–710,916–989`; `batch/best_snapshot.py:1454` | Benchmark quality uses `.get(evidence_str, 0.15)`; candidate existence separately drives supported/mixed/unsupported. Snapshot functional probe counts candidates. | Benchmark does not decode edge absence in this parameter slot. Unknown, reserved-token text, arbitrary text, NULL and blank each score 0.15 with a CI in one synthetic mixed table. Current 5,124 simulation rows have zero such labels. UW-F04 establishes intake reachability. |
| **Scientist `cross_graph/compiler.py:858–925,1648–1700`** -> `cross_graph/gatherers/academic.py:40–99,141–148` -> evidence-need assessment/profile | **Independent unknown weight 0.25**, default 0.25; drives best-parameter ranking and academic score. The 36 real unknown candidates each score 0.0722925; real assessment is `insufficient`, expert review required, transport confidence 0.9. | Parameter contract, not edge absence. Ideal unknown remains 0.25 even while academic unknown weight is temporarily zero. This is a live non-academic weighting path, the scope stop in UW-F07. No claim that unknown alone becomes `supported`: maximum 0.25 is below mixed 0.45 / supported 0.75 thresholds. The gatherer prefers transport confidence when available, and final profile confidence aggregates statuses; 0.0722925 is **not** directly added into that final confidence. |
| Academic `batch/transport_score.py:568–620` -> transport readers / grounded causal-prior resolution | Carries exact-edge numeric confidence through penalties/rewards; no class reweighting. | Label-only changes do not change transport. Current unknown source count zero; re-derived confidence could alter future output. |
| `runtime/quality/credal_reference.py:834–869,1091–1277,1507–1588` | Strength/layer are provenance signals; confidence, endpoints, contest membership and other quality predicates determine completion status. | No direct label weight, and label-only absence does not remove a row. Actual pure derivation over all 440 unknown family rows gives 419 incomplete, 21 contested, zero confirmed; all 18 unknown contested rows are contested. Exact unknown count zero. |
| Academic `SKGQuery.contested_edge_value_outer_set:2241–2339` -> `tools/quality/validation/check_layer3_gy_knowledge_substrate_contract.py` | Ignores selected strength, maps stored confidence to numeric trust cap/multiplier, emits a declared `search_only` / `proxy_identified` envelope if claim-linked CI estimates exist. | All 18 unknown contested rows resolve their 21 claims, but **zero** have the required CI estimates; zero current unknown envelopes can be produced by this path. Missing estimates raise, not invent bounds. Existing predicate is unchanged. |
| `runtime/quality/capability_index_compiler.py:875–1038`; `runtime/quality/proving_ground/causal_forecast_search.py`; Scientist causal-edge compiler branch | Consume exact edges or confidence-filtered support and transport. Capability compiler selects the strength field but does not interpret its class; a separate numeric parse of strongest dissent defaults nonnumeric labels to zero. | No current exact unknown input; Scientist causal-edge min 0.25 excludes all 440 family unknown rows. They retain existing confidence/row predicates. No authority producer or runtime-quality source repair is inferred. |
| Academic `knowledge/search.py:225–246` -> Scientist `agent/knowledge_tools.py:169–185`, `cross_graph/feedback.py:175–188`; benchmark/QC | Forward candidate claims/summaries or count rows; QC/benchmark inspect numeric confidence, age, conflict, provenance and availability. | Edge absence stays paired through the V2 path. Row existence and confidence are not automatically zeroed by a label. No extra evidence-class arithmetic at these terminals. |
| Academic `batch/best_snapshot.py`; `tools/ops_runners/cloud/merge_shards.py`; source-content relation census; substrate inventory and table-literal validation tools enumerated by the census | Copy/hash/inventory/recorded-history consumers. A label can affect content hashes, not confer authority by itself. | Preserve recorded absence/value bytes or report counts; no automatic history repair. This is not permission to run any copying/re-derivation tool. |

Adjacent but not adopted into this lane: Catalog
`data_forge/domains/catalog/knowledge/variable_alignment.py:265,326–391,505–535` has an
independent `unknown: 0.35` map and tuple/dict defaults. Its `align_meta_analytic` definition
and export are the only occurrences in the complete `src/` + `tools/` named-call search.
No live bridge from this pinned academic snapshot was established. It is not needed to
justify the stop: the directly executed Scientist consumer already does so.

### UW-F04 — the default is reachable, not a hypothetical dictionary lookup

`batch/graph_builder.py:390` reads simulation JSONL dictionaries grouped by work ID.
`run_graph_load:1095,1403–1430` consumes those dictionaries, or record metadata when no
simulation numeric file is present. It checks numeric ID, canonical name, and numeric point
estimate, then copies `str(numeric.get('evidence_strength') or '')`. The materializer checks
JSON shape but does not validate that label as an evidence enum. Thus a row with a valid ID,
canonical name, point estimate, CI and simulation-ready source layer can carry an arbitrary
label into the exact table queried by benchmark. This intake was inspected, **not invoked**.

The real benchmark function was run against one synthetic mixed in-memory table:

| Stored parameter label | Quality score with CI |
| --- | ---: |
| `rct` | 1.0 |
| `theoretical` | 0.15 |
| `unknown` | 0.15 |
| `not_established` | 0.15 |
| `alien` | 0.15 |
| NULL | 0.15 |
| empty string | 0.15 |

Missing/blank uses the recognized unknown key; arbitrary/reserved-token text uses the
unrecognized-key default. They are different ingress mechanisms with the same score.
Without CI/SE the function multiplies by 0.7. Current pinned default use is **zero**;
future/callable reachability is established. A constant-only change would not remove the
literal fallback. This is characterization, not a repair test taught to a new behavior.

### UW-F05 — unknown is not absent, but this corpus does not establish calibration

The complete 310,829 extraction JSON walk finds 137,714 embedded claim objects (a different
grain from the 137,589 persisted raw rows). All 137,714 use generic `strength`; zero have
an `evidence_strength` field or vocabulary sidecar. Exactly 1,813 say generic unknown.
The raw table independently has 1,813 unknown rows, across 725 works: all from
`resolve_extract`, all adjudicated; 1,774 fulltext and 39 abstract-only. Their raw publication
flag is true for 297; that flag is not the adjudicated historical publication decision.
Extraction confidence ranges 0.4–1 (mean 0.846282403), while trust ranges
0.1525–0.87 (mean 0.337728565). Neither number is outcome calibration of evidence strength.
Design hints include IV 878, unclear 761, structural-model 121, and 53 other hints;
unknown and the design axis demonstrably coexist.

The complete schema scan finds no calibration/outcome/weight-rule/strength-provenance column.
The recursive extraction-key census finds no calibration or weight-rule key. Its only
`outcome` hits are two `subgroup_effects.expected_outcomes` locations, not a weight-validation
artifact; its evidence-strength hits are 5,133 metadata simulation estimates. These are
reported rather than turning a keyword scan into a proof of calibration. More decisively,
the actual weighting paths consume constants/defaults, not a content-bound outcome/rule
reference. The supplied snapshot and consumers do **not establish** a licensing chain.

Code also disproves a universal reading of unknown as “the extractor deliberately judged
this evidence class unidentifiable”: `article_extractor.py:396–400` normalizes missing and
unrecognized inputs to unknown, `table_extractor.py:160` stamps unknown, and the numeric
reader defaults missing strength to `EvidenceParameter.UNKNOWN` (`ir/analytics/literature.py:503`).
The 51,908 raw parameter payload omissions are measured evidence of that catch-all behavior,
not a speculation from an enum default. There are 45,707 distinct raw parameter names;
41,657 have no exactly matching simulation-name row (46,827 raw rows). This is an exact-name
anti-join, not a claim about every possible alias lookup.

The appropriate Phase-1 conclusion is therefore **heterogeneous/catch-all provenance and
calibration not established**, not “every unknown is worthless” or “unknown equals absence.”
An explicitly recorded `UNKNOWN` remains a value with `candidate` status; an admitted edge
absence remains `None` + `not_established`. The corpus provides no warrant to collapse them.
Choosing close (a) or (b), and whether/where a declared limitation must travel, belongs to
Phase 2 after the scope ruling; it is not silently decided here.

### UW-F06 — before/after B-2 over identical inputs

The correct pre-implementation source is `1664a6d8a` (`dec7beccb^`, the design commit).
`git diff --exit-code fca52ea2b..1664a6d8a -- src tests` is empty; the B1 adapter in
`knowledge/types.py` is unchanged between `1664a6d8a` and this task's base. Old resolver
functions were extracted by AST from that ref and called in isolation; the current resolver
received the same values. No old writer or current producer was run.

| Same-input population | N | Unknown before → after | Declared absence before → after | Interpretation |
| --- | ---: | ---: | ---: | --- |
| All `DesignFamily` × explicitly supplied `EvidenceStrength` pairs | 200 | 2 → 20 | 0 → 0 | **+18**, +9 percentage points across 200 pairs. Among the 20 explicit unknown inputs, preservation rises 2/20 → 20/20. The old design override suppressed 18 real supplied unknowns. |
| All 20 design hints without evidence, plus four free-key placeholders | 24 | 2 → 0 | 0 → 24 | Missing evidence moves to absence, not to unknown. All 24 outcomes change. |
| All raw persisted legacy rows through the unchanged B1 adapter, callable `_infer` comparison | 137,589 | 137,589 → 0 | 0 → 137,589 | Diagnostic helper domain only. This branch was not the published caller; these are **not** 137,589 emitted edges. |
| Actual published cohort: old live adjudication resolver versus current resolver on the same admitted source rows | 7,868 | 0 → 0 | 0 → 7,868 | **No increase** in the measured published-cohort unknown frequency. Old replay reproduces the full stored distribution in UW-F02. |
| Its credibility-fallback subset | 342 | 0 → 0 | 0 → 342 | Old observational → absence, not unknown. Subset, not extra rows. |
| Span claim with omitted evidence / span claim with explicit unknown | One witness each | unknown → absence / unknown → unknown | Omission distinguished from value | Pinned span table absent; no empirical span-frequency estimate. |

162/200 explicit enum-pair outcomes change overall. This controlled matrix establishes a
real region in which B-2 increases unknown preservation, but there is no retained V2 typed
claim-input population here from which to estimate its production frequency. The negative
24-case matrix and actual published cohort do not increase it. No frequency of future runs
is inferred from synthetic prevalence. The 342 historical misstatements and all pinned
projection bytes remain recorded history.

### UW-F07 — Phase-1 stop and requested ruling

**Stop rule 1 is triggered.** The property to close is unfounded academic-evidence
contribution, not just the value of the academic dictionary. Scientist's
`_parameter_candidate_score` consumes the same typed academic candidates and independently
assigns unknown 0.25. Actual pinned inputs reach it. Setting the academic constant to zero
in isolation leaves the ideal Scientist score exactly 0.25. This is the **same contribution
class across another owner**, not a new authority/receipt/champion workstream.

Even inside academic, the constant-only falsifier leaves two zero-weight unknown articles
with confidence **0.06** via replication, and the all-zero parameter-prior branch replaces
weights with ones. The unchanged current ideal before-confidence is 0.15 for one unknown,
0.2775 for two unknowns or theoretical+unknown; adding edge absence does not change 0.15.
These diagnostics explain why a repair designed from the constant alone would be incomplete;
they are not an adopted implementation plan.

The requested architectural ruling is whether the row should own the directly reached
Scientist parameter-weighting consumer alongside the academic consumers, or explicitly
disposition it as a bounded residual with its own owner/limitation contract. Catalog alignment
has no established live bridge here and is not silently added. Any eventual close must keep
unknown as a recorded value, preserve B-2 edge encoding/exclusion, leave data unchanged, and
retain existing predicates/checker denominators. No repair round has been consumed. Phase 2
and Phase 3 are **not started**; their design, before/after repaired confidence, and new
red/green mixed-outcome evidence are deliberately not claimed.

### Transcriber-ready prose — row remains open

> `academic-unknown-evidence-contributes-nonzero-weight` — Phase 1 measured at `2a26fa610`;
> repair awaits scope ruling. In the pinned read-only snapshot, unknown occurs in 0/7,868
> exact-evidence rows, 0/7,607 exact edges, 440/15,945 retained family rows (confidence
> 0.009811872–0.183199924), and 18/723 contested rows (all confidence 0.15; three also carry
> unknown strongest dissent). There are zero unknown exact-derived transport rows. Full
> read-time family/hybrid prior queries expose 440 unknown rows; default Foundry min 0.2
> excludes them. Actual credal derivation gives 419 incomplete + 21 contested unknown family
> rows, and 18 contested unknown contested rows; none confirmed. The retained family/contested
> generations differ from current exact evidence, so mixed-row unknown numerical attribution
> is bounded by missing historical per-evidence provenance. Of 51,908 raw parameter payloads,
> all omit evidence strength; 51,883 read as UNKNOWN and 25 reject. Benchmark's arbitrary-key
> 0.15 default is reachable through simulation-row intake, although current 5,124 simulation
> rows contain zero unknown/unrecognized labels. No content-bound outcome calibration licenses
> unknown's contribution in the measured corpus/consumers. B-2 changes explicit-unknown
> preservation from 2 to 20 in the exhaustive 200 enum-pair matrix (+18), but published-cohort
> unknown remains 0→0 and missing evidence resolves to absence. The weighting class reaches
> Scientist's live cross-graph parameter scorer, which independently assigns UNKNOWN 0.25;
> it remains 0.25 with the academic constant zeroed. Stop rule 1 applies before design/repair.
> Keep the existing closure signal and the prohibition on relabeling UNKNOWN as
> NOT_ESTABLISHED. Findings and reproducible commands: journal UW-F01–UW-F07. Status: open,
> pending architectural scope disposition; no production data or source changed.

## Event 2 — reproducible commands and targeted characterization, 2026-09-05

All commands run from the worktree in UW-F01. The diagnostic files and logs are in
`.tmp_unknown_measure.sJ3Bou/`, confirmed ignored by `git check-ignore`. Their full programs
are reproduced below so the evidence does not depend on retaining ignored scratch files.
They are measurement code, not shipped product changes.

```sh
git status -sb
git rev-parse HEAD dec7beccb^
git diff --exit-code fca52ea2b..1664a6d8a -- src tests
git diff --exit-code 1664a6d8a..2a26fa610 -- src/polisyos/data_forge/domains/academic/knowledge/types.py
shasum -a256 production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb
git check-ignore .tmp_unknown_measure.sJ3Bou/corpus.py
rg -n 'query_parameters\(|get_parameter_prior\(|select_for_context\(' src tools --glob '*.py'
rg -n 'align_meta_analytic|contested_edge_value_outer_set' src tools --glob '*.py'
```

For direct source inspection, `sed -n` was used over the exact ranges in UW-F03–UW-F05,
including the publication-independent simulation-row intake, the parameter bridge, the
cross-graph assessment/gatherer/final status aggregation, and B2-F03/D03 in the prior journal.
Two scratch queries initially used guessed column names (`confidence`, `name`), failed with
DuckDB binder errors, and were corrected from `DESCRIBE`/the consumer SELECT to
`claim_extraction_confidence` and `canonical_name` before the successful full runs reproduced
below. These were measurement harness mistakes; no partial output is offered as a completed
census and no product fix was made.

Existing B-2 characterization: **35 passed, exit 0**, no source/test edits. The command is
bounded to 12 named nodes, including the parameterized 24-case design/placeholder matrix.
It verifies the inherited absence behavior, not closure of this unknown-weight row. There
is no new red/green repair evidence because the Phase-1 scope stop precedes implementation.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q \
  tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py::test_edge_strength_without_explicit_evidence_is_declared_absent \
  tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py::test_edge_strength_preserves_explicit_evidence_despite_divergent_design \
  tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py::test_legacy_theoretical_moderate_resolves_absence_not_observational \
  tests/unit/data_forge/domains/academic/batch/test_skg_confidence.py::test_declared_absence_contributes_zero_edge_confidence \
  tests/unit/data_forge/domains/academic/batch/test_skg_confidence.py::test_declared_absence_does_not_change_established_edge_confidence \
  tests/unit/data_forge/domains/academic/batch/test_skg_confidence.py::test_unknown_retains_its_existing_nonzero_edge_confidence \
  tests/unit/data_forge/domains/academic/knowledge/test_skg_query.py::test_query_claims_decodes_persisted_declared_absence \
  tests/unit/data_forge/domains/academic/knowledge/test_skg_query.py::test_query_edge_support_pairs_declared_absence_with_status \
  tests/unit/data_forge/domains/academic/knowledge/test_skg_query.py::test_query_claims_hybrid_ignores_declared_absence_when_evidence_exists \
  tests/unit/foundry/methods/catalog/causal/test_literature_prior.py::test_build_literature_prior_decodes_persisted_declared_absence \
  tests/unit/scientist/discovery/test_prior_miner.py::test_prior_miner_preserves_declared_absence_without_value_token \
  tests/unit/ir/test_literature_contract.py::test_literature_prior_roundtrips_declared_absence_without_value_token \
  > .tmp_unknown_measure.sJ3Bou/characterization-tests.log 2>&1
```

### Complete measurement programs

The four successful commands were:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python .tmp_unknown_measure.sJ3Bou/source_census.py > .tmp_unknown_measure.sJ3Bou/source_census.log 2>&1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python .tmp_unknown_measure.sJ3Bou/corpus.py > .tmp_unknown_measure.sJ3Bou/corpus.log 2>&1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python .tmp_unknown_measure.sJ3Bou/behavior.py > .tmp_unknown_measure.sJ3Bou/behavior.log 2>&1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python .tmp_unknown_measure.sJ3Bou/b2_delta.py > .tmp_unknown_measure.sJ3Bou/b2_delta.log 2>&1
```

Each completed with exit 0. The code below is the exact final script content used for those
runs. Read-only queries/pure functions are the measured paths; no graph or artifact producer
entry point is called. Replaying the code need not create a separate tracked file.

#### A — complete source denominator

```python
"""Complete tracked application/tool lexical census and complete Python AST walks."""
import ast
import json
import subprocess
from collections import Counter
from pathlib import Path

paths = [Path(p) for p in subprocess.check_output(['git','ls-files','src','tools','apps','packages'],text=True).splitlines()]
print('application_paths',len(paths),'file_types',json.dumps(Counter(p.suffix for p in paths),sort_keys=True))
weights, tables, numeric_maps = [], [], []
parse_errors = []
vocabulary = {'rct','meta_analysis','quasi_natural','quasi_natural_event','panel_fe','structural','observational','cross_sectional','theoretical'}
for p in paths:
    try:
        text = p.read_text()
    except (UnicodeDecodeError, OSError):
        continue
    if 'ac_skg_edges' in text or 'ac_skg_edge_evidence' in text:
        tables.append(str(p))
    if 'EVIDENCE_WEIGHTS' in text:
        weights.append(str(p))
    if p.suffix != '.py':
        continue
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        parse_errors.append([str(p),str(exc)])
        continue
    for node in ast.walk(tree):
        if isinstance(node,ast.Dict):
            keys = {k.value for k in node.keys if isinstance(k,ast.Constant) and isinstance(k.value,str)}
            if 'unknown' in keys and len(keys & vocabulary) >= 2:
                numeric_maps.append([str(p),node.lineno,ast.unparse(node)])
print('application_python_parse_errors',parse_errors)
print('weight_map_files',json.dumps(weights))
print('exact_table_literal_files',json.dumps(tables))
print('string_keyed_strength_dicts',json.dumps(numeric_maps))
all_py = [Path(p) for p in subprocess.check_output(['git','ls-files','src','tools','tests'],text=True).splitlines() if p.endswith('.py')]
errors = []
for p in all_py:
    try:
        ast.parse(p.read_text())
    except SyntaxError as exc:
        errors.append([str(p),str(exc)])
print('source_tool_test_python',len(all_py),'by_root',dict(Counter(p.parts[0] for p in all_py)),'parse_errors',errors)
```

#### B — complete snapshot populations and payloads

```python
"""Read-only Phase-1 census; no writer/producer entry points are invoked."""
import json
from collections import Counter
from pathlib import Path

import duckdb

from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery

DB = Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
con = duckdb.connect(str(DB), read_only=True)

def out(label, value):
    print(label, json.dumps(value, default=str, sort_keys=True), flush=True)

tables = [r[0] for r in con.execute('SHOW TABLES').fetchall()]
out('tables', {t: con.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in tables})
for table, column in (
    ('ac_skg_edge_evidence', 'evidence_strength'), ('ac_skg_edges', 'evidence_strength'),
    ('ac_skg_family_edges', 'evidence_strength'), ('ac_skg_contested_edges', 'evidence_strength'),
    ('ac_skg_contested_edges', 'strongest_dissent_strength'),
    ('ac_skg_simulation_parameters', 'evidence_strength'),
):
    out(table + '.' + column, con.execute(f'SELECT {column}, count(*) FROM {table} GROUP BY 1 ORDER BY 1').fetchall())
for table in ('ac_skg_family_edges', 'ac_skg_contested_edges'):
    out(table + '.unknown_confidence', con.execute(f"SELECT count(*),min(confidence),avg(confidence),max(confidence),sum(confidence),sum(n_articles),sum(n_claims) FROM {table} WHERE evidence_strength='unknown'").fetchone())
    out(table + '.dates', con.execute(f'SELECT min(updated_ts),max(updated_ts) FROM {table}').fetchone())
out('exact.dates', con.execute('SELECT min(updated_ts),max(updated_ts) FROM ac_skg_edges').fetchone())
out('transport', con.execute("SELECT count(*),count(*) FILTER(WHERE e.evidence_strength='unknown'),count(*) FILTER(WHERE e.evidence_strength='not_established'),count(*) FILTER(WHERE e.edge_id IS NULL),min(t.base_confidence),max(t.base_confidence),min(t.transport_confidence),max(t.transport_confidence) FROM ac_skg_transport_scores t LEFT JOIN ac_skg_edges e USING(edge_id)").fetchone())
out('unknown_contested_weights', con.execute("SELECT sum(positive_weight),sum(negative_weight),sum(mixed_weight) FROM ac_skg_contested_edges WHERE evidence_strength='unknown'").fetchone())
raw = {r[0]: r[1:] for r in con.execute('SELECT id,strength,work_id FROM ac_causal_claims_raw').fetchall()}
exact_claims = {r[0] for r in con.execute('SELECT claim_id FROM ac_skg_edge_evidence').fetchall()}
exact_edges = {r[0] for r in con.execute('SELECT edge_id FROM ac_skg_edges').fetchall()}
for table in ('ac_skg_family_edges', 'ac_skg_contested_edges'):
    rows = con.execute(f'SELECT evidence_strength,claim_refs,article_refs,quality_signals_json FROM {table}').fetchall()
    for label, selected in (('all', rows), ('strongest_unknown', [r for r in rows if r[0]=='unknown'])):
        refs = [str(x) for r in selected for x in json.loads(r[1] or '[]')]
        unknown = {x for x in refs if x in raw and raw[x][0]=='unknown'}
        out(table + '.' + label + '.lineage', {
            'rows': len(selected), 'claim_ref_occurrences': len(refs), 'unique_claim_refs': len(set(refs)),
            'missing_raw_refs': len(set(refs)-raw.keys()), 'unique_raw_unknown_refs': len(unknown),
            'raw_unknown_refs_in_current_exact': len(unknown & exact_claims),
            'unique_works': len({str(x) for r in selected for x in json.loads(r[2] or '[]')}),
            'rows_referencing_raw_unknown': sum(any(str(x) in unknown for x in json.loads(r[1] or '[]')) for r in selected),
            'referenced_exact_ids_in_current_exact': len({str(x) for r in selected for x in json.loads(r[3] or '{}').get('exact_edge_ids', [])} & exact_edges),
        })
out('raw_strength_mode', con.execute('SELECT r.strength,e.extraction_mode,count(*) FROM ac_causal_claims_raw r LEFT JOIN ac_article_extractions e USING(work_id) GROUP BY 1,2 ORDER BY 1,2').fetchall())
out('raw_unknown', con.execute("SELECT count(*),count(DISTINCT work_id),count(*) FILTER(WHERE publish_to_graph),min(claim_extraction_confidence),avg(claim_extraction_confidence),max(claim_extraction_confidence),min(trust_score),avg(trust_score),max(trust_score) FROM ac_causal_claims_raw WHERE strength='unknown'").fetchone())
out('raw_unknown_design', con.execute("SELECT design_family_hint,count(*) FROM ac_causal_claims_raw WHERE strength='unknown' GROUP BY 1 ORDER BY 1").fetchall())
out('raw_unknown_basis', con.execute("SELECT source_basis,count(*) FROM ac_causal_claims_raw WHERE strength='unknown' GROUP BY 1 ORDER BY 1").fetchall())
out('raw_unknown_adjudicated', con.execute("SELECT count(*),count(DISTINCT r.id) FROM ac_causal_claims_raw r JOIN ac_claim_adjudications a ON a.claim_id=r.id WHERE r.strength='unknown'").fetchone())
out('schema_candidate_calibration_fields', con.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='main' AND (lower(column_name) LIKE '%calibrat%' OR lower(column_name) LIKE '%outcome%' OR lower(column_name) LIKE '%weight_rule%' OR lower(column_name) LIKE '%strength_provenance%') ORDER BY 1,2").fetchall())

key_hits = Counter()
json_counts = Counter()
def walk(value, path=''):
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = path + '.' + key
            if any(s in key.lower() for s in ('calibrat','outcome','weight_rule','evidence_strength','vocabulary')):
                key_hits[next_path] += 1
            walk(item, next_path)
    elif isinstance(value, list):
        for item in value:
            walk(item, path + '[]')
for (value,) in con.execute('SELECT extraction_json FROM ac_article_extractions').fetchall():
    json_counts['rows'] += 1
    try:
        payload = json.loads(value)
    except (TypeError, ValueError):
        json_counts['invalid_json'] += 1
        continue
    walk(payload)
    claims = payload.get('causal_claims', []) if isinstance(payload, dict) else []
    for claim in claims:
        json_counts['claim_objects'] += 1
        if isinstance(claim, dict):
            for key in ('strength', 'evidence_strength', 'vocabulary'):
                json_counts['claim_has_' + key] += key in claim
            json_counts['generic_strength_unknown'] += claim.get('strength') == 'unknown'
out('extraction_json_census', json_counts)
out('extraction_json_key_hits', key_hits)

parameter_counts = Counter()
for name, encoded in con.execute('SELECT canonical_name,parameter_json FROM ac_skg_parameters').fetchall():
    parameter_counts['rows'] += 1
    try:
        payload = json.loads(encoded)
    except (TypeError, ValueError):
        parameter_counts['invalid_json'] += 1
        continue
    parameter_counts['has_evidence_strength'] += 'evidence_strength' in payload
    parameter = SKGQuery._to_evidence_parameter(name, payload)
    if parameter is None:
        parameter_counts['rejected'] += 1
    else:
        parameter_counts['accepted_' + parameter.evidence_strength.value] += 1
out('raw_parameter_census', parameter_counts)
out('raw_parameter_names', con.execute('SELECT count(DISTINCT canonical_name) FROM ac_skg_parameters').fetchone())
out('raw_without_exact_simulation_name', con.execute('SELECT count(*),count(DISTINCT p.canonical_name) FROM ac_skg_parameters p WHERE NOT EXISTS(SELECT 1 FROM ac_skg_simulation_parameters s WHERE s.canonical_name=p.canonical_name)').fetchone())
files = [p for p in DB.parents[2].rglob('*') if p.is_file()]
out('snapshot_files', {'count':len(files),'types':Counter(p.suffix for p in files),'paths':sorted(str(p.relative_to(DB.parents[2])) for p in files)})
con.close()
```

#### C — real consumers and synthetic mixed/default witnesses

```python
"""Pure/read-only consumer witnesses. Synthetic tables use only :memory:."""
import json
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path
from types import SimpleNamespace

import duckdb

from polisyos.data_forge.domains.academic.batch.benchmark import _quality_weighted_parameter_score
from polisyos.data_forge.domains.academic.knowledge.search import ScholarKnowledgeGraph
from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery, ParameterCandidate
from polisyos.data_forge.domains.academic.knowledge.skg_store import (
    ArticleEvidence, EVIDENCE_WEIGHTS, aggregate_edge_confidence,
    decode_edge_evidence_strength, encode_edge_evidence_strength, edge_strength_rank,
)
from polisyos.ir.analytics.literature import EvidenceParameter, EvidenceStrength
from polisyos.ir.analytics.cross_graph import EvidenceNeed, EvidenceNeedType
from polisyos.scientist.cross_graph.compiler import _parameter_candidate_score, _assess_academic_need
from polisyos.runtime.quality.credal_reference import (
    _derive_l2_family_edge, _derive_l2_contested_edge, _l2_contested_memberships,
)

def out(label, value):
    print(label, json.dumps(value, default=str, sort_keys=True), flush=True)

db = Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
query = SKGQuery(db_path=db, index_dir=db.parent.parent)
for mode in ('exact', 'family', 'hybrid'):
    rows = query.query_prior_for_variables([], min_confidence=0, limit=100000, edge_layer=mode)
    out('prior_' + mode, {'rows':len(rows),'unknown':sum(r['evidence_strength']=='unknown' for r in rows),'strength_statuses':Counter(str(r.get('evidence_strength_status')) for r in rows)})
name = 'demographic.female_share'
candidates = query.query_parameters(name, layer='auto', require_simulation_ready=True)
out('real_parameter_candidates', {'name':name,'count':len(candidates),'strengths':Counter(c.parameter.evidence_strength.value for c in candidates),'scores':Counter(_parameter_candidate_score(c) for c in candidates)})
need = EvidenceNeed(need_id='unknown-weight-diagnostic',need_type=EvidenceNeedType.PARAMETER_NEED,parameter_name=name)
assessment = _assess_academic_need(need, concepts=[], academic_query=query, target_context=None)
out('real_academic_assessment', vars(assessment))
graph = ScholarKnowledgeGraph(db_path=db,index_dir=db.parent.parent)
prior = graph.get_parameter_prior(name)
out('real_parameter_prior', None if prior is None else prior.model_dump(mode='json'))
con = query._con
names = {r[0] for r in con.execute('SELECT canonical_name FROM ac_skg_variables').fetchall()}
memberships, _ = _l2_contested_memberships(con)
family_rows = con.execute("SELECT family_edge_id,src_family,dst_family,direction,n_articles,n_claims,evidence_strength,confidence,direction_histogram_json,design_tier_histogram_json,candidate_layer,quality_signals_json FROM ac_skg_family_edges WHERE evidence_strength='unknown' ORDER BY family_edge_id").fetchall()
out('credal_unknown_family', Counter(_derive_l2_family_edge(r,version='1',variable_names=names,contested_edges=memberships).status for r in family_rows))
contested_rows = con.execute("SELECT contested_edge_id,src_family,dst_family,dominant_direction,resolution_status,runtime_support,confidence,positive_weight,negative_weight,mixed_weight,direction_histogram_json,quality_signals_json FROM ac_skg_contested_edges WHERE evidence_strength='unknown' ORDER BY contested_edge_id").fetchall()
out('credal_unknown_contested', Counter(_derive_l2_contested_edge(r,version='1').status for r in contested_rows))
graph.close()
query.close()

synthetic = duckdb.connect(':memory:')
synthetic.execute('CREATE TABLE ac_skg_simulation_parameters(canonical_name VARCHAR, point_estimate DOUBLE, evidence_strength VARCHAR, confidence_interval_json VARCHAR, std_error DOUBLE, source_layer VARCHAR)')
labels = ['unknown','not_established','alien',None,'','rct','theoretical']
synthetic.executemany('INSERT INTO ac_skg_simulation_parameters VALUES (?,1,?,?,NULL,?)', [(str(i),s,'[0,2]','simulation_ready') for i,s in enumerate(labels)])
out('benchmark_mixed_one_run', [(s,_quality_weighted_parameter_score(SimpleNamespace(_con=synthetic),str(i),current_year=2026)) for i,s in enumerate(labels)])
synthetic.close()
for strength in ('unknown','not_established','alien'):
    payload = {'value':1,'evidence_strength':strength}
    p = SKGQuery._to_evidence_parameter('x',payload)
    out('parameter_decode_' + strength, None if p is None else p.evidence_strength.value)
    try:
        out('edge_decode_' + strength, decode_edge_evidence_strength(strength))
    except ValueError as exc:
        out('edge_decode_' + strength, type(exc).__name__)
out('edge_ranks', {s:edge_strength_rank(s) for s in ('unknown','not_established')})
year = datetime.now(UTC).year
unknown = ArticleEvidence('unknown',1,publication_year=year,sample_size=5000)
absent = ArticleEvidence('not_established',1,publication_year=year,sample_size=5000)
theory = ArticleEvidence('theoretical',1,publication_year=year,sample_size=5000)
out('ideal_edge_aggregation', {'unknown':aggregate_edge_confidence([unknown]),'absence':aggregate_edge_confidence([absent]),'theory':aggregate_edge_confidence([theory]),'unknown_plus_absence':aggregate_edge_confidence([unknown,absent]),'two_unknown':aggregate_edge_confidence([unknown,unknown]),'theory_plus_unknown':aggregate_edge_confidence([theory,unknown])})
candidate = ParameterCandidate(parameter=EvidenceParameter(name='x',value=1,confidence_interval=(0,2),evidence_strength=EvidenceStrength.UNKNOWN),source_context=None,source_layer='simulation_ready')
out('scientist_ideal_unknown', _parameter_candidate_score(candidate))
saved = EVIDENCE_WEIGHTS['unknown']
try:
    EVIDENCE_WEIGHTS['unknown'] = 0.0
    out('diagnostic_academic_constant_zero', {'two_unknown_edge':aggregate_edge_confidence([unknown,unknown]),'scientist_ideal_unknown':_parameter_candidate_score(candidate)})
finally:
    EVIDENCE_WEIGHTS['unknown'] = saved
```

#### D — same-input pre/post-B-2 resolver comparison

```python
"""Same-input, pure pre/post B-2 resolver comparison; never re-derive a database."""
import ast
import subprocess
from collections import Counter

import duckdb
from polisyos.data_forge.domains.academic.batch.article_extractor import serialize_rich_claim_occurrence_vocabulary
from polisyos.data_forge.domains.academic.batch.graph_builder import _infer_edge_strength as post
from polisyos.data_forge.domains.academic.knowledge.skg_store import encode_edge_evidence_strength, normalize_strength
from polisyos.data_forge.domains.academic.knowledge.types import adapt_legacy_claim_occurrence_transport, candidate_claim_vocabulary_store_values
from polisyos.ir.analytics.literature import CausalClaim, DesignFamily, EvidenceStrength

rev = '1664a6d8a'
path = 'policy-engine/src/polisyos/data_forge/domains/academic/batch/graph_builder.py'
tree = ast.parse(subprocess.check_output(['git','show',f'{rev}:{path}'],text=True))
nodes = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'_infer_edge_strength','_legacy_strength_from_adjudication'}]
namespace = {'normalize_strength':normalize_strength}
exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),f'{rev}:{path}','exec'),namespace)
pre = namespace['_infer_edge_strength']
pre_legacy = namespace['_legacy_strength_from_adjudication']

def report(label, before, after):
    b,a = Counter(before),Counter(after)
    print(label,'n',len(before),'changed',sum(x!=y for x,y in zip(before,after,strict=True)),'unknown',f"{b['unknown']}->{a['unknown']}",'absence',f"{b['not_established']}->{a['not_established']}",flush=True)
    print('before',dict(sorted(b.items())),'after',dict(sorted(a.items())),flush=True)

def admitted_values(row):
    occurrence = {'cause':str(row[1] or ''),'effect':str(row[2] or ''),'direction':str(row[3] or ''),'strength':str(row[4] or ''),'mechanism':str(row[5] or ''),'design_family_hint':row[6]}
    return candidate_claim_vocabulary_store_values(adapt_legacy_claim_occurrence_transport(occurrence,provenance='legacy_snapshot'))

pairs = [{'design_family_hint':d.value,'evidence_strength':e.value} for d in DesignFamily for e in EvidenceStrength]
report('enum_20x10_explicit',[pre(i) for i in pairs],[post(i) for i in pairs])
negative = [{'design_family_hint':d.value,'evidence_strength':None,'evidence_strength_status':'not_established'} for d in DesignFamily]+[{'strength':s} for s in ('strong','very_strong','moderate','weak')]
report('negative_20_design_plus_4_placeholder',[pre(i) for i in negative],[post(i) for i in negative])
con = duckdb.connect('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb',read_only=True)
raw = con.execute('SELECT id,cause,effect,direction,strength,mechanism,design_family_hint FROM ac_causal_claims_raw ORDER BY id').fetchall()
values = {r[0]:admitted_values(r) for r in raw}
report('admitted_legacy_snapshot_callable',[pre(values[r[0]]) for r in raw],[post(values[r[0]]) for r in raw])
published = con.execute('SELECT e.claim_id,a.design_family,a.causal_credibility FROM ac_skg_edge_evidence e JOIN ac_claim_adjudications a ON a.claim_id=e.claim_id ORDER BY e.claim_id').fetchall()
before = [pre_legacy({'design_family':d,'causal_credibility':c}) for _,d,c in published]
after = [post(values[i]) for i,_,_ in published]
report('published_live_path',before,after)
mapped = {'rct','iv','did','rdd','synthetic_control','event_study','quasi_experimental_other','quasi_experimental_did','quasi_experimental_rdd','meta_analysis','panel_fe','system_gmm','gmm','structural_model','time_series_cointegration','ols','ols_cross_sectional'}
ix = [i for i,(_,d,c) in enumerate(published) if str(d or '').strip().lower() not in mapped and str(c or '').strip().lower() in {'strong','moderate','weak'}]
report('credibility_fallback_subset',[before[i] for i in ix],[after[i] for i in ix])
con.close()
for label,claim in (('span_omitted',CausalClaim(cause_variable='x',effect_variable='y')),('span_explicit_unknown',CausalClaim(cause_variable='x',effect_variable='y',evidence_strength=EvidenceStrength.UNKNOWN))):
    sidecar = candidate_claim_vocabulary_store_values(serialize_rich_claim_occurrence_vocabulary(claim,record_extraction_mode='diagnostic'))
    print(label,'before',normalize_strength(claim.evidence_strength.value),'after',encode_edge_evidence_strength(sidecar['evidence_strength'],status=sidecar['evidence_strength_status']),flush=True)
```

#### E — contested outer-set prerequisites, all unknown rows

This command reads the real link/estimate consumers without constructing or persisting an
outer-set artifact. Exit 0: `rows=18, resolved_claims=21, rows_with_ci_estimates=0,
ci_estimate_occurrences=0`.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python - <<'PY' > .tmp_unknown_measure.sJ3Bou/outer-set-links.log 2>&1
import json
from collections import Counter
from pathlib import Path
from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
p=Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
q=SKGQuery(p,p.parent.parent)
counts=Counter()
for key,refs in q._con.execute("SELECT contested_edge_id,claim_refs FROM ac_skg_contested_edges WHERE evidence_strength='unknown'").fetchall():
 counts['rows']+=1
 claims=q._contested_claim_rows(tuple(json.loads(refs)))
 estimates=q._parameter_estimates_for_work_ids(tuple(x['work_id'] for x in claims.values()))
 counts['resolved_claims']+=len(claims)
 counts['rows_with_ci_estimates']+=bool(estimates)
 counts['ci_estimate_occurrences']+=len(estimates)
print(dict(counts))
q.close()
PY
```

## Event 3 — pre-commit verification and review limitation, 2026-09-05

The four embedded Python programs were parsed and compared byte-for-byte (ignoring final
newlines only) against the successfully executed scratch scripts: `journal_programs=4`,
`syntax_errors=0`, `scratch_drift=0`. The post-measurement database hash is again exactly
`583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`.

A read-only reviewer was requested using the requesting-code-review skill, with the
Phase-1-only boundary, one-review budget, and no-source/data-write rules. It returned an
execution error: workspace credits exhausted. **No independent review verdict was received.**
That is a tooling non-receipt, not a GO or a product failure. It does not authorize a repair
or remove the need for the architect's scope ruling. Root readback checked the findings
against the complete logs and relevant terminal code; no independent approval is claimed.

Precision qualification to UW-F03's Scientist score bound: 0.25 is the ideal unknown score
with ordinary nonnegative transport penalties and factors at most one, and all 36 measured
real candidates score 0.0722925. The scorer itself does not cap its intermediate transport
factor at one for an arbitrary manually constructed negative penalty. No universal bound
over malformed candidate objects is asserted, and no parameter-validation repair is folded
into this row. The independent-weight scope-stop witness needs only the valid ideal and
actual pinned inputs already executed.

Diagnostic log SHA-256 receipts (logs are ignored scratch; reproducible programs are above):

| Log | SHA-256 |
| --- | --- |
| `corpus.log` | `82a75fe8e6e294df7ed1fbd6ce493c8c52aa5b0bdcda5fbf269fcfc8e13211d5` |
| `behavior.log` | `a25b5fc1214fd7e2388e54d58ad318840fa4ffc142a241e78eb052cd91b76d70` |
| `b2_delta.log` | `641bb04b40cde9c52ec09a878d05fa84f7996cb41f9d77e209db4c6d472f1849` |
| `source_census.log` | `6439d017ba3be8f9abf276c89bfd08fee977ace69af4bf4e3e94c79a3ff8bd71` |
| `outer-set-links.log` | `15f1f541f1f61e424ebf4f8a1d4043b25f4e497338e01862b20ac1cbad15e2b0` |
| `characterization-tests.log` | `23814bd54c3f40e10907bbb3fbbf634b818152cf7afb3d0013ebceb07460326b` |

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python - <<'PY'
import ast,re
from pathlib import Path
p=Path('docs/superpowers/journals/2026-09-04-unknown-evidence-weight.md')
blocks=re.findall(r'^```python\n(.*?)^```$',p.read_text(),re.M|re.S)
expected=['source_census','corpus','behavior','b2_delta']
assert len(blocks)==len(expected)
for text,name in zip(blocks,expected,strict=True):
 ast.parse(text)
 assert text.rstrip()==Path('.tmp_unknown_measure.sJ3Bou',name+'.py').read_text().rstrip(),name
print('journal_programs=4 syntax_errors=0 scratch_drift=0')
PY
```
