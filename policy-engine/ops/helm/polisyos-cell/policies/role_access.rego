package polisyos.authz.role_access

import rego.v1

default allow := false

role_permissions := {
	"admin": {
		"methods": {"GET", "POST", "PUT", "PATCH", "DELETE"},
		"paths": [".*"],
	},
	"analyst": {
		"methods": {"GET", "POST", "PUT"},
		"paths": [
			"^/api/v1/runs/.*",
			"^/api/v1/data/.*",
			"^/api/v1/reports/.*",
			"^/internal/.*",
		],
	},
	"viewer": {
		"methods": {"GET"},
		"paths": [
			"^/api/v1/runs/.*",
			"^/api/v1/reports/.*",
			"^/api/v1/data/[^/]+/summary$",
		],
	},
	"service": {
		"methods": {"GET", "POST", "PUT"},
		"paths": ["^/internal/.*", "^/api/v1/cas/.*", "^/api/v1/data/.*"],
	},
}

sensitive_paths := [
	"^/api/v1/gates/.*/decide$",
	"^/api/v1/policies/.*/publish$",
	"^/admin/.*",
]

allow if {
	some role in input.identity.roles
	perms := role_permissions[role]
	input.request.method in perms.methods
	some pattern in perms.paths
	regex.match(pattern, input.request.path)
	not mfa_required
}

mfa_required if {
	some pattern in sensitive_paths
	regex.match(pattern, input.request.path)
	not object.get(input.identity, "mfa_verified", false)
}

deny_reasons contains "MFA_REQUIRED" if {
	mfa_required
}

deny_reasons contains reason if {
	not allow
	not mfa_required
	reason := sprintf(
		"RBAC_DENY: method=%s path=%s roles=%v",
		[input.request.method, input.request.path, input.identity.roles],
	)
}

audit_entry := {
	"policy": "role_access",
	"decision": allow,
	"deny_reasons": deny_reasons,
	"roles": input.identity.roles,
	"path": input.request.path,
}
