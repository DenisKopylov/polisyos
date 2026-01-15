from __future__ import annotations

import json
import os
import platform
import warnings
from datetime import datetime, timezone
from enum import Enum
from importlib import metadata
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReproMode(str, Enum):
    STRICT = "strict"
    FAST = "fast"


class GeneratorInfo(BaseModel):
    name: str = Field(..., max_length=100)
    version: str = Field(..., max_length=50)

    model_config = ConfigDict(extra="forbid")


class RunRecord(BaseModel):
    """
    Корневой артефакт воспроизводимости для каждого прогона.
    """

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    run_id: str = Field(..., max_length=64)
    parent_run_id: Optional[str] = Field(None, max_length=64)

    seed: int
    repro_mode: ReproMode = ReproMode.FAST
    backend: str

    python_version: str
    platform: str

    generator: GeneratorInfo
    library_versions: Dict[str, Optional[str]]
    flags: Dict[str, Optional[str]]

    model_config = ConfigDict(extra="forbid")


def _safe_version(pkg: str) -> Optional[str]:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return None


def build_run_record(
    run_id: str,
    seed: int,
    *,
    parent_run_id: Optional[str] = None,
    repro_mode: ReproMode = ReproMode.FAST,
    generator: Optional[Dict[str, str]] = None,
    extra_flags: Optional[Dict[str, Optional[str]]] = None,
) -> RunRecord:
    # Lazy import to keep module lightweight in non-JAX contexts.
    import jax

    generator_info = generator or {"name": "policy-engine", "version": "0.1.0"}
    library_versions = {
        "jax": _safe_version("jax"),
        "jaxlib": _safe_version("jaxlib"),
        "equinox": _safe_version("equinox"),
        "diffrax": _safe_version("diffrax"),
        "optax": _safe_version("optax"),
        "duckdb": _safe_version("duckdb"),
        "kuzu": _safe_version("kuzu"),
    }

    flags = {
        "JAX_PLATFORM_NAME": os.getenv("JAX_PLATFORM_NAME"),
        "JAX_PLATFORMS": os.getenv("JAX_PLATFORMS"),
        "XLA_FLAGS": os.getenv("XLA_FLAGS"),
        "POLICY_ENGINE_ALLOW_JAX_METAL": os.getenv("POLICY_ENGINE_ALLOW_JAX_METAL"),
        "CUDA_VISIBLE_DEVICES": os.getenv("CUDA_VISIBLE_DEVICES"),
    }
    if extra_flags:
        flags.update(extra_flags)

    return RunRecord(
        run_id=run_id,
        parent_run_id=parent_run_id,
        seed=seed,
        repro_mode=repro_mode,
        backend=jax.default_backend(),
        python_version=platform.python_version(),
        platform=platform.platform(),
        generator=GeneratorInfo(**generator_info),
        library_versions=library_versions,
        flags=flags,
    )


def save_run_record_json(record: RunRecord, base_dir: Path = Path("runs")) -> Path:
    warnings.warn(
        "save_run_record_json is deprecated; use polisyos.runtime.log_artifact instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    output_dir = Path(base_dir or "runs") / "run_records"
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = record.model_dump()
    path = output_dir / f"{record.run_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return path
