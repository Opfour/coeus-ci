"""CLI entry point."""

import asyncio
import click
from rich.console import Console
from coeus.core import Orchestrator
from coeus.report import TerminalReport

console = Console()


@click.command()
@click.argument("target")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--modules", "-m", default=None,
              help="Comma-separated module list (e.g., whois,dns,edgar)")
@click.option("--timeout", "-t", default=30,
              help="Per-module timeout in seconds")
def main(target: str, json_output: bool, modules: str | None, timeout: int):
    """Coeus CI - Competitive intelligence from public data.

    TARGET is a domain name (e.g., acme.com).
    """
    asyncio.run(_run(target, json_output, modules, timeout))


async def _run(target: str, json_output: bool,
               modules: str | None, timeout: int):
    module_filter = [m.strip() for m in modules.split(",")] if modules else None
    orchestrator = Orchestrator(timeout=timeout)
    results = await orchestrator.run(target, module_filter=module_filter)

    if json_output:
        TerminalReport.print_json(results)
    else:
        TerminalReport.print_scorecard(results)
