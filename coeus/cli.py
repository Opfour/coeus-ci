"""CLI entry point."""

import asyncio
import re
import click
from rich.console import Console
from coeus import DEFAULT_WEB_PORT, DEFAULT_TIMEOUT
from coeus.core import Orchestrator
from coeus.report import TerminalReport

console = Console()

# Matches something that looks like a domain: word.tld or word.word.tld
_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$")


@click.command()
@click.argument("targets", nargs=-1)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--html", "html_output", is_flag=True,
              help="Save HTML report to ./reports/")
@click.option("--modules", "-m", default=None,
              help="Comma-separated module list (e.g., whois,dns,edgar)")
@click.option("--timeout", "-t", default=DEFAULT_TIMEOUT,
              help=f"Per-module timeout in seconds (default: {DEFAULT_TIMEOUT})")
@click.option("--web", is_flag=True, help="Launch web dashboard")
@click.option("--port", default=DEFAULT_WEB_PORT,
              help=f"Web dashboard port (default: {DEFAULT_WEB_PORT})")
def main(targets: tuple[str, ...], json_output: bool, html_output: bool,
         modules: str | None, timeout: int, web: bool, port: int):
    """Coeus CI - Competitive intelligence from public data.

    \b
    Accepts domains or company names:
        coeus apple.com
        coeus "apple inc"
        coeus apple.com microsoft.com    (comparison mode)
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
        raise click.UsageError("Provide at least one target domain or company name, or use --web for the dashboard.")

    parsed = _parse_targets(targets)
    asyncio.run(_run(parsed, json_output, html_output, modules, timeout))


def _is_domain(text: str) -> bool:
    """Check if text looks like a domain name."""
    return bool(_DOMAIN_RE.match(text.strip()))


def _parse_targets(raw_targets: tuple[str, ...]) -> list[str]:
    """Parse CLI arguments into a list of targets.

    Handles:
      - coeus apple.com                    → ["apple.com"]
      - coeus apple.com microsoft.com      → ["apple.com", "microsoft.com"]
      - coeus "apple inc"                  → ["apple inc"]  (quoted = company name)
      - coeus apple inc                    → ["apple inc"]  (non-domain words joined)
      - coeus apple.com "red cross"        → ["apple.com", "red cross"]
    """
    targets = []
    pending_words = []

    for arg in raw_targets:
        if _is_domain(arg):
            # Flush any pending company name words
            if pending_words:
                targets.append(" ".join(pending_words))
                pending_words = []
            targets.append(arg)
        else:
            pending_words.append(arg)

    # Flush remaining words as a company name
    if pending_words:
        targets.append(" ".join(pending_words))

    return targets


_COMPANY_SUFFIXES = {
    "inc", "inc.", "incorporated", "corp", "corp.", "corporation",
    "llc", "llc.", "ltd", "ltd.", "limited", "co", "co.",
    "company", "group", "holdings", "enterprises", "international",
}


async def _resolve_company_name(name: str) -> str | None:
    """Try to resolve a company name to a domain."""
    import aiohttp

    # Strip common corporate suffixes
    words = name.lower().split()
    core_words = [w for w in words if w.rstrip(".") not in _COMPANY_SUFFIXES]
    if not core_words:
        core_words = words  # fallback if everything was a suffix

    # Build domain guesses: "Apple Inc" → apple.com, "Red Cross" → redcross.com
    joined = "".join(re.sub(r"[^a-z0-9]", "", w) for w in core_words)
    full = "".join(re.sub(r"[^a-z0-9]", "", w) for w in words)
    # Also try first word only for single-brand companies
    first = re.sub(r"[^a-z0-9]", "", core_words[0]) if core_words else joined

    candidates = []
    seen = set()
    # Prioritize: full core name, then full with suffixes, then first word only
    for base in [joined, full, first]:
        if not base or base in seen:
            continue
        seen.add(base)
        for tld in [".com", ".org", ".net"]:
            candidates.append(f"{base}{tld}")

    async with aiohttp.ClientSession() as session:
        for domain in candidates:
            try:
                async with session.head(
                    f"https://{domain}",
                    timeout=aiohttp.ClientTimeout(total=5),
                    allow_redirects=True,
                ) as resp:
                    # Accept any response — if the server responds, the domain exists.
                    # Many legit sites return 403/405 on HEAD requests.
                    if resp.status < 500:
                        return domain
            except Exception:
                continue
    return None


async def _run(targets: list[str], json_output: bool, html_output: bool,
               modules: str | None, timeout: int):
    module_filter = [m.strip() for m in modules.split(",")] if modules else None
    orchestrator = Orchestrator(timeout=timeout)

    # Resolve company names to domains
    resolved_targets = []
    for target in targets:
        if _is_domain(target):
            resolved_targets.append(target)
        else:
            console.print(f"[dim]Resolving company name:[/dim] {target}")
            domain = await _resolve_company_name(target)
            if domain:
                console.print(f"[dim]  → found:[/dim] {domain}")
                resolved_targets.append(domain)
            else:
                console.print(f"[yellow]Could not resolve \"{target}\" to a domain.[/yellow]")
                console.print(f"[dim]  Tip: try the domain directly, e.g. coeus apple.com[/dim]")
                continue

    if not resolved_targets:
        console.print("[red]No valid targets to scan.[/red]")
        return

    reports = []
    for target in resolved_targets:
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
