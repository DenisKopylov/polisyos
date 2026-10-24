# Развёртывание и эксплуатация: предпочтительные решения

R15: для OPS-08/09 обязательны также `r15_extension` в [tasks.json](../tasks.json), [технический full-cycle](15-technical-method-lifecycle.md) и [joint-model research](../research/heterogeneous-model-execution.md). Исходные criteria ниже сохранены; additions не создают второго owner.

Статус: engineering recommendations; product execution UNRUN. Реализация только после E02 acceptance и полного affected-scope rebind. Исходные критерии не сокращаются; [общие решения](00-shared-decisions.md) предотвращают второго owner. [Нормативные уточнения](decision-clarifications.md) остаются предложениями.

<a id="OPS-01"></a>

## OPS-01 — A0 source/profile commissioning and trust dossier

Исходная запись: [tasks.json](../tasks.json), `tasks[id=OPS-01]`. Review: [root-review](root-review.md#OPS-01).

### Предпочтительное решение

Extend the existing deployment topology/release dossier into a versioned commissioning receipt bound to the built source digest, lock/profile, resolved runtime posture, use grant references, source and purpose, actors/audience, stores/copies, named operator and deputy, trust generation, selected workload, stop time, owner-set spend/SLO/RPO/RTO and rollback pair. Its checker must resolve the initial trust provision from an independently authenticated operator/release path; a package signature or self-hash cannot appoint its own issuer. Mark unknown institutional premises as typed limitations and deny protected input until resolved. The receipt records choices; it does not create legal authority or a second configuration service.

### Что переиспользовать

- `policy-engine/ops/release/deployment-topology.toml@dccea950845cda5b38f026e7770c07819d31f4d9` — `deployment topology and profile entries`. The planning source identifies this topology as contract_only and says it does not establish a working deployment.
- `policy-engine/src/polisyos/runtime/http/execution_policy.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `RuntimeExecutionPolicyResolver.from_env`. Historical observation: production environment label alone does not resolve a production execution profile; rebind after accepted E02.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Define a schema-versioned receipt that references rather than duplicates grant, claim-owner, trust-root, secret, and store records; bind exact build/config digests and effective profile.
2. Resolve profile to instantiated services and check source-use evidence with a fresh consumer before the first input; label each decisive premise by how it was established.
3. Require an out-of-band initial trust provision and separately record duty owner/deputy, audience, retention, expiry, spend ceiling, and service recovery targets.
4. Keep the local candidate profile distinct from any production/institutional designation; unknown or mismatched protected premises stop only the affected use.

### Рассмотренные альтернативы

- **Treat environment variables or a self-signed deployment manifest as production authorization.** — They describe configuration but do not prove effective services, an authorized source-use grant, or independent appointment of the signing root.
- **Adopt full TUF as a mandatory release service.** — TUF is a sound reference for root rotation and rollback defense, but the existing release owner should first determine whether the exact package-update threat justifies a full implementation.

### Free-grow и ресурсы

- **data or config growth:** Add versioned profiles, source/use references, audience and operations targets through the existing release configuration owner.
- **extension boundary:** A new authority issuer, jurisdictional grant, or trust protocol requires its institutional owner and independent verifier; arbitrary manifest fields never become authority.
- **resource behavior:** Receipt and validation scale with configured profiles and referenced owners; unknown mandatory schema version or unresolved protected premise refuses commissioning.


### Миграция и восстановление

Version receipts additively and retain old history. An unknown mandatory schema or weaker effective profile blocks promotion. Roll back the application/config pair only after preserving the failed digest and history; never restore a superseded trust generation or erase later revocation.


### Композиция и owners

- Keep profile, readiness, source-right status, trust generation, and claim currentness as distinct composed predicates, with authority purpose, provenance, rule/schema version, audience, and time roles bound.
- Use owner-supplied authority only as typed evidence; candidate/operator-selected roots can prove a declared prototype boundary, not institutional competence.


### Acceptance и различающие проверки

- A real receipt binds effective services and an independently authorized root generation to the exact digest, with source-use approval resolved by a fresh reader.
- Changing only POLISYOS_ENV, adding a valid self-signature, or retaining manifest markers after removing grant/profile verification still fails.


### Входы и ответственность за их получение

- Source/rightsholder approval for purpose, query, recipient, retention, and derived-use scope.
- Institutional authority for initial trust and successor appointment.
- Named service owner decisions for audience, spend, SLO, RPO, RTO, retention, and stop conditions.


### Когда обоснованно отклониться

- Any protected pilot, non-public source, paid provider call, or externally relied-upon currentness claim requires this commissioning receipt before effect.
- A new installation/update channel or key-compromise threat may justify adopting TUF or equivalent, following a separate threat decision.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [The Update Framework Specification v1.0.37](https://theupdateframework.github.io/specification/v1.0.37/index.html) — TUF uses an out-of-band trusted root, threshold signatures, sequential root versions, expiry, persisted root metadata, and an out-of-band recovery path if the root threshold is compromised. **Граница:** TUF is a protocol pattern, not an institutional appointment, legal grant, or required PolicyOS dependency.
- [CISA Alert AA20-352A: Advanced Persistent Threat Compromise](https://content.govdelivery.com/accounts/USDHSCISA/bulletins/2b1b32d) — CISA documented the SolarWinds supply-chain compromise and follow-on identity abuse, including malicious software delivered through the update chain and valid SAML tokens minted after signing-certificate compromise. **Граница:** This demonstrates that signatures and a trusted update path do not prove benign content or continuing identity integrity; it does not define a PolicyOS threat threshold.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="OPS-02"></a>

## OPS-02 — Finite local candidate pilot

Исходная запись: [tasks.json](../tasks.json), `tasks[id=OPS-02]`. Review: [root-review](root-review.md#OPS-02).

### Предпочтительное решение

Make the first journey a loopback-only, one-host candidate rehearsal using the existing embedded ControlWorker, SQLite WAL and filesystem CAS. For this initial unmeasured rehearsal profile only, default to one active worker operation and synthetic data; a different commissioned measured profile may use higher concurrency. Use no private/sensitive inputs, and no paid provider unless the commissioning receipt grants them. The operator sets a finite expiry, workload/run bound, and spend bound before execution; no universal numeric workload is asserted. Exercise request → durable job/receipt → quarantine → separate admission → fresh read, then one permitted reuse only if current source rights still allow it. Stop on the first unknown profile, grant, effect, restore, cost, or resource premise. SQLite WAL is same-host only; do not move this profile to a network filesystem or infer volume durability from a local directory.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/routes/acquisitions.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `acquisition route`. The plan names the existing acquisition route as the local journey entry.
- `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `worker construction and run lifecycle`. Historical composition constructs the embedded worker for the local profile; rebind is required before implementation.
- `policy-engine/src/polisyos/core/artifacts/backends/config.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `artifact backend configuration`. The plan identifies filesystem CAS as the current candidate path; mount guarantees remain unmeasured.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Commission the source/use, profile, finite limit, expiry, resource envelope, secret, egress and restore method before accepting input.
2. Run the journey through existing job, receipt and admission owners; prove a fresh reader consumes the admitted evidence rather than the producer's in-memory result.
3. Use SQLite's Online Backup API or an explicitly coordinated WAL-aware backup; restore into quarantine and reconcile CAS manifests, rights and revocations.
4. Record actual costs, process/memory/scratch bounds and failure states for this pinned workload; paid calls require an approved provider-account or per-operation ceiling.

### Рассмотренные альтернативы

- **Start directly with PostgreSQL, a remote worker fleet, object storage or Kubernetes.** — Those add stores, identities and failure domains before the local end-to-end custody path and measured service need exist.
- **Use run count alone as a resource cap.** — A single oversized or concurrent job can exceed host, byte, memory or spend bounds.

### Free-grow и ресурсы

- **data or config growth:** Increase workload and source classes through commissioned profile data and existing acquisition registries.
- **extension boundary:** A new source transport or effect type needs its typed adapter and rights handshake; arbitrary live provider code is not accepted as configuration.
- **resource behavior:** Unmeasured input/decoded-byte/RSS/scratch class defers or refuses; exhaustion stops further affected work before accepted limits.


### Миграция и восстановление

Keep local SQLite and CAS on the tested host/volume pair. Stop admissions, revoke scoped credentials, drain or cancel work, reconcile unknown provider effects, preserve the failed release/config and restore to quarantine. Raw data retention remains rights-bound.


### Композиция и owners

- Job completion is not admission; captured bytes are not usable evidence until separate verification/admission and a fresh consumer read.
- A stale duty owner gates only currentness-sensitive operations; unrelated candidate work requires its own valid scope.


### Acceptance и различающие проверки

- The fresh reader can resolve the persisted receipt and admitted artifact after restart; the marker-only route fails when admission/readback is removed.
- Foreign job IDs, expired grant, worker restart, unknown charge and mismatched restore leave no false completion and no additional affected dispatch.


### Входы и ответственность за их получение

- Source owner approval for every non-synthetic input and its permitted reuse.
- Provider billing owner approval for paid use and the meaning of a hard ceiling.
- Operator-defined finite workload, expiry, budget and restore targets.


### Когда обоснованно отклониться

- Move to a separate supervised worker when process isolation or a service-owned profile requires it, after OPS-03/04.
- Move to PostgreSQL or remote storage only when approved durability/concurrency targets cannot be met by the tested local pair.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Write-Ahead Logging](https://www.sqlite.org/wal.html) — SQLite WAL permits readers alongside a writer but requires all database processes on one host, does not work over a network filesystem, and the WAL file is part of persistent state. **Граница:** SQLite storage behavior does not establish the durability or locking semantics of an untested filesystem/container volume.
- [SQLite Online Backup API](https://www.sqlite.org/backup.html) — The Online Backup API can copy a live database as a snapshot while allowing writes between brief source reads; raw file copying has failure and locking limitations. **Граница:** A database snapshot alone does not capture CAS objects, source rights, revocations, credentials, or provider-side effects.
- [fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html) — Linux fsync flushes file data/metadata, while durable publication of a directory entry may require fsync of the directory. **Граница:** Filesystem, mount, device-cache, and network-volume behavior must be qualified on the exact deployment target.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="OPS-03"></a>

## OPS-03 — Effective posture and dependency readiness

Исходная запись: [tasks.json](../tasks.json), `tasks[id=OPS-03]`. Review: [root-review](root-review.md#OPS-03).

### Предпочтительное решение

Extend the existing health and execution-policy owners so readiness reports the resolved effective profile, mandatory schema version, database and CAS checks, and required worker lease/heartbeat freshness. Keep liveness as process viability; it should not be failed merely because an external dependency is temporarily unavailable. A selected profile is ready only when its required live components actually exist and pass their checks. If a worker is required but missing or stale, refuse worker-backed admissions; keep any genuinely independent route available only if its own readiness and authority contract permits it. Report safe degraded reasons without DSNs, credentials, job payloads, or source-sensitive detail. Kubernetes readiness illustrates this semantic split but is optional.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/routes/health.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `health and readiness routes`. Historical plan observation says readiness reports lifecycle/observability but not effective profile or required worker heartbeat.
- `policy-engine/src/polisyos/runtime/http/execution_policy.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `RuntimeExecutionPolicyResolver`. The profile resolver is the existing source for policy posture; use it instead of a duplicate profile registry.
- `policy-engine/src/polisyos/runtime/http/container.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `RuntimeServiceContainer.health_payload`. Historical notes say this reports service presence/type rather than resolved policy and worker heartbeat.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Derive required dependencies from the selected profile's actual composition, not from environment-variable names or backend enums.
2. Expose versioned live status for profile resolution, database connectivity/schema, CAS root access, and heartbeat/lease age where required.
3. Derive heartbeat freshness from the configured lease/renewal contract and reject stale or absent evidence; probe reads must not imply full restore or durability conformance.
4. Separate process liveness from readiness and make affected admission consumers use the live readiness result.

### Рассмотренные альтернативы

- **Use one unconditional /health boolean or a Kubernetes probe as the property.** — A process can be alive with missing dependencies; Kubernetes routes traffic based on the probe result but does not establish PolicyOS authorization or semantic readiness.
- **Treat configured external backend or a healthy DB ping as complete readiness.** — Neither proves a running worker lease, effective security profile, CAS read path, or source authorization.

### Free-grow и ресурсы

- **data or config growth:** Required component checks grow with profile composition and schema-versioned owner health signals.
- **extension boundary:** A new readiness predicate must name its owner, source evidence and affected operations; an institution-supplied promise cannot masquerade as a recomputed health fact.
- **resource behavior:** Health checks remain bounded, read-only where possible, and sampled to a configured freshness window; unsupported mandatory checks degrade/refuse readiness.


### Миграция и восстановление

Add the health projection compatibly for operator/API readers. Unknown mandatory profile fields or schema versions produce degraded readiness. Roll back the exact service/config pair if it restores only marker-based health.


### Композиция и owners

- Classify each readiness premise as recomputed, independently reconciled, consumer asserted, institutionally supplied, or not established; the last three cannot alone turn protected readiness green.
- Readiness is a service posture projection, not a source grant or policy publication decision.


### Acceptance и различающие проверки

- A real external profile with no runner, expired lease, weaker effective profile, failed DB/schema check, or unavailable CAS becomes unready.
- Removing the live check while preserving route fields and markers keeps acceptance red.


### Входы и ответственность за их получение

- Release owner defines required profile components and freshness semantics.
- Worker and store owners expose verifiable live signals with source time and generation.


### Когда обоснованно отклониться

- A distinct readiness endpoint per operation family is justified if one global health result blocks unrelated scopes or falsely admits unrelated ones.
- A new orchestration/orchestrator technology is not justified by readiness alone.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/) — Kubernetes distinguishes liveness from readiness; readiness can remove a temporarily unable pod from service without restarting it. **Граница:** This is a Kubernetes implementation of a useful distinction, not a requirement to deploy Kubernetes.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="OPS-04"></a>

## OPS-04 — Supervised external worker composition

Исходная запись: [tasks.json](../tasks.json), `tasks[id=OPS-04]`. Review: [root-review](root-review.md#OPS-04).

### Предпочтительное решение

Add one supervised entrypoint around the existing ControlWorker/ControlPlaneStore lifecycle and handler registry. The worker shares the existing durable job records, lease generation, heartbeat, renewal, cancellation and receipt path; it must not create a second queue or scheduler. For a single Linux host, systemd is a suitable supervisor with restart-on-failure and start-rate limiting. Treat restart as process recovery only: leases constrain concurrent ownership, while an effect completed just before a crash but not yet receipted remains an unknown effect. Retry only with provider-supported idempotency or positive reconciliation; otherwise preserve the attempt as unresolved and require review. Readiness consumes the live worker signal from OPS-03.


### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/services/control_worker.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ControlWorker`. Historical plan source says the embedded worker owns leasing and handler execution.
- `policy-engine/src/polisyos/runtime/http/services/control_plane_store.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ControlPlaneStore`. Existing control-store owner is the natural persistence/lease seam; current schema migration and external composition were not established.
- `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `run lifecycle composition`. Historical plan says runtime composes the worker only for embedded mode; accepted-tree rebind remains required.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Create the external process entrypoint under the existing runtime ops-runner owner and construct the same store, handler registry and worker lifecycle as embedded mode.
2. Bind worker identity, lease generation, attempt ID, job scope and cancellation to durable job state; persist start/heartbeat/finish/unknown-effect receipts.
3. Use a host service manager for process start, restart throttling, shutdown and operator health; leave job retry semantics to the existing control lifecycle.
4. For independently rolling API/worker profiles, qualify mixed-version compatibility over the complete affected supported reader/writer/schema/rule/backend window. N-1 is only a possible minimum, not the denominator; an atomic same-host pair does not acquire a new rolling-upgrade start barrier.


### Рассмотренные альтернативы

- **Launch one runner per API process or add a new broker/scheduler.** — That risks multiplying concurrency and duplicates the current job owner before the existing lifecycle has been composed externally.
- **Infer exactly-once execution from a lease or process restart.** — A lease cannot atomically cover a remote provider effect and local receipt.


### Free-grow и ресурсы

- **data or config growth:** New supported handler classes use the existing registry and versioned job contract.
- **extension boundary:** A new transport or durable dispatch mode needs a typed adapter and retry/cancel/receipt conformance; a handler label alone is insufficient.
- **resource behavior:** Unregistered handler, stale lease, unknown side effect or missing supervisor yields refusal/unknown outcome; restart rate limiting prevents crash loops.


### Миграция и восстановление

Stop affected new claims, drain or cancel their active leases and reconcile uncertain external effects before rollback. Use the actual supported directional API/worker/schema/rule matrix from OPS-05: independently roll back a component where the mixed version is qualified; coordinate an atomic pair only when required by that selected profile. Preserve permitted old job attempts/control history and unresolved effects; do not reinterpret old attempts or require all supported deployments to roll back together.


### Композиция и owners

- A job claim is exclusive only for a valid lease generation; current source rights are re-resolved on execute, retry and resume.
- Supervisor status, worker heartbeat, job completion, receipt persistence and semantic admission remain separate signals.
- The task rollback field uses this same directional compatibility matrix. An application/config artifact pair identifies one selected component and its settings; it is not a universal API-plus-worker atomic-release requirement.


### Acceptance и различающие проверки

- Authorized durable job completes through the external runner and a fresh API consumer sees its persisted result.
- Worker absence blocks readiness; duplicate runner, expired lease, cancel/crash window and unauthorized scope cannot emit false completion.
- Under a selected independently rolling profile, the actual supported mixed API/worker/schema direction serves a durable job and its fresh result reader; rollback may change only the affected component when that direction is supported. A supported retained older replay remains readable, while an undeclared or incompatible direction refuses. Remove the real compatibility check while keeping N-1/version labels: the incompatible-pair probe fails. Atomic-pair-only profiles retain their explicitly bounded coordinated rollback.


### Входы и ответственность за их получение

- Service operator chooses supervisor, host identity, restart and shutdown ownership.
- Source/provider owners define idempotency and how unknown effects can be reconciled.


### Когда обоснованно отклониться

- Use another process supervisor only where the supported OS or institution already operates it.
- A broker is considered only if measured control-store polling/lease behavior misses approved delivery targets and a separate owner approves durable bridge semantics.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [systemd.service](https://www.freedesktop.org/software/systemd/man/256/systemd.service.html) — systemd supports restart-on-failure for long-running services, and automatic restart is subject to start-rate limits. **Граница:** Process supervision does not provide durable job leases, exactly-once effects, or cross-store transaction semantics.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="OPS-05"></a>

## OPS-05 — Control-store migrations and cross-store recovery

Исходная запись: [tasks.json](../tasks.json), `tasks[id=OPS-05]`. Review: [root-review](root-review.md#OPS-05).

### Предпочтительное решение

Give ControlPlaneStore an explicit versioned migration chain with expand → dual-compatible reader/writer → backfill/verify → contract, and keep it separate from runtime-state and CAS schema owners. Before a protected restore, pin the actual database backup/timeline and the exact CAS mount or bucket/prefix, manifest root, object inventory and version. Restore DB and CAS into quarantine, compare object hashes, owner heads and control references, then reconcile post-snapshot rights changes, retractions and revocations from their canonical owners before a fresh protected read. Define RPO over accepted events, job state, CAS references and rights history; define RTO through the first permitted fresh protected read. Neither startup time nor a database snapshot alone is recovery. Recovery proof covers material Claim Ledger/publication withdrawal, correction, supersession and reissue history as well as rights/control state. Bind each relevant journal incarnation, cut/high-water, replay floor and its mapping to restored heads. Obtain a trusted continuity witness outside the actual selected rollback closure (not a second copy rolled back with the same snapshot); this may be an independently retained permitted checkpoint/journal, not a mandatory new service. Reconcile through LIF-02 and the existing claim/publication owner, then fence fresh-read enablement against intervening material transitions. A rights regrant never resurrects a withdrawn claim. Missing, deleted or unverifiable required history/witness keeps the affected restored head quarantined or explicitly historical/verification-limited; unaffected proven scopes may proceed. Respect LIF-05 minimization and do not reconstruct forbidden history merely to make restore green. Recovery follows each native representation and lawful retention contract; verify the required retained payload or receipt, preserve explicit gaps, and permit bounded cold verification only where the selected profile allows it. Neither every historical URI nor a readable root manifest defines successful recovery.


### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/services/control_plane_store.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ControlPlaneStore.ensure_schema`. Historical plan says schema creation is internal to the store and a versioned migration chain is not demonstrated.
- `policy-engine/ops/migrations/runtime_state/artifact_cas/README.md@dccea950845cda5b38f026e7770c07819d31f4d9` — `CAS migration and ownership documentation`. The plan treats runtime state and CAS as separate persistence owners.
- `policy-engine/docs/runbooks/replay-or-restore.md@dccea950845cda5b38f026e7770c07819d31f4d9` — `replay and restore procedure`. Existing restore owner is to be extended with quarantine reconciliation, not replaced.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Add monotonic schema version checks and compatibility for every distinct supported retained reader/writer/schema/rule direction (N-1 alone is insufficient) before separately supervised API/worker rollout; preserve the existing tenant/RLS migration order.
2. Inventory the actual SQLite/PostgreSQL backup method, WAL/timeline set, CAS mount type/options, object versions, root manifest, and store topology.
3. Restore to quarantine; classify and verify the exact use-required retained payloads or allowed query/result receipts, reconcile rights/claim histories newer than the backup, then fence each protected fresh use. Unexpected missing required retained bytes fail; lawful non-retention/deletion is not repaired by reconstructing forbidden input.
4. Measure owner-approved RPO/RTO on the exact selected backend and capture migration/restore receipts.
5. Recovery proof covers material Claim Ledger/publication withdrawal, correction, supersession and reissue history as well as rights/control state. Bind each relevant journal incarnation, cut/high-water, replay floor and its mapping to restored heads. Obtain a trusted continuity witness outside the actual selected rollback closure (not a second copy rolled back with the same snapshot); this may be an independently retained permitted checkpoint/journal, not a mandatory new service. Reconcile through LIF-02 and the existing claim/publication owner, then fence fresh-read enablement against intervening material transitions. A rights regrant never resurrects a withdrawn claim. Missing, deleted or unverifiable required history/witness keeps the affected restored head quarantined or explicitly historical/verification-limited; unaffected proven scopes may proceed. Respect LIF-05 minimization and do not reconstruct forbidden history merely to make restore green.


### Рассмотренные альтернативы

- **Treat a filesystem snapshot or DB backup as a multi-store transaction.** — Database control state and CAS object publication have no shared atomic commit and can be captured at different cuts.
- **Copy a live SQLite database file or reuse local directory results for a network/container mount.** — WAL is persistent state, and mount locking, visibility, rename durability and failure behavior are specific to the tested filesystem.


### Free-grow и ресурсы

- **data or config growth:** Migration versions and immutable CAS manifests grow under their canonical owners; rights history remains owned by source/custody authorities.
- **extension boundary:** A new database, volume type, snapshot vendor or rights source needs an explicit recovery adapter and exact restore conformance.
- **resource behavior:** Restore runs as a bounded, separately admitted resource class; unavailable history, missing WAL/object, hash mismatch or unsupported mount keeps the scope quarantined.


### Миграция и восстановление

Use versioned forward migrations with the explicitly supported retained reader/writer/schema/rule directions and reviewed compatible rollback (including N-1 where supported, not limited to it). Never restore old rights over newer correction/revocation. SQLite uses its Online Backup API or equivalent coordinated WAL-aware process; PostgreSQL uses the selected dump/base-backup/WAL strategy with timelines. All targets are measured, not inherited from documentation.


### Композиция и owners

- A recovery checkpoint binds database snapshot identity, CAS manifest/root, exact mount/backend configuration, control high-water, rights/revocation high-water, material Claim/public-history cuts and replay floors, externally-to-rollback continuity witness, and relevant time semantics.
- Fresh-read enablement is a separately enforced state transition, not an operator's claim that restore succeeded.
- Derive the recovery obligation set from the selected native representation/use and actual LIF-05 retention decisions, not every historical URI. Retained payload required by that use must resolve and verify; a lawful query-only/result-receipt contract verifies its own retained result, execution binding and limitations without demanding prohibited raw input. Verified lawful erasure is an explicit unavailable dependency, never corruption silently ignored or invented permission to re-fetch. A use still requiring the erased input remains limited/unavailable; independently sufficient current evidence can support a new scoped candidate/use under its own rules, without rehabilitating the old head or inventing continuity. Distinguish loss of an object that was required to survive the backup from an object deliberately not retained. Control/head/rights reconciliation and fences precede enablement. Large archives may use bounded per-scope retrieval and verification before each protected use where the native profile permits it; do not claim corpus-wide integrity from a sampled scan or a readable manifest. Full integrity/preservation obligations, if selected, remain separately scheduled and evidenced. No universal full-payload startup scan or second archive is required.
- A historical erased parent does not by itself forbid every retained derivative. A permitted retained assessment/model/result may support its qualified use if its own retention, current-use rights and sufficient verification basis survive. Recomputations or claims needing the missing raw basis remain unavailable; a receipt, hash or displayed number alone cannot establish that sufficient basis. Apply LIF-05/LIF-07 to the actual use/dependency relation, including any valid derivative-specific rule, and retain only allowed identifiers and replay limitations. No revived old head, invented raw replay or permission to reconstruct erased input.
- Bind verification to the bytes/version actually consumed by the native CAS/read path, not a path that can change between checking and reading. Reuse an existing qualified immutable handle/version pin, read lease or verified bounded streaming contract; do not add a second archive or mandatory whole-object RAM copy/double scan. If integrity completes only at end-of-stream, dependent processing is provisional and protected use waits for that required verification; chunk-level use needs the selected native contract to establish its scope. Current-use rights/fences still apply at the protected use. Accepted E02 guarantees should be rebound and witnessed, not reimplemented. Protected use includes every integrity-dependent publication, external egress and irreversible effect: retain provisional output under existing rights/resource bounds until its required verification completes. Earlier chunk release is allowed only when the selected contract verifies and binds each released unit and does not claim whole-stream integrity; unrelated outputs need not wait.


### Acceptance и различающие проверки

- Partial required DB/CAS cut, absent required retained WAL/object, stale required rights/claim history, interrupted migration and any incompatible required supported reader keep the affected scope quarantined; lawful non-retention follows the native representation/retention contract.
- Exact tested mount supports concurrent publish/crash/restart/restore and a fresh authorized read; changing the mount invalidates conformance.
- Restore a backup containing signed S0 after a later withdrawal and reissue: a continuity witness outside the selected rollback closure plus actual claim/public replay yields the correct fresh head and permitted history. Lose/roll back that witness, delete required history, or inject a withdrawal between reconcile and enablement: the affected restored scope remains fenced. Remove the claim-history witness while retaining rights/hash markers: the false-current recovery probe fails. An independently proven unaffected scope need not wait.
- Restore a mixed lawful archive containing a retained payload, a query-only result/receipt and a verified-erased dependency. The first two support only their actually qualified uses without copying forbidden raw input; a use still requiring the erased raw basis remains unavailable, while a genuinely independent scope can proceed. Unexpected loss of a required retained object or omission of a claimed required dependency fails. Lazy verification must catch a corrupted cold object before that object’s protected use and cannot attest whole-archive integrity. Removing representation/retention classification while retaining restore markers exposes either forbidden reconstruction or false admission.
- After verified lawful raw erasure, a separately permitted and sufficiently verified retained result supports its selected historical/derivative use with explicit replay limits. A raw-dependent recomputation or unpermitted new purpose remains refused/limited; a mere receipt is insufficient. Remove actual dependency/current-use qualification while retaining erasure and result markers: both blanket false refusal and unsupported admission are detected.
- Verify a cold object, then replace its locator/version or mutate a later streamed chunk before consumption. The exact stable object supports the qualified use; changed/unverified consumed bytes cannot authorize that use. Remove verifier-to-actual-reader binding while retaining successful hash/manifest markers: the substitution probe fails. Measure bounded buffers/read work for the selected profile; no full archive scan is implied. Corrupt the final chunk and inspect the actual effect/export sink: no whole-stream-integrity-dependent partial output may have escaped before failure. A qualified independently verified chunk profile may release only its supported units. Remove the release fence while retaining final hash/error markers: the actual premature-egress discriminator fails.


### Входы и ответственность за их получение

- Database and CAS operators provide their supported backup and restore mechanisms.
- Source/claim/right owners provide current corrections and revocations after the recovery cut.
- Service owner sets acceptable RPO/RTO and legal retention scope.


### Когда обоснованно отклониться

- Move from SQLite to PostgreSQL only when the selected same-host contract or measured concurrent writes fail an owner-approved target.
- Remote CAS recovery is selected only after OPS-10 adapter and restore conformance.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [Write-Ahead Logging](https://www.sqlite.org/wal.html) — SQLite WAL permits readers alongside a writer but requires all database processes on one host, does not work over a network filesystem, and the WAL file is part of persistent state. **Граница:** SQLite storage behavior does not establish the durability or locking semantics of an untested filesystem/container volume.
- [SQLite Online Backup API](https://www.sqlite.org/backup.html) — The Online Backup API can copy a live database as a snapshot while allowing writes between brief source reads; raw file copying has failure and locking limitations. **Граница:** A database snapshot alone does not capture CAS objects, source rights, revocations, credentials, or provider-side effects.
- [PostgreSQL Backup and Restore](https://www.postgresql.org/docs/current/backup.html) — PostgreSQL presents SQL dump, filesystem backup, and continuous archiving as distinct methods with different assumptions; PITR depends on a base backup and a suitable WAL archive. **Граница:** The current docs do not select a PolicyOS RPO/RTO or prove the selected operator's backup chain.
- [fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html) — Linux fsync flushes file data/metadata, while durable publication of a directory entry may require fsync of the directory. **Граница:** Filesystem, mount, device-cache, and network-volume behavior must be qualified on the exact deployment target.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="OPS-06"></a>

## OPS-06 — Tenant, job-read and egress authorization proof

Исходная запись: [tasks.json](../tasks.json), `tasks[id=OPS-06]`. Review: [root-review](root-review.md#OPS-06).

### Предпочтительное решение

Bind every job read, artifact read and source effect at the canonical consumer boundary to authenticated actor, tenant/cell, target owner, action, purpose, source/query, recipient and time-bounded grant. Resolve the target job owner before serialization or side effects; do not equate caller tenant, opaque IDs, network policy or connector credentials with permission. Preserve same-cell delegated sharing only when the actual grant permits it. Make a known foreign job ID and an absent ID return the same not-found projection where existence itself is protected. Re-resolve grants before execution, retry and resume. Treat the suspected historical route behavior as a falsifier to reproduce after source rebind, not an asserted live leak. Keep actor, tenant, job and raw-path identities out of metric dimensions; aggregate telemetry, overflowed attributes and sampled traces cannot prove that a grant or object-owner check occurred. The exact allowed access decision belongs in the existing access/audit receipt with its own authorization and audience rules.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/authz_middleware.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `runtime authentication/authorization middleware`. The plan names this as a runtime access seam but says exact target-object behavior must be tested.
- `policy-engine/src/polisyos/runtime/http/routes/control.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `job/control routes`. The candidate path is job read and action; authorize the target object before projecting lifecycle details.
- `policy-engine/ops/cloud/helm/polisyos-cell/templates/networkpolicy.yaml@dccea950845cda5b38f026e7770c07819d31f4d9` — `cell NetworkPolicy`. Network policy is an infrastructure perimeter input, not a semantic source grant.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Enumerate every direct and indirect reader/effect consumer for jobs, artifacts, connector calls and egress; route all through the existing authz and source-right owners.
2. Resolve the target's owner and exact action-purpose-recipient grant before content fetch, output shaping or external calls.
3. Carry a content-bound grant reference and issuer/provenance/time scope with the durable attempt; re-resolve at every retry/resume boundary.
4. Return equivalent not-found projections for foreign and absent objects when disclosure of existence is not permitted; preserve authorized denial audit.

### Рассмотренные альтернативы

- **Use random job IDs or infrastructure NetworkPolicy as the authorization check.** — OWASP's BOLA guidance notes identifier type is irrelevant; a network allow rule cannot authorize a particular record, purpose or recipient.
- **Build a second general permission ledger beside existing rights/authz owners.** — It would create competing grant truth and drift; extend the canonical resolver and typed evidence path.

### Free-grow и ресурсы

- **data or config growth:** Supported action/purpose combinations extend the existing policy registry and grant vocabulary.
- **extension boundary:** A new institution, rightsholder or source class requires an authorized issuer and typed evidence mapping; missing grants never imply allow.
- **resource behavior:** Authorization binds are constant per operation; large policy or recipient sets must have explicit bounded resolution cost and deny on unresolved scope.


### Миграция и восстановление

Version tenant ownership and policy references, dry-run/backfill before enabling row-level isolation, and preserve history. On mismatch, stop the affected route/source effect, revoke the scoped grant and retain denial events; never convert network reachability into permission.


### Композиция и owners

- Foreign/absent concealment, grant validity, object ownership and egress policy are different predicates; only the applicable object/source grant can authorize the operation.
- The permission evidence carries issuer, content binding, purpose, recipient, audience and validity interval.


### Acceptance и различающие проверки

- Positive same-cell sharing succeeds only with the exact grant; absent/foreign job ID projections match; cross-cell artifact and source calls deny.
- Removing consumer-side scope resolution while leaving middleware/network labels still exposes the divergent read/effect and must fail.
- Metric cardinality overflow, suppressed labels or sampled traces never turn a denied/missing grant into an allowed read; an authorized access receipt retains the exact resolved actor, owner, action and grant evidence.


### Входы и ответственность за их получение

- Tenant/cell identity issuers, source rightsholders, legal/custody authorities and network-policy owners.
- Institution decides whether object existence should be concealed and which audiences can inspect denied events.


### Когда обоснованно отклониться

- If target authorization spans multiple services, adopt a shared existing policy owner contract only after pinning actor, object, action, purpose and decision provenance across them.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [OWASP API1:2023 Broken Object Level Authorization](https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/) — Every endpoint that accepts an object ID and acts on it needs object-level authorization; identifier unpredictability does not replace that check. **Граница:** OWASP guidance identifies the class and mitigation, not whether the historical PolicyOS job route is vulnerable.
- [Project runner registration token security update](https://about.gitlab.com/blog/security-incident-runner-registration-token/) — GitLab reported that a project runner-registration-token vulnerability could expose project-scoped tokens to unauthorized users and reset tokens as mitigation. **Граница:** This incident supports narrow credential scope and revocation readiness; it is not evidence of a PolicyOS defect.
- [Metrics: Cardinality limits](https://opentelemetry.io/docs/concepts/signals/metrics/) — OpenTelemetry metrics SDKs bound the number of tracked attribute combinations (the documented default is 2000); additional measurements are folded into an overflow point, preserving overall totals but dropping the original attribute combination. Queries grouping/filtering by those dropped attributes can undercount. **Граница:** SDK default and behavior are telemetry implementation details, not PolicyOS audit or admission contracts. Exact per-decision evidence still requires a separately authorized durable receipt.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="OPS-07"></a>

## OPS-07 — Source secret resolution and provider budget accounting

Исходная запись: [tasks.json](../tasks.json), `tasks[id=OPS-07]`. Review: [root-review](root-review.md#OPS-07).

### Предпочтительное решение

Put only a scoped secret reference in a job. The worker resolves the secret just in time through the institution's existing secret authority, exposes it only to the connector execution, never serializes/logs it, and rechecks both grant and credential generation on retry/resume. At accepted-source rebind, name and extend the existing E02 monetary/budget owner if its scope covers provider-principal reservations. Otherwise OPS-07 owns the single minimal native provider-budget extension under the declared core/security boundary; ControlPlaneStore holds attempt refs rather than a duplicate budget authority. Maintain one reservation state per provider billing principal, not one process-local or tenant-local counter. Before a call, reserve the owner-approved maximum operation cost; admit only when reconciled spend plus outstanding reservations plus the new maximum is within the approved account ceiling. If the provider outcome or charge is unknown, retain the full reservation and do not retry unless that provider's exact endpoint supports stable idempotency or usage reconciliation. If account metering is incomplete, make no account-wide hard-cap claim; allow only an approved per-operation ceiling with an explicit unknown account state.

### Что переиспользовать

- `policy-engine/src/polisyos/fabric/connectors/base.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ConnectionConfig.auth_credentials`. Historical plan notes credential values are accepted and redacted here; this is a seam for reference resolution/redaction, not a secret authority.
- `policy-engine/src/polisyos/core/security/tenant_quota.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `tenant quota model`. Existing tenant quota is distinct from provider-account spend.
- `policy-engine/src/polisyos/core/security/quota_registry.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `TenantQuotaRegistry`. Historical observation says its state is process-local and cannot establish a shared provider billing cap.
- `policy-engine/src/polisyos/runtime/http/services/control_worker.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `worker connector execution boundary`. JIT secret resolution belongs at execution, not in job creation or API payload.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Bind each secret reference to connector, source/query, purpose, actor/cell, recipient, audience and expiry; resolve it only in the worker.
2. Use the actual billing principal as reservation key and write attempt ID, idempotency key, estimated upper bound, provider usage/charge evidence and reconciliation status durably.
3. Keep unknown outcome reservations held until evidence or an owner-reviewed closure resolves them; key rotation cannot reset accrued or reserved spend.
4. Project secret-reference health and budget state without values; expose unknown cost distinctly from zero cost.

### Рассмотренные альтернативы

- **Persist credentials in job payloads or depend on process-local tenant quotas.** — Credentials can leak through logs/receipts, while process-local counters multiply across workers and key rotation can bypass the real account ceiling.
- **Retry all timeouts with a new request or treat timeout as free.** — Remote execution and billing may have occurred without a response; provider idempotency is endpoint- and retention-specific.

### Free-grow и ресурсы

- **data or config growth:** Add secret backends and billing units through typed provider adapters/configuration with versioned price/window semantics.
- **extension boundary:** A new provider needs usage/charge and idempotency semantics; unsupported billing evidence stays unknown and cannot claim hard account limits.
- **resource behavior:** Reservations count toward the cap until reconciled; exceeding ceiling refuses/defer calls, and unknown ceiling or price requires an explicit per-operation approval.


### Миграция и восстановление

Keep tenant quotas and provider-account reservations as separate authorities. Migrate in-flight attempts with stable idempotency keys and preserve price/unit/window version. On rollback revoke the exact credential and hold unknown-charge reservations; do not assume it was free.


### Композиция и owners

- Source-use grant, credential validity and provider billing authority are three different bindings.
- Record provider identity, principal, endpoint, request parameters digest, attempt/idempotency key, event/usage time and accounting rule version.


### Acceptance и различающие проверки

- Concurrent workers on one account cannot exceed the reconciled ceiling; secret value is absent from every payload, log, receipt and operator projection.
- A timeout followed by restart, key rotation or connector switch retains reservation until reconciled; removing that accounting check fails.


### Входы и ответственность за их получение

- Institution's secret manager/issuer and its audit/rotation/revocation behavior.
- Provider billing owner supplies principal, charge/usage denominator, price schedule, idempotency behavior and whether a hard cap exists.


### Когда обоснованно отклониться

- If the provider lacks usage reconciliation or idempotency, restrict to an owner-approved per-operation max and do not promise shared account hard spend.
- Adopt a shared secret service only if existing institutional secret authority cannot issue the required scoped credential.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html) — Secrets should have least-privilege access, lifecycle and audit metadata, expiration/revocation, and short-lived credentials where practicable. **Граница:** It does not prescribe a single secret manager or eliminate the need for an institution-owned root credential and source-use grant.
- [Idempotent requests](https://docs.stripe.com/api/idempotent_requests) — Stripe supports request idempotency keys for safely retrying supported operations, with provider-specific parameter matching and key retention behavior. **Граница:** Idempotency behavior differs by provider and endpoint; a timeout or this example does not prove another provider did not execute or charge.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="OPS-08"></a>

## OPS-08 — Measured resource classes and shared admission

Исходная запись: [tasks.json](../tasks.json), `tasks[id=OPS-08]`. Review: [root-review](root-review.md#OPS-08).

### Предпочтительное решение

Consume the single LIF-06 native admission contract and implement the selected host enforcement adapters; do not create a second admission authority in ControlPlaneStore. One worker is an initial rehearsal-profile setting, not a global invariant. Commission measured class concurrency and enforce the aggregate cap, and a separately measured reserve for API, OS/control and restore; unmeasured classes receive no protected admission. On Linux, cgroup v2 can bound process groups, with memory.high/PSI used for pre-exhaustion load shedding and memory.max as a final failure boundary; directory/project quotas or an equivalent owner mechanism bound scratch. The admission transaction accounts for every API/worker process on the host and holds reservations until the process/attempt is actually reconciled. Change class/concurrency policy through a scoped qualification matrix with reserve intact. Single-factor tuning is useful for diagnosis, not a permanent scheduling rule: independent isolated measurements may run concurrently, and interacting class/cap changes require matched joint-load evidence before promotion. Use bounded low-cardinality metric dimensions for operational class/profile/status and expose overflow explicitly. OpenTelemetry cardinality overflow can preserve an aggregate total while dropping the whole per-measurement attribute combination, making filtered/grouped views undercount; do not use metrics, sampled traces, or their apparent absence as exact per-job, per-tenant, admission, or audit evidence. Persist exact permitted decision/attempt receipts in the existing control/audit owner and bind their access separately. Kubernetes may supply placement and aggregate quotas where already justified, but adds no PolicyOS semantics.


### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/services/control_worker.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `worker concurrency and job lifecycle`. This is the existing worker/job boundary; shared host admission should compose with it instead of a second scheduler.
- `policy-engine/src/polisyos/core/security/tenant_quota.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `TenantQuota`. Per-tenant quota is not aggregate host admission and should remain a separate limit.
- `policy-engine/ops/components/runtime/slo.yaml@dccea950845cda5b38f026e7770c07819d31f4d9` — `runtime SLO seed`. The plan says these are report-only seeds, not measured service ceilings.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Qualify a new class in a distinct finite measurement run authorized by the platform/service owner within an already verified isolation/enforcement envelope, with a hard bulk ceiling, existing control reserve, bounded scratch/time and no new protected custody commitment. Start small and increase only within that envelope; if the host cannot enforce it, use a suitable isolated host or record the qualification as unavailable. A candidate label alone authorizes neither unsafe workload nor unknown spend.
2. Define measured classes for network, interactive, CPU, high-RSS/native threads, model/GPU, index and restore; class limits include bytes, CPU, RSS, I/O, scratch, queue age, retries and drain.
3. Atomically reserve aggregate host and class capacity in the existing shared control store before starting work; release each resource charge only after verified release of its actual allocation or reconciled transfer to another live owner. Attempt completion/termination permits release only of proven attempt-private resources; shared caches, mapped files, IPC buffers and overlapping generations remain charged for their real lifetime.
4. Apply Linux cgroup or the selected platform's native hard controls and measure PSI/peak resource use; defer or reject before owner-set ceilings are reached.
5. Test cold/warm, skewed, concurrent tenants, slow provider, OOM pressure, restart, cancel and restore; preserve semantic outcomes while saturated.
6. Place control/custody/restore in protected process groups or leave measured headroom under a hard bulk ceiling, with actual scratch quotas. memory.high may be breached and memory.max can trigger OOM; neither setting alone proves graceful completion or a protected reserve. Qualify real saturation and recovery behavior.


### Рассмотренные альтернативы

- **Use per-process semaphores, run-count tickets or Kubernetes ResourceQuota alone.** — These can multiply across replicas or cover infrastructure resources without application/provider budgets, semantic overload behavior, or a process-wide denominator.
- **Infer runtime capacity from agentparallel100 or CI concurrency.** — Those are tool/reviewer capacities, not measured production runtime throughput or memory.


### Free-grow и ресурсы

- **data or config growth:** Supported class dimensions and ceilings can grow as versioned measured policy data.
- **extension boundary:** A new enforcement dimension or OS needs a native enforcement adapter; declarations without an enforcing owner remain not_established.
- **resource behavior:** Unmeasured classes receive no protected workload or prospective custody-duty admission. Bounded qualification uses the separately permitted existing enforcement envelope; absent envelope, exhausted reserve, stale process census or unsupported hard limit defers/refuses. No silent overcommit.


### Миграция и восстановление

Version class policies and in-flight reservations; keep agent/reviewer limits distinct from runtime jobs. On pressure or guardrail violation, reduce the affected pool, drain safely and retain jobs; never relax admission to meet throughput.


### Композиция и owners

- Class membership and resource limits are institutionally selected inputs; observed usage and permit consumption are recomputed; capacity release requires reconciled allocation lifetime; process/attempt termination alone does not release shared or persistent allocations.
- Per-tenant quota, shared host admission and provider spend ceiling compose independently.
- Resource classification/measurement policy belongs to the actual platform/service owner; no new institutional act is needed for each in-envelope sample unless that owner contract requires it. Production class admission consumes completed measurements and the actual supported concurrency/terminal denominator.
- Bind a versioned profile-specific queue/progress policy at LIF-04’s existing due-intent selector: eligibility and aggregate reservations come from LIF-06, measured headroom/age targets from OPS-08. Specify priority, fairness/aging or an explicitly limited best-effort class, queue admission/expiry and a bounded terminal/review disposition. Retry must preserve original admission age. No universal numeric deadline or mandatory DRF is imposed. An unbounded service/progress promise is forbidden; adverse load yields the declared defer/cancel/refusal/review result. Custody/revocation/reconciliation duties cannot disappear on queue TTL: retain their durable obligation and expose overdue/coverage loss through the existing owner.
- Accounting may use a conservative enforced process/pool envelope with verified shared-allocation ownership and reconciliation; no per-Python-object tracing or universal allocation ledger is required. Uncertain lifetime retains the relevant conservative charge/headroom bound rather than inventing free capacity. Partition or aggregate only when the physical bound remains valid.
- Treat review-required as an unresolved service/coverage state, not a terminal service success. The existing duty owner binds the actual review owner, triggering evidence, next wakeup/escalation or owner-permitted cutoff/transfer and original admission/due age; a callback, repeated review marker or fresh retry ID alone cannot discharge the duty or reset its clock. A class promising service/aging needs actual service progress within its commissioned bound; a class declaring best-effort may expire/refuse without that guarantee, with a visible outcome. For custody work, missed service changes the affected claim/coverage promptly through LIF-02 even if bulk compute or review is unavailable. A review result can authorize a new bounded plan but cannot rewrite the missed interval. This qualifies the selected policy, not a universal SLA or a new human-approval gate.
- LIF-04 persists the stable duty identity, admission-policy version and committed service class/terms, original age and durable due/next-trigger generation with its existing control-store intent. Normal policy updates govern new admissions. An active-duty change is an owner-qualified recorded successor/cutoff/transfer that preserves the original promise, missed intervals and affected coverage; automatic native transitions remain allowed. Current rights, safety restrictions and enforceable aggregate caps apply immediately even when they prevent the older service promise: expose the actual lapse/limitation, never freeze unsafe permission. A wakeup is a hint: restart/reconciliation recovers due duties from durable state and fences duplicate/old generations. Use persisted effective-time semantics plus elapsed-duration clock handling; process-local monotonic values are not durable deadlines. LIF-06 supplies current eligibility, OPS-08 the measured envelope; neither rewrites the admitted commitment or creates a second scheduler. Uncertain clock/order evidence limits the promised timing guarantee explicitly.


### Acceptance и различающие проверки

- Under the commissioned workload/process and supported simultaneous-terminal denominator, multiple workers cannot multiply the cap; shared scratch/memory pressure triggers bounded defer/refusal and the measured physical control reserve remains available. memory.max/OOM is a final failure boundary, not a guarantee of graceful handling for arbitrary workloads or host failure.
- Removing shared admission while leaving per-process limit markers makes the multi-process acceptance fail.
- High-cardinality telemetry visibly reports overflow; totals remain useful for operations, while exact per-job/tenant outcomes remain available only from authorized receipts and no aggregate or sampled signal can make an admission/audit decision.
- An unknown class can produce measurements inside an existing enforceable isolated envelope while its production/duty eligibility stays unavailable. No envelope means no run. Two disjoint measurement lanes can proceed concurrently within aggregate capacity; a joint class/cap policy cannot promote from isolated results that omit their interference.
- A terminal attempt leaves a shared 60/100 allocation alive: a new 50/100 request must defer/refuse until sufficient actual capacity is released or a separately qualified capacity envelope covers it. Duplicate completion/transfer cannot release twice; privately freed resources become usable. Removing lifetime reconciliation while retaining a completion receipt fails the saturation/admission discriminator.
- Under sustained arrivals in one eligible class, an older competing job either receives its selected-policy service opportunity or reaches its declared bounded terminal/review disposition; it cannot silently defer forever. Retry preserves first-admission age, and a custody/revocation duty remains durable with a truthful overdue/limited surface. Remove aging/expiry/disposition behavior while preserving queue-age metrics: the selected progress-policy probe fails; do not claim successful execution when only expiry/refusal occurred.
- Replace real service by repeated review-required events and new retry IDs while preserving queue-age metrics: the declared service guarantee fails and the duty remains overdue/unresolved. A real review disposition either schedules an accountable continuation, makes an authorized cutoff/transfer or preserves explicit limited coverage with its next trigger; it is not counted as execution. Positive service-class work progresses under its stated load bound, while explicit best-effort refusal remains a different truthful result. Remove the overdue-to-claim reaction but retain review markers: the custody coverage probe fails.
- Admit a duty under service policy v1, switch new admissions to v2 best-effort, stop the worker across its due time, then restart with a lost/duplicate wakeup and clock movement. The old duty retains v1 or an explicit owner-qualified transition/lapse, a new duty uses v2, and current safety/cap restrictions still prevent unsafe dispatch. New retry IDs and late expired workers cannot downgrade, strand or reset the old duty. Remove admission-commitment persistence or durable trigger recovery while retaining age/current-version/wakeup markers: the downgrade/stranding probe fails.


### Входы и ответственность за их получение

- Host/platform owner exposes cgroup or equivalent controls and physical capacity.
- Service owner sets process reserve, resource ceilings, queue-age target, workload window and acceptable latency/error envelope.


### Когда обоснованно отклониться

- Increase concurrency only after each candidate step passes the commissioned matrix on the actual hardware, with no limit breach or OOM and the reserve still available.
- Use Kubernetes only if measured deployment/failure/isolation needs and an operator owner justify its additional lifecycle cost.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [Control Group v2](https://docs.kernel.org/7.0/admin-guide/cgroup-v2.html) — Linux cgroup v2 exposes CPU, memory, process and I/O controls; memory.high throttles/reclaims while memory.max is a hard limit that can invoke OOM handling, and child limits can be overcommitted. **Граница:** Kernel controls bound OS resources for a configured cgroup; they do not by themselves provide application admission, provider spend limits, scratch quotas, or safe semantic outcomes.
- [Pressure Stall Information](https://docs.kernel.org/6.10/accounting/psi.html) — Linux PSI measures CPU, memory and I/O stall time and provides threshold triggers suitable for resource-pressure observation and load shedding. **Граница:** Pressure measurements are signals for an admission policy, not a universal capacity threshold or hard limit.
- [Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) — Kubernetes applies CPU limits through throttling and memory limits through kernel OOM behavior; requests guide scheduling and do not assert application-level/provider budgets. **Граница:** Kubernetes is one placement/enforcement option; these controls do not establish global job admission or semantic authorization.
- [Metrics: Cardinality limits](https://opentelemetry.io/docs/concepts/signals/metrics/) — OpenTelemetry metrics SDKs bound the number of tracked attribute combinations (the documented default is 2000); additional measurements are folded into an overflow point, preserving overall totals but dropping the original attribute combination. Queries grouping/filtering by those dropped attributes can undercount. **Граница:** SDK default and behavior are telemetry implementation details, not PolicyOS audit or admission contracts. Exact per-decision evidence still requires a separately authorized durable receipt.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="OPS-09"></a>

## OPS-09 — Hybrid private-source worker cell

Исходная запись: [tasks.json](../tasks.json), `tasks[id=OPS-09]`. Review: [root-review](root-review.md#OPS-09).

### Предпочтительное решение

Use a pull-only worker inside the source custodian's network, composed with the existing durable job lease and receipt path. A server request may authorize one bounded operation only when an independently resolved source grant allows its exact source/query, actor, purpose, cell, recipient and output format. Keep credentials and raw bytes local; return only the permitted result and a receipt bound to job/lease generation, source/version and output digest. Recheck grant and output-recipient policy immediately before release and on every retry/resume. The site enforces egress-deny-by-default except the controller and approved result route, and inventories temporary files, logs, caches, swap, crash dumps and derived outputs. A lease is execution coordination, not source permission. Do not mirror raw source data to a cloud cell as a shortcut.

### Что переиспользовать

- `policy-engine/src/polisyos/fabric/connectors/@dccea950845cda5b38f026e7770c07819d31f4d9` — `existing connector/source adapters`. The workstream assigns transport to existing connector owners and requires explicit typed source-use contracts.
- `policy-engine/src/polisyos/runtime/http/services/control_worker.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `durable worker lease and receipt lifecycle`. Use existing worker lifecycle as the dispatch bridge; remote/site execution parity is not yet established.
- `policy-engine/ops/cloud/helm/polisyos-cell/@dccea950845cda5b38f026e7770c07819d31f4d9` — `cell network/security composition`. Existing infrastructure owner can inform boundary configuration; manifest presence is not proof of custody.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Agree the smallest typed request/receipt interface with CAP-06 and source owner: source/query, action, grant, worker identity, expiry, byte/work cap, allowed output, recipient and idempotency/reconciliation key.
2. Have the site worker pull and validate a single leased job, execute locally, re-resolve rights before effect and output, then emit only the approved result/receipt.
3. Constrain and inventory local copies across temp, logs, cache, crash/core dumps, backups and downstream export; prove the network deny policy with traffic observation.
4. On revocation, stop dispatch and release, revoke the site credential, drain/cancel leases, reconcile remote side effects and tell the custodian which permitted outputs exist.

### Рассмотренные альтернативы

- **Push source credentials/raw data to a centralized cloud worker or LLM.** — It expands custody and copies; network access or a bearer token is not a right to use or disclose the source.
- **Create a second remote task queue.** — Reuse the existing job, lease and receipt owner; add only the site transport adapter if the agreed contract requires it.

### Free-grow и ресурсы

- **data or config growth:** New sites, query classes and allowed output formats extend typed connector configuration and conformance fixtures.
- **extension boundary:** New transport or semantic query class needs adapter plus source owner approval; arbitrary plugin code cannot release data.
- **resource behavior:** Unbounded query, raw output, missing rights, stale lease or unverified egress defers/refuses; local host class limits still apply.


### Миграция и восстановление

Version the site/central request and receipt schema; retain local history and raw data at the custodian. Revocation stops future dispatch; transferred permitted outputs are reconciled by recipient, digest and use rights, not erased by rolling back the server.


### Композиция и owners

- The receipt distinguishes source-side execution, output permitted, quarantine, semantic admission and later reuse; job completed does not imply output admissible.
- Worker credential, source grant and recipient/use grant are separate, time-bound bindings.


### Acceptance и различающие проверки

- Authorized bounded query returns the approved output and bound receipt while raw bytes/secret never leave declared local paths.
- Wrong recipient, revoked grant, retry after revocation, unauthorized egress or removal of the output recipient check blocks release.


### Входы и ответственность за их получение

- Custodian provides the site host, identity, source grant, retention and deletion/backup rules.
- Institutional network/security owner approves pull route and observes egress behavior.
- Local operator accepts responsibility for secrets, temp, backups and incident response.


### Когда обоснованно отклониться

- Use a different remote execution model only if the custodian cannot operate a site worker and explicitly accepts a different custody boundary.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [OWASP API1:2023 Broken Object Level Authorization](https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/) — Every endpoint that accepts an object ID and acts on it needs object-level authorization; identifier unpredictability does not replace that check. **Граница:** OWASP guidance identifies the class and mitigation, not whether the historical PolicyOS job route is vulnerable.
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html) — Secrets should have least-privilege access, lifecycle and audit metadata, expiration/revocation, and short-lived credentials where practicable. **Граница:** It does not prescribe a single secret manager or eliminate the need for an institution-owned root credential and source-use grant.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="OPS-10"></a>

## OPS-10 — Remote CAS parity and distributed/cloud cell

Исходная запись: [tasks.json](../tasks.json), `tasks[id=OPS-10]`. Review: [root-review](root-review.md#OPS-10).

### Предпочтительное решение

Use a qualified local profile as the initial default, but separate adapter implementation/conformance, deployment activation and replica sizing. A selected remote profile may be justified by custody, institutional topology, operability, availability or measured scale/cost requirements; exhausting vertical capacity is not a universal prerequisite. Bind the objective and compare the simplest suitable alternatives. For each selected S3/GCS adapter, namespace objects and caches by tenant/cell, prohibit cross-tenant deduplication and existence probes, bound reads by manifest size, and use the provider's conditional create/version/generation preconditions for immutable objects and mutable heads. Bind each read to owner scope before returning bytes. Treat DB pointer updates and object writes as a recoverable multi-store sequence, never as a provider-atomic transaction. Qualify concurrency, multipart failure, stale version, credential loss, delete/lifecycle, cache isolation and quarantine restore on the exact bucket/prefix/IAM/config.


### Что переиспользовать

- `policy-engine/src/polisyos/core/artifacts/backends/config.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `CAS backend configuration and ownership gate`. Historical plan says remote backends are named but explicit tenant/cell ownership factory is filesystem-only.
- `policy-engine/src/polisyos/core/artifacts/backends/s3_store.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `S3 adapter`. Adapter presence does not establish overwrite safety, ownership or restore parity.
- `policy-engine/src/polisyos/core/artifacts/backends/gcs_store.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `GCS adapter`. Generation preconditions are provider-specific and need exact adapter mapping/conformance.
- `policy-engine/src/polisyos/core/artifacts/backends/caching_store.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `cache adapter`. Cache namespace isolation is part of tenant/cell ownership, not a transparent implementation detail.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Name the concrete service, custody, topology or failure-domain objective and select the simplest qualifying local/remote alternative. A scale-specific choice should address measured workload causes; independent adapter preparation/conformance need not wait for local capacity exhaustion.
2. Extend the canonical adapter owner with explicit tenant/cell owner resolution and per-provider conditional-write/read/delete semantics; content hash is integrity evidence, not authorization.
3. Make object writes immutable and size/hash verified, then publish a versioned owner-scoped manifest/head through a compare-and-swap operation; reconcile partial object/database publication.
4. Run exact-provider/config concurrent publish, cache collision, multipart interruption, stale generation, credentials revocation, bounded read, restore and fresh-reader cases.


### Рассмотренные альтернативы

- **Switch to a bucket enum, S3-compatible endpoint or Kubernetes replicas and assume parity.** — Provider APIs have different conditional semantics, cache/identity configuration and failure modes; replica placement does not provide tenant or recovery correctness.
- **Use cross-tenant content deduplication by hash.** — It can reveal object existence and collapse independent ownership/retention boundaries.


### Free-grow и ресурсы

- **data or config growth:** New backend configurations use one adapter conformance interface and owner-scoped manifests.
- **extension boundary:** A new configuration of an already supported backend/mount/retention semantic class reuses its existing adapter and runs exact selected configuration/restore conformance. Only changed protocol, atomicity, encryption/key, retention or topology semantics require an adapter extension; a new bucket/site name alone is not a new code module.
- **resource behavior:** Bound bytes, request rate, concurrency, cache and retries; provider outage or ambiguous write yields reconciliation-required state, never silent head rollback.


### Миграция и восстановление

Migrate one selected cell at a time with dual-compatible readers and explicit object versions/owner scope. Stop new writes, pin verified manifests, restore the last qualified adapter/config and reconcile object/control references before serving. Never roll back into a superseded rights generation.


### Композиция и owners

- Object authority comes from resolved owner/manifest grant; provider key, bucket prefix and content digest do not self-authorize.
- Include backend/config/schema versions and object generation/time, cell, audience, provenance and recovery cut in receipts.
- Bind conditional-write guarantees to the exact provider API operation and multipart route: for example GCS XML multipart does not support request preconditions. Select a supported route or retain an explicitly proved immutable-version/owner-head protocol; provider-level capability labels cannot substitute for the actual operation race test.
- One canonical semantic owner does not require one physical process or a global mutex. Keep atomicity/fencing on the actual invariant key (job/attempt, source partition, claim head or budget principal). Distinct verified scopes can use separate workers/transactions; scopes sharing a cap, rights/disclosure budget or head still coordinate through its existing owner. Partitioning is an implementation option only after proving non-overlap and preservation of shared invariants, never by tenant/job labels alone.


### Acceptance и различающие проверки

- Exact backend/config supports concurrent owner-scoped create/read, bounded read, lifecycle and quarantined restore with hash/reference agreement and a fresh authorized consumer.
- Cross-cell IDs, cache-key collision, partial multipart write, stale generation and old-manifest rollback do not disclose or authorize an object.
- A second supported backend configuration is discovered and used without central routing or adapter-code edits, with its own namespace/IAM/restore evidence. A same-API configuration changing atomicity or retention cannot borrow that conformance. Disjoint cells can operate independently; shared billing/custody invariants remain shared.


### Входы и ответственность за их получение

- Chosen provider/account owner supplies IAM, conditional-write, versioning, lifecycle and backup behavior.
- Service owner supplies the measured SLO/capacity/failure target whose miss justifies added failure domains.


### Когда обоснованно отклониться

- Scale out after a source-bound deployment decision justified by its actual objective and costed alternatives; no unsupported throughput claim, no compulsory vertical-exhaustion gate for custody/failure-domain needs.
- Admit a specific remote CAS adapter only after exact configuration restore and cross-cell negative tests pass; otherwise preserve filesystem-only supported scope.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [How to prevent object overwrites with conditional writes](https://docs.aws.amazon.com/us_en/AmazonS3/latest/userguide/conditional-writes.html) — S3 conditional writes can prevent a put from replacing an existing key and can use If-Match preconditions; concurrent multipart/delete cases have distinct 409/412 behavior. **Граница:** Provider-specific behavior, multipart handling, and authorization still require tests against the selected adapter and configuration.
- [Request preconditions](https://docs.cloud.google.com/storage/docs/request-preconditions) — Cloud Storage generation/metageneration preconditions support conditional mutation and help prevent races; a lost response can leave the client uncertain whether a request applied. **Граница:** Generation conditions are provider-specific and do not make object storage transactional with the control database.
- [Custom Resources](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/) — Kubernetes documentation advises against using Custom Resources as storage for application, end-user, or monitoring data because this couples normal workload operation to the Kubernetes API; CRDs are intended for resources used with Kubernetes API/controller conventions. **Граница:** This is deployment guidance for Kubernetes and does not rule out a narrowly scoped configuration/control object when the API is already an owned interface. It gives no reason to make Kubernetes a mandatory dependency.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="OPS-11"></a>

## OPS-11 — Trust succession, currentness duty, and custody cutoff

Исходная запись: [tasks.json](../tasks.json), `tasks[id=OPS-11]`. Review: [root-review](root-review.md#OPS-11).

### Предпочтительное решение

Keep trust-root appointment, successor authorization, currentness-watch ownership and custody cutoff with the existing institution/claim owners; PolicyOS records and consumes their typed evidence. Provision the first root through an independent out-of-band path. For ordinary rotation, require the prior and successor trust conditions, a strictly next generation, persisted anti-rollback state and an authenticated acceptance by the successor operator. If the current root threshold is compromised, it cannot authorize its own replacement: freeze signing/promotion for that scope and require the institution's separate recovery channel. Preserve historical signature verification while downgrading current use until fresh rights/trust evidence is consumed. Before any currentness-bearing claim, require an active owner and deputy, due time, correction source, escalation reaction and accepted transfer; if missed or unstaffed, mark only the affected claim limited/stale or issue the owner's signed cutoff.

### Что переиспользовать

- `policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md@dccea950845cda5b38f026e7770c07819d31f4d9` — `signature rule and own/integrate/observe boundary`. This ratified identity document says the system owns its signatures and observes institutional succession; it must not become the institution's executor.
- `policy-engine/docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md@dccea950845cda5b38f026e7770c07819d31f4d9` — `shutdown and stuck-worker handoff`. Existing runbook is a place to wire duty transfer or cutoff rather than inventing a succession service.
- `policy-engine/docs/runbooks/canary-rollback-or-promotion-failure.md@dccea950845cda5b38f026e7770c07819d31f4d9` — `rollback/promotion failure procedure`. Use existing release rollback owner while preserving newer revocation/correction state.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Use TUF-style root metadata as a protocol reference: out-of-band trust, threshold keys, N+1 root versions, expiry and persisted generation; do not make TUF itself the issuer.
2. Resolve trust-root provision and successor evidence by content and independent issuer provenance; retain old and new generation, scope, time and operator acceptance.
3. Connect each published claim to its existing currentness duty owner/deputy, due time, correction/revocation source and bounded reaction.
4. On key compromise, freeze affected protected use, revoke/scoped credentials, preserve historical verification, reconstitute identity from the institution's independent root and reissue currentness only after fresh consumption.

### Рассмотренные альтернативы

- **Accept a self-signed replacement, signature chain alone, or restored old snapshot.** — A compromised root can sign its own successor; rollback may erase revocations; signature validity does not establish current-use permission.
- **Create a PolicyOS-operated institutional succession or notification service.** — That crosses the ratified boundary; PolicyOS owns its evidence contract and scoped claim reaction, not another institution's authority handoff.

### Free-grow и ресурсы

- **data or config growth:** Issuer and successor records grow by generation under the institution's chosen threshold and scope.
- **extension boundary:** A new trust root, issuer, or successor authority requires a separate authenticated appointment source; locally generated keys can authorize only a declared prototype.
- **resource behavior:** Missing owner/deputy, missed freshness deadline, expired root, old generation or unverified anti-rollback state blocks affected current claims and promotion.


### Миграция и восстановление

Trust and duty generations are monotonic and outside ordinary application rollback. Restore generation/revocation history before protected use; if unavailable, retain historical verification and impose a signed validity cutoff or stale limitation.


### Композиция и owners

- Historical signature validity, current authorization, active currentness duty and trust-root identity are separate statuses with explicit time semantics.
- Trust provision predicate must be independently reconciled, not consumer-asserted or self-attested.


### Acceptance и различающие проверки

- Authorized successor generation is admitted by an independent recovery path and consumed by the fresh source-use reader; root rollback or same-key self-replacement fails.
- No active duty owner/deputy or missed watch deadline limits the affected currentness claim but does not unnecessarily stop independently owned claims.


### Входы и ответственность за их получение

- Institution's trust authority and independent recovery custodians.
- Claim owners and currentness-watch owners accept duties or sign a bounded cutoff.
- Authoritative source for corrections/revocations and institutional time validity.


### Когда обоснованно отклониться

- If compromise can affect the entire institutional identity plane, use the institution's full reconstitution process rather than a local key-rotation workaround.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [The Update Framework Specification v1.0.37](https://theupdateframework.github.io/specification/v1.0.37/index.html) — TUF uses an out-of-band trusted root, threshold signatures, sequential root versions, expiry, persisted root metadata, and an out-of-band recovery path if the root threshold is compromised. **Граница:** TUF is a protocol pattern, not an institutional appointment, legal grant, or required PolicyOS dependency.
- [CISA Alert AA20-352A: Advanced Persistent Threat Compromise](https://content.govdelivery.com/accounts/USDHSCISA/bulletins/2b1b32d) — CISA documented the SolarWinds supply-chain compromise and follow-on identity abuse, including malicious software delivered through the update chain and valid SAML tokens minted after signing-certificate compromise. **Граница:** This demonstrates that signatures and a trusted update path do not prove benign content or continuing identity integrity; it does not define a PolicyOS threat threshold.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="OPS-12"></a>

## OPS-12 — Conditional air-gapped cell

Исходная запись: [tasks.json](../tasks.json), `tasks[id=OPS-12]`. Review: [root-review](root-review.md#OPS-12).

### Предпочтительное решение

Keep air-gap conditional on a named institution that requires it and can operate local identity, clock/freshness, source grants, secrets, models/methods, succession and restore. Deliver a versioned, signed offline bundle of the approved runtime, policy/config, methods and referenced evidence under an independently provisioned root. Use a TUF-like versioned root chain and anti-rollback; a digest alone only detects accidental change if its trust root is already valid. Define an owner-approved maximum offline validity and an explicit as_of time source. Once that bound expires, project the claim as stale/limited or historical; if clock rollback or freshness cannot be independently detected, do not assert currentness. Enforce no-egress outside the application with deny-by-default host/network controls and observe the full interface/DNS/update/telemetry/crash path. One egress event or untested route means the no-egress claim is not established.

### Что переиспользовать

- `policy-engine/ops/release/deployment-topology.toml@dccea950845cda5b38f026e7770c07819d31f4d9` — `deployment topology profiles`. Historical plan lists the profile seam; air-gap is not an accepted or wired deployment chain.
- `policy-engine/ops/migrations/runtime_state/README.md@dccea950845cda5b38f026e7770c07819d31f4d9` — `runtime-state migration/restore owner`. Reuse the current state/CAS restore boundary and add explicit bundle generation/reconciliation.
- `policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md@dccea950845cda5b38f026e7770c07819d31f4d9` — `signature custody and institutional boundary`. The institution owns local identity and policy authority; PolicyOS owns only its own signed claims and evidence contract.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Require a commissioning decision naming the institution's offline need, operators, successor, supported local sources, methods/models, trust root, time source, retention, backup and offline validity maximum.
2. Package immutable versioned artifacts and a manifest containing exact digests, schema/rule versions, source grants and limitations; import only through independent root verification and strict monotonic generation.
3. Prove update, key succession, restore and no-egress under the actual hardware/network boundary; restore into quarantine and reconcile rights/revocations not present in the offline snapshot.
4. Expose bundle generation, trusted as_of source, last freshness verification, missing dependencies and stale/limited projection to operators and claim consumers.

### Рассмотренные альтернативы

- **Treat offline mode as a switch on a cloud deployment or trust the bundle's own signing key.** — The mode changes clock, update, source-currentness, secrets, recovery and succession assumptions; self-signed package metadata cannot bootstrap authority.
- **Retain unrestricted internet egress for updates, telemetry or provider models.** — That contradicts a no-egress guarantee and can send source data or secrets outside the commissioned boundary.

### Free-grow и ресурсы

- **data or config growth:** New bundle versions and supported local source/method/model classes use versioned manifests and existing registries.
- **extension boundary:** New transport/model/update channel needs an adapter and offline behavior/conformance; an institution supplies local policy and external data rather than arbitrary code gaining authority.
- **resource behavior:** Bundle size, import bytes, restore disk/RAM and update cadence are bounded by the selected host; missing components, expired grants, invalid time or unsupported generations refuse current/protected claims.


### Миграция и восстановление

Freeze new imports and affected protected claims on integrity/time failure. Return only to a previously independently verified bundle if its trust and rights history remains current; never roll back generation or revocation history. If that cannot be proven, provide history with an explicit cutoff/limitation.


### Композиция и owners

- Offline bundle signature, source-use grant, method/model provenance, trust generation, bundle version and as_of freshness are distinct verified inputs.
- A no-egress claim is based on independently observed network behavior at the boundary, not an application configuration flag.


### Acceptance и различающие проверки

- Authorized import, monotonic update, key succession and quarantined restore succeed offline; tampered/self-signed/old bundle and clock rollback refuse.
- Freshness expires into limited/historical status, missing method/model/grant blocks protected claims, and any covert egress falsifies the no-egress property.


### Входы и ответственность за их получение

- Institution requests the tier and provides local operator, identity, model/source support and successors.
- Independent bundle transfer/root authority and trustworthy clock/freshness evidence.
- Local security/custody authority defines egress boundary, retention and recovery responsibilities.


### Когда обоснованно отклониться

- Commission only on a named institutional requirement and acceptance of local update/restore duties; absent that requirement the tier remains explicitly unselected.
- If trusted offline time or anti-rollback cannot survive the actual backup/restore closure, limit output to historical/candidate status.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [The Update Framework Specification v1.0.37](https://theupdateframework.github.io/specification/v1.0.37/index.html) — TUF uses an out-of-band trusted root, threshold signatures, sequential root versions, expiry, persisted root metadata, and an out-of-band recovery path if the root threshold is compromised. **Граница:** TUF is a protocol pattern, not an institutional appointment, legal grant, or required PolicyOS dependency.
- [CISA Alert AA20-352A: Advanced Persistent Threat Compromise](https://content.govdelivery.com/accounts/USDHSCISA/bulletins/2b1b32d) — CISA documented the SolarWinds supply-chain compromise and follow-on identity abuse, including malicious software delivered through the update chain and valid SAML tokens minted after signing-certificate compromise. **Граница:** This demonstrates that signatures and a trusted update path do not prove benign content or continuing identity integrity; it does not define a PolicyOS threat threshold.
- [fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html) — Linux fsync flushes file data/metadata, while durable publication of a directory entry may require fsync of the directory. **Граница:** Filesystem, mount, device-cache, and network-volume behavior must be qualified on the exact deployment target.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.
