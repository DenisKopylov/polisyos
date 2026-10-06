import json
from tools.quality.validation.check_docs_gate import build_gate_plan
paths=json.loads(__import__('sys').argv[1])
print(json.dumps({'full_changed_paths':paths,'actual':{'findings':[f.rule_id for f in build_gate_plan([p.removeprefix('policy-engine/') for p in paths]).findings]},'remove_foundry_doc':{'findings':[f.rule_id for f in build_gate_plan([p.removeprefix('policy-engine/') for p in paths if p!='policy-engine/docs/reference/foundry/causal-graph-reconciliation.md']).findings]},'remove_scientist_doc':{'findings':[f.rule_id for f in build_gate_plan([p.removeprefix('policy-engine/') for p in paths if p!='policy-engine/docs/reference/scientist/causal-graph-intake.md']).findings]}},indent=2))
