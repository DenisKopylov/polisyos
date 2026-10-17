# Mechanism Runtime Registry

runtime_registry.py derives runtime descriptors from the canonical polisyos.foundry.methods.selection.registry.MethodRegistry. It first registers the existing mechanism-method family through ensure_mechanism_methods_registered, then projects each registered method's runtime type, class path, supported fidelities, and hybrid default.

This module owns no second mechanism table. The runtime.py method consumer loads its factory lazily so method-family initialization does not introduce a registry import cycle. The stable Foundry compile/execute facade and method FQNs remain unchanged.

Runtime class loading remains on the declared method metadata path; this descriptor projection does not grant evidence or policy authority.
