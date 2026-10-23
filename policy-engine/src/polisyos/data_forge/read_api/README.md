# Data Forge read API facade

polisyos.data_forge.read_api declares a finite module facade in __all__ and
its TYPE_CHECKING imports. surface_routes.py owns the lazy module routes and
the summaries consumed by surfaces.py; requesting an advertised module loads
only that selected route, while unknown names continue to raise AttributeError.

The route table covers the six modules declared by the facade: academic,
catalog, compliance, legal, provenance, and ukraine. The surfaces helper
module is imported eagerly and exposes metadata and explicit load helpers.
Symbol exports continue to use the existing _EXPORTS mapping in __init__.py.

The facade previously advertised compliance and provenance through __all__ and
TYPE_CHECKING while omitting those module attributes from the runtime route map.
The route map now matches the complete declared module set. This restores the
declared import behavior; it does not add a supported public-surface contract
entry. architecture/public_surface/contract.toml remains the authority for
supported-surface guarantees and does not list compliance or provenance, so
their supported status remains not_established.

The repository guardrail uses bounded static source analysis to inventory
curated entrypoints and declared export routes. Dynamic reflection and
profile-dependent exports remain outside that proof. Source analysis alone does
not establish installed-wheel behavior, runtime origin, or a public API claim.
