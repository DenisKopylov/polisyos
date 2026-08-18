# GY-DEFC-9 N11 Suffix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the frozen N8/N10a family verifiable across ambient plugin-import postures, bind the current deployment closure, and complete one cold N11 live-contract validation with zero issues.

**Architecture:** Foundry retains the full method-catalog provenance manifest and its custody identity, and additionally owns a fail-closed governed comparison projection derived from the manifest's structural admission. N8 returns a typed split between governing issues and ambient findings; N10a consumes only the governing subset for its bridge decision while N8 continues to report ambient evidence. The frozen N8 and N10a artifacts remain byte-identical; the confidence ledger alone is reissued through its canonical writer after an exact pre-write declaration.

**Tech Stack:** Python 3.14, dataclasses and typed mappings, pytest, canonical PolicyOS validation CLIs, ordinary local git.

**Spec:** `docs/plans/active/layer3-slices/GY-engine-subordination.md` entries `GY-DEF14`, `GY-DEF16`, and `GY-DEFC-9`; execution journal `docs/superpowers/journals/2026-08-18-gy-defc-9-n11-suffix.md`.

## Global Constraints

- Work only in `/Users/deniskopylov/polisyos/.worktrees/gy-defc-9` on attached branch `codex/gy-defc-9-n11-suffix`; do not move the root worktree's HEAD.
- Local git only: no GitHub plugin, PR, push, merge of `main`, rebase, force-push, or stash-as-storage.
- Root is the only tracked-file editor and the only agent allowed to launch a process over 60 seconds; read-only subagents use terra or luna only.
- Verify branch attachment before every commit and stage explicit paths, never `git add -A`.
- Items 1 and 2 ship together. N8 and N10a governed artifacts remain byte-identical; only the confidence-ledger artifact may be reissued.
- The confidence accepted writer runs only after Items 1–3 are green and an exact candidate delta is committed. The single cold N11 run runs only after Items 1–4 are green.
- A mechanism repair round is consumed only by an independent Blocking or Important mechanism finding. Each item has two rounds; a third finding preserves and stops that item after classifying the defect.
- Every set claim enumerates its full denominator and carries a `P37` label. A suffix defect the shared projection owner cannot name triggers the property stop.
- Do not edit line 7 or any `Rev` frontmatter in `GY-engine-subordination.md`; the architect owns that physical line.

## Measured P39 Path Set

Mechanism paths are counted; mandatory records are held outside the count.

1. `src/polisyos/foundry/methods/catalog/snapshot.py`
2. `tools/quality/validation/check_layer3_gy_value_gate_contract.py`
3. `tools/quality/validation/check_layer3_gy_second_domain_pack.py`
4. `tests/unit/foundry/methods/test_catalog_snapshot.py`
5. `tests/unit/runtime/quality/test_value_gate.py`
6. `tests/unit/runtime/quality/test_second_domain_pack.py`
7. `architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json`

Mandatory record companions are `docs/superpowers/plans/2026-08-18-gy-defc-9-n11-suffix.md`, `docs/superpowers/journals/2026-08-18-gy-defc-9-n11-suffix.md`, and the authorized standing paragraphs inside the three active-plan entries. If a real Depth-N witness requires a fourth test path, record that measured expansion rather than weakening the witness or splitting the mechanism.

## Pattern Pass

- `P31`: close the class by routing all N8 verification comparisons through one owner projection, including validation, full check, and rederive-audit comparisons.
- `P32`/`P37`: a non-governing disposition is admitted only by a structurally valid parent admission and row declaration; missing, malformed, duplicated, contradictory, or unknown declarations fail closed.
- `P38`: the property is governed provenance equivalence; raw full-payload equality is the current proxy. The divergent case is two environments with identical governed inputs and different plugin importability.
- `P29`/`P33`: exercise real discovery in two environments, then mutate a governed input and require its named failure. Hand-edited ambient JSON is only a unit probe and cannot satisfy the environment witness.
- `P39`: tests and the confidence artifact are mechanism cost; only the mandated plan/journal/standing records are companions.
- Capability state at entry: the projection owner is `verification_missing`; the N8 typed result and N10a bridge are `consumer_missing`; the real environment and Depth-N cases are `semantic_test_missing`. The acceptance signal moves all three to `implemented` without changing the frozen N8/N10a artifacts.

---

### Task 1: Freeze the registration and complete disposition

**Files:**
- Create: `docs/superpowers/plans/2026-08-18-gy-defc-9-n11-suffix.md`
- Create: `docs/superpowers/journals/2026-08-18-gy-defc-9-n11-suffix.md`
- Modify: `docs/plans/active/layer3-slices/GY-engine-subordination.md`

**Interfaces:**
- Consumes: frozen N8 `denominators.catalog_provenance`, live `_catalog_denominators_cached()`, and the five-code entry receipt.
- Produces: the per-code and complete 32-row predicate disposition, Item 3 ruling, P39 set, and repair-round ledger.

- [ ] **Step 1: Record the complete census before source edits**

  Record 32 recorded rows, 32 live rows, 32 unique names per side, zero non-mapping rows, and the single differing row `ambient.discovered_component_membership`. State that its evidence classification changes `not_established -> recomputed`, but its placement is established by `decisive:false` plus `quarantine` under a valid parent admission.

- [ ] **Step 2: Record the five-code disposition**

  Put the three ambient-block codes in `ambient_findings`; split `catalog_predicate_provenance_mismatch` row by row; treat `catalog_provenance_manifest_mismatch` only as a derived raw-identity consequence that must stop firing.

- [ ] **Step 3: Record Item 3's durable ruling**

  State inside `GY-DEF14` that the historical discriminator is `not_established`, post-hoc invention would be a forbidden rebaseline, ambient posture remains fully recorded diagnostic evidence, and ambient posture is no longer a replay prerequisite.

- [ ] **Step 4: Verify plan frontmatter preservation**

  Compare line 7 and the active-plan frontmatter byte-for-byte with `main`, then commit only the three record paths.

### Task 2: Add the Foundry governed projection with red-first tests

**Files:**
- Modify: `src/polisyos/foundry/methods/catalog/snapshot.py`
- Test: `tests/unit/foundry/methods/test_catalog_snapshot.py`

**Interfaces:**
- Consumes: a complete raw catalog-provenance mapping.
- Produces: `method_catalog_governed_provenance_projection(payload: Mapping[str, object]) -> dict[str, object]` and `method_catalog_governed_provenance_id(payload: Mapping[str, object]) -> str`.

- [ ] **Step 1: Write the failing projection tests**

  Add one test proving two manifests that differ only in ambient observations and a structurally non-decisive predicate classification have different raw `method_catalog_provenance_id` values but identical governed projection identities. Add fail-closed cases for missing/malformed parent admission and malformed/contradictory predicate rows. The production mutation each test catches is deletion or weakening of the structural admission guard.

- [ ] **Step 2: Run the focused test and verify RED**

  Run:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/foundry/methods/test_catalog_snapshot.py -q -k 'governed_provenance'`

  Expected: failure because the governed projection APIs do not exist.

- [ ] **Step 3: Implement the smallest owner projection**

  Preserve all governed discovery, ambient source policy, ambient admission, runtime identity, decisive predicate rows, predicate bindings, admission policy, and schema. Replace each valid non-decisive predicate row with its structural shell (`predicate`, `decisive`, `fail_closed_action`) and omit ambient observation values plus raw `provenance_id` from the comparison projection. Raise `MethodCatalogDiscoveryProvenanceError` for absent, malformed, duplicated, contradictory, or unknown admission structures.

- [ ] **Step 4: Run the focused test and verify GREEN**

  Re-run the Step 2 command and require zero failures.

### Task 3: Split N8 findings and route every comparison path

**Files:**
- Modify: `tools/quality/validation/check_layer3_gy_value_gate_contract.py`
- Test: `tests/unit/runtime/quality/test_value_gate.py`

**Interfaces:**
- Consumes: the Foundry governed projection and full raw custody manifest.
- Produces: frozen `ValueGateValidationResult` with `governing_issues` and `ambient_findings`; `validate_payload_result(payload)` returns it; backward-compatible `validate_payload(payload)` returns only `governing_issues`.

- [ ] **Step 1: Write failing typed-result and comparison-path tests**

  Exercise: the three ambient block codes; per-row predicate splitting; raw custody tampering; malformed admission; governed discovery mutation; `check`; and `run_rederive_audit`. Assert ambient-only differences are reported but do not invalidate governed equivalence, while the governed mutation retains its existing named code.

- [ ] **Step 2: Write the real two-environment failing witness**

  Construct two isolated discovery environments with the same example-extension distribution metadata. Point one editable distribution at a source tree containing the example module and the other at a source tree where that target is not importable. Run the real discovery/catalog provenance path in both; do not hand-edit the produced ambient manifests. Assert raw ambient custody differs, governed identity matches, and N8 governing issues are empty for both.

- [ ] **Step 3: Verify the new tests are RED for the intended reasons**

  Run the focused `test_value_gate.py` selection and require failures from the absent typed result/projection routing, not fixture setup.

- [ ] **Step 4: Implement the typed result and routing**

  Split issues by structural admission, never by code allowlist. Keep raw custody self-hash validation governing. Make CLI JSON include `ambient_findings` while returning exit 0 for ambient-only drift. Compare whole N8 payloads through a governed payload projection in `check` and `run_rederive_audit`; keep the frozen reissue authorization strict and unused.

- [ ] **Step 5: Verify focused N8 tests and the live N8 receipt**

  Require the focused tests green and `--check-catalog-provenance --output-format json` to exit 0 with the three ambient codes plus the one differing predicate row visible only under `ambient_findings`. Do not write the N8 artifact.

### Task 4: Make N10a consume the typed result and witness Depth-N

**Files:**
- Modify: `tools/quality/validation/check_layer3_gy_second_domain_pack.py`
- Test: `tests/unit/runtime/quality/test_second_domain_pack.py`

**Interfaces:**
- Consumes: `n8.validate_payload_result(payload)`.
- Produces: unchanged N10a evidence bytes when `governing_issues` is empty; governed failures still return `n8_value_contract_invalid` with governing codes.

- [ ] **Step 1: Write failing N10a bridge tests**

  Feed a real ambient-different N8 payload through `_n8_transport_gap_closure` and require `closed:true`; feed a governed-different payload and require `closed:false`, reason `n8_value_contract_invalid`, and the existing named code. The production mutation caught is restoring `if any_issue` instead of `if governing_issues`.

- [ ] **Step 2: Write the Depth-N-level ambient-green/governed-red witness**

  Invoke the Depth-N provenance-stability consumer, not merely the N8 wrapper, with the ambient and governed variants. Require no `n8:*` issue for ambient-only drift and the namespaced governed code for governed drift. If this cannot be exercised without a fourth mirrored test path, add `tests/unit/runtime/quality/test_depth_n_universality.py`, update P39 before committing, and do not claim inheritance by assertion.

- [ ] **Step 3: Verify both tests RED**

  Run the focused N10a/Depth selection and confirm the ambient case fails at the current undifferentiated N8 issue set while the governed case is already red with its named code.

- [ ] **Step 4: Implement the N10a consumer**

  Change `_n8_transport_gap_closure` to decide only from `result.governing_issues`; do not persist ambient findings into the frozen N10a receipt. Preserve all governed failure behavior.

- [ ] **Step 5: Verify Items 1–3 together and commit**

  Run the three focused test files, live N8 catalog check, live N10a `--check`, Depth-N witness, ruff on the three source paths and three test paths, and architecture guardrails. Confirm the N8 and N10a artifact SHA-256 values are unchanged, verify branch attachment, stage the six mechanism paths explicitly, and commit Items 1–3 together.

### Task 5: Independent mechanism review and repair rounds

**Files:**
- Modify only paths named by a valid review finding.
- Update: `docs/superpowers/journals/2026-08-18-gy-defc-9-n11-suffix.md`

**Interfaces:**
- Consumes: committed Items 1–3 mechanism and exact task requirements.
- Produces: independent review classification per item and remaining round counts.

- [ ] **Step 1: Request an independent read-only review**

  Provide base SHA, head SHA, the five-code disposition, all forbidden closures, and the real environment/Depth acceptance cases. Ask for Blocking, Important, or Minor findings with the affected item named.

- [ ] **Step 2: Apply the round rule**

  A Blocking or Important mechanism finding consumes one round for its item. Add a red regression test, fix it, rerun the affected wave, request delta review, and append a correction commit. A third such finding preserves and stops that item after classifying the defect.

- [ ] **Step 3: Freeze source after reviews**

  Once reviews are clear, record source freeze and do not run an expensive writer before all required mechanism review has landed.

### Task 6: Declare and reissue the deployment identity

**Files:**
- Modify: `architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json`
- Update: `docs/superpowers/journals/2026-08-18-gy-defc-9-n11-suffix.md`

**Interfaces:**
- Consumes: frozen confidence artifact, canonical candidate writer, current complete source closure and all governed pins.
- Produces: exact pre-write transition declaration, accepted canonical confidence artifact, and post-write audit.

- [ ] **Step 1: Generate a candidate outside governed paths**

  Run the canonical confidence writer to an ignored candidate path under the serialized heavy-lane regime and the recorded contention ceiling. Do not change the governed artifact.

- [ ] **Step 2: Enumerate and commit the exact declaration**

  Walk every JSON leaf in frozen and candidate artifacts; bind file identities, embedded identities, complete delta rows, source-scope denominator, all pins, protected movement set, and acceptance rule. State the `catalog.py` source hash transition and any new projection-owner source transition. Commit the journal declaration before the accepted writer.

- [ ] **Step 3: Run the accepted writer once**

  Verify branch attachment and clean source, then run `check_layer3_gy_confidence_ledger.py --write --output-format json` under the declared ceiling. Accept only byte equality with the candidate and exact equality with every declared leaf/pin/source-scope predicate.

- [ ] **Step 4: Verify and commit the confidence artifact**

  Run the canonical `--check`, inspect the complete observed delta, update the journal receipt, stage only the confidence artifact and journal, and commit. N8 and N10a artifact hashes must still equal their base hashes.

### Task 7: Spend the one cold N11 run and close out

**Files:**
- Update: `docs/superpowers/journals/2026-08-18-gy-defc-9-n11-suffix.md`
- Modify only the authorized standing paragraphs in `docs/plans/active/layer3-slices/GY-engine-subordination.md` if the terminal result requires a standing update.

**Interfaces:**
- Consumes: green Items 1–4 and the accepted confidence artifact.
- Produces: one cold N11 live-contract receipt with zero issues, or a classified property stop.

- [ ] **Step 1: Reconfirm the cold authorization predicates**

  Require N8 green with ambient findings visible, N10a green, governed negative red, Depth-N ambient-green/governed-red, confidence check green, source frozen, and no unreviewed mechanism change.

- [ ] **Step 2: Launch the cold run once**

  Run the canonical N11 cold live-contract validation serialized under the supplied `4,693.118600` second ceiling and the §3.5.7 contention allowance. A timeout with zero changed bytes is a non-receipt and does not spend the allowance.

- [ ] **Step 3: Record the terminal receipt**

  Record exact command, wall time, exit status, issue count, changed-byte outcome, and P37 provenance. If a new defect appears, classify whether the shared projection owner names it before deciding proceed versus stop.

- [ ] **Step 4: Run final verification and commit records**

  Re-run focused tests, N8, N10a, confidence check, ruff, architecture guardrails, line-7/frontmatter byte checks, branch attachment, explicit path diff, and base-to-head artifact hashes. Re-read the failure register, commit the final journal/standing update explicitly, and read the delivered branch back before reporting completion.
