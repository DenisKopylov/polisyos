package polisyos.authz.tenant_boundary_test

import data.polisyos.authz.tenant_boundary
import rego.v1

test_same_tenant_allowed if {
	tenant_boundary.allow with input as {
		"identity": {"tenant_id": "tenant-a"},
		"resource": {"tenant_id": "tenant-a", "kind": "cas_artifact"},
	}
}

test_cross_tenant_denied if {
	not tenant_boundary.allow with input as {
		"identity": {"tenant_id": "tenant-a"},
		"resource": {"tenant_id": "tenant-b", "kind": "cas_artifact"},
	}
}

test_cross_tenant_has_reason if {
	reasons := tenant_boundary.deny_reasons with input as {
		"identity": {"tenant_id": "tenant-a"},
		"resource": {"tenant_id": "tenant-b", "kind": "cas_artifact"},
	}
	"CROSS_TENANT_ACCESS: identity=tenant-a resource=tenant-b kind=cas_artifact" in reasons
}
