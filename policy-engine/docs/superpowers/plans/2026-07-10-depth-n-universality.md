# GY-N10 Depth-N Universality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the existing PolicyOS generation cycle is domain-, method-family-, and depth-generic by running real owner paths from arbitrary plain language to honest typed terminals on two distinct domains plus an unseen-domain smoke.

**Architecture:** Extend the canonical S0/WMR, N4, intervention-substrate, Foundry output-contract, N5, recursion/composition, N6, N7, and N9 owners. Add only a content-bound cycle-context bridge, a Foundry-owned value-evidence projector, and a thin recursive router; keep pack evidence candidate-only and remove/fence the fixed-world and GY-G predecessor paths.

**Tech Stack:** Python 3.14, Pydantic v2 strict models, existing PolicyOS IR/Foundry/runtime contracts, pytest, Ruff, JSON generated artifacts, AST/source-flip validators.

## Global Constraints

- Product root is `policy-engine/`; follow `CONTRIBUTING.md` and the failure/repair register before design and closeout.
- Reuse order is `wire-existing -> extend-existing -> consolidate-existing -> build-new`.
- LLM and pack outputs are candidates, never authority. Authority requires resolve + content-bind + verifier provenance.
- Use no domain-name branch or engine enum for covariates, levers, contexts, regimes, outcomes, or method-family vocabulary.
- Education writability remains `0`; CG2 production binds remain frozen; education promotion is not expected.
- The frozen proof follows the evidence-selected Stage-2 fork. Fork A requires a real
  owner-backed non-panel `value_ready` positive plus education's separate real typed
  refusal. The measured Fork B instead requires the six-family native-contract proof,
  the owner-intake refusal, a content-bound N7 acquisition route for the absent world
  relationship, and education's separate real typed refusal. It must not fabricate a
  positive over an empty substrate denominator.
- No method FQN is pinned in runtime or proof expectations. The live registry/advisor selects from candidate/problem/owner-data modality and persists the ranked trace; a fixed method default is forbidden.
- Treatment assignment is owner-resolved world knowledge. An observational feature may be built only by joining canonical owner-recorded treated units/periods to owner-resolved observations; caller/test/candidate-supplied assignment and arbitrary or synthetic indicators are forbidden and fail typed as `treatment_assignment_not_owner_derived`.
- Do not create a second registry, world, generation cycle, value surface, coupling algebra, or recursion authority.
- Fence fixed-UA WMR creation, shaped-string WMR trust, `n6.bootstrap.*`, and the GY-G fixture structurally; do not patch one caller.
- Preserve every existing N5/N6/N8/N9 decisive mutation. Add coverage; never delete or weaken a gate.
- Run only targeted verification with `python3` and `.venv/bin/ruff`; never run full pytest, backend verify, or CI parity.
- Run exactly one mutating or validating process at a time. Give long owner lanes their full E9 budget.
- Use E1 content-addressed pack/world/engine caches, Lane-0 mini-worlds, cached Lane-1 owners, one cold two-domain closeout, E5 wall times, and E6 journal-first live capture.
- Runtime timestamps and wall time never participate in artifact content hashes. `--write` must be byte-stable.
- N10a's zero-engine receipt is replayed only over immutable commits `26cc7cc03efc9da44362dc2914a5bde8ac8f7e73..d8a8cf076da6233c66b0a90010647c0d437e81c4`; live owner rederive remains current, and moving-HEAD rebasing is a decisive failure.
- Every GY-N10 validator and focused universality harness checks, in order:
  current checkout, repository `.venv` identity, then canonical CG backend
  availability. Failures are typed `wrong_checkout_resolved`,
  `wrong_interpreter_resolved`, and `cg_substrate_unavailable`. Every displayed
  `python3` command is executed as
  `env PATH="$PWD/.venv/bin:$PATH" PYTHONPATH="$PWD/src:$PWD" python3 ...`;
  the command bodies below omit only that repeated envelope.
- The two infrastructure gaps `owner_registration_derivation_missing` and `journal_raw_evidence_persistence_missing` remain typed residuals unless existing owners close them without scope expansion.
- Every task follows RED -> observe expected failure -> minimal GREEN -> focused regression -> scoped commit.
- A later stage does not begin while the preceding stage gate is red.
- Execute through subagent-driven development with exactly one mutating implementer at a time and a read-only review after each scoped task; create an isolated worktree before Task 1 after the required user consent.

---

## File and ownership map

### New focused modules

- `src/polisyos/runtime/quality/cycle_substrate.py`: strict content-bound orchestration envelope over canonical S0/WMR plus candidate-only lever/transport evidence. It does not load a pack path or own a registry.
- `src/polisyos/foundry/methods/components/value_evidence.py`: generic output-contract/estimand/uncertainty projector owned by Foundry.
- `src/polisyos/runtime/quality/recursive_generation_cycle.py`: thin depth/budget traversal that delegates leaf cycles and existing coupling/composition owners.
- `src/polisyos/runtime/http/services/control/generation_cycle.py`: plain-language compiler-to-recursive-cycle bridge; HTTP/service layer owns the NL compiler call.
- `tests/unit/runtime/quality/test_depth_n_universality.py`: Lane-0 depth, Stage-4 three-run proof semantics, unseen-domain honesty, and artifact validator behavior.
- `tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py`: frozen proof producer/checker, drift/rederive/source-flip harness, and byte-stable writer.
- `architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json`: generated committed proof artifact.

### Canonical owners to extend

- `src/polisyos/runtime/quality/intervention_substrate.py`: two missing public wrappers and typed candidate-unbound resolution only.
- `src/polisyos/runtime/quality/design_generation.py`: canonical grounding vocabulary import, injected lever/WMR context, no shaped-ref trust.
- `src/polisyos/runtime/quality/generation_cycle.py`: context injection, WMR reuse, generic value consumer, N6 one-terminal coherence, bootstrap fence.
- `src/polisyos/runtime/quality/substrate_registry.py`: no new registry; reuse strict registrations, registry hash validation, persistence, and selected-entry resolution.
- `src/polisyos/runtime/quality/world_model_record.py`: reuse strict WMR/ref/hash validation; add only owner-derived boundary input support if generation-cycle composition cannot remain local.
- `src/polisyos/ir/analytics/transportability.py`: measured arbitrary S-node builder support.
- `src/polisyos/foundry/methods/components/consensus.py`: reuse `EstimandSpec` and typed report adapters; do not duplicate them in runtime.
- `src/polisyos/runtime/quality/workspace/loop.py`: remove/fence GY-G fixture APIs after default flip.
- `src/polisyos/runtime/quality/design_axes/coupling_composition.py`: reuse graph/classification/decomposition/composition authority; make missing evidence explicit where necessary.
- `src/polisyos/runtime/quality/joint_simulation_horizon.py`: consume observed graph and surface unsupported coupling honestly; no second simulator.

### Existing tests/validators to extend

- `tests/unit/runtime/quality/test_design_generation.py`
- `tests/unit/runtime/quality/test_intervention_substrate.py`
- `tests/unit/runtime/quality/test_substrate_registry.py`
- `tests/unit/runtime/quality/test_world_model_record.py`
- `tests/unit/runtime/quality/test_generation_cycle.py`
- `tests/unit/runtime/quality/test_value_gate.py`
- `tests/unit/runtime/quality/test_acquisition_planner.py`
- `tests/unit/runtime/quality/test_workspace_loop.py`
- `tests/unit/runtime/http/test_nl_pipeline_materialization.py`
- `tests/unit/runtime/quality/test_second_domain_pack.py`
- N4, N5, N6, N7, N8, N9 contract checkers named in the specification.

---

# Stage 1 — N4 repair, content-bound intake, and pack bridges

## Task 0: Freeze the N10a historical receipt before Stage 1

**Files:**
- Modify: `tools/quality/validation/check_layer3_gy_second_domain_pack.py`
- Modify: `tests/unit/runtime/quality/test_second_domain_pack.py`
- Regenerate: `architecture/policy_design_case/layer3_gy_second_domain_pack.json`

**Interfaces:**
- `zero_engine_code.scope_semantics = "historical_commit_range"`
- `zero_engine_code.task_base_commit = "26cc7cc03efc9da44362dc2914a5bde8ac8f7e73"`
- `zero_engine_code.proof_head_commit = "d8a8cf076da6233c66b0a90010647c0d437e81c4"`
- `_historical_task_changed_paths(root: Path, *, base: str, proof_head: str) -> list[str]` reads only `git diff --name-only base..proof_head`.

- [x] **Step 1: Write RED historical-range and moving-head mutation tests.**

```python
def test_n10a_zero_engine_receipt_is_pinned_to_historical_proof_head() -> None:
    pack = checker.build_live_bundle(REPO_ROOT)["pack"]
    receipt = pack["zero_engine_code"]
    assert receipt["scope_semantics"] == "historical_commit_range"
    assert receipt["task_base_commit"] == N10A_BASE_COMMIT
    assert receipt["proof_head_commit"] == N10A_PROOF_HEAD_COMMIT
    assert receipt["changed_engine_paths"] == []


def test_n10a_receipt_rebased_to_moving_head_is_rejected() -> None:
    for moving_head in ("HEAD", _git_head_sha(REPO_ROOT)):
        payloads = checker._load_frozen_bundle(REPO_ROOT)
        payloads["pack"]["zero_engine_code"]["proof_head_commit"] = moving_head
        payloads["pack"] = checker._with_content_hash(
            payloads["pack"],
            "manifest_content_hash",
            excluded_fields=("runtime_metrics",),
        )
        issues = checker.validate_bundle_payloads(payloads, REPO_ROOT)
        assert "historical_receipt_rebased_to_moving_head" in {
            issue["code"] for issue in issues
        }
```

- [x] **Step 2: Run the focused tests and observe RED on moving-HEAD semantics.**

```bash
PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/unit/runtime/quality/test_second_domain_pack.py -k 'historical_proof_head or moving_head' -q
```

- [x] **Step 3: Implement the immutable range verifier without weakening live owner checks.**

Require literal 40-hex commits, require `base` is ancestor of `proof_head`, require `proof_head` is ancestor of current `HEAD`, and compute changed/scope/engine paths only from that range. Working, staged, and untracked files are deliberately absent from this historical receipt. Keep every live pack-owner query, content hash, seam witness, and rederive audit unchanged. Extend corrupt drift with `historical_receipt_rebased_to_moving_head`.

- [x] **Step 4: Regenerate serially and verify.**

```bash
PYTHONPATH="$PWD/src:$PWD" python3 tools/quality/validation/check_layer3_gy_second_domain_pack.py --write --output-format json
PYTHONPATH="$PWD/src:$PWD" python3 tools/quality/validation/check_layer3_gy_second_domain_pack.py --check
PYTHONPATH="$PWD/src:$PWD" python3 tools/quality/validation/check_layer3_gy_second_domain_pack.py --rederive-audit
PYTHONPATH="$PWD/src:$PWD" python3 tools/quality/validation/check_layer3_gy_second_domain_pack.py --corrupt-field-drift-check  # exit 1
PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/unit/runtime/quality/test_second_domain_pack.py -k 'historical_proof_head or moving_head or pack' -q
.venv/bin/ruff check tools/quality/validation/check_layer3_gy_second_domain_pack.py tests/unit/runtime/quality/test_second_domain_pack.py
```

- [x] **Step 5: Commit the pre-Stage-1 historical proof repair.**

```bash
git add tools/quality/validation/check_layer3_gy_second_domain_pack.py tests/unit/runtime/quality/test_second_domain_pack.py architecture/policy_design_case/layer3_gy_second_domain_pack.json architecture/policy_design_case/layer3_gy_second_domain_census.json architecture/policy_design_case/layer3_gy_second_domain_smoke_design_problem.json architecture/policy_design_case/layer3_gy_second_domain_cycle_entry_trace.json architecture/policy_design_case/layer3_gy_second_domain_free_grow_gaps.json
git commit -m "fix: pin N10a proof to historical range"
```

## Task 0B: Install the structural wrong-checkout guard

**Files:**
- Create: `tools/quality/validation/checkout_guard.py`
- Create: `tests/unit/runtime/quality/test_depth_n_universality.py`

**Interfaces:**
- `assert_current_checkout(repo_root: Path) -> Path` returns the resolved `polisyos` package path or raises `WrongCheckoutResolvedError("wrong_checkout_resolved:<path>")`.
- The Stage-4 GY-N10 validator calls this guard before parsing arguments or reading proof artifacts.
- The focused universality harness imports only standard-library/guard code, calls the guard at module bootstrap, and only then imports any `polisyos.*` owner; an autouse fixture is too late because collection imports have already occurred.

- [x] **Step 1: Write RED current/wrong checkout tests.**

```python
def test_universality_harness_resolves_current_checkout() -> None:
    resolved = assert_current_checkout(REPO_ROOT)
    assert resolved.is_relative_to(REPO_ROOT / "src")


def test_wrong_checkout_is_rejected_before_proof_execution() -> None:
    result = _run_checkout_guard_with_pythonpath(MAIN_CHECKOUT / "policy-engine/src")
    assert result.returncode == 1
    assert "wrong_checkout_resolved" in result.stderr
```

- [x] **Step 2: Run and observe RED because the guard is absent.**

```bash
PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py -k 'checkout' -q
```

- [x] **Step 3: Implement the fail-closed path comparison.**

Resolve `repo_root`, import `polisyos` inside the guard, resolve `polisyos.__file__`, and require it to be below `repo_root / "src"`. Do not compare strings or accept symlink-shaped prefixes; use resolved `Path.is_relative_to`. At the top of `test_depth_n_universality.py`, call the guard before importing runtime owners. The subprocess mutation deliberately points `PYTHONPATH` at the main checkout while running the worktree guard and must refuse before a sentinel validator producer is called.

- [x] **Step 4: Verify and commit.**

```bash
PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py -k 'checkout' -q
.venv/bin/ruff check tools/quality/validation/checkout_guard.py tests/unit/runtime/quality/test_depth_n_universality.py
git add tools/quality/validation/checkout_guard.py tests/unit/runtime/quality/test_depth_n_universality.py
git commit -m "test: reject wrong checkout proof runs"
```

## Task 1: Restore the bounded N4 public owner surface

**Files:**
- Modify: `tests/unit/runtime/quality/test_design_generation.py`
- Modify: `src/polisyos/runtime/quality/intervention_substrate.py`
- Modify: `src/polisyos/runtime/quality/design_generation.py`
- Modify: `src/polisyos/scientist/agent/formalizer.py`
- Modify: `tools/quality/validation/check_layer3_gy_design_generation_contract.py`
- Create: `docs/superpowers/journals/2026-07-11-gy-n10-stage-1.md`

**Interfaces:**
- Produces: `production_composed_world_model_record(repo_root: str | Path) -> WorldModelRecord`
- Produces: `intervention_generation_registry_bundle(repo_root: str | Path) -> RegistryBundle`
- Produces: `trinity_bundle_formalizer_generator_path(bundle: TrinityBundle, *, recorded_calls: Sequence[object]) -> Literal["model_generated", "degraded_mock_fallback", "path_unrecorded"]`
- Re-exports: the exact `GroundingDispositionKind` imported from `grounding_disposition_vocab`

- [x] **Step 1: Audit every N4 import in one pass before editing production.**

Parse every module-level import in `design_generation.py`, import each owner module independently, resolve every imported symbol, and count live name loads in the AST. Write the resulting table to the Stage-1 journal with columns `module`, `symbol`, `live_use_count`, `resolution`, `disposition`, and `evidence`. Allowed dispositions are exactly `resolved`, `dead`, `live_existing_logic_to_wrap`, and `live_no_existing_owner_logic`. Delete only a dead import; wrap only existing logic. If any row is `live_no_existing_owner_logic`, stop before implementation and report.

- [x] **Step 2: Write the failing import, vocabulary-owner, and formalizer-evidence tests.**

```python
def test_default_n4_stack_imports_canonical_intervention_owners() -> None:
    from polisyos.runtime.quality import design_generation
    from polisyos.runtime.quality.intervention_substrate import (
        intervention_generation_registry_bundle,
        production_composed_world_model_record,
    )

    assert callable(intervention_generation_registry_bundle)
    assert callable(production_composed_world_model_record)
    assert design_generation.intervention_generation_registry_bundle is (
        intervention_generation_registry_bundle
    )


def test_design_generation_reexports_canonical_grounding_disposition_kind() -> None:
    from polisyos.runtime.quality import design_generation
    from polisyos.runtime.quality.grounding_disposition_vocab import (
        GroundingDispositionKind,
    )

    assert design_generation.GroundingDispositionKind is GroundingDispositionKind


def test_design_generation_has_one_grounding_disposition_owner() -> None:
    module = ast.parse(DESIGN_GENERATION_PATH.read_text(encoding="utf-8"))
    assert _imports_name_from(
        module,
        "polisyos.runtime.quality.grounding_disposition_vocab",
        "GroundingDispositionKind",
    )
    assert not _assigns_module_name(module, "GroundingDispositionKind")


def test_formalizer_path_requires_matching_recorded_response() -> None:
    bundle = _bundle([_intervention("recorded")])
    calls = (_formalizer_call(parsed_json=bundle.model_dump(mode="json")),)
    assert trinity_bundle_formalizer_generator_path(
        bundle, recorded_calls=calls
    ) == "model_generated"


def test_formalizer_path_without_record_is_typed_unrecorded() -> None:
    assert trinity_bundle_formalizer_generator_path(
        _bundle([_intervention("unrecorded")]), recorded_calls=()
    ) == "path_unrecorded"


def test_formalizer_path_mismatched_record_is_degraded() -> None:
    returned = _bundle([_intervention("returned")])
    recorded = _bundle([_intervention("different")])
    assert trinity_bundle_formalizer_generator_path(
        returned,
        recorded_calls=(_formalizer_call(parsed_json=recorded.model_dump(mode="json")),),
    ) == "degraded_mock_fallback"
```

- [x] **Step 3: Run the focused tests and observe the two sequential REDs.**

Run:

```bash
PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/unit/runtime/quality/test_design_generation.py -k 'default_n4_stack_imports or canonical_grounding_disposition or one_grounding_disposition_owner or formalizer_path' -q
```

Expected first: collection fails on the two public intervention owners. After adding only those wrappers, rerun and observe collection fail on `trinity_bundle_formalizer_generator_path`. The AST ownership test is the decisive local-vocabulary RED because equivalent `Literal` aliases may be identity-cached on Python 3.14.

- [x] **Step 4: Add only the canonical wrappers, recorded-evidence accessor, and vocabulary import.**

Implement these signatures in `intervention_substrate.py` by delegating to the existing private loaders/registry builders:

```python
def production_composed_world_model_record(repo_root: str | Path) -> WorldModelRecord:
    """Return the cached production WMR composed by the existing owner."""
    return _production_composed_world_model_record(Path(repo_root).resolve().as_posix())


def intervention_generation_registry_bundle(repo_root: str | Path) -> RegistryBundle:
    """Return the existing L6 slot/mechanism registries for the N4 linker."""
    bundle = load_l6_intervention_substrate(Path(repo_root).resolve())
    slots = _owner_slot_registry(bundle)
    mechanisms = _owner_mechanism_registry(bundle, slot_registry=slots)
    return _owner_registry_bundle(mechanism_registry=mechanisms, slot_registry=slots)
```

Export both in `__all__`. In `design_generation.py`, delete the local Literal definition and import:

```python
from polisyos.runtime.quality.grounding_disposition_vocab import GroundingDispositionKind
```

Add `GroundingDispositionKind` to `design_generation.__all__` so the re-export is explicit and the canonical object is the only public vocabulary.

In `formalizer.py`, the accessor inspects `recorded_calls` without importing runtime-quality types. It selects successful calls whose `role_hint == "formalizer"`, whose `parsed_json` validates through the same `TrinityBundle` normalization used by `LLMFormalizerAgent`, and whose normalized dump equals the returned bundle. A matching record returns `model_generated`; non-empty recorded evidence with no match returns `degraded_mock_fallback`; an empty/unreadable call slice returns `path_unrecorded`. No default argument is permitted.

At both live call sites in `design_generation.py`, pass the exact formalizer call slice. Initial generation passes `recording_client.calls[formalizer_call_start:]`; each salvage retry passes `recording_client.calls[retry_start:]`. `path_unrecorded` triggers salvage and, if still unresolved, a typed `formalizer_path_unrecorded` terminal rather than a real/degraded guess.

- [x] **Step 5: Add the decisive N4 source flip.**

Extend the existing restoring N4 mutation harness with `formalizer_recorded_path_derivation_removed`: patch the accessor so matching recorded evidence no longer resolves, require the live salvage/path probe to turn RED, restore the exact source hash in `finally`, and verify the restored N4 contract. Removing the derivation while retaining markers must not stay green.

- [x] **Step 6: Run the focused tests, guarded direct import, N4 contract, source flip, and Ruff.**

```bash
PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/unit/runtime/quality/test_design_generation.py -k 'default_n4_stack_imports or canonical_grounding_disposition or one_grounding_disposition_owner or formalizer_path' -q
PYTHONPATH="$PWD/src:$PWD" python3 -c 'from pathlib import Path; import polisyos; root=Path.cwd().resolve(); resolved=Path(polisyos.__file__).resolve(); assert resolved.is_relative_to(root / "src"), f"wrong_checkout_resolved:{resolved}"; import polisyos.runtime.quality.design_generation'
PYTHONPATH="$PWD/src:$PWD" python3 tools/quality/validation/check_layer3_gy_design_generation_contract.py --check
PYTHONPATH="$PWD/src:$PWD" python3 tools/quality/validation/check_layer3_gy_design_generation_contract.py --source-flip-mutations
.venv/bin/ruff check src/polisyos/runtime/quality/intervention_substrate.py src/polisyos/runtime/quality/design_generation.py src/polisyos/scientist/agent/formalizer.py tools/quality/validation/check_layer3_gy_design_generation_contract.py tests/unit/runtime/quality/test_design_generation.py
```

Expected: all exit `0`. Record this as closure of the long-standing N4 cloud-deferred import residual.

- [x] **Step 7: Commit the bounded repair and its journal discovery record.**

```bash
git add src/polisyos/runtime/quality/intervention_substrate.py src/polisyos/runtime/quality/design_generation.py src/polisyos/scientist/agent/formalizer.py tools/quality/validation/check_layer3_gy_design_generation_contract.py tests/unit/runtime/quality/test_design_generation.py docs/superpowers/journals/2026-07-11-gy-n10-stage-1.md
git commit -m "fix: restore N4 generation owner surface"
```

## Task 1R: Reconcile repository-runtime identity and N2 normalization provenance

**Files:**
- Modify: `tools/quality/validation/universality_preflight.py`
- Modify: `tests/unit/runtime/quality/test_depth_n_universality.py`
- Modify: `src/polisyos/runtime/quality/intervention_atom_binding.py`
- Modify: `tests/unit/runtime/quality/test_intervention_atom_binding.py`
- Modify: `tools/quality/validation/check_layer3_gy_intervention_atom_binding_contract.py`
- Regenerate: `architecture/policy_design_case/layer3_gy_intervention_atom_binding_contract.json`
- Modify: `docs/superpowers/journals/2026-07-11-gy-n10-stage-1.md`

**Interfaces:**
- `assert_repository_interpreter(repo_root: Path) -> Path` requires resolved
  `sys.prefix == sys.exec_prefix == (repo_root / ".venv").resolve()` and rejects
  the base interpreter as `wrong_interpreter_resolved`.
- `assert_universality_preflight` orders checkout -> interpreter -> canonical
  grounding-backend availability and keeps its current return shape.
- `AtomNormalizationRecord` is the strict immutable metadata model recovered
  from the never-landed July owner blob; no alias/shim is added.
- `InterventionAtomBinding.normalized_from` is optional, content-hashed,
  persisted provenance.
- `build_intervention_atom_binding(..., normalized_from: Mapping[str, Any] |
  AtomNormalizationRecord | None = None)` validates it through the
  canonical model and never uses it in a bind/admission predicate.

- [x] **Step 1: Write and observe interpreter-preflight REDs.**

Use fresh subprocesses. The repository venv passes; `sys._base_executable`
with the current `PYTHONPATH` fails before a producer sentinel; a deterministic
child with `sys.prefix`/`sys.exec_prefix` changed to base values fails the same
way; wrong checkout wins before wrong interpreter. Removing the interpreter
assertion while retaining its markers must let the deterministic child reach
the producer and turn `wrong_interpreter_preflight_removed` RED.

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py \
  -k 'interpreter or checkout or cg_substrate' -q
```

- [x] **Step 2: Implement the minimal preflight composition and verify GREEN.**

Use `sys.prefix`/`sys.exec_prefix`, not `VIRTUAL_ENV` and not the fully resolved
Python binary (which correctly resolves through the venv symlink to Homebrew's
base executable). Preserve the existing checkout-first and backend-owner tests.

- [x] **Step 3: Complete archaeology and constructor/consumer census before N2 edits.**

Record every `build_intervention_atom_binding` caller and every atom authority
consumer. The bounded class authorization applies only where July artifact,
recovered blob, or closure-test evidence proves the symbol and the field is
metadata/mechanics. Anything affecting what a gate accepts stops.

- [x] **Step 4: Write N2 RED round-trip and authority-isolation tests.**

Require strict validation of the July normalization payload, atom/CAS
round-trip, and identical `consume_intervention_atom_for_cycle` output with and
without provenance. The existing live N4 payoff test is the cross-owner RED.
The `normalized_from_used_as_authority` mutation makes the cycle consumer read
original pre-normalization slots; the N2 contract must go RED and restore the
exact source hash.

```bash
python3 -m pytest tests/unit/runtime/quality/test_intervention_atom_binding.py \
  tests/unit/runtime/quality/test_design_generation.py \
  -k 'normalized_from or legacy_exact_match' -q
```

- [x] **Step 5: Extend only the N2 owner, regenerate through its writer, and run blast radius.**

`normalized_from` is supporting provenance, not action/outcome or grounding
authority. Existing callers may omit it. The builder verifies any normalized
operator/slot values against the already-authoritative intervention/linker
halves but never uses provenance to repair or widen those halves.
When absent, `normalized_from` is omitted from semantic content hashing so the
two persisted July null rows retain their historical hashes; a non-null record
is content-hashed normally.

```bash
python3 tools/quality/validation/check_layer3_gy_intervention_atom_binding_contract.py --write
python3 tools/quality/validation/check_layer3_gy_intervention_atom_binding_contract.py --check
python3 tools/quality/validation/check_layer3_gy_intervention_atom_binding_contract.py --source-flip-mutations
python3 -m pytest tests/unit/runtime/quality/test_intervention_atom_binding.py \
  tests/unit/runtime/quality/test_design_generation.py \
  tests/unit/runtime/quality/test_intervention_substrate.py \
  tests/unit/runtime/quality/test_joint_simulation_horizon.py \
  tests/unit/runtime/quality/test_world_model_record.py \
  -k 'atom or normalized_from or legacy_exact_match' -q
.venv/bin/ruff check tools/quality/validation/universality_preflight.py \
  src/polisyos/runtime/quality/intervention_atom_binding.py \
  tools/quality/validation/check_layer3_gy_intervention_atom_binding_contract.py \
  tests/unit/runtime/quality/test_depth_n_universality.py \
  tests/unit/runtime/quality/test_intervention_atom_binding.py
```

- [x] **Step 6: Commit interpreter and N2 slices with the integration-debt journal table.**

Use separate scoped commits when practical. The journal table records symbol,
July evidence, metadata/mechanics disposition, owner, RED/GREEN evidence, and
source-flip restoration. Same-family stragglers may follow this exact loop; an
authority-affecting or ambiguous mismatch stops.

## Task 2: Add the content-bound cycle substrate envelope

**Progress checkpoint (2026-07-12, boundary continuation):** the strict envelope core, full-denominator WMR projection
checks, transport/candidate parent binding, fresh consumption revalidator, generic third-shape
probe, and the canonical `InterventionSubstrateBundle` full-payload integrity chokepoint are green.
The N10a pack now also persists one strict S0 registry payload, binds every lever to the data-derived
L2 selection, verifies its query against the immutable proof-head owner receipt plus the live S0
owner, and constructs one substrate-input projection before the baseline cycle for exact pack reuse.
It does not claim the legacy N6 trace consumed that projection; that remains the WMR/context bridge.
The N7 no-result receipt is reused only from the immutable proof-head evidence through a recomputed,
fully revalidated E1 key that binds effective retrieval limits, so raw evidence stays intact while
`--write` remains byte-stable. The canonical boundary owner now accepts a verified registry object
plus selected content hashes, derives jurisdiction/time/population from the actual `DesignProblem`,
emits repo-relative/content refs, and rejects an unresolved selection. The checker-only adapter
validates the frozen pack and receives that real WMR before projecting all four education levers and
both transport covariates into one context. Task 2 is complete. The context is not yet consumed by
N4/L6/N6, so the three bridges and the Stage-1 gate remain open.

**Files:**
- Create: `src/polisyos/runtime/quality/cycle_substrate.py`
- Modify: `src/polisyos/runtime/quality/__init__.py`
- Modify: `tests/unit/runtime/quality/test_substrate_registry.py`
- Modify: `tests/unit/runtime/quality/test_world_model_record.py`
- Modify: `tests/unit/runtime/quality/test_second_domain_pack.py`
- Modify: `tools/quality/validation/check_layer3_gy_second_domain_pack.py`

**Interfaces:**
- Produces strict `CandidateLeverEvidence`, `TransportCovariateObservation`, `TransportContextEvidence`, and `CycleSubstrateContext`.
- Produces `build_cycle_substrate_context(*, design_problem_ref: str, domain: str, substrate_registry: SubstrateRegistry, selected_registry_entry_hashes: Sequence[str], world_model_record: WorldModelRecord, intervention_substrate: InterventionSubstrateBundle | None, candidate_levers: Sequence[CandidateLeverEvidence], transport_context: TransportContextEvidence | None, source_pack_content_hash: str | None, substrate_input_content_hash: str | None) -> CycleSubstrateContext`.
- The runtime API accepts objects; only the checker projects the committed N10a JSON into those objects.

- [x] **Step 1: Write RED hash/authority/generic-shape tests.**

The tests must prove:

```python
def test_cycle_substrate_context_binds_registry_wmr_and_pack_hashes() -> None:
    context = _cycle_substrate_context(domain="education")
    assert context.substrate_registry_content_hash == context.substrate_registry.content_hash
    assert context.world_model_record_content_hash == context.world_model_record.content_hash
    assert context.source_pack_content_hash == _historical_pack_hash()
    assert context.substrate_input_content_hash == _education_substrate_input_hash()
    assert all(row.status == "candidate_unbound" for row in context.candidate_levers)


def test_cycle_substrate_context_rejects_stale_registry_hash() -> None:
    payload = _cycle_substrate_context(domain="education").model_dump(mode="python")
    payload["substrate_registry_content_hash"] = _hash("stale")
    with pytest.raises(ValueError, match="cycle_substrate_registry_hash_mismatch"):
        CycleSubstrateContext.model_validate(payload)


def test_cycle_substrate_context_rejects_cross_context_candidate() -> None:
    education = _cycle_substrate_context(domain="education")
    water = _cycle_substrate_context(
        domain="water_quality",
        lever_id="riparian_buffer_width",
        transport_covariate="watershed_slope",
    )
    payload = education.model_dump(mode="python")
    payload["candidate_levers"] = [water.candidate_levers[0].model_dump(mode="python")]
    with pytest.raises(ValueError, match="candidate_context_binding_mismatch"):
        CycleSubstrateContext.model_validate(payload)


def test_cycle_substrate_context_rejects_wmr_registry_mismatch() -> None:
    with pytest.raises(ValueError, match="wmr_registry_content_mismatch"):
        _cycle_substrate_context(world_model_record=_wmr_for_registry(_other_registry()))


def test_third_pack_vocabulary_needs_no_engine_branch() -> None:
    context = _cycle_substrate_context(
        domain="water_quality",
        lever_id="riparian_buffer_width",
        transport_covariate="watershed_slope",
    )
    assert context.candidate_levers[0].lever_id == "riparian_buffer_width"
    assert context.transport_context.covariates[0].canonical_var == "watershed_slope"
```

Also load the committed education pack through a checker helper and assert its full S0 registry payload revalidates and hash-matches `components.owner_writability.s0_registry_content_hash`; do not synthesize a registration.

- [x] **Step 2: Run the new tests and observe RED because the envelope/projector is absent.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_substrate_registry.py tests/unit/runtime/quality/test_world_model_record.py tests/unit/runtime/quality/test_second_domain_pack.py -k 'cycle_substrate or third_pack_vocabulary' -q
```

- [x] **Step 3: Implement the strict envelope and recomputing hash.**

Use this public shape; all models use `ConfigDict(extra="forbid", frozen=True)`:

```python
class CandidateLeverEvidence(BaseModel):
    lever_id: str
    instrument: str
    target_concept: str
    status: Literal["candidate_unbound"] = "candidate_unbound"
    entry_content_hash: str
    substrate_input_content_hash: str
    selected_registry_entry_hash: str
    context_binding_hash: str
    source_refs: tuple[str, ...]


class TransportCovariateObservation(BaseModel):
    canonical_var: str
    source_value: float
    target_value: float
    source_row_content_hash: str
    target_row_content_hash: str


class TransportContextEvidence(BaseModel):
    status: Literal["candidate_context_only_not_transport_authority"]
    source_context_id: str
    target_context_id: str
    source_profile_content_hash: str
    target_profile_content_hash: str
    covariates: tuple[TransportCovariateObservation, ...]


class CycleSubstrateContext(BaseModel):
    schema_version: str
    design_problem_ref: str
    domain: str
    source_pack_content_hash: str | None
    substrate_input_content_hash: str | None
    substrate_registry: SubstrateRegistry
    substrate_registry_content_hash: str
    selected_registry_entry_hashes: tuple[str, ...]
    world_model_record: WorldModelRecord
    world_model_record_content_hash: str
    intervention_substrate: InterventionSubstrateBundle | None
    candidate_levers: tuple[CandidateLeverEvidence, ...]
    transport_context: TransportContextEvidence | None
    authority_purpose: Literal["cycle_input_candidate_only"]
    may_not_use_for: tuple[str, ...]
    context_binding_hash: str
    content_hash: str
```

`substrate_input_content_hash` excludes downstream trace/gap refs and runtime metrics, preventing a pack→trace→pack hash cycle; `source_pack_content_hash` identifies the immutable historical N10a pack. `context_binding_hash` is computed first from the DesignProblem, substrate-input, registry, WMR, and selected-entry hashes. `build_cycle_substrate_context` must revalidate the registry/WMR, require `world_model_record.substrate_registry_ref` to bind the same registry content, resolve every selected entry hash from the registry and WMR resolution, and require every candidate's substrate-input/selected-entry/context-binding hashes to match. It then recomputes `content_hash` from stable hashes and candidate evidence. It must not accept a pack path.

For education lever vocabulary, `selected_registry_entry_hash` resolves the canonical L2 SKG registration (`l2_scholar_kg:scholar_knowledge.duckdb`) that owns the causal lever rows. The education-named L5 observation entry is not lever authority and cannot satisfy this membership proof.

N4 intake independently verifies `CycleSubstrateContext.design_problem_ref` and `domain` against the actual `DesignProblem`; a valid context for the wrong problem/domain is a substitution failure, not a reusable hint.

Add RED negatives for stale WMR, WMR/registry mismatch, selected-entry absent from either registry or WMR, and cross-context candidate substitution. A failure may not mint a refusal stamped with the unrelated context's hashes.

- [x] **Step 4: Add the checker-only pack projector.**

In `check_layer3_gy_second_domain_pack.py`, add a helper that:

1. validates `manifest_content_hash` using the existing pack hash routine;
2. validates `owner_query_results.s0_registry.registry_payload` as `SubstrateRegistry` (Task 0/2 regeneration must persist this already-rederived payload if the committed pack still omits it);
3. verifies the registry content hash and selected education entry hashes;
4. projects lever and transport rows into the strict candidate models; and
5. receives a concrete WMR from the canonical boundary builder rather than creating runtime authority from JSON presence.

- [x] **Step 5: Run focused tests and Ruff.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_substrate_registry.py tests/unit/runtime/quality/test_world_model_record.py tests/unit/runtime/quality/test_second_domain_pack.py -k 'cycle_substrate or third_pack_vocabulary' -q
.venv/bin/ruff check src/polisyos/runtime/quality/cycle_substrate.py src/polisyos/runtime/quality/__init__.py tools/quality/validation/check_layer3_gy_second_domain_pack.py tests/unit/runtime/quality/test_substrate_registry.py tests/unit/runtime/quality/test_world_model_record.py tests/unit/runtime/quality/test_second_domain_pack.py
```

- [x] **Step 6: Commit the canonical intake envelope.**

```bash
git add src/polisyos/runtime/quality/cycle_substrate.py src/polisyos/runtime/quality/__init__.py tools/quality/validation/check_layer3_gy_second_domain_pack.py tests/unit/runtime/quality/test_substrate_registry.py tests/unit/runtime/quality/test_world_model_record.py tests/unit/runtime/quality/test_second_domain_pack.py
git commit -m "feat: bind cycle substrate evidence"
```

## Task 3: Bridge candidate levers into N4 and intervention resolution

**Files:**
- Modify: `src/polisyos/runtime/quality/design_generation.py`
- Modify: `src/polisyos/runtime/quality/intervention_substrate.py`
- Modify: `src/polisyos/runtime/quality/generation_cycle.py`
- Modify: `tests/unit/runtime/quality/test_design_generation.py`
- Modify: `tests/unit/runtime/quality/test_intervention_substrate.py`
- Modify: `tests/unit/runtime/quality/test_generation_cycle.py`

**Interfaces:**
- Add keyword-only `cycle_substrate_context: CycleSubstrateContext | None = None` through N4 public entry points and `N4GenerationPort`.
- Extend `LeverSpaceSliceEntry` with `binding_status: Literal["world_bound", "candidate_unbound"]` and exact source hashes.
- Produce `InterventionLeverRefusal` and return `InterventionLeverResolution | InterventionLeverRefusal` when the complete `CycleSubstrateContext` selects a candidate lever.
- `GenerationCycleController._generate_node` preserves `generation_channel="n4_owner"` when the real result has grounding dispositions but no bound atoms; it routes immutable disposition refs, not fabricated intervention candidates.

- [x] **Step 1: Write RED tests for exact education levers and honest unbound resolution.**

```python
def test_prompt_slice_uses_injected_candidate_levers_without_binding_them() -> None:
    result = derive_lever_space_prompt_slice(
        _education_problem(),
        repo_root=Path.cwd(),
        reference=_reference(),
        cycle_substrate_context=_education_cycle_substrate_context(),
    )
    assert {row.operator_kind for row in result.entries} == {
        "education_blended_learning",
        "education_stem_education",
        "education_teaching_method",
        "education_dialogic_reading_modality",
    }
    assert {row.instrument for row in result.entries} == {
        "education.blended_learning",
        "education.stem_education",
        "education.teaching_method",
        "education.dialogic_reading_modality",
    }
    assert {row.binding_status for row in result.entries} == {"candidate_unbound"}
    assert all(row.target_world_slots == () for row in result.entries)


def test_pack_lever_resolution_returns_typed_candidate_unbound() -> None:
    result = resolve_intervention_lever(
        _owner_bundle(),
        operator_kind="education.teaching_method",
        parameter_value=0,
        cycle_substrate_context=_education_cycle_substrate_context(),
    )
    assert isinstance(result, InterventionLeverRefusal)
    assert result.status == "candidate_unbound"
    assert result.reason_code == "knob_operator_unresolved"
```

Add a third-pack-shaped lever test and a negative proving a candidate lever never appears in the writable knob dictionary.
Add cross-context substitution and stale-WMR tests that reach the real resolver owner and fail before a refusal hash is emitted.

Add a cycle-level RED test:

```python
def test_disposition_only_n4_result_never_falls_back_to_grammar() -> None:
    run = asyncio.run(_run_cycle_with_candidate_unbound_n4_result())
    cycle = run.cycles[0]
    assert cycle.generation_channel == "n4_owner"
    assert cycle.grounding.grounding_source == "cgf_firewall"
    assert cycle.grounding.grounding_disposition in {
        "novel_cg3",
        "non_binding_abstain",
        "unknown_blocked",
    }
    assert cycle.terminal_kind in _terminal_denominator()
    assert cycle.terminal_kind != "a_spec_gap"
    assert cycle.selected_candidate_content_hash in {
        disposition.raw_candidate_hash for disposition in _frozen_disposition_only_result().grounding_dispositions
    }
    assert "grammar_fallback" not in json.dumps(run.model_dump(mode="json"))
```

- [x] **Step 2: Run the focused tests and observe RED.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_design_generation.py tests/unit/runtime/quality/test_intervention_substrate.py tests/unit/runtime/quality/test_generation_cycle.py -k 'candidate_lever or candidate_unbound or injected_candidate' -q
```

- [x] **Step 3: Implement minimal typed propagation.**

Thread `cycle_substrate_context` through:

```python
async def generate_design_candidates_under_a(
    design_problem: DesignProblem,
    *,
    model_id: str,
    llm_client: object | None = None,
    repo_root: Path | None = None,
    min_diverse_candidates: int = 3,
    data_context: dict[str, Any] | None = None,
    world_model_record_ref: str | None = None,
    cycle_substrate_context: CycleSubstrateContext | None = None,
) -> GenerationUnderAResult:
    organ_run = await generate_design_candidate_bundle_under_a(
        design_problem,
        model_id=model_id,
        llm_client=llm_client,
        repo_root=repo_root,
        min_diverse_candidates=min_diverse_candidates,
        data_context=data_context,
        world_model_record_ref=world_model_record_ref,
        cycle_substrate_context=cycle_substrate_context,
    )
    return organ_run.result


def derive_lever_space_prompt_slice(
    design_problem: DesignProblem,
    *,
    repo_root: Path,
    reference: CredalReference | None = None,
    cycle_substrate_context: CycleSubstrateContext | None = None,
) -> LeverSpacePromptSlice:
    """Derive one non-authoritative slice from the explicitly selected context."""
```

Add the same keyword to `generate_design_candidate_bundle_under_a`; its existing body forwards the context to `derive_lever_space_prompt_slice` and `_content_bound_candidates`.

When context candidate levers are present, build prompt entries directly from their data and mark them `candidate_unbound`. Continue to derive verified `world_bound` entries from an explicitly supplied L6 bundle. Never substitute fixed L6 for a nonmatching domain.

`InterventionSpec.kind` accepts canonical identifier tokens rather than dotted concept surfaces. The
bridge therefore uses each pack row's already-persisted `lever_id` as `operator_kind` and carries the
exact dotted `instrument` separately in the same prompt entry. This is a data-derived normalization,
not a domain table or schema loosening.

Add a strict refusal model with a recomputed hash:

```python
class InterventionLeverRefusal(_StrictModel):
    status: Literal["candidate_unbound", "acquisition_required"]
    operator_kind: str
    reason_code: str
    candidate_entry_content_hash: str
    context_binding_hash: str
    substrate_registry_content_hash: str
    world_model_record_content_hash: str
    content_hash: str
```

The resolver receives `cycle_substrate_context` and selects the candidate from that context by exact operator/entry membership. It does not accept independently supplied candidate evidence or a loose WMR on this path. Preserve existing exception behavior when no context is supplied; this bounds the change and preserves old callers.

For disposition-only N4 output, derive an internal immutable reference only from `proposal_id`, `raw_candidate_hash`, and the exact `GroundingDispositionRecord`; do not construct an intervention atom. Merge every unmatched non-binding disposition into the cycle candidate denominator even when a mixed result also contains bound candidates—fixing only the all-empty case is insufficient. Extend candidate ID/hash resolution and `PolicyGroundingPort` matching by exact proposal/raw hash; atom/target-slot validation remains mandatory only for `shadow_bound`. `_joint_value_node` emits the existing typed simulation/value blocked states for an unbound candidate, and acquisition routing consumes the real grounding gaps. Grammar fallback remains available only when N4 produced neither bound candidates nor usable dispositions.

- [x] **Step 4: Run focused and frozen N4 checks.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_design_generation.py tests/unit/runtime/quality/test_intervention_substrate.py tests/unit/runtime/quality/test_generation_cycle.py -k 'candidate_lever or candidate_unbound or injected_candidate' -q
python3 tools/quality/validation/check_layer3_gy_design_generation_contract.py --check
python3 -c 'import polisyos.runtime.quality.design_generation'
.venv/bin/ruff check src/polisyos/runtime/quality/design_generation.py src/polisyos/runtime/quality/intervention_substrate.py src/polisyos/runtime/quality/generation_cycle.py tests/unit/runtime/quality/test_design_generation.py tests/unit/runtime/quality/test_intervention_substrate.py tests/unit/runtime/quality/test_generation_cycle.py
```

- [x] **Step 5: Commit the N4/L6 bridge.**

```bash
git add src/polisyos/runtime/quality/design_generation.py src/polisyos/runtime/quality/intervention_substrate.py src/polisyos/runtime/quality/generation_cycle.py tests/unit/runtime/quality/test_design_generation.py tests/unit/runtime/quality/test_intervention_substrate.py tests/unit/runtime/quality/test_generation_cycle.py
git commit -m "feat: route candidate levers through N4"
```

## Task 4: Reuse the concrete WMR and fence synthetic bootstrap authority

**Files:**
- Modify: `src/polisyos/runtime/quality/generation_cycle.py`
- Modify: `tests/unit/runtime/quality/test_generation_cycle.py`
- Modify: `tests/unit/runtime/quality/test_value_gate.py`
- Modify: `tests/unit/runtime/quality/test_acquisition_planner.py`
- Modify: `tools/quality/validation/check_layer3_gy_acquisition_contract.py` to add the derived bootstrap-caller/fail-closed witness without altering its existing mutation denominator.

**Interfaces:**
- `GenerationCycleController(*, generation_port: GenerationPort | None = None, grounding_port: GroundingPort | None = None, simulation_port: SimulationPort | None = None, value_port: ValuePort | None = None, promotion_port: PromotionPort | None = None, revision_policy: RevisionPolicy | None = None, voi_scheduler: SimpleVOIScheduler | None = None, acquisition_owner_gateway: object | None = None, repo_root: Path | None = None, model_id: str | None = None, cycle_substrate_context: CycleSubstrateContext | None = None, high_proxy_threshold: float = 0.8, low_grounding_threshold: float = 0.5)` injects the same context into N4/N5/N8.
- `JointSimulationPort(controller: JointSimulationHorizonController | None = None, *, repo_root: Path | None = None, cycle_substrate_context: CycleSubstrateContext | None = None)` returns the exact context WMR.
- `_n7_substrate_registry` resolves explicit context/hints or canonical catalogs and fails typed; it never constructs `n6.bootstrap.*` entries.

- [x] **Step 1: Write RED WMR/P32/cache tests.**

```python
def test_joint_port_reuses_exact_cycle_context_wmr() -> None:
    context = _education_cycle_substrate_context()
    observation = JointSimulationPort(cycle_substrate_context=context)(
        candidate=_education_candidate(),
        problem=_education_problem(),
        cycle_index=0,
    )
    assert observation.world_model_record is context.world_model_record
    assert observation.diagnostics["world_model_source"] == "cycle_substrate_context"


def test_shaped_wmr_ref_without_resolved_object_is_rejected() -> None:
    problem = _problem_with_world_ref("world_model_record_0123456789abcdef")
    observation = JointSimulationPort(repo_root=Path.cwd())(
        candidate=_candidate(), problem=problem, cycle_index=0
    )
    assert observation.status == "simulation_blocked"
    assert "world_model_record_unresolved" in observation.authority_blockers


def test_n7_registry_owner_failure_never_builds_bootstrap_authority(monkeypatch) -> None:
    monkeypatch.setattr(generation_cycle, "build_substrate_registry_from_existing_catalogs", _raise_owner_unavailable)
    run = asyncio.run(_run_acquisition_required_without_registry())
    assert run.cycles[0].terminal_kind == "acquisition_required"
    assert "n7_substrate_registry_unresolved" in run.cycles[0].counterexample.description
    assert "n6.bootstrap." not in json.dumps(run.model_dump(mode="json"))
```

Add a cache invalidation test using a second internally coherent registry/WMR pair: the registry content changes and the corresponding WMR is rebuilt/bound to it. Mutating only the registry hash while retaining the old WMR is an invalid-context RED, not a valid cache case. Add a no-hints N8 test accepting either a canonical catalog WMR or a typed `value_world_model_record_unwired` refusal—never fixed-UA contamination.

- [x] **Step 2: Run the new tests and observe RED.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_generation_cycle.py tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_acquisition_planner.py -k 'cycle_context_wmr or shaped_wmr or bootstrap_authority or cache_invalidation or no_hints' -q
```

- [x] **Step 3: Inject the context and remove the bootstrap constructor.**

Make the controller construct defaults as follows:

```python
self._generation_port = generation_port or N4GenerationPort(
    model_id=str(model_id), repo_root=repo_root, cycle_substrate_context=cycle_substrate_context
)
self._simulation_port = simulation_port or JointSimulationPort(
    repo_root=repo_root, cycle_substrate_context=cycle_substrate_context
)
self._value_port = value_port or FoundryValuePort(repo_root=repo_root)
```

`JointSimulationPort._boundary_world_model_record` returns the exact context WMR when present. Without context, it may resolve a concrete canonical owner WMR; missing owners produce `simulation_blocked`. Cache keys contain registry/WMR/problem/slot hashes only.

Delete the `n6.bootstrap.*` registration block. Convert registry-owner failure into the existing acquisition-required terminal with an explicit `n7_substrate_registry_unresolved` limitation/counterexample reason; do not fabricate an `AcquisitionReceipt`.

- [x] **Step 4: Run the N7 blast radius and focused regressions.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_generation_cycle.py tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_acquisition_planner.py -k 'acquisition or registry or boundary_wmr or no_hints or bootstrap' -q
python3 tools/quality/validation/check_layer3_gy_acquisition_contract.py --check
python3 tools/quality/validation/check_layer3_gy_acquisition_contract.py --corrupt-field-drift-check
python3 tools/quality/validation/check_layer3_gy_acquisition_contract.py --rederive-audit
.venv/bin/ruff check src/polisyos/runtime/quality/generation_cycle.py tests/unit/runtime/quality/test_generation_cycle.py tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_acquisition_planner.py
```

- [x] **Step 5: Commit the structural fence.**

```bash
git add src/polisyos/runtime/quality/generation_cycle.py tests/unit/runtime/quality/test_generation_cycle.py tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_acquisition_planner.py tools/quality/validation/check_layer3_gy_acquisition_contract.py
git commit -m "fix: fence synthetic cycle substrate authority"
```

## Task 5: Prove the Stage-1 education grounding-input movement

**Files:**
- Modify: `tools/quality/validation/check_layer3_gy_second_domain_pack.py`
- Modify: `tests/unit/runtime/quality/test_second_domain_pack.py`
- Regenerate: `architecture/policy_design_case/layer3_gy_second_domain_cycle_entry_trace.json`
- Regenerate: `architecture/policy_design_case/layer3_gy_second_domain_free_grow_gaps.json`
- Regenerate if content-bound references change: `architecture/policy_design_case/layer3_gy_second_domain_pack.json`

- [x] **Step 1: Write a RED semantic trace assertion.**

```python
def test_education_cycle_attempts_exact_pack_levers_before_honest_grounding_terminal() -> None:
    trace = checker.build_live_cycle_trace(REPO_ROOT)
    stage = trace["stage_attempts"]
    assert set(stage["generation"]["proposed_operator_kinds"]) == EXPECTED_EDUCATION_LEVERS
    assert stage["generation"]["lever_source_hash"] == trace["substrate_input_content_hash"]
    assert stage["generation"]["generation_channel"] == "n4_owner"
    assert stage["generation"]["exact_formalizer_input_hashes"]
    assert stage["grounding"]["attempted"] is True
    assert stage["grounding"]["disposition"] in {
        "novel_cg3",
        "non_binding_abstain",
        "unknown_blocked",
    }
    assert stage["grounding"]["candidate_entry_content_hash"] in {
        row["entry_content_hash"] for row in trace["pack_levers"]
    }
    assert stage["cycle_terminal"]["terminal_kind"] == (
        checker.expected_cycle_terminal_for_disposition(stage["grounding"]["disposition"])
    )
    assert stage["grounding"]["disposition"] == "novel_cg3"
    assert stage["cycle_terminal"]["terminal_kind"] == "search_ceiling_repair_required"
    assert stage["cycle_terminal"]["terminal_kind"] != "a_spec_gap"
    assert checker.recompute_baseline_diff(trace, checker.load_committed_baseline(REPO_ROOT))[
        "materially_deeper"
    ] is True
    gap_status = {gap["gap_id"]: gap["status"] for gap in trace["gap_triage"]}
    expected_closed = {
        "s0_to_n4_l6_bridge_missing": "closed",
        "s0_to_n5_wmr_bridge_missing": "closed",
        "s0_to_l6_world_slot_bridge_missing": "closed",
    }
    assert {gap_id: gap_status[gap_id] for gap_id in expected_closed} == expected_closed
```

- [x] **Step 2: Run the test and observe RED because the old trace uses grammar fallback and lacks pack context.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_second_domain_pack.py -k 'exact_pack_levers or grounding_terminal' -q
```

- [x] **Step 3: Update the checker producer to inject the strict context and record per-stage evidence.**

The trace must bind the stable substrate-input hash plus immutable source-pack hash, exact lever entry hashes, concrete WMR hash, N4 prompt-slice hash, exact formalizer input/proposal hashes, `generation_channel="n4_owner"`, grounding attempt/disposition, the independently typed cycle terminal, and a recomputed baseline diff. It must not claim grounded/current-valid when the lever is unbound. The Stage-1 gap producer closes the three pack bridges only from live behavioral receipts: N4 proves the pack slice reached the real drafter/formalizer and a disposition binds an entry hash; N5 proves `JointSimulationPort` returned the exact context WMR with matching registry/WMR/context hashes; L6 proves `_content_bound_candidates` invoked `resolve_intervention_lever`, persisted its typed result on the disposition, and `PolicyGroundingPort` consumed it. Removing any receipt after rehashing is RED. N7 persistence, N8 transport, and N6 validation remain residuals.

- [x] **Step 4: Regenerate serially and verify Stage 1.**

```bash
python3 tools/quality/validation/check_layer3_gy_second_domain_pack.py --write --output-format json
python3 tools/quality/validation/check_layer3_gy_second_domain_pack.py --check
python3 -m pytest tests/unit/runtime/quality/test_second_domain_pack.py -k 'exact_pack_levers or grounding_terminal or pack' -q
python3 tools/quality/validation/check_layer3_gy_design_generation_contract.py --check
python3 -c 'import polisyos.runtime.quality.design_generation'
python3 tools/quality/validation/check_layer3_gy_acquisition_contract.py --check
.venv/bin/ruff check src/polisyos/runtime/quality/cycle_substrate.py src/polisyos/runtime/quality/design_generation.py src/polisyos/runtime/quality/intervention_substrate.py src/polisyos/runtime/quality/generation_cycle.py tools/quality/validation/check_layer3_gy_second_domain_pack.py
```

- [x] **Step 5: Commit the Stage-1 proof and stop if any gate is red.**

```bash
git add tools/quality/validation/check_layer3_gy_second_domain_pack.py tests/unit/runtime/quality/test_second_domain_pack.py architecture/policy_design_case/layer3_gy_second_domain_cycle_entry_trace.json architecture/policy_design_case/layer3_gy_second_domain_free_grow_gaps.json architecture/policy_design_case/layer3_gy_second_domain_pack.json
git add docs/superpowers/journals/2026-07-11-gy-n10-stage-1.md
git commit -m "test: prove education pack reaches honest terminal"
```

---

# Stage 2 — Data-driven transport and generic Foundry value

Stage-1 closeout addendum (2026-07-12): the authorized N5 owner-half restoration from
`c87687ec5`, method-owned queue/stock-flow output contracts, the 35-validator import/collection
census, current-provenance education recapture, and full N4/N5/N6/N7/N8/N9 preservation gates are
green and recorded in `docs/superpowers/journals/2026-07-11-gy-n10-stage-1.md`. Stage 2 begins only
after the closeout commit containing that journal and the frozen Stage-1 artifacts.

## Task 6: Replace fixed transport dimensions with measured S-nodes

**Files:**
- Modify: `src/polisyos/ir/analytics/transportability.py`
- Modify: `src/polisyos/runtime/quality/generation_cycle.py`
- Modify: `tests/unit/runtime/quality/test_value_gate.py`
- Modify: `tools/quality/validation/check_layer3_gy_value_gate_contract.py`

**Interfaces:**
- Add `SelectionDiagramBuilder.add_measured_sigma_variable(variable_name: str, *, source_value: float, target_value: float, severity: Literal["low", "medium", "high"], role: SNodeRole | None, source_ref: str, target_ref: str) -> SelectionDiagramBuilder` and optional `source_ref`/`target_ref` fields on `SNode`.
- `_build_candidate_selection_diagram(*, candidate: object, problem: DesignProblem, world_record: WorldModelRecord, query_treatment: str, query_outcome: str, cycle_substrate_context: CycleSubstrateContext) -> SelectionDiagram` consumes only context data.

- [x] **Step 1: Write RED education/third-pack/no-fallback tests.**

```python
def test_education_selection_diagram_uses_only_pack_covariates() -> None:
    diagram = _build_candidate_selection_diagram(
        candidate=_education_candidate(),
        problem=_education_problem(),
        world_record=_education_world_record(),
        query_treatment="education_teaching_method",
        query_outcome="years_of_schooling",
        cycle_substrate_context=_education_cycle_substrate_context(),
    )
    assert {node.target_variable for node in diagram.s_nodes} == {
        "education_spending",
        "school_quality",
    }
    assert "state_capacity" not in diagram.base_graph.nodes
    assert "institutional_quality" not in diagram.base_graph.nodes


def test_third_pack_transport_vocabulary_flows_without_engine_change() -> None:
    diagram = _diagram_from_context(_water_quality_context())
    assert {node.target_variable for node in diagram.s_nodes} == {"watershed_slope"}


def test_missing_measured_transport_context_blocks_without_defaults() -> None:
    observation = _value_observation(context=_context_without_transport_values())
    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("transport_context_unresolved",)
```

- [x] **Step 2: Run focused tests and observe RED.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_value_gate.py -k 'selection_diagram or transport_vocabulary or transport_context' -q
```

- [x] **Step 3: Extend the IR builder and delete runtime defaults.**

Use the signature:

```python
def add_measured_sigma_variable(
    self,
    variable_name: str,
    *,
    source_value: float,
    target_value: float,
    severity: Literal["low", "medium", "high"],
    role: SNodeRole | None,
    source_ref: str,
    target_ref: str,
) -> SelectionDiagramBuilder:
    if variable_name in self._seen:
        return self
    self._seen.add(variable_name)
    s_node = SNode(
        target_variable=variable_name,
        context_dimension=f"measured:{variable_name}",
        source_value=source_value,
        target_value=target_value,
        delta=abs(target_value - source_value),
        severity=severity,
        role=role,
        source_ref=source_ref,
        target_ref=target_ref,
    )
    self._s_nodes.append(s_node)
    self._sigma_vars.append(SigmaVariable.from_s_node(s_node))
    return self
```

Remove the fixed tuple, all `.72/.68/.42/.36` defaults, `_world_post_conflict`, and jurisdiction-token inference. Missing context returns a typed owner access error; unknown causal role remains unknown rather than being labeled pre-treatment.

- [x] **Step 4: Add N8 source flips for tuple/default restoration and measured-value removal.**

Extend the existing restoring harness; do not replace its mutation denominator. Each patch must make the N8 probe RED and restore the original file hash in `finally`.

- [x] **Step 5: Run focused tests, N8 checker/harness, and Ruff.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_value_gate.py -k 'selection_diagram or transport_vocabulary or transport_context' -q
python3 tools/quality/validation/check_layer3_gy_value_gate_contract.py --check
python3 tools/quality/validation/check_layer3_gy_value_gate_contract.py --source-flip-mutations
.venv/bin/ruff check src/polisyos/ir/analytics/transportability.py src/polisyos/runtime/quality/generation_cycle.py tests/unit/runtime/quality/test_value_gate.py tools/quality/validation/check_layer3_gy_value_gate_contract.py
```

- [x] **Step 6: Commit A1.**

```bash
git add src/polisyos/ir/analytics/transportability.py src/polisyos/runtime/quality/generation_cycle.py tests/unit/runtime/quality/test_value_gate.py tools/quality/validation/check_layer3_gy_value_gate_contract.py
git commit -m "feat: derive value transport from domain data"
```

## Task 7: Add the Foundry-owned method-value projector

**Files:**
- Create: `src/polisyos/foundry/methods/components/value_evidence.py`
- Modify: `src/polisyos/foundry/methods/components/__init__.py`
- Modify: `tests/unit/runtime/quality/test_value_gate.py`

**Interfaces:**
- Produces `MethodValueEvidenceStatus`, `MethodValueRefusal`, and `MethodValueEvidence`.
- Produces `project_method_value_evidence(*, method_signature: MethodSignature, method_result: MethodResult, estimand: EstimandSpec, selected_output_slot: str | None = None) -> MethodValueEvidence | MethodValueRefusal`.

- [x] **Step 1: Write RED output-contract/estimand/uncertainty tests.**

```python
def test_posterior_contract_projects_native_interval() -> None:
    evidence = project_method_value_evidence(
        method_signature=_bayesian_signature(),
        method_result=_typed_posterior_result(interval=(-2.0, 5.0)),
        estimand=_bound_estimand(parameter="coefficients_0"),
    )
    assert isinstance(evidence, MethodValueEvidence)
    assert evidence.status == "value_ready"
    assert evidence.envelope.confidence_interval == (-2.0, 5.0)
    assert evidence.native_contract_id == PosteriorResult.contract_id


def test_shaped_mapping_without_resolved_contract_id_refuses() -> None:
    refusal = project_method_value_evidence(
        method_signature=_bayesian_signature(),
        method_result={"posterior_means": {"coefficients_0": 1.0}},
        estimand=_bound_estimand(parameter="coefficients_0"),
    )
    assert refusal.reason_code == "method_output_contract_unresolved"


def test_pretty_interval_for_wrong_estimand_refuses() -> None:
    refusal = project_method_value_evidence(
        method_signature=_bayesian_signature(),
        method_result=_typed_posterior_result(interval=(-2.0, 5.0)),
        estimand=_bound_estimand(parameter="education_teaching_method"),
    )
    assert refusal.reason_code == "method_estimand_binding_mismatch"
```

Also cover `EconometricResult`, forecasting horizon intervals, distributional/transport bounds, diagnostic-only unsupported methods, heuristic/non-gate-eligible envelopes, and exact deterministic bounds.

- [x] **Step 2: Run tests and observe RED because the Foundry projector is absent.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_value_gate.py -k 'posterior_contract or output_contract_unresolved or wrong_estimand or method_value_projector' -q
```

- [x] **Step 3: Implement the Foundry-owned total projection.**

Use strict models containing at least:

```python
class MethodValueEvidence(BaseModel):
    status: Literal["value_ready", "value_limited"]
    method_fqn: str
    method_family: str
    native_contract_id: str
    estimand: EstimandSpec
    envelope: UncertaintyEnvelope
    diagnostic_refs: tuple[str, ...]
    truthfulness_receipt: TruthfulnessReceipt | None
    limitation_codes: tuple[str, ...]
    content_hash: str


class MethodValueRefusal(BaseModel):
    status: Literal["value_refused"] = "value_refused"
    method_fqn: str
    method_family: str
    reason_code: str
    resolved_contract_id: str | None
    content_hash: str
```

Resolve the output slot from the live signature. Require a typed instance or explicit validation against the slot's contract ID. Reuse `SupportsConsensusTarget`, `EstimandSpec`, `to_uncertainty_envelope`, truthfulness extraction, and native report diagnostics. Do not branch on domain or duplicate the method-family denominator.

- [x] **Step 4: Run projector tests and Ruff.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_value_gate.py -k 'posterior_contract or output_contract_unresolved or wrong_estimand or method_value_projector' -q
.venv/bin/ruff check src/polisyos/foundry/methods/components/value_evidence.py src/polisyos/foundry/methods/components/__init__.py tests/unit/runtime/quality/test_value_gate.py
```

- [x] **Step 5: Commit the Foundry owner.**

```bash
git add src/polisyos/foundry/methods/components/value_evidence.py src/polisyos/foundry/methods/components/__init__.py tests/unit/runtime/quality/test_value_gate.py
git commit -m "feat: project typed Foundry value evidence"
```

## Task 8: Integrate generic inputs and prove both A2 directions

**Files:**
- Modify: `src/polisyos/runtime/quality/generation_cycle.py`
- Modify: `tests/unit/runtime/quality/test_value_gate.py`
- Modify: `tools/quality/validation/check_layer3_gy_value_gate_contract.py`
- Modify: `tools/quality/validation/check_layer3_gy_second_domain_pack.py`
- Modify: `tests/unit/runtime/quality/test_second_domain_pack.py`

**Interfaces:**
- Replace panel-only `load_panel_observational_data` orchestration with `resolve_method_input(*, method_signature: MethodSignature, candidate: object, problem: DesignProblem, world_record: WorldModelRecord) -> object`.
- `_s10_calibration_evidence_from_report` consumes `MethodValueEvidence`, not panel/DID fields.
- `_value_outer_set_from_foundry_result` consumes the native envelope and never invents width.
- The observational intake accepts treatment assignment only from a canonical,
  content-bound substrate owner. Missing or caller-supplied assignment returns
  `treatment_assignment_not_owner_derived` before estimator dispatch.

- [x] **Step 1: Commit the independent A2 strict seam.**

Land the advisor-denominator filter/model guard, explicit truthfulness refusal,
education-refusal receipt preservation, unknown-selection-authority refusal,
and atom-only candidate resolution with their already-observed focused tests.
Do not include an observational positive or frozen receipt that still trusts an
atom/test DTO for exposure assignment.

- [x] **Step 2: Commit a read-only substrate census and choose the positive lane.**

Census, in order, (B) L2 causal parameter estimates with native uncertainty,
study contexts, and transport metadata; (A) L1/L2 adoption/rollout assignment
records joinable to an outcome; and (C) another cheap domain with canonical
assignment. Persist table/column/count/content-ref evidence in the Stage-2
journal or a generated census artifact. Select only a lane whose complete input
is owner-resolved and content-bound. The authorized Rev-16 fork below governs
the measured empty-positive case.

### Rev-16 evidence-selected Stage-2 fork (2026-07-13)

The exact-match census was not treated as decisive because it predates CG1's
relation semantics. A second, shadow-only census therefore evaluated the complete
measured denominator through the real CG1 relation engine, with the false-analog
veto fully active and with no atom vocabulary supplied to retrieval. Its frozen
columnar table is
`architecture/policy_design_case/layer3_gy_n10_cg1_l2_relation_census.json`.

The denominator and result are:

- 2 canonical `shadow_bound` atoms;
- 5,124 L2 simulation parameter identities, hence a minimum 10,248
  atom-by-identity denominator;
- 3,579 exactly owner-bound numeric-edge identities and 13,092 fully evaluated
  atom-by-numeric-identity rows, including typed null-edge sentinels;
- 1,848 owner-validated explicit intervals and 1,817 standard-error rows;
- 3,579 UA transport rows, of which 3,351 meet the data-derived `0.35` floor;
- 1,076 `SAT:false-analog` vetoes and 12,016 `UNKNOWN:unknown` results;
- 0 certified exact/specialization/generalization/partial relations with a usable
  interval and transport receipt; therefore 0 Fork-A evidence candidates.

This selects **Fork B**. The end-to-end positive is substrate-gated, not an engine
failure: owner-derived rollout/assignment evidence is `producer_missing`, and the
certified atom-to-SKG numeric-estimate relationship is `bridge_missing`. The N10
Done-when clause "proven on a non-panel method family" is consequently satisfied
at the contract-owner level by the generic projector across six native families
(posterior, econometric, forecasting, distributional, partial-identification, and
transport), including real unverified-truthfulness and unsupported-output refusals.
The production end-to-end lane records the typed substrate residual and routes an
N7 acquisition requirement to acquire either rollout/assignment evidence or a
certified SKG identity bridge. Rule 5 forbids forcing the missing rate.

The compact receipt is content-addressed as
`sha256:b06c1667128178a68dc9031ec52eaff260856bd062b5bfff73c51baeee8481d0`;
the complete raw-table receipt is
`sha256:4ae666db63a0a9a0fb7d4981bc716ab83b1f507494da1d2987f595af9e5049a5`.
The committed checker owns cheap structural validation and the committed
shadow-owner recipe owns the on-demand full rederive, so certificate witnesses
remain replayable rather than trusted by compact shape.

This Rev-16 section supersedes every unconditional positive expectation elsewhere
in this plan. The Stage-2 gate under Fork B is: caller-authored assignment refused;
the hollow `AM/2020` receipt superseded through the canonical writer by an honest
refusal/acquisition receipt; six-family projector tests and both honesty directions
green; genuine advisor-selected education refusal retained; N8 frozen/live/mutation
gates green. Stages 3-4 remain authorized because universality is typed terminal
honesty, not positive-rate manufacture.

- [x] **Step 3: Write the Fork-B owner-intake and acquisition-route RED tests.**

The observational intake rejects a candidate/test/caller-authored assignment
before estimator dispatch. The refusal is consumed by the existing acquisition
owner, whose content-bound requirement names the missing evidence alternative:
canonical rollout/assignment rows or a certified SKG identity bridge. The CG1
census reference is costing/provenance evidence, never runtime authority. A
forged relation certificate, fuzzy name match, or arbitrary indicator must not
open the positive lane.

```python
def test_caller_supplied_treatment_assignment_routes_to_acquisition() -> None:
    observation = _run_observational_value_with_caller_assignment()
    assert observation.status == "value_blocked"
    assert observation.authority_blockers == (
        "treatment_assignment_not_owner_derived",
    )
    requirement = _route_value_gap_to_acquisition(observation)
    assert requirement.status == "acquisition_required"
    assert set(requirement.evidence_alternatives) == {
        "owner_rollout_assignment",
        "certified_skg_identity_bridge",
    }
    assert requirement.census_content_hash == (
        "sha256:b06c1667128178a68dc9031ec52eaff260856bd062b5bfff73c51baeee8481d0"
    )


def test_forged_skg_relation_certificate_cannot_open_value_lane() -> None:
    observation = _run_value_with_unverified_relation_certificate()
    assert observation.status == "value_blocked"
    assert "skg_prior_relation_unresolved" in observation.authority_blockers
```

The positive projector property remains covered by real native contract instances
for all six families. Those contract tests are not promoted into a production
receipt when the owner-input relationship is missing.

- [x] **Step 4: Write the separate education refusal and caller-assignment RED tests.**

```python
def test_real_education_non_panel_method_refuses_unbound_estimand() -> None:
    observation = _run_education_non_panel_value()
    assert observation.status == "value_blocked"
    assert observation.selected_method_fqn is not None
    assert observation.selected_method_fqn != "causal.inference.did.standard@1.0.0"
    assert observation.authority_blockers == ("method_estimand_binding_mismatch",)
    assert observation.method_selection_receipt.selection_authority == "foundry_advisor"
    assert observation.method_selection_receipt.ranked_alternatives


def test_caller_supplied_treatment_assignment_is_refused() -> None:
    observation = _run_observational_value_with_caller_assignment()
    assert observation.status == "value_blocked"
    assert observation.authority_blockers == (
        "treatment_assignment_not_owner_derived",
    )
```

- [x] **Step 5: Run the tests and observe RED at the owner-intake boundary.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_acquisition_planner.py -k 'treatment_assignment_not_owner_derived or skg_prior_relation_unresolved or real_education_non_panel' -q
```

- [x] **Step 6: Implement generic input materialization and thin runtime consumption.**

Selection derives `DataCharacteristics` from owner data and resolves a live catalog
signature only after the owner intake succeeds. Under Fork B no assignment producer
or SKG bridge is invented: the owner boundary refuses, the typed acquisition gap is
preserved, and estimator dispatch does not occur. Independently, runtime consumption
of `project_method_value_evidence` is total over the six-family contract denominator,
passes diagnostics to the real calibration verifier, and never reads panel-only
fields on a non-panel report. Preserve DID behavior through its own report adapter.

- [x] **Step 7: Derive the family denominator and extend both-way source flips.**

The N8 validator loads the live catalog snapshot, derives every family, and requires a total supported/limited/refused classification. Add restoring flips for:

- native uncertainty projection removed -> the six-family projector denominator
  loses a supported native contract -> RED;
- generic auto-pass of an uncalibratable report -> RED;
- estimand binding removed while interval remains -> RED;
- native interval replaced by hand-set width -> RED;
- advisor selection replaced by a hardwired method FQN -> RED with
  `value_method_selection_fixed_default`; and
- caller-supplied treatment assignment admitted -> RED with
  `treatment_assignment_not_owner_derived`;
- a forged/unverified CG1 relation certificate admitted -> RED; and
- the Fork-B acquisition residual or census provenance removed -> RED.

- [x] **Step 8: Run Stage-2 gate.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_second_domain_pack.py -k 'non_panel or value or transport' -q
python3 tools/quality/validation/check_layer3_gy_value_gate_contract.py --check
python3 tools/quality/validation/check_layer3_gy_value_gate_contract.py --source-flip-mutations
python3 tools/quality/validation/check_layer3_gy_second_domain_pack.py --check
rg -n "if .*education|if .*environment|if .*energy|if .*governance|match .*education|match .*environment|match .*energy|match .*governance" src/polisyos/runtime/quality/generation_cycle.py src/polisyos/runtime/quality/design_generation.py src/polisyos/runtime/quality/intervention_substrate.py
.venv/bin/ruff check src/polisyos/foundry/methods/components/value_evidence.py src/polisyos/runtime/quality/generation_cycle.py tools/quality/validation/check_layer3_gy_value_gate_contract.py tools/quality/validation/check_layer3_gy_second_domain_pack.py tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_second_domain_pack.py
```

The `rg` output must contain no domain-name branch; comments/test labels are reviewed manually and do not excuse a branch.

- [x] **Step 9: Commit A2 only after the Fork-B dual evidence exists.**

The two required receipts are the production refusal/acquisition receipt and the
genuine advisor-selected education refusal. The six-family contract denominator
is frozen alongside them; no `value_ready` receipt is required or permitted from
the measured empty owner-input denominator.

```bash
git add src/polisyos/runtime/quality/generation_cycle.py tools/quality/validation/check_layer3_gy_value_gate_contract.py tools/quality/validation/check_layer3_gy_second_domain_pack.py tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_second_domain_pack.py
git commit -m "feat: generalize value over Foundry contracts"
```

---

# Stage 3 — Depth-N router, GY-G strangle, and one-directional N6 repair

## Task 9: Make single-terminal N6 validation coherent without weakening positives

**Files:**
- Modify: `src/polisyos/runtime/quality/generation_cycle.py`
- Modify: `tests/unit/runtime/quality/test_generation_cycle.py`
- Modify: `tools/quality/validation/check_layer3_gy_generation_cycle_contract.py`

- [x] **Step 1: Write RED positive and fabricated-negative tests.**

```python
def test_one_cycle_honest_terminal_validates() -> None:
    run = _one_cycle_run(terminal_kind="acquisition_required", next_action="escalate")
    assert validate_generation_cycle_run(run) == ()


def test_one_cycle_unreachable_terminal_combination_is_rejected() -> None:
    run = _one_cycle_run(terminal_kind="frontier_stable", next_action="advance")
    assert any(
        issue["code"] == "terminal_next_action_incoherent"
        for issue in validate_generation_cycle_run(run)
    )
```

Add the fabricated combination to the checker's mutation denominator; retain every existing mutation ID.
In particular, keep `fake_cycle_same_candidate_repeated`, front-routing, VOI-routing, terminal-denominator, and strangle witnesses RED-capable.

- [x] **Step 2: Run focused tests and observe RED only for the two-cycle runtime requirement/new mutation.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_generation_cycle.py -k 'one_cycle_honest or unreachable_terminal' -q
```

- [x] **Step 3: Remove only the runtime two-cycle check and add coherence rules.**

Require at least one cycle, enum-derived full denominator, no terminal `advance`, completed/blocked reason consistency, and coherent front/VOI/revision state. Keep the frozen two-cycle positive in the checker.

- [x] **Step 4: Run the full N6 battery.**

```bash
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --check
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --corrupt-field-drift-check
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --rederive-audit
python3 -m pytest tests/unit/runtime/quality/test_generation_cycle.py -q
.venv/bin/ruff check src/polisyos/runtime/quality/generation_cycle.py tools/quality/validation/check_layer3_gy_generation_cycle_contract.py tests/unit/runtime/quality/test_generation_cycle.py
```

- [x] **Step 5: Commit the one-directional fix.**

```bash
git add src/polisyos/runtime/quality/generation_cycle.py tools/quality/validation/check_layer3_gy_generation_cycle_contract.py tests/unit/runtime/quality/test_generation_cycle.py
git commit -m "fix: validate honest single cycle terminals"
```

## Task 10: Add the thin recursive generation-cycle router

**Files:**
- Create: `src/polisyos/runtime/quality/recursive_generation_cycle.py`
- Modify: `src/polisyos/runtime/quality/__init__.py`
- Create/Modify: `tests/unit/runtime/quality/test_depth_n_universality.py`
- Create: `src/polisyos/runtime/http/services/control/generation_cycle.py`
- Modify: `tests/unit/runtime/http/test_nl_pipeline_materialization.py`

**Interfaces:**
- Produces `RecursiveCycleBudget`, `RecursiveCycleNode`, `RecursiveGenerationCycleRun`, and `RecursiveGenerationCycleController`.
- Produces service `compile_and_run_recursive_generation_cycle(*, raw_request: str, compiler_gateway: object, controller: RecursiveGenerationCycleController, budget_state: BudgetState, cycle_substrate_context: CycleSubstrateContext | None = None) -> CompiledRecursiveGenerationCycleRun` that calls the existing NL compiler and then the router.

- [x] **Step 1: Write RED Lane-0 depth and NL-front-door tests.**

```python
@pytest.mark.asyncio
async def test_recursive_router_executes_observed_depth_above_two() -> None:
    result = await _lane0_recursive_controller().run(
        _root_problem(), budget_state=_budget(), recursive_graph=_depth_three_graph()
    )
    assert result.observed_max_depth == 3
    assert {node.depth for node in result.nodes} == {0, 1, 2, 3}
    assert all(node.cycle_run.cycles for node in result.leaf_nodes)


@pytest.mark.asyncio
async def test_plain_language_front_door_calls_real_design_problem_compiler() -> None:
    result = await compile_and_run_recursive_generation_cycle(
        raw_request="Improve rural school completion without inventing legal authority.",
        compiler_gateway=_recording_gateway_for_raw_request(),
        controller=_lane0_recursive_controller(),
        budget_state=_budget(),
    )
    assert result.design_problem.nl_provenance.raw_request.startswith("Improve rural")
    assert result.recursive_run.root_design_problem_ref == _problem_hash(result.design_problem)
```

- [x] **Step 2: Run tests and observe RED because the router/front door are absent.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/http/test_nl_pipeline_materialization.py -k 'recursive_router or plain_language_front_door' -q
```

- [x] **Step 3: Implement the thin router.**

Use strict content-bound result types. The controller accepts an existing `RecursiveDesignGraph`, validated problem-by-node mapping produced from candidate decomposition, a cycle-controller factory, and existing coupling/composition ports. It traverses depth/budget, invokes `GenerationCycleController` only at executable leaves, and delegates every coupling/decomposition/composition decision. It does not define a terminal enum or coupling rule.

- [x] **Step 4: Implement the service bridge.**

`compile_and_run_recursive_generation_cycle` calls `build_design_problem_from_nl_request`, verifies raw-request/tool-response content binding, resolves the caller-supplied substrate context, and invokes the router. The runtime quality layer never imports HTTP.

- [x] **Step 5: Run focused tests and Ruff.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/http/test_nl_pipeline_materialization.py -k 'recursive_router or plain_language_front_door' -q
.venv/bin/ruff check src/polisyos/runtime/quality/recursive_generation_cycle.py src/polisyos/runtime/quality/__init__.py src/polisyos/runtime/http/services/control/generation_cycle.py tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/http/test_nl_pipeline_materialization.py
```

- [x] **Step 6: Commit the thin router.**

```bash
git add src/polisyos/runtime/quality/recursive_generation_cycle.py src/polisyos/runtime/quality/__init__.py src/polisyos/runtime/http/services/control/generation_cycle.py tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/http/test_nl_pipeline_materialization.py
git commit -m "feat: route generation cycles over depth"
```

## Task 11: Require observed N5 coupling and strangle GY-G atomically

**Files:**
- Modify: `src/polisyos/runtime/quality/recursive_generation_cycle.py`
- Modify: `src/polisyos/runtime/quality/generation_cycle.py`
- Modify: `src/polisyos/runtime/quality/workspace/loop.py`
- Modify: `src/polisyos/runtime/quality/design_axes/coupling_composition.py`
- Modify: `tools/quality/validation/check_layer3_gy_composition_artifacts.py`
- Modify: `tests/unit/runtime/quality/test_workspace_loop.py`
- Modify: `tests/unit/runtime/quality/test_depth_n_universality.py`
- Modify: `architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json`
- Modify: its existing ledger validator/test if generated/recomputed

- [x] **Step 1: Write RED coupling/strangle tests.**

```python
def test_missing_coupling_evidence_defaults_toward_entanglement() -> None:
    classification = classify_coupling(
        build_coupling_graph(
            design_ref="design://root",
            module_refs=("module://a", "module://b"),
            module_discovery_ref=None,
            interaction_edges=(),
            evidence_state="absent",
            rule_version_ref="repo://rules/gy-n10",
        )
    )
    assert classification.defaulted_to_more_coupling is True
    assert classification.coupling_regime != "modular"


@pytest.mark.asyncio
async def test_coupled_parent_runs_real_n5_and_records_interactions() -> None:
    result = await _run_coupled_lane0_depth_case()
    assert result.joint_simulation_receipts
    assert result.joint_simulation_receipts[0].interaction_count > 0
    assert result.joint_simulation_receipts[0].k_world_ref_before == (
        result.joint_simulation_receipts[0].k_world_ref_after
    )


def test_gy_g_strangle_receipt_has_no_production_fixture_callers() -> None:
    receipt = recompute_depth_n_strangle_receipt(REPO_ROOT)
    assert receipt.status == "strangled"
    assert receipt.production_fixture_callers == ()
    assert receipt.default_controller.endswith("RecursiveGenerationCycleController")
```

- [x] **Step 2: Run tests and observe RED because GY-G callers/default remain.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/quality/test_workspace_loop.py -k 'coupling_evidence or coupled_parent or gy_g_strangle' -q
```

- [x] **Step 3: Make coupling evidence explicit and consume real N5.**

Remove the default `evidence_state="observed"` or require all production callers to pass it explicitly. Missing producer evidence uses `absent`. The router supplies the same graph and intervention set to `JointSimulationHorizonController`; if engine decisions are unsupported or trajectories are absent, surface `simulation_blocked` rather than `joint_simulated`.

- [x] **Step 4: Perform the P28 default flip and predecessor removal in one change.**

Remove/fence `WorkspaceLoop.run_recursive_case`, `coupling_graph_for_subdesigns`, `_recursive_case_child_fixtures`, and the duplicate-case default. Rewrite composition artifact generation to use the recursive controller. Recompute the ledger row from a caller census and behavioral route. Explicitly list any test-only exemption.

- [x] **Step 5: Add restoring source flips.**

Add flips that reintroduce a fixture caller, default an empty graph to observed independence, skip N5 for a coupled parent, and label unsupported N5 output `joint_simulated`. Each must turn the N10 probe RED and restore source.

- [x] **Step 6: Run Stage-3 gate.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/quality/test_workspace_loop.py -q
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --check
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --corrupt-field-drift-check
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --rederive-audit
python3 tools/quality/validation/check_layer3_gy_joint_simulation_horizon_contract.py --check
python3 tools/quality/validation/check_layer3_gy_composition_artifacts.py --check
.venv/bin/ruff check src/polisyos/runtime/quality/recursive_generation_cycle.py src/polisyos/runtime/quality/generation_cycle.py src/polisyos/runtime/quality/workspace/loop.py src/polisyos/runtime/quality/design_axes/coupling_composition.py tools/quality/validation/check_layer3_gy_composition_artifacts.py tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/quality/test_workspace_loop.py
```

- [x] **Step 7: Commit the atomic strangle/default flip.**

```bash
git add src/polisyos/runtime/quality/recursive_generation_cycle.py src/polisyos/runtime/quality/generation_cycle.py src/polisyos/runtime/quality/workspace/loop.py src/polisyos/runtime/quality/design_axes/coupling_composition.py tools/quality/validation/check_layer3_gy_composition_artifacts.py tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/quality/test_workspace_loop.py architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json
git commit -m "feat: strangle fixed recursive cycle"
```

- [x] **Step 8: Land every Stage-3 rebaseline before proof capture.**

Regenerate and commit every depth-N, GY-G, N6, composition, and coupling
artifact affected by Stage 3.  Stage 4 may not begin with an upstream artifact
or receipt left dirty or knowingly stale.  This is the provenance-ordering law:
the census -> DesignProblem -> prompt-hash chain must have a committed base
before any expensive proof run is captured.

---

# Stage 4 — Three proof runs, frozen contract, and final gates

## Stage-4 entry gate: prove upstream provenance stability

Before Task 12 writes or captures any proof receipt, recompute the complete
census -> DesignProblem -> prompt-hash provenance chain against the committed
Stage-3 base and verify every frozen upstream artifact.  Record the resulting
refs and hashes in the Stage-4 journal.  The entry gate fails if the worktree has
an uncommitted upstream rebaseline, if a provenance link resolves to a stale
artifact, or if a recomputation changes a frozen hash.

If a Stage-4 discovery nevertheless requires an upstream artifact rebaseline,
land that owner correction first and honestly recapture every affected proof
run.  A proof receipt captured before its upstream provenance stabilized is not
reused, even when its terminal label happens to match.

### Stage-4 provenance checkpoint (2026-07-14)

The entry audit found the expected post-Stage-3 prompt-provenance ripple before
any proof capture. The N4 writer re-froze the unchanged semantic payload at
artifact SHA-256 `a7457d8cc0f304a3fdd9c128d3567a3e715cc2446dd61547bec0bef0aa0d76ca`.
That required a full owner recomputation of the Fork-B CG1/L2 census, which
preserved all 13,092 relation decisions and zero eligible positives while
moving the compact content hash to
`sha256:c6822ee88e9815508799f65e829086ef30e8809c00bca26bfa529dae3deea60c`
and the raw-table hash to
`sha256:1e87684360da9bfdd1c8db3b97581b174b1b167b93f1be4113615d36566dfdfc`.
The first N8 v2 writer re-bound those content-addressed inputs without semantic
terminal drift. That intermediate N8 change correctly invalidated the downstream N10a semantic projection,
domain census, DesignProblem, and education N4 capture. E7 replay proved the
old five-row journal's prompts stale, so one journal-first current-provenance
capture was accepted through the canonical owner. It proposed all four pack
levers, reached content-bound `candidate_unbound` refusals, and retained the
honest `search_ceiling_repair_required` terminal materially beyond the
`a_spec_gap` baseline. The five N10a artifacts are now byte-stable and their
frozen/live audits agree. The changed education candidate then reissued only
N8's education refusal/transport sections; the N8 first-vertical semantic
projection remained `sha256:b841113b0fa632da91963069ee02934ef89459755489e0ad318ccb5593c6fb18`,
so N10a needed only a closure-receipt replay and no second provider capture.
The converged N8 artifact file SHA-256 is
`ab303f06dc5084194143e423c40b34c8617af8568707e59aca45a17b4a6666f6`;
N8, N10a, and composition are simultaneously frozen/live green. The
cross-artifact stability receipt and clean committed base are therefore green;
Task 12 may begin, and no proof run preceded this gate.

## Task 12: Build the frozen universality contract validator test-first

**Files:**
- Create/Modify: `tests/unit/runtime/quality/test_depth_n_universality.py`
- Create: `tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py`

Generated-artifact lifecycle registration is deliberately deferred to Task 13.  Task 12 has no
owner-produced three-run artifact to register yet; registering a missing or scaffold proof would be
P29 authorial proof.

**Interfaces:**
- Calls `assert_current_checkout(REPO_ROOT)` before parsing modes, reading artifacts/caches, or invoking owners.
- A wrong package path renders `status=fail`, issue `wrong_checkout_resolved`, and exit `1` without entering a proof producer.

- [x] **Step 1: Write RED validator schema/drift/write tests.**

The first RED is the provenance-stability entry gate.  It recomputes the census,
DesignProblem, and prompt-hash refs from their canonical owners and refuses to
enter a proof producer on any drift or dirty upstream rebaseline.

```python
def test_universality_task12_payload_is_honestly_incomplete() -> None:
    payload = validator.build_live_payload(REPO_ROOT, lane="lane0")
    assert payload["proof_status"] == "proof_runs_pending"
    assert payload["domain_runs"] == {}
    assert payload["non_panel_evidence"]["fork"] == "B"
    assert payload["non_panel_evidence"]["status"] == "acquisition_required"
    assert payload["non_panel_evidence"]["supported_native_families"] == 6
    assert payload["non_panel_evidence"]["fork_a_candidate_count"] == 0
    assert payload["education_refusal"]["status"] == "value_blocked"
    assert payload["depth_evidence"]["observed_max_depth"] > 2


def test_universality_contract_content_hash_rejects_corruption() -> None:
    payload = validator.build_live_payload(REPO_ROOT, lane="lane0")
    payload["proof_status"] = "complete"
    report = validator.validate_payload(payload)
    assert any(issue["code"] == "contract_content_hash_mismatch" for issue in report["issues"])


def test_universality_write_is_byte_stable(tmp_path: Path) -> None:
    first = validator.write_payload(REPO_ROOT, tmp_path / "proof.json")
    second = validator.write_payload(REPO_ROOT, tmp_path / "proof.json")
    assert first == second


def test_universality_validator_refuses_wrong_checkout() -> None:
    result = _run_validator_with_pythonpath(MAIN_CHECKOUT / "policy-engine/src", "--check")
    assert result.returncode == 1
    assert "wrong_checkout_resolved" in result.stdout + result.stderr


def test_stage4_entry_refuses_upstream_provenance_drift() -> None:
    report = validator.check_provenance_stability(REPO_ROOT)
    assert report.status == "stable"
    assert report.census_ref
    assert report.design_problem_refs
    assert report.prompt_hashes
```

- [x] **Step 2: Run tests and observe RED because the validator is absent.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py -k 'universality_contract or byte_stable' -q
```

- [x] **Step 3: Implement validator modes and total semantic validation.**

Implement:

```text
--check
--corrupt-field-drift-check       exits 1 when corruption is correctly detected
--rederive-audit
--source-flip-mutations
--write
--output-format {text,json}
```

Run `check_provenance_stability` before every mode that can produce or validate
Stage-4 proof receipts.  The gate is read-only and content-addressed; wall time
and timestamps remain outside every content hash.

Task 12's in-memory payload includes the stable upstream refs, Fork-B evidence, education's current
`value_blocked` refusal, depth/composition/strangle receipts, explicit missing-capability labels, and
`contract_content_hash`.  It MUST say `proof_status=proof_runs_pending`, carry an empty
`domain_runs`, and refuse canonical `--write`/`--check` completion while the artifact is absent.
Task 13 extends this same validator with the three real runs and remaining capstone fields.  Hash
validation excludes only declared runtime metrics/times. Add a restoring `wrong_checkout_resolved`
source flip that points `PYTHONPATH` at the main checkout and proves the validator refuses before
producer execution.

- [x] **Step 4: Verify the focused scaffold without registering a proof artifact.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py -k 'universality_contract or byte_stable' -q
.venv/bin/ruff check tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py tests/unit/runtime/quality/test_depth_n_universality.py
```

- [x] **Step 5: Commit the validator scaffold before live proof writes.**

```bash
git add tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py tests/unit/runtime/quality/test_depth_n_universality.py
git commit -m "feat: add depth-N universality validator"
```

## Task 13: Produce three content-bound plain-language runs

**Files:**
- Modify: `tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py`
- Modify: `tests/unit/runtime/quality/test_depth_n_universality.py`
- Create/Regenerate: `architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json`
- Modify: `architecture/generated_artifacts.toml`
- Regenerate: `docs/reference/generated-artifacts.md`

- [x] **Step 1: Write RED semantic assertions for the three run classes.**

Use these exact structurally distinct raw requests so the compiler recordings are replayable and not case aliases:

```text
first_vertical: Design a policy to improve average household income and MSME survival in Ukraine under wartime fiscal constraints, considering a state-backed credit guarantee, and identify every evidence gap before recommendation.
education: Increase years of schooling and tertiary enrollment using evidence-backed teaching or learning interventions; do not assume that an education ministry can write to any simulation lever.
unseen: Reduce residential peak electricity demand and particulate emissions during heat waves without shifting costs onto low-income renters.
```

The tests assert:

- first vertical reaches an honest terminal through generalized N4-N9 paths;
- education proposes exact pack levers, attempts grounding/value/acquisition, refuses non-panel estimand honestly, and does not promote;
- unseen no-pack reaches an acquisition/abstention/spec-gap terminal with no UA/education WMR, lever, or transport contamination;
- all raw requests are compiled by `build_design_problem_from_nl_request`; and
- replacing any compiler receipt with the committed N10a smoke DTO fails `cycle_driven_by_pinned_fixture`.

- [x] **Step 2: Run Lane-0/cached tests and observe missing proof fields RED.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py -k 'first_vertical or education_run or unseen_domain or pinned_fixture' -q
```

- [x] **Step 3: Implement E1/E3/E5/E6 proof orchestration.**

Use content-addressed compiler recordings keyed by raw request, tool schema, provider/model, and raw response. Use Lane-0 mini-worlds for logic, cached owner data for Lane 1, and journal the one cold two-domain closeout before invoking live owners. Capture wall time outside content hashes.

Capture-resilience addendum (2026-07-14): normalized compiler/span responses are appended to the
ignored operational journal before strict `DesignProblem` admission. A response becomes a reusable
local recording only after canonical-owner replay succeeds, and the recording is replaced
atomically. The predetermined alternate compiler plan gives each model at most one attempt per raw
request; typed compiler refusals advance to the next model without retrying the refused model.
Compiler replay uses the model recorded in that receipt, while the explicitly constructed
production recursive controller retains the independently configured N4 leaf model. A partial
domain closeout is resumed from replay-validated local recordings and cannot mint a second
`cold_domain_closeout_started` event.

Supported-model addendum (2026-07-14): the live gateway catalog contains exactly Kimi and MiniMax.
MiniMax emitted think-prefixed function arguments, which the deliberately strict gateway boundary
correctly refused; the earlier Qwen plan entry was absent from the live catalog. The canonical NL
compiler now states its schema-owned non-empty collection contract generically in the structured
request. The remaining live plan is one post-repair Kimi attempt. It is not a same-state retry: the
compiler prompt hash changed, while the schema, gateway parser, admissibility verifier, and exact
raw requests remain unchanged. A second refusal exhausts the supported-model denominator and is a
hard stop.

- [x] **Step 4: Run one cold two-domain closeout serially with full budget, or record the exact cloud blocker.**

Do not retry concurrently. A missing credential/provider is recorded as a cloud residual; it may not be replaced by a fixture DTO.

Task-13 blocker note (2026-07-14): the cold domain closeout never began because the live compiler
denominator exhausted before producing the first strict `DesignProblem`. The catalog contained only
Kimi and MiniMax. MiniMax emitted reasoning-wrapped tool arguments and was correctly refused by the
audited strict gateway. Post-prompt-repair Kimi emitted request-grounded non-empty collections but
hit exactly `3072` completion tokens and ended its tool JSON mid-string (`char 6560`). No compiler
recording, N4 call, domain cache, or canonical artifact exists. The honest redesign is a separately
authorized canonical-compiler output-budget contract: derive/declare enough output budget for the
strict schema and surface provider truncation as a typed `design_problem_output_truncated` refusal.
The gateway parser and `DesignProblem` validators must remain unchanged.

Characterization addendum (2026-07-14, authorized): before selecting that owner configuration,
measure the full live two-model denominator by varying request controls only. The finite sweep uses
the exact generic compiler prompt and first-vertical request with forced `emit_design_problem`,
temperature `0`, and completion ceilings `8192`, `16384`, and `32768`. Kimi is measured at each
ceiling. MiniMax is measured both with its ordinary OpenAI-compatible request and with the
provider-native `reasoning_split=true` control that separates thinking from final output, at each
ceiling the gateway accepts. Unsupported request controls are recorded as `provider_refused`, not
silently dropped or rewritten. Every attempt records model, request controls, completion tokens,
finish reason, response hash, strict-parser disposition, schema disposition, and span-entailment
disposition in the ignored operational JSONL; the evidence summary is committed to the Stage-4
journal. Exploration responses are never proof recordings.

The strict gateway JSON parser, `DesignProblem(extra="forbid")`, and span-entailment verifier stay
byte-for-byte unchanged during characterization. There is no response-side sanitizer, unwrapping,
regex repair, prefix salvage, domain hint, schema-shape injection, or model/domain branch. A winning
configuration must natively produce exactly one clean, complete `emit_design_problem` call and pass
all existing owners. The selected completion budget is a typed compiler-owner policy justified by
the largest observed conforming emission plus explicit headroom; truncation at any configured
ceiling becomes `design_problem_output_truncated`, while malformed non-truncated output retains its
existing strict refusal. Characterization ends at one reproducible supported configuration or at a
typed model-conformance NO-GO; it never loops until green.

Characterization extension (measured, 2026-07-14): the first nine rows found no clean admission,
but they did not establish model exhaustion. Kimi at 16K and 32K emitted the same complete strict
schema (`4313` completion tokens, `finish_reason=stop`) and reached the real span verifier; one
constraint strengthened the source phrase "under wartime fiscal constraints" into an assertion
that expenditure and borrowing capacity were limited, so the verifier correctly returned neutral.
That is a generic candidate-authority prompt defect, not permission to change the verifier. A
second finite nine-row matrix therefore appends this domain-agnostic request invariant: never
interpret, elaborate, or strengthen a cited constraint beyond the exact semantic content of its
source; a named condition with no stated effects cannot acquire inferred consequences. The same
two models, three budgets, and MiniMax `reasoning_split` split are measured. Completed first-matrix
rows are reused from the operational journal rather than re-spending calls. Provider exception
messages are persisted in the extension because the first matrix recorded only their types.

Characterization decision (measured, 2026-07-14): the generic non-strengthening variant made Kimi
clean at all three ceilings. The lowest ceiling, `8192`, then passed independent shadow confirmation
for first-vertical, education, and unseen requests through the unchanged schema and span verifier.
Their completion counts were `5323`, `5152`, and `4187`; all ended with `finish_reason=stop`.
Therefore the compiler owner adopts the generic non-strengthening sentence and a typed output policy
whose observed maximum is `5323` and whose ceiling is the next power of two, `8192` (headroom `2869`,
about 53.9%). The model remains caller/advisor selected; no model id enters the compiler owner.
MiniMax ordinary requests remained reasoning-wrapped, while Gonka explicitly rejected the otherwise
valid provider-native `reasoning_split` parameter as unsupported. Those typed rows remain part of
the denominator. Exploration rows stay shadow-only and are not proof captures.

Proof-envelope correction (measured, 2026-07-14): the first post-checkpoint proof call inherited a
shorter ambient gateway timeout than the 600-second characterization envelope and exhausted it
before any provider response. The proof harness therefore owns an explicit serial capture envelope:
600 seconds, three gateway retries, and local prompt caching disabled. It journals a gateway timeout
as `proof_compiler_gateway_failed` before the existing exhausted-denominator terminal, instead of
letting a transport `RuntimeError` escape as a stack trace. This changes neither model selection nor
any parser/schema/entailment gate. The no-response attempt did not start the cold domain closeout;
one changed-envelope proof attempt remains authorized under E9.

- [ ] **Step 5: Write and immediately check the frozen artifact.**

```bash
python3 tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py --write --output-format json
python3 tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py --check
git diff --exit-code -- architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json
```

- [ ] **Step 6: Commit the proof artifact.**

```bash
git add tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py tests/unit/runtime/quality/test_depth_n_universality.py architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json
git commit -m "test: freeze depth-N universality proof"
```

## Task 14: Reconcile ledgers, gaps, residuals, and source flips

**Files:**
- Modify: `architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json`
- Modify: `architecture/policy_design_case/layer3_gy_second_domain_free_grow_gaps.json`
- Modify: `architecture/policy_design_case/layer3_gy_second_domain_cycle_entry_trace.json`
- Modify: `architecture/policy_design_case/layer3_gy_second_domain_pack.json` if bound hashes change
- Modify: relevant existing ledger/gap validator tests
- Modify: `tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py`

- [ ] **Step 1: Write RED reconciliation tests.**

Require exact seam evidence for the five closed gaps, typed reasons for the two residuals, the GY-G fixture disposition, zero production callers, and the education no-promotion reason.
Require the dedicated integration-debt ledger to enumerate every bounded
never-landed-state reconciliation, its historical evidence and owner-first
disposition, plus the wrong-checkout, wrong-interpreter, and CG-substrate
tripwires.

- [ ] **Step 2: Run focused reconciliation tests and observe RED on stale N10a/ledger rows.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/quality/test_second_domain_pack.py -k 'gap_triage or ledger or residual or no_promotion' -q
```

- [ ] **Step 3: Update generated records from live seam evidence.**

Reverify the three bridge closures already committed at the Stage-1 gate (`s0_to_n4_l6_bridge_missing`, `s0_to_n5_wmr_bridge_missing`, and `s0_to_l6_world_slot_bridge_missing`) without changing their historical closure receipts. Mark `n8_transport_tuple_hardcode` and `n6_single_terminal_validation_gap` closed with their later-stage function/receipt/hash evidence. Keep owner-registration derivation and raw journal persistence residual with their original capability labels and justification.

- [ ] **Step 4: Implement and run every decisive source flip serially.**

The N10 harness records `file:line -> RED -> restored` for every Section-8 class in the specification. It extends but does not alter the N5/N8/N9 restoring harnesses and the N6 mutation battery.

- [ ] **Step 5: Commit reconciliation and source flips.**

```bash
git add architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json architecture/policy_design_case/layer3_gy_second_domain_free_grow_gaps.json architecture/policy_design_case/layer3_gy_second_domain_cycle_entry_trace.json architecture/policy_design_case/layer3_gy_second_domain_pack.json tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/quality/test_second_domain_pack.py
git commit -m "docs: reconcile GY-N10 capability ledger"
```

## Task 15: Run the exact closeout gate and record verbatim evidence

**Files:**
- No planned source modification; if verification exposes a real touched-scope defect, return to that owning task's RED/GREEN cycle before rerunning closeout.
- Final journal is recorded in the frozen proof artifact/runtime-excluded verification section and the handoff response.

- [ ] **Step 1: Re-run the N10a pre-flight.**

```bash
python3 tools/quality/validation/check_layer3_gy_second_domain_pack.py --check
```

- [ ] **Step 2: Run the new contract gates serially.**

```bash
python3 tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py --check
python3 tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py --corrupt-field-drift-check
python3 tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py --rederive-audit
python3 tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py --source-flip-mutations
python3 tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py --write --output-format json
git diff --exit-code -- architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json
```

Expected: corrupt-field command exits `1`; all others exit `0`.

- [ ] **Step 3: Run frozen N4/N5/N6/N7/N8/N9 blast radius serially.**

```bash
python3 tools/quality/validation/check_layer3_gy_design_generation_contract.py --check
python3 -c 'import polisyos.runtime.quality.design_generation'
python3 tools/quality/validation/check_layer3_gy_acquisition_contract.py --check
python3 tools/quality/validation/check_layer3_gy_value_gate_contract.py --check
python3 tools/quality/validation/check_layer3_gy_value_gate_contract.py --source-flip-mutations
python3 tools/quality/validation/check_layer3_gy_promotion_contract.py --check
python3 tools/quality/validation/check_layer3_gy_promotion_contract.py --source-flip-mutations
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --check
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --corrupt-field-drift-check
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --rederive-audit
python3 tools/quality/validation/check_layer3_gy_joint_simulation_horizon_contract.py --check
```

- [ ] **Step 4: Run the exact focused pytest set plus N4/N7 additions.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_generation_cycle.py tests/unit/runtime/quality/test_promotion_sequence.py -q
python3 -m pytest tests/unit/runtime/quality/test_design_generation.py tests/unit/runtime/quality/test_acquisition_planner.py -q
```

- [ ] **Step 5: Run Ruff over every changed Python file and the domain-branch census.**

```bash
.venv/bin/ruff check src/polisyos/runtime/quality/cycle_substrate.py src/polisyos/runtime/quality/design_generation.py src/polisyos/runtime/quality/intervention_substrate.py src/polisyos/runtime/quality/generation_cycle.py src/polisyos/runtime/quality/recursive_generation_cycle.py src/polisyos/runtime/quality/workspace/loop.py src/polisyos/runtime/quality/design_axes/coupling_composition.py src/polisyos/runtime/http/services/control/generation_cycle.py src/polisyos/ir/analytics/transportability.py src/polisyos/foundry/methods/components/value_evidence.py tools/quality/validation/check_layer3_gy_second_domain_pack.py tools/quality/validation/check_layer3_gy_value_gate_contract.py tools/quality/validation/check_layer3_gy_generation_cycle_contract.py tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_generation_cycle.py tests/unit/runtime/quality/test_design_generation.py tests/unit/runtime/quality/test_intervention_substrate.py tests/unit/runtime/quality/test_acquisition_planner.py tests/unit/runtime/quality/test_second_domain_pack.py
rg -n "if .*education|if .*environment|if .*energy|if .*governance|match .*education|match .*environment|match .*energy|match .*governance" src/polisyos/runtime/quality src/polisyos/foundry/methods/components/value_evidence.py
```

Expected: Ruff exits `0`; the branch census returns no engine-domain branch matches.

- [ ] **Step 6: Inspect status and commit only genuine verification repairs.**

```bash
git status --short
git diff --check
```

If verification required a repair, repeat its RED/GREEN test and commit the scoped fix. Do not create a cosmetic closeout commit.

---

## Plan self-review checklist

- Every approved correction has an implementation task and stage gate.
- Task 1R binds the repository interpreter explicitly and restores N2
  `normalized_from` as non-authoritative provenance with a decisive source flip.
- The evidence-selected A2 fork is the Stage-2 exit gate. Fork B freezes a typed
  acquisition residual over the measured zero-positive denominator; education's
  genuine advisor-selected refusal is separate.
- No lane or method is code-pinned. Owner assignment/CG1 relation provenance,
  caller-assignment refusal, the six-family projector denominator, and the
  acquisition route are decisive RED/GREEN properties under Fork B.
- Task 0 pins N10a's historical receipt without weakening live owner rederive; Task 0B structurally rejects a wrong checkout.
- N4 wrappers, the recorded-evidence formalizer accessor, the one-pass import audit, and `GroundingDispositionKind` reconciliation are bounded to Task 1.
- N6 loosening is Stage 3, additive-only, with an unreachable one-cycle RED mutation.
- N7 tests/checker are in Stage 1 and final blast radius before/after the bootstrap fence.
- GY-G removal/default flip is atomic in Task 11.
- The original Section-8 commands are present; N4/N7 and full N6 modes are additive.
- No task authorizes education promotion, a fabricated pass/block, a domain branch, a parallel owner, or a weakened harness.
- The two infrastructure gaps remain typed residuals.
- The final artifact/report carries the integration-debt ledger for the full
  convergence cascade.
- Every stage ends at a fresh verification gate and scoped commit.
