# Fabric Connector Example

Install this package in editable mode to exercise the public
`polisyos.fabric_connectors` entry-point contract:

```bash
python -m pip install -e examples/extensions/fabric_connector
polisyos components list --kind fabric_connector --tag external-example
```

The component creates a deterministic in-memory connector and does not use the
network.
