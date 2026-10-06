"""Observe installed pytest option registration; never parse, collect or execute tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pytest
from _pytest.config import get_config


def main() -> None:
    """Write one exclusive runtime observation of actual option registration objects."""
    destination = Path(sys.argv[1])
    config = get_config()
    config.pluginmanager.load_setuptools_entrypoints("pytest11")
    actions = [
        {"options": a.option_strings, "nargs": a.nargs, "action": type(a).__name__}
        for a in config._parser.optparser._actions
        if a.option_strings
    ]
    sources = []
    for impl in config.pluginmanager.hook.pytest_addoption.get_hookimpls():
        function = impl.function
        path = Path(function.__code__.co_filename)
        content = path.read_bytes()
        sources.append(
            {
                "module": function.__module__,
                "function": function.__qualname__,
                "path": str(path),
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
        )
    import _pytest.config.argparsing as pytest_argparsing

    for module in (pytest_argparsing, argparse):
        path = Path(module.__file__)
        content = path.read_bytes()
        sources.append(
            {
                "module": module.__name__,
                "path": str(path),
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
        )
    result = {
        "schema": "policyos.e02.pytest_cli_option_profile.v1",
        "pytest_version": pytest.__version__,
        "python": sys.version,
        "measurement": (
            "Actual get_config builtin plugin registry plus installed pytest11 option "
            "registration; parser action inspection only, no config.parse, pytest.main, "
            "collection or test execution"
        ),
        "actions": actions,
        "option_registration_sources": sources,
        "distribution_versions": {
            distribution.project_name: distribution.version
            for _plugin, distribution in config.pluginmanager.list_plugin_distinfo()
        },
        "limits": [
            "Only named installed pytest9 contributor profile; custom repository pytest_addoption "
            "not loaded. Unknown option arity must remain unresolved, not a guessed selector.",
            "Source options observed from actual runtime objects; does not attest product tests or "
            "case counts.",
        ],
    }
    with destination.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    sys.stdout.write(
        json.dumps({"actions": len(actions), "sources": len(sources), "path": str(destination)}) + "\n"
    )


if __name__ == "__main__":
    main()
