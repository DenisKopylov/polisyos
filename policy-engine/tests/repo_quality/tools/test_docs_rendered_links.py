from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = "tools.quality.validation.check_docs_rendered_links"
SITE_URL = "https://example.test/policy/"


def _fixture_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    fixture_root = REPO_ROOT / "_build" / ".tmp" / "docs-rendered-links-tests" / tmp_path.name
    return fixture_root, fixture_root / "site", fixture_root / "receipt.json"


def _run_checker(site_dir: Path, site_url: str, output: Path) -> tuple[int, dict]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            MODULE,
            "--site-dir",
            str(site_dir),
            "--site-url",
            site_url,
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert output.is_file(), f"checker did not emit a receipt:\n{completed.stderr}"
    receipt = json.loads(output.read_text(encoding="utf-8"))
    return completed.returncode, receipt


def test_real_cli_fails_for_missing_emitted_asset_with_source_location(tmp_path: Path) -> None:
    fixture_root, site_dir, output = _fixture_paths(tmp_path)
    page = site_dir / "guide" / "index.html"
    page.parent.mkdir(parents=True)
    page.write_text(
        '<!doctype html>\n<html><body>\n<img src="../assets/missing.svg">\n</body></html>\n',
        encoding="utf-8",
    )

    try:
        exit_code, receipt = _run_checker(site_dir, SITE_URL, output)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert exit_code == 1
    assert receipt["verdict"] == "FAILED"
    assert receipt["summary"]["missing_target_file_count"] == 1
    assert receipt["findings"] == [
        {
            "kind": "missing_target_file",
            "source": "guide/index.html",
            "line": 3,
            "target": "../assets/missing.svg",
            "expected_output": "assets/missing.svg",
        }
    ]


def test_real_cli_does_not_follow_site_root_symlink_outside_build_tree(tmp_path: Path) -> None:
    fixture_root, _unused_site_dir, output = _fixture_paths(tmp_path)
    site_dir = fixture_root / "site-alias"
    fixture_root.mkdir(parents=True)
    site_dir.symlink_to(REPO_ROOT / "docs", target_is_directory=True)

    try:
        exit_code, receipt = _run_checker(site_dir, SITE_URL, output)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert exit_code == 2
    assert receipt["verdict"] == "UNRUN"
    assert any(
        row["reason"] == "site-root-resolves-outside-build-root" for row in receipt["unresolved"]
    )


def test_real_cli_rejects_receipt_path_outside_build_before_writing(tmp_path: Path) -> None:
    fixture_root, site_dir, _unused_output = _fixture_paths(tmp_path)
    site_dir.mkdir(parents=True)
    (site_dir / "index.html").write_text("<html></html>\n", encoding="utf-8")
    outside_output = REPO_ROOT / "docs" / f".rendered-links-{tmp_path.name}.json"
    assert not outside_output.exists()

    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                MODULE,
                "--site-dir",
                str(site_dir),
                "--site-url",
                SITE_URL,
                "--output",
                str(outside_output),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert completed.returncode == 2
    assert "--output must be an explicit path under repository _build/" in completed.stderr
    assert not outside_output.exists()


def test_real_cli_resolves_base_srcset_css_escapes_and_html_anchors(tmp_path: Path) -> None:
    fixture_root, site_dir, output = _fixture_paths(tmp_path)
    (site_dir / "guide").mkdir(parents=True)
    (site_dir / "guide" / "target").mkdir()
    (site_dir / "assets" / "icons").mkdir(parents=True)
    (site_dir / "assets" / "fonts").mkdir()
    (site_dir / "index.html").write_text("<html><body>root</body></html>", encoding="utf-8")
    (site_dir / "guide" / "index.html").write_text(
        "<html><head>\n"
        '<base href="../">\n'
        '<link rel="stylesheet" href="assets/theme.css">\n'
        "</head><body>\n"
        '<a href="guide/target/#manual">target</a>\n'
        '<img srcset="data:image/svg+xml,%3Csvg%3E 1x, assets/picture%20two.svg 2x">\n'
        "</body></html>\n",
        encoding="utf-8",
    )
    (site_dir / "guide" / "target" / "index.html").write_text(
        '<html><body><section id="manual">target</section></body></html>', encoding="utf-8"
    )
    (site_dir / "assets" / "theme.css").write_text(
        '@import "nested.css";\n.icon { background-image: url("icons/arrow\\20 right.svg"); }\n',
        encoding="utf-8",
    )
    (site_dir / "assets" / "nested.css").write_text(
        '.font { src: url("fonts/policy.woff2"); }\n', encoding="utf-8"
    )
    for relative in (
        "assets/picture two.svg",
        "assets/icons/arrow right.svg",
        "assets/fonts/policy.woff2",
    ):
        target = site_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"asset")

    try:
        exit_code, receipt = _run_checker(site_dir, SITE_URL, output)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert exit_code == 0
    assert receipt["verdict"] == "PASSED"
    assert receipt["summary"]["missing_target_file_count"] == 0
    assert receipt["summary"]["missing_html_fragment_count"] == 0
    assert receipt["summary"]["references_by_outcome"]["nonlocal_scheme_unmeasured"] == 1
    assert receipt["summary"]["references_by_outcome"]["local_target_exists"] == 7
    assert (
        sum(receipt["summary"]["references_by_outcome"].values())
        == receipt["summary"]["reference_count"]
    )
    assert receipt["input_receipt"]["html_css_content_reads"]["complete_verdict"] is True


def test_real_cli_detects_changed_html_bytes_and_removed_target_member(tmp_path: Path) -> None:
    fixture_root, site_dir, output = _fixture_paths(tmp_path)
    (site_dir / "target").mkdir(parents=True)
    page = site_dir / "index.html"
    target = site_dir / "target" / "index.html"
    page.write_text('<a href="target/#present">target</a>\n', encoding="utf-8")
    target.write_text('<section id="present">target</section>\n', encoding="utf-8")

    try:
        first_code, first = _run_checker(site_dir, SITE_URL, output)
        page.write_text('<a href="target/#absent">target</a>\n', encoding="utf-8")
        second_code, second = _run_checker(site_dir, SITE_URL, output)
        target.unlink()
        third_code, third = _run_checker(site_dir, SITE_URL, output)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert first_code == 0 and first["verdict"] == "PASSED"
    assert second_code == 1 and second["verdict"] == "FAILED"
    assert second["summary"]["missing_html_fragment_count"] == 1
    assert (
        first["input_receipt"]["enumerated_path_set_sha256"]
        == second["input_receipt"]["enumerated_path_set_sha256"]
    )
    first_page_reads = first["input_receipt"]["html_css_content_reads"]["inputs"]
    second_page_reads = second["input_receipt"]["html_css_content_reads"]["inputs"]
    first_page_hash = next(
        row["sha256"]
        for row in first_page_reads
        if row["path"] == "index.html" and row["operation"] == "read_bytes"
    )
    second_page_hash = next(
        row["sha256"]
        for row in second_page_reads
        if row["path"] == "index.html" and row["operation"] == "read_bytes"
    )
    assert first_page_hash != second_page_hash
    assert third_code == 1 and third["verdict"] == "FAILED"
    assert third["summary"]["missing_target_file_count"] == 1
    assert (
        second["input_receipt"]["enumerated_path_set_sha256"]
        != third["input_receipt"]["enumerated_path_set_sha256"]
    )


def test_real_cli_path_digest_distinguishes_newline_filename_from_two_members(
    tmp_path: Path,
) -> None:
    fixture_root = REPO_ROOT / "_build" / ".tmp" / "docs-rendered-links-tests" / tmp_path.name
    one_site = fixture_root / "one"
    two_site = fixture_root / "two"
    one_output = fixture_root / "one-receipt.json"
    two_output = fixture_root / "two-receipt.json"
    one_site.mkdir(parents=True)
    two_site.mkdir(parents=True)
    (one_site / "index.html").write_text("<html></html>\n", encoding="utf-8")
    (two_site / "index.html").write_text("<html></html>\n", encoding="utf-8")
    (one_site / "a\nb").write_bytes(b"member")
    (two_site / "a").write_bytes(b"member")
    (two_site / "b").write_bytes(b"member")

    try:
        one_code, one = _run_checker(one_site, SITE_URL, one_output)
        two_code, two = _run_checker(two_site, SITE_URL, two_output)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert one_code == 0 and two_code == 0
    assert one["verdict"] == "PASSED" and two["verdict"] == "PASSED"
    assert one["summary"]["enumerated_entry_count"] == 2
    assert two["summary"]["enumerated_entry_count"] == 3
    assert (
        one["input_receipt"]["enumerated_path_set_sha256"]
        != two["input_receipt"]["enumerated_path_set_sha256"]
    )


def test_real_main_returns_unrun_when_path_set_and_html_change_during_scan(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from tools.quality.validation import check_docs_rendered_links as checker

    fixture_root, site_dir, output = _fixture_paths(tmp_path)
    site_dir.mkdir(parents=True)
    page = site_dir / "index.html"
    page.write_text("<html><body>before</body></html>\n", encoding="utf-8")
    original_walk = checker._walk_site
    original_read = checker.measured_read_bytes
    walk_calls = 0
    read_calls = 0

    def add_member_after_first_enumeration(root: Path):
        nonlocal walk_calls
        result = original_walk(root)
        walk_calls += 1
        if walk_calls == 1:
            (root / "added-after-enumeration.svg").write_bytes(b"asset")
        return result

    def change_page_after_first_read(path: Path) -> bytes:
        nonlocal read_calls
        content = original_read(path)
        if path == page and read_calls == 0:
            read_calls += 1
            page.write_text("<html><body>after</body></html>\n", encoding="utf-8")
        return content

    monkeypatch.setattr(checker, "_walk_site", add_member_after_first_enumeration)
    monkeypatch.setattr(checker, "measured_read_bytes", change_page_after_first_read)

    try:
        exit_code = checker.main(
            [
                "--site-dir",
                str(site_dir),
                "--site-url",
                SITE_URL,
                "--output",
                str(output),
            ]
        )
        capsys.readouterr()
        receipt = json.loads(output.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert exit_code == 2
    assert receipt["verdict"] == "UNRUN"
    reasons = {row["reason"] for row in receipt["unresolved"]}
    assert "site-path-set-changed-during-scan" in reasons
    assert "html-css-content-changed-during-scan" in reasons


def test_real_cli_marks_path_escape_and_unsupported_css_as_unrun(tmp_path: Path) -> None:
    fixture_root, site_dir, output = _fixture_paths(tmp_path)
    (site_dir / "guide").mkdir(parents=True)
    (site_dir / "guide" / "index.html").write_text(
        '<a href="../../outside.html">outside</a>\n'
        '<a href="../%2e%2e/encoded-outside.html">encoded outside</a>\n'
        '<a href="..%2F..%2Fencoded-slash-outside.html">encoded slash outside</a>\n'
        '<link rel="stylesheet" href="broken.css">\n',
        encoding="utf-8",
    )
    (site_dir / "guide" / "broken.css").write_text(
        '.x { background: url("unterminated; color: red; }\n', encoding="utf-8"
    )

    try:
        exit_code, receipt = _run_checker(site_dir, SITE_URL, output)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert exit_code == 2
    assert receipt["verdict"] == "UNRUN"
    reasons = {row["reason"] for row in receipt["unresolved"]}
    assert "same-host-path-outside-site-base" in reasons
    assert "same-host-decoded-path-outside-site-base" in reasons
    assert "unsupported-css-reference-syntax" in reasons
    escaped_targets = {
        row["target"]
        for row in receipt["unresolved"]
        if row["reason"] == "same-host-decoded-path-outside-site-base"
    }
    assert "../%2e%2e/encoded-outside.html" in escaped_targets
    assert "..%2F..%2Fencoded-slash-outside.html" in escaped_targets


def test_real_cli_normalizes_default_http_port_for_same_origin_links(tmp_path: Path) -> None:
    fixture_root, site_dir, output = _fixture_paths(tmp_path)
    site_dir.mkdir(parents=True)
    (site_dir / "index.html").write_text(
        '<a href="https://EXAMPLE.test:443/policy/present.html">present</a>\n'
        '<a href="https://example.test:443/policy/missing.html">missing</a>\n',
        encoding="utf-8",
    )
    (site_dir / "present.html").write_text("<html></html>\n", encoding="utf-8")

    try:
        exit_code, receipt = _run_checker(site_dir, SITE_URL, output)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert exit_code == 1
    assert receipt["summary"]["references_by_outcome"]["local_target_exists"] == 1
    assert receipt["summary"]["missing_target_file_count"] == 1
    assert receipt["summary"]["references_by_outcome"].get("external_unverified", 0) == 0


def test_real_cli_treats_scheme_change_as_a_different_origin(tmp_path: Path) -> None:
    fixture_root, site_dir, output = _fixture_paths(tmp_path)
    site_dir.mkdir(parents=True)
    (site_dir / "index.html").write_text(
        '<a href="http://example.test/policy/missing.html">different scheme</a>\n',
        encoding="utf-8",
    )

    try:
        exit_code, receipt = _run_checker(site_dir, SITE_URL, output)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert exit_code == 0
    assert receipt["summary"]["references_by_outcome"]["external_unverified"] == 1
    assert receipt["summary"]["missing_target_file_count"] == 0


def test_real_cli_marks_malformed_same_host_port_unrun(tmp_path: Path) -> None:
    fixture_root, site_dir, output = _fixture_paths(tmp_path)
    site_dir.mkdir(parents=True)
    (site_dir / "index.html").write_text(
        '<a href="https://example.test:bad/policy/missing.html">bad port</a>\n'
        '<a href="https://example.test:/policy/missing-empty-port.html">empty port</a>\n',
        encoding="utf-8",
    )

    try:
        exit_code, receipt = _run_checker(site_dir, SITE_URL, output)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert exit_code == 2
    assert receipt["verdict"] == "UNRUN"
    malformed = [row for row in receipt["unresolved"] if row["reason"] == "malformed-url-authority"]
    assert len(malformed) == 2
    assert {row["target"] for row in malformed} == {
        "https://example.test:bad/policy/missing.html",
        "https://example.test:/policy/missing-empty-port.html",
    }


def test_real_cli_preserves_trailing_dot_as_distinct_ascii_origin(tmp_path: Path) -> None:
    fixture_root, site_dir, output = _fixture_paths(tmp_path)
    site_dir.mkdir(parents=True)
    (site_dir / "index.html").write_text(
        '<a href="https://example.test./policy/missing-dot.html">trailing dot</a>\n'
        '<a href="https://example.test/policy/missing-normal.html">normal host</a>\n',
        encoding="utf-8",
    )

    try:
        exit_code, receipt = _run_checker(site_dir, SITE_URL, output)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert exit_code == 1
    outcomes = receipt["summary"]["references_by_outcome"]
    assert outcomes["external_unverified"] == 1
    assert receipt["summary"]["missing_target_file_count"] == 1
    assert receipt["findings"][0]["target"] == "https://example.test/policy/missing-normal.html"


def test_real_cli_marks_ambiguous_host_forms_unrun(tmp_path: Path) -> None:
    fixture_root, site_dir, output = _fixture_paths(tmp_path)
    site_dir.mkdir(parents=True)
    (site_dir / "index.html").write_text(
        '<a href="https://faß.test/policy/missing-idna.html">non-ASCII host</a>\n'
        '<a href="https://%65xample.test/policy/missing-percent.html">percent host</a>\n'
        '<a href="https://127.1/policy/missing-numeric.html">legacy IPv4</a>\n',
        encoding="utf-8",
    )

    try:
        exit_code, receipt = _run_checker(site_dir, "https://fass.test/policy/", output)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert exit_code == 2
    assert receipt["verdict"] == "UNRUN"
    assert receipt["summary"]["missing_target_file_count"] == 0
    assert len(receipt["unresolved"]) == 3
    assert {row["reason"] for row in receipt["unresolved"]} == {
        "unsupported-non-ascii-host",
        "unsupported-percent-encoded-host",
        "ambiguous-numeric-ipv4-host",
    }
    details = {row["target"]: row["detail"] for row in receipt["unresolved"]}
    assert "non-ASCII hostname" in details["https://faß.test/policy/missing-idna.html"]
    assert (
        "percent-encoded hostname" in details["https://%65xample.test/policy/missing-percent.html"]
    )
    assert "legacy or numeric IPv4 spelling" in details["https://127.1/policy/missing-numeric.html"]


def test_real_cli_accepts_canonical_ipv4_and_bracketed_ipv6_origins(tmp_path: Path) -> None:
    cases = (
        ("ipv4", "https://127.0.0.1/policy/", "https://127.0.0.1/policy/"),
        ("ipv6", "https://[2001:db8::1]/policy/", "https://[2001:db8::1]/policy/"),
    )
    for name, site_url, target_prefix in cases:
        fixture_root, site_dir, output = _fixture_paths(tmp_path / name)
        site_dir.mkdir(parents=True)
        (site_dir / "index.html").write_text(
            f'<a href="{target_prefix}present.html">present</a>\n'
            f'<a href="{target_prefix}missing.html">missing</a>\n',
            encoding="utf-8",
        )
        (site_dir / "present.html").write_text("<html></html>\n", encoding="utf-8")

        try:
            exit_code, receipt = _run_checker(site_dir, site_url, output)
        finally:
            shutil.rmtree(fixture_root, ignore_errors=True)

        assert exit_code == 1, name
        assert receipt["summary"]["references_by_outcome"]["local_target_exists"] == 1, name
        assert receipt["summary"]["missing_target_file_count"] == 1, name
        assert receipt["unresolved"] == [], name


def test_real_cli_names_css_url_with_intervening_comment_as_unrun(tmp_path: Path) -> None:
    fixture_root, site_dir, output = _fixture_paths(tmp_path)
    site_dir.mkdir(parents=True)
    (site_dir / "index.html").write_text(
        '<link rel="stylesheet" href="styles.css">\n', encoding="utf-8"
    )
    (site_dir / "styles.css").write_text(
        ".icon { background-image: url/**/(icon.svg); }\n", encoding="utf-8"
    )
    (site_dir / "icon.svg").write_text("<svg></svg>\n", encoding="utf-8")

    try:
        exit_code, receipt = _run_checker(site_dir, SITE_URL, output)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert exit_code == 2
    assert receipt["verdict"] == "UNRUN"
    assert any(
        row["reason"] == "unsupported-css-reference-syntax"
        and "comment between CSS url identifier" in row.get("detail", "")
        for row in receipt["unresolved"]
    )


def test_real_cli_does_not_claim_missing_anchor_when_target_html_is_unreadable(
    tmp_path: Path,
) -> None:
    fixture_root, site_dir, output = _fixture_paths(tmp_path)
    (site_dir / "target").mkdir(parents=True)
    (site_dir / "index.html").write_text('<a href="target/#unknown">target</a>\n', encoding="utf-8")
    (site_dir / "target" / "index.html").write_bytes(b"\xff")

    try:
        exit_code, receipt = _run_checker(site_dir, SITE_URL, output)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert exit_code == 2
    assert receipt["verdict"] == "UNRUN"
    assert receipt["summary"]["missing_html_fragment_count"] == 0
    assert any(
        row["reason"] == "target-html-anchor-index-unavailable" for row in receipt["unresolved"]
    )


def test_receipt_declares_measured_reference_forms_and_unmeasured_boundaries(
    tmp_path: Path,
) -> None:
    fixture_root, site_dir, output = _fixture_paths(tmp_path)
    site_dir.mkdir(parents=True)
    (site_dir / "index.html").write_text("<html></html>\n", encoding="utf-8")

    try:
        exit_code, receipt = _run_checker(site_dir, SITE_URL, output)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    assert exit_code == 0
    assert "supported_reference_forms" in receipt["input_receipt"]
    assert "href" in receipt["input_receipt"]["supported_reference_forms"]["html_uri_attributes"]
    assert any(
        item.startswith("srcset ")
        for item in receipt["input_receipt"]["supported_reference_forms"]["html_other"]
    )
    assert any(
        "not HTML5 tree construction" in item for item in receipt["unresolved_by_construction"]
    )
