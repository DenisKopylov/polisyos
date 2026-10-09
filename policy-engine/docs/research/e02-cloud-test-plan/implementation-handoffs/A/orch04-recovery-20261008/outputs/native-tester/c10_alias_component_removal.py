"""Bounded semantic alias helper removal; no source file changes or full guard PASS."""
import pathlib,inspect,hashlib,json,argparse
import tests.unit.runtime.quality.test_recursive_generation_cycle_epoch_gate as m
p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();out=pathlib.Path(a.out);out.mkdir(exist_ok=False)
original=m._scan_python_source;pre=inspect.getsource(original);old='assignments.append((node.targets[0].id, node.value))';new='pass  # assignments.append((node.targets[0].id, node.value)) marker retained';assert pre.count(old)==1;post=pre.replace(old,new);(out/'preimage.py').write_text(pre);(out/'postimage.py').write_text(post)
r={'input_module':m.__file__,'input_module_sha256':hashlib.sha256(pathlib.Path(m.__file__).read_bytes()).hexdigest(),'property':'assignment alias propagation into actual constructor target census','preimage_sha256':hashlib.sha256(pre.encode()).hexdigest(),'postimage_sha256':hashlib.sha256(post.encode()).hexdigest(),'replacements':[[old,new]],'runtime_product_files_changed':False,'scope':'committed family/alias component only, no complete live guard authority or production conformance'};(out/'mutation.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
exec(compile(post,str(out/'postimage.py'),'exec'),m.__dict__)
try:m.test_recursive_constructor_census_scans_executable_source_families()
finally:m._scan_python_source=original
raise AssertionError('removed assignment alias unexpectedly satisfied component')
