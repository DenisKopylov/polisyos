from __future__ import annotations

import importlib
import os
import sys


def test_common_config_import_is_side_effect_free(monkeypatch) -> None:
    for key in (
        "JAX_PLATFORM_NAME",
        "JAX_PLATFORMS",
        "XLA_PYTHON_CLIENT_PREALLOCATE",
        "XLA_FLAGS",
        "SCIENTIST_TORCH_DEVICE",
        "OMP_NUM_THREADS",
    ):
        monkeypatch.delenv(key, raising=False)

    sys.modules.pop("polisyos.common.config", None)
    importlib.import_module("polisyos.common.config")

    for key in (
        "JAX_PLATFORM_NAME",
        "JAX_PLATFORMS",
        "XLA_PYTHON_CLIENT_PREALLOCATE",
        "XLA_FLAGS",
        "SCIENTIST_TORCH_DEVICE",
        "OMP_NUM_THREADS",
    ):
        assert os.environ.get(key) is None


def test_apply_process_bootstrap_sets_expected_env(tmp_path) -> None:
    config_module = importlib.import_module("polisyos.common.config")
    env: dict[str, str] = {}

    resolved = config_module.apply_process_bootstrap(
        env=env,
        load_dotenv_file=False,
        configure_logging_sinks=False,
        logs_root=tmp_path / "logs",
    )

    assert env["JAX_PLATFORM_NAME"] == "cpu"
    assert env["JAX_PLATFORMS"] == "cpu"
    assert env["XLA_PYTHON_CLIENT_PREALLOCATE"] == "false"
    assert env["SCIENTIST_TORCH_DEVICE"] == "cpu"
    assert "intra_op_parallelism_threads=" in env["XLA_FLAGS"]
    assert resolved.allowed_cores >= 1


def test_validate_process_bootstrap_detects_conflicting_jax_platforms() -> None:
    config_module = importlib.import_module("polisyos.common.config")
    config = config_module.build_process_bootstrap_config(
        env={
            "JAX_PLATFORM_NAME": "cpu",
            "JAX_PLATFORMS": "metal",
        }
    )

    conflicts = config_module.validate_process_bootstrap_config(config)

    assert conflicts == [
        "JAX_PLATFORM_NAME must be included in JAX_PLATFORMS when both are set"
    ]
