"""Verify complete selected bytes and the one lossless compressed witness."""

import gzip
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
selection = json.loads((HERE / "transfer-selection.json").read_bytes())
decoded = 0
aliases = 0
for row in selection["items"]:
    body = Path(row["path"]).read_bytes()
    assert len(body) == row["bytes"]
    assert hashlib.sha256(body).hexdigest() == row["sha256"]
    for alias in row.get("byte_identical_alias_paths", []):
        assert Path(alias).read_bytes() == body
        aliases += 1
    if row.get("encoding") == "gzip":
        raw = gzip.decompress(body)
        assert len(raw) == row["decoded_bytes"]
        assert hashlib.sha256(raw).hexdigest() == row["decoded_sha256"]
        assert raw == Path(row["decoded_path_original"]).read_bytes()
        witness = json.loads(raw)
        assert witness["check"] == "PASS"
        assert witness["pid"] != witness["reader_pid"]
        assert witness["source_guard_before"] == witness["source_guard_after"]
        decoded += 1
print(json.dumps({"check": "PASS", "unique_stored_files": len(selection["items"]), "byte_identical_alias_paths": aliases, "lossless_gzip_count": decoded, "source_sha": selection["source_sha"], "scientific_reexecution": False}, sort_keys=True))
