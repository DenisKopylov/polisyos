"""Prompt templates for article extraction pipeline."""

from polisyos.data_forge.domains.academic.batch.prompts.boundary_conditions import (
    BOUNDARY_CONDITIONS_SCHEMA_HINT,
)
from polisyos.data_forge.domains.academic.batch.prompts.causal_claims import (
    CAUSAL_CLAIMS_SCHEMA_HINT,
)
from polisyos.data_forge.domains.academic.batch.prompts.claim_adjudication import (
    CLAIM_ADJUDICATION_PROMPT_VARIANTS,
    CLAIM_ADJUDICATION_SCHEMA_HINT,
)
from polisyos.data_forge.domains.academic.batch.prompts.context_extraction import (
    CONTEXT_EXTRACTION_SCHEMA_HINT,
)
from polisyos.data_forge.domains.academic.batch.prompts.empirical_parameters import (
    EMPIRICAL_PARAMETERS_SCHEMA_HINT,
)
from polisyos.data_forge.domains.academic.batch.prompts.mechanisms import MECHANISMS_SCHEMA_HINT
from polisyos.data_forge.domains.academic.batch.prompts.moderator_extraction import (
    MODERATOR_EXTRACTION_SCHEMA_HINT,
)
from polisyos.data_forge.domains.academic.batch.prompts.paper_classification import (
    PAPER_CLASSIFICATION_PROMPT,
)
from polisyos.data_forge.domains.academic.batch.prompts.screening import SCREENING_PROMPT

__all__ = [
    "BOUNDARY_CONDITIONS_SCHEMA_HINT",
    "CAUSAL_CLAIMS_SCHEMA_HINT",
    "CLAIM_ADJUDICATION_PROMPT_VARIANTS",
    "CLAIM_ADJUDICATION_SCHEMA_HINT",
    "CONTEXT_EXTRACTION_SCHEMA_HINT",
    "EMPIRICAL_PARAMETERS_SCHEMA_HINT",
    "MECHANISMS_SCHEMA_HINT",
    "MODERATOR_EXTRACTION_SCHEMA_HINT",
    "PAPER_CLASSIFICATION_PROMPT",
    "SCREENING_PROMPT",
]
