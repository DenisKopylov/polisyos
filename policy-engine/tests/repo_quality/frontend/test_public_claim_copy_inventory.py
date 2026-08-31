"""Behavioral closure for claim-bearing copy on the public trust surface."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_ROOT = REPO_ROOT / "apps/runtime-dashboard"
CHECKER = DASHBOARD_ROOT / "scripts/check-public-claim-copy.mjs"


def _run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed repository-owned checker.
        [
            "corepack",
            "pnpm",
            "exec",
            "node",
            str(CHECKER),
            "--root",
            str(root),
            "--json",
        ],
        cwd=DASHBOARD_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _report(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert completed.stdout.strip(), completed.stderr
    return json.loads(completed.stdout)


def test_every_public_capability_assertion_resolves_to_claim_posture() -> None:
    """Enumerate the real route closure and reject unaudited claim copy."""

    completed = _run_checker(DASHBOARD_ROOT)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    report = _report(completed)

    assert report["schema_version"] == "policyos.public_claim_copy_check.v1"
    assert report["violations"] == []
    route = report["route"]
    assert route["app_routes_source"] == "src/app/routes/routes.tsx"
    assert route["route_export_source"] == "src/features/trust/routes.public.tsx"
    assert route["consumed_export"] == "trustRoute"
    assert route["path"] == "/trust"

    closure = report["import_closure"]
    local_paths = closure["local_paths"]
    external_modules = closure["external_modules"]
    assert local_paths == sorted(set(local_paths))
    assert external_modules == sorted(set(external_modules))
    assert closure["local_path_count"] == len(local_paths)
    assert closure["external_module_count"] == len(external_modules)
    assert sum(closure["local_file_type_counts"].values()) == len(local_paths)
    assert "src/features/trust/routes/TrustPosturePage.tsx" in local_paths
    assert "src/shared/i18n/locales/en.json" in local_paths
    assert "src/shared/i18n/locales/uk.json" in local_paths

    inbound = report["inbound_links"]
    assert inbound["tracked_production_tsx_count"] == len(
        inbound["tracked_production_tsx_paths"]
    )
    assert inbound["tracked_production_tsx_paths"] == sorted(
        set(inbound["tracked_production_tsx_paths"])
    )
    assert inbound["links"] == [
        {
            "copy_key": "landing.trustPosture",
            "destination": "/trust",
            "path": "src/features/landing/routes/LandingPage.tsx",
        }
    ]

    locale_copy = report["locale_copy"]
    assert locale_copy["active_locales"] == ["en", "uk"]
    assert locale_copy["leaf_count"] == len(locale_copy["leaf_keys"])
    assert locale_copy["leaf_keys"] == sorted(set(locale_copy["leaf_keys"]))
    assert locale_copy["source_language_authority"] == "not_established"

    inventory = report["claim_copy_inventory"]
    assert inventory["expression_count"] == len(inventory["expressions"])
    assert inventory["artifact_fields"] == sorted(
        set(inventory["artifact_fields"])
    )
    assert inventory["artifact_fields"]


def test_public_claim_copy_checker_rejects_claim_text_outside_posture(
    tmp_path: Path,
) -> None:
    """Falsify the checker with direct authoritative-looking JSX copy."""

    scratch = tmp_path / "runtime-dashboard"
    shutil.copytree(DASHBOARD_ROOT / "src", scratch / "src")
    artifact = Path("public/atlas/trust-claim-posture.v1.json")
    (scratch / artifact.parent).mkdir(parents=True)
    shutil.copy2(DASHBOARD_ROOT / artifact, scratch / artifact)
    target = scratch / "src/features/trust/routes/TrustPosturePage.tsx"
    source = target.read_text(encoding="utf-8")
    marker = '<div className="mx-auto max-w-6xl">'
    assert source.count(marker) == 1
    target.write_text(
        source.replace(
            marker,
            f"{marker}\n        <p>PolicyOS guarantees approval.</p>",
        ),
        encoding="utf-8",
    )
    subprocess.run(  # noqa: S603 - isolated local git denominator setup.
        ["git", "init", "--quiet"], cwd=scratch, check=True
    )
    subprocess.run(  # noqa: S603 - isolated local git denominator setup.
        ["git", "add", "src"], cwd=scratch, check=True
    )

    completed = _run_checker(scratch)
    assert completed.returncode == 1
    report = _report(completed)
    assert any(
        violation["code"] == "raw_claim_copy"
        and violation["path"]
        == "src/features/trust/routes/TrustPosturePage.tsx"
        for violation in report["violations"]
    )
