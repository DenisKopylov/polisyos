package polisyos.authz.decision_test

import data.polisyos.authz.decision
import rego.v1

runtime_decision_input(
	role,
	permission,
	path,
	resource_class,
	authority,
	resource_tenant,
) := {
	"identity": {
		"tenant_id": "tenant-a",
		"roles": [role],
		"permissions": [permission],
		"authorization_source": "canonical_role_permissions",
		"mfa_verified": true,
		"principal_type": "user",
	},
	"request": {
		"method": "POST",
		"path": path,
	},
	"peer": {"spiffe_id": ""},
	"action": {"permission": permission},
	"resource": {
		"tenant_id": resource_tenant,
		"kind": sprintf("%s.%s", [resource_class, authority]),
		"class": resource_class,
		"binding_authority": authority,
		"pii_tier": "none",
	},
}

runtime_service_read_input(path, grants, source) := {
	"identity": {
		"tenant_id": "tenant-a",
		"roles": ["admin"],
		"permissions": grants,
		"authorization_source": source,
		"mfa_verified": false,
		"principal_type": "user",
	},
	"request": {
		"method": "GET",
		"path": path,
	},
	"peer": {"spiffe_id": ""},
	"resource": {
		"tenant_id": "tenant-a",
		"kind": "http_resource",
		"pii_tier": "none",
	},
}

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

# These three truthful DS20 envelopes were rejected by the legacy
# role/path/tenant composition before the action-permission bridge existed.
test_decision_allows_truthful_ingestion_binding if {
	decision.allow with input as runtime_decision_input(
		"admin",
		"evidence.acquire",
		"/api/v1/control/data/ingest",
		"runtime.evidence.acquisition",
		"request_bound",
		"",
	)
}

test_decision_allows_truthful_same_tenant_launch_binding if {
	decision.allow with input as runtime_decision_input(
		"analyst",
		"runs.launch",
		"/api/v1/control/runs",
		"runtime.run_collection",
		"tenant_collection",
		"tenant-a",
	)
}

test_decision_allows_truthful_unscoped_promotion_binding if {
	decision.allow with input as runtime_decision_input(
		"analyst",
		"evidence.promotions.approve",
		"/api/v1/control/data/promotion/p-1/approve",
		"runtime.evidence.promotion.approve",
		"content_resolved_unscoped",
		"",
	)
}

test_decision_denies_unsafe_request_without_action_contract if {
	not decision.allow with input as {
		"identity": {
			"tenant_id": "tenant-a",
			"roles": ["admin"],
			"mfa_verified": true,
			"principal_type": "user",
		},
		"request": {
			"method": "DELETE",
			"path": "/api/v1/policies/42",
		},
		"peer": {"spiffe_id": ""},
		"resource": {"tenant_id": "tenant-a", "pii_tier": "none"},
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

test_decision_allows_exact_service_read_grant if {
	decision.allow with input as runtime_service_read_input(
		"/api/v1/runs/run-1/timeline",
		["runs.launch", "runs.view"],
		"deployment_service_principal",
	)
}

test_decision_denies_service_read_without_exact_grant_despite_admin_role if {
	not decision.allow with input as runtime_service_read_input(
		"/api/v1/control/jobs/job-1",
		["runs.launch"],
		"deployment_service_principal",
	)
}

test_decision_denies_unknown_projected_authorization_source if {
	not decision.allow with input as runtime_service_read_input(
		"/api/v1/control/jobs/job-1",
		["runs.view"],
		"client_self_assertion",
	)
}
