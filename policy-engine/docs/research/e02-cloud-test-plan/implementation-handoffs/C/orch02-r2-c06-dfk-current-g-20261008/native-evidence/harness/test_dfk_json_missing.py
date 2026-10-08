"""Add the unexecuted JSON boundary missing-input combination only."""
from test_dfk_boundary_modes import test_additional_cli_boundary_mode_preserves_real_json_receipt as run_boundary_case


def test_json_boundary_missing_selected_input(tmp_path):
    run_boundary_case(tmp_path, 'json', True)
