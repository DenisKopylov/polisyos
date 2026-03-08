"""Prompt templates for article extraction pipeline."""

from polisyos.academic.batch.prompts.boundary_conditions import BOUNDARY_CONDITIONS_SCHEMA_HINT
from polisyos.academic.batch.prompts.causal_claims import CAUSAL_CLAIMS_SCHEMA_HINT
from polisyos.academic.batch.prompts.claim_adjudication import (
    CLAIM_ADJUDICATION_PROMPT_VARIANTS,
    CLAIM_ADJUDICATION_SCHEMA_HINT,
)
from polisyos.academic.batch.prompts.empirical_parameters import EMPIRICAL_PARAMETERS_SCHEMA_HINT
from polisyos.academic.batch.prompts.mechanisms import MECHANISMS_SCHEMA_HINT
from polisyos.academic.batch.prompts.screening import SCREENING_PROMPT

__all__ = [
    "BOUNDARY_CONDITIONS_SCHEMA_HINT",
    "CAUSAL_CLAIMS_SCHEMA_HINT",
    "CLAIM_ADJUDICATION_PROMPT_VARIANTS",
    "CLAIM_ADJUDICATION_SCHEMA_HINT",
    "EMPIRICAL_PARAMETERS_SCHEMA_HINT",
    "MECHANISMS_SCHEMA_HINT",
    "SCREENING_PROMPT",
]
