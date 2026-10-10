from __future__ import annotations

from copy import deepcopy

import pytest

from polisyos.common.migrations._engine import LinearMigrationProfile, run_linear_migration

Step = tuple[str, str]


def test_engine_applies_each_edge_with_versions_and_preserves_input() -> None:
    original: dict[str, object] = {"version": "v0", "applied": []}
    original_before = deepcopy(original)
    calls: list[tuple[str, ...]] = []
    edges: dict[tuple[str, str], Step] = {
        ("manifest", "v0"): ("v1", "normalize"),
        ("manifest", "v1"): ("v2", "bind"),
    }

    def prepare(data: dict[str, object], artifact: str) -> tuple[dict[str, object], str]:
        calls.append(("prepare", artifact))
        working = deepcopy(data)
        version = working["version"]
        assert isinstance(version, str)
        return working, version

    def no_op(data: dict[str, object]) -> dict[str, object]:
        calls.append(("no_op",))
        return data

    def edge_target(edge: Step) -> str:
        return edge[0]

    def apply_step(
        data: dict[str, object], edge: Step, artifact: str, current: str, target: str
    ) -> dict[str, object]:
        calls.append(("apply", artifact, current, target, edge[1]))
        applied = data["applied"]
        assert isinstance(applied, list)
        applied.append(edge[1])
        data["version"] = target
        return data

    def edge_lookup(artifact: str, version: str) -> Step | None:
        calls.append(("lookup", artifact, version))
        return edges.get((artifact, version))

    profile = LinearMigrationProfile[dict[str, object], Step](
        prepare=prepare,
        no_op=no_op,
        edge_target=edge_target,
        apply_step=apply_step,
    )
    migrated = run_linear_migration(
        original,
        artifact="manifest",
        target_version="v2",
        edge_lookup=edge_lookup,
        profile=profile,
    )

    assert calls == [
        ("prepare", "manifest"),
        ("lookup", "manifest", "v0"),
        ("apply", "manifest", "v0", "v1", "normalize"),
        ("lookup", "manifest", "v1"),
        ("apply", "manifest", "v1", "v2", "bind"),
    ]
    assert migrated == {"version": "v2", "applied": ["normalize", "bind"]}
    assert original == original_before


def test_engine_rejects_a_missing_later_edge_after_real_first_step() -> None:
    original: dict[str, object] = {"version": "v0", "applied": []}
    original_before = deepcopy(original)
    lookups: list[tuple[str, str]] = []
    applied_versions: list[tuple[str, str]] = []
    edges: dict[tuple[str, str], Step] = {("manifest", "v0"): ("v1", "normalize")}

    def prepare(data: dict[str, object], artifact: str) -> tuple[dict[str, object], str]:
        del artifact
        working = deepcopy(data)
        version = working["version"]
        assert isinstance(version, str)
        return working, version

    def no_op(data: dict[str, object]) -> dict[str, object]:
        return data

    def edge_target(edge: Step) -> str:
        return edge[0]

    def apply_step(
        data: dict[str, object], edge: Step, artifact: str, current: str, target: str
    ) -> dict[str, object]:
        del artifact
        applied_versions.append((current, target))
        applied = data["applied"]
        assert isinstance(applied, list)
        applied.append(edge[1])
        return data

    def edge_lookup(artifact: str, version: str) -> Step | None:
        lookups.append((artifact, version))
        return edges.get((artifact, version))

    profile = LinearMigrationProfile[dict[str, object], Step](
        prepare=prepare,
        no_op=no_op,
        edge_target=edge_target,
        apply_step=apply_step,
    )

    with pytest.raises(ValueError, match="No migrator for 'manifest' from v1 to v2"):
        run_linear_migration(
            original,
            artifact="manifest",
            target_version="v2",
            edge_lookup=edge_lookup,
            profile=profile,
        )

    assert lookups == [("manifest", "v0"), ("manifest", "v1")]
    assert applied_versions == [("v0", "v1")]
    assert original == original_before
