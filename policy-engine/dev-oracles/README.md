# Development oracles

This root contains independently pinned development-only comparison tools. Each profile
owns its lockfile, setup and command; it does not add its dependencies to the PolicyOS
runtime or grant its numerical result production authority.

[`rdd-cct/README.md`](rdd-cct/README.md) documents the sharp-RD comparison profile and
its required independent reference run. Keep profile outputs in a separate scratch path,
and report the exact source, environment and inputs used.
