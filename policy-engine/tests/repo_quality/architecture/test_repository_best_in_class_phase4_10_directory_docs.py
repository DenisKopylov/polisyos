from __future__ import annotations

import tomllib
from pathlib import Path

from tools.devx.architecture import guardrails

REPO_ROOT = Path(__file__).resolve().parents[3]

AUTHORING_SECTIONS = (
    "## Purpose",
    "## Allowed File Categories",
    "## Public/Private Boundary",
    "## Naming Convention",
    "## Test Location",
    "## Fixture/Data Policy",
    "## Generated File Policy",
    "## Extension Points",
    "## Deprecation And Shim Policy",
)

HIGH_VOLUME_SUBTREE_DOCS: dict[str, tuple[str, ...]] = {
    "docs/adr": ("README.md", "AUTHORING.md", "index.md"),
    "schemas/snapshots/ir": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/foundry/methods/catalog/causal": (
        "README.md",
        "AUTHORING.md",
        "index.md",
    ),
    "src/polisyos/ir/analytics": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/foundry/methods": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/data_forge/domains/legal/batch": (
        "README.md",
        "AUTHORING.md",
        "index.md",
    ),
    "src/polisyos/data_forge/domains/catalog/batch": ("README.md", "AUTHORING.md"),
    "src/polisyos/scientist/agent": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/scientist/search": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/scientist/engine": ("README.md", "AUTHORING.md"),
    "src/polisyos/scientist/orchestration/engine": (
        "README.md",
        "AUTHORING.md",
        "index.md",
    ),
    "src/polisyos/runtime/http/services": ("README.md", "AUTHORING.md"),
    "src/polisyos/fabric/connectors/sources": ("README.md", "AUTHORING.md"),
    "apps/runtime-dashboard/src/shared/ui": ("README.md", "AUTHORING.md", "index.md"),
    "apps/runtime-dashboard/src/api": ("README.md", "AUTHORING.md", "index.md"),
    "apps/runtime-dashboard/src/features": ("README.md", "AUTHORING.md", "index.md"),
    "apps/runtime-dashboard/src/test": ("README.md", "AUTHORING.md"),
    "tests/unit/foundry/methods/catalog/causal": (
        "README.md",
        "AUTHORING.md",
        "index.md",
    ),
    "tests/unit/core/security": ("README.md", "AUTHORING.md"),
    "tests/unit/data_forge": ("README.md", "AUTHORING.md", "index.md"),
    "tests/unit/data_forge/domains/academic/batch": ("README.md", "AUTHORING.md"),
    "tests/unit/data_forge/legal_batch": ("README.md", "AUTHORING.md"),
    "tests/unit/foundry/agent_sim": ("README.md", "AUTHORING.md"),
    "tests/unit/foundry/methods": ("README.md", "AUTHORING.md"),
    "tests/unit/ir/analytics": ("README.md", "AUTHORING.md"),
    "tests/unit/runtime/http": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/agent": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/governance": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/orchestration/engine": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/search": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/nodes": ("README.md", "AUTHORING.md", "index.md"),
    "tests/_data": ("README.md", "AUTHORING.md", "index.md"),
    "tests/_golden": ("README.md", "AUTHORING.md"),
    "tests/_helpers": ("README.md", "AUTHORING.md"),
    "docs/archive/reports": ("README.md", "AUTHORING.md", "index.md"),
}

EXTENSION_HOST_READMES = {
    "polisyos.fabric_connectors": "src/polisyos/fabric/connectors/sources/README.md",
    "polisyos.scientist_governance_passes": (
        "src/polisyos/scientist/governance/passes/README.md"
    ),
    "polisyos.foundry_methods": "src/polisyos/foundry/methods/README.md",
    "polisyos.scientist_nodes": "src/polisyos/scientist/nodes/README.md",
    "polisyos.data_forge_domains": "src/polisyos/data_forge/domains/README.md",
    "polisyos.lex_normpacks": "src/polisyos/lex/normpack/README.md",
    "polisyos.runtime_middlewares": "src/polisyos/runtime/http/README.md",
}


def _load_toml(path: str) -> dict[str, object]:
    with (REPO_ROOT / path).open("rb") as stream:
        return tomllib.load(stream)


def test_high_volume_subtrees_have_local_authoring_closure() -> None:
    for subtree, expected_docs in HIGH_VOLUME_SUBTREE_DOCS.items():
        root = REPO_ROOT / subtree
        assert root.is_dir(), subtree
        for filename in expected_docs:
            path = root / filename
            assert path.is_file(), path.relative_to(REPO_ROOT).as_posix()

        authoring = (root / "AUTHORING.md").read_text(encoding="utf-8")
        for section in AUTHORING_SECTIONS:
            assert section in authoring, f"{subtree} missing {section}"


def test_public_stable_and_high_complexity_packages_have_readme_coverage() -> None:
    public_surface = _load_toml("architecture/public_surface/contract.toml")
    stable_readmes = [
        package["readme"]
        for package in public_surface["package"]  # type: ignore[index]
        if package["classification"] == "public_stable"
    ]
    assert stable_readmes
    for readme in stable_readmes:
        assert (REPO_ROOT / readme).is_file(), readme

    module_budget = _load_toml("architecture/module_size_budget.toml")
    for budget in module_budget["budget"]:  # type: ignore[index]
        path = Path(budget["path"])
        if not path.as_posix().startswith("src/polisyos/"):
            continue
        package_name = path.parts[2]
        package_readme = REPO_ROOT / "src" / "polisyos" / package_name / "README.md"
        assert package_readme.is_file(), budget["path"]


def test_guardrail_readme_gate_includes_high_complexity_packages() -> None:
    public_policies = guardrails._parse_public_surface(
        REPO_ROOT / "architecture/public_surface/contract.toml"
    )
    public_inventory = guardrails.build_public_surface_inventory(public_policies)
    subjects = guardrails._readme_gate_subjects(public_inventory)

    by_readme = {subject.readme: subject for subject in subjects}
    assert "high_complexity" in by_readme["src/polisyos/data_forge/README.md"].reason
    assert "public_surface:public_stable" in by_readme["src/polisyos/runtime/README.md"].reason


def test_extension_hosts_have_readme_coverage() -> None:
    extension_contract = _load_toml("architecture/extension_points.toml")
    names = {
        extension["name"]
        for extension in extension_contract["extension_point"]  # type: ignore[index]
    }
    assert names == set(EXTENSION_HOST_READMES)
    for name, readme in EXTENSION_HOST_READMES.items():
        path = REPO_ROOT / readme
        assert path.is_file(), name


def test_frontend_subtree_contracts_define_feature_module_convention() -> None:
    workspace_contract = (
        REPO_ROOT / "docs/reference/frontend/workspace-contract.md"
    ).read_text(encoding="utf-8")
    for required in (
        "apps/runtime-dashboard/src/app/",
        "apps/runtime-dashboard/src/features/",
        "apps/runtime-dashboard/src/shared/ui/",
        "apps/runtime-dashboard/src/shared/charts/",
        "apps/runtime-dashboard/src/api/",
        "apps/runtime-dashboard/src/test/",
    ):
        assert required in workspace_contract

    feature_readme = (
        REPO_ROOT / "apps/runtime-dashboard/src/features/README.md"
    ).read_text(encoding="utf-8")
    for required in ("domain/", "components/", "routes/", "hooks/", "api/", "state/"):
        assert required in feature_readme

    api_authoring = (
        REPO_ROOT / "apps/runtime-dashboard/src/api/AUTHORING.md"
    ).read_text(encoding="utf-8")
    assert "types.ts" in api_authoring
    assert "generate:api" in api_authoring


def test_package_readme_template_lists_phase4_10_fields() -> None:
    style_guide = (REPO_ROOT / "docs/style-guide.md").read_text(encoding="utf-8")
    for field in (
        "## Purpose",
        "## Public API",
        "## Internal Layout",
        "## Extension Points",
        "## Tests",
        "## Operability Links",
        "## Known Shims/Deprecations",
    ):
        assert field in style_guide
