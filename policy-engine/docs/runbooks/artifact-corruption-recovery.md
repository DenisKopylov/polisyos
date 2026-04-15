# Artifact Corruption Recovery

Related runbook: [Retained Artifact Recovery](retained-artifact-recovery.md).

> Use this runbook when read-time integrity verification detects a corrupted
> artifact blob, manifest mismatch, or related CAS corruption.

## Symptom

- artifact read/download returns a typed integrity error;
- one run, lineage view, or preview path fails while adjacent resources still
  work;
- operators see hash mismatch between manifest and blob content;
- downstream workflows fail because one upstream artifact cannot be trusted.

## Likely Causes

- partial or corrupted blob write from an earlier incident;
- manual file movement or unexpected filesystem resolution;
- backend storage corruption;
- trust-store or signature sidecar mismatch after rotation or recovery.

## Timeline Capture Expectations

- failing `artifact_id`;
- first `request_id` and endpoint where the mismatch was detected;
- whether the failure is digest mismatch, manifest inconsistency, or trust-store
  issue;
- upstream run/job/resource IDs that depend on the artifact.

## First Triage Steps

1. Confirm the exact failing artifact ID and capture the integrity error.
2. Determine whether corruption is isolated to:
   - one blob;
   - one manifest;
   - one artifact family or time window.
3. Preserve the corrupted artifact state before rewriting or deleting anything.
4. Identify whether a retained copy, replay path, or upstream reissue source is
   available.

## Rollback / Mitigation

- quarantine the corrupted artifact from normal read paths if possible;
- restore from a retained copy when chain-of-custody remains trustworthy;
- otherwise reissue or recompute from the nearest trusted upstream state;
- if trust-store mismatch is the real cause, switch to the key-rotation runbook
  rather than treating it as blob corruption;
- do not overwrite the corrupted evidence until root cause is documented.

## Escalation Owner

- primary: `@platform-owners`
- supporting: `@runtime-owners`, security owner when signing/trust is involved

## Follow-up Checklist

- link the restored or reissued artifact to the original corruption incident;
- confirm downstream run/lineage views now resolve cleanly;
- add a corruption regression test if the root cause was a product bug rather
  than underlying storage failure.

## Blameless Postmortem

### What Went Well

- whether read-time verification caught corruption before silent bad data escape;
- whether retained artifacts or replay made recovery straightforward.

### What Went Poorly

- whether evidence preservation slowed recovery because tooling was unclear;
- whether operators lacked a fast way to distinguish corruption from key/trust
  issues.

### Action Items

| Action item | Owner | Due date | Status |
|---|---|---|---|
| Improve corruption detection or recovery automation | `@platform-owners` | YYYY-MM-DD | open |
| Add the reproduced corruption path to tests or drills | affected owner | YYYY-MM-DD | open |
