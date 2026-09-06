# Vocabulary value provenance — 2026-09-06

## Event 1 — scope, baseline, and ordered work

Worktree: `/Users/deniskopylov/polisyos/.worktrees/debt-vocabulary-value-provenance/policy-engine`.
Branch: `codex/debt-vocabulary-value-provenance`; initial HEAD
`37c20aaa5124ebbe4868aa040eb3b0874458e680`; initial `git status -sb` was clean and attached.
All four bound rows in `docs/plans/active/DEBT-REGISTER.md` were read before design.
That directory is read-only for this lane; the architect transcribes at merge.

Order: independently reconcile the two inherited populations; row 1 whole-enum red,
single precedence repair, green and stored-footprint stop assessment; row 2 consumer
census before route selection and its own red/green repair; row 3 complete origin and
round-trip measurement before representation; row 4 only on its own negative signal.
Each row has at most one fix round. Any stored-schema change requires the user's
authorization naming its snapshots and `schemas/snapshots/ir/_manifest.json`.
No extraction run, model call, production producer invocation, data rewrite or historical
cohort assignment is authorized. Pure normalizer calls and controlled test fixtures are
used for the expressly requested behavioral tests; production data is read-only.
Rows 1 and 2 have independent delivery boundaries; a later stop cannot erase their work.

Pattern pass: P05/P15 (manufactured values must not acquire judgment authority), P07
(persisted provenance and schema boundary), P29/P32/P33 (execute the actual behavior,
not presence markers), P35/P36 (complete denominators and finding IDs), P38 (a retained
hint or a supplied key is not proof of its producer), P40 (one fix round per row), and
P41 (do not attribute a red gate without replay). Reuse the canonical normalizer,
graph writer, parameter DTO and SKG intake. Current provenance chain is
`artifact_missing` / `semantic_test_missing`; no new capability is claimed.
Acceptance: enum identity, adjudication-consistent persisted cell, then producer-bound
origin surviving the real round-trip, including an omitted-field negative. Companions
are this append-only journal and focused tests. The only contended resource is the
pinned DuckDB snapshot: all measurement connections use `read_only=True`, serialized.

Runtime: `/Users/deniskopylov/polisyos/policy-engine/.venv/bin/python` with
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src`; import readback confirmed the worktree's
`article_extractor.py`. Initial binary SHA-256 of
`production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb`
is `583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`.
An initial schema-inspection command exited 1 after that successful hash because it
guessed `ac_evidence_parameters`; the actual table is `ac_skg_parameters`. This is an
instrument error, not a product finding; subsequent inspection uses actual catalog names.

The bound debt checker is reserved for exactly one final invocation, alone on its
command line, redirected to `_build/x.log`, with its actual process exit status and a
full finding-code census captured separately. Tests are selected by exact file/node;
no directory-wide suite is authorized.

## Event 2 — VV-F01: independent population verification

Both inherited populations were verified before using their counts. Every connection
opened the pinned DuckDB file with `read_only=True`; the only SQL-created object in
these measurements is a connection-local TEMP VIEW. No production file was written.

| Complete population | First count | Independent count |
| --- | ---: | ---: |
| `ac_article_extractions.extraction_json` documents | Python JSON walk 310,829 | SQL 310,829; distinct IDs 310,829 |
| Embedded claim objects | 137,714 | SQL array traversal 137,714 |
| Recursive `evidence_strength` keys | 5,133 | SQL recursive JSONPath 5,133 |
| Documents with those keys | 1,577 | SQL 1,577 |
| Keys under `metadata.simulation_ready_numeric_estimates[*]` | 5,133 | SQL namespace extraction 5,133 |
| Strength keys outside that namespace | 0 | Recursive total minus namespace total 0 |
| Recursive `evidence_strength_status` keys | 0 | SQL recursive JSONPath 0 |
| `ac_skg_parameters.parameter_json` rows | 51,908 | SQL 51,908 |
| Raw parameter payloads containing `evidence_strength` | 0 | SQL `json_exists` 0 |
| Real SKG reader results equal to `UNKNOWN` | 51,883 | Direct DTO validation 51,883; independent SQL acceptance partition 51,883 |
| Raw parameter payloads rejected | 25 | Direct DTO validation 25; independent SQL 25, with identical rejected IDs |

This reconciles HC-F18 and the unknown-weight journal's UW-F02/F03 measurement.
The row-4 **head prose** remains stale: **all 51,908 omit the key**, while **51,883
successfully decode as unknown**. The other 25 have reversed confidence-interval bounds.
The independent SQL does not infer judgment provenance: it enumerates numeric validity
and missing-key conditions, and its rejected-ID symmetric difference from the actual
reader is zero. Neither population contains a demonstrated recorded-unknown judgment.
The 5,133 numeric-metadata values are 1 cross_sectional + 1,095 meta_analysis + 2,938
observational + 35 panel_fe + 328 quasi_natural + 736 rct. Their historical origins remain
unresolved; no cohort was retrospectively assigned from presence.

Exact successful commands (working directory is the worktree product root):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -u _build/vocabulary-value-provenance/measure.py > _build/vocabulary-value-provenance/measure.log 2>&1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/vocabulary-value-provenance/parameter-sql-crosscheck.py > _build/vocabulary-value-provenance/parameter-sql-crosscheck.log 2>&1
```

Both exited 0. The first draft of the census exited 1 because `Counter.update(data)`
was given a mapping's values rather than `data.keys()`; no result from that failed
instrument was used. An earlier catalog inspection also guessed `ac_raw_claims` and
exited 1; the measured table is `ac_causal_claims_raw`.

## Event 3 — VV-F02: row 1, one red/green fix round

The property is exact enum identity before any substring alias. The old code tests
substring containment first: `iv` is contained in `review_narrative`. That proxy and
identity diverge on five enum members, even though all 20 have exact self-aliases.
The production repair moves the exact alias lookup before the substring loop. No
alias or stored schema changes. Empty and unmatched inputs return `DesignFamily.UNCLEAR`
(`"unclear"`). Non-exact strings still follow the existing substring alias behavior;
this repair does not certify arbitrary free-text design classification.

The test's parameter set comes from the entire enum, not a list of the five failures.
It also exercises capitalization/space normalization and three unmatched/empty inputs.
The expectation is the enum identity, independent of the alias implementation. Reverting
just the precedence change would reintroduce the observed five failures.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q tests/unit/data_forge/domains/academic/batch/test_article_extractor.py -k 'design_family' > _build/vocabulary-value-provenance/row1-red.log 2>&1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q tests/unit/data_forge/domains/academic/batch/test_article_extractor.py > _build/vocabulary-value-provenance/row1-green.log 2>&1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check src/polisyos/data_forge/domains/academic/batch/article_extractor.py tests/unit/data_forge/domains/academic/batch/test_article_extractor.py
```

Red: exit 1, 5 failed / 18 passed, with exactly the five failures below. Green: exit 0,
52 passed in the exact selected file. Ruff: exit 0, `All checks passed!`. No directory-wide
test run. The runtime import was read back from this worktree, not the shared environment's
editable checkout. Before-table values were recorded before editing the implementation;
after-table values are from importing the edited implementation and traversing the enum.

| Enum value (all 20) | Before | After |
| --- | --- | --- |
| `rct` | `rct` | `rct` |
| `iv` | `iv` | `iv` |
| `did` | `did` | `did` |
| `rdd` | `rdd` | `rdd` |
| `synthetic_control` | `synthetic_control` | `synthetic_control` |
| `event_study` | `event_study` | `event_study` |
| `quasi_experimental_other` | `quasi_experimental_other` | `quasi_experimental_other` |
| `quasi_experimental_did` | `did` | `quasi_experimental_did` |
| `quasi_experimental_rdd` | `rdd` | `quasi_experimental_rdd` |
| `panel_fe` | `panel_fe` | `panel_fe` |
| `ols` | `ols` | `ols` |
| `ols_cross_sectional` | `ols` | `ols_cross_sectional` |
| `meta_analysis` | `meta_analysis` | `meta_analysis` |
| `review` | `review` | `review` |
| `review_narrative` | `iv` | `review_narrative` |
| `review_meta_analysis` | `meta_analysis` | `review_meta_analysis` |
| `theoretical` | `theoretical` | `theoretical` |
| `structural_model` | `structural_model` | `structural_model` |
| `time_series_cointegration` | `time_series_cointegration` | `time_series_cointegration` |
| `unclear` | `unclear` | `unclear` |

## Event 4 — VV-F03: nonzero stored footprint and the row-1 stop

**67,791 stored `design_family_hint` keys across 20,900 extraction documents**, all at
`causal_claims[*].design_family_hint`, all `extraction_mode=resolve_extract`. Python's
complete 310,829-document recursive walk and SQL's complete recursive JSONPath count
agree on both numbers. There are 58,693 resolve_extract documents in total and 252,136
deterministic documents (310,829 altogether), all in recorded run `20260406T074654Z`.
The separate `ac_causal_claims_raw` table has 137,589 rows: 67,791 nonempty hints with
the same full value distribution and 69,798 empty strings. These are two persisted
representations of the route, not 135,582 independent defects.

| Stored hint | Extraction JSON occurrences | Raw-table nonempty cells |
| --- | ---: | ---: |
| `did` | 246 | 246 |
| `event_study` | 41 | 41 |
| `iv` | 7,197 | 7,197 |
| `meta_analysis` | 1,409 | 1,409 |
| `ols` | 4,608 | 4,608 |
| `panel_fe` | 1,357 | 1,357 |
| `quasi_experimental_other` | 851 | 851 |
| `rct` | 855 | 855 |
| `rdd` | 20 | 20 |
| `review` | 12 | 12 |
| `structural_model` | 415 | 415 |
| `synthetic_control` | 7 | 7 |
| `theoretical` | 17,172 | 17,172 |
| `time_series_cointegration` | 1 | 1 |
| `unclear` | 33,600 | 33,600 |

The static route is `_resolve_extract_api.py`'s `_normalize_extraction_payload` intake
and `ArticleExtractor._extract_single` -> `article_extractor._normalize_extraction_payload`
-> `_normalize_causal_claim` -> `_normalize_design_family` -> typed `CausalClaim` ->
`_to_work_record` / `serialize_rich_claim_occurrence_vocabulary` -> `graph_builder.load_graph`
-> the extraction JSON and raw-claim inserts. `graph_builder.py` constructs
`extraction_payload` from admitted claim transports; the raw insert reads the admitted
`design_family_hint`. A complete AST walk over **2,619 `src/**/*.py` + 433 `tools/**/*.py`
= 3,052 Python files**, with zero parse errors, found one named call to each of
`_normalize_design_family` and `_normalize_causal_claim`, both in `article_extractor.py`.
This is a named-static-call census, not a claim of complete dynamic dispatch analysis.

The snapshot's `meta/source_lineage.json` routes the extraction and raw-claim tables to
its original academic source; it does not bind a normalizer source revision. The current
code path plus the retained resolve_extract envelopes establish a nonzero **route
footprint**, sufficient to refuse a capability-only close. They do **not** establish
which historical inputs changed value or prove the exact historical normalizer revision.
In particular, the 7,197 stored `iv` hints cannot be divided into genuine IV inputs and
mis-normalized narrative reviews from their value. **Actual corrupted-input count and
per-value historical origin: `not_established`.** No row is called corrupted solely because
its value is a shorter alias; no historical field is rewritten.

**VV-D01 — stop-rule disposition.** The user explicitly says to stop if row 1 has a
stored footprint, since its close changes from a capability-only repair to a data defect.
The forward precedence repair is preserved and committed; the debt row stays open with
its historical disposition unresolved. The strict-order continuation into phase 2 is
stopped here. The instruction to preserve rows independently is satisfied by retaining
row 1's completed forward repair; it does not authorize bypassing the earlier explicit
footprint stop to start row 2. No schema permission is inferred from that preservation rule.

Phase 2 consumer census, route choice and red/green test are **not performed after this
stop**. The brief's 488/7,526 observation remains inherited HC-F06 evidence, not a new
measurement in this lane. Phase 3's complete origin enumeration and positive/negative
persistence traces are also **not reached**. The row lists four producing origins before
this lane (candidate extraction, normalizer fallback, SKG fallback, deterministic
inheritance); that is an inherited enumeration, not a freshly measured count. No
before/after origin-count reduction is claimed from the design fix. Row 4's omitted-field
negative is not delivered and cannot close on adjacency. This is a stopped handoff,
not completion of all four rows.

## Event 5 — bounded verification and candidate finding

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m tools.devx.architecture.guardrails check --skip-generated-checks > _build/vocabulary-value-provenance/guardrails.log 2>&1
```

Exit 1. Generated freshness probes were explicitly excluded from this focused check;
no schema was edited and no full generated-artifact verification is claimed. The observed
red is deep-import baseline drift plus three acquisition-admission imports from
`src/polisyos/runtime/http/services/acquisition_admission_bundle.py` to
`polisyos.core.artifacts.manifest`, `.signing`, and `.write_contract`.
**VV-C01 candidate row:** acquisition-admission deep-import baseline/facade discrepancy;
owner routing: runtime/architecture. Left untouched, not opened in the active register,
not a reason to continue this lane's repair. Its provenance is `not_established` under
P41: no replay from the slice base was run, so this journal does not call it inherited
or assert a disjoint complete input denominator. The guardrail is red, never reported green.

`git diff --check` exited 0. Mechanism freeze is the five-line normalizer change and
its enum/unmatched tests; further edits in this delivery are journal appends only.

## Event 6 — reproducible measurement programs and evidence bindings

The following complete programs reconstruct the counts read-only. Scratch programs and
logs stay in `_build/`; this journal is the durable receipt.

### `measure.py`

SHA-256 `2d23a420cd7e50431bd876985b46ab015822b2776ffce71df9b4de8e4ba8f547`.

```python
"""Read-only reconciliation of inherited populations and the design-hint footprint."""
from collections import Counter
import json
from pathlib import Path
import duckdb
from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery

out = Path('_build/vocabulary-value-provenance')
db = Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
c = duckdb.connect(str(db), read_only=True, config={'threads':2, 'memory_limit':'2GB', 'temp_directory':str(out/'duckdb-temp')})
counts = Counter()
paths = Counter()
values = Counter()
hints = Counter()
keys = {'root': Counter(), 'metadata': Counter(), 'claim': Counter()}
ids = set()
hit_ids = set()
hint_ids = set()

def walk(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            current = path + (key,)
            if key in {'evidence_strength', 'evidence_strength_status', 'design_family_hint'}:
                yield key, current, child
            yield from walk(child, current)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child, path + ('[*]',))

cursor = c.execute('SELECT extraction_id, extraction_mode, extraction_json FROM ac_article_extractions')
while batch := cursor.fetchmany(1024):
    for eid, mode, raw in batch:
        data = json.loads(raw)
        ids.add(eid)
        counts['documents'] += 1
        keys['root'].update(data.keys())
        keys['metadata'].update(data.get('metadata', {}).keys())
        for claim in data.get('causal_claims', []):
            keys['claim'].update(claim.keys())
            counts['claims'] += 1
        for key, path, value in walk(data):
            counts[key] += 1
            if key != 'design_family_hint':
                hit_ids.add(eid)
                paths['.'.join(path)] += 1
                values[str(value)] += 1
            else:
                hint_ids.add(eid)
                hints[(mode, '.'.join(path), str(value))] += 1
summary = {'python':dict(counts), 'distinct_documents':len(ids), 'strength_documents':len(hit_ids), 'hint_documents':len(hint_ids), 'strength_paths':dict(paths), 'strength_values':dict(values), 'hint_distribution':[list(k)+[v] for k,v in sorted(hints.items())], 'complete_field_census':{k:dict(v) for k,v in keys.items()}}
summary['sql_axes'] = c.execute("""SELECT count(*), count(DISTINCT extraction_id), sum(json_array_length(extraction_json,'$.causal_claims')), sum(len(json_extract(extraction_json,'$..evidence_strength'))), sum(len(json_extract(extraction_json,'$..evidence_strength_status'))), count(*) FILTER (WHERE len(json_extract(extraction_json,'$..evidence_strength'))>0), sum(len(json_extract(extraction_json,'$.metadata.simulation_ready_numeric_estimates[*].evidence_strength'))), sum(len(json_extract(extraction_json,'$..design_family_hint'))), count(*) FILTER (WHERE len(json_extract(extraction_json,'$..design_family_hint'))>0) FROM ac_article_extractions""").fetchone()
assert summary['sql_axes'] == (counts['documents'],len(ids),counts['claims'],counts['evidence_strength'],counts['evidence_strength_status'],len(hit_ids),counts['evidence_strength'],counts['design_family_hint'],len(hint_ids))
params = c.execute('SELECT param_id, canonical_name, parameter_json FROM ac_skg_parameters').fetchall()
decodes = Counter()
rawkeys = Counter()
normal = Counter()
rejected = []
for pid, name, raw in params:
    payload = json.loads(raw)
    rawkeys.update(payload.keys())
    result = SKGQuery._to_evidence_parameter(name, payload)
    decodes[result.evidence_strength.value if result else '<rejected>'] += 1
    # Independently validate the ordinary normalized DTO path, outside the reader's fallback.
    from polisyos.ir.analytics.literature import EvidenceParameter
    try:
        other = EvidenceParameter.model_validate(SKGQuery._normalize_evidence_parameter_payload(name,payload))
        normal[other.evidence_strength.value] += 1
    except (ValueError,TypeError):
        normal['<rejected>'] += 1
    if result is None:
        rejected.append(pid)
summary['parameters'] = {'python_rows':len(params),'reader_decodes':dict(decodes),'independent_direct_validation':dict(normal),'raw_keys':dict(rawkeys),'sql_rows_and_presence':c.execute("SELECT count(*),count(*) FILTER(WHERE json_exists(parameter_json,'$.evidence_strength')) FROM ac_skg_parameters").fetchone(),'rejected_ids':rejected}
assert decodes == normal
assert len(params) == summary['parameters']['sql_rows_and_presence'][0]
assert rawkeys['evidence_strength'] == summary['parameters']['sql_rows_and_presence'][1]
summary['raw_hints'] = c.execute('SELECT design_family_hint,count(*) FROM ac_causal_claims_raw GROUP BY 1 ORDER BY 1').fetchall()
summary['raw_total'] = c.execute('SELECT count(*) FROM ac_causal_claims_raw').fetchone()[0]
summary['extraction_modes'] = c.execute('SELECT extraction_mode,count(*) FROM ac_article_extractions GROUP BY 1 ORDER BY 1').fetchall()
summary['runs'] = c.execute('SELECT run_id,extraction_mode,count(*) FROM ac_article_extractions GROUP BY 1,2 ORDER BY 1,2').fetchall()
(out/'measure.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k != 'complete_field_census'}, indent=2,sort_keys=True))
c.close()
```

### `parameter-sql-crosscheck.py`

SHA-256 `257cde4d5846fce33666b38842dde614419f29509b0cc4e62b3401af9c418c4e`.

```python
"""Independently count the raw parameter acceptance partition in SQL."""
import json
from pathlib import Path
import duckdb
out=Path('_build/vocabulary-value-provenance')
c=duckdb.connect('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb',read_only=True)
c.execute("""CREATE TEMP VIEW decoded AS SELECT param_id,
try_cast(json_extract_string(parameter_json,'$.value') AS DOUBLE) AS value,
try_cast(json_extract_string(parameter_json,'$.ci_low') AS DOUBLE) AS lo,
try_cast(json_extract_string(parameter_json,'$.ci_high') AS DOUBLE) AS hi,
try_cast(json_extract_string(parameter_json,'$.std_error') AS DOUBLE) AS se,
json_exists(parameter_json,'$.evidence_strength') AS supplied
FROM ac_skg_parameters""")
rejected={r[0] for r in c.execute('SELECT param_id FROM decoded WHERE value IS NULL OR NOT isfinite(value) OR (lo IS NOT NULL AND hi IS NOT NULL AND (lo>hi OR NOT isfinite(lo) OR NOT isfinite(hi))) OR (se IS NOT NULL AND (se<0 OR NOT isfinite(se)))').fetchall()}
rows=c.execute('SELECT count(*),count(*) FILTER(WHERE supplied),count(*) FILTER(WHERE lo>hi) FROM decoded').fetchone()
s=json.loads((out/'measure.json').read_text())
assert rejected==set(s['parameters']['rejected_ids'])
assert rows==(51908,0,25)
result={'sql_rows':rows[0],'sql_strength_keys':rows[1],'sql_reversed_intervals':rows[2],'sql_accepted_default_unknown':rows[0]-len(rejected),'sql_rejected':len(rejected),'sql_vs_reader_rejected_id_symmetric_difference':0}
print(json.dumps(result,sort_keys=True))
(out/'parameter-sql-crosscheck.json').write_text(json.dumps(result,indent=2)+'\n')
c.close()
```

### Captured output bindings

| File under `_build/vocabulary-value-provenance/` | SHA-256 |
| --- | --- |
| `measure.log` | `8e113be523242b6bfe0e9716fda949e978c4e0dad211e377fbd8ad6c370f9031` |
| `measure.json` | `7fd97178fd4d3bdacb1ca6c3616fd7074849dd985d062b0e3abca690b1ac95c4` |
| `parameter-sql-crosscheck.log` | `14d4afffe67f8a8be5379a856cae697ae6b53dc72a184636b27d0a504c4a8c3e` |
| `row1-red.log` | `0d9241b0125950f4f2fef90d13cab64912fc08de42638660f6dfc954311969ca` |
| `row1-green.log` | `4cf2124032e464147e816ec20702b3b32e3647b01af12dd56f695de26cf6f779` |
| `guardrails.log` | `83222fcdf3ced06fdbdcf01c6f376ec616139b272b8167cb42617f8aae5e85f4` |
| `design-calls.json` | `eee74281401014438edd3d6dcf5f056082b366960cb2fac5a6abbe9ab1a910db` |

## Event 7 — transcriber-ready dispositions, one paragraph per row

**`design-normalization-matches-a-substring-before-identity` — retain `open`; forward
repair delivered, historical disposition stopped.** VV-F02 proves the exact-identity
precedence repair red-first over all 20 DesignFamily members: the five named failures
become 20/20 round-trips; unmatched stays `unclear`; the focused file has 52 passing
cases. VV-F03 finds 67,791 retained resolve_extract hints across 20,900 documents and
the same nonempty raw-table population, so a capability-only close is refused under
stop rule 3. That route footprint is not the number of corrupted historical inputs:
the historical normalizer revision and pre-normalization values are not established.
No stored value or schema changed; the forward repair is preserved independently.

**`evidence-row-design-hint-differs-from-adjudication` — retain `open`; phase 2 not
reached because of row 1's explicit footprint stop.** This lane does not supply the
required consumer census, choose a rename/adjudicated-value route, alter the writer,
or discharge its red/green signal. HC-F06's inherited 488/7,526 remains the prior
measurement; no schema/manifest authorization was requested or exercised here.

**`parameter-evidence-strength-has-no-value-provenance` — retain `open`; phase 3 not
reached.** VV-F01 independently verifies HC-F18's 5,133 parameter-metadata strength
keys across 1,577 of 310,829 documents, zero occurrences outside that namespace and
zero evidence_strength_status keys. All historical origins remain unresolved. The
four inherited producing origins were not re-enumerated through all paths after the
earlier stop, and no reduction, persisted provenance mechanism or positive trace of
an actual recorded unknown judgment is claimed. Presence remains insufficient.

**`parameter-contract-cannot-distinguish-unsupplied-from-unknown` — retain `open` and
subordinate to value provenance.** VV-F01 corrects the raw denominator: all 51,908 raw
parameter payloads omit evidence_strength; the real SKG reader accepts 51,883 as
UNKNOWN and rejects 25 reversed intervals, independently reconciled in SQL with an
identical rejected-ID set. No field, generated snapshot or manifest changed. The
required negative proving that an omitted field cannot present as a recorded judgment
was not delivered; row 4 does not close by adjacency to the design repair.
