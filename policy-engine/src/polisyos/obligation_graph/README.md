# Obligation Graph

- Last updated: 2026-05-28

`polisyos.obligation_graph` is the W6.C owner for C38 obligation explosion
control. It compiles W6.A facet snapshots, W6.B governed rule snapshots, and
raw producer/critic/reviewer/LLM candidates into a typed `ObligationGraph`.

The module is internal by default. Its public contract inside the repository is
the three-tier ledger:

- candidate ledger: append-only, unbounded, raw `source_class`, never a closeout
  blocker;
- bundle ledger: canonicalized and deduplicated by
  `(family, scope, authority_profile, temporal_window, remedy_path)`;
- blocking frontier: complexity-budgeted and source-ceiling-gated.

Authority boundary: the graph is authoritative for obligation visibility,
bundle deduplication, and frontier selection. It is not domain evidence, legal
authority, claim support, method validity, participation legitimacy, or
projection authority.
