"""Independent parser A: complete domain and ambiguous-input semantics."""

import importlib
import importlib.util

import pytest


def owner():
    name = "polisyos.lex.knowledge.locale_census"
    assert importlib.util.find_spec(name), "Independent locale census parser A is absent"
    return importlib.import_module(name)


def test_string_leaves_preserve_exact_paths_and_identity(tmp_path):
    for name in ["en", "uk"]:
        (tmp_path / f"{name}.json").write_text('{"nested":{"x":"значення"},"x.y":"other"}')
    maps = owner().read_locale_catalogues(tmp_path)
    assert maps == {
        name + ".json": {("nested", "x"): "значення", ("x.y",): "other"} for name in ["en", "uk"]
    }


@pytest.mark.parametrize(
    "payload", ['{"x":null}', '{"x":[]}', '{"x":1}', '{"x":"a","x":"b"}', "{bad", "{}"]
)
def test_ambiguous_member_never_becomes_zero(tmp_path, payload):
    (tmp_path / "en.json").write_text(payload)
    with pytest.raises(ValueError, match="ambiguous"):
        owner().read_locale_catalogues(tmp_path)


def test_complete_directory_denominator_cannot_ignore_unknown_member(tmp_path):
    (tmp_path / "en.json").write_text('{"x":"a"}')
    (tmp_path / "unreadable.txt").write_text("unknown")
    with pytest.raises(ValueError, match="ambiguous"):
        owner().read_locale_catalogues(tmp_path)


@pytest.mark.parametrize(
    "payload", ['{"a":"x","\\u0061":"y"}', '{"x":"\\ud800"}', '{"x":"\\udc00"}']
)
def test_decoded_duplicate_and_unpaired_surrogate_are_ambiguous(tmp_path, payload):
    (tmp_path / "en.json").write_text(payload)
    with pytest.raises(ValueError, match="ambiguous"):
        owner().read_locale_catalogues(tmp_path)


def test_deep_unreadable_shape_is_ambiguous(tmp_path):
    payload = '{"x":' * 2000 + '"value"' + "}" * 2000
    (tmp_path / "en.json").write_text(payload)
    with pytest.raises(ValueError, match="ambiguous"):
        owner().read_locale_catalogues(tmp_path)
