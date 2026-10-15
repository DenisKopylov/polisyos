"""Use current native Hatch config to prove runtime-owned resource projections.

The bounded backend fixture contains the actual resolver, original resource files,
current project metadata/config and every existing forced resource. It does not
rebuild a complete PolicyOS source archive or replace the final installed wave.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest
from hatchling.builders.sdist import SdistBuilder
from hatchling.builders.wheel import WheelBuilder

PRODUCT = Path(__file__).resolve().parents[3]
RESOURCE_CONTRACT = PRODUCT / "tools/quality/validation/packaged_resource_contract.py"


def _runtime_inventory():
    result = subprocess.run(
        [sys.executable, "-I", str(RESOURCE_CONTRACT), "source", "--product-root", str(PRODUCT)],
        cwd=PRODUCT,
        capture_output=True,
        check=False,
        text=True,
        shell=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    inventory = json.loads(result.stdout)
    return inventory


def _runtime_resources():
    return _runtime_inventory()["assets"]


def _project(destination, assets):
    destination.mkdir()
    for name in ["pyproject.toml", "hatch.toml"]:
        shutil.copyfile(PRODUCT / name, destination / name)
    config = tomllib.loads((destination / "hatch.toml").read_text())
    helper = "src/polisyos/data_forge/domains/catalog/_resources.py"
    expected_mapping = {row["source"]: row["wheel"] for row in assets}
    assert config["build"]["targets"]["wheel"]["force-include"] == expected_mapping
    sources = [helper, *expected_mapping]
    for relative in sources:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PRODUCT / relative, target)
    (destination / "tools").mkdir()
    (destination / "tools" / "__init__.py").write_bytes(b'"""Bounded Hatch fixture namespace."""\n')
    return destination


def _assert_projection(wheel, assets):
    expected = {row["wheel"]: (PRODUCT / row["source"]).read_bytes() for row in assets}
    target_roots = {target.rsplit("/", 1)[0] + "/" for target in expected}
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        projected = {target: archive.read(target) for target in expected if target in names}
        for root in target_roots:
            assert {name for name in names if name.startswith(root) and not name.endswith("/")} == {
                target for target in expected if target.startswith(root)
            }
    assert projected == expected


def _assert_sdist(sdist, assets):
    with tarfile.open(sdist) as archive:
        members = archive.getmembers()
        regular = {member.name: member for member in members if member.isfile()}
        roots = {name.split("/", 1)[0] for name in regular}
        assert len(roots) == 1
        root = next(iter(roots))
        for row in assets:
            name = root + "/" + row["source"]
            assert name in regular
            stream = archive.extractfile(regular[name])
            assert stream is not None
            with stream:
                assert stream.read() == (PRODUCT / row["source"]).read_bytes()


def test_native_hatch_preserves_runtime_owned_resources_in_source_and_rebuilt_wheels(tmp_path):
    assets = _runtime_resources()
    project = _project(tmp_path / "native", assets)
    config = tomllib.loads((project / "hatch.toml").read_text())
    source_paths = {row["source"] for row in assets}
    assert source_paths <= set(config["build"]["targets"]["sdist"]["include"])
    wheel = Path(next(WheelBuilder(str(project)).build(versions=["standard"])))
    _assert_projection(wheel, assets)
    sdist = Path(next(SdistBuilder(str(project)).build()))
    _assert_sdist(sdist, assets)
    extracted = tmp_path / "rebuilt"
    with tarfile.open(sdist) as archive:
        archive.extractall(extracted, filter="data")
    (rebuilt,) = extracted.iterdir()
    rebuilt_wheel = Path(next(WheelBuilder(str(rebuilt)).build(versions=["standard"])))
    _assert_projection(rebuilt_wheel, assets)


def test_removing_each_runtime_owned_projection_retains_sdist_markers_but_fails_the_oracle(
    tmp_path,
):
    inventory = _runtime_inventory()
    assets = inventory["assets"]
    target_roots = {row["wheel"].rsplit("/", 1)[0] + "/" for row in assets}
    for index, resource_root in enumerate(sorted(target_roots)):
        row = next(row for row in assets if row["wheel"].startswith(resource_root))
        project = _project(tmp_path / f"missing-projection-{index}", assets)
        path = project / "hatch.toml"
        source = row["source"]
        line = f'"{source}" = "{row["wheel"]}"\n'
        body = path.read_text()
        assert line in body
        path.write_text(body.replace(line, ""))
        assert f'  "{source}",' in path.read_text()  # The sdist declaration remains.
        wheel = Path(next(WheelBuilder(str(project)).build(versions=["standard"])))
        with pytest.raises(AssertionError):
            _assert_projection(wheel, assets)


def test_changed_resource_bytes_fail_admission_even_with_all_paths(tmp_path):
    assets = _runtime_resources()
    project = _project(tmp_path / "altered-content", assets)
    path = project / assets[0]["source"]
    path.write_bytes(path.read_bytes() + b"\n# altered bytes\n")
    wheel = Path(next(WheelBuilder(str(project)).build(versions=["standard"])))
    with pytest.raises(AssertionError):
        _assert_projection(wheel, assets)


def test_sdist_omission_retains_wheel_projection_but_fails_runtime_owner_oracle(tmp_path):
    assets = _runtime_resources()
    row = assets[0]
    project = _project(tmp_path / "missing-sdist-source", assets)
    path = project / "hatch.toml"
    body = path.read_text()
    marker = f'  "{row["source"]}",\n'
    assert marker in body
    path.write_text(body.replace(marker, "", 1))
    assert f'"{row["source"]}" = "{row["wheel"]}"' in path.read_text()
    sdist = Path(next(SdistBuilder(str(project)).build()))
    with pytest.raises(AssertionError):
        _assert_sdist(sdist, assets)
