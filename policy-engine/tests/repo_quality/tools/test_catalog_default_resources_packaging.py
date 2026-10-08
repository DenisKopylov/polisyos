"""Use current native Hatch config to prove the four exact resource projections.

The bounded backend fixture contains the actual resolver, original resource files,
current project metadata/config and every existing forced resource. It does not
rebuild a complete PolicyOS source archive or replace the final installed wave.
"""

from __future__ import annotations

import shutil
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest
from hatchling.builders.sdist import SdistBuilder
from hatchling.builders.wheel import WheelBuilder

PRODUCT = Path(__file__).resolve().parents[3]
ORIGINALS = PRODUCT / "data" / "dataset_catalog"
RESOURCE_PREFIX = "polisyos/data_forge/domains/catalog/_resources/"


def _project(destination):
    destination.mkdir()
    for name in ["pyproject.toml", "hatch.toml"]:
        shutil.copyfile(PRODUCT / name, destination / name)
    config = tomllib.loads((destination / "hatch.toml").read_text())
    helper = "src/polisyos/data_forge/domains/catalog/_resources.py"
    sources = [helper, *config["build"]["targets"]["wheel"]["force-include"]]
    for relative in sources:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PRODUCT / relative, target)
    (destination / "tools").mkdir()
    (destination / "tools" / "__init__.py").write_bytes(b'"""Bounded Hatch fixture namespace."""\n')
    return destination


def _assert_projection(wheel):
    originals = {path.name: path.read_bytes() for path in ORIGINALS.glob("*.yaml")}
    assert len(originals) == 4
    with zipfile.ZipFile(wheel) as archive:
        projected = {
            name.removeprefix(RESOURCE_PREFIX): archive.read(name)
            for name in archive.namelist()
            if name.startswith(RESOURCE_PREFIX)
        }
    assert projected == originals


def test_native_current_hatch_preserves_all_four_original_resources_and_rebuilt_wheel(tmp_path):
    project = _project(tmp_path / "native")
    config = tomllib.loads((project / "hatch.toml").read_text())
    force = config["build"]["targets"]["wheel"]["force-include"]
    original_paths = {str(path.relative_to(PRODUCT)): path for path in ORIGINALS.glob("*.yaml")}
    selected = {
        source: target for source, target in force.items() if target.startswith(RESOURCE_PREFIX)
    }
    assert selected == {
        source: RESOURCE_PREFIX + path.name for source, path in original_paths.items()
    }
    assert set(original_paths) <= set(config["build"]["targets"]["sdist"]["include"])
    wheel = Path(next(WheelBuilder(str(project)).build(versions=["standard"])))
    _assert_projection(wheel)
    sdist = Path(next(SdistBuilder(str(project)).build()))
    extracted = tmp_path / "rebuilt"
    with tarfile.open(sdist) as archive:
        for source, path in original_paths.items():
            (member,) = [m for m in archive.getmembers() if m.name.endswith("/" + source)]
            stream = archive.extractfile(member)
            assert stream is not None and stream.read() == path.read_bytes()
        archive.extractall(extracted, filter="data")
    (rebuilt,) = extracted.iterdir()
    rebuilt_wheel = Path(next(WheelBuilder(str(rebuilt)).build(versions=["standard"])))
    _assert_projection(rebuilt_wheel)


@pytest.mark.parametrize("name", sorted(path.name for path in ORIGINALS.glob("*.yaml")))
def test_removing_one_projection_retains_markers_but_fails_the_byte_admission_oracle(
    tmp_path, name
):
    project = _project(tmp_path / "missing-projection")
    path = project / "hatch.toml"
    source = "data/dataset_catalog/" + name
    line = f'"{source}" = "{RESOURCE_PREFIX}{name}"\n'
    body = path.read_text()
    assert line in body
    path.write_text(body.replace(line, ""))
    assert source in path.read_text()  # The original sdist declaration remains.
    wheel = Path(next(WheelBuilder(str(project)).build(versions=["standard"])))
    with pytest.raises(AssertionError):
        _assert_projection(wheel)


def test_changed_resource_bytes_fail_admission_even_with_all_paths_and_yaml_shape(tmp_path):
    project = _project(tmp_path / "altered-content")
    path = project / "data" / "dataset_catalog" / "proxy_metric_alignments.yaml"
    body = path.read_text()
    assert "proxy_penalty: 0.15" in body
    path.write_text(body.replace("proxy_penalty: 0.15", "proxy_penalty: 0.25"))
    wheel = Path(next(WheelBuilder(str(project)).build(versions=["standard"])))
    with pytest.raises(AssertionError):
        _assert_projection(wheel)
