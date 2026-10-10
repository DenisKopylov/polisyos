# Independent review — Morris marker-removal harness V5

**Static verdict: GO for the prepared source-bound V5 probe set; no blocking static escape found. This is not an execution receipt.** V5 closes V4's omitted ragged-coercion boundary and adds an explicit bounded-child policy. No pytest selector or harness child was run during this review.

## Exact review boundary

- Candidate checkout: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`
- Branch/HEAD/tree: `codex/e02-unified-local-20261009` / `297b0557511234bb4b1bd3b09991cef0bd050a3f` / `ad9ecc1c4bf2acd57b187b5a2534aa9f3b2d3ffd`
- Harness: `LOCAL/raw/morris-marker-removal-harness-v5-20261010.py` @ `dcc96f1a27448bcb7f8e3fa6b92c4581990f0d4cf89c4b7f451b76df1b8fd50f`
- Author note: `LOCAL/dx0-native/morris-marker-removal-harness-v5-20261010.md` @ `cdbe154047fa7440743da1f1749ede3f378c466c9bea5ef404bb9c8b783258cc`
- Pinned source hashes read from the candidate match the six frozen manifest entries: Morris producer `screening.py` `b9a2a2dfc1e70473047a48500e9da2eab2c9180e567e36935017657caa7973e2`; Morris test `test_screening.py` `56f30b88836d86b3e811821f5bfae3d155fa9e185059e8da490d440fff0266f3`; IO helper `io.py` `79172d1619e3424d6282f0d5eaa89fdaf08d65d0de620b078562f1e7b16b86c9`; sync executor `chain_executor.py` `ecb335acfa0cca4574b101d328317534d22320164f5730239a69d1c78261b7ed`; async executor `async_chain_executor.py` `3b75e619092347c74dd51a92ab4e46e67d966965426a0903ad124c2c34a19c51`; backend tests `test_backends.py` `0f4c2a3d615f9bf7e45d5dabcf5f6621fc407499901a50af791096d647c31548`.

## Findings

P40 bucket: **SAME_CLASS_DEEPER**. V5 covers the actual recognized-array coercion-failure branch left out by V4, alongside V4's six sync/async rank cases and two Morris probes. The coercion mutation replaces only the unique `_as_array_like` exception branch with `return None`; it preserves the validator and downstream contract check. The marker `b"could not be coerced"` remains in the separate `validate_value_for_slot` message at `io.py:153`, so the in-memory marker check is consistent with this mutation. The mutation also asserts the target block is unique, absent afterward, and changes source bytes.

The ragged selector is pinned to the real two-mode test. The intact probe requires both tests to complete without consumer dispatch. The mutation probe requires both dispatch events, two JUnit failure/error outcomes, and typed-stage diagnostic text (`ValueError` or `MethodContractError`), so a pytest exit code alone cannot establish the property. Hook events bind the exact source/input manifest and record successful module execution before classification.

Every child is run through one `run_child` wrapper with a 60-second deadline. Timeout keeps available partial stdout/stderr, records a null return code and `ERROR/UNRUN`, and bypasses JUnit property classification. The 60-second cap has margin over the cited measured 8–10-second focused child runs and 17.39-second module run. The report separately tracks valid receipts and mutation detection, so a valid escape is not misreported as a harness failure or as a detected property.

## Limits

The review establishes only the harness's static readiness and declared selectors. The actual six child runs, retained JUnit/event evidence, source immutability checks after execution, and timeout behavior remain **UNRUN** here. V5 must be executed after the applicable source/input freeze; only its captured results can establish the runtime probes. No G adjudication or broader input-validation closure is claimed.
