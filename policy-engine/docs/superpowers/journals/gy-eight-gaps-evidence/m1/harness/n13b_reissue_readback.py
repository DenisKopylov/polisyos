"""Check the governed M1 companion delta without retaining copies of either receipt."""
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "43580c80b"


def prior(path):
    return subprocess.check_output(["git", "show", f"{BASE}:policy-engine/{path}"], cwd=ROOT)


def sha(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


path = "architecture/policy_design_case/layer3_gy_n13b_acquisition_executor_contract.json"
old_bytes = prior(path)
new_bytes = (ROOT / path).read_bytes()
old, new = json.loads(old_bytes), json.loads(new_bytes)
allowed = {"schema_version", "lifecycle", "source_owners", "contract_sha256"}
assert {key: value for key, value in old.items() if key not in allowed} == {
    key: value for key, value in new.items() if key not in allowed
}
assert old["schema_version"] == "policyos.layer3.gy.n13b.acquisition_executor_contract.v4"
assert new["schema_version"] == "policyos.layer3.gy.n13b.acquisition_executor_contract.v5"
old_owners = {row["path"]: row for row in old["source_owners"]}
new_owners = {row["path"]: row for row in new["source_owners"]}
verifier = "tools/quality/validation/check_layer3_gy_generated_public_lifecycle_audit.py"
assert set(new_owners) - set(old_owners) == {verifier}
assert set(old_owners) <= set(new_owners)
refreshed_owner_bindings = sorted(key for key, row in old_owners.items() if new_owners[key] != row)
for key in old_owners:
    # A fresh receipt may correct inherited stale bindings, but this lane did
    # not change those owners' source while performing lifecycle repair.
    assert prior(key) == (ROOT / key).read_bytes()
for key, row in new_owners.items():
    payload = (ROOT / key).read_bytes()
    assert row["file_sha256"] == sha(payload)
    assert row["byte_size"] == len(payload)
old_lifecycle, new_lifecycle = old["lifecycle"], new["lifecycle"]
allowed_lifecycle = {"schema_version", "generated_family_projection_sha256", "source_family_id", "manifest_sha256"}
assert {key: value for key, value in old_lifecycle.items() if key not in allowed_lifecycle} == {
    key: value for key, value in new_lifecycle.items() if key not in allowed_lifecycle
}
old_registry = tomllib.loads(prior("architecture/generated_artifacts.toml").decode())
new_registry = tomllib.loads((ROOT / "architecture/generated_artifacts.toml").read_text())
generated_id = "policy-design-case-layer3-gy-n13b-acquisition-executor"
source_id = "policy-design-case-layer3-gy-n13b-frozen-acquisition-evidence"
old_paths = {p for f in old_registry["family"] if f["id"] == generated_id for p in f["outputs"]}
new_paths = {p for f in new_registry["family"] if f["id"] in {generated_id, source_id} for p in f["outputs"]}
assert old_paths == new_paths
registrations = new_lifecycle["registrations"]
assert {row["path"] for row in registrations} == new_paths
assert len(registrations) == len(new_paths)
source = next(f for f in new_registry["family"] if f["id"] == source_id)
for relative in source["outputs"]:
    assert prior(relative) == (ROOT / relative).read_bytes()
assert len(source["outputs"]) == sum(1 for p in new_paths if p in source["outputs"])
print(json.dumps({
    "status": "pass",
    "contract": {"path": path, "base": BASE, "before_sha256": sha(old_bytes), "after_sha256": sha(new_bytes)},
    "changed_top_level_identities": sorted(key for key in set(old) | set(new) if key not in old or key not in new or old[key] != new[key]),
    "execution_and_authority_projections_unchanged": True,
    "lifecycle_registration_union_preserved": len(new_paths),
    "independent_registration_row_count": len(registrations),
    "frozen_source_files_byte_identical": len(source["outputs"]),
    "source_owner_rows_verified": len(new_owners),
    "added_verified_source_owner": verifier,
    "refreshed_inherited_source_owner_bindings": refreshed_owner_bindings,
    "existing_source_owner_files_unchanged_from_lane_base": True,
}, indent=2))
