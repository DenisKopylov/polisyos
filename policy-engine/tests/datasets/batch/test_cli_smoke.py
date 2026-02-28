from __future__ import annotations

from polisyos.datasets.batch import cli


def test_cli_harvest_dispatch(monkeypatch, tmp_path) -> None:
    called: dict[str, str] = {}

    async def _fake_run(args, stage: str) -> None:  # type: ignore[no-untyped-def]
        called["stage"] = stage
        called["snapshot_root"] = args.snapshot_root

    monkeypatch.setattr(cli, "_run_single_stage", _fake_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "harvest",
            "--snapshot-root",
            str(tmp_path / "snap"),
            "--wave",
            "A",
        ],
    )

    cli.main()
    assert called["stage"] == "harvest"
    assert called["snapshot_root"] == str(tmp_path / "snap")
