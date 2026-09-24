"""Independent acquisition grading, denominator and removal witnesses."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.quality.validation import check_gy_acquisition_assurance as checker


def test_complete_corpus_reconciles_two_parser_stacks():
    assert len(checker.validate_corpus()["cases"]) == 63


def test_independent_oracle_grades_real_persisted_consumers():
    assert checker.run_check() == 0


def test_each_named_mutant_fails_on_its_own_witness():
    assert checker.mutation_battery() == 0


@pytest.mark.parametrize("challenge", ["decoder", "loader", "comparator", "unconfined"])
def test_removing_oracle_independence_refuses(challenge):
    assert checker.run_check(challenge=challenge) == 2


def test_corrupt_immutable_input_refuses_before_grade(tmp_path):
    corrupted = tmp_path / "corpus.json"
    corrupted.write_bytes(checker.CORPUS.read_bytes().replace(b'"row_count":0', b'"row_count":1', 1))
    with pytest.raises(ValueError, match="immutable_corpus_drift"):
        checker.validate_corpus(corrupted)


def test_oracle_does_not_import_subject_decoder_or_comparison(monkeypatch, tmp_path):
    """Poison the subject after producing observations; oracle answers stay independent."""
    corpus = checker.validate_corpus()
    observed = checker.run_corpus(corpus, tmp_path)
    wire = checker.observation_wire(observed)
    monkeypatch.setattr(checker, "decode_case_inputs", lambda _: (_ for _ in ()).throw(
        AssertionError("shared decoder")
    ))
    monkeypatch.setattr(checker, "observation_wire", lambda _: "poisoned comparison")
    assert checker.evaluate_wire(wire).returncode == 0
    lines = wire.splitlines()
    changed = lines[1].split("\t")
    changed[3] = "admission_refused"
    lines[1] = "\t".join(changed)
    result = checker.evaluate_wire("\n".join(lines) + "\n")
    assert result.returncode == 1 and "happy.grounding_relation\tstate\t" in result.stdout


def test_oracle_seal_is_not_derived_from_selected_file():
    assert len(checker.EXPECTED_SHA256) == 64
    assert checker.EXPECTED.is_file()
    source = Path(checker.__file__).read_text()
    assert "ROOT_ORACLE_SEAL_PENDING" not in source


def test_cli_creates_ignored_scratch_from_absent_directory(tmp_path, monkeypatch):
    """A fresh checkout has no ignored raw directory; the instrument must own creation."""
    corpus = checker.validate_corpus()
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    monkeypatch.setattr(checker, "validate_corpus", lambda path=checker.CORPUS: corpus)
    monkeypatch.setattr("sys.argv", ["check_gy_acquisition_assurance", "--check"])
    scratch = tmp_path / "docs/superpowers/journals/gy-lattice/as1/raw"
    assert not scratch.exists()
    assert checker.main() == 0
    assert scratch.is_dir()
