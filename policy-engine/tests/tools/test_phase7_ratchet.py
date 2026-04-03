from __future__ import annotations

from pathlib import Path

from tools.ci import check_phase7_ratchet


def test_phase7_ratchet_is_optional_when_not_declared_and_no_new_packages() -> None:
    findings = check_phase7_ratchet.evaluate_phase7_ratchet(
        pr_body="## Summary\n\nNo ratchet changes here.\n",
        new_packages=(),
    )

    assert findings == []


def test_phase7_ratchet_requires_follow_up_boxes_once_declared(tmp_path: Path) -> None:
    pr_body = "\n".join(
        [
            "## Phase 7 Ratchet",
            "",
            "- [x] This PR introduces a new subsystem or major surface.",
            "- [ ] I added or updated the owner path, docs entry point, and test strategy.",
            "- [x] I considered compatibility, review / merge governance, and bootstrap / doctor impact.",
            "- [ ] I considered config / secrets, generated artifacts, observability / rollout, and release / runbook impact.",
            "- [ ] I linked the relevant evidence or checklist in `policy-engine/docs/reference/ratchet-policy.md`.",
        ]
    )

    findings = check_phase7_ratchet.evaluate_phase7_ratchet(
        pr_body=pr_body,
        new_packages=(),
        repo_root=tmp_path,
    )

    assert len(findings) == 3
    assert any("owner path, docs entry point, and test strategy" in finding for finding in findings)
    assert any("config / secrets" in finding for finding in findings)
    assert any("ratchet-policy.md" in finding for finding in findings)


def test_phase7_ratchet_detects_new_package_without_declaration(tmp_path: Path) -> None:
    repo_root = tmp_path
    package_dir = repo_root / "policy-engine" / "src" / "polisyos" / "new_surface"
    package_dir.mkdir(parents=True)

    findings = check_phase7_ratchet.evaluate_phase7_ratchet(
        pr_body="## Phase 7 Ratchet\n",
        new_packages=("new_surface",),
        repo_root=repo_root,
    )

    assert any("New package roots were added" in finding for finding in findings)
    assert any("missing its package README" in finding for finding in findings)


def test_detect_new_packages_uses_base_package_presence() -> None:
    changed_paths = [
        "policy-engine/src/polisyos/new_surface/__init__.py",
        "policy-engine/src/polisyos/existing_surface/module.py",
    ]

    detected = check_phase7_ratchet.detect_new_packages(
        changed_paths,
        package_exists=lambda package: package == "existing_surface",
    )

    assert detected == ("new_surface",)
