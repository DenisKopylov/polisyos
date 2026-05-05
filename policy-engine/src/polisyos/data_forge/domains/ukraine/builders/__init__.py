"""Split Ukraine stage-builder surface owned by Data Forge."""

from __future__ import annotations

from polisyos.data_forge.domains.ukraine.models import StageId

from .calibration import *
from .common import *
from .demography import *
from .release import *
from .sources import *

STAGE_BUILDERS = {
    StageId.D0_P0: build_d0_p0_stage,
    StageId.D1: build_d1_stage,
    StageId.D2: build_d2_stage,
    StageId.D3: build_d3_stage,
    StageId.D4: build_d4_stage,
    StageId.D5: build_d5_stage,
}

__all__ = tuple(name for name in globals() if not name.startswith("__"))
