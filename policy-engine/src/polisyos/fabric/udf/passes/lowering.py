from __future__ import annotations

from polisyos.ir.data_views import DataViewRequest
from polisyos.fabric.udf.plan import DataViewPlan


def lowering_pass(request: DataViewRequest, plan: DataViewPlan) -> DataViewPlan:
    """
    Pass 5: lowering placeholder. In future will emit DataFetchPlan/ProgramGraph/EvidencePlan.
    """
    return plan
