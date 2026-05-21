# Deterministic Replay

Source of truth: `src/polisyos/runtime/quality/replay.py`,
`tools/ops_runners/runtime/replay_canary_bundle.py`, and
`tests/unit/runtime/quality/test_replay.py`.

Deterministic replay records the minimum sanitized material needed to reproduce
and compare a serious canary without reusing runtime secrets.

## Artifacts

`replay_manifest_ref` points to a CAS artifact with
`schema_version: policyos.replay_manifest.v1`. It records:

- request fingerprint and request key shape
- git SHA
- dependency fingerprints
- feature flags
- provider/model metadata
- prompt/template fingerprints
- data refs, source refs, norm refs, and CAS refs
- random seeds
- sanitized run params
- quality scorecard ref
- execution summary
- quality summary

`drift_explanation_ref` points to a CAS artifact with
`schema_version: policyos.drift_explanation.v1`. It compares a baseline replay
manifest with the replay manifest and records every difference with:

- path
- typed drift source
- impact
- status
- baseline fingerprint
- replay fingerprint
- optional acceptance reason

Replay payloads must not contain raw secrets. Secret-like keys are represented
as presence/fingerprint metadata, and operators should never need a provider
credential to build or compare replay refs from a sanitized bundle.

## Drift Sources

Replay differences are classified as one of:

- `code`
- `data`
- `source`
- `norm`
- `provider`
- `model`
- `config`
- `prompt`
- `cas`
- `dependency`
- `nondeterminism`

Accepted drift must name a typed source and a bounded impact. A data snapshot
refresh, for example, may be accepted as `data` with `low` impact when the
operator records an explicit reason.

Unexplained drift fails production readiness. This includes deterministic output
or quality summary changes that do not have an accepted difference entry.

## Canary Bundle Runner

Use:

```bash
python -m tools.ops_runners.runtime.replay_canary_bundle \
  --bundle .polisyos/canary_evidence/<bundle> \
  --cas-root .polisyos/canary_replay_cas \
  --json-output .polisyos/canary_evidence/<bundle>/replay.json
```

The runner writes `replay.json`, links `replay_manifest_ref` and
`drift_explanation_ref` from `bundle.json`, and returns exit code `2` when the
drift explanation reports `production_readiness: fail`.

## Verification

```bash
uv run pytest tests/unit/runtime/quality/test_replay.py tests/repo_quality/tools/test_replay_canary_bundle.py -q
```
