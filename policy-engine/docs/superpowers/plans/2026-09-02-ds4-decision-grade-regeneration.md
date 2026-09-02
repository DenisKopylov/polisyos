# DS4 DecisionGrade Regeneration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Name the existing Policy Design Case `DecisionGrade` wire vocabulary, regenerate every registered runtime client surface, and bind the DS4 presentation waist to the generated type without changing any wire value.

**Architecture:** Convert the already-public `polisyos.pdc.DecisionGrade` alias to the repository's named PEP 695 alias form so Pydantic emits one OpenAPI component and replaces the single inline `AuthorityBoundary.decision_grade` enum with one reference. Run only the three registered generators, then make the dashboard's sole presentation waist recognize the four owner grades through a compile-time exhaustive, private `Record<DecisionGrade, ...>` while retaining an explicit runtime `unknown -> unrecognized` path.

**Tech Stack:** Python 3.14, Pydantic/FastAPI OpenAPI, pnpm 10, TypeScript, Vitest, repository architecture guardrails.

**Spec:** `docs/plans/active/atlas-slices/DS4-status-grammar-rebinding.md` and the architect-approved `ds4-waist-decision-grade` continuation dated 2026-09-02.

## Global Constraints

- Work only in `/Users/deniskopylov/polisyos/.worktrees/ds4-decision-grade-regeneration/policy-engine` on attached branch `codex/ds4-decision-grade-regeneration`.
- Use absolute paths in every command; do not checkout, switch, stash, read another worktree, or contact another project lane.
- Verify branch attachment before every commit; preserve append-only history.
- Run `corepack pnpm install --frozen-lockfile` before trusting TypeScript or generator evidence; prove its prepare hook leaves shared hook bytes unchanged.
- Run all three declared generators even when an output remains byte-identical; never hand-edit a generated output.
- Stop on any generated occurrence of `CgfDisposition` or `CacheAge`, any wire-value change, any unexplained changed path, or any need to hand-bind a generated file.
- Do not edit `docs/plans/active/`; the architect transcribes the journal's exact append-only prose.
- Keep `ValuePromotionDecisionGrade = blocked | low | medium | high` separate from DS4's admissibility lattice.
- Pattern pass: avoid P03 hidden surface, P04 lattice conflation, P27 owner bypass, P29 marker-only proof, P31 instance patching, P35 sampled denominators, and P38 proxy gates. Target state is an owner-derived named component, regenerated consumers, one checked waist, and behavioral plus type-level falsifiers.

---

### Task 1: Bind the toolchain and preserve the setup receipt

**Files:**
- Commit plan: `docs/superpowers/plans/2026-09-02-ds4-decision-grade-regeneration.md`
- Later record evidence: `docs/superpowers/journals/2026-09-02-ds4-decision-grade-regeneration.md`

**Interfaces:**
- Consumes: the provisioned Python environment and root pnpm lockfile.
- Produces: a trusted workspace install plus before/after hashes for the shared git hooks path.

- [ ] **Step 1: Verify and commit this plan on the attached branch**

Run `git status -sb`, `git symbolic-ref -q HEAD`, and `git diff --check`; add only this plan and commit it.

- [ ] **Step 2: Capture the shared hooks receipt before install**

Resolve `git rev-parse --git-path hooks`; hash every regular file under that exact directory, including its relative name, into the command transcript.

- [ ] **Step 3: Install the declared dashboard toolchain**

Run `corepack pnpm install --frozen-lockfile` from the product root and retain the prepare-hook output.

- [ ] **Step 4: Prove hooks were touched but not modified**

Hash the same complete hook-file denominator again and assert byte-for-byte equality with the pre-install manifest. Record that the prepare hook addressed the shared path while its content manifest remained unchanged.

- [ ] **Step 5: Take a freshness positive control**

Run the focused architecture-output-probe falsifier that constructs a temporary stale/failing generated family and asserts a freshness violation. Then run the clean guardrail snapshot so the toolchain's positive and negative paths are both observed without modifying a registered output.

### Task 2: Name the owner vocabulary through a RED/GREEN contract cycle

**Files:**
- Modify: `tests/unit/runtime/http/test_runtime_api_contract_hardening.py`
- Modify: `src/polisyos/pdc/_impl/layer2_readiness.py`

**Interfaces:**
- Consumes: public `polisyos.pdc.DecisionGrade` and `export_runtime_openapi_schema()`.
- Produces: one `DecisionGrade` OpenAPI component and exactly one `$ref` from `AuthorityBoundary.properties.decision_grade`.

- [ ] **Step 1: Write the failing owner/OpenAPI semantic test**

Add a focused test that derives the owner values from the public alias, asserts the named component has exactly those values, walks the complete live schema for `#/components/schemas/DecisionGrade`, and requires the sole reference path to be `AuthorityBoundary.properties.decision_grade.anyOf[0]`.

- [ ] **Step 2: Run the focused test and verify RED**

Run only the new pytest node. Expected failure: the live schema has no `DecisionGrade` component.

- [ ] **Step 3: Make the smallest owner change**

Change only the existing declaration from `DecisionGrade = Literal[...]` to `type DecisionGrade = Literal[...]`; preserve all four strings, ordering, uses, and facade exports.

- [ ] **Step 4: Run the focused test and verify GREEN**

The owner-derived component values must match and the complete reference count must equal one.

### Task 3: Regenerate all registered surfaces and prove wire-value preservation

**Files:**
- Regenerate: `schemas/runtime_api_v1.openapi.json`
- Regenerate: `packages/runtime-api-client/types.ts`
- Regenerate: `packages/runtime-api-client/runtimeApiClient.ts`
- Regenerate: `packages/runtime-api-client/runtimeApiClient.js`
- Regenerate: `packages/runtime-api-client/canonicalRuntimeApiClient.ts`
- Regenerate: `packages/runtime-api-client/canonicalRuntimeApiClient.js`
- Regenerate: `apps/runtime-dashboard/src/api/types.ts`
- Modify: `packages/runtime-api-client/runtimeApiClient.type-test.ts`

**Interfaces:**
- Consumes: the named live OpenAPI alias.
- Produces: raw, canonical, JavaScript, and dashboard generated outputs owned by the registry.

- [ ] **Step 1: Run the OpenAPI generator**

Run the exact `runtime-openapi-snapshot` generator from `architecture/generated_artifacts.toml`.

- [ ] **Step 2: Run the runtime-client generator**

Run `corepack pnpm --filter @polisyos/runtime-api-client run generate` exactly as registered.

- [ ] **Step 3: Run the dashboard-types generator**

Run `corepack pnpm --filter @polisyos/runtime-dashboard run generate:api` exactly as registered.

- [ ] **Step 4: Assert the generated-path stop rule**

Compare the changed-path set to the seven registered outputs plus the deliberate source/test/plan files. Stop on any other path.

- [ ] **Step 5: Test the wire migration against the pre-change snapshot**

Run a JSON semantic comparison between base `0413953e25a9efbba1521022156be3138dd855f6:schemas/runtime_api_v1.openapi.json` and the regenerated snapshot. Resolve the pre-change inline enum and post-change `$ref`; require byte-identical ordered values. Compare every pre-existing component's recursively reachable enum/const value multiset and require equality. Require 526 old components, 527 new components, and exactly one `DecisionGrade` reference.

- [ ] **Step 6: Add raw/canonical generated type equality**

Extend `runtimeApiClient.type-test.ts` with `Assert<Equal<DecisionGrade, RuntimeApiComponents["schemas"]["DecisionGrade"]>>`, importing the generated canonical alias and raw component interface. This fails compilation if canonicalization stops exporting the generated type.

- [ ] **Step 7: Assert vocabulary separation and after census**

Scan the complete seven-path denominator separately for `DecisionGrade`, `CgfDisposition`, and `CacheAge`. Stop unless `DecisionGrade` is present and both excluded names remain at zero.

### Task 4: Bind the DS4 waist with independent compile-time and runtime proofs

**Files:**
- Modify: `apps/runtime-dashboard/src/shared/ui/compounds/decisionGradePresentation.ts`
- Modify: `apps/runtime-dashboard/src/shared/ui/compounds/decisionGradePresentation.test.ts`

**Interfaces:**
- Consumes: generated package-root `DecisionGrade` and dashboard-local generated components.
- Produces: recognized presentation for owner grades and fail-open unrecognized presentation for opaque future values.

- [ ] **Step 1: Write failing runtime and type tests**

Add one test that expects `unsupported` to return `{ classification: "recognized", ownerLabel: "unsupported" }`, one that passes `future-owner-grade` and requires `{ classification: "unrecognized", ownerLabel: "future-owner-grade" }`, and type assertions that the recognized branch's `ownerLabel` is the package-generated `DecisionGrade` and equals the dashboard-generated component type.

- [ ] **Step 2: Write the no-second-copy falsifier**

Derive the owner strings from the generated OpenAPI component, parse every TS/TSX source under `apps/runtime-dashboard/src`, and reject a hand-written all-value union or vocabulary constant. Permit exactly one private, non-exported exhaustive presentation record in `decisionGradePresentation.ts`; add adversarial in-memory union and exported-constant sources and prove the scanner reports both.

- [ ] **Step 3: Run the targeted Vitest file and verify RED**

Expected failures: known owner grade remains `unrecognized`, recognized branch is absent, and the approved exhaustive record is absent.

- [ ] **Step 4: Implement the minimal presentation binding**

Import generated `DecisionGrade`; add one private object literal checked with `satisfies Record<DecisionGrade, DecisionGrade>`; add a real `hasOwn`-based runtime type guard; return the recognized discriminated branch only for present keys and retain the existing trimmed-label unrecognized branch for every other runtime value.

- [ ] **Step 5: Run the targeted Vitest file and both TypeScript typechecks**

Run the waist test, runtime-client typecheck, and dashboard typecheck. The Record proves compile-time exhaustiveness; the novel string test independently proves runtime fail-open behavior.

### Task 5: Verification loop one and coherent implementation commit

**Files:**
- All Task 2–4 source, test, and generated files.

**Interfaces:**
- Consumes: integrated working tree.
- Produces: a verified source/generated commit.

- [ ] **Step 1: Run each declared family verifier**

Run the OpenAPI verifier with `--skip-client-drift`, the full runtime-client verifier, and the dashboard registered replay/diff check.

- [ ] **Step 2: Run targeted Python and TypeScript tests**

Run the focused OpenAPI pytest node, relevant generated-client hardening nodes, the package type-test/typecheck, and the waist Vitest file.

- [ ] **Step 3: Run static and architecture checks**

Run Ruff on changed Python, `git diff --check`, architecture guardrails, and both carried baselines. Require debt ledger exit 0 with zero blocking; record docs lifecycle exit 1 with exactly six findings.

- [ ] **Step 4: Re-run all four condition tests**

Repeat wire semantic comparison, runtime unknown test, no-second-copy falsifier, and exact one-reference blast-radius count against the frozen integrated source.

- [ ] **Step 5: Review the complete diff and commit**

Verify only allowed paths changed, branch attachment is intact, then commit the source, tests, and seven regenerated outputs together. Re-read the commit from the branch.

### Task 6: Independent review, loop two, journal, and journal commit

**Files:**
- Create: `docs/superpowers/journals/2026-09-02-ds4-decision-grade-regeneration.md`

**Interfaces:**
- Consumes: the frozen implementation commit and all command receipts.
- Produces: an append-only closure journal with exact architect transcription prose.

- [ ] **Step 1: Request an independent diff review**

Give a fresh reviewer the exact DS4 requirements, base/head SHAs, stop rules, and four conditions. Classify findings under P40 and make no unrelated repairs.

- [ ] **Step 2: Apply only blocking DS4 findings and rerun impacted checks**

If the source changes, batch the required repair and refresh the implementation commit without rewriting earlier history.

- [ ] **Step 3: Run verification loop two from the final source**

Repeat every declared verifier, focused test/typecheck, wire semantic comparison, separation census, architecture guardrails, carried baselines, diff/path checks, and failure-register closeout pass.

- [ ] **Step 4: Write the append-only journal**

Record the exact seven-path before/after census, file-type/line/byte denominator, vocabulary ruling and `ValuePromotionDecisionGrade` distinction, generator commands/output, hook receipt, positive control, four-condition evidence, one-reference blast radius, verification exits, capability state transition, and exact append-only `ds4-waist-decision-grade` prose.

- [ ] **Step 5: Verify and commit the journal separately**

Run documentation/static checks appropriate to the journal, verify branch attachment, commit only the journal, and re-read both commits from the attached branch.

