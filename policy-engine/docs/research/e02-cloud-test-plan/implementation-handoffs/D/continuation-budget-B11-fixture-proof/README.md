# Canonical B1.1 fixture successor evidence

The executed runner and observer inputs are preserved byte for byte. The first runner used `-p capture`, which selected pytest's built-in capture plugin; its origin observer did not execute. Its complete 8 PASS / 1 fixture FAIL output is retained without an origin-observation claim. The successor selects the unique `e02_d_budget_capture` module and records all actual loaded product origins.

The associated lossless output payload contains original stdout, stderr, JUnit, source identities, runtime events, and fresh ledger bytes from both executions. Script members use pinned Git references instead of duplicating these tracked bodies. Resolve and verify each reference before reconstructing its original filename. All original `/tmp` files remain in place.

The seven migrated cases exercise canonical single-key receipt/retry/conflict/readback and aggregate reserve/release operations. They do not establish attempt-owned reservations or an atomic two-key settlement. The two unchanged native consumer selectors exercise actual full/split paid calls and capacity recheck. No product code changed, and optional numerical backend absence supplies no numerical verdict.
