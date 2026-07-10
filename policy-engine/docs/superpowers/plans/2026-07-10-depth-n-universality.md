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
- The frozen proof requires both a real non-panel `value_ready` positive and education's separate real typed non-panel refusal.
- A concrete Bayesian FQN may be pinned in this plan as a deterministic expectation, but runtime code must use the existing registry/advisor selection from candidate/problem/data modality and persist the ranked selection trace; a fixed method default is forbidden.
- Every treatment feature is derived by joining the candidate atom's real treated units/periods to owner-resolved observations; an arbitrary or synthetic treatment indicator is forbidden.
- Do not create a second registry, world, generation cycle, value surface, coupling algebra, or recursion authority.
- Fence fixed-UA WMR creation, shaped-string WMR trust, `n6.bootstrap.*`, and the GY-G fixture structurally; do not patch one caller.
- Preserve every existing N5/N6/N8/N9 decisive mutation. Add coverage; never delete or weaken a gate.
- Run only targeted verification with `python3` and `.venv/bin/ruff`; never run full pytest, backend verify, or CI parity.
- Run exactly one mutating or validating process at a time. Give long owner lanes their full E9 budget.
- Use E1 content-addressed pack/world/engine caches, Lane-0 mini-worlds, cached Lane-1 owners, one cold two-domain closeout, E5 wall times, and E6 journal-first live capture.
- Runtime timestamps and wall time never participate in artifact content hashes. `--write` must be byte-stable.
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

## Task 1: Restore the bounded N4 public owner surface

**Files:**
- Modify: `tests/unit/runtime/quality/test_design_generation.py`
- Modify: `src/polisyos/runtime/quality/intervention_substrate.py`
- Modify: `src/polisyos/runtime/quality/design_generation.py`

**Interfaces:**
- Produces: `production_composed_world_model_record(repo_root: str | Path) -> WorldModelRecord`
- Produces: `intervention_generation_registry_bundle(repo_root: str | Path) -> RegistryBundle`
- Re-exports: the exact `GroundingDispositionKind` imported from `grounding_disposition_vocab`

- [ ] **Step 1: Write the failing import/owner tests.**

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
```

- [ ] **Step 2: Run the two tests and observe RED.**

Run:

```bash
python3 -m pytest tests/unit/runtime/quality/test_design_generation.py -k 'default_n4_stack_imports or canonical_grounding_disposition' -q
```

Expected: collection/import fails because the two public intervention owners do not exist and the local `GroundingDispositionKind` is not the canonical object.

- [ ] **Step 3: Add only the canonical wrappers and vocabulary import.**

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

- [ ] **Step 4: Run the focused tests, direct import, N4 contract, and Ruff.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_design_generation.py -k 'default_n4_stack_imports or canonical_grounding_disposition' -q
python3 -c 'import polisyos.runtime.quality.design_generation'
python3 tools/quality/validation/check_layer3_gy_design_generation_contract.py --check
.venv/bin/ruff check src/polisyos/runtime/quality/intervention_substrate.py src/polisyos/runtime/quality/design_generation.py tests/unit/runtime/quality/test_design_generation.py
```

Expected: all exit `0`. Record this as closure of the long-standing N4 cloud-deferred import residual.

- [ ] **Step 5: Commit the bounded repair.**

```bash
git add src/polisyos/runtime/quality/intervention_substrate.py src/polisyos/runtime/quality/design_generation.py tests/unit/runtime/quality/test_design_generation.py
git commit -m "fix: restore N4 intervention owner surface"
```

## Task 2: Add the content-bound cycle substrate envelope

**Files:**
- Create: `src/polisyos/runtime/quality/cycle_substrate.py`
- Modify: `src/polisyos/runtime/quality/__init__.py`
- Modify: `tests/unit/runtime/quality/test_substrate_registry.py`
- Modify: `tests/unit/runtime/quality/test_world_model_record.py`
- Modify: `tests/unit/runtime/quality/test_second_domain_pack.py`
- Modify: `tools/quality/validation/check_layer3_gy_second_domain_pack.py`

**Interfaces:**
- Produces strict `CandidateLeverEvidence`, `TransportCovariateObservation`, `TransportContextEvidence`, and `CycleSubstrateContext`.
- Produces `build_cycle_substrate_context(*, design_problem_ref: str, domain: str, substrate_registry: SubstrateRegistry, selected_registry_entry_hashes: Sequence[str], world_model_record: WorldModelRecord, intervention_substrate: InterventionSubstrateBundle | None, candidate_levers: Sequence[CandidateLeverEvidence], transport_context: TransportContextEvidence | None, pack_content_hash: str | None) -> CycleSubstrateContext`.
- The runtime API accepts objects; only the checker projects the committed N10a JSON into those objects.

- [ ] **Step 1: Write RED hash/authority/generic-shape tests.**

The tests must prove:

```python
def test_cycle_substrate_context_binds_registry_wmr_and_pack_hashes() -> None:
    context = _cycle_substrate_context(domain="education")
    assert context.substrate_registry_content_hash == context.substrate_registry.content_hash
    assert context.world_model_record_content_hash == context.world_model_record.content_hash
    assert context.pack_content_hash == _hash("education-pack")
    assert all(row.status == "candidate_unbound" for row in context.candidate_levers)


def test_cycle_substrate_context_rejects_stale_registry_hash() -> None:
    payload = _cycle_substrate_context(domain="education").model_dump(mode="python")
    payload["substrate_registry_content_hash"] = _hash("stale")
    with pytest.raises(ValueError, match="cycle_substrate_registry_hash_mismatch"):
        CycleSubstrateContext.model_validate(payload)


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

- [ ] **Step 2: Run the new tests and observe RED because the envelope/projector is absent.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_substrate_registry.py tests/unit/runtime/quality/test_world_model_record.py tests/unit/runtime/quality/test_second_domain_pack.py -k 'cycle_substrate or third_pack_vocabulary' -q
```

- [ ] **Step 3: Implement the strict envelope and recomputing hash.**

Use this public shape; all models use `ConfigDict(extra="forbid", frozen=True)`:

```python
class CandidateLeverEvidence(BaseModel):
    lever_id: str
    instrument: str
    target_concept: str
    status: Literal["candidate_unbound"] = "candidate_unbound"
    entry_content_hash: str
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
    pack_content_hash: str | None
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
    content_hash: str
```

`build_cycle_substrate_context` must revalidate the registry/WMR, resolve every selected entry hash from the registry, and recompute `content_hash` from stable hashes and candidate evidence. It must not accept a pack path.

- [ ] **Step 4: Add the checker-only pack projector.**

In `check_layer3_gy_second_domain_pack.py`, add a helper that:

1. validates `manifest_content_hash` using the existing pack hash routine;
2. validates `owner_query_results.s0_registry.registry_payload` as `SubstrateRegistry`;
3. verifies the registry content hash and selected education entry hashes;
4. projects lever and transport rows into the strict candidate models; and
5. receives a concrete WMR from the canonical boundary builder rather than creating runtime authority from JSON presence.

- [ ] **Step 5: Run focused tests and Ruff.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_substrate_registry.py tests/unit/runtime/quality/test_world_model_record.py tests/unit/runtime/quality/test_second_domain_pack.py -k 'cycle_substrate or third_pack_vocabulary' -q
.venv/bin/ruff check src/polisyos/runtime/quality/cycle_substrate.py src/polisyos/runtime/quality/__init__.py tools/quality/validation/check_layer3_gy_second_domain_pack.py tests/unit/runtime/quality/test_substrate_registry.py tests/unit/runtime/quality/test_world_model_record.py tests/unit/runtime/quality/test_second_domain_pack.py
```

- [ ] **Step 6: Commit the canonical intake envelope.**

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
- Produce `InterventionLeverRefusal` and return `InterventionLeverResolution | InterventionLeverRefusal` when explicit candidate evidence is supplied.

- [ ] **Step 1: Write RED tests for exact education levers and honest unbound resolution.**

```python
def test_prompt_slice_uses_injected_candidate_levers_without_binding_them() -> None:
    result = derive_lever_space_prompt_slice(
        _education_problem(),
        repo_root=Path.cwd(),
        reference=_reference(),
        cycle_substrate_context=_education_cycle_substrate_context(),
    )
    assert {row.operator_kind for row in result.entries} == {
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
        candidate_evidence=_education_candidate_lever(),
        world_model_record=_education_world_record(),
    )
    assert isinstance(result, InterventionLeverRefusal)
    assert result.status == "candidate_unbound"
    assert result.reason_code == "knob_operator_unresolved"
```

Add a third-pack-shaped lever test and a negative proving a candidate lever never appears in the writable knob dictionary.

- [ ] **Step 2: Run the focused tests and observe RED.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_design_generation.py tests/unit/runtime/quality/test_intervention_substrate.py tests/unit/runtime/quality/test_generation_cycle.py -k 'candidate_lever or candidate_unbound or injected_candidate' -q
```

- [ ] **Step 3: Implement minimal typed propagation.**

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

Add a strict refusal model with a recomputed hash:

```python
class InterventionLeverRefusal(_StrictModel):
    status: Literal["candidate_unbound", "acquisition_required"]
    operator_kind: str
    reason_code: str
    candidate_entry_content_hash: str
    substrate_registry_content_hash: str
    world_model_record_content_hash: str
    content_hash: str
```

Preserve existing exception behavior when no explicit candidate evidence is supplied; this bounds the change and preserves old callers.

- [ ] **Step 4: Run focused and frozen N4 checks.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_design_generation.py tests/unit/runtime/quality/test_intervention_substrate.py tests/unit/runtime/quality/test_generation_cycle.py -k 'candidate_lever or candidate_unbound or injected_candidate' -q
python3 tools/quality/validation/check_layer3_gy_design_generation_contract.py --check
python3 -c 'import polisyos.runtime.quality.design_generation'
.venv/bin/ruff check src/polisyos/runtime/quality/design_generation.py src/polisyos/runtime/quality/intervention_substrate.py src/polisyos/runtime/quality/generation_cycle.py tests/unit/runtime/quality/test_design_generation.py tests/unit/runtime/quality/test_intervention_substrate.py tests/unit/runtime/quality/test_generation_cycle.py
```

- [ ] **Step 5: Commit the N4/L6 bridge.**

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

- [ ] **Step 1: Write RED WMR/P32/cache tests.**

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

Add a cache invalidation test where only `substrate_registry.content_hash` changes, and a no-hints N8 test accepting either a canonical catalog WMR or a typed `value_world_model_record_unwired` refusal—never fixed-UA contamination.

- [ ] **Step 2: Run the new tests and observe RED.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_generation_cycle.py tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_acquisition_planner.py -k 'cycle_context_wmr or shaped_wmr or bootstrap_authority or cache_invalidation or no_hints' -q
```

- [ ] **Step 3: Inject the context and remove the bootstrap constructor.**

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

- [ ] **Step 4: Run the N7 blast radius and focused regressions.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_generation_cycle.py tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_acquisition_planner.py -k 'acquisition or registry or boundary_wmr or no_hints or bootstrap' -q
python3 tools/quality/validation/check_layer3_gy_acquisition_contract.py --check
python3 tools/quality/validation/check_layer3_gy_acquisition_contract.py --corrupt-field-drift-check
python3 tools/quality/validation/check_layer3_gy_acquisition_contract.py --rederive-audit
.venv/bin/ruff check src/polisyos/runtime/quality/generation_cycle.py tests/unit/runtime/quality/test_generation_cycle.py tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_acquisition_planner.py
```

- [ ] **Step 5: Commit the structural fence.**

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

- [ ] **Step 1: Write a RED semantic trace assertion.**

```python
def test_education_cycle_attempts_exact_pack_levers_before_honest_grounding_terminal() -> None:
    trace = checker.build_live_cycle_trace(REPO_ROOT)
    stage = trace["stage_attempts"]
    assert set(stage["generation"]["proposed_operator_kinds"]) == EXPECTED_EDUCATION_LEVERS
    assert stage["generation"]["lever_source_hash"] == trace["pack_content_hash"]
    assert stage["grounding"]["attempted"] is True
    assert stage["grounding"]["terminal_state"] in {
        "novel_cg3",
        "non_binding_abstain",
        "acquisition_required",
    }
    assert trace["baseline_diff"]["materially_deeper"] is True
```

- [ ] **Step 2: Run the test and observe RED because the old trace uses grammar fallback and lacks pack context.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_second_domain_pack.py -k 'exact_pack_levers or grounding_terminal' -q
```

- [ ] **Step 3: Update the checker producer to inject the strict context and record per-stage evidence.**

The trace must bind the pack hash, exact lever entry hashes, concrete WMR hash, N4 prompt-slice hash, grounding attempt/disposition, and a baseline diff. It must not claim grounded/current-valid when the lever is unbound.

- [ ] **Step 4: Regenerate serially and verify Stage 1.**

```bash
python3 tools/quality/validation/check_layer3_gy_second_domain_pack.py --write --output-format json
python3 tools/quality/validation/check_layer3_gy_second_domain_pack.py --check
python3 -m pytest tests/unit/runtime/quality/test_second_domain_pack.py -k 'exact_pack_levers or grounding_terminal or pack' -q
python3 tools/quality/validation/check_layer3_gy_design_generation_contract.py --check
python3 -c 'import polisyos.runtime.quality.design_generation'
python3 tools/quality/validation/check_layer3_gy_acquisition_contract.py --check
.venv/bin/ruff check src/polisyos/runtime/quality/cycle_substrate.py src/polisyos/runtime/quality/design_generation.py src/polisyos/runtime/quality/intervention_substrate.py src/polisyos/runtime/quality/generation_cycle.py tools/quality/validation/check_layer3_gy_second_domain_pack.py
```

- [ ] **Step 5: Commit the Stage-1 proof and stop if any gate is red.**

```bash
git add tools/quality/validation/check_layer3_gy_second_domain_pack.py tests/unit/runtime/quality/test_second_domain_pack.py architecture/policy_design_case/layer3_gy_second_domain_cycle_entry_trace.json architecture/policy_design_case/layer3_gy_second_domain_free_grow_gaps.json architecture/policy_design_case/layer3_gy_second_domain_pack.json
git commit -m "test: prove education pack reaches grounding"
```

---

# Stage 2 — Data-driven transport and generic Foundry value

## Task 6: Replace fixed transport dimensions with measured S-nodes

**Files:**
- Modify: `src/polisyos/ir/analytics/transportability.py`
- Modify: `src/polisyos/runtime/quality/generation_cycle.py`
- Modify: `tests/unit/runtime/quality/test_value_gate.py`
- Modify: `tools/quality/validation/check_layer3_gy_value_gate_contract.py`

**Interfaces:**
- Add `SelectionDiagramBuilder.add_measured_sigma_variable(variable_name: str, *, source_value: float, target_value: float, severity: Literal["low", "medium", "high"], role: SNodeRole | None, source_ref: str, target_ref: str) -> SelectionDiagramBuilder` and optional `source_ref`/`target_ref` fields on `SNode`.
- `_build_candidate_selection_diagram(*, candidate: object, problem: DesignProblem, world_record: WorldModelRecord, query_treatment: str, query_outcome: str, cycle_substrate_context: CycleSubstrateContext) -> SelectionDiagram` consumes only context data.

- [ ] **Step 1: Write RED education/third-pack/no-fallback tests.**

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

- [ ] **Step 2: Run focused tests and observe RED.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_value_gate.py -k 'selection_diagram or transport_vocabulary or transport_context' -q
```

- [ ] **Step 3: Extend the IR builder and delete runtime defaults.**

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

- [ ] **Step 4: Add N8 source flips for tuple/default restoration and measured-value removal.**

Extend the existing restoring harness; do not replace its mutation denominator. Each patch must make the N8 probe RED and restore the original file hash in `finally`.

- [ ] **Step 5: Run focused tests, N8 checker/harness, and Ruff.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_value_gate.py -k 'selection_diagram or transport_vocabulary or transport_context' -q
python3 tools/quality/validation/check_layer3_gy_value_gate_contract.py --check
python3 tools/quality/validation/check_layer3_gy_value_gate_contract.py --source-flip-mutations
.venv/bin/ruff check src/polisyos/ir/analytics/transportability.py src/polisyos/runtime/quality/generation_cycle.py tests/unit/runtime/quality/test_value_gate.py tools/quality/validation/check_layer3_gy_value_gate_contract.py
```

- [ ] **Step 6: Commit A1.**

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

- [ ] **Step 1: Write RED output-contract/estimand/uncertainty tests.**

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

- [ ] **Step 2: Run tests and observe RED because the Foundry projector is absent.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_value_gate.py -k 'posterior_contract or output_contract_unresolved or wrong_estimand or method_value_projector' -q
```

- [ ] **Step 3: Implement the Foundry-owned total projection.**

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

- [ ] **Step 4: Run projector tests and Ruff.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_value_gate.py -k 'posterior_contract or output_contract_unresolved or wrong_estimand or method_value_projector' -q
.venv/bin/ruff check src/polisyos/foundry/methods/components/value_evidence.py src/polisyos/foundry/methods/components/__init__.py tests/unit/runtime/quality/test_value_gate.py
```

- [ ] **Step 5: Commit the Foundry owner.**

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

- [ ] **Step 1: Write the Stage-2-exit real non-panel positive RED test before integration.**

The plan's expected advisor outcome is `bayesian.regression.linear_regression@1.0.0` over the 64 owner-resolved L1 `avg_income` country/year rows already used by N8. Runtime code must not name or default to that FQN: derive `DataCharacteristics` from the real candidate/problem/owner rows, invoke the existing registry/advisor, and persist its full ranked selection trace, including the panel alternatives and why they lost on this shape. Feature zero is the exact binary treatment derived by joining the first vertical candidate atom's real binding (`treated_unit_ids=("AM",)`, `treatment_period=2020`) against those rows; its metadata name is `candidate_credit_guarantee:treatment`. The explicit `EstimandSpec` binds that candidate-derived feature to `coefficients_0`, the `avg_income` outcome, population/time/context, and the same atom. The posterior contract supplies the native credible interval. The resulting runtime observation may remain `identification_status="partial"` and low-grade, but it must be `value_ready` at Stage 2 exit. If the real advisor selects a different semantically valid non-panel method, the receipt records that real choice; if real posterior diagnostics/calibration refuse every bound lane, Stage 2 is NO-GO until the underlying owner semantics are repaired. Do not substitute a hand-built report, force the expected FQN, or defer method choice to closeout.

```python
def test_real_bound_non_panel_method_mints_native_width() -> None:
    observation = _run_real_bound_non_panel_value(credible_mass=0.80)
    widened = _run_real_bound_non_panel_value(credible_mass=0.95)
    assert observation.status == "value_ready"
    assert observation.method_selection_receipt.selection_authority == "foundry_advisor"
    assert observation.method_selection_receipt.selected_method_fqn == (
        observation.selected_method_fqn
    )
    assert observation.method_selection_receipt.ranked_alternatives
    assert any(
        row.method_family == "panel" and row.loss_reasons
        for row in observation.method_selection_receipt.ranked_alternatives
    )
    assert observation.selected_method_fqn != "causal.inference.did.standard@1.0.0"
    assert observation.treatment_provenance.source == "candidate_atom_binding"
    assert observation.treatment_provenance.treated_unit_ids == ("AM",)
    assert observation.treatment_provenance.treatment_period == 2020
    assert observation.treatment_provenance.joined_owner_row_count > 0
    assert observation.estimand.parameter == "coefficients_0"
    assert observation.estimand.treatment_ref == (
        observation.treatment_provenance.candidate_atom_ref
    )
    assert observation.value_receipt.value_outer_set.width[0] > 0.0
    assert widened.value_receipt.value_outer_set.width[0] > (
        observation.value_receipt.value_outer_set.width[0]
    )
    assert observation.value_receipt.calibration_receipt.status == "pass"
```

This test may not use a hand-built report or fixture DTO as the positive; it dispatches the real registered estimator over owner-resolved rows.

- [ ] **Step 2: Write the separate education refusal test.**

```python
def test_real_education_non_panel_method_refuses_unbound_estimand() -> None:
    observation = _run_education_non_panel_value()
    assert observation.status == "value_blocked"
    assert observation.selected_method_fqn is not None
    assert observation.selected_method_fqn != "causal.inference.did.standard@1.0.0"
    assert observation.authority_blockers == ("method_estimand_binding_mismatch",)
    assert observation.value_receipt is None
```

- [ ] **Step 3: Run both tests and observe RED for the expected panel-only/projector reasons.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_value_gate.py -k 'real_bound_non_panel or real_education_non_panel' -q
```

- [ ] **Step 4: Implement generic input materialization and thin runtime consumption.**

Selection derives `DataCharacteristics` from owner data, resolves a live catalog signature, and only then materializes its declared input slots. The runtime calls `project_method_value_evidence`, passes its diagnostics to the real calibration verifier, and derives `ValueOuterSet` from `evidence.envelope`. Remove report-field assumptions for `n_treated`, `n_control`, `pre_periods`, and `post_periods` from the generic path; preserve DID behavior through its own report adapter.

- [ ] **Step 5: Derive the family denominator and extend both-way source flips.**

The N8 validator loads the live catalog snapshot, derives every family, and requires a total supported/limited/refused classification. Add restoring flips for:

- native uncertainty projection removed -> non-panel positive vanishes -> RED;
- generic auto-pass of an uncalibratable report -> RED;
- estimand binding removed while interval remains -> RED;
- native interval replaced by hand-set width -> RED;
- advisor selection replaced by a hardwired method FQN -> RED with
  `value_method_selection_fixed_default`; and
- candidate-derived treatment join replaced by an arbitrary/synthetic feature
  -> RED with `candidate_treatment_provenance_missing`.

- [ ] **Step 6: Run Stage-2 gate.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_second_domain_pack.py -k 'non_panel or value or transport' -q
python3 tools/quality/validation/check_layer3_gy_value_gate_contract.py --check
python3 tools/quality/validation/check_layer3_gy_value_gate_contract.py --source-flip-mutations
python3 tools/quality/validation/check_layer3_gy_second_domain_pack.py --check
rg -n "if .*education|if .*environment|if .*energy|if .*governance|match .*education|match .*environment|match .*energy|match .*governance" src/polisyos/runtime/quality/generation_cycle.py src/polisyos/runtime/quality/design_generation.py src/polisyos/runtime/quality/intervention_substrate.py
.venv/bin/ruff check src/polisyos/foundry/methods/components/value_evidence.py src/polisyos/runtime/quality/generation_cycle.py tools/quality/validation/check_layer3_gy_value_gate_contract.py tools/quality/validation/check_layer3_gy_second_domain_pack.py tests/unit/runtime/quality/test_value_gate.py tests/unit/runtime/quality/test_second_domain_pack.py
```

The `rg` output must contain no domain-name branch; comments/test labels are reviewed manually and do not excuse a branch.

- [ ] **Step 7: Commit A2 only after both receipts exist.**

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

- [ ] **Step 1: Write RED positive and fabricated-negative tests.**

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

- [ ] **Step 2: Run focused tests and observe RED only for the two-cycle runtime requirement/new mutation.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_generation_cycle.py -k 'one_cycle_honest or unreachable_terminal' -q
```

- [ ] **Step 3: Remove only the runtime two-cycle check and add coherence rules.**

Require at least one cycle, enum-derived full denominator, no terminal `advance`, completed/blocked reason consistency, and coherent front/VOI/revision state. Keep the frozen two-cycle positive in the checker.

- [ ] **Step 4: Run the full N6 battery.**

```bash
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --check
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --corrupt-field-drift-check
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --rederive-audit
python3 -m pytest tests/unit/runtime/quality/test_generation_cycle.py -q
.venv/bin/ruff check src/polisyos/runtime/quality/generation_cycle.py tools/quality/validation/check_layer3_gy_generation_cycle_contract.py tests/unit/runtime/quality/test_generation_cycle.py
```

- [ ] **Step 5: Commit the one-directional fix.**

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

- [ ] **Step 1: Write RED Lane-0 depth and NL-front-door tests.**

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

- [ ] **Step 2: Run tests and observe RED because the router/front door are absent.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/http/test_nl_pipeline_materialization.py -k 'recursive_router or plain_language_front_door' -q
```

- [ ] **Step 3: Implement the thin router.**

Use strict content-bound result types. The controller accepts an existing `RecursiveDesignGraph`, validated problem-by-node mapping produced from candidate decomposition, a cycle-controller factory, and existing coupling/composition ports. It traverses depth/budget, invokes `GenerationCycleController` only at executable leaves, and delegates every coupling/decomposition/composition decision. It does not define a terminal enum or coupling rule.

- [ ] **Step 4: Implement the service bridge.**

`compile_and_run_recursive_generation_cycle` calls `build_design_problem_from_nl_request`, verifies raw-request/tool-response content binding, resolves the caller-supplied substrate context, and invokes the router. The runtime quality layer never imports HTTP.

- [ ] **Step 5: Run focused tests and Ruff.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/http/test_nl_pipeline_materialization.py -k 'recursive_router or plain_language_front_door' -q
.venv/bin/ruff check src/polisyos/runtime/quality/recursive_generation_cycle.py src/polisyos/runtime/quality/__init__.py src/polisyos/runtime/http/services/control/generation_cycle.py tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/http/test_nl_pipeline_materialization.py
```

- [ ] **Step 6: Commit the thin router.**

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

- [ ] **Step 1: Write RED coupling/strangle tests.**

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

- [ ] **Step 2: Run tests and observe RED because GY-G callers/default remain.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/quality/test_workspace_loop.py -k 'coupling_evidence or coupled_parent or gy_g_strangle' -q
```

- [ ] **Step 3: Make coupling evidence explicit and consume real N5.**

Remove the default `evidence_state="observed"` or require all production callers to pass it explicitly. Missing producer evidence uses `absent`. The router supplies the same graph and intervention set to `JointSimulationHorizonController`; if engine decisions are unsupported or trajectories are absent, surface `simulation_blocked` rather than `joint_simulated`.

- [ ] **Step 4: Perform the P28 default flip and predecessor removal in one change.**

Remove/fence `WorkspaceLoop.run_recursive_case`, `coupling_graph_for_subdesigns`, `_recursive_case_child_fixtures`, and the duplicate-case default. Rewrite composition artifact generation to use the recursive controller. Recompute the ledger row from a caller census and behavioral route. Explicitly list any test-only exemption.

- [ ] **Step 5: Add restoring source flips.**

Add flips that reintroduce a fixture caller, default an empty graph to observed independence, skip N5 for a coupled parent, and label unsupported N5 output `joint_simulated`. Each must turn the N10 probe RED and restore source.

- [ ] **Step 6: Run Stage-3 gate.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/quality/test_workspace_loop.py -q
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --check
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --corrupt-field-drift-check
python3 tools/quality/validation/check_layer3_gy_generation_cycle_contract.py --rederive-audit
python3 tools/quality/validation/check_layer3_gy_joint_simulation_horizon_contract.py --check
python3 tools/quality/validation/check_layer3_gy_composition_artifacts.py --check
.venv/bin/ruff check src/polisyos/runtime/quality/recursive_generation_cycle.py src/polisyos/runtime/quality/generation_cycle.py src/polisyos/runtime/quality/workspace/loop.py src/polisyos/runtime/quality/design_axes/coupling_composition.py tools/quality/validation/check_layer3_gy_composition_artifacts.py tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/quality/test_workspace_loop.py
```

- [ ] **Step 7: Commit the atomic strangle/default flip.**

```bash
git add src/polisyos/runtime/quality/recursive_generation_cycle.py src/polisyos/runtime/quality/generation_cycle.py src/polisyos/runtime/quality/workspace/loop.py src/polisyos/runtime/quality/design_axes/coupling_composition.py tools/quality/validation/check_layer3_gy_composition_artifacts.py tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/quality/test_workspace_loop.py architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json
git commit -m "feat: strangle fixed recursive cycle"
```

---

# Stage 4 — Three proof runs, frozen contract, and final gates

## Task 12: Build the frozen universality contract validator test-first

**Files:**
- Create/Modify: `tests/unit/runtime/quality/test_depth_n_universality.py`
- Create: `tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py`
- Modify: `architecture/generated_artifacts.toml`
- Regenerate: `docs/reference/generated-artifacts.md`

- [ ] **Step 1: Write RED validator schema/drift/write tests.**

```python
def test_universality_contract_requires_three_runs_and_two_part_a2_evidence() -> None:
    payload = validator.build_live_payload(REPO_ROOT, lane="lane0")
    assert set(payload["domain_runs"]) == {"first_vertical", "education", "unseen"}
    assert payload["non_panel_positive"]["status"] == "value_ready"
    assert payload["education_refusal"]["status"] == "value_refused"
    assert payload["depth_evidence"]["observed_max_depth"] > 2


def test_universality_contract_content_hash_rejects_corruption() -> None:
    payload = validator.build_live_payload(REPO_ROOT, lane="lane0")
    payload["domain_runs"]["education"]["terminal_kind"] = "promoted"
    report = validator.validate_payload(payload)
    assert any(issue["code"] == "contract_content_hash_mismatch" for issue in report["issues"])


def test_universality_write_is_byte_stable(tmp_path: Path) -> None:
    first = validator.write_payload(REPO_ROOT, tmp_path / "proof.json")
    second = validator.write_payload(REPO_ROOT, tmp_path / "proof.json")
    assert first == second
```

- [ ] **Step 2: Run tests and observe RED because the validator is absent.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py -k 'universality_contract or byte_stable' -q
```

- [ ] **Step 3: Implement validator modes and total semantic validation.**

Implement:

```text
--check
--corrupt-field-drift-check       exits 1 when corruption is correctly detected
--rederive-audit
--source-flip-mutations
--write
--output-format {text,json}
```

The payload includes schema/rule/producer refs, source hashes, pattern pass, NL input hashes, domain distinctness, per-stage traces, baseline diff, non-panel positive, education refusal, unseen smoke, terminal distributions, recursion/coupling/N5/composition receipts, GY-G strangle, gap triage, source flips, verification journal, runtime metrics, and `contract_content_hash`. Hash validation excludes only declared runtime metrics/times.

- [ ] **Step 4: Register generated-artifact lifecycle and verify focused tests.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py -k 'universality_contract or byte_stable' -q
.venv/bin/ruff check tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py tests/unit/runtime/quality/test_depth_n_universality.py
```

- [ ] **Step 5: Commit validator/lifecycle before live proof writes.**

```bash
git add tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py tests/unit/runtime/quality/test_depth_n_universality.py architecture/generated_artifacts.toml docs/reference/generated-artifacts.md
git commit -m "feat: add depth-N universality contract"
```

## Task 13: Produce three content-bound plain-language runs

**Files:**
- Modify: `tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py`
- Modify: `tests/unit/runtime/quality/test_depth_n_universality.py`
- Create/Regenerate: `architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json`

- [ ] **Step 1: Write RED semantic assertions for the three run classes.**

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

- [ ] **Step 2: Run Lane-0/cached tests and observe missing proof fields RED.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py -k 'first_vertical or education_run or unseen_domain or pinned_fixture' -q
```

- [ ] **Step 3: Implement E1/E3/E5/E6 proof orchestration.**

Use content-addressed compiler recordings keyed by raw request, tool schema, provider/model, and raw response. Use Lane-0 mini-worlds for logic, cached owner data for Lane 1, and journal the one cold two-domain closeout before invoking live owners. Capture wall time outside content hashes.

- [ ] **Step 4: Run one cold two-domain closeout serially with full budget, or record the exact cloud blocker.**

Do not retry concurrently. A missing credential/provider is recorded as a cloud residual; it may not be replaced by a fixture DTO.

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

- [ ] **Step 2: Run focused reconciliation tests and observe RED on stale N10a/ledger rows.**

```bash
python3 -m pytest tests/unit/runtime/quality/test_depth_n_universality.py tests/unit/runtime/quality/test_second_domain_pack.py -k 'gap_triage or ledger or residual or no_promotion' -q
```

- [ ] **Step 3: Update generated records from live seam evidence.**

Mark `n8_transport_tuple_hardcode`, `s0_to_n4_l6_bridge_missing`, `s0_to_n5_wmr_bridge_missing`, `s0_to_l6_world_slot_bridge_missing`, and `n6_single_terminal_validation_gap` closed with function/receipt/hash evidence. Keep owner-registration derivation and raw journal persistence residual with their original capability labels and justification.

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
- The non-panel positive is the Stage-2 exit gate (not its entry); education refusal is separate.
- The expected Bayesian FQN is plan-pinned only; advisor selection trace and candidate-real treatment provenance are decisive RED/GREEN properties.
- N4 wrappers and `GroundingDispositionKind` reconciliation are bounded to Task 1.
- N6 loosening is Stage 3, additive-only, with an unreachable one-cycle RED mutation.
- N7 tests/checker are in Stage 1 and final blast radius before/after the bootstrap fence.
- GY-G removal/default flip is atomic in Task 11.
- The original Section-8 commands are present; N4/N7 and full N6 modes are additive.
- No task authorizes education promotion, a fabricated pass/block, a domain branch, a parallel owner, or a weakened harness.
- The two infrastructure gaps remain typed residuals.
- Every stage ends at a fresh verification gate and scoped commit.
