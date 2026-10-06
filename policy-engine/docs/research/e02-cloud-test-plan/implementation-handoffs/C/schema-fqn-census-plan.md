# Schema FQN Census and Consumer Verification Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan inline. Steps use checkbox syntax for tracking.

**Goal:** Produce bounded, reproducible DFK-01 evidence for LA-005, LA-006, LA-026, and LA-027 while preserving every unresolved compatibility surface and current canonical owner.

**Architecture:** Add a read-only, one-shot evidence producer for this handoff. Task 3 invokes it to enumerate Git-visible inputs, bind each explicitly read file, report exact Python and text/resource hits, and name dynamic/archive boundaries it cannot establish. It is not a recurring checker, CI gate, or registered product command; its non-test consumer is this machine handoff. Add one real Foundry executor consumer witness alongside the existing schema registry/evolution/migration behavior test; record owner decisions as `not_established` until a committed owner ruling exists.

**Tech Stack:** Python 3.14, `ast`, `tools.lib.fs` measured reads, pytest, existing `PureExecutor` and Data Forge schema APIs.

**Spec:** `docs/research/e02-cloud-test-plan/execution-prompts/continuation-2026-10-06/C.md`; `closure-decisions/C.md`, `coverage.json`, `semantic-decisions.md`, `verification-and-closeout.md`; `docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/DFK-01.md` and its LA_r09 source criteria.

## Global Constraints

- Base is `198076863e143dea9f89f02734b13d50dae3eed5`; keep the DFK findings at their typed held/partial states unless the exact acceptance evidence and owner decisions exist.
- Do not delete or rename any compatibility FQN, create a generator, add schema contracts, or duplicate canonical schema/mechanism logic.
- Keep `polisyos.data_forge.kernel.pipeline.schemas` as an identity-preserving alias and `GeneratedSchemaModule` compatibility-only.
- Do not edit `pyproject.toml`, `uv.lock`, shared HYG test files, catalog/DFI files, production data, or another worktree.
- Do not build or install archives until the parent releases the environment slot; report wheel/sdist membership as `UNRUN` until then.
- Treat the census as source evidence only: dynamic dispatch outside recognized syntax, external consumers, and built archive contents remain explicit limitations.

## Pattern Pass

- Relevant patterns: P06, P27, P29, P31, P32, P33, P35, P36, P37, P38, P41.
- Existing risks: compatibility imports can be mistaken for public support; a string/AST census can be mistaken for dynamic or external closure; the legacy Data Forge path is still named canonical in the active consolidation plan.
- Target pattern: one exact bounded census with measured inputs and denominators, real canonical consumer witnesses, and owner decisions kept distinct from code behavior.
- Missing labels remain `verification_missing` for LA-005/026/027 and `semantic_test_missing` for LA-006 until their criterion-specific evidence is complete.
- Acceptance signal: fresh census output binds the complete admitted file set, lists exact hits and unresolved classes, the real Foundry and Data Forge consumer selectors pass, archive results stay `UNRUN` if the slot is unavailable, and all four finding verdicts retain honest authority/status.

## Review Focus

- A checked-in resource or serialized name may use a different path spelling than a Python import; the byte census must include all enumerated file types.
- A dynamic loader may construct an FQN from runtime data; list unresolved nonliteral loader sites rather than inferring zero.
- Package configuration predicts inclusion but does not prove a wheel or sdist member list; distinguish those claims.
- A green compatibility import test proves importability, not supported ABI; the relevant owner ruling remains separate.
- The Foundry witness must run a real canonical mechanism through `PureExecutor`, not only instantiate a class or test a shim.

---

### Task 1: Add the measured FQN census command

**Files:**
- Create `tools/quality/validation/schema_fqn_census.py`.
- Test in `tests/unit/remediation/test_dfk_01.py`.

- [x] Write tests for exact relative-import, serialized-name and resource-path hits, a nonliteral loader reported as unresolved, an ignored-only candidate input, an unreadable enumerated input, and a changed input changing both digest and match results.
- [x] Run those tests first and confirm they fail at the absent census command.
- [x] Implement the smallest CLI using Git's tracked, nonignored-untracked, and ignored path queries plus `measure_file_reads` / `measured_read_bytes`; keep Git/subprocess and dynamic-import limits explicit in the output.
- [x] Re-run the focused tests and inspect every output field on a fixture; run a full local text-input census to measure its denominator and findings.

### Task 2: Exercise canonical Foundry and Data Forge consumers

**Files:**
- Modify `tests/unit/remediation/test_dfk_01.py` only.

- [x] Add a real `PureExecutor.run` witness using canonical `TaxationMechanism` and an independently calculated fixed-rate result.
- [x] Compare the full canonical Foundry runtime registry to an independent ID/class-path fixture; resolve every registered runtime class and dispatch a mechanism through `MethodDispatcher`.
- [x] Assert exact tombstone FQN import failure and absence of the source-package resource; never recreate it in product source.
- [x] Run DFK schema/evolution/migration, the registry/runner witness, and real agent-sim mechanism/world consumer selectors (30 passed).
- [ ] The existing unified Foundry runtime consumer selector was run in the combined suite (33 passed, 1 failed): `test_simulation_methods_dispatch_and_agent_sim_bridge_runs` expects `not_available`, while the runtime returns `diagnostic_attached`. Its test and Foundry source inputs are unchanged from the slice base, but an exact base replay was unavailable under the one-worktree lease; classify this failure `not_established` under P41 and leave that separate consumer assertion untouched.
- [x] Do not add a registry, DTO migration, generator, or alias retirement to make the tests pass.

### Task 3: Record the census and four separate verdicts

**Files:**
- Create `docs/research/e02-cloud-test-plan/implementation-handoffs/C/schema-fqn-census-handoff.json` after the implementation commit.

- [ ] Run the source census at the exact implementation commit and retain the complete output separately if it is too large for the tracked receipt.
- [ ] Record the build configuration and leave built wheel/sdist results `UNRUN` until an authorized environment slot is available.
- [ ] Include each finding’s source criteria, exact owner role and unresolved Git-backed decision, measured evidence, missing input, capability label, and independent finding verdict.
- [ ] Re-read the receipt from the branch after writing it; commit it separately from implementation.

## Verification

Run the focused DFK and canonical consumer tests with the original read-only environment and this worktree on `PYTHONPATH`. Run Ruff and the relevant architecture/import guardrails. Do not run the full DFK archive-building command or any install/build operation until the parent releases the environment slot.
