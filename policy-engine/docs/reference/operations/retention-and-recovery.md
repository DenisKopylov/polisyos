# Retention and Recovery Policy

Related runbooks: [Replay or Restore Workflow](../../runbooks/replay-or-restore.md),
[Retained Artifact Recovery](../../runbooks/retained-artifact-recovery.md).
Related reference: [Operations Reference](index.md).

Owner: `@platform-owners`
Source of truth: `src/polisyos/core/artifacts/**`, `docs/reference/generated-artifacts.md`, and the linked replay/retention/corruption runbooks

> Эта страница задаёт lifecycle rules для operational artifacts, чтобы storage
> growth и restore expectations были intentional, а не accidental.

## Retention Classes

| Class                  | Default retention | Purpose                                                       |
| ---------------------- | ----------------- | ------------------------------------------------------------- |
| `R0 Ephemeral`         | 14 days           | short-lived CI diagnostics and local debugging outputs        |
| `R1 Short operational` | 30 days           | near-term troubleshooting, replay, and benchmark working sets |
| `R2 Release evidence`  | 90 days           | release-adjacent summaries and reproducible decision support  |
| `R3 Compliance`        | 365 days          | audit packages, signed outputs, provenance evidence           |
| `R4 Cold archive`      | 730 days          | long-tail restores, legacy archives, incident preservation    |

## Artifact Family Policy

| Artifact family                                                            | Retention class                            | Reproducible?                           | Policy                                                                    |
| -------------------------------------------------------------------------- | ------------------------------------------ | --------------------------------------- | ------------------------------------------------------------------------- |
| CI artifacts (visual diffs, Lighthouse, audit JSON, test reports)          | `R0`                                       | Usually yes                             | keep only to debug recent CI failures; discard after window expires       |
| Benchmark raw outputs in `benchmarks/_reports/`                            | `R1`                                       | Yes, if code/data/profile are preserved | keep recent comparison window; preserve release summaries longer          |
| Replay / state artifacts (`record_ref`, replay fixtures, checkpoint heads) | `R1` while active, `R4` if incident-linked | Partially                               | active operational value; incident-linked copies promoted to cold archive |
| Audit packages, provenance, SLSA, signing evidence                         | `R3`                                       | No for evidentiary value                | must remain intact with checksums and verification metadata               |
| Local snapshots / manifest trees                                           | `R1` by default                            | Usually yes                             | keep latest working window and promote only named restore points          |
| Cold-tier archives (legacy runs, incident tarballs)                        | `R4`                                       | No practical guarantee of recreation    | preserve report + checksum + archive together                             |
| Committed schema/OpenAPI snapshots in git                                  | git history                                | Yes, from repo history                  | generated workspace copies are discardable; committed history is retained |

## Reproducible vs Must Retain

### May Be Discarded After Window

- CI-only artifacts whose content can be recreated from the same commit and
  lockfiles;

- benchmark smoke outputs not tied to release decision or incident analysis;
- temporary local snapshots without designated restore-point status;
- transient generated docs site output.

### Must Be Retained

- audit packages used for compliance, review, or incident evidence;
- signed release evidence and SBOM/SLSA payloads;
- cold archives created as the only surviving copy of historical runs;
- incident-linked replay sessions, checkpoint heads, or restore bundles that
  explain a real production issue.

## Restore Drills

Phase 6 standardizes four restore drills:

| Drill                     | Cadence   | Success condition                                                              |
| ------------------------- | --------- | ------------------------------------------------------------------------------ |
| Replay session restore    | monthly   | known-good `replay_ref` reproduces without network access                      |
| Checkpoint resume restore | monthly   | checkpoint can be resolved and resumed on a clean workspace                    |
| Docs site rebuild         | monthly   | `uv run --extra docs python -m mkdocs build --strict` succeeds from clean sync |
| Archive restore           | quarterly | selected cold archive can be unpacked, hashed, and interpreted with its report |

## Recovery Procedures by Artifact Family

Detailed recovery execution lives in
[Retained Artifact Recovery](../../runbooks/retained-artifact-recovery.md).

### Replay / Record Sessions

- source of truth: CAS-backed `fabric.record_session`;
- restore artifact together with connector manifest context;
- validate using the same connector datasets the session was recorded against;
- if the session is incident-critical, promote a copy to `R4 Cold archive`.

### Checkpoints and Resume State

- source of truth: current checkpoint head plus referenced artifact payload;
- restore requires both metadata and payload compatibility with current workflow;
- corrupted head files are copied aside before repair;
- failed restore attempt is itself recorded in incident timeline.

### Audit Packages and Provenance

- restore package as an immutable bundle;
- verify checksum, provenance, signature, and SLSA sidecars before trusting it;
- never split `provenance`, `slsa`, and `signatures` from the package they
  describe.

### Legacy Run Archives

- restore requires both tarball and `.report.json` emitted by
  `tools/ops/runtime/archive_legacy_runs.py`;

- hash must match stored `archive_sha256`;
- if `--delete-source` was used, cold archive becomes the only truth and must
  be treated accordingly.

## Storage Governance Rules

- every retained artifact family needs a named owner;
- every cold archive needs checksum plus manifest/report;
- promote to longer retention only when there is a real decision, audit, or
  incident reason;

- silent sprawl is a platform smell and reviewed quarterly.

## Recovery Expectations

- responders should know before the incident whether a family is recoverable or
  merely reproducible;

- if a restore drill fails, treat it as an operational defect, not as bad luck;
- if required artifacts are missing, the owning team must update both retention
  policy and the relevant runbook.
