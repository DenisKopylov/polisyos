"""Tests for Phase 9.1 — zone-based lint policy assignment."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make tools/ importable
_tools_dir = Path(__file__).resolve().parent.parent.parent / "tools" / "lint"
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))

from lint_foundry import ZONE_MAP, DEFAULT_ZONE, _policy_for_file, _sorted_zone_entries


@pytest.fixture()
def foundry_root(tmp_path: Path) -> Path:
    """Create a mock foundry directory structure with representative files."""
    dirs = [
        "calibration",
        "compile",
        "methods/catalog/causal",
        "methods/catalog/causal/transport",
        "methods/catalog/econometrics",
        "methods/catalog/optimization",
        "methods/catalog/survey",
        "methods/backends",
        "methods/testing",
        "methods/cli",
        "plugins",
        "runtime",
        "agent_sim",
        "uncertainty",
    ]
    for d in dirs:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    files = [
        "calibration/bijectors.py",
        "compile/trinity_compiler.py",
        "constraints_engine.py",
        "methods/catalog/causal/tmle_core.py",
        "methods/catalog/causal/ci_backends.py",
        "methods/catalog/causal/transport/ot.py",
        "methods/catalog/econometrics/iv.py",
        "methods/catalog/optimization/linprog.py",
        "methods/catalog/survey/weighting.py",
        "methods/backends/dispatch.py",
        "methods/backends/checkpointing.py",
        "methods/backends/ray_runner.py",
        "methods/testing/helpers.py",
        "methods/cli/runner.py",
        "methods/base.py",
        "methods/discovery.py",
        "methods/hot_reload.py",
        "methods/cache.py",
        "methods/observability.py",
        "methods/compat_matrix.py",
        "methods/composer.py",
        "methods/deprecation.py",
        "methods/_artifacts_fingerprint.py",
        "methods/registry.py",
        "methods/compiler.py",
        "plugins/dashboard.py",
        "runtime/__init__.py",
        "agent_sim/core.py",
        "agents.py",
        "quickstart.py",
        "uncertainty/dispatcher.py",
    ]
    for f in files:
        (tmp_path / f).touch()

    return tmp_path


def test_pure_zone_no_banned_imports(foundry_root: Path) -> None:
    """Files in standard zone get 'standard' policy (strictest)."""
    assert _policy_for_file(foundry_root / "calibration" / "bijectors.py", foundry_root) == "standard"
    assert _policy_for_file(foundry_root / "constraints_engine.py", foundry_root) == "standard"
    assert _policy_for_file(foundry_root / "compile" / "trinity_compiler.py", foundry_root) == "standard"
    assert _policy_for_file(foundry_root / "uncertainty" / "dispatcher.py", foundry_root) == "standard"
    assert _policy_for_file(foundry_root / "methods" / "registry.py", foundry_root) == "standard"
    assert _policy_for_file(foundry_root / "methods" / "compiler.py", foundry_root) == "standard"


def test_mixed_zone_allows_scipy(foundry_root: Path) -> None:
    """Files in methods/backends/ and methods/catalog/ (non-causal) get 'mixed'."""
    assert _policy_for_file(foundry_root / "methods" / "backends" / "dispatch.py", foundry_root) == "mixed"
    assert _policy_for_file(foundry_root / "methods" / "catalog" / "survey" / "weighting.py", foundry_root) == "mixed"


def test_infra_zone_no_restrictions(foundry_root: Path) -> None:
    """Infra directories and files get 'infra' policy (no restrictions)."""
    # Directories
    assert _policy_for_file(foundry_root / "plugins" / "dashboard.py", foundry_root) == "infra"
    assert _policy_for_file(foundry_root / "runtime" / "__init__.py", foundry_root) == "infra"
    assert _policy_for_file(foundry_root / "agent_sim" / "core.py", foundry_root) == "infra"
    assert _policy_for_file(foundry_root / "methods" / "testing" / "helpers.py", foundry_root) == "infra"
    assert _policy_for_file(foundry_root / "methods" / "cli" / "runner.py", foundry_root) == "infra"
    # Individual files
    assert _policy_for_file(foundry_root / "agents.py", foundry_root) == "infra"
    assert _policy_for_file(foundry_root / "quickstart.py", foundry_root) == "infra"
    assert _policy_for_file(foundry_root / "methods" / "base.py", foundry_root) == "infra"
    assert _policy_for_file(foundry_root / "methods" / "hot_reload.py", foundry_root) == "infra"
    assert _policy_for_file(foundry_root / "methods" / "cache.py", foundry_root) == "infra"
    assert _policy_for_file(foundry_root / "methods" / "composer.py", foundry_root) == "infra"
    assert _policy_for_file(foundry_root / "methods" / "backends" / "checkpointing.py", foundry_root) == "infra"
    assert _policy_for_file(foundry_root / "methods" / "backends" / "ray_runner.py", foundry_root) == "infra"


def test_no_jax_zone_for_causal(foundry_root: Path) -> None:
    """Causal catalog files get 'no_jax' (mixed minus JAX family)."""
    assert _policy_for_file(foundry_root / "methods" / "catalog" / "causal" / "tmle_core.py", foundry_root) == "no_jax"
    assert _policy_for_file(foundry_root / "methods" / "catalog" / "causal" / "transport" / "ot.py", foundry_root) == "no_jax"
    assert _policy_for_file(foundry_root / "methods" / "catalog" / "econometrics" / "iv.py", foundry_root) == "no_jax"
    assert _policy_for_file(foundry_root / "methods" / "catalog" / "optimization" / "linprog.py", foundry_root) == "no_jax"


def test_no_jax_allowlist_override(foundry_root: Path) -> None:
    """ci_backends.py gets 'mixed' despite being in causal/ (allowlist override)."""
    f = foundry_root / "methods" / "catalog" / "causal" / "ci_backends.py"
    assert _policy_for_file(f, foundry_root) == "mixed"


def test_zone_map_values_valid() -> None:
    """All ZONE_MAP values must be recognized zone strings."""
    valid_zones = {"standard", "infra", "mixed", "no_jax"}
    for prefix, zone in ZONE_MAP.items():
        assert zone in valid_zones, f"Invalid zone '{zone}' for prefix '{prefix}'"


def test_default_zone_is_standard() -> None:
    """Unknown paths should fall back to standard (strictest)."""
    assert DEFAULT_ZONE == "standard"


def test_sorted_entries_longest_first() -> None:
    """Zone entries must be sorted longest-prefix-first for correct matching."""
    entries = _sorted_zone_entries()
    lengths = [len(prefix) for prefix, _ in entries]
    assert lengths == sorted(lengths, reverse=True)


def test_unknown_file_gets_standard(foundry_root: Path) -> None:
    """A file not matching any ZONE_MAP prefix gets standard policy."""
    unknown = foundry_root / "some_new_module.py"
    unknown.touch()
    assert _policy_for_file(unknown, foundry_root) == "standard"


def test_file_outside_foundry_root() -> None:
    """A file outside foundry_root gets standard policy."""
    assert _policy_for_file(Path("/tmp/random.py"), Path("/opt/foundry")) == "standard"
