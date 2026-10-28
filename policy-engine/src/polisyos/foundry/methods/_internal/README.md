# Foundry Methods Internals

`polisyos.foundry.methods._internal` contains private helpers shared by method
subpackages.

Do not import from this package outside `polisyos.foundry.methods` unless a
public facade explicitly exports the symbol.

`executable_identity.py` supplies the private process-local identity used by
compiler and fused executable caches. It holds object references and binds the
selected callable and the signature ABI plus slot bounds used in composition; it
is not a persisted source fingerprint. The shared signature predicate compares
those fields for the actual selected class with the signature expected at the
execution boundary. Numeric bounds use Python numeric equality without coercing
large integers to float; slot descriptions are not treated as execution identity.
