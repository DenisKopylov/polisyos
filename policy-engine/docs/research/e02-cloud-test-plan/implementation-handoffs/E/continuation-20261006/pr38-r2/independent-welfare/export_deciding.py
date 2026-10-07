import hashlib
import json
import sys
from pathlib import Path

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes


def _write_stdout(*values: object, flush: bool = False) -> None:
    """Emit the existing CLI text and optionally flush without logging side effects."""
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


ROOT = Path("/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer/welfare")
original = json.loads((ROOT / "independent-native-origins-artifacts.json").read_text())
case = original["results"][0]
store = FileSystemCAS(case["cas"])
refs = {k: v for k, v in case.items() if k.endswith("_ref")}
output = {
    "source_candidate": "884681db485b7466b183a206f83bbe0635f86ca3",
    "source_tree": "b9cdce22cd8af3bee3cda176207242a8381cbe1b",
    "data_identity": {
        "atoms": [0.0, 1.0],
        "weights": [3.0, 1.0],
        "row_axis": "independent_row",
        "N": 128,
        "seed": 31415,
        "PE": 2.0,
        "GE": "numpy.linalg.inv(I-A)",
    },
    "fresh_filesystem_cas": str(store.root),
    "artifacts": {},
}
for label, ref in refs.items():
    aid = ref if isinstance(ref, str) else ref["artifact_id"]
    raw = store.get_bytes(aid)
    manifest = store.get_manifest(aid)
    if not (store.verify(aid).ok):
        raise AssertionError
    output["artifacts"][label] = {
        "ref": ref,
        "bytes_sha256": hashlib.sha256(raw).hexdigest(),
        "manifest": manifest.model_dump(mode="json"),
        "content": from_canonical_bytes(raw),
    }
(ROOT / "native-ge-deciding-artifacts.json").write_text(json.dumps(output, indent=2) + "\n")
_write_stdout(
    json.dumps(
        {
            "source_candidate": output["source_candidate"],
            "artifacts": list(output["artifacts"]),
            "all_fresh_cas_verify": True,
            "deciding_output_bytes": (ROOT / "native-ge-deciding-artifacts.json").stat().st_size,
        },
        indent=2,
    )
)
