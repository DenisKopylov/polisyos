"""Lock backend configuration and factory."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from polisyos.scientist.engine.lock_protocol import RunLockBackend


class RunLockConfig(BaseModel):
    """Declarative run-lock backend configuration."""

    model_config = ConfigDict(extra="forbid")

    backend: Literal["fcntl", "redis", "dynamodb"] = "fcntl"
    redis_url: str | None = None
    ttl_seconds: int = 3600
    run_dir: Path | None = None
    heartbeat: bool = True

    # --- DynamoDB ---
    dynamodb_table_name: str | None = None
    dynamodb_region: str | None = None

    @classmethod
    def from_env(cls) -> RunLockConfig:
        return cls(
            backend=os.environ.get("POLISYOS_LOCK_BACKEND", "fcntl"),
            redis_url=os.environ.get("POLISYOS_LOCK_REDIS_URL"),
            ttl_seconds=int(os.environ.get("POLISYOS_LOCK_TTL_SECONDS", "3600")),
            run_dir=Path(d) if (d := os.environ.get("POLISYOS_LOCK_RUN_DIR")) else None,
            dynamodb_table_name=os.environ.get("POLISYOS_LOCK_DYNAMODB_TABLE"),
            dynamodb_region=os.environ.get("POLISYOS_LOCK_DYNAMODB_REGION"),
        )


def build_run_lock(config: RunLockConfig, *, run_dir: Path | None = None) -> RunLockBackend:
    """Construct a ``RunLockBackend`` from declarative config."""
    if config.backend == "fcntl":
        from .fcntl_lock import FcntlRunLock

        effective_dir = run_dir or config.run_dir
        if effective_dir is None:
            raise ValueError("run_dir is required for fcntl lock backend")
        return FcntlRunLock(effective_dir)

    if config.backend == "redis":
        from .redis_lock import RedisRunLock

        if not config.redis_url:
            raise ValueError("RunLockConfig.redis_url is required for redis backend")
        return RedisRunLock(
            redis_url=config.redis_url,
            ttl_seconds=config.ttl_seconds,
            heartbeat=config.heartbeat,
        )

    if config.backend == "dynamodb":
        from .dynamodb_lock import DynamoDBRunLock

        if not config.dynamodb_table_name:
            raise ValueError("RunLockConfig.dynamodb_table_name is required for dynamodb backend")
        return DynamoDBRunLock(
            table_name=config.dynamodb_table_name,
            region=config.dynamodb_region,
            ttl_seconds=config.ttl_seconds,
            heartbeat=config.heartbeat,
        )

    raise ValueError(f"Unknown lock backend: {config.backend!r}")
