"""Data Forge entrypoint for the academic batch pipeline."""

from __future__ import annotations

from importlib import import_module


def main() -> None:
    """Run the academic batch CLI through the Data Forge-owned entrypoint."""
    legacy_cli = import_module("polisyos.data_forge.domains.academic.batch.cli")
    legacy_cli.main()


__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover
    main()
