"""
Code verification sandbox for Drafter pass-3 constraints.
"""

from __future__ import annotations

import ast
import builtins
import json
import multiprocessing as mp
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from queue import Empty as QueueEmpty
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common.logger import get_logger
from polisyos.scientist.agent.protocols import DraftResult, ProblemFrame

logger = get_logger(__name__)

_CODE_VERIFIER_IMPORT_ERRORS = (ImportError, ModuleNotFoundError)
_CODE_VERIFIER_RESOURCE_LIMIT_ERRORS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_CODE_VERIFIER_EXECUTION_ERRORS = (
    ArithmeticError,
    AttributeError,
    ImportError,
    LookupError,
    MemoryError,
    NameError,
    RuntimeError,
    SyntaxError,
    TypeError,
    ValueError,
)


class VerificationStatus(str, Enum):
    """Verification status public type."""
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Verification result data model."""
    status: VerificationStatus
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    code: str = ""
    execution_time_ms: float = 0.0
    sandbox_output: str = ""

    def to_findings(self) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []
        for error in self.errors:
            category = "parameter_error"
            lowered = error.lower()
            if "budget" in lowered:
                category = "budget_violation"
            elif "overlap" in lowered or "target" in lowered:
                category = "target_overlap"
            elif "constraint" in lowered:
                category = "constraint_conflict"
            findings.append(
                {
                    "category": category,
                    "severity": "critical",
                    "description": error,
                    "suggested_fix": f"Fix violated assertion: {error}",
                    "affected_intervention": "",
                    "anchor": "verification:code",
                }
            )
        return findings


class SandboxConfig(BaseModel):
    """Sandbox config data model."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    timeout_seconds: float = Field(default=5.0, gt=0.0, le=30.0)
    max_output_chars: int = Field(default=4096, ge=256, le=65536)
    max_code_chars: int = Field(default=8192, ge=256, le=65536)
    max_memory_mb: int = Field(default=256, ge=64, le=4096)
    cpu_seconds_limit: int = Field(default=2, ge=1, le=30)
    use_restrictedpython_if_available: bool = True

    allowed_modules: tuple[str, ...] = (
        "math",
        "decimal",
        "json",
        "operator",
        "functools",
        "itertools",
        "collections",
    )
    allowed_builtins: tuple[str, ...] = (
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "enumerate",
        "float",
        "int",
        "isinstance",
        "len",
        "list",
        "max",
        "min",
        "range",
        "round",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
        "AssertionError",
        "ValueError",
        "TypeError",
    )
    blocked_names: tuple[str, ...] = (
        "open",
        "exec",
        "eval",
        "compile",
        "globals",
        "locals",
        "__import__",
        "os",
        "sys",
        "subprocess",
        "socket",
        "requests",
        "urllib",
        "http",
        "pathlib",
        "ctypes",
        "multiprocessing",
        "threading",
        "breakpoint",
    )

    @classmethod
    def from_env(cls) -> "SandboxConfig":
        kwargs: dict[str, Any] = {}
        raw = os.getenv("POLISYOS_CODE_VERIFICATION_TIMEOUT")
        if raw:
            kwargs["timeout_seconds"] = float(raw)
        return cls(**kwargs)


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value[:200]]
    if isinstance(value, tuple):
        return [_sanitize_value(item) for item in value[:200]]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for idx, (key, item) in enumerate(value.items()):
            if idx >= 200:
                break
            out[str(key)] = _sanitize_value(item)
        return out
    return str(value)


class _LimitedOutputBuffer:
    def __init__(self, max_chars: int) -> None:
        self._max_chars = max_chars
        self._parts: list[str] = []
        self._size = 0

    def write(self, text: str) -> int:
        if not text:
            return 0
        if self._size >= self._max_chars:
            return len(text)
        remaining = self._max_chars - self._size
        piece = text[:remaining]
        if piece:
            self._parts.append(piece)
            self._size += len(piece)
        return len(text)

    def flush(self) -> None:
        return None

    def getvalue(self) -> str:
        return "".join(self._parts)


class _RestrictedPrintCollector:
    """RestrictedPython-compatible print collector backed by the bounded buffer."""

    def __init__(self, limited_print: Any) -> None:
        self._limited_print = limited_print

    def write(self, text: str) -> None:
        self._limited_print(text, end="")

    def __call__(self) -> str:
        return ""


class VerificationCodeExtractor:
    """Extracts verification code from LLM pass-3 response payload."""

    @staticmethod
    def extract_from_llm_response(raw_response: str | None) -> str | None:
        if not raw_response:
            return None
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        code = payload.get("verification_code")
        if not isinstance(code, str):
            return None
        stripped = code.strip()
        return stripped or None


class DraftVariableExtractor:
    """Extracts primitive variables for code verification sandbox."""

    @staticmethod
    def extract(draft: DraftResult, problem_frame: ProblemFrame) -> dict[str, Any]:
        interventions: list[dict[str, Any]] = []
        rates: list[float] = []
        costs: list[float] = []
        targets: list[Any] = []

        for raw in draft.interventions:
            if not isinstance(raw, dict):
                continue
            clean: dict[str, Any] = {}
            for key, value in raw.items():
                clean[str(key)] = _sanitize_value(value)
            interventions.append(clean)

            params = raw.get("params")
            if params is None:
                params = raw.get("parameters")
            if isinstance(params, dict):
                for key, value in params.items():
                    if "rate" in str(key).lower():
                        try:
                            rates.append(float(value))
                        except (TypeError, ValueError):
                            pass

            for key in ("cost", "amount", "budget_cost"):
                if key in raw:
                    try:
                        costs.append(float(raw[key]))
                    except (TypeError, ValueError):
                        pass

            target = raw.get("target")
            if target is None:
                target = raw.get("target_population")
            if target is not None:
                targets.append(_sanitize_value(target))

        constraints = [str(item) for item in problem_frame.constraints[:50]]
        budget = 0.0
        for item in constraints:
            if "budget" not in item.lower():
                continue
            match = re.search(r"(-?\d+(?:\.\d+)?)", item.replace("_", ""))
            if match:
                try:
                    budget = float(match.group(1))
                    break
                except ValueError:
                    continue

        return {
            "interventions": interventions,
            "constraints": constraints,
            "total_budget": budget,
            "intervention_rates": rates,
            "intervention_costs": costs,
            "targets": targets,
            "intervention_count": len(interventions),
        }


class CodeVerificationSandbox:
    """Executes verification snippets in an isolated process."""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self._config = config or SandboxConfig()

    @property
    def config(self) -> SandboxConfig:
        return self._config

    def execute(
        self,
        code: str | None,
        *,
        variables: dict[str, Any] | None = None,
    ) -> VerificationResult:
        if not code or not code.strip():
            return VerificationResult(
                status=VerificationStatus.SKIPPED,
                passed=True,
                code="",
            )
        code = code.strip()
        if len(code) > self._config.max_code_chars:
            return VerificationResult(
                status=VerificationStatus.ERROR,
                passed=False,
                errors=[f"Code exceeds max length ({len(code)} > {self._config.max_code_chars})"],
                code=code[:256],
            )

        security_issues = self._security_scan(code)
        if security_issues:
            return VerificationResult(
                status=VerificationStatus.ERROR,
                passed=False,
                errors=security_issues,
                code=code,
            )

        safe_vars = _sanitize_value(variables or {})
        started = time.perf_counter()
        ctx = _verification_context()
        queue: mp.Queue[dict[str, Any]] = ctx.Queue(maxsize=1)
        process = ctx.Process(
            target=_verification_worker,
            args=(code, safe_vars, self._config.model_dump(mode="python"), queue),
        )
        process.start()
        process.join(timeout=self._config.timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join(timeout=1.0)
            if process.is_alive():
                process.kill()
                process.join(timeout=1.0)
            elapsed = (time.perf_counter() - started) * 1000.0
            return VerificationResult(
                status=VerificationStatus.ERROR,
                passed=False,
                errors=[f"Execution timeout ({self._config.timeout_seconds}s)"],
                code=code,
                execution_time_ms=elapsed,
            )

        elapsed = (time.perf_counter() - started) * 1000.0
        try:
            payload = queue.get(timeout=min(1.0, self._config.timeout_seconds))
        except QueueEmpty:
            return VerificationResult(
                status=VerificationStatus.ERROR,
                passed=False,
                errors=[f"Sandbox process exited without result (exitcode={process.exitcode})"],
                code=code,
                execution_time_ms=elapsed,
            )
        status_raw = str(payload.get("status", VerificationStatus.ERROR.value))
        try:
            status = VerificationStatus(status_raw)
        except ValueError:
            status = VerificationStatus.ERROR
        return VerificationResult(
            status=status,
            passed=bool(payload.get("passed", False)),
            errors=[str(item) for item in payload.get("errors", [])],
            warnings=[str(item) for item in payload.get("warnings", [])],
            code=code,
            execution_time_ms=elapsed,
            sandbox_output=str(payload.get("sandbox_output", "")),
        )

    def _security_scan(self, code: str) -> list[str]:
        errors: list[str] = []
        lowered = code.lower()
        for blocked in self._config.blocked_names:
            token = blocked.lower()
            pattern = rf"(?<![a-z0-9_]){re.escape(token)}(?![a-z0-9_])"
            if re.search(pattern, lowered):
                errors.append(f"Security violation: '{blocked}' is not allowed")
        if "__" in code:
            errors.append("Security violation: dunder access is not allowed")

        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            errors.append(f"SyntaxError: {exc.msg}")
            return errors

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name.split(".", 1)[0]
                    if mod not in self._config.allowed_modules:
                        errors.append(f"Import '{mod}' is not allowed")
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    errors.append("Relative imports are not allowed")
                else:
                    mod = node.module.split(".", 1)[0]
                    if mod not in self._config.allowed_modules:
                        errors.append(f"Import '{mod}' is not allowed")
            elif isinstance(node, ast.Attribute):
                if node.attr.startswith("__"):
                    errors.append("Dunder attributes are not allowed")
        return errors


def _verification_worker(
    code: str,
    variables: Any,
    config_payload: dict[str, Any],
    result_queue: mp.Queue[dict[str, Any]],
) -> None:
    config = SandboxConfig(**config_payload)
    try:
        _apply_resource_limits(config)
    except _CODE_VERIFIER_RESOURCE_LIMIT_ERRORS as exc:
        logger.debug("Verification resource limits degraded: %s", exc)

    allowed_modules = _load_allowed_modules(config.allowed_modules)
    output = _LimitedOutputBuffer(config.max_output_chars)

    def limited_print(*args: Any, sep: str = " ", end: str = "\n") -> None:
        chunks = [str(item) for item in args]
        text = sep.join(chunks) + end
        output.write(text)

    compiler, use_restricted_runtime = _resolve_compiler(config)
    globals_dict = _build_globals(
        config,
        allowed_modules,
        limited_print,
        variables,
        use_restricted_runtime=use_restricted_runtime,
    )

    try:
        compile_obj = compiler(code, "<verification>", "exec")
        exec(compile_obj, globals_dict, None)
        result_queue.put(
            {
                "status": VerificationStatus.PASSED.value,
                "passed": True,
                "errors": [],
                "warnings": [],
                "sandbox_output": output.getvalue(),
            }
        )
        return
    except AssertionError as exc:
        msg = str(exc) if str(exc) else "Assertion failed"
        result_queue.put(
            {
                "status": VerificationStatus.FAILED.value,
                "passed": False,
                "errors": [msg],
                "warnings": [],
                "sandbox_output": output.getvalue(),
            }
        )
        return
    except _CODE_VERIFIER_EXECUTION_ERRORS as exc:
        result_queue.put(
            {
                "status": VerificationStatus.ERROR.value,
                "passed": False,
                "errors": [f"{type(exc).__name__}: {exc}"],
                "warnings": [],
                "sandbox_output": output.getvalue(),
            }
        )
        return


def _load_allowed_modules(modules: tuple[str, ...]) -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    for name in modules:
        try:
            loaded[name] = __import__(name)
        except _CODE_VERIFIER_IMPORT_ERRORS:
            continue
    return loaded


def _resolve_compiler(config: SandboxConfig) -> tuple[Any, bool]:
    if not config.use_restrictedpython_if_available:
        return compile, False
    try:
        from RestrictedPython import compile_restricted  # type: ignore
        from RestrictedPython.Guards import safe_builtins, safer_getattr  # type: ignore
    except _CODE_VERIFIER_IMPORT_ERRORS:
        return compile, False
    del safe_builtins, safer_getattr
    return compile_restricted, True


def _verification_context() -> Any:
    if "fork" in mp.get_all_start_methods():
        return mp.get_context("fork")
    return mp.get_context("spawn")


def _build_allowed_builtins(
    config: SandboxConfig,
    limited_print: Any,
    allowed_modules: dict[str, Any],
) -> dict[str, Any]:
    allowed_builtins: dict[str, Any] = {}
    for name in config.allowed_builtins:
        if hasattr(builtins, name):
            allowed_builtins[name] = getattr(builtins, name)
    allowed_builtins["print"] = limited_print

    def restricted_import(name: str, *args: Any, **kwargs: Any) -> Any:
        root = str(name).split(".", 1)[0]
        if root in allowed_modules:
            return allowed_modules[root]
        raise ImportError(f"Import '{name}' is not allowed")

    allowed_builtins["__import__"] = restricted_import
    return allowed_builtins


def _build_globals(
    config: SandboxConfig,
    allowed_modules: dict[str, Any],
    limited_print: Any,
    variables: Any,
    *,
    use_restricted_runtime: bool = False,
) -> dict[str, Any]:
    allowed_builtins = _build_allowed_builtins(config, limited_print, allowed_modules)
    globals_dict: dict[str, Any] = {
        "__builtins__": allowed_builtins,
    }
    if use_restricted_runtime:
        try:
            from RestrictedPython.Guards import safe_builtins, safer_getattr  # type: ignore
        except _CODE_VERIFIER_IMPORT_ERRORS:
            use_restricted_runtime = False
        else:
            restricted_builtins = dict(safe_builtins)
            restricted_builtins.update(allowed_builtins)
            globals_dict.update(
                {
                    "__builtins__": restricted_builtins,
                    "_getattr_": safer_getattr,
                    "_getitem_": lambda obj, key: obj[key],
                    "_getiter_": iter,
                    "_print_": lambda *_args, **_kwargs: _RestrictedPrintCollector(
                        limited_print
                    ),
                }
            )
    for mod_name, module in allowed_modules.items():
        globals_dict[mod_name] = module
    if isinstance(variables, dict):
        for key, value in variables.items():
            if isinstance(key, str):
                globals_dict[key] = value
    return globals_dict


def _apply_resource_limits(config: SandboxConfig) -> None:
    try:
        import resource

    except _CODE_VERIFIER_IMPORT_ERRORS:
        return
    soft_mem = int(config.max_memory_mb) * 1024 * 1024
    hard_mem = soft_mem
    resource.setrlimit(resource.RLIMIT_AS, (soft_mem, hard_mem))
    cpu = int(config.cpu_seconds_limit)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
