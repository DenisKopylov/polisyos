from __future__ import annotations

import importlib

from polisyos.runtime.quality import confidence_ledger as ledger


def _legacy_quality_bindings() -> dict[str, object]:
    """Rebuild the facade's pre-explicit-import namespace and precedence."""

    fitness_report = importlib.import_module("polisyos.fabric.quality.fitness_report")
    processing = importlib.import_module("polisyos.fabric.quality.processing_guarantees")
    quality = importlib.import_module("polisyos.fabric.quality.quality")
    safety = importlib.import_module("polisyos.fabric.quality.safety")

    expected = {
        "DataFitnessReport": fitness_report.DataFitnessReport,
        "MetricFitness": fitness_report.MetricFitness,
    }
    for name in processing.__all__:
        expected[name] = getattr(processing, name)
    for name, value in vars(quality).items():
        if not name.startswith("_"):
            expected[name] = value
    expected["_default_metrics"] = quality._default_metrics
    for name in safety.__all__:
        expected[name] = getattr(safety, name)

    expected.update(
        {
            "fitness_report": fitness_report,
            "processing_guarantees": processing,
            "quality": quality,
            "safety": safety,
        }
    )
    return expected


def test_quality_facade_preserves_complete_legacy_namespace_and_precedence() -> None:
    facade = importlib.import_module("polisyos.fabric.quality")
    expected = _legacy_quality_bindings()
    observed = {name: value for name, value in vars(facade).items() if not name.startswith("__")}

    assert facade.__all__ == ["DataFitnessReport", "MetricFitness"]
    assert observed.keys() == expected.keys()
    assert all(observed[name] is value for name, value in expected.items())
    assert (
        facade._default_metrics
        is importlib.import_module("polisyos.fabric.quality.quality")._default_metrics
    )


def test_quality_gate_imports_exact_source_owned_facade_exports() -> None:
    facade = importlib.import_module("polisyos.fabric.quality")
    owner = importlib.import_module("polisyos.fabric.quality.quality")
    consumer = importlib.import_module("polisyos.scientist.governance.passes.quality_gate_pass")
    root = ledger._loaded_policy_engine_root()
    source_index = ledger._AuthorityImportClosureSourceIndex({}, {})
    for name in (
        "QualityIndicators",
        "QualityLevel",
        "QualityThresholds",
        "compute_quality_indicators",
        "get_cached_quality_indicators",
    ):
        assert getattr(facade, name) is getattr(owner, name)
        assert getattr(consumer, name) is getattr(owner, name)
        candidate = ledger._source_module_import_route_candidate(
            root,
            facade.__name__,
            name,
            directory_entries={},
            source_index=source_index,
            discovery_only=True,
        )
        assert candidate.route == ("symbol", owner.__name__, name)
