# Runtime Quality Unit Tests

Runtime-quality tests cover Policy Design Case closeout semantics, authority
composition, replay, capability graph wiring, and audit/export behavior. Keep
new tests close to the runtime-quality module they exercise, and use shared
fixtures only when the same evidence is consumed across multiple quality
surfaces.
