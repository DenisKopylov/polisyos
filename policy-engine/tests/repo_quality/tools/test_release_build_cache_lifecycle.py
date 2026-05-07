from __future__ import annotations

import os
from pathlib import Path

from tools.devx.workspace import release_build_cache_lifecycle as lifecycle


def _family(
    family_id: str,
    *,
    lifecycle_name: str,
    outputs: tuple[Path, ...],
    generator: str = "generator command",
    verifier: str = "verifier command",
    regenerate_commands: tuple[str, ...] = ("generate",),
    stale_output_behavior: str = "warn",
    retention_days: int | None = None,
) -> lifecycle.GeneratedFamily:
    return lifecycle.GeneratedFamily(
        family_id=family_id,
        lifecycle=lifecycle_name,
        generator=generator,
        verifier=verifier,
        promotion_target="promotion target",
        stale_output_behavior=stale_output_behavior,
        outputs=outputs,
        regenerate_commands=regenerate_commands,
        commit_policy="committed" if lifecycle_name == "generated_committed" else "local_ignored",
        retention_days=retention_days,
    )


def test_lifecycle_check_flags_tracked_ignored_umbrellas_and_missing_generator(
    tmp_path: Path,
) -> None:
    product_root = tmp_path / "policy-engine"
    product_root.mkdir()
    (product_root / "release").mkdir()
    (product_root / "release" / "README.md").write_text("release", encoding="utf-8")
    (product_root / "release-fragments" / "unreleased").mkdir(parents=True)
    (product_root / "release-fragments" / "unreleased" / "README.md").write_text(
        "fragments",
        encoding="utf-8",
    )
    generated_output = product_root / "schemas" / "generated.json"
    generated_output.parent.mkdir()
    generated_output.write_text("{}", encoding="utf-8")

    report = lifecycle.build_report(
        product_root=product_root,
        git_root=tmp_path,
        families=(
            _family(
                "missing-generator",
                lifecycle_name="generated_committed",
                outputs=(generated_output,),
                generator="",
                regenerate_commands=(),
            ),
        ),
        tracked_paths={
            "policy-engine/_build/release/source.toml",
            "policy-engine/_cache/tool/cache.db",
            "policy-engine/schemas/generated.json",
        },
        ignore_checker=lambda path: "_build" in path.parts or "_cache" in path.parts,
    )

    rendered = "\n".join(report.violations)
    assert "tracked file lives under ignored build/cache umbrella" in rendered
    assert "release source/output boundary violation under _build" in rendered
    assert "missing a generator entry" in rendered


def test_cleanup_is_dry_run_safe_and_preserves_release_inputs(tmp_path: Path) -> None:
    product_root = tmp_path / "policy-engine"
    product_root.mkdir()
    release_input = product_root / "release" / "keep.toml"
    release_input.parent.mkdir()
    release_input.write_text("keep", encoding="utf-8")
    fragment_input = product_root / "release-fragments" / "unreleased" / "keep.toml"
    fragment_input.parent.mkdir(parents=True)
    fragment_input.write_text("keep", encoding="utf-8")

    scratch_file = product_root / "_build" / "scratch" / "tmp.txt"
    scratch_file.parent.mkdir(parents=True)
    scratch_file.write_text("scratch", encoding="utf-8")
    product_cache = product_root / "_cache" / "tool" / "cache.bin"
    product_cache.parent.mkdir(parents=True)
    product_cache.write_text("cache", encoding="utf-8")
    wrong_root_cache = tmp_path / "_cache" / "ruff" / "cache.bin"
    wrong_root_cache.parent.mkdir(parents=True)
    wrong_root_cache.write_text("cache", encoding="utf-8")

    stale_output = product_root / "_build" / "release" / "sbom" / "sbom.json"
    stale_output.parent.mkdir(parents=True)
    stale_output.write_text("{}", encoding="utf-8")
    old = 1_000_000.0
    os.utime(stale_output, (old, old))
    os.utime(stale_output.parent, (old, old))

    def ignored(path: Path) -> bool:
        return "_build" in path.parts or "_cache" in path.parts

    tracked_paths = {
        "policy-engine/release/keep.toml",
        "policy-engine/release-fragments/unreleased/keep.toml",
    }
    report = lifecycle.build_report(
        product_root=product_root,
        git_root=tmp_path,
        families=(
            _family(
                "release-sbom",
                lifecycle_name="generated_ignored",
                outputs=(stale_output.parent,),
                retention_days=1,
            ),
        ),
        tracked_paths=tracked_paths,
        ignore_checker=ignored,
        now=old + (3 * lifecycle.SECONDS_PER_DAY),
    )

    candidate_paths = {candidate.path.resolve() for candidate in report.cleanup_candidates}
    assert (product_root / "_build" / "scratch").resolve() in candidate_paths
    assert (product_root / "_cache").resolve() in candidate_paths
    assert (tmp_path / "_cache").resolve() in candidate_paths
    assert stale_output.parent.resolve() in candidate_paths
    assert not any("release/keep.toml" in path.as_posix() for path in candidate_paths)

    errors = lifecycle.apply_cleanup(
        report,
        product_root=product_root,
        git_root=tmp_path,
        tracked_paths=tracked_paths,
        ignore_checker=ignored,
        apply=False,
    )

    assert errors == ()
    assert scratch_file.exists()
    assert product_cache.exists()
    assert wrong_root_cache.exists()
    assert stale_output.exists()
    assert release_input.exists()
    assert fragment_input.exists()


def test_cleanup_apply_removes_only_safe_ignored_candidates(tmp_path: Path) -> None:
    product_root = tmp_path / "policy-engine"
    product_root.mkdir()
    release_input = product_root / "release" / "keep.toml"
    release_input.parent.mkdir()
    release_input.write_text("keep", encoding="utf-8")
    scratch_file = product_root / "_build" / "scratch" / "tmp.txt"
    scratch_file.parent.mkdir(parents=True)
    scratch_file.write_text("scratch", encoding="utf-8")

    report = lifecycle.build_report(
        product_root=product_root,
        git_root=tmp_path,
        families=(),
        tracked_paths={"policy-engine/release/keep.toml"},
        ignore_checker=lambda path: "_build" in path.parts,
    )
    errors = lifecycle.apply_cleanup(
        report,
        product_root=product_root,
        git_root=tmp_path,
        tracked_paths={"policy-engine/release/keep.toml"},
        ignore_checker=lambda path: "_build" in path.parts,
        apply=True,
    )

    assert errors == ()
    assert not scratch_file.exists()
    assert release_input.exists()
