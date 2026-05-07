# Search Strategies Compatibility Shim

`polisyos.scientist.search.strategies` redirects to the canonical
`polisyos.scientist.methods.search.strategies` implementation.

New first-party imports should use
`polisyos.scientist.methods.search.strategies`. This shim is registered in
`architecture/shims.toml` with sunset `2027-03-02`.
