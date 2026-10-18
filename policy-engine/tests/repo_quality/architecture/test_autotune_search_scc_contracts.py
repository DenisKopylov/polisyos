from __future__ import annotations

from tools.quality.validation import decomposition_preflight as preflight


def test_autotune_search_contract_scc_is_absent_from_full_import_graph() -> None:
    """Require the real full source graph to keep the former SCC acyclic."""
    selected_scc = {
        "polisyos.scientist.methods.autotune.bayesian_generator",
        "polisyos.scientist.methods.autotune.cheap_stage",
        "polisyos.scientist.methods.autotune.execution_plan",
        "polisyos.scientist.methods.autotune.runtime",
        "polisyos.scientist.methods.search.adapters",
        "polisyos.scientist.methods.search.contracts",
        "polisyos.scientist.methods.search.controller",
        "polisyos.scientist.methods.search.funnel.orchestrator",
        "polisyos.scientist.methods.search.funnel.types",
        "polisyos.scientist.methods.search.pareto_registry",
        "polisyos.scientist.methods.search",
        "polisyos.scientist.methods.search.lifecycle",
        "polisyos.scientist.methods.search.run_state",
        "polisyos.scientist.methods.search.service",
        "polisyos.scientist.methods.search.stages",
    }
    graph = preflight.collect_import_graph()
    intersecting_cycles = [
        set(cycle["modules"]) & selected_scc
        for cycle in graph["cycles"]
        if set(cycle["modules"]) & selected_scc
    ]

    assert intersecting_cycles == []
