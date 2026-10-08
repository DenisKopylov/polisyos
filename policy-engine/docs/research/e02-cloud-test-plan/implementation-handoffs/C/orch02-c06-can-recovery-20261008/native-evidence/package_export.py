from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path


if __name__=='__main__':
    out=Path('/workspace/orch02-native-c06/packages');out.mkdir(exist_ok=False)
    rows=[]
    for role,repo,sha in (
        ('dfk',Path('/workspace/orch02-c06-dfk'),'cbbfffd367fe283813a8177575d26c0ede8d20c4'),
        ('can',Path('/workspace/orch02-c06-can'),'4901e26841e2be0ae6ef393754abed5cafb1e2d4'),
    ):
        artifact=out/role;artifact.mkdir()
        tarbytes=subprocess.run(['git','archive','--format=tar',sha,'policy-engine'],cwd=repo,capture_output=True,check=True).stdout
        path=artifact/'source.tar';path.write_bytes(tarbytes)
        with tarfile.open(fileobj=io.BytesIO(tarbytes)) as tar:
            members=tar.getmembers()
            tar.extractall(path=artifact/'source',filter='data')
        tree=subprocess.run(['git','ls-tree','-r','-z',sha,'policy-engine'],cwd=repo,capture_output=True,check=True).stdout
        (artifact/'git-tree.raw').write_bytes(tree)
        rows.append({'role':role,'source_commit':sha,'repo':str(repo),'tree_raw_sha256':hashlib.sha256(tree).hexdigest(),'source_archive':str(path),'source_archive_sha256':hashlib.sha256(tarbytes).hexdigest(),'archive_members':len(members),'source_directory':str(artifact/'source/policy-engine')})
    (out/'source-manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps(rows,indent=2))
