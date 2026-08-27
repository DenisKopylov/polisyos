from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/superpowers/plans/2026-08-20-gy-n12-epoch-chronology-implementation.md"


def _task_declared_paths(task: str) -> tuple[set[str], set[str]]:
    text = PLAN.read_text(encoding="utf-8")
    match = re.search(
        rf"^### Task {re.escape(task)} .*?\n(?P<body>.*?)(?=^### Task |^---$)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None
    body = match.group("body")

    def section(name: str) -> set[str]:
        rows: set[str] = set()
        active = False
        for line in body.splitlines():
            if line == f"**{name}:**":
                active = True
                continue
            if active and line.startswith("**"):
                break
            if active:
                declared = re.fullmatch(r"- `([^`]+)`", line)
                if declared is not None:
                    rows.add(declared.group(1))
        assert rows
        return rows

    return section("Add"), section("Modify")


def test_cluster2_plan_declares_exact_three_boundary_path_sets() -> None:
    task_21 = _task_declared_paths("2.1")
    task_22 = _task_declared_paths("2.2")
    task_23 = _task_declared_paths("2.3")
    task_24 = _task_declared_paths("2.4")

    boundary_1 = set().union(*task_21, *task_22)
    boundary_2 = set().union(*task_23)
    boundary_3 = set().union(*task_24)

    assert len(boundary_1) == 13
    assert len(boundary_2) == 3
    assert len(boundary_3) == 7
    assert boundary_2 & boundary_3 == {"src/polisyos/runtime/quality/README.md"}
    assert len(boundary_1 | boundary_2 | boundary_3) == 22

    assert boundary_1 == {
        "src/polisyos/core/contracts/chronology.py",
        "src/polisyos/core/security/full_prefix.py",
        "tests/unit/core/contracts/test_chronology.py",
        "tests/unit/core/security/test_full_prefix.py",
        "tests/repo_quality/test_gy_n12_cluster2_plan_paths.py",
        "src/polisyos/core/contracts/__init__.py",
        "src/polisyos/core/security/__init__.py",
        "src/polisyos/core/__init__.py",
        "src/polisyos/core/contracts/README.md",
        "src/polisyos/core/security/README.md",
        "architecture/public_surface/inventory.json",
        "docs/reference/public-surface.md",
        "release-fragments/unreleased/2026-08-20-gy-n12-epoch-chronology.toml",
    }


def test_cluster2_plan_keeps_later_production_family_adapters_out_of_scope() -> None:
    all_declared = set()
    for task in ("2.1", "2.2", "2.3", "2.4"):
        all_declared.update(*_task_declared_paths(task))

    assert not any("semantic_epoch" in declared for declared in all_declared)
    assert not any("release_family" in declared for declared in all_declared)
    assert not any("movement" in declared for declared in all_declared)
    assert not any("confidence" in declared for declared in all_declared)


def test_chronology_root_exports_are_visible_to_public_surface_writer() -> None:
    from tools.devx.architecture import guardrails

    policies = guardrails._parse_public_surface(guardrails.DEFAULT_PUBLIC_MANIFEST)
    inventory = guardrails.build_public_surface_inventory(policies)
    core = next(item for item in inventory if item.module == "polisyos.core")

    assert core.facade_mode_observed == "lazy_facade"
    assert {
        "ChronologyBundleRequest",
        "FullPrefixVerificationResult",
        "FullPrefixVerifier",
        "build_full_prefix_bundle",
    } <= set(core.exports)
