"""Read-only source/archive/site custody and one isolated installed consumer run.

All emitted files are reviewer-owned /tmp evidence. No build, product mutation,
worker quota, implicit dependency install or acceptance authority is introduced.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tarfile
import time
import tomllib
import zipfile


def binding(path):
    p = Path(path)
    raw = p.read_bytes()
    return {"path": str(p), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


config_path = Path(sys.argv[1]).resolve()
config = json.loads(config_path.read_text())
mode = sys.argv[2]
review = Path(config["review_scratch"])
root = Path(config["source_root"])
scratch = Path(config["scratch"])
source = config["source_sha"]
assert source == "8236d9c368336a5ea20c1586f29aea7321db6536"
assert config["source_tree"] == "724a77c88d4e6699ffead58a5e3e3990fb88640a"
assert review.is_relative_to(Path("/tmp"))


def git(*args):
    return subprocess.check_output(["git", *args], cwd=root)


def source_guard():
    assert git("rev-parse", "HEAD").decode().strip() == source
    assert git("rev-parse", "HEAD^{tree}").decode().strip() == config["source_tree"]
    assert not git("status", "--porcelain", "--untracked-files=no")


def carrier_guard():
    verified = []
    for kind in ("wheel", "sdist"):
        carrier = scratch / (kind + "-consumer")
        for role, source_path in config["carrier_paths"].items():
            raw = git("show", source + ":" + source_path)
            target = carrier / Path(source_path).name
            assert target.read_bytes() == raw, (kind, source_path)
            verified.append({"profile": kind, "role": role, "source_path": source_path,
                             "git_blob": git("rev-parse", source + ":" + source_path).decode().strip(),
                             **binding(target)})
        boundary = Path(__file__).with_name("test_installed_native_boundaries.py")
        assert binding(boundary)["sha256"] == config["independent_boundaries_sha256"]
        assert (carrier / boundary.name).read_bytes() == boundary.read_bytes()
    return verified


def package_guard():
    proof_path = scratch / "archive-installed-source-bindings.json"
    proof = json.loads(proof_path.read_text())
    assert proof["source_sha"] == source and proof["source_tree"] == config["source_tree"]
    rows = proof["source_bindings"]
    tree = {}
    for entry in git("ls-tree", "-rz", "--full-tree", source).split(b"\0"):
        if not entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        tree[path.decode()] = {"mode": mode, "kind": kind, "oid": oid}
    product_paths = {p for p in tree if p.startswith(("policy-engine/src/polisyos/", "policy-engine/tools/"))}
    hatch = tomllib.loads(git("show", source + ":policy-engine/hatch.toml").decode())
    resources = hatch["build"]["targets"]["wheel"]["force-include"]
    assert len(resources) == 7
    assert {r["source"] for r in rows if r["role"] == "tracked_product"} == product_paths
    assert {(r["source"], r["destination"]) for r in rows if r["role"] == "forced_resource"} == {
        ("policy-engine/" + path, target) for path, target in resources.items()}
    ids = [tree[row["source"]]["oid"] for row in rows]
    assert ids == [row["git_blob"] for row in rows]
    result = subprocess.run(["git", "cat-file", "--batch"], cwd=root,
        input=("\n".join(ids) + "\n").encode(), stdout=subprocess.PIPE, check=True)
    stream = io.BytesIO(result.stdout)
    expected = {}
    for row, oid in zip(rows, ids, strict=True):
        header = stream.readline().decode().strip().split()
        assert header[0] == oid and header[1] == "blob"
        raw = stream.read(int(header[2]))
        assert stream.read(1) == b"\n"
        assert len(raw) == row["bytes"] and hashlib.sha256(raw).hexdigest() == row["sha256"]
        assert row["destination"] not in expected
        expected[row["destination"]] = raw
    assert not stream.read()
    archive_refs = {}
    for kind in ("wheel", "rebuilt_wheel"):
        archive_path = config["archives"][kind]
        archive_refs[kind] = binding(archive_path)
        assert archive_refs[kind]["sha256"] == proof["archives"][kind]["sha256"]
        with zipfile.ZipFile(archive_path) as archive:
            names = {n for n in archive.namelist() if n.startswith(("polisyos/", "tools/")) and not n.endswith("/")}
            assert names == set(expected), (kind, names.symmetric_difference(expected))
            for target, raw in expected.items():
                assert archive.read(target) == raw, (kind, target)
    archive_refs["sdist"] = binding(config["archives"]["sdist"])
    assert archive_refs["sdist"]["sha256"] == proof["archives"]["sdist"]["sha256"]
    with tarfile.open(config["archives"]["sdist"]) as archive:
        prefix = archive.getnames()[0].split("/")[0] + "/"
        for row in rows:
            reader = archive.extractfile(prefix + row["source"].removeprefix("policy-engine/"))
            assert reader and reader.read() == expected[row["destination"]], row["source"]
    site_refs = {}
    for kind, site_path in config["sites"].items():
        site = Path(site_path)
        pth = site / "e02_readonly_dependencies.pth"
        assert pth.read_text() == config["dependency_site"] + "\n"
        for target, raw in expected.items():
            assert (site / target).read_bytes() == raw, (kind, target)
        py_files = {p.relative_to(site).as_posix() for prefix in ("polisyos", "tools") for p in (site / prefix).rglob("*.py")}
        assert py_files == {name for name in expected if name.endswith(".py")}
        site_refs[kind] = {"site": str(site), "files": len(expected), "complete_python_files": len(py_files), "dependency_pth": binding(pth)}
    return {"owner_proof": binding(proof_path), "archives": archive_refs, "sites": site_refs,
            "git_source_bindings_verified": len(rows), "forced_resources": sum(r["role"] == "forced_resource" for r in rows)}


source_guard()
carriers = carrier_guard()
if mode == "preflight":
    custody = package_guard()
    source_guard()
    record = {"check": "PASS", "source_sha": source, "source_tree": config["source_tree"],
              "config": binding(config_path), "custody": custody, "carrier_bindings": carriers,
              "scope": "Git/archive/site/carrier bytes only; native consumers UNRUN"}
    (review / "independent-preflight.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"check": "PASS", "source_sha": source, "files": custody["git_source_bindings_verified"],
                      "forced_resources": custody["forced_resources"], "carriers": len(carriers)}))
else:
    assert mode in ("wheel", "sdist")
    assert json.loads((review / "independent-preflight.json").read_text())["check"] == "PASS"
    python = config["installed_pythons"][mode]
    launcher = Path(__file__).with_name("launch_independent_wave.py")
    argv = [python, "-I", str(launcher), str(config_path), mode]
    cwd = scratch / (mode + "-consumer")
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    process = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True)
    record = {"source_sha": source, "source_tree": config["source_tree"], "profile": mode,
              "argv": argv, "cwd": str(cwd), "exit_code": process.returncode,
              "wall_seconds": time.monotonic() - started,
              "peak_child_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
              "environment": {"PYTHONPATH": "absent", "PYTHONDONTWRITEBYTECODE": "1",
                              "configured_external_worker_python": config["worker_python"]},
              "config": binding(config_path), "controller": binding(launcher), "carriers": carriers}
    for name, raw in (("stdout", process.stdout), ("stderr", process.stderr)):
        path = review / (mode + "-native." + name + ".txt")
        assert not path.exists()
        path.write_bytes(raw)
        record[name] = binding(path)
    source_guard()
    assert carrier_guard() == carriers
    record["source_and_carrier_post_guard"] = "PASS"
    (review / (mode + "-native.json")).write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"profile": mode, "exit_code": process.returncode,
                      "wall_seconds": record["wall_seconds"], "stdout": record["stdout"], "stderr": record["stderr"]}))
    raise SystemExit(process.returncode)
