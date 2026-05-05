package polisyos.authz.data_classification

import rego.v1

default allow := false

pii_level := {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
role_pii_ceiling := {"admin": 4, "analyst": 3, "viewer": 1, "service": 3, "system": 4}

effective_ceiling := max(ceilings) if {
	ceilings := [
	role_pii_ceiling[role] |
		some role in input.identity.roles
		role_pii_ceiling[role]
	]
}

effective_ceiling := 0 if {
	count(input.identity.roles) == 0
}

resource_level := pii_level[object.get(input.resource, "pii_tier", "none")]

allow if {
	resource_level <= effective_ceiling
	anonymization_ok
	not critical_needs_mfa
}

anonymization_ok if {
	resource_level < 2
}

anonymization_ok if {
	resource_level >= 2
	object.get(input.resource, "requires_anonymization", false)
}

anonymization_ok if {
	resource_level >= 2
	effective_ceiling >= 3
}

critical_needs_mfa if {
	resource_level >= 4
	not object.get(input.identity, "mfa_verified", false)
}

allowed_columns contains col.name if {
	some col in object.get(input.resource, "columns", [])
	pii_level[col.pii_tier] <= effective_ceiling
}

deny_reasons contains reason if {
	resource_level > effective_ceiling
	reason := sprintf(
		"PII_CEILING_EXCEEDED: resource=%s ceiling=%d",
		[object.get(input.resource, "pii_tier", "none"), effective_ceiling],
	)
}

deny_reasons contains "ANONYMIZATION_REQUIRED" if {
	resource_level >= 2
	not object.get(input.resource, "requires_anonymization", false)
	effective_ceiling < 3
}

deny_reasons contains "MFA_REQUIRED_FOR_CRITICAL" if {
	critical_needs_mfa
}

audit_entry := {
	"policy": "data_classification",
	"decision": allow,
	"effective_ceiling": effective_ceiling,
	"allowed_columns": allowed_columns,
	"deny_reasons": deny_reasons,
}
