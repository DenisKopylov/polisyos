package polisyos.authz.delegation_guard

import rego.v1

default allow := false

allow if {
	object.get(input.identity, "principal_type", "user") != "user"
}

allow if {
	object.get(input.identity, "principal_type", "user") == "user"
	object.get(input.peer, "spiffe_id", "") == ""
}

allow if {
	object.get(input.identity, "principal_type", "user") == "user"
	object.get(input.peer, "spiffe_id", "") != ""
	trusted_delegator
}

trusted_delegator if {
	startswith(object.get(input.peer, "spiffe_id", ""), "spiffe://")
}

deny_reasons contains "UNTRUSTED_DELEGATOR" if {
	object.get(input.identity, "principal_type", "user") == "user"
	object.get(input.peer, "spiffe_id", "") != ""
	not trusted_delegator
}

audit_entry := {
	"policy": "delegation_guard",
	"decision": allow,
	"peer_spiffe_id": object.get(input.peer, "spiffe_id", ""),
	"deny_reasons": deny_reasons,
}
