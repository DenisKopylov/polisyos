import ast,inspect
import pytest
from polisyos.runtime.quality.proving_ground import causal_forecast_search as owner
class RemoveRoute(ast.NodeTransformer):
 def visit_Constant(self,node):
  if node.value=='causal.inference.did.standard@1.0.0':node.value='causal.did.difference_in_differences@1.0.0'
  return node
tree=RemoveRoute().visit(ast.parse(inspect.getsource(owner._default_g2_runtime_method_candidate)));exec(compile(ast.fix_missing_locations(tree),'<canonical-request-route-removal>','exec'),owner.__dict__)
print('Actual maintained candidate FQN restored to retired/unsupported route; synthetic truthfulness/status/profile and all other metadata retained.',flush=True)
raise SystemExit(pytest.main(['-o','addopts=','-q','-ra','tests/unit/runtime/quality/test_did_request_route.py']))
