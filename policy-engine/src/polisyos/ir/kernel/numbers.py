"""Public kernel numbers module API."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BeforeValidator, Field
from typing_extensions import Annotated

from .base import reject_float

DecimalValue = Annotated[Decimal, BeforeValidator(reject_float)]
NonNegativeDecimal = Annotated[Decimal, BeforeValidator(reject_float), Field(ge=0)]
PositiveDecimal = Annotated[Decimal, BeforeValidator(reject_float), Field(gt=0)]
