import importlib.metadata,json,pathlib,sys
def pytest_sessionfinish(session,exitstatus):
 payload={'python':sys.version,'executable':sys.executable,'module_origins':{k:getattr(v,'__file__',None) for k,v in sys.modules.items() if k in ['polisyos.runtime.quality.generation_cycle','polisyos.runtime.quality.joint_simulation_horizon','polisyos.runtime.quality.design_axes.coupling_composition','polisyos.calibration.forecast_bridge','polisyos.core.artifacts.store']},'versions':{k:importlib.metadata.version(k) for k in ['pytest','pydantic','numpy','scipy']}}
 pathlib.Path(__file__).with_name('origins.json').write_text(json.dumps(payload,indent=2)+chr(10))
