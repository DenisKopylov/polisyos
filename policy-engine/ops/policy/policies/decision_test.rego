package polisyos.authz.decision_test

import data.polisyos.authz.decision
import rego.v1

test_decision_allows_valid_request if {
	decision.allow with input as {
		"identity": {
			"tenant_id": "tenant-a",
			"roles": ["analyst"],
			"mfa_verified": true,
			"principal_type": "user",
		},
		"request": {
			"method": "GET",
			"path": "/api/v1/runs/123",
		},
		"peer": {"spiffe_id": ""},
		"resource": {"tenant_id": "tenant-a", "pii_tier": "low"},
	}
}

test_decision_denies_cross_tenant if {
	not decision.allow with input as {
		"identity": {
			"tenant_id": "tenant-a",
			"roles": ["admin"],
			"mfa_verified": true,
			"principal_type": "user",
		},
		"request": {
			"method": "GET",
			"path": "/api/v1/cas/artifacts/sha256:1",
		},
		"peer": {"spiffe_id": ""},
		"resource": {"tenant_id": "tenant-b", "kind": "cas_artifact", "pii_tier": "none"},
	}
}
