package polisyos.authz.action_permission_test

import data.polisyos.authz.action_permission
import rego.v1

runtime_action_input(permission, resource_class, authority, resource_tenant, grants) := {
	"request": {
		"method": "POST",
		"path": "/api/v1/runtime-mutation",
	},
	"identity": {
		"tenant_id": "tenant-a",
		"roles": ["analyst"],
		"permissions": grants,
		"authorization_source": "canonical_role_permissions",
	},
	"action": {"permission": permission},
	"resource": {
		"tenant_id": resource_tenant,
		"class": resource_class,
		"binding_authority": authority,
		"kind": sprintf("%s.%s", [resource_class, authority]),
	},
}

runtime_service_read_input(path, resource_tenant, grants, source) := {
	"request": {
		"method": "GET",
		"path": path,
	},
	"identity": {
		"tenant_id": "tenant-a",
		"roles": ["admin"],
		"permissions": grants,
		"authorization_source": source,
	},
	"resource": {
		"tenant_id": resource_tenant,
		"kind": "http_resource",
	},
}

test_allows_exact_permission_resource_authority_contract if {
	action_permission.allow with input as runtime_action_input(
		"runs.launch",
		"runtime.run_collection",
		"tenant_collection",
		"tenant-a",
		["runs.launch"],
	)
}

test_denies_permission_absent_from_principal_grants if {
	not action_permission.allow with input as runtime_action_input(
		"runs.launch",
		"runtime.run_collection",
		"tenant_collection",
		"tenant-a",
		["runs.view"],
	)
}

test_denies_unknown_action_permission if {
	not action_permission.allow with input as runtime_action_input(
		"runs.launch.synonym",
		"runtime.run_collection",
		"tenant_collection",
		"tenant-a",
		["runs.launch.synonym"],
	)
}

test_denies_unknown_resource_class if {
	not action_permission.allow with input as runtime_action_input(
		"runs.launch",
		"runtime.run_collection.synonym",
		"tenant_collection",
		"tenant-a",
		["runs.launch"],
	)
}

test_denies_unknown_binding_authority if {
	not action_permission.allow with input as runtime_action_input(
		"runs.launch",
		"runtime.run_collection",
		"self_asserted",
		"tenant-a",
		["runs.launch"],
	)
}

test_denies_known_values_in_wrong_contract if {
	not action_permission.allow with input as runtime_action_input(
		"evidence.acquire",
		"runtime.run_collection",
		"tenant_collection",
		"tenant-a",
		["evidence.acquire"],
	)
}

test_denies_unknown_authorization_source if {
	candidate := runtime_action_input(
		"runs.launch",
		"runtime.run_collection",
		"tenant_collection",
		"tenant-a",
		["runs.launch"],
	)
	malformed := object.union(candidate, {"identity": object.union(candidate.identity, {"authorization_source": "client_self_assertion"})})
	not action_permission.allow with input as malformed
}

test_denies_unknown_extra_principal_grant if {
	not action_permission.allow with input as runtime_action_input(
		"runs.launch",
		"runtime.run_collection",
		"tenant_collection",
		"tenant-a",
		["runs.launch", "runs.launch.synonym"],
	)
}

test_denies_resource_kind_that_discards_binding_authority if {
	candidate := runtime_action_input(
		"runs.launch",
		"runtime.run_collection",
		"tenant_collection",
		"tenant-a",
		["runs.launch"],
	)
	malformed := object.union(candidate, {"resource": object.union(candidate.resource, {"kind": "runtime.run_collection"})})
	not action_permission.allow with input as malformed
}

test_denies_cross_tenant_owned_resource if {
	not action_permission.allow with input as runtime_action_input(
		"runs.launch",
		"runtime.run_collection",
		"tenant_collection",
		"tenant-b",
		["runs.launch"],
	)
}

test_denies_fabricated_tenant_on_unscoped_resource if {
	not action_permission.allow with input as runtime_action_input(
		"evidence.acquire",
		"runtime.evidence.acquisition",
		"request_bound",
		"tenant-a",
		["evidence.acquire"],
	)
}

test_denies_unsafe_request_without_action_contract if {
	not action_permission.allow with input as {
		"request": {"method": "DELETE", "path": "/api/v1/runtime-mutation"},
		"identity": {"tenant_id": "tenant-a"},
		"resource": {},
	}
}

test_denies_malformed_action_without_evaluation_error if {
	not action_permission.allow with input as {
		"request": {"method": "DELETE", "path": "/api/v1/runtime-mutation"},
		"identity": {
			"tenant_id": "tenant-a",
			"permissions": ["runs.launch"],
			"authorization_source": "canonical_role_permissions",
		},
		"action": "runs.launch",
		"resource": {
			"tenant_id": "tenant-a",
			"class": "runtime.run_collection",
			"binding_authority": "tenant_collection",
			"kind": "runtime.run_collection.tenant_collection",
		},
	}
}

test_service_read_allows_exact_canary_job_grant if {
	action_permission.service_read_allow with input as runtime_service_read_input(
		"/api/v1/control/jobs/job-1",
		"tenant-a",
		["runs.launch", "runs.view"],
		"deployment_service_principal",
	)
}

test_service_read_denies_overbroad_role_without_exact_grant if {
	not action_permission.service_read_allow with input as runtime_service_read_input(
		"/api/v1/control/jobs/job-1",
		"tenant-a",
		["runs.launch"],
		"deployment_service_principal",
	)
}

test_service_read_denies_unknown_path if {
	not action_permission.service_read_allow with input as runtime_service_read_input(
		"/api/v1/control/data/secret",
		"tenant-a",
		["runs.view"],
		"deployment_service_principal",
	)
}

test_service_read_denies_cross_tenant_resource if {
	not action_permission.service_read_allow with input as runtime_service_read_input(
		"/api/v1/runs/run-1",
		"tenant-b",
		["runs.view"],
		"deployment_service_principal",
	)
}

test_service_read_denies_unknown_authorization_source if {
	not action_permission.service_read_allow with input as runtime_service_read_input(
		"/api/v1/runs/run-1",
		"tenant-a",
		["runs.view"],
		"client_self_assertion",
	)
}
