"""Record actual portable dependencies and loopback availability in a fresh PID."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import platform
import socket
import sqlite3
import sys

packages = {
    "pytest": "pytest",
    "pytest_benchmark": "pytest-benchmark",
    "hypothesis": "hypothesis",
    "numpy": "numpy",
    "scipy": "scipy",
    "pandas": "pandas",
    "duckdb": "duckdb",
    "pyarrow": "pyarrow",
    "pydantic": "pydantic",
    "fastapi": "fastapi",
    "httpx": "httpx",
    "jwt": "PyJWT",
    "cryptography": "cryptography",
    "yaml": "PyYAML",
    "jax": "jax",
    "jaxlib": "jaxlib",
    "structlog": "structlog",
}
result = {
    "python": sys.version,
    "executable": sys.executable,
    "platform": platform.platform(),
    "packages": {},
}
for module_name, distribution in packages.items():
    try:
        module = importlib.import_module(module_name)
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            version = None
        result["packages"][module_name] = {
            "status": "available",
            "version": version,
            "file": getattr(module, "__file__", None),
        }
    except Exception as exc:
        result["packages"][module_name] = {
            "status": "unavailable",
            "exception": type(exc).__name__,
            "message": str(exc),
        }
try:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        result["loopback"] = {"status": "available", "address": "127.0.0.1:ephemeral"}
except OSError as exc:
    result["loopback"] = {
        "status": "unavailable",
        "exception": type(exc).__name__,
        "errno": exc.errno,
    }
try:
    with sqlite3.connect(":memory:") as conn:
        result["sqlite"] = conn.execute("select 1").fetchone()[0]
    import duckdb

    with duckdb.connect(":memory:") as conn:
        result["duckdb"] = conn.execute("select 1").fetchone()[0]
except Exception as exc:
    result["sql_probe"] = {
        "status": "unavailable",
        "exception": type(exc).__name__,
        "message": str(exc),
    }
try:
    import jax

    result["jax_runtime"] = {
        "backend": jax.default_backend(),
        "devices": [str(x) for x in jax.devices()],
        "x64": bool(jax.config.jax_enable_x64),
    }
except Exception as exc:
    result["jax_runtime"] = {
        "status": "unavailable",
        "exception": type(exc).__name__,
        "message": str(exc),
    }
print(json.dumps(result, sort_keys=True, indent=2))
