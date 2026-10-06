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
- [x] Test and include the repository's present text/resource suffixes and no-suffix configuration names, including owner TSV, policy, serialized `.blob`, log, CSS, templates, patches, Cypher, fixtures, and `.env.example`; prove each selected input contributes the expected FQN/resource evidence.
- [x] Re-run the focused tests and inspect every output field on a fixture.
- [x] Run the complete census at implementation `8ac2c232445eb78b1689fe2f6fb5e1830ccd5b35`: 13,604 selected UTF-8 inputs / 13,672 tracked paths, 0 untracked, 979 ignored, 0 unreadable/unsupported, 68 excluded known binaries, and 876 loader sites (559 literal / 317 unresolved). FQN/text/resource hit counts: LA-005 147, LA-006 21, LA-026 125, LA-027 157. Full output: `raw/schema-fqn-census-final.json@1bb60dcf846b8c1fd702ecf3099c7094a8be648c437b9eca6c0b988ade4602c8`.

### Task 2: Exercise canonical Foundry and Data Forge consumers

**Files:**
- Modify `tests/unit/remediation/test_dfk_01.py` only.

- [x] Add a real `PureExecutor.run` witness using canonical `TaxationMechanism` and an independently calculated fixed-rate result.
- [x] Compare the full canonical Foundry runtime registry to an independent ID/class-path fixture; resolve every registered runtime class and dispatch a mechanism through `MethodDispatcher`.
- [x] Assert exact tombstone FQN import failure and absence of the source-package resource; never recreate it in product source.
- [x] Run DFK schema/evolution/migration, the registry/runner witness, and real agent-sim mechanism/world consumer selectors (31 passed).
- [ ] The exact frozen-commit combined selector run collected 52 tests (50 passed, 2 failed). The unified Foundry consumer `test_simulation_methods_dispatch_and_agent_sim_bridge_runs` expects `not_available`, while runtime returns `diagnostic_attached`; exact base replay is unavailable under the one-worktree lease, so P41 provenance is `not_established`.
- [ ] Phase-8 and Foundry hygiene companions collected 17 tests (16 passed, 1 failed): `test_phase8_fabric_and_foundry_use_data_forge_read_api_only` finds `literature_prior.py` importing `polisyos.data_forge.domains.academic.knowledge.skg_query`. This path is outside the DFK write set; exact base replay is unavailable, so P41 provenance is `not_established`.
- [x] Do not add a registry, DTO migration, generator, or alias retirement to make the tests pass.

### Task 3: Record the census and four separate verdicts

**Files:**
- Create `docs/research/e02-cloud-test-plan/implementation-handoffs/C/schema-fqn-census-handoff.json` after the implementation commit.

- [x] Run the source census at the exact implementation commit and retain the complete output separately at the cited ignored `raw/` path.
- [x] Record build configuration (`hatchling>=1.27.0`, wheel `src/polisyos` + `tools`; source bytes include `pyproject.toml`/`hatch.toml`) and leave wheel/sdist `UNRUN` for the parent-owned archive slot.
- [x] Include each finding's source criteria, exact owner role and unresolved Git-backed decision, measured evidence, missing input, capability label, and independent finding verdict in `schema-fqn-census-handoff.json`.
- [x] Re-read the receipt from the branch after writing it; commit it separately from implementation.

## Verification

Focused DFK/schema/agent-simulator selectors pass 31/31 on the frozen implementation SHA; full selected consumer suite and companion outcomes are listed above. Ruff and `git diff --check` pass. Architecture guardrails ran at the frozen SHA and exited 2 with 151 deep-import findings plus generated OpenAPI and trust-claim snapshot drift; complete output is `raw/architecture-guardrails-final.log@57a1107531375bdae7f78efa9cc2c595b8b4873ea882beeb0a1f42ed0cd05deb`. A slice-base replay is unavailable, so P41 source attribution stays `not_established`. Do not run the full DFK archive-building command or any install/build operation until the parent releases the environment slot.
