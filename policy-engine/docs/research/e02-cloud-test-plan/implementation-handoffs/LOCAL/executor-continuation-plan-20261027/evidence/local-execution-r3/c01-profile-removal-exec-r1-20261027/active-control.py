def _require_exact_artifact_ref_binding(expected: ArtifactRef, candidates: tuple[ArtifactRef, ...]) -> None:
    """Require every same-ID node ref to carry the complete selected identity."""
    expected_identity = artifact_ref_identity_key(expected)[:3]
    if not candidates or any((artifact_ref_identity_key(candidate)[:3] != expected_identity for candidate in candidates)):
        raise SimulationResultProjectionError('simulation_result_node_binding_mismatch', 'The named workflow node carries a conflicting simulation result ref')
