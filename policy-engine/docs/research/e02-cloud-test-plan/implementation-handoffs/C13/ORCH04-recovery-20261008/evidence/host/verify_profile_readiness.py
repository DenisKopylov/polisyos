import importlib, importlib.metadata, json, platform, sys
names=['torch','gpytorch','botorch','linear_operator','numpy','scipy']
modules={name:importlib.import_module(name) for name in names}
print(json.dumps({'executable':sys.executable,'python':platform.python_version(),'platform':sys.platform,'modules':{name:{'origin':module.__file__,'version':getattr(module,'__version__',None)} for name,module in modules.items()},'qualification':'Import readiness only. No GP fit, native search/funnel numerical consumer, or product PASS.'},indent=2))
