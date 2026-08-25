# DS10 capability discovery — C00 execution journal

## Execution identity and boundary

- Attached branch: `codex/ds10-capability-discovery-plan`.
- Execution base: `8f760b813`.
- Product-root coordinate: `git rev-parse --show-prefix` returned `policy-engine/`.
- C00 mechanism paths: **0/50 observed**. C00 changed only P39 companions.
- C00 widening rounds: **0/12**. Its one register/test transaction adds no
  capability, surface, permission, or producer arm.
- Pattern pass: P35 requires the two complete-set derivations below; P38 keeps
  the DS8 assignment metric at 217 separate from the 261 live roots; P39 excludes
  the required journal, debt/register ledger, and moved denominator pin from the
  mechanism cap; P41 records the upstream missing witness as `artifact_missing`,
  rather than attributing a DS10 implementation failure to it.

## Entry census — two independent derivations

| fact | derivation A | derivation B | observed result |
| --- | --- | --- | --- |
| capability manifest physical lines | `wc -l src/polisyos/runtime/http/services/control/capabilities.py` | `awk 'END {print NR}'` and `git show HEAD:policy-engine/src/polisyos/runtime/http/services/control/capabilities.py \| wc -l` | 267 / 267 / 267 |
| direct `CapabilityFeatureInfo` constructors | AST direct-call walk | tokenizer `NAME CapabilityFeatureInfo` immediately followed by `(` | 21 at `52,59,68,75,84,94,101,108,115,124,131,140,147,154,164,174,184,191,198,206,213` |
| posture constants | quoted-string `git grep` over tracked `src/` | AST constants over all 2,576 tracked Python paths | `discoverable`: 1; `executable`: 2; `admitted_authority`: 2. The files are respectively `pre_adapter_grounding_inventory.py`; that file plus `workspace/loop.py`; and that file plus `legal_mandate_search.py`. |
| live register / DS8 assignment sub-register / DS10 roots | Python JSON length and distinct-set walk | `jq` length/`unique` projections | 261 entries / 261 unique `unit_id`; 217 assignments / 217 unique paths; 10 DS10 roots / 10 unique `unit_id`. Known members: `route-welcome`, `BureaucraticArtifactView.a11y.test.tsx`, and `route-knowledge`. |
| adapter artifact family | five admission JSON inputs plus five contract TOMLs | lifecycle-owner declarations plus G0 readiness manifest | 10 artifacts. |
| admission rows | recursive Python JSON-object walk on `admission_state` | recursive `jq` object walk on `admission_state` | 61 rows: 8 admitted, 52 candidate, 1 blocked; known admitted `layer3-substrate-data-binding-to-source-contract`. |
| declared adapter paths | `tomllib` count partition | TOML `[[adapter_paths]]`, reference, and count-field census | 41: G1 2, G2 4, G3 6, G4 11, GL 18; known `layer3_data_asset_port_to_source_contract`. |

### Exact pinned replay commands and outputs

Run from `policy-engine/` against the original C00 commit, whose source/data
inputs are unchanged by this correction:

```bash
ds10_input_commit=a5755a584858ae71a7f31856ec1ba6cf5c0254be
ds10_prefix=$(git rev-parse --show-prefix)
git show "${ds10_input_commit}:${ds10_prefix}src/polisyos/runtime/http/services/control/capabilities.py" | wc -l
git show "${ds10_input_commit}:${ds10_prefix}src/polisyos/runtime/http/services/control/capabilities.py" | awk 'END {print NR}'
git grep -l -E "['\"]discoverable['\"]" "$ds10_input_commit" -- src | sort
git grep -l -E "['\"]executable['\"]" "$ds10_input_commit" -- src | sort
git grep -l -E "['\"]admitted_authority['\"]" "$ds10_input_commit" -- src | sort
git show "${ds10_input_commit}:${ds10_prefix}architecture/atlas_surfaces/frontend-disposition-register.json" | jq '{entries: (.entries | length), units: (.entries | map(.unit_id) | unique | length), assignments: (.ds8_strangle_coverage.assignments | length), assignment_paths: (.ds8_strangle_coverage.assignments | map(.path) | unique | length), ds10: (.entries | map(select(.owner_slice == "DS10")) | length), ds10_units: (.entries | map(select(.owner_slice == "DS10") | .unit_id) | unique | length)}'
```

```text
     267
267
a5755a584858ae71a7f31856ec1ba6cf5c0254be:src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py
a5755a584858ae71a7f31856ec1ba6cf5c0254be:src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py
a5755a584858ae71a7f31856ec1ba6cf5c0254be:src/polisyos/runtime/quality/workspace/loop.py
a5755a584858ae71a7f31856ec1ba6cf5c0254be:src/polisyos/runtime/quality/proving_ground/legal_mandate_search.py
a5755a584858ae71a7f31856ec1ba6cf5c0254be:src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py
{
  "entries": 261,
  "units": 261,
  "assignments": 217,
  "assignment_paths": 217,
  "ds10": 10,
  "ds10_units": 10
}
```

The literal command block completed exit 0 at uptime `17:57 up 1 day, 8:10` →
`17:57 up 1 day, 8:10`.

The independent AST/tokenizer, JSON/`jq`, recursive admission, TOML, and lifecycle
walk was run with this exact script (the `git show` prefix pins every input):

```bash
uv run python - "$ds10_input_commit" "$ds10_prefix" <<'PY'
import ast, io, json, subprocess, sys, tokenize, tomllib
from collections import Counter
pin, prefix = sys.argv[1:]
def blob(path):
    return subprocess.run(['git', 'show', f'{pin}:{prefix}{path}'], check=True, capture_output=True, text=True).stdout
capabilities = blob('src/polisyos/runtime/http/services/control/capabilities.py')
tree = ast.parse(capabilities)
print('constructors.ast=', [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'CapabilityFeatureInfo'])
tokens = list(tokenize.generate_tokens(io.StringIO(capabilities).readline))
print('constructors.token=', [t.start[0] for i, t in enumerate(tokens[:-1]) if t.type == tokenize.NAME and t.string == 'CapabilityFeatureInfo' and tokens[i + 1].string == '('])
paths = [p for p in subprocess.run(['git', 'ls-tree', '-r', '--name-only', pin], check=True, capture_output=True, text=True).stdout.splitlines() if p.startswith('src/') and p.endswith('.py')]
terms = {term: set() for term in ('discoverable', 'executable', 'admitted_authority')}
for path in paths:
    for node in ast.walk(ast.parse(blob(path), filename=path)):
        if isinstance(node, ast.Constant) and node.value in terms: terms[node.value].add(path)
print('tracked_python_files=', len(paths)); [print(f'constants.ast.{term}=', sorted(terms[term])) for term in terms]
registry = json.loads(blob('architecture/atlas_surfaces/frontend-disposition-register.json')); entries = registry['entries']; assignments = registry['ds8_strangle_coverage']['assignments']; roots = [row for row in entries if row['owner_slice'] == 'DS10']
print('register.python=', len(entries), len({row['unit_id'] for row in entries}), len(assignments), len({row['path'] for row in assignments}), len(roots), len({row['unit_id'] for row in roots}))
admission_paths = ['architecture/policy_design_case/layer3_adapter_admission_registry.json', 'architecture/policy_design_case/layer3_g1_adapter_admission_registry.json', 'architecture/policy_design_case/layer3_g2_adapter_admission_registry.json', 'architecture/policy_design_case/layer3_g3_adapter_admission_registry.json', 'architecture/policy_design_case/layer3_gl_adapter_admission_registry.json']
contract_paths = ['architecture/policy_design_case/layer3_g1_adapter_contract_registry.toml', 'architecture/policy_design_case/layer3_g2_adapter_contract_registry.toml', 'architecture/policy_design_case/layer3_g3_adapter_contract_registry.toml', 'architecture/policy_design_case/layer3_g4_adapter_contract_registry.toml', 'architecture/policy_design_case/layer3_gl_adapter_contract_registry.toml']
rows = []
def walk(value):
    if isinstance(value, dict):
        if 'admission_state' in value: rows.append(value)
        for child in value.values(): walk(child)
    elif isinstance(value, list):
        for child in value: walk(child)
for path in admission_paths: walk(json.loads(blob(path))['adapter_admission_registry'])
print('artifacts.python=', len(admission_paths) + len(contract_paths)); print('admissions.python=', len(rows), Counter(row['admission_state'] for row in rows))
counts = []
for path in contract_paths:
    parsed = tomllib.loads(blob(path)); owner = parsed.get('adapter_contract_registry', {})
    counts.append(parsed.get('adapter_path_count', len(parsed.get('adapter_paths', owner.get('adapter_path_ids', owner.get('adapter_contract_refs', []))))))
print('adapter_paths.python=', counts, sum(counts))
PY
```

```text
constructors.ast= [52, 59, 68, 75, 84, 94, 101, 108, 115, 124, 131, 140, 147, 154, 164, 174, 184, 191, 198, 206, 213]
constructors.token= [52, 59, 68, 75, 84, 94, 101, 108, 115, 124, 131, 140, 147, 154, 164, 174, 184, 191, 198, 206, 213]
tracked_python_files= 2576
constants.ast.discoverable= ['src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py']
constants.ast.executable= ['src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py', 'src/polisyos/runtime/quality/workspace/loop.py']
constants.ast.admitted_authority= ['src/polisyos/runtime/quality/proving_ground/legal_mandate_search.py', 'src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py']
register.python= 261 261 217 217 10 10
artifacts.python= 10
admissions.python= 61 Counter({'candidate_shadow_only': 52, 'admitted': 8, 'blocked': 1})
adapter_paths.python= [2, 4, 6, 11, 18] 41
```

The literal Python script completed exit 0 at uptime `17:57 up 1 day, 8:10` →
`17:58 up 1 day, 8:11`.

For the independent lifecycle artifact family input, the same pin was passed to
`tomllib.loads(blob('architecture/generated_artifacts.toml'))` and the G0
`closure_artifact_paths`; their union was exactly the ten named JSON/TOML paths.

## C00 RED receipts

All selected tests collected successfully and then failed for the intentionally
unimplemented behavior (each exit 1, not a collection/syntax error):

```text
uv run pytest tests/unit/runtime/quality/test_capability_discovery.py::test_capability_discovery_postures_use_three_independent_producers -q
FAILED ...::test_capability_discovery_postures_use_three_independent_producers
ModuleNotFoundError: No module named 'polisyos.runtime.quality.capability_discovery'

uv run pytest tests/repo_quality/tools/test_ds10_capability_discovery_strangle.py::test_control_capability_manifest_has_no_authored_feature_rows -q
FAILED ...::test_control_capability_manifest_has_no_authored_feature_rows
AttributeError: module 'ds10_atlas_enforcement' has no attribute 'control_capability_manifest_contributors'

uv run pytest tests/repo_quality/tools/test_ds10_capability_discovery_strangle.py::test_capability_menu_rejects_hardcoded_picker_rows_and_id_branches -q
FAILED ...::test_capability_menu_rejects_hardcoded_picker_rows_and_id_branches
AttributeError: module 'ds10_atlas_enforcement' has no attribute 'check_capability_discovery_result_boundary'
```

The first RED invokes the future C02 runtime-quality composition API with three
distinguishable producers, requiring all sibling outputs and call provenance. The
second invokes the future C01 generic live Python manifest-contributor seam. The
third passes an injected hardcoded result row and ID/kind branch to the future C01
generic result-boundary checker while asserting its fixed-chrome control stays
accepted. Their absent seams are the intended missing behavior; none is a marker
or unconditional failure. The compulsory denominator pin was also RED after the debt row was added:
`test_real_census_replays_published_invariants` reported `assert 60 == 59`.
That is the expected P39 companion failure; the frontend metric remains pinned
at 217.

## Upstream registry receipt

```text
uv run pytest tests/unit/runtime/quality/test_adapter_registry_free_growth.py::test_post_g0_registry_admits_new_contract_from_data_only_mutation -q
ERROR: file or directory not found: tests/unit/runtime/quality/test_adapter_registry_free_growth.py::test_post_g0_registry_admits_new_contract_from_data_only_mutation
```

The command exited 4. The absent file is `artifact_missing`, owned by
`team-architecture` with producer lane `runtime/quality`, under debt
`ds10-adapter-registry-data-only-free-growth`. It is not a DS10 RED conjunct and
does not establish authority.

## C00 command ceilings and uptime

| command | uptime before → after | observed terminal / ceiling | writes |
| --- | --- | --- | --- |
| three individual DS10 RED witnesses | `17:28 up 1 day, 7:41` → same minute | completed exit 1 / 300s focused backend ceiling | no |
| upstream data-only registry witness | `17:28 up 1 day, 7:41` → `17:28 up 1 day, 7:42` | completed exit 4 / 300s focused backend ceiling | no |
| debt writer | `17:34 up 1 day, 7:47` → same minute | completed; 240s writer ceiling | yes, canonical `LEDGER.md` only |
| debt report-only | `17:34 up 1 day, 7:47` → same minute | completed; 30s report-only ceiling | no |
| denominator behavioral pin | `17:34 up 1 day, 7:47` → same minute | 1 passed; 300s focused backend ceiling | no |

The report-only output had exactly ten inherited
`register_supplies_missing_standing` findings and one inherited
`register_withholds_source_standing` finding. It had zero render, denominator,
closure, or DS10 debt drift. The writer preserved the checker frontend metric and
denominator at `frontend_disposition_rows=217`; only register `59 → 60` moved.

## Cluster continuation table

| cluster | status | mechanism paths | widening rounds | committed receipt |
| --- | --- | ---: | ---: | --- |
| C00 | committed and read back | 0/50 | 0/12 | `a5755a584858ae71a7f31856ec1ba6cf5c0254be` |
| C01 | not started | — | — | — |
| C02 | not started | — | — | — |
| C03 | not started | — | — | — |
| C04 | not started | — | — | — |
| C05 | not started | — | — | — |
| C06 | not started | — | — | — |
| C07 | not started | — | — | — |

## Committed-branch readback receipt

Original C00 commit `a5755a584858ae71a7f31856ec1ba6cf5c0254be` was read from
attached `refs/heads/codex/ds10-capability-discovery-plan`, not staging; its tree
was clean. `git show --format= --name-only a5755a584` was exactly:

```text
policy-engine/docs/plans/active/DEBT-REGISTER.md
policy-engine/docs/plans/active/LEDGER.md
policy-engine/docs/plans/active/atlas-slices/DS10-capability-discovery.md
policy-engine/docs/superpowers/journals/2026-08-25-ds10-capability-discovery.md
policy-engine/tests/repo_quality/tools/test_debt_ledger_checker.py
policy-engine/tests/repo_quality/tools/test_ds10_capability_discovery_strangle.py
policy-engine/tests/unit/runtime/quality/test_capability_discovery.py
policy-engine/tools/quality/validation/check_debt_ledger.py
```

`git show a5755a584:<path> | shasum -a 256` read every listed path. The original
receipt digests, in that order, were `9ffb2703bcf08365786f44b58ba2334fcb8e43895a6b1a63034537ee02ec1bc9`,
`5bef3da73a1432dd90bd4365221b5e2b5191fe6519eea384d0101f38ea76b148`,
`bb8fb6e89a97a6b8daa279a2c31d959497b593781f2f8c47fb576b87f7eaa0c9`,
`e443d19fe297c03ae99ec903bb0043fb4d90e30510c46e511a394b80a315c0ee`,
`434860ad07b1469821801a80edfa2b3a35b2ca1e54902526d7e7674aa3e1ff30`,
`5fb413625594cd8d9d3b5f2982532cc5c42e0ff2883aacd5be46e4cfafca824f`,
`a443622f2070d0cc9fca0893066fbb1cca159334ae9e32b6ac0e603d7581f793`, and
`6f8e5e07f7e4c2132187917b31fad6b09aa01010e04638d3c393da518a839f07`.
No original C00 path was a production mechanism path under `src/` or
`apps/runtime-dashboard/src/`. The correction commit's journal digest is reported
separately in the task report to avoid a self-referential journal hash.
