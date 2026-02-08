package polisyos.authz.delegation_guard_test

import rego.v1
import data.polisyos.authz.delegation_guard

test_user_context_from_service_peer_requires_spiffe if {
  not delegation_guard.allow with input as {
    "identity": {"principal_type": "user"},
    "peer": {"spiffe_id": "not-spiffe"},
  }
}

test_user_context_from_trusted_spiffe_peer_allowed if {
  delegation_guard.allow with input as {
    "identity": {"principal_type": "user"},
    "peer": {"spiffe_id": "spiffe://polisyos.io/cell/cell-a/svc/scientist"},
  }
}
