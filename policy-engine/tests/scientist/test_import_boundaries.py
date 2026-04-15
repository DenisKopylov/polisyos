from __future__ import annotations

import importlib
import sys


def _clear_import_state() -> None:
    prefixes = (
        "polisyos.core.contracts.lex",
        "polisyos.ir.analytics",
        "polisyos.ir.analytics.alignment_certification",
        "polisyos.ir.norm_pack",
        "polisyos.lex.api",
        "polisyos.scientist.cross_graph.compiler",
    )
    for module_name in list(sys.modules):
        if module_name in prefixes or module_name.startswith(prefixes):
            sys.modules.pop(module_name, None)


def test_core_lex_import_does_not_eagerly_load_scientist_alignment_boundary() -> None:
    _clear_import_state()

    module = importlib.import_module("polisyos.core.contracts.lex")

    assert module.ChangeProposalRef.__name__ == "ChangeProposalRef"
    assert "polisyos.ir.analytics" in sys.modules
    assert "polisyos.ir.analytics.alignment_certification" not in sys.modules
    assert "polisyos.scientist.cross_graph.compiler" not in sys.modules


def test_ir_analytics_alignment_exports_resolve_lazily() -> None:
    _clear_import_state()

    analytics = importlib.import_module("polisyos.ir.analytics")

    assert "polisyos.ir.analytics.alignment_certification" not in sys.modules
    assert analytics.AlignmentReport.__name__ == "AlignmentReport"
    assert "polisyos.ir.analytics.alignment_certification" in sys.modules
