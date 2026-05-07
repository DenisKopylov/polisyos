# Data Forge Domain Example

Install this package in editable mode to exercise the public
`polisyos.data_forge_domains` entry-point contract:

```bash
python -m pip install -e examples/extensions/data_forge_domain
polisyos components list --kind data_forge_domain --tag external-example
```

The domain materializes a tiny offline fixture and returns deterministic records.
