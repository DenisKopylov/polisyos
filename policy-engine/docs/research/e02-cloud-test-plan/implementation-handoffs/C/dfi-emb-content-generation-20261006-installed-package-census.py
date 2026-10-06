from __future__ import annotations
import hashlib, json, tarfile, tomllib, zipfile
from collections import Counter
from pathlib import Path
root = Path(__file__).parent
archive_path = root / 'candidate.tar'
sdist_path = root / 'dist' / 'policy_engine-0.1.0.tar.gz'
wheel_path = root / 'dist' / 'policy_engine-0.1.0-py3-none-any.whl'
def sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
archive_project: dict[str, bytes] = {}
with tarfile.open(archive_path, 'r:') as t:
    for member in t.getmembers():
        if member.isfile() and member.name.startswith('source/policy-engine/'):
            key = member.name[len('source/policy-engine/'):]
            f = t.extractfile(member)
            assert f is not None
            archive_project[key] = f.read()
project_meta = tomllib.loads(archive_project['pyproject.toml'].decode())
hatch = tomllib.loads(archive_project['hatch.toml'].decode())
force_include = hatch.get('build', {}).get('targets', {}).get('wheel', {}).get('force-include', {})
with tarfile.open(sdist_path, 'r:gz') as t:
    prefix = 'policy_engine-0.1.0/'
    smembers = {m.name[len(prefix):]: t.extractfile(m).read() for m in t.getmembers() if m.isfile() and m.name.startswith(prefix)}
sdist_common = set(archive_project) & set(smembers)
sdist_mismatch = sorted(k for k in sdist_common if archive_project[k] != smembers[k])
sdist_missing = sorted(set(archive_project) - set(smembers))
sdist_extra = sorted(set(smembers) - set(archive_project) - {'PKG-INFO'})
with zipfile.ZipFile(wheel_path) as z:
    wmembers = {n: z.read(n) for n in z.namelist() if not n.endswith('/')}
payload = {k:v for k,v in wmembers.items() if '.dist-info/' not in k}
forced_dst_to_source = {destination: source for source, destination in force_include.items()}
wheel_exact_matches=[]
wheel_forced_matches=[]
wheel_mismatches=[]
wheel_unmapped=[]
for path,data in payload.items():
    if path.startswith('polisyos/'):
        source_path='src/polisyos/'+path.removeprefix('polisyos/')
    elif path.startswith('tools/'):
        source_path=path
    else:
        wheel_unmapped.append(path); continue
    actual_source_path=forced_dst_to_source.get(path, source_path)
    if actual_source_path not in archive_project:
        wheel_mismatches.append({'wheel':path,'source':actual_source_path,'reason':'source path missing'})
    elif archive_project[actual_source_path] != data:
        wheel_mismatches.append({'wheel':path,'source':actual_source_path,'reason':'source bytes differ'})
    elif path in forced_dst_to_source:
        wheel_forced_matches.append({'wheel':path,'source':actual_source_path,'content_match':True})
    else:
        wheel_exact_matches.append({'wheel':path,'source':actual_source_path})
archive_readmes=sorted(k for k in archive_project if Path(k).name.lower().startswith('readme'))
sdist_readmes=sorted(k for k in smembers if Path(k).name.lower().startswith('readme'))
wheel_readmes=sorted(k for k in payload if Path(k).name.lower().startswith('readme'))
package_root_readmes=sorted(k for k in archive_readmes if k.startswith('src/polisyos/') or k.startswith('tools/'))
expected_wheel_readmes=sorted('polisyos/'+k.removeprefix('src/polisyos/') if k.startswith('src/polisyos/') else k for k in package_root_readmes)
readme_missing_from_wheel=sorted(set(expected_wheel_readmes)-set(wheel_readmes))
readme_exceptions_outside_package_roots=sorted(set(archive_readmes)-set(package_root_readmes))
metadata=next((data.decode(errors='replace') for name,data in wmembers.items() if name.endswith('.dist-info/METADATA')), '')
entry_points=next((data.decode(errors='replace') for name,data in wmembers.items() if name.endswith('.dist-info/entry_points.txt')), '')
archive_types=Counter(Path(k).suffix.lower() or '<no-extension>' for k in archive_project)
result={
 'candidate_commit':'12190b1e8a25a6e9c2edc3b9c08f106e76ea5b63','candidate_tree':'fcfe8de3a6cbc0dd1c0df1d02b65cc2d7c1cee04',
 'archive':{'sha256':sha(archive_path.read_bytes()),'bytes':archive_path.stat().st_size,'policy_engine_file_denominator':len(archive_project),'python_files':sum(k.endswith('.py') for k in archive_project),'pyi_files':sum(k.endswith('.pyi') for k in archive_project),'readme_count':len(archive_readmes),'file_types':dict(sorted(archive_types.items()))},
 'sdist':{'sha256':sha(sdist_path.read_bytes()),'bytes':sdist_path.stat().st_size,'members':len(smembers),'frozen_source_files_byte_identical':len(sdist_common),'source_mismatch_paths':sdist_mismatch,'generated_pkg_info':bool(smembers.get('PKG-INFO')) and 'PKG-INFO' not in archive_project,'extra_members':sdist_extra,'source_files_not_in_sdist_count':len(sdist_missing),'source_files_not_in_sdist_by_type':dict(sorted(Counter(Path(k).suffix.lower() or '<no-extension>' for k in sdist_missing).items())),'source_readmes':len(sdist_readmes),'source_readmes_missing':sorted(set(archive_readmes)-set(sdist_readmes))},
 'wheel':{'sha256':sha(wheel_path.read_bytes()),'bytes':wheel_path.stat().st_size,'members':len(wmembers),'payload_files':len(payload),'exact_path_byte_matches':len(wheel_exact_matches),'forced_include_byte_matches':wheel_forced_matches,'mismatch_paths':wheel_mismatches,'unmapped_payload_paths':wheel_unmapped,'source_package_readme_denominator':len(package_root_readmes),'payload_readme_count':len(wheel_readmes),'source_package_readmes_missing':readme_missing_from_wheel,'source_readme_exceptions_outside_package_roots_count':len(readme_exceptions_outside_package_roots),'source_readme_exceptions_outside_package_roots':readme_exceptions_outside_package_roots,'metadata_requires_dist':[line for line in metadata.splitlines() if line.startswith('Requires-Dist:')],'entry_points_groups':sum(1 for line in entry_points.splitlines() if line.startswith('[')),'entry_points_lines':sum(1 for line in entry_points.splitlines() if line and not line.startswith('[')),'entry_points_member':bool(entry_points)},
 'hatch_force_include_mapping':force_include,
 'package_dependency_denominator':{'project_base_dependencies':project_meta['project']['dependencies'],'optional_extra_names':sorted(project_meta['project'].get('optional-dependencies',{}))},
}
out=root/'package-census.json'; out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result,indent=2,sort_keys=True))
