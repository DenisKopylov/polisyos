# Minimal supported runtime profile

Interpreter: `/tmp/e02-D-runtime-minimal-20261006/bin/python` (Python 3.14.7).

A standard venv with system/user site disabled exposes the 148 exact installed distributions from the frozen core/runtime/test plan. Individual selected RECORD-owned files and selected dist-info metadata are linked to their original installed locations. No whole-parent site-packages path or pth is added; outside-site console scripts are excluded.

Actual small pytest/NumPy/Pydantic/orjson/uvloop confirmation completed. Torch, BoTorch, GPyTorch, HNSW and SALib discovery returned absent. This supports the declared non-GP runtime profile only; numerical requirements remain UNRUN. No product/test suite was executed here.

The XZ JSON preserves seven complete original metadata/inventory/output captures with their raw hashes and paths. The original files, environment and linked dependency targets remain intact and excluded from cleanup. No dependency or tracked project/source body is copied. The one unique confirmation instrument occurs once as a file here.

Creation input commit c2e0d259 and root 613343c3 differ, while both profile-defining pyproject.toml and uv.lock blobs/hash/size are identical. Exact source comparison is retained in the transport. The separate handoff binds this proof commit; it makes no product or finding closure claim.
