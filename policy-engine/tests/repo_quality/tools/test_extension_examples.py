from __future__ import annotations

from pathlib import Path

from tools.quality.validation import check_extension_examples

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase6_4_extension_examples_cover_required_hosts() -> None:
    examples = {example.slug: example for example in check_extension_examples.EXAMPLES}

    assert set(examples) == {
        "fabric_connector",
        "foundry_method",
        "scientist_governance_pass",
        "scientist_node",
        "data_forge_domain",
        "lex_normpack",
        "runtime_middleware",
    }
    assert {example.group for example in examples.values()} == {
        "polisyos.fabric_connectors",
        "polisyos.foundry_methods",
        "polisyos.scientist_governance_passes",
        "polisyos.scientist_nodes",
        "polisyos.data_forge_domains",
        "polisyos.lex_normpacks",
        "polisyos.runtime_middlewares",
    }


def test_phase6_4_extension_examples_have_installable_entry_point_contracts() -> None:
    errors = check_extension_examples.validate_pyproject(
        REPO_ROOT,
        check_extension_examples.EXAMPLES,
    )

    assert errors == []
