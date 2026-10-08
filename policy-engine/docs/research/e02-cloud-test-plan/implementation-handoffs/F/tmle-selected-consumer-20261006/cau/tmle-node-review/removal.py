"""Remove only canonical consumer property bodies in memory, retaining signatures."""
import argparse,ast,inspect,textwrap
import pytest
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as node
parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['projection','source']);parser.add_argument('selector');args=parser.parse_args()
function=node._verify_selected_tmle_projection if args.mode=='projection' else node._run_primary_causal_job
original_signature=inspect.signature(function)
tree=ast.parse(textwrap.dedent(inspect.getsource(function)));changed=[]
if args.mode=='projection':
 function_node=tree.body[0];assert isinstance(function_node,ast.FunctionDef)
 function_node.body=[ast.Pass()];changed.append('Only canonical TMLE projection verifier body removed; producer/result/CAS/report markers unchanged')
else:
 class RemoveSourceComparison(ast.NodeTransformer):
  def visit_If(self,n):
   self.generic_visit(n)
   if isinstance(n.test,ast.Compare) and 'observational_data.model_dump' in ast.unparse(n.test) and 'tmle_data.model_dump' in ast.unparse(n.test):
    changed.append('Only exact current source/materialization JSON equality refusal removed; typed checks/actual job/CAS/projection retained');return None
   return n
 tree=RemoveSourceComparison().visit(tree)
assert len(changed)==1
namespace={};exec(compile(ast.fix_missing_locations(tree),inspect.getsourcefile(function),'exec'),function.__globals__,namespace)
modified=namespace[function.__name__];assert modified.__code__.co_freevars==function.__code__.co_freevars
function.__code__=modified.__code__;assert inspect.signature(function)==original_signature
print({'property_removal':changed,'same_function_identity':True,'same_signature':str(original_signature)})
raise SystemExit(pytest.main(['-o','addopts=','-p','no:cacheprovider','-q','-s','--tb=short',args.selector]))
