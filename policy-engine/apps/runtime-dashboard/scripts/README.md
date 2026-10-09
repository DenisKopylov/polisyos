# Dashboard command owners

Maintenance route: team-frontend.

Build, evidence capture, reconciliation and measurement commands live here. package.json names the ordinary callers. coverage-scope.json is the shared inclusion/exclusion owner for Vitest and the coverage ratchet; changing it changes the measuring denominator. Python children must use the provisioned interpreter.

Owning entrypoint: `apps/runtime-dashboard/package.json`.

The dashboard's `generate-api-client.sh` uses the shared
`packages/runtime-api-client/scripts/generate-openapi-types.mjs` entrypoint so
dashboard types and the runtime client derive request/response field presence
from the same OpenAPI graph and locked generator version.

This local document explains the directory role. Its presence does not certify the contents or close a product capability.
