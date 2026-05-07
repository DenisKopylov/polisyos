# Foundry Method Extension Example

This package shows the supported external author interface for
`polisyos.foundry_methods`.

External packages expose exactly one entry point in `pyproject.toml`. The entry
point returns a `FoundryMethodPlugin`: an object with `metadata` and `create()`.
The helper `component_for_method()` builds that object from a normal
`FoundryMethod` class.

```toml
[project.entry-points."polisyos.foundry_methods"]
"example.weighted_average" = "polisyos_foundry_method_example:weighted_average_plugin"
```

Smoke test:

```bash
python -m pip install -e examples/extensions/foundry_method
polisyos components list --kind foundry_method --tag external-example
python -m pytest examples/extensions/foundry_method/tests -q
```
