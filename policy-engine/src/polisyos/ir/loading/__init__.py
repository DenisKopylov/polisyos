"""Owner-curated lazy facade for IR loading and source-citation contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.ir.api import LOADING_FACADE_EXPORTS, lazy_dir, resolve_lazy_export

if TYPE_CHECKING:
    from polisyos.ir.loading.citations import (
        AnchorKind as AnchorKind,
    )
    from polisyos.ir.loading.citations import (
        CitationRef as CitationRef,
    )
    from polisyos.ir.loading.citations import (
        DocumentRef as DocumentRef,
    )
    from polisyos.ir.loading.citations import (
        FragmentLocator as FragmentLocator,
    )
    from polisyos.ir.loading.fact_log import (
        Fact as Fact,
    )
    from polisyos.ir.loading.fact_log import (
        FactBatch as FactBatch,
    )
    from polisyos.ir.loading.fact_log import (
        FactLegal as FactLegal,
    )
    from polisyos.ir.loading.fact_log import (
        FactPIIEntity as FactPIIEntity,
    )
    from polisyos.ir.loading.fact_log import (
        FactProvenance as FactProvenance,
    )
    from polisyos.ir.loading.fact_log import (
        FactSegmentManifest as FactSegmentManifest,
    )
    from polisyos.ir.loading.fact_log import (
        FactTrust as FactTrust,
    )
    from polisyos.ir.loading.fact_log import (
        build_fact_id as build_fact_id,
    )

__all__ = sorted(LOADING_FACADE_EXPORTS)


def __getattr__(name: str) -> Any:
    return resolve_lazy_export(name, namespace=globals(), exports=LOADING_FACADE_EXPORTS)


def __dir__() -> list[str]:
    return lazy_dir(globals(), LOADING_FACADE_EXPORTS)
