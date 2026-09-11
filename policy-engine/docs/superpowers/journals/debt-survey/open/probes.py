"""Bounded read-only behavioral measurements; no product/test file is changed."""

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[5]
BASE = "fc823071a7b6f2c9a573172aec3499ad6d138c0f"


def calibration():
    from tests._helpers import runtime_http as fixture
    from polisyos.foundry.calibration import report
    from pydantic import ValidationError
    path = ROOT / "tests/_helpers/runtime_http.py"
    tree = ast.parse(path.read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and any(k.arg == "kind" and isinstance(k.value, ast.Constant)
                     and k.value.value == "foundry.calibration_report" for k in n.keywords)]
    raw = ast.literal_eval(calls[0].args[1])
    decorated = fixture._with_runtime_fixture_authority(raw)
    added = sorted(set(decorated)-set(raw))
    # Isolate extra-field refusal from the producer's unrelated version pattern.
    isolated = {k:v for k,v in decorated.items() if k != "schema_version"}
    errors = []
    try:
        report.CalibrationReport.model_validate(isolated)
    except ValidationError as error:
        errors = [{"loc": e["loc"], "type": e["type"]} for e in error.errors()]
    baseline = report.CalibrationReport.model_validate({k:v for k,v in raw.items() if k != "schema_version"})
    return {"source_modules": [fixture.__file__, report.__file__],
            "denominator": "all ast.Call nodes in tests/_helpers/runtime_http.py with exact calibration kind",
            "exact_kind_calls": [{"line":n.lineno,"callee":ast.unparse(n.func)} for n in calls],
            "added_keys": added,"producer_fields": sorted(report.CalibrationReport.model_fields),
            "added_keys_outside_producer_schema": sorted(set(added)-set(report.CalibrationReport.model_fields)),
            "real_model_refusals":errors,"unmodified_payload_without_version_accepted":bool(baseline),
            "limitation":"Exercises actual helper and actual strict DTO, not full HTTP or persisted fixture construction."}


def requirements():
    from polisyos.runtime.quality import producer_pipeline as pipeline
    from polisyos.method_requirement import MethodValidityRequirementSpec
    requirement = MethodValidityRequirementSpec(
        requirement_id="survey-survival",run_id="survey",claim_id="survey-survival",
        identification_class="point",method_expectations=["survival_data"],
        required_method_families=["survival_data"],transportability_requirement="target_population_limits",
        uncertainty_class="interval",assumption_validation_needs=[{"assumption_id":"right_censoring"},{"assumption_id":"support_overlap"}],
        concept_spine_refs=["concept:firm_survival"],obligation_refs=["survey-obligation"])
    binding = {"construct_ref":"construct:firm_survival","selected_capability_ref":"survey:capability"}
    manifest = {"contracts":[{"construct_ref":"construct:firm_survival","contract_target":"foundry.ml.survival_data.v1","required_assumption_gates":["right_censoring","support_overlap"]}]}
    outputs={}
    for label,value in (("no_manifest",None),("flat_manifest",manifest),("unrelated_construct",{"contracts":[dict(manifest['contracts'][0],construct_ref='construct:other')]})):
        result=pipeline._foundry_requirement_report(method_validity_requirement_specs=[requirement],candidate_methods=[],capability_bindings=[binding],observation_to_contract_manifest=value)
        outputs[label]=result
    return {"source_module":pipeline.__file__,"denominator":"three declared input variants to the actual Runtime pipeline helper; entire returned report retained",
            "outputs":outputs,"limitation":"Real helper boundary. Full production input arrival and end-to-end emitted authority are not established by this probe."}


def json_readability():
    a=sorted(subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'--','.'],cwd=ROOT,text=True).splitlines())
    a=[p for p in a if p.endswith('.json')]
    b=sorted(p for p in subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
             if p.endswith('.json') and not p.startswith('docs/superpowers/journals/debt-survey/'))
    assert a == b, {'base_only':sorted(set(a)-set(b)),'index_only':sorted(set(b)-set(a))}
    failures=[]
    for p in a:
        try:json.loads((ROOT/p).read_text())
        except Exception as e:failures.append({'path':p,'error':str(e)})
    return {'base':BASE,'denominator':'all tracked .json files under policy-engine; base-tree and index identities equal',
            'count':len(a),'enumerated_paths':a,'unreadable':failures}


def worktrees():
    raw=subprocess.check_output(['git','worktree','list','--porcelain'],cwd=ROOT,text=True)
    blocks=[dict(line.split(' ',1) if ' ' in line else (line,'') for line in b.splitlines())
            for b in raw.strip().split('\n\n')]
    common=Path(subprocess.check_output(['git','rev-parse','--git-common-dir'],cwd=ROOT,text=True).strip())
    if not common.is_absolute():common=(ROOT/common).resolve()
    records=[]
    for p in sorted((common/'worktrees').glob('*/gitdir')):
        target=Path(p.read_text().strip()).parent
        records.append({'registration':p.parent.name,'path':str(target),'exists':target.is_dir()})
    linked={b['worktree'] for b in blocks[1:]}
    assert linked == {r['path'] for r in records}
    return {'denominator':'current shared git worktree registrations, NOT pinned-tree history; includes this survey worktree',
            'raw_porcelain':raw,'registration_count':len(blocks),'stale_count':sum(not Path(b['worktree']).is_dir() for b in blocks),
            'independent_gitdir_identity_agreement':True,'linked_registrations':records}


def udf():
    directory=Path('/Users/deniskopylov/polisyos/policy-engine/production_data/canonical/local_data_20260501/policy_engine_data/curated')
    a=sorted(directory.glob('*.json'))
    b=sorted(p for p in directory.iterdir() if p.is_file() and p.suffix=='.json')
    assert a==b
    rows=[]
    for path in a:
        payload=path.read_bytes()
        try:
            json.loads(payload)
            result='readable'
        except Exception as error:
            result=str(error)
        rows.append({'path':str(path),'sha256':hashlib.sha256(payload).hexdigest(),'result':result})
    return {'denominator':'every direct .json member of named retained curated source directory; glob equals iterdir; current external bytes, not Git base history',
            'count':len(rows),'members':rows}


if __name__ == '__main__':
    functions={'calibration':calibration,'requirements':requirements,'json-readability':json_readability,'worktrees':worktrees,'udf':udf}
    print(json.dumps({'probe':sys.argv[1], 'base':BASE,'result':functions[sys.argv[1]]()},indent=2,ensure_ascii=False))
