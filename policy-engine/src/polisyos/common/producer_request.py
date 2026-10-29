"""Generic candidate request preparation and emission facade.

This source-issued carrier grants no institutional authority or external sender
identity. Semantic stage vocabularies stay in the actual producer package.
"""

from ._producer_request import (
    _binding_scope as producer_request_scope,
)
from ._producer_request import (
    _call_context as consume_producer_request_context,
)
from ._producer_request import (
    _capture_payload as capture_producer_payload,
)
from ._producer_request import (
    _derive_payload as derive_producer_payload,
)
from ._producer_request import (
    _issue_args as issue_producer_request_args,
)
from ._producer_request import (
    _owned_request_context as owned_producer_request_context,
)
from ._producer_request import (
    _parse_context as parse_producer_request_context,
)
from ._producer_request import (
    _PreparedEmission as PreparedProducerEmission,
)
from ._producer_request import (
    _producer_payload as producer_payload,
)
from ._producer_request import (
    _ProducerBinding as ProducerRequestBinding,
)
from ._producer_request import (
    _read_payload as read_producer_payload,
)
from ._producer_request import (
    _request_args as producer_request_args,
)
from ._producer_request import (
    _validate_prepared_payload as validate_prepared_producer_payload,
)
from ._producer_request import (
    _without_context as without_producer_request_context,
)

__all__ = [
    "PreparedProducerEmission",
    "ProducerRequestBinding",
    "capture_producer_payload",
    "consume_producer_request_context",
    "derive_producer_payload",
    "issue_producer_request_args",
    "owned_producer_request_context",
    "parse_producer_request_context",
    "producer_payload",
    "producer_request_args",
    "producer_request_scope",
    "read_producer_payload",
    "validate_prepared_producer_payload",
    "without_producer_request_context",
]
