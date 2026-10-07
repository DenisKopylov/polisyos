"""Create v1 evidence on exact source; reopen unchanged on the candidate."""
from pathlib import Path
import argparse, json, runpy
from polisyos.core.artifacts import FileSystemCAS
from polisyos.calibration.forecast_bridge import load_forecast_candidate_receipt
from polisyos.scientist.methods.backtesting.forecast_owner import ForecastOwner
from polisyos.ir.artifacts import get_json_artifact
parser=argparse.ArgumentParser()
parser.add_argument("--cas",type=Path,required=True)
parser.add_argument("--helper",type=Path)
args=parser.parse_args()
store=FileSystemCAS(args.cas)
ref_file=args.cas.parent / "legacy-candidate-ref.json"
if args.helper:
    helper=runpy.run_path(str(args.helper))
    request,profile=helper["_configured"](store,[31.,32.,33.,34.])
    result=ForecastOwner(store,empirical_profile_ref=profile).run(request)
    ref_file.write_text(json.dumps(result.candidate_receipt_ref.model_dump(mode="json")))
    print(json.dumps({"stage":"legacy-producer","request_version":get_json_artifact(store,get_json_artifact(store,result.candidate_receipt_ref.artifact_id)["request_ref"]["artifact_id"]).get("schema_version","1.0"),"candidate_ref":json.loads(ref_file.read_text()),"denominator":result.coverage_denominator}))
else:
    receipt=load_forecast_candidate_receipt(store,json.loads(ref_file.read_text()))
    print(json.dumps({"stage":"candidate-legacy-read","candidate_ref":json.loads(ref_file.read_text()),"verifier_provenance":receipt.verifier_provenance,"authority_scope":receipt.authority_scope,"outcome":"PASS"}))
