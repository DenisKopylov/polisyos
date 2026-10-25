# Decision requested: reflection contract for 11 supported Fabric signatures

For the 11 supported public-stable Fabric annotation sites whose reflection contract remains unresolved, does compatibility promise that typing.get_type_hints resolves them at runtime, or are annotations only required for static typing unless reflection is separately promised?

## Scope

The question covers these 11 Ruff occurrences on currently supported routes:

- Five connector invalidation API bindings: ConnectionHandle, SourceConnectorValue, ConnectorSchemaContract, EvolutionReport, and ConnectorCacheStore.
- ConnectionConfig on run_streaming_windowed.
- RuntimeTemporalRef and RuntimeTemporalScope on the root-facade TemporalRef.from_runtime_scope API.
- Iterable, Mapping, and Sequence on query_world_table.

ConnectorMetadataSpec is one additional public occurrence whose runtime reflection is already bound by a source comment and two tests. It is excluded from the question. The other two diagnostic rows are internal executor choices: private RuntimeLineageRef, and RuntimeQuantityValue on helpers under the unsupported polisyos.fabric.evidence route.

The evidence subpackage is documented as a legacy compatibility path, but it is not in the owner contract's supported entrypoints. The affected from_runtime_quantity helper is not exported by the stable root facade. The packet therefore does not ask G to elevate that helper's reflection behavior.

## Alternatives

**A — preserve runtime reflection (recommended).** Keep these 11 bindings available at runtime, replace broad TC001/TC003 suppressions with exact rationale-bearing exceptions, and add supported-facade reflection tests.

**B — static annotations only.** Move these 11 type-only imports under TYPE_CHECKING while preserving ordinary runtime use and static checks. This makes get_type_hints fail at the named signatures. G should classify whether this is a public_stable API removal under the existing compatibility policy before implementation.

## Migration and falsifier

Under A, test every named API through its supported facade, then remove only its exact runtime global while retaining annotation text and assert the reflection contract fails. Under B, test static typing and ordinary API behavior and document that no runtime-reflection promise is made for these signatures. Keep the existing ConnectorMetadataSpec behavior and tests unchanged. Leave the two internal rows to executor judgment.

Current isolated probes show the 14 exact bindings resolve and exact global removal raises NameError; this demonstrates present behavior only. It does not prove that behavior is a public contract. The current G packet asks only about the 11 unresolved supported public signatures.

No waiver, expiry date, authority or scientific semantic is requested. G528 IR owner-contract/version answers and G's seven N818 exception-identity choice remain unchanged.
