from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import io
import json
import os
import sys
import tarfile
import tempfile
import zipfile
from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "policy-engine").is_dir() and (parent / ".git").exists()
)
POSTIMAGE_ROOT = (
    Path(os.environ["E02_Q2_POSTIMAGE_ROOT"]).resolve(strict=True)
    if os.environ.get("E02_Q2_POSTIMAGE_ROOT")
    else None
)
Q2_SOURCE = (
    POSTIMAGE_ROOT / "policy-engine/tools/quality/validation/q2_composite"
    if POSTIMAGE_ROOT is not None
    else REPO_ROOT / "policy-engine/tools/quality/validation/q2_composite"
)
sys.path.insert(0, str(Q2_SOURCE))
from split_protocol import (
    MAX_INSTALLER_METADATA_OVERHEAD_BYTES,
    SplitProtocolError,
    build_source_inventory,
    read_installed_member,
    require_worker_space,
    snapshot_installed_tree,
    validate_inventory,
    validate_request_binding,
    validate_source_audit_selection,
    verify_gcp_archive_inventory,
    verify_installed_inventory,
    verify_sdist_inventory,
    verify_wheel_inventory,
    wheel_uncompressed_bytes,
    worker_write_budget,
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_consumer(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("e02_split_consumer_pin_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_consumer_request(transfer: Path, protocol_sha: str) -> Path:
    consumer_path = Q2_SOURCE / "split_consumer.py"
    (transfer / "split_consumer.py").write_bytes(consumer_path.read_bytes())
    request = {
        "harness": {
            "consumer_file": "split_consumer.py",
            "consumer_sha256": digest((transfer / "split_consumer.py").read_bytes()),
            "protocol_file": "split_protocol.py",
            "protocol_sha256": protocol_sha,
        }
    }
    request_path = transfer / "split-consumer-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    return request_path


def fixture_product(root: Path) -> tuple[dict[str, object], dict[str, object]]:
    product = root / "policy-engine"
    (product / "src/polisyos/data/_resources").mkdir(parents=True)
    (product / "tools/q2").mkdir(parents=True)
    (product / "data/owned").mkdir(parents=True)
    files = {
        "src/polisyos/__init__.py": b"PACKAGE = True\n",
        "src/polisyos/data/_resources.py": b"def resolve(name): return name\n",
        "src/polisyos/data/_resources/__init__.py": b"",
        "tools/__init__.py": b"",
        "tools/q2/consumer.py": b"def consume(): return True\n",
        "data/owned/g-resource.yaml": b"owner: G\n",
    }
    for relative, payload in files.items():
        path = product / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    (product / "hatch.toml").write_text(
        '[build.targets.wheel]\npackages = ["src/polisyos", "tools"]\n'
        "[build.targets.wheel.force-include]\n"
        '"data/owned/g-resource.yaml" = "polisyos/data/_resources/g-resource.yaml"\n'
        '[build.targets.sdist]\ninclude = ["data/owned/g-resource.yaml"]\n',
        encoding="utf-8",
    )
    (product / "pyproject.toml").write_text(
        '[project]\nname = "polisyos"\nversion = "0.0.0"\n', encoding="utf-8"
    )
    gcp_script = product / "ops/cloud/gcp/package_repo.sh"
    gcp_script.parent.mkdir(parents=True)
    gcp_script.write_text(
        "#!/bin/bash\npython3 - << 'PY'\n"
        'include_paths = ["policy-engine/src", "policy-engine/tools"]\n'
        'skip_parts = {"__pycache__", ".git"}\n'
        'skip_suffixes = {".pyc", ".pyo"}\n'
        'skip_names = {".DS_Store"}\nPY\n',
        encoding="utf-8",
    )
    source, tree = "1" * 40, "2" * 40
    asset = {
        "source": "data/owned/g-resource.yaml",
        "archive": "policy-engine/data/owned/g-resource.yaml",
        "wheel": "polisyos/data/_resources/g-resource.yaml",
        "bytes": len(files["data/owned/g-resource.yaml"]),
        "sha256": digest(files["data/owned/g-resource.yaml"]),
    }
    manifest = {
        "schema_version": 1,
        "candidate_baseline": {
            "source_sha": source,
            "source_tree": tree,
            "force_include_count": 1,
            "force_include_assets": [asset],
        },
    }
    return {"product": product, "files": files, "source": source, "tree": tree}, manifest


def write_wheel(
    path: Path,
    root: Path,
    rows: list[dict[str, object]],
    *,
    omit: str | None = None,
    tamper: str | None = None,
    extra: str | None = None,
) -> None:
    payloads: dict[str, bytes] = {}
    for row in rows:
        target = str(row["wheel"])
        if target == omit:
            continue
        source_path = root.joinpath(*Path(str(row["source"])).parts)
        payload = source_path.read_bytes()
        if target == tamper:
            payload += b"altered"
        payloads[target] = payload
    if extra:
        payloads[extra] = b"unexpected"
    metadata_root = "polisyos-0.0.0.dist-info"
    payloads[f"{metadata_root}/METADATA"] = (
        b"Metadata-Version: 2.4\nName: polisyos\nVersion: 0.0.0\n"
    )
    payloads[f"{metadata_root}/WHEEL"] = (
        b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    )
    record_path = f"{metadata_root}/RECORD"
    rows_out: list[list[str]] = []
    for name, payload in sorted(payloads.items()):
        digest_value = (
            base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).decode().rstrip("=")
        )
        rows_out.append([name, f"sha256={digest_value}", str(len(payload))])
    rows_out.append([record_path, "", ""])
    record_stream = io.StringIO(newline="")
    csv.writer(record_stream, lineterminator="\n").writerows(rows_out)
    payloads[record_path] = record_stream.getvalue().encode("utf-8")
    with zipfile.ZipFile(path, "w") as wheel:
        for name, payload in sorted(payloads.items()):
            wheel.writestr(name, payload)


def test_source_inventory_is_complete_and_derived_from_hatch_config() -> None:
    canonical_tmp = Path(tempfile.gettempdir()).resolve(strict=True)
    with tempfile.TemporaryDirectory(dir=canonical_tmp) as temporary:
        state, manifest = fixture_product(Path(temporary))
        inventory = build_source_inventory(
            state["product"], manifest, expected_commit=state["source"], expected_tree=state["tree"]
        )
        targets = {row["wheel"] for row in inventory["rows"]}
        assert targets == {
            "polisyos/__init__.py",
            "polisyos/data/_resources.py",
            "polisyos/data/_resources/__init__.py",
            "polisyos/data/_resources/g-resource.yaml",
            "tools/__init__.py",
            "tools/q2/consumer.py",
        }
        assert inventory["source"]["commit"] == state["source"]
        assert inventory["source"]["tree"] == state["tree"]
        assert len(inventory["assets"]) == 1
        assert inventory["assets"][0]["source"] == "data/owned/g-resource.yaml"


def test_wheel_inventory_accepts_exact_source_package_and_g_resource_bytes() -> None:
    canonical_tmp = Path(tempfile.gettempdir()).resolve(strict=True)
    with tempfile.TemporaryDirectory(dir=canonical_tmp) as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        inventory = build_source_inventory(
            state["product"], manifest, expected_commit=state["source"], expected_tree=state["tree"]
        )
        wheel_path = root / "candidate.whl"
        write_wheel(wheel_path, Path(state["product"]), inventory["rows"])
        result = verify_wheel_inventory(wheel_path, inventory)
        assert result["member_count"] == len(inventory["rows"]) + 3
        assert result["sha256"] == digest(wheel_path.read_bytes())


def test_wheel_inventory_rejects_missing_force_include_asset() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        inventory = build_source_inventory(
            state["product"], manifest, expected_commit=state["source"], expected_tree=state["tree"]
        )
        asset = inventory["assets"][0]["wheel"]
        wheel_path = root / "missing.whl"
        write_wheel(wheel_path, Path(state["product"]), inventory["rows"], omit=asset)
        with pytest.raises(SplitProtocolError, match=r"missing|member set"):
            verify_wheel_inventory(wheel_path, inventory)


def test_wheel_inventory_rejects_tampered_package_byte_and_unexpected_neighbor() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        inventory = build_source_inventory(
            state["product"], manifest, expected_commit=state["source"], expected_tree=state["tree"]
        )
        first = str(inventory["rows"][0]["wheel"])
        tampered = root / "tampered.whl"
        write_wheel(tampered, Path(state["product"]), inventory["rows"], tamper=first)
        try:
            verify_wheel_inventory(tampered, inventory)
        except SplitProtocolError:
            pass
        else:
            raise AssertionError("tampered source package byte was accepted")
        for name, extra in (
            ("package-neighbor.whl", "polisyos/foreign.py"),
            ("unowned-root.whl", "production_data/secret.json"),
        ):
            unexpected = root / name
            write_wheel(unexpected, Path(state["product"]), inventory["rows"], extra=extra)
            with pytest.raises(SplitProtocolError):
                verify_wheel_inventory(unexpected, inventory)


def test_source_inventory_rejects_wrong_freeze_and_present_asset_drift() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        state, manifest = fixture_product(Path(temporary))
        try:
            build_source_inventory(
                state["product"], manifest, expected_commit="3" * 40, expected_tree=state["tree"]
            )
        except SplitProtocolError:
            pass
        else:
            raise AssertionError("wrong commit was accepted")
        (state["product"] / "data/owned/g-resource.yaml").write_text("owner: impostor\n")
        try:
            build_source_inventory(
                state["product"],
                manifest,
                expected_commit=state["source"],
                expected_tree=state["tree"],
            )
        except SplitProtocolError:
            pass
        else:
            raise AssertionError("malformed-present resource drift was accepted")


def test_poisoned_neighbor_cannot_replace_installed_member_and_missing_is_refused() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        installed = root / "site-packages"
        target = installed / "polisyos/data/_resources/g-resource.yaml"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"owner: G\n")
        neutral = root / "neutral"
        poison = neutral / "data/owned/g-resource.yaml"
        poison.parent.mkdir(parents=True)
        poison.write_bytes(b"owner: foreign\n")
        old = Path.cwd()
        try:
            import os

            os.chdir(neutral)
            assert Path("data/owned/g-resource.yaml").read_bytes() != b"owner: G\n"
            assert (
                read_installed_member(installed, "polisyos/data/_resources/g-resource.yaml")
                == b"owner: G\n"
            )
            try:
                read_installed_member(installed, "polisyos/data/_resources/missing.yaml")
            except SplitProtocolError:
                pass
            else:
                raise AssertionError("missing installed asset was accepted")
        finally:
            os.chdir(old)


def test_worker_budget_preserves_cap_and_four_gib_reserve() -> None:
    budget = worker_write_budget(
        fast_forward_pack_bytes=4_000_000,
        checkout_growth_bytes=3_000_000,
        wheel_bytes=20_000_000,
        package_target_bytes=62_000_000,
        installer_transient_bytes=20_000_000,
        logs_and_test_temp_bytes=24_000_000,
        request_and_metadata_bytes=2_000_000,
    )
    observed = require_worker_space(
        free_bytes=4_558_636 * 1024,
        budget=budget,
    )
    assert observed["free_after_budget_bytes"] >= 4_294_967_296
    try:
        worker_write_budget(
            fast_forward_pack_bytes=200_000_000,
            checkout_growth_bytes=3_000_000,
            wheel_bytes=20_000_000,
            package_target_bytes=62_000_000,
            installer_transient_bytes=20_000_000,
            logs_and_test_temp_bytes=24_000_000,
            request_and_metadata_bytes=2_000_000,
        )
    except SplitProtocolError:
        pass
    else:
        raise AssertionError("over-cap worker plan was accepted")
    try:
        require_worker_space(
            free_bytes=budget["future_write_bytes"] + 4_294_967_295,
            budget=budget,
        )
    except SplitProtocolError:
        pass
    else:
        raise AssertionError("worker plan below reserve was accepted")


def test_worker_output_matrix_requires_exact_transfer_members_and_target_accounting() -> None:
    canonical_tmp = Path(tempfile.gettempdir()).resolve(strict=True)
    with tempfile.TemporaryDirectory(dir=canonical_tmp) as module_temporary:
        transfer = Path(module_temporary) / "transfer"
        transfer.mkdir()
        protocol_path = transfer / "split_protocol.py"
        protocol_path.write_bytes((Q2_SOURCE / "split_protocol.py").read_bytes())
        consumer_path = transfer / "split_consumer.py"
        request_path = write_consumer_request(transfer, digest(protocol_path.read_bytes()))
        consumer = load_consumer(consumer_path)
        consumer._load_pinned_protocol(
            Namespace(
                transfer_root=str(transfer),
                request=str(request_path),
                request_sha256=digest(request_path.read_bytes()),
            )
        )
    compile(consumer.origin_plugin_source(), "q2-installed-origin-plugin.py", "exec")
    compile(consumer.pytest_target_bootstrap_source(), "q2-target-bootstrap.py", "exec")
    events: list[str] = []

    def primary(profile: str) -> dict[str, str]:
        events.append(f"primary:{profile}")
        return {"profile": profile}

    def supplemental(profile: str) -> dict[str, str]:
        events.append(f"supplemental:{profile}")
        return {"profile": profile}

    matrix = consumer._execute_consumer_matrix(
        ["source-wheel", "rebuilt-sdist-wheel", "rebuilt-gcp-archive-wheel"],
        run_primary=primary,
        run_supplemental=supplemental,
    )
    assert events == [
        "primary:source-wheel",
        "primary:rebuilt-sdist-wheel",
        "primary:rebuilt-gcp-archive-wheel",
        "supplemental:source-wheel",
        "supplemental:rebuilt-sdist-wheel",
        "supplemental:rebuilt-gcp-archive-wheel",
    ]
    assert set(matrix["primary"]) == {
        "source-wheel",
        "rebuilt-sdist-wheel",
        "rebuilt-gcp-archive-wheel",
    }
    assert set(matrix["supplemental"]) == set(matrix["primary"])

    supplemental_calls: list[str] = []

    def failing_primary(profile: str) -> dict[str, str]:
        if profile == "rebuilt-sdist-wheel":
            raise RuntimeError("primary failed")
        return {"profile": profile}

    with pytest.raises(RuntimeError, match="primary failed"):
        consumer._execute_consumer_matrix(
            ["source-wheel", "rebuilt-sdist-wheel", "rebuilt-gcp-archive-wheel"],
            run_primary=failing_primary,
            run_supplemental=lambda profile: supplemental_calls.append(profile) or {},
        )
    assert supplemental_calls == []

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        transfer = root / "transfer"
        transfer.mkdir()
        (transfer / "split-consumer-request.json").write_bytes(b"request")
        wheel_dir = transfer / "wheels" / "source-wheel"
        wheel_dir.mkdir(parents=True)
        (wheel_dir / "polisyos.whl").write_bytes(b"wheel")
        expected = {
            "split-consumer-request.json",
            "wheels/source-wheel/polisyos.whl",
        }
        consumer._verify_transfer_file_set(transfer, expected)
        (transfer / "production_data").mkdir()
        (transfer / "production_data/secret.json").write_bytes(b"unexpected")
        with pytest.raises(consumer.SplitProtocolError, match="full member set"):
            consumer._verify_transfer_file_set(transfer, expected)

        output = root / "worker-output"
        target = output / "profiles/source-wheel/installed-target"
        target.mkdir(parents=True)
        (target / "package.py").write_bytes(b"seven!!")
        logs = output / "profiles/source-wheel/primary-consumers"
        logs.mkdir(parents=True)
        (logs / "consumer-suite.stdout.txt").write_bytes(b"receipt")
        assert consumer._output_tree_bytes(output) == len(b"seven!!") + len(b"receipt")
        assert consumer._output_tree_bytes(output, excluded_roots={target}) == len(b"receipt")


def test_request_binds_all_three_artifacts_and_both_consumer_phases() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        inventory = build_source_inventory(
            state["product"], manifest, expected_commit=state["source"], expected_tree=state["tree"]
        )
        profiles = [
            "source-wheel",
            "rebuilt-sdist-wheel",
            "rebuilt-gcp-archive-wheel",
        ]
        chain_keys = {
            "source-wheel": "source_wheel_sha256",
            "rebuilt-sdist-wheel": "rebuilt_sdist_wheel_sha256",
            "rebuilt-gcp-archive-wheel": "rebuilt_gcp_wheel_sha256",
        }
        wheel_paths: dict[str, Path] = {}
        artifacts: list[dict[str, object]] = []
        for profile in profiles:
            wheel = root / "wheels" / profile / "polisyos-0.0.0-py3-none-any.whl"
            wheel.parent.mkdir(parents=True)
            write_wheel(wheel, Path(state["product"]), inventory["rows"])
            wheel_paths[profile] = wheel
            artifacts.append(
                {
                    "profile": profile,
                    "chain_key": chain_keys[profile],
                    "file": f"wheels/{profile}/{wheel.name}",
                    "bytes": wheel.stat().st_size,
                    "sha256": digest(wheel.read_bytes()),
                }
            )
        manifest_raw = json.dumps(manifest, sort_keys=True).encode()
        inventory_raw = json.dumps(inventory, sort_keys=True).encode()
        wheel_sha = digest(next(iter(wheel_paths.values())).read_bytes())
        chain = {
            "source_archive_sha256": "a" * 64,
            "source_wheel_sha256": wheel_sha,
            "source_sdist_sha256": "c" * 64,
            "rebuilt_sdist_wheel_sha256": wheel_sha,
            "gcp_archive_sha256": "d" * 64,
            "rebuilt_gcp_wheel_sha256": wheel_sha,
        }
        overhead = {
            "origin_gate": 11,
            "origin_plugin": 13,
            "installer_metadata_reserve": MAX_INSTALLER_METADATA_OVERHEAD_BYTES,
        }
        wheel_bytes = sum(path.stat().st_size for path in wheel_paths.values())
        target_bytes = sum(wheel_uncompressed_bytes(path) for path in wheel_paths.values())
        target_bytes += len(profiles) * sum(overhead.values())
        budget = worker_write_budget(
            fast_forward_pack_bytes=1,
            checkout_growth_bytes=1,
            wheel_bytes=wheel_bytes,
            package_target_bytes=target_bytes,
            installer_transient_bytes=max(path.stat().st_size for path in wheel_paths.values()),
            logs_and_test_temp_bytes=1_000,
            request_and_metadata_bytes=1_000,
        )
        primary_ids = ["tests/unit/test_primary.py::test_primary"]
        supplemental_ids = ["tests/unit/test_supplemental.py::test_supplemental"]

        def ids_sha(values: list[str]) -> str:
            return digest(("\n".join(values) + "\n").encode())

        request = {
            "schema": "policyos.e02.q2.split-consumer-request.v2",
            "source": {"commit": state["source"], "tree": state["tree"]},
            "worker_write_budget": budget,
            "installed_target_overhead_bytes": overhead,
            "manifest_sha256": digest(manifest_raw),
            "inventory_sha256": digest(inventory_raw),
            "artifacts": artifacts,
            "artifact_chain": chain,
            "consumer_selection": {
                "manifest_driven": True,
                "profiles": profiles,
                "primary_node_ids": primary_ids,
                "primary_node_ids_sha256": ids_sha(primary_ids),
                "supplemental_node_ids": supplemental_ids,
                "supplemental_node_ids_sha256": ids_sha(supplemental_ids),
                "profile_case_count": len(profiles) * (len(primary_ids) + len(supplemental_ids)),
                "execution_plan": [
                    {"phase": phase, "profile": profile}
                    for phase in ("primary", "supplemental")
                    for profile in profiles
                ],
            },
        }
        assert validate_request_binding(
            request,
            manifest,
            inventory,
            manifest_sha256=digest(manifest_raw),
            inventory_sha256=digest(inventory_raw),
            expected_commit=state["source"],
            expected_tree=state["tree"],
            wheel_paths=wheel_paths,
        )["artifacts"].keys() == set(profiles)

        broken = dict(request)
        broken["artifact_chain"] = dict(chain)
        broken["artifact_chain"]["rebuilt_sdist_wheel_sha256"] = "f" * 64
        try:
            validate_request_binding(
                broken,
                manifest,
                inventory,
                manifest_sha256=digest(manifest_raw),
                inventory_sha256=digest(inventory_raw),
                expected_commit=state["source"],
                expected_tree=state["tree"],
                wheel_paths=wheel_paths,
            )
        except SplitProtocolError:
            pass
        else:
            raise AssertionError("mismatched artifact chain was accepted")

        wrong_filename = json.loads(json.dumps(request))
        wrong_filename["artifacts"][1]["file"] = "wheels/rebuilt-sdist-wheel/other.whl"
        try:
            validate_request_binding(
                wrong_filename,
                manifest,
                inventory,
                manifest_sha256=digest(manifest_raw),
                inventory_sha256=digest(inventory_raw),
                expected_commit=state["source"],
                expected_tree=state["tree"],
                wheel_paths=wheel_paths,
            )
        except SplitProtocolError:
            pass
        else:
            raise AssertionError("renamed profile wheel transfer was accepted")

        for field, replacement in (
            ("profile_case_count", 5),
            ("primary_node_ids_sha256", "0" * 64),
            ("manifest_driven", False),
        ):
            incomplete = json.loads(json.dumps(request))
            incomplete["consumer_selection"][field] = replacement
            with pytest.raises(SplitProtocolError):
                validate_request_binding(
                    incomplete,
                    manifest,
                    inventory,
                    manifest_sha256=digest(manifest_raw),
                    inventory_sha256=digest(inventory_raw),
                    expected_commit=state["source"],
                    expected_tree=state["tree"],
                    wheel_paths=wheel_paths,
                )

        missing_profile = json.loads(json.dumps(request))
        missing_profile["artifacts"].pop()
        with pytest.raises(SplitProtocolError):
            validate_request_binding(
                missing_profile,
                manifest,
                inventory,
                manifest_sha256=digest(manifest_raw),
                inventory_sha256=digest(inventory_raw),
                expected_commit=state["source"],
                expected_tree=state["tree"],
                wheel_paths=wheel_paths,
            )

        wrong_phase_order = json.loads(json.dumps(request))
        wrong_phase_order["consumer_selection"]["execution_plan"].reverse()
        with pytest.raises(SplitProtocolError, match="complete ordered"):
            validate_request_binding(
                wrong_phase_order,
                manifest,
                inventory,
                manifest_sha256=digest(manifest_raw),
                inventory_sha256=digest(inventory_raw),
                expected_commit=state["source"],
                expected_tree=state["tree"],
                wheel_paths=wheel_paths,
            )


def test_installed_inventory_checks_every_member_and_rejects_extra_file() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        inventory = build_source_inventory(
            state["product"], manifest, expected_commit=state["source"], expected_tree=state["tree"]
        )
        target = root / "target"
        target.mkdir()
        dependency = target / "existing_dependency/__init__.py"
        dependency.parent.mkdir()
        dependency.write_bytes(b"pre-existing dependency\n")
        before = snapshot_installed_tree(target)
        wheel = root / "installed.whl"
        write_wheel(wheel, Path(state["product"]), inventory["rows"])
        with zipfile.ZipFile(wheel) as archive:
            for info in archive.infolist():
                destination = target / info.filename
                if not destination.resolve().is_relative_to(target.resolve()):
                    raise AssertionError("test wheel fixture escaped its temporary target")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(info))
        result = verify_installed_inventory(
            target, inventory, before_snapshot=before, wheel_path=wheel
        )
        assert result["member_count"] == len(inventory["rows"]) + 3
        assert result["whole_target_delta_reconciled"] is True
        extra = target / "production_data/secret.json"
        extra.parent.mkdir()
        extra.write_bytes(b"must not be introduced by the installation")
        try:
            verify_installed_inventory(target, inventory, before_snapshot=before, wheel_path=wheel)
        except SplitProtocolError:
            pass
        else:
            raise AssertionError("unowned whole-target file was accepted")


def write_tar(path: Path, files: dict[str, bytes], *, extra: str | None = None) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(payload))
        if extra is not None:
            payload = b"unowned"
            info = tarfile.TarInfo(extra)
            info.size = len(payload)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(payload))


def test_sdist_and_gcp_archives_reject_unexpected_regular_members() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        inventory = build_source_inventory(
            state["product"], manifest, expected_commit=state["source"], expected_tree=state["tree"]
        )
        sdist_prefix = "polisyos-0.0.0"
        sdist_files = {
            f"{sdist_prefix}/{row['source']}": Path(state["product"])
            .joinpath(*Path(str(row["source"])).parts)
            .read_bytes()
            for row in inventory["sdist_source_rows"]
        }
        sdist_files[f"{sdist_prefix}/PKG-INFO"] = (
            b"Metadata-Version: 2.4\nName: polisyos\nVersion: 0.0.0\n"
        )
        good_sdist = root / "source.tar.gz"
        write_tar(good_sdist, sdist_files)
        assert verify_sdist_inventory(good_sdist, inventory)["complete_member_set"] is True
        bad_sdist = root / "source-with-extra.tar.gz"
        write_tar(bad_sdist, sdist_files, extra=f"{sdist_prefix}/production_data/secret.json")
        with pytest.raises(SplitProtocolError, match="complete regular-file set"):
            verify_sdist_inventory(bad_sdist, inventory)

        gcp_files = {
            row["archive"]: Path(state["product"])
            .joinpath(*Path(str(row["source"])).parts)
            .read_bytes()
            for row in inventory["gcp_source_rows"]
        }
        good_gcp = root / "gcp.tar.gz"
        write_tar(good_gcp, gcp_files)
        assert verify_gcp_archive_inventory(good_gcp, inventory)["complete_member_set"] is True
        bad_gcp = root / "gcp-with-extra.tar.gz"
        write_tar(bad_gcp, gcp_files, extra="policy-engine/production_data/leak.json")
        with pytest.raises(SplitProtocolError, match="complete regular-file set"):
            verify_gcp_archive_inventory(bad_gcp, inventory)


def test_source_audit_selection_binds_complete_profiles_and_both_id_sets() -> None:
    primary = ["tests/unit/test_a.py::test_x", "tests/unit/test_b.py::test_y"]
    supplemental = ["tests/unit/test_supplemental.py::test_extra"]
    profiles = ["source-wheel", "rebuilt-sdist-wheel", "rebuilt-gcp-archive-wheel"]

    def ids_digest(values: list[str]) -> str:
        return digest(("\n".join(values) + "\n").encode())

    receipt = {
        "schema_version": 1,
        "status": "source_preflight_exact",
        "source_sha": "1" * 40,
        "source_tree": "2" * 40,
        "source_object_and_actual_collection_reconcile": True,
        "capsule_bindings_current": True,
        "frozen_checkout_clean_tracked": True,
        "build_started": False,
        "install_started": False,
        "tests_executed": False,
        "pytest_collection_only": True,
        "runner_limitations": [],
        "primary": {
            "current_manifest_sha256": "3" * 64,
            "source_derived_ids": len(primary),
            "source_derived_node_ids": primary,
            "source_derived_ids_sha256": ids_digest(primary),
        },
        "supplemental": {
            "current_manifest_sha256": "4" * 64,
            "source_derived_ids": len(supplemental),
            "source_derived_node_ids": supplemental,
            "source_derived_ids_sha256": ids_digest(supplemental),
        },
        "profiles": profiles,
        "primary_runner_profile_names": profiles,
        "supplemental_runner_profile_names": profiles,
        "source_derived_profile_case_count": len(profiles) * (len(primary) + len(supplemental)),
    }
    selected = validate_source_audit_selection(
        receipt,
        expected_commit="1" * 40,
        expected_tree="2" * 40,
        manifest_sha256="3" * 64,
        supplemental_manifest_sha256="4" * 64,
    )
    assert selected["profiles"] == profiles
    assert selected["primary_node_ids"] == primary
    assert selected["supplemental_node_ids"] == supplemental
    assert selected["profile_case_count"] == 9

    broken = json.loads(json.dumps(receipt))
    broken["primary"]["source_derived_node_ids"][1] = "tests/unit/test_b.py::test_replaced"
    with pytest.raises(SplitProtocolError, match="digest differs"):
        validate_source_audit_selection(
            broken,
            expected_commit="1" * 40,
            expected_tree="2" * 40,
            manifest_sha256="3" * 64,
            supplemental_manifest_sha256="4" * 64,
        )


def test_actual_catalog_reader_ignores_poisoned_cwd_and_package_neighbors() -> None:
    repo = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (
            parent / "policy-engine/src/polisyos/data_forge/domains/catalog/_resources.py"
        ).is_file()
    )
    source_bytes = (
        repo / "policy-engine/src/polisyos/data_forge/domains/catalog/_resources.py"
    ).read_bytes()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        purelib = root / "environment/lib/python3.14/site-packages"
        catalog_dir = purelib / "polisyos/data_forge/domains/catalog"
        catalog_dir.mkdir(parents=True)
        reader_path = catalog_dir / "_resources.py"
        reader_path.write_bytes(source_bytes)
        spec = importlib.util.spec_from_file_location("split_test_resources", reader_path)
        assert spec is not None
        assert spec.loader is not None
        reader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reader)
        resource_root = catalog_dir / "_resources"
        resource_root.mkdir()
        selected = "metrics_map.yaml"
        expected = b"owner: installed\n"
        (resource_root / selected).write_bytes(expected)
        neutral = root / "neutral-cwd"
        package_neighbor = neutral / "polisyos/data_forge/domains/catalog/_resources"
        package_neighbor.mkdir(parents=True)
        (neutral / selected).write_bytes(b"owner: cwd-poison\n")
        (package_neighbor / selected).write_bytes(b"owner: package-poison\n")
        resolved = reader.catalog_default_resource_path(selected).resolve(strict=True)
        assert resolved == (resource_root / selected).resolve(strict=True)
        assert resolved.read_bytes() == expected


def test_actual_q2_origin_gate_accepts_selected_root_and_rejects_wrong_origin() -> None:
    gate_path = (
        REPO_ROOT
        / "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
        / "q2-packaging/raw/installed_origin_gate_r4.py"
    )
    spec = importlib.util.spec_from_file_location("q2_test_origin_gate", gate_path)
    assert spec is not None
    assert spec.loader is not None
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        selected = root / "installed/polisyos"
        selected.mkdir(parents=True)
        selected_module = selected / "probe.py"
        selected_module.write_text("SELECTED = True\n", encoding="utf-8")
        selected_spec = importlib.util.spec_from_file_location("polisyos.probe", selected_module)
        assert selected_spec is not None
        assert selected_spec.loader is not None
        selected_import = importlib.util.module_from_spec(selected_spec)
        selected_spec.loader.exec_module(selected_import)
        accepted, accepted_errors = gate.verify_loaded_module_origins(
            selected.parent, {"polisyos.probe": selected_import}
        )
        assert "polisyos.probe" in accepted
        assert accepted_errors == []

        neighbor = root / "neighbor/polisyos"
        neighbor.mkdir(parents=True)
        neighbor_module = neighbor / "probe.py"
        neighbor_module.write_text("SELECTED = False\n", encoding="utf-8")
        neighbor_spec = importlib.util.spec_from_file_location("polisyos.probe", neighbor_module)
        assert neighbor_spec is not None
        assert neighbor_spec.loader is not None
        neighbor_import = importlib.util.module_from_spec(neighbor_spec)
        neighbor_spec.loader.exec_module(neighbor_import)
        refused, refused_errors = gate.verify_loaded_module_origins(
            selected.parent, {"polisyos.probe": neighbor_import}
        )
        assert refused == {}
        assert refused_errors
        assert refused_errors[0]["module"] == "polisyos.probe"


def test_worker_checks_external_module_pins_before_protocol_execution() -> None:
    consumer_source = (Q2_SOURCE / "split_consumer.py").read_bytes()
    marker_name = "q2-split-protocol-executed-before-pin"
    canonical_tmp = Path(tempfile.gettempdir()).resolve(strict=True)
    with tempfile.TemporaryDirectory(dir=canonical_tmp) as temporary:
        transfer = Path(temporary) / "transfer"
        transfer.mkdir()
        consumer_path = transfer / "split_consumer.py"
        consumer_path.write_bytes(consumer_source)
        marker = Path(temporary) / marker_name
        protocol = (
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n"
        ).encode()
        protocol_path = transfer / "split_protocol.py"
        protocol_path.write_bytes(protocol)
        request_path = transfer / "split-consumer-request.json"
        request = {
            "harness": {
                "consumer_file": consumer_path.name,
                "consumer_sha256": digest(consumer_source),
                "protocol_file": protocol_path.name,
                "protocol_sha256": "0" * 64,
            }
        }
        request_path.write_text(json.dumps(request), encoding="utf-8")
        consumer = load_consumer(consumer_path)
        arguments = Namespace(
            transfer_root=str(transfer),
            request=str(request_path),
            request_sha256=digest(request_path.read_bytes()),
        )
        with pytest.raises(ValueError, match="split protocol differs"):
            consumer._load_pinned_protocol(arguments)
        assert not marker.exists(), "protocol bytes executed before their external pin passed"


def test_worker_loads_exact_protocol_after_request_and_byte_pins_pass() -> None:
    consumer_source = (Q2_SOURCE / "split_consumer.py").read_bytes()
    protocol_source = (Q2_SOURCE / "split_protocol.py").read_bytes()
    canonical_tmp = Path(tempfile.gettempdir()).resolve(strict=True)
    with tempfile.TemporaryDirectory(dir=canonical_tmp) as temporary:
        transfer = Path(temporary) / "transfer"
        transfer.mkdir()
        consumer_path = transfer / "split_consumer.py"
        consumer_path.write_bytes(consumer_source)
        protocol_path = transfer / "split_protocol.py"
        protocol_path.write_bytes(protocol_source)
        request_path = transfer / "split-consumer-request.json"
        request = {
            "harness": {
                "consumer_file": consumer_path.name,
                "consumer_sha256": digest(consumer_source),
                "protocol_file": protocol_path.name,
                "protocol_sha256": digest(protocol_source),
            }
        }
        request_path.write_text(json.dumps(request), encoding="utf-8")
        consumer = load_consumer(consumer_path)
        arguments = Namespace(
            transfer_root=str(transfer),
            request=str(request_path),
            request_sha256=digest(request_path.read_bytes()),
        )
        consumer._load_pinned_protocol(arguments)
        assert consumer.REQUEST_SCHEMA == "policyos.e02.q2.split-consumer-request.v2"
        cache = transfer / "__pycache__"
        assert not list(cache.glob("split_protocol.*.pyc")) if cache.exists() else True


def test_sdist_inventory_uses_hatchling_default_inputs_and_ignores_vcs_exclusions() -> None:
    from hatchling.builders.sdist import SdistBuilder

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        product = Path(state["product"])
        (product / ".gitignore").write_text("/production_data/\n", encoding="utf-8")
        (product / "README.md").write_text("fixture readme\n", encoding="utf-8")
        (product / "LICENSE").write_text("fixture license\n", encoding="utf-8")
        (product / "hatch_build.py").write_text("# fixture build script\n", encoding="utf-8")
        (product / "production_data").mkdir()
        (product / "production_data/secret.json").write_text('{"secret":true}\n', encoding="utf-8")
        hatch = product / "hatch.toml"
        hatch.write_text(
            hatch.read_text(encoding="utf-8").replace(
                'include = ["data/owned/g-resource.yaml"]',
                'include = ["data/owned/g-resource.yaml", "production_data"]',
            ),
            encoding="utf-8",
        )
        (product / "pyproject.toml").write_text(
            '[project]\nname="polisyos"\nversion="0.0.0"\nreadme="README.md"\n',
            encoding="utf-8",
        )
        builder = SdistBuilder(str(product))
        build_data = builder.get_default_build_data()
        builder.set_build_data_defaults(build_data)
        assert builder.get_build_hooks(str(product / "_build" / "dist")) == {}
        with builder.config.set_build_data(build_data):
            forced = list(builder.recurse_forced_files(builder.config.get_force_include()))
            assert not builder.config.include_path("production_data/secret.json", is_package=False)
            actual_producer_files = list(builder.recurse_included_files())
        producer_default_sources = {
            Path(item.path).relative_to(product).as_posix() for item in forced
        }
        assert {
            ".gitignore",
            "pyproject.toml",
            "hatch.toml",
            "hatch_build.py",
            "README.md",
            "LICENSE",
        } <= producer_default_sources

        inventory = build_source_inventory(
            product, manifest, expected_commit=state["source"], expected_tree=state["tree"]
        )
        source_rows = {row["source"]: row for row in inventory["sdist_source_rows"]}
        assert "production_data/secret.json" not in source_rows
        assert producer_default_sources <= source_rows.keys()
        inventory_pairs = {(row["source"], row["wheel"]) for row in inventory["sdist_source_rows"]}
        actual_pairs = {
            (
                Path(item.path).relative_to(product).as_posix(),
                item.distribution_path,
            )
            for item in actual_producer_files
        }
        assert inventory_pairs == actual_pairs
        for source in producer_default_sources:
            raw = (product / source).read_bytes()
            assert source_rows[source]["bytes"] == len(raw)
            assert source_rows[source]["sha256"] == digest(raw)


def test_sdist_inventory_rejects_force_include_of_vcs_excluded_production_data() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        product = Path(state["product"])
        (product / ".gitignore").write_text("/production_data/\n", encoding="utf-8")
        secret = product / "production_data/secret.json"
        secret.parent.mkdir()
        secret.write_text('{"secret":true}\n', encoding="utf-8")
        hatch = product / "hatch.toml"
        hatch.write_text(
            hatch.read_text(encoding="utf-8")
            + "\n[build.targets.sdist.force-include]\n"
            + '"production_data/secret.json" = "production_data/secret.json"\n',
            encoding="utf-8",
        )
        with pytest.raises(SplitProtocolError, match=r"excluded|ignored|protected"):
            build_source_inventory(
                product, manifest, expected_commit=state["source"], expected_tree=state["tree"]
            )


def test_sdist_inventory_matches_hatchling_negated_file_below_excluded_directory() -> None:
    from hatchling.builders.sdist import SdistBuilder

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        product = Path(state["product"])
        generated = product / "docs/generated"
        generated.mkdir(parents=True)
        (generated / "keep.py").write_text("kept by negation\n", encoding="utf-8")
        (generated / "drop.py").write_text("still excluded\n", encoding="utf-8")
        (product / ".gitignore").write_text(
            "docs/generated/**\n!docs/generated/keep.py\n", encoding="utf-8"
        )
        hatch = product / "hatch.toml"
        hatch.write_text(
            hatch.read_text(encoding="utf-8").replace(
                'include = ["data/owned/g-resource.yaml"]',
                'include = ["data/owned/g-resource.yaml", "docs"]',
            ),
            encoding="utf-8",
        )

        builder = SdistBuilder(str(product))
        build_data = builder.get_default_build_data()
        builder.set_build_data_defaults(build_data)
        with builder.config.set_build_data(build_data):
            assert builder.config.skip_excluded_dirs is False
            actual_pairs = {
                (
                    Path(item.path).relative_to(product).as_posix(),
                    item.distribution_path,
                )
                for item in builder.recurse_included_files()
            }

        inventory = build_source_inventory(
            product, manifest, expected_commit=state["source"], expected_tree=state["tree"]
        )
        inventory_pairs = {(row["source"], row["wheel"]) for row in inventory["sdist_source_rows"]}
        assert inventory_pairs == actual_pairs
        assert ("docs/generated/keep.py", "docs/generated/keep.py") in inventory_pairs
        assert not any(source == "docs/generated/drop.py" for source, _ in inventory_pairs)


def test_sdist_inventory_obeys_hatchling_skip_excluded_dirs_setting() -> None:
    from hatchling.builders.sdist import SdistBuilder

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        product = Path(state["product"])
        generated = product / "docs/generated"
        generated.mkdir(parents=True)
        (generated / "keep.py").write_text("negated but pruned\n", encoding="utf-8")
        (generated / "drop.py").write_text("excluded\n", encoding="utf-8")
        (product / ".gitignore").write_text(
            "docs/generated/**\n!docs/generated/keep.py\n", encoding="utf-8"
        )
        hatch = product / "hatch.toml"
        hatch.write_text(
            hatch.read_text(encoding="utf-8").replace(
                'include = ["data/owned/g-resource.yaml"]',
                'include = ["data/owned/g-resource.yaml", "docs"]\nskip-excluded-dirs = true',
            ),
            encoding="utf-8",
        )

        builder = SdistBuilder(str(product))
        build_data = builder.get_default_build_data()
        builder.set_build_data_defaults(build_data)
        with builder.config.set_build_data(build_data):
            assert builder.config.skip_excluded_dirs is True
            actual_pairs = {
                (
                    Path(item.path).relative_to(product).as_posix(),
                    item.distribution_path,
                )
                for item in builder.recurse_included_files()
            }

        inventory = build_source_inventory(
            product, manifest, expected_commit=state["source"], expected_tree=state["tree"]
        )
        inventory_pairs = {(row["source"], row["wheel"]) for row in inventory["sdist_source_rows"]}
        assert inventory_pairs == actual_pairs
        assert not any(source.startswith("docs/generated/") for source, _ in inventory_pairs)


def test_sdist_inventory_keeps_excluded_symlink_directory_out_of_selected_members() -> None:
    from hatchling.builders.sdist import SdistBuilder

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        product = Path(state["product"])
        external = root / "external-docs"
        external.mkdir()
        (external / "ignored.py").write_text("excluded symlink target\n", encoding="utf-8")
        docs = product / "docs"
        docs.mkdir()
        (docs / "excluded-link").symlink_to(external, target_is_directory=True)
        (product / ".gitignore").write_text("docs/excluded-link/**\n", encoding="utf-8")
        hatch = product / "hatch.toml"
        hatch.write_text(
            hatch.read_text(encoding="utf-8").replace(
                'include = ["data/owned/g-resource.yaml"]',
                'include = ["data/owned/g-resource.yaml", "docs"]',
            ),
            encoding="utf-8",
        )

        builder = SdistBuilder(str(product))
        build_data = builder.get_default_build_data()
        builder.set_build_data_defaults(build_data)
        with builder.config.set_build_data(build_data):
            assert builder.config.skip_excluded_dirs is False
            actual_sources = {
                Path(item.path).relative_to(product).as_posix()
                for item in builder.recurse_included_files()
            }
        assert not any(source.startswith("docs/excluded-link/") for source in actual_sources)

        inventory = build_source_inventory(
            product, manifest, expected_commit=state["source"], expected_tree=state["tree"]
        )
        inventory_sources = {row["source"] for row in inventory["sdist_source_rows"]}
        assert inventory_sources == actual_sources


def test_sdist_inventory_rejects_selected_file_under_symlink_directory() -> None:
    from hatchling.builders.sdist import SdistBuilder

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        product = Path(state["product"])
        external = root / "external-docs"
        external.mkdir()
        (external / "selected.py").write_text("selected through symlink\n", encoding="utf-8")
        docs = product / "docs"
        docs.mkdir()
        (docs / "selected-link").symlink_to(external, target_is_directory=True)
        hatch = product / "hatch.toml"
        hatch.write_text(
            hatch.read_text(encoding="utf-8").replace(
                'include = ["data/owned/g-resource.yaml"]',
                'include = ["data/owned/g-resource.yaml", "docs"]',
            ),
            encoding="utf-8",
        )

        builder = SdistBuilder(str(product))
        build_data = builder.get_default_build_data()
        builder.set_build_data_defaults(build_data)
        with builder.config.set_build_data(build_data):
            actual_sources = {
                Path(item.path).relative_to(product).as_posix()
                for item in builder.recurse_included_files()
            }
        assert "docs/selected-link/selected.py" in actual_sources

        with pytest.raises(SplitProtocolError, match="symlink"):
            build_source_inventory(
                product, manifest, expected_commit=state["source"], expected_tree=state["tree"]
            )


def test_sdist_inventory_skips_excluded_symlink_and_special_file_before_type_check() -> None:
    import os

    from hatchling.builders.sdist import SdistBuilder

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        product = Path(state["product"])
        docs = product / "docs"
        docs.mkdir()
        target = product / "outside-doc-tree.txt"
        target.write_text("not selected\n", encoding="utf-8")
        (docs / "ignored-link.txt").symlink_to(target)
        os.mkfifo(docs / "ignored-special.fifo")
        os.mkfifo(product / "LICENSE")
        (product / ".gitignore").write_text(
            "docs/ignored-link.txt\ndocs/ignored-special.fifo\n", encoding="utf-8"
        )
        hatch = product / "hatch.toml"
        hatch.write_text(
            hatch.read_text(encoding="utf-8").replace(
                'include = ["data/owned/g-resource.yaml"]',
                'include = ["data/owned/g-resource.yaml", "docs"]',
            ),
            encoding="utf-8",
        )

        builder = SdistBuilder(str(product))
        build_data = builder.get_default_build_data()
        builder.set_build_data_defaults(build_data)
        with builder.config.set_build_data(build_data):
            actual_producer_files = list(builder.recurse_included_files())

        inventory = build_source_inventory(
            product, manifest, expected_commit=state["source"], expected_tree=state["tree"]
        )
        inventory_pairs = {(row["source"], row["wheel"]) for row in inventory["sdist_source_rows"]}
        actual_pairs = {
            (Path(item.path).relative_to(product).as_posix(), item.distribution_path)
            for item in actual_producer_files
        }
        assert inventory_pairs == actual_pairs
        assert not any(source.startswith("docs/") for source, _ in inventory_pairs)
        assert inventory["project_metadata"]["license_rows"] == []


def test_sdist_inventory_rejects_a_selected_symlink_after_membership_selection() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        product = Path(state["product"])
        docs = product / "docs"
        docs.mkdir()
        (product / "outside-doc-tree.txt").write_text("selected alias\n", encoding="utf-8")
        (docs / "selected-link.txt").symlink_to(product / "outside-doc-tree.txt")
        hatch = product / "hatch.toml"
        hatch.write_text(
            hatch.read_text(encoding="utf-8").replace(
                'include = ["data/owned/g-resource.yaml"]',
                'include = ["data/owned/g-resource.yaml", "docs"]',
            ),
            encoding="utf-8",
        )

        with pytest.raises(SplitProtocolError, match="symlink"):
            build_source_inventory(
                product, manifest, expected_commit=state["source"], expected_tree=state["tree"]
            )


def test_sdist_inventory_rejects_a_selected_nonregular_file_after_membership_selection() -> None:
    import os

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        product = Path(state["product"])
        docs = product / "docs"
        docs.mkdir()
        os.mkfifo(docs / "selected-special.fifo")
        hatch = product / "hatch.toml"
        hatch.write_text(
            hatch.read_text(encoding="utf-8").replace(
                'include = ["data/owned/g-resource.yaml"]',
                'include = ["data/owned/g-resource.yaml", "docs"]',
            ),
            encoding="utf-8",
        )

        with pytest.raises(SplitProtocolError, match="not a regular file"):
            build_source_inventory(
                product, manifest, expected_commit=state["source"], expected_tree=state["tree"]
            )


def test_project_metadata_rejects_a_selected_license_symlink() -> None:
    from hatchling.builders.sdist import SdistBuilder

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        product = Path(state["product"])
        outside = product / "license-target.txt"
        outside.write_text("license source\n", encoding="utf-8")
        (product / "LICENSE").symlink_to(outside)
        builder = SdistBuilder(str(product))
        assert builder.metadata.core.license_files == ["LICENSE"]

        with pytest.raises(SplitProtocolError, match="symlink"):
            build_source_inventory(
                product, manifest, expected_commit=state["source"], expected_tree=state["tree"]
            )


def test_sdist_inventory_rejects_a_force_included_symlink() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        product = Path(state["product"])
        symlink = product / "data/owned/forced-link.yaml"
        symlink.symlink_to(product / "src/polisyos/__init__.py")
        hatch = product / "hatch.toml"
        hatch.write_text(
            hatch.read_text(encoding="utf-8")
            + "\n[build.targets.sdist.force-include]\n"
            + '"data/owned/forced-link.yaml" = "data/owned/forced-link.yaml"\n',
            encoding="utf-8",
        )

        with pytest.raises(SplitProtocolError, match="symlink"):
            build_source_inventory(
                product, manifest, expected_commit=state["source"], expected_tree=state["tree"]
            )


def test_inventory_rejects_dropped_hatchling_default_member_after_digest_refresh() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        state, manifest = fixture_product(root)
        product = Path(state["product"])
        (product / ".gitignore").write_text("/production_data/\n", encoding="utf-8")
        inventory = build_source_inventory(
            product, manifest, expected_commit=state["source"], expected_tree=state["tree"]
        )
        inventory["sdist_source_rows"] = [
            row for row in inventory["sdist_source_rows"] if row["source"] != ".gitignore"
        ]
        inventory["sdist_source_rows_sha256"] = digest(
            json.dumps(
                inventory["sdist_source_rows"],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        )
        with pytest.raises(SplitProtocolError, match="default or selected source membership"):
            validate_inventory(inventory)
