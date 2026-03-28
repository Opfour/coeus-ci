"""CLI entry point."""

import asyncio
import click
from rich.console import Console
from coeus.core import Orchestrator
from coeus.report import TerminalReport

console = Console()


@click.command()
@click.argument("targets", nargs=-1)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--html", "html_output", is_flag=True,
              help="Save HTML report to ./reports/")
@click.option("--modules", "-m", default=None,
              help="Comma-separated module list (e.g., whois,dns,edgar)")
@click.option("--timeout", "-t", default=30,
              help="Per-module timeout in seconds")
@click.option("--web", is_flag=True, help="Launch web dashboard")
@click.option("--port", default=9000, help="Web dashboard port (default: 9000)")
def main(targets: tuple[str, ...], json_output: bool, html_output: bool,
         modules: str | None, timeout: int, web: bool, port: int):
    """Coeus CI - Competitive intelligence from public data.

    \b
    TARGETS is one or more domain names:
        coeus acme.com
        coeus acme.com competitor.com    (comparison mode)
        coeus --web                      (launch web dashboard)
    """
    if web:
        from coeus.web import run_server
        console.print("[bold cyan]Coeus CI[/bold cyan] — Web dashboard")
        console.print(f"Starting server at [link=http://127.0.0.1:{port}]http://127.0.0.1:{port}[/link]")
        console.print("[dim]Press Ctrl+C to stop[/dim]")
        try:
            run_server(port=port)
        except OSError as e:
            if "address already in use" in str(e).lower():
                console.print(f"[red]Port {port} is already in use.[/red] Try: coeus --web --port {port + 1}")
            else:
                raise
        return

    if not targets:
        raise click.UsageError("Provide at least one target domain, or use --web for the dashboard.")

    asyncio.run(_run(targets, json_output, html_output, modules, timeout))


async def _run(targets: tuple[str, ...], json_output: bool, html_output: bool,
               modules: str | None, timeout: int):
    module_filter = [m.strip() for m in modules.split(",")] if modules else None
    orchestrator = Orchestrator(timeout=timeout)

    reports = []
    for target in targets:
        report = await orchestrator.run(target, module_filter=module_filter)
        reports.append(report)

    if len(reports) == 1:
        report = reports[0]
        if json_output:
            TerminalReport.print_json(report)
        else:
            TerminalReport.print_scorecard(report)

        if html_output:
            path = TerminalReport.save_html(report)
            console.print(f"\n[green]HTML report saved:[/green] {path}")
    else:
        # Comparison mode
        if json_output:
            import json as json_mod
            out = [r.model_dump(mode="json") for r in reports]
            print(json_mod.dumps(out, indent=2, default=str))
        else:
            _print_comparison(reports)

        if html_output:
            for report in reports:
                path = TerminalReport.save_html(report)
                console.print(f"[green]HTML report saved:[/green] {path}")


def _print_comparison(reports):
    """Side-by-side scorecard comparison."""
    from rich.table import Table

    # Header
    console.print("\n[bold cyan]Comparison Report[/bold cyan]\n")

    # Scorecard comparison table
    table = Table(title="Scorecard Comparison", show_header=True,
                  header_style="bold magenta")
    table.add_column("Dimension", style="cyan", min_width=16)

    for r in reports:
        name = r.company_name or r.target
        table.add_column(name, justify="center", min_width=10)

    # Get all dimensions
    all_dims = set()
    for r in reports:
        all_dims.update(r.final_scores.keys())

    for dim in sorted(all_dims):
        label = dim.replace("_", " ").title()
        values = []
        scores = []
        for r in reports:
            score = r.final_scores.get(dim, 0.0)
            scores.append(score)
            values.append(f"{score}/10")

        # Highlight the winner
        max_score = max(scores)
        styled = []
        for i, (val, score) in enumerate(zip(values, scores)):
            if score == max_score and max_score > 0:
                styled.append(f"[bold green]{val}[/bold green]")
            else:
                styled.append(val)

        table.add_row(label, *styled)

    console.print(table)

    # Findings comparison
    for r in reports:
        name = r.company_name or r.target
        high_findings = [f for f in r.findings
                         if f.severity.value in ("high", "critical")]
        if high_findings:
            console.print(f"\n[bold]{name}[/bold] — Risk flags:")
            for f in high_findings:
                console.print(f"  [red]{f.severity.value.upper()}[/red] {f.title}")

    # Quick stats
    console.print("\n[bold]Quick Stats[/bold]")
    stats_table = Table(show_header=True, header_style="bold")
    stats_table.add_column("Metric", style="cyan")
    for r in reports:
        stats_table.add_column(r.company_name or r.target, justify="center")

    # Domain age
    ages = []
    for r in reports:
        w = r.module_results.get("whois")
        age = w.data.get("domain_age_years") if w and w.success else None
        ages.append(f"{age}y" if age else "?")
    stats_table.add_row("Domain Age", *ages)

    # Modules OK
    stats_table.add_row("Modules OK", *[
        f"{sum(1 for m in r.module_results.values() if m.success)}/{len(r.module_results)}"
        for r in reports
    ])

    # Findings count
    stats_table.add_row("Total Findings", *[
        str(len(r.findings)) for r in reports
    ])

    console.print(stats_table)
    console.print()
