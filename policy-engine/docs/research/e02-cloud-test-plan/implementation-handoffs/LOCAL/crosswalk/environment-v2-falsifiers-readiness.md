# Environment v2 falsifier harness readiness

Status: harness authored, not executed. This artifact is a falsifier runner, not an admitted environment profile, source-freeze receipt, product test, occurrence evaluation, or formal closure.

The executable ignored harness is `LOCAL/raw/environment_v2_falsifiers.py` SHA-256 `65267dcc6d937668ef5892b2cd6bfdc473e6a64a5254daf3879def33c07ce3ca` (mode `0755`). The path is covered by `policy-engine/.gitignore:151` (`docs/research/**/raw/`). It imports the actual adapter and wrapper at run time and records their source hashes. Current readback sources are `LOCAL/raw/env_manifest_adapter.py` SHA-256 `ba037da67a4ebf036687c5fd4a95ac3d37722358a1c1c7236762f2414126e65c` and `LOCAL/raw/composed_mac_capture.py` SHA-256 `c9d6c5b77335e7833323f6616de94c743bc39ec05fd62f17d68f802857aac5a9`. The adapter’s applied source-boundary patch is not itself a final source freeze; the current observation remains V5 partial at `LOCAL/raw/v5-full-light-admission-verification-20261010/environment-v2-observation-pid-bound-r4.json` SHA-256 `b48b95a7c930a724ff8de35218cd2f67cefbbc91412568688702bc7e2281c095`.

## Required baseline

The main mode requires a future first-final-wave observation and stops before running any control unless all of these hold: its v2 evidence refs rehash; the adapter recomputes `source_freeze.status=resolved`; `source_context.plan_input_denominator_status=reconciled_exact_plan_set`; `command_input_binding.status=resolved`; the process capture is bound by its command output receipt; and the captured command has exit code zero with zero JUnit failures/errors. It also calls the real `load_and_validate_plan` and `verify_input_manifest` wrapper methods and compares the full projected rows to the frozen rows. A partial environment observation may be the baseline if its source and command evidence satisfy those checks; an absent, stale, partial-source, empty, or unrun denominator is reported as `NOT_RUN_BASELINE_UNADMITTED`, never as a green negative-control set.

The omission control removes an actual declared source/test input, updates `path_count`, recomputes the frozen-manifest self-digest and command input digest, and updates the handoff selection when present. It requires the command-input hash binding to remain resolved while the adapter’s complete wrapper-derived set reconciliation fails. This distinguishes a real required-set check from a self-consistent, shorter manifest.

The replacement-object control creates a dedicated Git repository under that run’s ignored raw output directory. It calls the real wrapper projection API against a commit whose working input has been replaced, first with `GIT_NO_REPLACE_OBJECTS=1`, then with replacement objects enabled. It records the exact `git` and wrapper Git streams. The control checks the adapter’s matching guard predicate: a nonempty `refs/replace` list must be rejected before the wrapper projection can support source evidence. It never writes refs to the candidate checkout. The comparison is an isolated wrapper-API falsifier, not a call to the entire adapter source-context function over the fixture.

## Controls and interpretation

The harness records 12 controls with their mutated input copies, rebuilt observations, validator readback, exact errors, and per-control results:

1. Wrong PID-derived sidecar base.
2. Capture PID that disagrees with its matching wrapper receipt.
3. Command plugin digest changed while the actual plugin bytes stay fixed.
4. Sidecar bytes changed at a PID-derived path while the receipt path is retargeted but its old content digest is retained.
5. Candidate tree drift against the frozen manifest.
6. Source-manifest digest drift against the checked manifest ref.
7. Command output inventory digest drift for the process sidecar.
8. Aggregate `complete` flag with unresolved roots or non-filesystem modules retained.
9. Unattested owner/version statuses for `_virtualenv`.
10. `opentelemetry` directory root marked resolved without file content or per-child origins.
11. Required plan-input omission with the manifest and command digests recomputed.
12. Canonical no-replace and replacement-enabled projections in the isolated Git fixture.

`PASS` means the targeted falsifier observed refusal or unresolved status; it does not prove an environment profile. `FALSIFIER_EXPOSED` means the mutated declaration crossed the tested projection. `UNRUN` means the selected process lacked a needed target; it cannot be counted as success. Any such status is retained in the overall result. The owner/version and namespace controls specifically probe whether a copied process-capture status can promote a root without owner or child-origin evidence; if they expose that, classify it as the existing P37/P38 environment-provenance class. Do not add per-root repairs. This is **P40 SAME_CLASS_DEEPER**: the mechanism must validate the complete required input/provenance quantity, or a named bounded residual and its falsifier must be declared. The controls do not establish complete environment provenance, admission, or G closure.

## Commands for the later frozen wave

Run the main falsifier only after the final source/input freeze and first fresh light command have produced a complete v2 observation. Substitute that actual report path; outputs go to a unique child of ignored `LOCAL/raw`:

```sh
python3 policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/environment_v2_falsifiers.py --repo-root . --baseline-observation <fresh-v2-observation-path> --output-parent policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw
```

Keep the earlier V5 serialization check separate and bounded. This is the exact recorded CLI, with the current adapter source path; its historical `PASS_PARTIAL_OBSERVATION` only revalidated the V5 partial report and did not resolve source freeze. Rerunning it is useful only as a partial serialization check:

```sh
python3 policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/env_manifest_adapter.py --repo-root . --command-metadata policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/v5-full-light-admission-verification-20261010/command.json --process-capture policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/v5-full-light-admission-verification-20261010/origins-50915.json --stdout policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/v5-full-light-admission-verification-20261010/stdout.txt --stderr policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/v5-full-light-admission-verification-20261010/stderr.txt --junit policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/v5-full-light-admission-verification-20261010/junit.xml --plugin-source policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed_mac_pytest_origin_plugin.py --output policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/v5-full-light-admission-verification-20261010/environment-v2-observation-pid-bound-r4.json --check
```

The separate harness mode for that old report is `python3 .../environment_v2_falsifiers.py --repo-root . --v5-partial-check`; it accepts only `PASS_PARTIAL_ONLY` and never feeds V5 into the source-bound controls. No product tests, harness run, Git-ref mutation, or environment mutation was performed for this preparation.
