"""Unified command entry point for repository tooling."""

from __future__ import annotations

import difflib
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import click

from tools._lib.fs import atomic_write_text
from tools._lib.output import OUTPUT_FORMATS, OutputFormat, ToolMessage, ToolResult, format_tool_result
from tools._lib.preflight import PreflightStatus, run_preflight
from tools._lib.runner import ToolExecutionError, ToolSpec, ToolStatus, invoke_tool_main
from tools._lib.timing import (
    append_timing_record,
    make_timing_record,
    read_timing_records,
    summarize_timing_records,
    timed_tool_run,
    timing_log_from_env,
)
from tools.registry import (
    categories,
    categories_for_zone,
    render_graph,
    render_reference_docs,
    specs_for_category,
    zones,
)

EX_CONFIG = 78


def _write_result(result: ToolResult, output_format: OutputFormat, *, stderr: bool = False) -> None:
    stream = sys.stderr if stderr else sys.stdout
    stream.write(format_tool_result(result, output_format=output_format))


def _preflight_result(spec: ToolSpec) -> ToolResult | None:
    preflight = run_preflight(spec)
    if preflight.status == PreflightStatus.OK:
        return None
    messages = tuple(
        ToolMessage(level=issue.status.value, message=issue.message)
        for issue in preflight.issues
    )
    return ToolResult(
        tool=spec.qualified_name,
        status=preflight.status.value,
        summary=f"preflight did not pass for {spec.qualified_name}",
        exit_code=EX_CONFIG,
        messages=messages,
        data={
            "required_extras": spec.required_extras,
            "required_imports": spec.required_imports,
            "external_dependencies": spec.external_dependencies,
            "replacement": spec.replacement,
        },
    )


def _append_timing_record(
    spec: ToolSpec,
    *,
    output_format: OutputFormat,
    timing_log: Path | None,
    state: dict[str, object],
    exit_code: int,
) -> None:
    timing_path = timing_log or timing_log_from_env()
    if timing_path is None:
        return
    record = make_timing_record(spec, state, exit_code=exit_code, output_format=output_format)
    append_timing_record(timing_path, record)


def _summary_payload(limit: int, timing_log: Path) -> dict[str, object]:
    records = read_timing_records(timing_log)
    summaries = summarize_timing_records(records)
    top_summaries = sorted(
        summaries,
        key=lambda summary: (-summary.average_duration_ms, summary.tool),
    )[:limit]
    return {
        "timing_log": str(timing_log),
        "record_count": len(records),
        "tool_count": len(summaries),
        "summaries": [
            {
                "tool": summary.tool,
                "category": summary.category,
                "runs": summary.runs,
                "failures": summary.failures,
                "skipped": summary.skipped,
                "latest_status": summary.latest_status,
                "latest_duration_ms": summary.latest_duration_ms,
                "average_duration_ms": summary.average_duration_ms,
                "p95_duration_ms": summary.p95_duration_ms,
                "budget_ms": summary.budget_ms,
                "over_budget_runs": summary.over_budget_runs,
            }
            for summary in top_summaries
        ],
    }


def _render_timing_text(payload: dict[str, object]) -> str:
    lines = [
        f"Timing log: {payload['timing_log']}",
        f"Recorded runs: {payload['record_count']} across {payload['tool_count']} tools",
        "",
        "Slowest tools by average duration:",
    ]
    summaries = payload["summaries"]
    assert isinstance(summaries, list)
    if not summaries:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    for item in summaries:
        assert isinstance(item, dict)
        budget = item.get("budget_ms")
        budget_text = ""
        if budget is not None:
            over_budget_runs = int(item.get("over_budget_runs") or 0)
            budget_text = f", budget={float(budget):.1f}ms, over_budget={over_budget_runs}"
        lines.append(
            "- "
            f"{item['tool']}: avg={float(item['average_duration_ms']):.1f}ms, "
            f"p95={float(item['p95_duration_ms']):.1f}ms, "
            f"latest={float(item['latest_duration_ms']):.1f}ms, "
            f"runs={int(item['runs'])}, failures={int(item['failures'])}, "
            f"skipped={int(item['skipped'])}, status={item['latest_status']}"
            f"{budget_text}"
        )
    return "\n".join(lines) + "\n"


def _render_timing_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Tool Timing Summary",
        "",
        f"- Timing log: `{payload['timing_log']}`",
        f"- Recorded runs: {payload['record_count']}",
        f"- Distinct tools: {payload['tool_count']}",
        "",
        "| Tool | Avg (ms) | P95 (ms) | Latest (ms) | Failures | Skipped | Budget (ms) | Over budget |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    summaries = payload["summaries"]
    assert isinstance(summaries, list)
    for item in summaries:
        assert isinstance(item, dict)
        budget = item.get("budget_ms")
        lines.append(
            f"| `{item['tool']}` | {float(item['average_duration_ms']):.1f} | "
            f"{float(item['p95_duration_ms']):.1f} | {float(item['latest_duration_ms']):.1f} | "
            f"{int(item['failures'])} | {int(item['skipped'])} | "
            f"{('-' if budget is None else f'{float(budget):.1f}')} | {int(item['over_budget_runs'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def _run_registered_tool(
    spec: ToolSpec,
    args: Sequence[str],
    *,
    output_format: OutputFormat,
    skip_preflight: bool,
    allow_degraded: bool,
    allow_deprecated: bool,
    timing_log: Path | None,
) -> int:
    timing_path = timing_log or timing_log_from_env()
    wants_help = any(arg in {"--help", "-h"} for arg in args)
    preflight_status = PreflightStatus.OK.value
    if not skip_preflight and not wants_help:
        result = _preflight_result(spec)
        if result is not None:
            preflight_status = result.status
            blocked_by_lifecycle = spec.status in {ToolStatus.DEPRECATED, ToolStatus.QUARANTINED}
            allowed_lifecycle = allow_deprecated and blocked_by_lifecycle
            allowed_degraded = allow_degraded and result.status == PreflightStatus.DEGRADED.value
            if not (allowed_lifecycle or allowed_degraded):
                _write_result(result, output_format, stderr=True)
                _append_timing_record(
                    spec,
                    output_format=output_format,
                    timing_log=timing_path,
                    state={
                        "tool": spec.qualified_name,
                        "category": spec.category,
                        "status": "skipped",
                        "preflight_status": result.status,
                        "started_at": datetime.now(UTC).isoformat(),
                        "duration_ms": 0.0,
                    },
                    exit_code=result.exit_code,
                )
                return result.exit_code
            _write_result(result, output_format, stderr=True)

    with timed_tool_run(spec) as timing_state:
        timing_state["preflight_status"] = preflight_status
        try:
            exit_code = invoke_tool_main(spec, args)
        except ToolExecutionError as exc:
            timing_state["status"] = "failed"
            result = ToolResult.failed(spec.qualified_name, str(exc), exit_code=1)
            _write_result(result, output_format, stderr=True)
            exit_code = 1
        except Exception as exc:  # pragma: no cover - protects CLI boundary around legacy tools.
            timing_state["status"] = "failed"
            result = ToolResult.failed(
                spec.qualified_name,
                f"unhandled tool failure: {type(exc).__name__}: {exc}",
                exit_code=1,
            )
            _write_result(result, output_format, stderr=True)
            exit_code = 1
        else:
            timing_state["status"] = "ok" if exit_code == 0 else "failed"
        finally:
            timing_state["exit_code"] = exit_code

    _append_timing_record(
        spec,
        output_format=output_format,
        timing_log=timing_path,
        state=timing_state,
        exit_code=exit_code,
    )
    return exit_code


def _make_tool_command(spec: ToolSpec) -> click.Command:
    @click.command(
        name=spec.name,
        help=spec.summary,
        add_help_option=False,
        context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
    )
    @click.option(
        "--output-format",
        type=click.Choice(list(OUTPUT_FORMATS)),
        default="text",
        show_default=True,
        help="Format for unified CLI boundary messages.",
    )
    @click.option("--skip-preflight", is_flag=True, help="Skip dependency and lifecycle preflight checks.")
    @click.option("--allow-degraded", is_flag=True, help="Run a tool even when preflight reports degraded mode.")
    @click.option("--allow-deprecated", is_flag=True, help="Run deprecated or quarantined legacy tools.")
    @click.option(
        "--timing-log",
        type=click.Path(path_type=Path, dir_okay=False, writable=True),
        default=None,
        help="Append a JSONL timing record to this path.",
    )
    @click.argument("args", nargs=-1, type=click.UNPROCESSED)
    def _command(
        output_format: OutputFormat,
        skip_preflight: bool,
        allow_degraded: bool,
        allow_deprecated: bool,
        timing_log: Path | None,
        args: tuple[str, ...],
    ) -> int:
        return _run_registered_tool(
            spec,
            args,
            output_format=output_format,
            skip_preflight=skip_preflight,
            allow_degraded=allow_degraded,
            allow_deprecated=allow_deprecated,
            timing_log=timing_log,
        )

    return _command


def _make_category_group(category: str) -> click.Group:
    group = click.Group(name=category, help=f"{category} tooling commands")
    for spec in specs_for_category(category):
        group.add_command(_make_tool_command(spec))
    return group


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """Run policy-engine repository tools through one discoverable interface."""


@cli.command("list")
@click.option(
    "--output-format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
@click.option(
    "--by-zone/--by-category",
    default=True,
    show_default=True,
    help="Render grouped by zone first or by category first.",
)
def list_commands(output_format: str, by_zone: bool) -> None:
    """List registered tools and lifecycle metadata."""

    specs = [spec for category in categories() for spec in specs_for_category(category)]
    if output_format == "json":
        import json

        payload = [
            {
                "name": spec.name,
                "zone": spec.zone,
                "category": spec.category,
                "qualified_name": spec.qualified_name,
                "module": spec.module,
                "callable": spec.callable_name,
                "status": spec.status.value,
                "summary": spec.summary,
                "dependencies": spec.dependencies,
                "replacement": spec.replacement,
                "aliases": spec.aliases,
            }
            for spec in specs
        ]
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    if by_zone:
        for zone in zones():
            click.echo(f"{zone}:")
            for category in categories_for_zone(zone):
                click.echo(f"  {category}:")
                for spec in specs_for_category(category):
                    marker = "" if spec.status == ToolStatus.ACTIVE else f" [{spec.status.value}]"
                    click.echo(f"    {spec.name}{marker} - {spec.summary}")
        return

    for category in categories():
        click.echo(f"{category}:")
        for spec in specs_for_category(category):
            marker = "" if spec.status == ToolStatus.ACTIVE else f" [{spec.status.value}]"
            click.echo(f"  {spec.name}{marker} - {spec.summary}")


@cli.command("graph")
@click.option(
    "--format",
    "graph_format",
    type=click.Choice(["mermaid", "dot", "json"]),
    default="mermaid",
    show_default=True,
)
def graph_command(graph_format: str) -> None:
    """Render the declared tool dependency graph."""

    click.echo(render_graph(graph_format), nl=False)


@cli.command("report-timing")
@click.option(
    "--timing-log",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Timing JSONL path. Defaults to the standard local telemetry log.",
)
@click.option(
    "--output-format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    default=10,
    show_default=True,
    help="Number of slowest tools to include.",
)
@click.option(
    "--summary-markdown",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Optional markdown summary output path for CI job summaries/artifacts.",
)
def report_timing_command(
    timing_log: Path | None,
    output_format: str,
    limit: int,
    summary_markdown: Path | None,
) -> None:
    """Summarize recent tool timing records and budget overruns."""

    target = timing_log or timing_log_from_env()
    if target is None or not target.exists():
        raise click.ClickException(f"Timing log not found: {target}")

    payload = _summary_payload(limit, target)
    if summary_markdown is not None:
        atomic_write_text(summary_markdown, _render_timing_markdown(payload))
        click.echo(f"Wrote {summary_markdown}", err=True)

    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    click.echo(_render_timing_text(payload), nl=False)


@cli.command("docs")
@click.option(
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Optional markdown output path.",
)
@click.option(
    "--check",
    is_flag=True,
    help="Fail if the generated markdown differs from the file passed via --output.",
)
def docs_command(output: Path | None, check: bool) -> None:
    """Generate markdown reference documentation from registry metadata."""

    docs = render_reference_docs()
    if check:
        if output is None:
            raise click.ClickException("--check requires --output so drift can be compared.")
        if not output.exists():
            raise click.ClickException(f"Generated docs target is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != docs:
            diff = "\n".join(
                difflib.unified_diff(
                    current.splitlines(),
                    docs.splitlines(),
                    fromfile=f"{output} (current)",
                    tofile=f"{output} (generated)",
                    lineterm="",
                )
            )
            raise click.ClickException(
                "Generated docs drift detected for "
                f"{output}. Re-run `uv run polisyos-tools docs --output {output}`.\n{diff}"
            )
        click.echo(f"Generated docs are current: {output}")
        return
    if output is None:
        click.echo(docs, nl=False)
        return
    atomic_write_text(output, docs)
    click.echo(f"Wrote {output}")


@cli.command("completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion_command(shell: str) -> None:
    """Print shell autocomplete installation snippets."""

    snippets = {
        "bash": 'eval "$(_POLISYOS_TOOLS_COMPLETE=bash_source polisyos-tools)"',
        "zsh": 'eval "$(_POLISYOS_TOOLS_COMPLETE=zsh_source polisyos-tools)"',
        "fish": "_POLISYOS_TOOLS_COMPLETE=fish_source polisyos-tools | source",
    }
    click.echo(snippets[shell])


for _category in categories():
    cli.add_command(_make_category_group(_category))


def main(argv: Sequence[str] | None = None) -> int:
    """Console-script compatible entry point."""

    try:
        result = cli.main(
            args=list(argv) if argv is not None else None,
            prog_name="polisyos-tools",
            standalone_mode=False,
        )
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except click.exceptions.Exit as exc:
        return int(exc.exit_code)
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        return 0 if exc.code is None else 1
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
