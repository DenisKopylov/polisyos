"""Compatibility coverage for the Lex/Data Forge legal read boundary."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from polisyos.core.errors import ErrorCategory
from polisyos.data_forge.domains.legal.contracts import ActiveVersionResult as DataForgeResult
from polisyos.data_forge.errors import LexValidationError as DataForgeValidationError
from polisyos.lex import api
from polisyos.lex.errors import LexValidationError
from polisyos.lex.types import ActiveVersionResult, ActiveVersionStrategy


def test_lex_runtime_contract_modules_import_without_data_forge_compatibility_edges() -> None:
    """Lex read contracts remain importable when the removed Data Forge edges are unavailable."""
    script = """
import builtins

blocked_prefixes = (
    'polisyos.data_forge.kernel.artifacts',
    'polisyos.data_forge.domains.legal.contracts',
)
original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == blocked_prefixes[0] or name.startswith(blocked_prefixes[0] + '.'):
        raise AssertionError('Lex imported Data Forge artifact readers')
    if name == blocked_prefixes[1] or name.startswith(blocked_prefixes[1] + '.'):
        raise AssertionError('Lex imported Data Forge legal contracts')
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
import polisyos.lex.artifacts
import polisyos.lex.errors
import polisyos.lex.types
"""
    project_root = Path(__file__).resolve().parents[4]
    environment = dict(os.environ, PYTHONPATH=str(project_root / "src"))
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_resolve_active_version_adapts_data_forge_read_result_to_lex_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Lex facade copies read results instead of exposing Data Forge's DTO."""
    produced = DataForgeResult(
        doc_source_id="ua:law:123",
        as_of_iso="2026-08-27",
        selected_doc_version_id="ua:law:123:v2",
        selected_doc_meta_artifact_id="a" * 64,
        selection_policy_id="lex.versioning_v1.effective_range_then_published_at",
        used_version_index_artifact_id="b" * 64,
        explanation=["as_of_normalized=2026-08-27"],
        candidates=[{"doc_version_id": "ua:law:123:v2", "effective_from": "2026-01-01"}],
    )
    monkeypatch.setattr(api.legal_read_api, "resolve_active_version", lambda **_kwargs: produced)

    resolved = api.resolve_active_version(
        cas=object(),  # type: ignore[arg-type]
        doc_source_id="ua:law:123",
        as_of_iso="2026-08-27",
        strategy=ActiveVersionStrategy(include_candidates=True),
    )

    assert isinstance(resolved, ActiveVersionResult)
    assert resolved is not produced
    assert resolved.doc_source_id == "ua:law:123"
    assert resolved.selected_doc_version_id == "ua:law:123:v2"
    assert resolved.candidates == [
        {"doc_version_id": "ua:law:123:v2", "effective_from": "2026-01-01"}
    ]


def test_resolve_active_version_translates_data_forge_policy_error_to_lex_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Data Forge failure semantics cross the read boundary as Lex-local errors."""
    produced_error = DataForgeValidationError(
        "version index doc_source_id mismatch",
        doc_source_id="ua:law:123",
        doc_version_id="ua:law:123:v2",
        details={"index_doc_source_id": "ua:law:456"},
    )
    monkeypatch.setattr(
        api.legal_read_api,
        "resolve_active_version",
        lambda **_kwargs: (_ for _ in ()).throw(produced_error),
    )

    with pytest.raises(LexValidationError) as raised:
        api.resolve_active_version(
            cas=object(),  # type: ignore[arg-type]
            doc_source_id="ua:law:123",
            as_of_iso="2026-08-27",
        )

    assert raised.value is not produced_error
    assert raised.value.category is ErrorCategory.VALIDATION
    assert raised.value.stage == "validation"
    assert raised.value.doc_source_id == "ua:law:123"
    assert raised.value.doc_version_id == "ua:law:123:v2"
    assert dict(raised.value.details) == {"index_doc_source_id": "ua:law:456"}
