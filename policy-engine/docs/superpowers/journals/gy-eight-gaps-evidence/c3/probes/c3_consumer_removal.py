"""Remove a real C3 consumer check in memory while preserving stored markers."""

from __future__ import annotations

import argparse
import importlib

import pytest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("property", choices=("binding", "replay", "emission"))
    args = parser.parse_args()
    owner = importlib.import_module("polisyos.runtime.quality.workspace.foundry_consumption")
    tests = importlib.import_module(
        "tests.unit.runtime.quality.test_workspace_foundry_consumption"
    )
    if args.property == "binding":
        original_case = tests._method_owner_case

        def preserve_receipt_without_revalidation(fixture):
            case = original_case(fixture)
            owner.verify_recorded_panel_method_input = lambda **_kwargs: case[1]
            return case

        tests._method_owner_case = preserve_receipt_without_revalidation
        print("Removed recorded-source revalidation; original typed binding and CAS markers retained.")
    elif args.property == "replay":
        owner._verify_method_replay = lambda **_kwargs: None
        print("Removed actual MethodBackend replay; bytes, schemas, refs and lineage checks retained.")
    else:
        owner.FoundryMethodOutputConsumer._require_verified_consumption = (
            lambda *_args, **kwargs: owner._consumption_bytes(kwargs["consumption"])
        )
        print("Removed verified-emission capability check; intake verification and markers retained.")
    return int(pytest.main([
        "-q", "--tb=short", "--show-capture=no",
        "tests/unit/runtime/quality/test_workspace_foundry_consumption.py",
    ]))


if __name__ == "__main__":
    raise SystemExit(main())
