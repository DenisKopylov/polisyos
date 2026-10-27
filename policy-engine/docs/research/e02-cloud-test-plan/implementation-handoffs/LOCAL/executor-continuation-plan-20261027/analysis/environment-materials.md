# E02 Environment and Materials Audit

**Snapshot:** 2026-10-27. Read-only audit of the pinned local E02 checkout; this file is the only requested output. No product checks, installs, cloud task, cleanup, recovery, or payload hashing were performed.

## Checkout and source state

The observed checkout is `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`, branch `codex/e02-unified-local-20261009`, HEAD `ad81c5b826bdfdda6aa2295b8641e9ae2a68b21a`, tree `df24ff6ff12e7039c0cbfbd47abc8bee82f5332e`; these match the requested pins. `git status -sb` also showed a large pre-existing untracked set, including mixed-owner `LOCAL/`, raw handoff material, fixtures and logs. Do not infer a clean checkout or overwrite those files. The older code preservation checkpoint `8698293225576fc7a1ad8f6d2c1ca8834f04140c` is a WIP ancestor, not the current HEAD or an acceptance receipt.

Commands and live local results:

```text
pwd                                      /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos
git branch --show-current               codex/e02-unified-local-20261009
git rev-parse HEAD                       ad81c5b826bdfdda6aa2295b8641e9ae2a68b21a
git rev-parse 'HEAD^{tree}'              df24ff6ff12e7039c0cbfbd47abc8bee82f5332e
df -Pk .                                 7,891,428 KiB available; 97% used
sysctl -n hw.memsize                     17,179,869,184 bytes (16 GiB)
sysctl -n hw.ncpu                        8
memory_pressure -Q                      78% free at observation
policy-engine/.venv/bin/python --version Python 3.14.3
```

The filtered process summary showed Codex/CUA and Node processes, but no Python/pytest worker. These are point-in-time host readings, not an admitted workload measurement. Current disk free space is about 7.52 GiB: above the existing 6 GiB general floor, but about 0.48 GiB below the 8 GiB R1 reserve. Do not start R1 or an install/build wave on this local disk without a later fresh admission check.

## Cloud CLI and capacity status

The supplied cloud environment ID is `6965429cdb308191a0e6eb63cb118ea3`. Only help/version commands were used; cloud task follow-up and cloud capacity remain **not verified**.

```text
command -v codex   /opt/homebrew/bin/codex
codex --version    codex-cli 0.36.0
```

The PATH CLI help does not list a `cloud` command. The exact app binary at `/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex` reports `codex-cli 0.165.0-alpha.1.2`; its `cloud --help` lists `exec`, `status`, `list`, `apply` and `diff`, and `cloud exec --help` requires `--env`. No environment was queried or task submitted. This proves the installed app CLI exposes a cloud interface, not that the supplied environment is reachable or configured.

The [core/native route note](core-native-routes.md) treats **about 32 GB as future total disk capacity**, explicitly not 32 GiB free and not RAM; no cloud receipt confirms even that total. No provider machine type, RAM, vCPU, disk mount/ephemeral behavior, usable free bytes/inodes, dependency cache, setup duration or cost was established. Keep these unknowns visible until the cloud executor reports them. Do not use Work cloud as a substitute.

## Local materials and portability

| Material | Observed state | Portability / handling |
| --- | --- | --- |
| `policy-engine/.venv` | Present; Python symlink resolves to the existing uv-managed CPython 3.14.3. | Reuse locally. Do not recreate or install. A cloud environment has no verified copy. |
| `policy-engine/node_modules` and dashboard Lefthook binary | Present; `policy-engine/apps/runtime-dashboard/node_modules/.bin/lefthook` exists. | No dependency install was run. On a fresh checkout, use the repository's locked `corepack pnpm install --frozen-lockfile` only when a selected task needs those packages. |
| `policy-engine/.polisyos` | Present; contents not traversed. | Preserve in place; do not classify its CAS/runtime state as disposable. |
| `policy-engine/production_data` | Symlink exists to `/Users/deniskopylov/polisyos/policy-engine/production_data`; target payload was not enumerated or read. | Local read-only link, not a portable cloud input. The first V6/C01 slice is a fixture-based programming check and does not establish production currentness. |
| Near-term G27-01/V6 materials | The RAW `test-only-r5/test.patch` and its `manifest.json`, the `stop-handover-r1/handover.json`, `plan-g27-v6-profile-matrix-red-r1.json`, and `run_case_with_tools_r2.py` all exist at their handoff paths. | These are local, unapplied evidence/proposal materials. The recorded A/A attempt failed with `simulation_result_binding_unavailable` before the intended A/B red; r5 is not a product fix or a passing test. Preserve the exact profile and fixture scope. |
| Retained audit outputs | The existing `D` audit directory and its case records are in place. | Preserve stdout/stderr/JUnit/profile/CAS outputs; this audit checked paths only and did not traverse payloads. |

The handover's `P`, `W`, `N` and `D` aliases expand to absolute `/Users/deniskopylov/...` paths under this machine. They are locators for the current local checkout and its RAW evidence, not portable contracts. On a future cloud worker, resolve the checkout with `git rev-parse --show-toplevel` and use repo-relative paths. Use pinned tracked source and the exact self-contained C01 materials; cross-check selected nonancestor G objects only if available, using the supplied selected-law summary otherwise. Fetch only separately admitted public objects needed for the admitted slice. Do not copy the entire local RAW tree, private production data, historical chat files or the full recovery copy set to make a cloud path resolve.

## Resource and dependency budget

| Resource | Existing bound or observation | Admission rule for a future cloud run |
| --- | --- | --- |
| Disk | The older local procedure estimates about 1.5 GiB of package scratch while reusing its worker; shared cache, fresh checkout, fresh dependency extraction and GCP overhead were excluded or unmeasured. Existing policy: 6 GiB floor; R1 needs 8 GiB free. | Treat ~32 GB as a provisional total-disk ceiling only. Measure actual free disk and inodes before setup and each native wave. The local 8 GiB R1 reserve and 6 GiB floor apply only to the actual Mac run. A cloud slice uses its own measured dependency/output/headroom budget, not those inherited local floors. The 1.5 GiB estimate does not certify a fresh cloud install fits. |
| RAM / concurrency | Local hardware is 16 GiB. Prior admission allowed up to two already measured jobs with combined RSS ≤4 GiB and one numerical thread per job; first unknown-cost, native GP and VM runs were single-job. | RAM is unknown in cloud and cannot be inferred from disk capacity. Start with one measured job, capture peak RSS and wall time, and keep unknown-cost numerical/GP/VM runs alone. Admit cloud concurrency against that VM's measured RAM/headroom and fixture contention; the local two-job/4-GiB bound does not apply to cloud. |
| Dependencies | Local Python and Node environments already exist. | Install only dependency groups required by the selected slice, from tracked locks; report before/after free space. Do not install every research extra or copy local caches as an unmeasured shortcut. |
| Test artifacts | Exact local handoff files exist; checkout size, cloud dependency expansion and test-output/CAS growth have no cloud measurement. | Before execution, record free disk/inodes and RAM; after each bounded run, retain its source/profile/input pins, stdout/stderr/JUnit and measured resource receipt. A capacity number alone is not an execution receipt. |

For the next G27-01 slice, use the recorded exact C01 plan and first establish both A/A selectors work on the scoped runtime store; only then observe the intended profile mismatch. The current failed A/A fixture is a harness/input blocker, not evidence of the product property. Keep this small fixture run separate from unmeasured native GP, VM and installed/package waves.

## Recovery and manifest arithmetic

Counts below were recomputed from the complete JSON manifest records; no bulk file content was read or hashed for this audit.

| Manifest/source | Recomputed denominator and result | Meaning |
| --- | --- | --- |
| `recovery-pre-checkpoint/manifest.json` — `LOCAL/raw/executor-handover-20261027/recovery-pre-checkpoint/manifest.json` (repository-root local locator), `untracked` | 5,435 regular-file records totaling 105,603,371 bytes. `index-vs-head.patch` is 0 bytes; `worktree-vs-index.patch` is 131,154 bytes. | The manifest records full local recovery copies of the pre-checkpoint nonignored untracked files and that originals were left in place. This audit did not lstat/hash every copy. This is not a cloud test fixture or permission to bulk-restore/commit. |
| [`proposal-index.json`](../../executor-handover-20261027/proposal-index.json), all `proposals[].patches[]` | 10 proposal groups, 12 patch records. | Selected proposals are unapplied. Copy/admit only the exact patch and companions chosen for a future task. |
| [`subagent-registry.json`](../../executor-handover-20261027/subagent-registry.json), `rows` | 570 metadata rows = root + 569 direct children; depth values are 0 and 1; 475 rollout locators available and 95 unavailable within checked paths. Twenty final live-tool entries were all completed. | Historical transcript contents were not scanned or copied. The 95 are missing locators in this bounded path check, not a count of lost source results; existing Git/RAW evidence remains separately indexed. |
| `LOCAL/raw/executor-handover-20261027/commit-source-checkpoint/intent.json`, `paths` | 17 source/test/tool paths. | These were committed as unfinished WIP in the 8698293 preservation checkpoint with normal hooks. They are not 17 remaining untracked files, a green verification wave, or product acceptance. |

For a specific missing local source, first compare its present bytes and owner against the current pinned branch and recovery manifest. Restore only that admitted path from the full copy under `recovery-pre-checkpoint/untracked/`; use the tracked Git checkpoint for committed source. Preserve the exact RAW run under `D` when a decision depends on it. Do not infer that the 95 unavailable historical message locators have a local transcript backup: no broader archive/iCloud search was performed, and their message-only contents are not claimed recoverable.

## Commit-hook impact and audit limits

The configured shared hook directory is `/Users/deniskopylov/polisyos/.git/hooks`. Active `pre-commit` and `prepare-commit-msg` scripts dispatch to the runtime-dashboard Lefthook config; the config has no Python/backend/native test command. A docs-only file outside `policy-engine/apps/runtime-dashboard/` does not match its Prettier/ESLint globs, but pre-commit still runs `check-contrast` and `check-reduced-motion` Node scripts. `pre-push` runs dashboard typecheck and is not part of an ordinary local documentation commit. No hook or verification command was run in this audit; root owns any eventual commit.

The counted sets use their manifests and explicit denominators (P35); status remains bounded to each recorded observation (P41). Cloud provisioning, actual cloud resource values, fresh-install disk footprint, production-data availability, and full historical transcript recovery remain unverified.
