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

## Event 8 — continuation correction and the single checker receipt

The user said `continue` after the initial row-1 stop report. The earlier VV-D01
interpretation stopped the whole lane; that was too broad against the user's
**per-row independent** stop rule and required delivery of phases 1–2. The row-1
historical close remains stopped, its forward repair remains committed as
`04c6bd0e9`, and row 2 now proceeds independently. Events 4 and 7 remain as historical
entries; final transcription below will supersede their not-reached dispositions.

The single bound checker has completed at `04c6bd0e9`: **process exit 0** from the
exec-session completion, with no command after it that could mask that status.
Its invocation was alone on its line after configuring PATH/PYTHONPATH on a prior line:

```sh
python tools/quality/validation/check_debt_ledger.py --check > _build/x.log 2>&1
```

The full code census used exactly:

```sh
grep -oE '^[a-z_]+:' _build/x.log | sort | uniq -c
```

```text
   9 closure_signal_count_exit_disagreement:
   9 closure_signal_identity_unresolvable:
   1 closure_signal_runner_unsupported:
  10 register_supplies_missing_standing:
```

All 29 findings appear under the checker's informational section. No finding is
filtered out by expected code. The invocation collected 44 named pytest selections
with `--collect-only`, not test execution. It is **not repeated** on continuation.
This was premature relative to the final lane endpoint; the receipt binds the
row-1 commit, not later source changes. Final source verification will be focused
tests and lint, and the stale scope of this receipt will stay explicit.

Complete captured checker output (SHA-256 `bd9cb15629ac3d74442136e662462f12380de760f02f59eea002f7e2aeaa21a1`):

```text
register_ids=199
gy_ids=38
atlas_debt_rows=22
frontend_disposition_entries=261
frontend_ds8_assignment_rows=217
gy_history_blocks=6
gy_absent_from_register=15
gy_absent_from_register_closed=15
ds5_nonclosure_rows=27
ds5_planless_routes=4
irregular_section_e_branch_rows=1
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
Informational findings (do not block):
closure_signal_count_exit_disagreement: DS11-EXTERNAL-A11Y-COUNTERSIGN: tests/repo_quality/docs/test_accessibility_evidence.py::test_external_countersign_is_content_bound_current_and_scope_exact; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: DS11-FULL-TRUST-CENTER-AND-DOCS-IA: tests/repo_quality/frontend/test_public_surface_claim_ownership.py::test_every_retained_trust_docs_route_has_an_approved_owner_and_evidence_contract; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: DS11-GROUNDED-PERFORMANCE: tests/integration/runtime_quality/test_first_governed_promotion.py::test_promoted_design_supplies_content_bound_public_performance_evidence; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: DS11-PUBLIC-SIGNATURE-POPULATION: tests/unit/runtime/http/test_public_export.py::test_first_governed_public_signature_is_custody_bound; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: DS11-SCOPE-ADJUDICATION-RECORD: tests/unit/core/contracts/test_scope_adjudication.py::test_four_way_ruling_is_produced_consumed_and_plane_specific; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: ds10-global-case-index-producer-allocation: tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: ds10-public-decision-rendering: tests/unit/runtime/http/test_public_export.py::test_public_decision_projection_is_custody_bound; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: global-case-index-producer-missing: tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_count_exit_disagreement: shared-git-hook-hardcodes-one-worktree-path: tests/repo_quality/tools/test_repo_hooks.py::test_shared_hook_contains_no_worktree_specific_path; ast=False; collected=0; exit=4; count=selects=0; exit=unresolvable
closure_signal_identity_unresolvable: DS11-EXTERNAL-A11Y-COUNTERSIGN: tests/repo_quality/docs/test_accessibility_evidence.py::test_external_countersign_is_content_bound_current_and_scope_exact; ast=False; collected=0; exit=4; ERROR: not found: /Users/deniskopylov/polisyos/.worktrees/debt-vocabulary-value-provenance/policy-engine/tests/repo_quality/docs/test_accessibility_evidence.py::test_external_countersign_is_content_bound_current_and_scope_exact | (no match in any of [<Module test_accessibility_evidence.py>])
closure_signal_identity_unresolvable: DS11-FULL-TRUST-CENTER-AND-DOCS-IA: tests/repo_quality/frontend/test_public_surface_claim_ownership.py::test_every_retained_trust_docs_route_has_an_approved_owner_and_evidence_contract; ast=False; collected=0; exit=4; no tests collected in 0.00s | ERROR: file or directory not found: tests/repo_quality/frontend/test_public_surface_claim_ownership.py::test_every_retained_trust_docs_route_has_an_approved_owner_and_evidence_contract
closure_signal_identity_unresolvable: DS11-GROUNDED-PERFORMANCE: tests/integration/runtime_quality/test_first_governed_promotion.py::test_promoted_design_supplies_content_bound_public_performance_evidence; ast=False; collected=0; exit=4; no tests collected in 0.00s | ERROR: file or directory not found: tests/integration/runtime_quality/test_first_governed_promotion.py::test_promoted_design_supplies_content_bound_public_performance_evidence
closure_signal_identity_unresolvable: DS11-PUBLIC-SIGNATURE-POPULATION: tests/unit/runtime/http/test_public_export.py::test_first_governed_public_signature_is_custody_bound; ast=False; collected=0; exit=4; no tests collected in 0.00s | ERROR: file or directory not found: tests/unit/runtime/http/test_public_export.py::test_first_governed_public_signature_is_custody_bound
closure_signal_identity_unresolvable: DS11-SCOPE-ADJUDICATION-RECORD: tests/unit/core/contracts/test_scope_adjudication.py::test_four_way_ruling_is_produced_consumed_and_plane_specific; ast=False; collected=0; exit=4; ERROR: not found: /Users/deniskopylov/polisyos/.worktrees/debt-vocabulary-value-provenance/policy-engine/tests/unit/core/contracts/test_scope_adjudication.py::test_four_way_ruling_is_produced_consumed_and_plane_specific | (no match in any of [<Module test_scope_adjudication.py>])
closure_signal_identity_unresolvable: ds10-global-case-index-producer-allocation: tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index; ast=False; collected=0; exit=4; ERROR: not found: /Users/deniskopylov/polisyos/.worktrees/debt-vocabulary-value-provenance/policy-engine/tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index | (no match in any of [<Module test_capability_discovery_api.py>])
closure_signal_identity_unresolvable: ds10-public-decision-rendering: tests/unit/runtime/http/test_public_export.py::test_public_decision_projection_is_custody_bound; ast=False; collected=0; exit=4; no tests collected in 0.00s | ERROR: file or directory not found: tests/unit/runtime/http/test_public_export.py::test_public_decision_projection_is_custody_bound
closure_signal_identity_unresolvable: global-case-index-producer-missing: tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index; ast=False; collected=0; exit=4; ERROR: not found: /Users/deniskopylov/polisyos/.worktrees/debt-vocabulary-value-provenance/policy-engine/tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index | (no match in any of [<Module test_capability_discovery_api.py>])
closure_signal_identity_unresolvable: shared-git-hook-hardcodes-one-worktree-path: tests/repo_quality/tools/test_repo_hooks.py::test_shared_hook_contains_no_worktree_specific_path; ast=False; collected=0; exit=4; no tests collected in 0.00s | ERROR: file or directory not found: tests/repo_quality/tools/test_repo_hooks.py::test_shared_hook_contains_no_worktree_specific_path
closure_signal_runner_unsupported: ds10-lex-pipeline-mutation-boundary: src/features/lex/routes/LexKnowledgeGraphPage.test.tsx; Vitest selection is unsupported by design; resolve this row manually
register_supplies_missing_standing: GY:GY-DEF14: register=closed, source=ambiguous
register_supplies_missing_standing: GY:GY-DEF15: register=closed, source=ambiguous
register_supplies_missing_standing: GY:GY-DEF19: register=closed, source=prose_only
register_supplies_missing_standing: GY:GY-DEF22: register=open, source=ambiguous
register_supplies_missing_standing: GY:GY-DEF23: register=blocked, source=ambiguous
register_supplies_missing_standing: GY:GY-DEFC-1: register=closed, source=ambiguous
register_supplies_missing_standing: GY:GY-GAP5: register=blocked, source=ambiguous
register_supplies_missing_standing: GY:GY-GAP6: register=blocked, source=ambiguous
register_supplies_missing_standing: GY:GY-GAP7: register=folded, source=ambiguous
register_supplies_missing_standing: GY:GY-GAP8: register=closed, source=ambiguous
```

## Event 9 — VV-F04: row-2 consumer census and route before repair

The first census covered every tracked file under src/tools/apps/packages/scripts/ops/schemas:
5,208 files; the complete product-tree cross-check then covered **10,535 tracked files**,
with 57 undecodable binary fixtures/assets and no unreadable source file. The latter
contains 5,749 Python files (including tests), 507 TypeScript and 716 TSX files; all
other file types and the exact hit list are in the embedded receipt below. Thirty
files mention the table: 10 production/tool Python files, 5 test Python files, and
15 documentation/generated data files. No architecture or frontend consumer was
omitted by the initially narrower roots. The new regression is included in the final
whole-tree count. This establishes in-repository literal and inspected dataflow reach;
external direct SQL clients and arbitrary dynamic plugins are not established.

| Production/tool file (under `src/polisyos/` unless `tools/`) | Read/write and interpretation |
| --- | --- |
| `data_forge/domains/academic/batch/graph_builder.py` | Batch writer; the defective hint assignment is row 2's repair. The retained adjudication is separately inserted from the same admitted mapping. |
| `data_forge/domains/academic/knowledge/skg_store.py` | Schema/index owner and sibling span-grounded writer; sibling already stores NULL in this column because it has no design adjudication. No schema alteration. |
| `data_forge/domains/academic/batch/edge_synthesize.py` | Reads the cell and counts it into `design_family_histogram_json`; does not infer evidence strength or adjudication from it. The histogram is a retained observational projection. Complete source search finds no downstream histogram reader beyond its schema/writer. |
| `tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py` | Copies `row[8]` into diagnostic evidence `design_family` and content-hashes the row; the downstream operation uses row identities/refs, not a recovered adjudication. |
| `data_forge/domains/academic/batch/benchmark.py` | Reads design_quality_tier and joined article year/source_basis; does not read this design_family column. |
| `data_forge/domains/academic/batch/qc.py` | Counts retracted and old evidence through article joins; no design_family read. |
| `data_forge/domains/academic/batch/best_snapshot.py` | Whole-table copy and version normalization, not interpretation. Historical hints stay historical after copy. |
| `tools/ops_runners/cloud/merge_shards.py` | Whole-row merge keyed by edge_id/claim_id/openalex_id; no adjudication interpretation. |
| `tools/quality/validation/check_layer3_gy_openalex_artifacts.py` | Table row count only. |
| `runtime/quality/proving_ground/causal_forecast_search.py` | Required-table inventory and query-trace table refs; no read of this column as an adjudication. |

The two value-consuming paths preserve/aggregate the stored field, while neither
recovers an adjudication from it. No inspected in-repository consumer uses this cell
to decide an adjudicated design. A rename would force those SQL projections and whole-row
copiers across a stored schema; the chosen route is **wire-existing admitted adjudication
into the existing column**, leaving the independently stored raw hint intact. The sibling
writer's NULL absence is already compatible. No new column, DTO field, snapshot, or manifest.

VV-F05 independently rechecks HC-F06 with Python joins over all 7,868 evidence rows,
67,791 unique adjudications and 137,589 unique raw claims, plus an independent SQL join:
**7,526 design-branch rows; 488 differ from adjudication; all 7,526 equal raw hints**.
The branch predicate is HC-F06's accepted complement of unclear/theoretical/review
with strong/moderate credibility; the retired evidence mapper was not executed.
Candidate observation **VV-C02**: across the entire 7,868-row table, 566 cells differ
from their retained adjudication (488 design-branch + 78 outside that branch).
This is the same writer-provenance class over the wider measured denominator, not
another repair round; no historical data pass is performed and no new row is opened.

Exact commands:

```sh
python3 _build/vocabulary-value-provenance/row2-census.py > _build/vocabulary-value-provenance/row2-census.log
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/vocabulary-value-provenance/row2-population.py > _build/vocabulary-value-provenance/row2-population.log 2>&1
```

Both exited 0. The chosen route was stated before editing the writer.

## Event 10 — VV-F06: row 2 red/green and independent preservation

Red: the actual `load_graph` writer persists a test DuckDB, then a fresh read-only
connection joins edge evidence to raw hints and retained adjudications. All 20 enum
members are supplied as hints paired with a different adjudicated enum member. Two
more cases cover absent hint and absent adjudicated design; one unadmitted producer
publication flag must emit no evidence row. The admitted-row input is controlled
fixture data, not a fresh adjudication producer/model invocation. The first observed
mismatch is stored `rct` versus retained `iv`, while raw hint remains `rct`.

One-line repair: `str(adjudication.get("design_family") or "")` replaces the hint
expression in the edge-evidence tuple, matching the retained-adjudication writer.
Missing adjudicated design stays the existing empty-string absence and never inherits
the hint. The existing publication gate requires an adjudication before reaching this
line. The evidence-strength axis and raw hint values are unchanged by this repair.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py::test_persisted_edge_design_matches_adjudication_despite_extractor_hint > _build/vocabulary-value-provenance/row2-red.log 2>&1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py tests/unit/data_forge/domains/academic/batch/test_graph_builder.py > _build/vocabulary-value-provenance/row2-green.log 2>&1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check src/polisyos/data_forge/domains/academic/batch/graph_builder.py tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py
```

Red exit 1 (assertion mismatch, not an import/setup error); green exit 0, 37 tests in
those two exact files; Ruff exit 0. The entire 22-row persisted comparison is equal
after the repair. This is forward writer repair, not a claim that the pinned 488
historical design-branch mismatches were rewritten. Those remain read-only.

Row 2 is committed separately before phase 3, so a provenance-schema stop cannot
cost either small repair. The already-completed debt-checker receipt binds row 1's
commit only; it was not rerun after this source change (Event 8).

### Row-2 complete-program receipts

```python
"""Complete tracked-source census of the persisted edge-evidence table."""
from pathlib import Path
from collections import Counter
import json,subprocess
root=Path.cwd()
roots=['.']
paths=[Path(p) for p in subprocess.check_output(['git','ls-files','--',*roots],text=True).splitlines()]
counts=Counter()
hits=[]
binary=[]
for p in paths:
    counts[p.suffix or '<none>']+=1
    try: lines=p.read_text().splitlines()
    except UnicodeError:
        binary.append(str(p)); continue
    found=[{'line':i,'text':s.strip()} for i,s in enumerate(lines,1) if 'ac_skg_edge_evidence' in s]
    if found: hits.append({'path':str(p),'hits':found})
result={'roots':roots,'tracked_files':len(paths),'by_type':dict(sorted(counts.items())),'undecodable':binary,'matching_files':len(hits),'hits':hits}
Path('_build/vocabulary-value-provenance/row2-census.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
```

```python
import duckdb,json
from pathlib import Path
c=duckdb.connect('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb',read_only=True)
a_rows=c.execute('SELECT claim_id,design_family,causal_credibility FROM ac_claim_adjudications').fetchall()
r_rows=c.execute('SELECT id,design_family_hint FROM ac_causal_claims_raw').fetchall()
e=c.execute('SELECT claim_id,design_family FROM ac_skg_edge_evidence').fetchall()
a={cid:(d,cc) for cid,d,cc in a_rows}; r=dict(r_rows)
assert len(a)==len(a_rows) and len(r)==len(r_rows)
branch=[(cid,d) for cid,d in e if not (a[cid][0] in {'unclear','theoretical','review'} and a[cid][1] in {'strong','moderate'})]
py=(len(e),len(branch),sum(d!=a[cid][0] for cid,d in branch),sum(d==r[cid] for cid,d in branch))
sql=c.execute("""SELECT (SELECT count(*) FROM ac_skg_edge_evidence),count(*),count(*) FILTER(WHERE e.design_family IS DISTINCT FROM a.design_family),count(*) FILTER(WHERE e.design_family IS NOT DISTINCT FROM r.design_family_hint) FROM ac_skg_edge_evidence e JOIN ac_claim_adjudications a ON a.claim_id=e.claim_id JOIN ac_causal_claims_raw r ON r.id=e.claim_id WHERE NOT(a.design_family IN ('unclear','theoretical','review') AND a.causal_credibility IN ('strong','moderate'))""").fetchone()
assert py==sql==(7868,7526,488,7526)
result={'python':py,'independent_sql':sql,'adjudications':len(a_rows),'raw_claims':len(r_rows),'all_evidence_divergent':sum(d!=a[cid][0] for cid,d in e)}
Path('_build/vocabulary-value-provenance/row2-population.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
c.close()
```

Complete denominator by file type: `{".blob": 11, ".cfg": 1, ".cjs": 9, ".css": 17, ".csv": 15, ".cypher": 2, ".duckdb": 4, ".example": 3, ".html": 3, ".ini": 11, ".js": 5, ".json": 1233, ".jsonc": 1, ".jsonl": 5, ".lock": 1, ".md": 1660, ".mdc": 1, ".mjs": 36, ".pkl": 2, ".png": 42, ".py": 5749, ".pyi": 5, ".rego": 23, ".reproducible": 1, ".sh": 45, ".sql": 6, ".svg": 18, ".tf": 1, ".tmpl": 7, ".toml": 221, ".tpl": 1, ".ts": 507, ".tsx": 716, ".txt": 5, ".typed": 2, ".webm": 6, ".yaml": 85, ".yml": 54, ".zip": 7, "<none>": 14}`.

Undecodable binary denominator: `{".pkl": 2, ".png": 42, ".webm": 6, ".zip": 7}`.

`row2-census.json` SHA-256 `3c2e320f5e1321d9a5c62bb37084ac61b6bde6480417ee3785bfc13a6d0bd2d0`.

`row2-population.log` SHA-256 `99467a63f8cf3b6f67b040edae18058d4198380b66f167c4d68ca274a18f66ed`.

`row2-red.log` SHA-256 `76f939e6cf321e060f1918c62c5ce3c43af3b0c0e4d65b175f2268cf52c5c5a6`.

`row2-green.log` SHA-256 `498e6947c683cfc4d9d8dd6500f7bced1426c92501b2b6f938049aa6eb2024c6`.

## Event 11 — VV-F07: measured origins, before and after the two repairs

Both forward repairs were read back from their branch commits before this phase:
`04c6bd0e9` (row 1), `1574d1e26` (row 2). Their source and test bytes matched the worktree.
The origin census parses every one of **3,052 Python files in src/tools** (2,619 + 433),
with zero parse errors. It enumerates every named EvidenceParameter constructor/validator,
parameter intake and numeric-rescue/merge call. References to the DTO and to the strength
field were followed through the serializer, SQL writer, SKG reader and terminal consumers.
This is a complete named-static-source census within those roots, with inspected
model_copy and dictionary projections; no claim is made about externally supplied code.

**The four convergent producing categories remain four, before 4 -> after 4.** The
brief's proposed reduction does not occur in this implementation: row 1 changes design
identity normalization, row 2 changes a design column's provenance. Neither removes a
parameter evidence-strength origin. `_normalize_evidence_strength` is indeed called
inside `_normalize_empirical_parameter`, but neither repair changes that function,
its fallback or its callers. The inherited design column is not a parameter-strength
producer on the inspected paths. The code's decisive input is the evidence-strength
axis or article methodology, not `design_family_hint` or the edge design column.

| Origin category | Before | After | Measured current producing/intake path |
| --- | ---: | ---: | --- |
| Explicit extraction candidate (including parsed numeric-rescue response) | present | present | `article_extractor._normalize_extraction_payload` calls `_normalize_empirical_parameter`; `_resolve_extract_api.py:1600` calls it on parsed rescue parameters. A supplied candidate is not independently validated evidence. |
| Normalizer manufacture for missing/unrecognized input | present | present | `_normalize_evidence_strength` returns UNKNOWN; `_normalize_empirical_parameter` explicitly inserts it before strict validation. |
| SKG validation-failure manufacture | present | present | `_to_evidence_parameter` tries strict validation, then explicitly assigns UNKNOWN for an invalid/missing strength and constructs a replacement. |
| Inheritance from another parameter, a claim or article methodology | present | present | `_deterministic_numeric_rescue_parameters` has all three sources; `_merge_numeric_parameter_lists`, `resolve_finalize._merge_parameters`, and `_effective_parameter_strength` also inherit values. These are more sites of the same origin class, not additional classes or additional fix rounds. |
| Non-supply (no origin event) | separate input state | still collapses on serialization | Ordinary `EvidenceParameter` default; raw SKG normalization preserves omission initially, a normal dump materializes UNKNOWN. This is absence of a producing origin, not a fifth extractor judgment. |
| Historically unmarked stored value | unresolved | unresolved | No retroactive assignment to any of the four producing categories is permitted. |

Named calls: three `_normalize_empirical_parameter` sites; three `_to_evidence_parameter`
sites (simulation query, raw query, relation census); two EvidenceParameter.model_validate
sites plus one direct fallback constructor. Nested ArticleExtractionResult validation and
ContextAdaptiveParameterBundle validation deserialize the same DTO through their schemas.
The numeric-rescue merge has two call sites, one for each rescue route.

A separate AST comparison against the slice base `37c20aaa5` confirms that all eight
inspected origin-owner functions are unchanged: `_normalize_evidence_strength`,
`_normalize_empirical_parameter`, `_normalize_evidence_parameter_payload`,
`_to_evidence_parameter`, `_deterministic_numeric_rescue_parameters`,
`_merge_numeric_parameter_lists`, `_merge_parameters`, `_effective_parameter_strength`.
This compares function syntax without location attributes, so row-1 line shifts do
not masquerade as a behavioral difference. The two prompt-fed candidate call sites
and their producer modules are also unchanged by the actual diff.

**VV-C03 candidate observation, same inheritance class:** finalization can replace
UNKNOWN or THEORETICAL with a linked claim's strength and then with article methodology;
its numeric row has no value-level origin. This matters directly to the measured
`metadata.simulation_ready_numeric_estimates` namespace. It is covered by the required
inheritance category and left unrepaired at the schema stop. **VV-C04 candidate
observation:** `table_extractor.tables_to_parameters` constructs an explicit unknown
with source=`table_extraction`; the complete named-call walk finds zero calls in the
3,052-file source denominator, so its connection to this live production path is
`implemented_but_not_orchestrated`, not an invented fifth measured historical cohort.
No extraction/table producer was invoked and neither candidate was opened in the register.

## Event 12 — VV-F08: persistence and consuming-path measurement

The real current route has two materially different persisted projections:

1. `_append_artifacts` writes ArticleExtractionResult.model_dump(mode="json") into
   article/resolve JSONL. `resolve_finalize` reloads that DTO, merges attempts, and
   writes its model dump again. `numeric_extract._load_final_results` validates the
   same JSON. No origin-bearing field survives because none exists in EvidenceParameter.
2. `_to_work_record` converts empirical parameters to EstimateCandidate, retaining
   numeric values, intervals, names and the `resolve_extract` pattern but **omitting
   evidence_strength**. `graph_builder` stores that EstimateCandidate model dump in
   `ac_skg_parameters.parameter_json`. This explains the raw parameter non-supply path
   as a current projection; it does not retrospectively prove every historical origin.
3. `resolve_finalize._simulation_ready_parameters` / `_curated_numeric_rows` use
   `_effective_parameter_strength` and write the resulting scalar into numeric metadata.
   `run_numeric_extract` also writes raw/curated/simulation JSONL. `graph_builder` projects
   the scalar to `ac_skg_simulation_parameters.evidence_strength`. Source_layer,
   linked_claim_ids and uncertainty_source describe row/context relations, not which
   branch produced this specific strength value.
4. `SKGQuery._query_raw_parameter_candidates` decodes the raw JSON; the simulation
   reader explicitly supplies its SQL scalar, including empty-string fallback, to
   `_to_evidence_parameter`. ParameterCandidate carries diagnostics/source_layer but
   no strength-origin record. `ParameterSelector.select_for_context` weights the value,
   then returns the selected EvidenceParameter. `search.get_parameter_prior` weights
   the same scalar and exposes best_design; unknown contributes zero after the prior
   repair, but zero weight does not identify judged unknown.
5. Scientist's causal `resolve_parameters` builds ContextAdaptiveParameterBundle with
   the selected DTO; its IR persist/load helpers use model_dump/model_validate.
   Foundry parameter_transfer consumes the selected numeric parameter/applicability.
   No consumer on this chain can recover an origin erased before persistence.

The complete SQL numeric-metadata field walk confirms **22 keys, each on all 5,133
numeric rows**, including source_layer, source_basis, linked_claim_ids and quality_flags,
but no value-origin record. Its full key denominator is:

```json
[
  [
    "canonical_name",
    5133
  ],
  [
    "confidence_interval",
    5133
  ],
  [
    "display_name",
    5133
  ],
  [
    "estimate_sign",
    5133
  ],
  [
    "estimate_type",
    5133
  ],
  [
    "evidence_strength",
    5133
  ],
  [
    "geographic_scope",
    5133
  ],
  [
    "linked_claim_ids",
    5133
  ],
  [
    "linked_edge_ids",
    5133
  ],
  [
    "linked_edge_pairs",
    5133
  ],
  [
    "numeric_id",
    5133
  ],
  [
    "openalex_id",
    5133
  ],
  [
    "parameter_name",
    5133
  ],
  [
    "point_estimate",
    5133
  ],
  [
    "quality_flags",
    5133
  ],
  [
    "source_basis",
    5133
  ],
  [
    "source_context",
    5133
  ],
  [
    "source_layer",
    5133
  ],
  [
    "std_error",
    5133
  ],
  [
    "time_period",
    5133
  ],
  [
    "uncertainty_source",
    5133
  ],
  [
    "unit",
    5133
  ]
]
```

The five named empirical-parameter consumer operations are characterization, weighting,
selection, persistence and numeric transfer; none creates a verified judgment predicate.
This path map covers the actual scalar producers and bridges discovered in the complete
source census, without claiming that a new end-to-end origin capability exists.

### VV-F09 — negative counterfactuals through the actual round-trip

The historical witness is selected read-only by stable param_id order, not supplied
as an invented historical judgment. Only controlled copies are modified, under `_build/`.
The omitted payload is normalized, wrapped in an ArticleExtractionResult, persisted as
ordinary JSON using the writer's model-dump shape, reloaded as that DTO, and passed to
the real SKG intake. Model calls, extraction runs and producer invocations are absent.

| Executed measurement | Observed outcome | Closure meaning |
| --- | --- | --- |
| Raw omitted payload -> SKG typed DTO -> ordinary model_dump/model_validate | UNKNOWN both times; fields_set false -> true | Non-supply is lost in the ordinary round-trip. |
| Omitted / controlled explicit unknown / unrecognized label -> empirical normalizer -> persisted article JSON -> validated parameter -> SKG consumer | Three origins, **one identical complete consumer payload**, all UNKNOWN and supplied | Neither value nor suppliedness identifies an extractor judgment. |
| Same three inputs with malformed parameter_type -> real SKG manual fallback -> JSON round-trip | Three inputs, **one identical complete persisted payload**, UNKNOWN and supplied | Validation fallback has no separable origin at the consuming boundary. |
| Pure numeric merge, retained parameter UNKNOWN plus enriching parameter RCT | Result RCT and supplied, with no origin reference | A non-unknown value can be inherited; value/presence is not a judgment test. |
| Add a controlled `evidence_strength_origin` sibling to an input | SKG normalization reports `dropped:evidence_strength_origin` | A loose JSON sibling cannot cross the current DTO boundary. |

The measurement program exits **0 because these collision assertions hold**. That is
**red evidence for the requested provenance closure**, not a passing implementation
of its negative. The full produced observations are:

```json
{
  "historical_witness": {
    "param_id": "00006956f86be07a48474869",
    "name": "climate.thermokarst_landslide_initiation_rate_pr",
    "payload_sha256": "ed723ae9090a8e08af89c92dbd83477b5f6efca890a73c3564bd96a5be49d8aa"
  },
  "ordinary_omission": {
    "before": "unknown",
    "supplied_before": false,
    "after": "unknown",
    "supplied_after": true
  },
  "normalizer_to_persisted_article_to_consumer": {
    "variants": [
      "omitted",
      "declared_unknown_counterfactual",
      "invalid_input"
    ],
    "distinct_full_consumer_payloads": 1,
    "all_value": "unknown",
    "all_supplied": true,
    "origin_field_present": false,
    "meaning": "collision witness; declared unknown is synthetic and not a historical judgment"
  },
  "fallback": {
    "variants": [
      "omitted",
      "declared_unknown_counterfactual",
      "invalid_input"
    ],
    "distinct_full_persisted_payloads": 1,
    "value": "unknown",
    "supplied": true
  },
  "merge_inheritance": {
    "input_keep": "unknown",
    "input_enrich": "rct",
    "output": "rct",
    "supplied": true,
    "origin_field_present": false
  },
  "origin_transport_absent": {
    "intake_drops_unknown_sibling": true,
    "diagnostics": [
      "dropped:evidence_strength_origin"
    ],
    "fields": [
      "name",
      "display_name",
      "parameter_type",
      "value",
      "value_range",
      "value_qualitative",
      "confidence_interval",
      "std_error",
      "unit",
      "evidence_strength",
      "geographic_scope",
      "time_period",
      "aggregation_level",
      "transferability",
      "transfer_conditions",
      "heterogeneity_note",
      "subgroup_estimates"
    ],
    "additional_properties": false
  }
}
```

**Positive trace: not established.** The explicitly supplied unknown in this probe is
labelled a controlled counterfactual, never a recorded extractor judgment. VV-F01's
complete retained populations contain no explicit raw-parameter strength keys, and
the 5,133 numeric-metadata strength values are all the six non-unknown labels already
listed. None can supply the required actual recorded-unknown judgment with a bound
producer. No historical cohort was reclassified; no live producer was called to make
up the missing positive. A future instrumented producer plus durable origin transport
is needed for that positive acceptance signal.

The first draft of the probe exited 1 because the ArticleExtractionResult fixture
omitted its required extraction_model, extraction_timestamp and extraction_confidence.
Those controlled fixture fields were supplied; no product code was changed. The final
program's fallback diagnostics intentionally report validation errors before exercising
the manual fallback; the command itself exits 0.

## Event 13 — VV-D02: schema stop, before any provenance implementation

The source census walks all **99 `schemas/snapshots/ir/*.schema.json` files** and finds
EvidenceParameter in exactly two: `article_extraction_result.schema.json` and
`context_adaptive_parameter_bundle.schema.json`. Both expose the same 17 properties,
require name, and have `additionalProperties=false`. The live DTO also has those
17 fields and `extra="forbid"`. Neither contains a strength-origin record. The
manifest has hash-bearing entries for both models; its presence is part of the
required authorization scope, not a second optional receipt.

The smallest correct next capability is a typed value-origin representation admitted
where the branch is known, retained with each value through both numeric and raw
projections, and consumed explicitly after persistence. An omitted origin must not
self-upgrade to extractor judgment. The raw EstimateCandidate projection and simulation
scalar projection need their own retained bridge too; merely adding a field to the
IR model would still be `bridge_missing`. An arbitrary string in transfer_conditions,
a source_layer label, fields_set or transient diagnostics would be a P32/P38 substitute
for typed, durable provenance and is not an acceptable schema-free repair.

**Stop rule 4 applies:** no honest provenance separation across this DTO can be delivered
without changing a stored contract. No row-3 implementation round is started. The known
IR schema authorization must explicitly include all of:

- `schemas/snapshots/ir/article_extraction_result.schema.json`
- `schemas/snapshots/ir/context_adaptive_parameter_bundle.schema.json`
- `schemas/snapshots/ir/_manifest.json`

This list names the confirmed affected IR surfaces, not a claim that the two downstream
storage bridges have already been designed or that a future stored-column change is
implicitly authorized. The stop freezes design before choosing those representations.
No schema, column, manifest, active plan or production datum was edited.

**Row 4 consequence:** non-supply is still not separable from recorded unknown after
persistence. Its own negative is not green, its provenance dependency is not delivered,
and it remains open. No status is inferred from adjacent repairs. Historical origins
stay unresolved even if forward provenance is later authorized.

## Event 14 — reproduction and final scope receipts

```sh
python3 _build/vocabulary-value-provenance/parameter-paths.py > _build/vocabulary-value-provenance/parameter-paths.log
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/vocabulary-value-provenance/parameter-roundtrip.py > _build/vocabulary-value-provenance/parameter-roundtrip.log 2>&1
```

Both final commands exited 0. The full probe is retained below; it exercises normalizers,
merge and serializers only, with local scratch JSON. The producer paths are read as code,
not invoked. Origin counts above are mechanisms, not invented historical row partitions.

### `parameter-paths.py`

```python
"""Complete source census of parameter constructors/intakes and stored schema owners."""
import ast,json,subprocess
from collections import Counter
from pathlib import Path
paths=[Path(p) for p in subprocess.check_output(['git','ls-files','src','tools'],text=True).splitlines() if p.endswith('.py')]
result={'source_files':len(paths),'by_root':dict(Counter(str(p).split('/')[0] for p in paths)),'parse_errors':[],'calls':[],'references':[],'strength_files':[]}
intakes={'_normalize_empirical_parameter','_to_evidence_parameter','_normalize_evidence_parameter_payload','_deterministic_numeric_rescue_parameters','_merge_numeric_parameter_lists'}
for p in paths:
 text=p.read_text()
 if 'evidence_strength' in text: result['strength_files'].append(str(p))
 try: tree=ast.parse(text)
 except SyntaxError as e: result['parse_errors'].append([str(p),str(e)]); continue
 if 'EvidenceParameter' in text:
  result['references'].append({'path':str(p),'lines':[[i,l.strip()] for i,l in enumerate(text.splitlines(),1) if 'EvidenceParameter' in l]})
 aliases={'EvidenceParameter'}
 for node in ast.walk(tree):
  if isinstance(node,ast.ImportFrom):
   aliases.update(n.asname or n.name for n in node.names if n.name=='EvidenceParameter')
 for node in ast.walk(tree):
  if not isinstance(node,ast.Call): continue
  f=node.func
  name=f.id if isinstance(f,ast.Name) else f.attr if isinstance(f,ast.Attribute) else ''
  is_model=(isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name) and f.value.id in aliases)
  if name in aliases or name in intakes or is_model:
   result['calls'].append({'path':str(p),'line':node.lineno,'call':ast.unparse(f),'expression':ast.unparse(node)})
schemas=list(Path('schemas/snapshots/ir').glob('*.schema.json'))
result['schema_files']=len(schemas); result['parameter_schemas']=[]
for p in schemas:
 data=json.loads(p.read_text())
 if 'EvidenceParameter' in data.get('$defs',{}):
  shape=data['$defs']['EvidenceParameter']
  result['parameter_schemas'].append({'path':str(p),'properties':list(shape['properties']),'required':shape.get('required'),'extra':shape.get('additionalProperties')})
Path('_build/vocabulary-value-provenance/parameter-paths.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in {'references','strength_files'}},indent=2))
```

### `parameter-roundtrip.py`

```python
"""Counterfactuals at real parameter intake/serialization/consumption boundaries; no producers."""
import json,hashlib
from pathlib import Path
import duckdb
from polisyos.data_forge.domains.academic.batch.article_extractor import _normalize_empirical_parameter
from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
from polisyos.data_forge.domains.academic.batch._resolve_extract_transformers import _merge_numeric_parameter_lists
from polisyos.ir.analytics.literature import EvidenceParameter,ArticleExtractionResult

out=Path('_build/vocabulary-value-provenance')
c=duckdb.connect('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb',read_only=True)
row=c.execute("SELECT param_id,canonical_name,parameter_json FROM ac_skg_parameters WHERE NOT json_exists(parameter_json,'$.evidence_strength') AND (try_cast(json_extract_string(parameter_json,'$.ci_low') AS DOUBLE)<=try_cast(json_extract_string(parameter_json,'$.ci_high') AS DOUBLE) OR json_extract_string(parameter_json,'$.ci_low') IS NULL OR json_extract_string(parameter_json,'$.ci_high') IS NULL) ORDER BY param_id LIMIT 1").fetchone()
c.close()
pid,name,raw_json=row
raw=json.loads(raw_json)
normal=SKGQuery._to_evidence_parameter(name,raw)
assert normal is not None
restored=EvidenceParameter.model_validate(normal.model_dump())
observations={'historical_witness':{'param_id':pid,'name':name,'payload_sha256':hashlib.sha256(raw_json.encode()).hexdigest()},'ordinary_omission':{'before':normal.evidence_strength.value,'supplied_before':'evidence_strength' in normal.model_fields_set,'after':restored.evidence_strength.value,'supplied_after':'evidence_strength' in restored.model_fields_set}}
assert observations['ordinary_omission']=={'before':'unknown','supplied_before':False,'after':'unknown','supplied_after':True}
variants={
    'omitted':raw,
    'declared_unknown_counterfactual':{**raw,'evidence_strength':'unknown'},
    'invalid_input':{**raw,'evidence_strength':'this-is-not-evidence'},
}
serialized={}
for label,payload in variants.items():
 p=_normalize_empirical_parameter(payload)
 assert p is not None
 article=ArticleExtractionResult(openalex_id='controlled:witness',title='No producer run',extraction_model='controlled-no-call',extraction_timestamp='2026-09-06T00:00:00Z',extraction_confidence=0.5,empirical_parameters=[p])
 # Same model serialization used by _append_artifacts, persisted locally as JSON, then real consumer intake.
 f=out/f'{label}-roundtrip.json'
 f.write_text(json.dumps(article.model_dump(mode='json'))+'\n')
 loaded=ArticleExtractionResult.model_validate_json(f.read_text()).empirical_parameters[0]
 result=SKGQuery._to_evidence_parameter(loaded.name,loaded.model_dump(mode='json'))
 assert result is not None
 serialized[label]=result.model_dump(mode='json')
 assert result.evidence_strength.value=='unknown' and 'evidence_strength' in result.model_fields_set
assert len({json.dumps(p,sort_keys=True) for p in serialized.values()})==1
observations['normalizer_to_persisted_article_to_consumer']={'variants':list(variants),'distinct_full_consumer_payloads':1,'all_value':'unknown','all_supplied':True,'origin_field_present':False,'meaning':'collision witness; declared unknown is synthetic and not a historical judgment'}
fallbacks={}
for label,payload in variants.items():
 diagnostics=[]
 p=SKGQuery._to_evidence_parameter(name,{**payload,'parameter_type':'malformed'},diagnostics=diagnostics)
 assert p is not None and 'fallback:manual_evidence_parameter' in diagnostics
 p=EvidenceParameter.model_validate_json(p.model_dump_json())
 fallbacks[label]=p.model_dump(mode='json')
assert len({json.dumps(p,sort_keys=True) for p in fallbacks.values()})==1
observations['fallback']={'variants':list(variants),'distinct_full_persisted_payloads':1,'value':'unknown','supplied':True}
# Existing inheritance merge; both parameters carry the same numeric estimate, without invoking rescue.
left=EvidenceParameter(name='controlled.effect',value=1.0,confidence_interval=(0.5,1.5))
right=EvidenceParameter(name='controlled.effect',value=1.0,evidence_strength='rct')
merged=_merge_numeric_parameter_lists([left],[right])
assert len(merged)==1 and merged[0].evidence_strength.value=='rct'
merged=EvidenceParameter.model_validate_json(merged[0].model_dump_json())
observations['merge_inheritance']={'input_keep':'unknown','input_enrich':'rct','output':merged.evidence_strength.value,'supplied':'evidence_strength' in merged.model_fields_set,'origin_field_present':False}
# An invented sibling provenance field is neither represented nor preserved by this current strict DTO/intake.
diagnostics=[]
marker_payload={**normal.model_dump(mode='json'),'evidence_strength_origin':{'kind':'extractor_judgment'}}
canonical=SKGQuery._normalize_evidence_parameter_payload(name,marker_payload,diagnostics=diagnostics)
assert 'evidence_strength_origin' not in canonical
observations['origin_transport_absent']={'intake_drops_unknown_sibling':True,'diagnostics':diagnostics,'fields':list(EvidenceParameter.model_fields),'additional_properties':EvidenceParameter.model_json_schema()['additionalProperties']}
print(json.dumps(observations,indent=2))
(out/'parameter-roundtrip.json').write_text(json.dumps(observations,indent=2)+'\n')
```

Output bindings:

| Output under `_build/vocabulary-value-provenance/` | SHA-256 |
| --- | --- |
| `parameter-paths.log` | `4a3d7cc5033ce0bc39858eb4807b2e07363151e9951305fa6a81d12d68fd2563` |
| `parameter-roundtrip.json` | `89d34fc37d41e7e5d1d7c62b6b72cf204e1c8cf09824cf61afa9337031463aae` |
| `origin-before-after.json` | `9f6d0c356f3867b1733040c0cac66b5a588ec71a74b373faa6abbf62a7df5355` |
| `numeric-field-census.json` | `c2eaaa14168ef8fe573a18c706b89a6c97ca9831db62ae3f16bde289fd6b447e` |

The failure/repair register was reopened before closeout. P05/P15/P32/P38 remain
explicitly unresolved for parameter-origin authority; P35 is satisfied by complete
source/schema/data denominators, not selected examples. The two forward repairs have
behavioral red/green receipts; no new provenance capability is called implemented.
The pattern register itself is unchanged because the user asked to journal incidental
findings, not open or repair them.

Final targeted Ruff on the four changed Python files exited 0. Source freeze is
`1574d1e26`; subsequent edits are this journal only. Tests are 52 passing cases in the
row-1 file and 37 in the two row-2 files; no full backend, directory suite or CI-parity
run. The limited architecture command from Event 5 remains red and is not labelled
inherited. The **single** debt checker exited 0 at `04c6bd0e9`, with the complete four-code
census in Event 8; it does not verify the later row-2 commit. No second run was made.
That premature checker invocation is a delivery limitation, not a final-head green claim.

Final production-data command (after all measurement reads):

```sh
shasum -a 256 production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb
```

Exit 0; SHA-256 **583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967**,
matching the required pin. All database connections to this file were read-only.

The branch diff from `37c20aaa5..HEAD` contains exactly five paths: this journal,
article_extractor.py, graph_builder.py, test_article_extractor.py, and
test_graph_builder_skg_tables.py. The complete filenames are recorded in the final
branch readback. No active-plan or stored-schema files are among them.

## Event 15 — final transcriber-ready prose (supersedes Event 7)

**`design-normalization-matches-a-substring-before-identity` — forward repair delivered
in `04c6bd0e9`; retain the historical close as open under stop rule 3.** VV-F02 reproduces
exactly five failures over all 20 DesignFamily members, then proves 20/20 exact identity
round-trips and unmatched=`unclear`; 52 focused tests pass. VV-F03 establishes 67,791
retained resolve_extract hints across 20,900 documents plus the matching nonempty raw-table
population. This is a nonzero route footprint, not a count of proved corrupt inputs:
the exact historical normalizer revision and pre-normalization values are unestablished.
No production-data repair or capability-only historical close is claimed.

**`evidence-row-design-hint-differs-from-adjudication` — forward writer repair delivered
in `1574d1e26` by the adjudicated-value route.** VV-F04's complete tracked-source census
finds no inspected consumer recovering adjudication from the column; its value readers
aggregate a histogram or copy diagnostic row data. VV-F05 independently reproduces
488/7,526 design-branch mismatches, all 7,526 equal raw hints. VV-F06's red-first real
DuckDB test covers every enum member, absent hint, absent adjudicated design and
unadmitted publication; 37 focused tests pass. The writer now persists exactly the
retained adjudication's design and preserves raw hints separately, with no schema
change. The historical 488 cells (566 mismatches over all 7,868 evidence rows) remain
untouched: the forward signal is discharged, not a retrospective rewrite of the snapshot.

**`parameter-evidence-strength-has-no-value-provenance` — remains open; stopped before
stored-schema design/implementation.** VV-F07 re-enumerates four producing categories
before and after the two repairs: extraction candidate, normalizer manufacture, SKG
fallback and inheritance (4 -> 4; non-supply is absence of origin). Finalization and
merge reveal further inheritance sites of the same class. VV-F08/F09 trace the real
serializer and SKG consumer: omitted, controlled explicit unknown and malformed values
collapse to identical complete payloads; fallback and inherited values carry no producer
origin. HC-F18's 5,133 parameter-metadata values and the raw 51,908 payloads are independently
reconciled, but no actual recorded unknown judgment can be bound to its producer from
them. The positive signal is not established and the negative closure is not green.
VV-D02 stops for an authorized typed provenance contract and its persistence bridges;
authorization must name both affected IR snapshots and `schemas/snapshots/ir/_manifest.json`.
Historical origins remain unresolved and no provenance capability is claimed.

**`parameter-contract-cannot-distinguish-unsupplied-from-unknown` — remains open,
subordinate to the unfinished provenance mechanism.** All 51,908 raw payloads omit the
field; 51,883 decode as UNKNOWN and 25 reversed intervals reject, independently reconciled
by SQL and identical rejected IDs. VV-F09 confirms fields_set preserves omission at
construction but ordinary persistence materializes UNKNOWN and makes suppliedness true.
The omitted-field negative therefore does not pass at the consuming boundary, and the
controlled explicit unknown is not substituted for a recorded judgment. No schema or
presence-only workaround was implemented; row 4 does not close on either design repair.


## Event 16 — VV-D03: resumed authorization and the actual public-contract boundary

The architect's 2026-09-06 continuation approves the additive, defaulted
EvidenceParameter origin contract, its producer/persistence/intake bridges, tests,
and generated IR artifacts. Rows 1–2 are accepted and are not reopened. This
supersedes VV-D02's explanation of the schema stop: `abi-schema-snapshots` in
`architecture/generated_artifacts.toml` declares both snapshots and manifest as
`generated_committed`, generated by `uv run --extra ml polisyos-tools diagnostics
gen-schema`. The load-bearing decision was the public contract, not permission to
hand-author derived files. No snapshot or manifest is edited by hand. The public
surface classification is `public_stable` (`polisyos.ir`, supported entrypoint
`polisyos.ir.analytics`); the approved change is additive. Existing callers may
omit the new field. No other public IR model definition changes.

Pattern pass: P01/P29 require producer-to-stored-record-to-reader behavior, not a
field-presence test; P04/P05/P15 keep origin separate from evidence authority;
P35/P36 require re-derived counts; P38 separates the actual failing architecture
predicate from the entire scanner; P41 requires the slice base, not the last
handoff commit. Historical values stay unresolved; no historical data is rewritten.
The existing WorkRecord metadata dictionary carries serialized EvidenceParameter
payloads through the bridge that formerly projected them only into EstimateCandidate.
Numeric midpoint conversion remains the existing conversion; no second public IR
type is added or changed. The simulation SQL path carries an additive nullable
`evidence_strength_origin` column. Compatibility ALTER leaves historical origins
NULL; old-schema and NULL-origin readers do not infer a judgment.

## Event 17 — VV-F10: independently re-derived construction and reference census

At entry HEAD `961ba490655ec00da0af7762b46be884290cff68`,
`_build/vocabulary-value-provenance/resumed-census.py` walks all 10,535 tracked
product files and parses all 5,749 Python files, with zero parse errors. The complete
source/tool denominator is 3,052 Python files (2,619 src + 433 tools); other Python
files are 2,500 tests, 147 benchmarks, 29 examples, 12 architecture, 3 apps, 3 docs,
1 ops, and two root scripts. It finds **one direct production constructor**
(`skg_query.py`, manual fallback), **two explicit model_validate calls**
(`article_extractor.py`, `skg_query.py`), and 18 test constructors; no constructors
in the other Python roots. Thus there are two construction-bearing production
modules, three construction/validation expressions, and one literal constructor,
not two literal constructors. The materially-larger-construction stop does not fire.

Typed references occur in seven production modules including the defining model;
there are six other modules: article_extractor, _resolve_extract_transformers,
resolve_finalize, skg_query, parameter_selector, and ir/analytics/parameters.
The two-consuming-module estimate is not used as the blast-radius denominator.
Additional scalar/dictionary projections were already enumerated in VV-F07/VV-F08.
This AST census covers named and imported-alias construction/validation expressions;
it does not claim to prove the absence of arbitrary reflection.

Exact command:
```bash
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/vocabulary-value-provenance/resumed-census.py
```

## Event 18 — VV-D04: seven representations of four measured producing categories

VV-F07's four categories remain four. The representation now distinguishes:

| Measured origin/category | Durable enum value | Meaning at the consuming boundary |
| --- | --- | --- |
| Fresh producer judgment, known value | supplied | Producer supplied a recognized non-UNKNOWN strength, including accepted aliases; still a candidate judgment |
| Fresh producer judgment, explicit UNKNOWN | declared_unknown | Producer actually supplied unknown; different from the default |
| No supply (absence, not a fifth producing category) | not_supplied | No strength key at producer intake; honest model default |
| Normalizer manufacture | normalizer_fallback | Present but unrecognized input, including null/empty, became UNKNOWN |
| SKG intake manufacture | intake_fallback | Intake could not decode strength/origin and manufactured UNKNOWN |
| Inheritance | inherited | Rescue, merge, or effective-strength selection took strength from another parameter, claim, or methodology |
| Historical/unmarked (unestablished origin, not an invented cohort) | unresolved | A stored/caller-supplied scalar exists without a recorded origin |

Invalid input folds into the measured normalizer/intake fallback categories; it is
not a producer's declaration of unknown. `not_supplied` is the declared field
default. The model's before validator marks a value without an origin unresolved,
so an old explicit UNKNOWN cannot be retroactively credited to an extractor. A
materialized default round-trips with its not_supplied origin. Explicitly inconsistent
origin/value pairs fail validation; an origin marker without a supplied strength
cannot record a judgment. SKG's allowlist derives from model_fields, so the new
field passes that allowlist without a second parallel list. Manual fallback preserves
a valid recorded origin when only an unrelated field required repair; it records
intake_fallback when it actually manufactures the strength.

## Event 19 — VV-F11: red-first behavior and bounded implementation evidence

Before any source-model changes, this exact command exited 1 with 16 assertion
failures, all at the absent origin representation (no collection/setup errors):
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q tests/unit/data_forge/domains/academic/batch/test_parameter_value_provenance.py > _build/vocabulary-value-provenance/row3-red.log 2>&1
```
The first three table cases are the original omitted / explicit unknown / invalid
input collision: normalizer → ArticleExtractionResult dump → JSON file → validation
→ SKG intake. Additional cases traverse _to_work_record → WorkRecord JSON →
load_graph → DuckDB parameter_json → intake. All three UNKNOWN values were identical
at the consumer and had no origin. Fresh RCT/alias and historical-unmarked cases
also failed at the missing discriminator.

Before changing finalizer/inheritance persistence, the following exited 1 with
three assertion failures (finalizer merge and two methodology-to-simulation cases):
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q tests/unit/data_forge/domains/academic/batch/test_parameter_value_provenance.py -k 'finalize_merge or methodology_inheritance' > _build/vocabulary-value-provenance/row3-inheritance-red.log 2>&1
```

Instrumentation corrections within this single implementation round: the first
merge fixture's RCT donor scored above the supposed kept parameter, so its supplied
origin was correct. Adding std_error to the kept fixture makes it win the existing
quality comparison and exercises real inheritance; the test also asserts that
retained std_error. The earlier VV-F09 merge witness established the scalar outcome,
but did not establish which object won that comparison. The four-origin result
still has independent deterministic/finalizer inheritance paths. A test-only
model_copy string was replaced with the enum to eliminate a serialization warning.
A legacy-DDL fixture removes its two simulation indexes before dropping the new
column; DuckDB rejected that fixture setup while dependent indexes existed.
No product repair was made for these fixture issues.

The first complete targeted wave exited 0, 85 tests (25 in the new provenance file):
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q tests/unit/data_forge/domains/academic/batch/test_parameter_value_provenance.py tests/unit/data_forge/domains/academic/knowledge/test_skg_query.py tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py tests/unit/data_forge/domains/academic/batch/test__resolve_extract_transformers.py tests/unit/ir/mirror_contracts/test_literature.py tests/unit/ir/mirror_contracts/test_parameters.py > _build/vocabulary-value-provenance/row3-targeted.log 2>&1
```
It exercises the public SKG query after storage, both merge paths, deterministic
rescue on controlled text, methodology inheritance through simulation SQL, legacy
schemas before and after the additive ALTER, historical/unmarked values, omission,
and preservation of an actual recorded unknown when unrelated intake repair occurs.
All fixtures are controlled local test artifacts; no historical recorded unknown
was discovered or claimed, and no live extraction/model/data pass was run.

## Event 20 — VV-F12: base replay, actual denominator, and routing

The exact earlier architecture command was replayed in a separate attached audit
worktree at the slice base `37c20aaa5124ebbe4868aa040eb3b0874458e680`:
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m tools.devx.architecture.guardrails check --skip-generated-checks > _build/vocabulary-value-provenance/guardrails.log 2>&1
```
It exited 1 and reproduced the earlier complete log byte-for-byte. The three new
edges are acquisition_admission_bundle → core.artifacts.manifest / signing /
write_contract. VV-C01 is routed to `team-polisyos`, accountable code owner
`@DenisKopylov`, per the runtime public-surface contract and repository CODEOWNERS.
No architecture repair or baseline acceptance is made here.

Denominator qualification: the full scanner reads 2,619 Python files; its
intersection with this lane's eight changed source files is **eight, not zero**.
Calling that global intersection zero would be false. The failing edge predicate's
inputs (source, public entrypoint policy, baseline, exceptions, checker) are all
byte-identical to base, with changed-path intersection zero. Imported-module sets
are also unchanged in all eight touched source files. This establishes the ownership
of these three findings; it is not a claim that the entire scanner ignores our work.
The full replay and intersection receipt is:
```json
{
  "base": "37c20aaa5124ebbe4868aa040eb3b0874458e680",
  "base_exit_code": 1,
  "base_log_sha256": "83222fcdf3ced06fdbdcf01c6f376ec616139b272b8167cb42617f8aae5e85f4",
  "replay_equals_initial_log": true,
  "scanner_python_files": 2619,
  "scanner_changed_path_intersection": [
    "src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py",
    "src/polisyos/data_forge/domains/academic/batch/article_extractor.py",
    "src/polisyos/data_forge/domains/academic/batch/graph_builder.py",
    "src/polisyos/data_forge/domains/academic/batch/numeric_extract.py",
    "src/polisyos/data_forge/domains/academic/batch/resolve_finalize.py",
    "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py",
    "src/polisyos/data_forge/domains/academic/knowledge/skg_store.py",
    "src/polisyos/ir/analytics/literature.py"
  ],
  "failing_predicate_inputs": [
    "src/polisyos/runtime/http/services/acquisition_admission_bundle.py",
    "architecture/public_surface/contract.toml",
    "architecture/baselines/imports/deep_import.json",
    "architecture/exceptions/guardrails.toml",
    "tools/devx/architecture/guardrails.py"
  ],
  "failing_predicate_changed_intersection": [],
  "failing_predicate_inputs_byte_equal": true,
  "changed_source_imported_module_sets_equal": {
    "src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py": true,
    "src/polisyos/data_forge/domains/academic/batch/article_extractor.py": true,
    "src/polisyos/data_forge/domains/academic/batch/graph_builder.py": true,
    "src/polisyos/data_forge/domains/academic/batch/numeric_extract.py": true,
    "src/polisyos/data_forge/domains/academic/batch/resolve_finalize.py": true,
    "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py": true,
    "src/polisyos/data_forge/domains/academic/knowledge/skg_store.py": true,
    "src/polisyos/ir/analytics/literature.py": true
  },
  "owner": "team-polisyos / @DenisKopylov (runtime public-surface contract and CODEOWNERS)"
}
```

VV-C05 (candidate only, leave untouched): the transformer module's pre-existing
Ruff findings were replayed over the same eight source paths at base. Every finding
matches by path, code, message, and affected source text; changed line numbers are
not used as identity. Route to `team-data-forge` / `@DenisKopylov`. New-file lint
findings introduced in this round were corrected; the remaining full-file red is:
```json
{
  "base_count": 116,
  "current_count": 116,
  "base_codes": {
    "F401": 30,
    "TC001": 1,
    "E501": 53,
    "F821": 29,
    "N806": 1,
    "SIM102": 2
  },
  "current_codes": {
    "F401": 30,
    "TC001": 1,
    "E501": 53,
    "F821": 29,
    "N806": 1,
    "SIM102": 2
  },
  "new": [],
  "removed": []
}
```
A green lint delta is not reported as a green full-file lint command. As with the
architecture check, whole-file input intersection is nonzero; the reproduced finding
spans, rather than the whole touched module, are unchanged.


## Event 21 — VV-F13: P29 removal probe, restoration, and positive/negative traces

`p29-probe.py` temporarily disables the actual producer derivation while retaining
the typed field, enum identifiers, and old branch text. It assigns not_supplied to
every input and leaves the old derivation under an unexecuted branch. The original
three round-trip cases then yield one pass (omission) and two failures (declared
unknown and invalid input). Both failures are consumer-visible UNKNOWN/not_supplied
instead of the expected distinct origins, not missing imports or markers. The
probe process exits 0 only after observing pytest exit 1 and restoring exact source
bytes in a finally block; no reset, stash, or history rewrite is involved.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python _build/vocabulary-value-provenance/p29-probe.py
```
```json
{
  "command": [
    "/Users/deniskopylov/polisyos/policy-engine/.venv/bin/python",
    "-m",
    "pytest",
    "-q",
    "tests/unit/data_forge/domains/academic/batch/test_parameter_value_provenance.py::test_origin_survives_normalizer_article_storage_and_skg_intake[supplied0-unknown-not_supplied]",
    "tests/unit/data_forge/domains/academic/batch/test_parameter_value_provenance.py::test_origin_survives_normalizer_article_storage_and_skg_intake[supplied1-unknown-declared_unknown]",
    "tests/unit/data_forge/domains/academic/batch/test_parameter_value_provenance.py::test_origin_survives_normalizer_article_storage_and_skg_intake[supplied2-unknown-normalizer_fallback]"
  ],
  "mutated_exit_code": 1,
  "source_restored_sha256": "58079de639926cd03c1f2a996d93b0046dac747a61411f837345c82f2b72de87",
  "source_restored_exactly": true
}
```
The restored real implementation then exited 0, seven passes:
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q tests/unit/data_forge/domains/academic/batch/test_parameter_value_provenance.py -k 'normalizer_article_storage' > _build/vocabulary-value-provenance/p29-restored-green.log 2>&1
```

Positive trace, VV-F11's `supplied1` case: producer input
`{name: controlled.effect, value: 1.0, evidence_strength: unknown}` enters the real
normalizer. It emits UNKNOWN/declared_unknown. That typed pair survives the
ArticleExtractionResult file and reload, WorkRecord file and reload, raw SKG
parameter_json, and a fresh `SKGQuery.query_parameters(..., layer="raw")` reader.
The reader sees `evidence_strength="unknown"` and
`evidence_strength_origin="declared_unknown"` using only the stored record. This is
an actual newly recorded judgment in a controlled test, not a claimed historical
extractor output or live model invocation. The original historical positive remains
not_established: the previously measured dataset supplied no actual marked unknown.

Negative trace, VV-F11's `supplied0` case: the same producer input omits strength.
The stored record and fresh reader expose UNKNOWN/not_supplied even after defaults
materialize. It cannot present as declared_unknown. Invalid input produces
UNKNOWN/normalizer_fallback; malformed intake produces UNKNOWN/intake_fallback;
new RCT input produces RCT/supplied; merge/rescue/methodology selection produces
RCT/inherited. Old stored UNKNOWN or RCT without an origin becomes unresolved,
including the legacy simulation reader both before and after the additive column
upgrade. A marker without a strength cannot manufacture a judgment. These cover the
row-3 negative and row-4 omission requirement on the actual persistence/intake paths.

## Event 22 — VV-F14: declared generation, companion output, and final source checks

The declared generator and checker were run with the already-provisioned shared
runtime, sync disabled, and the worktree first on PYTHONPATH. A preflight import
confirmed literature.__file__ points into this worktree, not the main checkout.
Exact commands (no generated file was hand-edited):
```bash
export UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/polisyos/policy-engine/.venv UV_NO_SYNC=1 PYTHONPATH=.:src PYTHONDONTWRITEBYTECODE=1
uv run --extra ml polisyos-tools diagnostics gen-schema > _build/vocabulary-value-provenance/gen-schema.log 2>&1
uv run --extra ml polisyos-tools diagnostics gen-schema --check > _build/vocabulary-value-provenance/gen-schema-check.log 2>&1
```
Both exit 0. Generation reports 101 models, four snapshot/manifest file updates;
the declared command also refreshes docs/reference/ir/schema-catalog.md and
docs/reference/schemas.md. The two parameter-bearing snapshots receive the origin
enum and optional/defaulted field. The manifest is generated with the corresponding
hashes; the snapshots are not independently authored approvals.

VV-C06 (candidate, source repair out of scope): full generation also refreshes
literature_causal_prior.schema.json for the pre-existing optional edge strength and
ClaimVocabularyAxisStatus field. The generated third snapshot is included because
the user explicitly requires committing the declared command's output. The same
schema rendered from the **slice base runtime** is parsed-identical to that generated
file. No second public IR source type is changed. The complete class-node comparison
in the only changed IR source file (39 old classes, 40 new) gives:
```json
{
  "ir_classes_before": 39,
  "ir_classes_after": 40,
  "added_classes": [
    "EvidenceStrengthOrigin"
  ],
  "changed_existing_classes": [
    "EvidenceParameter"
  ],
  "literature_causal_prior_generated_schema_equals_base_runtime": true
}
```
Owner for the stale derived artifact is team-polisyos / @DenisKopylov. This is a
base-runtime/generated-snapshot discrepancy, not a new LiteratureEdgePrior contract
decision or reopening the claim-axis lane. All six generated outputs travel with
this feature commit.

Final architecture command:
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m tools.devx.architecture.guardrails check --skip-generated-checks > _build/vocabulary-value-provenance/guardrails-final.log 2>&1
```
Exit 1, complete log byte-identical to the base replay, SHA-256
`83222fcdf3ced06fdbdcf01c6f376ec616139b272b8167cb42617f8aae5e85f4`. No new architecture finding.
VV-F12 gives the precise nonzero scanner / zero failing-predicate intersections.

Ruff over the seven other changed source files plus the new test exits 0. The full
eight-source-file command remains exit 1 with exactly the 116 reproduced transformer
findings in VV-C05; its source-text-keyed delta is empty. Commands for the complete
census and the green complement:
```bash
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check --output-format json src/polisyos/ir/analytics/literature.py src/polisyos/data_forge/domains/academic/batch/article_extractor.py src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py src/polisyos/data_forge/domains/academic/batch/resolve_finalize.py src/polisyos/data_forge/domains/academic/batch/numeric_extract.py src/polisyos/data_forge/domains/academic/batch/graph_builder.py src/polisyos/data_forge/domains/academic/knowledge/skg_query.py src/polisyos/data_forge/domains/academic/knowledge/skg_store.py tests/unit/data_forge/domains/academic/batch/test_parameter_value_provenance.py > _build/vocabulary-value-provenance/ruff-current.json
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check src/polisyos/ir/analytics/literature.py src/polisyos/data_forge/domains/academic/batch/article_extractor.py src/polisyos/data_forge/domains/academic/batch/resolve_finalize.py src/polisyos/data_forge/domains/academic/batch/numeric_extract.py src/polisyos/data_forge/domains/academic/batch/graph_builder.py src/polisyos/data_forge/domains/academic/knowledge/skg_query.py src/polisyos/data_forge/domains/academic/knowledge/skg_store.py tests/unit/data_forge/domains/academic/batch/test_parameter_value_provenance.py
```
The base Ruff replay uses the identical source-path list without the nonexistent new
test file; path/code/message/affected source text are compared as multisets.
`git diff --check` exits 0. No directory-wide test suite was run.

Compatibility/migration owner: team-data-forge, with team-polisyos for the approved
IR contract. Deploy the new reader with the producer; an older strict reader cannot
be assumed to retain a field it did not know. New readers accept old records with
honest unresolved/not_supplied treatment. No historical backfill is authorized or
performed. API/dashboard work beyond the existing stored record and public SKG query
is surface_out_of_scope for this lane.

### Reproducible resumed census and P29 probe

`resumed-census.py` (SHA-256 `a8d11d9b4a422aefce455b7eff6e679ce27f44b761cb92a3a77536e653011d10`):
```python
"""Re-derive the complete tracked Python construction and typed-reference sets."""
import ast
import json
import subprocess
from collections import Counter
from pathlib import Path

paths = [Path(p) for p in subprocess.check_output(['git', 'ls-files', '-z'], text=True).split('\0') if p]
out = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
       'tracked_files': len(paths), 'file_types': dict(Counter(p.suffix for p in paths)),
       'python_by_root': {}, 'parse_errors': [], 'direct_constructors': [],
       'validation_calls': [], 'typed_reference_modules': []}
py_paths = [p for p in paths if p.suffix == '.py']
out['python_by_root'] = dict(Counter(p.parts[0] for p in py_paths))
for p in py_paths:
    source = p.read_text()
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        out['parse_errors'].append([str(p), str(exc)])
        continue
    aliases = {'EvidenceParameter'}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            aliases.update(a.asname or a.name for a in n.names if a.name == 'EvidenceParameter')
    if any(isinstance(n, ast.Name) and n.id in aliases for n in ast.walk(tree)):
        out['typed_reference_modules'].append(str(p))
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        entry = {'path': str(p), 'line': n.lineno, 'call': ast.unparse(f)}
        if (isinstance(f, ast.Name) and f.id in aliases) or (isinstance(f, ast.Attribute) and f.attr == 'EvidenceParameter'):
            out['direct_constructors'].append(entry)
        elif isinstance(f, ast.Attribute) and ((isinstance(f.value, ast.Name) and f.value.id in aliases) or (isinstance(f.value, ast.Attribute) and f.value.attr == 'EvidenceParameter')):
            out['validation_calls'].append(entry)
out['production_direct_constructors'] = [r for r in out['direct_constructors'] if r['path'].startswith(('src/', 'tools/'))]
out['production_validation_calls'] = [r for r in out['validation_calls'] if r['path'].startswith(('src/', 'tools/'))]
out['production_typed_reference_modules'] = [p for p in out['typed_reference_modules'] if p.startswith(('src/', 'tools/'))]
Path('_build/vocabulary-value-provenance/resumed-census.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps({k: v for k, v in out.items() if k not in {'direct_constructors', 'validation_calls', 'typed_reference_modules'}}, indent=2))
```

`p29-probe.py` (SHA-256 `a944ec86a845cbacdcbb699f79d2e2eed5abb011976531fcc120fa6d138dc5e4`):
```python
"""Remove producer derivation, keep origin identifiers, and restore exact source bytes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

source = Path('src/polisyos/data_forge/domains/academic/batch/article_extractor.py')
original = source.read_bytes()
needle = '    if strength_origin is None:\n        if "evidence_strength" not in payload:\n'
replacement = ('    if strength_origin is None:\n'
               '        strength_origin = EvidenceStrengthOrigin.NOT_SUPPLIED\n'
               '    if False:  # P29: identifiers remain; derivation does not execute\n'
               '        if "evidence_strength" not in payload:\n')
assert original.decode().count(needle) == 1
mutated = original.decode().replace(needle, replacement).encode()
test = 'tests/unit/data_forge/domains/academic/batch/test_parameter_value_provenance.py::test_origin_survives_normalizer_article_storage_and_skg_intake'
nodes = [test + suffix for suffix in ('[supplied0-unknown-not_supplied]',
                                    '[supplied1-unknown-declared_unknown]',
                                    '[supplied2-unknown-normalizer_fallback]')]
command = [sys.executable, '-m', 'pytest', '-q', *nodes]
environment = {**os.environ, 'PYTHONPATH': '.:src', 'PYTHONDONTWRITEBYTECODE': '1'}
log = Path('_build/vocabulary-value-provenance/p29-red.log')
try:
    source.write_bytes(mutated)
    with log.open('w') as stream:
        result = subprocess.run(command, env=environment, stdout=stream, stderr=subprocess.STDOUT)
finally:
    source.write_bytes(original)
assert source.read_bytes() == original
receipt = {'command': command, 'mutated_exit_code': result.returncode,
           'source_restored_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
           'source_restored_exactly': source.read_bytes() == original}
Path('_build/vocabulary-value-provenance/p29-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt, indent=2))
assert result.returncode == 1, 'The semantic regression test must fail on removal of derivation'
```
