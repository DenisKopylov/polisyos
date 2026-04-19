"""Environment capture functions: hardware, software, runtimes, and orchestrator."""

from __future__ import annotations

import json
import os
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polisyos.common.logger import get_logger

from ._env_models import (
    ContainerInfo,
    CPUInfo,
    DependencyInfo,
    EnvironmentManifest,
    GitInfo,
    GPUInfo,
    JAXInfo,
    OSInfo,
    PythonInfo,
    SystemLibraryInfo,
    TEEInfo,
)
from ._env_utils import (
    MAX_LIBRARY_BYTES,
    SYSTEM_LIBRARY_NAMES,
    estimate_precision_loss,
    hash_file,
    parse_xla_flags,
    safe_package_version,
    safe_run,
)

logger = get_logger(__name__)

__all__ = [
    "capture_environment",
]


# ---------------------------------------------------------------------------
# Hardware capture
# ---------------------------------------------------------------------------


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

            match = re.search(r"model name\s*:\s*(.+)", cpuinfo)
            if match:
                model_name = match.group(1).strip()

            flags_match = re.search(r"flags\s*:\s*(.+)", cpuinfo)
            if flags_match:
                flags = flags_match.group(1).lower()
                has_avx = " avx " in f" {flags} "
                has_avx2 = " avx2 " in f" {flags} "
                has_avx512 = "avx512" in flags
                has_amx = " amx" in flags

            features_match = re.search(r"features\s*:\s*(.+)", cpuinfo, re.IGNORECASE)
            if features_match:
                features = features_match.group(1).lower()
                has_neon = " neon" in f" {features} "

            core_pairs: set[tuple[str, str]] = set()
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
            safe_run(["sysctl", "-n", "machdep.cpu.brand_string"])
            or safe_run(["sysctl", "-n", "hw.model"])
            or "Unknown"
        )
        physical = safe_run(["sysctl", "-n", "hw.physicalcpu"])
        logical = safe_run(["sysctl", "-n", "hw.logicalcpu"])
        if physical and physical.isdigit():
            core_count = max(1, int(physical))
        if logical and logical.isdigit():
            thread_count = max(1, int(logical))

        if arch == "arm64":
            has_neon = True
        else:
            features = safe_run(["sysctl", "-n", "machdep.cpu.features"]) or ""
            features_lower = features.lower()
            has_avx = "avx" in features_lower
            has_avx2 = "avx2" in features_lower

            leaf7 = safe_run(["sysctl", "-n", "machdep.cpu.leaf7_features"]) or ""
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
            major = re.search(r"CUDNN_MAJOR\s+(\d+)", content)
            minor = re.search(r"CUDNN_MINOR\s+(\d+)", content)
            patch = re.search(r"CUDNN_PATCHLEVEL\s+(\d+)", content)
            if major and minor and patch:
                return f"{major.group(1)}.{minor.group(1)}.{patch.group(1)}"
        except (IOError, OSError):
            continue

    return None


def _capture_gpu_info() -> GPUInfo:
    """
    Capture GPU information with graceful degradation.

    Handles:
    - NVIDIA GPUs via nvidia-smi
    - Apple Silicon Metal via system_profiler
    - No GPU available
    """
    gpu_info = GPUInfo()

    nvidia_smi = safe_run(
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
            gpu_info.topology = safe_run(["nvidia-smi", "topo", "-m"])

        nvcc_output = safe_run(["nvcc", "--version"])
        if nvcc_output:
            match = re.search(r"release (\d+\.\d+)", nvcc_output)
            if match:
                gpu_info.cuda_version = match.group(1)

        cudnn_version = _get_cudnn_version()
        if cudnn_version:
            gpu_info.cudnn_version = cudnn_version

    if sys.platform == "darwin":
        sp_output = safe_run(["system_profiler", "SPDisplaysDataType", "-json"])
        if sp_output:
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


# ---------------------------------------------------------------------------
# Software capture
# ---------------------------------------------------------------------------


def _capture_os_info() -> OSInfo:
    """Capture OS information."""
    kernel_version = None
    libc_version = None

    if sys.platform == "linux":
        kernel_version = safe_run(["uname", "-r"])
        ldd_output = safe_run(["ldd", "--version"])
        if ldd_output:
            match = re.search(r"(\d+\.\d+)", ldd_output)
            if match:
                libc_version = f"glibc-{match.group(1)}"
    elif sys.platform == "darwin":
        kernel_version = safe_run(["uname", "-r"])

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
    exe_hash = hash_file(Path(sys.executable))

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

    jax_info.jax_version = safe_package_version("jax")
    jax_info.jaxlib_version = safe_package_version("jaxlib")

    if jax_info.jax_version:
        try:
            import jax

            devices = jax.devices()
            jax_info.default_backend = jax.default_backend()
            jax_info.available_backends = sorted({device.platform for device in devices})
            jax_info.device_count = len(devices)

            xla_flags_env = os.environ.get("XLA_FLAGS", "")
            jax_info.xla_flags = parse_xla_flags(xla_flags_env)

            jax_info.deterministic_ops_enabled = (
                "--xla_gpu_deterministic_ops=true" in xla_flags_env
            )
            jax_info.x64_enabled = bool(getattr(jax.config, "x64_enabled", False))

            try:
                from jax._src import lib as jaxlib_internal


                xla_version = getattr(jaxlib_internal, "xla_extension_version", None)
                if xla_version is not None:
                    jax_info.xla_version = str(xla_version)
            except (ImportError, AttributeError):
                pass
        except Exception as exc:
            logger.debug("Ignored exception: %s", exc)

    return jax_info


def _capture_git_info(repo_path: Path | None = None) -> GitInfo | None:
    """Capture Git repository information."""
    if repo_path is None:
        repo_path = Path.cwd()

    git_dir = safe_run(["git", "-C", str(repo_path), "rev-parse", "--git-dir"])
    if not git_dir:
        return None

    commit_sha = safe_run(["git", "-C", str(repo_path), "rev-parse", "HEAD"])
    if not commit_sha:
        return None

    commit_short = commit_sha[:8]
    branch = safe_run(["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"])

    status = safe_run(["git", "-C", str(repo_path), "status", "--porcelain"])
    dirty = bool(status and status.strip())

    tags_output = safe_run(["git", "-C", str(repo_path), "tag", "--points-at", commit_sha])
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

    lockfile_hash = hash_file(lockfile)
    if not lockfile_hash:
        return None

    try:
        mtime = datetime.fromtimestamp(lockfile.stat().st_mtime, tz=timezone.utc)
    except (IOError, OSError):
        mtime = None

    key_packages: dict[str, str] = {}
    critical_pkgs = ["jax", "jaxlib", "equinox", "optax", "diffrax", "pydantic", "numpy"]
    for pkg in critical_pkgs:
        version = safe_package_version(pkg)
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


def _detect_compute_backends() -> dict[str, dict[str, str]]:
    """Detect available compute backend packages and their versions."""
    backends: dict[str, dict[str, str]] = {}
    for package_name, backend_name in [
        ("jax", "jax"),
        ("jaxlib", "jaxlib"),
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("statsmodels", "statsmodels"),
        ("linearmodels", "linearmodels"),
        ("dowhy", "dowhy"),
        ("econml", "econml"),
        ("ortools", "ortools"),
        ("pulp", "pulp"),
    ]:
        version = safe_package_version(package_name)
        if version:
            backends[backend_name] = {"version": version}
    return backends


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
    output = safe_run(["ldconfig", "-p"])
    if not output:
        return {}
    cache: dict[str, str] = {}
    for line in output.splitlines():
        match = re.match(r"\s*(\S+)\s+\([^)]*\)\s+=>\s+(\S+)", line)
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

    digest = hash_file(path, max_bytes=MAX_LIBRARY_BYTES)
    modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    return SystemLibraryInfo(
        filename=path.name,
        sha256=digest,
        size_bytes=stat.st_size,
        modified_at=modified_at,
    )


def _capture_tee_info() -> TEEInfo | None:
    """Capture TEE attestation metadata from environment variables."""
    status = os.getenv("POLISYOS_TEE_ATTESTATION_STATUS", "").strip().lower()
    platform_name = os.getenv("POLISYOS_TEE_PLATFORM", "").strip().lower() or None
    report_hash = os.getenv("POLISYOS_TEE_REPORT_HASH", "").strip() or None
    measurement = os.getenv("POLISYOS_TEE_MEASUREMENT", "").strip() or None
    verified_at = os.getenv("POLISYOS_TEE_VERIFIED_AT", "").strip() or None
    tcb_version = os.getenv("POLISYOS_TEE_TCB_VERSION", "").strip() or None

    if not status and not platform_name and not report_hash:
        return None

    return TEEInfo(
        platform=platform_name,
        attestation_status=status or "unknown",
        report_hash=report_hash,
        measurement=measurement,
        tcb_version=tcb_version,
        verified_at=verified_at,
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def capture_environment(
    *,
    project_root: Path | str | None = None,
    include_git: bool = True,
    include_dependencies: bool = True,
    include_system_libraries: bool = True,
    include_compute_backends: bool = False,
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
    expected_precision_loss = estimate_precision_loss(cpu_info, gpu_info, jax_info)
    metadata_payload = dict(custom_metadata or {})
    if include_compute_backends:
        metadata_payload["compute_backends"] = _detect_compute_backends()

    return EnvironmentManifest(
        cpu=cpu_info,
        gpu=gpu_info,
        os=_capture_os_info(),
        python=_capture_python_info(),
        jax=jax_info,
        git=_capture_git_info(root) if include_git else None,
        dependencies=_capture_dependency_info(root) if include_dependencies else None,
        container=_capture_container_info(),
        tee=_capture_tee_info(),
        system_libraries=system_libs,
        expected_precision_loss=expected_precision_loss,
        custom_metadata=metadata_payload,
    )
