# Atlas public-surface investigation and handback — 2026-09-07

## Investigation (written before repair)

Task invariant: a public surface may not assert a verification it cannot produce.
Worktree: `/Users/deniskopylov/polisyos/.worktrees/atlas`, branch
`codex/atlas-public-surface`, slice base `f48153870`. Ordinary local git only;
no push. Auxiliary proof worktree: `/Users/deniskopylov/polisyos/.worktrees/atlas-lane-base`,
branch `codex/atlas-lane-base`, created at the slice base solely to replay the
architecture gate (recorded at creation; never left unnamed). The DS17 branch is read-only.
The four requested debt rows and their closure signals were read as task inputs;
neither DEBT-REGISTER.md nor LEDGER.md is a verification oracle. No debt-ledger
checker is used. This journal is the explicitly authorized documentation companion.

Pattern pass: P05/P15 authority laundering; P29/P32 marker tests and trust by form;
P31/P33 structural repairs and hostile variants; P37/P38 decisive predicates versus
their proxies; P41 provenance of reds. Target: no client-created verification,
and source-driven print behavior with the protected parity assertion intact.
Capability claims remain bounded by actual producers, bridges and consumers.

### public-decision-verified-badge-is-client-computed

Pre-test mechanism: `publicationPacket.ts` computes an FNV-style 32-bit hash with
public `SIGNATURE_SALT`, serializes the packet alongside the hash, and accepts it
when the same browser algorithm reproduces the hash. `PublicDecisionViewerPage`
uses that local `valid` result for its `phase35.viewer.verified` badge (English:
“signature verified”). The two assertions to understand are
`publicationPacket > signs and verifies immutable public packets without privileged context`
and `PublicDecisionViewerPage > renders a verified signed public decision without API context`.
Their expected positive says only that the producer and verifier agree on bytes;
it does not establish origin, a governed publication, or custody. Prediction: both
pass at base, and an invented owner verdict re-issued by the same client also
passes and renders verified. This decisive predicate is `consumer_asserted`.
Cheapest honest close is still under investigation: reuse a real server verifier
if one exists, otherwise strangle the authority claim without inventing a server
receipt or calling an unsigned preview a verified publication.

### atlas-ui-token-print-projection-mismatch

Pre-test mechanism from token-source reading: `print.tokens.json` declares the
print/export projection, including A4 page `2.5cm 2cm`, print colors and ordered
hide/document/link rules. It lacks the live print.css screen-only run-detail
selector, paper URL suppression, eligible-paper-link rendering, public-decision
URL suppression and paper-control hiding introduced by later signed/A4 print work.
`project.ts` emits source rules in insertion order; the dashboard assertion compares
the complete ordered declarations with live CSS. Prediction: the assertion exposes
PRODUCT drift in the token source. Cheapest honest close: surgically extend that
source for the already-live print semantics and regenerate its owned projections;
keep the existing dashboard expectation unchanged. Measurement pending.

### DS11-SCOPE-ADJUDICATION-RECORD

Pre-test mechanism from the candidate owner: the constructor derives a proposed
four-way ruling but emits `authority_effect=none`, `closure_effect=none`, empty
`authoritative_for` and explicit resolver/claim-lifecycle-consumer limitations.
Prediction: the artifact is correctly candidate-band; a route that relabels it as
authority would mint a ruling. Closure requires a purpose-scoped evidence resolver,
persisted ruling and claim-lifecycle consumer, not just carrying the ratified rule.
The owning `core/contracts` boundary is outside the edit grant; executable evidence
and the cheapest honest next step are pending, not inferred from register status.

### DS11-PUBLIC-SIGNATURE-POPULATION

Pre-test hypothesis (sent by the investigating agent before execution): production
installs `UnappointedPublicSignaturePopulationProvider`; custody maintenance should
persist `not_established`, not claim a watched public population. The static fixture
proves advisory custody only. A real DS11 population needs the DS12 governed record
producer; a client packet or synthetic signature cannot supply it.

## Execution plan and resources

1. Independent investigations: root owns browser verification; one agent owns
   atlas-ui print files; two read-only agents inspect DS11 and DS17 respectively.
2. Record hypotheses, run focused base measurements, then make bounded repairs.
3. Run removal probes with markers retained and restore only our own mutations.
4. Freeze source, independent review, then one full dashboard Vitest wave with
   `--maxWorkers=1 --testTimeout=20000 --hookTimeout=20000`, plus relevant lint,
   type checks and architecture checks. No directory-wide pytest.
5. Commit clean boundaries after checking branch attachment; read delivered commits
   back from the branch. Stop before push.

Contended resource: full dashboard/browser suite is root-owned and serialized;
agents run focused tests only. No shared DuckDB or fixed-port server is scheduled.
`corepack pnpm install --frozen-lockfile` completed with exit 0 in this fresh worktree.

## Measurements and repairs

### Browser verification — PRODUCT; live defect removed, full row remains open

Both original files passed at base: `publicationPacket.test.ts` and
`PublicDecisionViewerPage.test.tsx`, 31/31, exit 0, 2.12 seconds:

```sh
corepack pnpm exec vitest run src/features/runs/domain/publicationPacket.test.ts src/features/runs/routes/PublicDecisionViewerPage.test.tsx --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000
```

The original domain assertion accepted a producer-created `sig:` marker and only
rejected a changed suffix. The original route assertion explicitly expected
“signature verified” without API context. Those passes encode the defect.
Before changing production code, an independent attack fixture reproduced the
public FNV algorithm over an invented decision. The real registered
`publicDecisionViewerRoute` rendered the forged decision as verified. The rewritten
negative failed on the actual verified badge, and the producer assertion failed
on `signature = sig:8c6474e7`. Eight owner-state variants likewise rendered verified.
Malformed input cases lacked the truthful unavailable state. Exact focused finding
set: the preview emission test; the forged public-route test; the eight
`does not admit a client-supplied ... owner state` cases; and the three malformed /
record-looking input cases. Exit 1, 13 failures, 20 passes. This was an executed
property counterexample, not a hypothesis inferred from code.

The cheapest honest repair is a strangle, not a verifier fabricated from a checksum.
The canonical export producer exists, but there is no admitted public-record
verification response to reuse. `PV-K01` requires separate verification dimensions;
`PV-K03` forbids transport/possession/projection minting a governed positive
(`POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`, DS12 ratified constraints).
A server checksum endpoint would merely relocate the false predicate.

Changes: delete client signing, local signature verification and URL payload
production; migrate internal callers to the existing `buildPublicDecisionPacket`
view-model producer; remove the signature token and public-link emitter from its
panel; remove unsigned `signedId` from local operator snapshots; label the preview
as unsigned in both active locales. Keep the existing public URL route, but never
parse/admit its content; render a truthful verification nonreceipt. The frozen `ru`
catalog is untouched. Historical verification text keys remain inert, not emitted.

The claim is intentionally bounded: this removes the live false positive and its
emitter. It does **not** supply a server-backed verification response and therefore
is not full closure of the row's conjunctive signal. That remaining chain is
`bridge_missing` / `verification_missing`; it is not an institutional stop on
building capability. DS12's positive mechanism and record owner remain a distinct
follow-up, not a manufactured success in this lane.

Assertion change ledger (no quiet relaxation):

- Domain `signs and verifies immutable public packets without privileged context`
  becomes `builds a preview without minting a public signature or URL`: old positive
  checked public-salt self-agreement; new negative forbids signature, signed ID and
  public URL emission and keeps interaction-state/opaque-authority checks.
- Domain `uses stable signatures for stable packet content` becomes
  `keeps a stable preview fingerprint without issuing a signature`: stability is
  still tested, now for the non-authoritative preview fingerprint, and neither
  result may emit a signature. The signature facility was deliberately retired.
- The domain trust-framing assertion now requires the true unsigned-preview
  limitation, rather than “frontend signature verifies packet integrity”.
- Route `renders a verified signed public decision without API context` becomes
  the forged-packet refusal through the **registered route**, using the real locale
  provider and visible copy. An attacker fixture, isolated under `src/test`, retains
  the entire old hash algorithm, so removing the production signer cannot make the
  negative vacuous.
- The route's publishable and seven opaque owner-state tests formerly admitted
  client-supplied labels. They now require refusal with no payload/authority text,
  even when the packet self-declares Verified / Publication authorized. Internal
  panel/domain tests retain opaque-state preservation; public transport no longer
  promotes those labels into a public record.
- `rejects invalid signed ids` expands to malformed, forged JSON and a record-looking
  ID. Without an installed verifier, none warrants a signature-invalid verdict;
  the visible result is verification unavailable.
- Panel `renders only the non-authoritative integrity signature notice for $label`
  becomes `renders an unsigned preview without a publication link for $label`.
  It checks the internal emission surface (not publicMode, which used to hide the
  link), no token, no public link, and an explicit unsigned limitation. The existing
  no-authority-granted / no-invented-dispute assertions remain.
- The public-route browser tests in `runtime-dashboard.visual.spec.ts` and
  `trust-framing-negative-traces.spec.ts` use the independent forgery helper and
  require nonreceipt/no packet/no verified badge. Former public-payload visibility
  expectations are obsolete because the forged packet is no longer admitted;
  human-decision isolation assertions remain. The trust-framing fixture also needed
  explicit epoch nonreceipt, supplied instead of bypassing the builder contract.
- Operator/domain/quantity harness changes only migrate the producer/type to the
  unsigned view model; their substantive assertions are unchanged.

Intermediate implementation errors were ours: the first migration left a renamed
verifier reference in the route, producing `signedId is not defined`; the typecheck
also rejected a widened `it.each` tuple. Repaired the references/tuple, not the
assertions. A formatter invocation used duplicated `policy-engine/` paths and failed
before those files were formatted; reran with git's relative-path option. These are
local BROKEN SCAFFOLDING invocations, not inherited product debt.
Focused route/domain/panel/operator checks then passed 46/46; after replacing the
mock locale with the real provider, route/domain/panel passed 39/39. Dashboard
three-project typecheck exited 0. Removal probes and frozen wave recorded below.

### Print projection — PRODUCT; repaired

Baseline dashboard parity exited 1 with exactly
`DTCG token projection parity > projects print tokens and export behavior`;
ten other assertions passed. The deterministic token checker simultaneously
exited 0. This separates a faithfully generated but stale source from corrupted
generated output and broken test scaffolding. History confirms the missing rules:
`1fc07ed01` scoped signed print targets; `fd43342f8` added governed A4 paper rules,
after the July token projection, without corresponding source changes.

Surgically extended `packages/atlas-ui/tokens/modes/print.tokens.json` with the
screen-only run-detail selector and four rules: paper URL suppression, eligible
paper link expansion, public-decision URL suppression, paper-control hiding.
Regenerated the five canonical outputs under `src/generated/`. The dashboard
assertion and source generator are unchanged:

```ts
expect(orderedContextRules([generatedCss], "print", true)).toEqual(
  orderedContextRules([mediaCss, printCss, stylesCss], "print", true),
);
```

Separate commands, each exit 0 after repair:

```sh
# apps/runtime-dashboard
corepack pnpm exec vitest run scripts/tokenProjectionParity.test.ts --project=unit --maxWorkers=1 --testTimeout=20000
# packages/atlas-ui (one invocation per command)
corepack pnpm run tokens:schema
node --experimental-strip-types ./src/tokens/project.ts --write
node --experimental-strip-types ./src/tokens/project.ts
corepack pnpm exec vitest run tests/tokenProjectionParity.test.ts tests/tokenProjectionDrift.test.ts --maxWorkers=1 --testTimeout=20000
corepack pnpm run lint
corepack pnpm run typecheck
corepack pnpm run check:architecture
```

Dashboard parity 11/11; owner tests 28/28. The schema command provisioned the Atlas
worktree's `.venv`; no other lane's environment was changed.
Removal probe changed only the generated paper-controls declaration from
`display: none !important` to `display: block !important`, keeping the selector,
source digest, `@generated` and TypeScript markers. The **unchanged** parity test
failed on exactly that declaration, and the deterministic checker separately
reported exactly `src/generated/tokens.css differs from deterministic projection`.
Restored by canonical generation; both reruns exited 0. No assertion was moved,
added or relaxed. This proves projection parity, not a fresh rendered PDF claim.

### DS11 scope adjudication — PRODUCT, authority capability incomplete

Executed the existing candidate tests: 8 parameter cases passed, exit 0. Every
candidate is `candidate_only`, `authority_effect=none`, `closure_effect=none`,
`authoritative_for=()`. The owner forbids scope ruling, lifecycle transition,
claim-head advance and publication authorization, and retains resolver/consumer
limitations. Synthetic references exercise the candidate contract, not authority.

Cheapest honest close: extend `core/contracts/scope_adjudication.py` with a distinct
purpose-scoped authority artifact admitted by an independent predicate resolver;
persist and replay it; consume it through Scientist claim lifecycle, then the HTTP
bridge and governed surface. This must preserve candidate-band behavior. The file
grant excludes `src/polisyos/core/contracts/**` and explicitly forbids
`src/polisyos/scientist/**`; duplicating their authority under HTTP would be P27/P31.
This is a genuine file boundary, not an appointment or ledger-transcription blocker.
The candidate-only terminal alternative was rejected in the recorded task-Q decision
(`2026-09-01-debt-q-remeasure-and-typing.md`, scope-adjudication investigation).
No repair/test was fabricated; the named authority closure remains absent.
Missing labels: `producer_missing`, `artifact_missing`, `bridge_missing`,
`consumer_missing`, `verification_missing`, `surface_missing`, `semantic_test_missing`
for the authority chain, not for the existing candidate contract.

### DS11 public signature population — PRODUCT, record/population dependency

The production container explicitly injects
`UnappointedPublicSignaturePopulationProvider`. Executing the real service's
`run_published_signature_custody_maintenance`, then reading its persisted scan,
returned `status=not_established`, `predicate_provenance=not_established`, reason
`public_signature_population_provider_unappointed`, member count 0, no monitor
refs, no lifecycle bridge refs and no outbox event. This is an honest nonreceipt.

The existing integration positive control passed once: a persisted literal
`synthetic-test-public-signature` in a `synthetic_test` static population produces
an advisory staleness event and a real lifecycle/outbox effect. The test is useful,
but it cannot establish a first governed public signature. The persister checks CAS
bytes/manifests and member bindings, not DS12 publication admission or the seven
separable PV-K01 dimensions.

Correction to the tempting first reading: `runtime/quality/public_export.py` **is**
a real redacted projection producer, so overall export is `bridge_missing`, not
`producer_missing`. Its `assert_public_export_official_use_limits` expressly
withholds authority. The missing governed record/population producer is a different
object. This task owns the successor consumer, not that record owner; existing
watcher wiring already consumes an admitted population. The cheapest honest next
step is for DS12 to supply its actual governed record/population and connect it to
that existing provider seam. No synthetic population was installed in production.

Do not overstate the blocker: no current GY promotion replay was performed, so
“first promotion remains unreachable” is `not_established`. Signing capability is
buildable with typed-empty slots; institutions gate an actual signature, not code.
This row remains open on its real record/population dependency. No test was added
or changed, and no removal probe is claimed for untouched authority mechanisms.

Backend measurement commands (each separate, from policy-engine):

```sh
env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/atlas/policy-engine/src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/core/contracts/test_scope_adjudication.py -q
env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/atlas/policy-engine/src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/integration/runtime_quality/test_published_signature_custody.py::test_every_public_signature_is_watched_for_staleness -q
```

Import readback confirmed both canonical modules and the service loaded from
`/Users/deniskopylov/polisyos/.worktrees/atlas/policy-engine/src`, using the base
Python environment read-only. A `runpy` maintenance probe reused the integration's
`_build_control_service`, called real maintenance over temporary worktree-local
CAS/SQLite and reread the persisted nonreceipt. Its first invocation named a missing
scratch parent and failed before construction: BROKEN SCAFFOLDING, fixed by using
an existing worktree-local temporary parent, retaining every assertion.

A complete Python `Path.rglob('*.py')` census read 2,621 files under
`src/polisyos/**/*.py` and 2,512 under `tests/**/*.py`. Literal-symbol distributions:

| Symbol | Source files containing it | Test files containing it |
| --- | --- | --- |
| ScopePredicateEvidenceResolver | none | none |
| ScopeAdjudicationClaimLifecycleConsumer | none | none |
| ScopeAdjudicationRecord | none | none |
| build_scope_adjudication_candidate | canonical module + contract facade | candidate test |
| persist_public_signature_population | custody module + facade | custody integration |
| StaticPublicSignaturePopulationProvider | custody module + facade | custody integration |
| UnappointedPublicSignaturePopulationProvider | custody module + facade + HTTP container | none |
| policyos.public.signature | none | custody integration |

These are literal-symbol findings, not proof that no differently named substitute
could exist. Explicit production wiring and executed nonreceipt behavior supply
the decisive evidence. Direct path check found no
`tests/unit/runtime/http/test_public_export.py`; AST enumeration found the five
candidate scope test functions. No nonexistent closure was manufactured.

### Removal probes, review, final gates and delivery

Root removal probe deliberately restored three forbidden behaviors while retaining
current nonreceipt/notice/packet-hash markers: added signature + signed URL output
to the real preview constructor; admitted URL JSON and rendered its packet plus a
verified badge in the real route; restored a public-link emitter in the internal
panel. Exit 1, with exactly these failing identities: the two preview domain
emission tests; the two unsigned panel cases; the forged route test; all eight
owner-state route cases. Malformed-input cases stayed refused. Source restoration
was checked byte-for-byte against the pre-probe snapshots (SHA-256 unchanged for
all three source files), then the focused gate returned 39/39, exit 0. This tests
actual output/admission, not absence of unused export names.

Two independent read-only reviews found no actionable blocking finding. P40 bucket:
this is the original client-issued-authority class, closed at emission and public
consumption; no further repair ladder was opened. Review explicitly confirms that
strangle is not full server-verification or governed-population closure.

Root production build `corepack pnpm exec vite build` passed (10.23 seconds main
build, plus PWA build); `node ./scripts/postbuild-security.mjs` and
`node ./scripts/check-atlas-ui-tailwind-source.mjs` each exited 0. Dashboard
`corepack pnpm run check:architecture` exited 0, no dependency violations.
The full dashboard Vitest/lint wave is pending; no complete-suite claim yet.

Root Python architecture gate returned exit 1. It reports baseline drift and the
three `acquisition_admission_bundle -> core.artifacts.{manifest,signing,write_contract}`
imports, plus required-freshness environment construction failure (copied Python
cannot load `@rpath/libpython3.14.dylib`). The exact gate has been replayed at the
slice base in the named auxiliary worktree, also exit 1; canonical finding identity-set differences are `main_only=[]`, `base_only=[]`.
The complete deep-import inputs are 2,621 `policy-engine/src/**/*.py` files plus
five controls: `architecture/public_surface/contract.toml`,
`architecture/baselines/imports/deep_import.json`,
`architecture/exceptions/guardrails.toml`, `tools/devx/architecture/guardrails.py`,
`tools/lib/imports.py`. Across all 2,626 members, changed-path intersection is empty
and base/current byte drift is empty. Those particular import findings are inherited
PRODUCT debt, owner runtime/architecture; no baseline sync is authorized here.

Freshness is a separate **INSTRUMENT** result: `_prepare_isolated_probe_environment`
uses `venv.EnvBuilder(with_pip=False)`; the copied interpreter cannot load its dylib
before a family probe runs. The complete copied-tree denominator, with the actual
probe exclusions, is 10,570 files at base and 10,572 here, and **all 25 changed paths
are included**. Thus neither freshness nor the whole gate is called disjoint or
green. No product freshness verdict exists from this failed instrument. No baseline
sync or forbidden tool edit was attempted.

## Proposed incidental rows

- Proposed follow-up `atlas-public-verification-record-bridge`: the browser strangle
  leaves the actual server-backed PUBLIC record/certificate and PV-K01 verification
  vector unimplemented. Reuse the existing export producer, keep promoted-record
  slots typed-empty, and do not promote projection/custody scans into issuer or
  current-authority verification. This is a successor proposal, not closure of
  the owned badge or population row.
- Proposed tool-owner investigation `isolated-freshness-python-dylib`: repair the
  copied-interpreter environment construction in
  `tools/devx/architecture/guardrails.py::_prepare_isolated_probe_environment`,
  then run actual freshness probes. The failure precedes those probes and is
  INSTRUMENT, reproduced at the exact slice base. No tool change in this diff.
- Hand back the inherited runtime/architecture import set for
  `acquisition_admission_bundle -> core.artifacts.{manifest,signing,write_contract}`.
  Do not silently baseline these edges; the owning lane must choose the facade or
  adjudicated import correction. Exact finding identity and input reconciliation
  are recorded above. None obstructs the public-surface repair.

## codex/ds17-confidence-ledger-risk-spend-plan analysis

**DS17-BRANCH-01: the complete amendment already landed.** Main and base resolved
to `f481538706316b0d94722fd2a3891b2067779a38`. Read-only
`git rev-list --left-right --count main...codex/ds17-confidence-ledger-risk-spend-plan`
reproduced 849 main-only / 2 branch-only commits. Walking the complete changed-path
set of both exclusive commits (all file types) found only
`policy-engine/docs/plans/active/atlas-slices/DS17-confidence-ledger-risk-spend.md`.
The branch's document blob and landed C00 `83627a1ff`'s document blob are identical:
`8f57796755b1983e8414a606e3607f40475c99f6`. Unmerged ancestry did not mean unrecovered
content; this measurement refuted that possible first reading.

The plan projects persisted GY-N11 confidence accounting into an authenticated
Cycle Board and exact-response MACHINE twin: exact rational arithmetic within a
scope, owner-derived populations, an honestly empty positive register, derived
negative coverage, declared-set and scope-locality limitations. Its amendment
strengthens content-bound witnesses, anti-narrowing, blocker algebra and
exact-or-typed-blocked projection. No PUBLIC delta claims or UI-issued authority.

**DS17-BRANCH-02: implementation landed with narrowed demonstrations.** Merge
`8c58085ca` records execution closure. Current code has the source-resolution /
re-admission producer in
`runtime/http/services/confidence_ledger_risk_spend_projection.py`, reviewer route
in `routes/governed_projections.py`, response-byte hook
`features/runs/api/useConfidenceLedgerRiskSpend.ts`, and reviewer-gated Cycle Board
panel. Existing behavioral tests cover independent witness admission, cross-scope
refusal, anti-narrowing and DOM/content mutation. The inspected
`confidenceLedgerRiskSpendTwin.test.tsx` changes caption content while retaining
semantic markers and changes honest-zero copy into an authority-positive assertion;
it expects blocked. Inspection is not a fresh pass receipt; the final dashboard
wave below is the independent live check.

**DS17-BRANCH-03: main's same-path document extends/corrects the fork.** Exact
branch-to-base whole-file diff: 243 added / 7 deleted lines. Main adds architect
rulings on MACHINE twin bounded adversary, C05 registration, demonstration restricted
to owner-producible states, and DS18 temporal ownership/reconciliation. Main
explicitly supersedes original real-artifact over-spend and Bayesian-without-coverage
demonstrations that the owner contract cannot produce; it distinguishes the built
domain over-spend gate from the absent real-source visual path. The seven removed
branch lines survive in main with `not-a-debt` prefixes. No unique amendment remains.

Bearing on these rows: DS17's marker-preserving falsifiers are a useful precedent.
Its REVIEWER/EXPERT/MACHINE confidence evidence cannot authorize public decision
signatures or scope rulings; using it that way exceeds its purpose. The stale
branch contains no print-token repair. No DS17 debt was invented from branch age.

Why the planning branch stopped: **not_established**. Its complete exclusive commit
messages are `90100917f docs(atlas): plan DS17 confidence risk spend` and
`f2c57a39d docs(atlas): amend DS17 coverage assessment`. Neither records a stop reason.
Approval-gated handback prose is not evidence of why no later commits appeared.

Recommendation: abandon **recovery work**, preserve the branch untouched.

| Option | Cost and loss |
| --- | --- |
| Recover amendment | No unique amendment exists; risks restoring superseded requirements. |
| Fold into current plan | Already done byte-for-byte by `83627a1ff`; preserve this lineage receipt. |
| Register new debts | Duplicates preserved non-closures and may misclassify future capability. |
| Abandon recovery, retain branch | No plan semantics lost; provenance stays available. Recommended. |

No mutation, worktree attachment, merge, rebase, cherry-pick, reset or deletion of
this branch occurred.
