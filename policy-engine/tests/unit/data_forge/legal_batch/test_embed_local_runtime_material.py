from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.data_forge.domains.legal import runtime_material
from polisyos.data_forge.domains.legal.batch import cli


def _profile_manifest() -> bytes:
    return json.dumps(
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


def _write_profile(root: Path, manifest: bytes) -> None:
    (root / "hf-cache").mkdir(parents=True)
    (root / "asset-file-manifest.txt").write_bytes(manifest)


def test_profile_root_factory_binds_only_the_fixed_children(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile_root = tmp_path / "profile"
    manifest = _profile_manifest()
    _write_profile(profile_root, manifest)
    monkeypatch.setattr(
        runtime_material,
        "LEGAL_CONTROLLED_MANIFEST_SHA256",
        hashlib.sha256(manifest).hexdigest(),
    )

    owner = runtime_material.LegalRuntimeMaterialOwner.from_profile_root(profile_root)

    assert owner._cache_root == (profile_root / "hf-cache").resolve()
    assert owner._manifest_path == (profile_root / "asset-file-manifest.txt").resolve()


@pytest.mark.parametrize("missing", ["hf-cache", "asset-file-manifest.txt"])
def test_profile_root_factory_refuses_missing_members_without_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, missing: str
) -> None:
    profile_root = tmp_path / "profile"
    profile_root.mkdir()
    if missing != "hf-cache":
        (profile_root / "hf-cache").mkdir()
    if missing != "asset-file-manifest.txt":
        manifest = _profile_manifest()
        (profile_root / "asset-file-manifest.txt").write_bytes(manifest)
        monkeypatch.setattr(
            runtime_material,
            "LEGAL_CONTROLLED_MANIFEST_SHA256",
            hashlib.sha256(manifest).hexdigest(),
        )

    with pytest.raises(runtime_material.LegalRuntimeMaterialError) as exc_info:
        runtime_material.LegalRuntimeMaterialOwner.from_profile_root(profile_root)

    assert exc_info.value.code == "query_encoder_runtime_material_not_established"


def test_profile_root_factory_refuses_present_but_unrecognized_manifest(
    tmp_path: Path,
) -> None:
    profile_root = tmp_path / "profile"
    _write_profile(profile_root, b'{"revision":"caller-selected"}')

    with pytest.raises(runtime_material.LegalRuntimeMaterialError) as exc_info:
        runtime_material.LegalRuntimeMaterialOwner.from_profile_root(profile_root)

    assert exc_info.value.code == "query_encoder_runtime_material_not_established"


@pytest.mark.parametrize("escaped_member", ["hf-cache", "asset-file-manifest.txt"])
def test_profile_root_factory_rejects_symlinked_members_outside_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, escaped_member: str
) -> None:
    profile_root = tmp_path / "profile"
    outside = tmp_path / "outside"
    profile_root.mkdir()
    outside.mkdir()
    manifest = _profile_manifest()
    monkeypatch.setattr(
        runtime_material,
        "LEGAL_CONTROLLED_MANIFEST_SHA256",
        hashlib.sha256(manifest).hexdigest(),
    )
    (outside / "hf-cache").mkdir()
    (outside / "asset-file-manifest.txt").write_bytes(manifest)
    for member in ("hf-cache", "asset-file-manifest.txt"):
        if member == escaped_member:
            (profile_root / member).symlink_to(
                outside / member,
                target_is_directory=member == "hf-cache",
            )
        elif member == "hf-cache":
            (profile_root / member).mkdir()
        else:
            (profile_root / member).write_bytes(manifest)

    with pytest.raises(runtime_material.LegalRuntimeMaterialError) as exc_info:
        runtime_material.LegalRuntimeMaterialOwner.from_profile_root(profile_root)

    assert exc_info.value.code == "query_encoder_runtime_material_not_established"


def test_embed_local_parser_keeps_legacy_defaults_and_accepts_controlled_profile(
    tmp_path: Path,
) -> None:
    parser = cli._build_parser()
    legacy_args = parser.parse_args(["embed-local", "--output-dir", str(tmp_path)])
    profiled_args = parser.parse_args(
        [
            "embed-local",
            "--output-dir",
            str(tmp_path),
            "--runtime-material-profile-root",
            str(tmp_path / "profile"),
        ]
    )

    assert legacy_args.model is None
    assert legacy_args.device is None
    assert legacy_args.batch_size is None
    assert legacy_args.chunk_size is None
    assert legacy_args.runtime_material_profile_root is None
    assert profiled_args.runtime_material_profile_root == tmp_path / "profile"


def test_embed_local_composes_owner_from_explicit_profile_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "graph.duckdb"
    db_path.touch()
    profile_root = tmp_path / "profile"
    owner = object()
    observed: dict[str, object] = {}

    def build(**kwargs: object) -> SimpleNamespace:
        observed.update(kwargs)
        return SimpleNamespace(
            entities_embedded=1,
            entities_skipped=0,
            facts_embedded=1,
            facts_skipped=0,
            provisions_embedded=1,
            provisions_skipped=0,
            elapsed_seconds=0.1,
        )

    # A classmethod replacement with a direct owner result exercises the same
    # CLI composition seam without loading a model.
    monkeypatch.setattr(
        runtime_material.LegalRuntimeMaterialOwner,
        "from_profile_root",
        classmethod(lambda cls, path: (observed.update(profile_root=path), owner)[1]),
    )
    monkeypatch.setattr(
        "polisyos.data_forge.domains.legal.batch.embedder.build_local_embeddings_and_indexes",
        build,
    )
    monkeypatch.setattr(
        "polisyos.data_forge.kernel.embeddings.embedding_generation_manifest",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(cli, "write_stage_manifest", lambda **kwargs: None)

    args = cli._build_parser().parse_args(
        [
            "embed-local",
            "--output-dir",
            str(tmp_path),
            "--db-path",
            str(db_path),
            "--runtime-material-profile-root",
            str(profile_root),
        ]
    )
    cli._cmd_embed_local(args)

    assert observed["profile_root"] == profile_root
    assert observed["runtime_material_owner"] is owner
    assert observed["embedding_model"] is None
    assert observed["embedding_device"] is None
    assert observed["embedding_batch_size"] is None
    assert observed["embedding_chunk_size"] is None


def test_embed_local_without_profile_keeps_legacy_ownerless_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "graph.duckdb"
    db_path.touch()
    observed: dict[str, object] = {}

    def unexpected_owner_factory(_cls: type[object], _path: Path) -> object:
        raise AssertionError("profileless generation must not resolve the Legal material owner")

    monkeypatch.setattr(
        runtime_material.LegalRuntimeMaterialOwner,
        "from_profile_root",
        classmethod(unexpected_owner_factory),
    )

    def build(**kwargs: object) -> SimpleNamespace:
        observed.update(kwargs)
        return SimpleNamespace(
            entities_embedded=1,
            entities_skipped=0,
            facts_embedded=1,
            facts_skipped=0,
            provisions_embedded=1,
            provisions_skipped=0,
            elapsed_seconds=0.1,
        )

    monkeypatch.setattr(
        "polisyos.data_forge.domains.legal.batch.embedder.build_local_embeddings_and_indexes",
        build,
    )
    monkeypatch.setattr(
        "polisyos.data_forge.kernel.embeddings.embedding_generation_manifest",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(cli, "write_stage_manifest", lambda **kwargs: None)

    args = cli._build_parser().parse_args(
        ["embed-local", "--output-dir", str(tmp_path), "--db-path", str(db_path)]
    )
    cli._cmd_embed_local(args)

    assert observed["runtime_material_owner"] is None
    assert observed["embedding_model"] is None
    assert observed["embedding_device"] is None


def test_stats_refuses_missing_aggregate_result_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    db_path.touch()

    class NoRowConnection:
        def execute(self, _query: str) -> NoRowConnection:
            return self

        def fetchone(self) -> None:
            return None

        def close(self) -> None:
            return None

    connection = NoRowConnection()
    monkeypatch.setitem(
        sys.modules,
        "duckdb",
        SimpleNamespace(connect=lambda *_args, **_kwargs: connection),
    )

    with pytest.raises(RuntimeError, match="legal_stats_count_row_missing"):
        cli._cmd_stats(SimpleNamespace(output_dir=tmp_path))
