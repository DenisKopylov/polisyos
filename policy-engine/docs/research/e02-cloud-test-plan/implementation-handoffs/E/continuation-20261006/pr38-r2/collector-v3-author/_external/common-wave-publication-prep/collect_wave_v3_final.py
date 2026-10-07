"""Collect source-bound E02 wave custody; never execute tests or delete inputs."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from defusedxml import ElementTree

CAPS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
    "POLISYOS_PYTEST_WORKERS",
)
COUNTS = ("cases", "passed", "failed", "errors", "skipped")


def identity(path: Path) -> dict[str, object]:
    """Hash complete stable bytes without loading large raw into memory."""
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("input changed while hashing: " + str(path))
    return {"bytes": after.st_size, "sha256": digest.hexdigest()}


class EvidenceAdmissionError(RuntimeError):
    """Reject an evidence role/path before copying any payload bytes."""


def reject_symlink_components(path: Path) -> None:
    for component in (path, *path.parents):
        if component.is_symlink():
            raise EvidenceAdmissionError("symlink component is not admitted: " + str(component))


def inside(root: Path, path: Path) -> Path:
    """Admit contained paths without allowing leaf or parent symlink aliases."""
    reject_symlink_components(path.absolute())
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise EvidenceAdmissionError("input escapes wave root: " + str(path))
    return resolved


def public_evidence(root: Path, path: Path, *, expected: Path | None = None) -> Path:
    """Admit public evidence roles; integrity never overrides raw/private exclusion."""
    resolved = inside(root, path)
    relative = resolved.relative_to(root)
    parts = [part.casefold() for part in relative.parts]
    if any(part in {"raw", "private"} or "git-config-private" in part for part in parts):
        raise EvidenceAdmissionError("raw/private evidence cannot be published: " + str(path))
    if resolved.name.casefold().endswith(".raw.json"):
        raise EvidenceAdmissionError("raw evidence cannot be published: " + str(path))
    if expected is not None and Path(os.path.abspath(path)) != Path(os.path.abspath(expected)):
        raise EvidenceAdmissionError(
            "evidence path differs from canonical planned role: " + str(path)
        )
    if resolved.exists() and not resolved.is_file():
        raise EvidenceAdmissionError("public evidence must be a regular file: " + str(path))
    return resolved


def canonical_job_output(wave: Path, job: dict[str, object]) -> Path:
    name = job["name"]
    if not isinstance(name, str) or not name or Path(name).name != name or name in {".", ".."}:
        raise EvidenceAdmissionError("invalid planned check name")
    expected = wave / "checks" / name
    output = inside(wave, Path(job["output"]))
    if Path(os.path.abspath(job["output"])) != expected:
        raise EvidenceAdmissionError("check output differs from canonical planned role")
    if job["junit"]:
        public_evidence(wave, Path(job["junit"]), expected=expected / "pytest.xml")
    return output


def _admit_git_object_arguments(arguments: tuple[str, ...]) -> None:
    """Keep object reads from interpreting record refs as Git options.

    Named/abbreviated refs remain available to retired source-pinned replay
    scripts; live packet admissions separately require full immutable SHAs.
    """
    if not arguments or arguments[0] not in {"show", "rev-parse"}:
        return
    safe_information_flags = {"--show-toplevel", "--git-dir", "--git-common-dir"}
    for value in arguments[1:]:
        if not isinstance(value, str) or not value or "\0" in value:
            raise ValueError("Git object argument must be a nonempty string")
        if value.startswith("-"):
            if arguments[0] == "rev-parse" and value in safe_information_flags:
                continue
            raise ValueError("Git object reference must never be an option")
        if ":" in value:
            _, relative = value.split(":", 1)
            path = Path(relative)
            if (
                not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or path.as_posix() != relative
                or "\0" in relative
            ):
                raise ValueError("Git object path must be repository relative")


def git_bytes(repo: Path, *argv: str) -> bytes:
    _admit_git_object_arguments(argv)
    executable = shutil.which("git")
    if executable is None:
        raise FileNotFoundError("Git unavailable")
    command = [str(Path(executable).resolve()), "-C", str(repo), *argv]
    # Fixed metadata commands and exact root-supplied refs; never shell execution.
    return subprocess.check_output(command)  # noqa: S603


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("expected JSON object: " + str(path))
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")


def junit_cases(path: Path) -> list[dict[str, object]]:
    """Recompute every case; case count never comes from AST or old wave."""
    cases = []
    for case in ElementTree.parse(path, forbid_dtd=True).getroot().iter("testcase"):
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        outcome = (
            "failed"
            if failure is not None
            else "errors"
            if error is not None
            else "skipped"
            if skipped is not None
            else "passed"
        )
        cases.append(
            {
                "name": case.get("name"),
                "classname": case.get("classname"),
                "file": case.get("file"),
                "seconds": case.get("time"),
                "outcome": outcome,
            }
        )
    return cases


def summarize_cases(cases: list[dict[str, object]]) -> dict[str, int]:
    counts = Counter(case["outcome"] for case in cases)
    return {"cases": len(cases), **{key: counts[key] for key in COUNTS[1:]}}


def owner_packet_inventory(
    repo: Path, candidate: str, packets: list[dict[str, object]], wave: Path
) -> list[dict[str, object]]:
    inventory = []
    for packet in packets:
        data = git_bytes(repo, "show", candidate + ":" + packet["source"])
        if hashlib.sha256(data).hexdigest() != packet["sha256"]:
            raise RuntimeError("owner packet Git identity mismatch")
        destination = public_evidence(wave, Path(packet["destination"]))
        if destination.parent != wave / "owner-packets" or destination.suffix != ".py":
            raise EvidenceAdmissionError("owner packet is outside its canonical public role")
        if not destination.exists() or identity(destination) != {
            "bytes": packet["bytes"],
            "sha256": packet["sha256"],
        }:
            raise RuntimeError("materialized owner packet identity mismatch")
        names = [
            node.name
            for node in ast.walk(ast.parse(data))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]
        inventory.append(
            {
                **packet,
                "module_stem": destination.stem,
                "test_functions": names,
                "owner": "A",
                "runtime_case_count": "Recomputed from actual JUnit only",
            }
        )
    return inventory


def raw_static_metadata(path: Path) -> dict[str, object]:
    """Decode the canonical producer's trailing denominator; hash all raw bytes."""
    size = path.stat().st_size
    with path.open("rb") as stream:
        stream.seek(max(0, size - 65536))
        tail = stream.read().decode("utf-8")
    # audit_repository appends base/denominator after its large static graph.
    marker = '\n  "denominator": '
    position = tail.rfind(marker)
    if position < 0:
        raise ValueError("canonical raw denominator unavailable")
    denominator, end = json.JSONDecoder().raw_decode(tail[position + len(marker) :])
    remaining = tail[position + len(marker) + end :].strip()
    if not isinstance(denominator, dict) or remaining != "}":
        raise ValueError("noncanonical raw denominator boundary")
    required = {
        "paths",
        "current_files",
        "base_files",
        "source_files",
        "current_sha256",
        "base_sha256",
    }
    if set(denominator) != required:
        raise ValueError("raw denominator schema mismatch")
    base_marker = '\n  "base": '
    base_position = tail.rfind(base_marker, 0, position)
    if base_position < 0:
        raise ValueError("raw source base unavailable")
    base, _ = json.JSONDecoder().raw_decode(tail[base_position + len(base_marker) :])
    return {
        "base": base,
        "denominator": denominator,
        "scope": (
            "Canonical trailing metadata only, full file hash/size custody; "
            "no full static graph or runtime invocation verification claimed."
        ),
    }


def expected_umbrella_scopes(repo: Path, candidate: str, gate: str) -> list[dict[str, object]]:
    """Read canonical command factories only; never run their commands."""
    product = repo / "policy-engine"
    sources = (
        "tools/devx/workspace/verify.py",
        "tools/devx/workspace/ci_parity.py",
        "tools/devx/workspace/_common.py",
    )
    for relative in sources:
        expected = git_bytes(repo, "show", candidate + ":policy-engine/" + relative)
        if (product / relative).read_bytes() != expected:
            raise RuntimeError("canonical stage source differs from frozen candidate")
    sys.path.insert(0, str(product))
    from tools.devx.workspace import ci_parity, verify
    from tools.devx.workspace._common import CommandSpec

    verify.PYTEST_NUMERICAL_ENV = {}

    def scope(name: str, argv: list[str]) -> dict[str, object]:
        module = verify if name == "verify" else ci_parity
        parsed = module._build_parser().parse_args(argv)
        commands = []
        if not parsed.skip_doctor:
            commands.append(
                CommandSpec(
                    label="doctor",
                    argv=module._doctor_command(parsed.surface),
                    cwd=module.PRODUCT_ROOT,
                )
            )
        if not parsed.frontend_only:
            if name == "verify":
                commands.extend(
                    verify._backend_commands(
                        pytest_workers=verify._resolve_pytest_workers(parsed.pytest_workers),
                        pytest_dist=verify._resolve_pytest_dist(),
                    )
                )
            else:
                commands.extend(
                    ci_parity._backend_commands(
                        skip_runtime_http=parsed.skip_runtime_http, skip_docs=parsed.skip_docs
                    )
                )
        if not parsed.backend_only:
            commands.extend(
                ci_parity._frontend_commands(
                    skip_browser=parsed.skip_browser,
                    include_e2e_smoke=parsed.include_e2e_smoke,
                    include_visual=parsed.include_visual,
                )
            )
        return {"gate": name, "argv": argv, "step_labels": [spec.label for spec in commands]}

    if gate == "workspace-verify":
        return [scope("verify", ["--backend-only"])]
    return [scope("ci-parity", []), scope("verify", ["--backend-only", "--skip-doctor"])]


def _admit_require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


_NO_PATH = object()


def admit_source(sha: object, path: object = _NO_PATH) -> None:
    """Refuse unbound or option-like Git objects before any child process."""
    _admit_require(
        isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha) is not None,
        "source requires an exact commit SHA",
    )
    if path is not _NO_PATH:
        _admit_require(isinstance(path, str) and bool(path), "source path requires a string")
        _admit_require(
            not any(character.isspace() or character == "\0" for character in path),
            "source path contains ambiguous characters",
        )
        relative = Path(path)
        _admit_require(
            not relative.is_absolute()
            and bool(relative.parts)
            and relative.as_posix() == path
            and ".." not in relative.parts,
            "source path must be repository relative",
        )
        _admit_require(not path.startswith("-") and ":" not in path, "source path is ambiguous")


def collect(args: argparse.Namespace) -> dict[str, object]:
    admit_source(args.candidate)
    reject_symlink_components(args.wave_root.absolute())
    wave = args.wave_root.resolve()
    repo = args.repo.resolve()
    publication = args.publication_root
    reject_symlink_components(publication.absolute())
    if publication.resolve().is_relative_to(wave):
        raise EvidenceAdmissionError("publication must not modify the original wave directory")
    if publication.exists() or publication.is_symlink():
        raise RuntimeError("publication output exists; preserve it and select fresh output")
    plan_path = public_evidence(wave, wave / "plan.json", expected=wave / "plan.json")
    plan = read_json(plan_path)
    candidate = args.candidate
    if plan["candidate_sha"] != candidate:
        raise RuntimeError("plan is not the requested exact frozen candidate")
    tree = git_bytes(repo, "rev-parse", candidate + "^{tree}").decode().strip()
    if plan["candidate_tree_sha"] != tree:
        raise RuntimeError("candidate tree identity mismatch")
    if Path(plan["output_root"]).resolve() != wave:
        raise RuntimeError("plan wave output root mismatch")
    jobs = plan["jobs"]
    for job in jobs:
        canonical_job_output(wave, job)
    names = [job["name"] for job in jobs]
    if len(names) != len(set(names)):
        raise RuntimeError("duplicate job name in complete plan")
    started = read_json(inside(wave, wave / "wave-started.json"))
    if started["candidate_sha"] != candidate:
        raise RuntimeError("wave start source mismatch")
    completion = wave / "execution-complete.json"
    importer_stop = wave / "not-started-after-importer.json"
    terminal = (
        completion if completion.exists() else importer_stop if importer_stop.exists() else None
    )
    if terminal is None and not args.capture_incomplete:
        raise RuntimeError("wave is not terminal; no collection before completion")
    terminal_data = None if terminal is None else read_json(inside(wave, terminal))
    if terminal_data is not None and terminal_data["candidate_sha"] != candidate:
        raise RuntimeError("terminal source mismatch")
    freeze_path = getattr(args, "freeze_receipt", None)
    freeze = None
    freeze_identity = None
    if freeze_path is not None:
        freeze_path = public_evidence(freeze_path.parent.resolve(), freeze_path)
        freeze = read_json(freeze_path)
        freeze_identity = identity(freeze_path)
        if (
            freeze["frozen_sha"] != candidate
            or freeze["tree"] != tree
            or Path(freeze["one_wave_output_root"]).resolve() != wave
            or freeze["remote_ls_readback_sha"] != candidate
            or freeze["source_tree_dirty"] is not False
        ):
            raise RuntimeError("source freeze receipt identity mismatch")
        for review in freeze["reviews"]:
            data = git_bytes(repo, "show", candidate + ":" + review["path"])
            if len(data) != review["bytes"] or hashlib.sha256(data).hexdigest() != review["sha256"]:
                raise RuntimeError("frozen review content does not bind candidate Git bytes")
    publication.mkdir(parents=True, exist_ok=False)
    publication = publication.resolve()
    assets = []
    custody = []
    issues = []

    def copy(path: Path, *, required: bool = True) -> bool:
        path = public_evidence(wave, path)
        relative = path.relative_to(wave)
        if not path.exists():
            if required:
                issues.append({"path": str(relative), "reason": "required evidence missing"})
            return False
        observed = identity(path)
        if observed["bytes"] > args.max_moderate_bytes:
            custody.append({"path": str(relative), **observed, "publication": "raw_only"})
            issues.append(
                {"path": str(relative), "reason": "complete output exceeds moderate limit"}
            )
            return False
        target = publication / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with path.open("rb") as original, target.open("xb") as copied:
            shutil.copyfileobj(original, copied)
        if identity(target) != observed or identity(path) != observed:
            raise RuntimeError("copy byte identity drift: " + str(relative))
        assets.append({"path": str(relative), **observed})
        return True

    copy(plan_path)
    copy(wave / "wave-started.json")
    if terminal is not None:
        copy(terminal)
    if freeze_path is not None:
        target = publication / "source-freeze-receipt.json"
        with freeze_path.open("rb") as original, target.open("xb") as copied:
            shutil.copyfileobj(original, copied)
        if identity(target) != freeze_identity or identity(freeze_path) != freeze_identity:
            raise RuntimeError("source freeze receipt changed during collection")
        assets.append({"path": target.name, **freeze_identity})
    packets = owner_packet_inventory(repo, candidate, plan["owner_packet_extra_inputs"], wave)
    for packet in packets:
        copy(Path(packet["destination"]))
    rows = []
    all_numeric_cases = []
    source_frames = []
    config_hashes = []
    expected_inputs = {}
    for name in (
        "AGENTS.md",
        "policy-engine/CONTRIBUTING.md",
        "policy-engine/pyproject.toml",
        "policy-engine/uv.lock",
    ):
        data = git_bytes(repo, "show", candidate + ":" + name)
        expected_inputs[name] = {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob": git_bytes(repo, "rev-parse", candidate + ":" + name).decode().strip(),
        }
    for job in jobs:
        output = canonical_job_output(wave, job)
        path = public_evidence(
            wave, output / (job["name"] + ".json"), expected=output / (job["name"] + ".json")
        )
        row = {
            "name": job["name"],
            "kind": job["kind"],
            "command": job["argv"],
            "cwd": job["cwd"],
            "outcome": "UNRUN",
            "case_counts": None,
        }
        if not path.exists():
            row["absence_reason"] = (
                "actual importer fail-fast"
                if terminal == importer_stop
                else "missing runner receipt; outcome not established"
            )
            if terminal != importer_stop:
                issues.append({"job": job["name"], "reason": row["absence_reason"]})
            rows.append(row)
            continue
        receipt = read_json(path)
        copy(path)
        row["outcome"] = receipt["outcome"]
        row["exit_code"] = receipt["exit_code"]
        row["wall_seconds"] = receipt["wall_seconds"]
        row["max_rss_kib"] = receipt["max_rss_kib"]
        row["user_cpu_seconds"] = receipt["user_cpu_seconds"]
        row["system_cpu_seconds"] = receipt["system_cpu_seconds"]
        row["rss_scope"] = receipt["rss_scope"]
        predicates = {
            "candidate": receipt["candidate_sha"] == candidate,
            "tree": receipt["candidate_tree_sha"] == tree,
            "ending_head": receipt["head_at_end"] == candidate,
            "command": receipt["command"] == job["argv"],
            "cwd": receipt["cwd"] == job["cwd"],
            "source_frames_equal": receipt["source_identity_before"]
            == receipt["source_identity_after"],
            "source_immutable": receipt["source_immutable"] is True,
            "config_stable": receipt["git_input_config"]["stable"] is True,
            "config_hashes_equal": receipt["git_input_config"]["sha256"]
            == receipt["git_input_config"]["after_sha256"],
            "declared_inputs_bound_to_candidate_git": receipt["input_files"] == expected_inputs,
            "tracked_path_count": receipt["source_identity_before"]["tracked_paths"]
            == plan["tracked_all_path_count"],
            "started_after_wave_start": receipt["started_unix"] >= started["started_unix"],
        }
        if not all(predicates.values()):
            issues.append(
                {"job": job["name"], "reason": "binding/input drift", "predicates": predicates}
            )
        row["binding_predicates"] = predicates
        if receipt["outcome"] not in {"PASS", "FAIL", "ERROR", "SKIP", "UNRUN"}:
            issues.append({"job": job["name"], "reason": "unknown check outcome"})
        if receipt["outcome"] == "PASS" and receipt["exit_code"] != 0:
            issues.append({"job": job["name"], "reason": "PASS conflicts with command failure"})
        source_frames.append(receipt["source_identity_before"])
        config_hashes.append(receipt["git_input_config"]["sha256"])
        variables = receipt["environment"]["selected_variables"]
        caps = {name: variables.get(name) for name in CAPS if variables.get(name) is not None}
        if caps:
            issues.append(
                {"job": job["name"], "reason": "numerical quota inherited", "variables": caps}
            )
        row["environment"] = receipt["environment"]
        row["backend_observer"] = receipt["actual_numeric_backend"]
        row["backend_observer_scope"] = (
            "Post-command observer process; test-child changed JAX config is not inferred."
        )
        stdout = None
        try:
            stdout = public_evidence(
                wave,
                Path(receipt["stdout_path"]),
                expected=output / (job["name"] + ".stdout.txt"),
            )
        except EvidenceAdmissionError as error:
            issues.append({"job": job["name"], "reason": str(error), "role": "stdout"})
        if stdout is not None:
            if not stdout.exists() or identity(stdout) != {
                "bytes": receipt["stdout_bytes"],
                "sha256": receipt["stdout_sha256"],
            }:
                issues.append({"job": job["name"], "reason": "stdout custody mismatch"})
            else:
                copy(stdout)
        private = inside(wave, Path(receipt["git_input_config"]["private_complete_path"]))
        if private != wave / "raw" / (job["name"] + ".git-config-private.nul"):
            raise EvidenceAdmissionError("private config custody differs from canonical raw role")
        if not private.exists() or identity(private) != {
            "bytes": receipt["git_input_config"]["bytes"],
            "sha256": receipt["git_input_config"]["sha256"],
        }:
            issues.append({"job": job["name"], "reason": "private Git config custody mismatch"})
        else:
            custody.append(
                {
                    "path": str(private.relative_to(wave)),
                    **identity(private),
                    "publication": "private_excluded_hash_size_only",
                }
            )
        if job["junit"]:
            xml = inside(wave, Path(job["junit"]))
            if xml.exists():
                copy(xml)
                cases = junit_cases(xml)
                for case in cases:
                    case["job_name"] = job["name"]
                counts = summarize_cases(cases)
                row["case_counts"] = counts
                row["cases"] = cases
                if counts != receipt["counts"]:
                    issues.append({"job": job["name"], "reason": "JUnit receipt counts mismatch"})
                if receipt["outcome"] == "PASS" and (counts["failed"] or counts["errors"]):
                    issues.append(
                        {
                            "job": job["name"],
                            "reason": "PASS conflicts with actual failed/error cases",
                        }
                    )
                if receipt["outcome"] == "SKIP" and (
                    not counts["cases"] or counts["skipped"] != counts["cases"]
                ):
                    issues.append(
                        {"job": job["name"], "reason": "SKIP conflicts with actual case outcomes"}
                    )
                if job["kind"] == "numerical":
                    all_numeric_cases.extend(cases)
            elif receipt["outcome"] != "UNRUN":
                issues.append(
                    {"job": job["name"], "reason": "JUnit missing on attempted numeric job"}
                )
        if job["name"] in {"workspace-verify", "ci-parity"}:
            stages_path = output / "internal-stages.json"
            if copy(stages_path):
                stages = read_json(stages_path)
                row["umbrella_stages"] = stages
                expected_scopes = expected_umbrella_scopes(repo, candidate, job["name"])
                row["canonical_stage_inventory"] = expected_scopes
                for scope in stages["scopes"]:
                    expected = next(
                        (
                            item
                            for item in expected_scopes
                            if item["gate"] == scope["gate"] and item["argv"] == scope["argv"]
                        ),
                        None,
                    )
                    if (
                        expected is None
                        or [step["label"] for step in scope["steps"]] != expected["step_labels"]
                    ):
                        issues.append(
                            {
                                "job": job["name"],
                                "reason": "canonical umbrella stage denominator mismatch",
                            }
                        )
                if receipt["outcome"] == "PASS" and len(stages["scopes"]) != len(expected_scopes):
                    issues.append(
                        {"job": job["name"], "reason": "PASS omits required umbrella scope"}
                    )
                flat = [step for scope in stages["scopes"] for step in scope["steps"]]
                if receipt["outcome"] == "PASS" and (
                    not flat or any(step["outcome"] != "PASS" for step in flat)
                ):
                    issues.append(
                        {
                            "job": job["name"],
                            "reason": "umbrella PASS conflicts with incomplete stages",
                        }
                    )
                row["umbrella_stage_outcomes"] = dict(Counter(step["outcome"] for step in flat))
        rows.append(row)
    numeric = [row for row in rows if row["kind"] == "numerical"]
    non_numeric = [row for row in rows if row["kind"] != "numerical"]
    if terminal == completion:
        for kind, field in (("numerical", "numerical_codes"), ("gate", "gate_codes")):
            selected = [row for row in rows if row["kind"] == kind]
            actual_codes = [
                row.get("exit_code") if all(row.get("binding_predicates", {}).values()) else 1
                for row in selected
            ]
            if terminal_data[field] != actual_codes:
                issues.append(
                    {"reason": "completion disagrees with actual check receipts", "kind": kind}
                )
        importer = next(row for row in rows if row["kind"] == "importer")
        if importer["outcome"] != "PASS":
            issues.append({"reason": "completion exists although importer did not PASS"})
    source_consistent = not source_frames or all(
        frame == source_frames[0] for frame in source_frames
    )
    config_consistent = not config_hashes or len(set(config_hashes)) == 1
    if not source_consistent or not config_consistent:
        issues.append({"reason": "input/config identity differs across wave jobs"})
    packet_rows = []
    packet_case_ids = set()
    unattributed_packet_case_ids = set()
    function_origins = {}
    source_paths = {path for group in plan["groups"].values() for path in group}
    source_paths.update(packet["source"] for packet in packets)
    for source in sorted(source_paths):
        data = git_bytes(repo, "show", candidate + ":" + source)
        for node in ast.walk(ast.parse(data)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test_"
            ):
                function_origins.setdefault(node.name, []).append(source)
    for packet in packets:
        packet_jobs = {job["name"] for job in jobs if packet["destination"] in job["argv"]}
        cases = []
        for case in all_numeric_cases:
            name = (case["name"] or "").split("[", 1)[0]
            if name not in packet["test_functions"] or case["job_name"] not in packet_jobs:
                continue
            classname = case["classname"] or ""
            destination = Path(packet["destination"])
            admitted_modules = {
                packet["module_stem"],
                destination.relative_to(wave).with_suffix("").as_posix().replace("/", "."),
            }
            file_label = case["file"]
            file_matches = not file_label
            if file_label:
                packet_job = next(job for job in jobs if job["name"] == case["job_name"])
                labeled = Path(file_label)
                if not labeled.is_absolute():
                    labeled = Path(packet_job["cwd"]) / labeled
                try:
                    labeled = public_evidence(wave, labeled, expected=destination)
                    file_matches = labeled == destination
                except EvidenceAdmissionError:
                    file_matches = False
            named_module = classname in admitted_modules
            anonymous_unique = not classname and function_origins[name] == [packet["source"]]
            if file_matches and (named_module or anonymous_unique):
                cases.append(case)
            else:
                unattributed_packet_case_ids.add(id(case))
                issues.append(
                    {
                        "source": packet["source"],
                        "case": case["name"],
                        "reason": "owner packet JUnit module/file identity not admitted",
                        "classname": classname,
                        "file": file_label,
                    }
                )
        packet_rows.append(
            {
                "source": packet["source"],
                "sha256": packet["sha256"],
                "owner": "A",
                "matching_basis": {
                    "exact_destination_in_source_bound_job_argv": sorted(packet_jobs),
                    "module_policy": "Exact declared module labels; no substring matching.",
                    "file_policy": "Absent or exact canonical owner-packet destination.",
                    "anonymous_classname_policy": (
                        "Require exact test-function uniqueness across all planned candidate "
                        "source inputs and matching job; refuse ambiguous identity."
                    ),
                    "function_origins": {
                        name: function_origins[name] for name in packet["test_functions"]
                    },
                },
                "counts": summarize_cases(cases),
                "cases": cases,
            }
        )
        packet_case_ids.update(id(case) for case in cases)
        if not cases and terminal != importer_stop:
            issues.append(
                {
                    "reason": "owner packet has no matching actual JUnit cases",
                    "source": packet["source"],
                }
            )
    static_job = next((job for job in jobs if job["name"] == "static-invocation"), None)
    static = None
    if static_job is not None:
        index = static_job["argv"].index("--receipt")
        raw = inside(wave, Path(static_job["argv"][index + 1]))
        if raw != wave / "raw" / "production-invocation.raw.json":
            raise EvidenceAdmissionError("static proxy custody differs from canonical raw role")
        if raw.exists():
            observed = identity(raw)
            custody.append(
                {
                    "path": str(raw.relative_to(wave)),
                    **observed,
                    "publication": "large_raw_excluded_no_repeated_dump",
                }
            )
            static = {
                "raw": str(raw.relative_to(wave)),
                **observed,
                "command": static_job["argv"],
                "candidate_sha": candidate,
                **raw_static_metadata(raw),
                "P41": "not_established; no inherited-red attribution",
            }
    cleanup = []
    for job in jobs:
        for key in ("TMPDIR", "RUFF_CACHE_DIR"):
            if key in job["environment"]:
                cleanup.append({"path": job["environment"][key], "kind": key})
        if job["kind"] == "numerical":
            index = job["argv"].index("--basetemp")
            cleanup.append({"path": job["argv"][index + 1], "kind": "numeric_basetemp"})
            for arg in job["argv"]:
                if arg.startswith("cache_dir="):
                    cleanup.append({"path": arg.removeprefix("cache_dir="), "kind": "pytest_cache"})
                elif arg.startswith("--benchmark-storage="):
                    cleanup.append(
                        {
                            "path": urlparse(arg.removeprefix("--benchmark-storage=")).path,
                            "kind": "benchmark_storage",
                        }
                    )
    cleanup.extend(
        {"path": str(wave / "umbrella-temp" / name), "kind": "umbrella_temporary"}
        for name in ("workspace-verify", "ci-parity")
    )
    control_fixture = plan.get("collector_control_only") is True
    collection_state = (
        "COMPLETE_BOUND"
        if terminal is not None and not issues
        else "LIMITED_INCOMPLETE_OR_INCONSISTENT"
    )
    if control_fixture:
        collection_state = "CONTROL_" + collection_state
    result = {
        "schema": "policyos.e02.wave_publication_custody.v1",
        "candidate_sha": candidate,
        "candidate_tree_sha": tree,
        "wave_root": str(wave),
        "publication_root": str(publication),
        "terminal": None if terminal is None else str(terminal.relative_to(wave)),
        "started": started,
        "completion": terminal_data,
        "source_freeze": freeze,
        "collection_state": collection_state,
        "publication_evidence_scope": (
            "Synthetic collector protocol control only; no numerical/backend evidence"
            if control_fixture
            else "Actual source-bound wave custody"
        ),
        "expected_job_count_from_complete_plan": len(jobs),
        "job_receipt_count": sum("exit_code" in row for row in rows),
        "native_file_count": plan["native_test_path_count"],
        "all_test_file_input_count": plan["test_input_path_count_including_owner_packets"],
        "source_runtime_input_count": plan["source_runtime_input_path_count"],
        "tracked_input_count": plan["tracked_all_path_count"],
        "changed_python_full_lint_denominator": len(plan["changed_python_lint_paths"]),
        "numeric_counts": summarize_cases(all_numeric_cases),
        "native_numeric_counts_excluding_A_packets": summarize_cases(
            [
                case
                for case in all_numeric_cases
                if id(case) not in packet_case_ids | unattributed_packet_case_ids
            ]
        ),
        "unattributed_owner_packet_counts": summarize_cases(
            [case for case in all_numeric_cases if id(case) in unattributed_packet_case_ids]
        ),
        "unattributed_owner_packet_cases": [
            case for case in all_numeric_cases if id(case) in unattributed_packet_case_ids
        ],
        "native_numeric_attribution_complete": not unattributed_packet_case_ids,
        "native_numeric_count_scope": (
            "Includes the explicit G ControlPlaneStore companion. Contrad"
            "ictory owner-packet identities stay unattributed and are exc"
            "luded from both native and A counts."
        ),
        "numeric_outcome_counts": dict(Counter(row["outcome"] for row in numeric)),
        "non_numeric_outcome_counts": dict(Counter(row["outcome"] for row in non_numeric)),
        "foreign_owner_A_packet_cases": packet_rows,
        "source_frames_consistent_across_jobs": source_consistent,
        "effective_git_config_consistent_across_jobs": config_consistent,
        "post_command_backend_observer_scope": "No inference of unmeasured test-child JAX state.",
        "jobs": rows,
        "static_proxy": static,
        "excluded_raw_custody": custody,
        "issues": issues,
        "numeric_results_are_new_candidate_only": not control_fixture,
        "doctor_is_full_ci": False,
        "finding_closure": False,
        "code_acceptance_and_original_criterion_decisions": (
            "Separate; ledger statuses not reclassified by check counts."
        ),
        "cleanup_policy": (
            "Only candidate list; no deletion or Trash action. Preserve u"
            "nique deciding bytes/code/docs. Check no active users before"
            " repeatables move to native Trash; without Trash keep exact "
            "candidates."
        ),
        "cleanup_candidates": cleanup,
        "raw_local_input_limitation": (
            "Raw graph/private config remain outside Git; exact command/s"
            "ource/hash/size and complete moderate stdout are published. "
            "Do not promote the bounded static proxy to runtime proof."
        ),
    }
    write_json(publication / "publication-receipt.json", result)
    write_json(publication / "raw-custody.json", custody)
    write_json(publication / "cleanup-candidates.json", cleanup)
    generated = []
    for path in sorted(publication.rglob("*")):
        if path.is_file():
            generated.append({"path": str(path.relative_to(publication)), **identity(path)})
    write_json(
        publication / "copy-index.json",
        {
            "files": generated,
            "file_count": len(generated),
            "total_bytes": sum(row["bytes"] for row in generated),
            "self_index_excluded": True,
            "wave_source_assets": assets,
        },
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--wave-root", type=Path, required=True)
    parser.add_argument("--publication-root", type=Path, required=True)
    parser.add_argument("--freeze-receipt", type=Path)
    parser.add_argument("--max-moderate-bytes", type=int, default=8 * 1024 * 1024)
    parser.add_argument("--capture-incomplete", action="store_true")
    args = parser.parse_args()
    result = collect(args)
    sys.stdout.write(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "candidate_sha",
                    "collection_state",
                    "expected_job_count_from_complete_plan",
                    "job_receipt_count",
                    "numeric_counts",
                    "numeric_outcome_counts",
                    "non_numeric_outcome_counts",
                )
            }
        )
        + "\n"
    )
    return 0 if result["collection_state"] == "COMPLETE_BOUND" else 1


if __name__ == "__main__":
    raise SystemExit(main())
