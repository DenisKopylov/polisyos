# Causal Method Facade

`polisyos.foundry.methods.causal` is the flat public facade for causal catalog
methods.

The export-name tuple lives in the lightweight `_exports.py` module. Importing
the facade root reads this metadata without loading catalog implementations;
first attribute access resolves the canonical owner from `_facade.py`.

The implementation remains under `catalog/causal/`; this package exists so
callers have a documented family home while removed deep legacy paths such as
`polisyos.foundry.methods.causal.synthetic_control` stay unavailable.


The flat facade also exposes selected runtime contracts and helpers for causal
capability construction, transport limitations, distributional effects and
bounds, and identification results. Each name resolves to its existing
`catalog/causal/` owner object. `BootstrapExecutionWork` remains on the stable
`polisyos.foundry.methods` API. These routes add no authority or evidence
semantics.
