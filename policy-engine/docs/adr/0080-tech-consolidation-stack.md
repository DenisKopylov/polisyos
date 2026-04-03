# ADR-0080: Tech consolidation stack for causal inference, discovery, and graphs

## Status
Proposed

## Date
2026-02-28

## Context
The causal-methods landscape in PolicyOS has grown organically, accumulating overlapping
dependencies: DoWhy and EconML for inference, tigramite and causal-learn for discovery,
DAGMA and NOTEARS for continuous optimisation-based discovery, y0 for symbolic
identification, NumPyro and PyMC for Bayesian modelling, and NetworkX, rustworkx, and
KuzuDB for graph operations. Without a clear tiering, every new contributor adds
another library, inflating the dependency tree, CI time, and cognitive load. A formal
consolidation policy is needed.

## Decision
1. **Tier 1 (Core, always installed):** DoWhy + EconML (identification & estimation),
   tigramite + causal-learn (discovery), rustworkx (in-memory graphs), KuzuDB (graph
   queries).
2. **Tier 2 (Optional extras):** NumPyro (`[bayesian]` extra), y0
   (`[causal-symbolic]` extra).
3. **Tier 3 (Backlog, not installed):** DAGMA, NOTEARS (excluded per ADR-0026), PyMC,
   full `causaleffect` R bridge. These remain on the research backlog and may be
   promoted to Tier 2 if a Phase explicitly requires them.
4. NetworkX is retained as a transitive dependency (DoWhy requires it) but is not
   used directly in hot paths; all new graph code targets rustworkx.
5. The `import_policy.toml` linter enforces tier boundaries: Tier 3 imports are
   compile-time errors; Tier 2 imports must be lazy and guarded.

## Consequences
### Positive
- Clear dependency budget reduces install size and CI build time.
- Tier enforcement via `import_policy.toml` prevents accidental dependency creep.
- New contributors have a well-defined decision tree for library selection.
### Negative
- Some research-stage methods (DAGMA) become harder to prototype inside the main repo.
- Tier promotion requires an ADR, adding process overhead.
- Tier 2 lazy-import guards add boilerplate to every call site.
