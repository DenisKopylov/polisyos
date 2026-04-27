from __future__ import annotations

from polisyos.scientist.evals.graders import EvalFamily, grader_for_family, list_graders


def test_grader_registry_covers_required_eval_families() -> None:
    graders = list_graders()

    assert {item.family for item in graders} == set(EvalFamily)
    assert grader_for_family("citation_faithfulness").requires_hidden_pack is True
