from __future__ import annotations

from polisyos.fabric.docs.backends.text_html import normalize_html_visible_text_v1


def test_html_normalizer_strips_script_payloads() -> None:
    result = normalize_html_visible_text_v1(
        "<h1>Visible</h1><script>alert('owned')</script><p>Still visible</p>"
    )

    assert "Visible" in result
    assert "Still visible" in result
    assert "owned" not in result
    assert "alert" not in result


def test_html_normalizer_strips_unclosed_style_payloads() -> None:
    result = normalize_html_visible_text_v1(
        "<p>Visible</p><style>body{display:none}.x{content:'leak'}"
    )

    assert "Visible" in result
    assert "display:none" not in result
    assert "leak" not in result
