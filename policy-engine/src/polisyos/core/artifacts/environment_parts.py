"""Environment module facade composed from focused sub-modules."""

from __future__ import annotations

import subprocess

from ._env_capture import capture_environment
from ._env_comparison import compare_environments
from ._env_models import (
    CPUInfo,
    ContainerInfo,
    DependencyInfo,
    EnvironmentDiff,
    EnvironmentManifest,
    EnvironmentManifestRef,
    GPUInfo,
    GitInfo,
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
    "CPUInfo",
    "ContainerInfo",
    "DEFAULT_COMMAND_TIMEOUT",
    "DependencyInfo",
    "EnvironmentDiff",
    "EnvironmentManifest",
    "EnvironmentManifestRef",
    "GPUInfo",
    "GitInfo",
    "JAXInfo",
    "MAX_LIBRARY_BYTES",
    "OSInfo",
    "PythonInfo",
    "RiskLevel",
    "SYSTEM_LIBRARY_NAMES",
    "SystemLibraryInfo",
    "TEEInfo",
    "capture_environment",
    "compare_environments",
    "subprocess",
]
