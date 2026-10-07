"""Delete projection/basis properties in canonical function code; keep all ABI markers."""
from __future__ import annotations
import argparse
import ast
import inspect
import textwrap

import pytest
from polisyos.foundry.methods.catalog.causal.treatment_effects import TMLEEstimator

parser=argparse.ArgumentParser()
parser.add_argument('mode',choices=['report_se','basis_order'])
parser.add_argument('selector')
args=parser.parse_args()
function=TMLEEstimator.report_from_result if args.mode=='report_se' else TMLEEstimator.pure_step
tree=ast.parse(textwrap.dedent(inspect.getsource(function)))
for node in tree.body:
    if isinstance(node,ast.FunctionDef):node.decorator_list=[]
mutations=[]

class RemoveProperty(ast.NodeTransformer):
    def visit_keyword(self,node):
        self.generic_visit(node)
        if args.mode=='report_se' and node.arg=='standard_error':
            node.value=ast.BinOp(left=node.value,op=ast.Mult(),right=ast.Constant(value=2.0))
            mutations.append('report.standard_error ×2; genuine result/fit/candidate/profile/CI unchanged')
        return node
    def visit_Call(self,node):
        self.generic_visit(node)
        if args.mode=='basis_order' and isinstance(node.func,ast.Attribute) and node.func.attr=='column_stack':
            arg=node.args[0]
            if isinstance(arg,ast.Tuple) and len(arg.elts)==2 and isinstance(arg.elts[0],ast.Name) and arg.elts[0].id=='X':
                arg.elts=list(reversed(arg.elts));mutations.append('same4columns/dimensions, W before X rather than actual requested X before W')
        return node

tree=ast.fix_missing_locations(RemoveProperty().visit(tree))
assert len(mutations)==1,mutations
namespace={}
exec(compile(tree,inspect.getsourcefile(function),'exec'),function.__globals__,namespace)
modified=namespace[function.__name__]
assert modified.__code__.co_freevars==function.__code__.co_freevars
original_signature=inspect.signature(function)
original_fqn=TMLEEstimator.signature.fqn
function.__code__=modified.__code__
assert inspect.signature(function)==original_signature
assert TMLEEstimator.signature.fqn==original_fqn
print({'property_removal':mutations,'same_signature':str(original_signature),'same_fqn':original_fqn})
raise SystemExit(pytest.main(['-o','addopts=','-p','no:cacheprovider','-q','-s','--tb=short',args.selector]))
