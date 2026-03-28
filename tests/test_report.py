"""Tests for report formatters."""

import os
import tempfile
from io import StringIO
from unittest.mock import patch
import pytest
from coeus.models import CompanyReport, ModuleResult, Finding, Severity, ScoreContribution, ScoreDimension
from coeus.report import TerminalReport, _score_bar, _sev_order, _sev_icon, _print_highlights


class TestHelpers:
    def test_score_bar_full(self):
        bar = _score_bar(10.0)
        assert "=" * 10 in bar
        assert "-" not in bar.replace("[/dim]", "").replace("[dim]", "").replace("[green]", "").replace("[/green]", "")

    def test_score_bar_zero(self):
        bar = _score_bar(0.0)
        assert "-" * 10 in bar

    def test_score_bar_partial(self):
        bar = _score_bar(7.0)
        # 7 filled, 3 empty
        assert "=======" in bar
        assert "---" in bar

    def test_sev_order_ranking(self):
        assert _sev_order(Severity.INFO) == 0
        assert _sev_order(Severity.LOW) == 1
        assert _sev_order(Severity.MEDIUM) == 2
        assert _sev_order(Severity.HIGH) == 3
        assert _sev_order(Severity.CRITICAL) == 4

    def test_sev_icon_all(self):
        for s in Severity:
            icon = _sev_icon(s)
            assert len(icon) > 0


class TestTerminalReport:
    @pytest.fixture
    def report(self):
        r = CompanyReport(target="example.com", company_name="Example Corp")
        r.module_results["whois"] = ModuleResult(
            module_name="whois", success=True, execution_time=0.5,
            data={"domain_age_years": 10, "registrar": "GoDaddy"},
        )
        r.module_results["ssl"] = ModuleResult(
            module_name="ssl", success=False, error="Connection refused",
        )
        r.findings = [
            Finding(title="Test finding", severity=Severity.HIGH, source="whois"),
        ]
        r.final_scores = {"stability": 8.0, "security": 5.0, "growth": 0.0,
                          "tech_maturity": 0.0, "financial": 0.0, "transparency": 0.0}
        return r

    def test_print_scorecard_no_crash(self, report, capsys):
        TerminalReport.print_scorecard(report)
        output = capsys.readouterr().out
        assert "Example Corp" in output

    def test_print_json_output(self, report, capsys):
        TerminalReport.print_json(report)
        output = capsys.readouterr().out
        import json
        parsed = json.loads(output)
        assert parsed["target"] == "example.com"

    def test_save_html_creates_file(self, report):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            result_path = TerminalReport.save_html(report, output_path=path)
            assert os.path.exists(result_path)
            content = open(result_path).read()
            assert "Example Corp" in content
        finally:
            os.unlink(path)

    def test_save_html_default_path(self, report):
        path = TerminalReport.save_html(report)
        try:
            assert os.path.exists(path)
            assert "example.com" in path
        finally:
            os.unlink(path)

    def test_save_html_contains_scores(self, report):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            TerminalReport.save_html(report, output_path=path)
            content = open(path).read()
            assert "8.0" in content  # stability score
            assert "stability" in content.lower()
        finally:
            os.unlink(path)


class TestPrintHighlights:
    def _make_report(self, **module_data):
        """Build a report with specified module results."""
        report = CompanyReport(target="example.com")
        for name, data in module_data.items():
            report.module_results[name] = ModuleResult(
                module_name=name, success=True, execution_time=0.1, data=data,
            )
        return report

    def test_whois_highlights(self, capsys):
        report = self._make_report(whois={"domain_age_years": 15, "registrar": "GoDaddy"})
        _print_highlights(report)
        out = capsys.readouterr().out
        assert "15" in out
        assert "GoDaddy" in out

    def test_dns_highlights(self, capsys):
        report = self._make_report(dns={"mail_provider": "Google Workspace", "cdn_detected": "Cloudflare"})
        _print_highlights(report)
        out = capsys.readouterr().out
        assert "Google Workspace" in out
        assert "Cloudflare" in out

    def test_ssl_highlights(self, capsys):
        report = self._make_report(ssl={"subject_org": "Apple Inc.", "issuer_org": "DigiCert"})
        _print_highlights(report)
        out = capsys.readouterr().out
        assert "Apple Inc." in out
        assert "DigiCert" in out

    def test_edgar_highlights(self, capsys):
        report = self._make_report(edgar={
            "is_public": True, "cik": "320193",
            "financials": {"revenue": 394_000_000_000, "employees": 164000},
        })
        _print_highlights(report)
        out = capsys.readouterr().out
        assert "320193" in out
        assert "394" in out
        assert "164" in out

    def test_nonprofit_highlights(self, capsys):
        report = self._make_report(nonprofit={
            "is_nonprofit": True, "name": "Red Cross", "revenue": 3_000_000_000,
        })
        _print_highlights(report)
        out = capsys.readouterr().out
        assert "Red Cross" in out

    def test_dba_highlights(self, capsys):
        report = self._make_report(dba={"business_type": "Corporation", "status": "Active"})
        _print_highlights(report)
        out = capsys.readouterr().out
        assert "Corporation" in out
        assert "Active" in out

    def test_tech_highlights(self, capsys):
        report = self._make_report(tech={"cms_detected": "WordPress"})
        _print_highlights(report)
        out = capsys.readouterr().out
        assert "WordPress" in out

    def test_headers_highlights(self, capsys):
        report = self._make_report(headers={"server": "nginx", "security_header_count": 3})
        _print_highlights(report)
        out = capsys.readouterr().out
        assert "nginx" in out
        assert "3/5" in out

    def test_failed_module_skipped(self, capsys):
        report = CompanyReport(target="example.com")
        report.module_results["whois"] = ModuleResult(
            module_name="whois", success=False, error="failed", execution_time=0.1,
        )
        _print_highlights(report)
        out = capsys.readouterr().out
        assert "GoDaddy" not in out  # should not print data from failed module
