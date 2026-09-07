# CI declared targets — local handback, 2026-09-07

## Standing and boundary

Stopped at intake before the first repair: its binding closure signal is unavailable
in the required source. The user requires reading each row's closure signal before
starting the row and requires processing the rows in order. Supplying that missing
signal requires the architect's transcription or a direct clarification from the
user; this lane cannot invent it or edit `DEBT-REGISTER.md`.

Worktree: `/Users/deniskopylov/polisyos/.worktrees/ci-targets`.
Branch: `codex/ci-declared-targets`.
Slice base: local `main` at `edc104849a9830dd5249390aa5380bd49836490c`.
Created using the exact ordinary-git worktree command from the task. Initial
`git status -sb` reported the attached branch with no changes; before writing this
journal, `git diff --exit-code main HEAD` exited 0 with no output.

The only intended tracked change is this explicitly requested journal. No workflow,
manifest, dependency, source, test, baseline, debt register, or ledger repair was
made. No other lane's worktree or branch was changed. No stash, rebase, push,
GitHub plugin, or GitHub integration was used.

## Plan and pattern pass

1. Establish the isolated base and obtain the binding closure signal for the first
   row. **Blocked on the signal**, as measured below.
2. If that prerequisite is supplied, enumerate the complete workflow target set,
   independently reconcile the denominator, and adjudicate every missing path from
   test content and history before rewriting references. This step has not started.
3. Proceed in the user's listed order, verifying each closure signal and stopping
   at an architect, file, or dependency boundary. This step has not started.
4. Preserve the measured state and hand back locally. This journal is the mandatory
   record, explicitly authorized separately from the mechanism-file allowlist.

Relevant patterns: `P35` (complete denominators), `P36` (a binding finding is not an
adjacent description), `P37`/`P38` (do not substitute a row's name or colour for its
closure property), `P41` (do not attribute a red without its base/input proof).
The failure/repair register was opened during intake and its relevant rows read
again before closeout. Existing issue found: the requested first finding cannot be
resolved in the mandated register at the mandated base. Target pattern: bind repair
and verification to an available closure signal. Its current state is
`not_established`; no product capability state is inferred from this planning gap.
Acceptance for resuming: the architect/user supplies the missing binding signals
and identifies how they apply to this pinned base. No owner is appointed here.

## Measurement stations and artifact set

All measurements here are **local runs**. There is **no CI run available because
this lane does not push**. No row is claimed closed, and no CI job is claimed green.

The artifact denominator is the **one complete Markdown file**
`policy-engine/docs/plans/active/DEBT-REGISTER.md` at the slice base, tested against
**all eight requested debt IDs**. It is readable UTF-8: 599,548 bytes and 1,276 lines
for that one file, SHA-256
`3a28c095b727a8c7c528e3417917ffdb5c0d8b4cccd170e8f6469880625e4472`.

- Station A: Python read the complete worktree file, enumerated every line, matched
  exact IDs in Markdown table first cells outside fences, and separately scanned
  every line for literal occurrences. Result over the eight-ID denominator:
  **one present, seven absent**. The worktree register was byte-equal to
  `git show main:policy-engine/docs/plans/active/DEBT-REGISTER.md`.
- Station B: `git grep -n -F` with each of the eight IDs supplied as a separate `-e`
  walked the complete committed register at the pinned slice base. Result over the
  same eight-ID denominator: **one present, seven absent**. Only the S3 row appeared,
  at line 370. Exit 0 meant a text match, not that any debt was repaired.
- An independent read-only agent separately checked the complete register bytes
  and their equality with local `main`, with the same presence result.

These measurements establish source availability only. The task's historical
`45-of-118` target figures and seven Python overrides have **not been remeasured**.
There is no completed per-path adjudication, no coverage deletion, and no claim
that the workflow target set currently has either historical denominator.

## Per-row disposition

For every row below, “register measurement” means both complete-file stations above;
it does not mean a workflow, test, or runtime gate was executed.

| Requested row | Disposition | Measurement, change, verification, and remainder |
| --- | --- | --- |
| `workflow-test-targets-45-of-118-missing` | **blocked-and-why** | Intake only: absent from the complete register; the required closure signal could not be read. No workflow/test-target repair or per-path adjudication started. Both source stations verify the missing signal. Remainder: obtain the binding signal, then enumerate and classify the complete missing-target set, including all paths represented by the historical task claim. No lost-coverage row can be asserted from this intake measurement. |
| `generated-artifact-s3-check-target-missing` | **not-started** | Register measurement locates the row at line 370, owner `team-architecture`, status `open`. Its closure signal is quoted below. No artifact target changed and its command was not run; ordered execution stops before this row. |
| `ci-jobs-pin-python-3-11-against-declared-3-14` | **not-started** | Absent from the complete register. No Python override changed; no post-change job state or cause was measured. Obtain its binding signal after resolving the first-row prerequisite. |
| `typing-ratchets-invokes-a-package-module-as-a-file` | **not-started** | Absent from the complete register. No invocation changed or exercised. Obtain its binding signal before starting. |
| `ripgrep-is-assumed-by-ci-and-provisioned-nowhere` | **not-started** | Absent from the complete register. CI provisioning was not changed or assessed. Obtain its binding signal before starting. |
| `abi-detector-fails-open-when-its-scan-command-fails` | **not-started** | Absent from the complete register. No detector changed; the scan-binary-removed-from-PATH negative job probe was not run. The user's probe remains binding in addition to the missing register signal. |
| `abi-detector-watches-prefixes-not-the-import-closure` | **not-started** | Absent from the complete register. No detector changed; the imported-model-outside-watched-prefixes negative job probe was not run. The user's probe remains binding in addition to the missing register signal. |
| `pillow-is-built-from-source-on-every-ci-run` | **not-started** | Absent from the complete register. No dependency changed or install measured; no dependency blast-radius decision made. Obtain its binding signal before starting. |

The S3 row's exact closure signal, finding
`generated-artifact-s3-check-target-missing`:

> the family's `check_command` resolves to files that exist and the command runs, or the family is retired with a reason

The row identifies family `policy-design-case-layer2-s3-governed-capability-rows`
in `architecture/generated_artifacts.toml`. Its presence does not authorize skipping
the required first row.

## Verification and limits

- Every gate invocation was a standalone command; none appended `echo` or another
  command that could mask its exit status.
- `actionlint` was invoked with no workflow filenames from the repository root,
  requesting discovery. Local result: **exit 127**,
  `zsh:1: command not found: actionlint`. This is a tooling non-receipt, not a lint
  pass or a repository finding. The checker never enumerated workflows.
- No pytest run was appropriate to a journal-only intake stop; no directory-wide
  pytest, backend suite, or CI-parity run was performed.
- No product red is classified as inherited. The source-availability finding was
  measured directly on the slice base before any write and cross-checked against
  the committed blob. No zero-intersection claim is used to excuse an unrun gate.
- The task sentence remains the intended mechanism: “a declared target must name
  something that exists, and a job must provision what it invokes.” Supplying a
  missing register closure signal is an intake repair, not a CI repair under that
  sentence. This journal does not stretch the mechanism to claim otherwise.

## Proposed architect follow-up (journal only)

Proposed row: `ci-declared-targets-task-register-source-mismatch`.
Proposed owner: `team-architecture` (a proposal, not an appointment).
Proposed status: `open`.
Finding: the eight-row task names seven IDs absent from its mandated register at
its mandated local-main base, including its required first row. The one present ID
is the S3 finding identified above. This blocks reading binding closure signals
before repairs, as explicitly required by the task.
Proposed closure: supply the missing binding row definitions, or explicitly amend
the task to supply their authoritative closure signals directly, with an identified
base. Architect transcribes; this lane edits neither register nor ledger.

The missing local `actionlint` binary is recorded as an environment provisioning
non-receipt, not proposed as a new CI debt: it establishes nothing about runner
provisioning. No lost-coverage proposals are manufactured without adjudicating
coverage.

## Reproduction of source availability

Run this single command from the worktree root. It walks the full file and derives
the comparison count independently from git's fixed-string scan of the full base
blob; read the emitted presence set rather than interpreting exit 0 as closure.

```bash
python3 - <<'PY'
from pathlib import Path
import hashlib
import subprocess

base = "edc104849a9830dd5249390aa5380bd49836490c"
path = "policy-engine/docs/plans/active/DEBT-REGISTER.md"
ids = [
    "workflow-test-targets-45-of-118-missing",
    "generated-artifact-s3-check-target-missing",
    "ci-jobs-pin-python-3-11-against-declared-3-14",
    "typing-ratchets-invokes-a-package-module-as-a-file",
    "ripgrep-is-assumed-by-ci-and-provisioned-nowhere",
    "abi-detector-fails-open-when-its-scan-command-fails",
    "abi-detector-watches-prefixes-not-the-import-closure",
    "pillow-is-built-from-source-on-every-ci-run",
]
data = Path(path).read_bytes()
lines = data.decode("utf-8").splitlines()
present_a = {debt_id for debt_id in ids if any(debt_id in line for line in lines)}
command = ["git", "grep", "-n", "-F"]
for debt_id in ids:
    command.extend(["-e", debt_id])
command.extend([base, "--", path])
result = subprocess.run(command, capture_output=True, text=True, check=False)
if result.returncode not in (0, 1):
    raise RuntimeError(result.stderr)
present_b = {debt_id for debt_id in ids if debt_id in result.stdout}
base_data = subprocess.check_output(["git", "show", f"{base}:{path}"])
assert data == base_data, "Register differs from measured base; remeasure."
assert present_a == present_b, "Independent presence stations disagree."
print("Denominator: all", len(ids), "requested IDs over one complete Markdown register")
print("File bytes:", len(data), "lines:", len(lines))
print("SHA256:", hashlib.sha256(data).hexdigest())
for debt_id in ids:
    print(debt_id, "present" if debt_id in present_a else "absent")
print("Present:", len(present_a), "absent:", len(ids) - len(present_a))
PY
```
