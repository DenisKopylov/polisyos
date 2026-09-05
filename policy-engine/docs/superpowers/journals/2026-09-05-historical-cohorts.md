# Historical cohorts — append-only journal

## Event 1 — Phase-1 measurement and framing stop, 2026-09-05

**Disposition: stop after Phase 1 under the task's first stop rule.** The nominated counts
are reproducible, but they are not a complete description of the historical footprint of
the two withdrawn rules. In particular, **342 is the credibility-fallback subset, not the
whole retained design/credibility-projection population**. The remaining 7,526 published
evidence rows also match the withdrawn mapper's design branches. Their retained source
claims likewise contain no separate `evidence_strength`. This is a correction to the
cohort boundary, **not a claim that another 7,526 study classifications have been proved
factually false**. HC-F03 states that distinction precisely.

No Phase-2 marker design or (a)/(b) choice is adopted. No implementation, schema change,
red/green repair round, data pass, extraction, adjudication, snapshot assembly, publication,
or production-data write has been performed. The open debt is not closed by this journal.
The separate parameter-value-provenance debt is neither investigated nor repaired here.

### HC-F01 — pin, custody, instructions, and method

- Worktree: `/Users/deniskopylov/polisyos/.worktrees/debt-historical-cohorts/policy-engine`.
- Attached branch: `codex/debt-historical-cohorts`.
- Supplied and independently read entry HEAD:
  `a2954f328397e8197b40633954535188ee29894c`.
- The two exact register rows were the first substantive reads. Register rule 9, root
  `AGENTS.md`, `CONTRIBUTING.md`, and the failure/repair register were read before analysis.
  No file under `docs/plans/active/` is edited; the architect transcribes at merge.
- Pinned database:
  `production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb`.
  The link resolves into the primary checkout's `production_data`; the database is
  2,390,503,424 bytes, mode `-r--r--r--`.
- Initial SHA-256:
  `583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`.
  Every snapshot connection explicitly uses `read_only=True`. The inspected `SKGQuery`
  and `ScholarKnowledgeStore` constructors also open read-only connections. No permissions
  were changed. A final hash receipt is appended below after closeout.
- There is no worktree-local `.venv`. Diagnostics use the provisioned primary checkout
  interpreter, `/Users/deniskopylov/polisyos/policy-engine/.venv/bin/python`, with
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src`. Executed import-path readback resolves
  `skg_query.py` and `credal_reference.py` to this worktree. No other lane was entered.
- Scratch scripts and logs are in the `git check-ignore`-confirmed
  `_build/historical-cohorts/`. The sole delivery file is this journal. Programs are
  reproduced below so the durable result does not depend on ignored scratch.

The executor of the SQL, Python, AST, and filesystem walks is this task. These findings
are **`recomputed`**, cross-checked through separately executed SQL and Python paths; they
are not claims of an independent institutional verifier. Historical invocation provenance
is a separate predicate and is **`not_established`**. That limitation describes the origin
proof, not the existence of the already-computed values.

Pattern pass: P35/P36 (complete denominators and inherited arithmetic), P37/P38 (do not
substitute a selected subset or matching output for the property being asserted), P07/P08
(generation/rule and time distinctions), P04/P05 (computed historical values versus absent
axes), and P31/P40 (avoid a marker confined to one reader). The missing historical
rule-binding capability remains `artifact_missing` / `verification_missing`; a complete
consumer bridge for a withdrawal marker is not demonstrated. No new capability is claimed.

### HC-F02 — the named counts, cross-check, and overlap

The complete snapshot walk finds **23 files**: one DuckDB, 16 JSON, two JSONL, one NPZ,
one HNSW, and two extensionless `.DS_Store` files. `SHOW TABLES` finds **27 tables**;
the program runs `count(*)` over every table. Full fetched row populations independently
reconcile the named table denominators below.

| Population | Complete table denominator | Nominated selection |
| --- | ---: | ---: |
| `ac_causal_claims_raw` | 137,589 | 342 selected evidence claim IDs resolve |
| `ac_claim_adjudications` | 67,791 | All 7,868 published evidence IDs resolve |
| `ac_skg_edge_evidence` | 7,868 | 342 credibility-fallback matches |
| `ac_skg_edges` | 7,607 | 341 distinct edges reached by those 342 claims |
| `ac_skg_family_edges` | 15,945 | 440 stored strongest labels equal `unknown` |
| `ac_skg_contested_edges` | 723 | 18 stored strongest labels equal `unknown` |
| `ac_skg_transport_scores` | 7,607 | 341 rows join the 342-claim exact-edge lineage |

The 342 selection is derived twice: a full Python walk of evidence joined by claim ID to
adjudications, and a SQL selection of adjudicated designs outside the mapper's design cases
with credibility in `strong/moderate/weak`. Both produce 342 identical `(claim_id, edge_id)`
pairs: **identity symmetric difference 0**, 342 distinct claims, 341 distinct exact edges.
Its complete distribution is:

| Adjudicated design | Credibility | Stored evidence class | Rows |
| --- | --- | --- | ---: |
| `unclear` | `moderate` | `observational` | 163 |
| `unclear` | `strong` | `observational` | 24 |
| `theoretical` | `moderate` | `observational` | 127 |
| `theoretical` | `strong` | `observational` | 4 |
| `review` | `moderate` | `observational` | 24 |
| **Total** | | | **342** |

The 440 and 18 selections are likewise derived from full fetched tables and independently
queried in SQL, with identity symmetric difference 0 for each. Family confidence is
0.009811871841035491–0.18319992393168316, sum 29.556900222879015; every selected contested
confidence is exactly 0.15. These sums describe stored values; they are not contribution
attributions or additive probabilities.

The grains must not be added as independent evidence:

- The 342-claim lineage touches 341 family rows and nine contested rows. None of those
  rows belongs to the 440/18 strongest-unknown selections.
- The 440 family rows reference 444 distinct raw claims. The 18 contested rows reference
  21 distinct raw claims, **all 21 within those 444**. The two nominated repairs' claim
  lineages are disjoint; the family and contested parts of the second cohort are not
  independent source populations.
- All 444 and all 21 referenced raw labels are generic `unknown`. **None** of these IDs
  exists in the current 7,868-row exact-evidence table. The 440 distinct exact-edge IDs
  listed by the unknown family rows are also absent from the current 7,607-row exact table.
  Do not manufacture missing per-evidence generation provenance from the raw label.
- Family `updated_ts` spans April 8 12:06:03.158251–12:08:34.885512; contested spans
  April 8 12:08:34.900879–12:08:43.002230. The single assembled SKG version is 1,
  created April 11 11:20:51.634942. Version 1 is not a generating rule identifier.

Cross-check against a separate population: complete JSON-reference expansion joined to raw
claims finds **1,030 family rows and 48 contested rows** referencing at least one raw generic
`unknown`; a full Python reference walk independently reproduces those counts. Those exceed
440/18 by 590/30. They are **lineage counts, not measured withdrawn-weight contributions**:
raw generic strength and historically synthesized per-evidence strength are different axes,
and the missing historical per-evidence generation prevents exact attribution. This task
does not silently replace the 458 selection with 1,078 affected confidence values.

### HC-F03 — the substantive framing correction

The retired `_legacy_strength_from_adjudication` function was read from ancestor
`cd6dfc50bea2a38f4785eacdcd1befc98b144ecf`, with ancestry checked against this task's HEAD.
Only that pure function's AST was executed, not the historical module or a graph producer.
For **all 7,868** joined evidence/adjudication rows its output equals the stored class:
**7,868 matches, zero disagreements**. The independently implemented mapping in
`measure.py` agrees. The branch partition is:

| Retired mapper branch matching stored bytes | Rows |
| --- | ---: |
| Design-to-evidence projection | 7,526 |
| Credibility-to-evidence fallback | 342 |
| **Complete published evidence denominator** | **7,868** |

The complete **310,829 `ac_article_extractions.extraction_json` documents** parse as JSON and
contain **137,714 embedded claim objects**. A Python walk reconciles exactly one retained
payload per published evidence claim: 7,868 matches / 7,868 distinct IDs. A separate SQL
`json_each` join independently returns `(7868, 7868, 7868, 0, 0)` for total joined rows,
distinct IDs, payload matches, explicit `evidence_strength` keys, and `claim_vocabulary`
sidecars. Thus **neither the 342 subset nor the other 7,526 has a retained separate evidence
axis**. Hints and method/supporting-span fields exist; their presence does not establish
the truth or falsity of the study classification. No span validation or new classification
has been performed.

The current B-1 source-row projection was then executed for all 7,868 matched raw rows:
all return `evidence_strength=None`, status `not_established`, and
`ambiguous_legacy_vocabulary`. Calling the current pure `_infer_edge_strength` on those
raw dictionaries returns the reserved absence encoding for all 7,868. This is a read/pure
function characterization, **not a claim that the current full writer accepts old rich
payloads or that a re-derivation pass has run**.

In contrast, the current exact-prior reader returns **all 7,607 exact edges with their stored
class unchanged and status `candidate`**. Therefore the additional design-branch population
is not merely unreachable source history. The forward repair withdrew the design
substitution together with the credibility substitution; the historical compatibility
question cannot be exhaustively delimited by the 342 credibility rows.

**What is refuted:** treating 342 as the full historical design/credibility-substitution
footprint to which the joint (a)/(b) decision applies. **What is not refuted:** the count and
identity of the 342 credibility-fallback examples, or the count of 458 strongest-unknown
aggregate rows. **What is not established:** that all 7,526 additional classifications are
factually wrong, or that exact reproduction proves the historical invocation of a particular
commit. Matching a withdrawn rule and proving factual misclassification are distinct claims.

This is the task's Phase-1 stop, not permission to enlarge implementation scope. If the
architect intends to repair only the two explicitly selected subsets, that narrower scope
must say it is partial with respect to the retired mapper's full matching population.

### HC-F04 — present consumer reach, executed against the snapshot

Every nominated identity was tested through current read-only functions. Thresholds were
explicitly lowered to zero and limits raised above the measured table denominator to test
reachability. This does not claim that every row is selected by an unmodified default query.

| Executed consumer | Input cohort / full denominator | Measured output |
| --- | --- | --- |
| `SKGQuery.query_edge_support`, exact mode | 341 linked edges / 7,607 | All 341 preserve stored class and confidence. |
| `query_prior_for_variables`, exact mode | Whole 7,607 exact-edge table | All 7,607 preserve stored class; all statuses `candidate`. |
| `query_edge_support`, family mode | 440 / 15,945 | All 440 preserve stored `unknown` and confidence. |
| `query_prior_for_variables`, family mode | Whole 15,945 family-edge table | All 440 nominated rows are returned as `unknown` / `candidate`. |
| `query_edge_support`, contested mode | 18 / 723 | All 18 preserve `unknown` and confidence 0.15. |
| `query_claims`, family and contested modes | 440 + 18 nominated aggregates | All preserve the stored value and confidence as `trust_score`; status `candidate`, empty `limitations`. |
| `ScholarKnowledgeStore.project_edge_summary`, using resolved exact support bindings | 341 linked edges | All preserve stored class/confidence, status `candidate`, empty `limitations`. This direct helper probe is not represented as the default exact `query_claims` route. |
| Runtime `_derive_l2_family_edge`, using actual variable and contested membership sets | 440 / 15,945 | All carry the stored confidence in provenance; 419 `incomplete`, 21 `contested`, zero `confirmed`. |
| Runtime `_derive_l2_contested_edge` | 18 / 723 | All 18 carry confidence 0.15 and stored directional weights in provenance; all `contested`. |

Concrete forwarded witness: family edge `c0b3a08b253d9eec2b59a171`,
`health.doctor_patient_communication_quality -> health.treatment_compliance`, retains
confidence `0.037113605242521164` and `unknown` / `candidate` in both the support record and
V2 summary. The summary has empty `limitations`; its source-row SHA-256 and current
projection-rule version bind the projection's bytes, not the rule that generated confidence.
Contested edge `73c55049f1e2839830140c3e` similarly forwards confidence 0.15; Runtime's
contested derivation does not even select the evidence-strength label.

The complete tracked byte census covers **4,781 files under `src/`, `tools/`, `apps/`,
`packages/`**, including 3,055 Python, 507 TypeScript, and 716 TSX files. All 3,055 Python
files parse, zero errors. There are **23 files** containing at least one of the five
evidence/exact/family/contested/transport table names. This is a literal census, not an
assertion that every hit executes or that lexical search proves a full call graph. The
program separately enumerates named query callers and generation-basis consumers.

Additional inspected routes, with their limits kept explicit:

- `scientist/methods/discovery/prior_miner.py:103` reads the prior query, then copies
  confidence, value/status, and quality signals into `PriorKnowledgeSupport`. Default
  confidence threshold 0 admits the family witness when selected by variables/limit.
- `foundry/methods/catalog/causal/literature_prior.py:196` reads hybrid priors, then
  constructs `LiteratureEdgePrior` from confidence, value/status and article references.
  The default 0.2 threshold excludes the 440 family rows; the configurable threshold is
  material. This task did not execute a Foundry workflow.
- `runtime/quality/capability_index_compiler.py:881` opens DuckDB directly and reads exact
  confidence plus transport/contested joins. Its output builds quality scores and source
  assets; it does not pass through the SKG query projection. No capability producer was run.
- `runtime/quality/credal_reference.py:839,856,899` is a separate direct SQL path. The pure
  derivation consumers above were executed with real rows; no persisted credal dataset was
  generated.
- `batch/best_snapshot.py:925` copies matching source columns in `_replace_table_contents`;
  `tools/ops_runners/cloud/merge_shards.py:244` attaches shard databases read-only and copies
  rows. These routes were inspected, **not run**. An annotation solely in a query DTO would
  not accompany their stored values. This is not a proof that future copier changes are
  impossible.
- Benchmark/QC, transport derivation, retraction, source inventories, and causal forecast
  search have separate table or named-query hits in the census. They were not invoked to
  produce data. Their presence is not inflated into an executed terminal witness.

Answer to present reachability: **yes**, current consumers can still read and forward every
nominated aggregate value. Candidate/incomplete/contested status already limits some uses,
but it does not identify a withdrawn rule. No completed after-(b) universal-reach claim is
made: Phase 1 stopped before a marker was designed. An SKG-only marker would be partial,
because direct Runtime SQL and copy/export paths do not consume that projection.

### HC-F05 — existing markers and prior art, not a marker design

The complete schema and quality-JSON key walks over evidence/exact/family/contested tables
find no stored withdrawal or generation-rule binding. All 16 snapshot JSON documents were
also walked recursively. They retain assembly/source descriptions and a snapshot version;
these do not identify the withdrawn substitution or unknown-contribution rule.

Existing markers must be described by their actual purpose:

- B-1's raw-claim projection **already** exposes `ambiguous_legacy_vocabulary` and absent
  axes. It does not mark the historical computed values subsequently read from edge tables.
- B-2's reserved storage encoding is `not_established` and represents an absent evidence
  axis. Replacing a computed historical class/confidence with it would collapse the
  distinction the task requires. This task performs no such replacement.
- `kernel/io/generation_basis.py` was the first prior-art implementation read. Its existing
  consumer in `skg_schema_generation_basis` binds **DDL and compatibility ALTER bytes**,
  not adjudication projection or confidence-weighting inputs. Current uses are publish and
  shadow loading; the complete census finds no call from the measured SKG/Runtime readers.
  The executed missing-basis probe returns `status='missing'` and
  `recorded_rule_version='unrecorded'`, not the identity of a withdrawn rule. That outcome
  concerns the missing basis receipt, not whether a stored number was computed.

A generation-basis digest supplied retrospectively by the producing/interested code would
not, by itself, establish the historical rule. HC-F03's byte reconciliation can support a
bounded statement of compatibility with the retired mapper; it must not be promoted to an
invocation receipt or proof that each inferred study classification is false.

### HC-D00 — why the (a)/(b) decision is withheld at this stop

The supplied task explicitly makes Phase 1 a prerequisite and requires a stop when the
framing is refuted. HC-F03 refutes the completeness of its 342-row rule footprint while
preserving the narrower count. Therefore neither (a) nor (b) is selected on the old framing.

The alternatives remain distinct. **(a)** would replace historical results under an
authorized data pass and requires authorization this task does not carry. **(b)** could
preserve values with a machine-readable, content-derived limitation, but its actual cohort,
claim about the retired rule, and reach through direct SQL and copies must be specified and
verified. The existing schema-basis comparison is not already that capability. A partial
query marker would help query consumers; it would not discharge the complete historical
rule claim or accompany every forwarding path measured here. This is an argument for
withholding the decision until the corrected boundary is acknowledged, not an assertion
that (b) is technically impossible or that (a) has been authorized.

**Red/green:** not applicable; Phase 3 was not entered and zero implementation fix rounds
were used. The evidence consists of targeted read-only characterization programs, all
completed with exit 0. No broad backend suite, CI-parity, data production, or live lane ran.

### HC-T01 — exact transcriber-ready prose for the open row

> **TASK 2026-09-05 — Phase-1 measurement; stays `open`, no (a)/(b) decision or repair.**
> At `a2954f328`, read-only SQL and Python population walks independently confirm the named
> selection: 440 of 15,945 family rows and 18 of 723 contested rows have stored strongest
> class `unknown`, with identical selected identities in both methods. Every nominated
> value remains forwardable through current SKG readers; the family and contested V2
> summaries retain confidence with `candidate` evidence status and empty limitations.
> These are 458 aggregate rows, not 458 independent source claims: the 21 distinct claims
> referenced by contested rows are contained in the family rows' 444 claims; all are absent
> from current exact evidence. They are disjoint from the 342-claim credibility-fallback
> subset. **The joint-decision framing is incomplete:** 342 is only the credibility tail
> of the withdrawn mapper. Another 7,526 of the complete 7,868 published evidence rows
> match its withdrawn design projections and also have no separately retained source
> evidence-strength axis. This is a retired-rule compatibility finding, not proof that
> those 7,526 classifications are factually false or a receipt of historical invocation.
> The 458 count likewise names strongest-unknown aggregates, not a measured census of
> every mixed aggregate's unknown contribution: 1,030 family and 48 contested rows have
> raw-unknown lineage, whose numeric contribution cannot be assigned from that lineage
> alone. The task stopped under its Phase-1 rule before selecting a marker or re-derivation.
> The existing generation-basis mechanism guards schema DDL/ALTER generation, not these
> computed values, and current direct SQL/copy paths bypass the query projection. No
> value is relabelled `not_established`, no parameter provenance is retroactively assigned,
> and the pinned snapshot remains unchanged. Findings and reproduction: HC-F02–HC-F05 in
> `docs/superpowers/journals/2026-09-05-historical-cohorts.md`.

### HC-T02 — separate paragraph for the closed 342-row row

> **2026-09-05 HISTORICAL-COHORT BOUNDARY CORRECTION — substitution repair stays `closed`.**
> The 342 evidence rows / 341 exact edges are independently reproduced as the credibility
> fallback subset, with the same five design/credibility groups; that count is not revoked.
> They are not the full historical footprint of the design/credibility mapper withdrawn
> by B-2. Executing the retired pure function over the complete published population matches
> all 7,868 stored evidence classes: 7,526 design projections plus 342 credibility
> fallbacks. A complete 310,829-extraction / 137,714-embedded-claim walk and independent SQL
> join find exactly one source payload for each published claim and no separate
> `evidence_strength` or vocabulary sidecar in any of them. Current exact-prior reads still
> forward all 7,607 stored aggregate classes as candidates. This identifies an additional
> retired-rule compatibility population; it does **not** establish another 7,526 false
> study classifications or prove a generating commit from output agreement. The historical
> decision must either account for that broader population or explicitly delimit itself
> to the 342 credibility examples. No historical rows were rewritten and B-2's forward
> repair is not reopened. See HC-F03/HC-F04 in
> `docs/superpowers/journals/2026-09-05-historical-cohorts.md`.

## Event 2 — reproducible measurement programs, 2026-09-05

Run from the product worktree above. `_build/historical-cohorts` is ignored scratch, not a
delivery/staging directory. Save the following programs there, then run:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/historical-cohorts/measure.py > _build/historical-cohorts/measure.log 2>&1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/historical-cohorts/census.py > _build/historical-cohorts/census.log 2>&1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/historical-cohorts/readers.py > _build/historical-cohorts/readers.log 2>&1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -u _build/historical-cohorts/source_basis.py > _build/historical-cohorts/source_basis.log 2>&1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -u _build/historical-cohorts/retired_rule.py > _build/historical-cohorts/retired_rule.log 2>&1
```

The first program writes only selected identity lists to ignored diagnostic scratch. All
database access is read-only. The programs below are the exact successful script contents.

### measure.py

```python
"""Read-only full-population characterization; never invoke a data producer."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import stat
import subprocess

import duckdb

DB = Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
OUT = Path('_build/historical-cohorts')

def emit(name, value):
    print(name, json.dumps(value, sort_keys=True, default=str), flush=True)

with DB.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
assert digest == '583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967'
emit('custody', dict(path=str(DB.resolve()), sha256=digest, size=DB.stat().st_size, mode=stat.filemode(DB.stat().st_mode)))
files = [p for p in DB.parents[2].rglob('*') if p.is_file()]
emit('snapshot_files', dict(total=len(files), by_type=dict(Counter(p.suffix or '<none>' for p in files)), paths=[str(p.relative_to(DB.parents[2])) for p in files]))
c = duckdb.connect(str(DB), read_only=True)

def rows(table):
    cur = c.execute('SELECT * FROM "'+table+'"')
    names = [col[0] for col in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]

tables = [t for (t,) in c.execute('SHOW TABLES').fetchall()]
counts = {t:c.execute('SELECT count(*) FROM "'+t+'"').fetchone()[0] for t in tables}
emit('table_denominator', dict(total=len(tables), rows=counts))
E = rows('ac_skg_edge_evidence')
A = {r['claim_id']:r for r in rows('ac_claim_adjudications')}
R = {r['id']:r for r in rows('ac_causal_claims_raw')}
X = rows('ac_skg_edges')
F = rows('ac_skg_family_edges')
C = rows('ac_skg_contested_edges')
T = rows('ac_skg_transport_scores')
normalize = lambda value: str(value or '').strip().lower()
design_map = {
 'rct':'rct', 'iv':'quasi_natural', 'did':'quasi_natural', 'rdd':'quasi_natural',
 'synthetic_control':'quasi_natural', 'event_study':'quasi_natural_event',
 'quasi_experimental_other':'quasi_natural_event', 'quasi_experimental_did':'quasi_natural_event',
 'quasi_experimental_rdd':'quasi_natural_event', 'meta_analysis':'meta_analysis',
 'panel_fe':'panel_fe', 'system_gmm':'panel_fe', 'gmm':'panel_fe',
 'structural_model':'structural', 'time_series_cointegration':'structural',
 'ols':'observational', 'ols_cross_sectional':'cross_sectional',
}
cred_map = {'strong':'observational','moderate':'observational','weak':'theoretical'}
cohort_a=[]
mismatches=[]
for row in E:
    a=A[row['claim_id']]
    design,cred=normalize(a['design_family']),normalize(a['causal_credibility'])
    expected = design_map.get(design, cred_map.get(cred,'unknown'))
    if expected != row['evidence_strength']: mismatches.append(row['claim_id'])
    if design not in design_map and cred in cred_map: cohort_a.append(row)
sql_a = c.execute("""
 SELECT e.claim_id,e.edge_id FROM ac_skg_edge_evidence e
 JOIN ac_claim_adjudications a ON a.claim_id=e.claim_id
 WHERE lower(trim(a.design_family)) NOT IN
 ('rct','iv','did','rdd','synthetic_control','event_study','quasi_experimental_other',
  'quasi_experimental_did','quasi_experimental_rdd','meta_analysis','panel_fe','system_gmm','gmm',
  'structural_model','time_series_cointegration','ols','ols_cross_sectional')
 AND lower(trim(a.causal_credibility)) IN ('strong','moderate','weak')
""").fetchall()
a_claims={r['claim_id'] for r in cohort_a}
a_edges={r['edge_id'] for r in cohort_a}
assert set(sql_a)=={(r['claim_id'],r['edge_id']) for r in cohort_a}
emit('cohort_a', dict(python_count=len(cohort_a), sql_count=len(sql_a), identity_symmetric_difference=0,
 distinct_claims=len(a_claims), distinct_exact_edges=len(a_edges), legacy_rule_mismatches=len(mismatches),
 raw_joined=sum(r['claim_id'] in R for r in E), adjudications_joined=len(E),
 distribution=dict(Counter('|'.join([A[r['claim_id']]['design_family'],A[r['claim_id']]['causal_credibility'],r['evidence_strength']]) for r in cohort_a))))

def refs(row): return set(json.loads(row['claim_refs'] or '[]'))

cohort_b={}
for table,data,key in [('ac_skg_family_edges',F,'family_edge_id'),('ac_skg_contested_edges',C,'contested_edge_id')]:
    unknown=[r for r in data if r['evidence_strength']=='unknown']
    cohort_b[table]=unknown
    ids={r[key] for r in unknown}
    sql_ids={r[0] for r in c.execute('SELECT '+key+' FROM '+table+" WHERE evidence_strength='unknown'").fetchall()}
    assert ids==sql_ids
    unknown_refs=set().union(*(refs(r) for r in unknown))
    sql_raw_unknown_rows=c.execute('SELECT count(DISTINCT t.'+key+') FROM '+table+" t, json_each(t.claim_refs) j JOIN ac_causal_claims_raw r ON r.id=json_extract_string(j.value,'$') WHERE r.strength='unknown'").fetchone()[0]
    py_raw_unknown_rows=sum(any(R[rid]['strength']=='unknown' for rid in refs(r)) for r in data)
    assert sql_raw_unknown_rows==py_raw_unknown_rows
    emit(table,dict(total=len(data), count_star_cross_check=counts[table],
     unknown_python=len(unknown),unknown_sql=len(sql_ids),identity_symmetric_difference=0,
     all_strengths=dict(Counter(r['evidence_strength'] for r in data)),
     confidence=dict(min=min(r['confidence'] for r in unknown),max=max(r['confidence'] for r in unknown),sum=sum(r['confidence'] for r in unknown)),
     cohort_a_lineage_rows=sum(bool(refs(r)&a_claims) for r in data),
     cohort_a_and_unknown_lineage_rows=sum(bool(refs(r)&a_claims) for r in unknown),
     unknown_distinct_claim_refs=len(unknown_refs),unknown_claims_in_exact_evidence=len(unknown_refs&{r['claim_id'] for r in E}),
     unknown_refs_in_a=len(unknown_refs&a_claims),unknown_refs_raw_strengths=dict(Counter(R[x]['strength'] for x in unknown_refs)),
     all_rows_with_raw_unknown_ref_python=py_raw_unknown_rows,all_rows_with_raw_unknown_ref_sql=sql_raw_unknown_rows,
     whole_table_distinct_claim_refs=len(set().union(*(refs(r) for r in data))),
     n_claims_mismatches=sum(r['n_claims']!=len(refs(r)) for r in data),
     unknown_quality_keys=dict(Counter(k for r in unknown for k in json.loads(r['quality_signals_json'] or '{}'))),
     updated_min=str(min(r['updated_ts'] for r in data)),updated_max=str(max(r['updated_ts'] for r in data))))

family_refs=set().union(*(refs(r) for r in cohort_b['ac_skg_family_edges']))
contested_refs=set().union(*(refs(r) for r in cohort_b['ac_skg_contested_edges']))
family_exact=set().union(*(set(json.loads(r['quality_signals_json'])['exact_edge_ids']) for r in cohort_b['ac_skg_family_edges']))
emit('lineage_overlap',dict(family_contested_claim_intersection=len(family_refs&contested_refs),contested_claims_outside_family=len(contested_refs-family_refs),
 unknown_family_exact_edge_refs=len(family_exact),unknown_family_exact_edge_refs_present=len(family_exact&{r['edge_id'] for r in X}),
 a_exact_edges_present=sum(r['edge_id'] in a_edges for r in X),a_transport_rows=sum(r['edge_id'] in a_edges for r in T)))
emit('stored_markers', {t:{'columns':[r[0] for r in c.execute('DESCRIBE '+t).fetchall()],
 'quality_keys':dict(Counter(k for r in data for k in json.loads(r.get('quality_signals_json') or '{}')))}
 for t,data in [('ac_skg_edge_evidence',E),('ac_skg_edges',X),('ac_skg_family_edges',F),('ac_skg_contested_edges',C)]})
emit('versions',rows('ac_skg_versions'))
emit('runs',rows('ac_runs'))
emit('witnesses',dict(a=cohort_a[0],family=cohort_b['ac_skg_family_edges'][0],contested=cohort_b['ac_skg_contested_edges'][0]))
OUT.joinpath('cohort-identities.json').write_text(json.dumps(dict(a_claims=sorted(a_claims),a_edges=sorted(a_edges),family_unknown=sorted(r['family_edge_id'] for r in cohort_b['ac_skg_family_edges']),contested_unknown=sorted(r['contested_edge_id'] for r in cohort_b['ac_skg_contested_edges'])),indent=2)+'\n')
c.close()
```

### census.py

```python
"""Complete tracked source/tool/application byte census, plus snapshot JSON walk."""
from collections import Counter, defaultdict
from pathlib import Path
import ast
import json
import subprocess

paths=[Path(p) for p in subprocess.check_output(['git','ls-files','src','tools','apps','packages'],text=True).splitlines()]
tokens=['ac_skg_edge_evidence','ac_skg_edges','ac_skg_family_edges','ac_skg_contested_edges','ac_skg_transport_scores','query_edge_support','query_prior_for_variables','query_claims','project_edge_summary','compare_generation_basis','GenerationBasisComparison']
hits=defaultdict(list)
errors=[]
for p in paths:
    raw=p.read_bytes()
    for token in tokens:
        if token.encode() in raw:
            lines=[i for i,line in enumerate(raw.splitlines(),1) if token.encode() in line]
            hits[token].append([str(p),lines])
    if p.suffix=='.py':
        try: ast.parse(raw)
        except SyntaxError as e: errors.append([str(p),str(e)])
print('source_denominator',json.dumps(dict(paths=len(paths),by_type=dict(Counter(p.suffix or '<none>' for p in paths)),python_parse_errors=errors),sort_keys=True))
for token in tokens: print(token,json.dumps(hits[token]))
root=Path('production_data/policyos_academic_runtime_slim_20260411T112032Z')
key_counts=Counter()
interesting=[]
json_files=list(root.rglob('*.json'))
for p in json_files:
    def walk(value,at=''):
        if isinstance(value,dict):
            for k,v in value.items():
                key_counts[k]+=1
                if any(s in k.lower() for s in ('basis','rule','withdra','incompat','stale','version','source')):
                    interesting.append([str(p.relative_to(root)),at+'/'+k,v if not isinstance(v,(dict,list)) else '<container>'])
                walk(v,at+'/'+k)
        elif isinstance(value,list):
            for n,v in enumerate(value): walk(v,at+'/'+str(n))
    walk(json.loads(p.read_text()))
print('snapshot_json_keys',json.dumps(dict(files=len(json_files),distinct_keys=len(key_counts),interesting=interesting),sort_keys=True))
```

### readers.py

```python
"""Exercise current read-only consumers against every nominated row identity."""
from pathlib import Path
from collections import Counter
from dataclasses import asdict
import inspect
import json

import duckdb
from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
from polisyos.data_forge.kernel.io.generation_basis import build_generation_basis, compare_generation_basis
from polisyos.runtime.quality.credal_reference import _derive_l2_family_edge, _derive_l2_contested_edge, _l2_contested_memberships

DB=Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
ids=json.loads(Path('_build/historical-cohorts/cohort-identities.json').read_text())
c=duckdb.connect(str(DB),read_only=True)
q=SKGQuery(DB,Path('_build/historical-cohorts/unused-index'))
print('import_paths',inspect.getfile(SKGQuery),inspect.getfile(_derive_l2_family_edge))
for mode,table,key,src,dst,cohort in [
 ('exact','ac_skg_edges','edge_id','src','dst',set(ids['a_edges'])),
 ('family','ac_skg_family_edges','family_edge_id','src_family','dst_family',set(ids['family_unknown'])),
 ('contested','ac_skg_contested_edges','contested_edge_id','src_family','dst_family',set(ids['contested_unknown'])),
]:
    data=c.execute(f'SELECT {key},{src},{dst},evidence_strength,confidence FROM {table}').fetchall()
    targets=[r for r in data if r[0] in cohort]
    support_match=summary_match=0
    statuses=Counter();limitations=Counter();first=None
    for rid,cause,effect,strength,confidence in targets:
        supports=q.query_edge_support(cause=cause,effect=effect,min_confidence=0,support_mode=mode,limit=len(data)+1)
        support=next((r for r in supports if r.edge_id==rid),None)
        assert support is not None,(mode,rid,'missing support')
        assert (support.evidence_strength,support.confidence)==(strength,confidence)
        support_match+=1
        summaries=q.query_claims(cause=cause,effect=effect,min_trust=0,support_mode=mode,limit=len(data)+1) if mode!='exact' else [q._store.project_edge_summary(source_table=table,source_identity=rid,cause=cause,effect=effect,direction=support.direction,evidence_strength=support.evidence_strength,mechanism='exact_support',domain='',trust_score=support.confidence,work_title='read-only characterization',source_bindings=support.source_bindings)]
        summary=next((r for r in summaries if r.id==rid),None)
        assert summary is not None,(mode,rid,'missing summary')
        assert (summary.evidence_strength.value,summary.trust_score)==(strength,confidence)
        summary_match+=1
        statuses[summary.evidence_strength_status.value]+=1
        limitations[str(summary.limitations)]+=1
        if first is None: first=dict(support=asdict(support),summary=summary.model_dump(mode='json'))
    print(mode+'_support_summary',json.dumps(dict(denominator=len(data),cohort=len(targets),support_value_matches=support_match,summary_value_matches=summary_match,statuses=dict(statuses),limitations=dict(limitations),witness=first),sort_keys=True,default=str))
    if mode!='contested':
        prior=q.query_prior_for_variables([],min_confidence=0,edge_layer=mode,limit=len(data)+1)
        selected=[r for r in prior if r['edge_id'] in cohort]
        assert {r['edge_id'] for r in selected}==cohort
        print(mode+'_prior',json.dumps(dict(total_returned=len(prior),cohort_forwarded=len(selected),keys=sorted(set().union(*(r.keys() for r in selected))),statuses=dict(Counter(r['evidence_strength_status'] for r in selected))),sort_keys=True))

membership,_=_l2_contested_memberships(c)
variables={r[0] for r in c.execute('SELECT canonical_name FROM ac_skg_variables').fetchall()}
family=c.execute('SELECT family_edge_id,src_family,dst_family,direction,n_articles,n_claims,evidence_strength,confidence,direction_histogram_json,design_tier_histogram_json,candidate_layer,quality_signals_json FROM ac_skg_family_edges').fetchall()
contested=c.execute('SELECT contested_edge_id,src_family,dst_family,dominant_direction,resolution_status,runtime_support,confidence,positive_weight,negative_weight,mixed_weight,direction_histogram_json,quality_signals_json FROM ac_skg_contested_edges').fetchall()
for mode,data,cohort in [('family',family,set(ids['family_unknown'])),('contested',contested,set(ids['contested_unknown']))]:
    derived=[_derive_l2_family_edge(r,version='1',variable_names=variables,contested_edges=membership) if mode=='family' else _derive_l2_contested_edge(r,version='1') for r in data if r[0] in cohort]
    print(mode+'_credal',json.dumps(dict(denominator=len(data),forwarded=len(derived),statuses=dict(Counter(r.status for r in derived)),witness=asdict(derived[0])),sort_keys=True,default=str))

current=build_generation_basis(basis_kind='measurement-only',generator_rule_version='current',members=[('synthetic',b'probe')])
print('basis_missing_probe',json.dumps(asdict(compare_generation_basis(None,current=current)),sort_keys=True))
q.close();c.close()
```

### source_basis.py

```python
"""Reconcile the complete retained claim payloads; no re-derivation or producer run."""
from pathlib import Path
from collections import Counter
import json
import duckdb

DB=Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
c=duckdb.connect(str(DB),read_only=True)
evidence={r[0]:r[1:] for r in c.execute('SELECT claim_id,edge_id,evidence_strength FROM ac_skg_edge_evidence').fetchall()}
ids=json.loads(Path('_build/historical-cohorts/cohort-identities.json').read_text())
a=set(ids['a_claims'])
seen=Counter();den=Counter();fields=Counter();by_group=Counter()
cur=c.execute('SELECT work_id,extraction_json FROM ac_article_extractions')
while batch:=cur.fetchmany(1000):
    for work,payload in batch:
        den['extractions']+=1
        value=json.loads(payload)
        den['valid_json']+=1
        for claim in value.get('causal_claims',[]):
            den['embedded_claims']+=1
            if not isinstance(claim,dict):
                den['non_object_claims']+=1;continue
            cid=claim.get('claim_id')
            if cid not in evidence:continue
            seen[cid]+=1
            group='credibility_tail' if cid in a else 'design_projection'
            by_group[group]+=1
            for key in claim:fields[group+':'+key]+=1
            if claim.get('evidence_strength') is not None:den['published_explicit_evidence']+=1
            if claim.get('claim_vocabulary'):den['published_vocabulary_sidecar']+=1
sql=c.execute("""
 WITH payload_claims AS (
 SELECT json_extract_string(j.value,'$.claim_id') claim_id,j.value
 FROM ac_article_extractions a,json_each(a.extraction_json,'$.causal_claims') j
 )
 SELECT count(*),count(DISTINCT e.claim_id),count(p.value),
 count(*) FILTER(WHERE json_exists(p.value,'$.evidence_strength')),
 count(*) FILTER(WHERE json_exists(p.value,'$.claim_vocabulary'))
 FROM ac_skg_edge_evidence e LEFT JOIN payload_claims p ON p.claim_id=e.claim_id
""").fetchone()
assert len(seen)==len(evidence)==sql[1]
assert sum(seen.values())==sql[2]
assert all(n==1 for n in seen.values())
assert sql[3]==den['published_explicit_evidence']==0
print('source_population',json.dumps(dict(denominator=dict(den),groups=dict(by_group),distinct_published_matches=len(seen),sql_cross_check=sql,published_field_counts=dict(fields)),sort_keys=True))
print('cohort_a_raw_generic_strengths',c.execute("SELECT r.strength,count(*) FROM ac_skg_edge_evidence e JOIN ac_causal_claims_raw r ON r.id=e.claim_id JOIN ac_claim_adjudications a ON a.claim_id=e.claim_id WHERE a.design_family IN ('unclear','theoretical','review') GROUP BY 1 ORDER BY 1").fetchall())
c.close()
```

### retired_rule.py

```python
"""Pure historical function replay and current read projections, without graph production."""
import ast
from collections import Counter
from pathlib import Path
import json
import subprocess

import duckdb
from polisyos.data_forge.domains.academic.batch.graph_builder import _infer_edge_strength
from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery

ref='cd6dfc50bea2a38f4785eacdcd1befc98b144ecf'
path='policy-engine/src/polisyos/data_forge/domains/academic/batch/graph_builder.py'
subprocess.run(['git','merge-base','--is-ancestor',ref,'HEAD'],check=True)
source=subprocess.check_output(['git','show',ref+':'+path],text=True)
tree=ast.parse(source)
function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_legacy_strength_from_adjudication')
namespace={}
exec(compile(ast.Module(body=[function],type_ignores=[]),str(ref)+':'+path,'exec'),namespace)
legacy=namespace[function.name]
DB=Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
c=duckdb.connect(str(DB),read_only=True)
rows=c.execute('SELECT e.claim_id,e.evidence_strength,a.design_family,a.causal_credibility FROM ac_skg_edge_evidence e JOIN ac_claim_adjudications a ON a.claim_id=e.claim_id').fetchall()
print('historical_function',json.dumps(dict(ref=ref,function=function.name,rows=len(rows),stored_matches=sum(legacy(dict(design_family=d,causal_credibility=k))==s for _,s,d,k in rows)),sort_keys=True),flush=True)
q=SKGQuery(DB,Path('_build/historical-cohorts/unused-index'))
cur=c.execute('SELECT r.* FROM ac_causal_claims_raw r JOIN ac_skg_edge_evidence e ON r.id=e.claim_id')
columns=[d[0] for d in cur.description]
states=Counter();encodings=Counter()
for row in cur.fetchall():
    raw=dict(zip(columns,row))
    projected=q._store._project_claim_row(raw,source_table='ac_causal_claims_raw')
    states[str(projected.evidence_strength)+'|'+projected.evidence_strength_status.value+'|'+str(tuple(x.value for x in projected.limitations))]+=1
    encodings[_infer_edge_strength(raw)]+=1
print('current_source_projection',json.dumps(dict(rows=sum(states.values()),value_status_limitation_counts=dict(states),pure_inference_counts=dict(encodings)),sort_keys=True),flush=True)
all_prior=q.query_prior_for_variables([],min_confidence=0,limit=8000,edge_layer='exact')
stored=dict(c.execute('SELECT edge_id,evidence_strength FROM ac_skg_edges').fetchall())
assert len(all_prior)==len(stored)
assert all(r['evidence_strength']==stored[r['edge_id']] for r in all_prior)
print('whole_exact_forward',json.dumps(dict(stored_denominator=len(stored),returned=len(all_prior),stored_class_matches=len(all_prior),status_counts=dict(Counter(r['evidence_strength_status'] for r in all_prior))),sort_keys=True),flush=True)
q.close();c.close()
```

### Measurement log identities

Every listed run completed with exit 0. These hashes identify diagnostic logs; the commands and exact source above are the reproducibility receipt.

| Log | SHA-256 |
| --- | --- |
| `measure.log` | `a5679eeb1c03803b0e60eb92f059b01b133e0f608861af7f4683d86739dc618b` |
| `census.log` | `5cd9b9b1f85bcb445fada0c682c96e605975177b819e4a2f6b174ca803cedc41` |
| `readers.log` | `1d433eb6a6bdc9928f9da58f6b879ffd30943137802f1412226fe40bd584d707` |
| `source_basis.log` | `ab036f65cda2873d74019c99324461e7a25d46edc850a177c999a805662de20e` |
| `retired_rule.log` | `0b35608a420f2347e944e844c3e87adb37ccf167d377e3766f606f7b5976c0a7` |

## Event 3 — pre-checker freeze, 2026-09-05

The Phase-1 stop and transcriber paragraphs are frozen. No product or test source changed. The only delivered change is this journal. The user's 2026-09-05 checker rule is applied literally: committing this requested journal **does change tracked files**, so the bound debt checker will run once at the end. The no-tracked-change skip receipt is inapplicable; claiming an unchanged tree would be false. The final checker and custody receipts will be appended without changing the measured result.
