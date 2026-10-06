"""Runtime-only GCM removal preserving fitted numbers, imports and declared markers."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import networkx as nx
import pytest
from dowhy import gcm
def local_fit(model,data):
    for node in nx.topological_sort(model.graph):
        parents=sorted(model.graph.predecessors(node))
        mechanism=model.causal_mechanism(node)
        if parents:
            mechanism.fit(data[parents].to_numpy(),data[[node]].to_numpy())
        else:
            mechanism.fit(data[[node]].to_numpy())
gcm.fit=local_fit
import importlib.util
spec=importlib.util.spec_from_file_location('oracle_fixture',Path('tests/test_worker.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
value=fixture.gcm_request()
from worker import execute
result=execute(value)
assert result['versions']['dowhy']=='0.14'
assert result['result']['fit_function']=='dowhy.gcm.fit'
assert len(result['result']['bootstrap_models'])==3
print(json.dumps({'control':'local mechanism fits retain source/profile markers and full fitted output; actual installed gcm.fit does not execute','point_slope':result['result']['mechanisms']['Y']['coefficients']['X'],'replicates':3}))
raise SystemExit(pytest.main(['tests/test_worker.py::test_genuine_gcm_assignment_fit_residual_rows_and_every_bootstrap_refit','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider','-q','--tb=short']))
