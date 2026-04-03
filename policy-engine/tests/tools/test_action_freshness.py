from __future__ import annotations

from pathlib import Path

from tools.ci import check_action_freshness


def test_discover_pinned_actions_reads_version_comments(tmp_path: Path) -> None:
    workflow = tmp_path / "ci.yml"
    workflow.write_text(
        "\n".join(
            [
                "jobs:",
                "  test:",
                "    steps:",
                "      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2",
                "      - uses: github/codeql-action/upload-sarif@3e6af16ff035267728e2ebc35df5d4c4cf249f81 # v3.30.3",
            ]
        ),
        encoding="utf-8",
    )

    entries = check_action_freshness.discover_pinned_actions(tmp_path)

    assert len(entries) == 2
    assert entries[0]["repo"] == "actions/checkout"
    assert entries[0]["tag"] == "v4.2.2"
    assert entries[1]["repo"] == "github/codeql-action"
    assert entries[1]["tag"] == "v3.30.3"


def test_evaluate_marks_actions_with_newer_upstream_release(monkeypatch) -> None:
    monkeypatch.setattr(check_action_freshness, "fetch_latest_tag", lambda repo: "v4.7.0")

    results = check_action_freshness.evaluate(
        [
            {
                "workflow": ".github/workflows/ci.yml",
                "line": 10,
                "repo": "actions/checkout",
                "sha": "11bd71901bbe5b1630ceea73d27597364c9af683",
                "tag": "v4.2.2",
            }
        ]
    )

    assert results[0]["status"] == "update-available"
