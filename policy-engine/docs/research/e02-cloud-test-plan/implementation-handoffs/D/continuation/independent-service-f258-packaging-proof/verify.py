import base64, gzip, hashlib, json, pathlib, subprocess, sys
repo, current_sha = sys.argv[1:3]
old_sha = "334f3b0e8a1e7313dbe05fec46331f1c52a9c5ad"
path = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/continuation/independent-service-f258-output.json.gz"
def git(*args):
    return subprocess.check_output(["git", *args], cwd=repo)
old = git("show", old_sha + ":" + path)
current = git("show", current_sha + ":" + path)
old_raw, current_raw = gzip.decompress(old), gzip.decompress(current)
a, b = json.loads(old_raw), json.loads(current_raw)
assert list(a) == list(b) and a["schema"] == b["schema"]
assert len(a["members"]) == len(b["members"]) == 60
restored = current_raw
changed = []
for i, (before, after) in enumerate(zip(a["members"], b["members"], strict=True)):
    if i not in (54, 57):
        assert before == after, i
        continue
    assert {k: v for k, v in before.items() if k != "content"} == {k: v for k, v in after.items() if k != "content"}
    ref = after["content"]
    assert ref["kind"] == "tracked_git_input_ref"
    assert ref["source_sha"] == before["origin"]["git_sha"]
    assert ref["path"] == before["origin"]["git_path"]
    raw = git("show", ref["source_sha"] + ":" + ref["path"])
    blob = git("rev-parse", ref["source_sha"] + ":" + ref["path"]).decode().strip()
    assert blob == ref["git_blob"]
    assert len(raw) == before["bytes"] == ref["bytes"]
    assert hashlib.sha256(raw).hexdigest() == before["sha256"] == ref["sha256"]
    assert base64.b64encode(raw).decode() == before["content"]
    token = json.dumps(ref, sort_keys=True, separators=(",", ":")).encode()
    assert restored.count(token) == 1
    restored = restored.replace(token, json.dumps(before["content"]).encode(), 1)
    changed.append({"index": i, "name": before["name"], "git_blob": blob, "bytes": len(raw), "sha256": ref["sha256"]})
assert restored == old_raw
# Metadata-only footprint and immutable receipt/scope bytes across the topic delta.
base_sha = "83fffc0f74fe3ef88857f57e5132187c8fb7101a"
paths = git("diff", "--name-only", base_sha, current_sha).decode().splitlines()
assert len(paths) == 3 and all(p.startswith("policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/continuation/independent-service-f258-") for p in paths)
print(json.dumps({"classification": "PASS_PACKAGING_BYTES_ONLY", "candidate_sha": current_sha, "candidate_tree": git("rev-parse", current_sha + "^{tree}").decode().strip(), "original_sha": old_sha, "original_carrier_sha256": hashlib.sha256(old).hexdigest(), "current_carrier_sha256": hashlib.sha256(current).hexdigest(), "other_members_unchanged": 58, "replacements": changed, "exact_raw_restoration_sha256": hashlib.sha256(restored).hexdigest(), "metadata_delta_paths": paths, "runtime_or_product_or_test_edits": 0}, indent=2))
