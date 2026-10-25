from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

PRODUCT = next(
    parent for parent in Path(__file__).resolve().parents if parent.name == "policy-engine"
)
CANDIDATE_ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = CANDIDATE_ROOT / "tools/quality/validation/packaged_resource_contract.py"
if not TOOL_PATH.is_file():
    TOOL_PATH = PRODUCT / "tools/quality/validation/packaged_resource_contract.py"


def _tool_module():
    spec = importlib.util.spec_from_file_location(
        "packaged_resource_contract_under_test", TOOL_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_inventory() -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(TOOL_PATH),
            "source",
            "--product-root",
            str(PRODUCT),
        ],
        cwd=PRODUCT,
        capture_output=True,
        check=False,
        text=True,
        shell=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def package_contract():
    inventory = _source_inventory()
    config = tomllib.loads((PRODUCT / "hatch.toml").read_text(encoding="utf-8"))
    targets = config["build"]["targets"]
    return (
        _tool_module(),
        inventory,
        targets["wheel"]["force-include"],
    )


def test_source_inventory_discovers_openapi_resource_from_actual_reader(package_contract):
    _validator, inventory, _force_include = package_contract
    owners = inventory["owners"]
    rows = owners["openapi_example_resources"]
    assert rows
    assets = {(asset["source"], asset["wheel"]): asset for asset in inventory["assets"]}
    for owner in rows:
        asset = assets[(owner["source"], owner["wheel"])]
        source = PRODUCT / asset["source"]
        payload = source.read_bytes()
        assert len(payload) == asset["bytes"]
        assert hashlib.sha256(payload).hexdigest() == asset["sha256"]


def test_current_hatch_projection_matches_runtime_owned_inventory(package_contract):
    validator, inventory, force_include = package_contract
    validator.validate_manifest_resources(inventory, inventory["assets"], force_include)


def test_owner_inventory_oracle_rejects_each_removed_or_corrupt_asset(package_contract):
    validator, inventory, force_include = package_contract
    assets = inventory["assets"]
    validator.validate_manifest_resources(inventory, assets, force_include)

    for index, asset in enumerate(assets):
        without_manifest_row = assets[:index] + assets[index + 1 :]
        with pytest.raises(validator.ResourceContractError):
            validator.validate_manifest_resources(inventory, without_manifest_row, force_include)

        corrupt_manifest = [dict(row) for row in assets]
        corrupt_manifest[index]["sha256"] = "0" * 64
        with pytest.raises(validator.ResourceContractError):
            validator.validate_manifest_resources(inventory, corrupt_manifest, force_include)

        without_wheel_target = dict(force_include)
        without_wheel_target.pop(asset["source"])
        with pytest.raises(validator.ResourceContractError):
            validator.validate_manifest_resources(inventory, assets, without_wheel_target)
