"""Unified command entry point for repository tooling."""

from __future__ import annotations

import difflib
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import click

from tools.lib.fs import atomic_write_text
from tools.lib.output import (
    OUTPUT_FORMATS,
    OutputFormat,
    ToolMessage,
    ToolResult,
    format_tool_result,
)
from tools.lib.preflight import PreflightStatus, run_preflight
from tools.lib.runner import ToolExecutionError, ToolSpec, ToolStatus, invoke_tool_main
from tools.lib.timing import (
    append_timing_record,
    derive_timing_budget_catalog,
    load_timing_budget_catalog,
    make_timing_record,
    observed_timing_keys,
    read_timing_records,
    summarize_timing_budget_lanes,
    summarize_timing_records,
    timed_tool_run,
    timing_log_from_env,
    uncatalogued_timing_keys,
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
TIMING_BUDGET_CATALOG_SCOPE = "recorded_successful_lanes_plus_repository_fallbacks"


def _write_result(result: ToolResult, output_format: OutputFormat, *, stderr: bool = False) -> None:
    stream = sys.stderr if stderr else sys.stdout
    stream.write(format_tool_result(result, output_format=output_format))


def _preflight_result(spec: ToolSpec) -> ToolResult | None:
    preflight = run_preflight(spec)
    if preflight.status == PreflightStatus.OK:
        return None
    messages = tuple(
        ToolMessage(level=issue.status.value, message=issue.message) for issue in preflight.issues
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


def _summary_payload(
    limit: int,
    timing_log: Path,
    *,
    include_unmeasured: bool = False,
) -> dict[str, object]:
    records = read_timing_records(timing_log)
    summaries = summarize_timing_records(records)
    repository_catalog = load_timing_budget_catalog()
    sample_source = f"timing_log:{timing_log.resolve()}"
    successful_observed_catalog = derive_timing_budget_catalog(
        records,
        [],
        sample_source=sample_source,
    )
    effective_catalog = derive_timing_budget_catalog(
        records,
        repository_catalog,
        sample_source=sample_source,
    )
    lane_summaries = summarize_timing_budget_lanes(records, effective_catalog)
    observed_lanes = observed_timing_keys(records)
    uncatalogued_lanes = uncatalogued_timing_keys(records, effective_catalog)
    top_summaries = sorted(
        summaries,
        key=lambda summary: (-summary.average_duration_ms, summary.tool),
    )[:limit]
    return {
        "timing_log": str(timing_log),
        "record_count": len(records),
        "tool_count": len(summaries),
        "timing_budget_catalog_scope": TIMING_BUDGET_CATALOG_SCOPE,
        "repository_catalog_lane_count": len(repository_catalog),
        "effective_catalog_lane_count": len(effective_catalog),
        "observed_lane_count": len(observed_lanes),
        "successful_observed_lane_count": len(successful_observed_catalog),
        "uncatalogued_lane_count": len(uncatalogued_lanes),
        "uncatalogued_lanes": list(uncatalogued_lanes),
        "summaries": [
            {
                "tool": summary.tool,
                "category": summary.category,
                "latest_mode": summary.latest_mode,
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
        "lane_summaries": [
            {
                "timing_key": summary.timing_key,
                "tool": summary.tool,
                "mode": summary.mode,
                "command": summary.command,
                "measured_p95_ms": summary.measured_p95_ms,
                "recommended_timeout_ms": summary.recommended_timeout_ms,
                "source_refs": list(summary.source_refs),
                "sample_count": summary.sample_count,
                "sample_source": summary.sample_source,
                "state": summary.state,
                "local_runs": summary.local_runs,
                "local_failures": summary.local_failures,
                "latest_duration_ms": summary.latest_duration_ms,
                "over_budget_runs": summary.over_budget_runs,
            }
            for summary in lane_summaries
            if include_unmeasured or summary.state != "unmeasured"
        ],
    }


def _render_timing_text(payload: dict[str, object]) -> str:
    lines = [
        f"Timing log: {payload['timing_log']}",
        f"Recorded runs: {payload['record_count']} across {payload['tool_count']} tools",
        f"Budget catalog scope: {payload['timing_budget_catalog_scope']}",
        f"Effective budget lanes: {payload['effective_catalog_lane_count']}",
        f"Observed lanes: {payload['observed_lane_count']}",
        f"Successful observed lanes: {payload['successful_observed_lane_count']}",
        f"Observed lanes without an accepted budget: {payload['uncatalogued_lane_count']}",
        "",
        "Slowest tools by average duration:",
    ]
    summaries = payload["summaries"]
    assert isinstance(summaries, list)
    if not summaries:
        lines.append("- none")

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
            f"mode={item['latest_mode']}, "
            f"p95={float(item['p95_duration_ms']):.1f}ms, "
            f"latest={float(item['latest_duration_ms']):.1f}ms, "
            f"runs={int(item['runs'])}, failures={int(item['failures'])}, "
            f"skipped={int(item['skipped'])}, status={item['latest_status']}"
            f"{budget_text}"
        )
    lane_summaries = payload["lane_summaries"]
    assert isinstance(lane_summaries, list)
    uncatalogued_lanes = payload["uncatalogued_lanes"]
    assert isinstance(uncatalogued_lanes, list)
    if uncatalogued_lanes:
        lines.extend(["", "Observed lanes without an accepted budget:"])
        lines.extend(f"- {timing_key}" for timing_key in uncatalogued_lanes)
    if lane_summaries:
        lines.extend(["", "Measured budget lanes:"])
        for item in lane_summaries:
            assert isinstance(item, dict)
            lines.append(
                "- "
                f"{item['timing_key']}: state={item['state']}, "
                f"p95={item['measured_p95_ms']}, "
                f"timeout={item['recommended_timeout_ms']}, "
                f"samples={item['sample_count']}, "
                f"sample_source={item['sample_source']}, "
                f"local_runs={item['local_runs']}, "
                f"over_budget={item['over_budget_runs']}"
            )
    return "\n".join(lines) + "\n"


def _render_timing_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Tool Timing Summary",
        "",
        f"- Timing log: `{payload['timing_log']}`",
        f"- Recorded runs: {payload['record_count']}",
        f"- Distinct tools: {payload['tool_count']}",
        f"- Budget catalog scope: `{payload['timing_budget_catalog_scope']}`",
        f"- Effective budget lanes: {payload['effective_catalog_lane_count']}",
        f"- Observed lanes: {payload['observed_lane_count']}",
        f"- Successful observed lanes: {payload['successful_observed_lane_count']}",
        f"- Observed lanes without an accepted budget: {payload['uncatalogued_lane_count']}",
        "",
        "| Tool | Mode | Avg (ms) | P95 (ms) | Latest (ms) | Failures | Skipped | Budget (ms) | Over budget |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    summaries = payload["summaries"]
    assert isinstance(summaries, list)
    for item in summaries:
        assert isinstance(item, dict)
        budget = item.get("budget_ms")
        lines.append(
            f"| `{item['tool']}` | {item['latest_mode']} | {float(item['average_duration_ms']):.1f} | "
            f"{float(item['p95_duration_ms']):.1f} | {float(item['latest_duration_ms']):.1f} | "
            f"{int(item['failures'])} | {int(item['skipped'])} | "
            f"{('-' if budget is None else f'{float(budget):.1f}')} | {int(item['over_budget_runs'])} |"
        )
    lane_summaries = payload["lane_summaries"]
    assert isinstance(lane_summaries, list)
    uncatalogued_lanes = payload["uncatalogued_lanes"]
    assert isinstance(uncatalogued_lanes, list)
    if uncatalogued_lanes:
        lines.extend(["", "## Observed Lanes Without An Accepted Budget", ""])
        lines.extend(f"- `{timing_key}`" for timing_key in uncatalogued_lanes)
    if lane_summaries:
        lines.extend(
            [
                "",
                "## Measured Budget Lanes",
                "",
                "| Lane | State | P95 (ms) | Recommended timeout (ms) | Samples | Source | Local runs | Over budget |",
                "| --- | --- | ---: | ---: | ---: | --- | ---: | ---: |",
            ]
        )
        for item in lane_summaries:
            assert isinstance(item, dict)
            lines.append(
                f"| `{item['timing_key']}` | {item['state']} | "
                f"{item['measured_p95_ms'] if item['measured_p95_ms'] is not None else '-'} | "
                f"{item['recommended_timeout_ms'] if item['recommended_timeout_ms'] is not None else '-'} | "
                f"{item['sample_count']} | {item['sample_source']} | "
                f"{item['local_runs']} | {item['over_budget_runs']} |"
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
    @click.option(
        "--skip-preflight", is_flag=True, help="Skip dependency and lifecycle preflight checks."
    )
    @click.option(
        "--allow-degraded",
        is_flag=True,
        help="Run a tool even when preflight reports degraded mode.",
    )
    @click.option(
        "--allow-deprecated", is_flag=True, help="Run deprecated or quarantined legacy tools."
    )
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
@click.option(
    "--include-unmeasured",
    is_flag=True,
    help="Include catalog lanes with no literal measurement samples.",
)
def report_timing_command(
    timing_log: Path | None,
    output_format: str,
    limit: int,
    summary_markdown: Path | None,
    include_unmeasured: bool,
) -> None:
    """Summarize recent tool timing records and budget overruns."""

    target = timing_log or timing_log_from_env()
    if target is None:
        raise click.ClickException("No timing log path is configured")

    payload = _summary_payload(limit, target, include_unmeasured=include_unmeasured)
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
