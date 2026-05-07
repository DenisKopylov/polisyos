# Runtime Middleware Example

Install this package in editable mode to exercise the public
`polisyos.runtime_middlewares` entry-point contract:

```bash
python -m pip install -e examples/extensions/runtime_middleware
polisyos components list --kind runtime_middleware --tag external-example
```

The middleware is a plain ASGI wrapper and does not require a live server.
