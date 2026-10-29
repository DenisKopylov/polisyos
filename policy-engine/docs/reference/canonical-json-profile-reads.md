# Version-qualified canonical JSON artifact reads

Core and IR share canonical mechanics and retain separate native type policies.
A declared canonical version is an interpretation input, not evidence of producer
authenticity, authority, currentness or cohort readiness.

| Selected read | `.2` | Explicit `.3` |
| --- | --- | --- |
| Core JSON artifact, async, bounded and frame readers | `core-tag-policy@1` | `core-tag-policy@2` |
| Generic IR JSON artifact reader | `ir-tag-policy@1` | `ir-tag-policy@2` |
| Common parser with omitted `supported_versions` | Default model version | Remains unknown candidate |
| IR owned callback path | Historical qualified decoder | Refused before payload/profile callbacks |
| Core/IR artifact writers | Existing admitted behavior | Retained writer fence |

Concrete generic readers explicitly pass their supported version tuple to
`parse_canonical_profile`. The parser still requires all profile fields and
validates them strictly. Other declared names/versions remain unknown candidates
in the Core inspection path; a trusted-value consumer must require a declared
conformant read. IR's generic trusted JSON helper refuses unsupported profiles.
Complete flags and exact selected manifest/payload identity remain load-bearing.
There is no wrapper-based version guessing.

Under `.3`, an ordinary mapping containing exact `_type` is structurally escaped,
retains all entries including nulls, and reconstructs without native tag redispatch.
This includes nested and escape-shaped raw maps. Core native `bytes_hex`, finite
`float_hex` and `array_digest` envelopes return their owner representation carriers,
not ordinary primitives. The float carrier preserves signed zero; the array
carrier describes supplied dtype/shape/digest and does not attest array contents.
Raw maps of those same shapes remain maps. IR refuses the unescaped Core-only
native descriptors while preserving their escaped data forms.

`CanonSpec.max_depth` remains logical value depth. The bounded Core artifact
reader's `CoreJsonReadLimits` independently bounds raw manifest bytes and actual
payload wire bytes, lexical container depth and nodes, including escape overhead.
It requires a supported size-known bounded backend and does not substitute an
unbounded byte/member read. Async and frame APIs retain their existing
materialization/resource contracts; accepting `.3` does not make those bounded
APIs or establish a process-memory guarantee.

No stored `.2` bytes, IDs, hashes, named hash domains, exception identities or
unqualified default interpretation are rewritten. The optional Common parser
keyword is additive; its omitted behavior is unchanged. To read an explicit `.3`
artifact, retain its complete profile and exact selected view and use a qualified
reader. Rollback must preserve those reader capabilities while writers remain
disabled. An old `.2` collision does not reveal whether its origin was a native
value or a raw mapping; do not reinterpret historical origin by guessing.

Generic read qualification does not enable IR owned callbacks. Their snapshot
path uses `.2`, and a registry readable flag or `validate_profile=True` cannot
prove that callback codec was migrated. It likewise does not enable persisted
`.3` writers, state/checkpoint or Foundry/cache/idempotency cohorts. The next owner
must bind its real resource policy and ready reader/rollback cohort before effect.
Fabric CAN.2 rows and TC's accepted `.2` artifacts remain independent.

Runtime acceptance, installed/no-checkout proof, property-removal witnesses and
G acceptance are separate from this source contract. The current reader proposal
requires those deciding outputs before a runtime PASS claim.

## Explicit method-sidecar writer cohort

The ordinary `FileSystemCAS.put_json` default stays `0.2.0`; explicit generic
`0.3.0` writes remain fenced. A caller may explicitly request the existing
Foundry execute sidecar path with `artifact_output_codec="bounded_v3"`. This
source-local policy covers only MethodArtifactOutputPayload@1.0 in the stock
local unsigned CAS without telemetry, quota or custom/enforced owner callbacks.
There is no automatic writer enablement from a manifest, policy label or ready
flag. Core revalidates the source policy and actual selected reader behavior
before publication. Other cohorts remain unqualified.

The sidecar preserves ordinary raw `_type` mappings recursively, including
escape-shaped maps and explicit nulls. Its declared value domain is exact JSON
builtins, finite floats except signed negative zero, nonempty exact string keys,
1,024 logical payload nodes/depth 8 and 4,096-bit integers. It refuses unsupported
models, callbacks, native Decimal/bytes/carriers and tuple before their
materialization. The physical bounds are separately 65,536 wire bytes, 7,178
wire nodes, container depth 28 and 4,096 manifest bytes. Aggregate/ref limits
remain 4 MiB/8,192. Refusal keeps an explicit unavailable artifact row with no
`.2` fallback; inventory completion does not promote unavailable sidecars.

`polisyos.foundry.execute.read_method_artifact_output_bounded` and Core's generic
source-policy bounded reader accept the exact selected output ref independently
of writer enablement. Fresh ArtifactInspector content/schema previews use the
public Foundry reader for this cohort after complete owner/profile admission.
Their first manifest read now enforces the existing Inspector manifest budget;
over-cap or unbounded-only backends fail before loading. Successful qualified
`.2` preview behavior is preserved. Raw `put_bytes` import remains distinct from
owned canonical production. Installed/no-checkout and full rollback qualification
are separate release evidence; source conformance establishes neither authenticity
nor external readiness, authority, whole-Q1 completion or G acceptance.

The writer's plain DTO domain excludes all nested or recursive Pydantic models;
no child callback is qualified by a root model declaration. Its source metadata
and complete actual manifest projection are wire-preflighted without JSON output
materialization before the final serializer. These are recomputed properties,
not readiness labels. Existing `.2` owned-reader metaclass compatibility remains.

Inspector recognizes the known Method kind or source schema before payload
loading, including joint kind/media substitutions on a selected same-ID view.
It refuses malformed Method cohort selectors on both content and schema surfaces.
Unrelated non-JSON selected cohorts may still expose raw text/bytes and metadata
with `canon_read_status="not_evaluated"`; this does not interpret or admit their
canonical value. Unknown JSON `.3` semantic inspection remains refused. This
uses CAN-01's purpose-scoped raw/unqualified boundary and does not globally
disable existing raw inspection or confer producer authenticity from a label.
