"""Data Forge entrypoint for the catalog batch pipeline."""

from __future__ import annotations

from importlib import import_module


def main() -> None:
    """Run the catalog batch CLI through the Data Forge-owned entrypoint."""
    legacy_cli = import_module("polisyos.data_forge.domains.catalog.batch.cli")
    legacy_cli.main()


__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover
    main()
