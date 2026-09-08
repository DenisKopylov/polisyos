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
catalog is untouched. The three retired verification messages in each active
catalog are replaced by the three nonreceipt messages; their consumers were removed.

The claim is intentionally bounded: this removes the live false positive and its
emitter. It does **not** supply a server-backed verification response and therefore
is not full closure of the row's conjunctive signal. That remaining chain is
`bridge_missing` / `verification_missing`; it is not an institutional stop on
building capability. DS12's positive mechanism and record owner remain a distinct
follow-up, not a manufactured success in this lane.

Final blocker audit corrects any stronger reading: no mandatory forbidden-file edit
was established for building additional PUBLIC signing/verifier capability. Existing
`core/artifacts/signing.py` exposes Ed25519 signer/verifier implementations, HTTP
`human_decisions.py` has persistence/resolution patterns, and the public export
producer can be imported without editing it. Their existing purpose boundaries
prohibit substituting human-act custody for `publication_authority`; signature
validity alone supplies neither the PUBLIC verification vector nor currentness.
The DS12 capability is explicitly buildable with an empty promoted-record slot.
Thus the remaining capability is **unfinished**, not an institutional/file blocker.
This lane delivers the smallest repair of the current false assertion. Adding a
second constant nonreceipt behind an HTTP endpoint would not establish verification;
the substantive DS12 signing/admission/verifier chain remains an explicit successor
proposal, not a claimed closure. The population row's task grant is successor-consumer
work, not ownership of the governed record producer.

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
verifier reference in the production route, producing `signedId is not defined`:
**PRODUCT**, correctly exposed by the executing test and repaired in production.
The typecheck separately rejected a widened test `it.each` tuple: **BROKEN
SCAFFOLDING**, repaired in the fixture without changing assertions.
A formatter invocation used duplicated `policy-engine/` paths and failed
before those files were formatted; reran with git's relative-path option. These are
local invocation/scaffolding failures, not inherited product debt. The final
journal review caught and corrected the earlier grouping of the production
reference error with these scaffolding failures (P40: new classification-error class).
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

Final P31 literal census walked all 1,108 TS/TSX/JS/JSX files under
`apps/runtime-dashboard/src`; the production filter excluded `test` path segments,
`.test/.spec/.stories/.a11y.` names and `.d.ts`, leaving 623 files. It found no
`buildSignedPublicDecisionPacket`, `verifyPublicDecisionPacket`, `SIGNATURE_SALT`,
`publicUrlPath` or `phase35.viewer.verified` references. This is a literal-chain
census, supplemented by the executed intake/emission probes, not a claim about
every differently named future signer. The Trust View gate uses its own broader
filter (including `.ts` test helpers); its denominator must not be conflated with
this production-only census.

Root production build `corepack pnpm exec vite build` passed (10.23 seconds main
build, plus PWA build); `node ./scripts/postbuild-security.mjs` and
`node ./scripts/check-atlas-ui-tailwind-source.mjs` each exited 0. Dashboard
`corepack pnpm run check:architecture` exited 0, no dependency violations.
Dashboard lint (`corepack pnpm run lint`) and the three-project typecheck each
exited 0. The first full dashboard command was:

```sh
corepack pnpm exec vitest run --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000 --reporter=json --outputFile=../../_build/atlas-public-surface-full.json
```

It exited 1 after 630.981 seconds. Its complete JSON assertion set contains
1,712 passed, two failed and 30 pending assertions, plus one collection failure
and one setup-failed suite whose 28 assertions were reported as skipped.
Finding identities, not just the total:

| Finding | Root and deciding evidence | Correction |
| --- | --- | --- |
| `locale catalogs > freezes the complete quantitative-use declaration set` | **PRODUCT**, introduced here: three new refusal messages were added while the three retired verification slots remained. The frozen leaf-count check was right about that expansion. | Replace the retired `verified`, `invalid`, `errorTitle` slots with the new refusal slots in en/uk. The complete catalog walk returns 2,868 leaves each; no consumer of the retired keys remains. Keep `parity.test.ts` byte-identical to base, including its quantitative-use identity assertions. |
| `shared Trust View architecture > censuses every production consumer over the reconciled live source population` | **INSTRUMENT**: the filesystem set included the new attack helper while `git ls-files` did not until it was staged. This verdict depends on staging state, not runtime behavior. | Stage the legitimate new helper. Do not rename it to evade the scanner or change the scanner/assertion. |
| `src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts` collection | **BROKEN SCAFFOLDING**: the child process explicitly uses isolation-local `.venv/bin/python`; importing the evidence producer failed on missing `jsonschema` before assertions ran. | Install the declared frozen `test` extra in this worktree. No test or producer change. |
| `src/test/evidence/atlasHealthMetrics.test.ts` suite setup | **BROKEN SCAFFOLDING**: `beforeAll` calls `measureAtlasHealthMetrics`, whose Python source validator imports the same missing `jsonschema`; all 28 assertions were skipped. The JSON reporter retained an empty suite message, so its original exception text is `not_established`. | The declared test environment restoration also allows all 28 unchanged assertions to execute and pass. |

The offline sync first lacked cached lint Node wheels, then the test extra's uvloop
wheel. `uv sync --frozen --extra test` downloaded the missing declared packages and
exited 0; no dependency manifest/lockfile changed. Reruns with the same single-worker
flags: locale + source-census files 89/89, evidence file 33/33, both exit 0. Independent
delta review found no actionable finding; the locale parity test and scanner files
remain unchanged. The second full wave uses the identical flags; its receipt is recorded at delivery below.

Final full wave, same command with output path
`../../_build/atlas-public-surface-final.json`: exit 0, **1,775 passed / 0 failed /
2 skipped**, 507.798 seconds. A script walked every suite status AND every
assertion status in both complete JSON reports. The resolved set is exactly the
four identities above; new and remaining finding sets are both empty. This fuller
comparison corrected the first read, which missed the setup-failed health suite
because it inspected assertion failures and nonempty suite messages. Its 28 skipped
cases are now passes; the reconciliation collection contributes 33 newly executed
cases. No assertion was relaxed to obtain this green.

Real Chromium public-route execution used the app's Playwright base config with a
worktree-local supplemental config changing only the Vite webserver to isolated
port 5297, no backend and no reused server. The eight trust-framing journey cases
passed. This verifies the actual nonreceipt without an API; it is not a server
verification receipt or a complete visual-suite claim.

A further browser removal probe restored URL JSON admission into the real
`PublicationPacketPanel` and displayed `signature verified`, retaining the real
nonreceipt section and its markers. The first probe incorrectly passed the envelope
instead of `.packet` and crashed before rendering: **BROKEN SCAFFOLDING**, no removal
receipt claimed. Correcting only the probe's payload selection produced the intended
red in `captures trust-framing-frontend_signed`: the nonreceipt was visible, but the
actual packet panel count was 1 instead of 0. Restore readback matched SHA-256
`65ce53f57a276d4ae7b43230196dd6fe537fe2d103911ac5783c512a2752ecf3`.
The restored eight-case Chromium run exited 0, 8/8, in 9.7 seconds.

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

Closeout pattern pass reread P29/P31/P32/P35/P37/P38/P41 from the failure/repair
register. Actual negative runtime behavior is the acceptance signal; exact source
restoration was verified after the probes, and candidate/synthetic evidence has
not been promoted into public authority. The complete changed-path walk, all file
types from the slice base, contains 25 files: 18 dashboard, six atlas-ui and this
journal. Its intersection with forbidden/outside-grant paths is empty.

### Local delivery receipt

Source commits on attached branch `codex/atlas-public-surface`:

- `2cd7a65582e80ac7296334ce3b37a0af5536773a` — governed print-token source and projections.
- `f57aa60dfa77f16a54153f473987491e84d90ccb` — browser-authority strangle, adversarial tests and investigation journal.

After the second commit, a complete `git show codex/atlas-public-surface:<path>`
readback checked every one of the 25 changed files against disk and checked all
24 code/test paths against the pre-verification SHA-256 freeze. Both comparisons
had no drift. Branch attachment and clean status were read back, not inferred
from the staging area. This journal-only receipt is appended after that readback.
Pre-commit contrast, reduced-motion, Prettier and ESLint hooks all passed;
Prettier reported the staged files unchanged. No hook was disabled. The pre-push
hook was not invoked and no push was attempted. No GitHub plugin was used.

Disposition: print projection is repaired with the protected assertion intact.
The live browser-created verification claim and emitter are removed, with property
and removal witnesses; full server-backed PUBLIC verification remains unimplemented.
DS11 scope authority remains beyond the allowed canonical contract/Scientist paths.
DS11 public-population closure still needs the actual governed record producer;
the existing successor consumer demonstrably preserves its honest nonreceipt.
These are not four claimed closures. No DEBT/LEDGER edit or debt-ledger checker was
used to turn a nonclosure into a green status.

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
wave recorded above is the independent live check.

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


## Continuation — true public verification and scope authority

The architect accepted the print close, forged-packet reproduction, DS17 analysis
and earlier architecture attribution, and granted the verification successor plus
`core/contracts/**` and `scientist/governance/**`. Previous nonclosures above are
first-round history, not a decision to stop this continuation.

Start readback: Atlas was attached and clean at `3ad4c18eb`. Local main had advanced
one commit beyond the supplied `5df4b16e4`, to `58f8073e4`; complete path diff of that
one commit contained only debt bookkeeping and its checker. The requested
`git merge --no-edit main` fast-forwarded successfully to `58f8073e4`, the continuation
base. No debt checker was run and no row was verified against DEBT/LEDGER.
No new auxiliary worktree has been created; `atlas-lane-base` remains the named
first-round station. No push is authorized or planned.

### Investigation and pre-test mechanisms

**Verification bridge (root, with independent crypto audit).** Hypothesis before
new code/tests: exact server-owned blob/manifest/signature evidence plus a trusted
Ed25519 key binding can authenticate a server-issued verification record, with no
browser-supplied authority input. The server must resolve the actual retained bytes
and return separately falsifiable dimensions; it cannot derive institutional
issuance, promoted-record status, or current authority from a projection or custody
scan. The PUBLIC route must consume that response and the old forgery must now get
a verifier-origin refusal, alongside a positive control for genuinely signed
verification-record bytes. `promoted_record` stays type-constrained empty.

Crypto pre-probe prediction: true signing/persistence/readback verifies; removing
trusted key binding refuses; corrupted bytes/signature fail. `signed_at` and
`signer_identity` are outside the core signed statement and cannot supply trusted
issuer identity or chronology. A revoked key's core verdict precedes crypto, so
historical authenticity and current revocation must not be collapsed. The concrete
exact-evidence adapter is not exported from the artifacts facade; public FileSystemCAS
exact-byte/sign/verify APIs are the fallback to test, without a forbidden core-artifacts
edit or duplicate byte-identity mechanism.

**Scope adjudication (independent scope owner).** Re-open the previous candidate-only
path under the expanded grant. Trace a real independently resolved scope premise
through authoritative record persistence and the actual claim-lifecycle consumer.
Do not create an HTTP-owned parallel ruling. If the actual consumer requires
Scientist paths outside governance, stop only this row with those exact paths.

**Public-signature population (independent producer investigation).** Pre-probe
hypothesis: current population persistence binds CAS identities/member references
but does not admit DS12 publication authority. Installing a static population would
therefore launder supplied provenance. A real producer must derive its set from
controlled PUBLIC issuance history, independently verify each purpose/content/issuer
binding, and only then reuse custody maintenance. A separate predicted failure was
that missing population evidence produces a `blocked` scan lacking references that
its own validator requires. Both hypotheses were written before execution.

Pattern pass: P01/P02 producer and bridge reality; P05/P15 no authority laundering;
P07/P08 exact bytes, version, historical/current distinction; P29/P31/P32 property
checks and single intake/emission; P37/P38 recomputed predicate, not caller assertion.
Acceptance: real cryptographic positive plus forged/tampered negative on the
server-to-public-route chain; scope authority and population claims only where
producer, admission, persistence, consumer and semantic negative actually exist.

Work plan: investigate and test hypotheses; settle narrow interfaces; implement
independent owner files; compose through HTTP and public route; run removal probes;
freeze/review; one full dashboard wave under CI flags with isolation-local Python
first on PATH; targeted backend tests, lint/typecheck/build and architecture checks.
Root serializes full dashboard/browser runs and shared HTTP container/route assembly.
Agents own disjoint scope, population and crypto investigation files. Journal is
root-owned. No directory-wide pytest, no unrelated GY path edits.

### Continuation measurements and corrections

The first actual public-HTTP probe ran before route wiring:
`.venv/bin/python -m pytest tests/unit/runtime/http/test_public_decision_verification_routes.py -q -o addopts=''`
returned 1 failed / 1 passed. Exact red: `test_legacy_browser_token_receives_public_verifier_refusal`
received HTTP 401 rather than a verifier response; the private `/api/v1/runs` denial
control passed. PRODUCT / missing bridge, not a stale assertion or a missing test provider.

Crypto investigation used `_build/atlas-public-verification-probe/probe.py` and its
`result.json`, real FileSystemCAS and Ed25519 bytes. Valid retained evidence verified;
blob/signature corruption and absent trust refused. Altering unsigned `signed_at` to
1900 still verified. Altering the identity hint refused under strict core identity,
but removing that hint still verified with the expected key binding. A revoked key
returned `revoked` for both intact and corrupt signatures because core revocation
precedes mathematical verification. Consequently the new report binds issuer,
purpose, rule, time, document digest and locator INSIDE its signed body; deployment
trust binds key to issuer and permitted purpose. Cryptographic validity and key
revocation are separate response dimensions. None supplies the seven PUBLIC
policy-authority dimensions, which remain Literal `not_established`.

A separate exact-byte probe signed the same blob twice: the second signing replaced
its `.sig` sidecar and the earlier exact-evidence read then refused, although its
retained original signature still verified. Proposed core-owner row:
`cas-resigning-overwrites-exact-signature-evidence`. It does not block this row:
each issued report contains a fresh opaque locator and is signed once; reads never
re-sign. Core artifacts are outside the grant and remain unchanged.

Implementation correction, PRODUCT: the first crypto implementation read a manifest
attribute incorrectly (`schema`, then a speculative `schema_` message); the owner
field is `artifact_schema`. Its fixture issuance failed before assertions until
that production API use was corrected. No assertion was relaxed. Root also corrected
its own returned locator from singular `/public/decision/` to the actual registered
plural `/public/decisions/` after independent review identified the mismatch.

Tooling receipt: isolation-local Python lacked ruff. With agent pytest processes
idle, one `uv sync --frozen --extra lint --extra test --extra runtime --extra ml`
completed exit 0 and installed the declared extras. No dependency lock changed.
All later Python and lint gates use `.venv/bin/python`; dashboard child Python uses
that venv first on PATH. An agent's earlier `uv run --with ruff` failed to find its
temporary executable and is a tooling nonreceipt, not product evidence.

### DS11-SCOPE-ADJUDICATION-RECORD — remaining canonical-owner boundary

The expanded grant was exercised through investigation and a real signed-event
probe. The existing candidate contract is valid: its exact unit file
`tests/unit/core/contracts/test_scope_adjudication.py` passed 8 tests. A complete AST
census of 2,621 `.py` files under `src/polisyos` had zero parse errors and found no
`ScopePredicateEvidenceResolver`, `ScopeAdjudicationRecord`, or
`ScopeAdjudicationClaimLifecycleConsumer` definitions. The existing
`ScopeAdjudicationCandidate` is in core/contracts. A candidate's authored
`recomputed` declaration is not independently resolved premise evidence.

The deciding measurement initialized a real CAS, Ed25519 key, signed owner
appointment and current claim head using the existing owner-event producer control.
An honestly signed supersession event advanced the real owner head. A second event
retained its trusted signer, owner, predecessor, successor and evidence, changed ONLY
the signed authority purpose to `scope_adjudication`, and was correctly re-signed.
`ClaimLedgerOwnerPort.append_verified_owner_event` returned `non_receipt`, `rejected`,
`claim_owner_event_rejected`; the canonical head stayed byte-identical. The honest
control advanced it. A first diagnostic tried `.status` on the advanced result
union and failed after the assertions; correcting that diagnostic and rerunning
completed exit 0 (BROKEN SCAFFOLDING in the probe printer, not a product finding).

Classification: PRODUCT / missing admitted scope-purpose lifecycle bridge. The
mandatory remaining path is
`src/polisyos/scientist/evidence/claims/head_index.py`: `append_verified_owner_event`
and complete-head replay accept the current supersession/DV purposes, not scope.
`scientist/governance/continuous/owner_events.py` is a natural allowed companion,
but changing it alone would leave the authoritative persistence/replay owner unable
to consume the ruling. No substitute HTTP record, dual-signed premise assertion,
preview rejection, or parallel claim ledger was created. The user explicitly requires
stopping this row at Scientist paths outside governance. This row is stopped at that
exact boundary; other rows continue. No scope production or test files were changed.

Source-adapter hypothesis before its next probe: reading CAS bytes under tenant
ownership does not itself prove those bytes still match the run's packet reference.
The issuer must hash the exact captured source bytes against that reference before
redaction/signing. Removing byte identity while retaining a real run, owned artifact
reference, valid JSON and all authority markers must prevent issuance. A source
corruption probe will distinguish this from report-signature verification.

That source hypothesis was **refuted before repair**. A cold corrupt source is
rejected by real run-resource binding (403 `authorization_binding_run_unresolved`).
After warming the real run route, the same corruption reaches the issuer and its
existing CAS read refuses (409 `public_document_source_unavailable`). Reading the
owner afterwards established `FileSystemCAS.get_bytes` calls `_read_verified_blob`.
No extra hash gate was added. The new test's initially guessed
`public_document_source_identity_mismatch` reason was corrected to the actual
existing refusal; the byte-identity and no-issued-record assertions stayed.
The initial cold fixture did not reach the intended issuer assertion (BROKEN
SCAFFOLDING); warming the real run first isolates that boundary. In an isolated
process, replacing only `_read_verified_blob` with an unchecked read, retaining
ownership, reference, valid JSON and signature markers, changed the response to 201
and killed `test_changed_source_bytes_cannot_issue_under_unchanged_run_reference`.
The production core file was never edited.

Another first reading was wrong: a purpose limitation is not the public-export
producer's workflow-failure predicate. The negative fixture initially changed only
`may_not_use_for=publication`; the existing producer correctly emitted a downgraded,
redacted, non-authoritative projection, which this report may authenticate without
promoting it. The corrected fixture supplies an actual `authority_result=blocked`
on the consumed export/public-packet surfaces; the unchanged HTTP 409 and empty
issuance-index assertions then passed with `authority_surface_blocked`. This is a
BROKEN SCAFFOLDING correction to the intended refusal input, not a change to the
producer or a relaxation of the refusal. The positive source fixture retains its
publication limitation; the response preserves projection-only semantics and no
PUBLIC authority. This distinction is why report authentication is not policy
publication approval.

### Verification bridge implementation and removal probes

One deployment-owned config file (`POLISYOS_PUBLIC_VERIFICATION_CONFIG`) supplies
report issuer identity, optional protected private PEM, and explicit public-key /
issuer / purpose / revocation bindings. Relative paths resolve against that file.
Missing config leaves issuance unavailable; malformed config fails startup. No
request supplies keys, documents or authority verdicts. Trust is an app-lifetime
configuration snapshot, not evidence of live key or policy currentness.

`POST /api/v1/runs/{run_id}/public-verification-record` requires the existing
PLATFORM_ADMIN permission and actual owned-run resource binding. It resolves the
run's retained packet, reuses canonical public redaction/official-use limits, then
persists a unique report and its issuance locator. The returned plural public path
is the actual dashboard route. Exact anonymous GET
`/api/v1/public-decisions/verification?record_id=...` serves only the report owner's
controlled index; it accepts no arbitrary CAS ref and exposes no unauthenticated
document. The adjacent private API retains its authentication requirements.

The report's signature covers all report fields. A real delete-and-re-sign probe
walked the complete 11-field report-model denominator: four defaulted fields
(`schema_version`, `purpose`, `publication_class`, `promoted_record`) initially
remained green when missing from signed bytes. PRODUCT, same signed-binding class
one level deeper. The repair widened to generic
`model_fields_set == set(PublicDecisionVerificationRecord.model_fields)`, preventing
model defaults from supplying evidence that was not signed. All field-omission
controls now refuse; no per-field allowlist was added.

The crypto removal replaced actual Ed25519 verification with fabricated VALID while
retaining report/signature/key markers. Exact failed identities: manifest tampering,
signature tampering, and revoked-corrupt signature. The real verifier was restored.
The full owned service test file passed 48 cases after the signed-field correction.
Configuration tests passed 15 cases. Removing strict/extra-forbid validation killed
root-extra, key-extra, coerced-string-bool and coerced-integer-bool cases; bypassing
private-key permission checks killed the readable-private-key case. Both probes were
process-local; production source stayed unchanged.

Frontend intake is strict and binds the exact requested locator to the response.
Only `report_authentication=verified` AND `cryptographic_signature=valid` AND
`report_key_status=trusted`, with complete signed context, may display the report
indicator. Every PUBLIC dimension must still be `not_established`, and promoted
record must be null. The route cancels stale work and binds state to its current
locator. The only arbitrary document field rendered is a React-escaped title.
No browser hashing, decoding or signing returned to production.

The existing forged-packet tests now require the real verifier response and its
reason before checking the public DOM. Unit removal probes removed authentication
conjuncts, exact response-ID binding, and stale-result suppression while retaining
markers; each failed its corresponding negative. Real API + real CAS + Ed25519 +
Vite + Chromium passed all ten dedicated cases: eight original trust-framing cases,
the real positive-then-same-ID-signature-corruption case, and the public human-decision
absence case. Corruption preserves report bytes/ID/key/time/digest and produces
`invalid`, `record_signature_invalid`, no document and no authenticated indication.
Legacy browser packets produce `invalid`, `client_token_not_server_issued`.

An actual-browser removal made the frontend authentication helper unconditionally
true while the server remained intact. The browser test first confirmed the real
invalid verifier response, then failed because the UI falsely rendered authenticated.
It therefore distinguishes an enabled verifier failure from the old constant-off
surface. Source was restored; final ten-case browser gate passed (54.3 seconds).
Earlier browser launcher failures were BROKEN SCAFFOLDING (missing optional external
security collaborators, then an untyped CAS path argument); zero assertions ran on
those attempts, and no assertions or security gates were disabled to repair them.

The source-to-export removal probe replaced only the supplied artifact set with an
empty set while keeping the canonical export producer and all generated projection
markers. The actual blocked-source test then issued a 201 report and failed its
unchanged 409/no-index assertion. It is a source-consumption check, not merely an
export-label check. The process ended; no production mutation remained.

### DS11-PUBLIC-SIGNATURE-POPULATION — reachable portion and sized residual

Measured root: PRODUCT / `producer_missing`. A static snapshot can preserve CAS
identities and arbitrary supplied member references, but cannot independently admit
DS12 issuance. The pre-implementation real-CAS probe supplied plain JSON labelled
as a signature plus an invented decision and caller-declared institutionally-supplied
provenance; the advisory watcher accepted `watched`. That is evidence about the
watcher's supplied-population contract, not evidence that a governed population
exists. No such fixture or snapshot was installed as the production provider.

Reachable work built: the report issuer now durably produces its own controlled
issuance inventory. `PublicVerificationRecordPopulationProvider` traverses that
actual inventory, calls the real verifier for every ID, checks response-ID binding,
and persists per-record diagnostics in the existing custody scan artifact. Runtime
container assembly supplies that adapter to the existing watcher. Authentic reports
with null promoted slots produce `governed_public_record_producer_missing`; corrupt
reports produce `public_record_verification_not_established`; malformed inventory
produces `public_record_inventory_unresolvable`. Predicate provenance stays
`not_established`; none creates a governed member or a watched-empty all-clear.

A distinct reachable PRODUCT defect was repaired: resolving a missing population
reference entered the watcher's blocked path, then the scan DTO raised ValidationError
because it required resolved references for that negative. The invariant now permits
an unresolved blocked/nonreceipt only with absent refs, no members, no provenance and
no lifecycle effects. Watched scans still require both resolved references. The
missing-population behavioral test passes; removing that support kills it.

Remaining producer work, sized as concrete dependencies rather than an untested time
estimate:

1. A governed DS12 PUBLIC decision record producer and admission owner must bind
   actual promoted decision bytes, purpose, issuer, scope, rule and relevant time.
   The verification-report record is not this record and its `promoted_record: None`
   is not a partially populated substitute. The new signer cannot appoint that owner.
2. That owner must supply a complete governed issuance history with publication /
   withdrawal / supersession semantics. The new local report index is an implemented
   inventory input, but makes no completeness claim over PUBLIC policy history.
3. Population construction must independently resolve each governed record to a real
   `decision_packet_ref`, nonempty `affected_claim_ids`, `published_at` and the governed
   staleness interval, then persist the actual population. These are the existing
   member contract's required inputs; caller-authored IDs or a redacted projection do
   not supply them. The report does not populate any of them.
4. The existing runtime watcher/ControlPlane bridge can consume that population and
   route observed staleness to the real claim lifecycle, but the producer's authority
   admission and current-head semantics must be proven against the canonical owner.
   The scope probe already identified `scientist/evidence/claims/head_index.py` as a
   live boundary when a new authority purpose reaches that owner. No GY path was
   changed or bypassed.

The allowed runtime/governance corridors therefore yielded a real issuance inventory,
verifier consumer, persisted negative diagnostics and a repaired negative lifecycle.
They do not contain evidence sufficient to mint the missing governed DS12 record.
The row remains open at that producer/admission gap. Building another typed positive
contract alone would not reduce it honestly.

Population removal probes: deleting actual inventory traversal killed real-inventory
and corrupt-index tests; replacing real verification with matching-ID positive
markers killed corrupt-signature and all three forged-observation variants. Exact
custody unit file plus `tests/integration/runtime_quality/test_published_signature_custody.py`
passed after restoration. No synthetic population is counted as an institutional
receipt or a closure witness.

### Existing assertion changes and review receipt

- `PublicDecisionViewerPage.test.tsx`: retained all forged-title, forged-signature,
  owner-framing and packet-panel prohibitions. Static unavailable wording now yields
  to the actual verifier reason and exact requested ID. Added positive, malformed,
  revoked/untrusted, mismatch, failure and race cases. The new property is enabled
  verification of the response, not continued feature removal.
- `trust-framing-negative-traces.spec.ts` and the public test in
  `runtime-dashboard.visual.spec.ts`: retain security assertions; require the actual
  server's `client_token_not_server_issued`. The visual public test no longer starts
  an unrelated private run-paper fixture; its forged run ID is explicitly arbitrary.
- `parity.test.ts`: only `ACTIVE_LOCALE_LEAF_COUNT` changes from 2868 to 2879.
  Complete walks of BOTH JSON catalogs found twelve new `phase35.viewer` leaves
  (recordAuthenticated, candidateCaveat, recordId, documentDigest, dimensionsTitle and
  seven dimensions) and removal of retired `phase35.openPublicViewer`. STALE
  EXPECTATION: the implemented feature deliberately requires the new vocabulary.
  Quantitative variable declarations, identity sets and hashes were not relaxed.
  Removing the new English caveat leaf while retaining the count killed the test.
- `test_runtime_api_authz.py`: strict mutating-route and permission identity matrices
  gained the actual new POST and PLATFORM_ADMIN binding. STALE EXPECTATION for that
  deliberate new route; equality assertions remain. The authorized fixture reused
  its existing secure-cell ownership helper and reaches the real unconfigured-key
  503, not an earlier source-refusal 409. Full file passed. A process-local executable
  dependency override killed the permissionless case; the independent override guard
  still denied publication with 503. This probe does not claim an authorization escape.

Independent review of the crypto service, population/index boundary, HTTP issuance,
configuration, middleware and frontend intake found no remaining demonstrated
privacy/authority escape. The identified locator mismatch and signed-default issue
were repaired and rechecked. All agent mutation probes are restored. Code freeze
precedes the final integrated gates; no other lane or prohibited owner file changed.


### Generated companions — method correction and measured divergence

The user extended the omitted grant to the committed OpenAPI snapshot and dashboard
API types and required regeneration, not application of my expectation patch. I ran
these declared commands in order, both with exit 0:

```sh
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
corepack pnpm --filter @polisyos/runtime-dashboard run generate:api
corepack pnpm --filter @polisyos/runtime-api-client run generate
```

The third is the declared downstream package generator and also exited 0. The
scratch `runtime-openapi.patch` is an expectation receipt only and was never applied.
Its expected snapshot was itself obtained from the exporter; no DS17 pin was
calculated by hand. Comparing the complete parsed regenerated document with that
snapshot found nine changed leaves, all within the existing confidence-ledger-risk-spend
200/default example. New endpoint and response-schema definitions matched exactly.
The leaf identity set is:

- `projection_hash`
- `replay_address`
- `replay_pins/projection_hash`
- `replay_pins/source_dependency_hash`
- `source/validation/bound_dependency_aggregate_identity`
- `source/validation/worker_validation_receipt_hash`
- `source_dependency_hash`
- `worker_validation_receipt_hash`
- `worker_validation_receipt_ref`

All are relative to
`paths[/api/v1/exports/governed-projections/confidence-ledger-risk-spend]/get/responses/200/content/application/json/examples/default/value`.
The three generated hash substitutions were dependency
`7f67471c394567aef3cc706a73a79d166f3ff82fd7ae2a7668be437bbfe4cc81` →
`77046db504735018dce503dddf4f8fa1962076c117c3e07dcd3d5e252f22f0fe`, projection
`19054e5fb9023e1d0054560533cbcc2ba77ddf80c7b10b7384404e0a8f3664e2` →
`d422a221ccc0b021ce61bd058ef80c289652af35951b928eb65a98efcb7b9a41`, and worker receipt
`2f13057c84b687e4fbd647a8909b35e9afb301f18f8f171261e2eb778d25a38f` →
`975b9b1be88deac320e8fc98b9d011f17195f9abcaee5ee8eb4acf3d2d4609eb`.
The actual current schema differs from the earlier read, and its derived pins are
kept. The source changed between exports: configuration now imports the documented
`polisyos.core` artifacts facade instead of the disallowed direct deep import.
`openapi-expectation-comparison.json` retains the complete expected/actual leaf values.
No stable-pins claim was made across that source change.

Regeneration then exposed a PRODUCT defect that the previous dashboard typecheck
could not observe: the runtime client generator emits its fallback `JsonValue` and
also emits the new OpenAPI schema named `JsonValue`. The canonicalizer preserves both;
TypeScript reports TS2300 twice. This is my newly exposed failure, not an inherited
red to ignore. The first generated full dashboard wave was deliberately cancelled
(exit 130) after this failure so source can be frozen again before the final wave.
The passing runtime API drift gate alone did not detect this compile error.

Before testing the repair direction: a public-report-specific recursive JSON schema
could preserve the exact JSON value grammar while avoiding the generic helper-name
collision; permissive `Any` or hand-edited generated aliases would not be honest
substitutes. The forbidden tools generator needs its own exact handback if that
measured namespace repair is sufficient for the current row. That hypothesis will
be tested before a DTO change.

Public-surface inventory checks also report two Atlas-owned drifts: the JSON
inventory and public-surface reference need the four new continuous-governance facade
exports (72 → 76). These are separate from the three adopted inherited acquisition
imports. A scratch generator run produced a 22-line JSON diff and 31-line reference
diff; the generated-artifacts reference was byte-identical. Permission for those
omitted companions and the required compatibility fragment is pending while
independent verification continues.

The first scoped-alias reading was refuted before repair: a plain recursive union
under strict Pydantic configuration still accepts `Decimal("1.1")` through its float
branch, while the original JsonValue rejects it. That union is not an equivalent
replacement. The follow-up must preserve rejection of non-JSON Python values and
prove the actual exported schema/client compiles; a rename alone is insufficient.
The real generator reproduction also showed Pydantic JsonValue exports `{}` and
therefore projects as `unknown`, not the recursive JSON grammar I expected. This
is an additional reason to measure an explicit schema without relaxing validation.


The user granted both public-surface companions and the authored compatibility
fragment. The exact declared command
`uv run python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline`
exited 0. Both regenerated files are byte-identical to the scratch generator previews;
the expected patch was never applied. The before/after git-status set added exactly
`architecture/public_surface/inventory.json` and `docs/reference/public-surface.md`,
with no removed statuses or unexpected paths. Branch attachment and both `.venv`
`.pth` files are byte-identical before/after; the editable install still points to
this Atlas product root and its `src`. The deep-import baseline and generated-artifacts
reference did not change. Receipts: `sync-before.json`, `sync-after.json`,
`sync-comparison.json`, and `public-surface-regeneration.log` under the probe root.
No freshness probe was invoked by sync and no freshness claim is derived from it.

The authored release fragment states the consumer correction plainly: the earlier
browser-computed verification claim was false; this continuation provides an
authenticated server report with all governed-public dimensions still withheld.
It is committed release input (`source_committed`); the user confirmed the directory's
structure exception was renewed on 2026-09-07 with a dated basis.

Proposed row — `public-surface-reference-missing-generated-artifact-registration`,
proposed owner team-architecture. `docs/reference/public-surface.md` identifies itself
as generated and names the canonical guardrails sync command, but the
`public-surface-inventory` registry family declares the inventory JSON and its
architecture directory, not this reference document. Proposed close: explicitly
register the reference output with its source, committed policy and freshness
binding. The standalone guardrails check currently does compare the rendered document,
but that does not supply the missing per-artifact registry declaration. The registry
is outside this grant and was not changed.


### Integrated gate receipts before the final JSON-schema delta

- Full dashboard: `PATH="<Atlas product>/.venv/bin:$PATH" corepack pnpm exec vitest run
  --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000 --reporter=default
  --reporter=json --outputFile.json=../../_build/atlas-public-verification-probe/dashboard-final.json`
  exited 0: 1,790 passed, zero failed, two skipped; 404 passing files and one skipped
  file; 564.70 seconds. Complete JSON `fullName`/status identity comparison against
  the prior Atlas dashboard receipt found `removed=[]`, `status_changes={}`,
  `failures=[]`; fifteen additions are the enabled public-viewer cases. Receipt:
  `dashboard-identity-delta.json`. This predates generated-companion completion and
  is not presented as the final regenerated dashboard result.
- Scoped Python integration: seven exact files (verification service, configuration,
  routes, container, epoch container, custody unit and custody integration) passed
  87 tests in 4.23 seconds. The first aggregate invocation cleared pytest addopts and
  omitted the configured importlib mode, causing a same-basename collection collision.
  BROKEN SCAFFOLDING: restoring `--import-mode=importlib` made the assertions run;
  none changed. No directory-wide pytest was run.
- Configuration's direct core import introduced one new architecture violation.
  Using the existing documented `from polisyos.core import artifacts` facade removed
  that edge. Configuration and routes passed all 21 tests after the correction;
  scoped Ruff passed. This is my corrected import violation, not an inherited one.
- Dashboard full ESLint, all three TypeScript projects, dashboard architecture,
  changed-frontend Prettier, Vite production build, postbuild security and Atlas UI
  Tailwind-source checks passed before regeneration. The later generated-client
  TS2300 supersedes that earlier TypeScript green and is being repaired explicitly.
- After the inventory regeneration, the complete architecture finding set is exactly
  the adopted acquisition-admission edges to `core.artifacts.manifest`,
  `core.artifacts.signing` and `core.artifacts.write_contract`, plus the baseline
  drift reporting those same three. The two Atlas-owned surface drifts disappeared;
  no findings were added. Full finding-identity delta is in
  `architecture-companions-finding-delta.json`. The gate remains exit 1, not green.
  I did not accept those imports into the baseline. The user-adopted GY attribution
  and original complete 2,626-member comparison remain the ownership receipt.
- The declared inventory sync does not exercise isolated freshness. That separate
  tool instrument is registered as unable to construct its interpreter; I do not
  reinterpret its failure as a product verdict or claim freshness from skipping it.
  Direct exporter/client drift checks are separate, scoped receipts.
- The authored compatibility fragment passed the existing release compatibility
  validator on this exact fragment: `errors=[]`, `findings=[]`.

Incidental proposed scaffolding investigation: passing HumanDecisionGate tests emit
unhandled acquisition-route MSW diagnostics during the full dashboard run. They did
not fail the current row and were not repaired or reclassified as product evidence.


The measured JSON repair retains the existing Pydantic `JsonValue` validator via
`WrapValidator` and gives its wire grammar a scoped recursive
`PublicDecisionJsonValue` alias. A direct named alias of JsonValue was also tested
and rejected: FastAPI still exported both components, retaining the collision.
No tools or generated outputs were edited. The service and response contract reuse
the same alias. The exact grammar, including recursive arrays/maps and null, is now
visible to the client generator instead of `{}`/`unknown`.

A new behavioral regression runs the actual response model through FastAPI OpenAPI,
the real runtime client generator and TypeScript compilation. Its consumer accepts
nested JSON values and requires compile errors for nested functions and undefined.
Before repair it failed TS2300 on duplicate JsonValue; after repair it passes.
Seven added service cases preserve nested bytes/tuple/set/Decimal/datetime/non-string
map-key rejections and every accepted JSON primitive's exact type through real
issuance and verification. Service/configuration/routes/schema together passed all
77 tests in 2.93 seconds; scoped Ruff passed. The cross-language schema test requires
the workspace Node/TypeScript dependencies from the normal pnpm install, and uses
`sys.executable` for its Python generator child rather than an unpinned `python3`.

Final regeneration after the measured JSON-source repair was again through the declared
commands. Complete comparison with the original expectation now has thirteen changed
JSON paths: the nine derived DS17 fields above, the owner-derived
`source/validation/bound_dependency_count` (6314 → 6315), removal of empty `JsonValue`,
addition of the explicit recursive `PublicDecisionJsonValue` schema, and the public
document field reference to that schema. The final dependency/projection/receipt
hashes are respectively
`a0c09198556aaba5842b019ef6e716eb9bb65f79fb4a7c9988196ff778cef951`,
`30666a461fe22adfee2d35691798bec5510b44c8656994ff2fdb87f2e91b9509`, and
`ab1cbbaf8d4fb69eb5729a801905dd6430680b1b66b07911caaf194b2263a753`.
These are exporter outputs, not authored pins. The complete value pairs are retained
in `openapi-final-expectation-comparison.json`; every difference from the initial
expectation is accounted for here.


The full regenerated typecheck refuted the first complete-client claim. Raw client
compilation passed, but both `openapi-typescript` outputs failed TS2502: their
`components.schemas.PublicDecisionJsonValue` property refers to itself through a
recursive union. PRODUCT, same schema-to-consumer class one level deeper (P40), not
a new authority failure and not broken dependency scaffolding. The new regression
covered only one of the two generators, which was insufficient for this repository's
actual consumer chain. The second full dashboard attempt was cancelled (exit 130)
before accepting a result from a source tree that needs another measured correction.

The mechanism is now widened to the complete generator chain: actual FastAPI schema,
raw generator, actual openapi-typescript output, and typed consumers of both. The
next hypothesis is an explicit recursive JSON graph whose array/object boundaries
are separate components, preserving the original strict validator; this lets each
generator express recursive containers without a self-referential interface union.
It must compile both outputs and preserve negative assignability before source is
changed. No generated file or expectation is edited to hide the type error.


Proposed tools-owner row — `runtime-client-generator-helper-component-alias-collision`,
proposed owner team-runtime with team-frontend. The actual generator emits its
compatibility `JsonValue` alias unconditionally, then emits a same-named component.
A minimal schema with `JsonValue: {type: string}` reproduces duplicate TypeScript
identifiers in both raw and canonical clients. This is independent of the public
report's authority semantics; the scoped explicit report grammar avoids this input
without pretending the general generator defect is repaired.

Exact unapplied handback below. The agent applied it only to a scratch copy of the
generator and compiled the original reproducer successfully. `tools/**` stays untouched.
The aliases are derived from the complete component mapping, not an enumerated list
of route names. This handback addresses the measured helper/component collision;
it does not purport to repair the separate indexed recursive-union projection.

```diff
--- a/tools/ops_runners/runtime/generate_runtime_client.py
+++ b/tools/ops_runners/runtime/generate_runtime_client.py
@@ -357,8 +356,0 @@
-        "export type JsonValue =",
-        "  | string",
-        "  | number",
-        "  | boolean",
-        "  | null",
-        "  | { [key: string]: JsonValue }",
-        "  | JsonValue[];",
-        "",
@@ -365,0 +358,22 @@
+    component_aliases = (
+        {
+            _ts_type_name(name)
+            for name, schema in components.items()
+            if isinstance(schema, dict)
+        }
+        if isinstance(components, dict)
+        else set()
+    )
+    if "JsonValue" not in component_aliases:
+        lines.extend(
+            [
+                "export type JsonValue =",
+                "  | string",
+                "  | number",
+                "  | boolean",
+                "  | null",
+                "  | { [key: string]: JsonValue }",
+                "  | JsonValue[];",
+                "",
+            ]
+        )
```


The widened probe also refuted the single Value/Object/Array schema alternative:
TS2502 remained, and OpenAPI/canonical consumer exclusions remained ineffective.
No source edit from that experiment was carried forward. The alias-repair ladder
stopped. The row is larger than initially sized because the generation path itself
cannot currently emit this supported JSON type for all consumers.

The missing generation transform is reachable within the grant: both declared
wrappers are under `apps/runtime-dashboard/scripts/` and
`packages/runtime-api-client/scripts/`. Its absence is therefore not a file boundary
or an architect decision. The next mechanism is a shared generic transform of the
actual generated TypeScript schema-reference graph: derive recursive strongly
connected components, express their types as named aliases, and route component
properties/references through those aliases. Keep nonrecursive bytes stable, retain
all recursive JSON exclusions, and run it from both declared generator commands.
This changes the producer for the actual quantity the property needs (the complete
recursive component graph), rather than adding another special case for this record.
It must fail the same complete-chain compiler probe when removed while component
names and schema markers stay. No tools-owner helper-alias fix is smuggled into this
work; that separate measured collision stays the unapplied handback above.


The shared generation transform passed the widened real-path test. It uses the
TypeScript AST to derive every `components.schemas` reference, computes strongly
connected sets and lifts recursive members into private aliases. References among
those members, including across recursive sets, bind to the aliases. Existing
identifiers are reserved before allocating names; nonrecursive property spans stay
byte-identical; a second pass is idempotent. Unguarded cycles fail explicitly rather
than becoming `unknown`. Both declared generator wrappers now invoke this same source.
No JSON value validator was changed again after the first strict wrapper repair.

Verification after the shared transform: all 77 focused Python cases passed in
7.01 seconds, including the complete raw/OpenAPI/canonical consumer compiler test;
package tests passed 8/8. The sibling compiler test covers self recursion, mutual
recursion, cross-component edges, a preoccupied alias name, and nested type
exclusions. This is generic over the actual graph, not an enumerated report-name
allowlist. Independent delta review found no demonstrated blocker and confirmed
CI provides Node 22 plus the frozen workspace for the cross-language pytest.

Removal probes remain decisive: bypassing the transform while preserving original
component names and schemas reproduces TS2502 and four unused negative directives
(function/undefined exclusions in the OpenAPI and canonical consumers). Replacing
the helper with an identity function kills both helper unit tests. Earlier probes
bypassing the original JSON validator kill all six nested invalid-value cases, and
erasing verified values while keeping report/signature markers kills the round-trip
case while authentication remains verified. No mutation process remains running.
Receipts are under `client-collision/removal-*.log`.

The package-local source inventory now names the new helper and compiler test, plus
the touched declared generation shell. Exact import expectations were added for the
new helper/test; all comparison logic stays unchanged. No external generated-artifact
registry or tools source was changed. The remaining package import-map mismatches
are being reconciled only after reading their deliberate consumer changes; the whole
gate is not being labelled inherited because this repair touches its denominator.


The two package import-map mismatches are STALE EXPECTATION with positive history
and consumer evidence. Commit `61ce304dde33` (2026-09-02) deliberately added
`./types.js` to the type test so DecisionGrade is checked against generated schema
components. Commit `17a36756c460` (2026-08-24) deliberately added the canonical client
and its real evidence-byte, exposure-header and POST-body forwarding test. The
package README and exports support both entrypoints; the import-map check last
changed at `7050786f2e18` (2026-07-17), before those consumers.

Exact expectation changes in `packages/runtime-api-client/scripts/check-architecture.mjs`:
the type test keeps `./canonicalRuntimeApiClient.js` and adds `./types.js`; the runtime
test keeps `./runtimeApiClient.js`, `node:assert/strict`, `node:test` and adds
`./canonicalRuntimeApiClient.js`. Strict sorted equality is retained. Deleting each
required import in a disposable package copy while retaining test bodies/markers
kills the check; an unapproved extra import also kills it. Package architecture now
passes. Neither consumer was changed to satisfy the map. Receipt:
`client-collision/architecture-removal-results.json`.


### Delivery wave (continued after midnight, 2026-09-08)

The delivery exporter retains the same thirteen expectation-difference paths; no
paths were added or removed relative to the prior complete comparison. After the
full-chain regression source froze, its recomputed dependency/projection/receipt
hashes are respectively
`98a4dc346466eb0af5e86ec27e2433662b3a1aad79f7bdddc0200be9c330ffcb`,
`e3b9f6f8b9207ece3f63c7cf535119f81ada82c6d6976dbba500206517322d9f`, and
`bf674ce2e94643002f12db8880cc42f96a77b18c4236425958f313360536aa2f`;
the bound dependency count remains 6315. Receipt:
`openapi-delivery-expectation-comparison.json`. The generated outputs were never
patched or hand-edited.

All six client/type artifacts are byte-identical to fresh output-root runs of the
two declared commands: dashboard `src/api/types.ts`, and package `types.ts`,
`runtimeApiClient.ts/.js`, `canonicalRuntimeApiClient.ts/.js`. The final actual
OpenAPI/client contract check exited 0. These directly exercise generation and
compare its bytes, without relying on the broken isolated freshness instrument.
Both delivery typechecks and both app/package lints passed. The final exact eight
backend files passed 95 tests in 53.42 seconds; scoped Ruff passed all twenty changed
Python files. Complete freeze comparison found `source_changes_since_freeze=[]`.
Architecture's finding identity set is unchanged: only the three adopted acquisition
imports and their baseline drift remain; no newly introduced finding is carried.

The first delivery browser attempt exited 1 before any test ran: its web server
missed the unchanged 120-second startup limit. I had started full Vitest, backend,
API check, build and architecture work concurrently. Process receipts show multiple
CPU-active Python/TypeScript/Chromium processes on an 8-core, 16-GiB station; they do
not prove a particular memory-pressure diagnosis. I cancelled my extra full Vitest
and build attempts (exit 130), allowed backend/API/architecture to finish, and
started the exact browser command separately with unchanged source and timeouts.
This is a startup/instrument hypothesis to test, not evidence of a public-verifier
regression. The failed startup contains zero assertion receipts and is not called
a passing browser test. `delivery-concurrency-receipt.json` preserves the observation.


The exact separate browser retry started its server with the unchanged timeout,
confirming the prior startup refusal was INSTRUMENT under the concurrent run rather
than a missing runtime provider. It then produced seven passing cases, including
real positive → same-ID corrupt signature and public human-decision absence, and
three new failures before verifier assertions. Exact failed identities:
`captures trust-framing-disputed`, `captures trust-framing-stale`,
`captures trust-framing-override_approved`. Each failed at the new
`(await verifierResponse).json()` waiter with CDP `Network.getResponseBody: No data
found for resource with given identifier`.

Before repairing this waiter: a response-header event may select the first request
that React StrictMode subsequently aborts; waiting for the matching request's actual
completion should provide the real verifier response body without weakening any
assertion. The failed traces must establish the aborted/header-only selection before
changing this scaffolding. The production verifier was not changed in response to
these three failures. No retry result is substituted for the missing assertions.


The waiter mechanism was established before repair from both traces and live
lifecycle diagnostics. All three failed traces had two identical verifier URLs:
the first response was 200 with no retained body, while the second retained the JSON.
Live diagnostics then bound the missing first body to an AbortSignal from
`PublicDecisionViewerPage` cleanup / React `disconnectPassiveEffect`, followed by
`requestfailed net::ERR_ABORTED`. The second request reached `requestfinished`.
The original header selector chose the first response in its failing cases.

Classification: BROKEN SCAFFOLDING. The verifier/UI assertions were right and did
not run because the waiter selected response headers before successful body
completion. Exactly three e2e files changed their verifier waiter to select the
matching native `requestfinished` event and then obtain that request's response:
`trust-framing-negative-traces.spec.ts`, `runtime-dashboard.visual.spec.ts`, and
`public-decision-verification.browser.ts`. No independent API request, route mock,
response substitution, timeout increase, production change or fixture change was used.
A full-file TypeScript AST comparison found every `expect` expression byte-identical
before/after (`browser-waiter-investigation/unchanged-assertions.json`).

The original-selector control failed `trust-framing-stale`,
`trust-framing-override_approved`, and `trust-framing-frontend_signed` at `.json()`;
the other five legacy cases passed. The repaired complete real-browser gate exited 0:
10/10 passed in 1.1 minutes. Trace reread confirmed the adversarial first response
still had no body in stale, override-approved, frontend-signed and the sibling public
visual test. The second completed response supplied actual JSON and all unchanged
assertions ran. This is a measured scaffolding repair, not a fortunate no-abort run.
Focused ESLint and diff checks passed. Original/repaired logs, traces, lifecycle
summaries and the exact waiter delta are under `browser-waiter-investigation/`.
The new freeze differs from the prior one only in those three e2e waiters; all other
source and generated companions are byte-identical.

Production Vite build and both `postbuild-security.mjs` and
`check-atlas-ui-tailwind-source.mjs` passed after complete generation. The final
full dashboard invocation is now running by itself with the same CI worker/timeouts
and the local venv first on PATH. No pre-push hook has been invoked or disabled.


### Final verification receipt and row dispositions

The final full dashboard command exited 0 in 953.65 seconds:

```sh
PATH="/Users/deniskopylov/polisyos/.worktrees/atlas/policy-engine/.venv/bin:$PATH" corepack pnpm exec vitest run --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000 --reporter=default --reporter=json --outputFile.json=../../_build/atlas-public-verification-probe/dashboard-serial-final.json
```

It ran alone from `apps/runtime-dashboard`: 404 files passed, one skipped;
1,790 tests passed, zero failed, two skipped. The complete JSON result denominator
is 405 files / 1,792 test occurrences. Identity comparison uses relative file,
full test name and within-name occurrence ordinal, preserving the repeated
parameterized names rather than collapsing them. Against the earlier continuation
receipt `dashboard-final.json`, added/removed/status-changed sets are all empty.
Against the prior delivered `_build/atlas-public-surface-final.json`, no identity
was removed and no existing verdict changed. The fifteen added identities all
passed and belong to `PublicDecisionViewerPage.test.tsx`:

- `PublicDecisionViewerPage authenticates a server record without granting decision authority`
- `PublicDecisionViewerPage does not display a late authenticated response after the record changes`
- `PublicDecisionViewerPage fails closed when the verifier cannot respond`
- `PublicDecisionViewerPage withholds the document when claimed current authority is removed or substituted`
- `PublicDecisionViewerPage withholds the document when cryptographic signature is removed or substituted`
- `PublicDecisionViewerPage withholds the document when extra authority marker is removed or substituted`
- `PublicDecisionViewerPage withholds the document when freeform authority reason is removed or substituted`
- `PublicDecisionViewerPage withholds the document when invented decision authority is removed or substituted`
- `PublicDecisionViewerPage withholds the document when malformed reasons is removed or substituted`
- `PublicDecisionViewerPage withholds the document when missing dimensions is removed or substituted`
- `PublicDecisionViewerPage withholds the document when record identity is removed or substituted`
- `PublicDecisionViewerPage withholds the document when report authentication is removed or substituted`
- `PublicDecisionViewerPage withholds the document when revoked report key is removed or substituted`
- `PublicDecisionViewerPage withholds the document when unknown status is removed or substituted`
- `PublicDecisionViewerPage withholds the document when untrusted report key is removed or substituted`

The same two skipped identities remain: DS10 capability discovery free growth
`renders the owner-index result without a dashboard identifier branch`, and
confidence-ledger risk-spend production twin `produces an exact native Chromium
receipt and restores focus and every scroll position`. No skip was introduced.
Complete identity/status sets and occurrence accounting are in
`_build/atlas-public-verification-probe/dashboard-delivery-identity-comparison.json`.
This supplements the final 10/10 real-browser, 95-test focused backend, eight-test
package, both typecheck/lint, scoped Ruff, production build/postbuild, generated-byte
and runtime-contract receipts above. Architecture is not called green: its exact
adopted acquisition-import finding set is unchanged; the broken isolated freshness
instrument was not used as a product verdict.

`atlas-public-verification-record-bridge` is **closed** by the implemented chain
and the binding removal probes. A server-issued record preserves signed report
bytes, the actual Ed25519 verifier confirms them, and the public indicator consumes
only that response. The real forged packet now receives the verifier's
`client_token_not_server_issued`; a valid issued record becomes unauthenticated
under same-ID signature corruption with `record_signature_invalid`. Forcing only
the browser indicator positive kills the real-route negative while those verifier
reasons remain. The feature is enabled and the negative is the verifier's refusal.
This discharges the remaining conjunct of
`public-decision-verified-badge-is-client-computed`. The seven governed PUBLIC
dimensions remain `not_established` and `promoted_record` remains typed empty;
report authentication supplies no governed issuance or current-authority claim.

`DS11-SCOPE-ADJUDICATION-RECORD` remains **open** at the measured canonical admission
and replay boundary in `src/polisyos/scientist/evidence/claims/head_index.py`, outside
the Scientist governance grant. `DS11-PUBLIC-SIGNATURE-POPULATION` remains **open**
at the four producer/admission dependencies sized above. Its reachable report
inventory, actual verifier consumer and persisted missing-producer diagnostics are
implemented, but are not a governed DS12 population. No synthetic fixture closes it.
The accepted print-token close and accepted byte-identical DS17 amendment analysis
stand; the stale DS17 branch remains untouched.

Final read-only audit found no new blocker. The complete staged delivery has 47
paths: 46 frozen implementation/test/generated/release companions plus this journal.
The grant audit found no outside-grant path; all 46 frozen hashes matched before
commit and `git diff --cached --check` passed. The normal local pre-commit hook is
kept enabled. No pre-push hook, push, debt-ledger check, rebase, stash, or mutation of
another lane's worktree/branch is part of delivery. Commit attachment and committed
file readback follow before the final handback.


### Local commit readback

Implementation commit `da73f861dbffc62db6a97a0013e4a0c99f59bede` was created on
attached branch `codex/atlas-public-surface`. The normal pre-commit hook passed
contrast, reduced-motion, Prettier and ESLint in 24.81 seconds. Every formatted
frontend file was reported unchanged; ESLint emitted only its existing ignored-file
warning for generated `src/api/types.ts` (zero errors). No hook was disabled.

After commit, a script read every delivery file from the named branch using
`git show codex/atlas-public-surface:<path>`. All 46 frozen source/companion hashes
matched; the commit's complete 47-path set had `unexpected_paths=[]` and
`missing_paths=[]`; the committed journal matched the working file. `git status -sb`
reported the attached branch with no changes. Receipt:
`_build/atlas-public-verification-probe/implementation-commit-readback.json`.
This final journal receipt is an append-only documentation companion; implementation
bytes remain frozen. Delivery stops locally at the push boundary. Nothing was pushed.
