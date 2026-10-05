import sys
import tarfile
from io import BytesIO
from pathlib import Path

source=Path(sys.argv[1])
target=Path(sys.argv[2])
with tarfile.open(source,'r:gz') as original, tarfile.open(target,'w:gz') as tampered:
    for item in original.getmembers():
        payload=original.extractfile(item) if item.isfile() else None
        tampered.addfile(item,payload)
    data=b'// raw-file tamper with original package exports unchanged\n'
    item=tarfile.TarInfo('package/runtimeApiClient.js')
    item.size=len(data)
    item.mode=0o644
    tampered.addfile(item,BytesIO(data))
print(target)
