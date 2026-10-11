# Phase 3A public-surface snapshot: version-gated v1 coordinate repair and v2 proposal

Status: local author proposal; no formal G closure or acceptance is claimed.

## Narrow v1 repair

The accepted repository-structure plan §14.6 (REPOSITORY_STRUCTURE_REMEDIATION_PLAN.md
blob 90bebb700b9901c3efb122b1bc3130d6e613b1b7 at the historical refresh tree,
§14.6 lines 1118–1130) defines the Phase 3A snapshot as __all__ plus public
classes, functions, Pydantic models, signatures, and FQNs. The v1 collector adds
an objects[].line source coordinate that is not part of that declared API
property. The comparator first requires the exact top-level JSON schema version
(integer 1, with booleans and numeric lookalikes rejected), then removes only a
recognized v1 object-row coordinate that is a positive, non-bool integer. It
leaves unknown/missing/malformed versions, invalid line values, and unrecognized
row shapes unchanged. It leaves line keys at every other path intact and
compares kind, name, fqn, bases, pydantic, signature, __all__, module identity,
package identity, and list membership as before. The historical baseline remains
byte-for-byte unchanged.

The falsifier is paired: adding blank lines before an unchanged definition
changes the collected object line and must keep the focused Phase 3A comparator
green; changing a parameter, object kind or FQN, class bases/Pydantic status,
exports, or deleting a public object while keeping its __all__ marker must make
the same comparator fail. A line value elsewhere in the snapshot must remain
load-bearing. This is a narrow compatibility repair for the existing v1
coordinate, not a new public-API policy.

## Version-gated scope and observed escapes

The first virtual patch used object-row shape without checking the document's
schema version. An independent gate probe found the same row shape in a v2 or
unversioned document; shifting only its line coordinate then compared equal.
A later independent V1 review found that line zero was also treated as a valid
coordinate and stripped. These are the same historical-snapshot ABI-proxy class
one level deeper (P40), not new classes. The mechanism now requires an exact
top-level JSON integer version of 1 and a positive non-bool integer line before
normalizing the recognized v1 row. Version 2, absent, boolean, float, string,
other malformed versions, line zero/negative/malformed values, and unrecognized
row shapes retain their data. Paired controls cover those cases and the real
temp-source collector fixtures set REPO_ROOT=tmp_path.resolve() and
SRC_ROOT=(tmp_path / "src").resolve() so _rel and module path resolution stay
inside the fixture root. Product path resolution is unchanged.

## Source provenance and recipe

The current v1 baseline is the committed blob
architecture/baselines/structure_remediation/public_surface_pre_decomp.json
at Git blob 4198448d810b49c95753f98b4cab28666ef96b05, present at refresh commit
e2f01782679d65f7211a1bef335e01e540261e10 (tree
58ed437ed131a1fd4c3d3084ba05cece731eab2f). Its generated timestamp is
2026-06-14T06:21:47.482093+00:00. At that exact tree, the collector is
tools/quality/validation/decomposition_preflight.py, blob
7f08dc882fb3736d62dfd25f4f19ecb066c968db. It emits direct public definitions
at lines 574–636; _signature at lines 656–660 serializes only node.args.
The accepted plan at that tree is blob 90bebb700b9901c3efb122b1bc3130d6e613b1b7,
section 14.6, lines 1118–1130. The baseline first entered the reorganized
tree at 7acba2e4e1b3c113e0d428786ed6e80db93ebdce with an earlier schema; it was
refreshed and reshaped at e2f0178.

The current candidate preimage decomposition_preflight.py SHA-256
526a0a8e0a2c5d5bf7c0249ad21aac66740940cd5ce444b378346d16076c2aed has an
additional alias-resolution collector path (_collect_public_surface_bindings,
_resolve_public_surface_definition, _public_surface_module_objects) absent
from the historical collector. That is a separate source-scope delta and may
add object rows the historical baseline does not contain. The coordinate patch
does not normalize away those additions. Replay the historical gate against
the final frozen collector before reporting green; the focused same-collector
fixture proves only the coordinate behavior.

The available generator is uv run python tools/quality/validation/decomposition_preflight.py generate.
It regenerates several Phase 3A artifacts together, including imports, fixtures,
schema/import-time baselines, and the blueprint. It is not a safe baseline-only
recipe. No historical baseline bytes are regenerated here.

## P40 bucket and residual property

This is the same historical-snapshot ABI-proxy class one level deeper: the
first patch keyed source-coordinate removal to row shape but omitted both the
schema-version discriminator and the positive-coordinate constraint. Widening
the mechanism once to require exact v1 schema plus a positive collector line is
the smallest honest class repair. Unknown versions, invalid coordinates, and
unrecognized shapes stay fully load-bearing. Per-version exception lists or
baseline regeneration would repeat the class of error.

The v1 whole-property residual remains explicit. _signature omits return
annotations: def f(x: int) -> str and -> bytes currently produce the same
signature. Class rows record bases and a Pydantic boolean but not constructor
signatures, public class fields, or Pydantic field definitions. Therefore v1
cannot claim complete Python ABI detection. This packet does not extend v1 or
silently accept return-annotation changes.

A return-only source prototype is the v2 falsifier: with the same name and
parameters, changing -> str to -> bytes must change a canonical v2 record.
A minimum v2 contract must separately specify and test parameter kinds,
defaults and annotations, return annotations, class call/constructor shape,
public fields/model fields, and re-export identity. Use static AST extraction
where sufficient, and explicitly bounded runtime/type semantics where not; do
not claim whole-ABI coverage from one return string.

## Migration choices for independent G adjudication

1. Keep v1 plus the exact-coordinate normalizer (recommended local repair).
   The historical baseline and v1 authority remain intact; v1 detects only the
   fields it actually records. The bounded constructor/return/field gap remains
   visible. Alias-collector scope changes are assessed independently.
2. Regenerate the v1 baseline. This moves the reference point and can absorb
   actual API changes. It changes the historical gate evidence and needs
   explicit G authority; it is not used here.
3. Introduce a separately versioned v2 contract and baseline. Keep v1
   read-only during migration, generate v2 from an explicit accepted freeze,
   run both gates, and switch or retire v1 only after G accepts the v2 property,
   producer, baseline provenance, and migration. This is the proposed path to
   closing the whole-property residual, with a separate owner/authority
   decision before implementation.

Prototype/falsifier evidence: current v1 _signature is ast.unparse(node.args)
only, so return-only changes are not observed. The minimal v2 prototype
ast.unparse(node.args) + " -> " + ast.unparse(node.returns) distinguishes
-> str from -> bytes. This proves the v1 gap and one return discriminator, not
full class/API coverage. G's next check is whether a separate v2 gate is
warranted and who has authority to freeze its baseline; until then the v1
coordinate patch is independent of that choice.
