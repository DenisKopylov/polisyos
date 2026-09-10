"""Behavioural tests for the independently allocated current-locale parser."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest


def _parser() -> ModuleType:
    name = "tools.quality.validation.locale_census_independent"
    assert importlib.util.find_spec(name) is not None, "independent locale parser is absent"
    return importlib.import_module(name)


def test_independent_parser_reads_exact_strings_and_unambiguous_paths(tmp_path: Path) -> None:
    parser = _parser()
    (tmp_path / "en.json").write_text(
        '{"a.b":"literal", "a":{"b":"nested"}, "empty":"", '
        '"escapes":"\\"\\\\\\/\\b\\f\\n\\r\\t", '
        '"unicode":"\\u0410\\ud83d\\ude00"}',
        encoding="utf-8",
    )
    assert parser.read_locale_catalogues(tmp_path) == {
        "en.json": {
            ("a.b",): "literal",
            ("a", "b"): "nested",
            ("empty",): "",
            ("escapes",): '"\\/\b\f\n\r\t',
            ("unicode",): "\u0410😀",
        }
    }


@pytest.mark.parametrize(
    "payload",
    [
        "{}",
        '{"a":{}}',
        '{"a":{},"b":"present"}',
        '{"a":"first","a":"last"}',
        '{"a":"first","\\u0061":"last"}',
        '{"a":{"x":"first","x":"last"}}',
        '{"a":["array"]}',
        '{"a":1}',
        '{"a":null}',
        '{"a":false}',
        '{"a":"unterminated}',
        '{"a":"bad\\q"}',
        '{"a":"bad\n"}',
        '{"a":"x",}',
        '{"a":"x"} trailing',
        '"not an object"',
        '{"a":"\\ud800"}',
        '{"a":"\\udc00"}',
    ],
)
def test_ambiguous_member_never_becomes_a_zero(tmp_path: Path, payload: str) -> None:
    parser = _parser()
    (tmp_path / "en.json").write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError, match="ambiguous"):
        parser.read_locale_catalogues(tmp_path)


def test_complete_file_denominator_includes_unexpected_member(tmp_path: Path) -> None:
    parser = _parser()
    (tmp_path / "en.json").write_text('{"a":"A"}', encoding="utf-8")
    (tmp_path / "unknown.txt").write_text("unreadable as catalogue", encoding="utf-8")
    with pytest.raises(ValueError, match="ambiguous"):
        parser.read_locale_catalogues(tmp_path)


def test_unreadable_encoding_is_ambiguous(tmp_path: Path) -> None:
    parser = _parser()
    (tmp_path / "en.json").write_bytes(b'{"a":"\xff"}')
    with pytest.raises(ValueError, match="ambiguous"):
        parser.read_locale_catalogues(tmp_path)


def test_independent_parser_executes_against_complete_live_catalogue_directory() -> None:
    parser = _parser()
    root = Path(__file__).resolve().parents[3]
    directory = root / "apps/runtime-dashboard/src/shared/i18n/locales"
    measured = parser.read_locale_catalogues(directory)
    assert set(measured) == {entry.name for entry in directory.iterdir()}
    assert "en.json" in measured
    assert all(leaves for leaves in measured.values())
