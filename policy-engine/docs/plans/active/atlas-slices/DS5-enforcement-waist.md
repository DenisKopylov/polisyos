---
plan_id: atlas-ds5-enforcement-waist
title: "DS5 - Enforcement Waist: Lints, Audience Mapping, Cache Discipline, Flags"
type: slice-plan
status: blocked_before_implementation - generated schema and mirrored HTTP test fence authorization required
created: 2026-08-01
revised: 2026-08-01
last_verified: 2026-08-01
stability: measured_plan_stop_gate
slice: DS5
baseline_commit: 5e648230204d5972d7d159aaffd50cb427ba3e81
execution_base_commit: 5e648230204d5972d7d159aaffd50cb427ba3e81
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
identity_boundary: ../../../system-design-decisions/policyos-identity-and-custody-boundary.md
ds1_plan: ./DS1-live-application-audit.md
ds1_report: ../../../reference/frontend/atlas-live-application-audit.md
ds4_plan: ./DS4-status-grammar-rebinding.md
ds4_journal: ./DS4-status-grammar-rebinding-journal.md
ds4_closure: ./DS4-status-grammar-rebinding-closure.md
ds20_closure: ./DS20-server-authz-enforcement-closure.md
disposition_register: ../../../../architecture/atlas_surfaces/frontend-disposition-register.json
status_inventory: ../../../../architecture/atlas_surfaces/status-retirement-inventory.json
waist_debt_register: ../../../../architecture/atlas_surfaces/ds4-waist-debt-register.json
baseline_debt_manifest: ../../../../architecture/atlas_surfaces/frontend-baseline-debt-manifest.json
readiness_ledger: ../../../../architecture/atlas_surfaces/live-application-readiness-ledger.json
journal: ./DS5-enforcement-waist-journal.md
closure: ./DS5-enforcement-waist-closure.md
audiences: [PUBLIC, REVIEWER, EXPERT, MACHINE]
owner: team-frontend
architecture_owner: team-architecture
depends_on:
  - ./DS1-live-application-audit.md
  - ./DS4-status-grammar-rebinding.md
  - ./DS20-server-authz-enforcement-closure.md
  - ../../../reference/policy-design-case-failure-patterns.md
---

# DS5 - Enforcement Waist: Lints, Audience Mapping, Cache Discipline, Flags

**Goal:** Turn Atlas laws 8, 9, 10, 12 and the audience half of law 11 into
mechanical, fail-closed enforcement. DS5 makes DS4's zero-violation state
durable; it does not create a second authority source in the browser.

**Architecture:** The enforcement flow is
`canonical owner -> strict runtime HTTP DTO -> OpenAPI -> generated client ->`
`one presentation adapter -> real consumer -> behavioral scanner/negative`.
The authorization flow is `server-owned RuntimePermission -> one audience`
`requirement mapping -> live route denial`; UI visibility is presentation only.
The cache flow is `source as_of + fetch observation + tenant/user + producer-`
`carried rule/epoch when present`
`-> explicit live/cached/stale/offline posture -> visible TimeSemanticsLabel`.
No timestamp heuristic, cached presence, client average, flag, or fixture identity
can manufacture authority.

**Tech stack:** Python 3.14, Pydantic 2, FastAPI/OpenAPI, generated TypeScript,
React 19, TanStack Query, TypeScript 5 compiler API, pnpm 10.33.2, Vite,
Vitest, Playwright, ESLint, dependency-cruiser, JSON Schema, and repository
architecture guardrails.

## Binding fence and no-merge posture

- Worktree: `.worktrees/atlas-ds5`; branch:
  `codex/atlas-ds5-enforcement-waist`; exact current-`main` base and execution
  base: `5e648230204d5972d7d159aaffd50cb427ba3e81`.
- Writable: `apps/runtime-dashboard/**`, `packages/atlas-ui/**`, generated output
  only in `packages/runtime-api-client/**`, `architecture/atlas_surfaces/**`,
  DS5 plan/journal/closure files, `docs/reference/frontend/**`, and the narrow
  runtime HTTP/schema owner surface under `src/polisyos/runtime/http/**`.
- Read-only: `design/atlas-v15/**`, the frozen
  `apps/runtime-dashboard/src/shared/i18n/locales/ru.json`, CI configuration,
  and every backend path outside `src/polisyos/runtime/http/**`. In particular,
  DS5 never edits `foundry`, `fabric`, `scientist`, or `data_forge`.
- The checked-in `schemas/runtime_api_v1.openapi.json` is the deterministic
  snapshot required by the explicit client-regeneration instruction, but the
  writable list omits that path while admitting only the HTTP/schema owner code
  under `src/polisyos/runtime/http/**`. The runtime contract cannot be green
  without refreshing the snapshot. The same literal fence omits the mirrored
  `tests/unit/runtime/http/**` files required by the mandated server-denial and
  generated-contract negatives; placing tests under production source would
  violate repository test layout. This plan therefore stops before C01 until
  the architect explicitly admits the generated snapshot and exactly these
  five mirrored test files:
  `test_authorization_audience_denials.py`,
  `test_runtime_permission_vocabulary.py`,
  `test_governed_projection_api.py`,
  `test_governed_projection_service.py`, and
  `test_runtime_api_contract_hardening.py`. If admitted, C06/C07 may change the
  snapshot only through the canonical exporter and may edit those tests only
  for the DS5 HTTP/schema contract, in the same commits as HTTP models,
  generated clients and governed re-anchors. Any hand-authored/other
  `schemas/**` diff or any other backend-test path remains a STOP.
- No merge, push, rebase onto `main`, CI edit, baseline suppression, skip,
  quarantine, timeout increase, or tolerance widening. Closure is an
  architect-review handoff.
- One scoped commit per cluster after red-first evidence and independent review.
  No partial family, unpaired register transition, or uncommitted tail crosses
  a cluster boundary.

### Authority-order conflicts resolved openly

1. The master Revision 3.6 row calls DS5 the sole unblocked Phase-B lane while
   the same row also says DS6 is unblocked. This is editorial scheduling drift,
   not a DS5 entry-gate failure; DS4 and DS20 inputs are present.
2. The historical DS4 plan still describes a partial re-cut, but the earlier
   governing master closure note and the DS4 closure report record DS4 closed
   and merged. DS5 consumes the realized 27 package / 41 rebind / 18 use-as-is /
   3 retire split, not the superseded pre-ruling split.
3. The Phase-A synthesis says D4 was pending. Revision 3.6 and the ratification
   at `7b6933770` are later and controlling: `uk` primary, `en` baseline and
   fallback, `ru` `legacy_continuity_frozen`—not active, not deleted.
4. Six narrow cache rows in the older disposition seed name DS14, DS8, or DS9
   as owner, while the higher master and this mission assign tenant/user/expiry
   cache discipline to DS5. DS5 owns only that cross-cutting storage-discipline
   sublayer and its live migrations; the domain capabilities and their root
   rows remain with the named slices. C14-C17 attach isolation evidence without
   falsely claiming those domain features rebound. The stale review-attention
   row receives DS4 deletion evidence and a fresh census, not a resurrected
   implementation.
5. The prompt inherited wording says “one of 9 typed labels”; the governing
   register defines ten usable capability labels. This plan uses the labels by
   name and makes no numerical claim.
6. Law 11 is the broader human-accountability law. DS5 mechanizes only its
   audience/permission enforcement half; it does not claim the whole law closed.

## DS5-C00: measured entry contract and stop gate

The slice may implement only after this plan exists with measured cluster
denominators and the generated-snapshot fence conflict above is adjudicated.
C00 is documentation-only and lands as its own commit; the current authorized
stopping point is that clean commit.

The installed-workspace precondition is satisfied: `corepack pnpm install
--frozen-lockfile` completed with pnpm 10.33.2 and the dashboard's
`node_modules/@polisyos/{atlas-ui,runtime-api-client}` entries resolve to the
workspace packages. Status-scanner reds observed without those links are not
evidence and must be discarded.

Three conditions still stop the slice at a clean, committed boundary:

- a canonical vocabulary symbol or governed field changes while C06 only
  expects uniform generated offset/hash drift;
- a new owner gap requires code outside `runtime/http` or attempts to close an
  opaque terminal/evidence extension;
- a boundary remeasurement exceeds the recorded cap. The response is a
  continuously numbered re-cut, never a larger cluster or weaker gate.

### Measured baseline receipt

All source denominators below were measured at
`5e648230204d5972d7d159aaffd50cb427ba3e81` after the frozen install and before
the first repository edit.

| Gate | Command | Receipt |
| --- | --- | --- |
| clean base | `git status --short`; `git rev-parse HEAD`; `git branch --show-current` | PASS; clean; exact SHA above; expected branch |
| install/link proof | `corepack pnpm install --frozen-lockfile`; `readlink apps/runtime-dashboard/node_modules/@polisyos/{atlas-ui,runtime-api-client}` | PASS; two workspace links resolve |
| dashboard typecheck | `cd apps/runtime-dashboard && corepack pnpm run typecheck` | PASS |
| dashboard production build | `cd apps/runtime-dashboard && corepack pnpm run build` | PASS; 3,885 modules; PWA precache 108 entries |
| dashboard lint | `cd apps/runtime-dashboard && corepack pnpm run lint` | PASS; parseable exit 0; no diagnostics |
| dashboard architecture | `cd apps/runtime-dashboard && corepack pnpm run check:architecture` | PASS; custom engine 0; dependency-cruiser 0 across 1,019 modules / 4,150 dependencies |
| dashboard components | `cd apps/runtime-dashboard && corepack pnpm run test:components -- --reporter=default --maxWorkers=1` | BASELINE RED; 311/312 files and 890/893 tests pass in 362.99 s; only the three DS6-owned `panels.agentPipeline.overBudget` en/uk/ru parity identities fail |
| prior timeout isolation | `cd apps/runtime-dashboard && corepack pnpm exec vitest run src/shared/ui/compounds/decisionGradePresentation.test.ts src/features/evidence/components/DataIntelligencePanel.test.tsx src/features/runs/components/readinessScientificContainment.test.ts --maxWorkers=1 --reporter=default` | PASS; 3/3 files, 12/12 tests in 19.76 s; the earlier resource-contention timeouts are not baseline identities |
| Atlas UI | `cd packages/atlas-ui && corepack pnpm run typecheck && corepack pnpm run lint && corepack pnpm run check:architecture && corepack pnpm run test` | PASS; architecture 36 source files; 18/18 files and 86/86 tests |
| disposition checker | `python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --verify-baseline-source-bytes --corruption-probes` | PASS; 261 roots, 13 supplemental findings, 23 seeded negatives, 8 censuses; corruption probes PASS |
| status checker | `python3 architecture/atlas_surfaces/check_status_retirement_inventory.py --check --corruption-probes` | PASS; 47 DS1 rows, 15 current authored statuses, 55 exemptions, 0 retirement debt, 3 waist debts; corruption probes PASS |
| governance unittest battery | `python3 -m unittest architecture.atlas_surfaces.test_frontend_baseline_debt_manifest architecture.atlas_surfaces.test_frontend_disposition_register architecture.atlas_surfaces.test_status_retirement_inventory` | PASS; 98/98 in 490.049 s |
| focused auth/audience HTTP | `uv run --extra runtime --extra ml pytest tests/unit/runtime/http/test_authorization_audience_denials.py tests/unit/runtime/http/test_runtime_permission_vocabulary.py tests/unit/runtime/http/test_auth_api.py -q` | PASS; 13/13 |

Two intentionally inherited closure reds are not C00 blockers: the three DS6
locale-parity failures and the DS8 `run detail A4 print` visual identity. The
frozen parity test, frozen `ru` catalog, and print expectation remain
byte-unmodified. Any new identity is red.

### Measured estate and cluster-sizing census

| Surface | Exact current denominator | Consequence |
| --- | ---: | --- |
| dashboard source | 942 TS/TSX/JS/JSX files | scanners derive the source set; no hand list |
| Atlas UI source | 36 TS/TSX/JS/JSX files | status and architecture recurrence include the package sibling |
| runtime HTTP | 87 Python files | only the named C06/C07 files are writable |
| DS4 status estate | 47 rows; 15 current authored; 0 retirement debt | C01 extends the existing semantic scanner; no second grep lint |
| architecture | 1,019 modules / 4,150 dependencies / 0 violations | C02 injects real violations into both engines |
| DS4 waist debts | exactly 3 | one C06 regeneration and three singular swap modules |
| generated governed receipts | 15 anchored rows / 10 distinct export symbols / 13 fields | C06 requires symbol count 1, unchanged fields, uniform offset, two refreshed hashes |
| CGF owner disposition | 70 owner rows; 3 values (`USE_AS_IS`, `REWORK_TO_FIT`, `DELETE`); 0 production consumers of its current adapter | keep owner values closed but presentation neutral |
| decision grade | 4 owner values; adapter has 10 call sites in 8 production consumer files | swap only the adapter, not the consumers |
| cache-age adapter | one adapter; one `TimeSemanticsLabel`; 2 live render sites | source freshness remains orthogonal |
| raw `fetch()` | historical DS1 9/5; live 5 calls / 3 production files | DS19 deleted four collaboration calls; preserve both receipts |
| all raw transport constructors | 7 calls / 5 production files | adds one `EventSource` and one `WebSocket` |
| flags | 12 keys; 8 consumed; 4 `consumer_missing` | wire 3, retire collaboration; auth pseudo-flag is separate |
| permissions | 33/33 unique server/OpenAPI values | dashboard local list has 15: 12 overlap, 3 unsupported collaboration strings, 21 omitted |
| governed projection audiences | 13 definitions: 5 EXPERT, 8 MACHINE, 0 PUBLIC, 0 REVIEWER | C07 enforces all four classes without relabeling producer data |
| N010 client exposure | 11 default-allow expressions across 6 production consumers | no fixture/previous-user authority while loading or failed |
| capability discovery | 14 hardcoded fallback feature records | 43 fixed-chrome surfaces and 19 nonempty capability gates are benign controls |
| locales | 2 ratified active locales but 3 currently exposed; 2,449 leaves in each en/uk/ru catalog | C05 removes active `ru` exposure without touching catalogs/parity |
| query cache | 66 `useQuery`/`queryOptions` syntax sites in 40 production files; 42 `queryFn` definitions / 39 files | only 1 producer carries owner `as_of`; C11 proves that consumer, C12 registers/enforces the remaining policy without inventing source time |
| IndexedDB | 1 DB / 2 stores; queue has exactly 2 kinds | promotion approve/reject barred; composer drafts enveloped |
| authority-like local state | historical 6 units; current 4 live | WhatIf deleted by DS19; review-attention source absent; lint prevents resurrection; C14-C17 migrate the live units plus composer |
| DS5 disposition ownership | 17 current roots | readiness ledger retains 21 historical DS5 rows; closure distinguishes them |

The historical 9/5 fetch and six-store denominators remain provenance facts,
not current implementation counts. DS5 does not relabel the 7/5 transport or
4/6 live-store measurements merely to match old prose.

### Reproducible census command ledger

The plan does not infer its denominators from prose. These are the exact
commands used for the source and carrier counts; the behavioral checker
commands and their receipts are in the baseline table above.

| Denominator | Reproducible command |
| --- | --- |
| 942 dashboard / 36 Atlas UI / 87 runtime HTTP source files | `rg --files apps/runtime-dashboard/src \| rg '\\.[jt]sx?$' \| wc -l`; repeat for `packages/atlas-ui/src`; `rg --files src/polisyos/runtime/http \| rg '\\.py$' \| wc -l` |
| 2,739-line existing semantic scanner | `wc -l architecture/atlas_surfaces/status_retirement_scan.mjs` |
| 15 generated anchors / 10 symbols / 13 field-bearing anchors | `jq '[.. \| objects \| select(has("export_symbol"))] \| {rows:length, symbols:([.[].export_symbol]\|unique\|length), fields:([.[]\|select(has("field"))]\|length)}' architecture/atlas_surfaces/status-retirement-inventory.json` |
| three waist debts and singular swap paths | `jq '.entries \| {count:length, swaps:[.[].swap_module], symbols:[.[].generated_client_anchor.symbol]}' architecture/atlas_surfaces/ds4-waist-debt-register.json` |
| 70 CGF rows / three values / zero adapter consumers | `jq '.source_reconciliation \| {total_owner_entries, disposition_counts}' architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json`; `rg -n 'presentCgfDisposition\|cgfDispositionPresentation' apps/runtime-dashboard/src --glob '!**/*.test.*' --glob '!**/*.stories.*'` returns only its declaration module |
| four decision grades / 10 calls / eight consumer files | literal `authority_and_store_census` command below; recorded owner values and source-derived calls/files |
| one cache-age adapter / one label / two renders | `rg -n 'TimeSemanticsLabel\|cacheAgePresentation\|cacheAgeLabel' apps/runtime-dashboard/src --glob '!**/*.test.*' --glob '!**/*.stories.*'` |
| 5 `fetch` / 3 files; 7 raw transports / 5 files | `rg -n --glob '!**/*.test.*' --glob '!**/*.stories.*' '\\bfetch\\s*\\(' apps/runtime-dashboard/src`; repeat with `\\b(fetch\\s*\\(\|new EventSource\\s*\\(\|new WebSocket\\s*\\()'` and use `rg -l` for file counts |
| 12 flag keys / 8 referenced outside owner / four named missing consumers | literal `flag_consumer_census` command and per-key output below |
| 33 server and generated permission values | literal `authority_and_store_census` command below; recorded `server=33`, `generated=33`, `equal=True` |
| 13 projection definitions / 5 EXPERT / 8 MACHINE | `sed -n '/^_DEFINITIONS:/,/^_DEFINITION_BY_ID/p' src/polisyos/runtime/http/services/governed_projections.py \| rg -c '_ProjectionDefinition\\('`; repeat the bounded scan with `rg -c 'AudienceClass.EXPERT'` and `rg -c 'AudienceClass.MACHINE'` |
| 11 N010 expressions / 6 production consumers | literal `authority_and_store_census` command below; its per-path output is 1/2/1/1/2/4 |
| 14 fallback capability records | `sed -n '/features: \\[/,/^  \\],/p' apps/runtime-dashboard/src/shared/lib/capabilities.ts \| rg -c '^      key:'`; `rg -n 'FALLBACK_CAPABILITY_MANIFEST\|capabilitiesQuery.isLoading'` locates the two production bypass consumers |
| 43 fixed surfaces / 19 nonempty capability requirements | literal TypeScript-AST `surface_census` command below; recorded components are workspace 6/4, run 8/4, panel 29/11 |
| 2 ratified active of 3 currently exposed locales; 2,449 leaves each | `jq '[paths(scalars)] \| length' apps/runtime-dashboard/src/shared/i18n/locales/{en,uk,ru}.json`; `rg -n 'SUPPORTED_LOCALES\|DEFAULT_LOCALE' apps/runtime-dashboard/src/shared/i18n/locale.ts` records the current `en/uk/ru` + `en` default drift C05 must close |
| 66 query syntax / 40 files; 42 producers / 39 files | `rg -n --glob '!**/*.test.*' --glob '!**/*.stories.*' --glob '!**/types.ts' '\\b(useQuery\|queryOptions)(<[^>]+>)?\\s*\\(' apps/runtime-dashboard/src`; repeat with `rg -l`; repeat both for `\\bqueryFn\\s*:` |
| 43 query-key constructors | `rg -c '^  [A-Za-z][A-Za-z0-9_]*:' apps/runtime-dashboard/src/api/queryKeys.ts`; C12 re-derives it from the real exported owner rather than pinning this number |
| 1 IndexedDB / 2 stores / 2 queue kinds | `rg -n 'openDB\|createObjectStore\|OfflineQueueItemKind' apps/runtime-dashboard/src/app/offline/{db.ts,offlineQueueRepository.ts}` |
| 6 historical / 4 live authority-store units / 8 living physical families | literal `authority_and_store_census` and `physical_store_census` commands below; both names and existence are recorded |
| 261 roots / 17 current DS5 roots / 21 historical readiness rows | `jq '[.. \| objects \| select(.owner_slice? == "DS5")] \| length' architecture/atlas_surfaces/frontend-disposition-register.json`; `jq '[.entries[] \| select(.owning_slice == "DS5")] \| length' architecture/atlas_surfaces/live-application-readiness-ledger.json`; the disposition checker supplies the 261-root denominator |

`authority_and_store_census` was run literally from product root:

```bash
python3 - <<'PY'
from pathlib import Path
import re

owner = Path("src/polisyos/pdc/_impl/layer2_readiness.py").read_text()
grade_block = re.search(r"DecisionGrade = Literal\[(.*?)\n\]", owner, re.S)
assert grade_block is not None
grade_values = re.findall(r'"([^"]+)"', grade_block.group(1))
grade_calls: dict[str, int] = {}
dashboard = Path("apps/runtime-dashboard/src")
for path in [*dashboard.rglob("*.ts"), *dashboard.rglob("*.tsx")]:
    if ".test." in path.name or ".stories." in path.name or path.name == "decisionGradePresentation.ts":
        continue
    count = len(re.findall(r"presentDecisionGradeLabel\s*\(", path.read_text()))
    if count:
        grade_calls[str(path)] = count
print("decision_grade", {"values": grade_values, "calls": sum(grade_calls.values()), "files": len(grade_calls)})

from polisyos.runtime.http.permissions import RuntimePermission
server_permissions = {permission.value for permission in RuntimePermission}
generated_types = Path("packages/runtime-api-client/types.ts").read_text()
permission_match = re.search(r'RuntimePermission: ([^;]+);', generated_types)
assert permission_match is not None
generated_permissions = set(re.findall(r'"([^"]+)"', permission_match.group(1)))
print("permissions", {"server": len(server_permissions), "generated": len(generated_permissions), "equal": server_permissions == generated_permissions})

n010_paths = [
    Path("apps/runtime-dashboard/src/app/routes/WorkspaceBoundary.tsx"),
    Path("apps/runtime-dashboard/src/app/layout/Sidebar.tsx"),
    Path("apps/runtime-dashboard/src/app/layout/Header.tsx"),
    Path("apps/runtime-dashboard/src/app/providers/InterfaceModeProvider.tsx"),
    Path("apps/runtime-dashboard/src/features/commandPalette/CommandPalette.tsx"),
    Path("apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx"),
]
n010_patterns = (
    re.compile(r"authz\s*\?\s*authz\.(?:can|isWorkspaceAllowed)\([^)]*\)\s*:\s*true"),
    re.compile(r"authz\?\.can\([^)]*\)\s*\?\?\s*true"),
)
n010_counts = {
    str(path): sum(len(pattern.findall(path.read_text())) for pattern in n010_patterns)
    for path in n010_paths
}
print("n010", {"counts": n010_counts, "expressions": sum(n010_counts.values()), "files": sum(value > 0 for value in n010_counts.values())})

n015_line = Path("docs/reference/frontend/atlas-live-application-audit.md").read_text().splitlines()[826]
n015_payload = n015_line.split("Persist ", 1)[1].split("; switch", 1)[0].replace(", and ", ", ")
historical_names = [name.strip() for name in n015_payload.split(", ")]
historical_paths = {
    "clerk": "apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts",
    "whatif": "apps/runtime-dashboard/src/features/whatif/state/useWhatIfStore.ts",
    "causal": "apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx",
    "dispute": "apps/runtime-dashboard/src/features/runs/domain/disputes.ts",
    "review_attention": "apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts",
    "operator": "apps/runtime-dashboard/src/features/runs/domain/operatorCraft.ts",
}
living_names = sorted(name for name, path in historical_paths.items() if Path(path).is_file())
print("stores", {"historical": len(historical_names), "historical_names": historical_names, "living": len(living_names), "living_names": living_names})
PY
```

Recorded output: decision grades
`unsupported/descriptive_only/advisory_admissible/decision_admissible`, 10
calls, 8 files; permissions `33/33/equal=True`; N010 path counts
`1/2/1/1/2/4`, total 11/6; stores 6 historical
(`Clerk`, WhatIf, causal, dispute, review attention, operator craft), 4 living
(`clerk`, `causal`, `dispute`, `operator`).

`flag_consumer_census` was run literally under `zsh`:

```bash
sed -n '/FEATURE_FLAG_KEYS = \[/,/\] as const/p' apps/runtime-dashboard/src/shared/lib/featureFlags.ts | sed -n 's/^  "\([^"]*\)",$/\1/p' | while IFS= read -r ds5_flag_key; do
  ds5_flag_files=$(rg -l --glob '!**/*.test.*' --glob '!**/*.stories.*' --glob '!**/featureFlags.ts' --glob '!**/test/**' "$ds5_flag_key" apps/runtime-dashboard/src | wc -l | tr -d ' ')
  print -r -- "$ds5_flag_key $ds5_flag_files"
done
```

Recorded output: `enableAtlasV2=4`, `enableClerkMode=1`, and each of dark,
Lex, narrative, platform, runs and composer `=1`; causal, collaboration,
command palette and WhatIf `=0`—12 keys, 8 consumers, 4 missing.

`surface_census` was run literally from `apps/runtime-dashboard` against the
installed TypeScript compiler:

```bash
node - <<'NODE'
const fs = require("node:fs");
const ts = require("typescript");

function source(path) {
  return ts.createSourceFile(path, fs.readFileSync(path, "utf8"), ts.ScriptTarget.Latest, true);
}
function unwrap(node) {
  while (ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isParenthesizedExpression(node)) node = node.expression;
  return node;
}
function variable(sf, name) {
  let found;
  function visit(node) {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === name) found = unwrap(node.initializer);
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return found;
}
function requiredCount(objects) {
  return objects.filter((object) => {
    const property = object.properties.find((item) => ts.isPropertyAssignment(item) && item.name.getText() === "requiredCapabilities");
    return property && ts.isArrayLiteralExpression(unwrap(property.initializer)) && unwrap(property.initializer).elements.length > 0;
  }).length;
}

const registry = source("src/app/surfaces/surfaceRegistry.ts");
const workspaces = source("src/app/workspaces.ts");
const run = unwrap(variable(registry, "RUN_DETAIL_SURFACES")).elements.map(unwrap);
const panels = unwrap(variable(registry, "PANEL_SURFACES")).elements.map(unwrap);
const workspaceObjects = unwrap(variable(workspaces, "WORKSPACES")).properties
  .filter(ts.isPropertyAssignment)
  .map((property) => unwrap(property.initializer));
const counts = {
  workspace: [workspaceObjects.length, requiredCount(workspaceObjects)],
  run: [run.length, requiredCount(run)],
  panel: [panels.length, requiredCount(panels)],
};
console.log(JSON.stringify({
  components: counts,
  surfaces: Object.values(counts).reduce((sum, value) => sum + value[0], 0),
  gated: Object.values(counts).reduce((sum, value) => sum + value[1], 0),
}));
NODE
```

Recorded output:
`{"components":{"workspace":[6,4],"run":[8,4],"panel":[29,11]},"surfaces":43,"gated":19}`.

`physical_store_census` was run literally from product root:

```bash
rg -n 'name: "polisyos-clerk-chat"|^export const COMPOSER_DRAFTS_STORE|^const (THRESHOLD_STORAGE_KEY|ANNOTATION_STORAGE_PREFIX|EVIDENCE_WALLET_STORAGE_KEY|ONBOARDING_STORAGE_PREFIX)|^export function disputeStorageKey|^function causalDraftStorageKey' apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx apps/runtime-dashboard/src/features/runs/domain/disputes.ts apps/runtime-dashboard/src/features/runs/domain/operatorCraft.ts apps/runtime-dashboard/src/app/offline/db.ts | wc -l
```

Recorded output: `8` living authority-like physical families: Clerk, composer,
causal, dispute, and four operator-craft keys.

The surface and store commands are bounded structural censuses, not future lint
implementations. C01/C12/C17 must replace those entry receipts with generic
owner-derived checks before claiming recurrence protection.

## Pattern pass and capability truth

Relevant repair rows are P01 (contract-only capability), P03 (hidden internal
richness), P04 (status lattice), P05 (authority boundary leak), P06 (shim
drift), P07/P08 (replay/time roles), P09 (warning lifecycle), P10 (semantic
adequacy), P13 (governance gravity), P15 (speculation laundering), P25/P26
(audience/authorization), P27/P28 (owner bypass/unstrangled legacy), P29
(marker-only proof), and P31-P34 (instance patching, trust by form, probe
teaching, dishonest exclusion).

The target correct pattern is:

```text
owner contract + producer + persisted artifact/event + generated bridge
  -> one consumer/presentation adapter
  -> behavioral verifier + corruption witness + benign counterexample
  -> API/dashboard/audit surface or explicit surface_out_of_scope
```

At entry, each waist row is `bridge_missing + surface_missing`; the requested
lint battery is `verification_missing`; audience mapping is `bridge_missing`;
N010 is `consumer_missing`; cache isolation is `contract_only` or
`verification_missing`; the four flag rows are `consumer_missing`; the review
WebSocket authentication remainder stays `bridge_missing` and is not closed by
a transport exemption. No cluster may upgrade a label unless producer, bridge,
consumer, negative, and surface evidence actually exist.

The enforcement battery is verification infrastructure, never authority. A
scanner cannot make a status admissible, a flag cannot grant permission, and a
presentation adapter cannot turn a TypeScript union into runtime owner proof.

## Universal cluster protocol

Every implementation cluster follows this order:

1. Record clean status, HEAD, exact preflight file set, current register rows,
   and inherited baseline identities.
2. Add the named negative first. Run it and journal the exact expected failure
   reason; a timeout or lost output is a non-receipt.
3. Make the smallest wire/extend/consolidate change. Never hand-edit generated
   output or copy a canonical vocabulary.
4. Move every touched register row with successor and consumer evidence, or
   keep it pending with a typed capability label and executable closure signal.
5. Run affected tests, typecheck, production build, scoped lint, both
   architecture engines where relevant, governed checkers, and corruption
   probes. False positives are defects and each lint carries a benign control.
6. At wave boundaries run full gates and compare inherited identities by hash;
   removals shrink debt, additions fail.
7. Request independent review. Important/Critical findings are repaired
   red-first and the cluster commit is amended before continuing.
8. Record exact denominators in the journal and leave one clean scoped commit.

A cluster measured above its cap stops at the preceding clean commit and is
re-cut with the next continuous number. No cap is enlarged after entry.

### Register transition map

| Authority row(s) | Boundary | Planned transition / proof |
| --- | --- | --- |
| 47 status rows + `status-retirement-inventory` | C01 | preserve 15/0 estate; add package-sibling unauthorized-definition semantic proof; no invented status |
| architecture baseline/recurrence receipts | C02 | zero remains zero; real custom and dependency-cruiser violations fail even with marker bytes intact |
| `raw-fetch-auth-refresh`, `raw-fetch-auth-initial`, `raw-fetch-auth-replay` | C03 | bounded `use_as_is` inside the typed auth transport owner plus symbol-bound exemption and corrupt sibling negative |
| `raw-fetch-flag-manifest` | C03 | bounded `use_as_is` inside the strict registry adapter; C18 supplies the consumer semantics |
| `transport-ws-review` | C03 | remains `bridge_missing`; typed constructor classification does not close N018 authentication/degradation |
| hardcoded capability fallback / `cache-query-memory` | C04 then C11-C12 | fallback removed in C04; root transitions only after cacheable/never-cache/operational/debt classes are derived and enforced |
| `route-app-layout::ru-ui-catalog` | C05 | stays `frozen_legacy_continuity`; active exposure negative proves it is not a product locale |
| three `ds4-waist-debt-register` rows | C06 | close only after runtime model, generated union, singular adapter, consumer, corruption and novel-value proof |
| audience enforcement supplemental/readiness evidence | C07 | four-class deny matrix over all 33 enum-owned permission values; no client substitute |
| `route-login`, `feature-auth`, `api-op-get-auth-me` | C08-C09 | core identity then six downstream surfaces rebound to verified live identity or explicit unknown; loading/error/401/cross-tenant remain fail-closed |
| composed/recomputed status verification | C10 | scanner proof only; no producer/status row is promoted by lint |
| `cache-query-memory` | C12 | rebound only for the governed classifier/consumer; 41 missing-owner producers are never cached at authority sinks or remain typed debt, never timestamp-inferred |
| `offline-queue-promotion-decision`, `cache-service-worker-static` | C13 | promotion row retired/strangled from the queue; SW remains use-as-is with behavioral no-API/authority-cache proof |
| `cache-local-storage-state`, `offline-draft-composer`; six named cache units | C14-C17 | composer + 4 live historic units enveloped; WhatIf deletion preserved; review-attention gets a fresh deletion census; domain feature ownership not claimed |
| four flag disposition rows | C18-C19 | strict registry first; causal/palette/what-if rebound to real whole-surface gates; collaboration retired and absent |
| 21 historical DS5 readiness rows vs 17 live DS5 roots | C20 | update only supported chain fields; deleted/handoff rows stay honest; no denominator collapse |

### Wave boundaries

- **W0 — C00:** plan, install/link proof, measured baseline, clean plan commit.
- **W1 — C01-C05:** status, architecture, transport, capability, and semantic-ID
  enforcement. Full dashboard/Atlas gates plus governed corruption probes.
- **W2 — C06-C10:** generated waist, audience denial, N010, and composition.
  Full runtime contract, focused HTTP, generated-client, dashboard, and scanner
  gates.
- **W3 — C11-C17:** query cache, offline action, and four bounded local-state
  families.
  Full dashboard suite, browser cache/offline tests, architecture, and zero-new
  baseline comparison.
- **W4 — C18-C20:** flags, ledgers, final receipts, closure and fence proof.
  Full closeout battery including Storybook/a11y/visual, with only the exact
  inherited DS6/DS8 identities allowed.

## Pre-sized execution clusters

### DS5-C01 — shared semantic engine and unauthorized-status-owner lint

**Measured set:** 7 files; cap 9:
`status_retirement_scan.mjs`, its status checker/test/inventory, one new shared
DS5 enforcement checker/test, and dashboard `package.json`. The 2,739-line
scanner already uses the TypeScript Program/TypeChecker and sink-flow analysis;
C01 extends that one engine rather than creating transport/copy/composition
siblings. The existing status checker keeps owning DS4 receipts; the DS5
checker consumes additive typed findings.

**Red first:** `test_package_namespace_alias_later_assignment_jsx_spread_revival_fails`.
The corruption declares a UI-local authority union in `@polisyos/atlas-ui`,
passes it through namespace import, wrapper, object property, array carrier,
later assignment, coercion, and JSX spread into a real authority sink. Marker
bytes stay present. A responsive interaction-state union is the benign control.

**Acceptance:** `isDefinitionSource` explicitly derives both dashboard and
`packages/atlas-ui/src/**` production sources and the resulting live package
denominator is journaled before commit. Sources are narrowed by actual generated
declaration provenance and load-bearing semantic fields—never wildcarded over
all projection values (the wildcard preflight produced 52 false sinks in 30
files). Every revival path fails at declaration owner and sink; generated
indexed owners, open terminal/evidence values, BadgeTone, responsive layout and
numeric width remain benign. The 47/15/0 estate is unchanged, corruption probes
pass, and `lint:enforcement` executes the real checker.

**Expected commit:** `DS5-C01 enforce canonical status ownership`.

### DS5-C02 — architecture recurrence in both engines

**Measured set:** 5 files; cap 7: dashboard custom architecture script and
dependency-cruiser config, Atlas UI architecture script, and the two existing
Atlas governance checker/test surfaces needed to execute corruption probes.
The inherited DS4 “both engines” claim means the dashboard custom checker plus
dependency-cruiser; Atlas UI's checker is an additional package sibling, not a
third origin of the 36->0 denominator.

**Red first:** `test_real_illegal_edges_fail_custom_and_dependency_engines`.
Inject `shared -> app/api` and `app-state -> provider` edges for the custom
engine, and a forbidden edge plus a cycle for dependency-cruiser; execute both
real commands. A package boundary injection exercises the sibling checker.
Removing the property while retaining rule/marker strings must go green. A
public barrel, shared->shared import, numeric error-budget width and three-way
responsive layout are benign controls.

**Acceptance:** the DS4 36->0 class is executable in both engines, future source
files are discovered, and `lint:enforcement` cannot remain green if either
engine is bypassed.

**Expected commit:** `DS5-C02 make architecture zero recurrent`.

### DS5-C03 — symbol-bound authority-transport lint

**Measured set:** exactly 11 files; cap 12: the shared C01
scanner/checker/test, one
canonical TypeScript `defineRawTransportRegistry`/purpose factory, the five
production owner files, dashboard package wiring, and the frontend disposition
register. Current targets are 7 constructors / 5 production files: auth 3,
flags 1, telemetry 1, SSE 1, WebSocket 1. The production owners are part of the
migration denominator, not hidden behind the scanner count.

**Red first:** `test_alias_namespace_wrapper_property_later_assignment_transport_escape_fails`.
The exemption must be an actual symbol reference owned by the real factory,
resolve to a declaration location and closed purpose (`auth`, `flag_exposure`,
`telemetry`, `governed_channel`), and match primitive to purpose. File/path/name
JSON allowlists, fake same-name factories and synthetic generated lookalikes
fail. Local injected functions named `fetch` and generated-client `fetchImpl`
are benign controls.

**Acceptance:** novel handwritten authority transport fails at a real sink;
all seven live calls resolve to typed owners; historical deleted collaboration
calls are not grandfathered; telemetry remains DS12-limited; review WS remains
N018 `bridge_missing`.

**Expected commit:** `DS5-C03 type raw authority transports`.

### DS5-C04 — capability discovery, not fixed chrome

**Measured set:** exactly 12 files; cap 12:
`shared/lib/capabilities.ts` + test, `api/hooks/useCapabilities.ts`,
`api/hooks/controlQueries.test.tsx`, `runDetailSurfaces.test.tsx`, the shared
C01 scanner/checker test, dashboard `package.json`, and
`CommandPalette.tsx` + test, plus the frontend disposition register. The
violation is 14 fallback feature records in two production consumers;
CommandPalette currently treats capability loading as allow. The 43 fixed
surfaces and 19 capability gates are benign constitutionally allowed chrome.

**Red first:** `test_hardcoded_open_ended_capability_carriers_reach_menu_sink`.
Cover authored values assignable to the real generated
`CapabilityFeatureInfo`/manifest owner through inline arrays, helper returns,
alias/object carriers and mapped JSX into discovery sinks. A runtime-fetched
`.features`, fixed workspace tab and typed `requiredCapabilities` gate must not
fail. A local generated-lookalike must fail owner binding.

**Acceptance:** discovery renders producer features or explicit unavailable;
no fallback capability inventory survives; loading/offline/error does not
invent features; checker follows values rather than keywords.

**Expected commit:** `DS5-C04 strangle capability menu fallback`.

### DS5-C05 — INT-R6 semantic IDs, static copy, and D4 locale posture

**Measured set:** exactly 12 files; cap 13: `locale.ts`, `LocaleProvider.tsx` +
test; new semantic-copy registry/schema/checker/test; the shared C01
scanner/checker test; dashboard `package.json`; and one surgical disposition
supplemental finding. Each locale catalog has 2,449 leaves; none is edited.

**Red first:**

- `test_limited_semantic_id_cannot_upgrade_strength` mutates the structured
  semantic class while keeping plausible copy;
- `test_may_not_use_for_cannot_become_optional_recommendation`;
- `test_ru_cannot_reenter_active_locale_by_alias_or_exemption`;
- `test_uk_is_primary_and_en_is_fallback`;
- `test_static_copy_alias_reaches_authority_label_sink`.

The verifier binds canonical generated semantic IDs and typed
strength/obligation fields. It accepts localized authority copy only with a
content-bound receipt naming a competent external policy-copy reviewer,
reviewer authority/version and source-language scope. No such receipt exists at
entry, and DS5 will not self-attest the current strings. Missing review fails
closed to the canonical semantic ID/English owner token and is recorded
`verification_missing` with DS6 evidence-workflow ownership and an executable
receipt closure signal. A text edit—including plausible “confirmed with
caveat”—without a reviewed receipt fails; changing the ID/strength to launder it
also fails. The automated checker does not claim to understand Ukrainian.

Locale types split product exposure from frozen continuity: the active product
owner is `uk | en`, while `ru` may remain only in an explicitly named legacy
continuity/formatting type and frozen-catalog parity. Product resolution,
storage, provider state, navigation and landing selection accept only the
active type; an alias from the legacy type into any of those sinks is the
negative. This avoids deleting the continuity material without leaving a
runtime path that can select it.

**Acceptance:** active locales are exactly `uk` and `en`; `uk` is the primary
and default product locale and `en` remains the explicit baseline/fallback;
`ru` catalog and parity test bytes are unchanged; authority labels resolve by
semantic ID and unreviewed localized authority copy fails to the honest
fallback; duplicate/static authority copy through wrappers and JSX fails; the
three DS6 parity failures remain exact. C05 claims the mechanical review gate,
not completed human semantic review.

**Expected commit:** `DS5-C05 anchor copy and locale semantics`.

### DS5-C06 — three waist contracts, one regeneration, one re-anchor

**Measured set:** exactly 24 files; cap 26:
`services/governed_projections.py`; the mirrored governed-projection service and
runtime-contract-hardening tests; generated OpenAPI snapshot; package
`types.ts`, `runtimeApiClient.{ts,js}` and
`canonicalRuntimeApiClient.{ts,js}`; dashboard `src/api/types.ts`; package
`runtimeApiClient.type-test.ts`; three swap modules + three tests; the waist
register; and status inventory/checker/test plus disposition
register/checker/test. No waist schema or decision-grade consumer file is
edited.

**Red first:**

- `test_generated_cgf_disposition_union_rejects_renamed_or_reordered_owner_values`;
- `test_generated_decision_grade_union_tracks_pdc_owner`;
- `test_generated_cache_age_union_keeps_source_freshness_orthogonal`;
- the existing novel-owner and no-value-export negatives for all three adapters;
- `test_reanchor_stops_on_changed_symbol_or_field`.

**Acceptance:** the owner contracts produce closed unions through OpenAPI and
the generated client; adapters use exhaustive generated-type-bound switches
and return explicit `unrecognized` for runtime novel labels without exporting
constants. Type erasure is not presented as runtime validation. Terminal kinds
and evidence classes remain opaque. Every governed `export_symbol` still
occurs once, all 13 fields are unchanged, one uniform offset explains anchor
movement, two client hashes refresh, surgical JSON diffs preserve unrelated
bytes, and both corruption batteries pass.

**Expected commit:** `DS5-C06 bridge the three canonical waist unions`.

### DS5-C07 — one server audience-permission mapping

**Measured set:** exactly 24 files; cap 26: four HTTP source files (new
`audience_permissions.py`, `authorization.py`, governed service and route);
the five fence-listed HTTP/contract tests; generated OpenAPI snapshot; package
`types.ts`, `runtimeApiClient.{ts,js}` and
`canonicalRuntimeApiClient.{ts,js}` plus dashboard `src/api/types.ts`; package
`runtimeApiClient.type-test.ts`; and seven governed receipt/re-anchor files
(waist register; status inventory/checker/test; disposition
register/checker/test). Audience schema, generated client, mapping, route
enforcement, consumer contract and re-anchors land together; no contract-only
cluster boundary is allowed. The single authored direction is
`RuntimePermission -> frozenset[AudienceClass]`; the inverse is derived. Every
one of the 33 values appears exactly once. Current inverse counts are PUBLIC 0,
REVIEWER 20, EXPERT 28, MACHINE 22.

| Eligible audiences | Exact server-owned permissions |
| --- | --- |
| REVIEWER, EXPERT, MACHINE | `artifacts.batch.read`, `artifacts.render`, `evidence.view`, `fabric.quality.read`, `fabric.trust.read`, `knowledge.search`, `knowledge.view`, `lineage.batch.read`, `platform.view`, `runs.batch.read`, `runs.view` |
| REVIEWER, EXPERT | `dashboard.view`, `evidence.acquire`, `evidence.review`, `runs.review` |
| EXPERT, MACHINE | `analysis.execute`, `evidence.discover`, `evidence.preview`, `evidence.resolve`, `evidence.sae.analyze`, `fabric.impact.analyze`, `knowledge.trigger`, `mobility.analyze`, `platform.admin`, `runs.feedback.evaluate`, `runs.launch` |
| REVIEWER | `decisions.validity.publish`, `evidence.promotions.approve`, `evidence.promotions.reject`, `runs.production_approval.create`, `runs.reissue` |
| EXPERT | `mode.analyst`, `scenarios.create` |
| PUBLIC | no privileged permission; this does not create an anonymous route |

Current EXPERT projections declare exact `mode.analyst`; current MACHINE
projections declare exact `platform.view`. `AudienceClass` gains PUBLIC in this
cluster. PUBLIC and REVIEWER construction and deny behavior are exercised
through the same real dependency, but no current producer projection is
relabeled merely to populate those classes and PUBLIC does not enter the
anonymous allowlist.

**Red first:**
`test_each_nonpublic_projection_requirement_denies_all_other_32_permissions`
and `test_public_audience_denies_all_33_privileged_permissions`. Audience is a
server-declared surface contract, not a principal identity or hierarchy. The
exact declared grant admits regardless of coarse role label; all other 32
grants without it deny. PUBLIC has no privileged grant and all 33 values deny;
DS5 does not invent an anonymous positive route to make the matrix look full.
A permissionless principal cannot fetch any current privileged projection.
Direct URL, coarse role, client header and UI-hidden variants exercise the
server path. A source-derived corruption witness rejects any DS20 high-stakes
permission classified for MACHINE.

**Acceptance:** one immutable mapping is imported by one real route dependency;
REVIEWER, EXPERT and MACHINE have exact-grant allow and wrong-grant deny
witnesses, while PUBLIC proves the empty mapping and 33/33 privileged denials;
a route requires its exact declared permission, never merely any permission
eligible for an audience; mapping coverage is generic over all 33 enum members;
projection producer audiences are not relabeled; all six source-derived
high-stakes permissions exclude MACHINE; generated symbols/fields are
re-anchored under the same unchanged-field/uniform-offset rule; the UI is not
part of the allow decision.

**Expected commit:** `DS5-C07 enforce audience permission boundaries`.

### DS5-C08 — N010 fail-closed client identity

**Measured set:** exactly 10 files; cap 10: `api/queryKeys.ts`,
`useAuthMe.ts` + test, `AuthzProvider.tsx` + new test,
`app/authz/permissions.ts` + new test, shared `src/test/render.tsx`, and the
affected Platform Health story, plus the frontend disposition register. Six
downstream production consumers currently contain 11 default-allow expressions
and are a separately sized C09 boundary.

**Red first:** `AuthzProvider denies loading error malformed 401 prior-user and tenant-switch identity`.
It asserts no permission, MFA, collaboration pseudo-flag, or high-stakes CTA.

**Acceptance:** no production `FALLBACK_AUTH_ME`, no infinite-stale identity,
no placeholder grant; query identity partitions by verified auth-session
revision; unknown identity is explicit and empty; dashboard permissions import
the generated 33-value type and the three collaboration literals disappear.
DS20 server identity is consumed, not reimplemented.

**Expected commit:** `DS5-C08 fail closed on unknown identity`.

### DS5-C09 — N010 downstream default-deny surfaces

**Measured set:** exactly 11 files; cap 12: six production consumers
(`WorkspaceBoundary.tsx`, `Sidebar.tsx`, `Header.tsx`,
`InterfaceModeProvider.tsx`, `CommandPalette.tsx`, `RunDetailLayout.tsx`), one
new cross-surface behavioral test, the shared C01 scanner/checker/test, and the
frontend disposition register.

**Red first:** `test_missing_authz_context_never_defaults_authority_surface_to_allow`.
Loading, absent provider, error, cached-prior-user and tenant-switch variants
cover all 11 current allow expressions; a genuinely permission-free fixed
PUBLIC chrome element is the benign control.

**Acceptance:** absent context is unknown/deny, not allow; permission-free fixed
chrome stays visible; all permission-bearing routes, tabs, commands and mode
switches require current verified Authz state. The shared semantic gate derives
permission sinks so a seventh consumer cannot reintroduce `?? true` or an
equivalent conditional carrier.

**Expected commit:** `DS5-C09 migrate authority surfaces to default deny`.

### DS5-C10 — weakest-boundary and recompute-not-pin lint

**Measured set:** 4 files; cap 7: the shared C01 semantic engine/checker/test
and package wiring; no second composition scanner is created.

**Red first:** `test_compensation_veto_loss_and_pinned_status_reach_authority_sink`.
Variants cover mean/sum/any/pass compensation, `blocked` and rights-bar loss,
cached presence, copied status between stores, aliases, object/array carriers,
and status without as-of revalidation. Duration averages, chart layout and
non-authority numeric reductions are benign controls.

**Acceptance:** composed/weakest-boundary status at a client authority sink must
be producer-carried. Even a mathematically correct client `min`/meet is a second
authority implementation and fails. A veto cannot be averaged or projected
away; manually persisted authority status, `placeholderData`/`initialData`, or
`staleTime: Infinity` for authority queries fails. Single-owner generated label
presentation, numeric/layout/interaction reductions and duration averages are
benign.

**Expected commit:** `DS5-C10 enforce weakest boundary and recomputation`.

### DS5-C11 — generated cache posture and one real consumer

**Measured set:** exactly 9 files; cap 10:
`src/api/cacheDiscipline.ts` + test,
`useDepthNCycleBoardProjection.ts` + test,
`TimeSemanticsLabel.tsx` + test, and `RunExplainabilityPanel.tsx` + its
governed-projection test, plus the frontend disposition register. The
OpenAPI/generated union and cache-age adapter land in C06. This is the
only current query producer whose payload carries owner `packet.as_of +
freshness`; `TimeSemanticsLabel` currently renders twice and receives no
`cacheAgeLabel`.

**Red first:**

- `classifies_preexisting_query_data_as_cached_with_owner_as_of`;
- `marks_retained_stale_data_without_consulting_source_timestamps`;
- `refuses_cached_posture_without_owner_as_of`;
- `authority_query_never_emits_offline_queued`.

The observation uses QueryObserver lifecycle (`data present`,
`isFetchedAfterMount`, explicit `isStale`, `fetchStatus`). It never compares
payload/source timestamps (`as_of`, `observed_at`, `source_as_of`,
`dataUpdatedAt`, or `ApiMeta.generated_at`) to infer cache age. `isStale` may
carry TanStack's configured lifecycle result; the client does not reconstruct
it from timestamps. Cache state and source freshness remain orthogonal.

**Acceptance:** the real governed consumer visibly renders live/cached/stale
with owner `as_of`; missing `as_of` is explicit unrecognized/blocked; novel
union values stay unrecognized; no authority query can render
`offline_queued`.

**Expected commit:** `DS5-C11 render governed cache posture`.

### DS5-C12 — query-cache recurrence and typed debt

**Measured set:** exactly 9 files; cap 9:
`status_retirement_scan.mjs`, the C01 DS5 checker/test,
`query-cache-policy-register.json` + schema, dashboard `queryClient.ts` + a new
focused test, dashboard `package.json`, and the frontend disposition register.
Current denominators are 43 canonical query-key constructors, 42 `queryFn`
producers / 39 files, and the broad 66/40 syntax census.

**Red first:** `test_new_query_without_policy_or_owner_as_of_fails_through_carriers`.
Variants cover alias, wrapper, object/array carrier, later assignment, JSX
spread, timestamp-derived cache age, status copied into cache, and sibling
query creation. A non-authority operational counter and layout query are benign.

Each producer is classified exactly once as
`never_cache_authority | cacheable_with_owner_as_of |
operational_non_authority | legacy_missing_owner`. The one C11 producer leaves
debt. A missing owner field is a typed integrate-contract with owner slice and
executable closure signal, never an exemption. In particular,
`ApiMeta.generated_at` is request/payload generation time, not source truth.

**Acceptance:** a new unclassified query turns the gate red; only owner-as-of
payloads may render retained data at an authority sink. `never_cache_authority`
queries prove `gcTime: 0`, no placeholder/initial data, and removal on offline
or failed refetch through the real QueryClient path. Operational non-authority
queries may retain data under their typed class. Legacy-missing-owner data
cannot render cached authority and remains a typed integrate-contract rather
than an exemption. The register derives its denominator from source and the
checker rejects omissions or stale rows.

**Expected commit:** `DS5-C12 enforce query cache ownership`.

### DS5-C13 — bar promotion authority from offline replay

**Measured set:** exactly 17 logical diffs; cap 18:
`app/offline/db.ts`; `offlineQueueRepository.ts` renamed to the composer-only
`composerDraftDb.ts`; deleted `OfflineQueueProvider.tsx`; `AppProviders.tsx`;
`sw.ts`; `useQueuedPromotionDecision.ts` renamed to
`useLivePromotionDecision.ts`; its test renamed likewise;
`DataIntelligencePanel.tsx` + test; `composerDraftRepository.ts`; and
`src/README.md`; plus a new focused SW test, the shared C01 semantic
scanner/checker/test, the frontend disposition register, and the status
inventory. This is 17 logical diffs and 20 old/new path names. The composer
repository import follows the rename; no queue API remains in its storage
module. The only current queue kinds are `promotion.approve` and
`promotion.reject`.

**Red first:**
`test_offline_retryable_promotion_never_queues_terminalizes_or_replays`,
`test_authority_mutation_alias_wrapper_cannot_reach_offline_or_sw_replay`, and
`test_service_worker_has_no_authority_sync_or_authenticated_api_cache`.
Offline, 408, 429 and 5xx variants cover both current decisions; a synthetic
publication/reissue/approval sibling is carried through aliases, helpers and
object storage into IndexedDB/SW sinks. A composer draft is the benign
persistence counterexample. Service-worker and visibility/online events cannot
resurrect authority mutation replay.

**Acceptance:** delete the authority queue end-to-end: the DB version removes
the legacy store; no reader, replay provider or service-worker sync survives;
no IndexedDB row and no optimistic approved/rejected state. The generic gate
derives authority-bearing mutation sinks and rejects future sibling action
types, not only the two deleted names. Retry is an explicit live user action
through the current server identity, permission, step-up, tenant and
producer-state enforcement, and renders any server denial. The focused SW
behavioral test imports the real worker path and proves authenticated API
requests are never cached and no authority background-sync registration or
message bridge exists; versioned static-shell caching remains benign.
Epoch/rule revalidation remains a DS18 integrate-contract unless the producer
already carries it. Both deleted status definitions retire surgically in the
status inventory; the offline/SW disposition rows transition in this commit;
composer draft persistence remains.

**Expected commit:** `DS5-C13 bar promotion authority from offline queue`.

### DS5-C14 — local-state contract and composer consumer

**Measured set:** exactly 7 files; cap 7:
`app/offline/authorityLocalState.ts` + test,
`composerDraftRepository.ts` + test, `ComposerModeSections.tsx`, and
`LaunchRunPage.test.tsx`, plus the frontend disposition register. C08 verified
tenant/user identity is a dependency.

**Red first:** `test_composer_draft_cannot_cross_tenant_user_or_expiry`.
Legacy unwrapped, malformed, expired, prior-tenant and prior-user bytes never
hydrate. A same-scope non-authority draft is the positive control.

**Acceptance:** physical key and strict envelope both content-bind family,
tenant and user; writer-owned TTL is checked against an injected clock; absent
identity fails closed; no legacy byte is silently migrated into authority.
`offline-draft-composer` gains a complete isolation consumer while
`cache-local-storage-state` stays pending until C17.

**Expected commit:** `DS5-C14 bind composer local state`.

### DS5-C15 — Clerk local-state family

**Measured set:** exactly 4 files; cap 5: `useChatStore.ts`, its test,
`ClerkChatPage.tsx` as the single identity/scope hydration bridge, and the
frontend disposition register.

**Red first:** `test_clerk_session_clears_before_cross_identity_rehydrate`.

**Acceptance:** Zustand storage is identity-keyed, expiry-checked and
`skipHydration`; identity change clears in-memory sessions before rehydrate;
live streaming state is never persisted. The `cache-clerk-sessions` domain row
remains DS14 `rebind_pending`; DS5 attaches isolation evidence only.

**Expected commit:** `DS5-C15 partition Clerk sessions`.

### DS5-C16 — causal and dispute local-state families

**Measured set:** exactly 7 files; cap 7: CausalTab/test, dispute domain/test,
DisputeRegistryPanel, one new focused panel test, and the frontend disposition
register.

**Red first:** `test_causal_and_dispute_state_reject_cross_scope_and_stale_bytes`.

**Acceptance:** explicit scope enters the shared adapter; causal storage stays
candidate/unidentified and never trusts a stored authority status; dispute
state stays interaction-only. DS8/DS9 domain rows remain `rebind_pending` with
partition successor evidence.

**Expected commit:** `DS5-C16 partition causal and dispute state`.

### DS5-C17 — operator-craft family and six-store reconciliation

**Measured set:** exactly 10 product/test/register files; cap 11:
`operatorCraft.ts` + test, `OperatorCraftPanel.tsx`, `AmbientTelemetryHud.tsx`,
the shared C01 TypeScript semantic scanner/checker/test, and the disposition
register/checker/test. Operator craft is one DS1 unit with four physical
families: threshold, annotations, evidence wallet, and onboarding. C17 also
records the existing WhatIf deletion and a fresh zero-path/zero-import census
for DS4-deleted review-attention.

**Red first:** `test_all_operator_craft_families_bind_scope_and_expiry` plus a
synthetic reintroduced unpartitioned review-attention store. A locale/theme/UI
preference store is the benign non-authority persistence counterexample.

**Acceptance:** all four families bind tenant/user/expiry. Generic recurrence
derives and classifies every persistent storage declaration/access from source,
then requires envelopes only for values that reach authority-like/local-state
sinks; unclassified access or an unenveloped authority-like family fails.
Locale, theme, dashboard-layout and other interaction-only preferences remain
typed benign classes rather than false positives. The current authority-like
living denominator is 8 physical families: Clerk, causal, dispute, composer,
and four operator keys. `cache-local-storage-state` reaches a bounded
`use_as_is` state only for this classification/partition adapter, not for all
browser persistence; feature semantic rows remain with DS8/DS9/DS14.
Review-attention becomes `deleted/strangled` with DS4 commit `bc1d01001` plus
fresh census; N015 is at most `partially_reduced` unless live server
revalidation is proven.

**Expected commit:** `DS5-C17 partition operator state and reconcile stores`.

### DS5-C18 — strict D5 exposure registry

**Measured set:** exactly 5 files; cap 6: feature-flag registry/test,
provider/test, and the frontend disposition register. There are 12 current keys
and four missing consumers.

**Red first:** `test_unknown_or_wrong_type_flag_fails_closed_at_every_source`.
Remote, window, props, cache and environment variants include an old schema and
the auth pseudo-flag.

**Acceptance:** one strict schema rejects unknown keys and wrong types with an
observable diagnostic; cache carries version/expiry/scope; no partial merge on
invalid input; the registry API accepts only typed rollout state and cannot
accept RuntimePermission.

**Expected commit:** `DS5-C18 make flag exposure registry strict`.

### DS5-C19 — wire three flags and retire collaboration

**Measured set:** exactly 13 files; cap 13: `AppShell.tsx` +
`layoutSurfaces.test.tsx`; `surfaceRegistry.ts`; `features/runs/route.tsx` +
`runDetailSurfaces.test.tsx`; `OverviewTab.tsx`; command palette + test; flag
registry + test; and disposition register/checker/test. The run-detail test is
the registry and direct-route negative, so `surfaceRegistry.test.ts` is not a
second edited proof. The surviving server-backed WhatIf workbench remains five
files and has one Overview consumer; no local WhatIf store returns.

**Red first:** `test_false_flag_blocks_route_deep_link_keyboard_and_cached_manifest`.
Run separately for causal graph, command palette and WhatIf. Collaboration key
absence is the retirement negative; a permission grant cannot make a false
rollout flag true and a flag cannot satisfy permission.

**Acceptance:** three whole-surface gates are real at route, deep-link and
keyboard entry; collaboration key and environment surface are retired; all
four disposition decisions carry successor/consumer or deletion evidence.

**Expected commit:** `DS5-C19 wire and retire D5 flags`.

### DS5-C20 — final ledgers, receipts, and architect handoff

**Measured set:** exactly 5 files; cap 6: this plan, DS5 journal, new closure,
`live-application-readiness-ledger.json`, and the generated frontend disposition
reference document. Disposition/status/waist rows and hashes transition in
their owning implementation/regeneration clusters, never as a C20 tail. All
JSON edits are surgical and idempotent.

**Red first:** closure corruption sweep: changed generated symbol/field,
synthetic status revival, raw transport alias, capability fallback, semantic
strength upgrade, active `ru`, audience bypass, pinned status, cached payload
without posture, queued authority action, cross-tenant store, unknown flag and
flag/permission substitution must each fail while benign siblings pass.

**Acceptance:** final clean-tree receipt table is complete; every touched row
has evidence and truthful capability state; baseline debt has zero new
identity; fence/lock/generated diffs are exact; independent review has no open
Important/Critical finding; closure explicitly lists what is not claimed.

**Expected commit:** `DS5-C20 close enforcement waist for architect review`.

## Expected cluster commits

| Cluster | Expected subject | Max files |
| --- | --- | ---: |
| C00 | `DS5-C00 plan measured enforcement waist` | 1 |
| C01 | `DS5-C01 enforce canonical status ownership` | 9 |
| C02 | `DS5-C02 make architecture zero recurrent` | 7 |
| C03 | `DS5-C03 type raw authority transports` | 12 |
| C04 | `DS5-C04 strangle capability menu fallback` | 12 |
| C05 | `DS5-C05 anchor copy and locale semantics` | 13 |
| C06 | `DS5-C06 bridge the three canonical waist unions` | 26 |
| C07 | `DS5-C07 enforce audience permission boundaries` | 26 |
| C08 | `DS5-C08 fail closed on unknown identity` | 10 |
| C09 | `DS5-C09 migrate authority surfaces to default deny` | 12 |
| C10 | `DS5-C10 enforce weakest boundary and recomputation` | 7 |
| C11 | `DS5-C11 render governed cache posture` | 10 |
| C12 | `DS5-C12 enforce query cache ownership` | 9 |
| C13 | `DS5-C13 bar promotion authority from offline queue` | 18 |
| C14 | `DS5-C14 bind composer local state` | 7 |
| C15 | `DS5-C15 partition Clerk sessions` | 5 |
| C16 | `DS5-C16 partition causal and dispute state` | 7 |
| C17 | `DS5-C17 partition operator state and reconcile stores` | 11 |
| C18 | `DS5-C18 make flag exposure registry strict` | 6 |
| C19 | `DS5-C19 wire and retire D5 flags` | 13 |
| C20 | `DS5-C20 close enforcement waist for architect review` | 6 |

## Closure battery

At C20 run each command separately and retain parseable output:

```bash
git status --short
git diff --check
python3 architecture/atlas_surfaces/check_status_retirement_inventory.py --check --corruption-probes
python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --verify-baseline-source-bytes --corruption-probes
python3 -m unittest architecture.atlas_surfaces.test_frontend_baseline_debt_manifest architecture.atlas_surfaces.test_frontend_disposition_register architecture.atlas_surfaces.test_status_retirement_inventory
uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
uv run polisyos-tools architecture guardrails check
```

And from the relevant workspaces:

```bash
corepack pnpm --dir packages/runtime-api-client run typecheck
corepack pnpm --dir packages/runtime-api-client run check:architecture
corepack pnpm --dir apps/runtime-dashboard run lint
corepack pnpm --dir apps/runtime-dashboard run check:architecture
corepack pnpm --dir apps/runtime-dashboard run typecheck
corepack pnpm --dir apps/runtime-dashboard run build
corepack pnpm --dir apps/runtime-dashboard run test:components
corepack pnpm --dir apps/runtime-dashboard run test:storybook
corepack pnpm --dir apps/runtime-dashboard run test:a11y
corepack pnpm --dir apps/runtime-dashboard run test:visual
corepack pnpm --dir packages/atlas-ui run lint
corepack pnpm --dir packages/atlas-ui run check:architecture
corepack pnpm --dir packages/atlas-ui run typecheck
corepack pnpm --dir packages/atlas-ui run test
```

The production build, typecheck, DS5-owned/touched tests, generated-client
contract and architecture gates are absolute green. Full component/visual gates
are honest baseline-red only for the exact three DS6 parity identities and the
one DS8 A4 print identity; no new failure or re-baseline is accepted.

## Explicit Not yet

- No merge, push, rebase, CI change, deployment claim, or backend-engine work.
- No closure or ordering of terminal kinds or evidence classes; unseen values
  stay opaque and neutral.
- No DS6 `overBudget` parity repair, frozen-set migration, `ru` catalog edit,
  or public locale-support claim.
- No DS8 A4 print expectation change and no claim of 18/18 visual green.
- No DS18 universal epoch/staleness chrome. DS5 supplies cache discipline and
  visible existing consumers; it does not invent producer epochs or infer
  cache age from timestamps.
- No DS9 mandate, approval, review-effectiveness, or promotion-CAS ownership;
  DS20's server halves are consumed, not re-closed.
- No DS12 telemetry/public-record closure; telemetry remains a typed sanctioned
  adapter with its privacy capability still `verification_missing`.
- No N018 review-WebSocket authentication/idle-safe surface closure. The raw
  constructor is governed, while the existing handshake/degradation gap stays
  `bridge_missing` with its named owner and closure signal.
- No ban on fixed curated workspace chrome or typed capability gates; law 12
  forbids open-ended hardcoded capability discovery.
- No claim that a lint, flag, cache hit, translation, or frontend union is an
  authority source.
