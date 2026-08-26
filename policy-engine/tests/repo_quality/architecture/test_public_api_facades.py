from __future__ import annotations

import ast
import importlib
from pathlib import Path

ROOT_PUBLIC_MODULES = {
    "core": ["polisyos.core"],
    "ir": ["polisyos.ir", "polisyos.ir.trinity", "polisyos.ir.linker", "polisyos.ir.migrations"],
    "fabric": ["polisyos.fabric", "polisyos.fabric.world"],
    "foundry": ["polisyos.foundry"],
    "scientist": ["polisyos.scientist"],
    "lex": ["polisyos.lex"],
    "scholar": ["polisyos.scholar"],
    "data_forge": ["polisyos.data_forge", "polisyos.data_forge.read_api"],
}


def test_public_modules_importable() -> None:
    for modules in ROOT_PUBLIC_MODULES.values():
        for module_name in modules:
            try:
                importlib.import_module(module_name)
            except ModuleNotFoundError as exc:
                missing = exc.name or ""
                if missing.startswith("polisyos"):
                    raise


def test_root_facades_define_all_and_no_star_reexport() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    src_root = repo_root / "src" / "polisyos"

    for root in ROOT_PUBLIC_MODULES:
        init_path = src_root / root / "__init__.py"
        assert init_path.exists(), f"Missing facade module: {init_path}"

        tree = ast.parse(init_path.read_text(encoding="utf-8"))
        has_all = False
        has_star_import = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        has_all = True
            if isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id == "__all__":
                    has_all = True
            if isinstance(node, ast.ImportFrom):
                if any(alias.name == "*" for alias in node.names):
                    has_star_import = True

        assert has_all, f"{init_path} must define curated __all__"
        assert not has_star_import, f"{init_path} must not use star re-export"


def test_scientist_claim_authority_facade_preserves_owner_objects() -> None:
    scientist = importlib.import_module("polisyos.scientist")
    claims = importlib.import_module("polisyos.scientist.evidence.claims.head_index")
    bridge = importlib.import_module("polisyos.scientist.governance.continuous.lifecycle_bridge")

    expected = {
        "ClaimLedgerCurrentHeadProjection": claims.ClaimLedgerCurrentHeadProjection,
        "ClaimLedgerOwnerPort": claims.ClaimLedgerOwnerPort,
        "ClaimLifecycleBridgeAdvanced": claims.ClaimLifecycleBridgeAdvanced,
        "build_default_claim_ledger_owner": claims.build_default_claim_ledger_owner,
        "EpochClaimLifecycleBridgeService": bridge.EpochClaimLifecycleBridgeService,
        "build_epoch_claim_lifecycle_bridge": bridge.build_epoch_claim_lifecycle_bridge,
    }
    assert set(expected) <= set(scientist.__all__)
    for name, owner_object in expected.items():
        assert getattr(scientist, name) is owner_object
