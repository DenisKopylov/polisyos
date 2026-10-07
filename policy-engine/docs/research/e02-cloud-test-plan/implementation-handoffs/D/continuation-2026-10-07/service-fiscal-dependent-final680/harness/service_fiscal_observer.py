"""Read-only loaded origins and complete setup/call/teardown phase observer."""
from __future__ import annotations
import hashlib,json,os,sys
from pathlib import Path
PHASES=[]
def pytest_runtest_logreport(report):
    PHASES.append({"nodeid":report.nodeid,"when":report.when,"outcome":report.outcome,"duration":report.duration,"wasxfail":getattr(report,"wasxfail",None)})
def pytest_sessionfinish(session,exitstatus):
    modules={}
    for name,module in sorted(sys.modules.items()):
        if module is None:continue
        raw=getattr(module,"__file__",None)
        if not raw:continue
        path=Path(raw)
        if not path.is_file():continue
        modules[name]={"path":str(path.resolve()),"bytes":path.stat().st_size,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    payload={"exitstatus":int(exitstatus),"python":sys.version,"executable":sys.executable,"argv":sys.argv,"phases":PHASES,"loaded_modules":modules,"scope":"Observer only; imported origins establish runtime identity, not numerical/scientific success by themselves."}
    Path(os.environ["E02_SERVICE_OBSERVER_OUTPUT"]).write_text(json.dumps(payload,sort_keys=True,indent=2)+"\n")
