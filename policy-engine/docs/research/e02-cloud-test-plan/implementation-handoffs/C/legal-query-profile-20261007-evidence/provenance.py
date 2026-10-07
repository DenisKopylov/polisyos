import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import pathlib
import sys


def digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

print(json.dumps({"python_executable": sys.executable, "python_version": sys.version, "sys_path_head": sys.path[:3]}, sort_keys=True))
for package in ("numpy", "hnswlib"):
    spec = importlib.util.find_spec(package)
    origin = spec.origin if spec else None
    try:
        version = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        version = None
    print(json.dumps({"package": package, "origin": origin, "version": version, "sha256": digest(origin) if origin and pathlib.Path(origin).is_file() else None}, sort_keys=True))
for name in (
    "polisyos.data_forge.domains.legal.embedding_projection",
    "polisyos.data_forge.domains.legal.batch.embedder",
    "polisyos.data_forge.kernel.embeddings",
    "polisyos.data_forge.kernel.io.generation_basis",
    "polisyos.lex.knowledge.store",
    "polisyos.lex.knowledge.search",
):
    module = importlib.import_module(name)
    origin = getattr(module, "__file__", None)
    print(json.dumps({"module": name, "origin": origin, "sha256": digest(origin) if origin and pathlib.Path(origin).is_file() else None}, sort_keys=True))
