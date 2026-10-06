import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser(description='Recompute the bounded tracked-code/config caller census; keep the derived match set in local scratch.')
parser.add_argument('--repo-root', type=Path, default=Path.cwd().parent if Path.cwd().name == 'policy-engine' else Path.cwd())
parser.add_argument('--output-dir', type=Path, required=True)
parser.add_argument('--profile-pattern', action='store_true')
args = parser.parse_args()
root = args.repo_root.resolve()
out = args.output_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
sha = subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
tree = subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip()
tracked = subprocess.check_output(['git','ls-tree','-r','--name-only',sha],cwd=root).decode().splitlines()
suffixes = {'.py','.json','.jsonl','.yaml','.yml','.toml','.ini','.cfg','.conf','.ts','.tsx','.js','.jsx','.sh'}
denominator = [path for path in tracked if Path(path).suffix in suffixes and not path.startswith('policy-engine/docs/research/') and not path.startswith('policy-engine/docs/plans/')]
pattern = re.compile(r'\b(?:IncomeTax|TaxSubsidy|LaborMarketMechanism|IncomeTaxMechanismMethod|TaxSubsidyMechanismMethod|LaborMarketMechanismMethod|TaxationMechanism|TransferMechanism|income_tax|tax_subsidy|labor_market|normalized_income_budget_loss|policy_loss_fn|compute_gini_hard|compute_gini|_gini_from_values|GiniObjective|_compute_distribution_state)\b' if args.profile_pattern else r'\b(?:normalized_income_budget_loss|policy_loss_fn|compute_gini_hard|compute_gini|_gini_from_values|GiniObjective|_compute_distribution_state)\b')
matches = []
unreadable = []
for name in denominator:
    try:
        text = (root / name).read_text()
    except (UnicodeError,OSError) as exc:
        unreadable.append({'path':name,'error':str(exc)})
        continue
    role = 'test' if '/tests/' in name else 'production_or_configuration'
    for number,line in enumerate(text.splitlines(),1):
        found = sorted(set(pattern.findall(line)))
        if found:
            matches.append({'path':name,'line':number,'role':role,'symbols':found,'text':line.strip()})
record = {'schema':'policyos.e02.static_consumer_census.v1','source_sha':sha,'tree_sha':tree,'scope':'Every tracked file with declared code/config suffix, except research/plan evidence; docs prose and binary data are not executable configurations. Working source bytes are read; all frozen source hashes are separately bound at implementation freeze.','denominator_command':['git','ls-tree','-r','--name-only',sha],'denominator_suffixes':sorted(suffixes),'excluded_prefixes':['policy-engine/docs/research/','policy-engine/docs/plans/'],'tracked_file_count':len(tracked),'eligible_file_count':len(denominator),'eligible_path_list_sha256':hashlib.sha256(('\n'.join(denominator)+'\n').encode()).hexdigest(),'unreadable':unreadable,'pattern':pattern.pattern,'matches':matches,'runtime_paths':{'exact_gini':['agent_sim.distributions.compute_gini -> compute_gini_hard','agent_sim.distributions.compute_all_distributions -> compute_gini','plugins.economics.state.EconomicState._compute_distributions -> compute_gini_hard -> registered GiniObjective','agent_sim.wiring.executors._compute_distribution_state -> compute_gini_hard -> native household distribution state','agent_sim.state.compute_aggregates -> _gini_from_values -> compute_gini_hard -> PureExecutor.run aggregation; training/population/graph executor consumers also use compute_aggregates'],'historical_loss':['plugins.economics.baselines.normalized_income_budget_loss','methods._internal.loss.policy_loss_fn identity alias','methods.loss compatibility facade','tests/unit/foundry/analysis/test_loss_numeric.py','tests/unit/remediation/test_eco_01.py']},'limits':['A static full tracked code/config text census cannot resolve external plugins, serialized configurations outside Git, reflection, dependency injection or production optimizer dispatch.','No real production optimizer invocation of the historical loss is established by the tracked literal callers; aliases must not be retired on this basis.','Native DGP/fixture consumers establish numeric contracts, not admitted real-data economic claims.']}
path=out/('profile-consumer-census.json' if args.profile_pattern else 'consumer-census.json')
path.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_sha':sha,'tracked':len(tracked),'eligible':len(denominator),'matches':len(matches),'production_matches':sum(x['role']=='production_or_configuration' for x in matches),'unreadable':unreadable}))
for item in matches:
    if item['role']=='production_or_configuration':
        print(f"{item['path']}:{item['line']} {item['text']}")
