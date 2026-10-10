# V6 C05 fresh lineage patch artifact

This is an unapplied test-only patch against the bytes identified as base `00954ff`. It targets only `tests/unit/runtime/http/test_control_service_di.py::test_fresh_run_details_get_keeps_n5_and_failed_sibling_checkpoint`. The source test file remains unchanged (SHA-256 `a350618bae4942c3e2184ad6b801b0180f7ac05a84495072649dbc2c3b90faed`).

The controlled fixture runs the actual N4/N5 producer and owner path, persists its N4 source, child context handoff, V5 N5 input, and N5 result, then reads the compiled artifact through a fresh runtime app. The route resolves V5 by selected CAS ref and checks the input’s run/job/tenant/cell, source/context refs, profile config/selection, child handoff/profile replay, and N4 source status before it emits `lineage_status=resolved`. The proposed equalities compare that fresh projection to the successful producer branch’s exact refs; they do not rely on fixture labels alone.

The patch keeps the typed boundary explicit: `currentness_status` remains `not_established`, and recursive checkpoint `publication_authority` must remain false. It leaves the existing later-N5-blob-corruption GET and exact failed-sibling checkpoint assertions untouched. This is a controlled CYC02 producer/readback witness only; it does not establish authentic RES-03/V1 inputs or global source currentness. The existing history-validator missing-context mutation remains as a structural falsifier; no attempt is made to promote that validator or create a synthetic owner-bound altered capsule.

P40: same producer → artifact/history → fresh-consumer class, one level deeper. The patch checks full lineage refs at the fresh consumer rather than only N5 status/result ref. If the assertions fail, the exact fresh route result identifies an unresolved producer-to-input/profile join; do not weaken the assertions or substitute a test-owned source and call it authentic RES-03.

No tests, lint, or runtime commands were run for this patch artifact, and the patch was not applied.
