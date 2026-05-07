# Discovery Workers Compatibility Shim

`polisyos.scientist.discovery.workers` redirects to the canonical
`polisyos.scientist.methods.discovery.workers` implementation.

New first-party imports should use
`polisyos.scientist.methods.discovery.workers`. This shim inherits the
`polisyos.scientist.discovery` package shim sunset of `2027-03-02`.
