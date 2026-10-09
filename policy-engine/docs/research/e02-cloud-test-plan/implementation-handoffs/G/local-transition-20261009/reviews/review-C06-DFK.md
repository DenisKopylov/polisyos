# Independent bounded admission review: C06-DFK

Date: 2026-10-09
Reviewer: independent G-side source review
Disposition: **HOLD this exact source commit for one output-serialization defect.** The bounded census implementation is otherwise reviewable and its real-Git/removal evidence is materially stronger than marker-only evidence. This hold is source-specific; it is not a demand for all global gates or formal finding closure before bounded code admission.

## Exact candidate and review scope

- G base: `dee58973f7673299070b7c7374f419b0adb8175c`.
- Source commit: `3a0d5549606087c1d4e8d344ed474c0dfb4cbe5d`; tree `1e2e7c6ca7948f3c2b771af431bd0d73510fec3a`; parent is exactly the G base.
- Published topic tip: `6c565cd65899d91bda370416651555eee143e194` (source commit plus handoff/publication material).
- Source delta against G is exactly three paths: new census CLI module, its mirrored DFK-01 tests, and a release fragment. The current-G DFK-02 tests are unchanged. Handoff input byte identities and recorded SHA-256 values match the candidate.
- Read the complete ORCH02-r2 coordinator handoff at `d9a4b671c99bf6a5435fde4fc873092e03b451b0`, the individual DFK handoff at the published tip, the full census module and test file, and the deciding manifests/reviews. The source is a normal child of G; no rebase or rewritten history was found.

## What the source does well

The command is an actual registry-discovered CLI (`polisyos-tools validation schema-fqn-census --repo-root …`), not a test-only helper. It enumerates Git-visible tracked and non-ignored untracked paths and separately records ignored candidates. The `-z` status parser retains both status columns, both paths for rename/copy records, and avoids Git’s quoted-path presentation. The census is explicitly a local static UTF-8 text census; it does not claim runtime, installed-wheel, archive, ignored-file, or external-consumer completeness and does not authorize retirement.

The source and handoff include behavioral probes against real temporary Git repositories, not only mocked command output. They cover staged and unstaged status combinations, rename/copy path records, spaces/newlines/non-ASCII names, nested product roots, and preservation of subsequent records. A missing selected path is represented as partial/unreadable with exit 2 rather than as an empty/complete census. The tests compare against a separate Git-diff/`ls-files` oracle. The historical-classifier removal probe leaves markers intact and fails all six matched real-Git cases, showing that the tests detect the behavior rather than merely the source shape.

## Deciding evidence and its limits

The source-qualified handoff reports 45/45 selected DFK-01 plus unchanged current-G DFK-02 tests passing, six fresh real-Git/public-CLI cases passing, four SARIF/JUnit cases passing, and the JSON missing-input scenario passing. The matched classifier-removal control reports six expected assertion failures and zero errors. Scoped Ruff, formatting, and strict mypy pass; the source-import gate is correctly skipped because no `src` paths changed. These are source-qualified receipts from the handoff; I did not rerun tests, install dependencies, or alter source.

The handoff also reports a global architecture-gate failure (196 diagnostics), a partial/static-only invocation check, and no installed-wheel/sdist or full package-archive census. The architecture diagnostic search recorded no direct match to this candidate’s module, command, or test path; it is not evidence that this source introduced those global findings, and it is not by itself a reason to reject this bounded source. Conversely, I did not reproduce every global diagnostic against the exact slice base, so P41 ownership of the aggregate red remains `not_established`. No product finding is formally closed by this review.

Before release/public documentation, G still needs the named companions: review/render the tools reference, account for the registry-discovered command and its Git dependency in the public inventory/operator lifecycle, and reconcile release inventory/version. Those obligations are separate from the source’s narrow local-census claim; they do not excuse the defect below.

## Blocking source defect: invalid-byte path names can break the JSON receipt

`_git_paths` and `_git_status_paths` decode Git path bytes with `os.fsdecode` (source lines 269, 298–303). On POSIX, undecodable filename bytes survive filesystem decoding as surrogate code points. Selected path strings then flow into receipt fields including `selection.selected_paths`, `read_paths`, and match/error records (around lines 603–604 and 790–819). `main` serializes the receipt with `json.dumps(..., ensure_ascii=False)` (line 875).

For a legal Git-visible selected filename whose bytes are not valid UTF-8, the serializer can emit a surrogate to stdout as invalid UTF-8 (or fail on a strict output encoding). The census can have read a valid UTF-8 file body and still label the bounded census complete while its promised JSON receipt is not valid UTF-8 JSON. The handoff bounds file contents to UTF-8 but does not declare filename bytes unsupported or force an incomplete result. Existing path tests cover spaces, newlines, and Unicode text names, not undecodable byte names. This is an observable defect in the command’s primary output contract, not a demand to census binary file contents.

Smallest repair: serialize with ASCII escaping (`ensure_ascii=True`, the JSON default) so surrogate-escaped filenames become valid JSON escape sequences; add a real-filesystem byte-name adversarial test that invokes the public command, decodes stdout as UTF-8, parses it as JSON, and confirms the selected path remains represented. Alternatively, explicitly reject such names and emit a valid partial receipt, but silently omitting them or claiming complete is not acceptable.

## Admission decision

**HOLD `3a0d5549…` as-is.** The exact source is not yet independently merge-ready because a valid filesystem path can invalidate its deciding JSON output. This is a narrow, locally repairable source issue. After the serializer fix and the focused byte-name regression/removal probes pass on the new immutable source, the bounded mechanism is otherwise suitable for G to consider independently of global architecture cleanup, installed packaging, production authority, or formal finding adjudication. Keep those release/verification/authority limitations explicit and finish the named G documentation/inventory companions before claiming public release completeness.

## Reviewer actions

Read-only inspection only: Git refs/status, exact `git show`/tree/diff/blob identities, source, tests, handoffs, and retained deciding outputs. No source mutation, commit, push, test execution, dependency installation, production-data access, or integration write was performed. This review is saved under the ignored `_build` tree; integration HEAD remains the stated G base.
