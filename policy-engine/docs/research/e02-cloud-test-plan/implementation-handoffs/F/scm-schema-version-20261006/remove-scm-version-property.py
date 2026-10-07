"""Memory-only version/removal controls retaining schema names, rules and source markers."""
import ast,copy,hashlib,json,pathlib,sys
import pytest
from polisyos.ir.analytics import structural_causal_model as scm
from polisyos.ir.schemas import catalog
mode=sys.argv[1]
path=pathlib.Path(scm.__file__);body=path.read_bytes()
if mode=='current_default':
    scm.StructuralCausalModelSpec.model_fields['schema_version'].default='1.0'
    scm.StructuralCausalModelSpec.model_rebuild(force=True)
    catalog.get_ir_schema_catalog.cache_clear()
    selectors=['tests/unit/ir/test_structural_causal_model_versions.py::test_current_scm_default_and_real_catalog_advertise_same_version','tests/unit/ir/test_structural_causal_model_versions.py::test_current_default_gcm_cannot_inherit_legacy_missing_worker_marker']
elif mode=='legacy_read':
    tree=ast.parse(body)
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='load_structural_causal_model_spec')
    guarded_return=copy.deepcopy(function.body[-1]);function.body[-1]=ast.If(test=ast.Constant(value=False),body=[guarded_return],orelse=[])
    function.body.append(ast.Return(value=ast.Call(func=ast.Attribute(value=ast.Name(id='StructuralCausalModelSpec',ctx=ast.Load()),attr='model_validate',ctx=ast.Load()),args=[ast.Name(id='payload',ctx=ast.Load())],keywords=[])))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),str(path)+':memory-legacy-property-removal','exec'),scm.__dict__)
    selectors=['tests/unit/ir/test_structural_causal_model_versions.py::test_actual_legacy_manifest_preserves_version_without_worker_authority']
else:raise ValueError(mode)
print(json.dumps({'mode':mode,'source_path':str(path),'source_sha256':hashlib.sha256(body).hexdigest(),'markers_retained':'schema names, field names, registry/readable versions; original legacy injection AST remains in unreachable arm','source_file_mutated':False}))
code=pytest.main(['-o','addopts=','-p','no:cacheprovider','-q','-s','--tb=short',*selectors]);assert path.read_bytes()==body;raise SystemExit(code)
