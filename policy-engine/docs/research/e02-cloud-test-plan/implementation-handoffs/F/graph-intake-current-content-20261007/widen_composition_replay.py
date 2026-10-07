from pathlib import Path
p=Path('/workspace/e02-F-graph-20261006/policy-engine/src/polisyos/scientist/nodes/builtins/causal/reconcile_causal_graph.py')
s=p.read_text();start=s.index('    try:\n        composed_graph = _resolve_graph_ref',s.index('def _apply_query_preservation_hook('));end=s.index('\n    traces = evaluate_query_preservation_batch(',start)
replacement='''    try:
        composed_graph = _resolve_graph_ref(ctx, graph_ref_payload)
        certificate = _resolve_typed_source(
            ctx, certificate_ref_payload,
            kind="ir.composition_certificate", model=CompositionCertificate,
        )
        interface_mapping = _resolve_typed_source(
            ctx, mapping_ref_payload, kind="ir.interface_mapping", model=InterfaceMapping,
        )
        if not certificate.source_fragment_refs:
            raise ValueError("Current composition source provenance is required for graph reuse")
        fragments = []
        for fragment_id, artifact_id in sorted(certificate.source_fragment_refs.items()):
            fragment = _resolve_typed_source(
                ctx, artifact_id, kind="ir.scm_fragment", model=SCMFragment,
            )
            if fragment.fragment_id != fragment_id:
                raise ValueError("Composition source fragment identity differs from its CAS body")
            fragments.append(fragment)
        actual_graph_refs = {fragment.fragment_id: str(fragment.graph_ref) for fragment in fragments}
        if actual_graph_refs != certificate.source_fragment_graph_refs:
            raise ValueError("Composition graph sources differ from actual fragment CAS content")
        fragment_graphs = _load_fragment_graphs(ctx, fragments)
        alignment_ref = state.artifacts_index.get(ARTIFACT_ALIGNMENT_REPORT_REF)
        if alignment_ref is None:
            raise ValueError("Actual alignment report is required for graph reuse")
        alignment = _resolve_typed_source(
            ctx, alignment_ref, kind="ir.alignment_report", model=AlignmentReport,
        )
        reproduced = ComposeSCMFragments.pure_step(
            FragmentCompositionData(
                fragments=fragments,
                fragment_graphs=fragment_graphs,
                alignment_report=alignment,
                interface_mapping=interface_mapping,
                source_fragment_refs=dict(certificate.source_fragment_refs),
                source_fragment_graph_refs=actual_graph_refs,
                metadata={
                    "alignment_report_ref": str(_selected_ref(alignment_ref, kind="ir.alignment_report").artifact_id),
                    "interface_mapping_ref": str(_selected_ref(mapping_ref_payload, kind="ir.interface_mapping").artifact_id),
                },
                direct_stitch_pairs=_parse_direct_stitch_pairs(state.params.get("direct_stitch_pairs")),
            ),
            params={},
        )
        if reproduced.get("composed_graph") != composed_graph:
            raise ValueError("Cached graph differs from actual composition source content")
        expected_certificate = reproduced["composition_certificate"].model_copy(
            update={"composed_graph_ref": str(_selected_ref(graph_ref_payload, kind="ir.causal_graph_model").artifact_id)}
        )
        # Failure-card refs are persistence outputs: compare their complete bodies.
        cards = reproduced.get("failure_cards", [])
        if cards or certificate.failure_card_bundle_ref is not None:
            if certificate.failure_card_bundle_ref is None:
                raise ValueError("Actual composition failure-card bundle is missing")
            bundle = _resolve_typed_source(
                ctx, certificate.failure_card_bundle_ref,
                kind="ir.composition_failure_card_bundle", model=CompositionFailureCardBundle,
            )
            expected_bundle = CompositionFailureCardBundle(cards=cards, metadata={
                "composition_status": expected_certificate.status,
                "structure_status": expected_certificate.structure_status,
                "review_status": expected_certificate.review_status,
                "source_fragment_ids": sorted(fragment.fragment_id for fragment in fragments),
            })
            if bundle != expected_bundle:
                raise ValueError("Cached failure cards differ from actual composition result")
        # Only query caches and the separately validated persistence pointer are
        # operational. All producer semantics, source refs and metadata must agree.
        if certificate.model_dump(mode="json", exclude={
            "checked_queries", "query_certificates", "failure_card_bundle_ref",
        }) != expected_certificate.model_dump(mode="json", exclude={
            "checked_queries", "query_certificates", "failure_card_bundle_ref",
        }):
            raise ValueError("Cached certificate differs from actual composition result")
        if expected_certificate.status == "broken":
            raise ValueError("Actual composition result refuses graph admission")
        # Evaluate fresh: an old operational query cache is not source authority.
        certificate = expected_certificate.model_copy(update={
            "failure_card_bundle_ref": certificate.failure_card_bundle_ref,
        })
        _validate_static_admg(composed_graph)
    except _RECONCILE_EXECUTION_ERRORS as exc:
        return NodeOutcome(
            status="fail", state=state,
            error=NodeError(code=node_errors.ERROR_INVALID_STATE,
                message=f"failed to reconcile composition graph content: {exc}"),
        )
'''
s=s[:start]+replacement+s[end:]
old='''            alignment_report, interface_mapping, alignment_report_ref, interface_mapping_ref = (
                _load_precomputed_alignment(ctx, state)
            )
            try:
                verification_config = AlignmentVerificationConfig.model_validate('''
new='''            try:
                alignment_report, interface_mapping, alignment_report_ref, interface_mapping_ref = (
                    _load_precomputed_alignment(ctx, state)
                )
                verification_config = AlignmentVerificationConfig.model_validate('''
assert old in s;s=s.replace(old,new)
# Whole source resolution failure must follow the canonical node failure contract.
s=s.replace('except _RECONCILE_VALIDATION_ERRORS as exc:\n                return NodeOutcome(\n                    status="fail",\n                    state=state,\n                    error=NodeError(\n                        code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,\n                        message=f"fragment alignment verification failed: {exc}",','except _RECONCILE_LOAD_ERRORS as exc:\n                return NodeOutcome(\n                    status="fail",\n                    state=state,\n                    error=NodeError(\n                        code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,\n                        message=f"fragment alignment verification failed: {exc}",')
needle='''    diagnostics = dict(new_state.params.get("reconciliation_diagnostics", {}))
    diagnostics["query_preservation_statuses"] = dict(query_statuses)'''
update='''    new_state.params["needs_expert_review"] = bool(reproduced.get("needs_expert_review", False))
    new_state.params["reconciliation_warnings"] = list(reproduced.get("warnings", []))
    new_state.params["composition_blocking_reasons"] = list(reproduced.get("blocking_reasons", []))
    diagnostics = dict(new_state.params.get("reconciliation_diagnostics", {}))
    diagnostics.update({
        "composition_status": certificate.status,
        "structure_status": certificate.structure_status,
        "review_status": certificate.review_status,
        "query_preservation_statuses": dict(query_statuses),
    })'''
assert needle in s;s=s.replace(needle,update)
s=s.replace('from pydantic import ValidationError','from pydantic import BaseModel, ValidationError').replace('if hasattr(ref, "model_dump")','if isinstance(ref, BaseModel)')
p.write_text(s)
