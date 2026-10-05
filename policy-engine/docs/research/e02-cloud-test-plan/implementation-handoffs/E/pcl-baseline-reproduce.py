import importlib.util,sys,tempfile,subprocess,json
from pathlib import Path
BASE='c40d4acae1ce58b597267255026d9356565828fd'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path)
 m=importlib.util.module_from_spec(spec)
 sys.modules[name]=m
 spec.loader.exec_module(m)
 return m
with tempfile.TemporaryDirectory(prefix='pcl-base-') as d:
 modules={}
 for name in ['curve','continuous']:
  src=subprocess.check_output(['git','show',BASE+':policy-engine/src/polisyos/calibration/'+name+'.py'],text=True)
  p=Path(d)/(name+'.py'); p.write_text(src)
  modules[name]=load('pcl_base_'+name,p)
 modules['continuous'].compute_calibration_curve=modules['curve'].compute_calibration_curve
 ys=list(map(float,range(100)))
 valid=[(v-.1,v+.1) for v in ys[:95]]+[(-1000.,-999.)]*5
 curve=modules['curve'].compute_calibration_curve(ys,[[],valid],levels=[.5,.95])
 report=modules['continuous'].evaluate_continuous(y_true=ys,intervals=[[],valid],levels=[.5,.95])
 print(json.dumps({'base_sha':BASE,'input_identity':'100 analytic observations 0..99; first level skipped; second level .95 covers95 observations','curve_status':curve.evaluation_status,'curve_n_comparisons':curve.n_comparisons,'curve_ece':curve.ece,'curve_positive':curve.is_well_calibrated,'native_report_status':report.metadata['interval_coverage'],'native_receipt_tier':report.to_truthfulness_receipt().runtime_truthfulness_tier,'native_receipt_reasons':report.to_truthfulness_receipt().degradation_reasons},indent=2))
 curve=modules['curve'].compute_calibration_curve([float('nan')]+ys[1:],[[(-1000.,999.)]*100],levels=[.99])
 print(json.dumps({'malformed':'one NaN observation at nominal.99','curve_ece':curve.ece,'curve_positive':curve.is_well_calibrated}))
 report=modules['continuous'].evaluate_continuous(y_true=[1.]*100,predictive_samples=[[0.,2.]]*100,levels=[1.])
 print(json.dumps({'source_alternative':'predictive_samples level1 bypasses supplied continuous open(0,1)domain','native_ece':report.metrics.ece,'native_tier':report.to_truthfulness_receipt().runtime_truthfulness_tier}))
