# Discovery Compatibility Shim

`polisyos.scientist.discovery` is a compatibility package for the canonical
`polisyos.scientist.methods.discovery` implementation.

New first-party imports should use `polisyos.scientist.methods.discovery`. This
shim is registered in `architecture/shims.toml` with sunset `2027-03-02`.
