"""Record the complete finite affected consumer command and OS-reported wait4 usage."""
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, UTC
from pathlib import Path

root = Path.cwd()
raw = root / "_build/e02-B-current-adapters/raw"
raw.mkdir(parents=True, exist_ok=True)
paths = [
"tests/unit/scientist/orchestration/llm/test_prompt_cache.py",
"tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py",
"tests/unit/scientist/orchestration/llm/test_budget_enforcer.py",
"tests/unit/scientist/orchestration/llm/test_cost_metrics.py",
"tests/unit/scientist/orchestration/llm/test_factory.py",
"tests/unit/scientist/orchestration/llm/test_prompt_sanitization.py",
"tests/unit/core/test_llm_core.py",
"tests/unit/remediation/test_llm_01.py",
]
argv = [sys.executable, "tools/quality/testing/run_timed_suite.py", "--lane", "pytest:e02-current-adapters-final126", "--capture-pytest-workload", "--receipt-output", "_build/e02-B-current-adapters/raw/native-final126-receipt.json", "--", sys.executable, "-m", "pytest", *paths, "-o", "addopts=", "-q", "--tb=short", "--junitxml=_build/e02-B-current-adapters/raw/native-final126.xml"]
head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
started = datetime.now(UTC).isoformat()
start = time.monotonic()
pid = os.fork()
if pid == 0:
    output = os.open(raw / "native-final126.log", os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o644)
    os.dup2(output, 1)
    os.dup2(output, 2)
    os.close(output)
    os.execv(sys.executable, argv)
_, status, usage = os.wait4(pid, 0)
end_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
receipt = {"schema":"e02.actual.affected-consumer.v1", "target_sha":head, "target_sha_after":end_head, "cwd":str(root), "argv":argv, "started_at":started, "wall_s":time.monotonic()-start, "exit_code":os.waitstatus_to_exitcode(status), "wait4_ru_maxrss_kib":usage.ru_maxrss, "rss_scope":"OS-reported maxrss for timed wrapper and its reaped descendants; not summed simultaneous cohort RSS", "driver_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "python":sys.version, "executable":sys.executable, "PYTHONPATH":os.environ.get("PYTHONPATH"), "TIKTOKEN_CACHE_DIR":os.environ.get("TIKTOKEN_CACHE_DIR"), "outputs":{}}
for name in ("native-final126.log","native-final126.xml","native-final126-receipt.json"):
    p=raw/name
    if p.exists(): receipt["outputs"][name]={"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"bytes":p.stat().st_size}
(raw/"native-final126-wrapper.json").write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps(receipt,indent=2),flush=True)
assert head == end_head, "source checkpoint moved during consumer replay"
raise SystemExit(receipt["exit_code"])
