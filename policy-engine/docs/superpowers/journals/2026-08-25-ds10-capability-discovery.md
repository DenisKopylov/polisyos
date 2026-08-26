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
