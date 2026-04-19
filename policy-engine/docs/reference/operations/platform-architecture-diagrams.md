# Platform Architecture Diagrams

Related reference: [Operations Reference](index.md), [Runtime API Versioning and
Deprecation Policy](../api/versioning.md), [Logging and Trace Context](../logging.md).

Owner: `@platform-owners`
Source of truth: `src/polisyos/runtime/http/**`, `src/polisyos/core/artifacts/**`, `src/polisyos/core/observability/**`, and the linked API/operations reference pages

> These diagrams are the operator-facing shorthand for the runtime platform
> contract after WS-0 through WS-2 hardening.

## C4 Container View

```mermaid
flowchart TB
    Client["Clients: dashboard, CLI, operators, generated SDKs"]
    Runtime["Runtime HTTP API"]
    Control["Control-plane services and workers"]
    CAS["Artifact store / CAS boundary"]
    Policy["Policy and authz dependencies"]
    Telemetry["Telemetry stack"]

    Client --> Runtime
    Runtime --> Control
    Runtime --> CAS
    Runtime --> Policy
    Runtime --> Telemetry
    Control --> CAS
    Control --> Telemetry
    Policy --> Telemetry
```

## Runtime HTTP Request Flow

```mermaid
flowchart LR
    Client["Client request"] --> App["FastAPI app"]
    App --> JWT["JWT / identity middleware"]
    JWT --> Cell["Cell router"]
    Cell --> Authz["Authz middleware"]
    Authz --> Guard["Rate limit / idempotency / resilience guards"]
    Guard --> Route["Route handler"]
    Route --> Services["Runtime services"]
    Services --> Store["ArtifactStore / control store / OPA"]
    Route --> Audit["Access or mutation audit"]
    Services --> Telemetry["Metrics / traces / logs"]
    Audit --> Telemetry
    Telemetry --> Response["RFC 7807 or success response"]
```

### Operator Notes

- Deny paths stop before downstream route logic can treat the request as
  authenticated.
- Mutation protection lives before side effects and records replay/throttle
  outcomes.
- Read paths attach data-access audit entries with `request_id`, actor, tenant,
  and resource metadata.

## Auth And Tenant Isolation Flow

```mermaid
flowchart TB
    Token["JWT bearer token"] --> Validate["OIDC / JWT validation"]
    Validate --> Bind["tenant_id and cell_id binding"]
    Bind --> Scope["request.state and AccessScope"]
    Scope --> OPA["OPA authz input"]
    OPA --> Namespace["namespaced run and artifact access"]
    Namespace --> Audit["audit trail with request_id, tenant, actor"]
```

### Operator Notes

- tenant or cell mismatch is a deny path, not a warning path;
- auth, routing, authorization, namespace checks, and audit should agree on the
  same tenant/cell identity;
- see [Security Model](../../explanation/security-model.md) and
  [Auth and tenant model](../api/auth-tenant-model.md) for the contract details.

## Control-Plane Lifecycle

```mermaid
stateDiagram-v2
    [*] --> created
    created --> starting
    starting --> ready
    starting --> failed
    ready --> stopping
    stopping --> stopped
    stopping --> failed
    failed --> stopping
```

### Lifecycle Responsibilities

- `created`: dependency graph assembled but not started.
- `starting`: heavy services are being initialized and legacy aliases are bound.
- `ready`: routes, workers, audit, and metrics are expected to be usable.
- `stopping`: new work should drain and long-lived connections should close.
- `stopped`: owned resources are closed in dependency order.
- `failed`: startup/shutdown or dependency initialization failed and requires
  operator inspection.

## CAS, Signing, and Integrity Flow

```mermaid
flowchart LR
    Producer["Producer / control path"] --> Blob["Blob write"]
    Blob --> Manifest["Manifest lifecycle"]
    Manifest --> Sign["Detached signature"]
    Sign --> Audit["Mutation audit"]
    Audit --> Store["Immutable CAS state"]

    Reader["Reader / download / preview"] --> Resolve["Manifest lookup"]
    Resolve --> Verify["Read-time digest verification"]
    Verify --> Trust["Signature / trust-store verification"]
    Trust --> Allow["Typed payload or typed integrity error"]
```

### Operator Notes

- Manifest creation is create-once and backed by atomic file-write behavior.
- Integrity mismatch is a typed failure, not a silent best-effort warning.
- Trust-store state determines whether a signed artifact is `valid`,
  `untrusted`, or `revoked`.

## Observability Topology

```mermaid
flowchart TB
    Request["Request / background job"] --> Trace["Tracer / spans"]
    Request --> Metrics["Metrics registry"]
    Request --> Log["Structured logger"]
    Request --> Audit["Runtime audit trails"]

    Trace --> Dash["Dashboards / alerts"]
    Metrics --> Dash
    Log --> Dash
    Audit --> Dash
```

### Signal Ownership

- traces explain why a request degraded;
- metrics show latency, saturation, circuit state, cache behavior, and
  rate-limit pressure;
- logs capture operator narrative plus dependency diagnostics;
- audit trails answer who read or changed which resource.
