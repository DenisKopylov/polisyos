"""Run real nonregular CAS byte reads in a separately importable OS process."""

import os
import socket
import sys
from pathlib import Path

from polisyos.core.artifacts import FileSystemCAS, PutOptions

root, kind = Path(sys.argv[1]), sys.argv[2]
store = FileSystemCAS(root, ownership_enforced=False)
ref = store.put_bytes(b"special boundary", PutOptions(kind="test", media_type="text/plain"))
blob, manifest = store._paths(ref.artifact_id)
original_manifest = manifest.read_bytes()
referent = root / "original.blob"
blob.rename(referent)
listener = None
if kind == "symlink":
    blob.symlink_to(referent)
elif kind == "dangling":
    blob.symlink_to(root / "missing")
elif kind == "fifo":
    os.mkfifo(blob)
elif kind == "socket":
    listener = socket.socket(socket.AF_UNIX)
    os.chdir(blob.parent)
    listener.bind(blob.name)
else:
    raise ValueError(kind)
try:
    result = store.verify(ref)
    if result.ok or referent.read_bytes() != b"special boundary":
        raise RuntimeError("nonregular supplied member was accepted or referent changed")
    if manifest.read_bytes() != original_manifest:
        raise RuntimeError("verification mutated the manifest")
    print(f"PASS: {kind} refused by actual FileSystemCAS.verify; old bytes unchanged")
finally:
    if listener is not None:
        listener.close()
