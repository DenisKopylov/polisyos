# Versioned candidate replay input

`ReplayCaptureV3` (`policyos.testing.design_generation_replay_input.v3`) stores
each unchanged `LLMGenerationCall` once with `CallUsageEvidenceV2` sidecars.
These strict testing formats are not product N4 CAS models, historical provider
usage signatures or billing authority. R1/R2 were unapplied proposals; no old
product schema is populated with a new field. Legacy loaders reject the new root,
and unknown evidence/envelope versions fail without a generic fallback.

The sidecar preserves selected nested-usage presence/type separately from outer
usage keys. The shared Core parser chooses one container: present malformed non-null nested values are invalid; a nullable nested container
remains missing and cannot borrow outer components; partial nested values cannot
borrow outer components;
only absent nested usage permits the supported top-level form. Alias presence
precedence preserves a present null component as invalid under the existing
Gateway contract; absence is missing, and explicit zero/unknown/invalid remain
distinct. The old recorder
convenience-total fallback is checked separately from the raw quantity.

Generic replay re-admits and freezes all supplied input bytes. Every unqualified
legacy pair stays unknown, including positive pairs. A captured reuse's billable
zero never becomes fresh known provider usage, and no Core attestation or old
reported monetary amount is forwarded. New replay uses the current configured
tariff and normal settlement owner.

## Candidate consistency is the deliberate boundary

Source/call/model/prompt/response joins and raw quantity interpretation are
recomputed from the supplied file. The file's provider-usage and settlement-ack
claims remain `consumer_asserted`; original capture execution/exchange association
is `not_established_by_this_artifact`. Jointly editing call and provider counters
and recomputing their internal hashes can produce another consistent candidate
input with the same event digest. The named joint-mutation test demonstrates
that limitation, rather than calling a self-hash historical authentication.
A historical or authority claim needs independently admitted actual exchange,
source/readset/backend evidence and accessible deciding bytes. This file grants
no acceptance, authority or closure.

## Explicit unqualified standalone writer

Use the admitted existing local environment/backend, one attempt, an existing
absolute physical user-owned case directory, and one fresh basename:

```sh
.venv/bin/python -m tools.quality.validation.capture_layer3_gy_design_generation_replay --repo-root . --attempts 1 --capture-v3-owner-root /absolute/owned/case --capture-v3-output capture-v3.json
```

The writer does not provision a producer settlement store. Its ordinary standalone
output is **unqualified candidate input**: raw candidate quantities may be present,
but unmanaged/uncommitted settlement leaves replay usage unknown. A successful
write is not runtime PASS or a known-provider-positive witness. The actual CLI
unit exercises that no-store writer -> file -> replay boundary with the current
configured model, separately from qualified in-memory fixture captures.

Destination admission precedes runtime/provider loading. It validates the original
complete physical owner chain without following symlinks, holds its directory
object, and uses no-follow exclusive creation for one basename. Existing files,
dangling links, parent links and traversal names refuse without replacement.
The caller owns the directory exclusively for the operation; this is confinement
to that admitted physical owner, not protection against arbitrary same-UID
interpreter/filesystem mutation. No parent directory is created automatically.

Failures preserve available actual calls/evidence and traceback in a distinct
diagnostic format when a replay input cannot be built. Neither diagnostics nor
successful candidate files prove the producer task completed. The command is
unnecessary for N7's explicit synthetic provider positive and must not be run to
manufacture evidence for historical counters. Old capture/second-domain format
and archive bytes remain unchanged and unqualified. Product CAS usage availability
and public usage surfaces remain outside this testing-only repair.

## Presence-preserving replay projection

Replay serialization reads the selected raw components, not nullable normalized
DTO counters. One Core adapter emits only present canonical components, preserves
invalid present fields, applies alias precedence and leaves an absent/derived
total absent. Qualified canonical quantity/status/total-basis and component
presence therefore survive both V3's wire projection and the actual replay raw
wire. Present invalid values may normalize to an invalid null; this preserves
canonical semantics, not original provider bytes.

The normal Gateway DTO retains its existing numeric convenience defaults and
explicit availability status; it is not evidence of raw component presence.
Unqualified/reuse/legacy input uses the same adapter with a one-way missing
ceiling. That ceiling never promotes availability and never clears invalid; it
also cannot reissue a formerly derived total as a reported quantity. These are
software-input properties, not historical capture authenticity.
