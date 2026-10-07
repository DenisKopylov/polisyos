"""Actual AST checker admission; these fixtures issue no runtime owner authority."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.quality.diagnostics import check_state_reads as checker


def _node(constructor: str, reads: list[str]) -> str:
    return (
        f"_SPEC = {constructor}(state_reads={reads!r})\n"
        "def execute(state, context):\n"
        "    return state.inputs.get('required')\n"
    )


@pytest.fixture
def tree(tmp_path: Path, monkeypatch):
    src = tmp_path / "src"
    selected = src / "polisyos/scientist/nodes/builtins"
    selected.mkdir(parents=True)
    monkeypatch.setattr(checker, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(checker, "SRC_ROOT", src)
    return src, selected


def _run(capsys):
    code = checker.main()
    text = capsys.readouterr().out
    receipt = json.loads(
        next(
            line.removeprefix("state_reads measurement: ")
            for line in text.splitlines()
            if line.startswith("state_reads measurement: ")
        )
    )
    return code, text, receipt


@pytest.mark.parametrize("constructor", ["NodeSpec", "OutputAwareNodeSpec"])
def test_actual_checker_admits_existing_declared_spec_constructor(
    tree, capsys, constructor
):
    _, selected = tree
    node = selected / "node.py"
    node.write_text(_node(constructor, ["inputs.required"]))
    code, text, receipt = _run(capsys)
    assert code == 0 and "state_reads contract check passed" in text
    assert receipt["selected_paths"] == [str(node)]
    assert receipt["selected_input_denominator"] == 1 and receipt["complete_verdict"]
    assert (
        receipt["inputs"][0]["path"] == "src/polisyos/scientist/nodes/builtins/node.py"
    )
    assert receipt["inputs"][0]["status"] == "read"


@pytest.mark.parametrize("constructor", ["NodeSpec", "OutputAwareNodeSpec"])
def test_actual_checker_preserves_missing_read_failure(tree, capsys, constructor):
    _, selected = tree
    node = selected / "node.py"
    node.write_text(_node(constructor, []))
    code, text, receipt = _run(capsys)
    assert code == 1 and "missing state_reads path 'inputs.required'" in text
    assert receipt["verdict"] == "FAIL" and receipt["complete_verdict"]
    assert receipt["inputs"][0]["status"] == "read"


@pytest.mark.parametrize("constructor", ["NodeSpec", "OutputAwareNodeSpec"])
def test_outside_selector_evidence_cannot_supply_selected_read(
    tree, capsys, constructor
):
    src, selected = tree
    node = selected / "node.py"
    node.write_text(_node(constructor, []))
    outside = src / "outside_selector.py"
    outside.write_text(_node(constructor, ["inputs.required"]))
    code, text, receipt = _run(capsys)
    assert code == 1 and "missing state_reads path 'inputs.required'" in text
    assert (
        receipt["selected_paths"] == [str(node)]
        and receipt["selected_input_denominator"] == 1
    )
    assert [record["path"] for record in receipt["inputs"]] == [
        "src/polisyos/scientist/nodes/builtins/node.py"
    ]
    assert any(
        "outside the declared selector" in value
        for value in receipt["unresolved_by_construction"]
    )


def test_unreadable_selected_utf8_remains_unrun(tree, capsys):
    _, selected = tree
    node = selected / "node.py"
    node.write_bytes(b"\xff\xfe")
    code, text, receipt = _run(capsys)
    assert code == 2 and "contract check passed" not in text
    assert receipt["verdict"] == "UNRUN" and not receipt["complete_verdict"]
    assert receipt["inputs"][0]["status"] == "unreadable"
    assert receipt["unresolved_inputs"] == [
        {"path": str(node), "reason": "UnicodeDecodeError"}
    ]


def test_missing_enumerated_member_remains_unrun(tree, capsys, monkeypatch):
    _, selected = tree
    node = selected / "missing.py"
    monkeypatch.setattr(checker, "_iter_node_files", lambda: [node])
    code, text, receipt = _run(capsys)
    assert code == 2 and "contract check passed" not in text
    assert receipt["selected_input_denominator"] == 1
    assert receipt["inputs"][0]["status"] == "unreadable"
    assert receipt["unresolved_inputs"] == [
        {"path": str(node), "reason": "FileNotFoundError"}
    ]


@pytest.mark.parametrize("constructor", ["nodespec", "OUTPUTAWARENODESPEC"])
def test_unknown_case_constructor_remains_undecided(tree, capsys, constructor):
    _, selected = tree
    node = selected / "node.py"
    node.write_text(_node(constructor, ["inputs.required"]))
    code, text, receipt = _run(capsys)
    assert code == 2 and "contract check passed" not in text
    assert receipt["inputs"][0]["status"] == "read"
    assert receipt["unresolved_inputs"] == [
        {"path": str(node), "reason": "unsupported_spec_constructor"}
    ]


def test_invalid_selected_python_remains_unrun(tree, capsys):
    _, selected = tree
    node = selected / "node.py"
    node.write_text("def execute(:\n")
    code, text, receipt = _run(capsys)
    assert code == 2 and "contract check passed" not in text
    assert receipt["inputs"][0]["status"] == "read"
    assert receipt["unresolved_inputs"] == [
        {"path": str(node), "reason": "SyntaxError"}
    ]


@pytest.mark.parametrize("constructor", ["NodeSpec", "OutputAwareNodeSpec"])
def test_changed_declared_reads_changes_actual_failure_and_receipt(
    tree, capsys, constructor
):
    _, selected = tree
    node = selected / "node.py"
    node.write_text(_node(constructor, ["inputs.required"]))
    before, _, before_receipt = _run(capsys)
    node.write_text(_node(constructor, []))
    after, text, after_receipt = _run(capsys)
    assert (
        before == 0
        and after == 1
        and "missing state_reads path 'inputs.required'" in text
    )
    assert before_receipt["selected_paths"] == after_receipt["selected_paths"]
    assert (
        before_receipt["inputs"][0]["text_sha256"]
        != after_receipt["inputs"][0]["text_sha256"]
    )


def test_annotated_spec_assignment_remains_explicitly_unresolved(tree, capsys):
    _, selected = tree
    node = selected / "node.py"
    node.write_text(
        "_SPEC: NodeSpec = UnknownSpec(state_reads=['inputs.required'])\n"
        "def execute(state, context):\n"
        "    return state.inputs.get('required')\n"
    )
    code, text, receipt = _run(capsys)
    assert code == 2 and "contract check passed" not in text
    assert receipt["unresolved_inputs"] == [
        {"path": str(node), "reason": "unsupported_spec_constructor"}
    ]


def test_annotated_existing_spec_preserves_declared_read_admission(tree, capsys):
    _, selected = tree
    node = selected / "node.py"
    node.write_text(
        "_SPEC: NodeSpec = OutputAwareNodeSpec(state_reads=['inputs.required'])\n"
        "def execute(state, context):\n"
        "    return state.inputs.get('required')\n"
    )
    code, text, receipt = _run(capsys)
    assert code == 0
    assert "state_reads contract check passed" in text
    assert receipt["verdict"] == "PASS"


def test_async_execute_missing_read_preserves_original_failure(tree, capsys):
    _, selected = tree
    node = selected / "node.py"
    node.write_text(_node("NodeSpec", []).replace("def execute", "async def execute"))
    code, text, receipt = _run(capsys)
    assert code == 1
    assert "missing state_reads path 'inputs.required'" in text
    assert receipt["verdict"] == "FAIL"


@pytest.mark.parametrize(
    ("declaration", "reason"),
    [
        ("KNOWN_READS", "unsupported_state_reads_expression"),
        ("[known_input]", "unsupported_state_reads_entry"),
    ],
)
def test_nonliteral_reads_remain_undecided(tree, capsys, declaration, reason):
    _, selected = tree
    node = selected / "node.py"
    node.write_text(
        f"_SPEC = NodeSpec(state_reads={declaration})\n"
        "def execute(state, context):\n"
        "    return state.inputs.get('required')\n"
    )
    code, text, receipt = _run(capsys)
    assert code == 2
    assert "contract check passed" not in text
    assert receipt["unresolved_inputs"] == [{"path": str(node), "reason": reason}]


@pytest.mark.parametrize(
    ("case", "source", "reason"),
    [
        (
            "direct_overwrite",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\n_SPEC = NodeSpec(state_reads=[])\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "annotated_overwrite",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\n_SPEC: NodeSpec = OutputAwareNodeSpec(state_reads=[])\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "reverse_overwrite",
            "_SPEC = NodeSpec(state_reads=[])\n_SPEC = NodeSpec(state_reads=['inputs.required'])\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "dead_if_supplies_read",
            "_SPEC = NodeSpec(state_reads=[])\nif False:\n    _SPEC = NodeSpec(state_reads=['inputs.required'])\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "conditional_supplies_read",
            "_SPEC = NodeSpec(state_reads=[])\nif flag:\n    _SPEC = NodeSpec(state_reads=['inputs.required'])\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "function_local_supplies_read",
            "_SPEC = NodeSpec(state_reads=[])\ndef helper():\n    _SPEC = NodeSpec(state_reads=['inputs.required'])\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "class_local_supplies_read",
            "_SPEC = NodeSpec(state_reads=[])\nclass Helper:\n    _SPEC = NodeSpec(state_reads=['inputs.required'])\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "nested_only_supplies_read",
            "def helper():\n    _SPEC = NodeSpec(state_reads=['inputs.required'])\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "unsupported_spec_binding_scope",
        ),
        (
            "sole_dead_supplies_read",
            "if False:\n    _SPEC = NodeSpec(state_reads=['inputs.required'])\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "unsupported_spec_binding_scope",
        ),
        (
            "delete_after_valid",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\ndel _SPEC\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "walrus_overwrite",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\n(_SPEC := NodeSpec(state_reads=[]))\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "for_target_overwrite",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\nfor _SPEC in [NodeSpec(state_reads=[])]:\n    pass\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "tuple_overwrite",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\n_SPEC, other = NodeSpec(state_reads=[]), None\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "augmented_overwrite",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\n_SPEC += replacement\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "definition",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\ndef _SPEC():\n    pass\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "async_definition",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\nasync def _SPEC():\n    pass\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "class_definition",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\nclass _SPEC:\n    pass\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "import_alias",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\nimport module as _SPEC\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "from_import",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\nfrom module import _SPEC\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "parameter_binding",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\ndef helper(_SPEC):\n    pass\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "exception_binding",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\ntry:\n    pass\nexcept Exception as _SPEC:\n    pass\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "match_capture",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\nmatch value:\n    case _SPEC:\n        pass\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "match_rest",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\nmatch value:\n    case {\"key\": value, **_SPEC}:\n        pass\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "with_binding",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\nwith context as _SPEC:\n    pass\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
        (
            "type_parameter_binding",
            "_SPEC = NodeSpec(state_reads=['inputs.required'])\ndef helper[_SPEC]():\n    pass\ndef execute(state, context):\n    return state.inputs.get('required')\n",
            "ambiguous_spec_binding",
        ),
    ],
)
def test_actual_checker_refuses_ambiguous_or_unscoped_spec_binding(
    tree, capsys, case, source, reason
):
    """Unreachable/local/overwritten declarations cannot supply an admitted module read."""
    _, selected = tree
    node = selected / f"{case}.py"
    node.write_text(source)
    code, text, receipt = _run(capsys)
    assert code == 2 and "contract check passed" not in text
    assert receipt["verdict"] == "UNRUN" and not receipt["complete_verdict"]
    assert receipt["selected_paths"] == [str(node)]
    assert receipt["selected_input_denominator"] == 1
    assert receipt["inputs"][0]["status"] == "read"
    assert receipt["unresolved_inputs"] == [{"path": str(node), "reason": reason}]
    assert receipt["inputs"][0]["text_sha256"]


def test_imported_source_name_does_not_create_a_local_spec_binding(tree, capsys):
    """An import renamed to another local symbol cannot shadow the admitted spec."""
    _, selected = tree
    node = selected / "renamed_import.py"
    node.write_text(
        "from module import _SPEC as OTHER_SPEC\n"
        + _node("NodeSpec", ["inputs.required"])
    )
    code, text, receipt = _run(capsys)
    assert code == 0 and "contract check passed" in text
    assert receipt["verdict"] == "PASS" and receipt["complete_verdict"]
    assert receipt["selected_paths"] == [str(node)]
    assert receipt["inputs"][0]["status"] == "read"
