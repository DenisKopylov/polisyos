# Artifact Corruption Recovery

Related runbook: [Retained Artifact Recovery](retained-artifact-recovery.md).
Related Fabric reference: [Fabric Data Plane](../reference/fabric/data-plane.md).

> Use this runbook when read-time integrity verification detects a corrupted
> artifact blob, manifest mismatch, or related CAS corruption.

Owner: `@platform-owners`
Last tested: `2026-04-17` against the linked recovery checks and current retained-artifact evidence.
Evidence path: `docs/reference/operations/retention-and-recovery.md`; `docs/archive/reports/core-runtime-closeout.md`; `tests/unit/fabric/test_lineage.py`
Rollback path: isolate the corrupted artifact, restore from a trusted retained copy or reissue from trusted upstream state, and keep the corrupted evidence for postmortem.

Freshness: 2026-04-17.

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
- Fabric schema snapshot or connector contract snapshot was edited manually
  instead of regenerated from source;

- quarantine, CDC, quality, or lineage artifact was restored without its
  manifest/checksum/provenance sidecar.

## Timeline Capture Expectations

- failing `artifact_id`;
- first `request_id` and endpoint where the mismatch was detected;
- whether the failure is digest mismatch, manifest inconsistency, or trust-store
  issue;

- upstream run/job/resource IDs that depend on the artifact.
- for Fabric, capture connector id, dataset id, profile id, schema id/version,
  artifact kind, quarantine reason, lineage graph id, and downstream world
  projection/table when available.

## First Triage Steps

1. Confirm the exact failing artifact ID and capture the integrity error.
2. Determine whether corruption is isolated to:

   - one blob;
   - one manifest;
   - one artifact family or time window.
3. Preserve the corrupted artifact state before rewriting or deleting anything.
4. Identify whether a retained copy, replay path, or upstream reissue source is
   available.
5. If the corruption is Fabric schema-related, compare generated snapshots
   against source contracts before restoring:

```bash
uv run polisyos-tools connectors check-contracts --check
uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out _build/.tmp/fabric-schema-governance.json
uv run --extra ml polisyos-tools diagnostics gen-schema --check
```

## Rollback / Mitigation

- quarantine the corrupted artifact from normal read paths if possible;
- restore from a retained copy when chain-of-custody remains trustworthy;
- otherwise reissue or recompute from the nearest trusted upstream state;
- if trust-store mismatch is the real cause, switch to the key-rotation runbook
  rather than treating it as blob corruption;

- do not overwrite the corrupted evidence until root cause is documented.
- for Fabric quarantine/CDC/lineage artifacts, prefer reissue from recorded
  replay or retained upstream evidence instead of hand-editing CAS payloads;

- for corrupted schema snapshots, regenerate from contract source and keep the
  failing snapshot as incident evidence.

## Escalation Owner

- primary: `@platform-owners`
- supporting: `@runtime-owners`, security owner when signing/trust is involved
- Fabric artifacts: `@fabric-owners`

## Follow-up Checklist

- link the restored or reissued artifact to the original corruption incident;
- confirm downstream run/lineage views now resolve cleanly;
- add a corruption regression test if the root cause was a product bug rather
  than underlying storage failure.

- if Fabric world/query artifacts were affected, rerun the materialization,
  lineage, and time-travel tests that match the corrupted surface.

## Blameless Postmortem

### What Went Well

- whether read-time verification caught corruption before silent bad data escape;
- whether retained artifacts or replay made recovery straightforward.

### What Went Poorly

- whether evidence preservation slowed recovery because tooling was unclear;
- whether operators lacked a fast way to distinguish corruption from key/trust
  issues.

### Action Items

| Action item                                                                   | Owner              | Due date   | Status |
| ----------------------------------------------------------------------------- | ------------------ | ---------- | ------ |
| Improve corruption detection or recovery automation                           | `@platform-owners` | YYYY-MM-DD | open   |
| Add the reproduced corruption path to tests or drills                         | affected owner     | YYYY-MM-DD | open   |
| Add Fabric schema/quarantine/lineage recovery evidence to the incident record | `@fabric-owners`   | YYYY-MM-DD | open   |
