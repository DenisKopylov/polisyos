package polisyos.authz.tenant_boundary

import rego.v1

default allow := false

allow if {
	input.identity.tenant_id != ""
	resource_tenant := object.get(input.resource, "tenant_id", input.identity.tenant_id)
	input.identity.tenant_id == resource_tenant
}

deny_reasons contains reason if {
	resource_tenant := object.get(input.resource, "tenant_id", "")
	resource_tenant != ""
	input.identity.tenant_id != resource_tenant
	reason := sprintf(
		"CROSS_TENANT_ACCESS: identity=%s resource=%s kind=%s",
		[input.identity.tenant_id, resource_tenant, object.get(input.resource, "kind", "")],
	)
}

audit_entry := {
	"policy": "tenant_boundary",
	"decision": allow,
	"identity_tenant": input.identity.tenant_id,
	"resource_tenant": object.get(input.resource, "tenant_id", ""),
	"deny_reasons": deny_reasons,
}
