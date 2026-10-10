# Independent ownership-denial and observability review

## Disposition

Partial review; no release, production-operability, or SLO-ownership closure is claimed. The current tree snapshot is identified below by file hashes. The Promtool receipt records a successful v2.50.0 check, but it is a reconstructed command transcript without the original command’s Git SHA and does not prove live scraping, series availability in a deployment, alert firing, or SLO authority.

## Runtime ownership-denial audit

The shared HTTP guards now cover both run and artifact ownership failures. In dependencies.py, the guard requires authenticated AccessScope first. A known run/artifact tenant mismatch and a missing owner tenant each append the existing request-scoped data-access record before raising the existing 403. All four branches use the same helper. The event uses the verified requester tenant and actor, requested resource identity, and denial code; it does not copy the owner tenant into the audit event or response.

For known cross-tenant mismatches, the helper also resolves the existing runtime metrics registry and calls record_tenant_boundary_violation with requester tenant, indexed owner tenant, and resource type. It does not increment this counter for an unscoped owner record or a matching tenant. Audit append and metric errors are separately caught; either failure leaves the original refusal intact. The audit writer uses the existing locked append path and flushes/fsyncs the event. Fresh reads use RuntimeDataAccessAuditTrail.scan_read_only.

The current ownership guard and audit-path hashes are:

- src/polisyos/runtime/http/dependencies.py — cbb66e72eadfa8add29f26480a1966c2aa5f831cb82c3f199986e5b0105f1cba
- src/polisyos/runtime/http/access_audit.py — 36045312577e30399fa53078f9e100c04dd6e549c10d65cf7b736abeb3803be5
- tests/unit/runtime/http/test_authorization.py — 6006a6255ca2b06e4b06894b741771be2ec7ee952541168e3ad8b7336731ecda
- tests/unit/runtime/http/test_runtime_api_authz.py — 8d98500330449b506f938484a510cc8dc6f2bd8c2bead6055d32c11183a631d2
- tests/unit/runtime/http/test_runtime_authorization_access_audit.py — 62f252eabf490f7d13f11bd9e5c85addf451b246bebbf2d9450451b788a096ff

I independently ran the focused run/artifact suite on this source snapshot: seven tests passed with two Python 3.14 Torch deprecation warnings in 20.92 seconds. The suite includes the persisted request-principal denial readback, unscoped run/artifact denials, append-failure refusal, and the new tenant metric probe. The metric test checks two real authenticated mismatch requests, exact run/artifact metric labels and counts, no metric increment for unscoped owners, 403 responses, and no owner-tenant leak in persisted caller-scoped audit events.

The broader source census recorded in LOCAL/dx0-native/raw/ownership-denial-source-census.txt covers 124 Runtime HTTP Python files and 58 uses of the two shared guards: 42 run-guard calls and 16 artifact-guard calls. Its SHA-256 is 1bd3d739376dbef42ae4b6ca45275d0d1be690735052d3127c0555d6a783b368. The existing closure note is LOCAL/dx0-native/ownership-denial-audit-closure.md, SHA-256 a46fad7037b69919c4bf756ae5351b41935af0355374314e7d2b5e3f4397f5e6. The retained earlier targeted output has six passes at LOCAL/dx0-native/raw/ownership-denial-targeted-pytest-rerun-03.txt, SHA-256 3c934a2a40c7dc67f65301a662506ab1306af492f38a13a15543e05fdbea8f40.

Residual: if the audit trail is unavailable, the protected request remains denied but the durable denial receipt cannot be guaranteed. Metric failure likewise cannot weaken the denial. No authorization code, authority, or status semantics changed.

## Core SLI and Prometheus review

The two active Core SLO copies now use the registered tenant-boundary series, polisyos_audit_tenant_boundary_violations_total:

- ops/components/core/slo.yaml and ops/observability/slo/core.yaml have identical SHA-256 5ebcbbc30f54d6bdbab93e2b7c89f06dc8f2c27c667d8b94a4f4c1c0e875d0d9.
- The producer is registered in src/polisyos/core/observability/_metrics_registry_base.py, SHA-256 922eac01d723a6e30070fd887f469b8c6c0c735d922b1fb76185cb0e47d62f85, and invoked from the shared runtime ownership helper in dependencies.py. The behavioral test described above confirms the emitted metric for source-owned run and artifact mismatches.
- The SLI name correction and rule loading are recorded in LOCAL/decisions/native-slo-delegation-g-choices.md, SHA-256 eea62ec399f09d2ac34194a8c81d4aa58e613289e54605f8961b083bf9d45867. That packet still has an unqualified stale sentence at line 38 saying Core tenant violations have a source-divergent metric name; the current source and follow-up section show that the series name is now aligned. This needs a documentation correction before relying on the packet as a fully current account.

Prometheus configuration lists eight rule files and Compose mounts the configuration plus the four top-level rule files and the rules directory. The current Prometheus config SHA-256 is 04779eca7326fcfdf36479add0d978b91994d97e37744bcdccfcbbb8031d4d6f; Compose SHA-256 is f12a1d97573f16020598829920b38fbf067b3509184e246640c7844c323af26d. The eight declared files are recording_rules.yml, slo_recording_rules.yml, alerts.yml, slo_alerts.yml, rules/audit_chain_alerts.yml, rules/runtime_operability_alerts.yml, rules/scientist-alerts.yml, and rules/mtls-rules.yaml. The checked-out component rule declarations are covered by this set; the two additional top-level files are recording-rule sets.

I read the raw operator transcript at LOCAL/s3-empirical/raw/promtool-v2.50.0-e02-2026-10-10.txt, SHA-256 2d8ce81903e99c08d1130926fc1f09665a7464efce624f8ba2ce3674dbfc5c1b. It records Prometheus 2.50.0 Linux/arm64, image digest sha256:042258e3578a558ce41b036104dfa997b2d25151ab6889a3f4d6187e27b1176c, with read-only config mounts, read-only root filesystems, and network mode none. Recorded check config and check rules commands exited zero: all eight rule files loaded, with 68 rules total. This is substantive syntax/load evidence, not just YAML parsing. The transcript says the original commands did not record a Git SHA or wall-clock timestamps; it records the checkout SHA only at reconstruction. Thus the transcript supports a successful check of the copied inputs, while exact byte identity to every current rule file is not independently established. It ran no Prometheus server or scrape.

A separate Core objective remains unresolved: both Core SLO files query polisyos_audit_sink_writes_total{status="success"}, but that series has no producer declaration or call site in src/polisyos. The current audit sink records polisyos_audit_entries_total and the polisyos_audit_write_latency_seconds histogram; replica latency observations use status values ok/error. These counters/histograms do not by themselves define the queried success-rate denominator: logical durable acceptance and asynchronous replica durability are different properties. Classify this objective as producer_missing and not_established pending the owner's choice of measured property; do not substitute a nearby metric or claim the Promtool syntax pass proves source availability. The present query is a concrete P38 divergence: promtool remains green if the missing series is never emitted.

The five exception components—common, berl, ddm, calibration, and security—still have status exception, expiry 2026-08-01, and empty objectives in their component SLO files. The expiry is past as of 2026-10-10. The same five decisions appear in each of three registries: 15 mirrored rows total, not 15 distinct decisions. The exception records remain present and none is waived by this review. The five owner choices in the SLO packet remain pending.

## Pattern disposition

P29/P32/P33/P37/P38: the denial review exercised actual request, persistence, and metric behavior rather than relying on field names. The Prometheus syntax check proves syntax and loading only; source availability is checked separately.

P40: SAME source-to-SLI binding class, now one level deeper. The tenant-boundary mismatch is repaired across the shared guard family with source and behavioral test evidence. The Core audit-sink SLI still queries a series with no producer and lacks an owner-defined success boundary. At the second occurrence, either widen to a complete source/consumer audit of all current Core SLI expressions or retain this exact bounded producer_missing/G-choice residual; another isolated metric-name patch would repeat the class.

The accepted capability state is therefore mixed: ownership-denial audit has source, persisted event, reader, and focused semantic verification; the local tenant-violation metric has a source call site and focused emission test, but live scrape/evaluation remains not_established. Core audit-sink success-rate remains producer_missing/not_established. Expired SLO exceptions and their owner decisions remain open.
