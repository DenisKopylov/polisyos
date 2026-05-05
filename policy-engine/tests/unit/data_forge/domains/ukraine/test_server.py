from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.data_forge.domains.ukraine.models import build_default_pipeline_config
from polisyos.data_forge.domains.ukraine.server import (
    build_bootstrap_script,
    probe_local_server_capabilities,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_bootstrap_script_contains_server_marker_and_cli(tmp_path: Path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    script = build_bootstrap_script(config.server, config.build_root)

    assert f"export {config.server.server_marker_env}=1" in script
    assert "uv run ukraine-data bootstrap-server --write-capabilities" in script
    assert str(config.build_root.raw_dir) in script
    assert str(config.build_root.manifests_dir) in script


def test_probe_local_server_capabilities_returns_manifest(tmp_path: Path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    capability = probe_local_server_capabilities(config.server)

    assert capability.host
    assert capability.total_ram_gib >= 0.0
    assert capability.free_disk_gib >= 0.0
