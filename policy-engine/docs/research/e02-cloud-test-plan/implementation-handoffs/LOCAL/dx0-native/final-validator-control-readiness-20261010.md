# Final validator/control readiness — 2026-10-10

## Frozen basis and disposition

This is a read-only readiness review of candidate `9de48febba1ef18c8e1252dc027cb0d89b88abc3`, tree `d524ed13bdbcf6b7e65b838ca2a42f70df15d5c9`, in `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`. I re-read the commit/tree and source files at that checkout. No test, `--check`, generator, build, or product command was run for this review. All current-candidate command outcomes below are **UNRUN**.

The relevant code is present and the existing controls are runnable. Do not call a `sync`/`--write` command: it rewrites governed output. For the final public/generated freshness verdict, use the check command and do not pass `--skip-generated-checks`.

## Commands for the root run

Run from `policy-engine/` after the frozen source is attached:

```bash
uv run polisyos-tools architecture guardrails check --all-generated-checks
```

This is the repository SOTA generated-drift command (`tests/repo_quality/architecture/test_repository_sota_phase5_closeout.py` pins it). It recomputes the supported public inventory and deep-import census, checks the committed public/reference/generated-artifacts output bytes and guardrail manifests, then runs default generated freshness plus the optional declared checks. Expected full success: exit `0` and `Architecture guardrail check passed.` Exit `1` is a failed check. Exit `2` prints `Architecture guardrail check UNRUN: required measurements unavailable; no complete verdict.` and is not PASS. `--skip-generated-checks` explicitly prints `SCOPE LIMITED` and a freshness-omitted success message, so it cannot satisfy the full freshness requirement.

For retained isolated generator evidence, the existing CLI accepts both `--generated-freshness-workspace-root <new-path>` and `--generated-freshness-uv-cache-dir <existing-cache>` together. The cache must already exist outside the repository. The required output probes run from an isolated source copy into a scratch output root; the implementation snapshots the live worktree before/after and verifies that the isolated source did not change. Do not substitute `sync`: `run_sync` writes `architecture/public_surface/inventory.json`, `docs/reference/public-surface.md`, the deep-import baseline (unless explicitly skipped), and `docs/reference/generated-artifacts.md`.

Scope distinction: the manifest has 110 family records. Four are selected for default freshness (runtime OpenAPI snapshot, runtime API client, runtime dashboard API types, trust-claim posture); 106 are optional. `--all-generated-checks` also dispatches the 82 optional families that declare a `check_command`; 24 optional family rows have no command and are skipped by that dispatcher. Optional commands run at their declared `check_cwd`, not through the isolated required-output probe runner. One explicit optional command writes `_build/.tmp/fabric-schema-governance.json` via `--evidence-out`; preserve that ignored diagnostic output. I did not execute or claim outcomes for any of those 82 commands.

Run the E02 index-integrity check from the repository root:

```bash
python3 policy-engine/docs/research/e02-cloud-test-plan/results/import_results.py --check
```

Expected on a consistent transferred pack: exit `0`, stdout exactly

```json
{"ok":true,"files":["cells.tsv","properties.tsv","events.jsonl","gates.json","routes.tsv","verification.json"]}
```

and empty stderr. This validates transferred text/index integrity only; it is not product behavior, VM receipt, semantic adequacy, or finding closure. `verification.json` itself says `product_closure=not_established` and `raw_archives_received=0`.

Existing public-surface controls can be run from `policy-engine/` without rewriting canonical files:

```bash
uv run pytest -q \
  tests/repo_quality/architecture/test_public_surface_supported_entrypoint_inventory.py::test_public_surface_inventory_corrupt_supported_entrypoint_fails_check \
  tests/repo_quality/architecture/test_public_surface_export_resolution.py::test_removed_import_resolution_keeps_facade_markers_but_original_oracle_fails \
  tests/repo_quality/architecture/test_public_surface_snapshot.py::test_public_surface_snapshot_gate_matches_phase3a_baseline
```

Expected: `3 passed`. The first test constructs a `tmp_path` repository, writes an inventory for one package/one entrypoint with `HumanDecisionRecord`, changes only that facade's `__all__` to empty, and requires the real `guardrails.run_check` to return `1` with `Public surface inventory JSON drift detected` and the stale name. Package and supported-entrypoint counts stay fixed; exported-name count does not. The second keeps the fixture facade's import and `__all__` markers but changes the export reader result to empty; the original positive-export oracle must fail, then pass again when the reader is restored. It is a marker-preserving behavioral oracle test, not a complete `run_check` integration. The third exercises a separate phase-3a snapshot gate and its full package-file census; it is supplemental, not a substitute for `guardrails check`.

For an independent count-preserving E02 output corruption probe on the frozen importer, use a new ignored scratch root and preserve the layout the importer actually opens:

- `$SCRATCH/results/` — copy the complete `results/` directory;
- `$SCRATCH/full-run/allocation.json` and `finding-routes.json`;
- `$SCRATCH/execution-organization/finding-owners.tsv`.

First run the clean-copy positive with `python3 policy-engine/docs/research/e02-cloud-test-plan/results/import_results.py --root "$SCRATCH/results" --check`. In the copy only, change the first tab-delimited `PASS` field in `cells.tsv` to `FAILED` once, leaving the row count unchanged, then run the same command. Required negative: exit `1`, empty stdout, stderr `index verification failed: derived artifact drift: cells.tsv\n`. Retain the scratch and full outputs; do not alter the tracked result pack. The importer already has this probe in the historical startup receipt, but its target is older (`c40d4acae1ce58b597267255026d9356565828fd`), so replay is required for current-candidate evidence.

## Input denominators and source binding

| Gate | Complete input set read or enumerated | Measured denominator at this candidate |
| --- | --- | --- |
| Public-surface inventory | `architecture/public_surface/contract.toml`, package facades and statically resolved local owner/re-export files, package README/reference pointers, plus the `generated_artifact_family` metadata in the public contract | 20 package policies; 38 explicitly supported entrypoints. The committed `architecture/public_surface/inventory.json` records 253 resolver input operations across the 38 entrypoints: 103 `read_bytes`, 150 path-existence probes, 85 unique paths (45 unique `read_bytes` paths). This is a source-binding census, not a runtime import of arbitrary modules. |
| Deep-import baseline | `_iter_py_files()` over `src/polisyos/**/*.py`, excluding `__pycache__`; each file is parsed for imports | 2,748 Python files. |
| Independent public snapshot test | `collect_public_surface_snapshot()` walks every top-level `src/polisyos` package directory with `__init__.py` and every nested Python file under those packages, excluding `__pycache__` | 25 package directories; 2,747 Python files. This is a separate phase-3a baseline and excludes one top-level `.py` outside those package directories. |
| Generated-artifact governance | Every `[[family]]` row in `architecture/generated_artifacts.toml`; checks/rendered reference are compared to their declared sources | 110 family rows; 4 default freshness families; 106 optional families, of which 82 declare optional `check_command` and 24 do not. `docs/reference/generated-artifacts.md` is rendered from this manifest. |
| E02 import/navigation index | `full-run/allocation.json`; `full-run/finding-routes.json`; `execution-organization/finding-owners.tsv`; `results/sources.json`; every listed `results/received/F01.txt`…`F15.txt` transfer | 15 allocation jobs and source rows/texts; 2,074 planned file×cut cells; 9 additional property states; 14 non-pytest gates; 282 finding routes and 282 owner rows. Six derived outputs are byte-compared: `cells.tsv`, `properties.tsv`, `events.jsonl`, `gates.json`, `routes.tsv`, `verification.json`. |

Source pins read from the frozen tree:

- `architecture/public_surface/contract.toml` SHA-256 `14ae5db4c9f137e2d5b434fd1cdf259151216e7952b50da04218754eef3bdce6`
- `architecture/generated_artifacts.toml` SHA-256 `2283a5faa66061b66cad5870976dcefd92cb40d74658300d93590ee6fe3e97da`
- `tools/devx/architecture/guardrails.py` SHA-256 `ab19751f999d3ca5385eb4997e78855b2a551e5cbbf26bd0f78addc991af9031`
- `docs/research/e02-cloud-test-plan/results/import_results.py` SHA-256 `701a73c316eb1d9b842004efbb8856960f9ccbe896816b365a13a415a7c50410`; this matches the helper digest recorded in current `results/validation.json`.

## Boundaries and review classification

- **P29/P32:** the public inventory checker recomputes the expected JSON from contract plus parsed source rather than trusting the stored export names; the `__all__` mutation test proves an actual source-to-output drift is rejected, and the reader test supplies the marker-preserving negative. The E02 importer's count-preserving output mutation proves the consumer notices a changed derived cell field, but only on its historical target until replayed now.
- **P35:** every count above is from a complete walk of the named path and file-type denominator, not a search-result count. The result pack's 2,074 cells/9 properties/14 gates/282 finding IDs describe transferred compact texts, not executed candidate tests.
- **P38:** the importer checks all six expected output strings against regenerated outputs and checks each transferred source SHA; a passing index therefore means transfer/navigation consistency only. The guardrail compares exact rendered outputs and runs source-derived checks; the standalone snapshot test is a different baseline and is not promoted to the canonical inventory result.
- **P40:** **SAME_CLASS_DEEPER** — this is the same generated-surface/validator-completeness class at the final-command boundary, not a new product mechanism. One bounded ambiguity surfaced: `architecture/public_surface/data_forge.json` exists, but `run_sync` writes only `inventory.json`, the public reference, the deep-import baseline, and the generated-artifacts reference, and `run_check` does not compare `data_forge.json`. The current canonical inventory check therefore does not establish freshness for that separate file; whether it is an intended generated output is not established by this review. No per-file patch is proposed.
- No formal G adjudication or E02 closure is made. Current exact-candidate results remain **UNRUN** until the root runs and captures the commands above.


## Authorized descendant delta readback

The follow-up read-only check was authorized for descendant `d5b465ba561801717626e7619204ee0062ba3ec6`, tree `0daf240801b5d7c12746598c20e40e6cdf807b3c`. `git diff --name-status 9de48febba1ef18c8e1252dc027cb0d89b88abc3..HEAD` shows only four additions under `LOCAL/r4-workload` (three replay/self-test plans and `raw/composed_mac_capture.py`); no product path changed. Re-read source hashes for the public-surface contract, generated-artifact manifest, architecture guardrail, and E02 importer; all equal the frozen-basis hashes above. Thus this descendant leaves the reviewed command and source denominators unchanged. No validator/test/generator was rerun; current descendant outcomes remain **UNRUN**.
