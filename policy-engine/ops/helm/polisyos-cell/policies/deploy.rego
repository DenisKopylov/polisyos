package polisyos.deploy.decision

import rego.v1

default allow := false

allow if {
    data.polisyos.deploy.vulnerability.allow with input as input
}

deny_reasons contains reason if {
    some reason in data.polisyos.deploy.vulnerability.deny_reasons with input as input
}

vulnerability_audit := entry if {
    entry := data.polisyos.deploy.vulnerability.audit_entry with input as input
}

audit_entry := {
    "policy": "deploy.decision",
    "decision": allow,
    "vulnerability": vulnerability_audit,
    "deny_reasons": deny_reasons,
}
