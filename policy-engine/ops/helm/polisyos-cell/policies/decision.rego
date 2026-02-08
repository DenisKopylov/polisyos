package polisyos.authz.decision

import rego.v1

default allow := false

allow if {
    data.polisyos.authz.tenant_boundary.allow with input as input
    data.polisyos.authz.role_access.allow with input as input
    data.polisyos.authz.data_classification.allow with input as input
    data.polisyos.authz.delegation_guard.allow with input as input
}

deny_reasons contains reason if {
    some reason in data.polisyos.authz.tenant_boundary.deny_reasons with input as input
}

deny_reasons contains reason if {
    some reason in data.polisyos.authz.role_access.deny_reasons with input as input
}

deny_reasons contains reason if {
    some reason in data.polisyos.authz.data_classification.deny_reasons with input as input
}

deny_reasons contains reason if {
    some reason in data.polisyos.authz.delegation_guard.deny_reasons with input as input
}

allowed_columns := data.polisyos.authz.data_classification.allowed_columns with input as input

audit_entry := {
    "policy": "decision",
    "decision": allow,
    "tenant_boundary": data.polisyos.authz.tenant_boundary.audit_entry with input as input,
    "role_access": data.polisyos.authz.role_access.audit_entry with input as input,
    "data_classification": data.polisyos.authz.data_classification.audit_entry with input as input,
    "delegation_guard": data.polisyos.authz.delegation_guard.audit_entry with input as input,
    "deny_reasons": deny_reasons,
}
