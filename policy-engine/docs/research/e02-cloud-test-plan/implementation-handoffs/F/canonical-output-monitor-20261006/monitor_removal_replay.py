"""Remove measured monitor properties in memory, retaining method markers."""

from __future__ import annotations

import argparse
from typing import Any

import numpy as np
import pytest

import polisyos.foundry.methods.lifecycle.output_monitor as module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "control",
        choices=("raw_keys", "no_raw_numeric", "no_slot_keys", "no_array_types", "metadata_float", "no_flags"),
    )
    args = parser.parse_args()
    original = module.MethodOutputMonitor.check_output_contract

    def removed(self: Any, **kwargs: Any) -> Any:
        if args.control == "raw_keys":
            return self.check_basic(kwargs["raw_output"], expected_keys=kwargs["expected_keys"])
        if args.control == "no_raw_numeric":
            kwargs["raw_output"] = {}
        if args.control == "no_slot_keys":
            kwargs["expected_keys"] = None
        if args.control == "no_array_types":
            kwargs["array_keys"] = frozenset()
        if args.control == "no_flags":
            return []
        return original(self, **kwargs)

    if args.control == "metadata_float":
        original_coerce = module._try_as_array

        def empty_as_float(value: Any) -> Any:
            if isinstance(value, (list, tuple)) and not value:
                return np.asarray(value)
            return original_coerce(value)

        module._try_as_array = empty_as_float
    else:
        module.MethodOutputMonitor.check_output_contract = removed

    return int(
        pytest.main(
            [
                "tests/unit/foundry/methods/backends/test_dispatch_output_contract.py",
                "-o", "addopts=", "-q", "-ra",
                "--basetemp", f"/tmp/e02-F-continuation-20261006/foundry/removal-{args.control}-tmp",
            ]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
