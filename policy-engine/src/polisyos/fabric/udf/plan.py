from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from polisyos.ir.data_views import AccessTier, DataViewType


@dataclass(frozen=True)
class DataViewPlan:
    request_id: str
    view_type: DataViewType
    dataset_name: str
    table: Optional[str]
    sql: Optional[str]
    params: List[Any]
    cypher: Optional[str]
    cypher_params: Dict[str, Any]
    access_tier: AccessTier
    redacted_fields: List[str]
