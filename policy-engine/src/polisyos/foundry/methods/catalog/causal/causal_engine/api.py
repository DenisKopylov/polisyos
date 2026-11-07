"""Public CausalEngine API assembled from Phase 4.1 split modules."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.core.artifacts import ArtifactStore, ensure_ir_artifact_store

if TYPE_CHECKING:
    from polisyos.ir import ArtifactStore as IRArtifactStore
    from polisyos.ir import CausalGraphModelRef, ProofBundle, ProofBundleRef

import polisyos.foundry.methods.catalog.causal.causal_engine.artifacts as _artifacts
import polisyos.foundry.methods.catalog.causal.causal_engine.discovery as _discovery
import polisyos.foundry.methods.catalog.causal.causal_engine.identification as _identification

from .artifacts import CausalEngineArtifactsMixin
from .discovery import CausalEngineDiscoveryMixin
from .estimation import CausalEngineEstimationMixin
from .identification import CausalEngineIdentificationMixin
from .sensitivity import CausalEngineSensitivityMixin


class CausalEngine(
    CausalEngineDiscoveryMixin,
    CausalEngineIdentificationMixin,
    CausalEngineSensitivityMixin,
    CausalEngineEstimationMixin,
    CausalEngineArtifactsMixin,
):
    """Pearl-Bareinboim causal engine: identify -> compile -> estimate -> audit."""

    def __init__(
        self,
        registry: Any = None,
        knowledge_base: Any | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self._registry = registry
        self._kb = knowledge_base
        self._artifact_store = artifact_store
        # At most128 outstanding producer contexts; weak identities retain no result/graph.
        self._selected_identification_context: dict[
            int, tuple[Any, str, tuple[str, str] | None, str]
        ] = {}

    @property
    def _ir_artifact_store(self) -> IRArtifactStore | None:
        """Select the IR port while retaining the raw Core owner for Core-only work."""
        if self._artifact_store is None:
            return None
        return ensure_ir_artifact_store(self._artifact_store)

    def load_identification(
        self,
        ref: ProofBundleRef,
        *,
        graph_ref: CausalGraphModelRef,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
        conditions: frozenset[str] | None = None,
    ) -> ProofBundle:
        """Reconcile selected static ID/IDC evidence with the actual graph and current query.

        This reader reuses the existing identification algorithms and returns their
        freshly reconstructed structural proof. It admits no numerical estimate,
        empirical graph validity, composability sidecar or policy authority. The
        generic IR loaders remain available for historical unselected inspection.

        Args:
            ref: Exact selected proof artifact produced by ``run`` or ``audit``.
            graph_ref: Exact selected graph profile for the requested analysis.
            treatment: Intervention variables in the structural query.
            outcome: Requested structural outcome variables.
            conditions: Optional IDC conditioning variables.

        Returns:
            A reconciled conditional structural proof with the retained trace ref.

        Raises:
            ValueError: Selected profiles or graph/query/proof bindings disagree.
        """
        from polisyos.foundry.methods.catalog.causal.id_engine import _internal_proof_step_to_ir
        from polisyos.ir import (
            ArtifactRefModel,
            InterventionQueryRef,
            load_causal_evidence_bundle,
            load_causal_graph_model,
            load_intervention_query,
            load_proof_bundle,
        )

        store = self._ir_artifact_store
        if store is None:
            raise ValueError("identification_artifact_store_unavailable")
        if ref.manifest_profile_sha256 is None or graph_ref.manifest_profile_sha256 is None:
            raise ValueError("identification_selected_profile_required")
        graph = load_causal_graph_model(store, graph_ref)
        proof = load_proof_bundle(store, ref)
        manifest = store.get_manifest(ref)

        def require_input(role: str, selected: ArtifactRefModel) -> None:
            candidates = [item for item in manifest.inputs if item.role == role]
            if (
                selected.manifest_profile_sha256 is None
                or len(candidates) != 1
                or str(candidates[0].artifact_id) != str(selected.artifact_id)
                or candidates[0].manifest_profile_sha256 != selected.manifest_profile_sha256
            ):
                raise ValueError(f"identification_{role}_selection_mismatch")

        require_input("graph", graph_ref)
        current = self.identify(
            treatment, outcome, graph, graph_ref=graph_ref, conditions=conditions
        )
        _, expected, _, _, _, _, _ = self._materialize_identification_artifacts(
            current, graph=graph, treatment=treatment, outcome=outcome, data_dict=None
        )
        graph_binding = self._graph_artifact_ref(graph)
        expected = expected.model_copy(update={"graph_ref": graph_binding})
        if (
            proof.graph_ref != graph_binding
            or proof.metadata.get("source_graph_ref") != graph_binding
            or proof.metadata.get("structural_query_string") != expected.query_ref
            or proof.metadata.get("structural_basis") != "conditional_on_selected_graph"
            or proof.metadata.get("empirical_graph_validity") != "not_established"
            or proof.metadata.get("policy_authority") is not False
        ):
            raise ValueError("identification_graph_or_query_binding_mismatch")

        expected_query = expected.metadata.get("intervention_query")
        if isinstance(expected_query, dict):
            selected_query = InterventionQueryRef.model_validate(
                proof.metadata.get("intervention_query_ref")
            )
            require_input("query", selected_query)
            actual_query = load_intervention_query(store, selected_query)
            if actual_query.model_dump(mode="json") != expected_query or proof.query_ref != str(
                selected_query.artifact_id
            ):
                raise ValueError("identification_query_payload_mismatch")
        elif proof.query_ref != expected.query_ref:
            raise ValueError("identification_query_payload_mismatch")

        # Reference-bearing persistence/composability attachments are outside this
        # reader's structural claim and are not returned as admitted authority.
        # All remaining present and future proof fields are compared generically.
        excluded = {
            "metadata",
            "query_ref",
            "composability_status",
            "proof_support_projection_hash",
        }
        excluded.update(
            name
            for name in type(proof).model_fields
            if isinstance(getattr(proof, name), ArtifactRefModel)
        )
        if proof.model_dump(mode="json", exclude=excluded) != expected.model_dump(
            mode="json", exclude=excluded
        ):
            raise ValueError("identification_proof_replay_mismatch")
        if proof.proof_trace_ref is None:
            raise ValueError("identification_proof_trace_unavailable")
        require_input("proof_trace", proof.proof_trace_ref)
        trace = load_causal_evidence_bundle(store, proof.proof_trace_ref)
        expected_ast = expected.estimand_ast or {}
        expected_steps = tuple(
            _internal_proof_step_to_ir(step) for step in getattr(current, "proof_steps", ())
        )
        if (
            trace.graph_fingerprint != _artifacts._fingerprint(graph.model_dump(mode="json"))
            or trace.query_str != expected.query_ref
            or trace.estimand_ast != expected_ast
            or trace.estimand_fingerprint
            != (_artifacts._fingerprint(expected_ast) if expected_ast else "")
            or trace.proof_steps != expected_steps
        ):
            raise ValueError("identification_proof_trace_replay_mismatch")
        return expected.model_copy(
            update={
                "query_ref": proof.query_ref,
                "proof_trace_ref": proof.proof_trace_ref,
                "metadata": {
                    **expected.metadata,
                    "source_graph_ref": graph_binding,
                    "selected_graph_ref": graph_ref.model_dump(mode="json"),
                    "selected_proof_ref": ref.model_dump(mode="json"),
                    "structural_query_string": expected.query_ref,
                    "structural_basis": "conditional_on_selected_graph",
                    "empirical_graph_validity": "not_established",
                    "policy_authority": False,
                    "unadmitted_extent": "numerical_estimation_and_composability_sidecars",
                },
            }
        )


_artifacts.CausalEngine = CausalEngine
_discovery.CausalEngine = CausalEngine
_identification.CausalEngine = CausalEngine


__all__ = ["CausalEngine"]
