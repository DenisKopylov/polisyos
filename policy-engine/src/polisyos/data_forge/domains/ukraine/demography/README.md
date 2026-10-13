# Ukraine Demography Artifacts

This package owns typed readers for Ukraine static-aging demographic artifacts.
It is a concrete Data Forge domain package, not an extension placeholder.

## Read one snapshot

The composite `load_demography_artifacts` reader selects one complete snapshot: either
the hierarchical `new` layout (`demography/targets.json` and
`demography/transition_priors.json`) or the flat `legacy` layout. If both complete
layouts exist, callers must select one explicitly. The optional donor file belongs to
that selected layout and may be absent.

The scalar readers `load_reconciled_targets`, `load_transition_priors`, and
`load_donor_pool` accept the same optional keyword-only `layout="new"` or
`layout="legacy"`. Without a selection, each reader can auto-select one complete layout or preserve
its historical isolated single-member read. Supplying `layout="new"` or
`layout="legacy"` requires that snapshot's targets and priors even when the caller
requests one scalar member or only the optional donor. Partial or mixed inputs and
ambiguous complete layouts are refused.

`load_donor_pool` returns `{}` only when no layout is selected and no known demographic
member exists, or when the selected complete layout omits its optional donor. Missing
selected layouts, malformed present members, and mixed inputs raise instead of being
interpreted as absence. When reading multiple scalar members, pass the same `layout`
to each call; use `load_demography_artifacts` when one typed aggregate is preferable.

## Evidence boundary

These readers validate one file layout and the array shapes needed by static aging.
They do not establish an authoritative source inventory, producer identity, custody,
profile, law, currentness, or external approval. The `UkraineDemographyArtifacts`
value is a validated candidate input, not an authority receipt.


## Candidate source-inventory route

The explicit demography_source_inventory stage accepts a request file naming
one existing Ukraine BuildRunManifest, its allowed root, the exact expected
stage, and the upstream output basename selected for each required role.
Only producer-stage outputs are eligible: the recipe reads them through
load_verified_stage_artifacts and load_verified_stage_output_bytes, persists
one inventory output in the existing build root, and the orchestrator writes
the stage BuildRunManifest. The verified-stage read API then snapshots the
inventory into CAS, and the four canonical readers consume that same receipt
through one resolver.

The stage is opt-in and is not included in build_full. D3 remains a different
producer and is never relabeled as the demographic source. The asset mirror
declares one source-inventory node between target/prior/donor inputs and static
aging; the mirror is a catalog contract, not proof that a source materializer
exists.

The producer returns the selected upstream `ArtifactRecord` values through
`StageBuildResult.inputs`. The orchestrator preserves that typed input contract
in the candidate stage manifest. The resolver derives the expected set from the
inventory's verified source receipt and source manifest, compares full record
metadata, and independently reopens each selected output from CAS to recompute
its content hash and size. The membership rule scales with the recipe's selected
role set; it does not encode a fixed output count.

The source-owner facts are a strict, fixed-denominator claim packet. Every
field must be supplied as consumer_asserted or explicitly not_established;
caller data cannot claim independent verification.
State-order and prior-axis equalities against the materialized members are
recomputed. The artifact and all consumers remain candidate_only because no
independent issuer/source-owner verifier establishes truth, authority, semantic
completeness, or currentness. A self-consistent false profile or value mapping
therefore remains candidate-only and is not a source acceptance.

Historical flat and hierarchical readers remain available through the
existing bounded adapter. Their results carry legacy_limited and
not_established source evidence; malformed or mixed layouts refuse, and an
inventory error never retries against filesystem history. A historical layout
that omits entrant_state_totals retains the old zero-shaped compatibility
projection only when its state axis is complete; metadata and source evidence
mark the value as not established rather than measured. A present malformed
field refuses, and candidate inventories still require entrant_state_totals.
The public read_api.ukraine facade exports the discriminated request union and
both request variants so callers can pass one verified inventory receipt to the
three role readers as well as the aggregate reader.


## Public type and compatibility

``UkraineDemographyArtifacts`` is contract v2 and requires ``source_evidence``. The
supported readers attach that evidence; callers that construct the DTO directly or
validate a v1 payload must migrate to the v2 field. No evidence value is inferred
or defaulted.

The individual role readers return ``DemographyRoleProjection``, which implements
``Mapping[str, object]`` and carries typed source evidence. Mapping-style reads
remain supported, while exact ``dict`` checks or callers that require a mutable
reader result must adapt (for a mutable copy, use ``dict(projection)``). Projection equality follows its mapping payload, with source evidence available
separately through .evidence. The projection remains read-only. Historical
selection errors retain their existing categories: ambiguous and partial layouts
raise ValueError, an explicitly missing selected layout raises FileNotFoundError,
and malformed JSON retains its decoder error. A standalone donor read returns an
empty projection only for a directory with no known demographic members or a
selected complete layout without donor; absence intent remains not_established.

The reader
call signatures and supported historical filesystem inputs remain available.

For candidate inventory calls, scalar readers validate all present members
against the aggregate shape contract before projecting one role. A missing
optional donor with ``not_established`` disposition remains absent for target
and prior reads; donor and aggregate reads still refuse it. Explicit
``intentionally_absent`` remains distinct, and a malformed present donor is
decoded and rejected instead of being treated as absent.

### CAS JSON snapshot profile status

Stage and release writers continue to preserve their existing source bytes, IDs, hashes, media types, schemas, and receipts. The selected JSON reader binds those exact bytes to the raw selected manifest. A supported declared Core profile must round-trip before a value is exposed. A profileless stage/release JSON snapshot can be parsed only as a typed candidate with `profile_absent_raw_snapshot_candidate`; the receipt keeps its exact artifact/profile identity and records producer attestation, authority, and currentness as `not_established`. A well-formed unsupported profile is carried raw-only as `declared_unknown_candidate`, without JSON decoding. Malformed-present profiles refuse. This status does not rewrite older manifests or infer historical eligibility. Parquet and opaque hash/basis bytes remain raw transport.
