import os
import sys
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

try:
    from loguru import logger  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import logging

    class _LoggerShim:
        def remove(self) -> None:
            return None

        def add(self, _sink, level: str = "ERROR") -> None:
            logging.basicConfig(level=getattr(logging, level, logging.ERROR))

    logger = _LoggerShim()

# Ensure `policy-engine/src` is on sys.path so imports like `import polisyos...` work under pytest.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
TESTS_ROOT = Path(__file__).resolve().parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

pytest_plugins = (
    "_helpers.artifacts",
    "_helpers.observability",
)

QUARANTINE_REGISTRY = TESTS_ROOT / "quarantine.toml"
PRIMARY_TAXONOMY_MARKERS = (
    "unit",
    "contract",
    "property",
    "integration",
    "performance",
    "repo_quality",
)


@dataclass(frozen=True)
class QuarantineEntry:
    runner: str
    selector: str
    owner: str
    expires_on: date
    reason: str
    reentry_criteria: str


def _load_quarantine_entries() -> tuple[dict[str, QuarantineEntry], list[QuarantineEntry]]:
    if not QUARANTINE_REGISTRY.exists():
        return {}, []

    payload = tomllib.loads(QUARANTINE_REGISTRY.read_text("utf-8"))
    pytest_entries: dict[str, QuarantineEntry] = {}
    expired_entries: list[QuarantineEntry] = []

    for raw_entry in payload.get("case", []):
        entry = QuarantineEntry(
            runner=str(raw_entry["runner"]),
            selector=str(raw_entry["selector"]),
            owner=str(raw_entry["owner"]),
            expires_on=date.fromisoformat(str(raw_entry["expires_on"])),
            reason=str(raw_entry["reason"]),
            reentry_criteria=str(raw_entry["reentry_criteria"]),
        )
        if entry.expires_on < date.today():
            expired_entries.append(entry)
        if entry.runner == "pytest":
            pytest_entries[entry.selector] = entry

    return pytest_entries, expired_entries


def _path_startswith(item: pytest.Item, relative_path: str) -> bool:
    return str(item.path.as_posix()).startswith(str((PROJECT_ROOT / relative_path).as_posix()))


def _infer_primary_marker(item: pytest.Item) -> str:
    existing_primary = next(
        (marker for marker in PRIMARY_TAXONOMY_MARKERS if item.get_closest_marker(marker)),
        None,
    )
    if existing_primary:
        return existing_primary

    file_name = item.path.name.lower()

    if _path_startswith(item, "tests/contract"):
        return "contract"
    if _path_startswith(item, "tests/repo_quality"):
        return "repo_quality"
    if item.get_closest_marker("benchmark") or _path_startswith(item, "tests/performance"):
        return "performance"
    if (
        _path_startswith(item, "tests/integration")
        or _path_startswith(item, "tests/unit/runtime/http")
        or _path_startswith(item, "tests/unit/fabric/connectors/reference")
        or item.get_closest_marker("integration")
    ):
        return "integration"
    if (
        item.get_closest_marker("property")
        or file_name.endswith("_properties.py")
        or "_property_" in file_name
        or file_name.startswith("test_property_")
    ):
        return "property"
    return "unit"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-quarantine",
        action="store_true",
        default=False,
        help="include tests listed in tests/quarantine.toml instead of skipping them",
    )


def pytest_configure(config: pytest.Config) -> None:
    quarantine_entries, expired_entries = _load_quarantine_entries()
    config._polisyos_quarantine_entries = quarantine_entries  # type: ignore[attr-defined]
    config._polisyos_expired_quarantines = expired_entries  # type: ignore[attr-defined]
    _configure_hypothesis_cache()


def _configure_hypothesis_cache() -> None:
    try:
        from hypothesis import settings
        from hypothesis.database import DirectoryBasedExampleDatabase
    except ModuleNotFoundError:
        return

    hypothesis_cache = PROJECT_ROOT / "_cache" / "hypothesis"
    hypothesis_cache.mkdir(parents=True, exist_ok=True)
    settings.register_profile(
        "polisyos",
        database=DirectoryBasedExampleDatabase(str(hypothesis_cache)),
    )
    settings.load_profile("polisyos")


def pytest_report_header(config: pytest.Config) -> list[str]:
    quarantine_entries: dict[str, QuarantineEntry] = getattr(
        config,
        "_polisyos_quarantine_entries",
        {},
    )
    expired_entries: list[QuarantineEntry] = getattr(
        config,
        "_polisyos_expired_quarantines",
        [],
    )
    lines = [f"test taxonomy enabled; active pytest quarantines={len(quarantine_entries)}"]
    if expired_entries:
        lines.append(
            "expired quarantines: "
            + ", ".join(
                f"{entry.selector} (owner={entry.owner}, expires={entry.expires_on})"
                for entry in expired_entries
            )
        )
    return lines


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    quarantine_entries: dict[str, QuarantineEntry] = getattr(
        config,
        "_polisyos_quarantine_entries",
        {},
    )
    include_quarantine = bool(config.getoption("--run-quarantine"))

    for item in items:
        primary_marker = _infer_primary_marker(item)
        item.add_marker(getattr(pytest.mark, primary_marker))

        nodeid_lower = item.nodeid.lower()
        if "smoke" in nodeid_lower or _path_startswith(item, "tests/e2e/demos"):
            item.add_marker(pytest.mark.smoke)
        if (
            primary_marker in {"integration", "performance"}
            or "slow" in nodeid_lower
            or item.get_closest_marker("benchmark")
        ):
            item.add_marker(pytest.mark.slow)

        quarantine_entry = quarantine_entries.get(item.nodeid)
        if quarantine_entry is not None:
            item.add_marker(pytest.mark.quarantine)
            item.add_marker(pytest.mark.flaky)
            item.user_properties.append(("quarantine_owner", quarantine_entry.owner))
            item.user_properties.append(
                ("quarantine_expires_on", quarantine_entry.expires_on.isoformat())
            )
            if not include_quarantine:
                item.add_marker(
                    pytest.mark.skip(
                        reason=(
                            "quarantined until "
                            f"{quarantine_entry.expires_on} "
                            f"(owner={quarantine_entry.owner}): {quarantine_entry.reason}"
                        )
                    )
                )


def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> None:
    """Clean direct runtime API helper envs without importing the heavy helper eagerly."""
    del item, nextitem
    runtime_http = sys.modules.get("_helpers.runtime_http")
    cleanup = getattr(runtime_http, "close_registered_runtime_api_envs", None)
    if callable(cleanup):
        cleanup()


# --- FORCE SETTINGS FOR TESTS ---
# Эти настройки должны сработать до любых других импортов в тестах

# 1. Жестко запрещаем аллокацию памяти
os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"

# 2. Для тестов всегда форсируем CPU (даже если есть GPU),
# чтобы избежать конфликтов драйверов в CI/CD
# JAX 0.4+ предпочитает JAX_PLATFORMS; JAX_PLATFORM_NAME оставляем для совместимости.
os.environ["JAX_PLATFORMS"] = "cpu"
os.environ["JAX_PLATFORM_NAME"] = "cpu"


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Настройка окружения перед запуском всех тестов."""

    # Убираем лишний шум логов, оставляем только ошибки
    logger.remove()
    logger.add(lambda msg: print(msg), level="ERROR")

    return
