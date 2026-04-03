"""Public backends runtime fingerprint module API."""
from __future__ import annotations

from importlib import metadata


_PACKAGE_ALIASES = {
    "sklearn": "scikit-learn",
}


def safe_version(package_name: str) -> str | None:
    """Safe version helper."""
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def runtime_stack_for(method_class: type) -> tuple[str, ...]:
    """Runtime stack for helper."""
    runtime_stack = getattr(method_class, "runtime_stack", ())
    if isinstance(runtime_stack, str):
        runtime_stack = (runtime_stack,)
    if isinstance(runtime_stack, (list, tuple, set, frozenset)):
        values = [str(item).strip() for item in runtime_stack if str(item).strip()]
        return tuple(dict.fromkeys(values))
    return ()


def capture_versions(
    *,
    base_packages: tuple[str, ...],
    runtime_stack: tuple[str, ...],
) -> dict[str, str]:
    """Capture versions helper."""
    versions: dict[str, str] = {}
    packages = list(base_packages)
    for item in runtime_stack:
        packages.append(_PACKAGE_ALIASES.get(item, item))
    for package_name in dict.fromkeys(packages):
        version = safe_version(package_name)
        if version:
            versions[package_name] = version
    return versions


__all__ = ["capture_versions", "runtime_stack_for", "safe_version"]
