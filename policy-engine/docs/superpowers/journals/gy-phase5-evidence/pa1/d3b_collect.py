"""Reconcile complete collected test identities against the prior executed JUnit set."""
from pathlib import Path
import json
from xml.etree import ElementTree
import pytest

class CompleteCollection:
    nodes = []
    def pytest_collection_finish(self, session):
        self.nodes = [item.nodeid for item in session.items]

collector = CompleteCollection()
record = json.loads(Path(__file__).with_name('d3b-final-targeted-v3.json').read_text())
args = record['argv'][3:]
args = [arg for arg in args if not arg.startswith('--junitxml=')]
rc = pytest.main([*args, '--collect-only'], plugins=[collector])
root = ElementTree.parse(Path(__file__).with_name('d3b-final-targeted-v3.xml'))
cases = root.findall('.//testcase')
executed = [item.attrib['classname'].replace('.', '/')+'.py::'+item.attrib['name'] for item in cases]
expected_set, executed_set = set(collector.nodes), set(executed)
result={'denominator':'entire temporal-intake test file, targeted SQLite concurrency, complete live-router/OpenAPI ownership inventory and new endpoint permission/identity/handler controls; independent pytest collection vs executed JUnit case identities', 'collection_returncode':int(rc),'collected_count':len(collector.nodes),'executed_count':len(executed),'collected_identities':sorted(expected_set),'executed_identities':sorted(executed_set),'missing_executions':sorted(expected_set-executed_set),'unexpected_executions':sorted(executed_set-expected_set),'duplicate_collected':len(collector.nodes)!=len(expected_set),'duplicate_executed':len(executed)!=len(executed_set),'unsuccessful_executions':[item.attrib for item in cases if list(item)]}
print(json.dumps(result,indent=2),flush=True)
assert rc == 0 and expected_set == executed_set
assert len(collector.nodes) == len(expected_set) and len(executed) == len(executed_set)
assert not result['unsuccessful_executions']
