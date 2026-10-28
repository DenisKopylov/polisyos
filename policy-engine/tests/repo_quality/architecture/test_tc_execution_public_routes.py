"""Exercise the admitted owner aliases and their actual cross-package routes."""

from __future__ import annotations

import ast
from pathlib import Path

from tools.devx.architecture import guardrails

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_bounded_owner_aliases_are_the_defining_objects() -> None:
    """Facades route to the owner objects rather than replacement DTOs."""
    import polisyos.core.contracts as contracts
    import polisyos.ir as ir
    from polisyos.core.contracts import decision_validity, fabric
    from polisyos.ir import linker

    assert (
        contracts.RegisteredSQLAdmissionBinding is decision_validity.RegisteredSQLAdmissionBinding
    )
    assert contracts.RegisteredSQLUseContract is decision_validity.RegisteredSQLUseContract
    assert (
        contracts.data_snapshot_manifest_inputs_match is fabric.data_snapshot_manifest_inputs_match
    )
    assert ir.LinkReport is linker.LinkReport


def test_tc_owner_and_compiler_use_supported_cross_package_routes() -> None:
    """Use the architecture owner's direct and from-list classifiers on both files."""
    policies = guardrails._parse_public_surface(
        REPO_ROOT / "architecture/public_surface/contract.toml"
    )
    allowed: dict[str, set[str]] = {}
    for policy in policies:
        root = guardrails._root_for_module(policy.module)
        if root is not None:
            allowed.setdefault(root, set()).update(policy.supported_entrypoints)

    edges: dict[str, guardrails.DeepImportEdge] = {}
    facade_cache: dict[str, tuple[Path, ast.Module] | None] = {}
    star_cache: dict[str, tuple[str, ...] | None] = {}
    for relative in (
        "src/polisyos/runtime/quality/owned_execution_identity.py",
        "src/polisyos/foundry/compile/manifest_inputs.py",
    ):
        path = REPO_ROOT / relative
        module_info = guardrails._module_name_for_path(path)
        assert module_info is not None
        source_module, is_package = module_info
        source_root = guardrails._root_for_module(source_module)
        assert source_root is not None
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                target = guardrails._resolve_import_module(source_module, is_package, node)
                targets = [] if target is None else [target]
            else:
                continue
            for target in targets:
                guardrails._maybe_add_deep_import(
                    edges=edges,
                    allowed_entrypoints=allowed,
                    source_module=source_module,
                    source_root=source_root,
                    source_file=path,
                    target_module=target,
                )
                if isinstance(node, ast.ImportFrom):
                    guardrails._maybe_add_fromlist_deep_imports(
                        aliases=node.names,
                        target_module=target,
                        source_module=source_module,
                        source_root=source_root,
                        source_file=path,
                        allowed_entrypoints=allowed,
                        edges=edges,
                        facade_cache=facade_cache,
                        star_export_cache=star_cache,
                    )
    assert not edges, {key: edge.resolution_reason for key, edge in edges.items()}


def test_registered_scientist_facades_resolve_existing_owners() -> None:
    """Registration must retain the older C7 and adapter routes as well."""
    import polisyos.scientist.adapters as adapters
    import polisyos.scientist.compute as compute
    from polisyos.scientist.adapters import fabric_bridge, foundry_bridge
    from polisyos.scientist.methods import advanced

    assert compute.C7AdvancedInputs is advanced.C7AdvancedInputs
    assert compute.C7AdvancedSuiteResult is advanced.C7AdvancedSuiteResult
    assert compute.C7PersistedArtifact is advanced.C7PersistedArtifact
    assert compute.run_c7_advanced_suite is advanced.run_c7_advanced_suite
    assert adapters.DefaultFabricPort is fabric_bridge.DefaultFabricPort
    assert adapters.DefaultFoundryPort is foundry_bridge.DefaultFoundryPort
    for facade in (compute, adapters):
        assert all(getattr(facade, name) is not None for name in facade.__all__)
