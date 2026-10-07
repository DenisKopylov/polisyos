# Independent review: 1830 B/D owner actions

Basis: clean `codex/e02-integration` at `127dc7ab`; read all five B and five D 1800 reports, both action drafts, and the bound original criteria/owner accounting. Read-only review; no tests or refs changed.

## Corrections required

1. `1830-D-actions.md:17` assigns the default hierarchical ParetoRegistry/provider gap to **B109**. The canonical B109 source (`bundles/OPT-01.md`, `B109@OPT-01`; D's `published-final-criterion-accounting.json`) is the `_find_non_dominated_2d` equality bug: direct-vs-fast Pareto agreement, including 1–4D and equal-coordinate controls. A-W04 input and D-W01 default-route wiring do not establish that criterion. Keep the default-route gap as a separate bounded consumer limitation or identify its actual criterion; do not route/close B109 through that provider chain. The 1800 D-consumer report repeats the mismatch, so its label does not supersede the canonical criterion.

2. `1830-D-actions.md:15` labels positive finite underflow as **B111**. Canonical `B111@OPT-01` is missing/non-finite metric admission and preservation of invalid status/reason, with reference/hypervolume finite or explicitly unavailable. A contributing finite box silently underflowing to available exact zero is a distinct representability counterexample. Keep the concrete 2D residual and derived-reference case, but explicitly classify it under P40 against the original criterion before assigning it to B111; retain the original B111 discriminator. The draft correctly limits the 3D/4D backend to its declared versions and says no independent general 4D oracle exists; preserve that limit.

3. `1830-D-actions.md:9` leaves global gate runs without their source pins. Preserve them as historical: the backend-25, frontend-8 and production invocation receipts are on `243ca4e`; the bounded current142/current127 passes are on `3f38e7c`; none is a current D-root `3c636ff` aggregate. Qualify the broad 80-file output by its own exact receipt/source as well, and state current-root global gate status as unrun/not established where no `3c` receipt exists. The 1800 deciding report explicitly distinguishes these generations.

4. `1830-B-actions.md:5,21` is stale after the final G16 receipt: it says G16 is pending and current-G verification UNRUN. The exact attempt-2 poststate receipt at `R/1800-Bcas-checks/outputs/attempt2/poststate-receipt.json` records **16/16 PASS** on `5ece606` / tree `ff36af8`; cite its pinned outputs and replace the pending wording. Keep this as that 16-case check only; it does not widen the 102-case author receipt to whole-B/G acceptance or close findings.

## Cross-checks that need no change

- B87 is correctly assigned to B for evidence and C for canonical `streaming.py` behavior. The 205/724 receipt has the committed raw `native.xml` (10,736 bytes, SHA `a5f9dd7c…`) and stdout, 7 pass / 1 fail; the action correctly keeps it open and asks for an exact frozen-G consumer replay.
- The 42 `polisyos.scientist.__all__` exports versus the 39-entry inventory/reference are the exact 3c surface discrepancy. `team-polisyos` is the stable contract's canonical owner; the action correctly routes inventory/readback and the release owner/version-owner reconciliation there.
- The raw HTTP underflow remains in the unchanged Gateway decoder. The 21-fail/3-control output is D1.0; the revised B1.1 response-text assertion has no deciding run. The draft keeps those identities separate and limits multi-key atomicity to profiles that actually use multiple keys.
- The D ledger counts (45 findings, 46 occurrences, 17 bundles; 0 closed / 35 limited / 7 held / 3 open) match the 3c accounting. No broad mathematical or independent 4D oracle claim is made.
