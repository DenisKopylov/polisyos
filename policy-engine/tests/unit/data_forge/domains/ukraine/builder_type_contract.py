"""Static consumer contract for the lazy Ukraine builder compatibility facade."""

from collections.abc import Callable
from pathlib import Path
from typing import Any, assert_type

from polisyos.data_forge.domains.ukraine import builders
from polisyos.data_forge.domains.ukraine.builders.contracts import StageBuildResult
from polisyos.data_forge.domains.ukraine.models import PipelineConfig, StageId


def check_builder_export_types(config: PipelineConfig, path: Path) -> None:
    """Require concrete callable and registry types at an ordinary importer."""
    assert_type(
        builders.STAGE_BUILDERS, dict[StageId, Callable[[PipelineConfig], StageBuildResult]]
    )
    assert_type(builders.build_d4_stage(config), StageBuildResult)
    assert_type(builders.build_d0_p0_stage(config), StageBuildResult)
    assert_type(builders.build_d2_stage(config), StageBuildResult)
    assert_type(builders._write_json(path, {"fixture": 1}), Path)
    assert_type(
        builders.MemoryAwareScheduler(max_workers=1, memory_budget_gib=1.0).run([]),
        dict[str, dict[str, Any]],
    )
