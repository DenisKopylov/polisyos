from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from polisyos.academic.knowledge.skg_query import SKGQuery
from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.causal.protocols import LiteraturePriorBuildData
from polisyos.ir.analytics.literature import LiteratureCausalPrior, LiteratureEdgePrior


def _build_empty_prior(
    *,
    variables: list[str],
    metadata: Mapping[str, Any] | None = None,
) -> tuple[LiteratureCausalPrior, list[str]]:
    prior = LiteratureCausalPrior(
        edges=[],
        skg_version_id=None,
        skg_snapshot_ref=None,
        metadata={**dict(metadata or {}), "variables": list(variables)},
    )
    return prior, []


@foundry_method(
    namespace="causal.prior",
    version="1.0.0",
    tags={"causal", "literature", "prior"},
)
class BuildLiteraturePrior:
    """Materialize LiteratureCausalPrior and graph projection from SKG tables."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="build_literature_prior",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="literature_prior_build_data",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("request", "json"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="literature_prior",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("artifact", "json"),
                ),
                SlotSpec(
                    name="literature_prior_graph",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("artifact", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="skg_db_path", default=None),
            ParameterSpec(name="skg_index_dir", default=None),
            ParameterSpec(name="min_confidence", default=0.2),
            ParameterSpec(name="limit", default=256),
            ParameterSpec(name="domain", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Build LiteratureCausalPrior from SKG edges and project it to CausalGraphModel."
        ),
        tags=frozenset({"causal", "literature", "prior"}),
        assumptions={
            "graceful_degradation": "Unavailable SKG returns empty prior with warning.",
            "lineage": "Result metadata carries skg snapshot/version for reproducibility.",
        },
        when_to_use="Incorporate literature-informed causal priors into graph discovery; constrain structure learning with prior knowledge",
        when_not_to_use="No SKG available and purely data-driven discovery is preferred; variables are entirely novel with no prior literature",
        output_interpretation="Literature prior edges with confidence scores. Higher confidence = stronger prior. Empty prior = no matching literature found.",
    )

    @staticmethod
    def pure_step(
        state: LiteraturePriorBuildData | Mapping[str, Any],
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        payload = (
            state
            if isinstance(state, LiteraturePriorBuildData)
            else LiteraturePriorBuildData.model_validate(state)
        )
        warnings: list[str] = []

        min_confidence = float(params.get("min_confidence", payload.min_confidence))
        limit = int(params.get("limit", payload.limit))
        domain_value = params.get("domain", payload.domain)
        domain = None if domain_value is None else str(domain_value)

        db_path_raw = params.get("skg_db_path", payload.skg_db_path)
        if db_path_raw is None:
            prior, _ = _build_empty_prior(
                variables=payload.variables,
                metadata={"build_status": "missing_skg_db_path"},
            )
            warnings.append("SKG path is not configured; returning empty literature prior.")
            return {
                "literature_prior": prior,
                "literature_prior_graph": prior.to_causal_graph_model(nodes=payload.variables),
                "warnings": warnings,
            }

        db_path = str(db_path_raw)

        index_dir_raw = params.get("skg_index_dir", payload.skg_index_dir)
        if index_dir_raw is not None:
            index_dir = str(index_dir_raw)
        else:
            index_dir = db_path.rsplit("/", 1)[0] if "/" in db_path else "."

        query: SKGQuery | None = None
        try:
            query = SKGQuery(db_path=db_path, index_dir=index_dir)
            rows = query.query_prior_for_variables(
                payload.variables,
                min_confidence=min_confidence,
                limit=limit,
                domain=domain,
                edge_layer="hybrid",
            )
            version_id = query.latest_skg_version_id()
            snapshot_ref = query.skg_snapshot_ref(version_id=version_id)
        except Exception as exc:
            prior, _ = _build_empty_prior(
                variables=payload.variables,
                metadata={
                    "build_status": "skg_query_failed",
                    "skg_db_path": str(db_path),
                    "error": str(exc),
                },
            )
            warnings.append(
                "Literature prior build degraded: SKG query failed; returning empty prior."
            )
            return {
                "literature_prior": prior,
                "literature_prior_graph": prior.to_causal_graph_model(nodes=payload.variables),
                "warnings": warnings,
            }
        finally:
            if query is not None:
                query.close()

        edges: list[LiteratureEdgePrior] = []
        for row in rows:
            edges.append(
                LiteratureEdgePrior(
                    src=str(row["src"]),
                    dst=str(row["dst"]),
                    confidence=float(row["confidence"]),
                    n_articles=int(row["n_articles"]),
                    evidence_strength=str(row["evidence_strength"]),
                    article_refs=[str(item) for item in row.get("article_refs", [])],
                    scope_conditions=[str(item) for item in row.get("scope_conditions", [])],
                    direction=str(row.get("direction", "mixed") or "mixed"),
                )
            )

        prior = LiteratureCausalPrior(
            edges=edges,
            skg_version_id=version_id,
            skg_snapshot_ref=snapshot_ref,
            metadata={
                "build_status": "ok",
                "variables": list(payload.variables),
                "domain": domain,
                "min_confidence": min_confidence,
                "limit": limit,
                **payload.metadata,
            },
        )
        graph = prior.to_causal_graph_model(nodes=payload.variables, min_confidence=min_confidence)
        return {
            "literature_prior": prior,
            "literature_prior_graph": graph,
            "warnings": warnings,
        }


__all__ = ["BuildLiteraturePrior"]
