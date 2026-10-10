# Runtime HTTP ownership-denial audit closure

## Scope and source boundary

This closes the ownership-denial audit residual recorded in
`runtime-http-mirrors-1.md`. The repair is in the shared run/artifact tenant
guards in `src/polisyos/runtime/http/dependencies.py`. No route handler, action
permission, versioned authorization event, public DTO, or source payload was
changed. The existing `RuntimeDataAccessAuditTrail` remains the only writer and
reader surface; `authorization.py` needed no additional sink seam. A follow-up
also connects proven cross-tenant mismatches to the already-defined Core
tenant-boundary counter; it does not create a second metric or treat an
unscoped owner as a known cross-tenant target.

An AST census of the complete Runtime HTTP Python source set found 124 `.py`
files and 58 uses of the two shared guards: 42 run-ownership calls and 16
artifact-ownership calls. Every guarded refusal now uses the same helper:

- `run_tenant_mismatch` and `run_tenant_unscoped`
- `artifact_tenant_mismatch` and `artifact_tenant_unscoped`

The helper appends an existing data-access record with `outcome="deny"` and
`metadata.denial_reason` set to the guard's existing error code. The envelope
uses the established request timestamp, request id, method, endpoint, actor,
tenant, operation, resource kind, and requested resource id. The tenant comes
from the verified requester scope; the resource owner's tenant and manifest
details are not copied into the event or returned response. The guard raises
the same 403 after the append attempt. An append exception is logged and cannot
turn that refusal into an allow or expose the protected resource.

The exact writer chain is `record_data_access_audit` →
`resolve_runtime_access_audit(request)` → `RuntimeDataAccessAuditTrail.append`
→ the trail's locked append/fsync to
`<cas_root>/runtime/audit/access.jsonl`. Fresh readers use
`RuntimeDataAccessAuditTrail.scan_read_only`, which returns parsed object
entries and separate nonblank, malformed, nonobject, and read-error counts;
the existing `query_runtime_audit` compliance reader filters the same stream
by timestamp, tenant, actor, endpoint, operation, outcome, and resource id.
The generic denial entry does not impersonate the versioned
`RuntimeAuthorizationAuditEvent` or the exact human-decision creation pointer
consumed by review-effectiveness.

For mismatches only, the same shared recorder resolves the existing runtime
metrics provider and calls `record_tenant_boundary_violation` with the verified
request tenant, verified target tenant, and resource type (`run` or
`artifact`). The target tenant is a metric label required by the existing Core
counter contract; it remains absent from the generic access-audit entry and
denial response. Both unscoped codes keep their existing access-audit entries
but do not increment the counter, because missing owner evidence establishes
no target tenant. Metric failures are logged without changing or weakening the
ownership refusal.

## Behavioral evidence

- `tests/unit/runtime/http/test_authorization.py` sends an authenticated
  tenant-A request to a tenant-B run. The real route returns the existing
  `run_tenant_mismatch` 403, omits tenant-B details, does not invoke the run
  projection, and a fresh trail reader finds exactly one denial bound to the
  request id, requester actor/tenant, route, and run id. The normal compliance
  query returns that same entry when filtered by the requesting tenant, actor,
  endpoint, operation, outcome, and resource id.
- `tests/unit/runtime/http/test_runtime_api_authz.py` strengthens the existing
  cross-tenant run negative with the same persisted-event readback.
- `tests/unit/runtime/http/test_runtime_authorization_access_audit.py` covers
  a run whose owner metadata is missing, artifact mismatch and unscoped
  artifact denials, and an audit-append failure that leaves the run request
  denied. Artifact probes assert the requested manifest id is not read after
  the ownership refusal; an app-owned custody-scan manifest read is excluded
  from that exact resource check.
- The follow-up test
  `test_tenant_boundary_metric_records_only_verified_mismatches` sends actual
  authenticated requests through both shared guards: tenant A to a tenant-B
  run, tenant B to a tenant-A artifact, an unscoped run, and an unscoped
  artifact. It reads the metric from an in-memory OpenTelemetry reader attached
  to the real `MetricsRegistry`: exactly the two proven mismatches emit one
  sample each with the expected source/target/resource labels, while both
  unscoped controls add no samples. Fresh audit reads still bind each mismatch
  to the request tenant and do not contain the owner tenant.

The first focused run exposed that the artifact read spy included an unrelated
app-owned custody-scan manifest. The preserved failed output is in the raw
directory; the corrected probe compares the requested artifact id, and the
fresh selected run passes all six expanded cases.

The complete AST source census is retained at
`raw/ownership-denial-source-census.txt`; the failed assertion run and corrected
six-case run with the compliance-reader assertion are
`raw/ownership-denial-targeted-pytest.txt` and
`raw/ownership-denial-targeted-pytest-rerun-03.txt`, respectively.

## P40 classification and boundary

**P40: SAME denial-audit class, widened across the complete ownership-guard
family. The earlier mirror tranche found the run-ownership instance; the first
repair closed both shared guard functions and all four refusal branches for
the access trail. The deeper producer omission is widened at that same shared
boundary: both proven mismatch branches feed the existing counter, while both
unscoped branches remain audit-only. The smallest removal falsifier is to
remove a mismatch's target binding from the common helper call: its actual
guard request must still deny and audit but stop incrementing the counter.
The original audit negative remains that a tenant-A-to-tenant-B request
returned 403 while a fresh trail reader contained no entry before the first
repair.

Requests without a verified access scope remain a separate 401 from
`require_access_scope` and are outside this ownership-denial repair. If audit
storage itself is unavailable, the denial remains fail-closed but a durable
receipt cannot be guaranteed; the append failure is logged. No authorization
vocabulary, issuer rule, authority, status, or currentness semantics were
introduced or altered.

## Validation

The selected focused test command passed six cases; Ruff, `py_compile`, and
release-fragment TOML parsing also passed. Complete outputs for the initial
overbroad artifact-spy run, final six-case run, and final scoped checks are
retained under `raw/` beside this packet. The pre-change single-test red
reproduction is summarized above. The final scoped lint/compile/TOML output is
`raw/ownership-denial-scoped-checks-02.txt`. No full Runtime HTTP suite or
backend suite was run in this slice.

The metric follow-up's focused four-branch HTTP test passed one case. Its full
stdout and JUnit result are
`../raw/ownership-denial-metric-producer-pytest.txt@sha256:ff7302cd30f5584f99f3c484fb2eb2493668d64974a47e551af41fcc1eab3ed5`
and
`../raw/ownership-denial-metric-producer-junit.xml@sha256:5c7540715ad5c48a2d520096b091501d2ba86025b268f988daa1767c4eddf374`.
The updated dependency helper and test pass configured Ruff and `py_compile`;
the release TOML parses. The scoped check output is
`raw/ownership-denial-metric-scoped-checks.txt@sha256:13c50d81f236249f048a80e3984474bc252c93de1448adb7f80a05f5267fb8c7`.
No full Runtime HTTP or backend suite was run for the follow-up.

The follow-up source, test, README, and release-fragment byte identities are
recorded in `raw/ownership-denial-audit-inventory.json`; the focused test's
semantic output is retained above rather than duplicated here.

The current source/test/doc path hashes and selected source anchor are recorded
in `raw/ownership-denial-audit-inventory.json`.
