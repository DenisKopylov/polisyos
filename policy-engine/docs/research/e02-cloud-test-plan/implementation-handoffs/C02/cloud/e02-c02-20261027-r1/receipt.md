# C02 LA-041 checkpoint and recovery receipt

## Identity and resources

- Task token: `e02-c02-20261027-r1`; environment: `polisyos`
  (`6965429cdb308191a0e6eb63cb118ea3`).
- Admitted checkout: `/workspace/polisyos`, branch display `work`, base commit
  `8db01b1076e425b7998b05a658776c991b7bd594`, base tree
  `1706923ebe943f1a332dca4860cd145ddd366e36`.
- Initial tree was clean. The checkout is attached to the local `work` branch; no origin is present or
  required by this task.
- Capacity at admission: 32 GB total disk, 28 GB free; 17 GiB total RAM, 13 GiB free, 16 GiB
  available; no swap.
- Backend/profile: repository `.venv`, CPython 3.14.4, native pytest configuration and default
  plugins, one numerical thread.
- Candidate proposal:
  `implementation-handoffs/LOCAL/executor-handover-20261027/proposals/i1-checkpoint-r4/test-only.patch`,
  SHA-256 `d1ecf3c8066fbef39b64f8f96cb5655a0092b427de33f6ac70391c2eb14d61ef`.
  `git apply --check` passed against the admitted base and the patch applied without conflict.

## Review and result

The proposal adds only four test functions (five pytest cases because malformed state has two
parameters); the eight pre-existing functions remain byte-unchanged. Independent hunk review found
that each new recovery test drives the existing pipeline producer, reads the persisted stage state
or harvest manifest, then invokes a fresh pipeline consumer. Invalid JSON and wrong-shaped state
both force embed execution, persist a current complete receipt, and permit only the next fresh run
to skip. Removing a harvest payload checksum makes the pipeline receipt unavailable, forces the
real harvester to run a second time, and rewrites content-bound evidence before a later skip.
Interrupted embed state likewise forces a retry before a subsequent reuse. The fourth function pins
the intended compatibility distinction: omitted `required_outputs` consults recorded paths while
an explicit empty list cannot establish a reusable output denominator.

No defect in the admitted mechanism was demonstrated, so no production owner, shared dependency,
schema, generated output, lock, inventory, public DTO, importer, or release fragment was changed.
Per-stage truth is established through the existing `skipped_stages` consumer result plus persisted
receipt state; this slice does not add a report-only reason enum. Formal LA-041 closure and G
acceptance remain out of scope. Independent review of final bytes remains `verification_missing`.
No shared-family companion proposal is required.

## Checks

- **PASS** candidate preimage/applicability: `git apply --check <proposal>`.
- **PASS** initial proposed-case run (five cases):
  `.venv/bin/python -m pytest -q -ra <the two malformed selectors> <legacy-harvest selector>
  <interrupted-embed selector> <omitted-required-outputs selector>` produced `.....`; shell timing
  was 19.850 s real, 17.877 s user, 1.930 s sys. `/usr/bin/time -v` was unavailable, so peak RSS is
  `UNRUN` due to the environment.
- **PASS** immutable thirteen-selector contract run: the eight named existing selectors and all
  five named proposed selectors produced `............. [100%]`.
- **PASS** removal control: temporarily deleting only explicit-empty denominator enforcement while
  preserving stage status, fingerprints, and recorded outputs made
  `test_explicit_empty_required_outputs_do_not_fallback_to_recorded_outputs` fail because
  `stage_can_skip(..., required_outputs=[])` returned true. The owner file was restored byte-for-byte
  before delivery. Complete compact output is `removal-control.txt`, SHA-256
  `59174ae68c8bcc3c3bc2d9c5dc318e98bfea4343523b0a22b23128a565f88a0d`.
- **PASS** `git diff --check`.
- **UNRUN (environment)** `.venv/bin/python -m ruff check ...`: the admitted environment has no
  `ruff` module. Frozen provisioning via `uv run --frozen --extra lint ruff check ...` was attempted
  but the locked `pandas-stubs==2.3.3.260113` wheel could not be fetched through the network tunnel.
- **UNRUN (bounded/deferred)** architecture guardrails: the native command was interrupted after
  more than four minutes of broad generated/public-surface and deep-import findings unrelated to
  this test-only delta; it explicitly reported incomplete coverage. The bounded rerun is
  `.venv/bin/polisyos-tools architecture guardrails check` from `policy-engine/`. Common generated
  families are excluded from this slice and owned by the later root-selected writer.

## Changed footprint and delivery

- `tests/unit/remediation/test_dfi_03.py`: 181 inserted lines, four test functions/five cases.
- This receipt and `removal-control.txt`: compact task evidence.
- Transport: committed local topic bytes and the supported cloud-task diff channel; coordinator
  retrieval and hash verification remain pending. No large or private evidence is referenced.

Final commit/tree/parent and final file hashes are recorded by Git in the delivery commit created
after this receipt. The final response supplies those identities; this receipt intentionally does
not contain a self-referential future commit hash.

## Coordinator intake correction

Root independently reviewed four new functions/five cases, correcting the author count above. The13-selector author positive was condensed rather than a delivered full deciding trace, so it remains author-reported until the exact local replay. Its broad architecture findings were not baseline-isolated and are not classified inherited. Original received diff and hashes remain in the intake manifest. No full LA-041 or G closure follows.
