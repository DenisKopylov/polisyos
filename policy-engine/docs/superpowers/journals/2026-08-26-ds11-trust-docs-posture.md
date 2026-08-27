# DS11 C00 execution journal — 2026-08-26

## Admission and scope

- Execution entry: `8e5832bbdb0f206b6221112f4a1502b45981bd40` on attached
  `codex/ds11-trust-docs-posture-plan`; prefix is empty at repository root and
  `policy-engine/` at product root. The immutable policy-source base remains
  `f935e0c2e9359bc1202ce5d36ea706de58f7aaab`.
- Recorded ancestry: DS9 `fd243d1ad` and DS6 `176276ef0` are ancestors of the
  execution entry. Branch prefix: `codex/`.
- User-approved execution amendments: hard slice mechanism ceiling `34` (sum
  is `26`, slack `8`, widening ceiling `9`); CC09 is tested in both
  directions. The later real page-a11y receipt corrected the supplied
  `21/24`/three-failure baseline to `20/24` and
  [DS11-A11Y-BASE-FAILURE-SET-4](../../plans/active/atlas-slices/DS11-trust-docs-posture.md#ds11-a11y-base-failure-set-4):
  color-blind distinguishability, run-report axe `dlitem`, runs-list
  screenreader missing `Open run`, and run-report screenreader missing
  `Export JSON`. This is a P35/P41 measurement correction, not a DS10 repair.
- Pattern pass: P01/P02/P05/P10/P29/P35–P41. DS11 remains
  `absent/unallocated`; C00 adds no product contract, producer, bridge,
  consumer, source metadata, or production/tooling mechanism.
- Path/round accounting: `0/0` C00 mechanism paths; one red-test/register
  transaction; `0/9` widening. P39 companions are the plan, this journal,
  two red test witnesses, debt register/ledger, and page-a11y receipt set.

## Complete-set entry census

The two stated derivations and known witnesses are preserved from the approved
execution plan and remain source-disjoint from C00 (which changes no `src/`
or dashboard production source): raw `authoritative_for` is `104` Python files
partitioned `66/5/5/27/1/0`; exact field is `103`; direct literals are
`35 sites/13 files/21 non-empty subjects`; wrapper-inclusive literals are
`59/24/28`; `may_not_use_for` is `116` Python files and its bounded literals
are `34/22/44`; anti-roles are `7` including CRM; dashboard is `14` immediate
directories and `17` entries; exact typed status-language files are `26`; the
RuntimeClaimRegistry vocabulary is `33` files; Trust View has exactly two
roots. The independent derivations are respectively AST vs token/raw-source,
`rg` vs pinned `git grep`/archive, and filesystem vs pinned tree walk. Known
witnesses: `best_snapshot.py` is the `authoritative_for_runtime` collision,
`foundry/welfare/frontier_emitter.py:144` anchors `may_not_use_for`, and
`src/polisyos/runtime/quality/claim_registry.py` is the distinct per-run
registry owner. The supplied dashboard `16/29` claims remain non-reproducing;
no C00 constant encodes them.

## Gate and command receipts

All commands ran with `/usr/bin/time -p`, with `uptime` immediately before and
after. `user + sys` is the completed-command ceiling measure.

| command | exit | completed user + sys | uptime pair | standing / writer |
| --- | ---: | ---: | --- | --- |
| `corepack pnpm install --frozen-lockfile` | 0 | `0.96 + 0.32 = 1.28s` | `18:20` -> `18:20` | no writer; frozen install current |
| `uv run polisyos-tools architecture guardrails check` | 0 | `40.74 + 41.67 = 82.41s` | `18:24` -> `18:26` | no writer; generated freshness clean |
| plain `lint_imports.py` policy/exceptions command | 1 | `0.75 + 0.28 = 1.03s` | `18:26` -> `18:26` | no writer; `84 + 4 = 88` inherited red |
| package-import exact slice-base replay | 1 | `83.89 + 4.49 = 88.38s` | `22:40` -> `22:42` | exact `f935e0c2e` JSON `finding_count=143`; the earlier 142 is invalidated as a shared-source-root reading; no current-branch count is claimed; known member `polisyos.runtime -> polisyos.runtime.quality` |
| frontend disposition `--check` | 1 | `195.14 + 27.53 = 222.67s` | `18:33` -> `18:37` | no writer; only `c13_print_receipt_invalid:.../RunDetailLayout.tsx`; transaction ceiling `445.34s` |
| page-a11y JSON replay A | 1 | `212.21 + 29.76 = 241.97s` | `18:28` -> `18:30` | no product writer; `20/24` and [DS11-A11Y-BASE-FAILURE-SET-4](../../plans/active/atlas-slices/DS11-trust-docs-posture.md#ds11-a11y-base-failure-set-4) |
| page-a11y JSON replay B | 1 | `287.42 + 40.22 = 327.64s` | `18:32` -> `18:35` | semantic/result observation `20/24` and [DS11-A11Y-BASE-FAILURE-SET-4](../../plans/active/atlas-slices/DS11-trust-docs-posture.md#ds11-a11y-base-failure-set-4) is `consumer_asserted` / `not_established`, so cannot support a semantic product gate or posture row. Separately, `/usr/bin/time -p` supplied completed-process `user` and `sys`; the harness recomputes the operational-only ceiling `2 × max(241.97, 327.64) = 655.28s`. That predicate may set only a harness timeout/stop budget, never product semantics or another gate. |
| debt report-only check | 0 | `0.43 + 0.35 = 0.78s` | `18:28` -> `18:28` | no writer; pre-write DS11 omissions and ledger drift observed |
| debt ledger writer | 1 | `2.01 + 2.05 = 4.06s` | `18:30` -> `18:30` | sole register-family writer; all DS11 rows rendered; inherited denominator mismatch `92 != 102` remains |
| debt ledger `--check` | 1 | `1.05 + 0.99 = 2.04s` | `18:38` -> `18:39` | no `explicit_nonclosure_missing`, `ledger_missing_id`, or `ledger_render_drift` for DS11; only denominator mismatch remains |
| DS11 red Python files | 1 | `18.13 + 1.10 = 19.23s` | `18:21` -> `18:21` | no writer; 13 collected, all red specifically for absent C01 posture behavior |
| ruff on the two red files | 0 | `0.08 + 0.07 = 0.15s` | `18:35` -> `18:35` | no writer |

The three import/release predicates are intentionally separate: release
guardrail is green, plain import linter is `88` red, and the exact-base
package-import replay is `143` red. Their non-equal counts are not combined;
the earlier 142 is not retained as an exact-base or current-branch claim.

## Page-a11y receipt

The complete raw set is exactly `run-1/results.json`, `run-1/.last-run.json`,
`environment-before.json`, `environment-after.json`, and normalized
`receipt.json` under
`docs/plans/active/atlas-slices/receipts/ds11-page-a11y-base/`. The normalized
receipt content-binds 24 identities, 20 passes, and
[DS11-A11Y-BASE-FAILURE-SET-4](../../plans/active/atlas-slices/DS11-trust-docs-posture.md#ds11-a11y-base-failure-set-4), exit `1`, the exact JSON reporter command,
raw SHA-256s, and those exact known base identities. It establishes only run 1;
the second measured agreement is
`consumer_asserted` / `not_established` for a consumer without its raw result
and cannot support a semantic product gate or posture row. The separately
recomputed completed-process resource measurement may set only its harness
timeout/stop budget. No green or certification state was authored.

## C00 handback

Changed paths are P39-only companions. Both CC09 direction reds are pinned;
the runtime-owned `RuntimeClaimRegistry` and all C01 production paths remain
untouched. Debt rows preserve their ratified capability labels, owners, and
closure commands. The remaining inherited package/debt/page reds are recorded
as evidence, not repaired in C00. The direct handwritten `source_rows`
free-growth witness is C00's red seam only; C01/C05 must replace or extend it
with a real scratch Python producer walk before CC06.

## C01 — typed trust posture compiler

### Scope, pattern, and TDD receipts

- Entry was clean attached `5da45e6c15d644a7a90d59393d1d0c857a3f9b87`
  on `codex/ds11-trust-docs-posture-plan`. C01 owns exactly three mechanism
  paths: the posture DTO/calculus, AST source compiler, and independent
  checker/token compiler. The two tests, this journal, and nearest README are
  P39 companions. No facade, runtime endpoint, manifest, generated artifact,
  dashboard, subject allowlist, or source-document metadata was added.
- The strengthened intended RED collected 16 tests and failed all 16 only at
  the absent three C01 owner modules. Exit was `1`; `real 38.10`, `user 34.29`,
  `sys 3.33`, completed `user + sys = 37.62s`; uptime `19:41` -> `19:42`.
  The free-growth test copies the complete real `src/**/*.py` tree and adds a
  scratch producer; both registry directions use the real runtime registry
  owner.
- Pattern pass: P04/P05/P07/P08/P10/P29/P31/P32/P35-P40. The correct pattern
  is strict DTO/calculus + complete AST producer + independently reconciled
  token walk + blocked unknown/runtime-bound rows. C01 is intentionally
  `artifact_missing`, `bridge_missing`, `consumer_missing`, and
  `surface_out_of_scope`; C02 owns persistence and C03+ own consumers/surfaces.
- Two genuine widening rounds were used: (1) complete real scratch source
  growth and strict/runtime-bound reconciliation; (2) forward-only bounded
  local alias semantics in both independent classifiers. Running mechanism
  accounting is `3/34`; widening is `2/9`. The CC09 two-way runtime separation
  remains a narrowing falsifier and consumes zero widening.

### Complete source census and self-observation

The immutable entry census is replayed separately from the live C01 tree. The
entry remains `2,579` Python files, `104` raw candidates, `103` exact-field
files, role partition `66/5/5/27/1/0`, `93` declaring, `32` consuming, direct
literal `35/13/21` plus five empty sites, wrapper-inclusive `59/24/28`, and
denied-purpose `116` raw plus `34/22/44` bounded literals. Known members remain
`best_snapshot.py` for the sole substring collision and
`frontier_emitter.py:144` for a denied-purpose literal.

C01's own `posture.py` is deliberately not excluded. It contributes exactly
one scanned file, one raw/exact file, one combined role, one inclusive
declaration/consumer, and one raw `may_not_use_for` file, but no bounded literal
site or subject. Both complete walks therefore independently report live:

```text
scanned/raw/exact: 2580 / 105 / 104
roles: declares 66; carries 5; consumes 5; combined 28; collision 1; ambiguous 0
inclusive declaring/consuming: 94 / 33
direct: 35 sites / 13 files / 21 subjects / 5 empty
wrapper-inclusive: 59 sites / 24 files / 28 subjects
may_not_use_for: 117 raw / 34 sites / 22 files / 44 subjects
reconciliation disagreements: 0
```

AST and token row digests are intentionally different derivation receipts;
file membership, roles, resolutions, and literal facts reconcile exactly.
Adding `ds11_growth_probe.py` to a complete scratch copy grows each scan/raw/
exact/declaring/direct-site census by one, creates exactly the new subject and
row without a central edit, content-binds its coordinate/digest/denial, and
keeps it `not_established` absent owner/jurisdiction/review/evidence metadata.

### Green, timing, and boundary receipts

| command | exit | timing / uptime | receipt |
| --- | ---: | --- | --- |
| focused 16-test pytest | 0 | `real 123.89`, `user 112.43`, `sys 6.87`; uptime `20:41` -> `20:43` | all 16 passed; includes full-tree dual walk, free growth, strict artifact, copy/a11y/scope, and both real registry directions |
| Ruff check + format-check, exact 3 mechanisms + 2 tests | 0 | sub-second | all checks passed; all five files formatted |
| C01 no-writer `--check-sources --json` | 0 | `real 50.89`, `user 47.52`, `sys 1.77`; uptime `20:38` -> `20:39` | `declared_outputs=[]`, `write_set=[]`, exact live censuses above |

The completed no-writer CPU measure is `47.52 + 1.77 = 49.29s`; C02's frozen
writer ceiling is `max(30s, 2 × 49.29s) = 98.58s`. The fixed-target scratch
writer test observes exactly one new file below the supplied output root.
Production imports contain neither runtime registry owner nor the legacy shim;
the posture compiler rejects the valid per-run schema, and changing two valid
full-axis runtime registries outside `src` leaves posture rows and bytes equal.
Conversely, a posture-shaped supported payload cannot discharge the real
runtime claim-local axes and the runtime registry remains failed.

Final delivery readback is performed from attached `HEAD` after the prescribed
commit; the exact non-self-referential commit hash and every-path readback are
recorded in the ignored C01 execution report.

### C01 review repair — F01–F05

The reviewed C01 commit was retained and repaired by a new append-only commit.
F01/F03/F04 are narrowing; F02 completes the pre-approved C02 producer/checker
seam inside the existing three mechanism paths and two-round widening budget.
F05 restores all four admitted C00 test identities while keeping the stronger
probes.

- Repair RED: 10 intended failures — exact empty predicate/evidence and
  keep-marker probes (3), declaration-form/parameter-carrier ambiguity (1),
  accessibility document/receipt/generated-family/CLI seams (4), and strict
  copy/accessibility evidence admission (2). Exit `1`; `real 241.35`,
  `user 167.80`, `sys 17.31`; start uptime `21:13`.
- Repair GREEN: 23 focused tests passed; `real 147.23`, `user 132.42`,
  `sys 7.90`. This includes exact recomputation of all eight support facts,
  property-removal probes, all legal declaration forms in both independent
  derivations, subjectless disagreements, strict frontmatter/body binding,
  five-file page receipt recomputation, narrow existing-owner generated
  rendering, fixed output probing, and closed copy/a11y admission.
- Post-repair no-writer CLI: exit `0`; `real 86.50`, `user 73.89`, `sys 4.01`;
  uptime `21:34` -> `21:36`; `declared_outputs=[]`, `write_set=[]`. Completed
  CPU is `77.90s`, so C02's repaired frozen ceiling is
  `max(30s, 2 × 77.90s) = 155.80s`.
- Both complete live walks still report `2,580/105/104`, roles
  `66/5/5/28/1/0`, inclusive declaration/consumption `94/33`, direct
  `35/13/21/5`, wrapper `59/24/28`, denied `117/34/22/44`, and zero
  disagreements. AST receipt is
  `sha256:c5e8f8ef92ac4a951973593a4f14b3a634f1077ce267381b7915ede30873d9f4`;
  token receipt is
  `sha256:984564413add3f568bed4169459764ac6a58809fae818e6d310bc5774e7b1233`.

### C01 review repair round 2 — semantic rows and admitted bytes

The two remaining findings are the same P29/P32/P38 class one level deeper,
not new classes: the outer register existed but its five groups were empty, and
binding facts still turned on digest-prefix/nonempty-verifier proxies. Per P40,
this repair widens the existing mechanism to the actual guarded quantity: fixed
semantic rows, complete row-derived memberships, admitted source/evidence byte
equality, and verifier identity/provenance derived from typed artifact bases.

- Repair-2 RED ran the two new behavioral falsifiers against `ec6cc3d606` and
  failed both: the compiler exposed only `example_claim` instead of the six
  required semantic subjects, and the byte/verifier falsifier could not find a
  `system_identity` row. Exit `1`; two failed, zero passed.
- The compiler now always emits the ratified system-identity bound, the planned
  universal custody commitment with its three exact owner/prerequisite/closure
  tuples, the historical internal accessibility row, blocked current
  conformance, blocked external certification, and blocked grounded
  performance. Missing C02 document frontmatter produces blocked accessibility
  rows rather than omission.
- The semantic/admission change is explicit in
  `policyos.trust.claim_posture_rules.v2`. A self-review falsifier replaced the
  ratified identity statement while leaving its document shape/frontmatter
  intact; the first run incorrectly remained supported, and the exact ratified
  source-byte boundary repair turned the row blocked on the next run.
- The register derives all five projection memberships from produced rows,
  rejects unresolved/duplicate/orphan memberships, derives a closed typed
  verifier set from identity/document/receipt bases, and recomputes every
  source/evidence digest against admitted content. Unknown, mismatched, novel,
  supplied, or self-attested verifier names fail closed. The filesystem
  falsifier mutates identity bytes with marker strings untouched and live
  validation returns `DS11-GENERATED-DRIFT` without Git/HEAD input.
- Mechanism accounting remains `3/34`; widening remains `2/9`. The three
  mechanism paths are unchanged; tests, this README, journal, and ignored
  report are P39 companions. CC09 stays two-directional and no runtime registry,
  facade, endpoint, manifest, generated bytes, dashboard, or source-document
  metadata was added.
- The isolated package-import correction is exact base `f935e0c2e`, exit `1`,
  JSON `finding_count=143`, `user 83.89 + sys 4.49 = 88.38s`, uptime `22:40`
  -> `22:42`. The earlier 142 is invalidated as a shared-source-root reading.
  A current-branch count is `not_established` and is not claimed here.

### C01 review repair round 3 — governed-performance evidence type

The new Important finding is a narrowing P05/P29 breakage: the grounded-
performance gate resolved and content-bound generic admitted evidence, but did
not establish that the verifier was produced by a governed-performance basis.
The divergent case was a real identity/accessibility verifier whose content and
provenance remained valid while its self-supplied subject was relabeled to
`grounded_performance`.

- RED exercised all three admitted verifier kinds and observed `supported` for
  each relabeled non-performance witness.
- The DS11 closed basis contains identity-boundary, accessibility-document, and
  page-a11y verifier types only. It contains no governed-performance producer,
  prerequisite type, or verifier kind, so rule v3 now keeps the family blocked;
  no generic admitted evidence or authored status can substitute for the absent
  typed basis.
- The regression also forges a real identity-derived semantic binding, rebuilds
  the register, and recomputes the artifact digest after authoring `supported`;
  both producer and validator reject the promotion.
- Mechanism accounting remains `3/34`; widening remains `2/9`. This is an
  append-only narrowing inside the existing C01 owner, with focused tests and
  the journal/report as P39 companions. No governed positive fixture or new
  producer/verifier type was fabricated.

## C02 — source binding and generated lifecycle

### Scope, RED, and reopened C01 freeze

- Entry was clean and attached at `ba176147b` on
  `codex/ds11-trust-docs-posture-plan`, with empty repository prefix. C02 owns
  exactly two new mechanism paths: the accessibility projection index and the
  generated-artifact family. The JSON, generated reference, focused tests,
  plan, and this journal are P39 companions. The checker is an observed path
  but remains an already-counted C01 mechanism.
- The two live-source witnesses failed at entry for the intended absent seams:
  missing accessibility frontmatter and missing generated family. Exit `1`;
  `user 20.39 + sys 0.87 = 21.26s`; uptime `23:36` before/after.
- GREEN exposed one C01 P38 proxy: the checker required the limitation sentence
  on one physical source line, while the immutable admitted Markdown body wraps
  it after `replace`. CC13/CC10 authorized reopening the C01 freeze as a
  narrowing repair in `check_trust_claim_posture.py`. Rejected seams were body
  reflow, weakening/deleting the limitation check, and authored frontmatter
  solely to satisfy the proxy. The repaired property normalizes presentation
  whitespace only within Markdown paragraphs, requires exactly one complete
  limitation sentence, and rejects a word-level semantic mutation. Three
  focused tests pass; `user 19.98 + sys 0.81 = 20.79s`; uptime `23:41` before/after.

### Immutable body and generated transaction

- Preimage and independently extracted post-frontmatter body both contain
  exactly `14,263` bytes with SHA-256
  `0e4a0280ab30e1c69cb373d438906aa50d36bd9765ec36e533b6fea1a7df93f0`;
  direct byte comparison exits `0`. All seven selectors resolve exactly once.
  The frontmatter is candidate indexing only.
- The generated-artifact token was acquired exclusively before any manifest,
  output, or reference write and remained held through the transaction. The
  frozen ceiling is `155.80s` completed `user + sys` per material writer/check.
  The committed writer changed exactly the JSON and generated reference:
  `user 28.01 + sys 0.93 = 28.94s`; uptime `23:41` -> `23:42`.
- A repeat committed write was byte-identical (`user 28.05 + sys 0.98 =
  29.03s`; uptime `23:42` -> `23:43`). The scratch output probe emitted exactly
  `apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json`, matched the
  committed bytes, and used `user 28.10 + sys 0.91 = 29.01s`; uptime `23:43`
  before/after. JSON SHA-256 is
  `b7d472da8e97fe0530d1fb7b8167cc37c1b9cbefe55fa249a1840c313ebf526c`.
- Opening semantic truth is evidence-derived: `system_identity` is supported
  only within the ratified purpose/bound; `universal_custody_commitment` is
  planned; historical internal pre-audit is blocked only on unestablished
  jurisdiction; current conformance, external certification, and grounded
  performance are blocked. All five projection groups are nonempty and
  row-derived.

### Mandatory P39 reconciliation

- Declared mechanisms are `26`, with arithmetic `3 + 2 + 13 + 8 = 26`; hard
  ceiling remains `34`, slack is `8`, and widening ceiling remains `9`.
  Running after C02 is `5/34` mechanisms and `4/9` widening rounds.
- C04 set A contains eight production clothing/issuer mechanisms. Two
  independent derivations agree over **625** dashboard production files
  (**304 `.ts`**, **321 `.tsx`**) and add `trust-view/index.ts`,
  `TrustViewBadge.tsx`, and `ProvenanceStrip.tsx` to the original five.
  Disagreeing scout set B named `HashChip.tsx` and `TrustViewBridge.tsx`; both
  are transports, not clothing/issuer mechanisms, and are explicitly excluded.
- The completed frontend transaction is
  `user 195.14 + sys 27.53 = 222.67s`, fixing its ceiling at `445.34s`.
  Package-import is pinned only at exact slice base `f935e0c2e`: exit `1`, JSON
  `finding_count=143`, `user 83.89 + sys 4.49 = 88.38s`, uptime `22:40` ->
  `22:42`. The earlier 142 is invalidated as a shared-source-root reading; no
  current-branch count is claimed.
- C03's visual companion is
  `apps/runtime-dashboard/e2e/ds11-runtime-dashboard.visual.spec.ts` and its
  own snapshots. Its title contains `DS11 trust posture`; no visual config edit
  is authorized.

### C02 targeted verification and closeout

- The final focused two-file pytest wave passes: `user 68.56 + sys 2.92 =
  71.48s`; uptime `23:49` -> `23:50`. Ruff lint and format checks pass for the
  three observed C01 mechanisms and two focused test files (`user 0.05 + sys
  0.02 = 0.07s`; uptime `23:50` before/after). The isolation-local `.venv`
  did not provide Ruff, so the read-only external dependency runtime was used
  with worktree `PYTHONPATH`; its resolved product imports were proved to come
  from this worktree.
- The generated register check passes (`user 27.97 + sys 1.05 = 29.02s`;
  uptime `23:50` -> `23:51`) and the accessibility receipt check passes (`user
  29.16 + sys 1.23 = 30.39s`; uptime `23:51` before/after).
- The first architecture guardrail correctly failed the isolated output probe:
  `uv run` wrote 229 `_cache/uv` paths outside the declared output root (`user
  60.43 + sys 15.84 = 76.27s`; uptime `23:51` -> `23:53`). This was a C02
  manifest narrowing, not an accepted side effect: the probe now invokes the
  already-running interpreter with `PYTHONDONTWRITEBYTECODE=1`. The regenerated
  committed bytes retain JSON SHA-256
  `b7d472da8e97fe0530d1fb7b8167cc37c1b9cbefe55fa249a1840c313ebf526c`
  (`user 28.64 + sys 0.92 = 29.56s`; uptime `23:54` before/after), and the
  guardrail then passes (`user 58.05 + sys 13.49 = 71.54s`; uptime `23:54` ->
  `23:55`).
- The last generated check passes (`user 28.76 + sys 0.91 = 29.67s`; uptime
  `23:56` before/after), as does `git diff --check`. The final accessibility
  body still byte-compares exactly to its preimage: `14,263` bytes and SHA-256
  `0e4a0280ab30e1c69cb373d438906aa50d36bd9765ec36e533b6fea1a7df93f0`.
  Every material writer/check remained below the frozen `155.80s` CPU ceiling.
- The complete transaction contains eight changed paths: two new C02
  mechanisms, one authorized already-counted C01 mechanism, and five P39
  companions. The planned ledger therefore remains `5/34` mechanisms and
  `4/9` widening rounds. The generated-artifact token remains held through the
  commit and branch readback.

### C02 review repair round 1 — execute the manifest probe

- Bucket: this is a new P29/P38 focused-regression defect class, command-
  authority bypass, rather than another instance of the C01 paragraph-
  whitespace proxy or the C02 `uv` output escape. The helper parsed and
  marker-checked `output_probe_command` but then bypassed it with direct
  in-process compiler/writer calls. A nonexistent executable with the same
  `--write`, `--output-root`, and `{output_root}` markers therefore stayed
  green.
- RED changes only the parsed command's executable from `uv` to
  `ds11-command-does-not-exist`, proves the remaining argv is byte-for-byte
  unchanged, and observes `Failed: DID NOT RAISE`. Exit `1`; `user 19.86 + sys
  0.87 = 20.73s`; uptime `00:13` -> `00:14`.
- The repaired helper copies an explicit dedicated source sibling through the
  existing architecture isolation owner, proves `.git` is absent, substitutes
  `{output_root}` in the exact parsed argv, checks executable availability, and
  invokes it with `subprocess.run(..., shell=False)` in a bounded deterministic
  environment. It requires exit `0`, the exact sole declared output, byte
  identity to the committed artifact, and unchanged original-repository and
  scratch-outside-output snapshots.
- Two diagnostic runs correctly exposed an incomplete interpreter-path
  receipt: both returned `env: python: No such file or directory` (`user 21.64
  + sys 6.60 = 28.24s`, uptime `00:15` -> `00:16`; then `user 21.56 + sys 6.57
  = 28.13s`, uptime `00:16` -> `00:17`). The final environment names the
  copied source's linked `.venv/bin` explicitly; it does not rewrite manifest
  argv. The real live probe then passes with `user 52.72 + sys 8.04 = 60.76s`,
  uptime `00:17` -> `00:18`.
- The post-format two-test wave passes (`user 52.33 + sys 9.86 = 62.19s`;
  uptime `00:19` -> `00:21`). The complete focused two-file wave passes (`user
  102.68 + sys 10.11 = 112.79s`; uptime `00:21` -> `00:23`). Targeted Ruff lint
  and format are clean. The unchanged architecture guardrail passes and reports
  one generator-observed trust-posture output (`user 55.82 + sys 13.35 =
  69.17s`; uptime `00:23` -> `00:24`). After strengthening the falsifier's
  only-executable-change proof, its final run passes (`user 20.39 + sys 0.91 =
  21.30s`; uptime `00:24` -> `00:25`).
- The token was reacquired exclusively before the repair and remains held
  through its separate commit/readback. Every material receipt remains below
  `155.80s`. This append-only repair changes the already-counted checker and
  focused test seams plus this mandatory journal companion; it adds no unique
  mechanism path or widening round. The ledger remains `5/34` and `4/9`.
- Final self-review removed the original-repository snapshot's optional Git
  path and uses the complete filesystem snapshot directly. On that final source,
  the two-test wave passes (`user 60.73 + sys 17.58 = 78.31s`; uptime `00:27`
  -> `00:28`), targeted Ruff remains clean, and the architecture guardrail
  passes again (`user 56.43 + sys 13.12 = 69.55s`; uptime `00:29` -> `00:30`).

## C03 — public posture route and exact-byte MACHINE twin

### Scope, RED, and pattern pass

- Entry was clean and attached at `b8e16b0d1` on
  `codex/ds11-trust-docs-posture-plan`, with empty repository prefix. C03 owns
  exactly the thirteen declared production mechanisms; six focused tests,
  i18n parity, the browser denominator helper, separate visual declaration,
  this journal, and the ignored task report are P39 companions. No rejected
  route-manifest/API/public-surface/config seam was needed.
- The first RED invocation exposed one test-only `.ts`/JSX transform defect
  before reaching the missing feature. After changing that test to
  `createElement`, the complete second RED failed all six files only at absent
  C03 modules/routes: exit `1`, `user 5.66 + sys 1.18 = 6.84s`, uptime
  `00:42` before/after. No production path existed before that receipt.
- Pattern pass: P01/P02/P03/P05/P10/P15/P29/P31/P32/P33/P35/P37/P38/P39.
  The correct pattern is byte-first strict admission -> artifact-generic
  human projection -> independent DOM twin and exact captured-byte MACHINE
  export. The surface preserves negative/planned states; it mints no support,
  grounded-performance, current accessibility, or implemented-custody claim.

### Strict admission, surface, and parity

- The feature-owned Zod 4 schema recursively types the complete committed
  artifact. All 21 object boundaries are strict; schema/rule/base values and
  all closed statuses/establishment classes are literals/enums. Deep unknown,
  missing, novel-version, malformed-state, and malformed-establishment probes
  fail. There is no passthrough, unknown escape, broad API validator, cache,
  storage, or last-known payload.
- The loader fetches only `/atlas/trust-claim-posture.v1.json` with JSON accept
  and `cache: no-store`, requires `ok`, captures a copied `Uint8Array` from
  `arrayBuffer()` before fatal UTF-8 decode/JSON parse/strict validation, and
  maps every failure to explicit unavailable posture.
- `/trust` is a top-level `APP_ROUTES` child imported from
  `features/trust/routes.public.tsx`. The route has static `/trust` href and no
  loader, workspace, or prefetch handle. Landing has one neutral `/trust`
  link. PUBLIC is the default; status/limitations/source/review remain visible
  for every artifact row. REVIEWER/EXPERT add visible artifact evidence depth
  while the tested claim-bearing DOM remains byte-for-byte equal across depth.
- MACHINE constructs its Blob only from a defensive copy of captured bytes;
  the production twin contains no serialization call. The independent DOM
  decoder covers every ordered PUBLIC claim id, subject, source coordinate and
  source state, effective state, blocker, limitation, and row/source review
  field. Removal, reorder, supported relabel, `aria-hidden` limitation,
  missing source, and missing review mutations all return
  `DS11-DOM-PARITY-DRIFT`.

### Locale, denominator, visual, and verification receipts

- Independent `jq` and Node tree walks agree: active English and Ukrainian
  each contain 2,652 leaves after C03, from 2,618 at `b8e16b0d`; the exact
  active pin alone moved to 2,652. Russian remains 2,449 leaves and its Git
  blob is unchanged at `7a25da19c935c363958f2b2f1d93071238bf62c3`.
- A complete helper-array parser derives route surfaces `17 -> 18`, adding
  only `trust`. A second page-a11y derivation follows all three wrapper imports
  and counts their `2 + 2 + 3` direct tests; together with the route inventory
  it derives `24 -> 25`.
- The unanchored existing visual matcher lists exactly one DS11 test in one
  separate file, titled `DS11 trust posture`; exit `0`,
  `user 0.90 + sys 0.09 = 0.99s`, uptime `00:53` before/after. No snapshot or
  config path was written.
- Final seven-file focused wave: 51/51 pass, exit `0`,
  `user 22.15 + sys 2.94 = 25.09s`, uptime `00:55` before/after. The earlier
  dedicated route/a11y wave passed 3/3 (`user 5.47 + sys 0.83 = 6.30s`). Final
  app typecheck passes, exit `0`, `user 19.66 + sys 0.67 = 20.33s`, uptime
  `00:55 -> 00:56`. `git diff --check` is clean.

### C03 accounting and handback

- Pre-staging complete-set comparison returns expected mechanisms `13`,
  observed mechanisms `13`, equality `true`, with no missing/unexpected path.
  C03 uses exactly rounds 5–7: deep strict byte-first admission, public
  route/human projection/locales, and MACHINE/DOM parity plus denominator.
- Running slice accounting is therefore `18/34` mechanisms and `7/9`
  widening rounds. C03 closes its public/MACHINE consumer and surface seam;
  slice-wide closure remains `verification_missing` until the owned C04–C06
  repair/corruption/closeout work lands. The custody watcher itself remains
  bridge-missing and is rendered only as the artifact's planned claim.

### C03 review repair round 1 — semantic admission and visible DOM truth

- P40 bucket: the findings narrow existing C03 P29/P32/P38/P35 mechanisms one
  level deeper; they are not a new capability class, path, or widening round.
- Repair RED ran the domain, full-DOM, and free-growth tests against
  `e0eea3143`: 8 intended failures exposed shape-only admission, claim values
  supplied by `data-*`, CSS-hidden content acceptance, and the six-row sampled
  denominator. Exit `1`; `real 5.62`, `user 14.44`, `sys 1.33`; uptime `01:12`
  before/after, up 2d15:25.
- The browser admission seam now awaits strict Zod parsing plus a generic
  replay of the canonical Pydantic v3 root calculus: ordering/uniqueness,
  source-binding semantics, admitted-source and verifier/evidence binding,
  effective posture, closed projection membership, and Python-compatible
  `source_set_digest`/`payload_digest` SHA-256 serialization. Missing Web
  Crypto fails unavailable.
- Review caught and removed an intermediate `sr-only` JSON shadow-value seam
  before final GREEN. The decoder now takes claim-bearing values from the
  actually presented heading, state, date, source, blocker, and limitation
  text. `data-null` only marks null type. `aria-hidden`, `hidden`, CSS
  `display:none`, and CSS `visibility:hidden` on decoded elements or ancestors
  fail closed.
- The independent DOM test renders, decodes, and compares all 342 committed
  PUBLIC rows, asserts the independently counted total and known
  `system_identity` member, then falsifies omission, reorder, visible claim ID,
  subject, status, source path/symbol/review, and hidden limitation variants.
  The admitted free-growth fixture now updates row evidence subjects, sorted
  claim/group membership, both digests, and crosses the real loader seam.
- Final repair wave: seven focused files, 58/58 pass, exit `0`, `real 14.01`,
  `user 36.96`, `sys 3.00`; uptime `01:25` before/after, up 2d15:38 ->
  2d15:39. App typecheck passes (`real 10.23`, `user 18.12`, `sys 0.48`;
  uptime `01:26`, up 2d15:39 before/after). Dedicated route/a11y passes 3/3 (`real 2.82`,
  `user 5.51`, `sys 0.82`; uptime `01:24` before/after). Exact visual list
  remains one test in one file (`real 0.72`, `user 0.69`, `sys 0.07`).
- Repair path audit is append-only within seven already-owned C03
  mechanism/test paths plus this journal and the ignored report. Production
  mechanism accounting remains exactly `18/34`; widening remains `7/9`.

### C03 review repair round 2 — null presentation and Gregorian dates

- P40 bucket: both residuals are the second finding in their existing class.
  The repair therefore widens each shared mechanism to the full property: one
  explicit neutral null-interface label covers every nullable DOM field, and
  one Gregorian predicate covers every root-reachable date schema. This adds
  no Atlas widening round or mechanism path.
- RED against `cc1ab3293`: the two focused files reported 4 intended failures
  (null presentation relabel plus non-leap February 29, February 30, and month
  13 with rebound payload digests), with 13 other tests passing. `real 15.96`,
  `user 24.52`, `sys 0.90`; uptime `01:32 -> 01:33`, up 2d15:45 -> 2d15:46.
- The renderer now presents the locale's canonical `notEstablished` label for
  every null subject/review/source value. The independent decoder and parity
  assertion require that label as an explicit interface argument and compare
  actual displayed text to it before returning null; `data-null` remains only
  a type marker. Null subject, row review, source symbol, source subject, and
  source review visible-text mutations all fail parity. No hidden or
  `data-value` shadow exists.
- The shared ISO-date schema now validates the proleptic Gregorian calendar:
  year 1–9999, month/day ranges, and the divisible-by-4/100/400 leap rule.
  Every one of the 11 root-reachable required/nullable date fields consumes
  that schema. Rebound-digest impossible dates fail structural admission.
- The full-DOM denominator assertion is now `register.claims.length`, while
  retaining the independently known `system_identity` member; future admitted
  free growth needs no count edit.
- Final receipts: seven focused files, 61/61 pass, exit `0`, `real 15.16`,
  `user 38.59`, `sys 3.16`; uptime `01:35 -> 01:36`, up 2d15:48 -> 2d15:49.
  App typecheck passes (`real 10.14`, `user 17.98`, `sys 0.50`; uptime `01:36`,
  up 2d15:49 before/after). Dedicated route/a11y passes 3/3 (`real 2.78`,
  `user 5.47`, `sys 0.79`). Exact visual list remains one test in one file
  (`real 0.69`, `user 0.70`, `sys 0.07`).
- Complete path comparison is exactly five already-owned C03 mechanism/test
  paths plus this journal and ignored report. Totals remain `18/34` mechanisms
  and `7/9` widening rounds.

### C04 — private Trust View presentation issuer

- Pattern pass: C04 closes the C01a authority-presentation instances under
  `P04`/`P05` with one issuer rather than caller-selected strings; `P29` and
  `P32` are met by executing the runtime identity path, not by checking prop
  names. The full AST source census prevents the P35/P38 sampled/wrong-set
  failure. `P39` keeps the eight product mechanisms separate from the focused
  tests, checker/schema, register/report, this journal, and ignored handback.
- Transport remains the generated owner contract:
  `src/polisyos/core/contracts/runtime.py:814` defines `VerificationMetadata`;
  `packages/runtime-api-client/runtimeApiClient.ts` owns the generated client
  shape. C04 adds no generated/client/locales/config path.
- `trust-glyphs.ts` is the only issuer: a module-private unique-symbol brand,
  private `WeakSet` identity registry and `WeakMap` display data, frozen issued
  objects/data, and guarded `Reflect.get` reads reject structural casts, copied
  or proxied values, and hostile getters. The exhaustive calculus is explicit:
  absent/non-object categorical data is unknown; novel categorical data is
  unrecognized; disputed or under-review vetoes; stale is distinct; verified
  requires current freshness plus nonblank hash/method/verifier; pending stays
  nonpositive; untraced/incomplete/unknown freshness stays unknown; resolved
  is not a veto.
- Both clothing components now accept only the issued presentation. The issuer
  is called once by TrustInspector, TrustMetadata, TrustViewBadge, and the
  ProvenanceStrip sibling; raw metadata remains detail/HashChip/inspector
  transport. The Trust View barrel omits issuer helpers/types. The full
  TypeScript census is exactly `625 = 304 .ts + 321 .tsx`, excludes test/spec,
  stories, declarations, and `src/test/**/*.tsx`, and has filesystem-to-Git
  equality; it does not special-case generated or C03 sources.
- The dedicated locked DS11 writer restored its two declared open predecessors
  and atomically materialized only
  `authority-presentation-prop-dispute-status` and
  `authority-presentation-prop-verification-status-icon-tone`, with report
  peer bytes preserved. `check_status_retirement_inventory.py` is not a C04
  companion or mechanism: the disposition checker invokes its existing scanner
  API read-only, so no status-inventory schema/state can express this repair.
- Final receipts: 10 focused Trust View/a11y/AST files pass `18/18` (exit 0;
  `real 4.20`, `user 18.75`, `sys 3.46`; uptime `02:59`, up 2d17:12).
  App typecheck passes (exit 0; `real 10.48`, `user 18.05`, `sys 0.56`; uptime
  `02:51`). The targeted writer/schema/forgery test passes (exit 0; `real
  49.20`, `user 64.62`, `sys 6.81`; uptime `02:56`). The final whole checker
  ran under the DS11 lock and returned only the inherited allowed C13 receipt:
  `c13_print_receipt_invalid:C13 current evidence drift:apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx`
  (exit 1; `real 64.33`, `user 90.11`, `sys 8.68`; uptime `02:57 -> 02:58`);
  it emitted no DS11 error. `git diff --check` is clean.
- C04 owns exactly eight product mechanism paths and is narrowing-only. Slice
  accounting moves `18/34 -> 26/34` mechanisms; widening remains `7/9`.
  No DS6 evidence was changed, and no DEBT-REGISTER/LEDGER row is added;
  any later debt-ledger decision remains C06-owned.

### C04 review repair — unbound metadata and complete issuer census

- P40 bucket: both findings are the existing C04 `P29`/`P32`/`P38` class one
  level deeper. This repair narrows the already-owned issuer, scanner, checker,
  and focused-test seams; it adds no production mechanism path or widening
  round.
- F1 RED: three focused frontend files reported 6 intended failures with 7
  passes. Shape-complete generated `VerificationMetadata` still produced
  positive `verified` and `none` clothing, stale/pending preserved positive
  dispute labels, and no typed limitation existed. The issuer now preserves
  only conservative negative projections (`disputed`/`under_review`, `stale`,
  `pending`); missing, novel, or marker-complete positive metadata projects to
  unknown/unrecognized. Every issued display datum carries the typed
  `content_bound_verification_receipt_missing` limitation. Positive verified
  clothing remains unavailable until a content-bound verification receipt with
  admitted verifier provenance crosses this seam; C04 does not invent that
  producer.
- F2 RED: the complete 625-file frontend falsifier missed namespace/property,
  re-export, dynamic-import, require, and local-alias access (5 failures); the
  governed scanner had no `moduleAccesses` facts, and its complete authority
  path set included the eight production mechanisms plus four P39 test
  companions. A later same-class RED proved destructuring aliases and a fifth
  direct named call hidden inside an already-counted mechanism also escaped.
- The frontend census now rejects all named unsafe forms, including namespace
  destructuring, while requiring exactly one direct call in each of
  ProvenanceStrip, TrustInspector, TrustMetadata, and TrustViewBadge. The shared
  TypeScript scanner emits unsafe module-access and direct-call facts. The
  governed checker consumes its complete `authorityPathFiles`, applies the
  same production exclusions as the 625-file TypeScript denominator, requires
  the exact eight mechanisms and four one-call owners, and rejects a genuine
  extra-call source override inside DisputeBadge.
- Final focused frontend wave: 15 Trust View/Provenance files, 33/33 pass (exit
  0; `real 5.10`, `user 28.11`, `sys 5.01`; uptime `17:48` before/after).
  Dashboard typecheck passes (exit 0; `real 13.24`, `user 25.04`, `sys 0.79`;
  uptime `17:48` before/after). Five targeted governed checker tests pass (exit
  0; `real 64.41`, `user 88.49`, `sys 9.51`; uptime `17:48 -> 17:49`).
- Register/report preimages were byte-identical to attached `e3df33744` before
  the only effective writer. One attempted `uv run python` invocation was a
  tooling non-receipt (`jsonschema` absent) and wrote nothing; system Python
  3 carried `jsonschema 4.25.1`. The effective locked writer completed its
  two-finding/eight-mechanism transition (exit 0; `real 50.49`, `user 65.35`,
  `sys 7.56`; uptime `17:50 -> 17:51`). The final locked whole checker returned
  exactly the inherited C13 receipt and no DS11 error (exit 1; `real 68.25`,
  `user 93.31`, `sys 9.54`; uptime `17:51 -> 17:52`).
- Path accounting remains exactly eight already-counted C04 production
  mechanisms; `status_retirement_scan.mjs`, the governed checker/tests,
  frontend tests, register/report, this journal, and the ignored handback are
  P39 companions. Slice totals remain `26/34` mechanisms and `7/9` widening
  rounds.

### C04 review repair — issuer receipt content binding

- Final same-class closure: the preceding writer invocation was idempotent and
  produced no register/report diff because the repaired rows still cited the
  issuer by plain path. RED proved a marker-preserving issuer-byte mutation did
  not change either stored row.
- The DS11 row producer now requires the live scanner's single issuer module
  fact and its `sha256:<64 hex>` source digest, then emits
  `trust-glyphs.ts#content-sha256=sha256:...` into both evidence-ref sets. The
  transition admits only the original pinned opening rows, the exact `e3df33744`
  repaired predecessor with its single unbound issuer ref, or the current
  bound result. A real source override appends a marker-preserving mutation,
  recomputes the scanner digest, and makes both stored transition rows red.
- Six targeted governed tests pass (exit 0; `real 69.59`, `user 98.84`, `sys
  10.20`; uptime `18:02 -> 18:04`). The final content-binding writer changes
  only the two issuer evidence refs (exit 0; `real 50.86`, `user 66.13`, `sys
  7.50`; uptime `18:04 -> 18:05`). The post-write locked checker again returns
  exactly the inherited C13 receipt and no DS11 error (exit 1; `real 67.45`,
  `user 92.64`, `sys 9.51`; uptime `18:05 -> 18:06`). Accounting remains
  `26/34` mechanisms and `7/9` widening rounds.
