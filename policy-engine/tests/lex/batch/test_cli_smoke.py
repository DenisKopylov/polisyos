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


def test_cli_run_accepts_gonka_api_keys(monkeypatch, tmp_path) -> None:
    called: dict[str, object] = {}

    def _fake_run(args):  # type: ignore[no-untyped-def]
        called["command"] = "run"
        called["gonka_api_keys"] = args.gonka_api_keys

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
            "--gonka-api-keys",
            "key-1,key-2,key-3",
        ],
    )

    cli.main()
    assert called["command"] == "run"
    assert called["gonka_api_keys"] == "key-1,key-2,key-3"


def test_cli_run_accepts_publish_bundle_flags(monkeypatch, tmp_path) -> None:
    called: dict[str, object] = {}

    def _fake_run(args):  # type: ignore[no-untyped-def]
        called["command"] = "run"
        called["stages"] = args.stages
        called["publish_require_embeddings"] = args.publish_require_embeddings

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
            "--stages",
            "structure,spo,ground_quotes,resolve_refs,graph,export_claims,publish_bundle",
            "--no-publish-require-embeddings",
        ],
    )

    cli.main()
    assert called["command"] == "run"
    assert "publish_bundle" in str(called["stages"])
    assert called["publish_require_embeddings"] is False


def test_cli_publish_accepts_embedding_flag(monkeypatch, tmp_path) -> None:
    called: dict[str, object] = {}

    def _fake_publish(args):  # type: ignore[no-untyped-def]
        called["command"] = "publish"
        called["require_embeddings"] = args.require_embeddings

    monkeypatch.setattr(cli, "_cmd_publish", _fake_publish)
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "publish",
            "--output-dir",
            str(tmp_path / "lex"),
            "--no-require-embeddings",
        ],
    )

    cli.main()
    assert called["command"] == "publish"
    assert called["require_embeddings"] is False


def test_cli_benchmark_dispatch(monkeypatch, tmp_path) -> None:
    called: dict[str, object] = {}

    def _fake_benchmark(args):  # type: ignore[no-untyped-def]
        called["command"] = "benchmark"
        called["output_dir"] = args.output_dir

    monkeypatch.setattr(cli, "_cmd_benchmark", _fake_benchmark)
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "benchmark",
            "--output-dir",
            str(tmp_path / "lex"),
        ],
    )

    cli.main()
    assert called["command"] == "benchmark"
    assert str(called["output_dir"]) == str(tmp_path / "lex")


def test_cli_smoke_dispatch(monkeypatch, tmp_path) -> None:
    called: dict[str, object] = {}

    def _fake_smoke(args):  # type: ignore[no-untyped-def]
        called["command"] = "smoke"
        called["profile"] = args.profile
        called["sample_docs"] = args.sample_docs
        called["spo_request_batch_chars"] = args.spo_request_batch_chars
        called["spo_group_timeout_seconds"] = args.spo_group_timeout_seconds

    monkeypatch.setattr(cli, "_cmd_smoke", _fake_smoke)
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "smoke",
            "--cards",
            str(tmp_path / "cards.xml"),
            "--texts",
            str(tmp_path / "texts.xml"),
            "--output-dir",
            str(tmp_path / "lex"),
            "--profile",
            "fast",
            "--sample-docs",
            "12",
            "--spo-request-batch-chars",
            "4800",
            "--spo-group-timeout-seconds",
            "75",
        ],
    )

    cli.main()
    assert called["command"] == "smoke"
    assert called["profile"] == "fast"
    assert called["sample_docs"] == 12
    assert called["spo_request_batch_chars"] == 4800
    assert called["spo_group_timeout_seconds"] == 75.0
