"""Module-invoked Runtime API server with an optional source-owned Legal profile."""

from __future__ import annotations

import argparse
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, cast

from polisyos.data_forge.read_api import legal as legal_read_api
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import (
    LegalQueryEncoderProvider,
    RuntimeContainerOverrides,
)

if TYPE_CHECKING:
    from polisyos.data_forge.read_api.legal import LegalRuntimeMaterialOwner


def create_profiled_runtime_api_app(
    *,
    runtime_material_profile_root: Path | None = None,
    cas_root: Path | str = Path(".polisyos/cas"),
    core_runs_root: Path | str | None = None,
) -> object:
    """Compose the ordinary Runtime API with an optional operator-selected profile.

    The profile root is process configuration only. It is never selected by an
    HTTP request, and a malformed explicit root raises the Legal owner's typed
    refusal rather than silently constructing a profileless provider.
    """
    if runtime_material_profile_root is None:
        return create_runtime_api_app(
            cas_root=cas_root,
            core_runs_root=core_runs_root,
        )

    owner_type = cast(
        "type[LegalRuntimeMaterialOwner]",
        legal_read_api.LegalRuntimeMaterialOwner,
    )
    owner = owner_type.from_profile_root(runtime_material_profile_root)
    overrides = RuntimeContainerOverrides(
        legal_query_encoder_provider=LegalQueryEncoderProvider(runtime_material_owner=owner)
    )
    return create_runtime_api_app(
        cas_root=cas_root,
        core_runs_root=core_runs_root,
        container_overrides=overrides,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the PolicyOS Runtime API with optional local Legal profile wiring."
    )
    parser.add_argument(
        "--runtime-material-profile-root",
        type=Path,
        default=None,
        help=(
            "Use the source-pinned Legal runtime profile rooted at this directory; "
            "requires hf-cache/ and asset-file-manifest.txt."
        ),
    )
    parser.add_argument("--cas-root", type=Path, default=Path(".polisyos/cas"))
    parser.add_argument("--core-runs-root", type=Path, default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--log-level",
        choices=("critical", "error", "warning", "info", "debug"),
        default="info",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run Uvicorn with a callable factory in this module's Python process context."""
    args = _build_parser().parse_args(argv)
    import uvicorn

    app_factory = partial(
        create_profiled_runtime_api_app,
        runtime_material_profile_root=args.runtime_material_profile_root,
        cas_root=args.cas_root,
        core_runs_root=args.core_runs_root,
    )
    config = uvicorn.Config(
        app_factory,
        factory=True,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )
    uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
