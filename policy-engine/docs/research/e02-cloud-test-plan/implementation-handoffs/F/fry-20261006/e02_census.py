import json, os
from collections import Counter
from pathlib import Path
reports=[];warnings=[];collected=[]
def pytest_collection_finish(session):
 collected.extend(x.nodeid for x in session.items)
def pytest_runtest_logreport(report):
 reports.append(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome,duration=report.duration))
def pytest_warning_recorded(warning_message, when, nodeid, location):
 warnings.append(dict(category=warning_message.category.__name__,message=str(warning_message.message),when=when,nodeid=nodeid))
def pytest_sessionfinish(session, exitstatus):
 counts=Counter((r['when']+':'+r['outcome']) for r in reports)
 payload=dict(exitstatus=int(exitstatus),collected=len(collected),collected_nodeids=collected,counts=dict(counts),reports=reports,warnings=warnings)
 Path(os.environ['E02_REPORT_PATH']).write_text(json.dumps(payload,indent=2)+'\n')
