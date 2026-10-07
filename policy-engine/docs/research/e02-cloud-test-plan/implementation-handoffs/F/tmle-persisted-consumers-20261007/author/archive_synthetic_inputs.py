"""Retain the actual synthetic CAS bytes used by the author removal probes."""
import hashlib
import json
from pathlib import Path
import tarfile

scratch = Path(__file__).resolve().parent
packet_path = scratch / "native/tmle-consumers0/producer-packet.json"
packet = json.loads(packet_path.read_bytes())
cas = Path(packet["cas_root"])
files = sorted(path for path in cas.rglob("*") if path.is_file())
assert not any(path.is_symlink() for path in files)
records = []
archive = scratch / "native-cas-input.tar.gz"
with tarfile.open(archive, "w:gz") as output:
    for path in files:
        raw = path.read_bytes()
        relative = path.relative_to(cas).as_posix()
        output.add(path, arcname=relative, recursive=False)
        records.append({"path": relative, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
result = {"input_purpose": "actual synthetic observation/result/report/envelope/evidence and adversarial simulation CAS; no production inputs or tracked source copies", "cas_root_original": str(cas), "producer_packet": {"path": str(packet_path), "bytes": len(packet_path.read_bytes()), "sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest()}, "files": records, "archive": {"path": str(archive), "bytes": len(archive.read_bytes()), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}, "replay": "Extract into unique scratch, replace only packet cas_root, invoke retained removal replayer with exact candidate test path and native source PYTHONPATH."}
(scratch / "cas-input-manifest.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"retained_cas_files": len(files), "archive": result["archive"]}))
