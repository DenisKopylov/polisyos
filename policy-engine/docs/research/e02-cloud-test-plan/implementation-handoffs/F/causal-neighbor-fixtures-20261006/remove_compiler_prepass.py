"""Memory-only removal of actual rewriting, retaining callable and IR markers."""
import functools,json,pathlib,hashlib
import pytest
from polisyos.foundry.methods.catalog.causal import do_calculus
original=do_calculus.rewrite_estimand
origin=pathlib.Path(do_calculus.__file__)
@functools.wraps(original)
def without_property(ast,graph,max_iterations=20,*,ctf_postpass=None):
    return ast,[]
print(json.dumps({'property_removed':'real rewriting/proof transfer','callable_name_preserved':without_property.__name__==original.__name__,'module_preserved':without_property.__module__==original.__module__,'docstring_preserved':without_property.__doc__==original.__doc__,'provider_origin':str(origin),'provider_sha256':hashlib.sha256(origin.read_bytes()).hexdigest(),'scope':'memory_only_no_source_or_IR_edits'}),flush=True)
do_calculus.rewrite_estimand=without_property
try:
    code=pytest.main(['-o','addopts=','-p','no:cacheprovider','-q','-ra','--tb=short','tests/unit/foundry/methods/catalog/causal/test_compile_estimand_do_calculus_prepass.py::TestDoCalculusPrePass::test_with_graph_does_not_raise'])
finally:
    do_calculus.rewrite_estimand=original
raise SystemExit(code)
