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

## Completed Stage 1 boundary and subsequent evidence

Stage 1 was committed as `bf9b862ef7b6dcc05ca58eb9e63612abc849e411` on
the attached `codex/acquisition-movement` branch. Every delivered file was then
read from that branch and compared with its workspace bytes. Complete receipt:
`raw/stage1-branch-readback.json` @ SHA-256
`548ead3699d993c7cef47fefa7102093dede45f965f3fa36d55fcb8f1c6de4ab`.
No production source edit followed. The subsequent R4 clarification cites the
primary handoff's explicit `deferred-with-a-name` standing and distinguishes it
from execution allocation. It does not promote the handoff into an active task.

### Targeted runtime evidence

The following acquisition command completed with the process's own exit **0**:

```sh
PYTHONPATH=src:tests:. .venv/bin/python -m pytest tests/unit/runtime/http/test_acquisition_route_authority_sink.py::test_active_owner_receipt_persists_reentry_pending_before_callback tests/unit/runtime/http/test_acquisition_control_worker.py::test_worker_loads_durable_decision_before_sealed_effect_and_terminal tests/unit/runtime/quality/test_generation_cycle.py::test_active_overlay_reentry_rejects_binding_and_trace_mutations tests/integration/core_runtime/test_acquisition_route_execution_binding.py -q
```

Complete output: `raw/baseline-acquisition-targets.log` @ SHA-256
`fe9dca0451129aaabdd76ea13e310b61a52091a146a1f9fe5b72b851eb33547f`.
The selectors are the verification denominator; no complete-suite or live
production claim is made. The separately retained mandate command also exited 0.

The frozen removal wave ran after the Stage 1 commit:

```sh
PYTHONPATH=src:tests:. .venv/bin/python docs/superpowers/journals/acquisition-movement/refusal_wave.py
```

Its process exited **0**. Within that one process the unchanged deciding witness
passed at baseline, failed with the real port's re-entry enforcement removed in
memory, and passed after restoration: assertion outcomes **0 → 1 → 0**. These
are assertion outcomes, not three subprocess exit codes. The original production
file and the witness bytes were unchanged throughout. The retained exception code,
positive-shaped result and source markers do not keep the witness green when
the enforcement is absent. Transport is isolated; institutional appointment,
real transport and production positive delta remain outside this probe's claim.

| Complete removal receipt | SHA-256 |
| --- | --- |
| `raw/frozen-refusal-wave-result.json` | `b6d12df6e52e3722b8be823d0c7ff4823e74a2783e3935d90455e34c61aef364` |
| `raw/frozen-refusal-wave/baseline.log` | `b47b0207e30644495daf62d1e6bfbadd13447655b16197943d7f8e64bd2c9aa3` |
| `raw/frozen-refusal-wave/removed.log` | `79f7f328963d6b5074b2680f92ee09bf75fc21a2d2a56eb447785cd99ef60b28` |
| `raw/frozen-refusal-wave/restored.log` | `b47b0207e30644495daf62d1e6bfbadd13447655b16197943d7f8e64bd2c9aa3` |

### Architecture measurements and own interference

Each command below was the **only command in its invocation**, with ordinary
output redirection and no pipeline, wrapper status or follow-on shell command:

```sh
PYTHONPATH=src:tests:. .venv/bin/python -m tools.cli architecture guardrails check
PYTHONPATH=src:tests:. UV_NO_SYNC=1 .venv/bin/python -m tools.cli architecture guardrails check --skip-generated-checks
```

The full check's process exited **2**, explicitly `UNRUN`: no complete verdict.
It invoked the OpenAPI owner with a temporary output path. I terminated that
owned child; its recorded exit is 143. The canonical OpenAPI snapshot was never
written. The full check also observed our journal edits while checking for
out-of-scratch writes and attributed those changed paths to its output probes.
That observation was confounded by **our concurrent work**, including the Stage 1
commit and research follow-ups. It is not evidence that the generators modified
those files. This is this lane's verification failure, not an inherited product
failure; no base replay/disjoint-input claim is made. The lane's verification
record is the named destination. Its deciding predicate, exclusive producer
attribution, is `not_established` for this run.

The structural command's own exit was **0**, with generated freshness explicitly
omitted. It does not certify OpenAPI or other generated freshness, or the separate
Atlas inventory gate. No guardrails sync was run and no register or ledger was
edited. Only targeted runtime tests were run.

| Complete architecture output | Process exit | SHA-256 |
| --- | --- | --- |
| `raw/architecture-guardrails.log` | 2; full verdict UNRUN | `895b45b66222743343e43125fc05bc0b1d908bf7b94e3c54cc698cea4c02b2cc` |
| `raw/architecture-structural-check.log` | 0; structural scope only | `bec5670b67034187ca56d3654b1891d7bae72736d0ba6c6a5bfccb7840b805bd` |

### Companion research receipts

These bind the reports' complete retained outputs. Their denominators and
independent cross-checks are specified in the corresponding report and census;
the raw files are not themselves new authority. Selected opaque/unreadable
members remain ambiguous rather than contributing an absence finding. The
timeout receipts establish nonreceipt, not product failure or inherited red.

| Receipt | SHA-256 |
| --- | --- |
| `mandate/raw/census.json` | `cc9c5f2443d5169b2a3754a3e40458f7357f5a3022f1d8b0c9a409641cd89ff0` |
| `mandate/raw/census.stdout` | `7c2b71fb309244a7fed3767df3e145b309d35eff2ccb6ecc45a63cef6f99448c` |
| `mandate/raw/active-alias-candidates.json` | `7dadc2f382f61800fa15bbfb7c38631c571c6ec061b44ed76ba3299d15df125c` |
| `mandate/raw/registration-projection.stdout` | `40629660b501240bed2f3ae30e3dc2a4edd5ecc634eabb4d4a2a6738cd5bc358` |
| `mandate/raw/semantic-witnesses.command.txt` | `999dbde7fd499b992185c89f4b7467ca941b57229fbd1ff78c929b44fc3fd699` |
| `mandate/raw/semantic-witnesses.stdout` | `c4b808d34f4db00b333696dec1f3a43a2887d8bfe0cb7af07a3cb98ff43a7830` |
| `positive/raw/census-complete.json` | `db7d41eb36f01cba4b67a3982bd11ea07c716efb4b2b12888086b9ab9ae94a77` |
| `positive/raw/census-summary.json` | `0957164745b70f44ccef8bb989b7106d9533142b24782ff03d995fa1a6f1465f` |
| `positive/raw/selected-caller-records.json` | `b4ecfddbc105d45289394429fe302b3cb602f23b8e41fc27bc95314e57907572` |
| `positive/raw/focused-tests.log` | `9a79a0c53124a53831db08cff90766749aa66da754140976882a5e2b17e854c2` |
| `positive/raw/port-probe.json` | `f176a72cb2a78fedc0f2f9ea1f015fdd881e30398e961c6e107671ef94572408` |
| `positive/raw/port-removal.log` | `a96d891a40f82d558022d4b078d5cb304736a91fc92ebf924daf59e51e620b1c` |
| `outliers/raw/census.json` | `b6546bb567727937866a5bc0b43e2348c10e82c900238af19d9f5745e93fc39b` |
| `outliers/raw/cost-schedule-comparison.json` | `afdbe4c95cbab1ab835cd9c304fbd82b1195b9bcbb4d6be2b7f3ea456641d681` |
| `outliers/raw/cost-schedule-probe-output.txt` | `86da7d0525f54330ab3aa5df28d315ef5221683c7c979b86b3a8488ae60e38c6` |
| `outliers/raw/retained-education-receipt-readback.json` | `fa00c186a7a7e75f53c35b6e5b6c430674850b1c0aea24398b2f8a6ce591769e` |
| `outliers/raw/education-current.json` | `7e20d11b7ac10023e502f77cd07cba0864346b39cb736a2f7aa25b223c23e02d` |
| `outliers/raw/numeric-semantic-tests-nonreceipt.json` | `254398b42dead48e474968ef976569713798ffe6b5f65443f58e9c9a85d0d42d` |

### Ledger result

The ledger command completed with its own process exit **0**. It was the only
command in its invocation:

```sh
PYTHONPATH=src:tests:. .venv/bin/python tools/quality/validation/check_debt_ledger.py --check
```

Complete deciding output: `raw/ledger-check.log` @ SHA-256
`3510f2ab1cc661c567b85cc8967b037974b30bd4fbcb92c34da544c8edc7fee3`.
This is the owner's bounded ledger verdict, including its explicit unresolved
imports/Git/subprocess, document-selection and ownership-act boundaries. Its
nonblocking informational findings remain in the complete receipt; they are not
promoted into passed runtime tests or completed debt rows.

Destinations for those incidental diagnostics: unresolved DS11 selectors to their
existing DS11 row owners; unsupported `ds10-lex-pipeline-mutation-boundary`
selection to its existing DS10 owner; register column recovery and GY standing
projection diagnostics to team-architecture's existing ledger/instrument-honesty
work. `GY-GAP6`'s ambiguous source standing remains part of this lane's separate
admission finding. No new register row or ledger regeneration was performed.

### Research instrument acceptance and correction

The final review found a **new research-witness integrity class**, with deeper
instances across output modes and error paths: incomplete stdout receipts,
unreadable input without an explicit partial verdict, and a registration-loss
conclusion that could survive removal of its deciding row. These are defects in
this lane's research harnesses. Their destination is these journal instruments
and retained acceptance evidence, not a new register entry or a runtime repair.
Historical successful censuses remain pinned observations; they are not certified
as satisfying the instrument contract in every hypothetical input state.

The root census now records its actual Git operations, explicit selectors and
unselected-document boundary. Its observed register-row total is derived from
the parsed occurrences, so a missing row cannot retain the declared count.
The actual caller was exercised on selected evidence, evidence only outside the
selector, malformed UTF-8, changed case, a missing selected source, a missing
commissioned row and an unreadable register. Selected incomplete inputs return
2/`UNRUN_partial_coverage`; outside evidence retains a named undecided boundary.
Removing AST enumeration in memory while retaining receipt fields makes the
unchanged presence witness fail; restoring it makes that witness pass.

The acceptance process exited **0** and retained all per-case caller outputs in
`raw/root-instrument-acceptance-v2/`; their full hashes are in its result receipt.
The original complete root census was rerun with exit **0**, with the same
5,704 selected Python-file denominator and independent index/tree/filesystem
reconciliation. This validates bounded research behavior, not runtime authority.

| Final root receipt | SHA-256 |
| --- | --- |
| `raw/root-instrument-acceptance-v2.py` (exact scratch harness) | `c01cf8096d7eff81edaf45960ea8b841ad1ad5d294206c848d8e5e24d50fa324` |
| `raw/root-instrument-acceptance-v2-result.json` | `2df93d4d7ef911acf032f533b35f06615a1934ed53552acaecbf6945a7fa74a9` |
| `raw/stage1-census-final-v2.json` | `a552c3abd9481776cc3df3a5d1847b56b0085841944f17cf8f1b6e7dfe692549` |
| `raw/final-partition-reconciliation.json` | `6bb07c21c663dbaf313736a941bdc62e4777614810a58fc932ecb2bfc042e8e4` |

The final independent mandate delta review found no blocking finding. It bucketed
the R4 clarification as the same registration/projection class and confirmed that
the proposed stop follows the commission's explicit Stage 1 split rule, without
making institutional absence block buildable mechanisms.

The root research-script Ruff invocation using this lane's Python exited 1 because
the reused module could not find a local Ruff executable. Repeating it with the
existing integration station's Python ran the actual checker and exited **1**:
line length/import/context-manager style, plus generic warnings for the required
JSON stdout, fixed-argument Git subprocess and this executable witness's asserts.
This is not a lint pass. The post-freeze cosmetic findings are recorded here under
the lane's research-harness maintenance destination, following the instruction to
record cosmetic findings after a frozen wave rather than reprice that wave.
The Git inputs are constructed in the script, and the recorded invocation does
not use Python optimization. No runtime source is involved.

Exact checker arguments: `-m ruff check
docs/superpowers/journals/acquisition-movement/probe_stage1.py
docs/superpowers/journals/acquisition-movement/refusal_wave.py`.
Complete initial nonreceipt: `raw/root-research-ruff.log` @ SHA-256
`5ba57848d1edd5b269a6d8fd0a44859842aff5ecdd6f579cd430f14496427086`.
Complete actual Ruff output: `raw/root-research-ruff-station.log` @ SHA-256
`1f70e594d9bc1991eb3c1e5c9b45e9906a4f8eb6133f1e15c0712a22af96731e`.

The companion instrument acceptance processes also exited **0** after their
repairs. Their complete receipts enumerate the actual cases and bind per-case
stdout/stderr. They exercise real callers against selected/outside, unreadable,
changed and absent evidence. Removing the decisive GY row leaves the projection
claim false; removing a source call leaves no fabricated call despite retained
tokens; the original malformed-input and denominator failures remain reachable.
No institutional or production-growth claim follows from these scratch fixtures.

| Companion acceptance receipt | SHA-256 |
| --- | --- |
| `mandate/raw/instrument_acceptance.py` | `a9020037a03bbcc33d9dc08bb8e7e2463ef417c1a4713c5980f20f1b10a20d13` |
| `mandate/raw/acceptance-legacy.stdout` (pre-repair falsifiers) | `ef412181dfaeb852f6da093cc12ab07a3af1cd75897c64c6868fc6967095d180` |
| `mandate/raw/acceptance-final.stdout` | `31cce8b68944e46572b2960b8c32cede5ccb8ffe806c0247103c80bff3ef27da` |
| `mandate/raw/registration-projection-corrected.stdout` | `5163921bd7703b793e371503cac58d883cfcf1dab4cf73fc16fd1da33195cc9e` |
| `positive/raw/acceptance_harness.py` | `07c427cf4564ecab52405079115edea8c5f8dc293116a74fc4662c39841ec548` |
| `positive/raw/acceptance-before-substantive.log` | `7528fc98deb6396b65d2c6b51cbd47e60e34e6a5936bcf26f4fe1e950d04768f` |
| `positive/raw/acceptance-final.log` | `73bf3fe25102c9a53c30f01c241901b5fb02c8545faa197774d7dae1ad8101e1` |
| `positive/raw/acceptance-final/removal-assertion-red.log` | `b731cef66c5513d23c17d3e27794d5e6f971af73d0ad26bd92a77cd0f8b24a5b` |
| `outliers/raw/instrument_acceptance.py` | `48b324e8bb178b26c49ddc33cf98303ab64486f2c56efaf5b1d6df917db62c1c` |
| `outliers/raw/instrument-acceptance-before.json` | `7dda538eca32938e3de9f1e7881be7ca3258e521915bfc527280a2fa5c62fea8` |
| `outliers/raw/instrument-acceptance-after-final.json` | `f2ece41dd378173ae65be77e8346ebb54fa05f97b0329178171e022df25352c0` |
| `outliers/raw/cost-schedule-final.stdout.json` | `151c358bf9ffcfc4f45436ead89d0e7a7e89a767df2b0a787d9d6671aa439148` |

The frozen companion scripts passed their targeted Ruff checks through the reused
integration interpreter: `mandate/raw/instrument-ruff-pass.stdout`,
`positive/raw/census-ruff-final.log`, and `outliers/raw/ruff-research-final.txt`
each have SHA-256
`82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`.
This does not subsume the separately recorded root-script lint result.

The corrected original-input replays completed successfully; their full read
receipts carry their actual selectors and pinned content. The acquisition
production-source denominator is unchanged. The mandate all-product census now
also sees this lane's already committed research files; its corpus is explicitly
the current tracked set, not falsely reported as the original base's set.

| Final original-input replay | SHA-256 |
| --- | --- |
| `mandate/raw/census-corrected.json` | `3926ada3f35bf218e826f11ae67d1829ed2eb0ddac7c26c09e63ee22212d76ed` |
| `positive/raw/census-disclosure-final.stdout` | `6af8fe431ed69ab02101bd2deb1c88b499c86e59c37b8e6c4ff060c53006bc52` |
| `outliers/raw/census-final.stdout.json` | `61dcc3b37ca4b6aff1943196f31e21efbdcfa1ad1c14b84c96d3d22f2604014e` |

After the research-script freeze, the structural architecture command above was
run again as the only command in its invocation. Its own process exited **0**.
Complete output: `raw/architecture-structural-final.log` @ SHA-256
`bec5670b67034187ca56d3654b1891d7bae72736d0ba6c6a5bfccb7840b805bd`.
Generated freshness remains explicitly outside that scoped verdict.

## Delivery disposition

`complete-pending-an-architect-decision on the 8+1+1 subject partition and the
active mandate-intake allocation`.

This closes the commissioned Stage 1 research and its evidence handling, not the
underlying acquisition debt rows. The concrete next decision and buildable links
are in `STAGE1.md` AM-R05. The split is the commission's explicit architectural
stop; missing institutional appointments are not engineering stop conditions.
No production source/test, register, ledger or canonical OpenAPI edit is delivered.
No push or guardrails sync was performed. The full freshness and root-script lint
limitations above remain visible; neither is labelled an inherited product red.
