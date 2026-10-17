from __future__ import annotations

from pathlib import Path

import pytest

import polisyos.core.artifacts as core_artifacts
import polisyos.data_forge as data_forge
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.data_forge.domains.legal.contracts import (
    LegalDocSource,
)
from polisyos.data_forge.domains.legal.contracts import (
    LexError as DataForgeLexError,
)
from polisyos.data_forge.domains.legal.contracts import (
    LexValidationError as DataForgeLexValidationError,
)
from polisyos.data_forge.kernel import (
    DataForgeError,
    DataForgeValidationError,
    SchemaCompatibilityError,
    SnapshotCommitError,
)
from polisyos.data_forge.kernel.artifacts import load_json_artifact
from polisyos.lex import LexValidationError as RuntimeLexValidationError


def test_generic_exceptions_have_one_kernel_owner_and_root_exports() -> None:
    """The public root and kernel names resolve to the same generic error classes."""
    assert data_forge.DataForgeError is DataForgeError
    assert data_forge.DataForgeValidationError is DataForgeValidationError
    assert data_forge.SchemaCompatibilityError is SchemaCompatibilityError
    assert data_forge.SnapshotCommitError is SnapshotCommitError

    assert DataForgeError.__module__ == "polisyos.data_forge.kernel"
    assert DataForgeValidationError.__module__ == "polisyos.data_forge.kernel"
    assert SchemaCompatibilityError.__module__ == "polisyos.data_forge.kernel"
    assert SnapshotCommitError.__module__ == "polisyos.data_forge.kernel"
    assert issubclass(DataForgeValidationError, DataForgeError)
    assert issubclass(DataForgeValidationError, ValueError)
    assert issubclass(SchemaCompatibilityError, DataForgeValidationError)
    assert issubclass(SnapshotCommitError, DataForgeError)


def test_legal_error_owner_preserves_mro_and_runtime_lex_separation() -> None:
    """Legal corpus errors remain distinct from the runtime Lex taxonomy."""
    assert DataForgeLexError.__module__ == "polisyos.data_forge.domains.legal.contracts"
    assert DataForgeLexValidationError.__module__ == ("polisyos.data_forge.domains.legal.contracts")
    assert DataForgeLexValidationError.__mro__ == (
        DataForgeLexValidationError,
        DataForgeLexError,
        PolicyOSError,
        Exception,
        BaseException,
        object,
    )
    assert not issubclass(DataForgeLexValidationError, DataForgeError)
    assert DataForgeLexValidationError is not RuntimeLexValidationError

    error = DataForgeLexValidationError(
        "invalid legal source",
        doc_source_id="ua:law:42",
        doc_version_id="ua:law:42:v1",
        details={"field": "license"},
    )
    assert error.category is ErrorCategory.VALIDATION
    assert error.stage == "validation"
    assert error.doc_source_id == "ua:law:42"
    assert error.doc_version_id == "ua:law:42:v1"
    assert error.to_dict() == {
        "type": "LexValidationError",
        "message": "invalid legal source",
        "category": "validation",
        "stage": "validation",
        "code": None,
        "details": {"field": "license"},
    }

    with pytest.raises(DataForgeLexValidationError, match="exactly one"):
        LegalDocSource(license="fixture-license")


def test_kernel_json_loader_defaults_generic_but_keeps_legal_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The shared kernel default is domain-neutral; callers may select legal semantics."""
    monkeypatch.setattr(
        core_artifacts,
        "load_core_json_artifact",
        lambda _cas, _artifact_id: ["not", "an", "object"],
    )
    artifact_id = "sha256:" + "a" * 64
    cas = FileSystemCAS(tmp_path)

    with pytest.raises(DataForgeValidationError, match="payload must be a JSON object"):
        load_json_artifact(cas, artifact_id)

    with pytest.raises(DataForgeLexValidationError, match="payload must be a JSON object"):
        load_json_artifact(cas, artifact_id, error_cls=DataForgeLexValidationError)
