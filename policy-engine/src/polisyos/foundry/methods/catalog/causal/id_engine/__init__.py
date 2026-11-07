"""Compatibility surface for a Phase 4.1 split module."""

from __future__ import annotations

from . import core as _core

globals().update({name: getattr(_core, name) for name in dir(_core) if not name.startswith("__")})
from . import transport as _transport

globals().update(
    {name: getattr(_transport, name) for name in dir(_transport) if not name.startswith("__")}
)
from . import counterfactual as _counterfactual

globals().update(
    {
        name: getattr(_counterfactual, name)
        for name in dir(_counterfactual)
        if not name.startswith("__")
    }
)
from . import api as _api

globals().update({name: getattr(_api, name) for name in dir(_api) if not name.startswith("__")})

# Keep explicit routes for the finite names consumed by causal_engine. The
# compatibility namespace copy remains available for the rest of the legacy API.
from polisyos.foundry.methods.catalog.causal._id_contracts import (
    CtfQuery as CtfQuery,
)
from polisyos.foundry.methods.catalog.causal._id_contracts import (
    HedgeCertificate as HedgeCertificate,
)
from polisyos.foundry.methods.catalog.causal._id_contracts import (
    IdentificationResult as IdentificationResult,
)
from polisyos.foundry.methods.catalog.causal._id_contracts import (
    IdentificationStatus as IdentificationStatus,
)
from polisyos.foundry.methods.catalog.causal._id_contracts import (
    ProofStep as ProofStep,
)
from polisyos.foundry.methods.catalog.causal._id_contracts import (
    RequiredDataSpec as RequiredDataSpec,
)
from polisyos.foundry.methods.catalog.causal._id_contracts import (
    SourceDomain as SourceDomain,
)

from .core import (
    id_algorithm as id_algorithm,
)
from .core import (
    id_with_oracle_fallback as id_with_oracle_fallback,
)
from .core import (
    idc_algorithm as idc_algorithm,
)
from .core import (
    tr_algorithm as tr_algorithm,
)
from .counterfactual import (
    _counterfactual_ast as _counterfactual_ast,
)
from .counterfactual import (
    _normalize_counterfactual_query as _normalize_counterfactual_query,
)
from .counterfactual import (
    id_star_algorithm as id_star_algorithm,
)
from .counterfactual import (
    idc_star_algorithm as idc_star_algorithm,
)
from .transport import (
    conditional_intervention_id as conditional_intervention_id,
)
from .transport import (
    dynamic_intervention_id as dynamic_intervention_id,
)
from .transport import (
    multi_outcome_id as multi_outcome_id,
)
from .transport import (
    mz_id_algorithm as mz_id_algorithm,
)
from .transport import (
    sid_algorithm as sid_algorithm,
)
from .transport import (
    z_id_algorithm as z_id_algorithm,
)

__all__ = [name for name in globals() if not name.startswith("__") and not name.startswith("_")]
