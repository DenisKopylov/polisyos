# Local adoption context for G review

This packet records a candidate-band internal extension, not G acceptance. The author packet below is preserved verbatim from `LOCAL/raw/acquisition-cas-candidate-route-r2-20261020/decision-packet.md@08153b508c5046de577eea6449d120a8a47a418b85b89a3b475996af13f65da4`. Its statements “not applied” and “independent review NOT YET DONE” describe the original authoring time. Independent review subsequently returned bounded GO in `LOCAL/raw/acquisition-cas-candidate-independent-review-r2-d2d2-20261020/review.md@4b801146f9e58106189ee05cbd5677dcd3c117f22c505de4d32543c7a3ce54b0`.

The local candidate adoption is based on `624f9dee8a3cc1c13c899786d3de76bfe88d6b30` (tree `92b023259e7481e2fce27e476449b01e5314c22a`). Exact adopted bytes and resulting commit must be read from the separate implementation readback; no future receipt SHA is asserted here. Product verification on this composition remains UNRUN at this packet boundary. Downstream failures stay open until replay; neither a scope string nor same-CAS identity establishes protected authority. `G_acceptance=false`; `closure_ids=[]`.

---

# Acquisition candidate CAS route — decision packet (R2)

Status: **author proposal only; not applied and not a G closure**. No canonical source was written in this task. The patch is based on exact path blobs at `048880bf854cf58bfa33171a94556ee91424d8e9`; it applies cleanly to the later current candidate HEAD recorded in `manifest.json` because all four leased paths are unchanged. Root must rebind the patch against its current branch before application.

## Evidence and boundary

The complete actual whole acquisition-module replay is `root-acquisition-whole-a3f0cabf-20261020-r1/actual/result.json@c298cb2d9bc10d88923191da80cebe978b9a9d89052c2d928bfedcc023e3c4d3`. It collected/completed 16 tests: 2 passed, 14 failed, 0 errors, 0 skipped. All 14 failures had the same first boundary: `recursive_contract_testing_candidate_n9_owner_not_established` at `recursive_generation_cycle.py:3529`, before leaf N6 execution, including the real no-cost negative `test_default_wdi_cost_selection_is_absent_before_served_execution`. This is a whole-module execution receipt, not OOM: resource abort was null, sampled process-tree RSS peaked at 1,215,578,112 bytes, and minimum sampled free disk was 15,200,202,752 bytes. Full names and deciding outputs are retained in the cited result/cases files.

The helper already selects `RecursiveGenerationCycleController.for_contract_testing`, and its leaf factory supplies `authority_scope="contract_testing"` with the app CAS. The parent constructor already accepts a CAS. However, the context-free candidate parent-to-leaf guard requires the leaf to be `production`; `GenerationCycleController` rejects an explicit CAS for production scope unless a `PromotionRuntime` is supplied, while that same guard forbids a runtime. Thus the current predicate makes the canonical parent/leaf candidate route unreachable before the consumer behavior under test.

**Property vs implementation (P38):** the property is that a canonical contract-testing recursive parent may use its canonical contract-testing leaf when the same non-null CAS object is bound by both, without entering the protected N9 authority path. The code currently tests the leaf's scope string (`production`) as a proxy for an established owner. Divergent case: exact canonical parent and leaf, same candidate CAS, no promotion runtime, canonical N9 port, and no method overrides are rejected solely because the leaf is visibly contract-testing. The actual status of all downstream acquisition claims remains unverified until the entire integration route is rerun.

## Proposed choice

P40 class: second finding in the same parent/factory/leaf/CAS ownership-handshake class. Widen one shared mechanism and test its boundary; do not add per-case bypasses.

- **Reuse unchanged:** retain the current production leaf route. Insufficient: it still rejects the actual canonical candidate producer/consumer chain at the scope discriminator.
- **Extend existing (recommended):** keep the current exact runtime checks, but accept a contract-testing leaf only when the parent itself is contract-testing and `leaf._artifact_store is parent._artifact_store` for a non-null store. Bind the parent to the app CAS in `persist_wdi_route`. The patch keeps exact parent and leaf types, canonical N9 port type, no runtime, no run/promote overrides, and no N9 refusal-method override. It does not relax the production branch.
- **Consolidate:** no second route abstraction or duplicate owner handshake exists to merge; adding one would obscure the established factory/parent contract.
- **Build new:** a new candidate route API/runtime owner is unnecessary for this bounded path and would expand migration surface without resolving an additional owner fact.

Effects: no schema, wire, persisted-history, public API, legal, or external-authority change. Parent and child remain `contract_testing`; the child run is asserted synthetic, promotion stays `not_promoted`, and receipts remain empty. No law, custody, currentness, or production claim is created. Migration is limited to binding the existing app CAS at the helper and adding a candidate identity clause at the canonical parent guard.

## Required falsifiers and next check

The patch adds unit controls that require wrong-CAS, parent wrapper, leaf subclass, N9 subclass, N9 method override, and injected promotion runtime to refuse before N6. It also upgrades the protected-intent test to include a same-CAS candidate leaf while preserving refusal before factory invocation, and adds a positive candidate leaf test that asserts synthetic/unpromoted/empty-receipt state. A comment now describes the fixture boundary accurately.

After root rebinding/review and application, run the full actual 16-test acquisition module with complete output. The real no-cost negative must reach its own expected refusal rather than the earlier owner guard; actual N7 report resolution and acquisition consumer checks must be observed in the positives. If this second same-class finding remains, stop instance repair: widen the one parent/leaf/CAS mechanism or publish a bounded residual and falsifier. This proposal does not establish that test replay outcome.

## Alternatives, authority, and verification status

No unresolved external fact or new sovereign contract is required. The existing candidate contract is reused and its owner handshake extended. Status remains candidate/synthetic until downstream admission evidence exists; the N9 protected band is unchanged. Time/currentness semantics are unchanged. A falsifier is the same route with a different CAS object or any disallowed owner override; each must remain red before N6.

Static verification on the prepared postimages: AST parse PASS, canonical Ruff check PASS, canonical Ruff format check PASS, and `git apply --check` PASS on the current branch HEAD. Product tests and runtime replay on the proposed bytes are **UNRUN**; independent review is **NOT YET DONE**. The two earlier actual PASSes do not prove this patch. Capability status therefore remains `verification_missing` / proposal only. `closure_ids=[]`; formal ID/occurrence adjudication belongs to G.

## Exact footprint

One runtime mechanism path: `src/polisyos/runtime/quality/recursive_generation_cycle.py`. Mandatory companions: `tests/_helpers/acquisition_production.py`, `tests/integration/core_runtime/test_acquisition_world_growth_chain.py`, and `tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py`. `src/polisyos/runtime/quality/generation_cycle.py` is not needed: its existing constructor already supports a contract-testing leaf with a fixture CAS. Exact base/path pins, resulting SHA-256 values, replay pointers, patch SHA, and current revalidation SHA are in `manifest.json`.
