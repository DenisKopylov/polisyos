"""Strictly validate private current-version migration outputs with installed Fabric DTO."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import sys
from pathlib import Path

from polisyos.fabric.identity.manifest import DatasetManifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    distribution = importlib.metadata.distribution("policy-engine")
    site_packages = Path(distribution.locate_file("")).resolve()
    module = importlib.import_module("polisyos.fabric.identity.manifest")
    module_path = Path(module.__file__).resolve()
    if not module_path.is_relative_to(site_packages):
        raise SystemExit("DatasetManifest import did not resolve from installed site-packages.")
    rows = []
    for name in ("agents", "entity_resolution", "interactions", "macro"):
        input_path = args.input_dir / f"{name}-manifest.json"
        output_path = args.output_dir / f"{name}-manifest.json"
        input_data = json.loads(input_path.read_bytes())
        output_data = json.loads(output_path.read_bytes())
        model = DatasetManifest.model_validate_json(output_path.read_bytes())
        row = {
            "name": name,
            "dataset_name": model.dataset_name,
            "schema_version": model.schema_version,
            "input_bytes": input_path.stat().st_size,
            "input_sha256": _sha256(input_path),
            "output_bytes": output_path.stat().st_size,
            "output_sha256": _sha256(output_path),
            "byte_identical": input_path.read_bytes() == output_path.read_bytes(),
            "json_semantically_equal": input_data == output_data,
            "strict_dto_accepted": True,
            "dto_dump_exclude_unset_matches_output": (
                model.model_dump(mode="json", exclude_unset=True) == output_data
            ),
        }
        if not row["json_semantically_equal"]:
            raise SystemExit(f"Current-version CLI changed JSON semantics for {name}.")
        if not row["dto_dump_exclude_unset_matches_output"]:
            raise SystemExit(f"Installed DTO round-trip differs for {name}.")
        rows.append(row)
    print(
        json.dumps(
            {
                "distribution_name": "policy-engine",
                "distribution_version": distribution.version,
                "site_packages": str(site_packages),
                "module_origin": str(module_path),
                "module_sha256": _sha256(module_path),
                "candidate_source_checkout_on_sys_path": any(
                    "e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/mig-004ae11/source"
                    in entry
                    for entry in sys.path
                ),
                "cwd": str(Path.cwd()),
                "results": rows,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
