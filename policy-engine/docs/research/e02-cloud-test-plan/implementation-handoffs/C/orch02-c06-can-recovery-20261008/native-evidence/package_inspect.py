from __future__ import annotations

import hashlib
import json
import tarfile
import tomllib
import zipfile
from pathlib import Path


BASE=Path('/workspace/orch02-native-c06/packages')


def inspect(role):
    artifact=BASE/role
    source=artifact/'source/policy-engine'
    config=tomllib.loads((source/'hatch.toml').read_text())
    force={destination:src for src,destination in config['build']['targets']['wheel'].get('force-include',{}).items()}
    source_rows=[]
    wheel=next((artifact/'dist').glob('*.whl'))
    with zipfile.ZipFile(wheel) as archive:
        wheel_rows=[]
        mismatches=[]
        for info in archive.infolist():
            data=archive.read(info)
            row={'path':info.filename,'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),'directory':info.is_dir()}
            wheel_rows.append(row)
            if info.is_dir() or '.dist-info/' in info.filename:
                continue
            sp=source/force.get(info.filename,('src/'+info.filename if info.filename.startswith('polisyos/') else info.filename))
            if not sp.is_file() or sp.read_bytes()!=data:
                mismatches.append({'member':info.filename,'source':str(sp)})
        assert not mismatches,mismatches
    sdist=next((artifact/'dist').glob('*.tar.gz'))
    with tarfile.open(sdist) as archive:
        sdist_rows=[]
        mismatches=[]
        for info in archive.getmembers():
            entry={'path':info.name,'size':info.size,'type':info.type.decode('ascii')}
            if info.isfile():
                data=archive.extractfile(info).read()
                entry['sha256']=hashlib.sha256(data).hexdigest()
                relative=Path(info.name).relative_to(Path(info.name).parts[0])
                sp=source/relative
                if relative.as_posix()!='PKG-INFO' and (not sp.is_file() or sp.read_bytes()!=data):
                    mismatches.append({'member':info.name,'source':str(sp)})
            sdist_rows.append(entry)
        assert not mismatches,mismatches
        rebuilt=artifact/'rebuilt-source'
        rebuilt.mkdir(exist_ok=False)
        archive.extractall(rebuilt,filter='data')
        rebuild_project=next(rebuilt.iterdir())
    retired=['polisyos/foundry/domain/schema.py','polisyos/foundry/domain/schema/','polisyos/foundry/domain/mechanisms/','polisyos/data_forge/kernel/schemas/codegen.py','polisyos/data_forge/kernel/schemas/codegen/']
    if role=='dfk':
        for prefix in retired:
            assert not any(row['path']==prefix or row['path'].startswith(prefix.rstrip('/')+'/') for row in wheel_rows),prefix
            assert not any('/src/'+prefix in row['path'] for row in sdist_rows),prefix
    result={'role':role,'wheel':str(wheel),'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'wheel_members':wheel_rows,'sdist':str(sdist),'sdist_sha256':hashlib.sha256(sdist.read_bytes()).hexdigest(),'sdist_members':sdist_rows,'all_source_owned_member_bytes_match_frozen_git_archive':True,'generated_metadata_boundary':'dist-info and PKG-INFO are generated distribution metadata; RECORD is reconciled with installed origins separately','DFK_retired_exact_member_prefixes_absent':retired if role=='dfk' else None,'rebuilt_project':str(rebuild_project)}
    (artifact/'archive-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return {k:result[k] for k in ('role','wheel','wheel_sha256','sdist','sdist_sha256','rebuilt_project')}|{'wheel_members':len(wheel_rows),'sdist_members':len(sdist_rows)}


if __name__=='__main__':
    print(json.dumps([inspect(role) for role in ('can','dfk')],indent=2))
