from __future__ import annotations

import json
from pathlib import Path

from tools.quality.validation import check_import_policy_projection as projection

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_projection_discovers_primary_root_contracts_from_contract_shape(
    tmp_path: Path,
) -> None:
    _write_policy(
        tmp_path,
        roots=("alpha", "beta"),
        allow={"alpha": ("alpha",), "beta": ("beta", "alpha")},
    )
    _write_contract(tmp_path, "alpha.toml", module="polisyos.alpha", allowed=())
    _write_contract(
        tmp_path,
        "beta.toml",
        module="polisyos.beta",
        allowed=("polisyos.alpha",),
    )
    _write_contract(
        tmp_path,
        "nested.toml",
        module="polisyos.alpha.child",
        allowed=("polisyos.beta",),
    )
    packages = tmp_path / "architecture" / "packages"
    (packages / "boundaries.toml").write_text(
        '[[package]]\nmodule = "polisyos.alpha"\n', encoding="utf-8"
    )
    (packages / "layout.toml").write_text('[[package]]\nname = "alpha"\n', encoding="utf-8")

    report = projection.build_report(tmp_path)

    assert report["status"] == "ready"
    assert report["primary_contract_file_count"] == 3
    assert report["primary_root_contract_count"] == 2
    assert report["primary_root_contracts"] == {
        "alpha": "architecture/packages/alpha.toml",
        "beta": "architecture/packages/beta.toml",
    }
    assert report["nested_primary_contracts"] == [
        {
            "module": "polisyos.alpha.child",
            "path": "architecture/packages/nested.toml",
        }
    ]
    assert report["missing_contract_roots"] == []
    assert report["pair_differences"] == []


def test_projection_fails_closed_for_a_missing_root_without_writing_policy(
    tmp_path: Path, capsys: object
) -> None:
    policy_path = _write_policy(
        tmp_path,
        roots=("alpha", "beta"),
        allow={"alpha": ("alpha",), "beta": ("beta",)},
    )
    _write_contract(tmp_path, "alpha.toml", module="polisyos.alpha", allowed=())
    before = policy_path.read_bytes()

    exit_code = projection.run_cli(["--repo-root", str(tmp_path), "--check"])
    payload = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]

    assert exit_code == 1
    assert payload["status"] == "blocked"
    assert payload["missing_contract_roots"] == ["beta"]
    assert policy_path.read_bytes() == before


def test_projection_reports_every_pair_whose_legal_verdict_would_change(
    tmp_path: Path,
) -> None:
    _write_policy(
        tmp_path,
        roots=("alpha", "beta"),
        allow={"alpha": ("alpha",), "beta": ("beta",)},
    )
    _write_contract(
        tmp_path,
        "alpha.toml",
        module="polisyos.alpha",
        allowed=("polisyos.beta.api",),
    )
    _write_contract(tmp_path, "beta.toml", module="polisyos.beta", allowed=())

    report = projection.build_report(tmp_path)

    assert report["status"] == "blocked"
    assert report["pair_differences"] == [
        {
            "boundary_contract_allows": True,
            "committed_matrix_allows": False,
            "contract_path": "architecture/packages/alpha.toml",
            "difference": "contract_only",
            "live_file_count": 0,
            "live_imports": [],
            "live_statement_count": 0,
            "source_root": "alpha",
            "target_root": "beta",
        }
    ]
    assert report["granularity_collapses"] == [
        {
            "dependency": "polisyos.beta.api",
            "projected_target_root": "beta",
            "source_root": "alpha",
        }
    ]


def test_projection_blocks_a_lossy_submodule_to_root_projection(tmp_path: Path) -> None:
    _write_policy(
        tmp_path,
        roots=("alpha", "beta"),
        allow={"alpha": ("alpha", "beta"), "beta": ("beta",)},
    )
    _write_contract(
        tmp_path,
        "alpha.toml",
        module="polisyos.alpha",
        allowed=("polisyos.beta.api",),
    )
    _write_contract(tmp_path, "beta.toml", module="polisyos.beta", allowed=())

    report = projection.build_report(tmp_path)

    assert report["pair_differences"] == []
    assert report["granularity_collapses"] == [
        {
            "dependency": "polisyos.beta.api",
            "projected_target_root": "beta",
            "source_root": "alpha",
        }
    ]
    assert report["status"] == "blocked"


def test_projection_refuses_a_boundary_rule_the_pair_matrix_cannot_represent(
    tmp_path: Path,
) -> None:
    _write_policy(
        tmp_path,
        roots=("runtime",),
        allow={"runtime": ("runtime",)},
    )
    _write_contract(
        tmp_path,
        "runtime.toml",
        module="polisyos.runtime",
        allowed=("public_facades_only",),
    )

    report = projection.build_report(tmp_path)

    assert report["status"] == "blocked"
    assert report["unrepresentable_dependency_rules"] == [
        {
            "dependency": "public_facades_only",
            "source_root": "runtime",
        }
    ]
    assert report["pair_differences"] == []


def test_projection_blocks_when_source_tree_is_missing(tmp_path: Path) -> None:
    _write_policy(
        tmp_path,
        roots=("alpha",),
        allow={"alpha": ("alpha",)},
        create_source_root=False,
    )
    _write_contract(tmp_path, "alpha.toml", module="polisyos.alpha", allowed=())

    report = projection.build_report(tmp_path)

    assert report["ambiguous_import_sources"] == [
        {
            "error": "SourceTreeMissing",
            "path": "src/polisyos",
        }
    ]
    assert report["status"] == "blocked"


def test_projection_blocks_an_empty_matrix_root_census(tmp_path: Path) -> None:
    _write_policy(tmp_path, roots=(), allow={})

    report = projection.build_report(tmp_path)

    assert report["configuration_errors"] == [{"code": "empty_matrix_roots"}]
    assert report["status"] == "blocked"


def test_projection_blocks_primary_contract_without_boundary_dependencies(
    tmp_path: Path,
) -> None:
    _write_policy(
        tmp_path,
        roots=("alpha",),
        allow={"alpha": ("alpha",)},
    )
    contract_path = tmp_path / "architecture" / "packages" / "alpha.toml"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(
        '[package]\nmodule = "polisyos.alpha"\nprimary_contract = true\n',
        encoding="utf-8",
    )

    report = projection.build_report(tmp_path)

    assert report["contract_errors"] == [
        {
            "code": "allowed_dependencies_missing_or_invalid",
            "path": "architecture/packages/alpha.toml",
        }
    ]
    assert report["status"] == "blocked"


def test_projection_blocks_when_a_live_import_source_is_unreadable(tmp_path: Path) -> None:
    _write_policy(
        tmp_path,
        roots=("alpha",),
        allow={"alpha": ("alpha",)},
    )
    _write_contract(tmp_path, "alpha.toml", module="polisyos.alpha", allowed=())
    source = tmp_path / "src" / "polisyos" / "alpha" / "broken.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def broken(:\n", encoding="utf-8")

    report = projection.build_report(tmp_path)

    assert report["status"] == "blocked"
    assert report["ambiguous_import_sources"] == [
        {
            "error": "SyntaxError",
            "path": "src/polisyos/alpha/broken.py",
        }
    ]


def test_projection_counts_root_barrel_and_relative_cross_root_imports(
    tmp_path: Path,
) -> None:
    _write_policy(
        tmp_path,
        roots=("alpha", "beta"),
        allow={"alpha": ("alpha",), "beta": ("beta",)},
    )
    _write_contract(
        tmp_path,
        "alpha.toml",
        module="polisyos.alpha",
        allowed=("polisyos.beta",),
    )
    _write_contract(tmp_path, "beta.toml", module="polisyos.beta", allowed=())
    root_barrel = tmp_path / "src" / "polisyos" / "alpha" / "root_barrel.py"
    relative = tmp_path / "src" / "polisyos" / "alpha" / "nested" / "relative.py"
    root_barrel.parent.mkdir(parents=True, exist_ok=True)
    relative.parent.mkdir(parents=True, exist_ok=True)
    root_barrel.write_text("from polisyos import beta\n", encoding="utf-8")
    relative.write_text("from ...beta import api\n", encoding="utf-8")

    report = projection.build_report(tmp_path)
    difference = report["pair_differences"][0]

    assert difference["source_root"] == "alpha"
    assert difference["target_root"] == "beta"
    assert difference["live_statement_count"] == 2
    assert difference["live_file_count"] == 2


def test_real_projection_enumerates_the_complete_migration_denominator() -> None:
    report = projection.build_report(REPO_ROOT)

    assert report["status"] == "blocked"
    assert report["matrix_root_count"] == 25
    assert report["primary_contract_file_count"] == 19
    assert report["primary_root_contract_count"] == 18
    assert report["missing_contract_roots"] == [
        "corpus",
        "data_requirement",
        "legal_requirement",
        "pdc",
        "policy_grammar",
        "schemas",
        "scholar_requirement",
    ]
    assert report["pair_difference_count"] == 18
    assert report["live_pair_difference_count"] == 11
    assert report["live_statement_count"] == 31
    assert report["live_file_count"] == 28
    assert any(
        item["source_root"] == "scientist"
        and item["target_root"] == "runtime"
        and item["difference"] == "policy_only"
        and item["live_statement_count"] == 13
        and item["live_file_count"] == 11
        for item in report["pair_differences"]
    )
    assert report["unrepresentable_dependency_rules"] == [
        {
            "dependency": "public_facades_only",
            "source_root": "runtime",
        }
    ]
    assert len(report["granularity_collapses"]) == 6


def _write_policy(
    repo_root: Path,
    *,
    roots: tuple[str, ...],
    allow: dict[str, tuple[str, ...]],
    create_source_root: bool = True,
) -> Path:
    policy_path = repo_root / "architecture" / "imports" / "policy.toml"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "[policy]",
        'version = "test"',
        'internal_prefix = "polisyos"',
        'src_root = "../../src"',
        "",
        "[roots]",
        "known = [" + ", ".join(f'"{root}"' for root in roots) + "]",
        "",
        "[internal.allow]",
    ]
    lines.extend(
        f"{source} = [" + ", ".join(f'"{target}"' for target in targets) + "]"
        for source, targets in allow.items()
    )
    policy_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if create_source_root:
        (repo_root / "src" / "polisyos").mkdir(parents=True, exist_ok=True)
    return policy_path


def _write_contract(
    repo_root: Path,
    filename: str,
    *,
    module: str,
    allowed: tuple[str, ...],
) -> Path:
    path = repo_root / "architecture" / "packages" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    dependencies = ", ".join(f'"{dependency}"' for dependency in allowed)
    path.write_text(
        "\n".join(
            (
                "[package]",
                f'module = "{module}"',
                "primary_contract = true",
                "",
                "[boundaries]",
                f"allowed_dependencies = [{dependencies}]",
                "forbidden_dependencies = []",
                "",
            )
        ),
        encoding="utf-8",
    )
    return path
