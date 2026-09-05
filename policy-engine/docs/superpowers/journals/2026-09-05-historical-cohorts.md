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

## Event 4 — final checker, custody, and delivery receipts, 2026-09-05

The measurement journal was committed as `f7e22ef74` on the attached
`codex/debt-historical-cohorts` branch before the checker. Reading it back from that commit
reproduced SHA-256 `a487fd85b6ed716d997a8e5b8804b60d81810c65aa27d8e3677cf513be1aa484`.
All five embedded programs were extracted from the committed journal, parsed with AST, and
compared byte-for-byte with the executed scratch programs: all five matched. This checks
reproducibility of the delivered record, not a new product behavior.

### Exactly one bound debt checker

```sh
/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python tools/quality/validation/check_debt_ledger.py --check > _build/historical-cohorts/bound-debt-check.log 2>&1
```

**Exit 0.** `real 952.71`, `user 906.41`, `sys 43.14` seconds (15m 52.71s wall time).
The checker completed without a restart or timeout. Its log SHA-256 is
`8a71034508196e14339b04d1b1af6e12931f5f33ffdfb533b2357ee8b2bb651d`.

Selected receipts from the complete checker output:

```text
register_ids=193
gy_ids=38
atlas_debt_rows=22
frontend_disposition_entries=261
frontend_ds8_assignment_rows=217
closure_signal_pytest_selections=44
closure_signal_identity_unresolvable=9
closure_signal_input_unresolvable=0
closure_signal_selects_nothing=0
closure_signal_collection_failed=0
closure_signal_collection_host_unknown=0
closure_signal_ast_collection_disagreements=0
closure_signal_count_exit_disagreements=9
```

The checker labels its reported findings **informational (do not block)**: the nine
unresolvable test identities and paired count/exit disagreements, one unsupported Vitest
runner, and register-supplied standing notices. Exit 0 is the debt-reconciliation result;
it does not mean all referenced tests exist or that 44 tests were executed and passed.
No second base replay was run, so these notices are not relabelled as independently proven
inherited failures. No checker, register, ledger, plan, or test was edited to obtain this
result.

### Final production-data and branch receipt

After the checker completed:

```sh
shasum -a 256 production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb
git diff --name-only a2954f328..HEAD
git status -sb
```

Observed snapshot SHA-256:
`583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967` — identical to entry.
The exact changed-path receipt was:

```text
policy-engine/docs/superpowers/journals/2026-09-05-historical-cohorts.md
```

`git status -sb` showed the attached branch with a clean tree before this final append.
This final append changes only the same journal and is committed separately; the final
branch file is read back after that commit. No source/test/active-plan/data changes,
rebase, stash, force-push, merge, live-lane work, or data re-derivation occurred.

The failure/repair register was re-read before closeout. P35/P37/P38 are handled by the
explicit subset/full-population distinction and the refusal to treat exact output agreement
as historical execution provenance. HC-T01 and HC-T02 remain the transcription paragraphs.
The terminal result is the Phase-1 framing stop; the open historical-confidence debt remains
open, and the forward substitution repair remains closed.

## Event 5 — Phase-5 severity, recoverability, and histogram measurement, 2026-09-05

Continuation base: `11b24787a97695cc77533f7171d1de0b2558ca5e`, attached to
`codex/debt-historical-cohorts`, clean on arrival. Events 1–4 are preserved verbatim.
The architect accepted HC-F03 and supplied an independent reconciliation; this continuation
does **not** execute the retired mapper or repeat that reconciliation. The new measurement
asks whether membership in its two branches describes the same defect. It does not.

**342 is the right cohort for the manufactured empirical-design defect.** The additional
7,526 are recoverable, lossy-but-faithful translations relative to their retained
adjudications. HC-F03's rule-membership count stands; HC-T01/HC-T02's implication that it
requires enlarging this defect cohort is superseded by the replacement paragraphs below.

The histogram investigation also exposes a narrower current-rule calculation that must be
distinguished from full historical replay: with the recorded `unknown` classes held fixed,
the current confidence rule yields zero for the 440 family rows, and the current contested
producer would emit none of the 18 rows. Missing historical numeric inputs do not obstruct
that zero-weight boundary. This result is recorded for the scope ruling reserved in the
continuation, before any marker or read-time correction is implemented.

### HC-F06 — design-branch severity and recovery

`_build/historical-cohorts/phase5.py` reads the one pinned DuckDB file through
`duckdb.connect(..., read_only=True)`. It walks all rows of each of the following tables;
each Python fetched-row count equals a separate SQL `count(*)`:

| Table | Complete row denominator |
| --- | ---: |
| `ac_skg_edge_evidence` | 7,868 |
| `ac_claim_adjudications` | 67,791 |
| `ac_causal_claims_raw` | 137,589 |
| `ac_skg_edges` | 7,607 |
| `ac_skg_family_edges` | 15,945 |
| `ac_skg_contested_edges` | 723 |

The accepted credibility-branch predicate selects the complement for the severity walk;
there is no new execution or comparison of the withdrawn mapper. All 7,526 design-branch
claims have a unique retained adjudication and a nonempty adjudicated design. The full
design-to-stored-class distribution is:

| Retained adjudicated design | Stored evidence class | Rows |
| --- | --- | ---: |
| `iv` | `quasi_natural` | 3,751 |
| `did` | `quasi_natural` | 325 |
| `rdd` | `quasi_natural` | 21 |
| `synthetic_control` | `quasi_natural` | 25 |
| `event_study` | `quasi_natural_event` | 28 |
| `quasi_experimental_other` | `quasi_natural_event` | 498 |
| `meta_analysis` | `meta_analysis` | 1,095 |
| `panel_fe` | `panel_fe` | 793 |
| `rct` | `rct` | 954 |
| `structural_model` | `structural` | 4 |
| `ols` | `observational` | 32 |
| **Total** | | **7,526** |

The coarser class alone cannot recover which of four designs supplied `quasi_natural`,
or which of two supplied `quasi_natural_event`. Joining `claim_id` to the retained
adjudication recovers the source design for every member. The existing normalization
owner explicitly groups `event_study`/`quasi_experimental_other` and the structural aliases
at `src/polisyos/data_forge/domains/academic/knowledge/skg_store.py:1215`; the `_event`
class name is not a new finding that every member asserted a specific event-study design.
No `gmm` or `system_gmm` member occurs in this measured branch, so their presence in the
retired rule is not reported as a measured loss in this snapshot.

These are faithful translations **relative to the retained adjudicated design**, not an
independent validation of the underlying papers or evidence quality. They do not convert
an adjudication of unclear, theoretical, or review into an empirical class. B-1's separate
evidence-axis requirement and B-2's forward repair remain intact; this finding does not
reinstate design substitution for future data.

One recovery trap is material: **488/7,526** `ac_skg_edge_evidence.design_family` cells
differ from their retained adjudications. All 7,526 equal the raw `design_family_hint`
instead. The writer stores the hint in that column
(`src/polisyos/data_forge/domains/academic/batch/graph_builder.py:1673`), while the accepted
HC-F03 reconciliation concerns the stored **evidence class** and the adjudication. Recovery
must use the adjudication join, not reinterpret the evidence row's hint as the adjudicated
design. This does not demonstrate an additional manufactured evidence class in the design
branch, nor does this task repair the hint column.

### HC-F07 — independently checked observational concentration

The complete Python join over 7,868 evidence rows selects 374 stored `observational`
rows. A separate SQL grouped join reproduces this partition:

```sql
SELECT a.design_family, a.causal_credibility, count(*)
FROM ac_skg_edge_evidence e
JOIN ac_claim_adjudications a ON a.claim_id=e.claim_id
WHERE e.evidence_strength='observational'
GROUP BY 1,2 ORDER BY 1,2;
```

| Adjudication | Credibility | Rows |
| --- | --- | ---: |
| `ols` | `moderate` | 32 |
| `review` | `moderate` | 24 |
| `theoretical` | `moderate` | 127 |
| `theoretical` | `strong` | 4 |
| `unclear` | `moderate` | 163 |
| `unclear` | `strong` | 24 |
| **Total** | | **374** |

Thus `342 / 374 * 100 = 91.44385026737967%` of this evidence class comes from the
credibility fallback, and 32 from an actual `ols` adjudication. Within the 342, 131 invert
the retained theoretical adjudication; 187 supply an empirical design where adjudication
is unclear; 24 substitute it for review. The empirical class is not supported by those
adjudications. This is the measured severity distinction from HC-F06. The 374 denominator
is evidence rows, not the 365 exact-edge summaries bearing the same label.

### HC-F08 — what the family histograms retain, and what they do not

The complete 15,945-row family walk parses both histogram columns as JSON objects with
positive integer counts. A second SQL `json_each` aggregation agrees with every one of
the 74 `(stored evidence class, design bin)` groups and all **16,658** design memberships:

```sql
SELECT f.evidence_strength, j.key, sum(CAST(j.value AS BIGINT))
FROM ac_skg_family_edges f, json_each(f.design_family_histogram_json) j
GROUP BY 1,2 ORDER BY 1,2;
```

Every family design histogram sums to its `n_claims`, and the sum of `n_claims` equals
16,658 distinct claim references. All those references resolve to both raw rows and
adjudications. Design-histogram counts agree with the retained adjudications in
15,395/15,945 rows; 550 disagree. Tier histograms sum to `n_claims` in 15,656/15,945 rows
and match retained adjudication tiers in 7,834/15,945. These columns cannot be treated as
universally current adjudication receipts.

For the nominated **440** family rows, the design histograms do retain exactly the designs
of all **444** referenced adjudications, with zero count disagreements. There are 436
single-claim rows and four two-claim rows. Their complete design membership distribution is:

| Design bin | Claim memberships |
| --- | ---: |
| `iv` | 3 |
| `meta_analysis` | 11 |
| `ols` | 46 |
| `rct` | 3 |
| `review` | 328 |
| `structural_model` | 53 |
| **Total** | **444** |

All 440 tier histograms also sum correctly, but only 62 match the retained adjudication
tiers. No design histogram has an `unknown` bin in the entire 15,945-row table. An
`unknown` **evidence class** must not be counted by searching for an `unknown` **design**
bin. All 444 raw generic labels are `unknown`; this does not establish that they were
extractor judgments, and it is not used to close the parameter-provenance debt.

Histograms are marginal counts, not a per-claim confidence-input record. The actual family
producer (`src/polisyos/data_forge/domains/academic/batch/edge_synthesize.py:432`) constructs
each `ArticleEvidence` from evidence strength, evidence-row confidence, publication year,
sample size, source basis, retraction, and FWCI. It increments design/tier histograms
separately at `:443`–`:446`; neither histogram enters `aggregate_edge_confidence` at `:495`.
All 444 nominated claim IDs are absent from the current exact-evidence table. Across the
whole family population, 8,790 of 16,658 claim references are absent there. In particular,
the original per-evidence confidence and its association with historical input classes
cannot simply be fetched from that table. Raw/adjudication values are not silently
substituted for the missing evidence inputs.

The complete walk finds 255 groups of family rows with identical design/tier histograms,
claim/article counts, direction, and strongest class but different stored confidences;
14 such groups occur within the 440. For example, unknown family rows
`e80d649297149c686d5de851` and `582514eb35cbc03876dc7439` both have one review claim,
tier 4, one article, and positive direction, but stored confidence is respectively
`0.017749079741729012` and `0.09986303023899068`. This falsifies reconstruction of the
**old numeric confidence from those histogram fields alone**. It does not falsify a
current-rule zero result; HC-F09 explicitly checks that boundary.

The contested table has no design/tier histograms of its own. For all **18/18** nominated
contested rows, every `quality_signals_json.family_edge_ids` reference resolves, all
referenced family strongest classes are `unknown`, and the union of family claim IDs equals
the contested claim IDs exactly. Thus the family layer supplies the retained membership
structure for the entire nominated contested cohort.

### HC-F09 — missing replay inputs do not prevent the unknown-only zero result

`_build/historical-cohorts/phase5_zero_boundary.py` imports and runs the real pure
`aggregate_edge_confidence`, `weighted_direction_summary`, `strongest_strength`, and
ranking/weight owners from this worktree. It never invokes a data pass. The complete
10-member weight catalogue establishes that every positive-base class outranks `unknown`;
an input with any such class cannot produce a strongest-class summary of `unknown` under
the retained selection rule. Unknown now has base weight zero. This is a property of the
actual strength-selection and confidence functions, not a histogram-column-name inference.

For a **current-policy interpretation that holds the stored `unknown` classifications
fixed**, all admissible unknown-only input sets therefore have empty positive-base support.
The current aggregator filters noncontributors *before* both noisy-OR and the replication
bonus and returns zero (`skg_store.py:514`–`:556`). The missing extraction-confidence,
publication-year, sample-size, source-basis, retraction, and FWCI inputs cannot change this
result. This does not recover those inputs or establish the truth of the class judgment.

The probe exercises all 440 family row structures twice with deliberately different
synthetic nuisance inputs, explicitly not attributed to the missing historical evidence:
zero confidence/old publication/missing sample/abstract/retracted/zero FWCI, then confidence
one/current-year/large sample/full text/not retracted/large FWCI. Both produce **440 zeros**.
The current function's early exclusion explains invariance beyond these two examples.

For the contested half, the probe extracts and executes the actual pure row-building loop
of `run_edge_synthesize` at `edge_synthesize.py:517`–`:581` using AST. It asserts that the
selected loop contains no `con`, `config`, or `resolver` references. Schema setup,
canonicalization, the writer entry point, and all persistence statements remain unexecuted.
Using the complete retained family membership for each of the 18 contested rows, both
nuisance variants produce zero direction weights and **zero emitted contested rows**.
The result is removal from the current contested projection, not a numeric replacement of
stored 0.15 with zero: the emission predicate at `:530`–`:537` fails before the 0.15 floor
at `:543` can be evaluated. A separate synthetic positive-base theoretical control through
the same loop emits all 18 row structures, proving this is not an empty or skipped loop.
No stored unknown is reclassified as theoretical by that control.

**Sufficiency answer:** the design/tier histograms are not a general replay basis, and do
not make the original inputs recoverable. Nevertheless, the retained strongest classes
plus the reconciled family membership are sufficient for this bounded current-rule
interpretation: **440 family confidences become zero; 18 contested rows cease to qualify**.
The result does not need the design histograms to license new evidence classes. It neither
recomputes mixed aggregates nor claims a full historical data-pass replay. No new numeric
dataset, source evidence, judgment, snapshot, or product projection has been produced.

This reaches the **property** behind the requested recomputability scope stop, although the
decisive reason is the zero-contribution rule rather than histogram richness. Stopping only
when a particular histogram supplied the answer would turn that rule into a P38 proxy.
The architect should rule on whether a read-time current-rule interpretation, retaining
stored values for audit, belongs beside the proposed withdrawal marker. No implementation
is admitted before that ruling.

### HC-F10 — one bounded wider-family measurement

The same complete walk confirms **6,421/15,945** family rows with strongest class
`observational`, versus **365/7,607** exact rows. The family observational rows refer to
6,594 distinct claims, of which 6,231 are absent from the current exact-evidence table;
only 361 of those family rows reference any current exact evidence. Therefore the family
population is wider than published exact evidence; neither 374 nor 365 is its denominator.

Across all family rows, a Python claim-reference walk and an independent SQL `json_each`
join agree on **1,030** rows with at least one raw generic `unknown` reference:
440 strongest-unknown, 461 quasi-natural, 60 observational, 35 RCT, 20 quasi-natural-event,
12 meta-analysis, one panel-FE, and one structural. The eight counts sum to 1,030; 590
are outside the nominated 440. HC-F02's separately measured 48 contested rows with such
lineage, including 30 outside the nominated 18, remains inherited evidence, not a new
census performed here.

This is **lineage exposure**, not an independently established count of numeric unknown
contributions in mixed aggregates. The raw generic label is not the missing historical
per-evidence value, design histograms do not record that value, and strongest-label
selection hides weaker inputs. No 590/30 rows are added to the repair cohort on that
proxy, and the existing claim-lineage disjointness result is unchanged. Their contribution
amounts and an exhaustive mixed-aggregate affected denominator remain `not_established`.

## Event 6 — fork argument, named residual, and scope stop, 2026-09-05

### HC-D01 — argument at the corrected boundary

For the manufactured-class **342**, **(b-derived) is feasible and justified**. I agree with
the architect's GY-CR5 distinction. A marker can be derived from the stored evidence class
and the joined adjudication under the accepted HC-F03 reconciliation; its basis is the
observed contradiction and the retired credibility-fallback relation. It need not rely on
the producer declaring its own provenance, nor establish the hash of a historical generator
invocation to identify this byte-level condition. It should claim that condition, not an
unrecorded invocation or independent validation of the underlying paper. The 7,526 faithful
translations should not receive the manufactured-design marker merely for matching the
other branch of the retired mapper.

For the **458** selected summaries, a withdrawal marker is also a bounded, read-derived
description of positive historical confidence under a recorded unknown-only summary. But
HC-F09 now demonstrates more than marking: a current-rule interpretation of those retained
classes is numerically determinate for family rows and changes contested membership. This
is the new choice the user reserved for a ruling before building. The joint decision cannot
be frozen as “histograms insufficient, therefore marker only”: that would be false precisely
at the zero-weight boundary. **The continuation stops here.** There is no Phase-6 marker
design commit, no Phase-7 code, and no red/green implementation claim.

**(a)** remains necessary for recovering/replacing missing source judgments or undertaking
a full authorized data pass; none is run or selected here. **(b-stored)** would place a
marker in persisted rows so SQL and byte-copy paths can carry it, but writing the pinned
snapshot is unauthorized; none is run or selected here. Neither is required merely to
compute the byte-derived marker or the limited current-policy interpretation above.

The existing `generation_basis.py` comparison is useful in purpose but is not an existing
historical inference mechanism. HC-F05 established that its current SKG receipt binds
schema/ALTER bytes, not these value-generation rules. It must not be retrospectively
stamped as a recorded generation receipt. B-1's value-beside-status separation is compatible
with a future separate withdrawal signal; B-2's `not_established` storage encoding is not
an encoding for a value that was computed under a withdrawn rule. Stored values and their
computed status must remain distinguishable from never-established evidence.

Nothing here supplies per-parameter value origins, changes parameter serialization, or
distinguishes a parameter extractor judgment from normalization or rescue. The proposed
edge-summary inference would **not** close
`parameter-evidence-strength-has-no-value-provenance`; no scope expansion into that row is
proposed. In particular, the 444 raw generic `unknown` labels are not promoted into a
judged-unknown cohort.

### HC-R01 — exact consumer boundary of the proposed partial marking

HC-F04's executed reach measurement stands. A marker added to the SKG query projection
could travel beside the stored class/confidence through edge support and prior results.
That would let a consumer of the enriched result identify the withdrawn rule without a
journal. It would not automatically reach every downstream number. The following residual
paths were re-read at this continuation's unchanged source revision:

| Consumer or copy path | Concrete residual for a query-only marker |
| --- | --- |
| `src/polisyos/runtime/quality/capability_index_compiler.py:881` | Opens DuckDB directly and selects exact confidence/class plus transport/contested joins; never calls the SKG query projection. |
| `src/polisyos/runtime/quality/credal_reference.py:839` | Direct SQL exact reader; family reader at `:856` and contested reader at `:899` likewise bypass the projection and forward confidence/weight data into derivations. |
| `src/polisyos/data_forge/domains/academic/batch/best_snapshot.py:925` | `_replace_table_contents` copies shared stored columns, without any query-derived annotation. |
| `tools/ops_runners/cloud/merge_shards.py:244` | Attaches shard DBs read-only, then copies table rows; an annotation that exists only in a query result is absent from copied bytes. |
| `src/polisyos/foundry/methods/catalog/causal/literature_prior.py:232` | Constructs `LiteratureEdgePrior` from selected values/status/confidence and article references; an extra query quality signal is not automatically copied into that DTO. Default threshold 0.2 excludes the 440, but configurable lower thresholds matter (HC-F04). |

The Scientist prior miner at
`src/polisyos/scientist/methods/discovery/prior_miner.py:103` carries query quality signals
in its support record, but no after-marker propagation has been implemented or tested.
These anchors name the residual; they are not a claim of universal terminal-consumer
coverage. HC-F04's complete source census also enumerates benchmark, transport, retraction,
inventory, and forecast references, and does not equate a literal hit with execution.

The practical value of partial marking is honest detection at the SKG result boundary.
The practical limit is that direct SQL, copied databases, and a downstream DTO which drops
the signal can still forward the value without it. A future partial repair must keep that
residual registered in the open row. No current reader changed in this continuation.

### HC-P01 — pattern and stop-rule pass

- **P35/P36:** counts are full walks of the six named DuckDB tables with SQL count and
  grouped-JSON cross-checks. Accepted HC-F03 is cited, not re-derived. HC-F06 corrects the
  inference from its membership count to defect severity.
- **P37/GY-CR5:** branch contradiction and join coverage are `recomputed`/`independently_reconciled`
  from stored bytes; the current-rule zero boundary is `recomputed` from the real function.
  Original missing per-evidence inputs and exact generator invocation remain
  `not_established`. The inference does not confer authority on those missing facts.
- **P38:** neither mapper membership nor presence of histogram columns decides the defect
  or recomputability. Identical histograms can have different old confidence, yet all
  unknown-only inputs have the same current zero result. The stop is keyed to that measured
  property, not to which named column made it visible.
- **P07/P31:** no claim of a complete historical replay or universal marker is made.
  Query-only marking would leave the named SQL/copy/projection residual. As of this stop,
  withdrawal marking remains `producer_missing` and its consumer/surface chain is not built.
- **P40:** no product implementation or fix round occurred. This is a pre-design measurement
  result, not a second same-class implementation escape. The one-fix-round limit is unspent.

The failure/repair register was opened for the continuation and again at closeout. No
register, ledger, plan, source, tool, test, or schema file is edited. The active-plan
transcription remains the architect's work.

### HC-T01-R1 — replace HC-T01 in full; open-row transcription

> **HISTORICAL-COHORTS CONTINUATION 2026-09-05 — stays open; measured scope ruling before implementation.** The manufactured-design cohort is 342 credibility-fallback evidence rows; the additional 7,526 retired-mapper matches are recoverable, lossy-but-faithful translations of retained adjudications and do not enlarge that defect cohort (HC-F06/HC-F07). The separate confidence selection remains 440/15,945 family and 18/723 contested rows. Family design histograms retain all 444 nominated claim designs, but do not retain general confidence-replay inputs; those claims' exact-evidence rows are absent. Nevertheless, holding the stored `unknown` classes fixed makes the current-rule result determinate: all 440 family confidences are zero, and all 18 contested rows fail the current producer's emission predicate before its 0.15 floor (HC-F08/HC-F09). This is a bounded current-policy interpretation, not recovery of missing source inputs or proof that the unknowns were extractor judgments. The architect must rule on that read-time interpretation before a marker-only design is frozen. No repair or data write occurred. Query-derived marking is defensible from joined bytes, but leaves direct SQL at `runtime/quality/capability_index_compiler.py:881` and `runtime/quality/credal_reference.py:839,856,899`, stored-column copiers at `data_forge/domains/academic/batch/best_snapshot.py:925` and `tools/ops_runners/cloud/merge_shards.py:244`, and the downstream prior DTO at `foundry/methods/catalog/causal/literature_prior.py:232` outside its automatic reach (HC-R01). The wider raw-unknown lineage is not a measured census of numeric contributions in mixed aggregates (HC-F10). Preserve that residual and the distinction from `not_established`; do not transcribe a universal marker or historical re-derivation as completed.

### HC-T02-R1 — replace HC-T02 in full; closed-row transcription

> **HISTORICAL-COHORTS CONTINUATION 2026-09-05 — remains closed for the forward repair; historical severity boundary corrected.** 342 is the correct manufactured empirical-design cohort: the retained adjudications are unclear (187), theoretical (131), or review (24), while the stored evidence class is observational. An independent Python/SQL concentration check over all 7,868 evidence rows finds 374 observational rows: 342 credibility fallbacks (91.44385026737967%) and 32 actual `ols` adjudications (HC-F07). The other 7,526 rows also match the retired mapper, but their class translations are lossy and faithful relative to retained adjudications; every fine source design is recoverable through the unique claim-to-adjudication join (HC-F06). Mapper membership is not a defect class, so those 7,526 do not enlarge this debt's historical cohort. Do not recover adjudicated design from the evidence row's `design_family` hint: 488 design-branch hint cells differ from adjudication. The 342 still reach 341 exact-edge summaries and remain unmarked; a marker derived from the joined contradiction survives the self-declaration objection, with the SQL/copy/downstream residual explicitly named in HC-R01. This continuation delivered measurement only and stopped for the confidence cohort's read-time interpretation ruling in HC-F09; it did not reopen or change the substitution repair, reclassify historical data, or implement a marker.

The two `-R1` paragraphs are the **sole replacement transcription text** from this
continuation. Event 1's HC-T01 and HC-T02 remain physically present as append-only history
and must not be concatenated with these replacements in the register.

## Event 7 — reproducible Phase-5 programs and observations, 2026-09-05

Only ignored `_build/historical-cohorts/` scratch files were used for measurement. The
complete programs below make the journal independently reproducible without relying on
uncommitted scratch. All production-data connections are explicitly read-only. No data
producer entry point is invoked. The two commands completed successfully; these are
measurement probes, not red/green evidence for a product implementation.

```sh
cd /Users/deniskopylov/polisyos/.worktrees/debt-historical-cohorts/policy-engine
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/historical-cohorts/phase5.py > _build/historical-cohorts/phase5.log
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/historical-cohorts/phase5_zero_boundary.py > _build/historical-cohorts/phase5_zero_boundary.log
```

### Program: phase5.py

SHA-256: `775d6149eb0ce4104c5ae4ca07acf58fa1a138ae7a8bce2f7a6fd4b09bb329c6`.

```python
"""Phase 5: read-only severity/recoverability census, not a data pass."""
from collections import Counter, defaultdict
from pathlib import Path
import json
import duckdb

DB = Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
OUT = Path('_build/historical-cohorts')
con = duckdb.connect(str(DB), read_only=True)

def emit(name, value):
    print(name, json.dumps(value, sort_keys=True, default=str), flush=True)

def rows(table):
    cursor = con.execute('SELECT * FROM ' + table)
    names = [col[0] for col in cursor.description]
    data = [dict(zip(names, row)) for row in cursor.fetchall()]
    assert len(data) == con.execute('SELECT count(*) FROM ' + table).fetchone()[0]
    return data

def hist(row, key):
    data = json.loads(row[key] or '{}')
    assert isinstance(data, dict)
    assert all(isinstance(k, str) and type(v) is int and v > 0 for k, v in data.items())
    return Counter(data)

def refs(row):
    return set(json.loads(row['claim_refs']))

E = rows('ac_skg_edge_evidence')
A_rows = rows('ac_claim_adjudications')
A = {r['claim_id']: r for r in A_rows}
assert len(A) == len(A_rows)
R_rows = rows('ac_causal_claims_raw')
R = {r['id']: r for r in R_rows}
assert len(R) == len(R_rows)
F = rows('ac_skg_family_edges')
C = rows('ac_skg_contested_edges')
X = rows('ac_skg_edges')
# Select the ACCEPTED credibility branch for the new severity census. Do not
# execute or re-reconcile the retired mapper (HC-F03 is already accepted).
fallback_ids = {r['claim_id'] for r in E if
    A[r['claim_id']]['design_family'] in {'unclear','theoretical','review'}
    and A[r['claim_id']]['causal_credibility'] in {'strong','moderate'}}
branch = [r for r in E if r['claim_id'] not in fallback_ids]
fallback = [r for r in E if r['claim_id'] in fallback_ids]
emit('denominator', {name: len(data) for name, data in [('evidence',E),('adjudications',A_rows),('raw',R_rows),('exact',X),('family',F),('contested',C)]})

groups = Counter((A[r['claim_id']]['design_family'], r['evidence_strength']) for r in branch)
by_class = defaultdict(set)
for design, strength in groups:
    by_class[strength].add(design)
emit('design_branch_recoverability', dict(
    rows=len(branch), unique_claim_ids=len({r['claim_id'] for r in branch}),
    missing_adjudications=sum(r['claim_id'] not in A for r in branch),
    source_design_missing=sum(not A[r['claim_id']]['design_family'] for r in branch),
    evidence_design_disagrees_with_adjudication=sum(r['design_family'] != A[r['claim_id']]['design_family'] for r in branch),
    evidence_design_disagrees_with_raw_hint=sum(r['design_family'] != R[r['claim_id']]['design_family_hint'] for r in branch),
    source_design_by_stored_class=[dict(design_family=k[0], stored_class=k[1], n=v) for k,v in sorted(groups.items())],
    multiple_source_designs_per_stored_class={k:sorted(v) for k,v in by_class.items() if len(v)>1},
    credibility_distribution=dict(Counter(A[r['claim_id']]['causal_credibility'] for r in branch)),
))
observational = [r for r in E if r['evidence_strength'] == 'observational']
concentration = Counter((A[r['claim_id']]['design_family'], A[r['claim_id']]['causal_credibility']) for r in observational)
sql_concentration = con.execute("""
SELECT a.design_family, a.causal_credibility, count(*)
FROM ac_skg_edge_evidence e JOIN ac_claim_adjudications a ON a.claim_id=e.claim_id
WHERE e.evidence_strength='observational' GROUP BY 1,2 ORDER BY 1,2
""").fetchall()
assert concentration == Counter({(d,c):n for d,c,n in sql_concentration})
emit('observational_concentration', dict(
    denominator=len(E), observational=len(observational),
    fallback=sum(r['claim_id'] in fallback_ids for r in observational),
    actual_ols=sum(A[r['claim_id']]['design_family']=='ols' for r in observational),
    fallback_percent=100*sum(r['claim_id'] in fallback_ids for r in observational)/len(observational),
    sql_cross_check=sql_concentration,
    theoretical_inversions=sum(A[r['claim_id']]['design_family']=='theoretical' for r in fallback),
))

evidence_ids = {r['claim_id'] for r in E}
family_by_id = {r['family_edge_id']:r for r in F}
for label, data in [('all',F),('strongest_unknown',[r for r in F if r['evidence_strength']=='unknown']),('strongest_observational',[r for r in F if r['evidence_strength']=='observational'])]:
    designs = Counter()
    tiers = Counter()
    all_refs = set()
    cov = Counter()
    collisions = defaultdict(list)
    for row in data:
        dh,th = hist(row,'design_family_histogram_json'),hist(row,'design_tier_histogram_json')
        rr = refs(row)
        assert len(rr) == row['n_claims']
        designs.update(dh); tiers.update(th); all_refs.update(rr)
        cov['design_counts_equal_n_claims'] += sum(dh.values()) == row['n_claims']
        cov['tier_counts_equal_n_claims'] += sum(th.values()) == row['n_claims']
        cov['has_unknown_design_bin'] += dh['unknown'] > 0
        cov['has_unclear_design_bin'] += dh['unclear'] > 0
        cov['has_retained_raw_unknown'] += any(R[x]['strength']=='unknown' for x in rr)
        cov['all_refs_have_adjudication'] += rr <= A.keys()
        cov['all_refs_have_exact_evidence'] += rr <= evidence_ids
        cov['any_ref_has_exact_evidence'] += bool(rr & evidence_ids)
        cov['has_accepted_342_lineage'] += bool(rr & fallback_ids)
        if rr <= A.keys():
            ad = Counter(A[x]['design_family'] for x in rr if A[x]['design_family'])
            at = Counter(str(A[x]['design_quality_tier']) for x in rr if A[x]['design_quality_tier'] is not None)
            cov['design_hist_matches_retained_adjudications'] += dh == ad
            cov['tier_hist_matches_retained_adjudications'] += th == at
        key = (tuple(sorted(dh.items())),tuple(sorted(th.items())),row['n_claims'],row['n_articles'],row['direction'],row['evidence_strength'])
        collisions[key].append(row)
    distinct = [v for v in collisions.values() if len({r['confidence'] for r in v})>1]
    witness = []
    if distinct:
        vv = sorted(distinct,key=lambda v:len(v),reverse=True)[0]
        witness = [min(vv,key=lambda r:r['confidence']),max(vv,key=lambda r:r['confidence'])]
    emit('family_histograms_'+label, dict(
        rows=len(data), n_claims_sum=sum(r['n_claims'] for r in data),distinct_claim_refs=len(all_refs),
        n_claims_distribution=dict(Counter(r['n_claims'] for r in data)),
        design_bins=dict(designs), tier_bins=dict(tiers),row_measures=dict(cov),
        refs_missing_raw=len(all_refs-R.keys()), refs_missing_adjudication=len(all_refs-A.keys()),refs_missing_exact_evidence=len(all_refs-evidence_ids),
        exact_evidence_confidence_cannot_be_looked_up_for=len(all_refs-evidence_ids),
        retained_raw_strengths=dict(Counter(R[x]['strength'] for x in all_refs)),
        retained_adjudicated_designs=dict(Counter(A[x]['design_family'] for x in all_refs if x in A)),
        identical_histograms_counts_direction_strength_but_different_confidence_groups=len(distinct),
        witness=[{k:r[k] for k in ['family_edge_id','n_claims','n_articles','direction','evidence_strength','confidence','design_family_histogram_json','design_tier_histogram_json','claim_refs']} for r in witness],
    ))

sql_hist = con.execute("""
SELECT f.evidence_strength, j.key, sum(CAST(j.value AS BIGINT))
FROM ac_skg_family_edges f, json_each(f.design_family_histogram_json) j
GROUP BY 1,2 ORDER BY 1,2
""").fetchall()
py_hist = Counter()
for r in F:
    for k,v in hist(r,'design_family_histogram_json').items():
        py_hist[r['evidence_strength'],k] += v
assert py_hist == Counter({(s,k):v for s,k,v in sql_hist})
emit('histogram_sql_cross_check',dict(groups=len(sql_hist), design_memberships=sum(v for _,_,v in sql_hist), identity_disagreements=0))

unknown_C = [r for r in C if r['evidence_strength']=='unknown']
cov = Counter()
for row in unknown_C:
    source_ids=set(json.loads(row['quality_signals_json'])['family_edge_ids'])
    source_rows=[family_by_id[x] for x in source_ids if x in family_by_id]
    cov['all_family_ids_present'] += source_ids <= family_by_id.keys()
    cov['source_family_labels_all_unknown'] += bool(source_rows) and all(r['evidence_strength']=='unknown' for r in source_rows)
    cov['family_claim_refs_cover_contested_exactly'] += (set().union(*(refs(r) for r in source_rows)) if source_rows else set()) == refs(row)
emit('contested_histogram_reach',dict(rows=len(unknown_C),own_design_histogram_column='design_family_histogram_json' in C[0],measures=dict(cov)))

sql_wider = con.execute("""
SELECT f.evidence_strength, count(DISTINCT f.family_edge_id)
FROM ac_skg_family_edges f, json_each(f.claim_refs) j
JOIN ac_causal_claims_raw r ON r.id=json_extract_string(j.value,'$')
WHERE r.strength='unknown' GROUP BY 1 ORDER BY 1
""").fetchall()
py_wider=Counter(r['evidence_strength'] for r in F if any(R[x]['strength']=='unknown' for x in refs(r)))
assert dict(sql_wider)==py_wider
emit('wider_family_population',dict(
    family_rows=len(F),exact_rows=len(X),
    family_observational=sum(r['evidence_strength']=='observational' for r in F),
    exact_observational=sum(r['evidence_strength']=='observational' for r in X),
    raw_unknown_lineage_by_family_strongest_class=dict(py_wider),
    total_family_claim_memberships=sum(r['n_claims'] for r in F),
    family_distinct_refs=len(set().union(*(refs(r) for r in F))),
))
con.close()
```

Complete successful output:

```text
denominator {"adjudications": 67791, "contested": 723, "evidence": 7868, "exact": 7607, "family": 15945, "raw": 137589}
design_branch_recoverability {"credibility_distribution": {"moderate": 6994, "strong": 532}, "evidence_design_disagrees_with_adjudication": 488, "evidence_design_disagrees_with_raw_hint": 0, "missing_adjudications": 0, "multiple_source_designs_per_stored_class": {"quasi_natural": ["did", "iv", "rdd", "synthetic_control"], "quasi_natural_event": ["event_study", "quasi_experimental_other"]}, "rows": 7526, "source_design_by_stored_class": [{"design_family": "did", "n": 325, "stored_class": "quasi_natural"}, {"design_family": "event_study", "n": 28, "stored_class": "quasi_natural_event"}, {"design_family": "iv", "n": 3751, "stored_class": "quasi_natural"}, {"design_family": "meta_analysis", "n": 1095, "stored_class": "meta_analysis"}, {"design_family": "ols", "n": 32, "stored_class": "observational"}, {"design_family": "panel_fe", "n": 793, "stored_class": "panel_fe"}, {"design_family": "quasi_experimental_other", "n": 498, "stored_class": "quasi_natural_event"}, {"design_family": "rct", "n": 954, "stored_class": "rct"}, {"design_family": "rdd", "n": 21, "stored_class": "quasi_natural"}, {"design_family": "structural_model", "n": 4, "stored_class": "structural"}, {"design_family": "synthetic_control", "n": 25, "stored_class": "quasi_natural"}], "source_design_missing": 0, "unique_claim_ids": 7526}
observational_concentration {"actual_ols": 32, "denominator": 7868, "fallback": 342, "fallback_percent": 91.44385026737967, "observational": 374, "sql_cross_check": [["ols", "moderate", 32], ["review", "moderate", 24], ["theoretical", "moderate", 127], ["theoretical", "strong", 4], ["unclear", "moderate", 163], ["unclear", "strong", 24]], "theoretical_inversions": 131}
family_histograms_all {"design_bins": {"did": 245, "event_study": 34, "iv": 3831, "meta_analysis": 2094, "ols": 4441, "panel_fe": 1268, "quasi_experimental_other": 700, "rct": 874, "rdd": 19, "review": 2356, "structural_model": 236, "synthetic_control": 10, "theoretical": 79, "unclear": 471}, "distinct_claim_refs": 16658, "exact_evidence_confidence_cannot_be_looked_up_for": 8790, "identical_histograms_counts_direction_strength_but_different_confidence_groups": 255, "n_claims_distribution": {"1": 15449, "2": 384, "3": 67, "4": 26, "5": 9, "6": 3, "7": 2, "8": 2, "10": 1, "12": 1, "21": 1}, "n_claims_sum": 16658, "refs_missing_adjudication": 0, "refs_missing_exact_evidence": 8790, "refs_missing_raw": 0, "retained_adjudicated_designs": {"did": 344, "event_study": 32, "iv": 3802, "meta_analysis": 2180, "ols": 4465, "panel_fe": 1295, "quasi_experimental_other": 559, "rct": 1021, "rdd": 21, "review": 2372, "structural_model": 220, "synthetic_control": 29, "theoretical": 131, "unclear": 187}, "retained_raw_strengths": {"cross_sectional": 2, "meta_analysis": 3418, "observational": 9021, "panel_fe": 251, "quasi_natural": 1476, "rct": 880, "theoretical": 564, "unknown": 1046}, "row_measures": {"all_refs_have_adjudication": 15945, "all_refs_have_exact_evidence": 7436, "any_ref_has_exact_evidence": 7592, "design_counts_equal_n_claims": 15945, "design_hist_matches_retained_adjudications": 15395, "has_accepted_342_lineage": 341, "has_retained_raw_unknown": 1030, "has_unclear_design_bin": 465, "has_unknown_design_bin": 0, "tier_counts_equal_n_claims": 15656, "tier_hist_matches_retained_adjudications": 7834}, "rows": 15945, "tier_bins": {"1": 5988, "2": 1236, "3": 5435, "4": 3709}, "witness": [{"claim_refs": "[\"f420df98b564cb11a05f97f6\"]", "confidence": 0.011471045816805248, "design_family_histogram_json": "{\"ols\": 1}", "design_tier_histogram_json": "{\"3\": 1}", "direction": "positive", "evidence_strength": "observational", "family_edge_id": "d0690e206a23bc454ee2c706", "n_articles": 1, "n_claims": 1}, {"claim_refs": "[\"74e8d104dc45099868346811\"]", "confidence": 0.2736119324427766, "design_family_histogram_json": "{\"ols\": 1}", "design_tier_histogram_json": "{\"3\": 1}", "direction": "positive", "evidence_strength": "observational", "family_edge_id": "2568c66e0759d98c41adf689", "n_articles": 1, "n_claims": 1}]}
family_histograms_strongest_unknown {"design_bins": {"iv": 3, "meta_analysis": 11, "ols": 46, "rct": 3, "review": 328, "structural_model": 53}, "distinct_claim_refs": 444, "exact_evidence_confidence_cannot_be_looked_up_for": 444, "identical_histograms_counts_direction_strength_but_different_confidence_groups": 14, "n_claims_distribution": {"1": 436, "2": 4}, "n_claims_sum": 444, "refs_missing_adjudication": 0, "refs_missing_exact_evidence": 444, "refs_missing_raw": 0, "retained_adjudicated_designs": {"iv": 3, "meta_analysis": 11, "ols": 46, "rct": 3, "review": 328, "structural_model": 53}, "retained_raw_strengths": {"unknown": 444}, "row_measures": {"all_refs_have_adjudication": 440, "all_refs_have_exact_evidence": 0, "any_ref_has_exact_evidence": 0, "design_counts_equal_n_claims": 440, "design_hist_matches_retained_adjudications": 440, "has_accepted_342_lineage": 0, "has_retained_raw_unknown": 440, "has_unclear_design_bin": 0, "has_unknown_design_bin": 0, "tier_counts_equal_n_claims": 440, "tier_hist_matches_retained_adjudications": 62}, "rows": 440, "tier_bins": {"1": 6, "3": 99, "4": 339}, "witness": [{"claim_refs": "[\"e88dd94a57c16915cd64d0fb\"]", "confidence": 0.017749079741729012, "design_family_histogram_json": "{\"review\": 1}", "design_tier_histogram_json": "{\"4\": 1}", "direction": "positive", "evidence_strength": "unknown", "family_edge_id": "e80d649297149c686d5de851", "n_articles": 1, "n_claims": 1}, {"claim_refs": "[\"331e7bf16e526d5cb32aceed\"]", "confidence": 0.09986303023899068, "design_family_histogram_json": "{\"review\": 1}", "design_tier_histogram_json": "{\"4\": 1}", "direction": "positive", "evidence_strength": "unknown", "family_edge_id": "582514eb35cbc03876dc7439", "n_articles": 1, "n_claims": 1}]}
family_histograms_strongest_observational {"design_bins": {"did": 7, "event_study": 3, "iv": 45, "meta_analysis": 116, "ols": 4170, "panel_fe": 262, "quasi_experimental_other": 14, "rct": 16, "review": 1473, "structural_model": 169, "synthetic_control": 1, "theoretical": 71, "unclear": 247}, "distinct_claim_refs": 6594, "exact_evidence_confidence_cannot_be_looked_up_for": 6231, "identical_histograms_counts_direction_strength_but_different_confidence_groups": 63, "n_claims_distribution": {"1": 6291, "2": 108, "3": 11, "4": 5, "5": 4, "7": 2}, "n_claims_sum": 6594, "refs_missing_adjudication": 0, "refs_missing_exact_evidence": 6231, "refs_missing_raw": 0, "retained_adjudicated_designs": {"did": 3, "event_study": 3, "iv": 36, "meta_analysis": 116, "ols": 4197, "panel_fe": 261, "quasi_experimental_other": 7, "rct": 15, "review": 1488, "structural_model": 157, "synthetic_control": 1, "theoretical": 128, "unclear": 182}, "retained_raw_strengths": {"meta_analysis": 2, "observational": 6386, "panel_fe": 1, "quasi_natural": 64, "rct": 2, "theoretical": 79, "unknown": 60}, "row_measures": {"all_refs_have_adjudication": 6421, "all_refs_have_exact_evidence": 358, "any_ref_has_exact_evidence": 361, "design_counts_equal_n_claims": 6421, "design_hist_matches_retained_adjudications": 6319, "has_accepted_342_lineage": 331, "has_retained_raw_unknown": 60, "has_unclear_design_bin": 246, "has_unknown_design_bin": 0, "tier_counts_equal_n_claims": 6209, "tier_hist_matches_retained_adjudications": 918}, "rows": 6421, "tier_bins": {"1": 69, "2": 278, "3": 4336, "4": 1699}, "witness": [{"claim_refs": "[\"f420df98b564cb11a05f97f6\"]", "confidence": 0.011471045816805248, "design_family_histogram_json": "{\"ols\": 1}", "design_tier_histogram_json": "{\"3\": 1}", "direction": "positive", "evidence_strength": "observational", "family_edge_id": "d0690e206a23bc454ee2c706", "n_articles": 1, "n_claims": 1}, {"claim_refs": "[\"74e8d104dc45099868346811\"]", "confidence": 0.2736119324427766, "design_family_histogram_json": "{\"ols\": 1}", "design_tier_histogram_json": "{\"3\": 1}", "direction": "positive", "evidence_strength": "observational", "family_edge_id": "2568c66e0759d98c41adf689", "n_articles": 1, "n_claims": 1}]}
histogram_sql_cross_check {"design_memberships": 16658, "groups": 74, "identity_disagreements": 0}
contested_histogram_reach {"measures": {"all_family_ids_present": 18, "family_claim_refs_cover_contested_exactly": 18, "source_family_labels_all_unknown": 18}, "own_design_histogram_column": false, "rows": 18}
wider_family_population {"exact_observational": 365, "exact_rows": 7607, "family_distinct_refs": 16658, "family_observational": 6421, "family_rows": 15945, "raw_unknown_lineage_by_family_strongest_class": {"meta_analysis": 12, "observational": 60, "panel_fe": 1, "quasi_natural": 461, "quasi_natural_event": 20, "rct": 35, "structural": 1, "unknown": 440}, "total_family_claim_memberships": 16658}
```

### Program: phase5_zero_boundary.py

SHA-256: `bb77890450b14c03b62a231d3d0ff4d3fca3c3bc3afb72cb971fdedd0940769e`.

```python
"""Pure current-rule counterfactual; no writer or production-data mutation."""
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
import ast
import hashlib
import json
import duckdb

from polisyos.data_forge.domains.academic.knowledge import skg_store as owner

DB = Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
PRODUCER = Path('src/polisyos/data_forge/domains/academic/batch/edge_synthesize.py')
con = duckdb.connect(str(DB), read_only=True)

def emit(name, value):
    print(name, json.dumps(value, sort_keys=True, default=str), flush=True)

def rows(table):
    cur = con.execute('SELECT * FROM '+table)
    cols = [c[0] for c in cur.description]
    data = [dict(zip(cols,r)) for r in cur.fetchall()]
    assert len(data) == con.execute('SELECT count(*) FROM '+table).fetchone()[0]
    return data

F = rows('ac_skg_family_edges')
C = rows('ac_skg_contested_edges')
FU = [r for r in F if r['evidence_strength']=='unknown']
CU = [r for r in C if r['evidence_strength']=='unknown']
FM = {r['family_edge_id']:r for r in F}

# The confidence-relevant vocabulary is derived from the real weight owner.
# Every positive-base value would outrank a stored strongest class of unknown.
catalogue = [(s,w,owner.strongest_strength(['unknown',s]),owner.edge_strength_rank(s)) for s,w in owner.EVIDENCE_WEIGHTS.items()]
assert all(best != 'unknown' and rank > 0 for s,w,best,rank in catalogue if w>0)
assert owner.EVIDENCE_WEIGHTS['unknown']==0.0
emit('positive_weight_strongest_boundary',dict(catalogue=catalogue,owner_path=owner.__file__,owner_sha256=hashlib.sha256(Path(owner.__file__).read_bytes()).hexdigest()))

# Paired arbitrary nuisance inputs, explicitly NOT recovered source values.
# They are irrelevant once the retained evidence strength is unknown.
variants = [
    dict(extraction_confidence=0.0, publication_year=1900, sample_size=None,source_basis='abstract_only',retracted=True,fwci=0.0),
    dict(extraction_confidence=1.0, publication_year=2026, sample_size=100000,source_basis='fulltext',retracted=False,fwci=100.0),
]
family_summary = []
for nuisance in variants:
    outputs = [owner.aggregate_edge_confidence([owner.ArticleEvidence(strength='unknown',**nuisance) for _ in range(r['n_claims'])]) for r in FU]
    assert set(outputs)=={0.0}
    family_summary.append(dict(nuisance=nuisance,rows=len(outputs),outputs=dict(Counter(outputs))))
emit('unknown_only_family_current_policy',dict(rows=len(FU),distinct_claim_refs=len(set().union(*(set(json.loads(r['claim_refs'])) for r in FU))),variants=family_summary))

# Execute the CURRENT producer's real, unedited contested-row loop only.
# AST extraction is restricted to the pure loop before the first DELETE;
# run_edge_synthesize, schema setup, canonicalization and persistence never run.
source=PRODUCER.read_text()
fn=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='run_edge_synthesize')
loops=[n for n in ast.walk(fn) if isinstance(n,ast.For) and isinstance(n.iter,ast.Call) and isinstance(n.iter.func,ast.Name) and n.iter.func.id=='sorted' and any(isinstance(x,ast.Name) and x.id=='pair_totals' for x in ast.walk(n.iter))]
assert len(loops)==1
loop=loops[0]
assert not any(isinstance(n,ast.Name) and n.id in {'con','config','resolver'} for n in ast.walk(loop))
module=ast.fix_missing_locations(ast.Module(body=[loop],type_ignores=[]))
compiled=compile(module,str(PRODUCER),'exec')
emit('pure_contested_loop',dict(path=str(PRODUCER),start=loop.lineno,end=loop.end_lineno,source_sha256=hashlib.sha256(PRODUCER.read_bytes()).hexdigest()))

def pair_payload(row,nuisance,*,strength_override=None):
    quality=json.loads(row['quality_signals_json'])
    fs=[FM[k] for k in quality['family_edge_ids']]
    assert fs and all(f['evidence_strength']=='unknown' for f in fs)
    assert set().union(*(set(json.loads(f['claim_refs'])) for f in fs))==set(json.loads(row['claim_refs']))
    direction_evidence=defaultdict(list)
    for f in fs:
        direction_evidence[f['direction']].extend(owner.ArticleEvidence(strength=strength_override or f['evidence_strength'],**nuisance) for _ in json.loads(f['claim_refs']))
    samples=[s for ss in direction_evidence.values() for s in ss]
    return dict(direction_histogram=json.loads(row['direction_histogram_json']),article_refs=json.loads(row['article_refs']),claim_refs=json.loads(row['claim_refs']),evidence_samples=samples,strengths=[s.strength for s in samples],direction_evidence=direction_evidence,exact_edge_ids=quality['exact_edge_ids'],family_edge_ids=quality['family_edge_ids'])

for i,nuisance in enumerate(variants):
    pairs={(r['src_family'],r['dst_family']):pair_payload(r,nuisance) for r in CU}
    assert len(pairs)==len(CU)
    env=dict(pair_totals=pairs,contested_rows=[],json=json,weighted_direction_summary=owner.weighted_direction_summary,aggregate_edge_confidence=owner.aggregate_edge_confidence,hash_contested_edge_id=owner.hash_contested_edge_id,strongest_strength=owner.strongest_strength)
    summaries=[owner.weighted_direction_summary(p['direction_evidence']) for p in pairs.values()]
    assert all(not s.is_contested and all(w==0 for w in s.direction_weights.values()) for s in summaries)
    exec(compiled,env)
    assert env['contested_rows']==[]
    emit('unknown_only_contested_current_policy',dict(variant=i,rows=len(CU),weighted_directions_all_zero=len(summaries),emitted_rows=len(env['contested_rows'])))

# Counterfactual positive contribution through the same extracted producer loop:
# theoretical is deliberately used as a distinct positive-base input, never
# retroactively assigned to any stored unknown claim.
pairs={(r['src_family'],r['dst_family']):pair_payload(r,variants[1],strength_override='theoretical') for r in CU}
env=dict(pair_totals=pairs,contested_rows=[],json=json,weighted_direction_summary=owner.weighted_direction_summary,aggregate_edge_confidence=owner.aggregate_edge_confidence,hash_contested_edge_id=owner.hash_contested_edge_id,strongest_strength=owner.strongest_strength)
exec(compiled,env)
assert len(env['contested_rows'])==len(CU)
emit('positive_control',dict(synthetic_input_strength='theoretical',stored_rows_used_for_structure=len(CU),emitted_rows=len(env['contested_rows'])))
con.close()
```

Complete successful output:

```text
positive_weight_strongest_boundary {"catalogue": [["rct", 1.0, "rct", 8], ["meta_analysis", 0.95, "meta_analysis", 7], ["quasi_natural", 0.7, "quasi_natural", 6], ["quasi_natural_event", 0.6, "quasi_natural_event", 5], ["panel_fe", 0.5, "panel_fe", 4], ["structural", 0.45, "structural", 3], ["observational", 0.3, "observational", 2], ["cross_sectional", 0.2, "cross_sectional", 1], ["theoretical", 0.15, "theoretical", 1], ["unknown", 0.0, "unknown", 0]], "owner_path": "/Users/deniskopylov/polisyos/.worktrees/debt-historical-cohorts/policy-engine/src/polisyos/data_forge/domains/academic/knowledge/skg_store.py", "owner_sha256": "aa0edb272ee322025c3334b259c40ce44628c9cf5988e4f885847cc575088de5"}
unknown_only_family_current_policy {"distinct_claim_refs": 444, "rows": 440, "variants": [{"nuisance": {"extraction_confidence": 0.0, "fwci": 0.0, "publication_year": 1900, "retracted": true, "sample_size": null, "source_basis": "abstract_only"}, "outputs": {"0.0": 440}, "rows": 440}, {"nuisance": {"extraction_confidence": 1.0, "fwci": 100.0, "publication_year": 2026, "retracted": false, "sample_size": 100000, "source_basis": "fulltext"}, "outputs": {"0.0": 440}, "rows": 440}]}
pure_contested_loop {"end": 581, "path": "src/polisyos/data_forge/domains/academic/batch/edge_synthesize.py", "source_sha256": "117f3467a7d021aa0aac36e09aab1711f6137ad1a77269754baf576562d1e955", "start": 517}
unknown_only_contested_current_policy {"emitted_rows": 0, "rows": 18, "variant": 0, "weighted_directions_all_zero": 18}
unknown_only_contested_current_policy {"emitted_rows": 0, "rows": 18, "variant": 1, "weighted_directions_all_zero": 18}
positive_control {"emitted_rows": 18, "stored_rows_used_for_structure": 18, "synthetic_input_strength": "theoretical"}
```

## Event 8 — continuation closeout and checker exemption receipt, 2026-09-05

Events 5–7 were committed as `541641d656f0325f5109fa1c11595f8350478ed0` and read back from
that branch; the committed bytes equal the worktree bytes. The first 49,083 bytes (Events
1–4 at `11b24787a`) remain identical. The two embedded measurement programs and their hashes
were checked against the executed scratch files. `git diff --check` passed. No product
implementation was made, so there is no implementation test or red/green claim.

The corrected checker predicate is applied to **checker-read files**, not all tracked
files. This continuation changes only the journal: no register, ledger, plan, tool, source,
test, or schema changed. **Bound debt checker skipped.** The requested command was run
against the committed continuation, with exactly this output:

```sh
git diff --name-only 11b24787a..HEAD
```

```text
policy-engine/docs/superpowers/journals/2026-09-05-historical-cohorts.md
```

The final production-data read after all measurement confirmed the full original SHA-256,
read-only mode, and size below. No producer, copier, live lane, production-data write, or
`chmod` was run. No rebase, force-push, or stash was used.

```text
sha256:583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967
mode: -r--r--r--
size: 2390503424 bytes
```

The observed pre-receipt branch state was `## codex/debt-historical-cohorts`, clean.
The SHA-256 of the committed journal **before this receipt append** was
`cde3ae92037b24eae8d5caa79e062ff8f7baa9cbc488cc7d2c8881ed934660ec`; that hash identifies
Events 1–7, not this subsequent append. This receipt is committed separately and the final
branch/path/append-only checks are repeated after that commit. The disposition remains the
HC-F09 scope stop; the two `-R1` paragraphs replace the old transcription text in full.
