"""Prepared C3 current-consumer falsifiers; run only after lane sequence release.

These are refusal controls, never canonical requirement or measurement evidence.
The method witness uses the existing real MethodBackend fixture and makes no
operational EvalSafety admission claim. This file has not been run as a gate.
"""

# Ruff's production-path assertion rule does not classify this scratch pytest file.
# ruff: noqa: S101

from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path
from typing import get_args

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.pdc import OperationClass
from polisyos.pdc._impl import layer2_design_search
from polisyos.runtime.quality.workspace import foundry_consumption as owner
from tests.unit.runtime.quality.test_workspace_foundry_consumption import (
    _method_owner_case,
)
from tests.unit.runtime.quality.test_workspace_foundry_consumption import (
    recorded_panel_owner as _recorded_panel_owner,
)

recorded_panel_owner = _recorded_panel_owner


def _assignment(module: object, name: str) -> ast.expr:
    path = Path(inspect.getfile(module))
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    ]
    assert len(matches) == 1, (path, name, len(matches))
    return matches[0]


def _complete_marker_population() -> tuple[tuple[str, str], ...]:
    """Reconcile runtime declarations with independently parsed owner declarations."""
    kinds = set(owner._ALLOWED_CONSTRAINT_SOURCES)
    kinds_ast = _assignment(owner, "_ALLOWED_CONSTRAINT_SOURCES")
    assert isinstance(kinds_ast, ast.Call)
    assert len(kinds_ast.args) == 1
    parsed_kinds = set(ast.literal_eval(kinds_ast.args[0]))
    assert kinds == parsed_kinds

    statuses = set(get_args(layer2_design_search.ConstraintRecordStatus))
    statuses_ast = _assignment(layer2_design_search, "ConstraintRecordStatus")
    assert isinstance(statuses_ast, ast.Subscript)
    parsed_statuses = set(ast.literal_eval(statuses_ast.slice))
    assert statuses == parsed_statuses

    population = {(kind, status) for kind in kinds for status in statuses}
    independently_nested = []
    for kind in sorted(parsed_kinds):
        for status in sorted(parsed_statuses):
            independently_nested.append((kind, status))
    assert len(independently_nested) == len(set(independently_nested))
    assert population == set(independently_nested)
    return tuple(sorted(population))


@pytest.mark.parametrize(
    ("source_kind", "status"),
    _complete_marker_population(),
    ids=lambda value: value,
)
def test_caller_markers_and_real_cas_bytes_do_not_mint_constraint_admission(
    tmp_path: Path, source_kind: str, status: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = store.put_json(
        {
            "source_kind": source_kind,
            "status": status,
            "proof_source": "deterministic_producer",
            "rule_version": owner.FOUNDRY_CONSUMPTION_RULE_VERSION,
            "not_an_owner_evaluation": True,
        },
        PutOptions(kind=f"gy.constraint_fixture.{source_kind}", media_type="application/json"),
    )
    # The ref really resolves. The missing property is owner recomputation, not CAS existence.
    store.get_bytes(source.artifact_id)
    store.get_manifest(source.artifact_id)
    sys.stdout.write(
        json.dumps(
            {
                "identity": [source_kind, status],
                "artifact_ref": str(source.artifact_id),
                "control": "CAS resolves; no source evaluation exists",
            },
            sort_keys=True,
        ) + "\n"
    )
    with pytest.raises(ValueError, match=r"constraint|governed|requirement"):
        owner.ConstraintStoreIngestor().ingest(
            snapshot_id=f"unverified-{source_kind}-{status}",
            grammar_expansion_ref=str(source.artifact_id),
            artifacts=[
                {
                    "source_kind": source_kind,
                    "artifact_ref": str(source.artifact_id),
                    "status": status,
                    "consumer_ref": "VERIFY",
                    "reason": "A caller declared the desired effect; no owner computed it.",
                }
            ],
        )


def test_absent_requirement_basis_is_not_an_empty_admitted_population() -> None:
    # This spelling is deliberately a negative control, never a governed source.
    with pytest.raises(ValueError, match=r"constraint|governed|requirement"):
        owner.ConstraintStoreIngestor().ingest(
            snapshot_id="unestablished-requirement-basis",
            grammar_expansion_ref="caller-declared-but-unresolved",
            artifacts=[],
        )


def test_present_unverified_constraint_ref_cannot_enter_method_consumption(
    recorded_panel_owner: object,
) -> None:
    store, binding, state = _method_owner_case(recorded_panel_owner)
    unrelated = store.put_json(
        {"constraint_records": [], "not_a_constraint_evaluation": True},
        PutOptions(kind="gy.constraint_fixture", media_type="application/json"),
    )
    store.get_bytes(unrelated.artifact_id)
    store.get_manifest(unrelated.artifact_id)
    consumer = owner.FoundryMethodOutputConsumer(store=store)
    sys.stdout.write(
        json.dumps(
            {
                "identity": "actual_method_owner/unrelated_constraint_ref",
                "constraint_ref": str(unrelated.artifact_id),
                "control": "Real method result and recorded binding remain unchanged",
            },
            sort_keys=True,
        ) + "\n"
    )
    with pytest.raises(ValueError, match="constraint"):
        consumer.consume_from_state(
            workspace_id="ws-c3-unverified-constraint",
            operation_invocation_id="invoke-c3-unverified-constraint",
            operation_class=OperationClass.ESTIMATE,
            state=state,
            measurement_root_ref=binding.observational_data_ref,
            binding_receipt_ref=binding.binding_receipt_ref,
            constraint_store_ref=str(unrelated.artifact_id),
        )
