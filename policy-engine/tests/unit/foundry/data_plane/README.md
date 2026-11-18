# Foundry Data Plane Tests

These tests exercise the binding owner from selected CAS inputs to the arguments
read by Foundry methods. The fixtures cover current and historical manifests,
exact scalar and entity-vector shapes, persistent state slots, and bindings
scoped to individual execution steps.

Run the suite from `policy-engine/` with
`uv run pytest tests/unit/foundry/data_plane -q`. For certified derivations,
start with `test_selected_method_input_steps.py` and keep both the valid replay
alongside the missing recipe, tensor, and occurrence controls. The owner
lives in [Foundry data plane](../../../../src/polisyos/foundry/data_plane/).
