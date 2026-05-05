"""Tests for EnvironmentManifest capture and comparison."""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from polisyos.core.artifacts.environment import (
    CPUInfo,
    EnvironmentManifest,
    GitInfo,
    GPUInfo,
    JAXInfo,
    OSInfo,
    PythonInfo,
    RiskLevel,
    capture_environment,
    compare_environments,
)


class TestCPUInfo:
    def test_cpu_info_fingerprint_deterministic(self):
        cpu = CPUInfo(
            architecture="x86_64",
            model_name="Test CPU",
            core_count=8,
            thread_count=16,
            has_avx=True,
            has_avx2=True,
            has_avx512=False,
            has_amx=False,
            has_neon=False,
        )
        assert cpu.fingerprint == cpu.fingerprint
        assert len(cpu.fingerprint) == 16

    def test_cpu_info_fingerprint_differs_on_arch(self):
        cpu_x86 = CPUInfo(
            architecture="x86_64",
            model_name="Test",
            core_count=8,
            thread_count=16,
        )
        cpu_arm = CPUInfo(
            architecture="arm64",
            model_name="Test",
            core_count=8,
            thread_count=16,
        )
        assert cpu_x86.fingerprint != cpu_arm.fingerprint


class TestGPUInfo:
    def test_gpu_info_defaults(self):
        gpu = GPUInfo()
        assert gpu.available is False
        assert gpu.device_count == 0
        assert gpu.cuda_version is None

    def test_gpu_info_with_cuda(self):
        gpu = GPUInfo(
            available=True,
            device_count=1,
            model_name="NVIDIA A100",
            device_names=["NVIDIA A100"],
            device_uuids=["GPU-123"],
            memory_gb=40.0,
            cuda_version="12.3",
            cuda_driver_version="545.23",
            cudnn_version="8.9.7",
        )
        assert gpu.available is True
        assert gpu.cuda_version == "12.3"


class TestEnvironmentManifest:
    @pytest.fixture
    def minimal_manifest(self) -> EnvironmentManifest:
        return EnvironmentManifest(
            cpu=CPUInfo(
                architecture="x86_64",
                model_name="Test CPU",
                core_count=8,
                thread_count=16,
            ),
            gpu=GPUInfo(),
            os=OSInfo(system="Linux", release="5.15.0", version="#1 SMP"),
            python=PythonInfo(
                version="3.11.5",
                implementation="CPython",
                compiler="GCC 11.4.0",
            ),
            jax=JAXInfo(jax_version="0.4.25"),
        )

    def test_manifest_fingerprint_deterministic(self, minimal_manifest):
        fp1 = minimal_manifest.fingerprint
        fp2 = minimal_manifest.fingerprint
        assert fp1 == fp2
        assert len(fp1) == 32

    def test_manifest_fingerprint_changes_on_jax_version(self, minimal_manifest):
        manifest2 = EnvironmentManifest(
            cpu=minimal_manifest.cpu,
            gpu=minimal_manifest.gpu,
            os=minimal_manifest.os,
            python=minimal_manifest.python,
            jax=JAXInfo(jax_version="0.4.26"),
        )
        assert minimal_manifest.fingerprint != manifest2.fingerprint

    def test_compatibility_score_identical(self, minimal_manifest):
        score = minimal_manifest.compatibility_score(minimal_manifest)
        assert score == 1.0

    def test_compatibility_score_critical_diff(self):
        manifest1 = EnvironmentManifest(
            cpu=CPUInfo(
                architecture="x86_64",
                model_name="Test",
                core_count=8,
                thread_count=16,
            ),
            gpu=GPUInfo(),
            os=OSInfo(system="Linux", release="5.15", version="#1"),
            python=PythonInfo(version="3.11.5", implementation="CPython", compiler="GCC"),
            jax=JAXInfo(),
        )
        manifest2 = EnvironmentManifest(
            cpu=CPUInfo(
                architecture="arm64",
                model_name="Test",
                core_count=8,
                thread_count=16,
            ),
            gpu=GPUInfo(),
            os=OSInfo(system="Darwin", release="23.0", version="Darwin"),
            python=PythonInfo(version="3.11.5", implementation="CPython", compiler="Clang"),
            jax=JAXInfo(),
        )

        score = manifest1.compatibility_score(manifest2)
        assert score == 0.0

    def test_manifest_json_roundtrip(self, minimal_manifest):
        json_str = minimal_manifest.model_dump_json()
        restored = EnvironmentManifest.model_validate_json(json_str)

        assert restored.fingerprint == minimal_manifest.fingerprint
        assert restored.cpu.architecture == minimal_manifest.cpu.architecture
        assert restored.jax.jax_version == minimal_manifest.jax.jax_version


class TestCompareEnvironments:
    def test_compare_identical_returns_empty(self):
        manifest = EnvironmentManifest(
            cpu=CPUInfo(architecture="x86_64", model_name="Test", core_count=8, thread_count=16),
            gpu=GPUInfo(),
            os=OSInfo(system="Linux", release="5.15", version="#1"),
            python=PythonInfo(version="3.11.5", implementation="CPython", compiler="GCC"),
            jax=JAXInfo(),
        )

        diffs = compare_environments(manifest, manifest)
        assert len(diffs) == 0

    def test_compare_detects_architecture_change(self):
        manifest1 = EnvironmentManifest(
            cpu=CPUInfo(architecture="x86_64", model_name="Intel", core_count=8, thread_count=16),
            gpu=GPUInfo(),
            os=OSInfo(system="Linux", release="5.15", version="#1"),
            python=PythonInfo(version="3.11.5", implementation="CPython", compiler="GCC"),
            jax=JAXInfo(),
        )
        manifest2 = EnvironmentManifest(
            cpu=CPUInfo(
                architecture="arm64",
                model_name="Apple M3",
                core_count=8,
                thread_count=8,
                has_neon=True,
            ),
            gpu=GPUInfo(),
            os=OSInfo(system="Darwin", release="23.0", version="Darwin"),
            python=PythonInfo(version="3.11.5", implementation="CPython", compiler="Clang"),
            jax=JAXInfo(),
        )

        diffs = compare_environments(manifest1, manifest2)

        arch_diffs = [diff for diff in diffs if diff.field_path == "cpu.architecture"]
        assert len(arch_diffs) == 1
        assert arch_diffs[0].risk_level == RiskLevel.CRITICAL

    def test_compare_detects_cuda_driver_change(self):
        manifest1 = EnvironmentManifest(
            cpu=CPUInfo(architecture="x86_64", model_name="Test", core_count=8, thread_count=16),
            gpu=GPUInfo(available=True, cuda_version="12.3", cuda_driver_version="535.129"),
            os=OSInfo(system="Linux", release="5.15", version="#1"),
            python=PythonInfo(version="3.11.5", implementation="CPython", compiler="GCC"),
            jax=JAXInfo(),
        )
        manifest2 = EnvironmentManifest(
            cpu=CPUInfo(architecture="x86_64", model_name="Test", core_count=8, thread_count=16),
            gpu=GPUInfo(available=True, cuda_version="12.3", cuda_driver_version="545.23"),
            os=OSInfo(system="Linux", release="5.15", version="#1"),
            python=PythonInfo(version="3.11.5", implementation="CPython", compiler="GCC"),
            jax=JAXInfo(),
        )

        diffs = compare_environments(manifest1, manifest2)
        driver_diffs = [diff for diff in diffs if "cuda_driver" in diff.field_path]
        assert len(driver_diffs) == 1
        assert driver_diffs[0].risk_level == RiskLevel.HIGH

    def test_compare_sorted_by_risk(self):
        manifest1 = EnvironmentManifest(
            cpu=CPUInfo(architecture="x86_64", model_name="Test", core_count=8, thread_count=16),
            gpu=GPUInfo(cuda_version="12.3"),
            os=OSInfo(system="Linux", release="5.15", version="#1"),
            python=PythonInfo(version="3.11.5", implementation="CPython", compiler="GCC"),
            jax=JAXInfo(jax_version="0.4.23", deterministic_ops_enabled=True),
            git=GitInfo(commit_sha="abc123def", commit_short="abc123de", dirty=False),
        )
        manifest2 = EnvironmentManifest(
            cpu=CPUInfo(
                architecture="arm64",
                model_name="Test",
                core_count=8,
                thread_count=8,
                has_neon=True,
            ),
            gpu=GPUInfo(cuda_version="12.4"),
            os=OSInfo(system="Darwin", release="23.0", version="Darwin"),
            python=PythonInfo(version="3.11.6", implementation="CPython", compiler="Clang"),
            jax=JAXInfo(jax_version="0.4.25", deterministic_ops_enabled=False),
            git=GitInfo(commit_sha="xyz789abc", commit_short="xyz789ab", dirty=True),
        )

        diffs = compare_environments(manifest1, manifest2)
        risk_order = {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 3,
            RiskLevel.INFO: 4,
        }
        for prev, current in zip(diffs, diffs[1:]):
            assert risk_order[prev.risk_level] <= risk_order[current.risk_level]


class TestCaptureEnvironment:
    def test_capture_returns_valid_manifest(self):
        manifest = capture_environment(include_system_libraries=False)

        assert manifest.schema_version == "1.0"
        assert manifest.captured_at is not None
        assert manifest.cpu.architecture in ("x86_64", "arm64", "aarch64", "AMD64")
        assert (
            manifest.python.version
            == f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )

    def test_capture_respects_flags(self, tmp_path):
        manifest = capture_environment(
            project_root=tmp_path,
            include_git=False,
            include_dependencies=False,
            include_system_libraries=False,
        )

        assert manifest.git is None
        assert manifest.dependencies is None

    def test_capture_handles_missing_nvidia_smi(self):
        with patch("polisyos.core.artifacts.environment.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("nvidia-smi not found")

            manifest = capture_environment(include_git=False, include_dependencies=False)

            assert manifest.gpu.available is False or manifest.gpu.metal_available is True

    def test_capture_performance(self):
        import time

        start = time.monotonic()
        capture_environment(include_system_libraries=False)
        elapsed = time.monotonic() - start

        assert elapsed < 5.0, f"Capture took {elapsed:.2f}s, expected < 5s"

    def test_capture_no_private_data(self):
        manifest = capture_environment(include_system_libraries=False)
        json_str = manifest.model_dump_json()

        hostname = platform.node()

        assert "hostname" not in json_str.lower() or hostname not in json_str
        assert "username" not in json_str.lower()
        assert "password" not in json_str.lower()


class TestGitCapture:
    def test_git_capture_in_repo(self, tmp_path: Path):
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        manifest = capture_environment(project_root=tmp_path, include_system_libraries=False)

        assert manifest.git is not None
        assert len(manifest.git.commit_sha) == 40
        assert len(manifest.git.commit_short) == 8
        assert manifest.git.dirty is False

    def test_git_capture_detects_dirty(self, tmp_path: Path):
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        (tmp_path / "test.txt").write_text("modified")

        manifest = capture_environment(project_root=tmp_path, include_system_libraries=False)

        assert manifest.git is not None
        assert manifest.git.dirty is True
