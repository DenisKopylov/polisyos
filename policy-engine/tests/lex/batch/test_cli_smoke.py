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
        called["gap_fill_mode"] = args.llm_gap_fill_mode
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
            "--llm-gap-fill-mode",
            "wide",
            "--no-extract-references",
        ],
    )

    cli.main()
    assert called["command"] == "run"
    assert called["gate_mode"] == "aggressive"
    assert called["gap_fill_mode"] == "wide"
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


def test_cli_run_accepts_jurisdiction_retry_and_amendment_quality_flags(monkeypatch, tmp_path) -> None:
    called: dict[str, object] = {}

    def _fake_run(args):  # type: ignore[no-untyped-def]
        called["command"] = "run"
        called["jurisdiction"] = args.jurisdiction
        called["spo_timeout_retry_enabled"] = args.spo_timeout_retry_enabled
        called["spo_timeout_retry_batch_size"] = args.spo_timeout_retry_batch_size
        called["pattern_feedback_enabled"] = args.pattern_feedback_enabled
        called["quality_min_amendment_extraction_coverage_pct"] = args.quality_min_amendment_extraction_coverage_pct
        called["quality_min_amendment_target_resolution_pct"] = args.quality_min_amendment_target_resolution_pct

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
            "--jurisdiction",
            "EU",
            "--spo-timeout-retry-batch-size",
            "2",
            "--quality-min-amendment-extraction-coverage-pct",
            "65",
            "--quality-min-amendment-target-resolution-pct",
            "80",
            "--no-pattern-feedback-enabled",
        ],
    )

    cli.main()
    assert called["command"] == "run"
    assert called["jurisdiction"] == "EU"
    assert called["spo_timeout_retry_enabled"] is True
    assert called["spo_timeout_retry_batch_size"] == 2
    assert called["pattern_feedback_enabled"] is False
    assert called["quality_min_amendment_extraction_coverage_pct"] == 65.0
    assert called["quality_min_amendment_target_resolution_pct"] == 80.0


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
        called["llm_gap_fill_mode"] = args.llm_gap_fill_mode
        called["llm_gap_fill_max_share"] = args.llm_gap_fill_max_share

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
            "--llm-gap-fill-mode",
            "wide",
            "--llm-gap-fill-max-share",
            "0.8",
        ],
    )

    cli.main()
    assert called["command"] == "smoke"
    assert called["profile"] == "fast"
    assert called["sample_docs"] == 12
    assert called["spo_request_batch_chars"] == 4800
    assert called["spo_group_timeout_seconds"] == 75.0
    assert called["llm_gap_fill_mode"] == "wide"
    assert called["llm_gap_fill_max_share"] == 0.8
