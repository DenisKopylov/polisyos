import hashlib
import importlib.metadata
import json
import pathlib
import platform
import sys

print(json.dumps({'candidate_source_sha':'c9125bc5e4d2992adeae468a79189d1fa535c88b','interpreter':sys.executable,'version':sys.version,'platform':platform.platform(),'executable_sha256':hashlib.sha256(pathlib.Path(sys.executable).read_bytes()).hexdigest(),'dependencies':{name:importlib.metadata.version(name) for name in ['jax','jaxlib','numpy','scipy','pydantic','pytest']},'profile':'actual locked root venv, candidate PYTHONPATH; native registered income_tax; no production payload or optional DoWhy/EconML claim'},indent=2))
