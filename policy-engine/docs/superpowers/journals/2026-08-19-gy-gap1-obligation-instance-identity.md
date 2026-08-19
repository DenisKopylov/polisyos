# GY-GAP1 + GY-DEF5 obligation-instance identity journal

Date: 2026-08-19
Branch: `codex/gy-gap1-obligation-instance-identity`
Base: `068aab9df41f2aeebf7b83a80c7939b02d196a5d`

## Entry contract

This lane closes GY-DEF5 first as a claim-only correction, then enters GY-GAP1 directly under the
ratified remove-one acceptance test. It changes no other GY row, writes no revision-frontmatter
entry, and leaves line 7 of the GY plan byte-identical. The base line-7 SHA-256, including its
newline, is `f88d113f34f339f14d333cdd3fe6459cf0e73d449ec3bb5f026567276a14aa37`.

### P39 mechanism / companion split

- GY-DEF5 mechanism: `src/polisyos/pdc/_impl/gy_waist.py` only.
- GY-DEF5 companions: this journal, the GY-DEF5 standing paragraph, the complete repository-text
  census, and the confidence-deployment identity measurement.
- GY-GAP1 mechanism: `src/polisyos/pdc/_impl/gy_waist.py`,
  `src/polisyos/pdc/_impl/layer2_design_search.py`,
  `src/polisyos/runtime/quality/generation_cycle.py`,
  `src/polisyos/runtime/quality/promotion_sequence.py`, and
  `tools/quality/validation/check_layer3_gy_promotion_contract.py`.
- GY-GAP1 companions: focused tests, this journal, the GY-GAP1 standing paragraph, the six
  permitted generated artifacts and their exact-delta declaration, plus all induced hash receipts.
  The confidence artifact is a deliberately deferred companion: it must remain stale for one later
  joint-lane reissue and is not written in this lane.

## GY-DEF5 entry and census

P37 provenance: internal enum/receipt totality is `recomputed`; world-level completeness is
`not_established`. P40 entry: implementation round 0/2. The mechanism is the docstring only; opening,
dissolving, or making the enum discoverable is explicitly out of scope.

Two independent complete scans at the base agreed:

- denominator: 9,873 tracked paths and 9,766 tracked text paths;
- `PromotionObligationClass`: 23 files and 214 literal occurrences;
- enum cardinality: 15 by both AST and lexical declaration scans;
- targeted universal/world-closure assertions: 16 lines in 11 files, with exactly one live
  violating claim—the `Universal N9 obligation-class denominator` docstring. All other matches are
  historical findings or explicit negative controls.

Closure witness: after the edit the live overclaim count is zero, while the enum declaration and
every behavioral producer/consumer remain byte-identical outside the docstring.

## Reconciled obligation population before GY-GAP1

Two independent structural walkers over all 1,170 tracked JSON files (zero parse failures) agree on
26 receipt-shaped objects, 390 obligation records, distribution `{15: 26}`, maximum `(class, gate)`
multiplicity 1, and zero repeated pairs. The earlier 19/285 census intentionally selected only
current v2 owner-bound receipts. The remaining seven receipts / 105 records are v1 historical
recordings preserved under the depth-N universality artifact; the full blast-radius population is
therefore 26/390.

Distribution by persisted artifact:

- depth-N universality: 17 receipts / 255 records (10 current v2, 7 historical v1);
- generation cycle: 2 / 30;
- promotion contract: 3 / 45;
- second-domain cycle trace: 4 / 60.

The real promotion-contract writer independently produced three current verification receipts, each
with 15 records, 15 distinct class/gate pairs, and maximum multiplicity 1. No canonical production
authority receipt is persisted; that population is `not_established`.

## Timing regime before source

All samples below were taken while the Atlas lane was active and are labelled `contended`; none is
promoted into a clean budget. The executor-declared ceiling was 600 seconds.

- Base promotion contract `--check`: validator 30.354552 s, process 47.15 s, success.
- Direct three-run census: 34.27 s, success.
- Fresh-worktree offline setup: tooling non-receipt after 0.99 s because the Python 3.14 `jaxlib`
  wheel was absent from the offline cache; zero tracked bytes changed. The worktree uses the already
  provisioned locked venv by symlink.
- Three-suite focused baseline: terminated at the 600 s ceiling after missing-worktree-data failures;
  non-receipt and not a budget sample.
- Root cause falsifier: after linking the canonical production data read-only, the first formerly
  failing N8 boundary test passed. Its duration remains contended.
