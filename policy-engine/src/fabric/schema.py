from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentRow(BaseModel):
    agent_id: str = Field(..., max_length=64)
    agent_type: str = Field("agent", max_length=32)
    age: int = Field(..., ge=0, le=120)
    income: float = Field(..., ge=0)
    savings: float = Field(..., ge=0)
    is_employed: bool

    model_config = ConfigDict(extra="forbid")


class MacroRow(BaseModel):
    run_id: str = Field(..., max_length=64)
    step: int = Field(..., ge=0)
    gdp: float = Field(..., ge=0)
    unemployment_rate: float = Field(..., ge=0, le=1)
    inflation_rate: float = Field(..., ge=-100, le=1000)
    avg_price: float = Field(..., ge=0)
    avg_income: float = Field(..., ge=0)
    government_balance: float

    model_config = ConfigDict(extra="forbid")


class InteractionRow(BaseModel):
    from_id: str = Field(..., max_length=64)
    to_id: str = Field(..., max_length=64)
    step: int = Field(..., ge=0)
    amount: float = Field(..., ge=0)
    type: str = Field(..., max_length=64)
    relation_type: Optional[str] = Field(None, max_length=64)

    model_config = ConfigDict(extra="forbid")
