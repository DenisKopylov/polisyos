# Uninvoked mechanisms completion journal

Lane base: `c49449343cbaa8dfeba9d0c7afd3de67355205a3`. Source delivery:
`1d7562c072249998d5f6a63f65374639a2384762` on `codex/uninvoked-plane`, in
`/Users/deniskopylov/polisyos/.worktrees/uninvoked`. Work is local; nothing was pushed.

The decision/source order is part of the evidence: `a8617020d` committed the
three research/architecture decisions, execution plan, complete census instrument
and raw-output ignore rule with **zero source/test delta**. `f3403d771` added the
DS15/DS18 routes; `1d7562c07` added the standing checker and caller-before-code
rule. All were reread from the attached branch. This journal adds no source.

## Five outcomes

| Row | Outcome | Production terminus or named caller task |
| --- | --- | --- |
| `ds18-epoch-history-independent-holder-unappointed` | **wired**, bounded provider-invocation audit | `python -m polisyos.runtime.quality.epoch_custody_audit --request REQUEST --cas-root CAS` → `main` → `audit_epoch_custody` → existing production factory → `evaluate_acceptance_and_custody` → exact request/result CAS readback → printed audit ref. Both institutional roles remain `not_established`. |
| `ds15-signed-v2-delegation-mandate-owner-authority` | **deferred-with-a-name: DS15-MANDATE-INTAKE** | `team-runtime` must build purpose-specific institutional evidence intake/selection and extend the governed deployment bundle/factory to install `ProductionAcquisitionAuthorityProvider`. Its required terminus is the existing served acquisition decision-request/execute routes plus job replay. No present production terminus invokes this gateway. |
| `ds15-semantic-epoch-qualification-authority` | **wired**, durable negative acquisition admission | `python -m polisyos.runtime.quality.acquisition_epoch_admission --request REQUEST` → `main` → `run_admission` → existing `admit_acquisition_with_production_semantic_epoch` → existing persisted owner receipt → exact CAS statement readback → JSON output. `policy_admission_missing` remains the result. |
| `gy-verifier-built-but-not-consulted-at-the-admission-seam` | **wired**, standing bounded recurrence instrument; existing repairs preserved | `python -m polisyos.runtime.quality.production_invocation --base BASE --receipt PATH` → `main` → `audit_repository` → `audit_sources` → full static graph assessment → persisted/read-back diagnostic receipt. New and lost call paths are derived from source, not these five names. Existing repaired seams and their termini are detailed below. |
| `gy-builder-mechanisms-have-no-production-caller` | **deferred-with-a-name: GY-CB2 and GY-ML2** | **GY-CB2 — real operator study intake**, `runtime/quality`, builds `operator_study_intake` and its study entry point after real operators, W5-R3-Q06 adjudication and GY-AS2/GY-AS3 inputs exist. **GY-ML2 — appointed Lex assurance intake**, `lex / scholar`, builds `multilingual_assurance_intake` and its Lex admission entry point after independently admitted trust roots/key custody and W5-R6-Q05 reconciliation. Current production terminus for either remaining producer: **none**. |

The named deferred tasks are concrete charters in the committed decisions, not
claims that institutional owners have accepted appointments or that work is
scheduled elsewhere. The remaining gateway/instruments are
`implemented_but_not_orchestrated`; their caller/intake and institutional chain
remain `producer_missing` / `absent/unallocated` as specified in the decisions.
A test importer is not counted as a caller.

## Discrepancies, kept separate from closure

- **U15-F01:** task Q audited `AgentActionAuthorityGateway`. The question's
  `AcquisitionAuthorityGateway` and `HumanDecisionProductionGateway` are not
  classes in the measured source tree. The similarly named Provider protocol
  and AdapterInput DTO are different symbols. Real/RecordedAcquisitionOwnerGateway
  perform data acquisition; they cannot substitute for signed mandate authority.
- **U15-F02:** the actual signed-action gateway still had a definition/import
  and no construction call in source. Its missing provider is a real remaining gap.
- **U15-F03:** the semantic-epoch record became partially stale. Three source
  call sites now invoke `qualify_chronology_query`, including the served temporal
  composition, but the full **persisted acquisition** producer still had no
  source caller. The new CLI closes that separate seam; it does not reopen the
  correct temporal refusal.
- **U15-F06:** research initially proposed the existing container override as a
  future production route. Further source inspection found that non-development
  `create_runtime_api_app` explicitly rejects direct overrides. The committed
  correction requires governed deployment composition, not an alternate factory
  bypass. This is engineering work as well as institutional provisioning.
- **UNINVOKED-DS18-01/02:** the holder record's absence of evaluation/persistence
  still held. The container already constructed the provider, so “provider
  missing” would have been wrong; construction did not call its evaluation method.
- **UNINVOKED-GY-01/02:** the two GY rows are not September 1 observations. The
  current verifier row names September 8 measurements and September 9 repairs;
  the builder row opened/changed September 10. The verifier row's five original
  seams are now repaired in source. Its remaining demand was a standing check,
  not five further repairs to closed source.
- **UNINVOKED-GY-04:** the builder row's three repaired source modules have real
  consumers; the two institutional producers still have none. `locale_census`
  has a runnable tooling caller and no `src/` import. That structural parser
  does not supply multilingual institutional assurance.

Decision sources (including each finding's owner-code anchors):
[DS15](../../specs/2026-09-10-uninvoked-ds15.md),
[DS18](../../specs/2026-09-10-uninvoked-ds18.md),
[GY](../../specs/2026-09-10-uninvoked-gy.md), and
[execution plan](../../plans/2026-09-10-uninvoked.md).

## Complete census and independent checks

The path/file-type denominator is **every tracked `policy-engine/src/**/*.py`**;
tests and tooling are excluded from these counts. [census.py](census.py) retains
all definition/import/call records in each `complete.json`, rather than a target
sample. `summary.json` is the bounded target projection. Complete raw outputs
are linked in the receipt table below and remain local/gitignored.

| Measurement | Base | Delivered source |
| --- | ---: | ---: |
| Tracked Python source files | 2,651 | 2,654 |
| Class definitions | 9,932 | 9,935 |
| Function/method definitions | 36,994 | 37,014 |
| Import statements | 25,445 | 25,481 |
| All AST call expressions | 366,926 | 367,214 |
| AST name/attribute call subset | 366,795 | 367,083 |
| Independent token-derived same subset | 366,795 | 367,083 |

Both observations have zero parse failures and zero cross-check disagreements.
Independent `git ls-files` and `git ls-tree` traversals reconcile exact path
identities. The second syntactic instrument is token grammar, not another AST
walk. It excludes definitions and respects statement boundaries. The 131 calls
outside its name/attribute intersection remain in the full AST census; they are
not silently omitted from the total. A further complete `git cat-file --batch`
check verifies every captured source SHA-256 against its pinned Git blob at
both revisions (`pinned-source-check.log`).

| Symbol | Base definitions | Base imports | Base calls | Delivered calls |
| --- | ---: | ---: | ---: | ---: |
| `AcquisitionAuthorityGateway` | 0 | 0 | 0 | 0 |
| `HumanDecisionProductionGateway` | 0 | 0 | 0 | 0 |
| `AgentActionAuthorityGateway` | 1 | 1 | 0 | 0 |
| `RealAcquisitionOwnerGateway` | 1 | 1 | 1 | 1 |
| `RecordedAcquisitionOwnerGateway` | 1 | 0 | 1 | 1 |
| `build_production_epoch_anchor_custody_provider` | 1 | 1 | 1 | 2 |
| `evaluate_acceptance_and_custody` | 2 | 0 | 0 | 1 |
| `admit_acquisition_with_production_semantic_epoch` | 1 | 0 | 0 | 1 |
| `qualify_chronology_query` | 1 | 0 | 3 | 3 |
| `run_instrument` | 1 | 0 | 0 | 0 |
| `run_assurance` | 1 | 0 | 0 | 0 |

Definition and import sites never count as constructions. The two evaluation
method definitions are the protocol and implementation. Alias expansion in the
research census is only a navigation hint; runtime evidence below establishes
the two new production invocations.

The standing graph instrument has a different, explicitly larger denominator:
**5,666 tracked current Python files across `src/`, `tools/`, and
`tests/`, versus 5,660 at base**, including 2,654 current source files. Its final
receipt reports zero new or regressed unresolved source-call paths.

Its `static_path` status never means `wired`. Its `uninvoked` diagnostic means
no root path resolved under this static model; it is not a factual declaration
that every historically unresolved callback or method is unused. Reflection,
callbacks, receiver types and conditional aliases require separate tracing;
HTTP decorators are not automatically treated as registered served roots.
Real-run receipt custody and gate substance remain behavioral requirements.
The new rule is recorded under existing P01/P02 maintenance guidance in
`docs/reference/policy-design-case-failure-patterns.md`.

## Load-bearing invocation and durable receipts

- **DS18:** removing only the new `evaluate_acceptance_and_custody` call made
  unchanged `test_cli_persists_both_unappointed_roles` fail with
  `custody_provider_result_missing_or_invalid`; no completed output survived.
  Exact source restoration and unchanged test hash are recorded. A direct CLI
  run outside pytest persisted receipt
  `sha256:20478a3e3407ca9d715cd5ecc1149c6e5481d7e5ecba94b25bc00bbe8c9b947a`
  in `ds18/raw/operational-cas`. It preserves the exact candidate request and
  separate acceptance/holder negatives, with invocation-only authority.
- **DS15:** removing only the new full-producer call made unchanged
  `test_cli_consumes_actual_persisted_policy_refusal` fail (exit 2 instead of
  typed-negative exit 1). The source was restored byte-for-byte and the same
  negative passed. Direct CLI receipt
  `sha256:511a63ac7af434ad6628184bb343f7b0006e3c3a498c0ac18773d038f12b6429`
  remains in `ds15/raw/operational/`. Independent readback checked frame length,
  raw hash, manifest identity/kind/media type, whole statement equality,
  semantic hash and finalization refs; no history append was invented.
- **Standing checker:** removing only `audit_repository`'s call to
  `audit_sources`, while retaining normal output markers and denominator
  emission, produced a false green. The unchanged
  `test_cli_reports_test_only_verifier_and_persists_negative` rejected it
  (`0 != 1`). Exact restoration and unchanged test hash are recorded. Later
  test extensions add actual CLI `--check` recomputation and corrupted-source-
  denominator rejection; they preserve the negative assertions used by removal.
  The full final diagnostic receipt is `census/raw/invocation-final.json`.

All operational inputs used for these demonstrations are explicitly isolated
synthetic candidates. Persistence establishes what the existing owners actually
returned. It establishes neither an appointment nor whole-history authenticity.

The original GY repairs retain their real termini: C1/C3/S3 pass through
`WorkspaceLoop` and `ControlPlaneWorkspaceLoopTransitionMixin`, reached from
`control.launch_run` / `POST /api/v1/control/runs` through `launch_workflow_run`.
K's extractor is invoked by the accuracy instrument consumed by
`tools.quality.validation.check_layer3_gy_openalex_artifacts`'s module CLI.
L's post-output GX verifier is invoked by the loop artifact checker CLI before
outcome admission. Six selected cases across those five seams passed, including
actual extractor removal and post-output-GX removal with pass markers retained.
Their closed source was not edited.

The already repaired builder chains remain separate: canonical Fabric non-data
acquisition and ceiling relations feed `fabric.evidence.acquisition_assurance`
and its runnable `check_gy_acquisition_assurance` checker. Adaptation state feeds
`constrained_response` / `vocabulary_crosswalk`, then `response_corpus_evaluator`
and `tools.check_response_corpus` or the canonical crosswalk checker.
`locale_census` terminates at `check_multilingual_locale_census`. None supplies
the absent operator-study or Lex trust-root consumer.

## Verification, review and boundaries

| Targeted gate | Result | Measured wall time |
| --- | --- | ---: |
| DS15 new CLI file + original authority-composition node | 7 passed | 141.54 s |
| DS15 unchanged negative after exact restoration | 1 passed | 91.71 s |
| DS18 new CLI file + two existing provider/constructor checks | 9 passed | 181.72 s |
| Generic invocation checker file, including `--check` and corrupt receipt | 9 passed | 97.31 s |
| Selected C1/C3/S3/K/L behavioral nodes | 6 passed | 570.61 s |
| Ruff, exact three source/test pairs | passed | bounded local checks |
| Architecture `guardrails check --skip-generated-checks` | passed | generated checks explicitly not run |

Commands used `.venv/bin/python -m pytest -o addopts=` with only the named files
or selected nodes, never a directory suite. No backend-wide or CI-parity suite
was run. Each gate was a separate command. For repeat runs, retain an outer
600 s allowance for the CLI/checker test groups and 1,200 s for the selected GY
seam group; individual tested CLI subprocesses already use explicit 180 s caps.

Review bucket: two witnesses were the same declaration/walk-coverage class
(`__main__` lexical scope and a `match` statement container). Before separate
instance repairs, registration was widened to generic AST-child traversal and
bound to AST node identity. The unchanged witnesses pass and independent
re-review accepted this class closure within the declared static limits. The
initial full checker run was cancelled after that review invalidated its loaded
code; it supplies no green or inherited-red claim. Its per-file Git reads were
also replaced with one complete batch before the deciding rerun.

Harness non-receipts were corrected before using semantic results: offline
`uv sync` lacked cached jaxlib, so an isolation-local Python 3.14 venv reads
already installed dependencies with this worktree's `src` first; a local Ruff
executable link supplies its expected scripts path. Read-only production data
was linked for the original regression, while new operational fixtures are
isolated. `corepack pnpm install --frozen-lockfile` supplied the ordinary Git
hook runtime before the first successful commit. Missing module/fixture/tool
setup failures are retained separately from deciding behavior.

**Excluded signer:** `ds18-epoch-predicate-policy-signer-unappointed` is unchanged.
The served temporal query still reaches the existing unallocated-policy
composition and returns the correct `policy_admission_missing`.

**Blocked positive transition:** this lane changes **none** of what blocks
`ds18-positive-transition-production-unorchestrated`. It adds no pre-N9 trigger,
complete dependency denominator provider, perturbation adjudication provider,
purpose-scoped signer/appointment, or production denominator-reconciliation
reader/verifier provenance. An audited negative is not a positive transition.

The actual `confidence_ledger._deployment_relative_paths` owner derived all
98 deployment inputs; their intersection with the lane's changed Python paths
is empty. No governed architecture/schema artifact, DEBT-REGISTER or LEDGER was
changed. Existing Python source has zero delta: only the three new modules
were added. No governed epoch bump or artifact reissue occurred.

## Complete local evidence receipts

Paths below are relative to this journal. SHA-256 identifies the entire file.
Raw directories were gitignored in the first commit. Large AST records and
operational CAS data stay on this machine, not in Git; the pinned source and
instrument allow reproduction. No duplicate source dumps are committed.

| Complete output | SHA-256 |
| --- | --- |
| [census/raw/base/summary.json](census/raw/base/summary.json) | `63188b12d35b5ccd9ce1165b0fb0f4182d2d59e9e5e1f73916786356bfec99f6` |
| [census/raw/base/complete.json](census/raw/base/complete.json) | `84dbee40336bb57772773ebfd3394dac6611c6bb9ed8512bda9b159a75112178` |
| [census/raw/final/summary.json](census/raw/final/summary.json) | `8633ab7dd84724b354aa96aed09f153e61510182f566f293609f2e05522f94db` |
| [census/raw/final/complete.json](census/raw/final/complete.json) | `6d1cdf682fbdbcbc88d0ea753c57358ce090d0426ec6e24a252511fddb7caf60` |
| [census/raw/pinned-source-check.log](census/raw/pinned-source-check.log) | `d138cbb002ef7e7eb0d602fac01fc3518b4afff08ebbcd8494a6422e625d6b66` |
| [census/raw/invocation-final.json](census/raw/invocation-final.json) | `4a97414341d4b73999b8bb7aa4742622eb0dcfe08f38cddd1259a2ed906289ad` |
| [census/raw/final-tests.log](census/raw/final-tests.log) | `35bf9565c3305df1c586e3408a30199590df4eb78e63562ed8c7511d89079f7d` |
| [census/raw/removal.log](census/raw/removal.log) | `e21639e350c512494c2181cc4154e356e56a3f35f72bbdda3b0e35fc3dfef6fd` |
| [census/raw/removal-state.json](census/raw/removal-state.json) | `59d3ac85d5af3b2cf2cf2ea744a366fdd9418daaab4f4bb9c56b875b7f3ca3bc` |
| [census/raw/review-scope-red.log](census/raw/review-scope-red.log) | `f18f153da306d5f3371edf50dd0a8164f2f10364fb987e2aaad6c872160338da` |
| [census/raw/review-scope-green.log](census/raw/review-scope-green.log) | `59116637d28661aae5fa024b0e14724c17c622760410e07773a5267121ada6f7` |
| [census/raw/gy-existing-seams.log](census/raw/gy-existing-seams.log) | `11fa8f8455cb13dcff43d4e570c2a51cc927f8cdecb8f6d0ce30c88280ea1183` |
| [census/raw/architecture.log](census/raw/architecture.log) | `a00bf171f39187ce0d77359dd678a7c7f3d219354dac7488f61087f1fc40f5fb` |
| [census/raw/governed-deployment-intersection.json](census/raw/governed-deployment-intersection.json) | `11e5313f485580387d509815fa800bfdfed40d0ced52bd278d996a1f5b6f0580` |
| [census/raw/ruff.log](census/raw/ruff.log) | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| [ds15/raw/red.txt](ds15/raw/red.txt) | `78b20d1f74179dad8ed7422d9e2bc2e823ca2edf9af83144e3a7f36bf80769df` |
| [ds15/raw/green-first.txt](ds15/raw/green-first.txt) | `9129b129201729113b30a58629aac29d183aa6d4301a82c7ac4924935619d96f` |
| [ds15/raw/green-restored.txt](ds15/raw/green-restored.txt) | `a613129661f2631c2824cfadb2638efe79008f3e2bd149b5d96e22d69ee3fa39` |
| [ds15/raw/removal.txt](ds15/raw/removal.txt) | `18a65bee13b0314659b80b3214a5329938bad430b5853717cf44bd4aa5bbe4d7` |
| [ds15/raw/removal-transition.json](ds15/raw/removal-transition.json) | `18d02806f68d3f237dbcbd4ca5f538612cd0aa47f0d9eb1f81d6ca1568f3a102` |
| [ds15/raw/operational/receipt.json](ds15/raw/operational/receipt.json) | `ffff32a6cb7327b951c4abf3cb13968329dcaea7f0c172084979acc2cd3fbdc2` |
| [ds15/raw/operational/readback.json](ds15/raw/operational/readback.json) | `e1ca4de95be6e2352bb618587b4fb85c09c610a22a6e9ad3ba4a1bbf5326564b` |
| [ds15/raw/ruff-final.txt](ds15/raw/ruff-final.txt) | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| [ds18/raw/targeted-final.log](ds18/raw/targeted-final.log) | `2f7a27abdbca07e42a359bd351ec8f4c469ffb479032be24b159aec2f41c2f7f` |
| [ds18/raw/removal-call.log](ds18/raw/removal-call.log) | `57681303890f5928a7adbfe55e6c86eeada75fc5394a6a06b2f72048bb9106fe` |
| [ds18/raw/removal-state.json](ds18/raw/removal-state.json) | `3fdc22c601e165c9f8f6c7c900fa9601789b5298607a161cc779ac8996306191` |
| [ds18/raw/operational-run.log](ds18/raw/operational-run.log) | `2fa46a6f0d32e70a30621c320a03a84fa6bc030ddbdc603b1f865e8d9b7e5459` |
| [ds18/raw/ruff-final.log](ds18/raw/ruff-final.log) | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
