#!/usr/bin/env python3
"""Shared helpers for repo-local workspace commands."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tools._lib.imports import repo_root_from
from typing import Mapping, Sequence

PRODUCT_ROOT = repo_root_from(__file__)
FRONTEND_ROOT = PRODUCT_ROOT / "frontend" / "runtime-dashboard"
PYTHON_BASELINE = "3.14"
NODE_BASELINE = "22"
UV_BASELINE = "0.9.21"
UV_SYNC_PROFILES: dict[str, tuple[str, ...]] = {
    "minimal": ("lint", "test"),
    "docs": ("lint", "docs"),
    "runtime": ("lint", "test", "runtime"),
    "research": ("lint", "test", "runtime", "research"),
}
DEFAULT_UV_SYNC_PROFILE = "runtime"

OPTIONAL_SURFACES: dict[str, dict[str, object]] = {
    "llm-openai": {
        "description": "OpenAI-backed Lex and LLM workflows",
        "requirements": (("OPENAI_API_KEY",),),
    },
    "llm-anthropic": {
        "description": "Anthropic-backed LLM workflows",
        "requirements": (("ANTHROPIC_API_KEY",),),
    },
    "runtime-research-postgres": {
        "description": "Durable research control plane",
        "requirements": (("POLISYOS_CONTROL_POSTGRES_DSN",),),
    },
    "runtime-oidc": {
        "description": "Runtime JWT/OIDC validation",
        "requirements": (("POLISYOS_KEYCLOAK_ISSUER_URL", "POLISYOS_KEYCLOAK_JWKS_URI"),),
    },
    "runtime-signing": {
        "description": "Artifact signing and verification",
        "requirements": (
            ("POLISYOS_SIGNING_KEY",),
            ("POLISYOS_SIGNING_KEY_FILE",),
        ),
    },
    "datasets-unpd": {
        "description": "UNPD dataset ingest",
        "requirements": (("POLISYOS_UNPD_API_TOKEN",),),
    },
    "frontend-sentry-runtime": {
        "description": "Browser-side Sentry instrumentation",
        "requirements": (("VITE_SENTRY_DSN",),),
    },
    "frontend-sentry-build": {
        "description": "Frontend sourcemap upload and release attribution",
        "requirements": (("SENTRY_AUTH_TOKEN", "SENTRY_ORG", "SENTRY_PROJECT"),),
    },
}


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """Command invocation metadata."""

    label: str
    argv: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str] | None = None


def version_text(command: Sequence[str], *, cwd: Path = PRODUCT_ROOT) -> str:
    """Return stdout for a version-like command or raise on failure."""

    completed = subprocess.run(
        list(command),
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return (completed.stdout or completed.stderr).strip()


def run_command(spec: CommandSpec) -> None:
    """Run a command with inherited stdio."""

    print(f"[run] {spec.label}")
    env = None
    if spec.env:
        env = {**os.environ, **spec.env}
    subprocess.run(list(spec.argv), cwd=spec.cwd, check=True, env=env)


def is_env_set(name: str, environ: Mapping[str, str] | None = None) -> bool:
    """Return whether an environment variable is non-empty."""

    env = os.environ if environ is None else environ
    return bool(str(env.get(name, "")).strip())


def parse_major_version(raw: str) -> int | None:
    """Extract the major component from a version string like `v22.11.0`."""

    match = re.search(r"(\d+)", raw)
    if match is None:
        return None
    return int(match.group(1))


def parse_semver(raw: str) -> tuple[int, int, int] | None:
    """Extract a semantic version triple from tool output like `uv 0.9.21`."""

    match = re.search(r"(\d+)\.(\d+)\.(\d+)", raw)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def python_baseline_matches(version_info: tuple[int, int, int]) -> bool:
    """Return whether the interpreter matches the supported baseline minor."""

    return version_info[:2] == (3, 14)


def node_baseline_matches(raw: str) -> bool:
    """Return whether a Node version string matches the supported major."""

    return parse_major_version(raw) == int(NODE_BASELINE)


def uv_baseline_matches(raw: str) -> bool:
    """Return whether a uv version string matches the pinned workspace baseline."""

    parsed = parse_semver(raw)
    expected = tuple(int(part) for part in UV_BASELINE.split("."))
    return parsed == expected


def user_local_uv_path() -> Path:
    """Return the preferred user-local uv install path."""

    return Path.home() / ".local" / "bin" / "uv"


def baseline_uv_binary() -> str | None:
    """Return a uv binary matching the pinned baseline, if one is available."""

    candidates: list[str] = []
    path_uv = shutil.which("uv")
    if path_uv:
        candidates.append(path_uv)

    local_uv = user_local_uv_path()
    if local_uv.exists():
        rendered = str(local_uv)
        if rendered not in candidates:
            candidates.append(rendered)

    for binary in candidates:
        try:
            reported = version_text((binary, "--version"))
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        if uv_baseline_matches(reported):
            return binary

    return None


def surface_status(
    surface: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> tuple[bool, str]:
    """Evaluate one optional surface against the provided environment mapping."""

    env = os.environ if environ is None else environ
    if surface not in OPTIONAL_SURFACES:
        raise KeyError(surface)

    requirements = OPTIONAL_SURFACES[surface]["requirements"]
    assert isinstance(requirements, tuple)

    for group in requirements:
        if all(is_env_set(name, env) for name in group):
            joined = ", ".join(group)
            return True, f"{surface}: ready via {joined}"

    alternatives = [" + ".join(group) for group in requirements]
    return False, f"{surface}: missing one of {' OR '.join(alternatives)}"


def uv_command() -> tuple[str, ...]:
    """Resolve the `uv` invocation currently available on this machine."""

    binary = baseline_uv_binary()
    if binary:
        return (binary,)

    binary = shutil.which("uv")
    if binary:
        return (binary,)
    return (sys.executable, "-m", "uv")
