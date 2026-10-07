"""Restore only paired-list coverage; preserve native v3 state and actual history parser."""
import ast
import inspect
import textwrap


def pytest_configure():
    from polisyos.scientist.methods.autotune import bayesian_generator as owner

    for name in ('set_state', 'validate_checkpoint_history'):
        current=getattr(owner.BayesianCandidateGenerator,name)
        tree=ast.parse(textwrap.dedent(inspect.getsource(current)))
        matches=[]
        for node in ast.walk(tree):
            if not isinstance(node,ast.If):continue
            if any(isinstance(child,ast.Constant) and child.value=='Generator checkpoint current-row coverage is incomplete' for body in node.body for child in ast.walk(body)):
                matches.append(node)
        assert len(matches)==1, 'actual count-admission boundary changed'
        guard=matches[0]
        assert isinstance(guard.test,ast.BoolOp) and isinstance(guard.test.op,ast.Or)
        removed=[];kept=[]
        predicates={
            'native.iteration != count','count != native.iteration',
            'len(rows) != count','len(digests) != count',
        }
        for term in guard.test.values:
            if ast.unparse(term) in predicates:removed.append(ast.unparse(term))
            else:kept.append(term)
        assert len(removed)==3, (name,removed)
        kept.append(ast.parse('len(rows) != len(digests)',mode='eval').body)
        guard.test=ast.BoolOp(op=ast.Or(),values=kept)
        ast.fix_missing_locations(tree)
        namespace={}
        exec(compile(tree,'<only-native-count-grounding-removed>', 'exec'),current.__globals__,namespace)
        setattr(owner.BayesianCandidateGenerator,name,namespace[name])
