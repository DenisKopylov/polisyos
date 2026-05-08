"""Public fabric registry module API."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from polisyos.core.registry.generic import GenericRegistry
from polisyos.fabric.identity.manifest import DatasetManifest


class ManifestRegistry:
    """Manifest registry implementation."""

    def __init__(self, curated_dir: Path) -> None:
        self.curated_dir = curated_dir
        self._manifests = GenericRegistry[str, DatasetManifest](
            key_fn=lambda manifest: manifest.dataset_name,
        )
        self._load_manifests()

    def _load_manifests(self) -> None:
        if not self.curated_dir.exists():
            raise ValueError(f"Curated directory not found: {self.curated_dir}")
        for path in sorted(self.curated_dir.glob("*_manifest.json")):
            try:
                raw = path.read_text(encoding="utf-8")
                manifest = DatasetManifest.model_validate_json(raw)
            except ValidationError as exc:
                raise ValueError(f"Invalid manifest {path}: {exc}") from exc
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid manifest JSON {path}: {exc}") from exc
            self._manifests.register(manifest, override=True)

    def require(self, dataset_name: str) -> DatasetManifest:
        manifest = self._manifests.get(dataset_name)
        if manifest is None:
            raise ValueError(f"Missing DatasetManifest for '{dataset_name}' in {self.curated_dir}")
        if manifest.reconciliation and manifest.reconciliation.status != "pass":
            raise ValueError(
                f"Dataset '{dataset_name}' marked unusable: reconciliation {manifest.reconciliation.status}"
            )
        return manifest

    def require_entity_resolution(self) -> DatasetManifest:
        return self.require("entity_resolution")
