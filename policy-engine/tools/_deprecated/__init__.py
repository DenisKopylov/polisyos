"""Legacy tooling inventory kept out of the active command surface."""

from __future__ import annotations

LEGACY_TOOL_REPLACEMENTS: dict[str, str] = {
    "demos.run-export-demo": "runtime export-runtime-openapi",
    "demos.run-mechanism-design": "benchmarks bench-domain",
    "demos.run-udf-query-demo": "diagnostics check-setup",
    "demos.run-udf-hybrid-demo": "diagnostics check-setup",
    "diagnostics.check-udf-perf": "diagnostics check-setup",
}
