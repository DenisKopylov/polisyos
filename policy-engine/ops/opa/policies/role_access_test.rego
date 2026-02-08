package polisyos.authz.role_access_test

import rego.v1
import data.polisyos.authz.role_access

test_admin_full_access if {
  role_access.allow with input as {
    "identity": {"roles": ["admin"], "mfa_verified": true},
    "request": {"method": "DELETE", "path": "/api/v1/policies/42"},
  }
}

test_viewer_denied_write if {
  not role_access.allow with input as {
    "identity": {"roles": ["viewer"], "mfa_verified": false},
    "request": {"method": "POST", "path": "/api/v1/runs/42"},
  }
}

test_sensitive_path_requires_mfa if {
  reasons := role_access.deny_reasons with input as {
    "identity": {"roles": ["analyst"], "mfa_verified": false},
    "request": {"method": "POST", "path": "/admin/users"},
  }
  "MFA_REQUIRED" in reasons
}
