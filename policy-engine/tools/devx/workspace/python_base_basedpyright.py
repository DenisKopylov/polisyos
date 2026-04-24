#!/usr/bin/env python3
"""Run basedpyright across the Phase 3 Python base layers in serial order."""

from __future__ import annotations

import argparse

from ._common import run_command
from ._repo_hygiene import PYTHON_BASE_LAYERS, uv_run

_LAYER_NAMES = tuple(layer for layer, _, _ in PYTHON_BASE_LAYERS)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run `basedpyright` over the Python base layers in serial order: "
            "common, then ir, then core."
        )
    )
    parser.add_argument(
        "--layer",
        action="append",
        choices=_LAYER_NAMES,
        help=(
            "Restrict the run to one or more named layers. "
            "Defaults to the full common -> ir -> core chain."
        ),
    )
    return parser


def _selected_layers(selected: list[str] | None) -> list[tuple[str, str, str]]:
    requested = set(selected or _LAYER_NAMES)
    return [layer for layer in PYTHON_BASE_LAYERS if layer[0] in requested]


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    for layer_name, source_dir, _ in _selected_layers(args.layer):
        run_command(
            uv_run(
                f"basedpyright {layer_name}",
                "basedpyright",
                source_dir,
            )
        )

    print("[python-base-basedpyright] Phase 3 base-layer basedpyright checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
