"""Propose additive canonical public exports without writing foreign sources."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

out = Path("/workspace/orch02-r2/c05/g-patch")
repo = Path("/workspace/orch02-c05-r2-gproposal")
G = "dee58973f7673299070b7c7374f419b0adb8175c"
proposals = []


def propose(path, transform, owner, contract):
    before = subprocess.check_output(["git", "show", f"{G}:{path}"], cwd=repo).decode()
    after = transform(before)
    artifact = out / "foreign-postimages" / path
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(after)
    ast.parse(after)
    compile(after, path, "exec")
    old_blob = subprocess.check_output(["git", "rev-parse", f"{G}:{path}"], cwd=repo).decode().strip()
    new_blob = subprocess.check_output(["git", "hash-object", "--stdin"], input=after.encode(), cwd=repo).decode().strip()
    patch = f"diff --git a/{path} b/{path}\nindex {old_blob}..{new_blob} 100644\n" + "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=f"a/{path}", tofile=f"b/{path}"))
    proposals.append({"path": path, "owner": owner, "preimage_blob": old_blob, "preimage_sha256": hashlib.sha256(before.encode()).hexdigest(), "postimage_blob": new_blob, "postimage_sha256": hashlib.sha256(after.encode()).hexdigest(), "contract": contract, "patch": patch})


def fabric(text):
    text = text.replace("from types import ModuleType\n", "from types import ModuleType\nfrom typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from polisyos.fabric.connectors.profiles.models import SourceExecutionPolicy as SourceExecutionPolicy\n    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry as SourceProfileRegistry\n    from polisyos.fabric.connectors.profiles.resolver import (\n        resolve_connection_config as resolve_connection_config,\n        resolve_execution_policy as resolve_execution_policy,\n    )\n")
    text = text.replace("__all__ = [\n", '__all__ = [\n    "SourceExecutionPolicy",\n    "SourceProfileRegistry",\n    "resolve_connection_config",\n    "resolve_execution_policy",\n', 1)
    text = text.replace("_LAZY_IMPORTS: dict[str, tuple[str, str]] = {\n", '_LAZY_IMPORTS: dict[str, tuple[str, str]] = {\n    "SourceExecutionPolicy": ("polisyos.fabric.connectors.profiles.models", "SourceExecutionPolicy"),\n    "SourceProfileRegistry": ("polisyos.fabric.connectors.profiles.registry", "SourceProfileRegistry"),\n    "resolve_connection_config": ("polisyos.fabric.connectors.profiles.resolver", "resolve_connection_config"),\n    "resolve_execution_policy": ("polisyos.fabric.connectors.profiles.resolver", "resolve_execution_policy"),\n', 1)
    return text


def core(text):
    text = text.replace("_LAZY_EXPORTS = {\n", '_LAZY_EXPORTS = {\n    "ArtifactStore": ("polisyos.core.artifacts.protocol", "ArtifactStore"),\n    "ArtifactStoreConfig": ("polisyos.core.artifacts.backends.config", "ArtifactStoreConfig"),\n', 1)
    text = text.replace("if TYPE_CHECKING:\n", "if TYPE_CHECKING:\n    from polisyos.core.artifacts.backends.config import ArtifactStoreConfig as ArtifactStoreConfig\n    from polisyos.core.artifacts.protocol import ArtifactStore as ArtifactStore\n", 1)
    return text.replace("__all__ = [\n", '__all__ = [\n    "ArtifactStore",\n    "ArtifactStoreConfig",\n', 1)


def ir(text):
    text = text.replace("from typing import Any\n", "from typing import TYPE_CHECKING, Any\n\nif TYPE_CHECKING:\n    from polisyos.ir.connectors import FetchRequest as FetchRequest, FetchResult as FetchResult\n", 1)
    text = text.replace("__all__ = [\n", '__all__ = [\n    "FetchRequest",\n    "FetchResult",\n', 1)
    return text.replace("_LAZY_IMPORTS: dict[str, tuple[str, str]] = {\n", '_LAZY_IMPORTS: dict[str, tuple[str, str]] = {\n    "FetchRequest": ("polisyos.ir.connectors", "FetchRequest"),\n    "FetchResult": ("polisyos.ir.connectors", "FetchResult"),\n', 1)


def read_api(text):
    text = text.replace("if TYPE_CHECKING:\n", "if TYPE_CHECKING:\n    from polisyos.data_forge.domains.catalog.registry import (\n        CatalogSourceRegistryEntry as CatalogSourceRegistryEntry,\n        CatalogSourceRegistrySpec as CatalogSourceRegistrySpec,\n        load_catalog_source_registry as load_catalog_source_registry,\n    )\n    from polisyos.data_forge.domains.catalog.source_modules import CatalogRunProfile as CatalogRunProfile\n    from polisyos.data_forge.domains.catalog.selection import CatalogSelectionError as CatalogRunProfileSelectionError\n", 1)
    text = text.replace("    return load_lazy_export(name, exports=_EXPORTS, module_name=__name__, namespace=globals())\n", '    if name == "CatalogRunProfileSelectionError":\n        from polisyos.data_forge.domains.catalog.selection import CatalogSelectionError\n\n        globals()[name] = CatalogSelectionError\n        return CatalogSelectionError\n    return load_lazy_export(name, exports=_EXPORTS, module_name=__name__, namespace=globals())\n', 1)
    return text.replace("_EXPORTS = {\n", '_EXPORTS = {\n    "CatalogRunProfileSelectionError": "polisyos.data_forge.domains.catalog.selection",\n', 1)


propose("policy-engine/src/polisyos/fabric/__init__.py", fabric, "G/Fabric canonical facade owner", "Add lazy public aliases and truthful TYPE_CHECKING reexports for the existing registry, effective connection resolver, execution-policy resolver and execution-policy class. Same canonical objects; no new resolver/cache.")
propose("policy-engine/src/polisyos/core/__init__.py", core, "C02/G Core canonical facade owner", "Expose existing artifact protocol/config classes lazily with static reexports. Preserve all Core exports and optional-dependency cold-import behavior; no Core implementation edits.")
propose("policy-engine/src/polisyos/ir/__init__.py", ir, "G/IR canonical facade owner", "Expose the existing FetchRequest and generic FetchResult through the existing root lazy facade with typed reexports; no DTO copy or implicit Fabric-base reexport.")
propose("policy-engine/src/polisyos/data_forge/read_api/catalog.py", read_api, "G/Data Forge shared read-API owner", "Add typed reexports for existing registry/selection contracts and an additive CatalogRunProfileSelectionError alias. Preserve current G CatalogSelectionError bound to derivation_catalog_selection and every existing export/serving function.")
raw = "".join(row.pop("patch") for row in proposals).encode()
(out / "foreign-public-companions.patch").write_bytes(raw)
result = subprocess.run(["git", "apply", "--check", str(out / "foreign-public-companions.patch")], cwd=repo, capture_output=True)
(out / "foreign-apply-check.stdout.txt").write_bytes(result.stdout)
(out / "foreign-apply-check.stderr.txt").write_bytes(result.stderr)
document = {"schema": "policyos.e02.c05.G-public-companion-proposal.v1", "state": "UNAPPLIED_FOREIGN_OWNER_SELECTION_REQUIRED", "G": G, "patch_sha256": hashlib.sha256(raw).hexdigest(), "patch_bytes": len(raw), "git_apply_check_exit": result.returncode, "rows": proposals, "generated_companions": {"owner": "G/canonical DevX", "requirement": "Regenerate public-surface inventory and affected typed/export projections from selected canonical source. Reconcile actual import guardrails on that composition; no blanket policy, baseline, ignore, expiry or lock change is proposed."}, "formal_closure_ids": []}
(out / "foreign-public-companions.json").write_text(json.dumps(document, indent=2)+"\n")
print(json.dumps({key:document[key] for key in ("state","patch_sha256","patch_bytes","git_apply_check_exit")},indent=2))
raise SystemExit(result.returncode)
