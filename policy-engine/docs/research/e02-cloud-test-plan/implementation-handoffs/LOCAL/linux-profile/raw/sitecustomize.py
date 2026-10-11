import hashlib
import itertools
import json
import os
import subprocess
from pathlib import Path

_root = Path(os.environ["E02_CAPTURE_DIR"])
_root.mkdir(parents=True, exist_ok=True)
_lane = os.environ.get("E02_CAPTURE_LANE", "run")
_original_popen = subprocess.Popen
_sequence = itertools.count()


class _RecordedPopen(_original_popen):
    def __init__(self, *args, **kwargs):
        self._e02_key = f"{_lane}-{os.getpid()}-{next(_sequence):04d}"
        self._e02_command = args[0] if args else kwargs.get("args")
        self._e02_recorded = False
        super().__init__(*args, **kwargs)

    def communicate(self, input=None, timeout=None):
        stdout, stderr = super().communicate(input=input, timeout=timeout)
        if not self._e02_recorded:
            out_bytes = self._as_bytes(stdout)
            err_bytes = self._as_bytes(stderr)
            out_path = _root / f"{self._e02_key}.stdout.bin"
            err_path = _root / f"{self._e02_key}.stderr.bin"
            out_path.write_bytes(out_bytes)
            err_path.write_bytes(err_bytes)
            metadata = {
                "command": self._e02_command,
                "returncode": self.returncode,
                "stdout_bytes": len(out_bytes),
                "stderr_bytes": len(err_bytes),
                "stdout_sha256": hashlib.sha256(out_bytes).hexdigest(),
                "stderr_sha256": hashlib.sha256(err_bytes).hexdigest(),
                "text_mode": bool(getattr(self, "text_mode", False)),
                "encoding": getattr(self, "encoding", None),
                "errors": getattr(self, "errors", None),
            }
            (_root / f"{self._e02_key}.json").write_text(
                json.dumps(metadata, ensure_ascii=True, sort_keys=True, default=repr) + "\n",
                encoding="utf-8",
            )
            self._e02_recorded = True
        return stdout, stderr

    def _as_bytes(self, value):
        if value is None:
            return b""
        if isinstance(value, bytes):
            return value
        return value.encode(
            getattr(self, "encoding", None) or "utf-8",
            errors=getattr(self, "errors", None) or "strict",
        )


subprocess.Popen = _RecordedPopen
