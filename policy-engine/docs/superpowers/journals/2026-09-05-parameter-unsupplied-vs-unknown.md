# Parameter omission versus unknown — Phase-1 stop

## 2026-09-05 — scope, baseline, and disposition

Task: `parameter-contract-cannot-distinguish-unsupplied-from-unknown`.
Worktree: `/Users/deniskopylov/polisyos/.worktrees/debt-parameter-unsupplied-vs-unknown/policy-engine`.
Attached branch: `codex/debt-parameter-unsupplied-vs-unknown`.
Entry commit: `92c08804a`; `git status -sb` showed the named branch and a clean tree.

Read the binding row in `docs/plans/active/DEBT-REGISTER.md:334` before investigation.
Its closure signal is: the two states are separately representable, every reading
consumer distinguishes them, and a negative proves omission cannot present as a
recorded judgment. **That closure is not claimed. The row remains open.**

**Phase 1 stopped; Phases 2 and 3 were not entered.** Finding `PU-F01` triggers the
explicit generated-surface stop. Findings `PU-F02` and `PU-F03` also trigger the
standing invitation to stop when measurement refutes the framing. This journal is
the measurement handoff, not a design approval or a completed repair. No design
choice, implementation, test change, generated output, or data pass was made.

The stop takes precedence over completing the rest of the consumer census. The
counts below are explicitly bounded; none is presented as the full runtime blast
radius. In particular, neither one literal constructor nor three named production
instantiation sites is a closure denominator: nested model validation, producer
normalization, persistence, copying, and consumers also matter.

Initial snapshot check, from the task worktree:

```sh
shasum -a 256 production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb
```

Result: `583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`.
Only the hash reader opened this file. No database query, data generation, writer,
permission change, or historical cohort recount was performed.

## PU-F01 — generated ABI surfaces contradict the premise

The narrow runtime OpenAPI observation is correct: zero literal occurrences in
`schemas/runtime_api_v1.openapi.json`. It does not establish absence from all
generated surfaces. The complete filesystem byte census below found
`EvidenceParameter` in these **two committed generated IR schemas**:

| Schema | Root model | Reference to the nested parameter |
| --- | --- | --- |
| `schemas/snapshots/ir/article_extraction_result.schema.json` | `ArticleExtractionResult` | `$.properties.empirical_parameters.items` |
| `schemas/snapshots/ir/context_adaptive_parameter_bundle.schema.json` | `ContextAdaptiveParameterBundle` | `$.properties.parameters.additionalProperties` |

Both contain `$defs.EvidenceParameter.properties.evidence_strength` equal to
`{"$ref": "#/$defs/EvidenceStrength", "default": "unknown"}`. Both paths were
confirmed tracked. The canonical ABI registry admits their enclosing models:
`src/polisyos/schemas/abi_models.py:356` (`article_extraction_result`) and `:370`
(`context_adaptive_parameter_bundle`); the committed IR `_manifest.json` carries
both entries too.

This is generated ownership, not an inference from a filename: the authoritative
family ID **`abi-schema-snapshots`** in `architecture/generated_artifacts.toml:602`
declares `lifecycle = "generated_committed"`, lists `schemas/snapshots/ir/` as an
output, names the ABI registry plus live contracts as source of truth, and requires
regeneration when ABI-visible contracts change. The corresponding reference is
`docs/reference/generated-artifacts.md`, family `abi-schema-snapshots`.

The contract default is therefore embedded in a governed generated ABI surface.
No generator or checker was narrowed, bypassed, or used to rewrite it. This alone
requires stopping under Phase-1 rule 1; whether further freezing rules apply is
unnecessary to that decision.

Surface census denominator, all existing files below each root, excluding only
`node_modules` path components; content was scanned as bytes, including binaries:

| Root | Files | File-type denominator | Files containing the literal |
| --- | ---: | --- | ---: |
| `packages/` | 104 | no suffix 1; `.css` 1; `.js` 2; `.json` 20; `.md` 3; `.mjs` 8; `.sh` 1; `.ts` 24; `.tsx` 44 | 0 |
| `apps/` | 1,322 | no suffix 5; `.cjs` 9; `.css` 14; `.example` 1; `.html` 2; `.js` 3; `.json` 42; `.md` 23; `.mjs` 24; `.png` 33; `.py` 3; `.sh` 1; `.svg` 18; `.ts` 471; `.tsx` 672; `.yml` 1 | 0 |
| `schemas/` | 157 | `.json` 143; `.md` 14 | 2 |

Commands (read-only; no TypeScript semantic scanner was used):

```sh
python3 - <<'PY'
from collections import Counter
from pathlib import Path
for root in ('packages', 'apps', 'schemas'):
    files = [p for p in Path(root).rglob('*')
             if p.is_file() and 'node_modules' not in p.parts]
    print(root, len(files), dict(sorted(Counter(p.suffix for p in files).items())))
    print([str(p) for p in files if b'EvidenceParameter' in p.read_bytes()])
print('runtime_openapi_literal_occurrences',
      Path('schemas/runtime_api_v1.openapi.json').read_bytes().count(b'EvidenceParameter'))
PY

python3 - <<'PY'
import json
import subprocess
from pathlib import Path
for name in ('article_extraction_result', 'context_adaptive_parameter_bundle'):
    p = Path(f'schemas/snapshots/ir/{name}.schema.json')
    schema = json.loads(p.read_text())
    print(p, schema['title'],
          schema['$defs']['EvidenceParameter']['properties']['evidence_strength'])
    def refs(obj, path='$'):
        if isinstance(obj, dict):
            if obj.get('$ref') == '#/$defs/EvidenceParameter':
                print('REFERENCE', path)
            for key, value in obj.items():
                refs(value, path + '.' + key)
        elif isinstance(obj, list):
            for index, value in enumerate(obj):
                refs(value, path + f'[{index}]')
    refs(schema)
    tracked = subprocess.check_output(['git', 'ls-files', '-z', '--', str(p)])
    assert tracked.decode().split('\0')[0] == str(p)
PY

rg -n 'ArticleExtractionResult|ContextAdaptiveParameterBundle|article_extraction_result|context_adaptive_parameter_bundle' src/polisyos/schemas/abi_models.py schemas/snapshots/ir/_manifest.json
sed -n '602,630p' architecture/generated_artifacts.toml
```

## PU-F02 — the two textual matches are not two constructions

Complete filesystem AST census: **3,052 Python files under `src/` and `tools/`**,
comprising **2,619 + 433**. It found:

| Kind | Count | Site and field behavior |
| --- | ---: | --- |
| Literal `EvidenceParameter(...)` call | 1 | `knowledge/skg_query.py:1824`; explicitly passes `evidence_strength=evidence_strength` at `:1836` |
| `EvidenceParameter.model_validate(...)` call | 2 | `batch/article_extractor.py:885`, `knowledge/skg_query.py:1776` |
| `EvidenceParameter.model_fields` access | 1 | `knowledge/skg_query.py:1743`, used to filter deserialization payloads |
| Class declaration matching the constructor-shaped text | 1 | `ir/analytics/literature.py:488`, `class EvidenceParameter(BaseModel):` |

The sole constructor's keyword list is `name`, `display_name`, `parameter_type`,
`value`, `confidence_interval`, `std_error`, `unit`, **`evidence_strength`**,
`time_period`, `geographic_scope`. Thus the brief's "2, neither passing
evidence_strength" is false. The two lexical matches consist of one call and one
declaration. This identifies the count mismatch without assuming how the earlier
measurement was made.

Independent cross-check: a git-tracked path enumeration plus regex classification
also examined **3,052 `.py` files** in the same roots, finding **one call candidate
and one class declaration**. Set reconciliation reported
`TRACKED_MINUS_WALK=[]` and `WALK_MINUS_TRACKED=[]`. It is a second enumeration and
a second counting method, not a repeat of an AST-derived list. Alias/dynamic and
enclosing-model analysis is not certified by this literal-call census.

AST command:

```sh
python3 - <<'PY'
import ast
from pathlib import Path
roots = ('src', 'tools')
files = sorted(p for root in roots for p in Path(root).rglob('*.py') if p.is_file())
print('DENOMINATOR', len(files),
      {r: sum(p.is_relative_to(r) for p in files) for r in roots})
counts = dict(constructor_calls=0, validation_calls=0, field_filters=0, class_definitions=0)
for p in files:
    tree = ast.parse(p.read_text(), filename=str(p))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'EvidenceParameter':
            counts['class_definitions'] += 1
            print('CLASS', p, node.lineno)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'EvidenceParameter':
            counts['constructor_calls'] += 1
            print('CALL', p, node.lineno, [k.arg for k in node.keywords])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == 'EvidenceParameter':
            counts['validation_calls'] += 1
            print('METHOD', p, node.lineno, node.func.attr)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'EvidenceParameter' and node.attr == 'model_fields':
            counts['field_filters'] += 1
            print('FILTER', p, node.lineno)
print('COUNTS', counts)
PY
```

Independent command:

```sh
python3 - <<'PY'
import re
import subprocess
from pathlib import Path
paths = [Path(p) for p in subprocess.check_output(
    ['git', 'ls-files', '-z', '--', 'src', 'tools']).decode().split('\0') if p.endswith('.py')]
print('INDEPENDENT_TRACKED_DENOMINATOR', len(paths))
count = 0
for p in paths:
    text = p.read_text()
    for match in re.finditer(r'\bEvidenceParameter\s*\(', text):
        prefix = text[text.rfind('\n', 0, match.start()) + 1:match.start()]
        kind = 'class_definition' if re.search(r'\bclass\s+$', prefix) else 'call_candidate'
        count += kind == 'call_candidate'
        print(kind, p, text[:match.start()].count('\n') + 1)
print('LEXICAL_CALL_CANDIDATES', count)
walk = {p for root in ('src', 'tools') for p in Path(root).rglob('*.py') if p.is_file()}
print('TRACKED_MINUS_WALK', sorted(str(p) for p in set(paths) - walk))
print('WALK_MINUS_TRACKED', sorted(str(p) for p in walk - set(paths)))
PY

rg -n 'EvidenceParameter\s*\(' src tools -g '*.py'
rg -n 'EvidenceParameter\.' src tools -g '*.py'
```

## PU-F03 — equal field values, different construction state; loss at other boundaries

The live worktree's `EvidenceParameter` has a non-optional enum field defaulting
to `UNKNOWN`. The field **value** is equal for omission and explicit `unknown`.
The stronger claim that the constructed instances cannot distinguish them is
false: Pydantic's `model_fields_set` retains presence for both direct construction
and `model_validate`, including the ordinary SKG normalization/validation path.

That observation is **not** a closure or a recommendation to use this marker as
judgment provenance. The same real-path probe demonstrates why:

| Path | Omitted input: strength / marked supplied | Explicit unknown: strength / marked supplied |
| --- | --- | --- |
| Direct constructor | `unknown` / false | `unknown` / true |
| `model_validate` | `unknown` / false | `unknown` / true |
| SKG normalizer + normal validation | `unknown` / false | `unknown` / true |
| Article extractor normalizer + validation | `unknown` / true | `unknown` / true |
| SKG validation-failure fallback | `unknown` / true | `unknown` / true |
| JSON round-trip using ordinary `model_dump_json()` | `unknown` / true | `unknown` / true |
| JSON round-trip using `exclude_unset=True` | `unknown` / false | `unknown` / true |

The extractor's `_normalize_evidence_strength` at `article_extractor.py:396`
maps empty and unrecognized values to `unknown`; `_normalize_empirical_parameter`
inserts that value at `:873` **before** validating at `:885`. The SKG fallback
at `skg_query.py:1817` reads the raw field, maps failed enum conversion to
`UNKNOWN`, and explicitly supplies it to the constructor. Removing the contract
default alone would not remove either mechanism.

Ordinary serialization materializes the default and subsequent validation sees a
supplied field. Real enclosing artifact paths use this serialization shape:
`persist_article_extraction_result` / `load_article_extraction_result`
(`literature.py:1783`, `:1801`) and
`persist_context_adaptive_parameter_bundle` / `load_context_adaptive_parameter_bundle`
(`parameters.py:59`, `:81`). This explains a real semantic loss without attributing
all of it to construction. These are observed paths, not an exhaustive round-trip
inventory.

Behavioral probe, exit **0**, all assertions passed on unchanged source. The shared
main-worktree interpreter was used because this worktree has no `.venv`; explicit
`PYTHONPATH=src` plus the printed `inspect.getfile` paths confirmed all three
owners came from this task worktree. No test runner or directory-wide suite ran.

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python - <<'PY'
import inspect
from polisyos.ir.analytics.literature import EvidenceParameter
from polisyos.data_forge.domains.academic.batch.article_extractor import _normalize_empirical_parameter
from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
print('parameter_owner', inspect.getfile(EvidenceParameter))
print('extractor_owner', inspect.getfile(_normalize_empirical_parameter))
print('query_owner', inspect.getfile(SKGQuery))
for label, extra in [('omitted', {}), ('explicit_unknown', {'evidence_strength': 'unknown'})]:
    payload = {'name': 'probe', 'value': 1.0, **extra}
    for path in ('constructor', 'model_validate', 'skg_normal', 'extractor', 'skg_fallback'):
        diagnostics = []
        if path == 'constructor':
            p = EvidenceParameter(**payload)
        elif path == 'model_validate':
            p = EvidenceParameter.model_validate(payload)
        elif path == 'skg_normal':
            p = SKGQuery._to_evidence_parameter('probe', payload, diagnostics=diagnostics)
        elif path == 'extractor':
            p = _normalize_empirical_parameter(payload, diagnostics=diagnostics)
        else:
            p = SKGQuery._to_evidence_parameter('probe', {**payload, 'parameter_type': 'malformed'}, diagnostics=diagnostics)
        assert p is not None
        print(label, path, 'value=', p.evidence_strength.value,
              'field_supplied=', 'evidence_strength' in p.model_fields_set,
              'diagnostics=', diagnostics)
        if path in ('constructor', 'model_validate', 'skg_normal'):
            assert ('evidence_strength' in p.model_fields_set) == bool(extra)
        else:
            assert 'evidence_strength' in p.model_fields_set
        if path == 'model_validate':
            sparse = EvidenceParameter.model_validate_json(p.model_dump_json(exclude_unset=True))
            full = EvidenceParameter.model_validate_json(p.model_dump_json())
            print('roundtrip', label,
                  'exclude_unset_supplied=', 'evidence_strength' in sparse.model_fields_set,
                  'default_supplied=', 'evidence_strength' in full.model_fields_set)
            assert ('evidence_strength' in sparse.model_fields_set) == bool(extra)
            assert 'evidence_strength' in full.model_fields_set
PY
```

The deliberately malformed parameter type selected the existing fallback; it
reported `fallback:validation_failed:ValidationError` and
`fallback:manual_evidence_parameter`. No production predicate was weakened to
make that probe run.

## Consumer observations before the stop — not a completeness claim

The field-reading search already shows why a nullable-field edit cannot be
scoped by constructor count. These consumers were inspected before the stop;
the remaining complete construction/validation/filter/copy/round-trip and
consumer census remains **not_established**.

| Observed consumer | Existing handling of the field |
| --- | --- |
| `knowledge/search.py:160` | Enum value lookup, zero fallback, exclude noncontributing candidates; later projects `best_design` at `:186` from a contributing candidate. |
| `scientist/cross_graph/compiler.py:1678` | `getattr(..., "value", None)` and zero if absent/unrecognized; ordinary omitted input currently arrives as `UNKNOWN`. |
| `knowledge/parameter_selector.py:116` | Dereferences `.value` for evidence weighting. |
| `batch/resolve_finalize.py:271`, `:583`, `:598` | Merge preference and design-resolution paths dereference `.value`; `unknown` can trigger substitution from another parameter or linked claim. |
| `batch/_resolve_extract_transformers.py:1299`, `:1487`, `:1539`, `:1573`, `:1652` | Quality/rescue/merge/filter/projection paths read the parameter enum and often dereference `.value`. |

`knowledge/` and `batch/` above are under
`src/polisyos/data_forge/domains/academic/`; `scientist/` is under `src/polisyos/`.
No consumer behavior changed. The weighting repair is not reopened.

## Forward versus historical; design and test disposition

The raw omission cohort **51,883 of 51,908** is inherited from the task, not
recounted here. A raw omitted key and an explicitly stored `unknown` can be
separated by field presence on fresh validation, as the synthetic real-path
probe proves. This is a statement about recorded payload presence, **not** proof
that an explicit `unknown` was an extractor's judgment: the measured normalizers
can manufacture exactly that value from omission.

The pinned snapshot has not acquired provenance it never recorded. This work
cannot distinguish a historical extractor that privately could not tell from
one that never supplied the field, cannot certify an explicit-unknown historical
cohort as judgments, and does not retroactively separate the 51,883. It neither
builds calibration nor establishes that the default is calibration's sole
blocker. No forward contract repair was made either, because the task stopped.

B-1's `CausalClaimResultV2` invariant in `knowledge/types.py:352` and
`VersionedClaimVocabularyEnvelope` in `ir/analytics/literature.py:166` were read as
prior art. **Transferability and a design choice were not decided** after the stop.
There is no Phase-2 design commit and no Phase-3 red/green implementation evidence.
The probe above is evidence for the stop, not the requested closure negative.
The closure negative and consumer integration proof remain `semantic_test_missing`
for this task's repair. Review fix rounds used: none.

## Pattern pass

Read `docs/reference/policy-design-case-failure-patterns.md` before investigation.
Relevant IDs: **P35** (a constructor-shaped match is not a call and a narrow surface
search is not the complete denominator), **P38** (field value equality does not
measure all instance state; suppliedness does not prove a recorded judgment),
**P31** (normalization and serialization reopen a default-only instance repair),
**P29/P33** (exercise actual validation and producer paths), **P07** (generated ABI
compatibility), **P15** (an inferred/default value must not become judgment
provenance). No new recurring class was invented; the register already describes
the failures, so it was not changed.

Target correct pattern and acceptance signal remain the row's whole-chain
omission-versus-judgment invariant, including its negative, under an explicitly
admitted ABI scope. No external capability is claimed. The stop predicate is
`recomputed` for schema contents and `independently_reconciled` against the
canonical generated-family and ABI registry, rather than trusting the brief's
zero over a smaller set.

## Exact transcriber-ready prose

Append to the existing row's evidence/closure prose; **retain status `open`**:

> **2026-09-05 parameter-contract measurement — basis corrected; Phase 1 stopped.**
> `PU-F01`: the runtime OpenAPI/packages/apps zero was accurate but did not cover
> generated IR ABI snapshots. `EvidenceParameter` is nested in the committed
> `article_extraction_result.schema.json` and
> `context_adaptive_parameter_bundle.schema.json`, both owned by generated family
> `abi-schema-snapshots`; their strength field embeds `default: unknown`. The
> generated-surface stop therefore applies. `PU-F02`: complete AST enumeration of
> 3,052 `.py` files in `src/` and `tools/` (2,619 + 433), independently cross-checked
> against the same complete tracked set by lexical classification, found one
> direct constructor, which explicitly supplies `evidence_strength`; the other
> constructor-shaped textual match is the class declaration. Two direct validation
> sites and the SKG field filter were also found; these counts are not the whole
> nested deserialization/round-trip blast radius. `PU-F03`: omission and explicit
> unknown have equal field values but remain distinguishable in
> `model_fields_set` at construction and on the ordinary SKG validation path.
> The extractor normalizer and SKG fallback manufacture supplied unknowns, and
> ordinary serialization erases the presence distinction. The debt is a real
> provenance-preservation problem across those boundaries, not solely loss at
> construction. No repair, ABI regeneration, calibration, data production, or
> historical cohort recount was performed. The inherited 51,883 omitted payloads
> are not retroactively separated into historical extractor judgments versus
> non-supply. Re-scope the generated ABI boundary and finish the full producer,
> round-trip, and consumer census before selecting a representation. Closure
> remains the original whole-chain distinction and negative. Evidence:
> `docs/superpowers/journals/2026-09-05-parameter-unsupplied-vs-unknown.md`, findings
> `PU-F01`–`PU-F03`.

Binding-key search additionally found the existing row in
`docs/plans/active/LEDGER.md:92` and the related acceptance statement in
`docs/superpowers/specs/2026-09-05-basis-grade-carrier-investigation.md:374`.
The latter already requires preservation through construction, persistence, and
every consumer; it does not repeat the false count. No binding or row was edited.
The architect owns active-plan transcription; this append-only journal is the
sole tracked deliverable.


## 2026-09-05 — pre-commit verification append

Readback corrected two locator typos in the narrative above: the parameter
normalizer inserts `evidence_strength` at `article_extractor.py:875` (not `:873`),
and `load_context_adaptive_parameter_bundle` starts at `parameters.py:80`
(not `:81`). The mechanism descriptions and census outputs are unchanged.
Corrections are appended to preserve the journal.

The denominator arithmetic was checked: 2,619 + 433 = 3,052; the surface
file-type subtotals sum to 104, 1,322, and 157. `git diff --check` exited 0;
`git status -sb` still named the supplied branch and showed only this new
journal. Reopened the failure/repair register for closeout (P07, P15, P31,
P35, P38, P41). No repair round, source edit, or active-plan edit occurred.
The bound debt checker will be run once after this measurement commit, with
all output redirected to a local scratch file; its result will be appended.


## 2026-09-05 — final checker, custody, and delivery append

Measurement commit `e73e43297a8c2ddaf932fe320f4149fb2f9c9318` was read back from
`codex/debt-parameter-unsupplied-vs-unknown`, byte-compared with the local journal,
and checked against the task base. Its only changed path is this journal. The
commit hook printed that no lefthook configuration was found at the worktree root;
the commit succeeded. No hook configuration was changed.

### One bound debt-checker run

```sh
mkdir -p _build/parameter-unsupplied-vs-unknown
/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python tools/quality/validation/check_debt_ledger.py --check > _build/parameter-unsupplied-vs-unknown/bound-debt-check.txt 2>&1
```

**Exit 0**, 592.33 seconds real, 558.50 user, 28.22 system. Exactly one invocation;
no write mode, report-only flag, reduced input set, retry, or baseline replay.
The checker performs pytest collection to resolve registered selectors; this
was not test execution. No directory-wide test run was made.

Log: `_build/parameter-unsupplied-vs-unknown/bound-debt-check.txt`, ignored scratch
in the task worktree. The complete captured log has 8354 bytes and 59 lines;
SHA-256 `8b8f462e92808acaa1e508d33f54f4fbb8fecbf20c8de271c32dbe224362a55c`. All 26 integer metrics, copied from the complete log:

```text
register_ids=192
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
```

The complete finding-line denominator is 29 informational findings:
9 `closure_signal_count_exit_disagreement`; 9 `closure_signal_identity_unresolvable`; 1 `closure_signal_runner_unsupported`; 10 `register_supplies_missing_standing`. There are no blocking findings. The green command does not
prove the unresolvable identities exist, does not close this task's row, and
is not an inherited-red attribution. Findings were preserved without remediation
outside the task scope.

### Final custody and scope check

After the checker finished, the same read-only `shasum -a 256` command again
returned `583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`.
`git status -sb` showed the attached task branch and a clean tree before this
append. The five embedded Python reproduction snippets also parsed successfully.
No implementation, generated schema, active plan, weight, edge encoding, or
production data changed. No push, rebase, force-push, stash, or branch switch ran.

**Final disposition: Phase-1 stop with corrected basis; debt remains open.**
The full consumer/round-trip closure census, Phase-2 representation choice, and
Phase-3 red/green repair are unperformed under the explicit stop rules. The
transcription above is ready for the architect; it does not authorize a wider
ABI repair. This final journal append is the closeout commit, not a design phase.

## 2026-09-05 — ratified Phase-1 continuation: gate evidence first

The principal ratified `PU-F01`–`PU-F03` and authorized an additive optional
property in exactly the two existing ABI schemas, while explicitly forbidding
any third generated surface. Continuation entry: `1cddd7774`. `git status -sb`
confirmed the requested attached branch and clean tree. The requested
`git merge main` returned **Already up to date**: the local `main` ref was
`92c08804a72aadb4d698a26b0af1fba0823c0da9`, already an ancestor. No rebase, branch
switch, or history rewrite was used.

### PU-G01 — gate answer: presence preserves two observable buckets, not three origins

**A presence-only repair can retain “omitted at this intake” versus “supplied at
this intake” on the ordinary SKG path. It cannot identify whether a supplied
`unknown` was judged or manufactured upstream.** It therefore does not, by
itself, supply a calibration cohort of recorded unknown judgments. At the
extractor/fallback output, even the distinction between those input origins has
already been erased. This is a bounded two-bucket answer, not a claim that an
origin-aware future producer could never distinguish the three states.

The gate was checked on **one real omitted numeric payload**, selected read-only
from the pinned snapshot, plus explicitly controlled counterfactuals over that
same payload. This is a witness, not a historical census. The selected raw JSON
had SHA-256 `eabf99048ea5972275f84686986d6bd7a221c8625611e443a9661545370a8bc0`.
No payload was saved, re-derived, or exported, and no cohort count was computed.
The snapshot's initial continuation hash was again
`583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`.

| Measured path | Omitted input | Explicit-unknown counterfactual | Gate consequence |
| --- | --- | --- | --- |
| `SKGQuery._normalize_evidence_parameter_payload` → normal `model_validate` | Preserves missing key and false field-presence bit | Preserves supplied key | Suppliedness survives intake, not judgment provenance |
| Ordinary `model_dump()` → `model_validate()` | Materializes `unknown`; presence becomes true | Presence is already true | Existing round-trip loses omission |
| `_normalize_empirical_parameter` | Inserts normalized `unknown` | Emits `unknown` | Entire serialized values and `model_fields_set` are identical |
| SKG validation-failure fallback | Constructs explicit `UNKNOWN` | Constructs explicit `UNKNOWN` | Serialized outputs are identical; both mark the field supplied |

The final two comparisons deliberately changed origin while holding the
normalizer's observable output equal. A downstream presence classifier cannot
recover the distinction from that output. An unmarked legacy record is not
promoted to “judged” by discovering that its key exists.

The source map also prevents treating every normalizer caller as a fresh
extractor judgment. A full walk of **3,052 `.py` files in `src/` and `tools/`
(2,619 + 433)**, followed by AST classification of calls to the two named intake
functions, found:

| Intake | Named call sites | Input origin |
| --- | --- | --- |
| `_normalize_empirical_parameter` | `batch/article_extractor.py:1147`; `batch/_resolve_extract_api.py:1600`; `batch/_resolve_extract_transformers.py:1467` | Main parsed extraction; parsed LLM numeric rescue; deterministic rescue that copies strength from another parameter, a claim, or article methodology |
| `_to_evidence_parameter` | `knowledge/skg_query.py:405`; `knowledge/skg_query.py:467`; `tools/quality/validation/rederive_layer3_gy_n10_cg1_l2_relation_census.py:419` | Simulation-table projection; raw parameter JSON; relation-census consumer |

`batch/` and `knowledge/` above are under
`src/polisyos/data_forge/domains/academic/`. These are three named calls to each
intake, not a complete dynamic or transitive consumer count. Ordinary SKG
normalization preserves the input suppliedness it receives; the simulation
reader already supplies `str(row[7] or "")`. Deterministic rescue also supplies a
strength without recording an independent parameter-level judgment. Thus a flag
derived at the common validator cannot label every present value “judged”.

The useful prospective distinction is conditional: an instrumented producer
could record the branch that supplied or manufactured a value before it erases
the input state. **No three-state producer contract was implemented or certified
here.** The separate ABI stop below was encountered before representation design.
The historical 51,883 omissions and 342/458 cohorts remain untouched; neither
presence retention nor a newly added status retroactively supplies their missing
judgment provenance.

Real-payload probe, exit **0**; all assertions passed against unchanged source:

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python - <<'PY'
import hashlib, json
from pathlib import Path
import duckdb
from polisyos.ir.analytics.literature import EvidenceParameter
from polisyos.data_forge.domains.academic.batch.article_extractor import _normalize_empirical_parameter
from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
p = Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
with duckdb.connect(str(p), read_only=True) as con:
    row = con.execute("SELECT canonical_name, parameter_json FROM ac_skg_parameters WHERE NOT json_exists(parameter_json, '$.evidence_strength') AND try_cast(json_extract_string(parameter_json, '$.value') AS DOUBLE) IS NOT NULL LIMIT 1").fetchone()
assert row is not None
name, raw_json = row
raw = json.loads(raw_json)
assert 'evidence_strength' not in raw
print('ONE_READ_ONLY_WITNESS_SHA256', hashlib.sha256(raw_json.encode()).hexdigest())
normal = SKGQuery._to_evidence_parameter(name, raw)
assert normal is not None
assert 'evidence_strength' not in normal.model_fields_set
full = EvidenceParameter.model_validate(normal.model_dump())
assert 'evidence_strength' in full.model_fields_set
fresh_unknown = {**raw, 'evidence_strength': 'unknown'}
manufactured = _normalize_empirical_parameter(raw)
supplied = _normalize_empirical_parameter(fresh_unknown)
assert manufactured is not None and supplied is not None
assert manufactured.model_dump(mode='json') == supplied.model_dump(mode='json')
assert manufactured.model_fields_set == supplied.model_fields_set
for label, payload in [('omitted', raw), ('supplied_unknown', fresh_unknown)]:
    diagnostics = []
    fallback = SKGQuery._to_evidence_parameter(name, {**payload, 'parameter_type': 'malformed'}, diagnostics=diagnostics)
    assert fallback is not None
    assert 'evidence_strength' in fallback.model_fields_set
    print('SKG_FALLBACK', label, fallback.evidence_strength.value, diagnostics)
    if label == 'omitted':
        fallback_first = fallback
    else:
        assert fallback.model_dump() == fallback_first.model_dump()
print('EXTRACTOR_AND_FALLBACK_ORIGIN_COLLISIONS_CONFIRMED', True)
PY
```

The controlled supplied-unknown input is not represented as a historical judgment.
The malformed parameter type selects the existing fallback and is not a product
predicate change. The exact call-census command was:

```sh
python3 - <<'PY'
import ast
from collections import Counter
from pathlib import Path
files = sorted(p for root in ('src', 'tools') for p in Path(root).rglob('*.py') if p.is_file())
print('PYTHON_DENOMINATOR', len(files), dict(Counter(p.parts[0] for p in files)))
counts = Counter()
for p in files:
    text = p.read_text()
    if not any(symbol in text for symbol in ('_normalize_empirical_parameter', '_to_evidence_parameter')):
        continue
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ''
        if name in ('_normalize_empirical_parameter', '_to_evidence_parameter'):
            counts[name] += 1
            print('CALL', p, node.lineno, ast.unparse(func))
print('NAMED_CALLS', dict(counts))
PY
```

### PU-G02 — optional addition is additive, but the two-file governed scope cannot verify

The principal's **schema-level observation is confirmed**: both embedded
`EvidenceParameter` definitions have `required = ["name"]`, so
`evidence_strength` is not required. The witness added only a new optional string
property, removed it in a comparison copy, and asserted exact equality with the
original schema. It changed no existing requiredness, type, default, or property.

**The governed output denominator is nevertheless at least three files.**
`schemas/snapshots/ir/_manifest.json` records `sha256_full` and `sha256_semantic`
for both schemas, plus a `content_hash` over its model entries. The same
`abi-schema-snapshots` generated family owns this file under `schemas/snapshots/ir/`;
`schemas/snapshots/ir/AUTHORING.md` explicitly identifies the manifest as generated
snapshot metadata. The canonical generator `gen_schema.py` recomputes the schema
hashes in `_load_or_generate_entry_payload`, builds the manifest in `_build_manifest`,
and `_process_module` checks it with `_assert_manifest_equals`.

Measured, using those **unchanged owner functions**:

- Both current schema hashes match their recorded manifest entries.
- The unchanged manifest passes the owner comparator: `CONTROL_ERRORS=[]`.
- A pure optional-property addition changes both full and semantic hashes.
- With the recomputed hashes and manifest content hash, the owner comparator
  rejects the still-committed manifest:
  `snapshot out of date: schemas/snapshots/ir/_manifest.json`.

The manifest content hash moved from
`043a4935b5da12dc4357d88513d05999f08a27771b670a19877282e6b24b1d71` to
`a307807b28561ead0bed552dc7f721e86c43add7f4802254ac52a6955ec479a4` for the
disposable in-memory witness. No schema or manifest file was written. This is
not a full generator run or an assertion that the whole ABI check is green;
it directly exercises the existing manifest predicate that the allowed change
would invalidate.

**Stop rule 2 applies.** The required third generated artifact is explicitly
outside the continuation's scope. Keeping stale hashes or omitting the manifest
comparison would conflict with stop rule 3 as well. No checker was weakened or
narrowed. This is not a claim that optional properties are intrinsically breaking:
the addition is additive, and its generated receipt still has to change.

Bucket: the same generated-denominator class as `PU-F01`, one level deeper
(schema owner → generated manifest). No implementation/fix round was attempted.
P39's distinction between mechanism paths and mandatory companions does not
override an explicit prohibition on **any other generated surface**.

Read-only additive witness, exit **0**, with expected comparator rejection asserted:

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python - <<'PY'
from copy import deepcopy
import json
from pathlib import Path
from tools.quality.diagnostics import gen_schema as owner
manifest_path = Path('schemas/snapshots/ir/_manifest.json')
manifest = json.loads(manifest_path.read_text())
control_errors = []
owner._assert_manifest_equals(manifest_path, manifest, control_errors)
assert not control_errors
changed = deepcopy(manifest)
for key in ('article_extraction_result', 'context_adaptive_parameter_bundle'):
    schema_path = Path('schemas/snapshots/ir') / manifest['models'][key]['schema_file']
    schema = json.loads(schema_path.read_text())
    recorded = manifest['models'][key]
    assert owner._schema_hash(schema) == recorded['sha256_full']
    assert owner._schema_hash(owner._strip_metadata(schema)) == recorded['sha256_semantic']
    candidate = deepcopy(schema)
    param = candidate['$defs']['EvidenceParameter']
    assert 'evidence_strength' not in param['required']
    assert 'optional_probe_status' not in param['properties']
    param['properties']['optional_probe_status'] = {'type': 'string'}
    restored = deepcopy(candidate)
    del restored['$defs']['EvidenceParameter']['properties']['optional_probe_status']
    assert restored == schema
    assert param['required'] == schema['$defs']['EvidenceParameter']['required']
    full = owner._schema_hash(candidate)
    semantic = owner._schema_hash(owner._strip_metadata(candidate))
    assert full != recorded['sha256_full'] and semantic != recorded['sha256_semantic']
    changed['models'][key]['sha256_full'] = full
    changed['models'][key]['sha256_semantic'] = semantic
changed['content_hash'] = owner._schema_hash(changed['models'])
assert changed['content_hash'] != manifest['content_hash']
probe_errors = []
owner._assert_manifest_equals(manifest_path, changed, probe_errors)
assert probe_errors == [f'snapshot out of date: {manifest_path}']
print('CONTROL_ERRORS', control_errors)
print('CANONICAL_CHECKER_ERRORS', probe_errors)
print('WRITTEN_FILES', [])
PY
```

### Design and implementation disposition

The gate answer above was recorded before any representation decision. The
optional-property witness is a falsifier for governed scope, not a proposed
status vocabulary. No Phase-2 design was selected or committed and no Phase-3
implementation or red/green cycle was started, in accordance with the stop.
B-1's exact nullable-value/absence invariant is not silently claimed to transfer
to the currently non-nullable field; resolving that design question remains work
for the admitted scope. The task's closure negative remains `semantic_test_missing`.

The failure register was reopened before this investigation. Relevant existing
patterns: P35 (complete generated output denominator), P38 (presence is not
judgment provenance), P31 (intake/normalizer/emission class), P07 (content-bound
generated receipt), P29/P33 (real owner comparator and counterfactual probes),
P15 (candidate value does not acquire authority from a field-presence bit).
No new register rule is needed for this repeated class.

### Exact continuation transcriber-ready prose

Replace the incorrect mechanism sentence; keep the row **open**:

> `EvidenceParameter.evidence_strength` defaults to `UNKNOWN`; omission and
> explicit unknown have equal field values but remain distinguishable in
> Pydantic's `model_fields_set` at construction and on the ordinary SKG validation
> path. An ordinary `model_dump` → `model_validate` round-trip erases that presence
> distinction. The extractor normalizer and SKG fallback also manufacture explicit
> `UNKNOWN` before constructing the parameter, so preserving presence alone
> distinguishes omitted versus supplied at an intake, not judged versus
> manufactured unknown. It does not establish a historical or forward calibration
> cohort of recorded unknown judgments without producer-origin evidence.

Append the continuation result:

> **2026-09-05 ratified Phase-1 continuation — stopped before design.** `PU-G01`
> exercised one real omitted payload read-only and controlled counterfactuals:
> ordinary SKG intake preserves omission, ordinary round-trip loses it, and the
> extractor/fallback emit identical values and presence for omitted versus
> explicitly supplied unknown inputs. No historical cohort was re-derived.
> `PU-G02` confirms that a new optional property is additive in both ABI schemas,
> but refutes the sufficiency of the two-file generated scope: the generated IR
> `_manifest.json` content-binds both schemas. An in-memory optional-only addition
> changed both schema hashes and made the unchanged canonical manifest checker
> reject the old manifest. Stop rule 2 therefore applies; no source, schema,
> manifest, weight, edge encoding, or production data changed. The missing scope
> companion is `schemas/snapshots/ir/_manifest.json`; admitting it would remove
> this measured stop, not certify that no other prerequisite exists. The row stays
> open, with the original negative and complete producer/consumer/round-trip
> closure still required. Evidence: this journal, `PU-G01` and `PU-G02`.
