# B108 vector score-source carrier and schema decision packet

Status: author candidate for independent G decision; no formal acceptance or closure is asserted.

## Property and defect

A policy-vector scalar may enter search ranking, training, selection, or a persisted Pareto frontier only when the selected channels and their source binding can be recomputed from a carried source basis. The previous `source_kind="objective_stack"` label admitted a scalar without a source payload. Persistent registry entries retained a vector but not a source record, so current-source-only checks either trusted self-labels or lost every frontier score.

## Reuse-first alternatives

1. **Reuse `ObjectiveScoreAssessment` alone.** It already carries the rule and channel operands, but its source values are derived from the vector and do not bind the emitted runtime result or the runtime attempt. It cannot detect a removed or changed source result in the persisted consumer path.
2. **Extend the vector with a compact source projection (candidate).** Add `score_source` containing only the emitted `objective_channels` and the four existing runtime attempt/configuration fields in `bootstrap`. Bind that projection hash into the existing score assessment; compare it against the actual stage result when present; verify runtime metadata against the emitted bootstrap fields. Consumers of persisted vectors can recompute without copying the full simulation payload. Bump the artifact schema from 1.0 to 1.1. Old 1.0 vectors remain readable as diagnostic data, but cannot enter score consumers without the new source basis.
3. **Consolidate into a separate score-basis CAS artifact.** This adds an artifact, writer, reference, resolver, and joins in the Pareto/transfer/VOI consumers. No existing shared owner requires this separation; it increases bridge failure points.
4. **Build a new scoring authority or objective framework.** Rejected for this candidate: it would change the existing scalar rule and risk inventing units, weights, or authority. The implementation preserves the existing arithmetic and uses source binding only for availability.

## Impact and migration

- New output schema: `polisyos.scientist.policy_design.PolicyEvaluationVector@1.1`.
- Readers continue to parse 1.0 payloads because the new field is optional. A 1.0 vector lacking source context remains available for display/diagnosis but is unranked, excluded from training, and excluded from benchmark selection and frontier admission.
- No old artifact is rewritten, backfilled, or assigned new provenance. New runtime producers bind their emitted source result before returning the vector.
- Source binding establishes input agreement and score completeness only. It does not establish calibration, causal validity, scientific authority, or production currentness.
- Candidate status: prototype implementation in this RAW patch; independent review, composed consumer replay, schema/public-surface regeneration, and G contract acceptance remain pending.

## Prototype and falsifier

The source projection is content-hashed into the score rule. The expected discriminators are: valid numeric zero remains available; absent/empty channel maps do not create zero; changing or removing an emitted channel fails; changing or stripping runtime invocation/bootstrap binding fails; a valid sibling remains rankable when another candidate is unassessed. These are authored in the candidate tests but have not been run in this RAW lane. The decisive runtime check is the native policy-runtime producer followed by CAS reload, `PolicyEvaluationVector` reconstruction, `ParetoRegistry` projection, and selection benchmark admission with the removal variants.

## G decision requested

Confirm whether schema 1.1 is the accepted compatibility boundary for source-bound vector scoring, or specify the existing repository migration convention that should replace it. Until then, new code is a review candidate; existing unbound 1.0 inputs remain unscored and no formal closure is proposed for B108.
