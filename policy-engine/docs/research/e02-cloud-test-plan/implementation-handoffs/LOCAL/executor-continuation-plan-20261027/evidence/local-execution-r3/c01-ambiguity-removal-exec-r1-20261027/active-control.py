def _unique_workflow_report_node(payload: dict[str, Any], *, alias: str) -> dict[str, Any] | None:
    """Select one raw named node, refusing ambiguity before any node projection."""
    rows = payload.get('nodes')
    if not isinstance(rows, list):
        raise SimulationResultProjectionError('simulation_result_node_binding_mismatch', 'The workflow report has no valid node binding collection')
    selected: dict[str, Any] | None = None
    for row in rows:
        row_alias = _as_str(row.get('alias')) if isinstance(row, dict) else None
        if not row_alias:
            raise SimulationResultProjectionError('simulation_result_node_binding_mismatch', 'The workflow report carries a node whose relevance cannot be established')
        if row_alias != alias:
            continue
        if selected is not None and _c01_ambiguity_enabled():
            raise SimulationResultProjectionError('simulation_result_node_binding_mismatch', 'The named workflow node binding is ambiguous')
        selected = row
    return selected
