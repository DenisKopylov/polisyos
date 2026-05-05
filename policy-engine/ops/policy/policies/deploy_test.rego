package polisyos.deploy.decision_test

import data.polisyos.deploy.decision
import rego.v1

test_deploy_allow if {
	decision.allow with input as {"deployment": {
		"image": "ghcr.io/polisyos/policy-engine:main",
		"sbom": {
			"hash": "abc",
			"vulnerabilities": [],
		},
	}}
}

test_deploy_deny_if_missing_sbom if {
	not decision.allow with input as {"deployment": {"image": "ghcr.io/polisyos/policy-engine:main"}}
}
