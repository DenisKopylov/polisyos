# Extension Examples Contract

Source of truth: `architecture/extension_points.toml`.

Each extension point must grow an installable example package before the
extension is treated as public-stable. Example packages must be independent
`pyproject.toml` projects, installable with `python -m pip install -e`, and must
declare exactly one entry point in the group they demonstrate.

Every example must include:

- a minimal plugin implementation;
- a smoke test that runs without network access;
- the declared `contract_version`;
- the ABI target expected by the host;
- a release-fragment note when user-visible behavior changes.

Available examples:

- [fabric_connector](fabric_connector/) demonstrates the
  `polisyos.fabric_connectors` contract with an offline rows connector.
- [foundry_method](foundry_method/) demonstrates the canonical
  `polisyos.foundry_methods` contract through
  `polisyos.foundry.extensions.component_for_method()`.
- [scientist_node](scientist_node/) demonstrates the `polisyos.scientist_nodes`
  contract with a deterministic state-annotation node.
- [data_forge_domain](data_forge_domain/) demonstrates the
  `polisyos.data_forge_domains` contract with a tiny materialization domain.
- [lex_normpack](lex_normpack/) demonstrates the `polisyos.lex_normpacks`
  contract with a static NormPack provider.
- [runtime_middleware](runtime_middleware/) demonstrates the
  `polisyos.runtime_middlewares` contract with a plain ASGI middleware.

Repository gate:

```bash
uv run polisyos-tools validation check-extension-examples
```
