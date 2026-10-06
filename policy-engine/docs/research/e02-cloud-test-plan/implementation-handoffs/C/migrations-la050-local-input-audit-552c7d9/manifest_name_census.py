"""Inventory manifest-named JSON/YAML metadata under the documented local input root."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path("/Users/deniskopylov/polisyos/policy-engine/production_data")
REQUIRED_DATASET_FIELDS = {
    "dataset_name",
    "source",
    "license",
    "raw_hash",
    "schema_version",
    "row_count",
    "pii_flags",
    "quality",
}
OPTIONAL_DATASET_FIELDS = {"reconciliation", "created_at"}
FIND_ARGV = [
    "find",
    str(ROOT),
    "-type",
    "f",
    "(",
    "-iname",
    "*manifest*.json",
    "-o",
    "-iname",
    "*manifest*.yaml",
    "-o",
    "-iname",
    "*manifest*.yml",
    ")",
    "-print",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    process = subprocess.run(FIND_ARGV, check=True, capture_output=True, text=True)
    paths = sorted(Path(line) for line in process.stdout.splitlines())
    rows = []
    for path in paths:
        raw = path.read_bytes()
        row = {
            "path": str(path),
            "relative_path": str(path.relative_to(ROOT)),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "format": path.suffix.lower().lstrip("."),
        }
        if path.suffix.lower() == ".json":
            document = json.loads(raw)
            row["top_level_type"] = type(document).__name__
            if isinstance(document, dict):
                keys = set(document)
                row["top_level_keys"] = sorted(keys)
                row["metadata"] = {
                    key: document[key]
                    for key in ("kind", "schema_version", "dataset_name")
                    if key in document
                    and isinstance(document[key], (str, int, float, bool, type(None)))
                }
                row["dataset_field_name_shape"] = (
                    REQUIRED_DATASET_FIELDS <= keys
                    and keys <= REQUIRED_DATASET_FIELDS | OPTIONAL_DATASET_FIELDS
                )
            else:
                row["top_level_keys"] = None
                row["metadata"] = {}
                row["dataset_field_name_shape"] = False
        else:
            row["top_level_type"] = "not_parsed_yaml"
            row["top_level_keys"] = None
            row["metadata"] = {}
            row["dataset_field_name_shape"] = False
        rows.append(row)
    print(
        json.dumps(
            {
                "scope": "Manifest-named JSON/YAML paths under the documented original production_data root only.",
                "not_scanned": [
                    "JSONL payloads",
                    "database rows",
                    "non-manifest-named files",
                    "external/archive roots not identified by the tracked owner map",
                ],
                "find_argv": FIND_ARGV,
                "candidate_count": len(rows),
                "dataset_field_name_shape_count": sum(
                    bool(row["dataset_field_name_shape"]) for row in rows
                ),
                "files": rows,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
