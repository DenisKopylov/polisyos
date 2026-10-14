# English reader translation of ADR-0002: Make Scientist flow-nodes-only

Document type: English reader translation (informational derivative)  
Source pin: `af387828fbf27dce6dec8665286180df0dd10d1c`  
Source of truth: `docs/adr/0002-scientist-flow-nodes-only.md`

This page translates the decision text in the [source ADR](../../adr/0002-scientist-flow-nodes-only.md), whose SHA-256 is
`7e4dc78d96fdc9de7e89b24f8a676809d72cb18afa87798db22ed81f3c6561e4`.
The generated ADR index reports the source status as `unknown` at the source pin.
This derivative does not ratify or revise the decision and does not establish
that the decision was implemented.

- **Date:** 2026-01-12
- **Decision:** Make `build_workflow()` and `run_experiment()`, based on
  `flow_nodes.py`, the only public Scientist entry points. Move all legacy
  nodes (`orchestrator/nodes.py` and other auxiliary writes to `logs/`) to
  `_legacy/`, emit `DeprecationWarning`, and exclude them through the linter.
- **Context:** The orchestrator contains two coexisting execution paths: the new
  LangGraph workflow and the older set of nodes that call Foundry directly and
  write to `logs/`. This creates parallel worlds and inconsistent artifacts.
- **Consequences:**
  - Limit the public Scientist API to its official functions.
  - Legacy imports emit `DeprecationWarning` and are prohibited in production
    code.
  - Unify artifact writes through the runtime API
    (`runs/<run_id>/...`); workflow execution does not create the `logs/`
    directory.
- **Removal point:** 60 days or two minor releases after deployment of the ADR,
  whichever comes first. After date T, remove Scientist `_legacy` modules and
  remove `DeprecationWarning`.
