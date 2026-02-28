from __future__ import annotations

from polisyos.lex.batch import cli


def test_cli_embed_local_dispatch(monkeypatch, tmp_path) -> None:
    called: dict[str, str] = {}

    def _fake_embed(args):  # type: ignore[no-untyped-def]
        called["command"] = "embed-local"
        called["output_dir"] = str(args.output_dir)

    monkeypatch.setattr(cli, "_cmd_embed_local", _fake_embed)
    monkeypatch.setattr(
        "sys.argv",
        ["prog", "embed-local", "--output-dir", str(tmp_path / "lex")],
    )

    cli.main()
    assert called["command"] == "embed-local"
    assert called["output_dir"] == str(tmp_path / "lex")


def test_cli_run_accepts_llm_gate_flags(monkeypatch, tmp_path) -> None:
    called: dict[str, object] = {}

    def _fake_run(args):  # type: ignore[no-untyped-def]
        called["command"] = "run"
        called["gate_mode"] = args.llm_gate_mode
        called["extract_refs"] = args.extract_references

    monkeypatch.setattr(cli, "_cmd_run", _fake_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "run",
            "--cards",
            str(tmp_path / "cards.xml"),
            "--texts",
            str(tmp_path / "texts.xml"),
            "--output-dir",
            str(tmp_path / "lex"),
            "--llm-gate-mode",
            "aggressive",
            "--no-extract-references",
        ],
    )

    cli.main()
    assert called["command"] == "run"
    assert called["gate_mode"] == "aggressive"
    assert called["extract_refs"] is False
