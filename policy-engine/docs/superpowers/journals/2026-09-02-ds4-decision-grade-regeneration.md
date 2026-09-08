# DS4 DecisionGrade contract-surface regeneration journal

- Date: 2026-09-02
- Worktree: `/Users/deniskopylov/polisyos/.worktrees/ds4-decision-grade-regeneration/policy-engine`
- Branch: `codex/ds4-decision-grade-regeneration`
- Task base: `0413953e25a9efbba1521022156be3138dd855f6`
- Plan commit: `6a37346ba`
- Implementation and generated-output commit: `61ce304dde33b85afb56d5d28614dd3e05bacfab`

## Scope and vocabulary decision

The presentation waist binds the canonical
`polisyos.pdc.DecisionGrade` vocabulary:

1. `unsupported`
2. `descriptive_only`
3. `advisory_admissible`
4. `decision_admissible`

`DecisionGrade` was already public through `polisyos.pdc`. The owner change
was only the established PEP 695 naming pattern:

    DecisionGrade = Literal[...]

became:

    type DecisionGrade = Literal[...]

That gives Pydantic/OpenAPI a named alias while retaining the same public
facade and the same four strings. It does not add an endpoint, DTO, operation,
or Python public export.

`ValuePromotionDecisionGrade` is explicitly excluded. It is owned by
`src/polisyos/core/contracts/value_outer_set.py` and has the different
`blocked | low | medium | high` promotion lattice. Treating that similarly
named type as the DS4 owner would be a P27 canonical-owner bypass.
`CgfDisposition` remains `producer_missing`; `CacheAge` remains retired.

Before this change the 599-byte waist did not contain a local vocabulary copy:
it classified every input as `unrecognized`. This is therefore the first
time the dashboard surface recognizes an owner-issued decision grade, not a
refactor of an existing recognizer.

The pattern pass applied:

- P27: name the existing canonical owner instead of creating a dashboard or
  runtime-HTTP vocabulary.
- P29: exercise live OpenAPI, generated types, TypeScript exhaustiveness, and
  runtime unknown-value behavior rather than checking marker strings.
- P31/P33: scan the complete dashboard `src` denominator for a second
  vocabulary declaration, and falsify the scanner with alias, parameter-union,
  literal-constant, and spread-composed variants.
- P35: derive every count below from the complete seven-path denominator.

## Required before census

The census ran before the first regeneration. Its denominator was exactly one
JSON file, four TypeScript files, and two JavaScript files: 7 paths, 139,982
lines, and 4,684,099 bytes.

| Registered path | Lines before | Bytes before | Named `DecisionGrade` before |
| --- | ---: | ---: | ---: |
| `schemas/runtime_api_v1.openapi.json` | 75,457 | 2,674,883 | 0 |
| `packages/runtime-api-client/types.ts` | 25,736 | 892,913 | 0 |
| `packages/runtime-api-client/runtimeApiClient.ts` | 7,130 | 212,381 | 0 |
| `packages/runtime-api-client/runtimeApiClient.js` | 850 | 30,273 | 0 |
| `packages/runtime-api-client/canonicalRuntimeApiClient.ts` | 3,290 | 101,412 | 0 |
| `packages/runtime-api-client/canonicalRuntimeApiClient.js` | 872 | 30,407 | 0 |
| `apps/runtime-dashboard/src/api/types.ts` | 26,647 | 741,830 | 0 |
| **Total** | **139,982** | **4,684,099** | **0** |

`CgfDisposition` and `CacheAge` were also zero in every member of the
seven-path denominator. The OpenAPI snapshot had 526 named components.
`AuthorityBoundary.properties.decision_grade.anyOf[0].enum` was the sole
inline occurrence of the four DS4 strings.

## Registry map

All three families are `generated_committed` and declare
`stale_output_behavior = "fail"`.

### `runtime-openapi-snapshot`

- Output: `schemas/runtime_api_v1.openapi.json`
- Declared generator:

      PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json

- Declared verifier:

      uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py --skip-client-drift

### `runtime-api-client`

- Outputs: `types.ts`, `runtimeApiClient.ts`, `runtimeApiClient.js`,
  `canonicalRuntimeApiClient.ts`, and `canonicalRuntimeApiClient.js`
  under `packages/runtime-api-client`.
- Declared generator:

      corepack pnpm --filter @polisyos/runtime-api-client run generate

- Declared verifier:

      uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py

### `runtime-dashboard-api-types`

- Output: `apps/runtime-dashboard/src/api/types.ts`
- Declared generator:

      corepack pnpm --filter @polisyos/runtime-dashboard run generate:api

- Declared verifier: from `apps/runtime-dashboard`, replay
  `corepack pnpm run generate:api` and require
  `src/api/types.ts` to remain byte-identical.

## Toolchain receipt and shared-hook observation

The required install ran before any TypeScript or generator result was trusted:

    /opt/homebrew/bin/corepack pnpm install --frozen-lockfile

It exited 0 with pnpm 10.33.2 and installed 1,215 packages. The prepare hook
reported the shared `core.hooksPath` at
`/Users/deniskopylov/polisyos/.git/hooks` and installed lefthook wrappers
there. The positive-control test
`test_guardrails_corruption_names_failed_family_and_keeps_sibling_clean`
then passed (1/1), proving that a deliberately corrupted generated-client
candidate is named while its sibling family remains clean.

The shared hooks denominator contained 18 files before and after. The measured
wrapper changes were:

| Hook | Before bytes / SHA-256 | After bytes / SHA-256 |
| --- | --- | --- |
| `pre-commit` | 2,407 / `325bffbcd714b37ebb0cf8ab7543f2396ec673a083b60fbc32ed637df5008d58` | 2,421 / `05e548f4243c305155d330a6659a7a0c1f7716fc8ed51f0da2ae485304373600` |
| `pre-push` | 2,405 / `799e3a15368ea7d7112b29065d4f7844d46f385067691453b723101ed45b4e49` | 2,419 / `7796972e07fa9290ca6debde3368aa725abd87363e309019c78cc07759ec749b` |

Each 14-byte size delta is the twice-embedded literal path to this worktree's
`node_modules`. The other 16 hooks were byte- and mode-identical.
`pre-commit.old` remained 656 bytes with SHA-256
`2f4d77186362b2d2540812436d655c29a814d67497a75bd2de66bb3d0bc4123b`.
Per the architect's adjudication, these two files are lefthook-generated shims
with no user-authored content; they were left in place and not modified again.
This is the measured instance of the separately registered
`shared-git-hook-hardcodes-one-worktree-path` finding, not DS4 work.

The expected commit-time symptom occurred:

    No config files with names ["lefthook" ".lefthook" ".config/lefthook"] have been found

## RED, generation, and waist binding

The owner RED test asked live OpenAPI for a `DecisionGrade` component derived
from public `polisyos.pdc.DecisionGrade`, and for exactly one property
reference at `AuthorityBoundary.properties.decision_grade.anyOf[0]`. It
failed with a missing `DecisionGrade` component before the owner alias was
named and passed after the one-line owner change.

The dashboard RED run had two independent failures:

- a known `unsupported` grade still returned `unrecognized`;
- no private exhaustive runtime record existed.

The final waist imports `DecisionGrade` from
`@polisyos/runtime-api-client`, uses a private
`Record<DecisionGrade, DecisionGrade>`, and checks runtime membership with
`Object.hasOwn`. A string not in the generated union continues through the
runtime fail-open path as:

    { classification: "unrecognized", ownerLabel: <trimmed input> }

The package type test proves canonical `DecisionGrade` equals
`types.ts`'s generated `components["schemas"]["DecisionGrade"]`. The
dashboard test proves the recognized branch's `ownerLabel` is that package
type and that it equals the dashboard-local generated component type. There
is no hand-copied union in production code.

The first falsifier revision caught a type alias and literal array but allowed
a function-parameter union and a constant assembled from two spread
fragments. The adversarial test was made RED on both escapes. The final
scanner visits every TypeScript `UnionTypeNode`, recursively resolves
same-file constant initializers, scans every `.ts`/`.tsx` under dashboard
`src` except the registered generated `api/types.ts`, and permits exactly
the one required private exhaustive record. The focused suite returned 9/9;
an independent delta review found no remaining Critical or Important issue.

## Generator executions and outputs

All registered generators ran; no generated file was hand-edited.

1. OpenAPI generator, exit 0:

       PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/ds4-decision-grade-regeneration/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/ds4-decision-grade-regeneration/policy-engine /opt/homebrew/bin/uv run --extra runtime --extra ml python /Users/deniskopylov/polisyos/.worktrees/ds4-decision-grade-regeneration/policy-engine/tools/ops_runners/runtime/export_runtime_openapi.py --output /Users/deniskopylov/polisyos/.worktrees/ds4-decision-grade-regeneration/policy-engine/schemas/runtime_api_v1.openapi.json

   Output:

       /Users/deniskopylov/polisyos/.worktrees/ds4-decision-grade-regeneration/policy-engine/schemas/runtime_api_v1.openapi.json

2. Runtime client generator, exit 0:

       /opt/homebrew/bin/corepack pnpm --filter @polisyos/runtime-api-client run generate

   It emitted all five registered outputs: `types.ts`,
   `runtimeApiClient.ts`, `runtimeApiClient.js`,
   `canonicalRuntimeApiClient.ts`, and
   `canonicalRuntimeApiClient.js`.

3. Dashboard API generator, exit 0:

       /opt/homebrew/bin/corepack pnpm --filter @polisyos/runtime-dashboard run generate:api

   `openapi-typescript 7.13.0` generated
   `apps/runtime-dashboard/src/api/types.ts`.

Five registered outputs changed. Both JavaScript outputs replayed but remained
byte-identical because no HTTP operation changed.

## After census

| Registered path | Lines after | Bytes after | Named `DecisionGrade` after |
| --- | ---: | ---: | ---: |
| `schemas/runtime_api_v1.openapi.json` | 75,459 | 2,674,883 | 2 |
| `packages/runtime-api-client/types.ts` | 25,737 | 892,970 | 2 |
| `packages/runtime-api-client/runtimeApiClient.ts` | 7,132 | 212,425 | 2 |
| `packages/runtime-api-client/runtimeApiClient.js` | 850 | 30,273 | 0 |
| `packages/runtime-api-client/canonicalRuntimeApiClient.ts` | 3,292 | 101,491 | 2 |
| `packages/runtime-api-client/canonicalRuntimeApiClient.js` | 872 | 30,407 | 0 |
| `apps/runtime-dashboard/src/api/types.ts` | 26,645 | 741,831 | 2 |
| **Total** | **139,987** | **4,684,280** | **10** |

`CgfDisposition`, `CacheAge`, and `ValuePromotionDecisionGrade` are zero
across all seven outputs after regeneration.

## Four conditions

### 1. Wire values did not move

A complete script loaded the task-base OpenAPI blob with `git show`, loaded
the regenerated blob from the branch, resolved component references
recursively, and compared every pre-existing component's reachable
`enum`/`const` multiset.

Observed output:

    before_values ['unsupported', 'descriptive_only', 'advisory_admissible', 'decision_admissible']
    after_values ['unsupported', 'descriptive_only', 'advisory_admissible', 'decision_admissible']
    before_wire_bytes_hex 5b22756e737570706f72746564222c2264657363726970746976655f6f6e6c79222c2261647669736f72795f61646d69737369626c65222c226465636973696f6e5f61646d69737369626c65225d
    after_wire_bytes_hex 5b22756e737570706f72746564222c2264657363726970746976655f6f6e6c79222c2261647669736f72795f61646d69737369626c65222c226465636973696f6e5f61646d69737369626c65225d
    wire_bytes_identical True
    before_components 526
    after_components 527
    changed_preexisting_component_value_sets []

The OpenAPI schema changed from an inline enum to one named component and a
reference. The strings and their order are byte-identical.

The exporter was replayed after regeneration. Its schema SHA-256 remained
`8030f2c3584e1f989299074052661dfc60994e1193d92032630e691f457222f7`
before and after the replay.

### Derived DS17 example receipt

The OpenAPI JSON diff also refreshed ten leaf values inside only the
`confidence-ledger-risk-spend` 200-response example: dependency count and
aggregate identity, worker receipt hash/ref, copied source dependency hash,
projection hash, the two replay pins, and the replay URL containing those
pins. No path, operation, response schema, or component value set changed.

This was traced rather than discarded as noise:

- the last schema-changing commit `981ec05dd5` reproduces exactly 6,246
  consulted paths and aggregate
  `sha256:e219ef2cd5ccfdbdd558aa588ccf7d101093e51f3830b628f028f6dd4049fea8`;
- the task-base archive reproduces 6,276 paths and aggregate
  `sha256:d1c60f2cca58ade2c18737ca103b044055f0312777fee7d2ba78717aff831652`;
- the current branch has the same 6,276-path key set and aggregate
  `sha256:a6a63c551ac2e6c4372e427949fc8a12c4dd46627c714d6b00b09cc56e0ba01a`.

The 6,246 to 6,276 count is completely accounted for by 31 added consulted
paths and one removed path between the last schema regeneration and task base:

    + src/polisyos/core/contracts/scope_adjudication.py
    + src/polisyos/pdc/_impl/evaluation_safety.py
    + src/polisyos/pdc/_impl/world_model_record.py
    + src/polisyos/runtime/http/services/acquisition_admission_bundle.py
    + src/polisyos/runtime/http/services/acquisition_surface_execution.py
    + src/polisyos/scientist/governance/continuous/published_signature_custody.py
    + src/polisyos/scientist/replay/deterministic.py
    + tests/integration/core_runtime/test_acquisition_admission_bundle.py
    + tests/integration/core_runtime/test_acquisition_production_boundary.py
    + tests/integration/core_runtime/test_acquisition_route_execution_binding.py
    + tests/integration/runtime_quality/test_published_signature_custody.py
    + tests/integration/scientist/governance
    + tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py
    + tests/repo_quality/architecture/test_continuous_incident_import_cycle.py
    + tests/repo_quality/architecture/test_import_governance_contract.py
    + tests/repo_quality/docs
    + tests/repo_quality/docs/test_accessibility_evidence.py
    + tests/repo_quality/docs/test_docs_lifecycle_checker.py
    + tests/repo_quality/frontend
    + tests/repo_quality/frontend/test_ds9_visual_collection_boundary.py
    + tests/repo_quality/frontend/test_fixture_runtime_bound_paper.py
    + tests/repo_quality/frontend/test_public_claim_copy_inventory.py
    + tests/repo_quality/test_task_l_research_censuses.py
    + tests/unit/core/contracts/test_scope_adjudication.py
    + tests/unit/pdc/test_world_model_record_contract.py
    + tests/unit/runtime/http/test_control_worker_maintenance.py
    + tests/unit/runtime/quality/adapter_registry_test_support.py
    + tests/unit/runtime/quality/test_adapter_registry_capability_discovery.py
    + tests/unit/runtime/quality/test_adapter_registry_free_growth.py
    + tests/unit/scientist/replay/test_deterministic_compatibility.py
    + tools/quality/testing/pytest_workload_receipt.py
    - src/polisyos/core/observability/truthfulness.py

Current versus task base has no added or removed dependency key. Only the
deliberately changed owner file and focused live-OpenAPI test have different
content identities. The wrapper delta is therefore deterministic generated
provenance, not a hidden DS4 wire-value movement.

One exporter replay and one full-verifier attempt hit the existing owner's
fixed 120-second subprocess boundary. The immediately following typed
resolution was `available`, `passed`, had zero issue codes, and reproduced
the exact 6,276-path aggregate. Serial execution with
`PYTHONDONTWRITEBYTECODE=1`, `PYTHONNOUSERSITE=1`,
`PYTHONHASHSEED=0`, and `POLISYOS_EXECUTION_PROFILE=dev` then made the
unchanged declared commands pass. No timeout, validator, or product code was
changed.

### 2. Compile-time exhaustiveness and runtime fail-open are separate

- Compile time: the private
  `Record<DecisionGrade, DecisionGrade>` makes an owner-union addition fail
  dashboard typecheck until presentation is updated.
- Runtime known value: `unsupported` returns
  `classification: "recognized"`.
- Runtime future value: `future-owner-grade` returns
  `classification: "unrecognized"` with the label preserved; no
  `undefined` classification and no crash.

Both package and dashboard typechecks passed twice. The focused Vitest file
passed 9/9 twice.

### 3. No second hand-written vocabulary

The scanner walks all TypeScript/TSX under
`apps/runtime-dashboard/src`, excluding only the registered generated
`api/types.ts`, permits exactly one private exhaustive runtime record, and
fails on a complete hand-written union or constant. Its falsifier exercises:

- a type alias union;
- a function-parameter union;
- an exported literal array;
- an exported constant composed from two spread fragments.

The RED run missed the parameter/spread variants; the final scanner catches
both. Production scan result:

    { authorizedRecordCount: 1, findings: [] }

### 4. Blast radius is one property

Observed output:

    DecisionGrade_property_ref_count 1
    DecisionGrade_property_ref_paths ['components.schemas.AuthorityBoundary.properties.decision_grade']

The named component is referenced by exactly one property, as expected.

## Two verification loops

| Check | Loop 1 | Loop 2 |
| --- | --- | --- |
| Ruff check over changed Python | exit 0 | exit 0 |
| Focused live-OpenAPI pytest | exit 0, 1 passed | exit 0, 1 passed |
| Runtime client package typecheck | exit 0 | exit 0 |
| Dashboard typecheck | exit 0 | exit 0 |
| Focused waist Vitest | exit 0, 9 passed | exit 0, 9 passed |
| OpenAPI declared verifier | exit 0 | exit 0 |
| Runtime-client declared verifier | exit 0 after typed timeout diagnosis and unchanged retry | exit 0 |
| Dashboard declared replay | exit 0; SHA-256 `08c769ee0189ace820be1a51f0b7e419b258254b98ecefd8aed7a8a87e94a1dc` unchanged | exit 0; same hash unchanged |
| Debt ledger `--check` | exit 0; zero blocking | exit 0; zero blocking |
| Docs lifecycle | exit 1; exactly 6 carried findings | exit 1; exactly the same 6 findings |

The repository-wide architecture command was also run before source changes
and in both final loops:

    /opt/homebrew/bin/uv run polisyos-tools architecture guardrails check

Every run reported:

    Generated artifact freshness clean: runtime-api-client (5 generator-observed outputs).
    Generated artifact freshness clean: runtime-dashboard-api-types (1 generator-observed outputs).

The aggregate command nevertheless exited 1 for the same pre-existing,
disjoint inputs on every run:

1. three deep imports from
   `src/polisyos/runtime/http/services/acquisition_admission_bundle.py` to
   `polisyos.core.artifacts.{manifest,signing,write_contract}`;
2. stale
   `apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json`.

Neither input intersects this branch's changed-path denominator. P41 therefore
classifies the aggregate red as inherited; changing either would add a second
concern and violate the branch's explicit scope. The deciding rule is: DS4 is
closed when its declared family verifiers and both generated-client freshness
probes are clean and a repository-wide residual reproduces before DS4 with
zero changed-path intersection. Do not sync a baseline or regenerate an
unrelated family to make the aggregate exit green.

## Exact append-only register prose for architect transcription

### `ds4-waist-decision-grade`

> **TASK DS4 2026-09-02 — `blocked` -> `closed`; `bridge_missing + surface_missing` -> closed.** Commit `61ce304dde33b85afb56d5d28614dd3e05bacfab` names the already-public canonical `polisyos.pdc.DecisionGrade` alias, regenerates all seven registered OpenAPI/runtime-client/dashboard outputs, and binds the sole DS4 presentation waist to the package-generated type. This is the first implementation that recognizes owner grades: a private exhaustive `Record<DecisionGrade, DecisionGrade>` makes future owner-union growth fail dashboard typecheck, while a separate runtime guard preserves a newer-server string as `classification: "unrecognized"`. The four wire strings are byte-identical before/after; no pre-existing component's reachable enum/const value set changed; named components move 526 -> 527; exactly one property, `AuthorityBoundary.properties.decision_grade`, references the new component. The dashboard-wide AST falsifier allows only the required private record and rejects alias, parameter-union, literal-constant, and spread-composed second copies. `ValuePromotionDecisionGrade` remains the separate `blocked | low | medium | high` promotion lattice; `CgfDisposition` remains `producer_missing`; `CacheAge` remains retired. Both verification loops leave the runtime-client and dashboard generated-family freshness probes clean. The repository-wide architecture aggregate retains only the P41-carried, pre-DS4 acquisition deep-import and trust-claim-posture drift; those paths are disjoint from DS4 and are not transcribed as DS4 work.
