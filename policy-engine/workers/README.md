# External worker profiles

This root contains separately packaged worker implementations selected through explicit
runtime configuration. A worker is an execution dependency, not an importable PolicyOS
product API; its own lock, protocol and source binding define its runtime boundary.

[`dowhy-014/README.md`](dowhy-014/README.md) documents the isolated DoWhy profile,
supported operations and limits. A worker response remains candidate computation until
the owning PolicyOS path validates and consumes it.
