"""Environment manifest schema and capture logic for reproducibility."""

from __future__ import annotations

import hashlib
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from enum import Enum
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from .manifest import ArtifactRef


DEFAULT_COMMAND_TIMEOUT = 1.5
MAX_LIBRARY_BYTES = 64 * 1024 * 1024
SYSTEM_LIBRARY_NAMES = (
    "libcuda.so",
    "libcudnn.so",
    "libcublas.so",
    "libcublasLt.so",
    "libcudart.so",
)


class RiskLevel(str, Enum):
    """Risk level for environment differences."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class CPUInfo(BaseModel):
    """CPU hardware information."""

    model_config = ConfigDict(extra="ignore")

    architecture: str = Field(..., description="CPU architecture (x86_64, arm64)")
    model_name: str = Field(..., description="CPU model name")
    core_count: int = Field(..., ge=1, description="Number of physical cores")
    thread_count: int = Field(..., ge=1, description="Number of logical threads")

    has_avx: bool = Field(default=False, description="AVX support")
    has_avx2: bool = Field(default=False, description="AVX2 support")
    has_avx512: bool = Field(default=False, description="AVX-512 support")
    has_amx: bool = Field(default=False, description="AMX (Advanced Matrix Extensions)")
    has_neon: bool = Field(default=False, description="ARM NEON support")

    @computed_field
    @property
    def fingerprint(self) -> str:
        """Generate fingerprint for CPU capabilities."""
        flags = (
            f"{self.architecture}:{self.has_avx}:{self.has_avx2}:"
            f"{self.has_avx512}:{self.has_amx}:{self.has_neon}"
        )
        return hashlib.sha256(flags.encode()).hexdigest()[:16]


class GPUInfo(BaseModel):
    """GPU hardware information."""

    model_config = ConfigDict(extra="forbid")

    available: bool = Field(default=False, description="Whether GPU is available")
    device_count: int = Field(default=0, ge=0, description="Number of GPU devices")
    model_name: str | None = Field(default=None, description="GPU model name")
    device_names: list[str] = Field(default_factory=list, description="GPU device names")
    device_uuids: list[str] = Field(default_factory=list, description="GPU device UUIDs")
    memory_gb: float | None = Field(default=None, ge=0, description="GPU memory in GB")

    cuda_version: str | None = Field(default=None, description="CUDA toolkit version")
    cuda_driver_version: str | None = Field(default=None, description="CUDA driver version")
    cudnn_version: str | None = Field(default=None, description="cuDNN version")
    topology: str | None = Field(default=None, description="GPU topology summary")

    metal_available: bool = Field(default=False, description="Metal API available")
    metal_device_name: str | None = Field(default=None, description="Metal device name")


class OSInfo(BaseModel):
    """Operating system information."""

    model_config = ConfigDict(extra="forbid")

    system: str = Field(..., description="OS name (Linux, Darwin, Windows)")
    release: str = Field(..., description="OS release version")
    version: str = Field(..., description="OS version string")
    kernel_version: str | None = Field(default=None, description="Kernel version")
    libc_version: str | None = Field(default=None, description="libc version (glibc)")


class PythonInfo(BaseModel):
    """Python runtime information."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(..., description="Python version (e.g., 3.11.5)")
    implementation: str = Field(..., description="Python implementation (CPython)")
    compiler: str = Field(..., description="Compiler used to build Python")
    executable_hash: str | None = Field(default=None, description="Hash of Python executable")


class JAXInfo(BaseModel):
    """JAX/XLA runtime information."""

    model_config = ConfigDict(extra="forbid")

    jax_version: str | None = Field(default=None, description="JAX version")
    jaxlib_version: str | None = Field(default=None, description="jaxlib version")
    xla_version: str | None = Field(default=None, description="XLA version hash")

    default_backend: str | None = Field(default=None, description="Default JAX backend")
    available_backends: list[str] = Field(default_factory=list, description="Available backends")
    device_count: int = Field(default=0, ge=0, description="Number of JAX devices")

    xla_flags: dict[str, str] = Field(default_factory=dict, description="Active XLA flags")

    deterministic_ops_enabled: bool = Field(default=False, description="XLA deterministic ops")
    x64_enabled: bool = Field(default=False, description="64-bit precision enabled")


class GitInfo(BaseModel):
    """Git repository information."""

    model_config = ConfigDict(extra="forbid")

    commit_sha: str = Field(..., min_length=7, max_length=40, description="Git commit SHA")
    commit_short: str = Field(..., min_length=7, max_length=8, description="Short commit SHA")
    branch: str | None = Field(default=None, description="Current branch name")
    dirty: bool = Field(default=False, description="Working directory has uncommitted changes")
    tags: list[str] = Field(default_factory=list, description="Tags pointing to commit")


class DependencyInfo(BaseModel):
    """Dependency lockfile information."""

    model_config = ConfigDict(extra="forbid")

    lockfile_path: str = Field(..., description="Path to lockfile (uv.lock)")
    lockfile_hash: str = Field(..., description="SHA256 hash of lockfile content")
    lockfile_modified: datetime | None = Field(default=None, description="Last modification time")

    key_packages: dict[str, str] = Field(
        default_factory=dict,
        description="Versions of critical packages (jax, equinox, etc.)",
    )


class ContainerInfo(BaseModel):
    """Container/Docker information."""

    model_config = ConfigDict(extra="forbid")

    in_container: bool = Field(default=False, description="Running inside container")
    docker_image_sha: str | None = Field(default=None, description="Docker image SHA256")
    docker_image_tag: str | None = Field(default=None, description="Docker image tag")
    container_runtime: str | None = Field(default=None, description="Container runtime (docker, podman)")


class SystemLibraryInfo(BaseModel):
    """System library fingerprint."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(..., description="Library filename (basename only)")
    sha256: str | None = Field(default=None, description="SHA256 hash of library content")
    size_bytes: int | None = Field(default=None, ge=0, description="Size in bytes")
    modified_at: datetime | None = Field(default=None, description="Last modification time")


class EnvironmentDiff(BaseModel):
    """Difference between two environment manifests."""

    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(..., description="Dot-notation path to differing field")
    field_name: str = Field(..., description="Human-readable field name")
    value_a: Any = Field(..., description="Value in first manifest")
    value_b: Any = Field(..., description="Value in second manifest")
    risk_level: RiskLevel = Field(..., description="Risk level of this difference")
    explanation: str = Field(..., description="Human-readable explanation")


class EnvironmentManifest(BaseModel):
    """
    Complete environment fingerprint for reproducible simulations.

    Captures all factors that can affect simulation results:
    - Hardware (CPU architecture, instruction sets, GPU)
    - Software (OS, Python, drivers)
    - Runtimes (JAX, XLA, CUDA)
    - Code/Config (Git commit, lockfile hash, Docker image)
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of capture",
    )

    cpu: CPUInfo
    gpu: GPUInfo

    os: OSInfo
    python: PythonInfo

    jax: JAXInfo

    git: GitInfo | None = None
    dependencies: DependencyInfo | None = None
    container: ContainerInfo | None = None
    system_libraries: dict[str, SystemLibraryInfo] = Field(
        default_factory=dict,
        description="Hashes of key system libraries",
    )
    expected_precision_loss: str | None = Field(
        default=None,
        description="Hint for cross-platform numeric drift",
    )

    custom_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional custom metadata",
    )

    @computed_field
    @property
    def fingerprint(self) -> str:
        """
        Generate a compact fingerprint for quick equality checks.
        Includes only fields that affect reproducibility.
        """
        lib_fingerprint = _fingerprint_system_libraries(self.system_libraries)
        xla_flags = _format_xla_flags(self.jax.xla_flags)
        critical_fields = [
            self.cpu.fingerprint,
            self.gpu.cuda_version or "no-cuda",
            self.gpu.cuda_driver_version or "no-cuda-driver",
            self.gpu.cudnn_version or "no-cudnn",
            self.python.version,
            self.jax.jax_version or "no-jax",
            self.jax.jaxlib_version or "no-jaxlib",
            self.jax.xla_version or "no-xla",
            xla_flags or "no-xla-flags",
            str(self.jax.deterministic_ops_enabled),
            str(self.jax.x64_enabled),
            self.dependencies.lockfile_hash if self.dependencies else "no-lock",
            self.git.commit_sha if self.git else "no-git",
            lib_fingerprint or "no-system-libs",
        ]
        combined = "|".join(critical_fields)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def compatibility_score(self, other: "EnvironmentManifest") -> float:
        """
        Calculate compatibility score between two environments.

        Returns:
            float: 1.0 = identical, 0.0 = completely incompatible
        """
        if self.fingerprint == other.fingerprint:
            return 1.0

        diffs = compare_environments(self, other)
        if not diffs:
            return 1.0

        risk_weights = {
            RiskLevel.CRITICAL: 0.0,
            RiskLevel.HIGH: 0.3,
            RiskLevel.MEDIUM: 0.7,
            RiskLevel.LOW: 0.9,
            RiskLevel.INFO: 1.0,
        }
        worst_risk = min(diffs, key=lambda diff: _risk_order(diff.risk_level)).risk_level
        return risk_weights[worst_risk]


class EnvironmentManifestRef(ArtifactRef):
    """Typed reference to EnvironmentManifest artifact."""

    kind: Literal["foundry.environment_manifest"] = "foundry.environment_manifest"
    media_type: Literal["application/json"] = "application/json"


def _safe_run(cmd: list[str], timeout: float = DEFAULT_COMMAND_TIMEOUT) -> str | None:
    """
    Safely execute a system command with timeout.

    Returns None if command fails or is not available.
    Never raises exceptions.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _safe_package_version(package: str) -> str | None:
    """Safely get installed package version."""
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def _hash_file(path: Path, *, max_bytes: int | None = None) -> str | None:
    """Compute SHA256 hash of a file."""
    if not path.exists():
        return None
    try:
        if max_bytes is not None:
            size = path.stat().st_size
            if size > max_bytes:
                return None
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (IOError, OSError):
        return None


def _capture_cpu_info() -> CPUInfo:
    """Capture CPU information cross-platform."""
    arch = platform.machine() or "unknown"
    model_name = "Unknown"
    core_count = os.cpu_count() or 1
    thread_count = core_count

    has_avx = has_avx2 = has_avx512 = has_amx = has_neon = False

    if sys.platform == "linux":
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                cpuinfo = f.read()

            match = re.search(r"model name\\s*:\\s*(.+)", cpuinfo)
            if match:
                model_name = match.group(1).strip()

            flags_match = re.search(r"flags\\s*:\\s*(.+)", cpuinfo)
            if flags_match:
                flags = flags_match.group(1).lower()
                has_avx = " avx " in f" {flags} "
                has_avx2 = " avx2 " in f" {flags} "
                has_avx512 = "avx512" in flags
                has_amx = " amx" in flags

            features_match = re.search(r"features\\s*:\\s*(.+)", cpuinfo, re.IGNORECASE)
            if features_match:
                features = features_match.group(1).lower()
                has_neon = " neon" in f" {features} "

            core_pairs = set()
            phys_id = core_id = None
            for line in cpuinfo.splitlines():
                if line.startswith("physical id"):
                    phys_id = line.split(":", 1)[1].strip()
                elif line.startswith("core id"):
                    core_id = line.split(":", 1)[1].strip()
                elif not line.strip() and phys_id is not None and core_id is not None:
                    core_pairs.add((phys_id, core_id))
                    phys_id = core_id = None
            if phys_id is not None and core_id is not None:
                core_pairs.add((phys_id, core_id))
            if core_pairs:
                core_count = len(core_pairs)
        except (IOError, OSError):
            pass

    elif sys.platform == "darwin":
        model_name = (
            _safe_run(["sysctl", "-n", "machdep.cpu.brand_string"])
            or _safe_run(["sysctl", "-n", "hw.model"])
            or "Unknown"
        )
        physical = _safe_run(["sysctl", "-n", "hw.physicalcpu"])
        logical = _safe_run(["sysctl", "-n", "hw.logicalcpu"])
        if physical and physical.isdigit():
            core_count = max(1, int(physical))
        if logical and logical.isdigit():
            thread_count = max(1, int(logical))

        if arch == "arm64":
            has_neon = True
        else:
            features = _safe_run(["sysctl", "-n", "machdep.cpu.features"]) or ""
            features_lower = features.lower()
            has_avx = "avx" in features_lower
            has_avx2 = "avx2" in features_lower

            leaf7 = _safe_run(["sysctl", "-n", "machdep.cpu.leaf7_features"]) or ""
            has_avx512 = "avx512" in leaf7.lower()

    return CPUInfo(
        architecture=arch,
        model_name=model_name,
        core_count=max(1, core_count),
        thread_count=max(1, thread_count),
        has_avx=has_avx,
        has_avx2=has_avx2,
        has_avx512=has_avx512,
        has_amx=has_amx,
        has_neon=has_neon,
    )


def _capture_gpu_info() -> GPUInfo:
    """
    Capture GPU information with graceful degradation.

    Handles:
    - NVIDIA GPUs via nvidia-smi
    - Apple Silicon Metal via system_profiler
    - No GPU available
    """
    gpu_info = GPUInfo()

    nvidia_smi = _safe_run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version,uuid",
            "--format=csv,noheader,nounits",
        ]
    )
    if nvidia_smi:
        lines = [line.strip() for line in nvidia_smi.splitlines() if line.strip()]
        device_names: list[str] = []
        device_uuids: list[str] = []
        for line in lines:
            parts = [part.strip() for part in line.split(",")]
            if parts:
                device_names.append(parts[0])
                if gpu_info.model_name is None:
                    gpu_info.model_name = parts[0]
            if len(parts) > 1 and gpu_info.memory_gb is None:
                try:
                    gpu_info.memory_gb = float(parts[1]) / 1024
                except ValueError:
                    pass
            if len(parts) > 2 and gpu_info.cuda_driver_version is None:
                gpu_info.cuda_driver_version = parts[2]
            if len(parts) > 3:
                device_uuids.append(parts[3])

        gpu_info.available = True
        gpu_info.device_count = len(lines)
        gpu_info.device_names = device_names
        gpu_info.device_uuids = device_uuids

        if gpu_info.device_count > 1:
            gpu_info.topology = _safe_run(["nvidia-smi", "topo", "-m"])

        nvcc_output = _safe_run(["nvcc", "--version"])
        if nvcc_output:
            match = re.search(r"release (\\d+\\.\\d+)", nvcc_output)
            if match:
                gpu_info.cuda_version = match.group(1)

        cudnn_version = _get_cudnn_version()
        if cudnn_version:
            gpu_info.cudnn_version = cudnn_version

    if sys.platform == "darwin":
        sp_output = _safe_run(["system_profiler", "SPDisplaysDataType", "-json"])
        if sp_output:
            import json

            try:
                data = json.loads(sp_output)
                displays = data.get("SPDisplaysDataType", [])
                for display in displays:
                    model = display.get("sppci_model") or display.get("spdisplays_model")
                    if model:
                        gpu_info.metal_available = True
                        gpu_info.metal_device_name = model
                        if not gpu_info.available:
                            gpu_info.available = True
                            gpu_info.device_count = 1
                            gpu_info.model_name = model
                            gpu_info.device_names = [model]
                        break
            except (json.JSONDecodeError, KeyError):
                pass

    return gpu_info


def _get_cudnn_version() -> str | None:
    """Extract cuDNN version from header or library."""
    cudnn_paths = [
        "/usr/include/cudnn_version.h",
        "/usr/local/cuda/include/cudnn_version.h",
        "/usr/include/x86_64-linux-gnu/cudnn_version.h",
    ]

    for path in cudnn_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            major = re.search(r"CUDNN_MAJOR\\s+(\\d+)", content)
            minor = re.search(r"CUDNN_MINOR\\s+(\\d+)", content)
            patch = re.search(r"CUDNN_PATCHLEVEL\\s+(\\d+)", content)
            if major and minor and patch:
                return f"{major.group(1)}.{minor.group(1)}.{patch.group(1)}"
        except (IOError, OSError):
            continue

    return None


def _capture_os_info() -> OSInfo:
    """Capture OS information."""
    kernel_version = None
    libc_version = None

    if sys.platform == "linux":
        kernel_version = _safe_run(["uname", "-r"])
        ldd_output = _safe_run(["ldd", "--version"])
        if ldd_output:
            match = re.search(r"(\\d+\\.\\d+)", ldd_output)
            if match:
                libc_version = f"glibc-{match.group(1)}"
    elif sys.platform == "darwin":
        kernel_version = _safe_run(["uname", "-r"])

    return OSInfo(
        system=platform.system(),
        release=platform.release(),
        version=platform.version(),
        kernel_version=kernel_version,
        libc_version=libc_version,
    )


def _capture_python_info() -> PythonInfo:
    """Capture Python runtime information."""
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    exe_hash = _hash_file(Path(sys.executable))

    return PythonInfo(
        version=version,
        implementation=platform.python_implementation(),
        compiler=platform.python_compiler(),
        executable_hash=exe_hash[:16] if exe_hash else None,
    )


def _capture_jax_info() -> JAXInfo:
    """
    Capture JAX/XLA runtime information.

    Must be called AFTER JAX is initialized to get accurate device info.
    """
    jax_info = JAXInfo()

    jax_info.jax_version = _safe_package_version("jax")
    jax_info.jaxlib_version = _safe_package_version("jaxlib")

    if jax_info.jax_version:
        try:
            import jax

            devices = jax.devices()
            jax_info.default_backend = jax.default_backend()
            jax_info.available_backends = sorted({device.platform for device in devices})
            jax_info.device_count = len(devices)

            xla_flags_env = os.environ.get("XLA_FLAGS", "")
            jax_info.xla_flags = _parse_xla_flags(xla_flags_env)

            jax_info.deterministic_ops_enabled = (
                "--xla_gpu_deterministic_ops=true" in xla_flags_env
            )
            jax_info.x64_enabled = bool(jax.config.x64_enabled)

            try:
                from jax._src import lib as jaxlib_internal

                xla_version = getattr(jaxlib_internal, "xla_extension_version", None)
                if xla_version is not None:
                    jax_info.xla_version = str(xla_version)
            except (ImportError, AttributeError):
                pass
        except Exception:
            pass

    return jax_info


def _parse_xla_flags(flags_str: str) -> dict[str, str]:
    """Parse XLA_FLAGS environment variable into dict."""
    result: dict[str, str] = {}
    for flag in flags_str.split():
        if "=" in flag:
            key, value = flag.split("=", 1)
            result[key.lstrip("-")] = value
        elif flag.startswith("--"):
            result[flag.lstrip("-")] = "true"
    return result


def _capture_git_info(repo_path: Path | None = None) -> GitInfo | None:
    """Capture Git repository information."""
    if repo_path is None:
        repo_path = Path.cwd()

    git_dir = _safe_run(["git", "-C", str(repo_path), "rev-parse", "--git-dir"])
    if not git_dir:
        return None

    commit_sha = _safe_run(["git", "-C", str(repo_path), "rev-parse", "HEAD"])
    if not commit_sha:
        return None

    commit_short = commit_sha[:8]
    branch = _safe_run(["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"])

    status = _safe_run(["git", "-C", str(repo_path), "status", "--porcelain"])
    dirty = bool(status and status.strip())

    tags_output = _safe_run(["git", "-C", str(repo_path), "tag", "--points-at", commit_sha])
    tags = tags_output.split("\n") if tags_output else []
    tags = [tag.strip() for tag in tags if tag.strip()]

    return GitInfo(
        commit_sha=commit_sha,
        commit_short=commit_short,
        branch=branch,
        dirty=dirty,
        tags=tags,
    )


def _capture_dependency_info(project_root: Path | None = None) -> DependencyInfo | None:
    """
    Capture dependency lockfile information.

    Supports uv.lock (primary) with fallback to other lockfiles.
    """
    if project_root is None:
        project_root = Path.cwd()

    lockfile = project_root / "uv.lock"
    if not lockfile.exists():
        for alt in ["poetry.lock", "Pipfile.lock", "requirements.txt"]:
            alt_path = project_root / alt
            if alt_path.exists():
                lockfile = alt_path
                break
        else:
            return None

    lockfile_hash = _hash_file(lockfile)
    if not lockfile_hash:
        return None

    try:
        mtime = datetime.fromtimestamp(lockfile.stat().st_mtime, tz=timezone.utc)
    except (IOError, OSError):
        mtime = None

    key_packages: dict[str, str] = {}
    critical_pkgs = ["jax", "jaxlib", "equinox", "optax", "diffrax", "pydantic", "numpy"]
    for pkg in critical_pkgs:
        version = _safe_package_version(pkg)
        if version:
            key_packages[pkg] = version

    return DependencyInfo(
        lockfile_path=str(lockfile.relative_to(project_root)),
        lockfile_hash=f"sha256:{lockfile_hash}",
        lockfile_modified=mtime,
        key_packages=key_packages,
    )


def _capture_container_info() -> ContainerInfo:
    """Detect if running in a container and capture relevant info."""
    in_container = False
    docker_image_sha = None
    docker_image_tag = None
    container_runtime = None

    if Path("/.dockerenv").exists():
        in_container = True
        container_runtime = "docker"
    elif Path("/run/.containerenv").exists():
        in_container = True
        container_runtime = "podman"

    try:
        with open("/proc/1/cgroup", "r", encoding="utf-8") as f:
            cgroup = f.read()
        if "docker" in cgroup or "kubepods" in cgroup or "containerd" in cgroup:
            in_container = True
            if "docker" in cgroup:
                container_runtime = container_runtime or "docker"
    except (IOError, OSError):
        pass

    docker_image_sha = os.environ.get("DOCKER_IMAGE_SHA256")
    docker_image_tag = os.environ.get("DOCKER_IMAGE_TAG")

    return ContainerInfo(
        in_container=in_container,
        docker_image_sha=docker_image_sha,
        docker_image_tag=docker_image_tag,
        container_runtime=container_runtime,
    )


def _capture_system_libraries() -> dict[str, SystemLibraryInfo]:
    """Capture hashes of key system libraries."""
    if sys.platform != "linux":
        return {}

    cache = _ldconfig_cache()
    results: dict[str, SystemLibraryInfo] = {}
    for name in SYSTEM_LIBRARY_NAMES:
        path = _resolve_library_path(name, cache)
        if not path:
            continue
        info = _system_library_info(path)
        if info is not None:
            results[name] = info
    return results


def _ldconfig_cache() -> dict[str, str]:
    output = _safe_run(["ldconfig", "-p"])
    if not output:
        return {}
    cache: dict[str, str] = {}
    for line in output.splitlines():
        match = re.match(r"\\s*(\\S+)\\s+\\([^)]*\\)\\s+=>\\s+(\\S+)", line)
        if match:
            cache[match.group(1)] = match.group(2)
    return cache


def _resolve_library_path(name: str, cache: dict[str, str]) -> Path | None:
    for key in sorted(cache):
        if key.startswith(name):
            path = Path(cache[key])
            if path.exists():
                return path

    for directory in _candidate_library_dirs():
        base = Path(directory)
        candidate = base / name
        if candidate.exists():
            return candidate
        for match in sorted(base.glob(f"{name}*")):
            if match.is_file():
                return match
    return None


def _candidate_library_dirs() -> list[str]:
    env_dirs: list[str] = []
    for var in ("LD_LIBRARY_PATH", "LIBRARY_PATH"):
        value = os.environ.get(var)
        if value:
            env_dirs.extend([part for part in value.split(":") if part])

    default_dirs = [
        "/usr/lib",
        "/usr/lib64",
        "/usr/local/lib",
        "/usr/local/cuda/lib64",
        "/usr/lib/x86_64-linux-gnu",
        "/lib/x86_64-linux-gnu",
        "/lib64",
        "/lib",
    ]
    deduped = list(dict.fromkeys(env_dirs + default_dirs))
    return [path for path in deduped if path]


def _system_library_info(path: Path) -> SystemLibraryInfo | None:
    try:
        stat = path.stat()
    except (IOError, OSError):
        return None

    digest = _hash_file(path, max_bytes=MAX_LIBRARY_BYTES)
    modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    return SystemLibraryInfo(
        filename=path.name,
        sha256=digest,
        size_bytes=stat.st_size,
        modified_at=modified_at,
    )


def _estimate_precision_loss(cpu: CPUInfo, gpu: GPUInfo, jax_info: JAXInfo) -> str | None:
    arch = cpu.architecture.lower()
    if arch in {"arm64", "aarch64"}:
        return "arch_fma_variance"
    if jax_info.jax_version and gpu.available and not jax_info.deterministic_ops_enabled:
        return "gpu_nondeterministic"
    return None


def capture_environment(
    *,
    project_root: Path | str | None = None,
    include_git: bool = True,
    include_dependencies: bool = True,
    include_system_libraries: bool = True,
    custom_metadata: dict[str, Any] | None = None,
) -> EnvironmentManifest:
    """
    Capture complete environment manifest.

    Performance target: < 2 seconds total execution time.
    """
    root = Path(project_root) if project_root else None
    cpu_info = _capture_cpu_info()
    gpu_info = _capture_gpu_info()
    jax_info = _capture_jax_info()
    system_libs = _capture_system_libraries() if include_system_libraries else {}
    expected_precision_loss = _estimate_precision_loss(cpu_info, gpu_info, jax_info)

    return EnvironmentManifest(
        cpu=cpu_info,
        gpu=gpu_info,
        os=_capture_os_info(),
        python=_capture_python_info(),
        jax=jax_info,
        git=_capture_git_info(root) if include_git else None,
        dependencies=_capture_dependency_info(root) if include_dependencies else None,
        container=_capture_container_info(),
        system_libraries=system_libs,
        expected_precision_loss=expected_precision_loss,
        custom_metadata=custom_metadata or {},
    )


def compare_environments(a: EnvironmentManifest, b: EnvironmentManifest) -> list[EnvironmentDiff]:
    """
    Compare two environment manifests and return differences.

    Returns list of EnvironmentDiff ordered by risk level (critical first).
    """
    diffs: list[EnvironmentDiff] = []

    if a.cpu.architecture != b.cpu.architecture:
        diffs.append(
            EnvironmentDiff(
                field_path="cpu.architecture",
                field_name="CPU Architecture",
                value_a=a.cpu.architecture,
                value_b=b.cpu.architecture,
                risk_level=RiskLevel.CRITICAL,
                explanation=(
                    "Different CPU architectures will produce different floating-point results"
                ),
            )
        )

    for flag, name in [("has_avx512", "AVX-512"), ("has_avx2", "AVX2"), ("has_amx", "AMX")]:
        if getattr(a.cpu, flag) != getattr(b.cpu, flag):
            diffs.append(
                EnvironmentDiff(
                    field_path=f"cpu.{flag}",
                    field_name=f"CPU {name} Support",
                    value_a=getattr(a.cpu, flag),
                    value_b=getattr(b.cpu, flag),
                    risk_level=RiskLevel.HIGH,
                    explanation=(
                        f"{name} affects vectorized operations and may cause numerical differences"
                    ),
                )
            )

    if a.gpu.device_count != b.gpu.device_count:
        diffs.append(
            EnvironmentDiff(
                field_path="gpu.device_count",
                field_name="GPU Device Count",
                value_a=a.gpu.device_count,
                value_b=b.gpu.device_count,
                risk_level=RiskLevel.HIGH,
                explanation="Different GPU counts can change device assignment and parallelism",
            )
        )

    if a.gpu.model_name != b.gpu.model_name:
        diffs.append(
            EnvironmentDiff(
                field_path="gpu.model_name",
                field_name="GPU Model",
                value_a=a.gpu.model_name,
                value_b=b.gpu.model_name,
                risk_level=RiskLevel.MEDIUM,
                explanation="Different GPU models may produce different numerical behavior",
            )
        )

    uuids_a = set(a.gpu.device_uuids)
    uuids_b = set(b.gpu.device_uuids)
    if uuids_a or uuids_b:
        if uuids_a != uuids_b:
            diffs.append(
                EnvironmentDiff(
                    field_path="gpu.device_uuids",
                    field_name="GPU UUIDs",
                    value_a=sorted(uuids_a),
                    value_b=sorted(uuids_b),
                    risk_level=RiskLevel.HIGH,
                    explanation="GPU UUID changes indicate different physical devices",
                )
            )

    if a.gpu.cuda_version != b.gpu.cuda_version:
        diffs.append(
            EnvironmentDiff(
                field_path="gpu.cuda_version",
                field_name="CUDA Version",
                value_a=a.gpu.cuda_version,
                value_b=b.gpu.cuda_version,
                risk_level=RiskLevel.HIGH,
                explanation="Different CUDA versions have different kernel implementations",
            )
        )

    if a.gpu.cuda_driver_version != b.gpu.cuda_driver_version:
        diffs.append(
            EnvironmentDiff(
                field_path="gpu.cuda_driver_version",
                field_name="CUDA Driver Version",
                value_a=a.gpu.cuda_driver_version,
                value_b=b.gpu.cuda_driver_version,
                risk_level=RiskLevel.HIGH,
                explanation="Driver version affects GPU operation behavior",
            )
        )

    if a.gpu.cudnn_version != b.gpu.cudnn_version:
        diffs.append(
            EnvironmentDiff(
                field_path="gpu.cudnn_version",
                field_name="cuDNN Version",
                value_a=a.gpu.cudnn_version,
                value_b=b.gpu.cudnn_version,
                risk_level=RiskLevel.HIGH,
                explanation="cuDNN version affects convolution algorithm selection",
            )
        )

    if a.jax.jax_version != b.jax.jax_version:
        diffs.append(
            EnvironmentDiff(
                field_path="jax.jax_version",
                field_name="JAX Version",
                value_a=a.jax.jax_version,
                value_b=b.jax.jax_version,
                risk_level=RiskLevel.HIGH,
                explanation="JAX version affects computation graph compilation",
            )
        )

    if a.jax.xla_flags != b.jax.xla_flags:
        diffs.append(
            EnvironmentDiff(
                field_path="jax.xla_flags",
                field_name="XLA Flags",
                value_a=a.jax.xla_flags,
                value_b=b.jax.xla_flags,
                risk_level=RiskLevel.HIGH,
                explanation="XLA flags affect compiler optimizations and determinism",
            )
        )

    if a.jax.deterministic_ops_enabled != b.jax.deterministic_ops_enabled:
        diffs.append(
            EnvironmentDiff(
                field_path="jax.deterministic_ops_enabled",
                field_name="XLA Deterministic Ops",
                value_a=a.jax.deterministic_ops_enabled,
                value_b=b.jax.deterministic_ops_enabled,
                risk_level=RiskLevel.CRITICAL,
                explanation="Non-deterministic ops will cause different results on each run",
            )
        )

    if a.jax.x64_enabled != b.jax.x64_enabled:
        diffs.append(
            EnvironmentDiff(
                field_path="jax.x64_enabled",
                field_name="JAX X64 Enabled",
                value_a=a.jax.x64_enabled,
                value_b=b.jax.x64_enabled,
                risk_level=RiskLevel.HIGH,
                explanation="64-bit precision changes numerical results",
            )
        )

    if a.jax.default_backend != b.jax.default_backend:
        diffs.append(
            EnvironmentDiff(
                field_path="jax.default_backend",
                field_name="JAX Default Backend",
                value_a=a.jax.default_backend,
                value_b=b.jax.default_backend,
                risk_level=RiskLevel.HIGH,
                explanation="Backend selection affects device-specific computations",
            )
        )

    if a.python.version != b.python.version:
        diffs.append(
            EnvironmentDiff(
                field_path="python.version",
                field_name="Python Version",
                value_a=a.python.version,
                value_b=b.python.version,
                risk_level=RiskLevel.MEDIUM,
                explanation="Minor Python version differences rarely affect numerical results",
            )
        )

    if a.dependencies and b.dependencies:
        if a.dependencies.lockfile_hash != b.dependencies.lockfile_hash:
            diffs.append(
                EnvironmentDiff(
                    field_path="dependencies.lockfile_hash",
                    field_name="Dependency Lockfile Hash",
                    value_a=_short_hash(a.dependencies.lockfile_hash),
                    value_b=_short_hash(b.dependencies.lockfile_hash),
                    risk_level=RiskLevel.HIGH,
                    explanation="Package version changes may affect computation",
                )
            )
    elif a.dependencies or b.dependencies:
        diffs.append(
            EnvironmentDiff(
                field_path="dependencies.lockfile_hash",
                field_name="Dependency Lockfile Hash",
                value_a=a.dependencies.lockfile_hash if a.dependencies else None,
                value_b=b.dependencies.lockfile_hash if b.dependencies else None,
                risk_level=RiskLevel.LOW,
                explanation="Missing lockfile information reduces reproducibility guarantees",
            )
        )

    if a.git and b.git:
        if a.git.commit_sha != b.git.commit_sha:
            diffs.append(
                EnvironmentDiff(
                    field_path="git.commit_sha",
                    field_name="Git Commit",
                    value_a=a.git.commit_short,
                    value_b=b.git.commit_short,
                    risk_level=RiskLevel.MEDIUM,
                    explanation="Code changes between commits",
                )
            )

        if a.git.dirty or b.git.dirty:
            diffs.append(
                EnvironmentDiff(
                    field_path="git.dirty",
                    field_name="Uncommitted Changes",
                    value_a=a.git.dirty,
                    value_b=b.git.dirty,
                    risk_level=RiskLevel.LOW,
                    explanation="Working directory has uncommitted changes",
                )
            )

    system_keys = set(a.system_libraries) | set(b.system_libraries)
    for name in sorted(system_keys):
        info_a = a.system_libraries.get(name)
        info_b = b.system_libraries.get(name)
        if info_a is None or info_b is None:
            diffs.append(
                EnvironmentDiff(
                    field_path=f"system_libraries.{name}",
                    field_name=f"System Library {name}",
                    value_a=info_a.model_dump() if info_a else None,
                    value_b=info_b.model_dump() if info_b else None,
                    risk_level=RiskLevel.MEDIUM,
                    explanation="Missing system library metadata may hide runtime differences",
                )
            )
            continue
        if info_a.sha256 != info_b.sha256:
            diffs.append(
                EnvironmentDiff(
                    field_path=f"system_libraries.{name}.sha256",
                    field_name=f"System Library {name}",
                    value_a=_short_hash(info_a.sha256),
                    value_b=_short_hash(info_b.sha256),
                    risk_level=RiskLevel.HIGH,
                    explanation="System library changes can alter runtime behavior",
                )
            )

    if a.expected_precision_loss != b.expected_precision_loss:
        diffs.append(
            EnvironmentDiff(
                field_path="expected_precision_loss",
                field_name="Expected Precision Loss",
                value_a=a.expected_precision_loss,
                value_b=b.expected_precision_loss,
                risk_level=RiskLevel.INFO,
                explanation="Precision hint differs across environments",
            )
        )

    diffs.sort(key=lambda diff: _risk_order(diff.risk_level))
    return diffs


def _short_hash(value: str | None) -> str | None:
    if not value:
        return value
    return value[:24] + "..." if len(value) > 24 else value


def _risk_order(risk: RiskLevel) -> int:
    order = {
        RiskLevel.CRITICAL: 0,
        RiskLevel.HIGH: 1,
        RiskLevel.MEDIUM: 2,
        RiskLevel.LOW: 3,
        RiskLevel.INFO: 4,
    }
    return order[risk]


def _format_xla_flags(flags: dict[str, str]) -> str:
    if not flags:
        return ""
    parts = [f"{key}={value}" for key, value in sorted(flags.items())]
    return " ".join(parts)


def _fingerprint_system_libraries(libs: dict[str, SystemLibraryInfo]) -> str:
    if not libs:
        return ""
    parts = []
    for name in sorted(libs):
        info = libs[name]
        if info.sha256:
            parts.append(f"{name}:{info.sha256}")
        else:
            parts.append(f"{name}:nohash")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
