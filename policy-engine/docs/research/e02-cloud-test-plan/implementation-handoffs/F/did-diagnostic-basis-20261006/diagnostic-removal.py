import ast,inspect,sys
import pytest
from polisyos.foundry.methods.catalog.causal import did
original=did._did_diagnostic_contract;tree=ast.parse(inspect.getsource(original));fn=tree.body[0];position=next(i for i,s in enumerate(fn.body) if isinstance(s,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='basis' for t in s.targets));fn.body[position+1:position+1]=ast.parse("basis.pop('outcome'); basis.pop('time_treatment')").body;ns=did.__dict__;exec(compile(ast.fix_missing_locations(tree),'<canonical-diagnostic-input-removal>','exec'),ns)
print('Canonical helper actual input digest loses outcome/time_treatment; diagnostic labels/profile/scalar target and numerical computation preserved.',flush=True)
selectors = ['tests/unit/foundry/methods/catalog/causal/test_did_diagnostic_binding.py::test_every_actual_diagnostic_input_is_bound_even_if_result_does_not_change[' + method + '-' + field + ']' for method in ['StandardDifferenceInDifferences', 'StaggeredDifferenceInDifferences'] for field in ['outcome', 'time_treatment']]
raise SystemExit(pytest.main(['-o', 'addopts=', '-q', '-ra', *selectors]))
