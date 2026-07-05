"""Validation-only shared CGF world cache for closeout sweeps."""

from __future__ import annotations

import contextlib
import importlib
import json
import resource
import sys
import time
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polisyos.pdc import gy_content_hash


@dataclass(frozen=True)
class GroundingWorldCacheKey:
    """Content key for one owner-derived grounding world."""

    reference_hash: str
    reference_epoch: str

    def to_payload(self) -> dict[str, str]:
        """Return a stable JSON payload."""

        return {
            "reference_epoch": self.reference_epoch,
            "reference_hash": self.reference_hash,
        }


@dataclass(frozen=True)
class GroundingWorldCacheEntry:
    """Cached owner-derived world reused by validation tooling."""

    key: GroundingWorldCacheKey
    reference: Any
    world_model_record: Any
    relation_engine: Any
    owner_fingerprint: str
    cold_build_wall_seconds: float
    fts_prewarm_wall_seconds: float
    indexed_edge_count: int

    def to_receipt(self) -> dict[str, Any]:
        """Return an audit-safe cache receipt."""

        return {
            "cold_build_wall_seconds": self.cold_build_wall_seconds,
            "fts_prewarm_wall_seconds": self.fts_prewarm_wall_seconds,
            "indexed_edge_count": self.indexed_edge_count,
            "key": self.key.to_payload(),
            "owner_fingerprint": self.owner_fingerprint,
            "world_model_record_id": getattr(
                self.world_model_record,
                "world_model_record_id",
                None,
            ),
            "world_model_record_hash": getattr(
                self.world_model_record,
                "content_hash",
                None,
            ),
        }


class StaleGroundingWorldCacheHitError(RuntimeError):
    """Raised when a cached world is requested under a different owner key."""


class GroundingWorldCache:
    """Build and patch a single owner-derived CGF world for validators."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.entries: dict[GroundingWorldCacheKey, GroundingWorldCacheEntry] = {}
        self.active_entry: GroundingWorldCacheEntry | None = None
        self.stats: Counter[str] = Counter()
        self._patches: list[tuple[Any, str, Any]] = []
        self._installed = False
        self._credal_reference_module = importlib.import_module(
            "polisyos.runtime.quality.credal_reference"
        )
        self._intervention_substrate_module = importlib.import_module(
            "polisyos.runtime.quality.intervention_substrate"
        )
        self._grounding_relation_module = importlib.import_module(
            "polisyos.runtime.quality.grounding_relation"
        )
        self._design_generation_module = importlib.import_module(
            "polisyos.runtime.quality.design_generation"
        )
        self._original_build_credal_reference = (
            self._credal_reference_module.build_credal_reference
        )
        self._original_relation_engine_init = (
            self._grounding_relation_module.GroundingRelationEngine.__init__
        )
        self._original_production_wmr = (
            self._intervention_substrate_module.production_composed_world_model_record
        )
        self._original_private_production_wmr = (
            self._intervention_substrate_module._production_composed_world_model_record
        )

    def get_entry(self, *, reason: str = "warm") -> GroundingWorldCacheEntry:
        """Return the active world entry, building it once on first use."""

        if self.active_entry is not None:
            self.stats["hits"] += 1
            return self.active_entry
        self.stats["misses"] += 1
        entry = self._build_entry(reason=reason)
        self.entries[entry.key] = entry
        self.active_entry = entry
        return entry

    def require_active_key(self, key: GroundingWorldCacheKey) -> GroundingWorldCacheEntry:
        """Return the active entry only when its owner key matches."""

        entry = self.get_entry(reason="require_active_key")
        if entry.key != key:
            self.stats["stale_rejections"] += 1
            raise StaleGroundingWorldCacheHitError(
                "grounding_world_cache_stale_hit:"
                f"{entry.key.to_payload()}!={key.to_payload()}"
            )
        return entry

    @contextlib.contextmanager
    def installed(self) -> Iterator[GroundingWorldCache]:
        """Patch runtime-quality imports for validation-only cache reuse."""

        if self._installed:
            yield self
            return
        self.get_entry(reason="install")
        self._installed = True
        self._install_patches()
        try:
            yield self
        finally:
            self._restore_patches()
            self._installed = False

    def owner_change_probe(self) -> dict[str, Any]:
        """Exercise cache miss and stale-hit semantics with a changed owner key."""

        from polisyos.runtime.quality.credal_reference import (
            AdmissibleCompletion,
            CredalReferenceEdge,
            replace_reference_edge,
        )

        entry = self.get_entry(reason="owner_change_probe")
        first_edge = next(iter(entry.reference.essential_edges.values()))
        changed_edge = CredalReferenceEdge(
            modality=first_edge.modality,
            edge_id=first_edge.edge_id,
            status=first_edge.status,
            admissible_completions=(
                AdmissibleCompletion(
                    "fixed",
                    {"owner_change_probe": first_edge.edge_id},
                    "compute_economics_owner_change_probe",
                ),
            ),
            provenance={
                **dict(first_edge.provenance),
                "compute_economics_probe": "owner_data_changed",
            },
            unit=first_edge.unit,
            scale=first_edge.scale,
        )
        changed_reference = replace_reference_edge(entry.reference, changed_edge)
        changed_key = key_for_reference(changed_reference)
        miss_for_changed_key = changed_key not in self.entries
        try:
            self.require_active_key(changed_key)
            stale_hit_rejected = False
        except StaleGroundingWorldCacheHitError:
            stale_hit_rejected = True
        return {
            "changed_key": changed_key.to_payload(),
            "miss_for_changed_owner_key": miss_for_changed_key,
            "original_key": entry.key.to_payload(),
            "status": (
                "pass"
                if miss_for_changed_key and stale_hit_rejected
                else "fail"
            ),
            "stale_hit_rejected": stale_hit_rejected,
        }

    def _build_entry(self, *, reason: str) -> GroundingWorldCacheEntry:
        started = time.monotonic()
        world_model_record = self._original_production_wmr(self.repo_root)
        reference = self._original_build_credal_reference(
            self.repo_root,
            world_model_record=world_model_record,
        )
        relation_engine = self._grounding_relation_module.GroundingRelationEngine(
            reference
        )
        prewarm_wall = self._prewarm_relation_engine(relation_engine)
        wall_seconds = max(0.0, time.monotonic() - started)
        key = key_for_reference(reference)
        owner_fingerprint = gy_content_hash(
            {
                "component_versions": dict(sorted(reference.component_versions.items())),
                "reference_epoch": reference.reference_epoch,
                "reference_hash": reference.reference_hash,
                "world_model_record_hash": getattr(
                    world_model_record,
                    "content_hash",
                    None,
                ),
            }
        )
        self.stats["builds"] += 1
        self.stats[f"build_reason:{reason}"] += 1
        return GroundingWorldCacheEntry(
            key=key,
            reference=reference,
            world_model_record=world_model_record,
            relation_engine=relation_engine,
            owner_fingerprint=owner_fingerprint,
            cold_build_wall_seconds=wall_seconds,
            fts_prewarm_wall_seconds=prewarm_wall,
            indexed_edge_count=(
                relation_engine._fts_index.indexed_edge_count
                if relation_engine._fts_index is not None
                else 0
            ),
        )

    def _prewarm_relation_engine(self, relation_engine: Any) -> float:
        n4_contract = importlib.import_module(
            "tools.quality.validation.check_layer3_gy_design_generation_contract"
        )
        recordings = n4_contract._load_recordings(self.repo_root)
        if not recordings:
            return 0.0
        design_problem = n4_contract._design_problem(recordings[0])
        return float(
            self._design_generation_module._prewarm_grounding_relation_index(
                relation_engine,
                design_problem=design_problem,
            )
        )

    def _install_patches(self) -> None:
        self._patch(
            self._credal_reference_module,
            "build_credal_reference",
            self._cached_build_credal_reference,
        )
        self._patch(
            self._credal_reference_module,
            "_production_world_model_record",
            self._cached_private_production_wmr,
        )
        self._patch(
            self._credal_reference_module,
            "_production_composed_world_model_record",
            self._cached_private_production_wmr,
        )
        self._patch(
            self._intervention_substrate_module,
            "production_composed_world_model_record",
            self._cached_production_wmr,
        )
        self._patch(
            self._intervention_substrate_module,
            "_production_composed_world_model_record",
            self._cached_private_production_wmr,
        )
        self._patch(
            self._design_generation_module,
            "build_credal_reference",
            self._cached_build_credal_reference,
        )
        self._patch(
            self._design_generation_module,
            "production_composed_world_model_record",
            self._cached_production_wmr,
        )

        def cached_relation_engine_init(
            instance: Any,
            reference: Any,
            *,
            axis_witness_provider: Any | None = None,
            policy: Any | None = None,
        ) -> None:
            self._cached_relation_engine_init(
                instance,
                reference,
                axis_witness_provider=axis_witness_provider,
                policy=policy,
            )

        self._patch(
            self._grounding_relation_module.GroundingRelationEngine,
            "__init__",
            cached_relation_engine_init,
        )

    def _restore_patches(self) -> None:
        while self._patches:
            target, name, original = self._patches.pop()
            setattr(target, name, original)

    def _patch(self, target: Any, name: str, replacement: Any) -> None:
        self._patches.append((target, name, getattr(target, name)))
        setattr(target, name, replacement)

    def _cached_build_credal_reference(
        self,
        repo_root: Path,
        *,
        as_of: str | None = None,
        world_model_record: Any | None = None,
    ) -> Any:
        root = Path(repo_root).resolve()
        if root != self.repo_root:
            return self._original_build_reference_with_optional_as_of(
                repo_root,
                as_of=as_of,
                world_model_record=world_model_record,
            )
        entry = self.get_entry(reason="validator")
        if world_model_record is not None and (
            getattr(world_model_record, "content_hash", None)
            != getattr(entry.world_model_record, "content_hash", None)
        ):
            self.stats["bypass_foreign_world_model_record"] += 1
            return self._original_build_reference_with_optional_as_of(
                repo_root,
                as_of=as_of,
                world_model_record=world_model_record,
            )
        if as_of is not None and str(as_of) != str(entry.reference.as_of):
            self.stats["bypass_foreign_as_of"] += 1
            return self._original_build_reference_with_optional_as_of(
                repo_root,
                as_of=as_of,
                world_model_record=world_model_record,
            )
        self.stats["reference_reuses"] += 1
        return entry.reference

    def _original_build_reference_with_optional_as_of(
        self,
        repo_root: Path,
        *,
        as_of: str | None,
        world_model_record: Any | None,
    ) -> Any:
        kwargs: dict[str, Any] = {"world_model_record": world_model_record}
        if as_of is not None:
            kwargs["as_of"] = as_of
        return self._original_build_credal_reference(repo_root, **kwargs)

    def _cached_production_wmr(self, repo_root: Path | str) -> Any:
        if Path(repo_root).resolve() != self.repo_root:
            return self._original_production_wmr(repo_root)
        self.stats["world_model_record_reuses"] += 1
        return self.get_entry(reason="world_model_record").world_model_record

    def _cached_private_production_wmr(self, repo_root: str) -> Any:
        if Path(repo_root).resolve() != self.repo_root:
            return self._original_private_production_wmr(repo_root)
        self.stats["world_model_record_reuses"] += 1
        return self.get_entry(reason="private_world_model_record").world_model_record

    def _cached_relation_engine_init(
        self,
        instance: Any,
        reference: Any,
        *,
        axis_witness_provider: Any | None = None,
        policy: Any | None = None,
    ) -> None:
        self._original_relation_engine_init(
            instance,
            reference,
            axis_witness_provider=axis_witness_provider,
            policy=policy,
        )
        entry = self.get_entry(reason="relation_engine_init")
        if reference is entry.reference:
            instance._reference_atoms = entry.relation_engine.reference_atoms
            instance._fts_index = entry.relation_engine._fts_index
            self.stats["fts_index_reuses"] += 1


def key_for_reference(reference: Any) -> GroundingWorldCacheKey:
    """Return the content cache key for a CredalReference-like object."""

    return GroundingWorldCacheKey(
        reference_hash=str(reference.reference_hash),
        reference_epoch=str(reference.reference_epoch),
    )


def stable_json_bytes(payload: Any) -> bytes:
    """Return canonical JSON bytes for byte-identity checks."""

    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def rss_mb() -> float:
    """Return current process max RSS in MiB."""

    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return value / (1024.0 * 1024.0)
    return value / 1024.0
