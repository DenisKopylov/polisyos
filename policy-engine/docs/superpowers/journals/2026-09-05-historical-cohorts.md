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

## Event 9 — Phase-6 partition at the current-source boundary, 2026-09-05

Continuation base: `424e8b2ee3a362b6ba18045767d931ad72acfaed`, attached to
`codex/debt-historical-cohorts`, clean on arrival. Events 1–8 remain verbatim. The user
admitted route (c) for consideration, confirmed HC-F09, and reserved the route decision
until this measurement. **No route is chosen and no implementation is made in this round.**

**The exact-layer collapse hypothesis is confirmed, and bucket 2 also covers the complete
family and contested populations.** At the current **source-projection** boundary, all
7,607 exact and 15,945 family confidences compute to zero. All 723 contested rows have
zero current base confidence and zero direction weights, so they fail the current
confidence-based emission predicate. Their current result is **not emitted**, not a
replacement final confidence of zero. The table below distinguishes those results.

HC-F09 held the stored evidence classes fixed and measured the selected 458. This round
instead follows each stored aggregate's retained claim membership through the current B-1
source projection and B-2 evidence-axis encoding before applying the current confidence
functions. That change of boundary explains the larger result; it is not a new assertion
that every historical class was manufactured by the credibility fallback or every stored
confidence contained an `unknown` contribution.

### HC-F11 — retained membership, source projection, and independent cross-check

Two programs in ignored `_build/historical-cohorts/` perform the measurement against the
one pinned `scholar_knowledge.duckdb` file, using `duckdb.connect(..., read_only=True)`.
Complete executable programs and complete successful outputs follow in Event 10.

`phase6_exact.py` first walks all **7,607** `ac_skg_edges` and all **7,868**
`ac_skg_edge_evidence` rows, cross-checking both against SQL `count(*)`. It joins all
evidence claim IDs to raw claims and adjudications: **7,868 unique rows in each join**, no
duplicates, missing raw rows, or projection errors. There are exactly 7,607 distinct
evidence edge IDs, none absent from the exact table. Every exact edge has evidence members.
For every edge, the evidence claim-ID set equals `quality_signals_json.claim_ids`, the
evidence work-ID set equals `article_refs`, and evidence source/destination/direction equals
the edge's identity fields. The full walk checks all 7,868 evidence memberships, not a
sample or a count inferred from metadata.

The real read-only owner `ScholarKnowledgeStore._project_claim_row`
(`src/polisyos/data_forge/domains/academic/knowledge/store.py:488`) projects all those raw
rows to **`evidence_strength=None`, status `not_established`**. The actual pure
`_infer_edge_strength` at `batch/graph_builder.py:659` encodes all of them as the reserved
`not_established` storage value. Every exact edge is then evaluated by the real
`aggregate_edge_confidence` using `(encoded strength, projected extraction confidence)`
tuples; coercion of those tuples belongs to that function. No historical numeric input is
invented, and the absence exclusion makes the missing multiplicative factors irrelevant.

A second computation uses SQL `json_each`, relational `EXCEPT` in both directions for
the claim/article memberships, source-row joins, identity comparisons, and the sign of
stored confidence. It consumes **no Python projected results**. Its rule premise is the
separately inspected legacy source schema and current absence adapter, not a producer
provenance declaration. The Python and SQL **identity sets match for all three buckets**.
Only after that exact-layer result was confirmed did the family/contested program run.

`phase6_aggregates.py` walks all **15,945** family rows and all **723** contested rows,
again cross-checking SQL table counts. Their retained claim references resolve to
**16,658 unique raw rows** in the combined source join, with no duplicates or projection
errors. Family rows reference 16,658 distinct claims; contested rows reference 965. Every
row has a nonempty claim set whose size equals its stored `n_claims`. The real source
owner projects all 16,658 selected raw rows to `None` / `not_established`; the pure encoder
returns the absence encoding for all 16,658. A second SQL reference walk independently
counts unique references, checks their resolution and `n_claims`, and derives the three
bucket identity sets without reading the Python projection outputs. They match exactly.

All 723 contested rows also retain every referenced family ID, and in every case the union
of those family claim references equals the contested claim set. This additional full-set
retention check agrees with the contested row's own source membership.

The source table is physically `legacy_v1`, not a v2 table with a supplied evidence axis.
The relevant adapter at `src/polisyos/ir/analytics/literature.py:223` retains occurrence
fields and the legacy audit label without inferring any v2 axis. This is a computation
from the current stored source/schema and current rule; it does not validate the underlying
papers or retrospectively identify an extractor judgment.

**Scope of “recomputable”:** these results concern the current confidence rule on the
complete **retained membership of each existing aggregate**, after current source
projection. They do not regenerate canonical variables, rerun adjudication/publication
gates, rebuild a graph, or predict that a complete data pass would finish successfully.
No producer or writer is invoked. The stored summary classes, confidences and memberships
remain unchanged. In particular, the raw source projection is executed; the old rich
extraction payload is not presented to a full graph writer as if its admission had passed.

### HC-F12 — complete three-bucket partition

Bucket 1 means a determinate current-rule result equal to stored. Bucket 2 means a
determinate different result; for contested rows that includes determinate failure of the
emission predicate. Bucket 3 means that retained bytes do not determine the result. A
determinate **not-emitted** result is not bucket 3 and must not be assigned a fictitious
numeric confidence merely to subtract it from the stored value.

| Layer | Complete denominator | Bucket 1: equal, Python / SQL | Bucket 2: different, Python / SQL | Bucket 3: not recomputable, Python / SQL | Bucket-2 numerical confidences going to zero | Other determinate change |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Exact | 7,607 | 0 / 0 | **7,607 / 7,607** | 0 / 0 | **7,607** | None |
| Family | 15,945 | 0 / 0 | **15,945 / 15,945** | 0 / 0 | **15,945** | None |
| Contested | 723 | 0 / 0 | **723 / 723** | 0 / 0 | **0 final confidence replacements** | **723 not emitted; 723 base confidences zero** |

The three buckets sum exactly to each independently counted table denominator. Every
stored exact/family confidence is positive; equality is tested exactly, without a tolerance
that could hide a small change. Every current exact/family result is exactly `0.0`.
No row falls in bucket 3. The scripts explicitly account for missing/empty membership,
count/membership disagreement, unresolved or invalid source projection, and a positive
source axis requiring additional numeric inputs; none is encountered in these populations.

The missing historical per-evidence inputs identified in HC-F08 remain missing. They do
not put these rows in bucket 3 because **absence is excluded before those inputs matter**.
The broader source projection removes positive-base evidence from every group, not only
the previously selected strongest-unknown groups. HC-F08's inability to reconstruct the
old inputs and HC-F12's determinate current zero result are different statements.

For contested rows the real `weighted_direction_summary` computes every direction weight
as zero. The unchanged admission predicate at
`src/polisyos/data_forge/domains/academic/batch/edge_synthesize.py:530` requires either
contested positive-and-negative support or positive mixed support. Both are false for all
723 rows, so the `continue` at `:537` precedes the confidence floor at `:543`. This round
runs the pure confidence/direction functions and evaluates that inspected predicate; it
does **not** invoke the producer, an AST-extracted producer loop, canonicalization, or any
persistence routine. A current final contested confidence is consequently unavailable
because no row qualifies, while that disposition is fully determinate.

For reproducible identity reconciliation, bucket-2 IDs are sorted, newline-joined, and
SHA-256 hashed. Python and SQL identity symmetric differences are zero:

| Layer | Bucket-2 identity digest |
| --- | --- |
| Exact | `cbf1ae75f084685addc6dee86bf1785b87b96846b7be9b53ac0370f1f7fdb152` |
| Family | `ab4adfd0b0a81b19b54e1fb80ee0ab3cbc8df54324e3e2f4ce70164d3447654f` |
| Contested | `e78058eb9ccf3f98a1e8e639ba69b27940617bd252810f6ae51728cfee67739b` |

### HC-F13 — difference distribution, including the contested nonnumeric outcome

For exact and family rows, `delta = current confidence - stored confidence`. Every delta
is negative. The complete Python statistics and separate SQL aggregates agree up to
ordinary floating-point accumulation order; bucket identities/equality and histogram counts
agree exactly. Full precision is retained in Event 10's output.

| Layer | Changed numerical rows | Minimum delta | Maximum delta | Mean delta |
| --- | ---: | ---: | ---: | ---: |
| Exact | 7,607 | -0.9975408332428939 | -0.03149999999999997 | -0.45332494080630115 |
| Family | 15,945 | -0.9992589346255975 | -0.009811871841035491 | -0.2480690902801303 |

The bins below are **decrease magnitudes**, `stored - current`, for exact/family. The
contested column instead describes the **stored confidence of rows now not emitted**;
it is not a numeric current-minus-stored difference. Every cell has a matching independent
SQL count.

| Interval, lower exclusive / upper inclusive | Exact decrease | Family decrease | Stored contested confidence, all now not emitted |
| --- | ---: | ---: | ---: |
| (0, 0.05] | 15 | 492 | 0 |
| (0.05, 0.10] | 84 | 2,594 | 0 |
| (0.10, 0.25] | 265 | 5,789 | 427 |
| (0.25, 0.50] | 5,147 | 6,013 | 237 |
| (0.50, 0.75] | 2,043 | 964 | 55 |
| (0.75, 1.00] | 53 | 93 | 4 |
| **Complete denominator** | **7,607** | **15,945** | **723** |

The 723 stored contested confidences range from **0.15** to **0.8155864680301657**, mean
**0.26226157357899144**. All transition from a stored row to failure of the current
confidence-based emission predicate. A numeric final-confidence delta is not defined for
any of those 723 rows. Their current base confidences are zero; their direction-weight
differences are numerical and independently cross-checked:

| Stored direction-weight field | Nonzero stored cells going to zero | Minimum current-minus-stored | Maximum current-minus-stored |
| --- | ---: | ---: | ---: |
| `positive_weight` | 131 / 723 | -1.311582 | 0.0 |
| `negative_weight` | 119 / 723 | -2.321379 | 0.0 |
| `mixed_weight` | 632 / 723 | -1.206897 | 0.0 |

These are per-field counts, not disjoint sets of contested rows. The stored confidence
remains its actual stored value in the diagnostic results. It is never overwritten by the
base confidence or by a zero chosen for a non-emitted row.

### HC-F14 — the within-axis rescue is disallowed, and absence is not unknown

The code supports the reading that adjudication cannot supply the missing evidence axis:

1. `src/polisyos/data_forge/domains/academic/batch/graph_builder.py:408` defines
   `_legacy_strength_from_adjudication`; at `:409` it literally discards the adjudication
   and at `:410` returns `encode_edge_evidence_strength(None)`.
2. The current `_infer_edge_strength` at `:659` takes only the explicit
   `evidence_strength` and `evidence_strength_status` fields. It has no design fallback.
3. `src/polisyos/data_forge/domains/academic/knowledge/skg_store.py:1170` encodes an absent
   axis as `not_established`; `decode_edge_evidence_strength` at `:1200` returns
   **`None`, `ClaimVocabularyAxisStatus.NOT_ESTABLISHED`** for that encoding. A supplied
   `EvidenceStrength.UNKNOWN` is a separate candidate value.
4. `aggregate_edge_confidence` excludes declared absence at `:530` and nonpositive-base
   evidence at `:531`, returning zero for the empty valid set at `:533`–`:534`, before
   noisy-OR and the replication bonus.

The pure adjudication helper was executed on **all 7,868 retained published adjudications**;
every result is the absence encoding. The complete manufactured-class subset has these
current decoded outcomes:

| Retained adjudicated design | Rows | Current evidence value | Current evidence status |
| --- | ---: | --- | --- |
| `theoretical` | 131 | `None` | `not_established` |
| `unclear` | 187 | `None` | `not_established` |
| `review` | 24 | `None` | `not_established` |
| **Total** | **342** | | |

Consequently, adding `theoretical` to a design map would restore the cross-axis inference
B-2 removed. Sharing the spelling `theoretical` across two enums does not make an
adjudicated design an explicit evidence-axis value. **The brief's proposed correction to
`unknown` also needs correction:** the current evidence value is absence, not an unknown
judgment. The two states contribute the same zero but remain semantically distinct.

HC-F06's **severity** distinction survives: the 342 contradict or outrun their retained
adjudicated design, while the other 7,526 are faithful coarse translations relative to
that adjudication. Its possible implication that the 7,526 are **fine under today's
evidence rule** does not survive. Every one lacks the explicit current evidence axis and
contributes no positive support in this current-source computation. Contradiction and
failure to reproduce the stored value under current rules are different dimensions; both
are now measured rather than inferred from mapper membership.

### HC-D02 — stop at the measured partition; no route decision

**Bucket 2 swallows each complete layer.** The selected 458 is a valid count of stored
strongest-unknown family/contested summaries, but not the boundary of values differing
from a computation under today's source/evidence rules. Even the exact layer alone has
7,607 changed values. On this retained-membership calculation, re-derivation under the
current evidence rules has a zero-confidence target across the exact/family layers, not
a localized correction of 458 rows; a marker limited to those 458 would omit more than an
order of magnitude of the measured current-rule differences. This is not a claim that all
these rows were factually misclassified, generated by the same withdrawn branch, or
previously weighted as unknown.

The route choice remains the architect's. This round does not build a marker, a new
contract, a read-time substitution, or a data pass. A future delivery must keep the stored
value, its own status, and any determinate current-rule result distinguishable in the
value-beside-status form the user required. In particular, current-rule zero must not
silently replace stored confidence, and not-emitted must not masquerade as a zero final
confidence. Existing readers still return their existing stored values.

**HC-R01 remains registered without narrowing.** Direct SQL at
`src/polisyos/runtime/quality/capability_index_compiler.py:881` and
`src/polisyos/runtime/quality/credal_reference.py:839,856,899`, stored-column copy paths at
`src/polisyos/data_forge/domains/academic/batch/best_snapshot.py:925` and
`tools/ops_runners/cloud/merge_shards.py:244`, and the downstream prior DTO at
`src/polisyos/foundry/methods/catalog/causal/literature_prior.py:232` remain outside automatic
propagation of a query-only signal. Their source bytes are unchanged; no new after-change
reach claim is made.

The source projection and confidence calculations are `recomputed`; the membership/bucket
counts are `independently_reconciled` by a second computation on the same pinned bytes.
Original generating invocations, missing historical numeric inputs, and underlying paper
truth are not established by this measurement. The failure/repair register was read at
entry and closeout: P35/P36 prohibit substituting an inherited row count for this census;
P37/P38 require distinguishing the present-source predicate from the stored-label proxy;
P04 preserves absence versus unknown and computed values versus unavailable rows.

The 488 hint/adjudication mismatches and the parameter-value-provenance debt are not
investigated or changed. B-1/B-2 are not reopened. No product fix round was spent. There
was one scratch SQL parser error, documented in Event 10, and no product-code finding or
repair. The authorized work stops when this partition is recorded; implementation remains
out of scope regardless of the result.

### HC-T01-R2 — replace HC-T01-R1 in full; open-row transcription

> **HISTORICAL-COHORTS PHASE 6, 2026-09-05 — stays open; the current-rule cohort is the complete measured layers, with the route decision reserved to the architect.** Independent Python/pure-function and SQL computations on the pinned snapshot partition exact rows as **0 equal / 7,607 different / 0 not recomputable**, family as **0 / 15,945 / 0**, and contested as **0 / 723 / 0**, with identical bucket identities (HC-F11/HC-F12). Every exact/family confidence computes to zero after the current source projection: all 7,868 published source claims and all 16,658 family/contested source claims project to `None` / `not_established`, so no positive-base evidence survives. All 723 contested rows have zero base confidence and direction weights and fail the current confidence-based emission predicate before the 0.15 floor; their result is not-emitted, not a zero final confidence (HC-F13). These are determinate current-rule results on retained aggregate memberships, not a full graph/data-pass replay or recovered historical source inputs. The 458 strongest-unknown selection therefore understates current-rule differences by more than an order of magnitude; a current-rule re-derivation would not be a localized repair of those rows. This does not classify all historical values as factual misstatements or attribute all of them to the unknown-weight rule. The 342 adjudication-contradicting substitutions remain a distinct severity subset; the other 7,526 faithful design translations are equally unsupported by today's explicit evidence-axis requirement (HC-F14). No route or implementation is chosen. Any later delivery must preserve stored value/status beside a separately identified current-rule outcome, never silently substitute it, and must retain HC-R01's direct-SQL, copy, and downstream-projection residual. The snapshot and all product/read paths are unchanged.

### HC-T02-R2 — replace HC-T02-R1 in full; closed-row transcription

> **HISTORICAL-COHORTS PHASE 6, 2026-09-05 — remains closed for the forward repair; historical severity and present-rule reproducibility are separate.** The 342 manufactured empirical-design rows remain the correct contradiction cohort: theoretical 131, unclear 187, review 24, all stored observational; the previously checked 342/374 observational concentration remains 91.44385026737967%. The other 7,526 are faithful coarse translations relative to retained adjudications (HC-F06/HC-F07), but that does not make them derivable under today's evidence rule. The pure helper at `data_forge/domains/academic/batch/graph_builder.py:408` discards adjudication, and `_infer_edge_strength` at `:659` reads only the explicit evidence axis. All 7,868 published source claims now project to `None` / `not_established`; all 7,607 exact-edge confidences recompute to zero on their completely reconciled retained memberships (HC-F11/HC-F12). The proposed theoretical-design rescue would restore the removed cross-axis inference; the replacement is absence, not a recorded unknown judgment (HC-F14). No historical class/confidence, B-1/B-2 repair, or reader is changed. The broader confidence/currentness decision remains with the architect, and any future envelope must preserve stored values and HC-R01's named consumer residual. The 488 hint mismatches and parameter-value provenance remain outside this task.

These two **`-R2` paragraphs supersede the corresponding `-R1` paragraphs in full**.
The original and `-R1` paragraphs remain physically present as append-only history.
Replacements **must not be concatenated** with either earlier version when transcribing.

## Event 10 — Phase-6 reproduction and execution evidence, 2026-09-05

The complete programs below are diagnostic report producers only: production-data access
is read-only, and no data-producing/writing entry point is invoked. Per-row diagnostic
JSON is written only to ignored `_build/historical-cohorts/`, alongside stdout logs. The
retired mapper is not rerun. The exact program finishes by asserting the collapse
hypothesis before allowing the remaining-layer program to proceed.

```sh
cd /Users/deniskopylov/polisyos/.worktrees/debt-historical-cohorts/policy-engine
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/historical-cohorts/phase6_exact.py > _build/historical-cohorts/phase6_exact.log
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/historical-cohorts/phase6_aggregates.py > _build/historical-cohorts/phase6_aggregates.log
```

The exact command exited 0 in 2.44 seconds. The first aggregate attempt stopped at its SQL
cross-check because the scratch CTE was named the reserved word `references`
(`ParserException: syntax error at or near "references"`); it had not produced a verified
partition. The CTE was renamed `claim_references`, and that command then exited 0 in
2.72 seconds. This was a scratch-query syntax correction, not a product repair, a second
semantic finding, or a red/green implementation claim. No test suite or bound debt checker
is run for a journal-only measurement. The programs and successful outputs below are the
final executed versions.

### Program: phase6_exact.py

SHA-256: `d44059c5f0ea1858e2b6508af5dac74c5fb92f714934bd756b84a66b6b75a010`.

```python
"""Read-only current-source confidence partition; no producer invocation."""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import math

import duckdb
from polisyos.data_forge.domains.academic.batch.graph_builder import (
    _infer_edge_strength, _legacy_strength_from_adjudication,
)
from polisyos.data_forge.domains.academic.knowledge.store import ScholarKnowledgeStore
from polisyos.data_forge.domains.academic.knowledge import skg_store as owner

DB=Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
OUT=Path('_build/historical-cohorts')
con=duckdb.connect(str(DB),read_only=True)
store=ScholarKnowledgeStore._from_connection(con)

def emit(name,data):
    print(name,json.dumps(data,sort_keys=True,default=str),flush=True)

def fetch(sql):
    cur=con.execute(sql)
    names=[c[0] for c in cur.description]
    return [dict(zip(names,r)) for r in cur.fetchall()]

def table(name):
    data=fetch('SELECT * FROM '+name)
    assert len(data)==con.execute('SELECT count(*) FROM '+name).fetchone()[0]
    return data

def digest(ids):
    return hashlib.sha256('\n'.join(sorted(ids)).encode()).hexdigest()

def stats(values):
    if not values:return None
    return dict(n=len(values),minimum=min(values),maximum=max(values),sum=math.fsum(values),mean=math.fsum(values)/len(values))

X=table('ac_skg_edges'); E=table('ac_skg_edge_evidence')
Rrows=fetch('SELECT r.* FROM ac_causal_claims_raw r JOIN ac_skg_edge_evidence e ON e.claim_id=r.id')
R={r['id']:r for r in Rrows}
assert len(Rrows)==len(R)  # neither duplicated source IDs nor duplicated evidence claims
Arows=fetch('SELECT a.* FROM ac_claim_adjudications a JOIN ac_skg_edge_evidence e ON e.claim_id=a.claim_id')
A={r['claim_id']:r for r in Arows}
assert len(A)==len(Arows)
schema=store._claim_table_schema('ac_causal_claims_raw')
assert schema=='legacy_v1'
cols={r[0] for r in con.execute('DESCRIBE ac_causal_claims_raw').fetchall()}
assert 'evidence_strength' not in cols and 'claim_vocabulary_schema_version' not in cols
P={}; encodings={}; projection_errors={}
for cid,r in R.items():
    try:
        p=store._project_claim_row(r,source_table='ac_causal_claims_raw')
        P[cid]=p
        encodings[cid]=_infer_edge_strength(p.model_dump(mode='json'))
    except Exception as exc:
        projection_errors[cid]=type(exc).__name__+': '+str(exc)
emit('source_projection',dict(evidence_rows=len(E),raw_rows=len(R),adjudications=len(A),schema=schema,errors=dict(Counter(projection_errors.values())),value_status=dict(Counter(str(p.evidence_strength)+'|'+p.evidence_strength_status.value for p in P.values())),encodings=dict(Counter(encodings.values()))))

by_edge=defaultdict(list)
for e in E: by_edge[e['edge_id']].append(e)
result=[]; membership=Counter()
for x in X:
    ee=by_edge[x['edge_id']]
    ids={e['claim_id'] for e in ee}
    quality=json.loads(x['quality_signals_json'])
    quality_ids=set(quality.get('claim_ids',[]))
    article_ids=set(json.loads(x['article_refs']))
    why=[]
    if not ee:why.append('no_evidence_members')
    if not ids <= R.keys():why.append('missing_raw_claim')
    if not ids <= P.keys():why.append('source_projection_unavailable')
    if ids!=quality_ids:why.append('quality_claim_membership_disagrees')
    if {e['openalex_id'] for e in ee}!=article_ids:why.append('article_membership_disagrees')
    if any((e['src'],e['dst'],e['direction'])!=(x['src'],x['dst'],x['direction']) for e in ee):why.append('evidence_edge_identity_disagrees')
    if any(encodings.get(cid)!=owner.EDGE_EVIDENCE_NOT_ESTABLISHED for cid in ids):why.append('positive_or_other_axis_requires_remaining_inputs')
    if why:
        result.append(dict(id=x['edge_id'],bucket=3,reasons=why,current=None,stored=x['confidence']))
        continue
    # Each tuple contains two values from the real current source projection.
    # The public aggregator owns tuple coercion; no historical nuisance input is invented.
    samples=[(encodings[e['claim_id']],P[e['claim_id']].claim_extraction_confidence) for e in ee]
    current=owner.aggregate_edge_confidence(samples)
    assert math.isfinite(current) and math.isfinite(x['confidence'])
    result.append(dict(id=x['edge_id'],bucket=1 if current==x['confidence'] else 2,current=current,stored=x['confidence'],delta=current-x['confidence'],stored_class=x['evidence_strength']))
    membership['checked_edges']+=1;membership['checked_evidence_members']+=len(ee)

# Independent SQL membership and confidence-sign partition, using the independently
# inspected legacy schema/absence-adapter rule; no Python projected outputs feed SQL.
sql=con.execute("""
WITH q AS (
 SELECT x.edge_id, json_extract_string(j.value,'$') claim_id
 FROM ac_skg_edges x, json_each(x.quality_signals_json,'$.claim_ids') j
), a AS (
 SELECT x.edge_id,json_extract_string(j.value,'$') openalex_id
 FROM ac_skg_edges x,json_each(x.article_refs) j
), eligible AS (
 SELECT x.edge_id,x.confidence,
 EXISTS(SELECT 1 FROM ac_skg_edge_evidence e WHERE e.edge_id=x.edge_id)
 AND NOT EXISTS(SELECT 1 FROM ac_skg_edge_evidence e LEFT JOIN ac_causal_claims_raw r ON r.id=e.claim_id
   WHERE e.edge_id=x.edge_id AND (r.id IS NULL OR e.src<>x.src OR e.dst<>x.dst OR e.direction<>x.direction))
 AND NOT EXISTS(SELECT claim_id FROM q WHERE q.edge_id=x.edge_id EXCEPT SELECT claim_id FROM ac_skg_edge_evidence e WHERE e.edge_id=x.edge_id)
 AND NOT EXISTS(SELECT claim_id FROM ac_skg_edge_evidence e WHERE e.edge_id=x.edge_id EXCEPT SELECT claim_id FROM q WHERE q.edge_id=x.edge_id)
 AND NOT EXISTS(SELECT openalex_id FROM a WHERE a.edge_id=x.edge_id EXCEPT SELECT openalex_id FROM ac_skg_edge_evidence e WHERE e.edge_id=x.edge_id)
 AND NOT EXISTS(SELECT openalex_id FROM ac_skg_edge_evidence e WHERE e.edge_id=x.edge_id EXCEPT SELECT openalex_id FROM a WHERE a.edge_id=x.edge_id)
 AS recomputable FROM ac_skg_edges x
)
SELECT edge_id,CASE WHEN NOT recomputable THEN 3 WHEN confidence=0 THEN 1 ELSE 2 END bucket FROM eligible
""").fetchall()
for bucket in (1,2,3):
    pids={r['id'] for r in result if r['bucket']==bucket}
    sids={rid for rid,b in sql if b==bucket}
    assert pids==sids
    emit('exact_bucket',dict(bucket=bucket,python=len(pids),sql=len(sids),identity_symmetric_difference=0,ids_sha256=digest(pids)))
emit('exact_completeness',dict(exact_rows=len(X),evidence_rows=len(E),distinct_evidence_edges=len(by_edge),evidence_without_exact=len(set(by_edge)-{r['edge_id'] for r in X}),counts=dict(membership),unrecomputable_reasons=dict(Counter(reason for r in result for reason in r.get('reasons',[])))))

diff=[r for r in result if r['bucket']==2]
emit('exact_difference',dict(current_minus_stored=stats([r['delta'] for r in diff]),go_to_zero=sum(r['current']==0 for r in diff),by_stored_class={s:dict(n=sum(r['stored_class']==s for r in diff),deltas=stats([r['delta'] for r in diff if r['stored_class']==s])) for s in sorted({r['stored_class'] for r in diff})}))
bounds=[0,0.05,0.1,0.25,0.5,0.75,1]
for low,high in zip(bounds,bounds[1:]):
    py=sum(low < -r['delta'] <= high for r in diff)
    sqln=con.execute('SELECT count(*) FROM ac_skg_edges WHERE confidence>? AND confidence<=?',[low,high]).fetchone()[0]
    assert py==sqln
    emit('exact_decrease_bin',dict(lower_exclusive=low,upper_inclusive=high,python=py,sql=sqln))
sqlstats=con.execute('SELECT count(*),min(-confidence),max(-confidence),sum(-confidence),avg(-confidence) FROM ac_skg_edges WHERE confidence<>0').fetchone()
assert len(diff)==sqlstats[0]
for got,expected in zip([min(r['delta'] for r in diff),max(r['delta'] for r in diff),math.fsum(r['delta'] for r in diff),math.fsum(r['delta'] for r in diff)/len(diff)],sqlstats[1:]):assert math.isclose(got,expected,abs_tol=1e-10,rel_tol=1e-12)
emit('exact_difference_sql',dict(n=sqlstats[0],minimum=sqlstats[1],maximum=sqlstats[2],sum=sqlstats[3],mean=sqlstats[4]))

rescue=Counter()
for cid,a in A.items():
    encoded=_legacy_strength_from_adjudication(a)
    assert encoded==owner.EDGE_EVIDENCE_NOT_ESTABLISHED
    if a['design_family'] in {'unclear','theoretical','review'}:
        decoded,status=owner.decode_edge_evidence_strength(encoded)
        rescue[a['design_family'],str(decoded),status.value]+=1
emit('within_axis_rescue',dict(adjudications_tested=len(A),outcomes=[dict(design=d,current_value=v,current_status=s,n=n) for (d,v,s),n in sorted(rescue.items())],legacy_adjudication_helper_encoding=owner.EDGE_EVIDENCE_NOT_ESTABLISHED))
OUT.joinpath('phase6-exact-results.json').write_text(json.dumps(result,sort_keys=True)+'\n')
con.close()
assert all(r['bucket'] in (1,2) and r['current']==0.0 for r in result), 'STOP: exact collapse hypothesis refuted or not established'
emit('exact_hypothesis','CONFIRMED: every exact current-rule confidence is zero; proceed to the remaining layers only')
```

Complete successful output:

```text
source_projection {"adjudications": 7868, "encodings": {"not_established": 7868}, "errors": {}, "evidence_rows": 7868, "raw_rows": 7868, "schema": "legacy_v1", "value_status": {"None|not_established": 7868}}
exact_bucket {"bucket": 1, "identity_symmetric_difference": 0, "ids_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "python": 0, "sql": 0}
exact_bucket {"bucket": 2, "identity_symmetric_difference": 0, "ids_sha256": "cbf1ae75f084685addc6dee86bf1785b87b96846b7be9b53ac0370f1f7fdb152", "python": 7607, "sql": 7607}
exact_bucket {"bucket": 3, "identity_symmetric_difference": 0, "ids_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "python": 0, "sql": 0}
exact_completeness {"counts": {"checked_edges": 7607, "checked_evidence_members": 7868}, "distinct_evidence_edges": 7607, "evidence_rows": 7868, "evidence_without_exact": 0, "exact_rows": 7607, "unrecomputable_reasons": {}}
exact_difference {"by_stored_class": {"meta_analysis": {"deltas": {"maximum": -0.55, "mean": -0.5579266702098638, "minimum": -0.9397110769339542, "n": 1047, "sum": -584.1492237097274}, "n": 1047}, "observational": {"deltas": {"maximum": -0.03149999999999997, "mean": -0.11686576157015377, "minimum": -0.2534438603443461, "n": 365, "sum": -42.656002973106126}, "n": 365}, "panel_fe": {"deltas": {"maximum": -0.35, "mean": -0.35218924413840264, "minimum": -0.5608933224125778, "n": 765, "sum": -269.424771765878}, "n": 765}, "quasi_natural": {"deltas": {"maximum": -0.45, "mean": -0.45423483355380645, "minimum": -0.8718574099427912, "n": 4019, "sum": -1825.5697960527482}, "n": 4019}, "quasi_natural_event": {"deltas": {"maximum": -0.4, "mean": -0.4024384168790645, "minimum": -0.6817407274009959, "n": 499, "sum": -200.8167700226532}, "n": 499}, "rct": {"deltas": {"maximum": -0.55, "mean": -0.5774766338717493, "minimum": -0.9975408332428939, "n": 909, "sum": -524.9262601894201}, "n": 909}, "structural": {"deltas": {"maximum": -0.3, "mean": -0.3, "minimum": -0.3, "n": 3, "sum": -0.8999999999999999}, "n": 3}}, "current_minus_stored": {"maximum": -0.03149999999999997, "mean": -0.45332494080630115, "minimum": -0.9975408332428939, "n": 7607, "sum": -3448.442824713533}, "go_to_zero": 7607}
exact_decrease_bin {"lower_exclusive": 0, "python": 15, "sql": 15, "upper_inclusive": 0.05}
exact_decrease_bin {"lower_exclusive": 0.05, "python": 84, "sql": 84, "upper_inclusive": 0.1}
exact_decrease_bin {"lower_exclusive": 0.1, "python": 265, "sql": 265, "upper_inclusive": 0.25}
exact_decrease_bin {"lower_exclusive": 0.25, "python": 5147, "sql": 5147, "upper_inclusive": 0.5}
exact_decrease_bin {"lower_exclusive": 0.5, "python": 2043, "sql": 2043, "upper_inclusive": 0.75}
exact_decrease_bin {"lower_exclusive": 0.75, "python": 53, "sql": 53, "upper_inclusive": 1}
exact_difference_sql {"maximum": -0.03149999999999997, "mean": -0.45332494080627816, "minimum": -0.9975408332428939, "n": 7607, "sum": -3448.442824713358}
within_axis_rescue {"adjudications_tested": 7868, "legacy_adjudication_helper_encoding": "not_established", "outcomes": [{"current_status": "not_established", "current_value": "None", "design": "review", "n": 24}, {"current_status": "not_established", "current_value": "None", "design": "theoretical", "n": 131}, {"current_status": "not_established", "current_value": "None", "design": "unclear", "n": 187}]}
exact_hypothesis "CONFIRMED: every exact current-rule confidence is zero; proceed to the remaining layers only"
```

### Program: phase6_aggregates.py

SHA-256: `a42a1d28028b61291fda90a6f129ac600c755e83939002f59b643986add34c00`.

```python
"""Read-only source-projected family/contested partition; never run a producer."""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import math

import duckdb
from polisyos.data_forge.domains.academic.batch.graph_builder import _infer_edge_strength
from polisyos.data_forge.domains.academic.knowledge.store import ScholarKnowledgeStore
from polisyos.data_forge.domains.academic.knowledge import skg_store as owner

DB=Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
OUT=Path('_build/historical-cohorts')
prior=json.loads(OUT.joinpath('phase6-exact-results.json').read_text())
assert prior and all(r['bucket'] in (1,2) and r['current']==0 for r in prior)
con=duckdb.connect(str(DB),read_only=True)
store=ScholarKnowledgeStore._from_connection(con)

def emit(name,data):
    print(name,json.dumps(data,sort_keys=True,default=str),flush=True)

def fetch(sql):
    cur=con.execute(sql);names=[c[0] for c in cur.description]
    return [dict(zip(names,r)) for r in cur.fetchall()]

def table(name):
    data=fetch('SELECT * FROM '+name)
    assert len(data)==con.execute('SELECT count(*) FROM '+name).fetchone()[0]
    return data

def refs(r):return set(json.loads(r['claim_refs']))

def digest(ids):return hashlib.sha256('\n'.join(sorted(ids)).encode()).hexdigest()

def stats(values):
    if not values:return None
    return dict(n=len(values),minimum=min(values),maximum=max(values),sum=math.fsum(values),mean=math.fsum(values)/len(values))

F=table('ac_skg_family_edges'); C=table('ac_skg_contested_edges')
Rrows=fetch("""
WITH needed AS (
 SELECT json_extract_string(j.value,'$') id FROM ac_skg_family_edges f,json_each(f.claim_refs) j
 UNION
 SELECT json_extract_string(j.value,'$') id FROM ac_skg_contested_edges c,json_each(c.claim_refs) j
) SELECT r.* FROM ac_causal_claims_raw r JOIN needed n ON n.id=r.id
""")
R={r['id']:r for r in Rrows};assert len(R)==len(Rrows)
assert store._claim_table_schema('ac_causal_claims_raw')=='legacy_v1'
P={};encoded={};errors={}
for cid,r in R.items():
    try:
        p=store._project_claim_row(r,source_table='ac_causal_claims_raw')
        P[cid]=p;encoded[cid]=_infer_edge_strength(p.model_dump(mode='json'))
    except Exception as exc:
        errors[cid]=type(exc).__name__+': '+str(exc)
emit('aggregate_source_projection',dict(raw_rows=len(R),family_rows=len(F),contested_rows=len(C),family_distinct_claim_refs=len(set().union(*(refs(r) for r in F))),contested_distinct_claim_refs=len(set().union(*(refs(r) for r in C))),errors=dict(Counter(errors.values())),value_status=dict(Counter(str(p.evidence_strength)+'|'+p.evidence_strength_status.value for p in P.values())),encodings=dict(Counter(encoded.values()))))

def calculate(row,key,layer):
    rr=refs(row);why=[]
    if not rr:why.append('empty_claim_membership')
    if row['n_claims']!=len(rr):why.append('claim_count_disagrees')
    if not rr<=R.keys():why.append('missing_raw_claim')
    if not rr<=P.keys():why.append('source_projection_unavailable')
    if any(encoded.get(cid)!=owner.EDGE_EVIDENCE_NOT_ESTABLISHED for cid in rr):why.append('positive_or_other_axis_requires_remaining_inputs')
    if why:return dict(id=row[key],bucket=3,reasons=why,current=None,stored=row['confidence'])
    samples=[(encoded[cid],P[cid].claim_extraction_confidence) for cid in sorted(rr)]
    base=owner.aggregate_edge_confidence(samples)
    assert base==0.0
    if layer=='family':
        return dict(id=row[key],bucket=1 if base==row['confidence'] else 2,stored=row['confidence'],current=base,delta=base-row['confidence'],stored_class=row['evidence_strength'])
    direction_samples=defaultdict(list)
    for cid in sorted(rr):
        direction_samples[P[cid].direction].append((encoded[cid],P[cid].claim_extraction_confidence))
    summary=owner.weighted_direction_summary(dict(direction_samples))
    assert all(v==0.0 for v in summary.direction_weights.values())
    positive=summary.direction_weights.get('positive',0.0)
    negative=summary.direction_weights.get('negative',0.0)
    mixed=sum(summary.direction_weights.get(k,0.0) for k in ('mixed','ambiguous','non_linear'))
    # Observe the unchanged producer's admission predicate at edge_synthesize.py:530-537.
    # No producer function or row-building loop is invoked in this round.
    emits=(summary.is_contested and positive>0.0 and negative>0.0) or mixed>0.0
    assert not emits
    return dict(id=row[key],bucket=2,stored=row['confidence'],current=None,current_status='not_emitted',base_confidence=base,delta=None,stored_class=row['evidence_strength'],direction_weight_deltas={k:-float(row[k] or 0.0) for k in ('positive_weight','negative_weight','mixed_weight')})

results={}
for layer,data,tname,key in [('family',F,'ac_skg_family_edges','family_edge_id'),('contested',C,'ac_skg_contested_edges','contested_edge_id')]:
    out=[calculate(r,key,layer) for r in data];results[layer]=out
    # Independent SQL reference completeness and stored-value comparison. It consumes
    # no Python projection outputs and uses the separately established legacy schema.
    sql=con.execute('''
WITH claim_references AS (
 SELECT t.'''+key+''' id,json_extract_string(j.value,'$') claim_id
 FROM '''+tname+''' t,json_each(t.claim_refs) j
), coverage AS (
 SELECT rr.id,count(*) n_refs,count(DISTINCT rr.claim_id) unique_refs,
 count(r.id) resolved
 FROM claim_references rr LEFT JOIN ac_causal_claims_raw r ON r.id=rr.claim_id GROUP BY rr.id
)
SELECT t.'''+key+''',CASE
 WHEN coalesce(v.unique_refs,0)=0 OR v.unique_refs<>t.n_claims OR v.resolved<>v.n_refs THEN 3
 '''+('WHEN t.confidence=0 THEN 1' if layer=='family' else '')+'''
 ELSE 2 END bucket
FROM '''+tname+''' t LEFT JOIN coverage v ON v.id=t.'''+key).fetchall()
    for bucket in (1,2,3):
        pids={r['id'] for r in out if r['bucket']==bucket};sids={rid for rid,b in sql if b==bucket}
        assert pids==sids
        emit(layer+'_bucket',dict(bucket=bucket,python=len(pids),sql=len(sids),identity_symmetric_difference=0,ids_sha256=digest(pids)))
    emit(layer+'_partition_detail',dict(total=len(data),reasons=dict(Counter(w for r in out for w in r.get('reasons',[]))),current_value_status=dict(Counter(str(r['current'])+'|'+r.get('current_status','numeric') for r in out)),go_to_numeric_zero=sum(r['bucket']==2 and r['current']==0 for r in out),base_confidence_zero=sum(r.get('base_confidence')==0 for r in out),by_stored_class=dict(Counter(r['stored_class'] for r in out if r['bucket']==2))))

    diff=[r for r in out if r['bucket']==2]
    values=[r['delta'] for r in diff] if layer=='family' else [r['stored'] for r in diff]
    sign=-1 if layer=='family' else 1
    sqlstats=con.execute('SELECT count(*),min('+str(sign)+'*confidence),max('+str(sign)+'*confidence),sum('+str(sign)+'*confidence),avg('+str(sign)+'*confidence) FROM '+tname).fetchone()
    ps=stats(values)
    assert len(values)==sqlstats[0]
    for got,expected in zip([ps['minimum'],ps['maximum'],ps['sum'],ps['mean']],sqlstats[1:]):assert math.isclose(got,expected,abs_tol=1e-9,rel_tol=1e-12)
    emit(layer+'_difference',dict(measure='current_minus_stored' if layer=='family' else 'stored_confidence_of_rows_now_not_emitted',python=ps,sql=dict(n=sqlstats[0],minimum=sqlstats[1],maximum=sqlstats[2],sum=sqlstats[3],mean=sqlstats[4]),numeric_delta_unavailable=len(diff) if layer=='contested' else 0))
    for low,high in zip([0,.05,.1,.25,.5,.75],[.05,.1,.25,.5,.75,1]):
        py=sum(low<r['stored']<=high for r in diff)
        sqln=con.execute('SELECT count(*) FROM '+tname+' WHERE confidence>? AND confidence<=?',[low,high]).fetchone()[0]
        assert py==sqln
        emit(layer+'_distribution_bin',dict(measure='confidence_decrease' if layer=='family' else 'stored_confidence_of_not_emitted_rows',lower_exclusive=low,upper_inclusive=high,python=py,sql=sqln))
    if layer=='contested':
        for field in ('positive_weight','negative_weight','mixed_weight'):
            vals=[r['direction_weight_deltas'][field] for r in diff]
            s=con.execute('SELECT min(-'+field+'),max(-'+field+'),sum(-'+field+'),count(*) FILTER(WHERE '+field+'<>0) FROM '+tname).fetchone()
            assert math.isclose(math.fsum(vals),s[2],abs_tol=1e-9)
            assert sum(v!=0 for v in vals)==s[3]
            emit('contested_direction_weight_difference',dict(field=field,python=stats(vals),go_to_zero=s[3],sql_minimum=s[0],sql_maximum=s[1],sql_sum=s[2]))

# Independent retention audit; not a premise for recovering original nuisance values.
FM={r['family_edge_id']:r for r in F};links=Counter()
for row in C:
    fids=set(json.loads(row['quality_signals_json'])['family_edge_ids'])
    links['all_family_ids_present']+=fids<=FM.keys()
    if fids<=FM.keys():
        links['family_claim_union_equals_contested']+=set().union(*(refs(FM[k]) for k in fids))==refs(row)
emit('contested_family_retention',dict(contested_rows=len(C),counts=dict(links)))
OUT.joinpath('phase6-aggregate-results.json').write_text(json.dumps(results,sort_keys=True)+'\n')
con.close()
```

Complete successful output:

```text
aggregate_source_projection {"contested_distinct_claim_refs": 965, "contested_rows": 723, "encodings": {"not_established": 16658}, "errors": {}, "family_distinct_claim_refs": 16658, "family_rows": 15945, "raw_rows": 16658, "value_status": {"None|not_established": 16658}}
family_bucket {"bucket": 1, "identity_symmetric_difference": 0, "ids_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "python": 0, "sql": 0}
family_bucket {"bucket": 2, "identity_symmetric_difference": 0, "ids_sha256": "ab4adfd0b0a81b19b54e1fb80ee0ab3cbc8df54324e3e2f4ce70164d3447654f", "python": 15945, "sql": 15945}
family_bucket {"bucket": 3, "identity_symmetric_difference": 0, "ids_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "python": 0, "sql": 0}
family_partition_detail {"base_confidence_zero": 0, "by_stored_class": {"cross_sectional": 2, "meta_analysis": 2306, "observational": 6421, "panel_fe": 859, "quasi_natural": 4307, "quasi_natural_event": 495, "rct": 951, "structural": 3, "theoretical": 161, "unknown": 440}, "current_value_status": {"0.0|numeric": 15945}, "go_to_numeric_zero": 15945, "reasons": {}, "total": 15945}
family_difference {"measure": "current_minus_stored", "numeric_delta_unavailable": 0, "python": {"maximum": -0.009811871841035491, "mean": -0.2480690902801303, "minimum": -0.9992589346255975, "n": 15945, "sum": -3955.4616445166776}, "sql": {"maximum": -0.009811871841035491, "mean": -0.24806909028013174, "minimum": -0.9992589346255975, "n": 15945, "sum": -3955.4616445167007}}
family_distribution_bin {"lower_exclusive": 0, "measure": "confidence_decrease", "python": 492, "sql": 492, "upper_inclusive": 0.05}
family_distribution_bin {"lower_exclusive": 0.05, "measure": "confidence_decrease", "python": 2594, "sql": 2594, "upper_inclusive": 0.1}
family_distribution_bin {"lower_exclusive": 0.1, "measure": "confidence_decrease", "python": 5789, "sql": 5789, "upper_inclusive": 0.25}
family_distribution_bin {"lower_exclusive": 0.25, "measure": "confidence_decrease", "python": 6013, "sql": 6013, "upper_inclusive": 0.5}
family_distribution_bin {"lower_exclusive": 0.5, "measure": "confidence_decrease", "python": 964, "sql": 964, "upper_inclusive": 0.75}
family_distribution_bin {"lower_exclusive": 0.75, "measure": "confidence_decrease", "python": 93, "sql": 93, "upper_inclusive": 1}
contested_bucket {"bucket": 1, "identity_symmetric_difference": 0, "ids_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "python": 0, "sql": 0}
contested_bucket {"bucket": 2, "identity_symmetric_difference": 0, "ids_sha256": "e78058eb9ccf3f98a1e8e639ba69b27940617bd252810f6ae51728cfee67739b", "python": 723, "sql": 723}
contested_bucket {"bucket": 3, "identity_symmetric_difference": 0, "ids_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "python": 0, "sql": 0}
contested_partition_detail {"base_confidence_zero": 723, "by_stored_class": {"meta_analysis": 133, "observational": 298, "panel_fe": 41, "quasi_natural": 176, "quasi_natural_event": 23, "rct": 31, "theoretical": 3, "unknown": 18}, "current_value_status": {"None|not_emitted": 723}, "go_to_numeric_zero": 0, "reasons": {}, "total": 723}
contested_difference {"measure": "stored_confidence_of_rows_now_not_emitted", "numeric_delta_unavailable": 723, "python": {"maximum": 0.8155864680301657, "mean": 0.26226157357899144, "minimum": 0.15, "n": 723, "sum": 189.6151176976108}, "sql": {"maximum": 0.8155864680301657, "mean": 0.26226157357899266, "minimum": 0.15, "n": 723, "sum": 189.61511769761168}}
contested_distribution_bin {"lower_exclusive": 0, "measure": "stored_confidence_of_not_emitted_rows", "python": 0, "sql": 0, "upper_inclusive": 0.05}
contested_distribution_bin {"lower_exclusive": 0.05, "measure": "stored_confidence_of_not_emitted_rows", "python": 0, "sql": 0, "upper_inclusive": 0.1}
contested_distribution_bin {"lower_exclusive": 0.1, "measure": "stored_confidence_of_not_emitted_rows", "python": 427, "sql": 427, "upper_inclusive": 0.25}
contested_distribution_bin {"lower_exclusive": 0.25, "measure": "stored_confidence_of_not_emitted_rows", "python": 237, "sql": 237, "upper_inclusive": 0.5}
contested_distribution_bin {"lower_exclusive": 0.5, "measure": "stored_confidence_of_not_emitted_rows", "python": 55, "sql": 55, "upper_inclusive": 0.75}
contested_distribution_bin {"lower_exclusive": 0.75, "measure": "stored_confidence_of_not_emitted_rows", "python": 4, "sql": 4, "upper_inclusive": 1}
contested_direction_weight_difference {"field": "positive_weight", "go_to_zero": 131, "python": {"maximum": -0.0, "mean": -0.05498906500691563, "minimum": -1.311582, "n": 723, "sum": -39.757094}, "sql_maximum": -0.0, "sql_minimum": -1.311582, "sql_sum": -39.757093999999974}
contested_direction_weight_difference {"field": "negative_weight", "go_to_zero": 119, "python": {"maximum": -0.0, "mean": -0.05499171645919779, "minimum": -2.321379, "n": 723, "sum": -39.759011}, "sql_maximum": -0.0, "sql_minimum": -2.321379, "sql_sum": -39.75901099999999}
contested_direction_weight_difference {"field": "mixed_weight", "go_to_zero": 632, "python": {"maximum": -0.0, "mean": -0.19969940525587826, "minimum": -1.206897, "n": 723, "sum": -144.38267}, "sql_maximum": -0.0, "sql_minimum": -1.206897, "sql_sum": -144.38267000000013}
contested_family_retention {"contested_rows": 723, "counts": {"all_family_ids_present": 723, "family_claim_union_equals_contested": 723}}
```

## Event 11 — Phase-6 closeout, custody, and checker exemption, 2026-09-05

Events 9–10 were committed as `1a4efd43e075fe7330a9724a050fe3b4881eaf38` on
`codex/debt-historical-cohorts` and read back from the branch. The committed journal equals
the worktree file, preserves the original 104,271-byte prefix (Events 1–8) verbatim, and
contains the exact executed measurement programs and their SHA-256 hashes. `git diff
--check` passed. The observed branch state after the measurement commit was clean:
`## codex/debt-historical-cohorts`.

Only the journal changed. No checker-read register, ledger, plan, tool, source, test, or
schema file changed, so **the bound debt checker was skipped** under the corrected rule.
The receipt was run against the committed continuation:

```sh
git diff --name-only 424e8b2ee..HEAD
```

```text
policy-engine/docs/superpowers/journals/2026-09-05-historical-cohorts.md
```

The final production-data hash read after all measurements confirmed:

```text
sha256:583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967
mode: -r--r--r--
size: 2390503424 bytes
```

No production-data write, chmod, producer/writer invocation, live lane, rebase, force-push,
or stash occurred. Only read-only/pure recomputation into the diagnostic report was done.
No product implementation or route decision was made. The user-required stop is Phase-6
partition completion; the architect now owns the route ruling on HC-F11–HC-F14.

The committed journal SHA-256 **before this receipt append** was
`5d23c6efc2165983a18923c9e9b4d00f3aaab12260625ecd5f132cab5389dfab` (Events 1–10).
This receipt is committed separately, followed by a final branch/path/prefix readback;
that later journal hash is not claimed to equal the pre-receipt hash. HC-T01-R2 and
HC-T02-R2 are the sole replacement transcription paragraphs from this round and must not
be concatenated with the preserved earlier versions.


## Event 12 — Phase-7 producer verification and mandatory early stop, 2026-09-05

Entry branch: `codex/debt-historical-cohorts`, attached and clean at
`afcc4a839c07a0c37ce479dcbda843aa7deb20ae`. Events 1–11 are preserved verbatim.
The Phase-7 instruction requires a working current extractor that can carry the named
axis end-to-end before the corpus/input/cost measurements. Its first stop rule applies:
**the cited selective LLM extraction path fails during prompt preparation, before its
model request.** This was reported immediately; subsequent work only records the stop.

### HC-F15 — the named axis exists in source, but the cited producer cannot request it

The code read in the brief is partly supported. At
`src/polisyos/data_forge/domains/academic/batch/llm_extractor.py:123`, the prompt asks for a
separately named `evidence_strength` class or null. The LLM serializer retains that named
value at `:62` and constructs its value/status at `:85–86`; a present value is candidate,
while `None` has status `not_established` (`_candidate_status`, `:36`).
`parse_llm_result` calls that serializer for dictionary causal claims at `:466–469`.
These are static transport facts, not evidence of a successful producer invocation.

The actual request path fails earlier. `EXTRACTION_PROMPT`, defined at `:97`, contains
literal, unescaped JSON object braces starting at `:100`. The assignment in
`extract_with_llm` at `:403` executes:

```python
prompt = EXTRACTION_PROMPT.format(topic=topic, abstract=abstract[:4000])
```

The formatter reads the outer JSON object as a replacement field named
`\n  "estimates"` (shown escaped here). That is not either supplied keyword. Evaluating
**only this original source expression**, against the imported current module's unchanged
constant, raises `KeyError: '\n  "estimates"'` for empty, 37-character, and 5,000-character
abstracts. The constant and keyword mismatch cause the failure before abstract content
can matter. The assignment is before and outside the `try` at `:404`, and thus before
`client.chat_completion` at `:405`; the handler at `:411` does not catch this failure.
The selective stage's `llm`/`audit_llm` branch at `:588` awaits this function at `:599`
before `parse_llm_result` at `:605`. No model request or parsed axis is reachable through
that invocation with the checked source constant.

**Independent cross-check and denominator.** The witness reads the complete
`src/polisyos/data_forge/domains/academic/batch/llm_extractor.py` file: one `.py` file,
one top-level `EXTRACTION_PROMPT` definition, the complete `extract_with_llm` AST, and
the complete `run_extract_llm` AST. It asserts that the imported module is this worktree's
file and its runtime constant equals the independently parsed AST literal. A separate
`string.Formatter().parse` observation returns the exact two fields
`["\n  \"estimates\"", "abstract"]`; evaluating the original assignment expression yields
the same missing-key exception in all three input cases. The complete program and output
are in Event 13. This is a negative behavioral witness of prompt preparation, not a
repository-wide producer census or a positive end-to-end extraction test. No extractor,
stage, serializer, client, or writer was invoked. The witness imports the module and
executes only the pure string expression from the request path.

**A second correction to the cited reading:**
`src/polisyos/data_forge/domains/academic/batch/parser.py:423,427` are members of the
forbidden-key list in `serialize_deterministic_claim_occurrence_vocabulary` (`:409`).
That function rejects occurrence input containing `evidence_strength` or its status
at `:433–434`; it supplies `source_basis=ABSTRACT_ONLY` with candidate status at
`:442–443`, without supplying an evidence axis. Those lines do not carry the evidence
axis through the deterministic path. This observation does not reopen or repair the
intentional B-1/B-2 absence boundary.

**What is refuted:** the cited current selective LLM route supplies a working
end-to-end producer on which the proposed re-extraction requirement can presently rely.
**What is not established:** the date the axis was introduced, complete-corpus absence,
the viability of every other producer, or the claim that the whole academic pipeline
cannot produce confidence. Snapshot age itself is not disproven by the prompt failure;
the stronger operational inference that this is merely an old snapshot with a verified
working replacement producer is not supported. In particular, the separately identified
IR keyword inference is not a substitute receipt for this route.

### HC-D03 — stop disposition; vintage, input scope, and cost remain unmeasured

The user required an immediate stop if the extractor did not populate the axis end-to-end.
HC-F15 meets that stop before any Phase-7 database census or re-extraction/input probe.
The remaining requested quantities are recorded as follows, not filled from the brief:

| Phase-7 question | Result at this stop |
| --- | --- |
| Complete `ac_article_extractions` axis/status presence | **Not measured.** The earlier 310,829 documents / 137,714 embedded claims are census denominators, not a complete axis-presence result. HC-F03 established absence in the 7,868 published payloads; this round does not extend it to every document. |
| `source_basis` distribution over the needed re-extraction population | **Not measured.** A source-code `ABSTRACT_ONLY` assignment is not a distribution over retained documents. |
| Retained text sufficient versus sources requiring re-fetch | **Not measured.** Neither compute-only work nor a data-acquisition requirement is established. The source-availability stop was not reached. |
| Article and claim workload needed to restore exact/family/contested layers | **Not measured.** HC-F11's 7,868 exact source claims, 16,658 family claim references and 965 contested claim references are retained lineage counts, not a measured article workload or a guarantee of restoring those edge identities after fresh extraction. |
| Re-extraction token, money, or elapsed-time range | **`not_established`.** No cost range is asserted. |
| Layer-vintage declaration propagation to direct SQL and copiers | **Not measured.** No declaration was designed or implemented; layer scope alone is not a consumer-reach proof. |

A bounded cost would require a verified working producer, the measured article/input
set and retained text availability, any acquisition work, actual prompt and token sizes,
a selected model's input/output charging basis, and declared output/retry/gating and
throughput assumptions. No extraction, producer invocation, source fetch, or paid call was
performed to obtain those inputs. Those are prerequisites for a later measurement, not an
authorized pass or a promise about its price. The introduction date and complete-corpus
walk would also be needed before declaring that the artifact predates the axis everywhere.

HC-F11–HC-F14 remain the accepted retained-membership result: **7,607 exact and 15,945
family current-rule confidences are zero; all 723 contested memberships have zero base
confidence/direction weights and fail the confidence-based emission predicate.** The
latter outcome is not-emitted, not a zero final confidence. Their projected source value
is `None` / `not_established`, not a recorded unknown. Those measurements establish no
positive-confidence restoration by recomputation from these retained source projections;
they do not establish that current or future producers cannot supply explicit evidence.

The Phase-7 ruling withdrawing per-row marking stands. No (a), (b), (c), read-time value
replacement, or layer declaration is selected or built here. The proposed conclusion
**"this row is not closable by code; convert it into a buildable layer-vintage declaration
plus a measured re-extraction requirement in the data-capability register" is withheld**:
its producer, complete vintage, input availability, cost, and declaration-reach premises
were not established before the stop. HC-F15 identifies a concrete code failure for a
separate scope ruling; repairing that failure would not itself restore this snapshot.

HC-R01's named residual remains unchanged: direct SQL at
`src/polisyos/runtime/quality/capability_index_compiler.py:881` and
`src/polisyos/runtime/quality/credal_reference.py:839,856,899`; stored-column copies at
`src/polisyos/data_forge/domains/academic/batch/best_snapshot.py:925` and
`tools/ops_runners/cloud/merge_shards.py:244`; and the downstream prior DTO at
`src/polisyos/foundry/methods/catalog/causal/literature_prior.py:232`. This is the inherited
measured residual from HC-R01, not a new propagation measurement. Any future current-rule
interpretation must keep stored value/status and separately identified current-rule
outcome distinguishable; a direct reader must never silently disagree with stored bytes.

The failure/repair register was read at entry and before closeout. Pattern pass:
P01/P12 distinguish a field-bearing contract from a functioning producer; P29/P38 reject
field-name presence as proof of a working path (the divergence is the real prompt-expression
failure while every named field remains present); P35/P36 prevent promoting the published
payload census or the brief into a whole-corpus fact; P04 preserves absence/unknown and
zero/not-emitted; P37 labels the pure prompt failure **`recomputed`**, while successful
end-to-end production and the later cost/vintage conclusions remain **`not_established`**.
A working end-to-end capability has **`verification_missing`**; the measured request
preparation is blocked. The negative witness is not a positive capability verification.

HC-F15 is a **new producer execution class**, distinct from the historical substitution
and unknown-weight findings. No repair was attempted, so the one fix round remains
unspent; there is no second repair round or new product test. Neither `literature.py`, the
488 hint mismatches, nor `parameter-evidence-strength-has-no-value-provenance` is repaired
or investigated further. The architect's separately named IR issue remains separate.
No active plan or register is edited; proposed transcriptions below are journal-only.

### HC-T03 — proposed separate producer-row prose; not registered by this task

> **ACADEMIC LLM PROMPT PREPARATION BLOCKS EXTRACTION — new scope ruling required (HC-F15).** At the Phase-7 entry source, `src/polisyos/data_forge/domains/academic/batch/llm_extractor.py:97` defines a JSON-bearing prompt with unescaped literal braces. The original `.format(topic=topic, abstract=abstract[:4000])` expression at `:403` raises `KeyError: '\n  "estimates"'` before the `try` at `:404` and before the model request at `:405`. The selective `llm`/`audit_llm` stage calls that function at `:599` before parsing at `:605`, so the cited route cannot produce an evidence-axis payload. An AST/runtime-constant reconciliation and pure execution of the exact expression witness the failure without calling a producer or client. This does not establish that every academic producer is broken, nor date the introduction of the failure. Follow-up needs a separately authorized repair and a behavioral receipt that the actual request path can prepare its prompt, reach a controlled client, and carry returned named candidate evidence through the real downstream boundary. No repair or data pass occurred here; this is not a reopening of B-1/B-2 or a fix for the separately registered IR keyword inference.

### HC-T01-R3 — replace HC-T01-R2 in full; open-row transcription

> **HISTORICAL-COHORTS PHASE 7, 2026-09-05 — stays open; the vintage/re-extraction ruling stops at producer verification.** The accepted complete retained-membership partition remains exact **0 equal / 7,607 different / 0 not recomputable**, family **0 / 15,945 / 0**, and contested **0 / 723 / 0**, independently reconciled by Python/pure-function and SQL bucket identities (HC-F11/HC-F12). Every exact/family confidence computes to zero from the current source projection; all 723 contested memberships have zero base confidence and direction weights and fail the current confidence-based emission predicate before the 0.15 floor, so their outcome is not-emitted, not zero final confidence (HC-F13). Source value is `None` / `not_established`, not a recorded unknown (HC-F14). The historical 458 strongest-unknown count is not the boundary of current-rule differences; this does not make all historical values factual misstatements. Per-row marking is withdrawn by the Phase-7 ruling. The proposed replacement with a whole-snapshot vintage declaration and measured re-extraction requirement is not yet established: the cited LLM prompt asks for `evidence_strength`, but its original `.format(...)` at `src/polisyos/data_forge/domains/academic/batch/llm_extractor.py:403` raises `KeyError: '\n  "estimates"'` from unescaped JSON braces before the model request; the cited deterministic parser lines reject, rather than carry, the axis (HC-F15). Phase 7 therefore stopped before the complete-corpus axis walk, source-basis/input-availability census, article workload, cost range, and declaration-reach measurement (HC-D03). Re-extraction cost and compute-versus-acquisition ownership are `not_established`; the conclusion that this row is not closable by code and ready to convert into a costed data-capability requirement is withheld. The measured producer failure needs a separate scope ruling (HC-T03); it neither disproves the snapshot's age nor establishes that every current producer is broken. Any future current-rule interpretation must preserve stored value/status beside the separate current-rule outcome, retain HC-R01's named direct-SQL/copy/downstream residual, and prove declaration reach before claiming it. No route, reader, historical byte, or B-1/B-2 repair changed.

### HC-T02-R3 — replace HC-T02-R2 in full; closed-row transcription

> **HISTORICAL-COHORTS PHASE 7, 2026-09-05 — remains closed for the forward repair; contradiction, present-rule reproducibility, and producer viability are separate.** The 342 manufactured empirical-design rows remain the contradiction cohort: theoretical 131, unclear 187, review 24, all stored observational. HC-F06/HC-F07 independently established that they constitute 342 of 374 observational evidence rows (91.44385026737967%); the other 32 come from actual OLS adjudications. The other 7,526 published rows are faithful coarse translations relative to retained adjudications, but that does not make them derivable under today's explicit evidence-axis rule. `data_forge/domains/academic/batch/graph_builder.py:408` discards adjudication and `_infer_edge_strength` at `:659` reads the explicit axis; all 7,868 published source claims project to `None` / `not_established`, and all 7,607 exact confidences compute to zero on reconciled retained memberships (HC-F11/HC-F12/HC-F14). The proposed theoretical-design rescue would restore the removed cross-axis inference. Phase 7 additionally found that the cited selective LLM producer fails in prompt formatting at `src/polisyos/data_forge/domains/academic/batch/llm_extractor.py:403` before its request (HC-F15); this is a separate producer issue, not evidence reopening the forward substitution repair or proving that the entire pipeline cannot produce confidence. The whole-corpus vintage, retained input availability, restoration workload, and re-extraction cost remain unmeasured because the required early stop preceded them (HC-D03). Per-row marking is withdrawn; no replacement layer declaration or data-capability conversion is claimed. Stored values and readers remain unchanged, HC-R01's named residual persists, and the broader route decision remains with the architect. The 488 hint mismatches, parameter-value provenance, and separately registered IR keyword inference remain outside this task.

These two **`-R3` paragraphs supersede HC-T01-R2 and HC-T02-R2 in full**. The original,
`-R1`, and `-R2` paragraphs remain physically present as append-only history. The
replacements **must not be concatenated** with any earlier version when transcribing.
HC-T03 is separate proposed producer-row prose; it is not an extra clause to concatenate
onto either historical row.

## Event 13 — Phase-7 pure failure witness and commands, 2026-09-05

The witness below is retained verbatim from the executed ignored scratch file
`_build/historical-cohorts/phase7_vintage_stop.py`; the journal is the committed record.
Its SHA-256 is `b964b9eb993e945baef566ee3a8c72f4d18c474053441d5214f0055b1cded1d1`.
The captured output SHA-256 is
`421fc94f8e9ee9c1ce3ab0b2d1876e3c4476b40ce74c5458db3fdea0e928af12`.
The measured source `.py` file SHA-256 is
`5ad13f22b7bc6aac2cae1be9397391e04374d888aabd21c168cf681d0387f6b4`.

Command, from the provisioned `policy-engine` worktree:

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/historical-cohorts/phase7_vintage_stop.py > _build/historical-cohorts/phase7_vintage_stop.log
```

The command exited **0** in approximately **1.54 seconds** because every expected
prompt-formatting failure was observed and asserted. Exit 0 is **not** a successful
extraction, a green producer test, or a positive end-to-end capability receipt. There is
no red/green repair sequence: this round is measurement-only and stops on the negative
witness. No product test or broad suite was run. The source was not patched even in scratch;
the original expression and original constant were used.

```python
"""Pure prompt-preparation witness: no extraction, client, producer, or writer call."""
from pathlib import Path
import ast
import hashlib
import json
import string

from polisyos.data_forge.domains.academic.batch import llm_extractor as current

path=Path('src/polisyos/data_forge/domains/academic/batch/llm_extractor.py')
assert Path(current.__file__).resolve()==path.resolve()
source=path.read_text()
tree=ast.parse(source)
definitions=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='EXTRACTION_PROMPT' for t in n.targets)]
assert len(definitions)==1
literal=ast.literal_eval(definitions[0].value)
assert literal==current.EXTRACTION_PROMPT
fn=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='extract_with_llm')
assignment=next(n for n in fn.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='prompt' for t in n.targets))
guard=next(n for n in fn.body if isinstance(n,ast.Try))
assert fn.body.index(assignment)<fn.body.index(guard)
assert not any(n is assignment for n in ast.walk(guard))
requests=[n for n in ast.walk(guard) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='chat_completion']
assert len(requests)==1
fields=[field for _,field,_,_ in string.Formatter().parse(literal) if field is not None]
print('source',json.dumps(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),prompt_line=definitions[0].lineno,format_line=assignment.lineno,try_line=guard.lineno,request_line=requests[0].lineno,format_outside_try=True,module_literal_equals_ast_literal=True),sort_keys=True))
print('format_fields',json.dumps(fields))
assert fields==['\n  "estimates"','abstract']

# Evaluate only the exact prompt assignment expression extracted from current source.
# The extractor coroutine, stage, client and serializers are not invoked.
expression=compile(ast.Expression(body=assignment.value),str(path),'eval')
for label,abstract in [('empty',''),('short','Read-only prompt-preparation witness.'),('long','A'*5000)]:
    try:
        eval(expression,{'EXTRACTION_PROMPT':current.EXTRACTION_PROMPT,'topic':'measurement','abstract':abstract})
    except KeyError as exc:
        assert exc.args==('\n  "estimates"',)
        print('format_failure',json.dumps(dict(input_case=label,input_chars=len(abstract),exception=type(exc).__name__,missing_key=exc.args[0],request_invoked=False),sort_keys=True))
    else:
        raise AssertionError('Unexpected successful prompt preparation; stop finding refuted')

stage=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='run_extract_llm')
calls=[n for n in ast.walk(stage) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {'extract_with_llm','parse_llm_result'}]
print('stage_call_sites',json.dumps(sorted((n.func.id,n.lineno) for n in calls)))
print('disposition','STOP: the cited selective LLM extraction path fails before the model request; end-to-end working-producer premise refuted for that path only.')
```

Complete captured output:

```text
source {"format_line": 403, "format_outside_try": true, "module_literal_equals_ast_literal": true, "path": "src/polisyos/data_forge/domains/academic/batch/llm_extractor.py", "prompt_line": 97, "request_line": 405, "sha256": "5ad13f22b7bc6aac2cae1be9397391e04374d888aabd21c168cf681d0387f6b4", "try_line": 404}
format_fields ["\n  \"estimates\"", "abstract"]
format_failure {"exception": "KeyError", "input_case": "empty", "input_chars": 0, "missing_key": "\n  \"estimates\"", "request_invoked": false}
format_failure {"exception": "KeyError", "input_case": "short", "input_chars": 37, "missing_key": "\n  \"estimates\"", "request_invoked": false}
format_failure {"exception": "KeyError", "input_case": "long", "input_chars": 5000, "missing_key": "\n  \"estimates\"", "request_invoked": false}
stage_call_sites [["extract_with_llm", 599], ["parse_llm_result", 605]]
disposition STOP: the cited selective LLM extraction path fails before the model request; end-to-end working-producer premise refuted for that path only.
```

Anchor correction from the final numbered-source read: `_candidate_status` is defined
at `llm_extractor.py:37`; HC-F15's `:36` points to the preceding blank line. The value/status
behavior and measured failure are unchanged.


## Event 14 — Phase-7 closeout, custody, and checker exemption, 2026-09-05

Events 12–13 were committed as `22ce4f69eb7a2ba4285022823790ae6a340f2703` on
`codex/debt-historical-cohorts` and read back from the branch. The committed journal equals
the worktree file, preserves the original 155,533-byte prefix (Events 1–11) verbatim, and
contains the exact executed witness and captured output. `git diff --check` passed before
commit and against the committed continuation. The observed branch state was clean:
`## codex/debt-historical-cohorts`.

**The bound debt checker was skipped.** Only the journal changed; no checker-read
register, ledger, `docs/plans/`, `tools/`, `src/`, `tests/`, or schema file changed.
The corrected Phase-7 predicate therefore does not require a checker run. Receipt against
the committed continuation:

```sh
git diff --name-only afcc4a839..HEAD
```

```text
policy-engine/docs/superpowers/journals/2026-09-05-historical-cohorts.md
```

The final production-data custody read opened the pinned DuckDB file in binary read mode,
computed `hashlib.file_digest(..., 'sha256')`, and checked its mode and size. It completed
in approximately 1.27 seconds and confirmed:

```text
path: production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb
sha256:583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967
mode: -r--r--r--
size: 2390503424 bytes
```

No production-data write, chmod, extraction, data pass, producer/writer invocation,
source fetch, live lane, rebase, force-push, or stash occurred. No source, product test,
active plan, or register changed. HC-F15 is an observed failure, not a repaired path;
there is no implementation green and no product fix round was spent. The requested early
stop remains in force, with the unmeasured Phase-7 quantities and cost `not_established`
recorded in HC-D03. The source failure and any continuation require the architect's scope
ruling; this journal does not expand that authority.

The committed journal SHA-256 **before this receipt append** was
`fb0e9ebb876604c10864a00cd1743a7d17ecae64ed6da179fb3896469f6e67a9` (Events 1–13).
This receipt is committed separately, followed by a final branch/path/prefix readback.
HC-T01-R3 and HC-T02-R3 replace the corresponding `-R2` paragraphs in full and **must not
be concatenated** with the preserved earlier versions. HC-T03 remains a separate proposed
producer-row transcription, not a registration or repair performed by this task.


## Event 15 — Phase-8 complete source census and producer-premise stop, 2026-09-05

Entry branch: `codex/debt-historical-cohorts`, attached and clean at
`b97969a3f41e177a72b1f42bfcca129d3f9114bf`. Events 1–14 remain verbatim. The Phase-8
source/test repair grant is conditional on finding no working alternative producer.
**That prerequisite is refuted:** the active rich `resolve_extract` route has a working
prompt/provider-response/claim-transport chain. A controlled response reaches graph
inference as `rct` / `candidate` and has a positive pure aggregate confidence, without
using the broken `extract_with_llm` function. The finding was reported immediately and
**stop rule 1 was applied before any repair**. Later work only reconciles and records
this census, its witness, and custody.

### HC-F16 — complete producer-candidate census, denominator, and independent reconciliation

The path denominator is the complete physical `src/` + `tools/` tree at entry, including
hidden/ignored paths; `Path.rglob` and `rg --files --hidden --no-ignore` agree on every
path. All 3,355 paths are also tracked. There are **3,052 Python files**, all parsed with
zero syntax errors, and **303 other files**, which were included in the text census.
File-type denominator:

| Type | Files |
| --- | ---: |
| `.py` | 3,052 |
| `.md` | 200 |
| `.sh` | 27 |
| `.json` | 18 |
| `.csv` | 15 |
| `.ts` | 12 |
| `.yaml` | 11 |
| `.tmpl` | 7 |
| `.pyi` | 5 |
| `.cypher`, `.toml`, `.typed` | 2 each |
| `.sql`, `.txt` | 1 each |
| **Total** | **3,355** |

The complete source-text scan finds **301 lines in 47 files** containing
`evidence_strength` (including `evidence_strength_status`). All matching files are `.py`.
Python byte/text scanning, `rg --json --hidden --no-ignore`, and independently enumerated
`git grep -n evidence_strength b97969a3f -- src tools` agree on the **complete path/line
identity set**, not just its size: **zero symmetric difference**. The sorted path
inventory hash is `8c76b3fd7ece7b17f9e055a61e71df69fddc17ef1c52a94e6886cefbea65df79`.
The Git comparison is against committed entry bytes, not a scratch or edited source tree.

The AST scan records **64 syntactic field-write candidates in 19 files**: keyword
arguments, dictionary construction, attribute/subscript assignments, or `setattr` with a
literal target field. This is a search denominator, **not 64 producers**: query filters,
contract declarations, and downstream projections also use the keyword/dictionary
syntax. SQL strings, templates, reads, annotations, and copies are retained in the wider
301-line set and checked against the typed transport boundary rather than lost by limiting
the census to assignment syntax. The program and complete candidate/call-site output are
preserved in Event 16.

A second view starts at the actual `ClaimOccurrenceVocabularyTransport` constructors.
The complete AST call set finds **four local builder functions**. An independent
source-declaration scan finds the same four identities. **Two** explicitly supply the
named evidence value/status; the deterministic and historical-adapter builders supply
absence. The writer/transport inventory is:

| Writer or transport owner | Value source and reach to `graph_builder._infer_edge_strength` |
| --- | --- |
| `batch/article_extractor.py:953` `_normalize_causal_claim` (field at `:973`) | Normalizes a named claim field from a parsed rich response and validates `CausalClaim` at `:996`. The active `resolve_extract` worker calls the enclosing payload normalizer at `_resolve_extract_api.py:1517`. This is an additional producer route; its explicit `rct` input, subsequent gate, serialization, and inference were exercised in HC-F17. This witness does not establish historical provenance or calibrate the normalized field. |
| `batch/article_extractor.py:1901` `serialize_rich_claim_occurrence_vocabulary` | Emits the separately named value/status at `:1949–1950`, using the typed claim's supplied fields. Called by `_to_work_record` at `:2010`; active resolve extraction and finalize call `_to_work_record` at `_resolve_extract_api.py:1757` and `resolve_finalize.py:937`. The resulting nested transport survives the actual JSONL adapter and `_admitted_claim_parts` before inference. Its separate OpenAlex-ingest caller is `knowledge/skg_store.py:729`; that caller uses its own SQL-ingest path, not the batch `_infer_edge_strength` call. |
| `batch/llm_extractor.py:45` `serialize_llm_claim_occurrence_vocabulary` | Emits the named value/status at `:85–86`, called by `parse_llm_result` at `:467`. The codec can accept a supplied model response, but its selective producer call remains blocked by HC-F15's prompt-format failure at `:403`, before request and parse. It is not the rich producer above. |
| `batch/parser.py:409` `serialize_deterministic_claim_occurrence_vocabulary` | A real transport builder called by `parse_raw_sources` at `:647`, but rejects occurrence-supplied evidence value/status at `:421–434`. It does not produce a named evidence judgment; the evidence axis remains absent. |
| `knowledge/types.py:220` `adapt_legacy_claim_occurrence_transport` | The fourth transport builder, used for explicitly identified historical inputs; adapts old vocabulary to absence. It is not a new extraction producer. |
| `knowledge/types.py:187` `candidate_claim_vocabulary_store_values` | Re-admits and flattens an existing transport, carrying value/status at `:205–208`. It is a persistence-layout copier, not an independent observation. `_admitted_claim_parts` at `batch/graph_builder.py:367` uses it. |
| `knowledge/types.py:545` `adapt_jsonl_work_record_claims` | Generic persisted-v2 ingress preserves nested `occurrence`/`vocabulary`; legacy inputs take the absence adapter. `run_graph_load` uses it at `batch/graph_builder.py:1802`. Externally supplied valid v2 records can carry an axis; admission does not establish who originally observed it. |

Paths in that table are relative to `src/polisyos/data_forge/domains/academic/`.
The four builder identities are the rich serializer, selective-LLM serializer,
deterministic serializer, and legacy adapter. The normalizer, flattening copier, and
JSONL reader are separately named so their roles are not counted as extra independent
extractors. `load_graph` has **one** `_infer_edge_strength` call at `:1634` in the complete
AST set. It consumes the vocabulary of records admitted at `:1117–1120` and is gated by a
separately admitted `publishable_edge` adjudication at `:1594–1600` and nonempty endpoints.
An axis reaching that function is not, by itself, permission to publish an edge.

The remaining syntactic candidates are accounted for below. This table names each file's
complete candidate count and plane; the exact containing function and line for **every**
site are in Event 16. A candidate count does not assert the absence of generic forwarding
or prove an unrelated runtime route was executed.

| File (under `src/polisyos/` unless `tools/` is shown) | Sites | Disposition relative to claim production for this batch boundary |
| --- | ---: | --- |
| `data_forge/domains/academic/batch/_resolve_extract_transformers.py` | 3 | Numeric-parameter rescue, merge, and prompt projection; not a new claim evidence-axis writer. |
| `data_forge/domains/academic/batch/article_extractor.py` | 4 | Three claim normalizer/serializer sites above; one empirical-parameter normalizer, outside this claim boundary. |
| `data_forge/domains/academic/batch/llm_extractor.py` | 3 | Selective-LLM serializer value dictionary and two envelope fields, above. |
| `data_forge/domains/academic/batch/numeric_extract.py` | 1 | Raw numeric-parameter projection. |
| `data_forge/domains/academic/batch/resolve_finalize.py` | 3 | Parameter merging, curated numeric rows, and simulation-ready parameters; its rich claim bridge is separately listed above. |
| `data_forge/domains/academic/batch/table_extractor.py` | 1 | Table-to-parameter construction. |
| `data_forge/domains/academic/knowledge/skg_query.py` | 14 | Query filters, edge/prior projections, and parameter conversion; downstream of stored evidence, not the rich response producer. |
| `data_forge/domains/academic/knowledge/store.py` | 11 | Claim/edge projection, audit, and a validation predicate; returns stored or adapted vocabulary. |
| `data_forge/domains/academic/knowledge/types.py` | 2 | Column-type map and admitted persistence layout; not observations. |
| `foundry/analysis/attractors.py` | 3 | Attractor/certificate contracts, a different evidence-bearing result type. |
| `foundry/methods/catalog/bayesian/pmd_hmc.py` | 1 | Multimodality assessment contract. |
| `foundry/methods/catalog/causal/literature_prior.py` | 2 | Downstream literature-prior DTO. |
| `ir/analytics/literature.py` | 2 | The gold-record and OpenAlex span-grounded `CausalClaim` constructor sites; included in the required complete source census. No IR producer was invoked or changed. The separately registered keyword mechanism is not investigated or repaired here; the observed OpenAlex storage caller uses the separate SKG ingest path above. |
| `runtime/http/openapi_contract.py` | 2 | OpenAPI contract fields. |
| `runtime/quality/credal_reference.py` | 4 | Stored edge/family/claim projections. |
| `scientist/cross_graph/gatherers/academic.py` | 1 | Literature-prior baseline projection. |
| `scientist/methods/discovery/prior_miner.py` | 2 | Mined-prior DTO value/status. |
| `tools/ops_runners/experiments/run_msme_final_fresg_suite.py` | 1 | Experimental policy-score result. |
| `tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py` | 4 | Validation census/projection rows. |
| **Total** | **64** | Complete syntactic candidate set; semantic producer count is not inferred from this total. |

No competing source mechanism needs to be repaired to deliver this result. The rich path
alone is a counterexample to the Phase-8 premise; the literal/source set and local builder
reconciliation are complete, while live operation, production credentials, historical
invocations, and every downstream scheduler/ingest outcome are not claimed to have been
executed or certified.

### HC-F17 — active rich route: rendered prompt, controlled response, persisted shape, inference

The active route is visible in the actual orchestration: `batch/pipeline.py:125` invokes
`run_resolve_extract`, and the explicit claim lane invokes the same stage at `:140`.
The facade in `batch/resolve_extract.py:92` delegates to `_resolve_extract_api`. Its
`llm_worker` uses `_prompt_for_bundle` at `_resolve_extract_api.py:1358`, then awaits
`_await_provider_json` at `:1364`. It does not call selective `extract_with_llm`.

The prompt owner is `_resolve_extract_transformers.py:1247`. It already uses a readable
literal schema and targeted replacement of `{canonical_names_block}` at `:1258`; JSON
braces are never passed through `str.format`. The actual claim schema includes the
separate evidence axis (`_resolve_extract_api.py:549`; shared via the facade globals).
A controlled witness calls the active facade's real prompt function and provider wrapper
with an in-memory pool, then follows the worker's response-to-record functions:

```text
_prompt_for_bundle
  -> _await_provider_json (controlled pool, no network)
  -> _normalize_extraction_payload -> ArticleExtractionResult.model_validate
  -> _apply_publish_gate
  -> _to_work_record -> serialize_rich_claim_occurrence_vocabulary
  -> WorkRecord.model_dump_json -> json.loads
  -> adapt_jsonl_work_record_claims
  -> graph_builder._admitted_claim_parts
  -> graph_builder._infer_edge_strength
```

The fixture deliberately supplies synthetic sentence spans and a named `rct` response.
The measured result is **one controlled provider call, zero real model calls, one
normalized claim, `publish_to_graph=True` with no claim-level blockers, one claim after
JSON round-trip, evidence `rct` / `candidate`, and inferred edge strength `rct`**. The
current pure aggregation function returns **0.55** for the resulting single-claim sample.
This is a code-path witness with synthetic inputs, not measured paper evidence or a
confidence calibration result.

The **rendered** 9,183-character prompt contains the claim JSON block with single braces;
the controlled pool checks the rendered block before returning its response. Its SHA-256
is `1727fc4f0806f0783fe62ab735f0a2de5153c3580e7f6c6ef3aa2879843366e1`.
That positive receipt belongs to the existing rich path. The selective LLM template was
not edited, escaped, substituted, or otherwise repaired. Its known formatting failure
remains HC-F15; this witness never routes through it.

**Reachability limit:** the scheduler, extraction stage/coroutine, artifact writers,
graph loader, and adjudicator were not invoked. The real graph loop additionally requires
a separately admitted publishable adjudication, and this task did not manufacture one.
The witness exercises the real prompt/provider-wrapper/normalizer/gate/serialization/
admission/inference functions, while the orchestration connections and adjudication gate
are read from their source. It establishes a working candidate-axis path under a
controlled response; it does not establish real-provider availability, past successful
runs, paper truth, or an authorized published result. The zero real-model-call and no-stage
counts describe this harness, not the repository's history.

This suffices to refute **"the LLM path [meaning selective `extract_with_llm`] is its only
producer"**, **"the axis has no working producer at all"**, and the consequent claim
**"fresh data must again produce zero because the only producer is broken"**. Fresh
explicit evidence can reach current inference; whether a particular fresh source yields
it remains a data question. HC-F11–HC-F14's universal-zero result for the pinned retained
source projections remains intact. It is not a universal theorem about future rich
extractions.

### HC-D04 — mandatory stop, unspent repair, and deferred measurements

The Phase-8 instruction says **"Stop if the census finds a working producer — the
diagnosis is then wrong."** HC-F17 triggers that rule before task 2. The explicit scope
grant to repair the selective prompt is conditional and is not exercised after its
premise fails. No repair design or source/test implementation is committed. The one fix
round remains unspent; no red-first test for the proposed repair or implementation green
is claimed. The positive controlled-response witness is verification of existing code.

Task 2's swallowing/sibling investigation was not reached. HC-F15 still locates the known
format error before the selective function's `try`, but this round makes no new claim
about what other failures its broad handler hides and performs no handler repair. The
architect's supplied first-commit/B-1 history was not replayed before this stop; the
separate selective failure is established at the task's source, without attributing every
past extraction attempt or every producer to that one function.

No LLM gate was enabled or changed. A future repair of the selective prompt would allow
its existing model-call branch to make real requests when its route is enabled; that
operational consequence still matters, but **this round did not activate it**. The rich
route already has its own model-request path, subject to its configuration and gates.

Task 3 remains conditional on tasks 1–2 completing without a stop, so the complete-corpus
axis/status walk, source-basis/input-availability census, article/claim restoration scope,
and re-extraction cost range remain **unmeasured**. Cost remains **`not_established`**,
with the bounding prerequisites in HC-D03. Neither compute-only work nor a source
acquisition requirement is established. The introduction date and complete 310,829-document /
137,714-embedded-claim axis population are not inferred from the existence of this rich
path or from the earlier 7,868-published-payload result.

The Phase-7 withdrawal of per-row marking and HC-R01's residual stand. No layer-vintage
declaration, read-time numeric substitution, or data-capability conversion is implemented.
Existing residual anchors remain direct SQL at
`src/polisyos/runtime/quality/capability_index_compiler.py:881` and
`src/polisyos/runtime/quality/credal_reference.py:839,856,899`; stored-column copies at
`src/polisyos/data_forge/domains/academic/batch/best_snapshot.py:925` and
`tools/ops_runners/cloud/merge_shards.py:244`; and downstream
`src/polisyos/foundry/methods/catalog/causal/literature_prior.py:232`.
A current-rule interpretation must still keep stored value/status separate from its
current-rule outcome; a read path must never silently replace stored bytes.

Pattern pass (failure/repair register read at entry and closeout): P35/P36 require the
complete source denominator and separate the architect's supplied history from the
measured finding; P29/P38 require a rendered/consumed signal instead of a template substring;
P01/P02 distinguish the actual active rich bridge from the selected broken sibling;
P04/P05 preserve candidate authority and absence versus unknown. The source census is
**`independently_reconciled`**; the synthetic response-to-inference result is
**`recomputed`**. Historical invocation provenance, real-provider operation, restoration
cost, and production publication are **`not_established`** by this witness. It is not a
claim to close every capability link or lift a candidate into authority.

The 488 hint mismatches, parameter-value provenance, B-1/B-2 repairs, and IR keyword issue
are not repaired or further investigated. No active plan, register, source, test, schema,
or release fragment is changed. The only tracked deliverable is this appended journal.
The Phase-8 prediction that the checker would apply anticipated source/test work; that
work did not occur. Under the explicitly unchanged checker predicate (actual changes to
files it reads), the checker is **skipped**, with the committed diff receipt in Event 17.

### HC-T01-R4 — replace HC-T01-R3 in full; open-row transcription

> **HISTORICAL-COHORTS PHASE 8, 2026-09-05 — stays open; a working rich producer refutes the proposed universal producer absence.** The accepted retained-membership partition remains exact **0 equal / 7,607 different / 0 not recomputable**, family **0 / 15,945 / 0**, and contested **0 / 723 / 0**, independently reconciled in HC-F11/HC-F12. Exact/family current-rule confidences are zero; all 723 contested memberships have zero base confidence and direction weights and fail the current emission predicate before its floor, so their outcome is not-emitted, not zero final confidence (HC-F13). Source value is `None` / `not_established`, not a recorded unknown (HC-F14); the 458 strongest-unknown rows are not the current-rule difference boundary. Per-row marking remains withdrawn. The complete Phase-8 census covers 3,355 `src/`/`tools/` files, including 3,052 Python files with zero parse errors; independent scans reconcile all 301 matching lines in 47 files and all four local claim-transport builders (HC-F16). The active rich `resolve_extract` route uses a separate working prompt and `_normalize_causal_claim` -> rich serializer -> `WorkRecord` bridge. A controlled response survives the real publication gate, JSON round-trip, admission, and `_infer_edge_strength` as `rct` / `candidate`, with a positive 0.55 pure confidence result (HC-F17). No real model, extraction stage, writer, or adjudicator ran; actual publication still requires an admitted publishable adjudication. The broken selective `extract_with_llm` prompt remains a separate defect, not the only producer. Consequently the claim that re-extraction must again yield zero because the axis has no producer is refuted. Stop rule 1 prevented the proposed formatting repair and all deferred corpus/input/workload/cost measurements (HC-D04); their cost and compute-versus-acquisition ownership remain `not_established`. Neither whole-corpus vintage nor a ready layer-declaration/data-capability conversion is established, and the claim that this row is not closable by code remains withheld. No route or historical/read-path value changed; HC-R01's named direct-SQL/copy/downstream residual persists, and any future current-rule interpretation must preserve stored value/status separately.

### HC-T02-R4 — replace HC-T02-R3 in full; closed-row transcription

> **HISTORICAL-COHORTS PHASE 8, 2026-09-05 — remains closed for the forward substitution repair.** The contradiction cohort remains 342 stored observational evidence rows: theoretical 131, unclear 187, review 24; they are 342 of 374 observational rows (91.44385026737967%), with the other 32 from actual OLS adjudications (HC-F06/HC-F07). The remaining 7,526 are faithful coarse translations relative to retained adjudications, but are not derivable from adjudication under today's explicit evidence-axis rule. All 7,868 published source claims project to `None` / `not_established` and all 7,607 exact confidences compute to zero on reconciled retained memberships; the proposed theoretical-design rescue would reinstate the removed cross-axis inference (HC-F11/HC-F12/HC-F14). Phase 8 refutes the inference that this makes every future extraction zero: the complete source census identifies the separate active rich `resolve_extract` producer, and its controlled response-to-claim/JSONL/admission path preserves `rct` / `candidate` into `_infer_edge_strength` with a positive pure confidence result (HC-F16/HC-F17). This is a synthetic code-path witness, not paper evidence, a real model run, or an authorized publication; the graph still requires an admitted publishable adjudication. The selective LLM prompt failure remains a separate unrepaired defect and no longer supports a claim that the entire axis has no producer. The mandatory census stop left whole-corpus vintage, retained-input availability, restoration workload, and cost unmeasured (HC-D04). Per-row marking remains withdrawn; no layer declaration, read-time replacement, data pass, or reader changed. HC-R01 persists, and the broader route decision remains with the architect. The 488 hint mismatches, parameter-value provenance, and IR keyword inference remain outside this repair.

### HC-T03-R4 — separate producer-row correction; replaces the proposed HC-T03 wording

> **ACADEMIC EVIDENCE-AXIS PRODUCER CENSUS, 2026-09-05 — the proposed “no working producer” diagnosis is refuted; the selective prompt defect remains open and unrepaired.** HC-F16 enumerates the complete 3,355-file `src/`/`tools/` tree and reconciles 301 matching lines in 47 files plus four claim-transport builders. The rich `resolve_extract` producer is separate from selective `extract_with_llm`: `_resolve_extract_api.py:1358` calls `_prompt_for_bundle`, whose owner at `_resolve_extract_transformers.py:1247` keeps literal JSON intact, and the response reaches `_normalize_extraction_payload` at `_resolve_extract_api.py:1517` and `_to_work_record` at `:1757`. The existing rich normalizer/serializer and real JSONL/admission/inference functions carry a controlled named `rct` response as `rct` / `candidate`; pure confidence is 0.55 (HC-F17). The stage, real model, writers, and adjudicator were not invoked, so live-provider operation and publication are not certified. Separately, `llm_extractor.py:403` still fails before its request because the selective template's unescaped JSON braces are interpreted by `.format` (HC-F15). That bounded execution defect, not absence of every evidence-axis producer, is the accurate remaining code debt. Phase-8 stop rule 1 prevented its conditional repair; no red/green repair or handler-sibling investigation was performed. A future separately scoped formatting fix must exercise the real selective request path against a controlled client and prove that rendered model-facing text retains single JSON braces. When that route is enabled, unblocking prompt preparation permits real model calls; this task enabled nothing. Do not merge this producer-row correction with either historical-confidence row.

**HC-T01-R4 and HC-T02-R4 supersede their corresponding `-R3` paragraphs in full.**
HC-T03-R4 is separate producer-row prose and supersedes the earlier proposed HC-T03 for
that purpose. Every earlier paragraph remains physically present as append-only history.
The replacements **must not be concatenated** with any earlier version or with one
another when transcribing the different rows.

## Event 16 — Phase-8 reproducible census and controlled witness, 2026-09-05

All programs below are ignored diagnostic scratch, copied verbatim into this journal.
No tracked test or source file was added. Commands ran from the provisioned `policy-engine`
worktree with the shared venv and bytecode writes disabled:

```sh
env PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/historical-cohorts/phase8_producer_census.py > _build/historical-cohorts/phase8-producer-census.log
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/historical-cohorts/phase8_rich_axis_witness.py > _build/historical-cohorts/phase8-rich-axis-witness.log
env PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/historical-cohorts/phase8_census_crosscheck.py > _build/historical-cohorts/phase8-census-crosscheck.log
```

All three final commands exited **0**. The census outlasted its initial 10-second tool
yield and completed on the same process without a restart; its total wall time was not
captured. The controlled witness completed in approximately **1.95 seconds** and the
successful reconciliation in approximately **0.04 seconds**. One initial reconciliation
scratch error assumed Git's paths would include `policy-engine/`; the command actually
returns `src/`/`tools/` paths relative to this working directory. That assertion failed
before any count was accepted. A direct Git observation confirmed the path form; the
scratch reader was corrected and the full identity comparison then passed. This was a
census-harness path assumption, not a producer defect or a spent product repair round.

The controlled witness's exit 0 means the declared synthetic value reached the actual
inference boundary. It does not certify a live data pass or an implementation fix.
The programs write only diagnostic JSON/log output under `_build/historical-cohorts/`;
they do not invoke extraction stages, graph writers, or database operations.

### Program: phase8_producer_census.py

Program SHA-256: `3736c8d1f5fdc2946984c7bddd76053d3768bc087a17a0bde939a1910a4610f6`.

Captured output SHA-256: `3ec2e1a0fdf8251e209d4301a2cf687ee048a4768602c91343dda964cb68d1f9`.

```python
"""Read-only source census; no producer, writer, database or network invocation."""
from pathlib import Path
from collections import Counter
import ast
import hashlib
import json
import subprocess

out=Path('_build/historical-cohorts')
roots=[Path('src'),Path('tools')]
paths=sorted(str(p) for root in roots for p in root.rglob('*') if p.is_file())
rg_paths=sorted(subprocess.check_output(['rg','--files','--hidden','--no-ignore','src','tools'],text=True).splitlines())
assert paths==rg_paths, (set(paths)-set(rg_paths),set(rg_paths)-set(paths))
tracked=set(subprocess.check_output(['git','ls-files','src','tools'],text=True).splitlines())
needles=('evidence_strength','evidence_strength_status')
text_hits=[];py_hits=[];parse_errors=[];writes=[];symbols=[]
for name in paths:
    p=Path(name)
    if p.suffix=='.pyc': continue
    raw=p.read_bytes()
    try: content=raw.decode('utf-8')
    except UnicodeDecodeError: continue
    for i,line in enumerate(content.splitlines(),1):
        if 'evidence_strength' in line:
            text_hits.append(dict(path=name,line=i,text=line))
    if p.suffix!='.py':continue
    try: tree=ast.parse(content,filename=name)
    except SyntaxError as e:
        parse_errors.append(dict(path=name,error=str(e)));continue
    parent={c:n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
    def scope(n):
        names=[]
        while n in parent:
            n=parent[n]
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):names.append(n.name)
        return '.'.join(reversed(names)) or '<module>'
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            symbols.append(dict(path=name,line=n.lineno,name=n.name,scope=scope(n)))
        keys=[];kind=None
        if isinstance(n,ast.keyword) and n.arg in needles:
            keys=[n.arg];kind='keyword'
        elif isinstance(n,ast.Dict):
            keys=[k.value for k in n.keys if isinstance(k,ast.Constant) and k.value in needles]
            kind='dict'
        elif isinstance(n,ast.Attribute) and isinstance(n.ctx,ast.Store) and n.attr in needles:
            keys=[n.attr];kind='attribute_assignment'
        elif isinstance(n,ast.Subscript) and isinstance(n.ctx,ast.Store) and isinstance(n.slice,ast.Constant) and n.slice.value in needles:
            keys=[n.slice.value];kind='subscript_assignment'
        elif isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='setattr' and len(n.args)>1 and isinstance(n.args[1],ast.Constant) and n.args[1].value in needles:
            keys=[n.args[1].value];kind='setattr'
        if keys:
            writes.append(dict(path=name,line=n.lineno,scope=scope(n),kind=kind,keys=keys))
        if isinstance(n,ast.Call):
            func=ast.unparse(n.func)
            if any(s in func for s in ['CausalClaim','ClaimOccurrenceVocabularyTransport','VersionedClaimVocabularyEnvelope','WorkRecord','_infer_edge_strength','serialize_rich_claim','serialize_llm_claim','serialize_deterministic_claim','_to_work_record']):
                py_hits.append(dict(path=name,line=n.lineno,scope=scope(n),call=func))
rg=subprocess.run(['rg','--json','--hidden','--no-ignore','--glob','!*.pyc','evidence_strength','src','tools'],capture_output=True,text=True,check=True)
rg_hits=[json.loads(line)['data'] for line in rg.stdout.splitlines() if json.loads(line)['type']=='match']
rg_set={(r['path']['text'],r['line_number']) for r in rg_hits}
py_set={(r['path'],r['line']) for r in text_hits}
assert py_set==rg_set,(py_set-rg_set,rg_set-py_set)
summary=dict(file_count=len(paths),rg_file_count=len(rg_paths),file_types=dict(Counter(Path(n).suffix or '<none>' for n in paths)),tracked_count=len(tracked),tracked_not_physical=sorted(tracked-set(paths)),python_files=sum(Path(n).suffix=='.py' for n in paths),parse_errors=parse_errors,text_hit_files=len({r['path'] for r in text_hits}),text_hit_lines=len(text_hits),rg_hit_files=len({r['path']['text'] for r in rg_hits}),rg_hit_lines=len(rg_hits),write_syntax_sites=len(writes),write_syntax_files=len({r['path'] for r in writes}),inventory_sha256=hashlib.sha256(('\n'.join(paths)+'\n').encode()).hexdigest())
for name,data in [('inventory',paths),('text-hits',text_hits),('write-sites',writes),('boundary-calls',py_hits),('symbols',symbols),('summary',summary)]:
    out.joinpath('phase8-'+name+'.json').write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
print(json.dumps(summary,sort_keys=True,indent=2))
print('WRITE_SYNTAX_SITES (candidates, not all claim producers)')
for w in writes: print(json.dumps(w,sort_keys=True))
print('BOUNDARY_CALLS')
for row in py_hits:print(json.dumps(row,sort_keys=True))
```

Complete captured output:

```text
{
  "file_count": 3355,
  "file_types": {
    ".csv": 15,
    ".cypher": 2,
    ".json": 18,
    ".md": 200,
    ".py": 3052,
    ".pyi": 5,
    ".sh": 27,
    ".sql": 1,
    ".tmpl": 7,
    ".toml": 2,
    ".ts": 12,
    ".txt": 1,
    ".typed": 2,
    ".yaml": 11
  },
  "inventory_sha256": "8c76b3fd7ece7b17f9e055a61e71df69fddc17ef1c52a94e6886cefbea65df79",
  "parse_errors": [],
  "python_files": 3052,
  "rg_file_count": 3355,
  "rg_hit_files": 47,
  "rg_hit_lines": 301,
  "text_hit_files": 47,
  "text_hit_lines": 301,
  "tracked_count": 3355,
  "tracked_not_physical": [],
  "write_syntax_files": 19,
  "write_syntax_sites": 64
}
WRITE_SYNTAX_SITES (candidates, not all claim producers)
{"keys": ["evidence_strength"], "kind": "dict", "line": 1646, "path": "src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py", "scope": "_build_numeric_rescue_prompt"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 1533, "path": "src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py", "scope": "_merge_numeric_parameter_lists"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 1468, "path": "src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py", "scope": "_deterministic_numeric_rescue_parameters"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 863, "path": "src/polisyos/data_forge/domains/academic/batch/article_extractor.py", "scope": "_normalize_empirical_parameter"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 953, "path": "src/polisyos/data_forge/domains/academic/batch/article_extractor.py", "scope": "_normalize_causal_claim"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 1949, "path": "src/polisyos/data_forge/domains/academic/batch/article_extractor.py", "scope": "serialize_rich_claim_occurrence_vocabulary"}
{"keys": ["evidence_strength_status"], "kind": "keyword", "line": 1950, "path": "src/polisyos/data_forge/domains/academic/batch/article_extractor.py", "scope": "serialize_rich_claim_occurrence_vocabulary"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 60, "path": "src/polisyos/data_forge/domains/academic/batch/llm_extractor.py", "scope": "serialize_llm_claim_occurrence_vocabulary"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 85, "path": "src/polisyos/data_forge/domains/academic/batch/llm_extractor.py", "scope": "serialize_llm_claim_occurrence_vocabulary"}
{"keys": ["evidence_strength_status"], "kind": "keyword", "line": 86, "path": "src/polisyos/data_forge/domains/academic/batch/llm_extractor.py", "scope": "serialize_llm_claim_occurrence_vocabulary"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 66, "path": "src/polisyos/data_forge/domains/academic/batch/numeric_extract.py", "scope": "_raw_numeric_rows"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 710, "path": "src/polisyos/data_forge/domains/academic/batch/resolve_finalize.py", "scope": "_curated_numeric_rows"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 864, "path": "src/polisyos/data_forge/domains/academic/batch/resolve_finalize.py", "scope": "_simulation_ready_parameters"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 263, "path": "src/polisyos/data_forge/domains/academic/batch/resolve_finalize.py", "scope": "_merge_parameters"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 154, "path": "src/polisyos/data_forge/domains/academic/batch/table_extractor.py", "scope": "tables_to_parameters"}
{"keys": ["evidence_strength", "evidence_strength_status"], "kind": "dict", "line": 2589, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py", "scope": "SKGQuery.query_prior_for_variables"}
{"keys": ["evidence_strength", "evidence_strength_status"], "kind": "dict", "line": 2654, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py", "scope": "SKGQuery._query_prior_rows_from_exact"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 217, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py", "scope": "SKGQuery.query_claims"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 407, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py", "scope": "SKGQuery._query_simulation_parameter_candidates"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 1072, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py", "scope": "SKGQuery._query_edge_support_for_names"}
{"keys": ["evidence_strength_status"], "kind": "keyword", "line": 1074, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py", "scope": "SKGQuery._query_edge_support_for_names"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 1836, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py", "scope": "SKGQuery._to_evidence_parameter"}
{"keys": ["evidence_strength", "evidence_strength_status"], "kind": "dict", "line": 2717, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py", "scope": "SKGQuery._query_prior_rows_from_family"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 1130, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py", "scope": "SKGQuery._query_exact_edge_support"}
{"keys": ["evidence_strength_status"], "kind": "keyword", "line": 1132, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py", "scope": "SKGQuery._query_exact_edge_support"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 1182, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py", "scope": "SKGQuery._query_contested_edge_support"}
{"keys": ["evidence_strength_status"], "kind": "keyword", "line": 1184, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py", "scope": "SKGQuery._query_contested_edge_support"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 1239, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py", "scope": "SKGQuery._query_family_edge_support"}
{"keys": ["evidence_strength_status"], "kind": "keyword", "line": 1241, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py", "scope": "SKGQuery._query_family_edge_support"}
{"keys": ["evidence_strength", "evidence_strength_status"], "kind": "dict", "line": 528, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore._project_claim_row"}
{"keys": ["evidence_strength", "evidence_strength_status"], "kind": "dict", "line": 658, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore.project_edge_summary"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 850, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore._explicit_v2_invalid_predicate"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 560, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore._project_claim_row"}
{"keys": ["evidence_strength_status"], "kind": "keyword", "line": 561, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore._project_claim_row"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 651, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore.project_edge_summary"}
{"keys": ["evidence_strength_status"], "kind": "keyword", "line": 652, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore.project_edge_summary"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 681, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore.project_edge_summary"}
{"keys": ["evidence_strength_status"], "kind": "keyword", "line": 682, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore.project_edge_summary"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 997, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore.audit_claim_lineage"}
{"keys": ["evidence_strength_status"], "kind": "keyword", "line": 998, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore.audit_claim_lineage"}
{"keys": ["evidence_strength", "evidence_strength_status"], "kind": "dict", "line": 35, "path": "src/polisyos/data_forge/domains/academic/knowledge/types.py", "scope": "<module>"}
{"keys": ["evidence_strength", "evidence_strength_status"], "kind": "dict", "line": 197, "path": "src/polisyos/data_forge/domains/academic/knowledge/types.py", "scope": "candidate_claim_vocabulary_store_values"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 1033, "path": "src/polisyos/foundry/analysis/attractors.py", "scope": "_certificate_for_regime"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 1017, "path": "src/polisyos/foundry/analysis/attractors.py", "scope": "_certificate_for_regime"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 1078, "path": "src/polisyos/foundry/analysis/attractors.py", "scope": "_fixed_point_attractor_from_state"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 1087, "path": "src/polisyos/foundry/methods/catalog/bayesian/pmd_hmc.py", "scope": "assess_pmd_hmc_multimodality"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 237, "path": "src/polisyos/foundry/methods/catalog/causal/literature_prior.py", "scope": "BuildLiteraturePrior.pure_step"}
{"keys": ["evidence_strength_status"], "kind": "keyword", "line": 238, "path": "src/polisyos/foundry/methods/catalog/causal/literature_prior.py", "scope": "BuildLiteraturePrior.pure_step"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 1362, "path": "src/polisyos/ir/analytics/literature.py", "scope": "_gold_record_to_causal_claim"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 1097, "path": "src/polisyos/ir/analytics/literature.py", "scope": "extract_span_grounded_claims_from_openalex_work"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 2039, "path": "src/polisyos/runtime/http/openapi_contract.py", "scope": "<module>"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 2125, "path": "src/polisyos/runtime/http/openapi_contract.py", "scope": "<module>"}
{"keys": ["evidence_strength", "evidence_strength_status"], "kind": "dict", "line": 1435, "path": "src/polisyos/runtime/quality/credal_reference.py", "scope": "_derive_l2_causal_claim"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 1115, "path": "src/polisyos/runtime/quality/credal_reference.py", "scope": "_derive_l2_causal_edge"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 1211, "path": "src/polisyos/runtime/quality/credal_reference.py", "scope": "_derive_l2_family_edge"}
{"keys": ["evidence_strength", "evidence_strength_status"], "kind": "dict", "line": 1406, "path": "src/polisyos/runtime/quality/credal_reference.py", "scope": "_derive_l2_causal_claim"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 226, "path": "src/polisyos/scientist/cross_graph/gatherers/academic.py", "scope": "_assess_literature_prior_baseline"}
{"keys": ["evidence_strength"], "kind": "keyword", "line": 149, "path": "src/polisyos/scientist/methods/discovery/prior_miner.py", "scope": "PriorMiner.mine"}
{"keys": ["evidence_strength_status"], "kind": "keyword", "line": 154, "path": "src/polisyos/scientist/methods/discovery/prior_miner.py", "scope": "PriorMiner.mine"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 935, "path": "tools/ops_runners/experiments/run_msme_final_fresg_suite.py", "scope": "policy_world_score"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 325, "path": "tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py", "scope": "main"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 346, "path": "tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py", "scope": "main"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 399, "path": "tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py", "scope": "main"}
{"keys": ["evidence_strength"], "kind": "dict", "line": 421, "path": "tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py", "scope": "main"}
BOUNDARY_CALLS
{"call": "_to_work_record", "line": 1757, "path": "src/polisyos/data_forge/domains/academic/batch/_resolve_extract_api.py", "scope": "_run_resolve_extract_pass.llm_worker"}
{"call": "ClaimOccurrenceVocabularyTransport", "line": 1940, "path": "src/polisyos/data_forge/domains/academic/batch/article_extractor.py", "scope": "serialize_rich_claim_occurrence_vocabulary"}
{"call": "WorkRecord", "line": 2052, "path": "src/polisyos/data_forge/domains/academic/batch/article_extractor.py", "scope": "_to_work_record"}
{"call": "CausalClaim.model_validate", "line": 996, "path": "src/polisyos/data_forge/domains/academic/batch/article_extractor.py", "scope": "_normalize_causal_claim"}
{"call": "serialize_rich_claim_occurrence_vocabulary", "line": 2010, "path": "src/polisyos/data_forge/domains/academic/batch/article_extractor.py", "scope": "_to_work_record"}
{"call": "VersionedClaimVocabularyEnvelope", "line": 1942, "path": "src/polisyos/data_forge/domains/academic/batch/article_extractor.py", "scope": "serialize_rich_claim_occurrence_vocabulary"}
{"call": "VersionedClaimVocabularyEnvelope.model_validate", "line": 916, "path": "src/polisyos/data_forge/domains/academic/batch/best_snapshot.py", "scope": "_validate_explicit_v2_claim_vocabulary_rows"}
{"call": "_infer_edge_strength", "line": 1634, "path": "src/polisyos/data_forge/domains/academic/batch/graph_builder.py", "scope": "load_graph"}
{"call": "ClaimOccurrenceVocabularyTransport", "line": 76, "path": "src/polisyos/data_forge/domains/academic/batch/llm_extractor.py", "scope": "serialize_llm_claim_occurrence_vocabulary"}
{"call": "serialize_llm_claim_occurrence_vocabulary", "line": 467, "path": "src/polisyos/data_forge/domains/academic/batch/llm_extractor.py", "scope": "parse_llm_result"}
{"call": "VersionedClaimVocabularyEnvelope", "line": 78, "path": "src/polisyos/data_forge/domains/academic/batch/llm_extractor.py", "scope": "serialize_llm_claim_occurrence_vocabulary"}
{"call": "ClaimOccurrenceVocabularyTransport", "line": 435, "path": "src/polisyos/data_forge/domains/academic/batch/parser.py", "scope": "serialize_deterministic_claim_occurrence_vocabulary"}
{"call": "VersionedClaimVocabularyEnvelope", "line": 437, "path": "src/polisyos/data_forge/domains/academic/batch/parser.py", "scope": "serialize_deterministic_claim_occurrence_vocabulary"}
{"call": "serialize_deterministic_claim_occurrence_vocabulary", "line": 647, "path": "src/polisyos/data_forge/domains/academic/batch/parser.py", "scope": "parse_raw_sources"}
{"call": "WorkRecord", "line": 693, "path": "src/polisyos/data_forge/domains/academic/batch/parser.py", "scope": "parse_raw_sources"}
{"call": "_to_work_record", "line": 937, "path": "src/polisyos/data_forge/domains/academic/batch/resolve_finalize.py", "scope": "run_resolve_finalize"}
{"call": "serialize_rich_claim_occurrence_vocabulary", "line": 729, "path": "src/polisyos/data_forge/domains/academic/knowledge/skg_store.py", "scope": "ingest_openalex_span_grounded_claims"}
{"call": "CausalClaimResultV2", "line": 546, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore._project_claim_row"}
{"call": "VersionedClaimVocabularyEnvelope", "line": 646, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore.project_edge_summary"}
{"call": "CausalClaimResultV2", "line": 671, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore.project_edge_summary"}
{"call": "CausalClaimResultV1", "line": 783, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore._as_v1_audit"}
{"call": "VersionedClaimVocabularyEnvelope.model_validate", "line": 503, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore._project_claim_row"}
{"call": "VersionedClaimVocabularyEnvelope", "line": 990, "path": "src/polisyos/data_forge/domains/academic/knowledge/store.py", "scope": "ScholarKnowledgeStore.audit_claim_lineage"}
{"call": "ClaimOccurrenceVocabularyTransport.model_validate", "line": 184, "path": "src/polisyos/data_forge/domains/academic/knowledge/types.py", "scope": "admit_candidate_claim_vocabulary"}
{"call": "WorkRecord.model_validate", "line": 585, "path": "src/polisyos/data_forge/domains/academic/knowledge/types.py", "scope": "adapt_jsonl_work_record_claims"}
{"call": "ClaimOccurrenceVocabularyTransport", "line": 258, "path": "src/polisyos/data_forge/domains/academic/knowledge/types.py", "scope": "adapt_legacy_claim_occurrence_transport"}
{"call": "WorkRecord.model_validate", "line": 560, "path": "src/polisyos/data_forge/domains/academic/knowledge/types.py", "scope": "adapt_jsonl_work_record_claims"}
{"call": "VersionedClaimVocabularyEnvelope", "line": 236, "path": "src/polisyos/ir/analytics/literature.py", "scope": "adapt_legacy_claim_occurrence_as_v2_absence"}
{"call": "CausalClaim", "line": 1353, "path": "src/polisyos/ir/analytics/literature.py", "scope": "_gold_record_to_causal_claim"}
{"call": "CausalClaim", "line": 1088, "path": "src/polisyos/ir/analytics/literature.py", "scope": "extract_span_grounded_claims_from_openalex_work"}
```

### Program: phase8_census_crosscheck.py

Program SHA-256: `4efd9c6a3ff486726c5974ffa3feb91a48aab85ff3d9c154b3a7c311af432693`.

Captured output SHA-256: `0d56290875c838bf2781ccad0aeedea5ae331e6ff509f54788d8781174fa4097`.

```python
"""Independent census reconciliation against the committed Git tree and declaration scan."""
from pathlib import Path
from collections import Counter
import json
import re
import subprocess
out=Path('_build/historical-cohorts')
base='b97969a3f'
assert subprocess.check_output(['git','rev-parse','--short=9','HEAD'],text=True).strip()==base
raw=subprocess.check_output(['git','grep','-n','evidence_strength',base,'--','src','tools'],text=True)
git_hits=set()
for line in raw.splitlines():
    _,path,number,_=line.split(':',3)
    assert path.startswith(('src/','tools/'))
    git_hits.add((path,int(number)))
hits=json.loads(out.joinpath('phase8-text-hits.json').read_text())
assert git_hits=={(h['path'],h['line']) for h in hits}
call_rows=json.loads(out.joinpath('phase8-boundary-calls.json').read_text())
constructors={(r['path'],r['scope']) for r in call_rows if r['call']=='ClaimOccurrenceVocabularyTransport'}
scan=subprocess.check_output(['rg','-n',r'^def (serialize_.*claim_occurrence_vocabulary|adapt_legacy_claim_occurrence_transport)','src','tools'],text=True)
declarations=set()
for line in scan.splitlines():
    path,number,source=line.split(':',2)
    declarations.add((path,re.match(r'def (\w+)',source).group(1)))
assert declarations==constructors
writes=json.loads(out.joinpath('phase8-write-sites.json').read_text())
emitting_owners={key for key in constructors if any((w['path'],w['scope'])==key and set(w['keys']) & {'evidence_strength','evidence_strength_status'} for w in writes)}
summary=dict(git_ref=base,git_hit_lines=len(git_hits),git_hit_files=len({p for p,l in git_hits}),line_identity_symmetric_difference=0,transport_constructor_owners=len(constructors),independent_declaration_owners=len(declarations),owner_identity_symmetric_difference=0,named_axis_transport_owners=len(emitting_owners),transport_owners=sorted(constructors),named_axis_owners=sorted(emitting_owners),syntax_candidate_count_by_file=dict(Counter(w['path'] for w in writes)))
out.joinpath('phase8-crosscheck.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
print(json.dumps(summary,sort_keys=True,indent=2))
```

Complete captured output:

```text
{
  "git_hit_files": 47,
  "git_hit_lines": 301,
  "git_ref": "b97969a3f",
  "independent_declaration_owners": 4,
  "line_identity_symmetric_difference": 0,
  "named_axis_owners": [
    [
      "src/polisyos/data_forge/domains/academic/batch/article_extractor.py",
      "serialize_rich_claim_occurrence_vocabulary"
    ],
    [
      "src/polisyos/data_forge/domains/academic/batch/llm_extractor.py",
      "serialize_llm_claim_occurrence_vocabulary"
    ]
  ],
  "named_axis_transport_owners": 2,
  "owner_identity_symmetric_difference": 0,
  "syntax_candidate_count_by_file": {
    "src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py": 3,
    "src/polisyos/data_forge/domains/academic/batch/article_extractor.py": 4,
    "src/polisyos/data_forge/domains/academic/batch/llm_extractor.py": 3,
    "src/polisyos/data_forge/domains/academic/batch/numeric_extract.py": 1,
    "src/polisyos/data_forge/domains/academic/batch/resolve_finalize.py": 3,
    "src/polisyos/data_forge/domains/academic/batch/table_extractor.py": 1,
    "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py": 14,
    "src/polisyos/data_forge/domains/academic/knowledge/store.py": 11,
    "src/polisyos/data_forge/domains/academic/knowledge/types.py": 2,
    "src/polisyos/foundry/analysis/attractors.py": 3,
    "src/polisyos/foundry/methods/catalog/bayesian/pmd_hmc.py": 1,
    "src/polisyos/foundry/methods/catalog/causal/literature_prior.py": 2,
    "src/polisyos/ir/analytics/literature.py": 2,
    "src/polisyos/runtime/http/openapi_contract.py": 2,
    "src/polisyos/runtime/quality/credal_reference.py": 4,
    "src/polisyos/scientist/cross_graph/gatherers/academic.py": 1,
    "src/polisyos/scientist/methods/discovery/prior_miner.py": 2,
    "tools/ops_runners/experiments/run_msme_final_fresg_suite.py": 1,
    "tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py": 4
  },
  "transport_constructor_owners": 4,
  "transport_owners": [
    [
      "src/polisyos/data_forge/domains/academic/batch/article_extractor.py",
      "serialize_rich_claim_occurrence_vocabulary"
    ],
    [
      "src/polisyos/data_forge/domains/academic/batch/llm_extractor.py",
      "serialize_llm_claim_occurrence_vocabulary"
    ],
    [
      "src/polisyos/data_forge/domains/academic/batch/parser.py",
      "serialize_deterministic_claim_occurrence_vocabulary"
    ],
    [
      "src/polisyos/data_forge/domains/academic/knowledge/types.py",
      "adapt_legacy_claim_occurrence_transport"
    ]
  ]
}
```

### Program: phase8_rich_axis_witness.py

Program SHA-256: `297c281078507e573d94585e286898cd79a55471cfe1213f2566e6009b32f65d`.

Captured output SHA-256: `5e62ccde2bf53c6f787f89817dd40e93a6ed9f5f30d5b8d17cc21376cce47468`.

```python
"""Synthetic response/transport witness. No extraction stage, data pass, writer or network."""
import asyncio
import hashlib
import json
from pathlib import Path

from polisyos.data_forge.domains.academic.batch import resolve_extract as active
from polisyos.data_forge.domains.academic.batch.graph_builder import _admitted_claim_parts, _infer_edge_strength
from polisyos.data_forge.domains.academic.knowledge.types import adapt_jsonl_work_record_claims
from polisyos.data_forge.domains.academic.knowledge.skg_store import aggregate_edge_confidence

# Deliberately synthetic inputs, supplied to normalizers only. No paper is extracted.
work={'id':'https://openalex.org/PHASE8_SYNTHETIC','title':'Synthetic transfer experiment','publication_year':2024,'cited_by_count':20,'type':'article'}
method={'span_id':'m_01','section':'methods','text':'We randomly assigned cash transfers to households in a randomized controlled trial.','sentence_index':0,'score':0.9}
support={'span_id':'r_01','section':'results','text':'The cash transfer increased household income by 12 percent relative to the control group.','sentence_index':1,'score':0.9}
bundle={'source_kind':'fulltext_html','source_basis':'fulltext','text_quality':'extracted_fulltext','method_sentences':[method],'result_sentences':[support],'claim_sentences':[support],'abstract_sentences':[]}
parsed={'causal_claims':[{'claim_text':support['text'],'claim_type':'causal_claim','cause_variable':'fiscal.cash_transfer','effect_variable':'economic.household_income','direction':'positive','claim_explicitness':'explicit','design_family_hint':'rct','evidence_strength':'rct','claim_extraction_confidence':0.8,'source_basis':'fulltext','supporting_span_ids':['r_01'],'method_span_ids':['m_01']}],'empirical_parameters':[],'mechanisms':[],'boundary_conditions':[],'methodology':'randomized controlled trial','methodology_enum':'rct','extraction_confidence':0.8,'sample_size':100}

class ControlledPool:
    def __init__(self):self.calls=[]
    async def chat_json(self,*,model,prompt,temperature):
        assert model=='phase8-controlled-response'
        assert temperature==0.0
        assert 'Each causal_claim object must use sentence IDs' in prompt
        assert '\n{\n  "claim_text"' in prompt
        assert '\n{{\n' not in prompt
        self.calls.append((model,prompt,temperature))
        return active.ProviderResponse(parsed=parsed,usage={},http_status=200,finish_reason='stop',latency_ms=0,retry_count=0,limiter_wait_ms=0,backoff_sleep_ms=0,parse_status='ok',error_class='',raw_content=json.dumps(parsed),truncated_output=False)

prompt=active._prompt_for_bundle(bundle,topic_display_names=[])
assert '"evidence_strength"' in prompt
pool=ControlledPool()
response=asyncio.run(active._await_provider_json(pool,model='phase8-controlled-response',prompt=prompt,temperature=0.0,watchdog_seconds=None))
assert len(pool.calls)==1
payload=active._normalize_extraction_payload(work,response.parsed,'phase8-controlled-response',response.usage,evidence_bundle=bundle,source_kind='fulltext_html')
result=active.ArticleExtractionResult.model_validate(payload)
assert len(result.causal_claims)==1
result=active._apply_publish_gate(result)
claim=result.causal_claims[0]
assert claim.publish_to_graph and claim.publish_blockers==[]
assert claim.evidence_strength.value=='rct'
record=active._to_work_record(result=result,raw_work=work,topic_ids=[],topic_display_names=[],run_id='phase8-synthetic-witness',pass_name='diagnostic')
wire=record.model_dump_json()
reloaded=adapt_jsonl_work_record_claims(json.loads(wire),provenance='legacy_jsonl')
assert len(reloaded.causal_claims)==1
transport,operational,values=_admitted_claim_parts(reloaded.causal_claims[0])
assert values['evidence_strength']=='rct'
assert values['evidence_strength_status']=='candidate'
encoded=_infer_edge_strength(values)
assert encoded=='rct'
confidence=aggregate_edge_confidence([(encoded,0.8)])
assert confidence>0.0
print(json.dumps(dict(controlled_provider_calls=len(pool.calls),real_model_calls=0,extraction_stages_run=0,database_writes=0,rendered_prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),rendered_prompt_chars=len(prompt),normalized_claims=len(result.causal_claims),claim_publish_to_graph=claim.publish_to_graph,claim_publish_blockers=claim.publish_blockers,roundtrip_claims=len(reloaded.causal_claims),source_evidence=values['evidence_strength'],source_evidence_status=values['evidence_strength_status'],inferred_edge_strength=encoded,pure_single_claim_confidence=confidence),sort_keys=True))
print('scope: active prompt/provider-wrapper/response-normalizer/publish-gate/WorkRecord/JSONL/admission/inference functions executed with synthetic bytes. The scheduler, extractor coroutine, artifact writers, graph loader and adjudicator were not run; actual publication still requires a separately admitted publishable adjudication.')
print('STOP: the active rich resolve_extract route can carry a non-absent candidate evidence axis to graph inference; the exclusive-dead-producer diagnosis is refuted.')
```

Complete captured output:

```text
{"claim_publish_blockers": [], "claim_publish_to_graph": true, "controlled_provider_calls": 1, "database_writes": 0, "extraction_stages_run": 0, "inferred_edge_strength": "rct", "normalized_claims": 1, "pure_single_claim_confidence": 0.55, "real_model_calls": 0, "rendered_prompt_chars": 9183, "rendered_prompt_sha256": "1727fc4f0806f0783fe62ab735f0a2de5153c3580e7f6c6ef3aa2879843366e1", "roundtrip_claims": 1, "source_evidence": "rct", "source_evidence_status": "candidate"}
scope: active prompt/provider-wrapper/response-normalizer/publish-gate/WorkRecord/JSONL/admission/inference functions executed with synthetic bytes. The scheduler, extractor coroutine, artifact writers, graph loader and adjudicator were not run; actual publication still requires a separately admitted publishable adjudication.
STOP: the active rich resolve_extract route can carry a non-absent candidate evidence axis to graph inference; the exclusive-dead-producer diagnosis is refuted.
```

### Census decoding completeness receipt

A final reconciliation checked every path in the recorded inventory for UTF-8 decoding,
so the census's guarded decode branch cannot have silently excluded a source file:

```python
from pathlib import Path
from collections import Counter
import json
paths = json.loads(Path('_build/historical-cohorts/phase8-inventory.json').read_text())
text = Counter()
bad = []
for name in paths:
    try:
        Path(name).read_bytes().decode('utf-8')
    except UnicodeDecodeError:
        bad.append(name)
    else:
        text[Path(name).suffix] += 1
assert not bad
assert text['.py'] == 3052
print(json.dumps(dict(utf8_decoded_files=sum(text.values()),
                      utf8_python_files=text['.py'], decode_failures=bad), sort_keys=True))
```

Observed exit 0 and output:

```text
{"decode_failures": [], "utf8_decoded_files": 3355, "utf8_python_files": 3052}
```

This reconciles the already measured source denominator; no new producer or data path
was investigated after the stop. All 3,052 Python files reached the AST parser and the
recorded parse-error set is empty. The final numbered-source read also confirmed the
transport, flattening, JSONL, active prompt replacement, and provider-wrapper anchors
used in HC-F16/HC-F17.


## Event 17 — Phase-8 closeout, custody, and checker disposition, 2026-09-05

Events 15–16 were committed as `56c7f14999796f4f7b3e312b7fb02653171bf222` on
`codex/debt-historical-cohorts` and read back from that branch. The committed journal
equals the worktree file, preserves the original 179,996-byte prefix (Events 1–14)
verbatim, and contains all three executed programs and their captured outputs verbatim.
`git diff --check` passed before commit and against the committed continuation. The
observed branch was attached and clean: `## codex/debt-historical-cohorts`.

### Single checker disposition receipt — skipped after the prerequisite stop

The Phase-8 brief anticipated source/test work and therefore a checker run. Stop rule 1
prevented that work: **no checker-read file changed**. The explicitly unchanged predicate
is based on actual changes to the register, ledger, `docs/plans/`, `tools/`, `src/`,
`tests/`, or schemas; authorization to change them is not a change. This continuation is
journal-only, so **zero bound checker invocations** occurred. Receipt against its
committed changes:

```sh
git diff --name-only b97969a3f..HEAD
```

```text
policy-engine/docs/superpowers/journals/2026-09-05-historical-cohorts.md
```

### Final production-data custody

The closing custody read opened the pinned DuckDB file in binary read mode, computed
`hashlib.file_digest(..., 'sha256')`, and checked its mode and size. It completed in
approximately 1.41 seconds and confirmed:

```text
path: production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb
sha256:583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967
mode: -r--r--r--
size: 2390503424 bytes
```

No production-data write, chmod, real model/network request, extraction stage, batch,
graph writer, adjudicator invocation, route enablement, live lane, rebase, force-push,
or stash occurred. The controlled response witness called the real provider wrapper
with an in-memory pool and exercised pure normalization, gate, transport, and inference
functions; it did not generate or persist research data. No product implementation or
handler repair was made. The one fix round remains unspent.

The committed journal SHA-256 **before this receipt append** was
`2f1a787cfff44ee8cd65fb0c8a8a84c09f8be6d66371292695a1f74b788df03d` (Events 1–16).
This receipt is committed separately, followed by a final branch/path/prefix readback.
HC-T01-R4 and HC-T02-R4 replace their corresponding `-R3` paragraphs in full, with
HC-T03-R4 separately transcribed to the producer row. They **must not be concatenated**
with the physically preserved earlier versions or with one another.
