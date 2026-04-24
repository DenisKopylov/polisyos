"""Entity resolution with alias seeds and multilingual normalization."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.common.logger import get_logger
from polisyos.lex.batch.quality_filters import (
    compact_text,
    is_low_quality_entity_text,
    is_synthetic_subject,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = get_logger(__name__)

_DEFAULT_SEED_ENTITIES = (
    {
        "entity_id": "inst_minfin_ua",
        "name_en": "Ministry of Finance of Ukraine",
        "name_uk": "Міністерство фінансів України",
        "entity_type": "institution",
        "entity_subtype": "government_body",
        "aliases_en": ["MinFin", "Ministry of Finance"],
        "aliases_uk": ["Мінфін", "Міністерство фінансів"],
        "wikidata_id": "",
    },
)


def normalize_entity_name(name: str) -> str:
    """Normalize entity name helper."""
    lowered = str(name or "").strip().lower()
    collapsed = "".join(char if char.isalnum() else "_" for char in lowered)
    while "__" in collapsed:
        collapsed = collapsed.replace("__", "_")
    return collapsed.strip("_")


def _entity_id(*parts: str) -> str:
    canon = "|".join(parts)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


@dataclass
class EntityRecord:
    """Entity record data model."""

    entity_id: str
    name_en: str
    name_uk: str
    entity_type: str
    entity_subtype: str = ""
    mention_count: int = 1
    aliases_en: set[str] = field(default_factory=set)
    aliases_uk: set[str] = field(default_factory=set)
    wikidata_id: str = ""


class EntityResolver:
    """In-memory entity resolver with alias seeds and fuzzy fallback."""

    _FUZZY_MIN_NAME_LENGTH = 8
    _FUZZY_MAX_BUCKET_CANDIDATES = 64
    _FUZZY_DISABLE_AFTER_RECORDS = 5000
    _FUZZY_LENGTH_SLACK = 3

    def __init__(self, *, seeds_path: Path | None = None) -> None:
        self._records: dict[str, EntityRecord] = {}
        self._name_index: dict[str, str] = {}
        self._alias_index: dict[str, str] = {}
        self._fuzzy_bucket_index: dict[tuple[str, int], set[str]] = {}
        self._load_seed_entities(seeds_path)

    def resolve(
        self,
        *,
        name_en: str,
        name_uk: str,
        entity_type: str = "concept",
        entity_subtype: str = "",
    ) -> str:
        if is_synthetic_subject(name_uk) or is_synthetic_subject(name_en):
            label = compact_text(name_uk) or compact_text(name_en) or "synthetic_subject"
            return self._special_entity(
                kind="synthetic_subject",
                name_en=label if re.search(r"[a-z]", label, re.IGNORECASE) else "synthetic_subject",
                name_uk=label,
            )

        filtered_name_en = "" if is_low_quality_entity_text(name_en) else name_en
        filtered_name_uk = "" if is_low_quality_entity_text(name_uk) else name_uk
        if not filtered_name_en and not filtered_name_uk:
            return self._special_entity(
                kind="low_quality_fragment",
                name_en="low_quality_fragment",
                name_uk="низькоякісний фрагмент",
            )

        candidates = [
            normalize_entity_name(filtered_name_en),
            normalize_entity_name(filtered_name_uk),
        ]
        for candidate in candidates:
            if candidate and candidate in self._name_index:
                entity_id = self._name_index[candidate]
                self._merge_aliases(entity_id, name_en=filtered_name_en, name_uk=filtered_name_uk)
                return entity_id
            if candidate and candidate in self._alias_index:
                entity_id = self._alias_index[candidate]
                self._merge_aliases(entity_id, name_en=filtered_name_en, name_uk=filtered_name_uk)
                return entity_id

        entity_id = self._fuzzy_match(name_en=filtered_name_en, name_uk=filtered_name_uk)
        if entity_id:
            self._merge_aliases(entity_id, name_en=filtered_name_en, name_uk=filtered_name_uk)
            return entity_id

        norm = (
            normalize_entity_name(filtered_name_en)
            or normalize_entity_name(filtered_name_uk)
            or "unknown"
        )
        entity_id = _entity_id(norm, entity_type, entity_subtype)
        record = EntityRecord(
            entity_id=entity_id,
            name_en=filtered_name_en,
            name_uk=filtered_name_uk,
            entity_type=entity_type,
            entity_subtype=entity_subtype,
        )
        self._records[entity_id] = record
        self._register_name(entity_id, filtered_name_en)
        self._register_name(entity_id, filtered_name_uk)
        return entity_id

    def all_records(self) -> Iterator[EntityRecord]:
        yield from self._records.values()

    @property
    def count(self) -> int:
        return len(self._records)

    def _load_seed_entities(self, seeds_path: Path | None) -> None:
        candidate_paths = []
        if seeds_path is not None:
            candidate_paths.append(seeds_path)
        base_dir = Path(__file__).resolve().parents[4] / "data" / "lex_knowledge"
        candidate_paths.extend(
            [
                base_dir / "entity_seeds.yaml",
                base_dir / "entity_seeds.json",
            ]
        )
        loaded_seed_payload = False
        for path in candidate_paths:
            if not path.exists():
                continue
            try:
                payload = self._load_seed_payload(path)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to load entity seeds from %s: %s", path, exc)
                continue
            loaded_seed_payload = self._register_seed_payload(payload)
            if loaded_seed_payload:
                break
        if not loaded_seed_payload:
            self._register_seed_payload({"entities": list(_DEFAULT_SEED_ENTITIES)})

    def _register_seed_payload(self, payload: dict) -> bool:
        entities = payload.get("entities") if isinstance(payload, dict) else None
        if not isinstance(entities, list):
            return False
        registered_any = False
        for item in entities:
            if not isinstance(item, dict):
                continue
            entity_id = str(item.get("entity_id") or "").strip()
            name_en = str(item.get("name_en") or "")
            name_uk = str(item.get("name_uk") or "")
            if not entity_id or not (name_en or name_uk):
                continue
            record = EntityRecord(
                entity_id=entity_id,
                name_en=name_en,
                name_uk=name_uk,
                entity_type=str(item.get("entity_type") or "concept"),
                entity_subtype=str(item.get("entity_subtype") or ""),
                mention_count=0,
                wikidata_id=str(item.get("wikidata_id") or ""),
            )
            record.aliases_en.update(
                str(alias) for alias in item.get("aliases_en") or [] if str(alias).strip()
            )
            record.aliases_uk.update(
                str(alias) for alias in item.get("aliases_uk") or [] if str(alias).strip()
            )
            self._records[entity_id] = record
            self._register_name(entity_id, name_en)
            self._register_name(entity_id, name_uk)
            for alias in [*record.aliases_en, *record.aliases_uk]:
                self._register_alias(entity_id, alias)
            registered_any = True
        return registered_any

    def _load_seed_payload(self, path: Path) -> dict:
        if path.suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        try:
            import yaml  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("PyYAML is required to load entity seed YAML") from exc
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}

    def _register_name(self, entity_id: str, name: str) -> None:
        normalized = normalize_entity_name(name)
        if normalized:
            self._name_index[normalized] = entity_id
            bucket = self._fuzzy_bucket(normalized)
            self._fuzzy_bucket_index.setdefault(bucket, set()).add(normalized)

    def _register_alias(self, entity_id: str, alias: str) -> None:
        normalized = normalize_entity_name(alias)
        if normalized:
            self._alias_index[normalized] = entity_id

    def _merge_aliases(self, entity_id: str, *, name_en: str, name_uk: str) -> None:
        record = self._records[entity_id]
        record.mention_count += 1
        if name_en and name_en != record.name_en:
            record.aliases_en.add(name_en)
            self._register_alias(entity_id, name_en)
        if name_uk and name_uk != record.name_uk:
            record.aliases_uk.add(name_uk)
            self._register_alias(entity_id, name_uk)

    def _fuzzy_match(self, *, name_en: str, name_uk: str) -> str | None:
        candidates = [normalize_entity_name(name_en), normalize_entity_name(name_uk)]
        searchable = [candidate for candidate in candidates if candidate]
        if not searchable:
            return None
        if len(self._records) >= self._FUZZY_DISABLE_AFTER_RECORDS:
            return None
        best_id = ""
        best_score = 0.0
        for candidate in searchable:
            if len(candidate) < self._FUZZY_MIN_NAME_LENGTH:
                continue
            for known_name in self._fuzzy_candidates(candidate):
                entity_id = self._name_index.get(known_name, "")
                if not entity_id:
                    continue
                score = difflib.SequenceMatcher(None, candidate, known_name).ratio()
                if score > best_score:
                    best_score = score
                    best_id = entity_id
        if best_score >= 0.9:
            return best_id
        return None

    def _fuzzy_bucket(self, normalized: str) -> tuple[str, int]:
        prefix = normalized[:2]
        length_band = len(normalized) // 4
        return prefix, length_band

    def _fuzzy_candidates(self, candidate: str) -> list[str]:
        prefix = candidate[:2]
        length_band = len(candidate) // 4
        names: list[str] = []
        seen: set[str] = set()
        for delta in (-1, 0, 1):
            bucket = self._fuzzy_bucket_index.get((prefix, length_band + delta), set())
            for known_name in bucket:
                if known_name in seen:
                    continue
                if abs(len(known_name) - len(candidate)) > self._FUZZY_LENGTH_SLACK:
                    continue
                seen.add(known_name)
                names.append(known_name)
                if len(names) >= self._FUZZY_MAX_BUCKET_CANDIDATES:
                    return names
        return names

    def _special_entity(self, *, kind: str, name_en: str, name_uk: str) -> str:
        entity_id = _entity_id(kind)
        record = self._records.get(entity_id)
        if record is None:
            record = EntityRecord(
                entity_id=entity_id,
                name_en=name_en,
                name_uk=name_uk,
                entity_type="concept",
                entity_subtype=kind,
                mention_count=0,
            )
            self._records[entity_id] = record
            self._register_name(entity_id, name_en)
            self._register_name(entity_id, name_uk)
        record.mention_count += 1
        return entity_id
