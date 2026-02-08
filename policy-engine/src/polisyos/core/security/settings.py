from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SecuritySettings:
    """Runtime settings for tenant-isolation components."""

    POLISYOS_MULTI_TENANT_ENABLED: bool = False
    POLISYOS_CELL_REGISTRY_PATH: str = ""
    POLISYOS_DEFAULT_CELL_TIER: str = "shared"
    POLISYOS_ALLOWED_REGIONS: str = ""
    POLISYOS_MULTI_TENANT_FAIL_CLOSED: bool = True

    def allowed_regions(self) -> set[str]:
        return {
            region.strip()
            for region in self.POLISYOS_ALLOWED_REGIONS.split(",")
            if region.strip()
        }


@lru_cache(maxsize=1)
def get_security_settings() -> SecuritySettings:
    return SecuritySettings(
        POLISYOS_MULTI_TENANT_ENABLED=_parse_bool(
            os.getenv("POLISYOS_MULTI_TENANT_ENABLED"),
            False,
        ),
        POLISYOS_CELL_REGISTRY_PATH=os.getenv("POLISYOS_CELL_REGISTRY_PATH", ""),
        POLISYOS_DEFAULT_CELL_TIER=os.getenv("POLISYOS_DEFAULT_CELL_TIER", "shared"),
        POLISYOS_ALLOWED_REGIONS=os.getenv(
            "POLISYOS_ALLOWED_REGIONS",
            "",
        ),
        POLISYOS_MULTI_TENANT_FAIL_CLOSED=_parse_bool(
            os.getenv("POLISYOS_MULTI_TENANT_FAIL_CLOSED"),
            True,
        ),
    )


__all__ = ["SecuritySettings", "get_security_settings"]
