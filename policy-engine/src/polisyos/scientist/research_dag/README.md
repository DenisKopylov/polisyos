# Research DAG Compatibility Shim

`polisyos.scientist.research_dag` is a compatibility package for the canonical
`polisyos.scientist.methods.research_dag` implementation.

New first-party imports should use `polisyos.scientist.methods.research_dag`.
This shim is registered in `architecture/shims.toml` with sunset `2027-03-02`.
