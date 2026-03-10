from __future__ import annotations


class TestAuthMe:
    def test_get_auth_me_returns_frontend_principal(self, runtime_api_env):
        client = runtime_api_env["client"]

        resp = client.get("/api/v1/auth/me")

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == "fixture-analyst"
        assert body["tenant_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        assert body["roles"] == ["analyst"]
        assert "runs.launch" in body["permissions"]
        assert "evidence.promotions.approve" in body["permissions"]
        assert body["feature_overrides"]["enableReviewCollaboration"] is True
