from pathlib import Path

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.trust import persist_uncertainty_bounds, two_pass_compare


def test_two_pass_compare_bounds() -> None:
    bounds = two_pass_compare(optimistic_value=10.0, pessimistic_value=6.0)
    assert bounds.lower == 6.0
    assert bounds.upper == 10.0
    assert bounds.value == 8.0
    assert bounds.method == "two_pass_compare"


def test_persist_uncertainty_bounds(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    bounds = two_pass_compare(optimistic_value=5.0, pessimistic_value=3.0)
    ref = persist_uncertainty_bounds(store, bounds)

    manifest = store.get_manifest(ArtifactID.model_validate(ref.artifact_id))
    assert manifest.kind == "fabric.uncertainty_bounds"
