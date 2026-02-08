package polisyos.authz.decision

import rego.v1

default allow := false

tenant_boundary_allow if {
    data.polisyos.authz.tenant_boundary.allow with input as input
}

role_access_allow if {
    data.polisyos.authz.role_access.allow with input as input
}

data_classification_allow if {
    data.polisyos.authz.data_classification.allow with input as input
}

delegation_guard_allow if {
    data.polisyos.authz.delegation_guard.allow with input as input
}

allow if {
    tenant_boundary_allow
    role_access_allow
    data_classification_allow
    delegation_guard_allow
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

allowed_columns := cols if {
    cols := data.polisyos.authz.data_classification.allowed_columns with input as input
}

tenant_boundary_audit := entry if {
    entry := data.polisyos.authz.tenant_boundary.audit_entry with input as input
}

role_access_audit := entry if {
    entry := data.polisyos.authz.role_access.audit_entry with input as input
}

data_classification_audit := entry if {
    entry := data.polisyos.authz.data_classification.audit_entry with input as input
}

delegation_guard_audit := entry if {
    entry := data.polisyos.authz.delegation_guard.audit_entry with input as input
}

audit_entry := {
    "policy": "decision",
    "decision": allow,
    "tenant_boundary": tenant_boundary_audit,
    "role_access": role_access_audit,
    "data_classification": data_classification_audit,
    "delegation_guard": delegation_guard_audit,
    "deny_reasons": deny_reasons,
}
