package polisyos.authz.action_permission

import rego.v1

default allow := false

default action_request := false

default principal_projection_request := false

default deployment_service_read_request := false

default service_read_allow := false

# This set is a policy projection of RuntimePermission. The Python parity gate
# evaluates this rule and requires exact equality with the server enum.
permission_vocabulary := {
	"analysis.execute",
	"artifacts.batch.read",
	"artifacts.render",
	"dashboard.view",
	"decisions.validity.publish",
	"evidence.acquire",
	"evidence.discover",
	"evidence.preview",
	"evidence.promotions.approve",
	"evidence.promotions.reject",
	"evidence.resolve",
	"evidence.review",
	"evidence.sae.analyze",
	"evidence.view",
	"fabric.impact.analyze",
	"fabric.quality.read",
	"fabric.trust.read",
	"knowledge.search",
	"knowledge.trigger",
	"knowledge.view",
	"lineage.batch.read",
	"mobility.analyze",
	"mode.analyst",
	"platform.admin",
	"platform.view",
	"runs.batch.read",
	"runs.feedback.evaluate",
	"runs.human_decisions.create",
	"runs.launch",
	"runs.production_approval.create",
	"runs.reissue",
	"runs.review",
	"runs.view",
	"scenarios.create",
}

binding_authority_vocabulary := {
	"candidate",
	"content_resolved_unscoped",
	"ownership_verified",
	"request_bound",
	"tenant_collection",
}

authorization_source_vocabulary := {
	"canonical_role_permissions",
	"deployment_service_principal",
}

unsafe_methods := {"POST", "PUT", "PATCH", "DELETE"}

# Every admitted action-guarded route has one exact permission/resource/authority
# combination. Known values in a novel combination remain denied.
action_contracts := {
	"analysis.execute": {
		"runtime.analysis.attractors": {"tenant_collection"},
		"runtime.analysis.basin_map.candidate": {"candidate"},
		"runtime.analysis.continuation.candidate": {"candidate"},
		"runtime.analysis.lyapunov": {"tenant_collection"},
	},
	"artifacts.batch.read": {"runtime.artifact.batch": {"ownership_verified"}},
	"artifacts.render": {"runtime.artifact.bureaucratic_render": {"ownership_verified"}},
	"decisions.validity.publish": {"runtime.decision_validity.event": {"request_bound"}},
	"evidence.acquire": {"runtime.evidence.acquisition": {"request_bound"}},
	"evidence.discover": {"runtime.evidence.discover": {"request_bound"}},
	"evidence.preview": {"runtime.evidence.preview": {"request_bound"}},
	"evidence.promotions.approve": {"runtime.evidence.promotion.approve": {"content_resolved_unscoped"}},
	"evidence.promotions.reject": {"runtime.evidence.promotion.reject": {"content_resolved_unscoped"}},
	"evidence.resolve": {"runtime.evidence.resolve": {"request_bound"}},
	"evidence.sae.analyze": {"runtime.evidence.sae_causal_frontier": {"request_bound"}},
	"fabric.impact.analyze": {"runtime.fabric.impact": {"ownership_verified", "request_bound"}},
	"fabric.quality.read": {"runtime.fabric.quality_batch": {"ownership_verified"}},
	"fabric.trust.read": {"runtime.fabric.trust_batch": {"ownership_verified"}},
	"knowledge.search": {"runtime.lex_workspace.search": {"tenant_collection"}},
	"knowledge.trigger": {"runtime.lex_workspace.trigger": {"tenant_collection"}},
	"lineage.batch.read": {"runtime.lineage.batch": {"ownership_verified"}},
	"mobility.analyze": {
		"runtime.mobility_bounds": {"tenant_collection"},
		"runtime.mobility_estimate": {"tenant_collection"},
	},
	"runs.batch.read": {"runtime.run.batch": {"ownership_verified"}},
	"runs.feedback.evaluate": {"runtime.run.feedback_evaluation": {"ownership_verified"}},
	"runs.human_decisions.create": {"runtime.run.human_decision": {"ownership_verified"}},
	"runs.launch": {
		"runtime.run_collection": {"tenant_collection"},
		"runtime.run_collection.nl": {"tenant_collection"},
	},
	"runs.production_approval.create": {"runtime.run.production_approval": {"ownership_verified"}},
	"runs.reissue": {"runtime.run.reissue": {"ownership_verified"}},
	"runs.review": {
		"runtime.case_inspection": {"tenant_collection"},
		"runtime.governed_projection.depth_n_cycle_board": {"tenant_collection"},
		"runtime.run.human_decision_evidence": {"ownership_verified"},
		"runtime.run.human_decision_gate": {"ownership_verified"},
		"runtime.run.human_decision_record": {"ownership_verified"},
		"runtime.run.human_decision_review_effectiveness": {"ownership_verified"},
		"runtime.run_paper": {"tenant_collection"},
	},
	"scenarios.create": {"runtime.run.scenario.candidate": {"candidate", "ownership_verified"}},
}

# Deployment-managed service principals never inherit a role-shaped read
# surface. These are the exact GET paths required by the runtime canary after
# launch; the grant still comes from the canonical 33-value vocabulary.
service_read_contracts := {
	"runs.view": {
		"^/api/v1/control/jobs/[^/]+$",
		"^/api/v1/runs/[^/]+$",
		"^/api/v1/runs/[^/]+/(agents|lineage|timeline)$",
	},
}

resource_class_vocabulary contains resource_class if {
	some permission in permission_vocabulary
	some resource_class, _authorities in action_contracts[permission]
}

action_request if {
	object.get(input, "action", null) != null
}

action_request if {
	input.request.method in unsafe_methods
}

principal_projection_request if {
	not action_request
	object.get(input.identity, "authorization_source", "") != ""
}

deployment_service_read_request if {
	principal_projection_request
	authorization_source == "deployment_service_principal"
}

action_object := candidate if {
	candidate := object.get(input, "action", {})
	is_object(candidate)
}

action_object := {} if {
	candidate := object.get(input, "action", {})
	not is_object(candidate)
}

action_permission := object.get(action_object, "permission", "")
resource_class := object.get(input.resource, "class", "")
binding_authority := object.get(input.resource, "binding_authority", "")
authorization_source := object.get(input.identity, "authorization_source", "")
principal_permissions := object.get(input.identity, "permissions", [])

known_action_permission if {
	action_permission in permission_vocabulary
}

known_resource_class if {
	resource_class in resource_class_vocabulary
}

known_binding_authority if {
	binding_authority in binding_authority_vocabulary
}

known_authorization_source if {
	authorization_source in authorization_source_vocabulary
}

principal_permissions_known if {
	is_array(principal_permissions)
	every permission in principal_permissions {
		permission in permission_vocabulary
	}
}

principal_has_permission if {
	is_array(principal_permissions)
	action_permission in principal_permissions
}

service_read_path_allow if {
	input.request.method == "GET"
	is_array(principal_permissions)
	some permission in principal_permissions
	patterns := service_read_contracts[permission]
	some pattern in patterns
	regex.match(pattern, input.request.path)
}

service_read_tenant_binding_allow if {
	identity_tenant := object.get(input.identity, "tenant_id", "")
	identity_tenant != ""
	object.get(input.resource, "tenant_id", "") == identity_tenant
}

service_read_allow if {
	deployment_service_read_request
	principal_permissions_known
	service_read_path_allow
	service_read_tenant_binding_allow
}

action_resource_contract_allow if {
	authorities := action_contracts[action_permission][resource_class]
	binding_authority in authorities
}

resource_kind_matches if {
	input.resource.kind == sprintf("%s.%s", [resource_class, binding_authority])
}

tenant_binding_allow if {
	binding_authority in {"ownership_verified", "tenant_collection"}
	identity_tenant := object.get(input.identity, "tenant_id", "")
	identity_tenant != ""
	object.get(input.resource, "tenant_id", "") == identity_tenant
}

tenant_binding_allow if {
	binding_authority in {"content_resolved_unscoped", "request_bound"}
	object.get(input.identity, "tenant_id", "") != ""
	object.get(input.resource, "tenant_id", "") == ""
}

tenant_binding_allow if {
	binding_authority == "candidate"
	object.get(input.identity, "tenant_id", "") != ""
	object.get(input.resource, "tenant_id", "") == ""
}

tenant_binding_allow if {
	binding_authority == "candidate"
	identity_tenant := object.get(input.identity, "tenant_id", "")
	identity_tenant != ""
	object.get(input.resource, "tenant_id", "") == identity_tenant
}

allow if {
	action_request
	known_action_permission
	known_resource_class
	known_binding_authority
	known_authorization_source
	principal_permissions_known
	principal_has_permission
	action_resource_contract_allow
	resource_kind_matches
	tenant_binding_allow
}

deny_reasons contains "SERVICE_READ_AUTHORIZATION_SOURCE_DENY" if {
	principal_projection_request
	not deployment_service_read_request
}

deny_reasons contains "SERVICE_READ_PERMISSION_VOCABULARY_INVALID" if {
	deployment_service_read_request
	not principal_permissions_known
}

deny_reasons contains "SERVICE_READ_PERMISSION_DENY" if {
	deployment_service_read_request
	principal_permissions_known
	not service_read_path_allow
}

deny_reasons contains "SERVICE_READ_RESOURCE_TENANT_BINDING_DENY" if {
	deployment_service_read_request
	not service_read_tenant_binding_allow
}

deny_reasons contains "ACTION_PERMISSION_UNKNOWN" if {
	action_request
	not known_action_permission
}

deny_reasons contains "ACTION_RESOURCE_CLASS_UNKNOWN" if {
	action_request
	not known_resource_class
}

deny_reasons contains "ACTION_BINDING_AUTHORITY_UNKNOWN" if {
	action_request
	not known_binding_authority
}

deny_reasons contains "ACTION_AUTHORIZATION_SOURCE_UNKNOWN" if {
	action_request
	not known_authorization_source
}

deny_reasons contains "ACTION_PRINCIPAL_PERMISSION_VOCABULARY_INVALID" if {
	action_request
	not principal_permissions_known
}

deny_reasons contains "ACTION_PERMISSION_DENY" if {
	action_request
	known_action_permission
	not principal_has_permission
}

deny_reasons contains "ACTION_RESOURCE_CONTRACT_DENY" if {
	action_request
	known_action_permission
	known_resource_class
	known_binding_authority
	not action_resource_contract_allow
}

deny_reasons contains "ACTION_RESOURCE_KIND_MISMATCH" if {
	action_request
	known_resource_class
	known_binding_authority
	not resource_kind_matches
}

deny_reasons contains "ACTION_RESOURCE_TENANT_BINDING_DENY" if {
	action_request
	known_binding_authority
	not tenant_binding_allow
}

audit_entry := {
	"policy": "action_permission",
	"decision": allow,
	"principal_projection_request": principal_projection_request,
	"service_read_decision": service_read_allow,
	"permission": action_permission,
	"resource_class": resource_class,
	"binding_authority": binding_authority,
	"authorization_source": authorization_source,
	"deny_reasons": deny_reasons,
}
