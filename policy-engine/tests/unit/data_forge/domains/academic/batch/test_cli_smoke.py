from __future__ import annotations

import asyncio

import pytest

from polisyos.data_forge.domains.academic.batch import cli


def test_cli_parse_dispatch(monkeypatch, tmp_path) -> None:
    called: dict[str, str] = {}

    async def _fake_run(args, stage: str) -> None:  # type: ignore[no-untyped-def]
        called["stage"] = stage
        called["snapshot_root"] = args.snapshot_root

    monkeypatch.setattr(cli, "_run_stage", _fake_run)
    monkeypatch.setattr(
        "sys.argv",
        ["prog", "parse", "--snapshot-root", str(tmp_path / "snap")],
    )

    cli.main()
    assert called["stage"] == "parse"
    assert called["snapshot_root"] == str(tmp_path / "snap")


def test_cli_resolve_extract_dispatch(monkeypatch, tmp_path) -> None:
    called: dict[str, str] = {}

    async def _fake_run(args, stage: str) -> None:  # type: ignore[no-untyped-def]
        called["stage"] = stage
        called["snapshot_root"] = args.snapshot_root

    monkeypatch.setattr(cli, "_run_stage", _fake_run)
    monkeypatch.setattr(
        "sys.argv",
        ["prog", "resolve-extract", "--snapshot-root", str(tmp_path / "snap")],
    )

    cli.main()
    assert called["stage"] == "resolve-extract"
    assert called["snapshot_root"] == str(tmp_path / "snap")


def test_data_forge_cli_cannot_execute_scientist_claim_authority(tmp_path) -> None:
    parser = cli._build_parser()
    args = parser.parse_args(
        ["claim-adjudicate", "--snapshot-root", str(tmp_path / "snap")]
    )

    with pytest.raises(RuntimeError, match="Scientist-owned claim adjudication route"):
        asyncio.run(cli._run_stage(args, "claim-adjudicate"))
