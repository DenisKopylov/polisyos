# B-2 — manufactured edge design and the span publication gate

## Event 1 — Phase 1 finding, 2026-09-04

**Phase:** understand only. **Disposition:** scope ruling required before Phase 2.
No implementation design, source edit, test edit, schema edit, or data repair has been made.

### Basis and custody

- Worktree: `/Users/deniskopylov/polisyos/.worktrees/debt-b2-manufactured-design/policy-engine`.
- Attached branch: `codex/debt-b2-manufactured-design`.
- Entry HEAD and merge base with main: `cd6dfc50bea2a38f4785eacdcd1befc98b144ecf`.
- B-1 merge `155810bcc` is an ancestor. Its vocabulary boundary is retained, not reopened.
- The first read was the two exact rows in `docs/plans/active/DEBT-REGISTER.md`.
  Their closure signals remain the contract. No file under `docs/plans/active/` is edited.
- The snapshot is
  `production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb`.
  The `production_data` link resolves to the primary checkout's read-only data directory.
  Every database connection to that snapshot used `duckdb.connect(path, read_only=True)`.
  Initial SHA-256:
  `583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`.
- The worktree has no local `.venv`. Diagnostics used
  `/Users/deniskopylov/polisyos/policy-engine/.venv/bin/python`, with `PYTHONPATH=src`
  for source execution. Import-path readback confirmed both `graph_builder` and `skg_store`
  came from this worktree. Both checkout `uv.lock` files hash to
  `3f9dfe227ec3c49747027fefa5d73acba9c9e21ec691c44829fb1066a69b38d1`.
- No extraction or adjudication was run. The gate reproduction constructed one synthetic claim
  and called the existing writer against `:memory:` only; it never received a production path.
- Initial parallel investigations returned account-credit errors, not findings. After the user's
  continuation, the same read-only investigators resumed. Root measurements below were executed
  independently, not accepted from the failed attempts.

### Pattern pass

Relevant patterns are P04/P05 (absence and authority), P14 (evidence-strength truthfulness),
P31/P40 (one class in multiple projections), P35 (complete denominators), and P37/P38
(declared predicate versus the property actually measured). The register was read before analysis.

The observed class is **one vocabulary axis being substituted for another**, followed by rank
arithmetic that does not distinguish an unestablished value from observed weak/unknown evidence.
The free-key branch is one instance; the adjudication credibility fallback is the same class on
the live branch, not a new unrelated finding. The span writer has a separate missing publication
predicate and misleading projection names. The measured repair-state gaps are
`verification_missing` for the publication predicate and `semantic_test_missing` for the stated
negative closure properties. This finding does not claim an absent producer or a completed repair.

## B2-F01 — the named free-key function does not produce the published cohort

The complete AST call census over **5,549 tracked Python files under `src/`, `tools/`, and
`tests/`**, with zero parse errors, finds exactly two `_infer_edge_strength` calls:
`graph_builder.py:1691` and `:1728`. Both are the `else` of the same expression:

```python
_legacy_strength_from_adjudication(adjudication)
if adjudication is not None
else _infer_edge_strength(claim)
```

The loop has already required `adjudication is not None and
adjudication.get("publishable_edge")` at `graph_builder.py:1648-1653`. Thus neither `else`
is reachable through the current published-edge loop. `_infer_edge_strength` still contains
the defective free-key conversion at `:709-715`; direct invocation reproduces it, but removing
it alone changes **zero currently reachable batch edge emissions**.

The live source is `_legacy_strength_from_adjudication`, defined at `:408-434`, called at
`:1689` and `:1726`. Its output enters both the aggregate evidence samples and
`ac_skg_edge_evidence.evidence_strength`; `_materialize_skg` emits the aggregate to
`ac_skg_edges.evidence_strength` and `confidence` at `:947-962`.

This corrects the register's causal attribution, not its closure requirement. A callable
placeholder-to-design coercion remains a defect even though its present caller branch is dead.

## B2-F02 — provenance of all 7,868 published evidence rows

The complete pinned snapshot denominator is:

| Table or relation | Rows |
| --- | ---: |
| `ac_causal_claims_raw` | 137,589 |
| `ac_claim_adjudications` | 67,791 |
| `ac_causal_claims` | 7,868 |
| `ac_skg_edge_evidence` | 7,868 |
| `ac_skg_edges` | 7,607 |
| `ac_skg_span_grounded_claims` table existence | 0 tables |

Every one of the 7,868 evidence rows joins to a raw claim and an adjudication. All 7,868 raw
hints are populated; **zero** are eligible for the blank-hint free-key fallback. The whole
69,798-row blank-hint `moderate` placeholder cohort has **zero adjudications and zero published
edge-evidence rows**.

The actual split is not “free key versus raw design hint.” It is:

| Actual branch consistent with the persisted lineage and current writer | Evidence rows |
| --- | ---: |
| Adjudicated design mapped into evidence class | 7,526 |
| Adjudicated credibility fallback mapped into evidence class | 342 |
| `_infer_edge_strength` free-key fallback | 0 |
| **Total** | **7,868** |

Replaying the complete current `_legacy_strength_from_adjudication` case distinction in SQL
against all joined rows yields **zero disagreements** with stored evidence strength. This is
an exact reconstruction from recorded lineage, not a producer receipt proving the historical
invocation. The slim snapshot has neither the source evidence nor a receipt that establishes the
truth of a study design. “Populated hint” must not be transcribed as “grounded design.”

The stored class distribution reconciles to 7,868:

| Class | Rows |
| --- | ---: |
| `quasi_natural` | 4,122 |
| `meta_analysis` | 1,095 |
| `rct` | 954 |
| `panel_fe` | 793 |
| `quasi_natural_event` | 526 |
| `observational` | 374 |
| `structural` | 4 |

For the 4,122 `quasi_natural` rows specifically: **0 free-key fallback**, **4,122 populated raw
hints**, and **4,122 matching adjudication-design projections**. The adjudicated designs are
IV 3,751 + DiD 325 + synthetic control 25 + RDD 21 = 4,122. Only 3,945 raw hints map to that
same coarse class, and only 3,944 equal the adjudicated design literally. The other 177 raw
hints would not produce `quasi_natural` under the hint mapping. The historical result cannot
therefore be attributed wholesale to the raw hint path either.

The register's 254 `observational` rows are **`design_family='unclear'`**, not NULL/blank.
That column equals the raw hint in all 7,868 joined rows. Across the full published set,
566 raw hints differ from adjudicated design; 5,276 recorded raw `strength` labels differ
from published evidence strength. These are distinct recorded axes, not interchangeable sources.

## B2-F03 — consumer map and absence behavior

The pinned full-tree lexical census covers **4,781 tracked files under `src/`, `tools/`,
`apps/`, and `packages/`**, including **3,055 Python, 507 TypeScript, 716 TSX, and one SQL file**.
It finds 20 files containing either table literal: 15 source files and five tools, enumerated
below. Literal-free API callers were then followed through the query and prior contracts.
This is a code/data-flow census, not a claim that token search alone proves a call graph.

“Absent” below means the value is absent while the row/schema remains. Deleting rows or dropping
the column is a different operation. No actual snapshot value was changed to run this analysis.

| Consumer / terminal | Interpretation and downstream effect | What absence does today |
| --- | --- | --- |
| `knowledge/skg_store.py:486-595,1120-1168` | **Rank/weight.** Evidence weights, noisy-OR confidence, strength floors, multi-article bonus, directional contest and strongest dissent. `unknown` has base weight 0.15 and rank 0. | Not a zero-evidence state. Unknown still contributes; an unrecognized marker/blank uses the unknown weight and can receive the generic 0.10 floor. Multi-article count still includes it. |
| `batch/graph_builder.py:1687-1735,947-962` | Produces per-claim class, then chooses strongest class and aggregate confidence for exact edges. | Removing only the named `_infer` fallback changes no current published-loop output (B2-F01). The live adjudication path must be considered separately. |
| `batch/edge_synthesize.py:360-575` | **Rank/weight** from each evidence row into family and contested confidence/directional weights. `design_family` is separately an **opaque histogram label**, not an authority decision. | An absent class is stringified and still reaches weighting; absent design-family values are omitted from that histogram, not refused. |
| `knowledge/skg_versioning.py:115-162` | **Rank/weight replay.** Retraction normalizes the stored strongest class, approximates remaining articles, then recomputes confidence. | Blank/unrecognized strength normalizes to `unknown` and still contributes. No absence status is retained. |
| `batch/transport_score.py:567-620` | Does not read class/design. Carries rank-derived exact confidence into transport confidence after penalties/rewards. | Label-only absence has no effect; re-derived confidence changes transport. |
| `knowledge/skg_query.py:1090-1250,1643-1659` -> `knowledge/store.py:575-779` -> V2 claim/read API | **Candidate evidence enum**, not design authority. Exact/family/contested support carries the class; hybrid picks strongest. The V2 summary re-resolves and content-binds source rows, then returns `evidence_strength` with `candidate` status. | The support/summary path already preserves NULL/blank as `None` and returns `not_established`; a literal `not_established` in the value column is not an enum and is rejected. This read-side shape does not repair writer/aggregation semantics. |
| `skg_query.py:2503-2710` -> `scientist/methods/discovery/prior_miner.py:103-189` -> `priors.py:59-75,256-283` -> `search/readiness.py:1021-1062` | Class and layer are **opaque labels** persisted in `PriorKnowledgeSupport`. Readiness uses bundle status and resolved-edge coverage, not the label. | Blank/missing prior fields default to `unknown`; SQL NULL is stringified as `"None"` by the query and retained as an opaque nonempty string. A retained row still counts as resolved; label absence alone does not reduce coverage. |
| Same prior query -> `foundry/methods/catalog/causal/literature_prior.py:229-263` -> `ir/analytics/literature.py:894-1000` -> `foundry/.../graph_reconciliation.py:303-352,451-477` | Parses **EvidenceStrength enum**, carries it as graph metadata; literature confidence drives graph inclusion and combined confidence. | `unknown` is accepted. NULL/blank/new marker is not uniformly supported: query stringification followed by enum construction raises outside the query fallback block. A naive new string sentinel would break this consumer. |
| `scientist/cross_graph/compiler.py:927-1028` | Does not use the class for causal-edge support. Uses confidence, work count, conflict and transport to choose `SUPPORTED`/`MIXED`/`UNSUPPORTED`, persisted in the cross-graph evidence profile. | Label-only absence does not change the result; no row means unsupported. Re-derived confidence can alter the result. |
| `runtime/quality/credal_reference.py:834-869,1091-1274` | Class and `candidate_layer` are **opaque provenance signals**. Confidence, endpoints, approval, blockers, contest and direction agreement drive confirmed/contested/incomplete completions. | Label-only absence does not change closure status. Rank-derived confidence can. A label cannot be credited with the status predicates it does not drive. |
| `runtime/quality/capability_index_compiler.py:875-1038` | SELECTs `evidence_strength` but **does not consume its value**. Confidence/transport/parameter/boundary scores build an `EvidenceCapability` and its separate scholarly-support authority envelope. | An absent value with the column retained makes no direct difference. Re-derived confidence affects the score. The envelope's authority basis is a separate question, outside this task's authority-chain scope. |
| `runtime/quality/proving_ground/causal_forecast_search.py:1150-1258,1545-1558,6045-6050` | Candidate search and edge identity resolution; uses confidence/row existence, not class or layer. | Label-only absence has no direct effect; changed confidence/removed row changes selected candidates. |
| `batch/benchmark.py:453-545,764-809`; `batch/qc.py:1155-1164,1254-1283,1328-1334` | Benchmark uses confidence, work counts, conflict, age and the separate design-quality tier; QC uses counts/retractions/age/low confidence. | Label-only absence is not inspected. Re-derived confidence or a removed evidence row changes the evaluated input. These predicates must not be weakened to hide that. |
| `batch/best_snapshot.py`; `tools/ops_runners/cloud/merge_shards.py` | **Opaque copying/merging**, plus named functional checks. Retain recorded table bytes/values until existing rebuild paths are deliberately run. | No automatic historical reclassification. Removing a producer guess does not repair already recorded rows. |
| `tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py:284-367` | **Opaque source-content evidence**: carries class, design and layer into row hashes/census artifacts. | A changed/absent value changes the bound content hash. It is not an authority predicate on the class. |
| `knowledge/types.py`; `runtime/quality/substrate_registry.py`; the other three table-literal validation tools | Schema/binding names, table inventory, row/count witnesses. | No class-to-authority or class-ranking branch. They do not establish design provenance. |

The remaining three table-literal validation tools in the last row are
`check_layer3_gy_openalex_artifacts.py`, `check_layer3_gy_p2_semantic_evidence_quality_audit.py`,
and `check_layer3_gy_second_domain_pack.py`. The first is also the span writer's sole non-test caller.

The complete 20-file table-literal set is:

```text
src/polisyos/data_forge/domains/academic/batch/benchmark.py
src/polisyos/data_forge/domains/academic/batch/best_snapshot.py
src/polisyos/data_forge/domains/academic/batch/edge_synthesize.py
src/polisyos/data_forge/domains/academic/batch/graph_builder.py
src/polisyos/data_forge/domains/academic/batch/qc.py
src/polisyos/data_forge/domains/academic/batch/transport_score.py
src/polisyos/data_forge/domains/academic/knowledge/skg_query.py
src/polisyos/data_forge/domains/academic/knowledge/skg_store.py
src/polisyos/data_forge/domains/academic/knowledge/skg_versioning.py
src/polisyos/data_forge/domains/academic/knowledge/store.py
src/polisyos/data_forge/domains/academic/knowledge/types.py
src/polisyos/runtime/quality/capability_index_compiler.py
src/polisyos/runtime/quality/credal_reference.py
src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py
src/polisyos/runtime/quality/substrate_registry.py
tools/ops_runners/cloud/merge_shards.py
tools/quality/validation/check_layer3_gy_openalex_artifacts.py
tools/quality/validation/check_layer3_gy_p2_semantic_evidence_quality_audit.py
tools/quality/validation/check_layer3_gy_second_domain_pack.py
tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py
```

## B2-F04 — `candidate_layer` is misleading, not the authority switch

Across the full 4,781-file application/tool denominator, `design_tier_authority` has exactly
one literal occurrence: `skg_store.py:849`, the writer. The complete `candidate_layer` read
census finds transport through SKGQuery, PriorMiner/PriorKnowledgeSupport, and credal provenance.
None compares that layer to decide authority, admissibility, or closure. Changing that one
string does not change those consumers' decisions.

Do not conflate this with the **different field** `authority_tier='design_tier_l2'`:
`literature.py:1720` derives it from span support, the writer persists it in the span row and
quality JSON and returns it in the ingest report, and `runtime/quality/candidate_firewall.py`
does inspect that field (`:410,523,627`). Its predicate concerns resolved supporting spans,
not a proof of study design. The named layer literal is not that field. No authority/receipt/
evaluator repair is undertaken here.

The `design_family` column is also not a verified-design producer: both batch and span writers
fill it from a hint. In the observed consumers it is a histogram/content/provenance label. The
span writer's projection still misnames candidate content; inert naming is not permission to
retain the misleading claim in the eventual repair.

## B2-F05 — the publication bypass is genuine, with no current snapshot footprint

The complete 5,549-Python-file AST census finds five calls to
`ingest_openalex_span_grounded_claims`: four in two test files and one non-test call at
`tools/quality/validation/check_layer3_gy_openalex_artifacts.py:342`. There is no call from
production `src/` code. The function is nonetheless a callable, exercised writer, not harmless
dead text.

The non-test caller forwards `claims` without a publication filter. Its upstream
`extract_span_grounded_claims_from_openalex_work` sets `publish_to_graph=False` at
`ir/analytics/literature.py:1085`; the only subsequent filter there is span support (`:1087-1095`).
The ingest does vocabulary preflight before writes and checks `validated_supporting` in its
loop (`skg_store.py:802-810`), but does not check publication. Thus the missing check is not
merely defence-in-depth behind a caller gate.

A synthetic, source-bound in-memory reproduction used the real vocabulary preflight,
real span validator with an injected deterministic support client, and real writer. It did not
run extraction. Identical input with only the publication flag changed produced:

| `publish_to_graph` | ingested / rejected | exact edges | evidence rows | span rows |
| --- | --- | --- | --- | --- |
| `False` | 1 / 0 | `observational`, `design_tier_authority` | `observational`, hint `iv` | `design_tier_l2` |
| `True` | 1 / 0 | `observational`, `design_tier_authority` | `observational`, hint `iv` | `design_tier_l2` |

The pinned April database has **no span-grounded table at all**, and all 7,607 exact edges have
`candidate_layer='candidate'`. The span-writer defect therefore has **zero materialized
span-writer footprint in this snapshot and is fully live in code**. This is a capability defect,
not a claim of historical data contamination by that writer and not a finding of harmlessness.

## B2-F06 — the two scope questions require the architect's ruling

### 1. The design-to-evidence coarsening is not a property-preserving fallback

The current enums contain 20 DesignFamily and 10 EvidenceStrength members, with exactly four
shared literals: `meta_analysis`, `panel_fe`, `rct`, `theoretical`. Their parallel status and
entry dates are the supplied group-B finding; B-1 preserves the independent axes.

Execution over the complete **20 x 10 = 200** design/evidence input pairs shows that
`_infer_edge_strength` overrides an explicitly supplied evidence class in **162 pairs**, across
**18 design hints**. Concrete divergent witness:

```text
design_family_hint=iv, evidence_strength=observational -> quasi_natural
```

The code checks the hint first; it does not consult study content, a versioned compatibility rule,
or an adjudication of the evidence-strength axis. This establishes a live semantic substitution
inside the helper, not a justified coarsening. It does not establish that every recorded study
design is false. Its present batch branch remains unreachable as measured in B2-F01.

The edge layer has no equivalent of B-1's enforced value/status absence at its write/aggregation
boundary: its value columns are `VARCHAR NOT NULL`, ArticleEvidence takes a string, and
`unknown` is a member of the evidence vocabulary with nonzero weight. An isolated new string
is not an honest structural absence either: it is normalized/weighted by some consumers and
rejected by others (B2-F03). The existing V2 summary read already has the optional-value plus
`not_established` shape, but this is only one consumer, not the entire edge chain.

### 2. `_legacy_strength_from_adjudication` is present and is the live third path

It maps design first, then `causal_credibility` strong/moderate to `observational`, weak to
`theoretical`, at `graph_builder.py:432-434`. B-1 no longer uses its output as the curated claim's
vocabulary on new writes, but both edge emissions still use it.

The exact 342-row credibility fallback split is:

| Adjudicated design | Credibility | Emitted class | Rows |
| --- | --- | --- | ---: |
| `unclear` | `moderate` | `observational` | 163 |
| `unclear` | `strong` | `observational` | 24 |
| `theoretical` | `moderate` | `observational` | 127 |
| `theoretical` | `strong` | `observational` | 4 |
| `review` | `moderate` | `observational` | 24 |
| **Total** | | | **342** |

That lineage reaches 342/7,868 historical curated claims, 342/7,868 evidence rows,
341/7,607 exact edges, 341/15,945 family edges, 9/723 contested rows, and 341/7,607 transport
rows. These are full-table intersections, not extrapolations. No counterfactual rebuild or exact
status/score delta is claimed. A theoretical design plus moderate credibility becoming
observational is the measured same-class divergent witness.

### Recommendation and Phase-1 stop

**Recommend widening the edge-row remit to the live edge-vocabulary projection and its absence
consumers, explicitly including both coarsening paths and the credibility fallback.** A repair
confined to the dead free-key branch cannot honestly be described as repairing the published
cohort or the general “claim with no established design” property. The consumer map also shows
why merely substituting `unknown` or a new string is not enough.

This is materially wider than the named free-key mechanism. Under the explicit Phase-1 stop
rule, Phase 2 and Phase 3 are **not entered**. This recommendation is not a design approval or
permission to change the additional paths. The architect must rule on that scope first.

The publication-gate row has no technical blocker and is independently executable. It is not
being declared blocked by the edge row. The present stop is the requested global Phase-1 scope
checkpoint, not a claim that one row's dependency makes the other unexecutable.

Nothing here requests the out-of-scope vocabulary split, reclassification of 69,798 placeholders,
snapshot production, or adjudication/champion/receipt authority work. The historical snapshot
remains recorded history; no decision to repair or re-derive it has been made in Phase 1.

## Transcriber-ready prose — neither row closes in Phase 1

### `academic-graph-manufactures-design-from-a-placeholder`

> **TASK B-2 PHASE-1 2026-09-04 — basis corrected; remains `open`.** The free-key coercion is
> callable but its two published-loop call sites are unreachable `else` branches: the loop
> requires an adjudication, then always uses `_legacy_strength_from_adjudication`. Read-only
> replay of snapshot `sha256:583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`
> finds zero fallback-eligible rows among all 7,868 published evidence rows; all join to
> adjudications and populated raw hints. All 4,122 `quasi_natural` values match adjudicated
> IV/DiD/RDD/synthetic-control projections, not the free-key branch. The 254 `observational`
> rows carry the nonempty hint `unclear`, not an absent column. The live same-class defect is
> the adjudication projection: 342 evidence rows/341 exact edges derive `observational` from
> credibility despite unclear/theoretical/review designs; those lineages reach family,
> contested and transport rows. The hint coarsening also overrides explicit evidence class
> in 162 of the 200 current-enum input pairs. Phase 1 recommends an explicitly widened
> edge-projection/declared-absence remit; no repair or closure is claimed before the architect's
> ruling. The original negative closure signal remains unmet.

### `span-grounded-writer-ignores-the-publication-gate`

> **TASK B-2 PHASE-1 2026-09-04 — bypass confirmed; remains `open` and independently executable.**
> The sole non-test caller passes extractor output without filtering, while the extractor
> explicitly sets `publish_to_graph=False`. A synthetic in-memory call through the actual
> vocabulary preflight, span validator and writer ingests one edge/evidence/span row with
> `False`, exactly as with `True`. The April snapshot has no span-grounded table, so the defect
> has zero current materialized footprint and remains fully live in code. Severity is refined:
> `candidate_layer='design_tier_authority'` is an inert misleading label carried in prior and
> credal metadata, not a consumed authority predicate; the different `authority_tier` field must
> not be conflated with it. Hint-to-`design_family` projection remains misleading. No publication
> check or candidate projection repair has been implemented; all closure conjuncts remain open.

## Reproduction commands and observations

All commands below ran from the worktree product root. Read-only code inspection used the cited
line ranges with `nl -ba ... | sed -n 'start,endp'`; no planner file was changed.

### A. Binding and complete census

```sh
rg -n -C 12 'academic-graph-manufactures-design-from-a-placeholder|span-grounded-writer-ignores-the-publication-gate' docs/plans/active/DEBT-REGISTER.md
git status -sb
git symbolic-ref -q HEAD
git rev-parse HEAD
git merge-base HEAD main
git merge-base --is-ancestor 155810bcc HEAD
shasum -a 256 production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb
git grep -l -e 'ac_skg_edges' -e 'ac_skg_edge_evidence' HEAD -- 'src/**' 'tools/**' 'apps/**' 'packages/**'
git grep -n -e 'design_tier_authority' -e 'candidate_layer' HEAD -- 'src/**' 'tools/**' 'apps/**' 'packages/**'
git ls-files src tools apps packages | awk 'BEGIN {n=0; py=0; ts=0; tsx=0; sql=0} {n++; if ($0 ~ /\.py$/) py++; if ($0 ~ /\.ts$/) ts++; if ($0 ~ /\.tsx$/) tsx++; if ($0 ~ /\.sql$/) sql++} END {print "tracked_src_tools_apps_packages",n,"python",py,"typescript",ts,"tsx",tsx,"sql",sql}'
rg -n 'query_edge_support\(|query_prior_for_variables\(|query_causal_edges\(' src tools --glob '*.py'
rg -n 'PriorKnowledgeBundle|PriorKnowledgeSupport|support_rows' src/polisyos/scientist --glob '*.py'
git grep -n -e 'design_tier_l2' -e 'assert_l2_claim_authority_span_grounded' HEAD -- 'src/**' 'tools/**' 'tests/**'
```

Exact AST call census:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python - <<'PY'
import ast
import subprocess
from pathlib import Path
names={'_infer_edge_strength','_legacy_strength_from_adjudication','ingest_openalex_span_grounded_claims'}
paths=[p for p in subprocess.check_output(['git','ls-files','-z','--','src','tools','tests']).decode().split('\0') if p.endswith('.py')]
errors=[]; found={name:[] for name in names}
for name in paths:
    try: tree=ast.parse(Path(name).read_text(encoding='utf-8'), filename=name)
    except (SyntaxError,UnicodeError) as exc: errors.append((name,str(exc))); continue
    aliases={a.asname or a.name:a.name for node in ast.walk(tree) if isinstance(node,ast.ImportFrom) for a in node.names if a.name in names}
    for node in ast.walk(tree):
        if isinstance(node,ast.Call):
            target=aliases.get(node.func.id,node.func.id) if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else ''
            if target in names: found[target].append(f'{name}:{node.lineno}')
print('python_denominator',len(paths),'parse_errors',errors)
for name in sorted(found): print(name, 'calls',len(found[name]), found[name])
PY
```

Output: `python_denominator 5549 parse_errors []`; `_infer_edge_strength` 2 calls and
`_legacy_strength_from_adjudication` 2 calls at B2-F01's locations; span ingest 5 calls at
the four test locations `test_extraction_strength_vocabulary.py:1083,1110`,
`test_openalex_skg_ingest.py:74,172`, and the tool location `:342`.

### B. Read-only provenance queries

The query driver was the primary checkout's `.venv/bin/python`, opening exactly the snapshot
path above with `duckdb.connect(path, read_only=True)`. These are the executed query bodies;
all results are stated in B2-F02/B2-F06. No schema-ensure helper was called on the snapshot.

```sql
SELECT
 (SELECT count(*) FROM ac_causal_claims_raw) raw,
 (SELECT count(*) FROM ac_causal_claims) curated,
 (SELECT count(*) FROM ac_claim_adjudications) adjudications,
 (SELECT count(*) FROM ac_skg_edges) edges,
 (SELECT count(*) FROM ac_skg_edge_evidence) evidence,
 (SELECT count(*) FROM information_schema.tables
  WHERE table_name='ac_skg_span_grounded_claims') span_table_count;

SELECT evidence_strength,count(*) FROM ac_skg_edge_evidence
GROUP BY 1 ORDER BY 2 DESC,1;
SELECT candidate_layer,count(*) FROM ac_skg_edges GROUP BY 1 ORDER BY 2 DESC,1;

SELECT count(*) total, count(r.id) raw_joined, count(a.claim_id) adjudication_joined,
 count(*) FILTER (WHERE NULLIF(TRIM(r.design_family_hint),'') IS NULL) blank_raw_hint,
 count(*) FILTER (WHERE NULLIF(TRIM(r.design_family_hint),'') IS NOT NULL) populated_raw_hint,
 count(*) FILTER (WHERE NULLIF(TRIM(r.design_family_hint),'') IS NULL
   AND LOWER(TRIM(r.strength)) IN ('strong','very_strong','moderate','weak')) free_key_fallback_eligible
FROM ac_skg_edge_evidence e
LEFT JOIN ac_causal_claims_raw r ON r.id=e.claim_id
LEFT JOIN ac_claim_adjudications a ON a.claim_id=e.claim_id;

SELECT count(*) total_quasi,
 count(*) FILTER (WHERE NULLIF(TRIM(r.design_family_hint),'') IS NULL
   AND LOWER(TRIM(r.strength)) IN ('strong','very_strong','moderate','weak')) free_key_fallback_eligible,
 count(*) FILTER (WHERE NULLIF(TRIM(r.design_family_hint),'') IS NOT NULL) populated_raw_hint,
 count(*) FILTER (WHERE LOWER(TRIM(a.design_family)) IN ('iv','did','rdd','synthetic_control')) adjudication_design_maps_quasi,
 count(*) FILTER (WHERE LOWER(TRIM(r.design_family_hint)) IN ('iv','did','rdd','synthetic_control')) raw_hint_maps_quasi,
 count(*) FILTER (WHERE LOWER(TRIM(r.design_family_hint)) = LOWER(TRIM(a.design_family))) raw_hint_equals_adjudicated_design
FROM ac_skg_edge_evidence e
JOIN ac_causal_claims_raw r ON r.id=e.claim_id
JOIN ac_claim_adjudications a ON a.claim_id=e.claim_id
WHERE e.evidence_strength='quasi_natural';

SELECT a.design_family,count(*)
FROM ac_skg_edge_evidence e JOIN ac_claim_adjudications a ON a.claim_id=e.claim_id
WHERE e.evidence_strength='quasi_natural' GROUP BY 1 ORDER BY 2 DESC,1;

SELECT a.design_family,a.causal_credibility,e.evidence_strength,count(*)
FROM ac_skg_edge_evidence e JOIN ac_claim_adjudications a ON a.claim_id=e.claim_id
GROUP BY 1,2,3 ORDER BY 4 DESC,1,2,3;

SELECT count(*) FROM ac_skg_edge_evidence e
JOIN ac_claim_adjudications a ON a.claim_id=e.claim_id
WHERE e.evidence_strength <> CASE
 WHEN LOWER(TRIM(a.design_family))='rct' THEN 'rct'
 WHEN LOWER(TRIM(a.design_family)) IN ('iv','did','rdd','synthetic_control') THEN 'quasi_natural'
 WHEN LOWER(TRIM(a.design_family)) IN ('event_study','quasi_experimental_other','quasi_experimental_did','quasi_experimental_rdd') THEN 'quasi_natural_event'
 WHEN LOWER(TRIM(a.design_family))='meta_analysis' THEN 'meta_analysis'
 WHEN LOWER(TRIM(a.design_family)) IN ('panel_fe','system_gmm','gmm') THEN 'panel_fe'
 WHEN LOWER(TRIM(a.design_family)) IN ('structural_model','time_series_cointegration') THEN 'structural'
 WHEN LOWER(TRIM(a.design_family))='ols' THEN 'observational'
 WHEN LOWER(TRIM(a.design_family))='ols_cross_sectional' THEN 'cross_sectional'
 WHEN LOWER(TRIM(a.causal_credibility))='weak' THEN 'theoretical'
 WHEN LOWER(TRIM(a.causal_credibility)) IN ('strong','moderate') THEN 'observational'
 ELSE 'unknown' END;

SELECT design_family,count(*) FROM ac_skg_edge_evidence
WHERE evidence_strength='observational' GROUP BY 1 ORDER BY 2 DESC,1;

SELECT count(*) FROM ac_skg_edge_evidence e
JOIN ac_claim_adjudications a ON e.claim_id=a.claim_id
WHERE lower(trim(e.design_family))<>lower(trim(a.design_family));
SELECT count(*) FROM ac_skg_edge_evidence e
JOIN ac_causal_claims_raw r ON e.claim_id=r.id
WHERE e.design_family IS DISTINCT FROM r.design_family_hint;
SELECT count(*) FROM ac_skg_edge_evidence e
JOIN ac_causal_claims_raw r ON e.claim_id=r.id
WHERE e.evidence_strength IS DISTINCT FROM r.strength;

SELECT count(*),count(a.claim_id),count(e.claim_id)
FROM ac_causal_claims_raw r
LEFT JOIN ac_claim_adjudications a ON a.claim_id=r.id
LEFT JOIN ac_skg_edge_evidence e ON e.claim_id=r.id
WHERE NULLIF(TRIM(r.design_family_hint),'') IS NULL
  AND LOWER(TRIM(r.strength))='moderate';
```

The 342-lineage intersection used this executed selection:

```sql
SELECT e.claim_id,e.edge_id,a.design_family,a.causal_credibility,e.evidence_strength
FROM ac_skg_edge_evidence e JOIN ac_claim_adjudications a ON a.claim_id=e.claim_id
WHERE LOWER(TRIM(a.design_family)) NOT IN
 ('rct','iv','did','rdd','synthetic_control','event_study','quasi_experimental_other',
  'quasi_experimental_did','quasi_experimental_rdd','meta_analysis','panel_fe',
  'system_gmm','gmm','structural_model','time_series_cointegration','ols','ols_cross_sectional')
 AND LOWER(TRIM(a.causal_credibility)) IN ('strong','moderate','weak');
```

The Python driver made `claims={r[0] for r in affected}` and `edges={r[1] for r in affected}`,
then read the **complete** `id`/`claim_id`/`edge_id` column of each named table and counted set
membership. For family/contested it read the complete `claim_refs` column and counted
`bool(set(json.loads(row[0] or '[]')) & claims)`. The six full denominators and intersections
are stated in B2-F06.

### C. Actual-function coarsening, absence, and publication diagnostics

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python - <<'PY'
from hashlib import sha256
from types import SimpleNamespace
import duckdb
from polisyos.data_forge.domains.academic.batch.graph_builder import _infer_edge_strength, _legacy_strength_from_adjudication
from polisyos.data_forge.domains.academic.knowledge.skg_store import ArticleEvidence, aggregate_edge_confidence, ingest_openalex_span_grounded_claims, normalize_strength
from polisyos.ir.analytics.literature import CausalClaim, CausalDirection, DesignFamily, EvidenceSpan, EvidenceStrength, OpenAlexWorkText
from polisyos.scholar.search.models import SearchQueryTrace

print('enum_sets', len(DesignFamily), len(EvidenceStrength), sorted({v.value for v in DesignFamily} & {v.value for v in EvidenceStrength}))
overrides = [(d.value, e.value, _infer_edge_strength({'design_family_hint': d.value, 'evidence_strength': e.value})) for d in DesignFamily for e in EvidenceStrength if _infer_edge_strength({'design_family_hint': d.value, 'evidence_strength': e.value}) != e.value]
print('coarsening_matrix', 'input_pairs', len(DesignFamily)*len(EvidenceStrength), 'explicit_evidence_overrides', len(overrides), 'designs_overriding_explicit_evidence', len({r[0] for r in overrides}))
print('coarsening_divergence', _infer_edge_strength({'design_family_hint': 'iv', 'evidence_strength': 'observational'}))
print('placeholder_results', {s: _infer_edge_strength({'strength': s}) for s in ('strong','very_strong','moderate','weak','')})
print('legacy_divergence', _legacy_strength_from_adjudication({'design_family':'theoretical','causal_credibility':'moderate'}))
print('absence_current_behavior', {str(s): (normalize_strength(s), aggregate_edge_confidence([ArticleEvidence(strength=s, extraction_confidence=1.0)])) for s in ('unknown','not_established','')})

class SupportClient:
    async def generate(self, *, messages, tools, temperature=None, seed=None):
        return SimpleNamespace(content='', tool_calls=[SimpleNamespace(id='diagnostic', name='layer3_gy_record_span_support_judgment', arguments={'decision':'entails','confidence':0.91,'rationale':'synthetic diagnostic witness'})], usage=SimpleNamespace(total_tokens=5), raw={'deterministic_replay_key':'synthetic-only'})
class Canonizer:
    def canonize(self, value):
        return value.lower(), False
text = 'Tax credits increase business investment.'
digest = sha256(text.encode()).hexdigest()
work = OpenAlexWorkText(openalex_id='https://openalex.org/W-SYNTHETIC-B2', title='Synthetic B2 witness', source_text=text, abstract_text=text, content_sha256=digest)
span = EvidenceSpan(span_id='synthetic-span', text=text, source_ref=work.openalex_id, start_char=0, end_char=len(text), content_sha256=digest)
claim = CausalClaim(claim_id='synthetic-claim', cause_variable='tax credits', effect_variable='business investment', direction=CausalDirection.POSITIVE, claim_text=text, design_family_hint=DesignFamily.IV, evidence_strength=EvidenceStrength.OBSERVATIONAL, supporting_spans=[span], supporting_span_ids=[span.span_id], claim_extraction_confidence=0.91, publish_to_graph=False)
for publish in (False, True):
    with duckdb.connect(':memory:') as con:
        report = ingest_openalex_span_grounded_claims(con, work=work, claims=[claim.model_copy(update={'publish_to_graph':publish})], query_trace=SearchQueryTrace(query_node_id='synthetic-q', query='tax credits investment', perspective='root', provider='openalex', hit_count=1), span_support_client=SupportClient(), variable_canonizer=Canonizer())
        print('gate_witness', publish, 'ingested', report.ingested_claim_count, 'rejected', report.rejected_claim_count, 'report_tier',report.authority_tier, 'edge_rows',con.execute('SELECT evidence_strength,candidate_layer FROM ac_skg_edges').fetchall(), 'evidence_rows',con.execute('SELECT evidence_strength,design_family FROM ac_skg_edge_evidence').fetchall(), 'span_rows',con.execute('SELECT authority_tier FROM ac_skg_span_grounded_claims').fetchall())
PY
```

Observed output (exit 0):

```text
enum_sets 20 10 ['meta_analysis', 'panel_fe', 'rct', 'theoretical']
coarsening_matrix input_pairs 200 explicit_evidence_overrides 162 designs_overriding_explicit_evidence 18
coarsening_divergence quasi_natural
placeholder_results {'strong': 'quasi_natural', 'very_strong': 'quasi_natural', 'moderate': 'observational', 'weak': 'theoretical', '': 'unknown'}
legacy_divergence observational
absence_current_behavior {'unknown': ('unknown', 0.08925000000000005), 'not_established': ('unknown', 0.1), '': ('unknown', 0.1)}
gate_witness False ingested 1 rejected 0 report_tier design_tier_l2 edge_rows [('observational', 'design_tier_authority')] evidence_rows [('observational', 'iv')] span_rows [('design_tier_l2',)]
gate_witness True ingested 1 rejected 0 report_tier design_tier_l2 edge_rows [('observational', 'design_tier_authority')] evidence_rows [('observational', 'iv')] span_rows [('design_tier_l2',)]
```

These are Phase-1 diagnostic witnesses, not Phase-3 red/green tests. No test suite, directory-wide
or otherwise, has been used to claim implementation closure. Phase-2 design and Phase-3
red/green evidence are deliberately pending the scope ruling.

## Event 2 — independent reconciliation and appended corrections, 2026-09-04

The three read-only investigations completed. Their consumer, gate, and population results
agree with the root's measurements. The root independently reran the additional witnesses
below before accepting them. This event supersedes the explicitly identified statements in
Event 1; earlier journal text is preserved under the append-only rule.

### B2-F02 correction — retained spans exist; their adequacy is not established

**Supersedes B2-F02's sentence “The slim snapshot has neither the source evidence nor a
receipt that establishes the truth of a study design.”** The first half was too broad.
The absence of `ac_skg_span_grounded_claims` does not mean absence of retained source spans.

Walking all 310,829 `ac_article_extractions` payloads finds 310,829 valid JSON documents,
containing 137,714 causal-claim objects. Of those objects, 67,791 have all three fields
`design_family_hint`, `method_spans`, and `supporting_spans`. Joining the complete published
population by claim ID gives exactly 7,868 distinct claim IDs and 7,868 payload matches:

| Retained field / reconciliation | Published rows |
| --- | ---: |
| Populated payload design hint | 7,868 / 7,868 |
| Explicit payload `evidence_strength` field | 0 / 7,868 |
| Nonempty `method_spans` array | 5,192 / 7,868 |
| Nonempty `method_span_ids` array | 5,192 / 7,868 |
| Nonempty `supporting_spans` array | 7,868 / 7,868 |
| Nonempty `supporting_span_ids` array | 7,868 / 7,868 |
| Payload/raw work-ID, hint, or strength disagreements | 0 in each of the three comparisons |

These are **availability counts**, not semantic validation or a claim that every span ID
content-binds. No grounding/reclassification run was performed. The bounded finding is that
the projection consumes classification strings, not their method spans or an independently
established evidence-strength axis. Neither the truth of every design hint nor its falsity
has been established here. The 342-row live fallback finding and the zero placeholder
contribution remain unchanged.

`meta/source_lineage.json` records both graph tables, raw/curated claims, adjudications, and
article extractions as sourced from `original`, whose snapshot identifier is
`policyos_fullprod_1000t_20260324`. The lineage artifact's `generated_at` is
`2026-04-11T15:56:21.417044+00:00`. The identifier is not independently verified as a row
creation/copy timestamp. No per-row branch receipt or generating commit was found; B2-F02's
branch attribution is a **recomputed reconstruction**, not a logged execution proof.

Root reproduction (same read-only connection and interpreter as Event 1):

```sql
SELECT count(*) total,
 count(*) FILTER (WHERE json_valid(extraction_json)) valid_payloads
FROM ac_article_extractions;

SELECT count(*) total,
 count(*) FILTER (
  WHERE json_extract(c.value,'$.design_family_hint') IS NOT NULL
    AND json_extract(c.value,'$.method_spans') IS NOT NULL
    AND json_extract(c.value,'$.supporting_spans') IS NOT NULL) enriched
FROM ac_article_extractions a,json_each(a.extraction_json,'$.causal_claims') c;

WITH payload_claims AS (
 SELECT a.work_id,json_extract_string(c.value,'$.claim_id') claim_id,c.value
 FROM ac_article_extractions a,json_each(a.extraction_json,'$.causal_claims') c
),published AS (
 SELECT e.claim_id,r.work_id,r.design_family_hint,r.strength,
        p.work_id payload_work_id,p.value
 FROM ac_skg_edge_evidence e
 LEFT JOIN ac_causal_claims_raw r ON r.id=e.claim_id
 LEFT JOIN payload_claims p ON p.claim_id=e.claim_id
)
SELECT count(*) evidence_rows,count(value) payload_matches,
 count(DISTINCT claim_id) distinct_claim_ids,
 count(*) FILTER (WHERE json_extract_string(value,'$.design_family_hint') IS NOT NULL) hint_present,
 count(*) FILTER (WHERE json_extract(value,'$.evidence_strength') IS NOT NULL) evidence_strength_present,
 count(*) FILTER (WHERE json_array_length(value,'$.method_spans')>0) method_spans_nonempty,
 count(*) FILTER (WHERE json_array_length(value,'$.method_span_ids')>0) method_ids_nonempty,
 count(*) FILTER (WHERE json_array_length(value,'$.supporting_spans')>0) supporting_spans_nonempty,
 count(*) FILTER (WHERE json_array_length(value,'$.supporting_span_ids')>0) supporting_ids_nonempty,
 count(*) FILTER (WHERE work_id IS DISTINCT FROM payload_work_id) work_mismatches,
 count(*) FILTER (WHERE json_extract_string(value,'$.design_family_hint') IS DISTINCT FROM design_family_hint) hint_mismatches,
 count(*) FILTER (WHERE json_extract_string(value,'$.strength') IS DISTINCT FROM strength) strength_mismatches
FROM published;
```

Outputs: `(310829,310829)`; `(137714,67791)`;
`(7868,7868,7868,7868,0,5192,5192,7868,7868,0,0,0)`.
Two preliminary diagnostic queries failed read-only: `valid` was a reserved alias, and
`ac_skg_edge_evidence` has no `work_id` column. The successful query above uses the raw claim's
work ID; neither failed attempt changed data.

```sh
sed -n '1,160p' production_data/policyos_academic_runtime_slim_20260411T112032Z/meta/source_lineage.json
```

### B2-F03 additions — remaining API terminals

- `scientist/cross_graph/gatherers/academic.py:187-249` receives the Foundry literature prior.
  It copies the strength into metadata; confidence and article count determine usable support
  and `MIXED`/`INSUFFICIENT`, not the label. Missing label alone does not change that decision.
- `SKGQuery.resolve_grounded_causal_prior` at `skg_query.py:2322-2415` consumes edge support
  through content match, confidence, scope/version and transport. It ignores the strength
  label when computing relevance; removing a row or changing numeric confidence can matter.
- `scientist/methods/search/judge_stack.py:317-321` exposes the complete
  `PriorKnowledgeBundle` as JSON in judge state. Thus “opaque label” describes the typed code
  path, not a guarantee that a later model cannot interpret the wording. No model-judgment
  counterfactual was run; that effect is `not_established`.
- `knowledge/search.py:225-246` exposes exact curated claims directly and non-exact graph
  summaries through the V2 query path. `scientist/agent/knowledge_tools.py:169-185` forwards
  that result without an extra design interpretation. `scientist/cross_graph/feedback.py:175-188`
  uses the returned row count, not evidence strength, for its support witness. V2 absence
  remains as described in B2-F03; label-only absence does not remove a returned row.
- The complete 4,781-file tracked application/tool census finds `design_family_histogram`
  only in `edge_synthesize.py` (four writer/construction occurrences) and `skg_store.py`
  (one DDL occurrence). There is no named-field downstream reader in that denominator.

Commands: `sed -n` over the exact ranges above;
`git grep -n 'design_family_histogram' HEAD -- 'src/**' 'tools/**' 'apps/**' 'packages/**'`;
`rg -n 'find_causal_evidence' src/polisyos/data_forge/domains/academic src/polisyos/scientist --glob '*.py'`.

### B2-F04 refinement — opaque for authority, not byte-inert

**Supersedes “inert” in the first span-row transcription wherever it implies no observable
effect.** The label does not choose authority or credal status, but provenance is hashed.
`credal_reference.py:287-301` includes the label-bearing provenance in edge content hashes;
`:438-459` includes edge hashes in the reference epoch/hash; `:483-523` binds certificates
and detects staleness on changed hashes. Therefore changing the label can stale a bound
certificate even while leaving edge status/completions identical. The staleness helper's
non-test external caller in the inspected source/tool tree is a contract-validation tool,
not a production source caller. This is content identity, not design authority bestowed by
the string. No runtime-quality source change is proposed or performed in Phase 1.

Root pure-function witness: four layers × five conditions = 20 derived edges. Holding the
other inputs fixed, all four layers give the same status and completions in each condition,
but four distinct content hashes:

| Condition | Status for all four layer strings | Identical completions | Distinct hashes |
| --- | --- | --- | ---: |
| confidence 0.2 | incomplete | yes | 4 |
| confidence 0.5 | contested | yes | 4 |
| confidence 0.9 | confirmed | yes | 4 |
| confidence 0.9 with publication blocker | contested | yes | 4 |
| confidence 0.9 with unapproved endpoint | incomplete | yes | 4 |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python - <<'PY'
import json
from polisyos.runtime.quality.credal_reference import _derive_l2_causal_edge
from polisyos.runtime.quality.candidate_firewall import l2_claim_authority_grounding_issues_for_payload
layers=('candidate','design_tier_authority','arbitrary','')
scenarios=(('low',.2,{},True),('mid',.5,{},True),('high',.9,{},True),('blocked',.9,{'publish_blockers':['diagnostic']},True),('unapproved',.9,{},False))
for name,confidence,quality,approved in scenarios:
    results=[_derive_l2_causal_edge(('synthetic-edge','X','Y','positive',2,'observational',confidence,layer,json.dumps(quality)),version='synthetic',variable_names={'X','Y'},approved_variables={'X','Y'} if approved else {'X'},contested_edges={}) for layer in layers]
    print('layer_counterfactual',name,'statuses',[r.status for r in results],'same_completions',all(r.admissible_completions==results[0].admissible_completions for r in results),'distinct_hashes',len({r.content_hash for r in results}))
for field,value in [('candidate_layer','design_tier_authority'),('authority_tier','design_tier_l2')]:
    issues=l2_claim_authority_grounding_issues_for_payload({'claim_authority':{field:value}},surface='synthetic-diagnostic')
    print('firewall_field',field,'issues',[i['code'] for i in issues])
PY
```

Exit 0. The `candidate_layer` payload yields `[]`; the different `authority_tier` payload
yields `['l2_claim_authority_grounding_unresolved']`. This does not validate the latter's
authority producer; it distinguishes two different fields and preserves the out-of-scope
authority-chain boundary. These remain diagnostic witnesses, not implementation tests.

### Final transcriber-ready prose — supersedes Event 1's two draft transcriptions

#### `academic-graph-manufactures-design-from-a-placeholder`

> **TASK B-2 PHASE-1 2026-09-04 — basis corrected; remains `open`.** The free-key coercion is
> callable but both published-loop call sites are unreachable alternatives: an adjudication is
> required first, and `_legacy_strength_from_adjudication` supplies the emitted class. Full
> read-only reconciliation of snapshot `sha256:583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`
> finds 0 fallback-eligible rows among all 7,868 published evidence rows; all join adjudications
> and populated hints. The 4,122 `quasi_natural` values exactly match adjudicated
> IV/DiD/RDD/synthetic-control projections. The 254 `observational` rows carry `unclear`, not
> blank design hints. Current-helper replay matches all 7,868 rows: 7,526 design mappings and
> 342 credibility fallbacks, the latter reaching 341 exact edges and family/contested/transport
> memberships. This is reconstructed lineage, not a historical branch receipt. Retained method
> spans exist for 5,192 published claims and supporting spans for all 7,868; their adequacy and
> an independent evidence-strength basis are not established by this census. The helper's hint
> coarsening overrides explicit evidence strength in 162/200 current-enum pairs. Phase 1
> recommends widening the edge repair to both coarsening paths, the live credibility fallback,
> and declared-absence consumers; the architect's scope ruling is pending. No source/data
> repair or negative closure test has been delivered. The original closure contract stands.

#### `span-grounded-writer-ignores-the-publication-gate`

> **TASK B-2 PHASE-1 2026-09-04 — bypass confirmed; remains `open` and independently executable.**
> The sole non-test caller passes extractor output unfiltered; the extractor sets
> `publish_to_graph=False`. Actual preflight/span-validation/writer execution against a
> synthetic in-memory database writes an edge, evidence row and span row with `False`, just
> as with `True`. The pinned April snapshot has no span-grounded table and no
> `design_tier_authority` exact-edge layers: zero current snapshot footprint, fully live code
> defect. `candidate_layer='design_tier_authority'` is an opaque misleading provenance label,
> not an authority predicate: layer-only changes preserve credal status/completions while
> changing content hashes. The separate `authority_tier` field must not be conflated with it.
> Hint-to-`design_family` projection remains misleading. Phase 1's global scope checkpoint is
> observed; this row has no technical blocker of its own. No gate or projection repair is
> implemented, and none of its closure conjuncts is claimed complete.

### Scope disposition after reconciliation

B2-F06's recommendation and Phase-1 stop stand. The basis is the recomputed live writer
branch, the full snapshot replay, and actual consumer absence arithmetic, not the original
row's incorrect inference from a plurality. These are same-class projections under P31/P40.
No decision about migrating/re-deriving history, no Phase-2 design, and no Phase-3 code is
substituted for the architect's ruling. The failure/repair register was reread before closeout.

## Event 3 — review corrections to the consumer map, 2026-09-04

A fresh, read-only reviewer independently reproduced the core population, branch-replay,
coarsening, and snapshot-footprint findings. Two map details were verified by the root and
are appended here. Both are **existing-class consumer-map omissions**, not a new defect
class or permission to implement a wider repair.

1. **B2-F03 correction: the prior path is not opaque at every step.**
   `SKGQuery.query_prior_for_variables` at `:2576-2580` ranks the strength labels when it
   merges matching hybrid rows. `_strongest_strength` at `:1644-1659` uses
   `EVIDENCE_WEIGHTS`; absent/blank inputs are omitted, two absent inputs return `None`,
   and an unrecognized nonempty string receives the `unknown` weight. Its SQL readers
   stringify NULL as `"None"` before this merge, so that case is not a declared absence.
   The merge computes confidence separately as the maximum input confidence and orders
   rows by confidence. Thus loss of one class can change the retained label without
   changing confidence/coverage; downstream PriorMiner and the stored support contract
   still carry it opaquely. Event 1's prior-path row is superseded only to the extent that
   it described this entire path as opaque. The separate `query_edge_support` hybrid
   ranking was already recorded in the original map.
2. **B2-F03 addition: contested-edge outer-set terminal.**
   `SKGQuery.contested_edge_value_outer_set` at `:2223-2320` SELECTs contested strength
   as `row[7]` but does not read that value. It binds claim references, resolves numeric
   estimates, constructs a signed interval, and maps confidence through
   `_data_trust_from_score` (`:1450-1459`) to a bounded trust cap/multiplier with
   `promotion_floor=0.2`. The returned outer set is explicitly `search_only` and
   `proxy_identified`, with declared assumptions. Label-only absence does not alter the
   result; rank-derived confidence can affect its numeric trust. Missing claims/estimates
   raise instead of silently supplying a value. Its sole source/tool caller found by the
   named-call search is `check_layer3_gy_knowledge_substrate_contract.py:176-209`, which
   records interval bounds, proxy status, and resolved claim/estimate counts. No repair to
   that separate authority/promotion machinery is implied.

Root verification commands (read-only):

```sh
sed -n '2490,2775p' src/polisyos/data_forge/domains/academic/knowledge/skg_query.py
sed -n '1638,1664p' src/polisyos/data_forge/domains/academic/knowledge/skg_query.py
sed -n '2215,2322p' src/polisyos/data_forge/domains/academic/knowledge/skg_query.py
rg -n -A 38 'def _data_trust_from_score' src/polisyos/data_forge/domains/academic/knowledge/skg_query.py
rg -n 'contested_edge_value_outer_set' src tools --glob '*.py'
sed -n '140,209p' tools/quality/validation/check_layer3_gy_knowledge_substrate_contract.py
```

These additions do not change Event 2's final transcription prose or B2-F06's scope stop.

The review's final verdict is **GO for the Phase-1 commit**, with no critical or important
findings. A final precision correction to the original prior row: `unknown` is the fallback
for missing **evidence strength**, not every prior field. Root readback of
`prior_miner.py:134-160` confirms missing `candidate_layer` defaults to the configured
`support_mode`. This qualification and the two map additions above fully dispose of the
review's minor findings; no source change or additional authority-chain work follows.

## Event 4 — Phase-1 verification receipt, 2026-09-04

### Bound debt checker — exactly one invocation

```sh
/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python tools/quality/validation/check_debt_ledger.py --check > .tmp_b2_check.fMs01p/bound-debt-check.txt 2>&1
```

**Exit 0**, measured wall time **585.64 seconds** (`user 557.19`, `sys 26.82`).
No blocking findings. Output was redirected for the whole run, not reconstructed afterward.
The 59-line log is retained at
`/Users/deniskopylov/polisyos/.worktrees/debt-b2-manufactured-design/policy-engine/.tmp_b2_check.fMs01p/bound-debt-check.txt`,
in a `git check-ignore`-confirmed scratch directory. Log SHA-256:
`e3fec61aed497fa4b535ec6af5e9c02eb4afdd391554a96a8efc003b5232051b`.

Selected exact metrics:

```text
register_ids=189
gy_ids=38
atlas_debt_rows=22
frontend_disposition_entries=261
frontend_ds8_assignment_rows=217
explicit_nonclosure_entries=29
explicit_nonclosure_identified=18
explicit_nonclosure_typed_not_a_debt=11
explicit_nonclosure_resolved_history=8
explicit_nonclosure_unidentified=0
closure_signal_pytest_selections=44
closure_signal_unsupported_runners=1
closure_signal_identities_without_commands=4
closure_signal_identity_unresolvable=9
closure_signal_input_unresolvable=0
closure_signal_selects_nothing=0
closure_signal_collection_failed=0
closure_signal_collection_host_unknown=0
closure_signal_ast_collection_disagreements=0
closure_signal_count_exit_disagreements=9
```

The log retains informational unresolved identities/count-exit disagreements, an unsupported
Vitest selector, and register/source-standing notes. They are not silently called successful
test executions. This checker reconciles the ledger and collects its named selections; it
does not provide B-2 red/green implementation evidence. No directory-wide test run, backend
verify, producer invocation, or second debt-checker invocation was performed.

### Custody and changed-path verification

After the checker completed, the root again ran:

```sh
shasum -a 256 production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb
git status -sb
git diff --name-only
git diff -- docs/plans/active/
git diff --no-index --check /dev/null docs/superpowers/journals/2026-09-04-manufactured-design-and-publication-gate.md
```

The final snapshot SHA-256 is unchanged:
`583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`.
The branch remains attached to `codex/debt-b2-manufactured-design`. The only delivered change
is this append-only journal; source, tests, schemas, active plans, and the read-only snapshot
are unchanged. Whitespace checking passed. No predicates or checker inspection sets were
weakened. The Phase-1 findings were independently reviewed, but **neither debt row is closed**.

**Handoff:** Phase 1 is ready for the architect. Phase 2 design and Phase 3 red-first
implementation remain unstarted pending the explicitly widened edge-projection/absence
scope ruling. The publication-gate row is still independently executable and has no
technical blocker of its own.

## Event 5 — Phase-2 design, 2026-09-04

The architect ratified Phase 1 and ruled that the repair is **relocated, not widened**. The
live credibility fallback, both design-first coarsenings, the callable free-key fallback,
and the missing edge-absence representation are one substitution seam. This event is the
design checkpoint committed before any Phase-3 source or test change.

### D01 — one edge-evidence resolver, two compatibility entry points

An edge's evidence class comes only from the admitted `evidence_strength` axis. A present
candidate enum value is preserved exactly. An absent axis resolves to declared absence.
Neither `design_family_hint`, adjudicated `design_family`, generic `strength`, nor
`causal_credibility` is evidence for that axis.

`_infer_edge_strength` and `_legacy_strength_from_adjudication` remain separate private entry
points only so their callable contracts and negative regressions stay visible. Both delegate
to one resolver. `_infer_edge_strength` passes the explicit value/status from the claim
sidecar. The legacy adjudication object has no evidence-strength axis, so its wrapper resolves
to absence; the published loop will resolve from the admitted vocabulary sidecar rather than
from adjudication. This removes both mappings without inventing a replacement rule.

The required divergent witness is structural: a `theoretical` design plus `moderate`
credibility has no supplied evidence class and therefore resolves to absence, never
`observational`. A separately supplied evidence class remains itself regardless of any design.

### D02 — declared absence across `VARCHAR NOT NULL`

The edge tables retain their existing `VARCHAR NOT NULL` value columns. At that persistence
boundary the existing status literal `not_established` is a reserved storage encoding for an
absent evidence value. It is **not** added to `EvidenceStrength`, is ranked below no evidence
class, and must never reach a typed consumer as a class.

The status therefore replaces the missing value only in the legacy relational slot; a
parallel status column is not added. At typed boundaries the encoding is decoded to the B-1
shape: `evidence_strength=None` beside
`evidence_strength_status=ClaimVocabularyAxisStatus.NOT_ESTABLISHED`. A present enum is paired
with `CANDIDATE`. Contradictory value/status pairs and arbitrary nonempty tokens still fail.
This is the edge layer's equivalent of B-1's declared-absence vocabulary without a four-table
schema migration or historical rewrite.

### D03 — consumer disposition

The B2-F03 consumers divide into three groups:

| Consumer | Declared-absence behavior after repair |
| --- | --- |
| `skg_store.py` aggregation/ranking, `edge_synthesize.py`, `skg_versioning.py` | Preserve the storage token but exclude absent articles from strength weights, floors, replication bonuses, strongest-class choice, and directional dissent. Absence-only input has zero strength contribution. Mixed input uses established classes. Genuine `unknown` retains its measured nonzero behavior. Shared helpers carry this through synthesis/retraction, so those two callers need no independent inference rule. |
| `skg_query.py` and `knowledge/store.py` | Decode before comparison or enum construction. Exact/family/contested and prior rows expose `None` plus `not_established`; all-absent strongest selection is absent, while mixed selection chooses an established class. Existing confidence, coverage, physical-row binding, and malformed-token rejection remain intact. |
| Foundry `literature_prior.py`, IR `LiteratureEdgePrior`, `graph_reconciliation.py`, Scientist `prior_miner.py`/`PriorKnowledgeSupport` | These are the consumers that currently reject or stringify a new marker. Their typed contracts accept the explicit optional value with the companion status and never expose the storage token. Graph metadata carries both fields. Inclusion, reconciliation, readiness, and resolved-edge coverage remain confidence/row based. Omitted legacy constructor fields keep their existing `unknown` default; an explicitly decoded absence cannot collapse to that default. |

`transport_score.py`, the cross-graph compiler, search/proving-ground paths, benchmarks/QC,
`credal_reference.py`, and `capability_index_compiler.py` do not interpret the label directly.
They retain their existing row/confidence predicates. No runtime-quality source change is
needed; those are consumers already identified in Phase 1, not an authority seam to redesign.
Opaque copy/hash consumers preserve whichever recorded value they receive.

### D04 — publication gate and candidate projection

`ingest_openalex_span_grounded_claims` keeps whole-batch vocabulary re-admission before the
first schema/write operation. After that preflight, each claim must satisfy
`publish_to_graph is True` before canonization or any edge, evidence, or span row is emitted.
Span support remains an independent unchanged predicate. An unpublished candidate is counted
as rejected and may remain in the article/query/version audit intake, but it reaches none of
the three graph-publication tables. A mixed batch publishes only admitted claims, and a denied
claim targeting an existing edge cannot mutate it.

The writer will consume the admitted vocabulary sidecar rather than DTO defaults. It writes
`candidate_layer='candidate'`, not the authority-suggesting `design_tier_authority`, and writes
SQL `design_family=NULL`; the actual `design_family_hint` remains losslessly retained under its
candidate name/status in the article vocabulary envelope. The separate span
`authority_tier` field and its producer are untouched. This repair removes a misleading
projection; it does not invent design or authority.

### D05 — history and generated witnesses

The pinned 7,868-row snapshot remains recorded history. In particular, its 342 live-fallback
evidence rows carry the measured axis misstatement and are the cohort a future authorized
re-derivation must identify. This task performs no re-extraction, re-adjudication, snapshot
rewrite, or producer run.

The committed OpenAlex ingest witness was generated from extractor claims whose publication
flag is false, so a truthful recomputation would change its positive graph rows to rejections.
Under the no-data ruling it is not regenerated here, and the checker predicate is not weakened
or narrowed to hide that fact. Phase 3 uses authored in-memory positive/negative controls; the
old artifact remains historical evidence of the defect rather than evidence for the repair.

### D06 — explicit non-goal: `unknown` weight

`EvidenceStrength.UNKNOWN` keeps its current nonzero contribution. That is an unfounded-
contribution question, not the substitution repaired here. Phase 3 pins the distinction:
declared absence contributes zero, while `unknown` retains existing behavior. Exact
transcriber-ready prose for the new row will report the measurement and request a separate
scope/impact investigation without claiming closure.

### D07 — red/green acceptance plan

Targeted tests will be added before each implementation slice:

1. resolver negatives prove placeholders, design hints, and credibility cannot emit any
   design-vocabulary member; explicit evidence survives unchanged; the theoretical/moderate
   witness is absent rather than observational;
2. codec/aggregation tests prove the `NOT NULL` encoding round-trips to typed absence, contributes
   zero, composes with established classes, and does not change genuine `unknown`;
3. query/IR/Foundry/Scientist tests prove the representation survives the real rejecting and
   normalizing consumers without token leakage or changed row/coverage predicates;
4. span-ingest tests prove false/default/truthy-forged publication values cannot write graph rows,
   mixed and existing-edge cases are safe, candidate naming is honest, and the vocabulary
   preflight still precedes all database writes.

Each claim gets a recorded failing invocation before its implementation and a matching green
invocation afterward. Tests are selected by file/node only; no directory-wide suite or data
producer is permitted. After source freeze, changed-path lint/architecture checks and the
bound debt checker run; the debt checker is invoked exactly once, with all output redirected.

### Pattern and capability pass

Relevant patterns are P04 (status lattice), P05/P15 (candidate versus authority), P10
(semantic adequacy), P14 (evidence-strength truthfulness), P31 (class-level repair), P37/P38
(real publication predicate/property), and P40 (one bounded fix round per row). The pre-repair
edge-absence chain is `consumer_missing` + `semantic_test_missing`; the span gate is
`semantic_test_missing`. The target pattern is one admitted-axis resolver, one reversible
storage encoding, exhaustive typed consumption, and one publication guard before every graph
emission. Acceptance is the two registered closure signals plus the named divergent and
end-to-end negative witnesses. Authority/receipt/champion work remains explicitly out of scope.

Phase-2 read-only commands used to confirm the ratified design inputs:

```sh
git merge --ff-only main
sed -n '170,215p' src/polisyos/data_forge/domains/academic/knowledge/types.py
sed -n '300,365p' src/polisyos/data_forge/domains/academic/knowledge/types.py
sed -n '1901,1970p' src/polisyos/data_forge/domains/academic/batch/article_extractor.py
sed -n '45,90p' src/polisyos/scientist/methods/discovery/priors.py
sed -n '125,170p' src/polisyos/scientist/methods/discovery/prior_miner.py
sed -n '215,270p' src/polisyos/foundry/methods/catalog/causal/literature_prior.py
sed -n '330,365p' src/polisyos/foundry/methods/catalog/causal/graph_reconciliation.py
```

The merge was a fast-forward from `861898cf7` through the architect's ratification commits to
`fca52ea2b`; no rebase occurred. The source/test tree and `production_data` remained unchanged
through this design checkpoint.

## Event 6 — Phase-3 implementation and verification, 2026-09-04

### Delivered behavior

Commit `dec7beccb` implements the ratified seam; `9ade77cbd` is the mechanical
architecture-facade correction found by the guardrail census.

- `encode_edge_evidence_strength` is the single write-boundary resolver. It accepts an exact
  `EvidenceStrength` candidate or the paired absence, rejects contradictory/unsupported input,
  and encodes absence as `not_established` for the existing `VARCHAR NOT NULL` columns.
  `decode_edge_evidence_strength` reverses that into `None` plus
  `ClaimVocabularyAxisStatus.NOT_ESTABLISHED`.
- `_infer_edge_strength` now consults only `evidence_strength` and its status.
  `_legacy_strength_from_adjudication` can no longer project design or credibility and returns
  declared absence. The published batch loop uses the admitted vocabulary values for both the
  accumulator and evidence row, so the legacy helper is no longer its live source.
- Aggregation excludes declared absence from weights, confidence floors, replication bonus and
  directional dissent. Ranking preserves an all-absence result and selects an established class
  from mixed input. `unknown` remains a distinct enum member with its existing weight.
- Exact/family/contested query records now carry an optional value plus status. The V2 store,
  prior query, IR literature prior, Foundry build/reconciliation and Scientist prior support all
  preserve that shape; no typed consumer sees the storage token. Row/confidence/coverage and
  content-binding predicates are unchanged.
- The span writer still preflights the complete batch before its first database operation, then
  requires `claim.publish_to_graph is True` before grounding/canonization/emission. False,
  missing and forged truthy values are rejected. Published rows use `candidate_layer='candidate'`
  and NULL `design_family`; the actual hint remains in the article's admitted candidate envelope.
  The independent `authority_tier` produced by span grounding is unchanged.

No schema migration, snapshot/data write, extractor run, adjudication run, authority producer,
receipt, evaluator, or checker weakening was introduced. The pinned snapshot's 342 affected
historical evidence rows remain recorded history and are the explicit target population for a
future authorized re-derivation.

### Red evidence

All red runs used the provisioned main virtualenv with the worktree first on `PYTHONPATH`; all
output was redirected. They ran before their corresponding source changes.

1. Resolver/aggregation red — exit 1, **28 failed and one characterization passed**. The passing
   case pins the existing `unknown` contribution; the failures show four free-key placeholders,
   all 20 design-family values without evidence, the explicit-class override, the
   theoretical/moderate fallback, absence-only confidence and absence replication.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q \
  tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py::test_edge_strength_without_explicit_evidence_is_declared_absent \
  tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py::test_edge_strength_preserves_explicit_evidence_despite_divergent_design \
  tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py::test_legacy_theoretical_moderate_resolves_absence_not_observational \
  tests/unit/data_forge/domains/academic/batch/test_skg_confidence.py::test_declared_absence_contributes_zero_edge_confidence \
  tests/unit/data_forge/domains/academic/batch/test_skg_confidence.py::test_declared_absence_does_not_change_established_edge_confidence \
  tests/unit/data_forge/domains/academic/batch/test_skg_confidence.py::test_unknown_retains_its_existing_nonzero_edge_confidence \
  > .tmp/b2-red/resolver-aggregation-red.txt 2>&1
```

2. Publication/candidate projection red — exit 1, **six failed**: all four denied values were
   ingested, the layer was `design_tier_authority`, and both mixed claims were published.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q \
  tests/unit/data_forge/domains/academic/knowledge/test_openalex_skg_ingest.py::test_span_writer_publication_gate_requires_literal_true \
  tests/unit/data_forge/domains/academic/knowledge/test_openalex_skg_ingest.py::test_span_writer_persists_candidate_projection_without_design_authority \
  tests/unit/data_forge/domains/academic/knowledge/test_openalex_skg_ingest.py::test_span_writer_mixed_batch_publishes_only_allowed_claim \
  > .tmp_b2_check.fMs01p/phase3-gate-red.txt 2>&1
```

3. Consumer red — exit 1, **five failed**. The store rejected the token, Foundry tried to construct
   an enum from it, the IR rejected optional value/status, and Scientist defaulted absence to
   `unknown`.

```sh
PYTHONPATH=src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q \
  tests/unit/data_forge/domains/academic/knowledge/test_skg_query.py::test_query_claims_decodes_persisted_declared_absence \
  tests/unit/data_forge/domains/academic/knowledge/test_skg_query.py::test_query_claims_hybrid_ignores_declared_absence_when_evidence_exists \
  tests/unit/foundry/methods/catalog/causal/test_literature_prior.py::test_build_literature_prior_decodes_persisted_declared_absence \
  tests/unit/ir/test_literature_contract.py::test_literature_prior_roundtrips_declared_absence_without_value_token \
  tests/unit/scientist/discovery/test_prior_miner.py::test_prior_miner_preserves_declared_absence_without_value_token \
  > .pytest_cache/b2-red-consumers.log 2>&1
```

4. Typed edge-support status red — exit 1, **one failed** because `EdgeSupportRecord` had no status
   field. The matching green was one passed test after adding the paired status.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q \
  tests/unit/data_forge/domains/academic/knowledge/test_skg_query.py::test_query_edge_support_pairs_declared_absence_with_status \
  > .tmp_b2_check.fMs01p/phase3-edge-support-status-red.txt 2>&1
```

### Green and blast-radius evidence

The matching focused greens were **29 passed**, **six passed**, **five passed**, and **one passed**
respectively, recorded in `phase3-resolver-green.txt`, `phase3-gate-green.txt`,
`phase3-consumers-green.txt`, and `phase3-edge-support-status-green.txt` under the ignored scratch
paths above.

After source freeze, three targeted file/node waves ran in parallel and exited 0:

```sh
/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q \
  tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py \
  tests/unit/data_forge/domains/academic/batch/test_skg_confidence.py \
  tests/unit/data_forge/domains/academic/batch/test_skg_versioning.py \
  > .tmp_b2_check.fMs01p/final-targeted-batch.txt 2>&1

/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q \
  tests/unit/data_forge/domains/academic/knowledge/test_openalex_skg_ingest.py \
  tests/unit/data_forge/domains/academic/knowledge/test_skg_query.py \
  tests/unit/data_forge/domains/academic/knowledge/test_store.py \
  > .tmp_b2_check.fMs01p/final-targeted-knowledge.txt 2>&1

/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q \
  tests/unit/foundry/methods/catalog/causal/test_literature_prior.py \
  tests/unit/foundry/methods/catalog/causal/test_graph_reconciliation.py \
  tests/unit/ir/test_literature_contract.py \
  tests/unit/scientist/discovery/test_prior_miner.py \
  tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py::test_claim_axes_round_trip_through_activated_writer_and_all_public_readers \
  > .tmp_b2_check.fMs01p/final-targeted-downstream.txt 2>&1
```

Results: **44 passed in 4.57s**, **71 passed in 43.82s**, and **47 passed in 53.60s**. The knowledge
wave's two warnings are the intentional Pydantic serializer warnings from forged non-boolean
publication values; those values remain negative controls and are rejected by the writer.
Changed-path Ruff exited 0 (`All checks passed!`, 0.04s). A focused post-facade Scientist rerun
also exited 0 with four passed tests.

### Review and architecture disposition

The bounded read-only Phase-3 review over `1664a6d8a..dec7beccb` returned no Critical or Important
findings, no second same-class defect, and no stop trigger. Its verdict was ready for closeout.

The first provisioned architecture run correctly found one B-2-owned deep import from Scientist
to the defining IR module. Commit `9ade77cbd` routes that import through the existing stable
`polisyos.ir.analytics` facade. The post-fix architecture census no longer lists any B-2 path,
but the command still exits 1 on three `runtime.http.services.acquisition_admission_bundle` deep
imports, an OpenAPI output mismatch, and generator non-receipts caused by absent frontend modules
and `python` on their isolated PATH.

Under P41, the exact command was replayed at slice base `fca52ea2b` in a disposable detached
worktree. It exited 1 with the **same three runtime imports and same generator classes**; worktree
creation/removal both exited 0. The current B-2 diff does not touch any reported residual input.
The residual is therefore inherited, not a B-2 failure, and no baseline, generated artifact,
checker predicate, or unrelated Runtime source was changed. The initial `uv run --offline`
attempt did not execute the guardrail because uncached `jaxlib==0.8.2` could not be resolved;
the measured provisioned-environment runs above are the executed checks.

### Transcriber-ready row prose

#### `academic-graph-manufactures-design-from-a-placeholder`

> **TASK B-2 2026-09-04 — `open` -> `closed`; architect-ratified relocated remit delivered.**
> Edge evidence now comes only from the admitted `evidence_strength` axis. The callable free-key
> fallback is gone; design hints, adjudicated design, generic `strength`, and causal credibility
> can no longer manufacture an evidence class. `_legacy_strength_from_adjudication` resolves to
> declared absence, and the live published loop resolves its admitted vocabulary sidecar through
> the same strict encoder. A missing value survives the existing `VARCHAR NOT NULL` tables as the
> reserved storage encoding `not_established`, which is not an `EvidenceStrength` member and is
> decoded at every typed boundary to `None` plus status `not_established`. Ranking/aggregation
> exclude it; mixed rows retain the established class; genuine `unknown` remains distinct. The
> negative matrix covers all 20 `DesignFamily` members plus four placeholder labels and proves none
> can yield any design/evidence member without explicit evidence. The measured divergent witness,
> theoretical design plus moderate credibility, now resolves to absence rather than
> `observational`; an explicitly supplied cross-sectional class survives an RCT hint unchanged.
> Exact/family/contested, V2 store, Foundry/IR/reconciliation and Scientist prior consumers all
> preserve the optional value/status without storage-token leakage. The pinned snapshot is not
> rewritten: its 342 historical live-fallback rows retain the recorded misstatement and are the
> named cohort for any future authorized re-derivation. No data was produced.

#### `span-grounded-writer-ignores-the-publication-gate`

> **TASK B-2 2026-09-04 — `open` -> `closed`; live code defect repaired with zero historical data
> footprint.** `ingest_openalex_span_grounded_claims` retains whole-batch vocabulary preflight and
> now requires the literal predicate `publish_to_graph is True` before grounding, canonization or
> graph emission. False, default/missing, `None`, string `"false"`, and integer `1` controls write
> zero rows to `ac_skg_edges`, `ac_skg_edge_evidence`, and `ac_skg_span_grounded_claims`; a mixed
> batch publishes only the allowed claim, and a denied same-edge replay leaves the existing edge
> and evidence unchanged. A true, source-bound positive control still publishes. The writer now
> consumes the admitted evidence sidecar, writes `candidate_layer='candidate'`, and writes NULL to
> both SQL `design_family` fields while retaining the actual `design_family_hint` under its
> candidate name/status in the article envelope. The separate span-grounding `authority_tier` is
> unchanged and is not conflated with candidate-layer naming. The April snapshot still has no
> span-grounded table; this was a live capability defect with zero materialized footprint, not a
> harmless row-count result.

#### New row: `academic-unknown-evidence-contributes-nonzero-weight`

> **TASK B-2 REPORT 2026-09-04 — new, `open`, unallocated; unfounded contribution is not the closed
> substitution class.** `EvidenceStrength.UNKNOWN` has base weight **0.15**, equal to theoretical
> evidence. The Phase-1 pure witness produced confidence `0.08925000000000005` under the ordinary
> missing-sample/current-year factors, while the Phase-3 ideal-factor characterization produces
> `0.15`; both prove nonzero contribution. The reconciled 7,868-row pinned exact-evidence
> distribution contains zero `unknown` rows, so no current exact-table footprint is asserted, but
> the behavior is live for future/other rows and feeds noisy-OR confidence, replication and
> downstream rank-derived consumers. B-2 deliberately preserves and pins it. Closure requires a
> complete exact/family/contested/transport/prior/credal footprint measurement and either a
> provenance rule that licenses `unknown` as contributing evidence or a zero-contribution/declared-
> limitation repair, with before/after confidence and mixed-outcome negative tests. Do not close
> this row by relabeling `unknown` as `not_established`; they are now structurally distinct.

The bound debt-checker receipt and final snapshot/readback receipt follow in the next append-only
event after the single end-of-task invocation.

## Event 7 — final debt-checker and custody receipt, 2026-09-04

### Bound debt checker — single Phase-3 closeout invocation

```sh
/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python tools/quality/validation/check_debt_ledger.py --check > .tmp_b2_check.fMs01p/final-bound-debt-check.txt 2>&1
```

**Exit 0**, measured wall time **569.49 seconds** (`user 534.91`, `sys 27.23`). The complete
59-line output remained redirected throughout. Log SHA-256:
`122c1576fe6e9abe2828ce254aa290a4fb8adc00ecba33a38fa4bf0a8dee7b62`.

Selected exact metrics:

```text
register_ids=189
gy_ids=38
atlas_debt_rows=22
frontend_disposition_entries=261
frontend_ds8_assignment_rows=217
explicit_nonclosure_entries=29
explicit_nonclosure_identified=18
explicit_nonclosure_typed_not_a_debt=11
explicit_nonclosure_resolved_history=8
explicit_nonclosure_unidentified=0
closure_signal_pytest_selections=44
closure_signal_unsupported_runners=1
closure_signal_identities_without_commands=4
closure_signal_identity_unresolvable=9
closure_signal_input_unresolvable=0
closure_signal_selects_nothing=0
closure_signal_collection_failed=0
closure_signal_collection_host_unknown=0
closure_signal_ast_collection_disagreements=0
closure_signal_count_exit_disagreements=9
```

The retained unsupported Vitest selector, nine unresolved identities/count-exit disagreements,
and register/source-standing notes are explicitly informational in the checker's output. They
are not presented as successful test runs and are unchanged by B-2. No second Phase-3 debt-checker
invocation was made.

### Final custody/readback

After the checker returned, read-only verification produced:

```text
production snapshot sha256 = 583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967
branch = refs/heads/codex/debt-b2-manufactured-design
implementation = dec7beccb
architecture facade correction = 9ade77cbd
Phase-3 journal = 367aa8433 plus this final append
active-plan diff = empty
```

The snapshot digest exactly matches the task's pinned value. `production_data` was never handed
to a writer, chmodded, regenerated, or otherwise mutated. No source under
`src/polisyos/runtime/quality/` changed. The only post-checker repository write is this append-only
receipt; it changes neither a checker input predicate nor implementation behavior.
