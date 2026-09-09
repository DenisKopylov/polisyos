"""Retain actual HTTP failure payload before the producer's temporary store closes."""
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from tools.quality.validation import check_layer3_gy_loop_artifacts as owner


def main():
    real_get = TestClient.get

    def observed_get(client, *args, **kwargs):
        response = real_get(client, *args, **kwargs)
        print(json.dumps({"method": "GET", "path": str(args[0]),
                          "status_code": response.status_code,
                          "complete_http_payload": response.json()}, sort_keys=True))
        return response

    with patch.object(TestClient, "get", observed_get):
        owner._run_durable_workspace_loop_observation(
            fixture_id="ua_msme_credit_worldbank_measurement",
            catalog_mode="slice0_fixture", repo_root=Path.cwd(),
        )


if __name__ == "__main__":
    main()
