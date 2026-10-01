# R9 canonical ID checkpoint — 2026-10-01

## Discrepancies and boundary

This is a bounded repair, not R9 closure. The corrected fixture now reaches
public verification: issuance returns 201, then verification returns 200 with
`report_authentication=invalid`. Earlier public-export cells stopped in fixture
setup and do not establish attribution of this served failure. Four CAS-03
failures still expose repeated manifest reads, eager explicit input consumption,
cancellation and eager default inventory. B152/B154/B155 remain partial.

## Property and implementation

Public blob-ID projections and signature batches identify typed IDs by their
canonical content identity. `ArtifactID` is intentionally unhashable; constructing
Python sets of its instances was the wrong predicate. The existing CAS owner
now deduplicates by `.hex`, preserves typed return values and orders the public
projection by that identity. The full inventory retains both default aliases
and exact selected manifest views. The test uses two blobs and three manifest
views: five inventory entries project to two unique blob IDs.

P38 limitation: this normalization still materializes a complete input sequence;
it proves identity and order, not bounded consumption. The approved next repair
extends the existing scheduler and snapshot reader. It does not create a second
CAS owner. Synthetic publication setup and direct custody reads now enter their
existing tenant scope; HTTP requests execute after that scope has exited.

## Deciding evidence

Tests ran at candidate HEAD `324eb3d2fbc5f0ad1af80495ebac469ecc6762b4` with
the frozen working patch. It was subsequently preserved as immutable candidate
`d66327d876c1b6453976a71202db845c7a270600`, containing exactly four paths.
Its parent-to-checkpoint patch is
`/Users/deniskopylov/.codex/scratch/R9_D663_ROOT_INTEGRATION.patch@sha256:69b7e2efdb0ddba0ecf65175c8b6c43ec82434e943b046d081086d6809b5c6d6`.
Root verified each canonical preimage equals the candidate parent, and each
committed candidate image equals its reviewed freeze. No source changed while
tests ran. This receipt accompanies integration; candidate results below are
not relabelled as a fresh integration run.

Three whole files produced 27 testcase outcomes: protocol 10 pass; CAS-03
5 pass / 4 fail; public export 3 pass / 5 fail, with zero setup errors. All three
origin audits passed, all 6,414 tracked Python/config inputs stayed unchanged,
and no resource guard fired. Root verified all nine raw JUnit/stdout/stderr
hashes and the three origin hashes:
`/Users/deniskopylov/.codex/scratch/R9_V5_ROOT_WHOLE_FILE_RECONCILIATION_20261001.json@sha256:cc2d1fbe9f584c8bb63ba22e41200c3f49c632a62924913218ba55e6f4dd8dd4`.

The removal probe temporarily replaces only the canonical dedup helper, keeping
source markers and call sites. Of two selected tests, the duplicate-ID witness
fails with `total=2` instead of 1; the distinct-ID preflight-error control passes.
Source and origin checks pass. The first adapter compared shorthand `fail/pass`
with the harness's `failed/passed` and incorrectly labelled the probe; raw JUnit
is preserved and the root correction records the actual successful probe:
`/Users/deniskopylov/.codex/scratch/R9_FIXTURE_SCOPE_RUNTIME_GROUPS_20261001/removal-probe/run-20261001T044421579302Z/ROOT_VERDICT_LABEL_CORRECTION.json@sha256:4a603e539125b264e32362d77e7c2ffc3891410725e65a2e30f04b89c31279f4`.

Independent runtime review gives bounded GO and explicitly withholds class
acceptance:
`/Users/deniskopylov/.codex/scratch/R9_FIXTURE_SCOPE_FREEZE_20261001T042447Z/INDEPENDENT_CHECKPOINT_RUNTIME_REVIEW.md@sha256:cae2c9d4b6b2970d4bcaca4fb88d95c5250326bf3f3b4e00945a8da6acbd6c0e`.

## Remaining owners

- CAS signature scheduler/snapshot owner: B152/B155 bulk and read reuse repair.
- Governed public verification owner: the served invalid receipt, with its
  actual refusal reason to be measured before any fix.
- Root test broker: fresh integration replay and the complete touched-file
  four-base denominator. Neither this checkpoint nor its two-case probe
  completes that denominator.
