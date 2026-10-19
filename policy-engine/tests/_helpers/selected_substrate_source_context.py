"""Select candidate-only source roots for substrate integration tests."""

from __future__ import annotations

from pathlib import Path

from tools.quality.validation.substrate_source_context import (
    CandidateSubstrateSourceContext,
    candidate_source_context_for_entrypoint,
)


def select_substrate_source_context(
    code_root: Path,
    *,
    workspace_root: Path,
    source_owner_root: Path | None = None,
) -> CandidateSubstrateSourceContext:
    """Bind a test's code root, linked data owner, and isolated WMR workspace."""

    selected_owner = source_owner_root
    if selected_owner is None:
        selected_owner = (code_root.resolve() / "production_data").resolve().parent
    context = candidate_source_context_for_entrypoint(
        code_root,
        source_owner_root=selected_owner,
        workspace_root=workspace_root,
    )
    assert context is not None
    return context
