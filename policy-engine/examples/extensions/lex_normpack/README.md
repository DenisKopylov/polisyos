# Lex NormPack Example

Install this package in editable mode to exercise the public
`polisyos.lex_normpacks` entry-point contract:

```bash
python -m pip install -e examples/extensions/lex_normpack
polisyos components list --kind norm_pack_provider --tag external-example
```

The provider returns a static NormPack from a tiny in-package fixture.
