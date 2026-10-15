from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from polisyos.data_forge.domains.ukraine import cli
from polisyos.data_forge.domains.ukraine.cli import _parse_stage, build_parser
from polisyos.data_forge.domains.ukraine.models import StageId

if TYPE_CHECKING:
    from pathlib import Path


def test_parse_stage_normalizes_hyphenated_ids() -> None:
    assert _parse_stage("d0-p0") == StageId.D0_P0
    assert _parse_stage("d1") == StageId.D1
    assert _parse_stage("full") == StageId.FULL


def test_build_parser_accepts_build_arguments(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(["--root", str(tmp_path), "build", "d2", "--resume"])

    assert args.command == "build"
    assert args.stage == StageId.D2
    assert args.resume is True
    assert args.root == tmp_path


def test_domain_cli_requires_an_ops_orchestrator_factory(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Ops composition"):
        cli.main(["--root", str(tmp_path), "validate-part-a"])


def test_domain_cli_uses_the_supplied_orchestrator_factory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_root = tmp_path / "artifacts"
    workspace_root = tmp_path / "checkout"
    captured: dict[str, object] = {}

    class _Manifest:
        def model_dump(self, **_: object) -> dict[str, object]:
            return {"status": "passed"}

    class _Orchestrator:
        def validate_part_a(self) -> SimpleNamespace:
            return SimpleNamespace(status="passed", manifest=_Manifest())

    def factory(config: object, root: Path | None) -> _Orchestrator:
        captured["config_root"] = config.build_root.root  # type: ignore[attr-defined]
        captured["workspace_root"] = root
        return _Orchestrator()

    monkeypatch.setattr(cli, "_emit", lambda _: None)
    result = cli.main(
        ["--root", str(config_root), "--workspace-root", str(workspace_root), "validate-part-a"],
        orchestrator_factory=factory,
    )

    assert result == 0
    assert captured == {"config_root": config_root, "workspace_root": workspace_root}
