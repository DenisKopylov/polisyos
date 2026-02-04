from __future__ import annotations

from pathlib import Path

from polisyos.core.components import (
    ENTRY_POINT_GROUP_FOUNDRY_METHODS,
    ENTRY_POINT_GROUP_IR_FRAGMENTS,
    ENTRY_POINT_GROUP_LEX_EVALUATORS,
    ENTRY_POINT_GROUP_LEX_EXTRACTORS,
    ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS,
    ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS,
    discover_components,
)
from polisyos.packs.econ.ir_fragments import econ_ir_fragment_component
from polisyos.packs.roads.foundry_methods import roads_method_component
from polisyos.packs.roads.ir_fragments import roads_ir_fragment_component
from polisyos.packs.roads.lex_evaluators import lex_simple_evaluator_component
from polisyos.packs.roads.norms_provider import roads_norms_provider_component
from polisyos.packs.roads.scholar_extractors import (
    lex_norm_regex_extractor_component,
    roads_extractor_component,
)


class _FakeEntryPoint:
    def __init__(self, *, group: str, name: str, loader):
        self.group = group
        self.name = name
        self._loader = loader
        self.value = f"{name}:component"
        self.module = name
        self.attr = "component"

    def load(self):
        return self._loader


class _FakeEntryPoints:
    def __init__(self, by_group):
        self._by_group = by_group

    def select(self, *, group: str):
        return list(self._by_group.get(group, []))


def test_pack_install_like_import_dev_scan() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    packs_root = repo_root / "src" / "polisyos" / "packs"

    report = discover_components(
        groups=[],
        include_dev_scan=True,
        dev_scan_paths=[packs_root],
    )
    ids = {str(item.metadata.component_id) for item in report.components}

    assert "roads.ir.registry_fragment@1.0.0" in ids
    assert "roads.method.speed_cap@1.0.0" in ids
    assert "roads.scholar.speed_limit@1.0.0" in ids
    assert "roads.normpack.static_provider@1.0.0" in ids


def test_pack_discovery_entry_points_equivalent(monkeypatch) -> None:
    by_group = {
        ENTRY_POINT_GROUP_IR_FRAGMENTS: [
            _FakeEntryPoint(group=ENTRY_POINT_GROUP_IR_FRAGMENTS, name="roads.ir", loader=lambda: roads_ir_fragment_component),
            _FakeEntryPoint(group=ENTRY_POINT_GROUP_IR_FRAGMENTS, name="econ.ir", loader=lambda: econ_ir_fragment_component),
        ],
        ENTRY_POINT_GROUP_FOUNDRY_METHODS: [
            _FakeEntryPoint(group=ENTRY_POINT_GROUP_FOUNDRY_METHODS, name="roads.method", loader=lambda: roads_method_component),
        ],
        ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS: [
            _FakeEntryPoint(group=ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS, name="roads.scholar", loader=lambda: roads_extractor_component),
        ],
        ENTRY_POINT_GROUP_LEX_EXTRACTORS: [
            _FakeEntryPoint(group=ENTRY_POINT_GROUP_LEX_EXTRACTORS, name="roads.lex", loader=lambda: lex_norm_regex_extractor_component),
        ],
        ENTRY_POINT_GROUP_LEX_EVALUATORS: [
            _FakeEntryPoint(group=ENTRY_POINT_GROUP_LEX_EVALUATORS, name="roads.eval", loader=lambda: lex_simple_evaluator_component),
        ],
        ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS: [
            _FakeEntryPoint(group=ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS, name="roads.provider", loader=lambda: roads_norms_provider_component),
        ],
    }

    monkeypatch.setattr(
        "polisyos.core.components.discovery.metadata.entry_points",
        lambda: _FakeEntryPoints(by_group),
    )

    entry_report = discover_components(include_dev_scan=False)

    repo_root = Path(__file__).resolve().parents[1]
    packs_root = repo_root / "src" / "polisyos" / "packs"
    dev_report = discover_components(groups=[], include_dev_scan=True, dev_scan_paths=[packs_root])

    entry_set = {(str(item.metadata.component_id), item.metadata.kind.value) for item in entry_report.components}
    dev_set = {(str(item.metadata.component_id), item.metadata.kind.value) for item in dev_report.components}

    # Entry-points in this test cover the same built-in components subset.
    assert entry_set.issubset(dev_set)
