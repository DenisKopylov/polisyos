# Independent A11 receipt review

**Disposition: GO for the focused selector only.** The 11-case result is supported by raw pytest stdout, the raw nested JUnit `<testsuite>`, and the exact-candidate source/origin receipts. It does not establish full A acceptance or production/served-path closure.

## Verified

- Candidate `905820ceac5860c7d1c4ebcbdde7b1265afb0b15` resolves to tree `98405fab6c567d9fd44a5e30387c0ba32a7c7cf9`. The retry manifest binds 2,933 Git inputs / 55,580,566 bytes to that SHA/tree; its archive hash matches the retained tar. All 2,933 extracted entries and all 2,933 pre/post selected inputs report matching hashes.
- Attempt 1 collected zero because `tools.lib.imports` was missing. The retry adds exactly four candidate Git siblings (`imports.py`, `output.py`, `preflight.py`, `sql.py`) required by the tools package initializer. This is a disclosed source-closure correction, not a product failure.
- Raw stdout lists the 11 exact cases as PASS and ends `11 passed, 1 warning in 25.80s`, exit 0. Raw JUnit contains a nested suite with 11 tests, zero failures/errors/skips. The initial derived parser read the outer `testsuites` tag and counted zero; the corrected nested summary matches the unmodified stdout/XML. The single Pydantic serializer warning is on the deliberate subclass-refusal case.
- The 1,468 parent-process `polisyos` file origins are recorded under candidate `src/polisyos`; the origin verifier maps each to a retry-manifest Git input and reports all hashes matching. The fresh child separately proves the actual `generation_cycle.py` path is the retry checkout, with distinct PID, exit 0, and raw stdout/stderr hashes. Its value is `value_conditional` with `simulation_only_k_sim_not_world_evidence` retained.
- The test's main counterfactual is effective: removing the N5 selector argument preserves the refusal marker but selects the refused high-ranked candidate; the test then confirms blocked simulation and zero N5 calls. All-infeasible and feasible-over-conflicting cases also exercise the production default N5 path through synthetic tenant-scoped CAS fixtures.

## Scope and report correction

This is a controlled fixture witness: generator and grounding ports are doubles, and the NCM is synthetic. The file checks legacy injected-controller call compatibility and that a profile-handoff composition declines preflight; it does not establish hard-feasibility enforcement for injected/custom controllers, profile handoffs, or custom request factories. It also does not cover production N4/grounding, valid-manifest L6 inputs, served POST→GET, or broad simulation/finding closure.

The report's statement “No unselected generated files remained inside either candidate checkout” is false. The retry checkout contains three extra, zero-byte `.polisyos/runtime/grounding_risk/*/cas/artifacts/ownership/transactions/root.lock` files absent from the 2,933-input manifest; the initial checkout has none. They were created during the retry run and do not alter any selected input hash. Correct that inventory sentence and disclose the generated residue before relying on the storage/cleanup description. This does not invalidate the focused test result.

Review was read-only: no tests rerun, refs changed, or tracked files edited. G remains clean at `127dc7ab8365d29eb656fe32c0c894f6cc971286`.

## Correction adjudication — generated lockfiles

The earlier observation that no unselected generated files remained was accurate only as a byte-total statement, not as a file-count statement. Inspection of the isolated retry checkout confirms exactly three extra `.polisyos/runtime/grounding_risk/<record-hash>/cas/artifacts/ownership/transactions/root.lock` files. All three are zero bytes and report zero allocated bytes; their mtimes fall within the single retry test window. They are absent from the candidate Git tree and the 2,933-input selected source manifest. The before/after input manifests still match all selected hashes.

The focused 11-case PASS remains unchanged. This correction did not rerun tests, alter source or refs, or rewrite any raw stdout, JUnit, input manifest, or observer output. Exact paths, stats, candidate-entry probes, and hashes of preserved raw receipts are in `../2020-A11-postrun-lock-residue.json`.

## Independent acknowledgement of the lock-residue correction

I independently checked `R/2020-A11-postrun-lock-residue.json`: all 16 preserved raw-receipt SHA-256 entries pass `shasum -c`. I re-statted each of the three retry-checkout lock files: their device/inode pairs match the receipt, each is zero bytes with zero allocated blocks and the empty-file SHA-256, and each path is absent both from candidate `905820`'s Git tree and the 2,933-entry source manifest. The report's correction is therefore supported. This acknowledgement confirms only that correction and the already-reviewed scoped 11-case GO; it does not expand the test's property scope. No test was rerun, and no Git ref or tracked file changed.
