# Normative generation disposition v2 migration

S8 disposition CAS writes now use the internal
`policyos.normative_generation_disposition.v2` envelope. It carries the unchanged
`NormativeGenerationDisposition.v1` historical projection and the N6 currentness
observation used for that admission. The public HTTP projection remains v1; no
OpenAPI or generated-client update is required.

## Reader and writer order

Deploy a reader that understands both disposition artifact epochs before enabling
v2 writes. The reader verifies the CAS content hash, artifact kind and schema,
canonical bytes, inner v1 projection, source-run binding, and the persisted
currentness-to-source identity binding. It replays the historical projection
without consulting the live Confidence Ledger. A separate current projection
reads currentness again before any S8 authority decision.

V1 artifacts remain immutable and replayable as history. Because v1 did not
record admission currentness, its currentness is `not_established`; it cannot
establish current S8 authority or support an authoritative evidence-head
transition. A v2 artifact admitted with stale or unestablished currentness stays
blocked even if a later observation is current. Reissue only through the
authorized owner transition with its new premise recorded.

## Rollback

Keep the v2-capable reader deployed while any v2 artifacts exist. A v1-only
binary cannot read the v2 envelope and must not silently interpret it as the
inner v1 projection. If rollback is required, roll back to a release that reads
both v1 and v2. Retain the original CAS bytes; do not down-convert v2, rewrite a
v1 artifact, bulk-migrate records, or restamp a receipt. No bulk migration is
needed.

The persisted observation is typed evidence from the existing Confidence Ledger
owner; it does not appoint the deployment-identity issuer or N6 census issuer.
An absent issuer or census remains `UNRUN` and blocks current authority while
ordinary candidate computation remains available with its limitation declared.
