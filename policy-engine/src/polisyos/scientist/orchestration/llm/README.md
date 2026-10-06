# LLM (`polisyos.scientist.llm`)

`llm` — gateway-first LLM runtime Scientist: конфигурирование клиентов, traced
execution, fallback routing, prompt caching и registry model profiles для control/UI surfaces.

## Роль в системе

- **Зависит от:** `core.llm`, `core.observability`
- **Используется в:** `scientist.agent`, runtime control flows, multi-model orchestration
- Пакет изолирует provider/gateway specifics от agent- и workflow-layer кода.

## Ключевые концепции

- **GatewayLLMClient** — OpenAI-compatible gateway transport.
- **GatewayLLMConfig** — env-driven runtime configuration.
- **TracedLLMClient** — observability-aware wrapper поверх raw client.
- **Profiles registry** — built-in model profiles for runtime selection/UI.
- **Fallback router / prompt cache** — supporting runtime resilience and efficiency.
- **Settlement owner** — `LLMBudgetEnforcer` can compose the actual initialized budget middleware;
  producer event settlement precedes cache publication and carries exact ledger receipts. A raw
  `BudgetState` provides memory accounting, not a durable acknowledgement.
- **Reuse owner** — `create_traced_gateway_client(cache_reuse_authorizer=...)` accepts an internal
  typed deployment-owner contract. External snapshot reuse requires a fresh actor/tenant/scope/
  purpose/exact-evidence/epoch decision. Caller metadata and CAS readability cannot grant reuse.
  Without an owner, snapshot requests invoke the provider. Pure request caching remains scoped
  to the actual principal and trusted accounting composition.

Owner decisions are operational deployment inputs; the library makes no institutional issuer
claim. Cancelled consumers do not cancel owned producer settlement. Failed or missing durable
ACK blocks reuse and remains unknown until exact event receipts reconcile; process death before
a provider completion/event is observed requires external provider evidence.

The factory explicitly binds the actual `CachingLLMClient` emitter to its traced receiver.
Manual trusted compositions pass that client's `cache_reuse_owner`; an unconfigured receiver
and bare response parser bill provider usage. The runtime issuer record authenticates the exact
request, cache key and reuse event. Another cache's issuer or copied/edited prior record cannot
grant reuse; provider/request kwargs do not install receiver authority. This operational issuer
binding is separate from the deployment owner's permission decision above and cannot be serialized.

Each eligible cache flight owns one absolute monotonic deadline through provider I/O,
mandatory completion, serialization and publication. An observed late response is still
settled; expiry refuses result/cache admission after settlement. Physical completion can
outlive that deadline when a provider or synchronous accounting/cache lock cannot stop.
Followers share the producer deadline. Cache reads recheck the supplied owner decision
before emission; custom caches must implement `put(..., admission_check=...)` at their
atomic storage boundary. An unsupported signature refuses before provider work starts.

An accounted flight records actual dispatch and join participation before awaiting the producer.
The constructor-admitted cache emitter reports the exact request, scope, receiver attempt and
physical producer identity even when completion or result admission fails. A joined receiver
retires its own undispatched intent without declaring a zero monetary charge; the physical
producer's original known or unknown settlement remains separate. Direct
`LLMBudgetEnforcer(client=CachingLLMClient(...))` composition uses the same mandatory physical
completion hook before cache publication, including late responses refused at emission. The
runtime registration is internal and cannot be installed by response metadata or request kwargs.
Atomic publication is verified here for `InMemoryPromptCache`; a foreign implementation
  requires its own conformance evidence. The owner decision itself remains a deployment
  premise, including any required atomic epoch semantics.

`GatewayUsage` keeps numeric telemetry fields and adds usage/cost knowledge statuses. Its
default zero counts represent missing evidence. The canonical SDK parser distinguishes explicit
valid zero counts, missing fields and invalid fields; cache serialization preserves those statuses.
An observed valid reported cost takes precedence over usage pricing. Missing cost is estimated
only from validated observed counts; invalid or inaccessible cost evidence remains unknown.

With an initialized filesystem ledger, `LLMBudgetEnforcer` atomically reserves all target keys
and persists an exact request intent before the client is entered. Constructor-bound live-owner
identity permits concurrent owned in-flight calls. A fresh owner blocks unresolved old intents;
unknown cost, unknown charge ACK and pending protected audit acts block intersecting new work.
Known charge receipts remain separate from required audit delivery. Supplied protected budget
audit actions retain their exact run, payload and reservation/charge context on failure. A trusted
constructor `audit_reconciler` may verify the original act and return a typed exact resolution;
`reconcile_required_audit(act_id)` neither regenerates a response nor charges again. Restoration
of an append target, a diagnostic reference or a caller-provided boolean cannot clear pending work.
Ambiguous external/provider status and audit effects need exact owner evidence; the wrapper does
not invent zero cost or blindly append a replacement act. A plain `BudgetState` has only memory
accounting. Existing deployment call sites and the factory must explicitly compose initialized
middleware to obtain the durable profile; these capabilities do not imply a deployed billing or
institutional reuse-authority contract.
The durable profile requires an explicit nonempty `run_id` on the constructor or the existing
per-call `_run_id` input; absence refuses before reservation/provider work. The library does not
invent a run identity for a missing operational scope.
The factory's traced client refuses delegated streaming when required accounting is configured;
streaming is not a supported financial completion port in this profile. Unmanaged streaming is
outside these completion receipts.

## Public API

- `GatewayLLMClient`, `GatewayLLMResponse`, `GatewayUsage`
- `GatewayLLMConfig`
- `TracedLLMClient`, `LLMClientProtocol`
- `create_traced_gateway_client(...)`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 14
- Exports: 7
- README теперь отражает profiles/fallback/cache surface, а не только gateway client
