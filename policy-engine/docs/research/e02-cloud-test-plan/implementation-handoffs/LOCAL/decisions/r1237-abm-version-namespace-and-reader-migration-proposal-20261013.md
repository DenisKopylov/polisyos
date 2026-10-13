# R1237 — ABM version namespace and strict-reader migration proposal

Status: author proposal for independent G; no publication, version ruling, issuer,
or formal closure. This packet accompanies the reviewed R1214/R1227 typed
projection and the real coupled-producer failures in R1183.

## Observed boundary and prototype

The actual Foundry `build_abm_result_from_simulation` passes the complete Core
`SimulationResult.model_dump(mode="json")` into strict IR `ABMResult`. R1183
recorded two failures before the scientific assertions because IR rejected
`execution_input_basis_ref` and `execution_source_status`. R1214 preserves these
fields with a neutral IR ref and the existing Core 1.4 status/basis/feedback
invariants. Independent R1227 approves that source and the corrected four-field
reference identity oracle; runtime acceptance remains for the composed replay.

Existing code has three coordinates: Core's copied payload `schema_version`,
IR's ABMResult reflection/default version 1.3, and outer CAS `ir.abm_result`
artifact schema 1.0. Source: `src/polisyos/foundry/methods/catalog/simulation/dynamics.py`,
`src/polisyos/ir/analytics/phase4_dynamics.py`, and
`tools/quality/diagnostics/gen_schema.py`. These are observations of the current
source, not proof that their cross-version interpretation is ratified.

## Alternatives, impact and migration

1. Wire existing complete projection, retain the three current coordinates for
   the local candidate, and withhold publication until G resolves the persisted
   version boundary. This is the implemented prototype: no field stripping,
   no Core import into IR, no historical blob rewriting, and no scientific
   contract change. Generated consumers must be refreshed. Strict old readers
   can reject extra fields, so this is not forward-compatible publication.
2. Extend the existing outer artifact format with an explicit new version and
   dual-version loader; select legacy emission when fields are absent, reject
   new fields in legacy envelopes, and roll readers before writers. This needs
   a concrete team-ir/G version ruling and matched generator/catalog/ref
   consumers. It is the recommended publication path if the outer artifact
   version is the governed format coordinate.
3. Consolidate the payload version into an IR-owned version plus a separately
   typed Core-source version. This clarifies two purposes but changes public
   DTOs, bridge callers, version selectors, tests, generated clients and archives.
   It is wider than the conversion repair; do not silently substitute it. A new
   projection subsystem adds no needed quantity and is not proposed.

Recommendation: accept or reject the narrow conversion prototype independently
from publication, then rule whether the persisted boundary is outer artifact
version (alternative 2) or a consolidated payload namespace (alternative 3).
The root author will not declare a new release version or a successful migration
window without that ruling. Existing `team-ir` owner and two-minor-release
compatibility metadata come from the repository template/IR diagnostics; they
are not a new external approval or waiver.

## Required decision and discriminating checks

G must name the governed version coordinate and allowed legacy/new emission,
reader rollout order, generated-client compatibility and version owner. The
minimum positive witness is actual Core 1.3 historical and Core 1.4
`single_step_basis` / `feedback_uncomposed` producer payloads converted through IR,
persisted in CAS, then read with a fresh strict reader preserving all four ref
identity fields. The matched falsifiers are wrong-kind/media/profile or missing
basis/feedback, new source fields under a legacy envelope, and an old strict
reader consuming a new emitted payload. Markers must remain while the invariant
is removed. R1214 supplies the current-coordinate round-trip and malformed
controls; new envelope/version controls are required after G's concrete choice.

Generate the actual ABMResult ABI snapshot/catalog, run canonical schema `--check`
and corrupt-field drift, then installed-wheel and rebuilt-sdist consumers on
the chosen format. Record exact source/input/backend freeze and full deciding
outputs. Do not claim generated readiness from this packet or static review.

## Status, authority and time

The projection records selected execution inputs; it does not establish model
calibration, law, source custody/currentness, scientific adequacy, or policy
admissibility. Historical bytes and append-only history are preserved. No
clock shift, blanket exception expiry, migration completion date, issuer
permission, or causal positive is invented. G owns independent code acceptance,
integration publication and formal adjudication. `closure_ids=[]`.

Pattern pass: P01/P02 actual producer→typed IR→CAS→fresh consumer, P05/P08
version and authority/time separation, P29/P32 substantive identity/removal
checks, P38 cross-class model equality is not reference identity, P39 mandatory
release/migration/generated companions outside mechanism budget, P40 batch the
whole version boundary rather than per-reader workarounds.
