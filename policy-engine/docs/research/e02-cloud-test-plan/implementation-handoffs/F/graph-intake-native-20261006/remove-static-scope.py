import ast, functools, inspect, sys, textwrap
import pytest
import polisyos.foundry.methods.catalog.causal.graph_reconciliation as owner
cls = owner.ReconcileCausalGraph
original = cls.pure_step
while hasattr(original, "__wrapped__"):
    original = original.__wrapped__
tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
fn = tree.body[0]
fn.decorator_list = []
removed = []
body = []
for statement in fn.body:
    text = ast.unparse(statement)
    if isinstance(statement, ast.If) and (
        "reconciliation cannot orient unresolved or mixed endpoints" in text
        or "static reconciliation cannot repair a cycle by lagging or dropping edges" in text
    ):
        removed.append(text)
    else:
        body.append(statement)
fn.body = body
assert len(removed) == 2
scope = dict(vars(owner))
exec(compile(ast.fix_missing_locations(tree), "<property-removal-control>", "exec"), scope)
original.__code__ = scope[fn.name].__code__
@functools.wraps(cls.validate_static_intake)
def absent_static_property(graph):
    return None
cls.validate_static_intake = staticmethod(absent_static_property)
print("CONTROL: only endpoint/static/union-cycle admission deleted; profile, request snapshots, registry/signature, CAS lineage and result markers retained")
raise SystemExit(pytest.main(sys.argv[1:]))
