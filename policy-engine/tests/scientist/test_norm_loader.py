from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir.norm_pack import NormPack, NormRule, RuleType
from polisyos.scientist.agent.norm_loader import CASNormPackLoader, StaticNormPackLoader


def _norm_pack() -> NormPack:
    return NormPack(
        pack_id="pack_test",
        jurisdiction="uk",
        norms=[
            NormRule(
                norm_id="rule_1",
                rule_type=RuleType.OBLIGATION,
                description="Provide equal treatment",
            )
        ],
    )


def test_static_norm_loader_returns_preconfigured_pack() -> None:
    pack = _norm_pack()
    loader = StaticNormPackLoader(norm_pack=pack)

    loaded = loader.load_for_context(jurisdiction="uk", domain="fiscal")

    assert loaded is not None
    assert loaded.pack_id == "pack_test"


def test_cas_norm_loader_loads_by_context(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    pack = _norm_pack()
    ref = cas.put_json(
        pack.model_dump(mode="json"),
        PutOptions(kind="ir.norm_pack", media_type="application/json"),
    )

    loader = CASNormPackLoader(cas, refs_by_context={"uk:fiscal": str(ref.artifact_id)})
    loaded = loader.load_for_context(jurisdiction="uk", domain="fiscal")

    assert loaded is not None
    assert loaded.pack_id == "pack_test"


def test_cas_norm_loader_assertion_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeCAS:
        def get_bytes(self, artifact_id):
            del artifact_id
            return b"{}"

    def _boom(value):
        del value
        raise AssertionError("artifact id invariant failed")

    monkeypatch.setattr(
        "polisyos.scientist.agent.norm_loader.ArtifactID.model_validate",
        _boom,
    )

    loader = CASNormPackLoader(_FakeCAS(), default_ref="sha256:" + ("0" * 64))

    with pytest.raises(AssertionError, match="artifact id invariant failed"):
        loader.load_for_context(jurisdiction="uk", domain="fiscal")
