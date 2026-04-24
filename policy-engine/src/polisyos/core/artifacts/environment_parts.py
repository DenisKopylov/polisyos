"""Environment module facade composed from focused sub-modules."""

from __future__ import annotations

import subprocess

from ._env_capture import capture_environment
from ._env_comparison import compare_environments
from ._env_models import (
    ContainerInfo,
    CPUInfo,
    DependencyInfo,
    EnvironmentDiff,
    EnvironmentManifest,
    EnvironmentManifestRef,
    GitInfo,
    GPUInfo,
    JAXInfo,
    OSInfo,
    PythonInfo,
    RiskLevel,
    SystemLibraryInfo,
    TEEInfo,
)
from ._env_utils import (
    DEFAULT_COMMAND_TIMEOUT,
    MAX_LIBRARY_BYTES,
    SYSTEM_LIBRARY_NAMES,
)

__all__ = [
    "DEFAULT_COMMAND_TIMEOUT",
    "MAX_LIBRARY_BYTES",
    "SYSTEM_LIBRARY_NAMES",
    "CPUInfo",
    "ContainerInfo",
    "DependencyInfo",
    "EnvironmentDiff",
    "EnvironmentManifest",
    "EnvironmentManifestRef",
    "GPUInfo",
    "GitInfo",
    "JAXInfo",
    "OSInfo",
    "PythonInfo",
    "RiskLevel",
    "SystemLibraryInfo",
    "TEEInfo",
    "capture_environment",
    "compare_environments",
    "subprocess",
]
