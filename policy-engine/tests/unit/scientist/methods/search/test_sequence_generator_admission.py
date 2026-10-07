"""Scalar corpus refusal and ordinary dispatch at the native search boundaries."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCALAR = r"""
import json
from polisyos.scientist.methods.autotune.runtime import SequenceCandidateGenerator
corpus = [{"value": 1}, {"value": 2}]
generator = SequenceCandidateGenerator(corpus)
assert generator.generate([], None, {}) == {"value": 1}
state = generator.get_state()
fresh = SequenceCandidateGenerator(corpus)
fresh.set_state(state)
assert fresh.generate([], None, {}) == generator.generate([], None, {}) == {"value": 2}
assert fresh.generate([], None, {}) == generator.generate([], None, {}) == {"value": 2}
assert fresh.get_state() == generator.get_state()
assert generator.get_state()["version"] == "sequence-generator.v1"
try:
    SequenceCandidateGenerator([])
except ValueError as exc:
    assert str(exc) == "sequence_generator_requires_nonempty_corpus"
else:
    raise AssertionError("empty scalar corpus was admitted")
index = generator._index
generator._candidates.clear()
try:
    generator.generate([], None, {})
except ValueError as exc:
    assert str(exc) == "sequence_generator_requires_nonempty_corpus"
else:
    raise AssertionError("removed scalar corpus fabricated a subject")
assert generator._index == index
print(json.dumps({"stream": [1, 2, 2], "fresh_cursor": fresh.get_state()["index"],
                  "constructor_refusal": "sequence_generator_requires_nonempty_corpus",
                  "removed_corpus_cursor_unchanged": index}))
"""

_FACTORY = r"""
import json, sys
from dataclasses import replace
from pathlib import Path
from polisyos.core.canon.canon_json import from_canonical_bytes
from polisyos.scientist.methods.autotune.runtime import SequenceCandidateGenerator
from polisyos.scientist.methods.search.controller import SearchStatus
from test_service_persistence import _runner
root = Path(sys.argv[1])
runner, store, registry, suite, evaluator, spec = _runner(root)
suite_bytes = store.get_bytes(suite)
try:
    runner.create_service(replace(spec, candidate_generator=SequenceCandidateGenerator([])),
                          suite_ref=suite, max_iterations=3)
except ValueError as exc:
    assert str(exc) == "sequence_generator_requires_nonempty_corpus"
else:
    raise AssertionError("unsupported scalar input activated the factory")
assert evaluator.calls == [] and registry.get("resume") is None
assert store.get_bytes(suite) == suite_bytes
# Valid configuration activates the real factory; later corpus removal must refuse.
service = runner.create_service(spec, suite_ref=suite, max_iterations=3)
service.controller._generator._candidates.clear()
try:
    service.run_search(initial_context={})
except ValueError as exc:
    assert str(exc) == "sequence_generator_requires_nonempty_corpus"
else:
    raise AssertionError("removed corpus was reported as successful exhaustion")
assert service.controller._status is SearchStatus.FAILED
assert service.controller._history == []
assert service._pending_candidates == {} and service._completed_candidate_ids == set()
assert service._ask_iteration == service.controller._generator._index == 0
assert evaluator.calls == [] and registry.get("resume") is None
assert service.checkpoint_ref is not None
saved = from_canonical_bytes(store.get_bytes(service.checkpoint_ref))
assert saved["run_state"]["status"] == "failed"
assert saved["failure"] == "ValueError: sequence_generator_requires_nonempty_corpus"
assert saved["run_state"]["history"] == [] and saved["pending_candidate_ids"] == []
assert saved["generator_state"]["candidates"] == []
assert store.get_bytes(suite) == suite_bytes
fresh_runner, _, _, _, fresh_evaluator, fresh_spec = _runner(root)
fresh = fresh_runner.create_service(fresh_spec, suite_ref=suite, max_iterations=3)
try:
    fresh.restore(service.checkpoint_ref)
except ValueError as exc:
    assert "sequence_generator_checkpoint_mismatch" in str(exc)
else:
    raise AssertionError("fresh nonempty corpus accepted removed-corpus state")
assert fresh_evaluator.calls == []
print(json.dumps({"input_refusal_before_activation": True, "actual_live_factory": True,
                  "failure": saved["failure"], "evaluations": 0, "effects": 0,
                  "checkpoint_ref": service.checkpoint_ref.model_dump(mode="json"),
                  "fresh_original_corpus_refused": True}))
"""

_LAZY = r"""
import importlib.abc, json, sys
from pathlib import Path
attempts = []
class NoAdvisor(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "polisyos.foundry.methods.selection.advisor":
            attempts.append(fullname)
            raise ImportError("selection_advisor_unavailable_control")
        return None
sys.meta_path.insert(0, NoAdvisor())
from test_service_persistence import _runner
runner, store, _, suite, evaluator, spec = _runner(Path(sys.argv[1]))
service = runner.create_service(spec, suite_ref=suite, max_iterations=3)
proposal = service.ask(None, None, {})[0]
assert proposal.payload["value"] == 1
assert evaluator.calls == [] and attempts == []
from polisyos.core.canon.canon_json import from_canonical_bytes
saved = from_canonical_bytes(store.get_bytes(service.checkpoint_ref))
assert saved["pending_candidate_ids"] == [proposal.candidate_id]
from polisyos.core.contracts.execution_plan import (
    MethodCatalogSnapshot, MethodDagNode, PreflightDiagnostic, PreflightReport,
)
from polisyos.scientist.methods.autotune.execution_plan import (
    ExecutionPlanSearchConfig, suggest_execution_plan_topology_mutations,
)
from polisyos.scientist.methods.search import controller as controller_module
records = []
original_degraded = controller_module._search_degraded
def observe_degraded(**kwargs):
    records.append({"operation": kwargs["operation"], "reason": kwargs["reason"],
                    "exception": type(kwargs["exc"]).__name__})
    return original_degraded(**kwargs)
controller_module._search_degraded = observe_degraded
plan = ExecutionPlanSearchConfig(method_dag=[MethodDagNode(node_id="n1", method_fqn="method.a")])
catalog = MethodCatalogSnapshot(snapshot_id="bounded-unavailable-control")
preflight = PreflightReport(diagnostics=[PreflightDiagnostic(
    code="method_catalog.method_unavailable", message="bounded selector activation", path=["n1"],
)])
context = {"execution_plan_search_config": plan, "catalog_snapshot": catalog,
           "preflight_report": preflight, "original_input": "retained"}
enriched = service.controller._build_generation_context(context, iteration=1)
assert enriched["original_input"] == "retained"
assert "execution_plan_topology_mutation_payload" not in enriched
assert records == [{"operation": "build_generation_context",
                    "reason": "execution_plan_context_unavailable", "exception": "ImportError"}]
assert attempts == ["polisyos.foundry.methods.selection.advisor"]
try:
    suggest_execution_plan_topology_mutations(plan, preflight_report=preflight, catalog=catalog)
except ImportError as exc:
    assert str(exc) == "selection_advisor_unavailable_control"
else:
    raise AssertionError("actual topology consumer bypassed required selection")
assert len(attempts) == 2
assert set(service._pending_candidates) == {proposal.candidate_id}
print(json.dumps({"ordinary_proposal": proposal.payload, "pending_readback": saved["pending_candidate_ids"],
                  "required_selector_attempts": attempts, "degraded": records,
                  "topology_positive": "UNRUN-required-backend"}))
"""

_DISPATCH = r"""
import json
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import BudgetDeficitObjective, CompositeObjective
from polisyos.scientist.methods.search.stopping import MaxIterations
from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds, PolicyCandidate
class ConfiguredPolicy:
    def __init__(self):
        self.calls = []
    def suggest(self, evaluations):
        self.calls.append(["suggest", len(evaluations)])
        return PolicyCandidate(candidate_id="configured-ucb", params={"x": 3.0},
                               source_strategy="bounded-UCB", metadata={"configured_law": "UCB"})
    def suggest_batch(self, evaluations, batch_size):
        self.calls.append(["suggest_batch", batch_size])
        return [PolicyCandidate(candidate_id=f"batch-{index}", params={"x": 4.0},
                                source_strategy="bounded-qEI", metadata={"configured_law": "qEI"})
                for index in range(batch_size)]
    def update(self, evaluation):
        pass
receipts = []
for size in [1, 2]:
    strategy = ConfiguredPolicy()
    adapter = StrategyAdapter(strategy, SearchSpace(bounds=[ParameterBounds(name="x", lower=0, upper=10)]))
    controller = SearchController(
        SearchConfig(stopping=MaxIterations(1), objective=CompositeObjective([BudgetDeficitObjective()]),
                     enable_stage_a=False, batch_size=size), adapter,
        stage_a_evaluator=lambda candidate, context: True,
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"budget_deficit": 2.0}, "feedback": {"verdict": "APPROVE"}},
    )
    result = controller.run(initial_context={})
    expected = [["suggest", 0]] if size == 1 else [["suggest_batch", 2]]
    assert strategy.calls == expected, (size, strategy.calls, expected)
    assert len(result.history) == result.iterations_completed == 1
    metadata = result.history[0].candidate["_strategy_metadata"]
    assert metadata["configured_law"] == ("UCB" if size == 1 else "qEI")
    receipts.append({"batch_size": size, "calls": strategy.calls, "metadata": metadata})
print(json.dumps({"actual_controller_adapter_dispatch": receipts,
                  "scope": "bounded configured-law routing; not numerical GP evidence"}))
"""


@pytest.mark.parametrize(
    "script",
    [_SCALAR, _FACTORY, _LAZY, _DISPATCH],
    ids=[
        "scalar-corpus",
        "native-factory-refusal",
        "lazy-selector-boundary",
        "configured-unit-dispatch",
    ],
)
def test_sequence_admission_and_native_consumer_boundaries(script, tmp_path):
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(Path(__file__).parent), environment.get("PYTHONPATH", "")])
    )
    child = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        env=environment,
    )
    print(
        json.dumps({"stdout": child.stdout, "stderr": child.stderr, "returncode": child.returncode})
    )
    assert child.returncode == 0, child.stdout + child.stderr
