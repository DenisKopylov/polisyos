# DS10 capability discovery — C00–C01 execution journal

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
| C01 | verified boundary; committed by this boundary | 5/50 | 2/12 | `feat(core): define independent capability discovery postures` |
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

## C01 canonical contract and generic enumeration strangle

### Identity, path accounting, and pattern pass

- C01 started from exact base `fd69e66cb0b8998abd17361f20cef9f9d5070428`
  on attached `codex/ds10-capability-discovery-plan`; product prefix was
  `policy-engine/` and the tree was clean.
- The five declared mechanism paths are exactly the new canonical discovery
  contract, the existing search and control contracts, the G0 inventory import,
  and Atlas enforcement checker named by the approved plan. No adapter admission
  artifact or builder changed.
- P39 companions are the four mirrored/repo-quality test paths plus this journal.
  Mechanism accounting is **5/50** and widening accounting is **2/12**.
- CC03/CC04/CC07 are closed at the contract boundary by three sibling producer
  results and fail-closed authority evidence requirements. CC13/CC16 are bound by
  source-derived Python and dashboard denominators, import/alias/value-flow facts,
  and the sibling/indirect render mutation. Relevant repairs are P04/P05/P15/P25,
  P27/P29/P31/P33/P35/P38/P39/P41: no ordinal posture promotion, no authority from
  discovery, no key table as lint truth, behavioral corruption, complete physical
  denominators, and explicit slice-base ownership of observed reds.

### RED-first receipts

Before production/tooling edits, the contract identity failed at collection with
`ModuleNotFoundError: polisyos.core.contracts.capability_discovery` (exit 2,
1.25s). The two repo-quality identities failed only because the new checker APIs
were absent (2 failed, exit 1, 1.87s). The three focused Atlas identities failed
only because the new checker APIs were absent (3 failed, exit 1, 1.81s). These
mutations respectively catch absence of the canonical posture contract, an
import-aliased direct manifest contributor, and indirect/sibling hardcoded result
rows/branches while retaining the fixed-chrome benign control.

### Implemented property and live denominators

`CapabilityDiscoveryRequest` wraps the real `SearchRequest` and a six-kind filter;
it does not manufacture placeholder constructs/layers. `SearchFrontier` extends
`SearchLedger`, so selected/rejected/no-hit/index/freshness/replay truth remains
owned by the existing grammar while only observed counts, cutoff, and typed
completeness are added. The response keeps three sibling discovery, execution,
and purpose-bound authority results. Positive execution requires operation,
conformance, and policy inputs; positive authority requires both binding and
currentness. A discoverable candidate cannot populate `authoritative_for`.

`validate_enforcement` now derives and invokes both C01 checks on real source
sets. The measured physical denominators are **2,577 Python files** and **1,026
dashboard TS/TSX files**. The live Python result is the known pre-C03 set of **21
manifest contributors**; the live discovery-render result is **0 violations**
because its generic surface does not exist until C05. Current contributors are
returned as validation errors rather than whitelisted by the one-time 21-key plan
table; C03 removes/re-grounds them. Corruption tests prove chained Python value
flow, direct and full-module imports, sibling render imports, indirect constants,
adapter-ID switches, authored arrays, and accepted data-driven/fixed-chrome cases.

### GREEN and replay receipts

- Canonical contract tests: 7 passed; after the no-hit/incompleteness falsifier
  was added, the same seven identities remained green.
- Search plus discovery contracts: 9 passed.
- G0 suite: 33 passed before the canonical-identity companion; contract plus G0
  focused replay passed 39 tests. The final focused replay includes the added G0
  identity and is recorded in the task report.
- Repo-quality DS10 strangles: 2 passed.
- Focused Atlas C01 checks were 6 passed before live-entry integration; the final
  C01 selector is recorded in the task report.
- G0 JSON replay against `fd69e66c` was byte-identical. Both SHA-256 digests were
  `9f4b83e347aa5147425cd82bf5bb411799e845f7662eab745d09d13bc011d73c`.

The approved combined command was started at uptime `18:17 up 1 day, 8:30` with
the frozen 300s ceiling and was interrupted only after exceeding it; pytest
unwound at 341.47s. It is a verification non-receipt and was not rerun. The
smallest exposed TS-stack identity was isolated exactly:

```text
architecture/atlas_surfaces/test_atlas_enforcement.py::AtlasEnforcementTests::test_query_construction_and_producer_censuses_are_source_complete
```

It exits 1 on the C01 tree with `RangeError: Maximum call stack size exceeded`
inside `status_retirement_scan.mjs:typeContainsAnyOrUnknown`. An archive replay of
the exact same identity at slice base `c31c8cec725727637ee986e4541ac7926a553513`
also exits 1 with the same stack overflow. Its complete production input
denominator is TS/TSX; C01 changes zero TS/TSX paths, so the changed-input
intersection is zero. Under P41 this is inherited scanner debt, while the killed
combined run itself remains a non-receipt. No other exposed failure is claimed
inherited without its own exact replay.

Focused Ruff checks are green for all new/changed C01 additions. The three
pre-existing noncanonical files (Atlas checker, Atlas test, G0 inventory) fail
whole-file format checks at both the slice/base content and current content; a
line-range comparison found no new formatting delta after the one C01 checker
wrap was repaired. Base/current Ruff diagnostic counts are 13/13 for the checker,
222/222 for the Atlas test, and 0/0 for G0. Final diff/readback receipts and exact
uptime pairs are written in the external C01 report after commit.

## 2026-08-26 approved CC15 amendment and C05 restart

The accepted C00–C04 boundary is attached and clean at
`9d4fbc0506fc0d99884d7c438c6333dc93ec7262`, with 18/50 unique mechanism paths
and 7 consumed rounds. Product-root `git rev-parse --show-prefix` remains
`policy-engine/`.

The earlier C05 stop correctly measured the post-G0 bridge-adapter family but
incorrectly bound that overloaded family name to CC15. The master-plan property
is UI genericity over the six-kind capability-row federation. Two independent
kind censuses agree on six kinds; two independent production-class censuses
agree on zero concrete `CapabilityDiscoveryProvider` implementations at restart.
The complete owner-index census found `legal_norm` strongest: the real Lex
database and CapabilityIndex compiler admit a row only after grounding,
reference resolution, hallucination clearance, jurisdiction, and temporal
effectiveness are recomputed. `case` remains absent/unallocated; source and
Scientist registries lack equivalent durable owner snapshots.

CC15 is therefore amended to one generated `legal_norm` owner row, a production
Lex provider, real index rebuild, real FastAPI route, real hook/panel, exact
captured MACHINE bytes, DOM parity, and complete test-start dashboard path,
extension-partition, and byte equality. No response fixture, direct DTO, or test
provider double can satisfy the witness. The post-G0 rows
`ds10-adapter-registry-data-only-free-growth` and
`ds10-adapter-admission-capability-discovery-bridge` retain team-architecture /
runtime-quality ownership and executable commands but are not CC15 conjuncts.

The amendment consumes round 8 and raises only the round stop ceiling, 12 → 15;
the hard path ceiling remains 50. CC15 requires one pre-authorized C05 path
exception: `src/polisyos/runtime/quality/capability_discovery.py`, because the
complete production census found no existing concrete provider and the rejected
seam is the test `_Provider`/direct owner DTO. That path was already counted by
C02, so the slice-wide unique-path denominator does not grow.

### C05 initial RED

Before any C05 production edit, the exact amended witness command completed red
with exit 4 because its test artifact was absent:

```text
uv run pytest tests/integration/runtime_frontend/test_capability_discovery_free_growth.py::test_new_legal_norm_owner_row_appears_without_frontend_code_change -q
```

Receipt: 0.87s against the frozen 300s focused-backend ceiling; uptime
`09:21 up 1 day, 23:34` before and after. An earlier wrapper attempted to assign
zsh's read-only `status` variable after observing the same absent test; that
wrapper is a tooling non-receipt and is not evidence.

### C05 owner-index implementation and GREEN receipts

The selected owner is `legal_norm`. Unlike the other currently available seams,
its Lex owner database is compiled through grounding, reference resolution,
hallucination, jurisdiction, and temporal checks into a content-bound
`CapabilityIndex` snapshot. `LexCapabilityDiscoveryProvider` searches that real
projection and preserves its selected/rejected rows, cutoff, freshness, replay,
and typed incompleteness. A later provider-side filter was rejected because it
would let quarantined owner data enter the owner snapshot before being hidden;
the compiler now admits only `canonical`/`canonicalized` legal facts. This is a
narrowing repair and consumes no round.

The exact free-growth test derives scratch Lex tables from the real owner DB
schema, inserts a generated valid row plus unrelated, quarantined, and malformed
siblings, runs the real compiler, installs the production provider through the
runtime's normal override seam, calls a live FastAPI server, and renders the real
hook and panel. Its generated ID is absent from both source trees. It asserts one
candidate-grade result, execution only from the independent resolver, authority
not admitted with the visible `not_established` reason, selected and rejected
frontier rows, exact captured/downloaded MACHINE bytes, full DOM twin equality,
and complete test-start dashboard path/extension/byte equality.

The exact amended witness is GREEN: one passed in 26s against the frozen 300s
ceiling, uptime `09:45 up 1 day, 23:58` -> `09:46 up 1 day, 23:59`. Its original
artifact-absent RED is recorded above. The provider/compiler focused wave is
GREEN: 20 passed in 41s against 300s, uptime `09:47 up 2 days, 0 sec` ->
`09:47 up 2 days, 1 min`. One preceding selector miss named a nonexistent test
identity and exited 4; it is a tooling non-receipt, not product evidence.

The generic dashboard wave is GREEN: 10 files passed, one environment-gated live
file skipped, 26 passed/1 skipped in 4s against 30s; uptime
`09:45 up 1 day, 23:58` before/after. The live file is exercised, not skipped, by
the Python witness above. An earlier completed dashboard wave failed 2/27 after
the proof surface began reading producer/time fields from intentionally partial
hook doubles; the doubles were repaired to the generated contract. A second
focused failure retained the old authority-state expectation (`not_established`
instead of state `bridge_missing` plus reason `not_established`) and was corrected
without changing production semantics. TypeScript compilation, Prettier, Ruff,
the two generic DS10 strangle identities, and diff whitespace checks are green.

The panel binds both `query_text` and `construct_refs` to the normalized user
term; retaining the opening construct while editing the query was found to be a
real all-terms search escape and removed as a free narrowing. It renders request,
candidate grade, all three posture states/producers/proof refs/provenance/time,
selected and rejected evidence/limitations, counts, cutoff, indexes, versions,
freshness, no-hit, completeness, and incompleteness. The DOM twin reconstructs
the ordered envelope/results/postures/frontier/candidate partitions, and its
mutations cover omission, reordering, selected-row drift, and authority drift.

C05 has 13 declared dashboard mechanism paths plus two pre-authorized reused
backend paths: `runtime/quality/capability_discovery.py` for CC15 because no
concrete production provider existed, and
`runtime/quality/capability_index_compiler.py` for CC15's quarantined-row sibling
because a provider filter was the rejected late seam. Those two were already in
the slice's C02 denominator. The slice-wide unique mechanism count is therefore
**31/50**; the amendment plus C05's two widenings bring rounds to **10/15**.

## C06 fixed chrome, generic palette, and root adjudication

The complete 14-direct-plus-one-downstream manifest census is now partitioned by
plane. Workspace routes, run tabs, panels, dashboard/Lex navigation, and fixed
command entries use typed local `SurfaceAvailability` plus their existing authz
and rollout owners; discovery cannot hide or unlock them. Composer execution
checks still read the server-produced manifest through execution-policy-named
helpers, but its four manifest-derived “capability highlight” tiles and the
downstream `ComposerModeSections` prop channel are gone. Lex trigger remains a
dedicated authenticated mutation and never enters discovery results.

The first C06 delta left the command palette with fixed commands only. That
would have met chrome separation while missing the approved open-result half, so
the source freeze was explicitly invalidated. The palette now binds its input to
`useCapabilitySearch`, requests all six contract kinds, and renders returned rows
generically with candidate clothing and the three independent posture states.
Selecting a candidate navigates to the evidence surface; it grants no action or
permission. The hook gained an `enabled` gate so a closed or empty palette does
not generate an owner query. Reopening the C05 hook is a CC14 path exception; the
rejected seam was an always-on search. It adds no unique slice path or round.

The register writer changes exactly the ten DS10 root objects: five
`rebind_pending/strangled` with successor receipts and five
`use_as_is/not_applicable` without successors. The live register remains 261
entries/261 unique, while the separate DS8 denominator remains 217 assignments/
217 unique and its raw object bytes equal the C05 preimage. Review found that the
first writer implementation parsed and serialized the whole governed JSON even
though its resulting diff happened to be bounded. That mechanism was replaced
with a ten-object span writer, non-target byte equality, idempotency, failure-
atomic register/report promotion, and a same-count DS8 corruption rejection.
This is a P29/P39 narrowing and consumes no round.

RED-first fixed-chrome tests initially failed three identities in 1.50s. The
current focused dashboard wave is GREEN: 11 files / 92 tests in 8s against 30s,
uptime `09:51 up 2 days, 4 mins` before/after. The exact DS10 root and renamed
manifest-reviewer mutation identities are GREEN: 2 passed in 13s against 300s,
uptime `09:57 up 2 days, 10 mins` -> `09:57 up 2 days, 11 mins`. The surgical
writer/corruption pair is separately GREEN at 2 passed in 5.7s.

The broad two-file Atlas architecture command was manually interrupted at its
300s ceiling and is a non-receipt. Before interruption it reproduced the known
slice-base TypeScript `RangeError`, exposed generated authority/supplemental
register drift that C07's narrow register regeneration owns, and found one DS10
test mutation still targeting the retired `useCapabilityDiscovery` spelling.
The latter was repaired to `useCapabilityManifestAvailability` and its exact
identity is green. No interrupted output is counted as a suite receipt.

C06 has its 12 declared mechanism paths plus the reused hook exception above.
It adds 12 unique paths, so the slice is **43/50**. Its three planned widenings
bring the running round total to **13/15**.

## C07 freeze, closeout findings, and final receipts

### Identity, accounting, and source freeze

C07 began attached and clean at
`b4e96e0ebfa1c1ec7ec6f721e636f984a1ad58dc`; product-root
`git rev-parse --show-prefix` returned `policy-engine/`. Source was frozen after
the accessibility repair. Later changes were tests and mandatory governance
companions only. The visual lane, register writer, and debt writer were acquired
separately and released before the closeout commit.

Two independent path derivations agree on **46/50 unique mechanism paths**:

1. the complete base-to-closeout set has 105 paths; P39 classification gives
   46 mechanisms plus 59 mandatory companions (this journal was already in the
   base-to-closeout path union before its C07 append);
2. accepted C00-C04 `18` + C05 `13` + C06 `12` + three C07 exceptions = `46`.

The approved declaration was 42. Its four recorded exceptions are C04's
`tools/ops_runners/runtime/generate_runtime_client.py` plus three C07 narrowing
paths: `features/evidence/domain/searchParams.ts` (CC14 real palette selection),
deleted `useDataCatalogSearch.ts` (CC17 one strict hook), and
`DataIntelligencePanel.tsx` (CC11/CC18/CC19 removal of the sibling hit-only
renderer). C07's closeout commit contains 56 paths after this journal: three new
mechanism exceptions and 53 already-counted mechanisms or P39 companions. The
round account is **14/15**; C07 consumes one verification transaction and every
post-freeze repair is narrowing.

### CC15 final form and causal-method scope correction

The CC15 carrier is `legal_norm` because the Lex owner database is the strongest
real extensible index: grounding, reference resolution, hallucination clearance,
jurisdiction, and temporal effectiveness are recomputed before its rows enter a
content-bound `CapabilityIndex`. The final witness creates an ID absent from both
source trees, writes it through the real Lex schema and admission compiler,
installs the production `LexCapabilityDiscoveryProvider` through the runtime's
normal dependency seam, starts the real FastAPI route, and renders the real hook
and panel. No fixture response, provider double, direct DTO, or ID branch can
satisfy it. It asserts exactly one candidate-grade row; execution only from the
independent operation/conformance/policy producer; authority
`bridge_missing/not_established`; selected and rejected candidates; exact
captured-response/MACHINE bytes; full DOM parity; and complete test-start
dashboard path, extension partition, and bytes unchanged. Its original exact
RED was the absent test artifact (exit 4, 0.87s). Final GREEN: 1/1 in 237s under
the frozen 300s ceiling, uptime `13:34 up 2 days, 3:47` ->
`13:38 up 2 days, 3:51`. Missing, stale, quarantined, malformed,
policy-disabled, no-hit, and recall-miss siblings remain independent controls.

Closeout inspection found that the plan's old `project_capability_features`
sentence was unsafe. The complete projection consists of causal backend/family
availability booleans, not owner-indexed method rows; adapting them as
`discoverable` would be a P38 execution-to-discovery collapse. The typed causal
contract remains in the manifest's `causal_runtime` execution projection and
method discovery stays `producer_missing`. New debt
`ds10-causal-method-index-provider-bridge` is owned by `foundry/methods`, producer
bridge lane `runtime/quality`. Its exact closure test is absent and exits 4 in
34s at uptime `13:29 up 2 days, 3:42`; this is `artifact_missing`, not a DS10
positive and not a blocker because the surface renders the typed negative.

### Accessibility and visual freeze

Independent review rejected the first contrast witness as a P38 proxy: it
accepted semi-transparent backgrounds, ignored Axe incomplete results, and did
not require a numeric contrast pass. The strengthened test requires the
candidate badge to be inside the tested backdrop, rendered alpha exactly 255,
no background image, zero Axe violations, zero incomplete nodes, and at least
one numeric WCAG-AA pass whose actual ratio meets the required ratio. The first
strengthened RED found the missing opaque backdrop (106.30s,
`12:39` -> `12:41`); after adding it, the second RED exposed the real 1.12:1
contrast (67.83s, `12:41` -> `12:43`). The final candidate wrapper uses opaque
paper plus foreground text. Focused a11y is 3/3 green in 79.67s under 240s,
uptime `12:55` -> `12:56`. The scrollable packet list is a named, focusable
native list with a tightly bounded lint exception.

That repair invalidated the first visual freeze explicitly. The final refrozen
transaction used `PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1`: stale no-writer RED
was exactly 553 candidate-snapshot pixels (1 failed/1 passed, 102.12s), then one
final writer passed 2/2 in 84.80s, followed by two no-writer passes: 2/2 in
74.00s (`12:57` -> `12:58`) and 2/2 in 79.28s (`12:58` -> `12:59`). Snapshot
SHA-256 values are
`46b4448b90b4ee2bfed5332c82cedb9fe03dbccbf4589dcfc711aeb8107bd336`
(candidate/executable/authority-negative) and
`25424f2dec721a8c1454933023129a31d13e89413dc29ed7923171b8f27c50b8`
(incomplete no-hit). Both were visually inspected; the lane and fixed ports were
released.

### Governance, facades, debt, and expected reds

The ten DS10 roots are exact: five `rebind_pending/strangled` with successors
(`route-knowledge`, `feature-command-palette`, `feature-lex`,
`api-op-get-control-capabilities`, `api-op-search-data-catalog`) and five
`use_as_is/not_applicable` without successors (`api-op-get-data-index-stats`,
`api-op-get-lex-graph-stats`, `api-op-search-lex-graph`,
`api-op-get-lex-pipeline-status`, `api-op-trigger-lex-pipeline`). The live root
denominator is 261/261; the separate DS8 assignment denominator remains 217/217.
The surgical writer's final transaction completed in 151.15s under 240s,
uptime `13:12` -> `13:14`; DS10 register tests are 11/11 green in 82.94s.

The DS6 C13 whole-file census is 2 stale of 11: `RunDetailLayout.tsx` and the
shared visual spec. The global checker remains intentionally fail-fast on only
`c13_print_receipt_invalid:...RunDetailLayout.tsx` (120.32s under 240s,
`13:16` -> `13:18`); the exact owner test is red in 5.99s. Debt
`ds10-c13-print-receipt-reissue`, owner `team-design` / DS6 independent print
lane, owns reissue. DS10 does not rewrite another slice's receipt.

The original guardrail delta was 14 DS10-owned cross-root deep imports. Existing
facades routed two `ApiMeta` edges:

- `runtime.quality.capability_discovery -> core.contracts.runtime`;
- `runtime.http.services.control.capability_discovery -> core.contracts.runtime`.

The final guardrail run completed in 247s, uptime `13:21` -> `13:25`, and reports
exactly 12 deferred edges, owned by `team-polisyos` under
`ds10-capability-discovery-stable-facades`:

1. `runtime.http.openapi_contract -> core.contracts.capability_discovery`;
2. `runtime.http.routes.control -> core.contracts.capability_discovery`;
3. `runtime.http.services.control.capability_discovery -> core.contracts.capability_discovery`;
4. `runtime.http.services.control.run_lifecycle -> core.contracts.capability_discovery`;
5. the same source -> `core.contracts.search`;
6. `runtime.quality.capability_authority -> core.contracts.capability_discovery`;
7. `runtime.quality.capability_discovery -> core.contracts.capability_discovery`;
8. the same source -> `core.contracts.search`;
9. `runtime.quality.capability_index -> core.contracts.capability_discovery`;
10. `runtime.quality.capability_resolver -> core.contracts.capability_discovery`;
11. the same source -> `core.contracts.control`;
12. `runtime.quality.proving_ground.pre_adapter_grounding_inventory -> core.contracts.capability_discovery`.

The final debt census is 72/72 with 13 DS10 rows. The two owner cells that had
projected as `—` were corrected to exact `team-fabric` and `team-design`; DS15
and DS12 successor wording moved out of the owner cells. The writer completed
and wrote the ledger in 4s, then returned the expected composite exit 1 for ten
`register_supplies_missing_standing` plus one
`register_withholds_source_standing`. Report-only reproduced exactly those 11
informational findings in 2s, and the complete ledger test file is 32/32 green in
12s. The frontend metric remains the untouched DS8-labelled 217 denominator.

### Final targeted verification wave

| lane | final receipt |
| --- | --- |
| backend discovery/API/generic strangle | 30/30 green in 141s under 300s; uptime `13:31` -> `13:34` |
| amended free growth | 1/1 green in 237s under 300s; uptime `13:34` -> `13:38` |
| dashboard strict hook/panel/a11y/twin/palette/Lex | 6 files, 29/29 green in 9s; uptime `13:31` -> `13:31` |
| REVIEWER/EXPERT panel witness | initial duplicate-text assertion RED 2/4; final case asserts visible candidate clothing plus all typed negatives for both audiences: 4/4 green in 2s, Prettier/scoped ESLint green in 11s, uptime `13:50` -> `13:51` |
| mixed-status precedence permutation | 1/1 green in 63s; `index_stale` wins independently of provider insertion order while the complete sibling stays discoverable |
| TypeScript compilation | green in 166s under 300s; uptime `13:34` -> `13:37` |
| changed frontend formatting | Prettier green across 47 TS/TSX files; broad ESLint exceeded 300s and was killed, so it is a non-receipt; scoped DS10 lint is green |
| Python lint | Ruff diagnostics green on 33 non-architecture changed files; format check has the same two whole-file conflicts at slice base and current (`pre_adapter_grounding_inventory.py` and its test), so the completed format failure is recorded, not promoted to green |
| architecture | 11/11 DS10 register tests green; global C13 exact declared red; guardrails exact 12-edge declared red |
| debt | 72/72, exact 11 informational findings, 32/32 tests green |

The combined C01 command, C03 333.95s wave, C04 261s replay against 240s,
coordinate-broken Ruff wrapper, broad 300s ESLint kill, and the invalidated first
visual freeze remain non-receipts. None is cited as passing evidence.

### Closure-item and cluster hand-back index

The plan's implementation receipt index binds CC01-CC22. In particular, CC07's
mixed-status permutation and CC18's EXPERT audience now have direct behavioral
witnesses; CC15 binds the real owner path; CC20 binds 10/10 roots; CC22 is closed
only by the forthcoming C07 commit and attached-branch readback reported in the
final hand-back.

| cluster | commits / boundary | declared vs observed mechanism paths | running paths | rounds | attached readback |
| --- | --- | --- | ---: | ---: | --- |
| C00 | `a5755a584`, `d134aa5d5`, `fd69e66cb` | 0 / 0 | 0/50 | 0/15 | clean, hashes recorded above |
| C01 | `26b271655`, `481fe2de5`, `e77f99ec0`, `0d0e3c92c` | 5 / 5 | 5/50 | 2/15 | attached/read back |
| C02 | `d38860720`, `db4cb758a`, `5093c1951` | 5 / 5 | 10/50 | 5/15 | attached/read back |
| C03 | `1c1587059`, `18c667141`, `4a33f3eae` | 7 / 7 | 17/50 | 7/15 | attached/read back |
| C04 | `c279bbd14`, `290b5ef14`, `9d4fbc050` | 0 declared / 1 generator exception | 18/50 | 7/15 | attached/read back; failed upstream binding later corrected |
| C05 | `1d87637f8` | 13 / 13; reused C02 paths add zero unique | 31/50 | 10/15 | attached/read back |
| C06 | `b4e96e0eb` | 12 / 12; reused hook adds zero unique | 43/50 | 13/15 | attached/read back |
| C07 | `docs(atlas): close DS10 capability discovery` | 0 declared / 3 authorized narrowing exceptions | 46/50 | 14/15 | commit hash and post-commit branch hashes belong to the final hand-back |

The source tree is frozen, all 22 checkboxes are closed against the indexed
evidence, every open boundary has an owner and executable command, and no stop
condition fired.
