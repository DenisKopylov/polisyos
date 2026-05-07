from __future__ import annotations

import json
from pathlib import Path

from tools.devx.workspace import remote_acceptance


def test_resolve_playwright_version_prefers_lockfile(tmp_path: Path) -> None:
    package_json = tmp_path / "package.json"
    package_lock = tmp_path / "package-lock.json"
    package_json.write_text(
        json.dumps({"devDependencies": {"@playwright/test": "^1.55.0"}}),
        encoding="utf-8",
    )
    package_lock.write_text(
        json.dumps(
            {
                "packages": {
                    "node_modules/@playwright/test": {
                        "version": "1.58.2",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    assert (
        remote_acceptance.resolve_playwright_version(
            package_json=package_json,
            package_lock=package_lock,
        )
        == "1.58.2"
    )


def test_render_toolchain_env_uses_isolated_paths() -> None:
    config = remote_acceptance.RemoteAcceptanceConfig()

    rendered = remote_acceptance.render_toolchain_env(config)

    assert f"export PATH={config.toolchain_bin}:" in rendered
    assert f'export UV_PYTHON_INSTALL_DIR="{config.toolchain_root}/python"' not in rendered
    assert f"export UV_PYTHON_INSTALL_DIR={config.toolchain_root}/python" in rendered
    assert f"export UV_PYTHON={config.toolchain_bin}/python3" in rendered
    assert "export UV_PYTHON_DOWNLOADS=never" in rendered
    assert "export POLISYOS_PYTEST_WORKERS=auto" in rendered
    assert "export POLISYOS_PYTEST_DIST=worksteal" in rendered


def test_resolve_remote_python_request_prefers_snapshot_patch(tmp_path: Path) -> None:
    fabric = tmp_path / "fabric.json"
    ir = tmp_path / "ir.json"
    fabric.write_text(json.dumps({"python_version": "3.14.0"}), encoding="utf-8")
    ir.write_text(json.dumps({"python_version": "3.14.0"}), encoding="utf-8")

    assert remote_acceptance.resolve_remote_python_request((fabric, ir)) == "3.14.0"


def test_build_provision_script_covers_required_surfaces() -> None:
    config = remote_acceptance.RemoteAcceptanceConfig()

    script = remote_acceptance.build_provision_script(
        config,
        playwright_version="1.58.2",
        python_request="3.14.0",
    )

    assert "docker.io" in script
    assert "docker-compose-v2" in script
    assert "libjpeg-dev" in script
    assert "uv python install" in script
    assert "latest-v22.x" in script
    assert "3.14.0" in script
    assert f"export UV_PYTHON={config.toolchain_bin}/python3" in script
    assert "export UV_PYTHON_DOWNLOADS=never" in script
    assert "export POLISYOS_PYTEST_WORKERS=auto" in script
    assert "npm exec --yes @playwright/test@1.58.2 --" in script
    assert "install-deps chromium" in script
    assert config.toolchain_env in script


def test_build_clean_checkout_script_uses_bundle_and_commit() -> None:
    config = remote_acceptance.RemoteAcceptanceConfig()

    script = remote_acceptance.build_clean_checkout_script(
        config,
        bundle_path="/root/polisyos-artifacts/bundles/example.bundle",
        commit="abc123",
    )

    assert config.clean_tree in script
    assert "git -C" in script
    assert "/root/polisyos-artifacts/bundles/example.bundle" in script
    assert "abc123" in script


def test_temporary_bundle_ref_is_stable_for_commit() -> None:
    assert (
        remote_acceptance._temporary_bundle_ref("abc123") == "refs/codex/remote-acceptance/abc123"
    )


def test_rsync_excludes_cover_local_caches() -> None:
    assert ".git/" in remote_acceptance.RSYNC_EXCLUDES
    assert "node_modules/" in remote_acceptance.RSYNC_EXCLUDES
    assert ".venv*/" in remote_acceptance.RSYNC_EXCLUDES
    assert "_build/" in remote_acceptance.RSYNC_EXCLUDES
    assert "_cache/" in remote_acceptance.RSYNC_EXCLUDES
    assert ".polisyos/" in remote_acceptance.RSYNC_EXCLUDES
    assert "/policy-engine/data/policy-engine-local/" in remote_acceptance.RSYNC_EXCLUDES
    assert "data/raw/" in remote_acceptance.RSYNC_EXCLUDES
    assert "data/dataset_catalog/" not in remote_acceptance.RSYNC_EXCLUDES
    assert "/policy-engine/runs/" not in remote_acceptance.RSYNC_EXCLUDES
    assert "runs/" not in remote_acceptance.RSYNC_EXCLUDES


def test_rsync_command_syncs_only_required_workspace_roots() -> None:
    config = remote_acceptance.RemoteAcceptanceConfig()

    argv = remote_acceptance._rsync_command(config, delete=True)

    assert str(remote_acceptance.WORKSPACE_ROOT / ".github") in argv
    assert str(remote_acceptance.WORKSPACE_ROOT / "policy-engine") in argv
