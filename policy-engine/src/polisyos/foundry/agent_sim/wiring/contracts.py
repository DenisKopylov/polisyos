"""Define vectorized intervention payloads consumed by agent-sim executors.

These classes are the public boundary objects between compiled intervention
metadata and synthetic runtime state updates. They normalize firm lifecycle,
procurement shock, tax, and transfer inputs before executor classes mutate a
`GlobalState` snapshot.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import chex
import jax.numpy as jnp
import numpy as np
from jaxtyping import Array, Float, Int

from polisyos.ir.governance.policy_spec import CompiledLexIntervention
from polisyos.ir.observation.contracts import MultiplexGraphLayerId


class FirmLifecycleEventType(IntEnum):
    """Enumerate lifecycle event codes accepted by `FirmLifecycleEventBatch`."""

    ENTRY = 0
    EXIT = 1
    TYPE_TRANSITION = 2


_LAYER_CODE_MAP = {
    MultiplexGraphLayerId.BUDGET: 0,
    MultiplexGraphLayerId.PROCUREMENT: 1,
    MultiplexGraphLayerId.TRADE: 2,
    MultiplexGraphLayerId.DISTRESS: 3,
    MultiplexGraphLayerId.PUBLIC_SERVICE: 4,
}


def multiplex_layer_code(layer: MultiplexGraphLayerId | str) -> int:
    """Map a multiplex graph layer identifier to its compact integer code."""

    if isinstance(layer, str):
        normalized = MultiplexGraphLayerId(layer)
    else:
        normalized = layer
    return _LAYER_CODE_MAP[normalized]


@chex.dataclass(frozen=True)
class FirmLifecycleEventBatch:
    """Carry firm lifecycle events as aligned JAX arrays for vectorized updates.

    All fields must share the same leading `n_events` dimension. Missing
    optional numeric values are represented with `NaN` so executors can keep
    existing firm-state values when a record omits an update.
    """

    event_type: Int[Array, n_events]
    firm_id: Int[Array, n_events]
    cell_id: Int[Array, n_events]
    firm_type_id: Int[Array, n_events]
    sector_id: Int[Array, n_events]
    productivity: Float[Array, n_events]
    capital: Float[Array, n_events]
    cash: Float[Array, n_events]
    inventory: Float[Array, n_events]
    debt: Float[Array, n_events]
    wage_offer: Float[Array, n_events]
    price: Float[Array, n_events]

    @classmethod
    def empty(cls) -> FirmLifecycleEventBatch:
        """Return a zero-length batch that preserves dtypes expected by executors."""
        empty_i = jnp.zeros((0,), dtype=jnp.int32)
        empty_f = jnp.zeros((0,), dtype=jnp.float32)
        return cls(
            event_type=empty_i,
            firm_id=empty_i,
            cell_id=empty_i,
            firm_type_id=empty_i,
            sector_id=empty_i,
            productivity=empty_f,
            capital=empty_f,
            cash=empty_f,
            inventory=empty_f,
            debt=empty_f,
            wage_offer=empty_f,
            price=empty_f,
        )

    @classmethod
    def from_records(
        cls,
        records: Sequence[Mapping[str, Any]],
    ) -> FirmLifecycleEventBatch:
        """Build a vectorized lifecycle batch from dict-like records.

        Args:
            records: Sequence of mappings containing `event_type` and optional
                firm state fields.

        Returns:
            `FirmLifecycleEventBatch` with one array per lifecycle attribute.
        """
        if not records:
            return cls.empty()
        return cls(
            event_type=jnp.asarray(
                [int(record["event_type"]) for record in records],
                dtype=jnp.int32,
            ),
            firm_id=jnp.asarray(
                [int(record.get("firm_id", -1)) for record in records],
                dtype=jnp.int32,
            ),
            cell_id=jnp.asarray(
                [int(record.get("cell_id", -1)) for record in records],
                dtype=jnp.int32,
            ),
            firm_type_id=jnp.asarray(
                [int(record.get("firm_type_id", -1)) for record in records],
                dtype=jnp.int32,
            ),
            sector_id=jnp.asarray(
                [int(record.get("sector_id", -1)) for record in records],
                dtype=jnp.int32,
            ),
            productivity=jnp.asarray(
                [float(record.get("productivity", np.nan)) for record in records],
                dtype=jnp.float32,
            ),
            capital=jnp.asarray(
                [float(record.get("capital", np.nan)) for record in records],
                dtype=jnp.float32,
            ),
            cash=jnp.asarray(
                [float(record.get("cash", np.nan)) for record in records],
                dtype=jnp.float32,
            ),
            inventory=jnp.asarray(
                [float(record.get("inventory", np.nan)) for record in records],
                dtype=jnp.float32,
            ),
            debt=jnp.asarray(
                [float(record.get("debt", np.nan)) for record in records],
                dtype=jnp.float32,
            ),
            wage_offer=jnp.asarray(
                [float(record.get("wage_offer", np.nan)) for record in records],
                dtype=jnp.float32,
            ),
            price=jnp.asarray(
                [float(record.get("price", np.nan)) for record in records],
                dtype=jnp.float32,
            ),
        )


@chex.dataclass(frozen=True)
class ProcurementShockBatch:
    """Carry supply-chain shock seeds for propagation over the procurement graph."""

    origin_firm_id: Int[Array, n_shocks]
    magnitude: Float[Array, n_shocks]
    decay: Float[Array, n_shocks]
    max_hops: Int[Array, n_shocks]

    @classmethod
    def empty(cls) -> ProcurementShockBatch:
        """Return an empty shock batch with executor-compatible dtypes."""
        empty_i = jnp.zeros((0,), dtype=jnp.int32)
        empty_f = jnp.zeros((0,), dtype=jnp.float32)
        return cls(
            origin_firm_id=empty_i,
            magnitude=empty_f,
            decay=empty_f,
            max_hops=empty_i,
        )

    @classmethod
    def from_records(
        cls,
        records: Sequence[Mapping[str, Any]],
    ) -> ProcurementShockBatch:
        """Build a procurement shock batch from dict-like shock records."""
        if not records:
            return cls.empty()
        return cls(
            origin_firm_id=jnp.asarray(
                [int(record.get("origin_firm_id", -1)) for record in records],
                dtype=jnp.int32,
            ),
            magnitude=jnp.asarray(
                [float(record.get("magnitude", 0.0)) for record in records],
                dtype=jnp.float32,
            ),
            decay=jnp.asarray(
                [float(record.get("decay", 0.5)) for record in records],
                dtype=jnp.float32,
            ),
            max_hops=jnp.asarray(
                [int(record.get("max_hops", 1)) for record in records],
                dtype=jnp.int32,
            ),
        )


def _coerce_numeric_tuple(values: Sequence[Any] | None) -> tuple[int, ...]:
    resolved: list[int] = []
    for value in values or ():
        if value is None:
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, np.integer)):
            resolved.append(int(value))
            continue
        text = str(value).strip()
        if not text:
            continue
        if text.lstrip("-").isdigit():
            resolved.append(int(text))
            continue
        if "-" in text and text.rsplit("-", 1)[-1].isdigit():
            resolved.append(int(text.rsplit("-", 1)[-1]))
    return tuple(dict.fromkeys(resolved))


def _resolve_float(
    params: Mapping[str, Any],
    *keys: str,
    default: float = 0.0,
) -> float:
    for key in keys:
        if key in params and params[key] is not None:
            return float(params[key])
    return float(default)


def _resolve_str(
    params: Mapping[str, Any],
    *keys: str,
    default: str,
) -> str:
    for key in keys:
        if key in params and params[key] is not None:
            return str(params[key])
    return default


@dataclass(frozen=True)
class InterventionMechanismConfig:
    """Normalize tax, transfer, and targeting parameters for distribution mechanisms.

    This object is the control side of agent simulation; synthetic state lives
    in `GlobalState`, while this config only declares which agents/firms/cells
    are eligible and how policy parameters should be interpreted.
    """

    base_tax_rate: float = 0.0
    tax_progressivity: float = 0.0
    total_transfer_budget: float = 0.0
    target_percentile: float = 0.3
    transfer_formula: str = "uniform"
    target_cell_ids: tuple[int, ...] = ()
    target_household_cell_ids: tuple[int, ...] = ()
    target_firm_ids: tuple[int, ...] = ()
    target_region_codes: tuple[int, ...] = ()
    target_sector_ids: tuple[int, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_params(
        cls,
        params: Mapping[str, Any] | None = None,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> InterventionMechanismConfig:
        """Normalize loose intervention params/metadata into a strict runtime config."""
        resolved = dict(params or {})
        extra = dict(metadata or {})
        return cls(
            base_tax_rate=_resolve_float(
                resolved,
                "base_tax_rate",
                "base_rate",
                "tax_rate",
                "rate",
                default=0.0,
            ),
            tax_progressivity=_resolve_float(
                resolved,
                "tax_progressivity",
                "progressivity",
                default=0.0,
            ),
            total_transfer_budget=_resolve_float(
                resolved,
                "total_transfer_budget",
                "total_budget",
                "budget",
                "amount",
                default=0.0,
            ),
            target_percentile=_resolve_float(
                resolved,
                "target_percentile",
                "percentile",
                default=0.3,
            ),
            transfer_formula=_resolve_str(
                resolved,
                "transfer_formula",
                "formula",
                default="uniform",
            ),
            target_cell_ids=_coerce_numeric_tuple(
                resolved.get("target_cell_ids", extra.get("target_cell_ids"))
            ),
            target_household_cell_ids=_coerce_numeric_tuple(
                resolved.get(
                    "target_household_cell_ids",
                    extra.get("target_household_cell_ids"),
                )
            ),
            target_firm_ids=_coerce_numeric_tuple(
                resolved.get("target_firm_ids", extra.get("target_firm_ids"))
            ),
            target_region_codes=_coerce_numeric_tuple(
                resolved.get("target_region_codes", extra.get("target_region_codes"))
            ),
            target_sector_ids=_coerce_numeric_tuple(
                resolved.get("target_sector_ids", extra.get("target_sector_ids"))
            ),
            metadata=extra,
        )

    @classmethod
    def from_compiled_intervention(
        cls,
        compiled: CompiledLexIntervention,
    ) -> InterventionMechanismConfig:
        """Create a runtime config from a compiled Lex intervention contract."""
        params = dict(compiled.intervention.params)
        metadata = dict(compiled.metadata)
        kind = compiled.intervention.kind
        metadata.setdefault("intervention_kind", kind)
        metadata.setdefault(
            "target_region_ids",
            list(compiled.intervention.target_region_ids),
        )
        metadata.setdefault(
            "target_sector_ids",
            list(compiled.intervention.target_sector_ids),
        )
        if kind in {"tax_rate_change", "distribution_aware_tax", "tax_rule_change"}:
            params.setdefault(
                "base_tax_rate", _resolve_float(params, "tax_rate", "rate", default=0.0)
            )
            params.setdefault(
                "tax_progressivity",
                _resolve_float(params, "progressivity", default=0.0),
            )
        if kind in {"targeted_subsidy_rule", "transfer_rule_change", "targeted_transfer"}:
            params.setdefault(
                "total_transfer_budget",
                _resolve_float(params, "budget", "total_budget", "amount", default=0.0),
            )
            params.setdefault(
                "target_percentile",
                _resolve_float(params, "target_percentile", "percentile", default=0.3),
            )
            params.setdefault(
                "transfer_formula",
                _resolve_str(params, "transfer_formula", "formula", default="uniform"),
            )
        return cls.from_params(
            params,
            metadata={
                **metadata,
                "target_region_codes": compiled.intervention.target_region_ids,
                "target_sector_ids": compiled.intervention.target_sector_ids,
            },
        )

    def has_tax(self) -> bool:
        """Return `True` when the config activates a tax mechanism."""
        return self.base_tax_rate > 0.0 or self.tax_progressivity > 0.0

    def has_transfer(self) -> bool:
        """Return `True` when the config activates a transfer mechanism."""
        return self.total_transfer_budget > 0.0


__all__ = [
    "FirmLifecycleEventBatch",
    "FirmLifecycleEventType",
    "InterventionMechanismConfig",
    "ProcurementShockBatch",
    "multiplex_layer_code",
]
