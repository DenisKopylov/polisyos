import importlib,importlib.metadata,json,platform,sys
packages=['numpy','scipy','pytest','pydantic','networkx','dowhy','econml']
r={'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'package_distribution_versions':{},'module_origins':{}}
for name in packages:
 try:r['package_distribution_versions'][name]=importlib.metadata.version(name)
 except importlib.metadata.PackageNotFoundError:r['package_distribution_versions'][name]=None
for name in ['polisyos.foundry.methods.catalog.causal.graph_reconciliation','polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph','polisyos.ir.analytics.causal_graph','numpy','scipy']:
 r['module_origins'][name]=importlib.import_module(name).__file__
r['optional_backend_scope']='DoWhy/EconML excluded by baseline Python3.14 marker; absence is not a positive backend witness. Actual selected method backend is Numpy.'
print(json.dumps(r,indent=2))
