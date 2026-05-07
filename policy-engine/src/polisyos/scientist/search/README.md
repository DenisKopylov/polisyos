# Search Compatibility Shim

`polisyos.scientist.search` is a compatibility package for the canonical
`polisyos.scientist.methods.search` implementation.

New first-party imports should use `polisyos.scientist.methods.search`. This
shim is registered in `architecture/shims.toml` with sunset `2027-03-02`.
