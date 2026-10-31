"""Read the canonical registry materialization graph through bounded Core sources."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_registry_bundle, load_registry_bundle_content
from polisyos.ir.kernel import (
    ConstraintRegistry,
    MechanismTypeRegistry,
    MergeRuleRegistry,
    MetricRegistry,
    SelectorFieldRegistry,
    SlotRegistry,
    TrustRegistry,
    UnitsRegistry,
)


class _BoundedOnly:
    def __init__(self, store):
        self.store = store

    def __getattr__(self, name):
        return getattr(self.store, name)

    def get_bytes(self, *args, **kwargs):
        raise AssertionError("registry attempted an unbounded payload fallback")

    def get_manifest(self, *args, **kwargs):
        raise AssertionError("registry attempted an unbounded manifest fallback")


def _bundle(store):
    return build_registry_bundle(
        store,
        slot_registry=SlotRegistry(),
        merge_registry=MergeRuleRegistry(),
        mechanism_registry=MechanismTypeRegistry(),
        constraint_registry=ConstraintRegistry(),
        selector_field_registry=SelectorFieldRegistry(),
        metric_registry=MetricRegistry(),
        units_registry=UnitsRegistry(),
        trust_registry=TrustRegistry(),
        return_selected_profile=True,
    )


def _limits(max_bytes=1_000_000):
    return CoreJsonReadLimits(
        max_bytes=max_bytes, max_depth=100, max_elements=100_000, max_manifest_bytes=1_000_000
    )


def test_real_registry_materializer_bounds_all_eight_member_reads(tmp_path) -> None:
    from polisyos.scientist.orchestration.engine.child_compiler_closure import _ExecutionReader

    store = FileSystemCAS(tmp_path / "cas")
    bundle = _bundle(store)
    bounded = _BoundedOnly(store)

    class RecordingReader(_ExecutionReader):
        def __init__(self):
            super().__init__(bounded, _limits())
            self.models = []

        def read_typed_model(self, model, ref):
            self.models.append(model.__name__)
            return super().read_typed_model(model, ref)

    reader = RecordingReader()
    result = load_registry_bundle_content(bounded, bundle.bundle_ref, reader=reader)
    assert result.bundle_ref == bundle.bundle_ref
    assert reader.models == [
        "RegistryBundlePayload",
        "SlotRegistry",
        "MergeRuleRegistry",
        "MechanismTypeRegistry",
        "ConstraintRegistry",
        "SelectorFieldRegistry",
        "MetricRegistry",
        "UnitsRegistry",
        "TrustRegistry",
    ]
    assert result.trust_registry == TrustRegistry()
    assert reader.manifest_bytes + reader.payload_bytes > 0


@pytest.mark.parametrize("invalid", ["model", "manifest", "count", "reference"])
def test_bounded_registry_rejects_malformed_source_reply_or_selector(tmp_path, invalid) -> None:
    from polisyos.scientist.orchestration.engine.child_compiler_closure import _ExecutionReader

    store = FileSystemCAS(tmp_path / "cas")
    bundle = _bundle(store)
    bounded = _BoundedOnly(store)

    class InvalidReader(_ExecutionReader):
        def read_typed_model(self, model, ref):
            manifest, value, manifest_bytes, payload_bytes = super().read_typed_model(model, ref)
            if invalid == "model":
                value = SlotRegistry()
            elif invalid == "manifest":
                manifest = manifest.model_copy(update={"kind": "test.foreign"})
            elif invalid == "count":
                manifest_bytes = True
            return manifest, value, manifest_bytes, payload_bytes

    selector = bundle.bundle_ref
    if invalid == "reference":
        selector = selector.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(ValueError, match="registry_bounded_reader_"):
        load_registry_bundle_content(bounded, selector, reader=InvalidReader(bounded, _limits()))


def test_bounded_registry_budget_refusal_never_uses_legacy_store_methods(tmp_path) -> None:
    from polisyos.scientist.orchestration.engine.child_compiler_closure import _ExecutionReader

    store = FileSystemCAS(tmp_path / "cas")
    bundle = _bundle(store)
    cap = len(store.get_raw_manifest_bytes(bundle.bundle_ref)) + len(
        store.get_bytes(bundle.bundle_ref)
    )
    bounded = _BoundedOnly(store)
    reader = _ExecutionReader(bounded, _limits(cap))
    with pytest.raises(ValueError, match="child_compiler_execution_read_budget_exhausted"):
        load_registry_bundle_content(bounded, bundle.bundle_ref, reader=reader)
    assert reader.manifest_bytes + reader.payload_bytes <= cap
