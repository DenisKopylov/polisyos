"""Run the source-selected Q2 host partitions using the existing consumer APIs."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import sys
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import ModuleType

    from .worker_host_driver import SourceBundle


class HostProfileExecutorError(RuntimeError):
    """Raised when a selected host profile cannot produce a bound receipt."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise HostProfileExecutorError(f"{label} is not a regular file: {path}")
    raw = path.read_bytes()
    if path.is_symlink() or not path.is_file():
        raise HostProfileExecutorError(f"{label} changed while being read: {path}")
    return raw


def _load_source_module(path: Path, expected_sha256: str, name: str) -> ModuleType:
    raw = _read_regular(path, name)
    if _sha256(raw) != expected_sha256:
        raise HostProfileExecutorError(f"{name} differs from the composite plan source pin")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise HostProfileExecutorError(f"cannot load source-owned module {name}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise
    if previous is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = previous
    if Path(module.__file__).resolve(strict=True) != path.resolve(strict=True):
        raise HostProfileExecutorError(f"{name} imported from another source path")
    return module


def _write_json(path: Path, value: object) -> dict[str, str]:
    if path.exists() or path.is_symlink():
        raise HostProfileExecutorError(f"refusing to replace retained evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n"
    path.write_bytes(raw)
    readback = _read_regular(path, "written host evidence")
    if readback != raw:
        raise HostProfileExecutorError(f"host evidence readback differs: {path}")
    return {"path": path.name, "sha256": _sha256(raw)}


def _evidence_ref(root: Path, path: Path) -> dict[str, str]:
    raw = _read_regular(path, "host execution evidence")
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as error:
        raise HostProfileExecutorError(
            "host execution evidence escaped its receipt root"
        ) from error
    posix = PurePosixPath(relative)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
        raise HostProfileExecutorError("host evidence path is not a safe relative path")
    return {"path": relative, "sha256": _sha256(raw)}


def _load_json_pin(reference: dict[str, Any], label: str) -> tuple[Path, dict[str, Any]]:
    if type(reference) is not dict or set(reference) != {"path", "sha256"}:
        raise HostProfileExecutorError(f"{label} source pin is malformed")
    path = Path(reference["path"])
    raw = _read_regular(path, label)
    if _sha256(raw) != reference["sha256"]:
        raise HostProfileExecutorError(f"{label} differs from its source pin")
    value = json.loads(raw)
    if type(value) is not dict:
        raise HostProfileExecutorError(f"{label} JSON root must be an object")
    return path, value


class HostProfileExecutor:
    """Execute the concrete host-primary Q2 consumer for each selected profile."""

    def __init__(
        self,
        *,
        plan: dict[str, Any],
        source_bundle: SourceBundle,
        source_root: Path,
        product_root: Path,
        app_python: Path,
        uv: Path,
        dependency_site: Path,
        output_root: Path,
        timeout_seconds: int = 1800,
    ) -> None:
        self.plan = plan
        self.bundle = source_bundle
        self.source_root = source_root.resolve(strict=True)
        self.product_root = product_root.resolve(strict=True)
        self.app_python = app_python.resolve(strict=True)
        self.uv = uv.resolve(strict=True)
        self.dependency_site = dependency_site.resolve(strict=True)
        self.output_root = output_root.absolute()
        if platform.system() != "Darwin" or sys.platform != "darwin":
            raise HostProfileExecutorError("the selected host executor requires measured Darwin")
        if self.product_root != self.source_root / "policy-engine":
            raise HostProfileExecutorError(
                "host product root differs from the selected source root"
            )
        if self.source_root != Path(plan["source_checkout"]["path"]).resolve(strict=True):
            raise HostProfileExecutorError("host source root differs from the source-bound plan")
        if not self.dependency_site.is_dir():
            raise HostProfileExecutorError("selected host dependency profile is unavailable")
        if type(timeout_seconds) is not int or timeout_seconds <= 0:
            raise HostProfileExecutorError("host consumer timeout must be a positive integer")
        self.timeout_seconds = timeout_seconds
        self.runner = _load_source_module(
            Path(plan["source_inputs"]["canonical_q2_runner"]["path"]),
            plan["source_inputs"]["canonical_q2_runner"]["sha256"],
            f"e02_q2_runner_host_{plan['source']['commit'][:12]}",
        )
        self.supplemental_runner = _load_source_module(
            Path(plan["source_inputs"]["canonical_supplemental_runner"]["path"]),
            plan["source_inputs"]["canonical_supplemental_runner"]["sha256"],
            f"e02_q2_supplemental_host_{plan['source']['commit'][:12]}",
        )
        self.consumer = source_bundle.split_consumer
        self.manifest_path, self.manifest = _load_json_pin(
            plan["source_inputs"]["primary_manifest"], "primary source manifest"
        )
        self.inventory_path, self.inventory = _load_json_pin(
            plan["source_inputs"]["source_inventory"],
            "complete source package inventory",
        )
        self.owner_inventory_path = Path(plan["owner_inventory"]["path"]).resolve(strict=True)
        owner_raw = _read_regular(self.owner_inventory_path, "runtime owner inventory")
        if _sha256(owner_raw) != plan["owner_inventory"]["sha256"]:
            raise HostProfileExecutorError("runtime owner inventory differs from its source pin")
        self.owner_inventory = json.loads(owner_raw)
        if type(self.owner_inventory) is not dict:
            raise HostProfileExecutorError("runtime owner inventory root must be an object")
        if self.output_root.exists() or self.output_root.is_symlink():
            raise HostProfileExecutorError("host executor output root must be fresh")
        self.output_root.mkdir(parents=True, mode=0o700, exist_ok=False)
        profile_probe = self.output_root / "host-interpreter"
        profile_probe.mkdir(mode=0o700)
        self.host_profile = self.runner.interpreter_info(
            self.app_python, log_dir=profile_probe, name="selected-host-consumer"
        )
        if (
            self.host_profile.get("implementation") != "cpython"
            or self.host_profile.get("version", [])[:2] != [3, 14]
            or Path(self.host_profile.get("purelib", "")).resolve(strict=True)
            != self.dependency_site
        ):
            raise HostProfileExecutorError(
                "selected host interpreter does not match the measured dependency profile"
            )
        self.contexts: dict[str, dict[str, Any]] = {}

    def _partition_row(self, partition: dict[str, Any]) -> dict[str, Any]:
        profile = partition.get("profile")
        rows = [
            row
            for row in self.plan["run_plan"]
            if row.get("phase") == "primary"
            and row.get("profile") == profile
            and row.get("executor") == "host"
        ]
        if len(rows) != 1 or partition != rows[0]:
            raise HostProfileExecutorError("host callback differs from its exact source plan row")
        return rows[0]

    def run_partition(self, partition: dict[str, Any]) -> Path:
        """Install and run one exact host partition, returning its complete receipt."""
        row = self._partition_row(partition)
        profile = row["profile"]
        if profile in self.contexts:
            raise HostProfileExecutorError("host profile partition was invoked more than once")
        artifact = next(
            (
                item
                for item in self.plan["artifacts"]
                if item.get("profile") == profile and item.get("sha256") == row["artifact_sha256"]
            ),
            None,
        )
        if type(artifact) is not dict:
            raise HostProfileExecutorError("host partition lacks its exact producer wheel")
        wheel = Path(artifact["path"]).resolve(strict=True)
        wheel_raw = _read_regular(wheel, "selected producer wheel")
        if len(wheel_raw) != artifact["bytes"] or _sha256(wheel_raw) != artifact["sha256"]:
            raise HostProfileExecutorError("selected producer wheel bytes differ from the plan")

        profile_root = self.output_root / profile
        profile_root.mkdir(mode=0o700, exist_ok=False)
        target = profile_root / "installed-target"
        target.mkdir(mode=0o700, exist_ok=False)
        primary_root = profile_root / "host-primary"
        primary_root.mkdir(mode=0o700, exist_ok=False)
        logs = primary_root / "logs"
        logs.mkdir(mode=0o700)
        temporary = primary_root / "tmp"
        temporary.mkdir(mode=0o700)

        gate_bytes, _gate_receipt = self.runner.load_installed_origin_gate()
        gate_path = target / "q2_installed_origin_gate.py"
        plugin_path = target / "q2_installed_origin_plugin.py"
        plugin_bytes = self.consumer.origin_plugin_source()
        self.consumer._write_new_or_same(gate_path, gate_bytes, "installed-origin gate")
        self.consumer._write_new_or_same(
            plugin_path, plugin_bytes, "installed-origin pytest plugin"
        )
        if (
            _sha256(_read_regular(gate_path, "installed-origin gate"))
            != self.runner.INSTALLED_ORIGIN_GATE_SHA256
            or _read_regular(plugin_path, "installed-origin plugin") != plugin_bytes
        ):
            raise HostProfileExecutorError("installed-origin helper differs from source bytes")

        preinstall = self.consumer._check_preinstall_target(target, self.inventory)
        before_install = preinstall.pop("_whole_target_before_snapshot")
        child_env = self.runner.clean_child_env()
        child_env.update(
            {
                "TMPDIR": str(temporary),
                "PYTHONDONTWRITEBYTECODE": "1",
                "UV_CACHE_DIR": str(primary_root / "uv-no-cache"),
            }
        )
        install_result = self.runner.run_command(
            [
                str(self.uv),
                "pip",
                "install",
                "--offline",
                "--no-index",
                "--no-deps",
                "--no-cache",
                "--python",
                str(self.app_python),
                "--target",
                str(target),
                str(wheel),
            ],
            cwd=primary_root,
            env=child_env,
            log_stem=logs / "uv-install-selected-wheel",
            check=False,
            timeout_seconds=180,
        )
        _write_json(
            primary_root / "installer-process.json",
            {
                "argv": install_result.args,
                "returncode": install_result.returncode,
                "stdout_sha256": _sha256(
                    (logs / "uv-install-selected-wheel.stdout.txt").read_bytes()
                ),
                "stderr_sha256": _sha256(
                    (logs / "uv-install-selected-wheel.stderr.txt").read_bytes()
                ),
            },
        )
        if install_result.returncode != 0:
            raise HostProfileExecutorError(
                f"offline source-bound {profile} wheel installation failed; outputs retained"
            )
        pth_after = [
            {"path": str(path), "sha256": self.runner.sha256_file(path)}
            for path in sorted(target.glob("*.pth"))
        ]
        egg_links_after = [str(path) for path in sorted(target.glob("*.egg-link"))]
        if (
            pth_after != preinstall["existing_pth_files"]
            or egg_links_after != preinstall["existing_egg_link_files"]
        ):
            raise HostProfileExecutorError("wheel install changed .pth or editable-link state")
        install_proof = self.consumer.verify_installed_inventory(
            target,
            self.inventory,
            before_snapshot=before_install,
            wheel_path=wheel,
        )
        _write_json(primary_root / "installed-inventory-proof.json", install_proof)
        target_before = self.consumer.snapshot_installed_tree(target)
        target_before_ref = _write_json(primary_root / "target-before-snapshot.json", target_before)

        resource_proof = self.consumer._run_installed_resource_helper(
            self.runner,
            self.app_python,
            target,
            self.dependency_site,
            self.product_root,
            self.source_root,
            self.owner_inventory,
            primary_root,
            logs,
        )
        resource_ref = _write_json(primary_root / "resource-proof.json", resource_proof)
        poison_proof = self.consumer._poisoned_neighbor_probe(
            self.runner,
            self.app_python,
            target,
            self.dependency_site,
            self.product_root,
            self.source_root,
            self.owner_inventory,
            primary_root,
            logs,
        )
        poison_ref = _write_json(primary_root / "poison-neighbor-proof.json", poison_proof)

        consumer_output = primary_root / "consumer"
        consumer_output.mkdir(mode=0o700)
        bootstrap = primary_root / "pytest-target-bootstrap.py"
        bootstrap.write_bytes(self.consumer.pytest_target_bootstrap_source())
        if _sha256(_read_regular(bootstrap, "pytest target bootstrap")) != _sha256(
            self.consumer.pytest_target_bootstrap_source()
        ):
            raise HostProfileExecutorError("pytest target bootstrap changed after writing")
        env = self.runner.clean_child_env()
        env.update(
            {
                "E02_SOURCE_ROOT": str(self.source_root),
                "E02_LIVE_PRODUCT_ROOT": str(self.product_root),
                "E02_DEPENDENCY_SITE": str(self.dependency_site),
                "E02_Q2_INSTALLED_TARGET": str(target),
                "E02_NODEIDS_REPORT": str(consumer_output / "collected-nodeids.json"),
                "E02_ORIGIN_REPORT": str(consumer_output / "origin-proof.json"),
                "E02_Q2_TARGET_PROOF": str(consumer_output / "installed-target-proof.json"),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        canonical_args = self.runner.pytest_arguments(
            self.app_python, self.product_root, self.manifest, consumer_output
        )
        if canonical_args[:4] != [str(self.app_python), "-I", "-m", "pytest"]:
            raise HostProfileExecutorError("canonical Q2 runner changed its isolated pytest entry")
        try:
            basetemp_at = canonical_args.index("--basetemp")
        except ValueError as error:
            raise HostProfileExecutorError("canonical Q2 runner omitted pytest basetemp") from error
        fixed_args = canonical_args[: basetemp_at + 2]
        node_ids = row["node_ids"]
        if type(node_ids) is not list or not node_ids or len(node_ids) != len(set(node_ids)):
            raise HostProfileExecutorError("host primary selection is empty or duplicated")
        selectors: list[str] = []
        for node_id in node_ids:
            path_text, separator, selector = node_id.partition("::")
            relative = PurePosixPath(path_text)
            if (
                not separator
                or not selector
                or relative.is_absolute()
                or relative.as_posix() != path_text
                or any(part in {"", ".", ".."} for part in relative.parts)
            ):
                raise HostProfileExecutorError("selected primary node ID is not a safe source path")
            selectors.append(f"{self.product_root.joinpath(*relative.parts)}::{selector}")
        command = [
            str(self.app_python),
            "-I",
            str(bootstrap),
            *fixed_args[4:],
            *selectors,
        ]
        process_result = self.runner.run_command(
            command,
            cwd=self.source_root,
            env=env,
            log_stem=consumer_output / "consumer-suite",
            check=False,
            stream_output=True,
            timeout_seconds=self.timeout_seconds,
        )
        expected_current = set(node_ids)
        baseline_ids = set(self.runner.baseline_node_ids(self.product_root, self.manifest))
        expected_original = expected_current & baseline_ids
        consumer_proof = self.runner.verify_consumer_run(
            process_result,
            run_root=consumer_output,
            output=consumer_output,
            manifest=self.manifest,
            expected_original_ids=expected_original,
            expected_current_ids=expected_current,
        )
        target_proof_path = consumer_output / "installed-target-proof.json"
        target_proof = json.loads(_read_regular(target_proof_path, "installed target proof"))
        if (
            target_proof.get("purelib") != str(target)
            or target_proof.get("dependency_site") != str(self.dependency_site)
            or target_proof.get("node_ids") != len(expected_current)
        ):
            raise HostProfileExecutorError("pytest target proof differs from selected target/cases")
        target_after = self.consumer.snapshot_installed_tree(target)
        target_after_ref = _write_json(primary_root / "target-after-snapshot.json", target_after)
        if target_before != target_after:
            raise HostProfileExecutorError("host consumer changed installed wheel bytes")
        identity = {
            "schema": "policyos.e02.q2.execution-identity.v1",
            "source": self.plan["source"],
            "platform_system": platform.system(),
            "sys_platform": sys.platform,
            "machine": platform.machine(),
            "python": str(self.app_python),
            "python_version": self.host_profile["version"],
            "runner_sha256": self.plan["input_pins"]["consumer_runner_sha256"],
            "source_checkout_root": str(self.source_root),
        }
        identity_ref = _write_json(primary_root / "execution-identity.json", identity)
        node_ids_path = consumer_output / "collected-nodeids.json"
        junit_path = consumer_output / "wave-junit.xml"
        origin_path = consumer_output / "origin-proof.json"
        target_proof_ref = _evidence_ref(primary_root, target_proof_path)
        result_path = primary_root / "primary-result.json"
        result = {
            "schema": self.bundle.composite.EXECUTION_SCHEMA,
            "source": self.plan["source"],
            "input_pins": self.plan["input_pins"],
            "profile": profile,
            "executor": "host",
            "artifact_sha256": row["artifact_sha256"],
            "plan_sha256": self.plan["plan_sha256"],
            "runner_sha256": self.plan["input_pins"]["consumer_runner_sha256"],
            "returncode": consumer_proof["returncode"],
            "execution_identity": identity_ref,
            "collected_node_ids": _evidence_ref(primary_root, node_ids_path),
            "junit": _evidence_ref(primary_root, junit_path),
            "origin_proof": _evidence_ref(primary_root, origin_path),
            "installed_target_proof": target_proof_ref,
            "resource_proof": resource_ref,
            "poison_proof": poison_ref,
            "target_before_snapshot": target_before_ref,
            "target_after_snapshot": target_after_ref,
            "stdout": _evidence_ref(primary_root, consumer_output / "consumer-suite.stdout.txt"),
            "stderr": _evidence_ref(primary_root, consumer_output / "consumer-suite.stderr.txt"),
        }
        _write_json(result_path, result)
        self.contexts[profile] = {
            "target": target,
            "profile_root": profile_root,
            "consumer_proof": consumer_proof,
        }
        return result_path


class SupplementalProfileExecutor:
    """Run each existing supplemental suite only after recomputing the barrier."""

    def __init__(self, host: HostProfileExecutor) -> None:
        self.host = host
        self.plan = host.plan
        self.bundle = host.bundle
        self.output_root = host.output_root
        self.runner = host.runner
        self.consumer = host.consumer
        self.supplemental_runner = host.supplemental_runner
        self.supplemental_manifest_path, self.supplemental_manifest = _load_json_pin(
            self.plan["source_inputs"]["supplemental_manifest"],
            "supplemental source manifest",
        )
        selected_ids = self.supplemental_runner.suite_node_ids(
            host.product_root, self.supplemental_manifest
        )
        if sorted(selected_ids) != self.plan["supplemental"]["node_ids"]:
            raise HostProfileExecutorError(
                "supplemental runner recomputed a different selected case set"
            )
        self.completed: set[str] = set()

    def run_profile(self, profile: str, admission: dict[str, Any]) -> dict[str, Any]:
        """Run one selected supplemental profile after a fresh six-row check."""
        if profile not in self.plan["profiles"] or profile in self.completed:
            raise HostProfileExecutorError("supplemental profile is absent or duplicated")
        if type(admission) is not dict or set(admission) != {
            "barrier",
            "execution_rows",
        }:
            raise HostProfileExecutorError("supplemental callback lacks the composite admission")
        barrier_sha = self.bundle.composite.require_supplemental_barrier(
            admission["barrier"], self.plan, admission["execution_rows"]
        )
        context = self.host.contexts.get(profile)
        if type(context) is not dict:
            raise HostProfileExecutorError("supplemental profile lacks its completed host install")
        target = context["target"]
        before = self.consumer.snapshot_installed_tree(target)
        profile_root: Path = context["profile_root"]
        output = profile_root / "supplemental"
        expected_ids = set(self.plan["supplemental"]["node_ids"])
        proof = self.consumer._run_supplemental_suite(
            self.runner,
            self.supplemental_runner,
            self.host.app_python,
            _bootstrap_path(profile_root),
            self.host.source_root,
            self.host.product_root,
            self.supplemental_manifest,
            target,
            self.host.dependency_site,
            output,
            timeout_seconds=self.host.timeout_seconds,
            expected_ids=expected_ids,
        )
        after = self.consumer.snapshot_installed_tree(target)
        if before != after:
            raise HostProfileExecutorError("supplemental consumer changed installed wheel bytes")
        proof_path = output / "supplemental-proof.json"
        proof_ref = _write_json(
            proof_path,
            {
                "schema": "policyos.e02.q2.supplemental-host-execution.v1",
                "source": self.plan["source"],
                "plan_sha256": self.plan["plan_sha256"],
                "profile": profile,
                "barrier_sha256": barrier_sha,
                "node_ids": sorted(expected_ids),
                "node_ids_sha256": self.plan["supplemental"]["node_ids_sha256"],
                "consumer": proof,
                "installed_target_unchanged": True,
            },
        )
        self.completed.add(profile)
        return {
            "profile": profile,
            "status": "verified_by_existing_supplemental_runner",
            "barrier_sha256": barrier_sha,
            "node_ids_sha256": self.plan["supplemental"]["node_ids_sha256"],
            "proof": proof_ref,
        }


def _bootstrap_path(profile_root: Path) -> Path:
    path = profile_root / "host-primary" / "pytest-target-bootstrap.py"
    if path.is_symlink() or not path.is_file():
        raise HostProfileExecutorError("selected host bootstrap is unavailable")
    return path
