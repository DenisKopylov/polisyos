from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from polisyos.data_forge.domains.ukraine.models import build_default_pipeline_config
from polisyos.data_forge.domains.ukraine.server import (
    OpsCompositionRequiredError,
    build_bootstrap_script,
    probe_local_server_capabilities,
)
from tools.ops_runners.ukraine_data.server_bootstrap import (
    probe_local_server_capabilities as probe_ops_server_capabilities,
)
from tools.ops_runners.ukraine_data.server_bootstrap import (
    render_bootstrap_script,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_domain_bootstrap_renderer_requires_ops_composition(tmp_path: Path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")

    with pytest.raises(OpsCompositionRequiredError, match="Ops composition"):
        build_bootstrap_script(config.server, config.build_root)


def test_ops_bootstrap_script_contains_server_marker_and_cli(tmp_path: Path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    script = render_bootstrap_script(config.server, config.build_root)

    assert f"export {config.server.server_marker_env}=1" in script
    assert "uv run ukraine-data bootstrap-server --write-capabilities" in script
    assert str(config.build_root.raw_dir) in script
    assert str(config.build_root.manifests_dir) in script


def test_domain_server_probe_requires_ops_composition(tmp_path: Path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")

    with pytest.raises(OpsCompositionRequiredError, match="Ops-owned"):
        probe_local_server_capabilities(config.server)


def test_ops_probe_local_server_capabilities_returns_manifest(tmp_path: Path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    capability = probe_ops_server_capabilities(config.server)

    assert capability.host
    assert capability.total_ram_gib >= 0.0
    assert capability.free_disk_gib >= 0.0
