from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.data_forge.domains.legal import runtime_material
from polisyos.runtime.http import profiled_server
from polisyos.runtime.http.container import LegalQueryEncoderProvider, RuntimeContainerOverrides


def _profile_fixture(profile_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (profile_root / "hf-cache").mkdir(parents=True)
    manifest = json.dumps(
        {
            "revision": runtime_material.LEGAL_CONTROLLED_MODEL_REVISION,
            "named_file_count": 9,
            "files": [
                {"path": f"file-{index}", "sha256": "0" * 64, "size": 0} for index in range(9)
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    (profile_root / "asset-file-manifest.txt").write_bytes(manifest)
    monkeypatch.setattr(
        runtime_material,
        "LEGAL_CONTROLLED_MANIFEST_SHA256",
        hashlib.sha256(manifest).hexdigest(),
    )


def test_profiled_app_wires_existing_owner_provider_and_container(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile_root = tmp_path / "profile"
    profile_root.mkdir()
    _profile_fixture(profile_root, monkeypatch)
    captured: dict[str, object] = {}

    def create_app(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(profiled_server, "create_runtime_api_app", create_app)

    app = profiled_server.create_profiled_runtime_api_app(
        runtime_material_profile_root=profile_root
    )

    assert app is not None
    overrides = captured["container_overrides"]
    assert isinstance(overrides, RuntimeContainerOverrides)
    provider = overrides.legal_query_encoder_provider
    assert isinstance(provider, LegalQueryEncoderProvider)
    owner = provider.runtime_material_owner
    assert type(owner) is runtime_material.LegalRuntimeMaterialOwner
    assert owner._cache_root == (profile_root / "hf-cache").resolve()


def test_profiled_app_keeps_profileless_default_composition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    sentinel = object()
    monkeypatch.setattr(
        profiled_server,
        "create_runtime_api_app",
        lambda **kwargs: (captured.update(kwargs), sentinel)[1],
    )

    assert profiled_server.create_profiled_runtime_api_app() is sentinel
    assert "container_overrides" not in captured


def test_malformed_explicit_profile_refuses_before_app_factory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    called = False

    def create_app(**_kwargs: object) -> object:
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(profiled_server, "create_runtime_api_app", create_app)

    with pytest.raises(runtime_material.LegalRuntimeMaterialError) as exc_info:
        profiled_server.create_profiled_runtime_api_app(
            runtime_material_profile_root=tmp_path / "missing-profile"
        )

    assert exc_info.value.code == "query_encoder_runtime_material_not_established"
    assert called is False


def test_present_wrong_profile_refuses_before_app_factory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile_root = tmp_path / "wrong-profile"
    profile_root.mkdir()
    _profile_fixture(profile_root, monkeypatch)
    monkeypatch.setattr(
        runtime_material,
        "LEGAL_CONTROLLED_MANIFEST_SHA256",
        "0" * 64,
    )
    called = False

    def create_app(**_kwargs: object) -> object:
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(profiled_server, "create_runtime_api_app", create_app)

    with pytest.raises(runtime_material.LegalRuntimeMaterialError) as exc_info:
        profiled_server.create_profiled_runtime_api_app(runtime_material_profile_root=profile_root)

    assert exc_info.value.code == "query_encoder_runtime_material_not_established"
    assert called is False


def test_module_runner_uses_factory_without_import_path_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    class Config:
        def __init__(self, app: object, **kwargs: object) -> None:
            captured["app"] = app
            captured.update(kwargs)

    class Server:
        def __init__(self, config: object) -> None:
            captured["config"] = config

        def run(self) -> None:
            captured["ran"] = True

    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(Config=Config, Server=Server))

    profiled_server.main(
        [
            "--runtime-material-profile-root",
            str(tmp_path / "profile"),
            "--host",
            "127.0.0.1",
            "--port",
            "9100",
        ]
    )

    assert callable(captured["app"])
    assert captured["factory"] is True
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9100
    assert "app_dir" not in captured
    assert captured["ran"] is True
