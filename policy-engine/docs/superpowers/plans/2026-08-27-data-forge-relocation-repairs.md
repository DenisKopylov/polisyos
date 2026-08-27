# DataForge Relocation Repairs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the four review findings, finish as many of DataForge rows 3–8 as the 8-round ceiling permits, and restore the release guardrail with an enumerated baseline transaction.

**Architecture:** Freeze producer bytes into the existing CAS before any consumer parses them, keep D4 policy authority in Scientist, and make Foundry method contracts durable and explicitly selectable. Relocate the remaining consumers by capability seam, then freeze and enumerate the resulting deep-import graph rather than synchronizing it blindly.

**Tech Stack:** Python 3.14, Pydantic, pandas, `FileSystemCAS`, pytest, Ruff, PolicyOS architecture validators.

**Spec:** `docs/superpowers/specs/2026-08-27-data-forge-relocation-repairs.md`

## Global Constraints

- Work only on attached branch `codex/import-relocate-data-forge`; no push, merge, or rebase.
- Never run `guardrails sync`.
- Continue the widening ledger from 4; hard stop at 8.
- Repairs have priority and consume no new round unless they create a genuinely new authority-bearing seam.
- Use targeted tests only; no full pytest run.
- Run `git rev-parse --show-prefix` before reporting path coordinates.
- Read direct command exit codes before processing output.
- Time measured validators with `user + sys` and an `uptime` pair.
- Derive all set-level counts twice and preserve disagreement.

---

### Task 1: Immutable Ukraine stage snapshots

**Files:**
- Modify: `src/polisyos/data_forge/read_api/ukraine.py`
- Modify: `tests/unit/data_forge/read_api/test_ukraine_stage_artifacts.py`
- Modify: `src/polisyos/foundry/data_plane/bindings.py`
- Modify: `tests/unit/foundry/data_plane/test_bindings_multiscale.py`

**Interfaces:**
- Consumes: `FileSystemCAS.put_bytes(data: bytes, opts: PutOptions) -> ArtifactRef` and `get_bytes(artifact_id) -> bytes`.
- Produces: `load_verified_stage_artifacts(manifest_path, *, store, allowed_root, expected_stage, required_outputs) -> VerifiedUkraineStageArtifacts`; each output carries `content_ref: ArtifactRef` and audit-only `source_path`; the receipt carries `manifest_ref: ArtifactRef`.
- Produces: `load_verified_stage_output_bytes(store, receipt, output_name) -> bytes` as the sole consumer read path.

- [ ] **Step 1: Write failing intake tests**

Add tests that mutate a source output after admission and assert the immutable
bytes remain available through `load_verified_stage_output_bytes`; assert a
manifest/output hash mismatch still fails before a receipt is returned.

- [ ] **Step 2: Run the focused read-api tests and observe RED**

Run `.venv/bin/python -m pytest tests/unit/data_forge/read_api/test_ukraine_stage_artifacts.py -q`.
Expected failure: the current receipt has no CAS refs and reopens the source path.

- [ ] **Step 3: Implement single-read snapshot admission**

Read manifest bytes once, validate with `BuildRunManifest.model_validate_json`,
read each output once, compare `len(bytes)` and `sha256(bytes)` to the manifest,
and persist exactly those bytes. Keep source paths only for audit display.

- [ ] **Step 4: Make Foundry parse snapshot bytes**

Replace `Path(output.path).read_text()` with the shared snapshot-byte reader.
Use `json.loads(bytes)` and retain strict object validation.

- [ ] **Step 5: Run focused read-api and Foundry tests GREEN**

Run `.venv/bin/python -m pytest tests/unit/data_forge/read_api/test_ukraine_stage_artifacts.py tests/unit/foundry/data_plane/test_bindings_multiscale.py -q`.

- [ ] **Step 6: Commit with ledger 4/8**

Commit message: `fix(data-forge): freeze verified stage bytes in CAS`.

### Task 2: Remove producer authority from D4

**Files:**
- Modify: `src/polisyos/data_forge/domains/ukraine/builders/calibration.py`
- Modify: `src/polisyos/data_forge/domains/ukraine/builders/sources.py`
- Modify: `src/polisyos/data_forge/domains/ukraine/models.py`
- Modify: `src/polisyos/scientist/governance/blueprint_release.py`
- Modify: `tests/unit/data_forge/domains/ukraine/test_builders.py`
- Modify: `tests/unit/scientist/governance/test_blueprint_release.py`

**Interfaces:**
- Consumes: immutable receipts and snapshot-byte reader from Task 1.
- Produces: routing-only `_UkraineD4GovernanceRequest`; Scientist constant `_UKRAINE_D4_COVERAGE_THRESHOLD = 0.95`; no producer waiver path.
- Produces: raw identity-cohort rows `{cohort, raw_identity}` and Scientist recomputation against `agent_registry_runtime.parquet`.

- [ ] **Step 1: Write authority falsifiers**

Add tests for: a producer waiver flip under a constant receipt/hash witness;
all-true producer `resolved` flags; household rows with no verifier-grade
coverage/identification evidence; and post-admission JSON/parquet mutation.
Each test must fail against the current positive-signoff path.

- [ ] **Step 2: Run the D4 tests and observe RED**

Run `.venv/bin/python -m pytest tests/unit/scientist/governance/test_blueprint_release.py tests/unit/data_forge/domains/ukraine/test_builders.py -q`.

- [ ] **Step 3: Narrow the producer request and cohort**

Remove `coverage_threshold`, `waived_signoff_families`, and `resolved` from
producer-authored governance inputs. Keep only fixed routing/schema fields.

- [ ] **Step 4: Implement Scientist-owned conservative predicates**

Read all inputs from CAS snapshots. Recompute exact identity membership from
raw cohort identities and the immutable registry. Project household rows as
`BOUNDS_ONLY`, `EXPLORATORY`, zero asserted coverage, and bias-unvalidated.
Apply 0.95 with no waivers and fail closed before calibration promotion.

- [ ] **Step 5: Run the D4 tests GREEN**

Run the same focused command and verify the constant-hash waiver falsifier and
household block both pass.

- [ ] **Step 6: Commit with ledger 4/8**

Commit message: `fix(scientist): remove producer authority from D4 signoff`.

### Task 3: Orchestrate the 13 Foundry method inputs

**Files:**
- Modify: `src/polisyos/foundry/data_plane/bindings.py`
- Modify: `src/polisyos/foundry/data_plane/__init__.py`
- Modify: `src/polisyos/scientist/nodes/builtins/data/bind_foundry_inputs.py`
- Modify: `src/polisyos/scientist/nodes/builtins/state_keys.py`
- Modify: `src/polisyos/scientist/orchestration/workflows/causal_full.py`
- Modify: `src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py`
- Modify: `tests/unit/foundry/data_plane/test_bindings_multiscale.py`
- Modify: `tests/unit/scientist/nodes/test_bind_foundry_inputs_node.py`
- Modify: `tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py`

**Interfaces:**
- Produces: a strict method-input bundle mapping all 13 stable keys to `{contract_id, artifact_ref, stage_receipt_ref}`.
- Consumes: explicit `params.ukraine_foundry_method_selection = {"contract_key": str, "method_fqn": str}`; absence means no execution and never chooses a default.
- Produces: execution result/evidence refs whose authority purpose is execution-only and which are rejected when supplied as method-validity or governance evidence.

- [ ] **Step 1: Write failing persistence, selection, and authority tests**

Assert all 13 refs resolve from CAS; missing selection performs no method run;
unknown key and contract-incompatible method fail; `d2_panel_observational`
reaches the real causal-evaluation path; and execution evidence cannot satisfy a
validity-evidence intake.

- [ ] **Step 2: Run the three focused test files and observe RED**

Run `.venv/bin/python -m pytest tests/unit/foundry/data_plane/test_bindings_multiscale.py tests/unit/scientist/nodes/test_bind_foundry_inputs_node.py tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py -q`.

- [ ] **Step 3: Persist the typed bundle and route explicit selection**

Persist each validated DTO with its stage snapshot lineage, then persist the
bundle. Transport its ref through `ExperimentState`. Require exact selection,
verify the selected contract ID against the registered method signature, and
invoke the existing backend without promoting the result.

- [ ] **Step 4: Connect the exercised panel consumer**

Set `observational_data_ref` only for explicit
`d2_panel_observational` selection and order `run_causal_evaluation` after
`bind_foundry_inputs` in the causal workflow. Pass both method-input and intake
receipt refs into execution lineage.

- [ ] **Step 5: Run focused tests GREEN**

Run the same three files and verify all 13 durable refs plus the one real
workflow consumer.

- [ ] **Step 6: Commit with ledger 4/8**

Commit message: `fix(foundry): orchestrate verified method inputs`.

### Task 4: Close shared legal compatibility and record residual states

**Files:**
- Modify: `_build/.tmp/import-relocate-data-forge/phase1-classification.md`
- Modify: `src/polisyos/lex/artifacts.py`
- Modify: `src/polisyos/lex/errors.py`
- Modify: `src/polisyos/lex/types.py`
- Modify: `src/polisyos/lex/api.py`
- Modify: `src/polisyos/lex/__init__.py`
- Modify: `tests/unit/data_forge/legal_batch/test_lex_shared_contract_relocation.py`
- Modify: `tests/unit/lex/mirror_contracts/test_api.py`
- Modify: `tests/unit/lex/mirror_contracts/test_artifacts.py`
- Modify: `tests/unit/lex/mirror_contracts/test_errors.py`
- Modify: `tests/unit/lex/mirror_contracts/test_types.py`
- Modify: `tests/unit/lex/test_common.py`
- Create: `docs/superpowers/journals/2026-08-27-data-forge-relocation-repairs.md`

**Interfaces:**
- Keeps: `latest_object_by_subject` in `polisyos.common.timestamps` with no production edit.
- Produces: Lex-owned runtime errors/readers/read-side DTOs and explicit adapters from DataForge read results.
- Records: 13 contract states, exactly one `exercised_workflow_consumer` and twelve `selectable_unselected/consumer_missing` unless tests establish more.

- [ ] **Step 1: Write failing compatibility tests**

Assert Lex runtime readers/errors/types have no import-time dependency on
`polisyos.data_forge.kernel.artifacts` or
`polisyos.data_forge.domains.legal.contracts`, while active-version behavior is
preserved through the explicit adapter.

- [ ] **Step 2: Run focused Lex/DataForge tests and observe RED**

Run `.venv/bin/python -m pytest tests/unit/data_forge/legal_batch/test_lex_shared_contract_relocation.py tests/unit/lex/mirror_contracts/test_api.py tests/unit/lex/mirror_contracts/test_artifacts.py tests/unit/lex/mirror_contracts/test_errors.py tests/unit/lex/mirror_contracts/test_types.py tests/unit/lex/test_common.py -q`.

- [ ] **Step 3: Remove compatibility edges and amend row 21**

Implement Lex-local runtime contracts/readers/errors. Convert DataForge
active-version results explicitly in `lex.api`. Amend the frozen receipt to
name Common as the measured owner and list all three consumers.

- [ ] **Step 4: Write the execution journal**

Record ledger 4/8, the 13 per-contract states, the inherited Ruff comparison,
the row-21 amendment, and every red/green receipt produced so far.

- [ ] **Step 5: Run the named tests GREEN and recompute package edges**

Verify both compatibility edges are absent from the package-boundary finding
keys without claiming the full package gate passes.

- [ ] **Step 6: Commit with ledger 4/8**

Commit message: `fix(architecture): close legal compatibility edges`.

### Task 5: Round 5 — relocate claim adjudication

**Files:**
- Modify: `src/polisyos/data_forge/domains/academic/batch/claim_adjudicator.py`
- Modify: `src/polisyos/data_forge/domains/academic/batch/pipeline.py`
- Create: `src/polisyos/scientist/methods/autotune/claim_adjudication_runtime.py`
- Modify: `tests/unit/data_forge/domains/academic/batch/test_claim_adjudicator.py`
- Modify: `tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_autotune.py`
- Create: `tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py`

**Interfaces:**
- DataForge produces raw claim rows and immutable artifact references.
- Scientist consumes admitted config/champion provenance and produces the adjudication result; an unadmitted config cannot set `publishable_edge`.

- [x] **Step 1: Write a failing end-to-end ownership test**
- [x] **Step 2: Run `.venv/bin/python -m pytest tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py tests/unit/data_forge/domains/academic/batch/test_claim_adjudicator.py tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_autotune.py -q` RED because DataForge still executes Scientist policy**
- [x] **Step 3: Move the consumer stage above DataForge without copying policy down**
- [x] **Step 4: Run the same focused claim-adjudication files GREEN**
- [x] **Step 5: Commit and print ledger 5/8**

Commit message: `feat(scientist): own claim adjudication runtime`.

### Task 6: Round 6 — relocate the Lex semantic benchmark

**Files:**
- Modify: `src/polisyos/data_forge/domains/legal/batch/benchmark.py`
- Create: `src/polisyos/lex/benchmark.py`
- Modify: `tests/unit/data_forge/legal_batch/test_benchmark.py`
- Create: `tests/unit/lex/test_benchmark.py`

**Interfaces:**
- DataForge supplies benchmark fixtures/artifact refs.
- Lex owns `NormPackBuildRequest`, `assemble_norm_pack`, graph search, and transport-constraint execution for rows 4–6.

- [x] **Step 1: Write failing Lex semantic benchmark tests**
- [x] **Step 2: Run `.venv/bin/python -m pytest tests/unit/lex/test_benchmark.py tests/unit/data_forge/legal_batch/test_benchmark.py -q` RED against the DataForge-owned consumer**
- [x] **Step 3: Move the semantic consumer to Lex and preserve persisted outputs**
- [x] **Step 4: Run the same focused files GREEN**
- [x] **Step 5: Commit and print ledger 6/8**

Commit message: `feat(lex): own legal semantic benchmark`.

### Task 7: Round 7 — relocate Scientist retrieval evaluation

**Files:**
- Modify: `src/polisyos/data_forge/domains/legal/batch/benchmark.py`
- Create: `src/polisyos/scientist/agent/knowledge_benchmark.py`
- Modify: `tests/unit/data_forge/legal_batch/test_benchmark.py`
- Create: `tests/unit/scientist/agent/test_knowledge_benchmark.py`

**Interfaces:**
- Consumes DataForge fixture refs and the Lex semantic report.
- Produces a diagnostic retrieval report with `may_not_use_for` legal admissibility or publication.

- [ ] **Step 1: Write a mixed-outcome falsifier**

Prove a high retrieval score cannot turn a failed NormPack/transport result
green.

- [ ] **Step 2: Run `.venv/bin/python -m pytest tests/unit/scientist/agent/test_knowledge_benchmark.py tests/unit/data_forge/legal_batch/test_benchmark.py -q` RED against the combined DataForge benchmark**
- [ ] **Step 3: Move the `KnowledgeToolkit` consumer to Scientist**
- [ ] **Step 4: Run the same focused files GREEN**
- [ ] **Step 5: Commit and print ledger 7/8**

Commit message: `feat(scientist): own legal retrieval benchmark`.

### Task 8: Round 8 — relocate the Lex search CLI

**Files:**
- Modify: `src/polisyos/data_forge/domains/legal/batch/cli.py`
- Create: `src/polisyos/lex/knowledge/cli.py`
- Modify: `tests/unit/data_forge/legal_batch/test_cli_smoke.py`
- Create: `tests/unit/lex/knowledge/test_cli.py`

**Interfaces:**
- Lex owns direct `LegalKnowledgeStore` search.
- DataForge CLI no longer imports or substitutes the Lex runtime store.

- [ ] **Step 1: Write failing CLI ownership/behavior tests**
- [ ] **Step 2: Run `.venv/bin/python -m pytest tests/unit/lex/knowledge/test_cli.py tests/unit/data_forge/legal_batch/test_cli_smoke.py -q` RED against the DataForge command**
- [ ] **Step 3: Move the command to Lex without a DataForge read-api substitute**
- [ ] **Step 4: Run the same focused files GREEN**
- [ ] **Step 5: Commit and print ledger 8/8**

Commit message: `feat(lex): own legal search command`.

### Task 9: Enumerated baseline, registrations, and final verification

**Files:**
- Modify: `architecture/baselines/imports/deep_import.json`
- Modify: `docs/plans/active/DEBT-REGISTER.md`
- Modify: `docs/plans/active/LEDGER.md`
- Modify: `docs/superpowers/journals/2026-08-27-data-forge-relocation-repairs.md`

**Interfaces:**
- Consumes: source-frozen canonical and independent deep-import edge sets.
- Produces: exact baseline additions/removals and executed closure signals for all three registrations.

- [ ] **Step 1: Freeze source and run both deep-import derivations**

Record additions and removals separately. For each addition, name the original
statement or round; cite the three Round-3 Scientist edges individually.

- [ ] **Step 2: Execute closure signals before writing register rows**

Execute strict predicates for the Fabric facade conflict, the 13-contract
residual inventory, and the inherited Ruff identity comparison evidence.

- [ ] **Step 3: Patch the baseline explicitly**

Use `apply_patch` against individually enumerated edge blocks. Do not invoke a
renderer or sync command to overwrite the file.

- [ ] **Step 4: Write register and ledger rows**

Register the Fabric enforced-predicate contradiction with the architect-created
witness and executable closure signal; register the twelve per-contract
residuals; record Ruff as inherited evidence rather than repair debt.

- [ ] **Step 5: Run targeted blast-radius tests and Ruff**

Run the exact focused files named in Tasks 1–8 plus `.venv/bin/python -m ruff
check` over `git diff --name-only 9300a06e9 -- 'src/**/*.py' 'tests/**/*.py'`.
Preserve inherited diagnostics separately.

- [ ] **Step 6: Run the three final predicates separately**

Run the source import linter, release guardrail, and package-import gate with
direct exit capture, measured CPU time, and uptime pairs. Independently derive
each set count and report any disagreement.

- [ ] **Step 7: Verify the release guardrail exits 0**

If any edge resists, stop and name it with its trace instead of committing a
red baseline narrative.

- [ ] **Step 8: Commit records/baseline with ledger 8/8 and re-read branch**

Commit message: `chore(architecture): ratify relocation import baseline`.
