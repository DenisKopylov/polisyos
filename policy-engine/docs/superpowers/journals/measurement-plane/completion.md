# Measurement plane completion journal

Status: Stage 1 decisions and complete population recorded; Stage 2 begins after this commit readback.

Lane: `codex/measurement-plane`, base `307dabcb4`. Local ordinary git; no push,
prune, guardrails sync, register or ledger edits. Root serializes git and the
four shared instruments. Row 1 surveys alone; then rows 2+3 and 4+5 may overlap.

Name admission: `git worktree list | grep measurement-plane` exited 1 with no
output; `git rev-parse --verify codex/measurement-plane` exited 128 (`fatal:
Needed a single revision`). Target path did not exist. The requested
`git worktree add /Users/deniskopylov/polisyos/.worktrees/measurement-plane -b
codex/measurement-plane 307dabcb4` completed; `git status -sb` read back
`## codex/measurement-plane` with a clean tree.

Evidence policy: complete deciding output and removal probes retained; large
outputs in gitignored `**/raw/`, cited by path and SHA-256. Tracked inputs are
cited as path@commit. Search predicates must expose their counterexample and
run case-insensitively. ASTs establish definitions and calls. Every set-level
count names its full path/file-type denominator and independent cross-check.
Unreadable members remain ambiguous.

## Baseline receipts

The first guardrail invocation failed because root wrote the Row 1 decision while
its output-footprint probe was active. This is root's scheduling error, not
inherited product debt. The frozen rerun passed with zero findings (420.41 s).
Serialize the repository filesystem snapshot for later guardrails: no tracked
writes during its run. Both invocations preserved their complete output.

The ledger generated-artifact check passed with `register_ids=260`, no blocking
findings, and exactly two `register_status_column_shifted` informational findings:
`extraction-ask-offers-six-of-ten-evidence-classes` and the retained pipe-regression
row. Its full run took 1029.57 s. This receipt is a check result, not evidence
about the source tree from the register or ledger prose.

The invocation baseline passed through `uv run python -m pytest -q
tests/unit/runtime/quality/test_production_invocation.py` (19 collected items,
10.02 s). Bare `uv run pytest` had used `/opt/homebrew/bin/pytest` because the
cloned installed packages lacked the console script; that distinct environment
failed the CLI import test. Use the isolation-local module launcher.
Atlas scope baseline: `uv run python -m pytest -q
architecture/atlas_surfaces/test_atlas_enforcement.py -k scope_obligations`,
5 selected items passed (3.63 s).

Environment: `corepack pnpm install --frozen-lockfile` completed. Offline uv cache
missed compiled wheels, so installed packages were copied by APFS clone from the
local root environment, then the worktree was reconciled with
`uv sync --offline --frozen --no-build-isolation --extra lint --extra test
--extra runtime`. Missing build tools were installed in the isolated environment
only; no manifest/lock changed. `tools` and `polisyos` resolve inside this lane.

Complete outputs (SHA-256; raw paths are intentionally gitignored):

- `docs/superpowers/journals/measurement-plane/baseline/raw/atlas-scope-tests.log@813f2fe8a693a17133d234e599e457872dfc6e8b16e6b4f1c60232fd53b34773`
- `docs/superpowers/journals/measurement-plane/baseline/raw/debt-ledger.log@653c081aa81153812a2faa4e5aead674f4c36be701a63f60c33bb622b6f650e3`
- `docs/superpowers/journals/measurement-plane/baseline/raw/guardrails-frozen.log@04f48c422c506201260004cd8f2267975ae5593baac6ff22e2c832e561e57fec`
- `docs/superpowers/journals/measurement-plane/baseline/raw/guardrails.log@bfad605a96c50a7439e3271dedaf306acb4975b14c0b3cc715be46309e2df178`
- `docs/superpowers/journals/measurement-plane/baseline/raw/production-invocation-module-tests.log@cbf54da1fbbd65626318b61caad2a79d7f05fc019a52f2a4bfb72a9d206ae497`
- `docs/superpowers/journals/measurement-plane/baseline/raw/production-invocation-tests.log@d144c9df99e563f586fb30b8f2a3cace1ac68b3b1765a1ffe1b969eb9dde27be`

## Stage 1 findings retained during research

Row 1 source denominator and provisional role inventory are committed in
`docs/superpowers/journals/measurement-plane/row1/survey.md@42c09a7a4`.
The 270 candidate labels are not an admitted instrument total. Per-source
semantic adjudication and input-disclosure review remain in progress before repair.
Decision readback: `docs/superpowers/specs/2026-09-12-measurement-instrument-boundaries.md@0dedbe49f`.

The Atlas admission probe read 132/132 tracked Markdown plans, independently
reconciled against `git ls-tree` at the slice base. Results: 24 slice plans,
103 excluded documents, 5 invalid YAML inputs. The deciding output is
`docs/superpowers/journals/measurement-plane/row1/raw/atlas-plan-admission-baseline.json@796f90c67ccaa9e37e7624feb726c93a635d4ca210c678546edeebe6c8a18539`.
This is a bounded parse result, never an allocation verdict. The five invalid
inputs must remain named unresolved records rather than silently disappear.

Incidental destinations (open until final reconciliation):

- **MP-B1 — team-devx / team-architecture research backlog:** complete the per-emitter
  population classification and route historical disclosure migration. Candidate
  strings cannot establish compliance. The classification part is active in this lane.
- **MP-B2 — explicit nowhere:** two same-named conditional nested definitions in
  `tools/quality/validation/gy_acquisition_assurance_oracle.py@307dabcb4` are only a
  syntactic duplicate candidate; no overwriting defect has been established.
- **MP-B3 — team-architecture / plan document owners:** repair the five malformed
  frontmatter inputs admitted by the Atlas parse probe before requesting complete
  plan-selection coverage. This lane reports partial coverage; prohibited document
  edits are not smuggled into the instrument repair.


## Stage transition

The five decisions were committed together by `e6ffe219b` and all five full files
were read back through attached `codex/measurement-plane`. Row2's generated-artifact
constraint was appended in `5f8bc7485` and read back. Source remained unchanged
through the complete instrument review. Final population: 319 owners / 498 source
files / 1,269 tracked tools+architecture files; 16 bounded-mode input disclosures,
290 partial, 13 none; 317 survey-found owners. The 270-candidate result is superseded.
MP-B1's census work is complete; historical output-mode migration remains with
team-devx and each listed source owner under the standing author/review rule.

The broader ledger test file produced 8 failures over 71 AST test definitions
(0 async), elapsed 587.20 s; complete output:
`docs/superpowers/journals/measurement-plane/baseline/raw/debt-ledger-unit-tests.log@5936553f0ac4cef89ea4409ca648af7f4095b545f96a8622363b3bbd7b57fe71`.
An exact-command replay is running at the original slice base in the isolated
local clone `baseline/raw/base-ledger-replay`; it adds no worktree registration.
No inherited-red exclusion is claimed before its result and input-intersection review.

Additional destinations: **MP-B4**, Foundry calibration model owner, explicit
schema_version `1.0` rejected by the current escaped regex while the unvalidated
default accepts it (MP3-02). **MP-B5**, DevX ledger test owner, stale return-arity
and historical live-state assertions, pending the exact-base replay. **MP-B2** is
resolved to explicit nowhere: AST guards put the two nested `action` definitions
in mutually exclusive decoder / non-decoder branches; this is not an overwrite.

## Stage 2 working receipt

Stage 1 was admitted at `2bd011568e393823cffdbba0e27a80884a6adfe9`; all five
files and the complete source census were read back from the attached branch
before source edits. Red measurement tests were preserved in `d6cea8caa`.
The ledger read/unreadable/original-missing-row tests passed 3/3; the Atlas
scope and disclosure selection passed 10/10. The two pipe regressions failed
before the format change, then passed with three measurement/absence checks
(5/5). Updated historical companion assertions passed their focused 8/8 run.

The original-base local clone reproduced the same eight ledger test failures;
it additionally failed generated rendering because its local ref namespace
lacks this repository's branch refs. That ninth failure is a control-environment
limitation, not inherited product debt. No disjoint-input exclusion is claimed:
this lane changes the ledger instrument and repairs stale test companions.
The source unchanged by the task still supplies the mutable census; expectations
now pin 260 register IDs and the measured current selector set. The historical
subject-scope regression is expressed with synthetic source rows, preserving
sibling-evidence rejection after the original live row closed.

**Row 2 generated-artifact constraint is now established, not hypothetical.**
The tokenized owner projection changes exactly two owner cells in the generated
ledger (`extraction-ask-offers-six-of-ten-evidence-classes` and
`register-cells-may-contain-pipes-and-shift-every-column`). Canonical register and
ledger bytes remain untouched. `ledger_render_drift` must continue to fail;
its suppression, a compatibility wrong-owner projection, or editing the forbidden
artifact would defeat the task. Completion of Row 2's canonical green requires
its owner to regenerate LEDGER through the existing writer after accepting this
change. Status: implementation under verification, pending owner regeneration.
This does not stop the other four rows.

Standing rule: `docs/how-to/author-measurement-instruments.md`, linked from root,
tools and architecture author surfaces, binds future absence instruments by
behavior. MP-B1 retains historical output migration; 16 disclosed bounded modes
are not an all-format compliance claim. The file-reader collector explicitly
excludes imports, Git/ref access, subprocess reads and services; Atlas additionally
names delegated schema-helper reads. These are declared limits, not fake reads.

Working complete outputs (SHA-256):
- `docs/superpowers/journals/measurement-plane/execution/raw/ledger-measurement-red.log@589ee863e66312b13eaf270467ddd72a20a67dd33dc0009b19147a1ee737b66e`
- `docs/superpowers/journals/measurement-plane/execution/raw/ledger-measurement-green.log@dd6e413df167e4ef822f091f8169d164d7da81e43eb8e40a325f0a77b618b0f3`
- `docs/superpowers/journals/measurement-plane/execution/raw/atlas-measurement-red.log@ceb576c6180d19f623378650ce2f4a812556544fc65362548747089d2b7d0d3c`
- `docs/superpowers/journals/measurement-plane/execution/raw/atlas-measurement-green.log@0ade57e64a67c200f40950ee0888f16cf5688c44f1c5d6e6b8255e3b36579af9`
- `docs/superpowers/journals/measurement-plane/execution/raw/ledger-pipes-red.log@0079f1e6578db5e68e52d326c6c2ec0c58a8d8b60f410857b4c73ba66683c455`
- `docs/superpowers/journals/measurement-plane/execution/raw/ledger-pipes-green.log@8d2b4163d41fa7f2ac8c40fcce225500f12ea26fd020028b08fb2632c5556d6a`
- `docs/superpowers/journals/measurement-plane/execution/raw/ledger-companions-green.log@d30295b9c8225d21d491a6956a2da70ad89108c0390f530f673e3894a389069c`
- `docs/superpowers/journals/measurement-plane/execution/raw/ledger-projection-drift.log@f129a9ba5dba65d5a8845a944b1fd2c04fb5d43e7030f0de6aba4b25e26b1b6e`
- `docs/superpowers/journals/measurement-plane/baseline/raw/debt-ledger-unit-base.log@c18deb2bcc9a6d2069467e8554cacbcef6ec66c17ab50414bc5d0cddd86e31f1`
