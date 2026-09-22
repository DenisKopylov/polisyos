"""CYC-05 witnesses for typed recursive limits and structural receipts."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import polisyos.runtime.http.services.control.generation_cycle as generation_cycle_service
from polisyos.core import canon
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.pdc import SearchTerminalKind, SubDesignContract, gy_content_hash
from polisyos.runtime.quality.design_axes.coupling_composition import (
    _search_exit_binding_hash,
    derive_recursive_design_graph,
)
from polisyos.runtime.http.services.control.generation_cycle import (
    _build_cycle_substrate_context_from_owner,
)
from polisyos.runtime.quality.design_problem import DesignProblemAuthorityError
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
    GenerationCycleError,
    StrangleReceipt,
    validate_generation_cycle_run,
)
from polisyos.runtime.quality.open_world_risk import PromotionRuntime
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    build_default_recursive_generation_cycle_controller,
    recompute_depth_n_strangle_receipt,
)
from polisyos.runtime.quality.workspace.loop import WorkspaceLoop, WorkspaceSearchExitContract
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tests.unit.remediation.test_cyc_02 import (
    _recursive_contract_testing_controller,
    _recursive_leaf_terminal,
    _recursive_parent_request,
)
from tests.unit.runtime.quality.test_generation_cycle import (
    _CgfGenerationPort,
    _DataGapValuePort,
    REPO_ROOT,
    _budget,
    _cyc01_owner_bound_n5_case,
    _problem,
)


def _source_root(root: Path) -> Path:
    source = root / "src" / "polisyos"
    source.mkdir(parents=True)
    return source


def test_depth_n_strangle_receipt_fails_closed_when_source_is_missing(tmp_path: Path) -> None:
    """An absent controlled source slice cannot produce positive strangle evidence."""

    receipt = recompute_depth_n_strangle_receipt(tmp_path)

    assert receipt.status == "not_established"
    assert receipt.source_state == "missing"
    assert receipt.source_content_hash is None
    assert receipt.parse_errors == ()
    assert receipt.production_fixture_callers == ()
    assert receipt.production_default_routes == ()
    assert receipt.default_controller == "unresolved"


def test_depth_n_strangle_receipt_requires_explicit_source_root() -> None:
    """The legacy diagnostic receipt cannot adopt the process working directory."""

    receipt = recompute_depth_n_strangle_receipt()

    assert receipt.status == "not_established"
    assert receipt.source_state == "not_established"
    assert receipt.source_content_hash is None
    assert receipt.default_controller == "unresolved"


def test_generation_cycle_strangle_receipt_fails_closed_when_source_is_missing(
    tmp_path: Path,
) -> None:
    """The actual N6 owner must not promote an absent source denominator."""

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "not_established"
    assert receipt.source_state == "missing"
    assert receipt.source_content_hash is None
    assert receipt.source_file_count == 0
    assert receipt.parse_errors == ()


def test_generation_cycle_strangle_receipt_separates_parse_error_from_caller(
    tmp_path: Path,
) -> None:
    """The actual N6 owner keeps parse failure distinct from caller drift."""

    source = _source_root(tmp_path)
    (source / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "not_established"
    assert receipt.source_state == "parse_error"
    assert receipt.source_content_hash is None
    assert receipt.source_file_count == 1
    assert receipt.production_single_pass_callers == ()
    assert any("src/polisyos/broken.py" in item for item in receipt.parse_errors)


def test_generation_cycle_receipt_replay_requires_explicit_source_root(tmp_path: Path) -> None:
    """Receipt replay must not silently inspect the process working directory."""

    source = _source_root(tmp_path)
    (source / "owner.py").write_text("def owner():\n    return None\n", encoding="utf-8")
    receipt = StrangleReceipt.recompute(tmp_path)

    with pytest.raises(
        GenerationCycleError,
        match="generation_cycle_strangle_receipt_currentness_not_established",
    ):
        receipt.verify_current()


def test_generation_cycle_receipt_recompute_without_root_is_not_established() -> None:
    """Receipt production must not adopt the process cwd as a source checkout."""

    receipt = StrangleReceipt.recompute()

    assert receipt.status == "not_established"
    assert receipt.source_state == "not_established"
    assert receipt.source_content_hash is None


@pytest.mark.asyncio
async def test_http_job_progress_exposes_requested_and_effective_recursive_limits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The HTTP worker must retain requested limits beside its effective budget."""

    from tests.unit.runtime.http.test_control_service_di import (
        _NeverCalledEvalSafetyVerifier,
        _build_control_service,
        _fixture_claims,
    )
    from tests.unit.runtime.quality.test_generation_cycle import REPO_ROOT
    from polisyos.core.contracts.control import NaturalLanguageRunRequest
    from polisyos.runtime.http.services.control.generation_cycle import (
        _resolve_http_recursive_budget,
    )
    from polisyos.runtime.http.execution_policy import RuntimePrincipal
    from polisyos.runtime.quality import promotion_sequence as promotion_sequence_module

    service = _build_control_service(tmp_path)
    try:
        monkeypatch.setattr(
            promotion_sequence_module,
            "_legacy_policy_promotion_callers",
            lambda repo_root: (),
        )
        problem = _problem("cyc_05_http_limit_visibility")

        async def compile_problem(**kwargs):
            del kwargs
            return problem

        monkeypatch.setattr(
            generation_cycle_service,
            "build_design_problem_from_nl_request",
            compile_problem,
        )
        _, recursive_budget_resolution = _resolve_http_recursive_budget(7)

        compiled_fixture = (
            await generation_cycle_service.compile_and_run_recursive_generation_cycle(
                raw_request=problem.nl_provenance.raw_request,
                context={},
                model_name="fixture-model",
                compiler_gateway=object(),  # type: ignore[arg-type]
                budget_state=_budget(),
                recursive_budget=RecursiveCycleBudget(
                    max_depth=0,
                    max_nodes=1,
                    min_cycles_per_leaf=1,
                    max_cycles_per_leaf=3,
                ),
                recursive_budget_resolution=recursive_budget_resolution,
                promotion_runtime=service._promotion_runtime,
                root_evaluation_context=None,
                eval_safety_verifier=_NeverCalledEvalSafetyVerifier(),
                repo_root=REPO_ROOT,
            )
        )

        launch = await service.launch_nl_run(
            NaturalLanguageRunRequest(
                request=problem.nl_provenance.raw_request,
                llm_model="simulated-qwen",
                max_iterations=7,
            ),
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
        )
        record = service._control_store.get_job(launch.job_id)
        assert record is not None

        async def compile_worker_request(**kwargs):
            recursive_budget = kwargs["recursive_budget"]
            assert recursive_budget.max_depth == 0
            assert recursive_budget.max_nodes == 1
            assert recursive_budget.max_cycles_per_leaf == 3
            assert kwargs["recursive_budget_resolution"] == recursive_budget_resolution
            return compiled_fixture

        monkeypatch.setattr(
            generation_cycle_service,
            "compile_and_run_recursive_generation_cycle",
            compile_worker_request,
        )

        service._process_control_job(record)

        completed = service._control_store.get_job(launch.job_id)
        assert completed is not None
        assert completed.state == "completed"
        assert completed.progress["recursive_budget_resolution"] == {
            "requested_max_iterations": 7,
            "effective_max_iterations": 3,
            "recursive_budget": {
                "max_depth": 0,
                "max_nodes": 1,
                "min_cycles_per_leaf": 1,
                "max_cycles_per_leaf": 3,
            },
            "clamp_reason": "requested_max_iterations_above_http_cycle_cap_3",
        }
        compiled_ref = ArtifactID.model_validate(
            completed.progress["compiled_recursive_generation_cycle_ref"]
        )
        persisted = generation_cycle_service.CompiledRecursiveGenerationCycleRun.model_validate(
            canon.from_canonical_bytes(service._artifact_store.get_bytes(compiled_ref))
        )
        assert persisted.recursive_budget_resolution == recursive_budget_resolution
    finally:
        service.close()


def test_generation_cycle_receipt_replay_binds_bounded_limitations(tmp_path: Path) -> None:
    """Replay must bind the declared bounded census limitations as well as bytes."""

    source = _source_root(tmp_path)
    (source / "owner.py").write_text("def owner():\n    return None\n", encoding="utf-8")
    receipt = StrangleReceipt.recompute(tmp_path)
    changed_limitations = receipt.model_copy(
        update={"limitation_refs": ("build_identity_unavailable",)}
    )

    with pytest.raises(GenerationCycleError, match="generation_cycle_strangle_receipt_stale"):
        changed_limitations.verify_current(tmp_path)


def test_http_owner_context_requires_explicit_source_root() -> None:
    """HTTP source-owner preparation must not inspect the process cwd."""

    problem = _problem("cyc_05_http_rootless_context")
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))

    assert (
        _build_cycle_substrate_context_from_owner(
            problem=problem,
            problem_ref=problem_ref,
            repo_root=None,
        )
        is None
    )


@pytest.mark.asyncio
async def test_http_rejects_injected_controller_source_root_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The HTTP composition cannot validate checkout B with controller checkout A."""

    root_a = tmp_path / "checkout-a"
    root_b = tmp_path / "checkout-b"
    root_a.mkdir()
    root_b.mkdir()
    problem = _problem("cyc_05_controller_root_mismatch")
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "promotion-cas"))
    verifier = object()
    controller = build_default_recursive_generation_cycle_controller(
        promotion_runtime=runtime,
        eval_safety_verifier=verifier,  # type: ignore[arg-type]
        repo_root=root_a,
    )

    async def compile_problem(**kwargs):
        del kwargs
        return problem

    async def fail_if_controller_runs(*args, **kwargs):
        del args, kwargs
        raise AssertionError("root-mismatched controller reached recursive execution")

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        compile_problem,
    )
    monkeypatch.setattr(
        generation_cycle_service,
        "_build_cycle_substrate_context_from_owner",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(controller, "run", fail_if_controller_runs)

    with pytest.raises(DesignProblemAuthorityError) as exc_info:
        await generation_cycle_service.compile_and_run_recursive_generation_cycle(
            raw_request=problem.nl_provenance.raw_request,
            context={},
            model_name="fixture-model",
            compiler_gateway=object(),  # type: ignore[arg-type]
            controller=controller,
            budget_state=_budget(),
            recursive_budget=RecursiveCycleBudget(
                max_depth=0,
                max_nodes=1,
                min_cycles_per_leaf=1,
                max_cycles_per_leaf=1,
            ),
            root_evaluation_context=None,
            eval_safety_verifier=verifier,  # type: ignore[arg-type]
            promotion_runtime=runtime,
            repo_root=root_b,
        )

    assert exc_info.value.code == "recursive_controller_repo_root_mismatch"


@pytest.mark.asyncio
async def test_generation_cycle_consumer_keeps_missing_source_non_positive(
    tmp_path: Path,
) -> None:
    """The real N6 consumer must retain a missing-source refusal."""

    run = await GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_DataGapValuePort(),
        repo_root=tmp_path,
        authority_scope="contract_testing",
    ).run(
        _problem("cyc_05_missing_source_consumer"),
        budget_state=_budget(),
        max_cycles=1,
    )

    issues = validate_generation_cycle_run(run, repo_root=tmp_path)
    assert "strangle_receipt_currentness_not_established" in {
        issue["code"] for issue in issues
    }


@pytest.mark.asyncio
async def test_generation_cycle_consumer_keeps_parse_error_non_positive(
    tmp_path: Path,
) -> None:
    """The real N6 consumer must retain a parse-error refusal."""

    source = _source_root(tmp_path)
    (source / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    run = await GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_DataGapValuePort(),
        repo_root=tmp_path,
        authority_scope="contract_testing",
    ).run(
        _problem("cyc_05_parse_error_consumer"),
        budget_state=_budget(),
        max_cycles=1,
    )

    issues = validate_generation_cycle_run(run, repo_root=tmp_path)
    assert "strangle_receipt_currentness_not_established" in {
        issue["code"] for issue in issues
    }


def test_depth_n_strangle_receipt_separates_parse_error_from_prohibited_caller(
    tmp_path: Path,
) -> None:
    """A syntax error is an unestablished denominator, not a caller finding."""

    source = _source_root(tmp_path)
    (source / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    receipt = recompute_depth_n_strangle_receipt(tmp_path)

    assert receipt.status == "not_established"
    assert receipt.source_state == "parse_error"
    assert receipt.source_content_hash is None
    assert receipt.production_fixture_callers == ()
    assert any("src/polisyos/broken.py" in item for item in receipt.parse_errors)


def test_depth_n_strangle_receipt_binds_available_slice_and_invalidates_on_change(
    tmp_path: Path,
) -> None:
    """A real caller is drift, and any source-slice change yields a new receipt identity."""

    source = _source_root(tmp_path)
    (source / "route.py").write_text(
        "def route():\n"
        "    return build_default_recursive_generation_cycle_controller()\n",
        encoding="utf-8",
    )
    (source / "legacy.py").write_text(
        "def route():\n"
        "    return run_recursive_case()\n",
        encoding="utf-8",
    )

    receipt = recompute_depth_n_strangle_receipt(tmp_path)

    assert receipt.status == "drift"
    assert receipt.source_state == "available"
    assert receipt.source_content_hash is not None
    assert receipt.parse_errors == ()
    assert receipt.production_fixture_callers == (
        "src/polisyos/legacy.py:2:call:run_recursive_case",
    )
    assert receipt.production_default_routes == (
        "src/polisyos/route.py:2:call:build_default_recursive_generation_cycle_controller",
    )
    original_hash = receipt.source_content_hash

    (source / "route.py").write_text(
        "def route():\n"
        "    # meaningful source-slice change\n"
        "    return build_default_recursive_generation_cycle_controller()\n",
        encoding="utf-8",
    )
    changed = recompute_depth_n_strangle_receipt(tmp_path)

    assert changed.source_state == "available"
    assert changed.source_content_hash is not None
    assert changed.source_content_hash != original_hash


@pytest.mark.asyncio
async def test_generation_cycle_consumer_rejects_stale_source_receipt(tmp_path: Path) -> None:
    """The actual N6 run consumer must reject a receipt after source drift."""

    source = _source_root(tmp_path)
    (source / "owner.py").write_text("def owner():\n    return None\n", encoding="utf-8")
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_DataGapValuePort(),
        repo_root=tmp_path,
        authority_scope="contract_testing",
    )

    run = await controller.run(
        _problem("cyc_05_source_bound_run"),
        budget_state=_budget(),
        max_cycles=1,
    )
    receipt = run.strangle_receipt
    source_files = {
        path.relative_to(tmp_path).as_posix(): "sha256:"
        + hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((tmp_path / "src" / "polisyos").rglob("*.py"))
    }
    assert receipt.status == "strangled"
    assert receipt.source_state == "available"
    assert receipt.source_file_count == len(source_files)
    assert receipt.source_content_hash == gy_content_hash(
        {"scope": "src/polisyos", "files": source_files}
    )
    unchecked_issues = validate_generation_cycle_run(run)
    assert {
        "strangle_receipt_currentness_not_established"
    } <= {issue["code"] for issue in unchecked_issues}
    assert validate_generation_cycle_run(run, repo_root=tmp_path) == ()

    (source / "owner.py").write_text(
        "def owner():\n    return 'changed'\n",
        encoding="utf-8",
    )
    with pytest.raises(GenerationCycleError, match="generation_cycle_strangle_receipt_stale"):
        run.strangle_receipt.verify_current(tmp_path)
    issues = validate_generation_cycle_run(run, repo_root=tmp_path)
    assert {issue["code"] for issue in issues} >= {"strangle_receipt_stale"}


def _cyc05_recursive_fixture_case(tmp_path: Path) -> tuple[
    str,
    tuple[SubDesignContract, SubDesignContract],
    object,
    dict[str, object],
    object,
]:
    """Build one real fixture decomposition and its explicit recursive inputs."""

    root = "design://cyc-05/fixture-parent"
    loop = WorkspaceLoop()
    children = tuple(
        loop.decompose_fixture(
            parent_workspace_id=root,
            child_fixture_ids=[
                "ua_msme_credit_worldbank_measurement",
                "ua_msme_credit_worldbank_measurement",
            ],
        )
    )
    assert len(children) == 2
    child_refs = tuple(child.workspace_id for child in children)
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=child_refs,
        parent_child_edges=((root, child_refs[0]), (root, child_refs[1])),
        rule_version_ref="repo://rules/cyc-05-recursive-fixture",
    )
    parent_problem, context, _candidate = _cyc01_owner_bound_n5_case()
    request = _recursive_parent_request(
        parent_ref=root,
        child_refs=child_refs,
        problem=parent_problem,
        world_model_record=context.world_model_record,
    )
    # The contract-testing leaf owner emits the same terminal for both child
    # routes. Preserve each WorkspaceLoop result's identity/artifacts while
    # binding the explicit handoff to that canonical leaf terminal.
    leaf_terminal = _recursive_leaf_terminal()
    routed_children = tuple(
        child.model_copy(
            update={
                "search_exit": child.search_exit.model_copy(
                    update={"terminal_state": leaf_terminal}
                )
            }
        )
        for child in children
    )
    problems = {
        root: parent_problem,
        child_refs[0]: _problem("cyc05_recursive_child_a"),
        child_refs[1]: _problem("cyc05_recursive_child_b"),
    }
    return root, routed_children, graph, problems, request


def _cyc05_recursive_budget() -> BudgetState:
    return BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=5.0)},
    )


async def _run_cyc05_recursive_case(
    *,
    tmp_path: Path,
    root: str,
    graph: object,
    problems: dict[str, object],
    request: object,
    subdesigns: tuple[SubDesignContract, ...],
) -> tuple[object, list[object]]:
    # Keep the validation root test-owned and deterministic.  The canonical
    # leaf validator requires a complete, parseable ``src/polisyos`` slice to
    # establish its strangle receipt; an empty ``tmp_path`` would therefore
    # fail before the recursive parent reaches N5.  This benign source file
    # has no ``run_fixture`` caller and is not production code under test.
    source_root = tmp_path / "src" / "polisyos"
    source_root.mkdir(parents=True)
    (source_root / "owner.py").write_text(
        "def owner() -> None:\n    return None\n",
        encoding="utf-8",
    )
    controller = _recursive_contract_testing_controller(tmp_path)
    calls: list[object] = []

    class _RecordingN5:
        def run(self, concrete_request: object) -> object:
            calls.append(concrete_request)
            return original_n5.run(concrete_request)

    original_n5 = controller._joint_simulation_controller
    controller._joint_simulation_controller = _RecordingN5()  # type: ignore[assignment]
    try:
        result = await controller.run(
            graph,  # type: ignore[arg-type]
            problems_by_node=problems,  # type: ignore[arg-type]
            budget_state=_cyc05_recursive_budget(),
            recursive_budget=RecursiveCycleBudget(
                max_depth=1,
                max_nodes=3,
                min_cycles_per_leaf=1,
                max_cycles_per_leaf=1,
            ),
            joint_simulation_requests_by_node={root: request},  # type: ignore[dict-item]
            subdesign_contracts_by_node={root: subdesigns},
        )
    finally:
        controller._joint_simulation_controller = original_n5
    return result, calls


@pytest.mark.asyncio
async def test_workspace_fixture_children_flow_through_recursive_graph_and_n5(
    tmp_path: Path,
) -> None:
    """Explicit WorkspaceLoop children retain identity through graph, N5 and composition."""

    root, subdesigns, graph, problems, request = _cyc05_recursive_fixture_case(tmp_path)
    result, calls = await _run_cyc05_recursive_case(
        tmp_path=tmp_path,
        root=root,
        graph=graph,
        problems=problems,
        request=request,
        subdesigns=subdesigns,
    )

    child_refs = tuple(child.workspace_id for child in subdesigns)
    assert tuple(graph.parent_child_edges) == (
        (root, child_refs[0]),
        (root, child_refs[1]),
    )
    assert tuple(child.search_exit.workspace_id for child in subdesigns) == child_refs
    assert len(calls) == 1
    root_node = next(node for node in result.nodes if node.node_ref == root)
    assert root_node.child_refs == child_refs
    assert root_node.joint_simulation is not None
    assert root_node.joint_simulation_ref is not None
    assert root_node.composition_certificate is not None
    assert root_node.composition_certificate.input_subdesigns == [
        child.subdesign_id for child in subdesigns
    ]
    assert root_node.composition_certificate.coupling_gate.verdict == "valid"
    routed = {node.node_ref: node for node in result.nodes}
    for child in subdesigns:
        node = routed[child.workspace_id]
        assert node.cycle_run is not None
        assert node.terminal == child.search_exit.terminal_state
        assert child.producer_roots
        assert child.search_exit.output_artifacts
    assert result.authority_scope == "contract_testing"
    assert root_node.terminal.kind is not SearchTerminalKind.GROUNDED_ADMISSIBLE


def test_workspace_fixture_child_alias_roundtrip_preserves_source_identity() -> None:
    """The parent export aliases are unique while nested child evidence stays source-bound."""

    loop = WorkspaceLoop()
    children = tuple(
        loop.decompose_fixture(
            parent_workspace_id="design://cyc-05/alias-readback-parent",
            child_fixture_ids=[
                "ua_msme_credit_worldbank_measurement",
                "ua_msme_credit_worldbank_measurement",
            ],
        )
    )

    alias_workspace_ids = tuple(child.workspace_id for child in children)
    assert len(alias_workspace_ids) == len(children) == 2
    assert len(set(alias_workspace_ids)) == len(children)
    assert tuple(child.search_exit.workspace_id for child in children) == alias_workspace_ids

    # The same fixture deliberately emits the same source exit handle.  The
    # exported workspace alias and its content-bound search-exit hash provide
    # the identity that distinguishes the two parent-facing children.
    source_exit_ids = tuple(child.search_exit.exit_id for child in children)
    assert len(set(source_exit_ids)) == 1
    binding_hashes = tuple(
        _search_exit_binding_hash(child.search_exit.model_dump(mode="json"))
        for child in children
    )
    assert len(set(binding_hashes)) == len(children)

    for child in children:
        assert isinstance(child.search_exit, WorkspaceSearchExitContract)
        source_workspace_id = child.search_exit.workspace_contract.workspace_id
        assert source_workspace_id != child.workspace_id
        assert child.search_exit.frontier_snapshot.workspace_id == source_workspace_id
        assert child.search_exit.incompleteness_record.workspace_id == source_workspace_id
        assert child.search_exit.search_ledger.workspace_id == source_workspace_id
        assert child.search_exit.voi_audit.workspace_id == source_workspace_id

        payload = child.search_exit.model_dump(mode="json")
        roundtripped = WorkspaceSearchExitContract.model_validate(payload)
        assert roundtripped.model_dump(mode="json") == payload
        assert roundtripped.workspace_id == child.workspace_id
        assert roundtripped.exit_id == child.search_exit.exit_id
        assert roundtripped.workspace_contract_ref == child.search_exit.workspace_contract_ref
        assert roundtripped.workspace_contract.workspace_id == source_workspace_id
        assert roundtripped.frontier_snapshot.workspace_id == source_workspace_id
        assert roundtripped.incompleteness_record.workspace_id == source_workspace_id
        assert roundtripped.search_ledger.workspace_id == source_workspace_id
        assert roundtripped.voi_audit.workspace_id == source_workspace_id


@pytest.mark.asyncio
@pytest.mark.parametrize("control", ("missing_child", "missing_coupling", "identity"))
async def test_recursive_parent_blocks_without_n5_or_composition_for_missing_inputs(
    tmp_path: Path,
    control: str,
) -> None:
    """All three incomplete handoffs fail closed before N5 or composition."""

    root, subdesigns, graph, problems, request = _cyc05_recursive_fixture_case(tmp_path)
    if control == "missing_child":
        supplied = subdesigns[:1]
    elif control == "missing_coupling":
        supplied = subdesigns
        request = request.model_copy(update={"coupling_graph": None})
    else:
        supplied = (
            subdesigns[0].model_copy(
                update={
                    "search_exit": subdesigns[0].search_exit.model_copy(
                        update={"workspace_id": "design://wrong-child-exit"}
                    )
                }
            ),
            subdesigns[1],
        )

    result, calls = await _run_cyc05_recursive_case(
        tmp_path=tmp_path,
        root=root,
        graph=graph,
        problems=problems,
        request=request,
        subdesigns=supplied,
    )
    root_node = next(node for node in result.nodes if node.node_ref == root)
    assert calls == []
    assert root_node.joint_simulation is None
    assert root_node.composition_certificate is None
    assert root_node.terminal.kind is SearchTerminalKind.RECURSIVE_BLOCKED
    assert root_node.terminal.blocking_obligations == [
        {
            "missing_child": "subdesign_contract_denominator_missing",
            "missing_coupling": "observed_coupling_evidence_missing",
            "identity": "recursive_subdesign_terminal_binding_mismatch",
        }[control]
    ]


@pytest.mark.asyncio
async def test_recursive_parent_blocks_for_wrong_parent_workspace_identity(tmp_path: Path) -> None:
    """A child exported under another parent cannot reach N5 or composition."""

    root, subdesigns, graph, problems, request = _cyc05_recursive_fixture_case(tmp_path)
    supplied = (
        subdesigns[0].model_copy(update={"parent_workspace_id": "design://wrong-parent"}),
        subdesigns[1],
    )

    result, calls = await _run_cyc05_recursive_case(
        tmp_path=tmp_path,
        root=root,
        graph=graph,
        problems=problems,
        request=request,
        subdesigns=supplied,
    )
    root_node = next(node for node in result.nodes if node.node_ref == root)
    assert calls == []
    assert root_node.joint_simulation is None
    assert root_node.composition_certificate is None
    assert root_node.terminal.kind is SearchTerminalKind.RECURSIVE_BLOCKED
    assert root_node.terminal.blocking_obligations == [
        "recursive_subdesign_terminal_binding_mismatch"
    ]
