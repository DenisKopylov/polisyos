# Ops Deploy Tools

`tools/ops/deploy/` is the reserved canonical home for cross-environment
deployment orchestration that is not tied to one cloud provider.

Cloud-specific deployment helpers remain under `tools/ops/cloud/` and are
exposed through:

```bash
uv run polisyos-tools cloud deploy-to-server --help
uv run polisyos-tools cloud setup-server --help
```

New deployment commands should be added here only when they are provider-neutral
or coordinate multiple provider-specific commands. Add them to `tools.registry`
before wiring CI or docs.
