"""Independent stage1 byte custody and source-footprint check, no product tests."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

repo = "/dev/shm/e02-orch03-20261008/c07"
root = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/"
checks = []


def git(*args):
    return subprocess.check_output(["git", "-C", repo, *args])


def read(commit, path):
    return git("show", f"{commit}:{path}")


def eq(label, actual, expected):
    checks.append({"label": label, "actual": actual, "expected": expected, "state": "PASS" if actual == expected else "FAIL"})


def checked_bytes(label, raw, size, digest):
    eq(label + ":bytes", len(raw), size)
    eq(label + ":sha256", hashlib.sha256(raw).hexdigest(), digest)


c08 = "222d0867d47428bdb1835c6e6a68c2787bc05be9"
p08 = root + "F/parallel-20261008-c08/proof-source-query-handoff/manifest.json"
m08 = json.loads(read(c08, p08))
stored08 = decoded08 = 0
for item in m08["entries"]:
    data = read(c08, item["path"])
    checked_bytes(item["path"], data, item["stored_bytes"], item["stored_sha256"])
    decoded = gzip.decompress(data) if item["encoding"] == "gzip" else data
    checked_bytes(item["origin"], decoded, item["decoded_bytes"], item["decoded_sha256"])
    stored08 += len(data)
    decoded08 += len(decoded)
eq("C08 entry count", len(m08["entries"]), 177)
eq("C08 stored sum", stored08, m08["stored_bytes"])
eq("C08 decoded sum", decoded08, m08["decoded_bytes"])
receipt08 = json.loads(read(c08, root + "F/parallel-20261008-c08/proof-source-query-handoff.json"))
foot08 = receipt08["full_source_test_companion_footprint"]
actual08 = git("diff", "--name-only", foot08["base"], foot08["candidate"]).decode().splitlines()
eq("C08 full footprint", [p["path"] for p in foot08["paths"]], actual08)
for item in foot08["paths"]:
    for side in ["base", "candidate"]:
        if item[side] is not None:
            data = read(foot08[side], item["path"])
            checked_bytes("C08 " + side + ":" + item["path"], data, item[side]["bytes"], item[side]["sha256"])
            eq("C08 " + side + " blob:" + item["path"], git("rev-parse", f"{foot08[side]}:{item['path']}").decode().strip(), item[side]["blob"])

c09 = "8ea1f703f8ed6cd9294f9e9cce7f9aa96cf9d8b2"
p09 = root + "E/parallel-20261008-c09/interval-consumer-basis/"
m09 = json.loads(read(c09, p09 + "artifact-manifest.json"))
for item in m09["artifacts"]:
    checked_bytes(item["path"], read(c09, item["path"]), item["bytes"], item["sha256"])
index = json.loads(gzip.decompress(read(c09, p09 + m09["complete_archive_members"])))
members_count = members_bytes = 0
for archive in index["archives"]:
    raw = read(c09, archive["archive"])
    checked_bytes(archive["archive"], raw, archive["stored_bytes"], archive["stored_sha256"])
    decoded = gzip.decompress(raw)
    checked_bytes(archive["archive"] + ":tar", decoded, archive["decoded_tar_bytes"], archive["decoded_tar_sha256"])
    with tarfile.open(fileobj=io.BytesIO(decoded), mode="r:") as tf:
        files = [m for m in tf.getmembers() if m.isfile()]
        eq(archive["archive"] + ":complete member roster", sorted(m.name for m in files), sorted(m["path"] for m in archive["members"]))
        actual_payload_bytes = 0
        for item in archive["members"]:
            data = tf.extractfile(item["path"]).read()
            checked_bytes(archive["archive"] + ":" + item["path"], data, item["bytes"], item["sha256"])
            actual_payload_bytes += len(data)
        eq(archive["archive"] + ":member count", len(files), archive["member_count"])
        eq(archive["archive"] + ":payload bytes", actual_payload_bytes, archive["member_payload_bytes"])
        members_count += len(files)
        members_bytes += actual_payload_bytes
eq("C09 direct artifacts", len(m09["artifacts"]), 24)
eq("C09 archives", len(index["archives"]), 8)
eq("C09 members", members_count, 2075)
eq("C09 member payload bytes", members_bytes, 6209000)
receipt09 = json.loads(read(c09, p09[:-1] + ".json"))
actual09 = git("diff", "--name-only", receipt09["slice_base_sha"], receipt09["candidate_sha"]).decode().splitlines()
eq("C09 full footprint", [p["path"] for p in receipt09["full_footprint"]], actual09)
for item in receipt09["full_footprint"]:
    for side, commit in [("base", receipt09["slice_base_sha"]), ("candidate", receipt09["candidate_sha"])]:
        if item[side + "_blob"] is not None:
            eq("C09 " + side + " blob:" + item["path"], git("rev-parse", f"{commit}:{item['path']}").decode().strip(), item[side + "_blob"])

out = {
    "purpose": "Independent Git byte custody/source-footprint only, no product test/review/acceptance",
    "C08": {"commit": c08, "entries": len(m08["entries"]), "stored_bytes": stored08, "decoded_bytes": decoded08, "source_paths": len(actual08)},
    "C09": {"commit": c09, "direct_artifacts": len(m09["artifacts"]), "archives": len(index["archives"]), "members": members_count, "member_payload_bytes": members_bytes, "source_paths": len(actual09)},
    "checks": checks,
    "mismatches": [check for check in checks if check["state"] != "PASS"],
}
p = Path("/dev/shm/e02-orch03-20261008/c07-coordination-review/stage1-custody.json")
p.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps({k:v for k,v in out.items() if k != "checks"}))
