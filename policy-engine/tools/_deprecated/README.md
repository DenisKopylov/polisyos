# Deprecated And Quarantined Tools

This directory records legacy tools that remain in the repository only for
compatibility or historical reference.

Use `polisyos-tools list` to see the active lifecycle status for every command.
Deprecated tools are blocked by default in the unified CLI unless explicitly
run with `--allow-deprecated`. Quarantined tools are legacy surfaces with known
missing dependencies or broken compatibility contracts.

Current quarantine set:

| Tool                         | Replacement               | Reason                                                              |
| ---------------------------- | ------------------------- | ------------------------------------------------------------------- |
| `diagnostics.check-udf-perf` | `diagnostics check-setup` | Depends on removed `polisyos.fabric.udf.*` and graph-store modules. |
| `demos.run-udf-query-demo`   | `diagnostics check-setup` | Depends on removed `polisyos.fabric.udf.*`.                         |
| `demos.run-udf-hybrid-demo`  | `diagnostics check-setup` | Depends on removed UDF and graph-store APIs.                        |

Deprecated but not quarantined:

| Tool                         | Replacement                      | Reason                                                        |
| ---------------------------- | -------------------------------- | ------------------------------------------------------------- |
| `demos.run-export-demo`      | `runtime export-runtime-openapi` | Historical Foundry import paths.                              |
| `demos.run-mechanism-design` | `benchmarks bench-domain`        | Manual research script predating the current method registry. |
