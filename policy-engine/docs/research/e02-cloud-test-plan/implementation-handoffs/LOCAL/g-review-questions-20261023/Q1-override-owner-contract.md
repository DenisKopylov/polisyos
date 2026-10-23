# IR-Q1 — Shared producer/write and reader owner law

**NEW architecture question; not code acceptance.** This asks about an existing public API's semantics and its migration, not permission to fix plumbing.

## Decision requested and recommendation

Select how the owner contract governs `schema_name` and `schema_version` overrides on producers and the corresponding shared admission on readers. The census identifies 70 distinct producer functions with both keyword overrides among 84 missing-declaration typed rows; all five already centrally enforced typed producer rows are overrideable too. Their defaults identify a default, not the full supported range.

**Recommend extend-existing:** put nonserialized typed owner metadata alongside the existing typed ref; use one owner resolution on both persistence and shared reading. Admit only explicitly supported identities or owner-validated extensions. Preserve the callable keyword signature where useful, but **narrowing accepted keyword values is a behavioral compatibility break even when that signature stays unchanged**. G should select the rollout rule; accountable owners supply the accepted identities and genuine historical artifacts.

## Alternatives and tradeoffs

| Route | Behavior | Impact |
|---|---|---|
| Reuse defaults as a closed list | Readers accept only today's producer defaults | Rejected: invents an allowlist and can reject artifacts the current public writer emits |
| Extend typed owner contract (recommended) | Same owner validates writes and reads; owner versions/aliases/extensions explicit | Fits current refs and shared intake; requires a coordinated compatibility migration |
| Preserve open extension API under an explicit owner resolver | Named extension contracts/validators bind each admitted override to a real owner law | Preserves extensibility but needs actual owner law; arbitrary strings/self-labels remain insufficient for authority |
| Consolidate central registry | Registry owns identities, version lifecycle and migrations | Consider only if existing typed refs/migration registry cannot own needed lifecycle; avoid a second source of truth |
| Build new schema governance subsystem | Separate service/platform | Present evidence does not justify this scope |

The two known-owner generic selectors need a narrow bridge into the same owner contract, not a parallel intake. Fourteen constant-only producer rows can be wired independently where owner source establishes their law; this does not resolve the 70 overrideable rows.

## Footprint, compatibility and rollout

Owner declaration: `src/polisyos/ir/registry/refs.py`. Shared admission: `src/polisyos/ir/artifacts/contracts.py` and `io.py`. Producer/consumer functions and exact source hashes are in the [complete residual census](remaining-93-callsite-census.csv). Mandatory companions include typed facades/exports, migrations, DTOs, schemas/catalogs if affected, all importer tests and history fixtures. Reuse `get_json_artifact`'s public signature; do not change CAS byte/hash/profile resolution or G resource resolution.

Nonserialized class metadata should leave DTO/ref wire bytes unchanged. A rejected formerly accepted override is nevertheless an API behavior change. Prefer reader-first rollout: establish owner-supported historical identities/aliases, upgrade consumers, then enforce writer admission and eventually retire explicitly named compatibility routes. Do not relabel old manifests, rewrite CAS, or infer a historical supported set from defaults. Unknown current/historical facts remain explicit; no silent conversion, loss of fields or blanket grandfathering into authority. A candidate unknown may remain declared under S0-K06, but cannot become authority-grade by the presence of a ref.

Schema identity/version, byte/content conformance, selected profile, provenance and valid/current time are distinct predicates. Schema version is not event time; a digest establishes neither owner authority nor currentness. Malformed supplied identity must refuse, not become absence/default.

## Input and decision boundary

G selects shared write/read ownership, open-extension versus finite declarations, and migration behavior. Producer/DTO owners supply supported current and historical names/versions, override consumers, retired aliases and actual artifacts needing compatibility. G's architecture choice cannot supply those facts. Until they exist, scope the admitted cohort precisely; do not stamp defaults onto the remaining 70 rows or claim the 93 residual callsites closed.

## Deciding prototype/falsifiers — UNRUN

Use actual producers for supported current/historical writes and fresh shared readers. Exercise plausible nondefault overrides. Every emitted supported artifact must read under the same owner law; unsupported values must refuse before persistence. Same-kind JSON with wrong media/schema name/version must refuse before `get_bytes` (counter stays zero). Then delete validation but retain declarations/markers: semantic tests must fail. Also probe present-malformed input, sibling generic selector, and profileless historical rollout without inventing producer attestation. These proposed question-specific runtime probes are **UNRUN**.

**Requested G output:** selected route, accountable owner location, whether/how existing overrides remain supported, reader/writer rollout and retirement condition, status/authority consequence, and exact acceptance signal. Root implements the selected mechanism and all companions; independent code acceptance remains G's.
