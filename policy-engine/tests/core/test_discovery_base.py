from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.discovery import BaseDiscovery, discovery_module_name, list_entry_points


@dataclass
class _DummyEntryPoint:
    name: str
    value: str


class _SourceOk:
    def __init__(self) -> None:
        self.errors = ["warning-1"]

    def discover(self):
        yield "a"
        yield "b"


class _SourceFail:
    def discover(self):
        raise RuntimeError("boom")


def test_base_discovery_collects_items_and_errors() -> None:
    collector = BaseDiscovery[str, str](
        on_source_error=lambda _source, exc: f"source-error:{exc}",
    )
    collector.add_source(_SourceOk())
    collector.add_source(_SourceFail())

    batches, processed = collector.collect()

    assert processed == 2
    assert batches[0].items == ["a", "b"]
    assert batches[0].errors == ["warning-1"]
    assert batches[1].items == []
    assert batches[1].errors == ["source-error:boom"]


def test_discovery_module_name_is_deterministic(tmp_path) -> None:
    path = tmp_path / "module.py"
    path.write_text("# stub", encoding="utf-8")

    first = discovery_module_name(path, prefix="pfx_", digest_length=8)
    second = discovery_module_name(path, prefix="pfx_", digest_length=8)

    assert first == second
    assert first.startswith("pfx_")


def test_list_entry_points_compat(monkeypatch) -> None:
    ep_a = _DummyEntryPoint(name="b", value="z")
    ep_b = _DummyEntryPoint(name="a", value="z")

    class _FakeCollection:
        def select(self, *, group: str):
            assert group == "x.group"
            return [ep_a, ep_b]

    monkeypatch.setattr(
        "polisyos.core.discovery.base.metadata.entry_points",
        lambda: _FakeCollection(),
    )

    entries = list_entry_points(group="x.group")
    assert [entry.name for entry in entries] == ["a", "b"]

