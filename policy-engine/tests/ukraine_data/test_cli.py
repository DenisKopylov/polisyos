from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.ukraine_data.cli import _parse_stage, build_parser
from polisyos.ukraine_data.models import StageId

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
