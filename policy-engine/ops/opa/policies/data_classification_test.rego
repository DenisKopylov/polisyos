package polisyos.authz.data_classification_test

import data.polisyos.authz.data_classification
import rego.v1

test_low_allowed_for_viewer if {
	data_classification.allow with input as {
		"identity": {"roles": ["viewer"], "mfa_verified": false},
		"resource": {"pii_tier": "low"},
	}
}

test_high_denied_for_viewer if {
	not data_classification.allow with input as {
		"identity": {"roles": ["viewer"], "mfa_verified": false},
		"resource": {"pii_tier": "high"},
	}
}

test_critical_requires_mfa if {
	reasons := data_classification.deny_reasons with input as {
		"identity": {"roles": ["admin"], "mfa_verified": false},
		"resource": {"pii_tier": "critical"},
	}
	"MFA_REQUIRED_FOR_CRITICAL" in reasons
}

test_allowed_columns_filtered_by_ceiling if {
	allowed := data_classification.allowed_columns with input as {
		"identity": {"roles": ["viewer"], "mfa_verified": false},
		"resource": {
			"pii_tier": "none",
			"columns": [
				{"name": "gdp", "pii_tier": "none"},
				{"name": "email", "pii_tier": "medium"},
				{"name": "age_group", "pii_tier": "low"},
			],
		},
	}
	allowed == {"gdp", "age_group"}
}
