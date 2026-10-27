# V6 — Persisted simulation after sibling failure

This packet proposes the bounded author task exit for V6. The native witness at `8a24cc8` runs a real SQLite-backed `run_simulation`, persists the typed SimulationResult/state/report, injects a later independent sibling failure, and reads the result through a fresh parsed debug API GET with wrong-reference and tamper controls.

The exact 2,055-path runtime readset has zero recorded mismatches, and product source/tests/configuration are unchanged through current HEAD `76691bd`; there was no runtime execution at that HEAD. The proof uses a custom DAG after control-job setup, not the default 23-node workflow or browser rendering.

The source implementation is preserved across mixed commits. G can review this candidate-only witness separately from formal B13 closure.
