# Acquisition movement evidence

All raw paths are relative to this journal directory and gitignored. SHA-256 is
over complete retained bytes, not the displayed terminal excerpt. Research scripts
and reports are tracked; raw inputs/outputs are not duplicated into Git.

## Admission, environment and Stage 1 census

| Receipt | Process exit / meaning | SHA-256 |
| --- | --- | --- |
| `raw/worktree-admission-create.json` | 0; exact proposed branch/path admitted before creation | `449a5d3151fb2c0178065f4c6ce5513e019fe3d2549ff0e41202ab7d6483e402` |
| `raw/worktree-admission-resume.json` | 0; exact attached pair verified after creation | `db80be7d3f3ac8744d3c13f6ffa8317c58864dc5bc8fc35c18b995cc6fc033d5` |
| `raw/stage1-census.json` | 0; complete bounded census | `33f713d37f5a6d0bd7dd7fa79487bf962740de1f0f72e90372473cd9acc80c38` |
| `raw/partition-reconciliation.json` | 0; ten commission IDs = eight lifecycle + one numeric + one provenance row | `a23bde1648bf1957a1c4c4307d9d6a7b491b8f00ed55df0fda9a8d6636ea0afc` |
| `raw/environment-setup.log` | 1; offline lint/test/runtime wheel cache incomplete | `c649b8c35cb13842d5d6953c012810101cbb00b7724f6fd8bd7015450cf53883` |
| `raw/environment-runtime-setup.log` | 1; offline test/runtime cache incomplete | `fdb3914291a3524f00850db8925cff980b65e5d4c965110a62cd04117c08bc67` |
| `raw/environment-reused-station.json` | 0; explicit local dependency reuse, this lane's source/tools imported | `b790292377bbbcd95df069fa90a4d27d52bbd6113f763edce17a11f7cbbe4845` |
| `raw/pnpm-install.log` | 0; `corepack pnpm install --frozen-lockfile`, before TypeScript owner scans | `ad357c6f2599417adf652688c0299e5b5d6f51aacdf1ff20bb36c6bf5b364dcf` |

The census command was
`PYTHONPATH=src:tests:. .venv/bin/python docs/superpowers/journals/acquisition-movement/probe_stage1.py`.
Its denominator is all **5,704 `.py` files under `policy-engine/{src,tools,tests}/`**;
Git index, pinned HEAD tree and recursive filesystem sets reconcile exactly.
No selected member failed reading or parsing. The commissioned first-cell row
census uses the Markdown table tokenizer and independently reconciles exact
first-cell prefixes: **ten selected IDs, each present once**. Static call
selection retains its alias/receiver/runtime-dispatch boundary. The independent
positive and outlier censuses use their own source-set and call derivations.

The local `.venv` uses Python 3.14.3 and a `.pth` pointing to the existing
`integration` worktree's installed dependency directory. This is an explicitly
reused station, not a successful fresh frozen bootstrap. `PYTHONPATH=src:tests:.`
keeps this lane's code first. No shared dependencies or production data are written.

## Semantic scope and in-flight checks at the Stage 1 commit

The mandate four-node command and complete exit-0 output are bound in
`mandate/stage1.md`. Positive component and removal observations are bounded to
isolated test transport, with no institutional appointment or live production
growth claimed. The initial port baseline was compiled before a later harness
flag addition; it and the mutant preserve the same deciding assertion but are
not claimed as identical harness bytes. A frozen harness replay will resolve that
evidence limitation before final closeout.

The initial positive two-node command completed with one component pass and a
CLI subprocess timeout; fresh CLI execution is `UNRUN`, not a product failure.
The outlier education/numeric timeouts are likewise harness nonreceipts. Their
source-derived subject classifications do not depend on a claimed fresh green.

At the Stage 1 source freeze, the root acquisition baseline, ledger check and
architecture guardrails are still running. They are not certified here. The two
required gates each run as the **only command in their own shell invocation**,
with direct redirection to `raw/ledger-check.log` and
`raw/architecture-guardrails.log`; no pipeline can substitute another process's
exit. Final process results and raw hashes will be appended after completion.

Stage 1 was reviewed independently for mandate/registration and for positive
admission/qualification. The latter found a present-versus-proposed consumer
ambiguity and the fresh-count/replay distinction; both were corrected in
`STAGE1.md`. A deeper native predicate-producer absence is recorded in the same
qualification class, not hidden behind appointment wording.
