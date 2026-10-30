# Data Forge read API facade

polisyos.data_forge.read_api declares a finite module facade in __all__ and
its TYPE_CHECKING imports. surface_routes.py owns the lazy module routes and
the summaries consumed by surfaces.py; requesting an advertised module loads
only that selected route, while unknown names continue to raise AttributeError.

The route table covers the six modules declared by the facade: academic,
catalog, compliance, legal, provenance, and ukraine. The surfaces helper
module is imported eagerly and exposes metadata and explicit load helpers.
Symbol exports continue to use the existing _EXPORTS mapping in __init__.py.

The facade previously advertised compliance and provenance through __all__ and
TYPE_CHECKING while omitting those module attributes from the runtime route map.
The route map now matches the complete declared module set. This restores the
declared import behavior; it does not add a supported public-surface contract
entry. architecture/public_surface/contract.toml remains the authority for
supported-surface guarantees and does not list compliance or provenance, so
their supported status remains not_established.

The repository guardrail uses bounded static source analysis to inventory
curated entrypoints and declared export routes. Dynamic reflection and
profile-dependent exports remain outside that proof. Source analysis alone does
not establish installed-wheel behavior, runtime origin, or a public API claim.


## Ukraine observation periods

`polisyos.data_forge.read_api.ukraine` exposes the experimental
`project_ukraine_observation_periods(values, *, time_grain)` function and
`UKRAINE_PERIOD_PROJECTION_VERSION`. Pass a pandas `Series` of normalized
period identifiers and a declared `polisyos.ir.TimeFrequency` (`M`, `Q`, or
`Y`). The function returns four aligned string series: inclusive start, inclusive end, disposition, and reason.
It preserves the input order and index, including duplicate labels. The version
names the projection rule; it is not the source's version or proof of the
original artifact's schema.

The dispositions are `valid`, `missing`, `invalid`, and `limited`. Missing,
malformed, or insufficiently precise identifiers have absent bounds; `limited`
includes a year or quarter that cannot determine a requested month. Their reasons
are `period_identifier_missing`, `period_identifier_invalid`, and
`period_precision_insufficient`, respectively. A valid result has an absent
reason. The selected Ukrainian normalizers retain unknown period values instead
of substituting a date, and preserve annual and quarterly precision rather than
selecting a month. A source's finer-than-declared period convention and original
per-record date lineage are not established by this projection.

D2 observation frames and D3 calibrated household cells carry normalized period
identifiers, projection fields, and the projection version. The Scientist D4
consumer recomputes those fields from the available identifier and rejects
inconsistent declarations. Legacy D3 cells with an identifier can be recomputed
in the consuming view; an old D2 panel without an identifier remains
`not_established` for new exact signoff. Rebuilding affected observations must
use their actual source and provenance; it does not rewrite historical artifacts
or establish that a source remains current. Annual and quarterly source profiles
need their own grain and consumer requalification.

A D2 pre-publication reader failure cannot use an unbounded full-frame fallback
when the decoded allocation and concurrent residency are not bounded. The failed
stage records the underlying error and confirmed partial scratch counts and
paths with scratch integrity `not_established`. Each observation member is
copied in bounded chunks to a private temporary file, whose actual bytes must
match the source's pre-copy SHA-256 before the first batch. The initial reader
and any restart read that same file. The copy is capped at the opened source's
initial size, checked against the D2 disk hint when supplied, and admitted only
if the temporary filesystem has enough free space with a reserve. The disk hint
bounds this copy, not the stage's cumulative disk use. Each iterator holds one
member's copy at a time; it is removed on completion, failure, or generator
cancellation. Concurrent disk use can still cause a write failure, and a
memory-backed temporary filesystem can charge the copy to memory.

Small self-generated Parquet tests cover mutation, replacement, and ABA during
streaming and retain the downstream shard and verified-read checks. They do not
establish production-size resource behavior, a successful full-read profile,
producer authenticity, source currentness, an atomic multi-member generation,
or promotion eligibility. Since the pre-copy digest itself comes from the
mutable path, matching reads do not prove that even one member was captured
atomically from a single producer generation.


## Catalog source failure family

`catalog.CatalogReadSourceError` extends `CatalogSelectionError` for actual
native read-source failures. It carries the exact existing code/detail, while
consumers classify by ancestry rather than an enumerated reason prefix. Store
source identity/session operations use this family for unavailable/changed
bytes and uncheckpointed WAL. Existing selection-error catches remain valid.
The formerly raw open-change ValueError is now this typed failure with
`catalog_read_source_changed_while_opening`; its legacy detail is retained.
Source failures must not become absence or best-effort provider fallback.
This experimental facade addition needs root's ordinary public inventory and
installed-reader qualification; it grants no source authority or currentness.

Escaped native DuckDB query/backend errors also use this typed read-source
family (`catalog_read_native_query_unavailable`); a closed backend is ERROR,
not evidence of zero observations. The original driver exception is retained
as the cause.

## Historical acquired source replay

The catalog facade exposes the existing `derive_canonical_observations` owner
and `normalized_acquisition_source_body`, which delegates to the same normalized
FetchResult codec used by live acquisition authority. Runtime historical
candidate replay uses these existing transformations after resolving the exact
source/passport/boundary bindings; it does not invent a second row parser or
claim present native admission from a historical source. Unsupported cache
formats remain a typed refusal.

The runtime-safe facade exposes the existing publisher JSON reader plus
`prepare_publish_manifest`, `prepare_snapshot_binding_meaning` and
`read_snapshot_binding_meaning`. Runtime candidate preparation uses these owner
constructors instead of recreating finalization law or treating generated hashes
as effective source meaning. Historical binding projection rechecks full emitted
values before any owner-generated occurrence field is projected.
