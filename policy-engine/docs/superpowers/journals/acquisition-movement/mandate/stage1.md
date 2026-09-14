# Stage 1 — mandate intake and deterministic admission

Research owner: `/root/mandate_research`. Read-only research at attached
`codex/acquisition-movement`, commission base `28b8a1a42`. Product paths below are
relative to `policy-engine/`. No source, tests, configuration, register or ledger
were edited. Probe and execution output live in the ignored sibling `raw/` directory.

## Decision

**AM-M01 — the three rows share a missing governed deployment composition, but
are not one authority subject.** Separate the institutional act / external evidence
plane from PolicyOS receipt-verification-selection, its deterministic admission mint,
and the served request/worker consumer. The institutional mandate and currentness
signature is `integrate`; PolicyOS's purpose-scoped acquisition-admission artifact
and refusal custody are `own`. A configured signer alone does not install the
missing production authority provider. Generic non-data movement (`GY-AQ1`) and
numeric VoI decisions are further subjects and cannot be closed by this composition.

The institutional absence remains visible and blocks authority. It does not block
building the sanctioned intake, unappointed arm, request/worker bridge and durable
refusal surface: identity decision §9 items 5–6, at
`docs/system-design-decisions/policyos-identity-and-custody-boundary.md:180–220`.

## Exact rows, changed deciding variables

| Row | What the current evidence decides | Wait and remaining buildable link |
| --- | --- | --- |
| `ds15-mandate-intake-has-no-registered-task` (`DEBT-REGISTER.md:516`) | **AM-M02:** exact-name absence in the admitted active-plan body is measured; global absence of an equivalent allocation is not established. There is a named deferral with owner/caller/scope in U15-F06, but it is explicitly deferred and not an executed or commissioned successor. Ledger projection cannot settle this question. | Registration/scope reconciliation; neither an institution nor an absent executor. Use the present commission to assign the actual governed deployment intake after the root resolves the subgroup. Do not make another registration from a ledger zero. |
| `ds15-signed-v2-delegation-mandate-owner-authority` (`DEBT-REGISTER.md:435`) | **AM-M03:** U15-F02/F04/F06 and OR-N13-02/03 still describe the live service. `CurrentMandateOwnerEvidence` is an evidence DTO, and the gateway's plain mappings are not a purpose-specific unappointed institutional slot. The service's default provider is absent. | Institutional `absent/unallocated`; intake/selection `producer_missing`; gateway `implemented_but_not_orchestrated` and full served bridge `bridge_missing`. Build sanctioned deployment configuration/selection, a typed unappointed arm, gateway invocation and persisted refusal consumption. Real institutional evidence changes authority only after that chain exists. |
| `ds15-deterministic-admission-bundle-producer` (`DEBT-REGISTER.md:564`) | **AM-M04:** producer, persisted bundle path, immutable invocation map and gateway consumer exist. The signing slot is explicit and empty. The row's “signer alone” describes an isolated producer configuration, not the served chain: the production provider still cannot construct/invoke it. | `implemented_but_not_orchestrated` for the isolated bundle producer; production composition `bridge_missing`; real purpose-scoped signer/trusted identity `absent/unallocated`. Wire the existing producer through the same sanctioned intake. Do not rebuild the producer and do not call a test signature appointment. |

The older Task E statement that `deterministic_admission_bundle:producer_missing` is
stale needs a plane-aware correction: the component producer exists, but the
production workflow still does lack its producer invocation. A replacement should
name the missing composition precisely; changing the string to `ready` would be false.
This affects both the model default and emitted projection in
`src/polisyos/runtime/http/services/acquisition_action_service.py:106–111,598–612`.

## R4: registration versus projection

**AM-M02a — deciding measured set.** The independent recursive filesystem read
opened all **93 Markdown files under `docs/plans/active/`**, reconciled with the
same 93 tracked Markdown paths in the whole-tree receipt. All reads succeeded.
Removing the two explicitly non-evidentiary register/ledger files leaves **91**.
There is no case-sensitive or case-insensitive `DS15-MANDATE-INTAKE` token in those
91 files. That is a literal bounded fact, not proof that an equivalent task is absent.
No prior census denominator was copied.

The closest explicit task evidence is:

- U15-F06 in `docs/superpowers/specs/2026-09-10-uninvoked-ds15.md:64–109`: named
  `DS15-MANDATE-INTAKE`, team-runtime, exact future provider/deployment extension,
  existing decision-request/execute termini and worker replay; explicitly deferred.
- `docs/superpowers/plans/2026-09-10-uninvoked.md:71–78`: the mandate row's intended
  result is **deferred**, while other rows have executable instructions. This is
  a real deferral record, not a hidden active execution instruction.
- OR-N13-04 in `docs/superpowers/specs/2026-09-11-owner-residuals-n13b.md:53–71`:
  alias reconciliation is still owed. Its historical 90-file denominator is not
  the current denominator.

Potential nearby owners have different operative scopes: DS15 C02 consumes and
verifies external bands while excluding manufacture of either real signed artifact
(`docs/plans/active/atlas-slices/DS15-acquisition-routes.md:951–971`); GY-PA2's
current guarded-adapter standing does not appoint the sanctioned deployment intake
(`docs/plans/active/layer3-slices/GY-engine-subordination.md:2998–3046`); GY-AQ1
owns candidate non-data admission/re-entry, not institutional action authority
(same file `:5719–5726`); S7 owns shadow-loop delegation records with no production
promotion (`docs/plans/active/layer2-slices/S7-operating-model-delegation.md:24`);
GL owns legal knowledge search and claim-level applicability, not this external
agency-delegation admission (`docs/plans/active/layer3-slices/GL-legal-mandate-search-engine.md:74–90`).
The complete active-plan token candidate set is retained, but semantic allocation
under arbitrary unrecognized synonyms remains `unresolved_by_construction`.
**No matching active successor was established; no global absence verdict is made.**

**AM-M02b — the live projection has a different property.**
`tools/quality/validation/check_debt_ledger.py:389–407` inventories only
`docs/plans/active/atlas-slices` and `docs/superpowers/plans`; filenames yield
numeric DS IDs. `_parse_gy_tasks` at `:465–510` accepts GY table grammar and filters
`executed`, `not_executable`, and `not_started`. It is not a generic task registry.
Its own receipt at `:1336–1341` says ownership acts and unselected documents are
undecided. The real **GY-AQ1** registration at the current plan `:1800` has
`executed` standing and is absent from the projected open-work list. The actual
owner call reproduces that discrepancy. This is a positive witness of an existing
registration the instrument does not project; it is not evidence that GY-AQ1 owns
DS15's missing intake. The counterexample distinguishes the instrument's selector
from R4's semantic ownership question.

## Existing contracts, exact refusal chain, and termini

**AM-M03a — external evidence and authority selection.**
`src/polisyos/runtime/quality/agent_action_authority.py` already owns:

- `CurrentMandateOwnerEvidence` (`:245–270`), purpose `agent_action_delegation`,
  effective interval/currentness/revocation, version, signer identity and provenance.
- `ResolvedDelegationContract` (`:344–356`), including exact CAS hash, resource
  digest, signature and reconciliation-event references.
- `AgentActionAuthorityGateway` (`:492–553`), requiring the sealed exact DS20
  proof, signed CAS, durable event log/idempotency owners, verifier, run identity,
  resource→contract, owner→mandate and invocation→bundle mappings.
- Exact missing-contract refusal `delegation_contract_not_persisted` (`:654–656`);
  missing currentness refusal `current_mandate_authority_not_established`
  (`:694–709`). Signed evidence is reopened, then owner/purpose/time/revocation/
  rule-version/signature are tested (`:710–740`). Before effect execution, current
  contract/currentness is resolved again (`:1126–1134`).

These mechanisms should be reused. The DTO's own provenance literal is not the
external institution's appointment; the intake must resolve and independently
verify actual purpose-scoped evidence. A generally trusted key or self-described
mapping must not become the appointment predicate.

**AM-M04a — deterministic signing slot is real and narrower.**
`src/polisyos/runtime/http/services/acquisition_admission_bundle.py:90–131`
provides `AcquisitionAdmissionSigningSlot` with optional signer/verifier/identity and
literal acquisition-admission purpose. `require_configured` raises
`acquisition_admission_signer_unconfigured` before artifact write. The producer
(`:146–257`) recomputes the exact tuple, permission/resource/effect hashes, resolves
persisted delegation, writes through the authority artifact/event writer, signs,
verifies, reconciles, reads back and returns `MappingProxyType` invocation refs.
This is not a mandate-owner slot and must not be reused as one.

**AM-M03b — non-test service and external surface exist; the intake does not.**
`RuntimeContainerOverrides.acquisition_authority_provider` is `Any | None = None`
(`src/polisyos/runtime/http/container.py:78`), forwarded by `RuntimeContainer`
(`:393`). `AcquisitionAuthorityGatewayProvider` (`acquisition_action_service.py:211–231`)
only declares `for_request` and `for_job`. The service accepts `None` (`:242`) and
raises `acquisition_authority_producer_missing` (`:806–809`) from decision-request
`:325` and execute `:382`. This is before gateway/persisted PA2 decision and before
external effects. Therefore the current 503 surface is not a durable gateway refusal.

The registered termini are existing served POST routes:
`/api/v1/runs/{run_id}/acquisition-routes/{route_id}/decision-request` and `/execute`,
respectively `request_run_acquisition_decision` and `execute_run_acquisition_route`
in `src/polisyos/runtime/http/routes/acquisitions.py:167–230`.
The route maps the absent provider to service-unavailable (`:108–114`). It obtains
the frozen DS20 proof from `_MUTATION_AUTHZ` (`:98–105`), and decision persistence
is already consumed by `request_decision` (`acquisition_action_service.py:339–358`).
The worker bridge is installed by the service (`:274`); `for_job` must re-resolve
current authority for the job, not replay a stale request-time positive.
A local CLI cannot manufacture that request-bound proof to close the gap.

**AM-M03c — sanctioned composition is the required extension.**
Non-development `create_runtime_api_app` rejects any direct `container_overrides`
(`src/polisyos/runtime/http/app.py:156–167`). `RuntimeDeploymentSecurity` is
factory-only and attested (`deployment_security.py:588–640`). Its current fields
now include `epoch_deployment` (`:604`) in addition to the historical U15 fields;
that is a measured change, but still no acquisition-authority intake. Extend the
actual deployment owner with a purpose-specific typed empty/available selection
and bridge to the container. Reusing the dev override would prove a different property.

## Evidence, limitations, and acceptance

Whole-tree probe `raw/census.py` enumerated `git ls-files policy-engine` and
independently walked the filesystem: **12,935 tracked paths = 12,873 successfully
UTF-8-decoded members + 62 undecodable binary members**. No failed reads; no tracked
path missing from the filesystem walk; no untracked candidate authority document
outside the excluded research directory. Python AST parsing covered **6,208 tracked
`.py` files across all product subtrees**, with no parse failures. This probe's
camel-case symbol selector does not claim a complete gateway call graph; root's
source/tools/tests AST call receipt supplies that separate current caller census.
Dynamic registration, externally deployed code and institutional services remain
unresolved. All counts are recomputed by this research agent, not supplied by the
old journals. The boundary is all tracked product files, not all files on the machine.
The 62 non-UTF-8 members remain opaque/ambiguous for textual ownership; they are
never counted as empty authority documents. Exact text absence is bounded to
successfully decoded selected files only.

Raw evidence (SHA-256):

- `raw/census.json` — `cc9c5f2443d5169b2a3754a3e40458f7357f5a3022f1d8b0c9a409641cd89ff0`.
- `raw/active-alias-candidates.json` — `7dadc2f382f61800fa15bbfb7c38631c571c6ec061b44ed76ba3299d15df125c`.
- `raw/registration-projection.stdout` — `40629660b501240bed2f3ae30e3dc2a4edd5ecc634eabb4d4a2a6738cd5bc358`.
- `raw/registration-projection-initial-error.stdout` — retained harness error:
  omitted collector root; no product failure and no absence result was emitted.

The four-node replay completed with process exit 0. Exact command is retained in
`raw/semantic-witnesses.command.txt` (SHA-256
`999dbde7fd499b992185c89f4b7467ca941b57229fbd1ff78c929b44fc3fd699`);
complete output `raw/semantic-witnesses.stdout` has SHA-256
`c4b808d34f4db00b333696dec1f3a43a2887d8bfe0cb7af07a3cb98ff43a7830`.
Those fixture-backed component witnesses establish refusal and artifact
behavior; they cannot establish a real institutional appointment or successful served
production handshake. No positive production or world-growth claim is made.

Acceptance for later engineering: real served request → actual DS20 proof → governed
provider → typed absent/available evidence selection → existing gateway and existing
bundle producer as applicable → durable refusal or admitted decision → exact readback
on the existing surface, plus worker revalidation. Remove only provider invocation
under the identical absent-institution/request and prove the unchanged receipt assertion
fails. Preserve absence and zero effects for missing, stale, revoked, wrong-purpose,
cross-resource, malformed and present-but-unverified evidence. A signer-configured
component test alone is not this acceptance signal.

Pattern pass: P01/P02/P12 composition gaps; P05/P22/P26 authority purpose and mandate;
P29/P32/P33 substantive verification, not fixture-key appointment; P35/P36 measured
sets and finding IDs; P37/P38 absent evidence versus absent mechanism, and task
registration versus projection. Under P40 the production-intake observations are
**the same OR-N13/U15 class at a deeper consumer**, not a new per-row repair class.
The ledger-selector observation is a **different measurement class** with its
limitation already disclosed by the current instrument; no repair is proposed here.
