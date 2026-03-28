"""Output formatters for terminal, JSON, and HTML."""

import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from jinja2 import Environment, FileSystemLoader
from coeus.models import CompanyReport, Severity

console = Console()


class TerminalReport:
    @staticmethod
    def print_scorecard(report: CompanyReport):
        name = report.company_name or report.target
        console.print(f"\n[bold cyan]{name}[/bold cyan]")
        console.print(f"[dim]Target: {report.target}[/dim]\n")

        ok = sum(1 for r in report.module_results.values() if r.success)
        total = len(report.module_results)
        console.print(f"[dim]Modules: {ok}/{total} succeeded[/dim]\n")

        # Scorecard
        table = Table(title="Scorecard", show_header=True, header_style="bold magenta")
        table.add_column("Dimension", style="cyan", min_width=16)
        table.add_column("Score", justify="center", min_width=6)
        table.add_column("Bar", min_width=12)

        for dim, score in report.final_scores.items():
            bar = _score_bar(score)
            label = dim.replace("_", " ").title()
            table.add_row(label, f"{score}/10", bar)

        console.print(table)

        # Findings
        if report.findings:
            console.print("\n[bold]Findings[/bold]")
            for f in sorted(report.findings,
                            key=lambda x: _sev_order(x.severity), reverse=True):
                icon = _sev_icon(f.severity)
                console.print(f"  {icon} [bold]{f.title}[/bold]")
                if f.detail:
                    console.print(f"      {f.detail}")

        # Module details
        console.print("\n[bold]Module Details[/bold]")
        for name, result in report.module_results.items():
            if result.success:
                console.print(
                    f"  [green]OK[/green]   {name} ({result.execution_time:.1f}s)")
            else:
                console.print(
                    f"  [red]FAIL[/red] {name}: {result.error}")

        # Key data highlights
        _print_highlights(report)
        console.print()

    @staticmethod
    def print_json(report: CompanyReport):
        print(report.model_dump_json(indent=2))

    @staticmethod
    def save_html(report: CompanyReport, output_path: str | None = None) -> str:
        """Render report as self-contained HTML file."""
        template_dir = Path(__file__).parent.parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))

        def score_color(score):
            if score >= 7:
                return "#3fb950"
            elif score >= 4:
                return "#d29922"
            return "#f85149"

        def score_class(score):
            if score >= 7:
                return "score-green"
            elif score >= 4:
                return "score-yellow"
            return "score-red"

        env.globals["score_color"] = score_color
        env.globals["score_class"] = score_class

        template = env.get_template("report.html")

        # Extract domain age from whois data
        domain_age = None
        whois_data = report.module_results.get("whois")
        if whois_data and whois_data.success:
            domain_age = whois_data.data.get("domain_age_years")

        html = template.render(
            target=report.target,
            company_name=report.company_name,
            generated_at=report.generated_at.strftime("%Y-%m-%d %H:%M"),
            scores=report.final_scores,
            findings=sorted(report.findings,
                            key=lambda f: _sev_order(f.severity), reverse=True),
            module_results=report.module_results,
            modules_ok=sum(1 for r in report.module_results.values() if r.success),
            modules_total=len(report.module_results),
            domain_age=domain_age,
        )

        if not output_path:
            os.makedirs("reports", exist_ok=True)
            safe_name = report.target.replace("/", "_").replace(":", "_")
            output_path = f"reports/{safe_name}.html"

        with open(output_path, "w") as f:
            f.write(html)

        return output_path


def _print_highlights(report: CompanyReport):
    """Print interesting data points from module results."""
    console.print("\n[bold]Key Intelligence[/bold]")

    for name, result in report.module_results.items():
        if not result.success or not result.data:
            continue

        d = result.data

        if name == "whois":
            age = d.get("domain_age_years")
            reg = d.get("registrar")
            if age:
                console.print(f"  Domain age: {age} years")
            if reg:
                console.print(f"  Registrar: {reg}")

        elif name == "dns":
            mail = d.get("mail_provider")
            cdn = d.get("cdn_detected")
            if mail:
                console.print(f"  Mail provider: {mail}")
            if cdn:
                console.print(f"  CDN: {cdn}")

        elif name == "ssl":
            org = d.get("subject_org")
            issuer = d.get("issuer_org")
            if org:
                console.print(f"  Certificate org: {org}")
            if issuer:
                console.print(f"  Certificate CA: {issuer}")

        elif name == "edgar":
            if d.get("is_public"):
                fin = d.get("financials", {})
                console.print(f"  SEC: Public company (CIK {d.get('cik', '?')})")
                if fin.get("revenue"):
                    console.print(f"  Revenue: ${fin['revenue']:,.0f}")
                if fin.get("employees"):
                    console.print(f"  Employees: {fin['employees']:,}")

        elif name == "nonprofit":
            if d.get("is_nonprofit"):
                console.print(f"  501(c)(3): {d.get('name', 'Yes')}")
                rev = d.get("revenue")
                if rev:
                    console.print(f"  Nonprofit revenue: ${rev:,.0f}")

        elif name == "dba":
            btype = d.get("business_type")
            status = d.get("status")
            if btype:
                console.print(f"  Business type: {btype}")
            if status:
                console.print(f"  Registration status: {status}")

        elif name == "tech":
            cms = d.get("cms_detected")
            if cms:
                console.print(f"  CMS: {cms}")

        elif name == "headers":
            server = d.get("server")
            count = d.get("security_header_count", 0)
            if server:
                console.print(f"  Server: {server}")
            console.print(f"  Security headers: {count}/5")


def _score_bar(score: float) -> str:
    filled = int(score)
    return "[green]" + "=" * filled + "[/green][dim]" + "-" * (10 - filled) + "[/dim]"


def _sev_order(s: Severity) -> int:
    return {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}[s.value]


def _sev_icon(s: Severity) -> str:
    return {
        "info": "[blue]INFO[/blue]",
        "low": "[cyan]LOW [/cyan]",
        "medium": "[yellow]MED [/yellow]",
        "high": "[red]HIGH[/red]",
        "critical": "[bold red]CRIT[/bold red]",
    }[s.value]
