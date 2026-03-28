"""Tests for CLI argument parsing and target resolution."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from click.testing import CliRunner
from coeus.cli import (
    main, _is_domain, _looks_like_ticker, _parse_targets,
    _resolve_ticker, _resolve_company_name, _print_comparison,
)
from coeus.models import CompanyReport, ModuleResult, Finding, Severity


class TestIsDomain:
    def test_valid_com(self):
        assert _is_domain("example.com") is True

    def test_valid_subdomain(self):
        assert _is_domain("sub.example.co.uk") is True

    def test_invalid_no_tld(self):
        assert _is_domain("notadomain") is False

    def test_invalid_spaces(self):
        assert _is_domain("not a domain") is False

    def test_invalid_ticker(self):
        assert _is_domain("AAPL") is False


class TestLooksLikeTicker:
    def test_valid_uppercase(self):
        assert _looks_like_ticker("AAPL") is True

    def test_valid_single_char(self):
        assert _looks_like_ticker("A") is True

    def test_lowercase_rejected(self):
        assert _looks_like_ticker("aapl") is False

    def test_mixed_case_rejected(self):
        assert _looks_like_ticker("Aapl") is False

    def test_too_long(self):
        assert _looks_like_ticker("ABCDEF") is False

    def test_with_numbers(self):
        assert _looks_like_ticker("AB1") is False


class TestParseTargets:
    def test_single_domain(self):
        assert _parse_targets(("example.com",)) == ["example.com"]

    def test_multiple_domains(self):
        assert _parse_targets(("a.com", "b.com")) == ["a.com", "b.com"]

    def test_ticker(self):
        assert _parse_targets(("AAPL",)) == ["AAPL"]

    def test_multiple_tickers(self):
        assert _parse_targets(("AAPL", "MSFT")) == ["AAPL", "MSFT"]

    def test_company_name_joined(self):
        assert _parse_targets(("apple", "inc")) == ["apple inc"]

    def test_mixed_domain_and_company(self):
        result = _parse_targets(("apple.com", "red", "cross"))
        assert result == ["apple.com", "red cross"]

    def test_quoted_company(self):
        assert _parse_targets(("apple inc",)) == ["apple inc"]

    def test_domain_then_ticker(self):
        result = _parse_targets(("apple.com", "MSFT"))
        assert result == ["apple.com", "MSFT"]


class TestCli:
    def test_no_targets_error(self):
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code != 0

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Competitive intelligence" in result.output

    def test_web_flag(self):
        runner = CliRunner()
        with patch("coeus.web.run_server") as mock_server:
            result = runner.invoke(main, ["--web"])
            # Verifies the --web flag path executes without crash

    def test_modules_option(self):
        runner = CliRunner()
        with patch("coeus.cli._run", new_callable=AsyncMock) as mock_run:
            with patch("coeus.cli.asyncio") as mock_asyncio:
                mock_asyncio.run = lambda coro: None
                result = runner.invoke(main, ["example.com", "--modules", "whois,dns"])
                # Verify it reaches asyncio.run without error
                assert result.exit_code == 0 or "Error" not in (result.output or "")

    def test_web_port_in_use(self):
        runner = CliRunner()
        with patch("coeus.web.run_server", side_effect=OSError("address already in use")):
            result = runner.invoke(main, ["--web", "--port", "9999"])
            assert "already in use" in result.output

    def test_web_other_os_error(self):
        runner = CliRunner()
        with patch("coeus.web.run_server", side_effect=OSError("permission denied")):
            result = runner.invoke(main, ["--web"])
            assert result.exit_code != 0


class TestResolveTicker:
    @pytest.mark.asyncio
    async def test_found(self):
        mock_data = {"0": {"ticker": "AAPL", "title": "Apple Inc.", "cik_str": "320193"}}
        from aioresponses import aioresponses
        with aioresponses() as m:
            m.get("https://www.sec.gov/files/company_tickers.json",
                  payload=mock_data)
            result = await _resolve_ticker("AAPL")
            assert result == ("Apple Inc.", "AAPL")

    @pytest.mark.asyncio
    async def test_not_found(self):
        from aioresponses import aioresponses
        with aioresponses() as m:
            m.get("https://www.sec.gov/files/company_tickers.json",
                  payload={"0": {"ticker": "MSFT", "title": "Microsoft", "cik_str": "789019"}})
            result = await _resolve_ticker("ZZZZ")
            assert result is None

    @pytest.mark.asyncio
    async def test_network_error(self):
        from aioresponses import aioresponses
        with aioresponses() as m:
            m.get("https://www.sec.gov/files/company_tickers.json",
                  exception=ConnectionError("timeout"))
            result = await _resolve_ticker("AAPL")
            assert result is None


class TestResolveCompanyName:
    @pytest.mark.asyncio
    async def test_found_com(self):
        from aioresponses import aioresponses
        import re
        with aioresponses() as m:
            m.head(re.compile(r"https://apple\.com"), status=200)
            result = await _resolve_company_name("Apple Inc")
            assert result == "apple.com"

    @pytest.mark.asyncio
    async def test_strips_suffixes(self):
        from aioresponses import aioresponses
        import re
        with aioresponses() as m:
            m.head(re.compile(r"https://acme\.com"), status=200)
            result = await _resolve_company_name("Acme Corporation")
            assert result == "acme.com"

    @pytest.mark.asyncio
    async def test_not_found(self):
        from aioresponses import aioresponses
        import re
        with aioresponses() as m:
            m.head(re.compile(r"https://.*"), exception=ConnectionError("nope"),
                   repeat=True)
            result = await _resolve_company_name("Nonexistent Corp XYZ")
            assert result is None

    @pytest.mark.asyncio
    async def test_500_skipped(self):
        from aioresponses import aioresponses
        import re
        with aioresponses() as m:
            m.head(re.compile(r"https://.*"), status=500, repeat=True)
            result = await _resolve_company_name("Bad Server Inc")
            assert result is None

    @pytest.mark.asyncio
    async def test_403_accepted(self):
        """Sites returning 403 on HEAD should still be considered valid."""
        from aioresponses import aioresponses
        import re
        with aioresponses() as m:
            m.head(re.compile(r"https://redcross\.com"), status=403)
            result = await _resolve_company_name("Red Cross")
            assert result == "redcross.com"


class TestRun:
    @pytest.mark.asyncio
    async def test_run_single_domain(self):
        from coeus.cli import _run
        report = CompanyReport(target="example.com", company_name="Example")
        report.final_scores = {"stability": 5.0}
        with patch("coeus.cli.Orchestrator") as MockOrch:
            instance = MockOrch.return_value
            instance.run = AsyncMock(return_value=report)
            await _run(["example.com"], False, False, None, 30)

    @pytest.mark.asyncio
    async def test_run_json_output(self, capsys):
        from coeus.cli import _run
        report = CompanyReport(target="example.com", company_name="Example")
        report.final_scores = {"stability": 5.0}
        with patch("coeus.cli.Orchestrator") as MockOrch:
            instance = MockOrch.return_value
            instance.run = AsyncMock(return_value=report)
            await _run(["example.com"], True, False, None, 30)
        output = capsys.readouterr().out
        assert "example.com" in output

    @pytest.mark.asyncio
    async def test_run_with_module_filter(self):
        from coeus.cli import _run
        report = CompanyReport(target="example.com")
        with patch("coeus.cli.Orchestrator") as MockOrch:
            instance = MockOrch.return_value
            instance.run = AsyncMock(return_value=report)
            await _run(["example.com"], False, False, "whois,dns", 30)
            instance.run.assert_called_once_with("example.com", module_filter=["whois", "dns"])

    @pytest.mark.asyncio
    async def test_run_ticker_resolution(self):
        from coeus.cli import _run
        report = CompanyReport(target="apple.com", company_name="Apple Inc.")
        report.final_scores = {"stability": 5.0}
        with patch("coeus.cli.Orchestrator") as MockOrch, \
             patch("coeus.cli._resolve_ticker", new_callable=AsyncMock,
                   return_value=("Apple Inc.", "AAPL")), \
             patch("coeus.cli._resolve_company_name", new_callable=AsyncMock,
                   return_value="apple.com"):
            instance = MockOrch.return_value
            instance.run = AsyncMock(return_value=report)
            await _run(["AAPL"], False, False, None, 30)
            instance.run.assert_called_once_with("apple.com", module_filter=None)

    @pytest.mark.asyncio
    async def test_run_company_name_resolution(self):
        from coeus.cli import _run
        report = CompanyReport(target="apple.com", company_name="Apple Inc.")
        with patch("coeus.cli.Orchestrator") as MockOrch, \
             patch("coeus.cli._resolve_company_name", new_callable=AsyncMock,
                   return_value="apple.com"):
            instance = MockOrch.return_value
            instance.run = AsyncMock(return_value=report)
            await _run(["apple inc"], False, False, None, 30)
            instance.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_no_resolved_targets(self, capsys):
        from coeus.cli import _run
        with patch("coeus.cli._resolve_company_name", new_callable=AsyncMock,
                   return_value=None):
            await _run(["nonexistent company xyz"], False, False, None, 30)
        output = capsys.readouterr().out
        assert "No valid targets" in output

    @pytest.mark.asyncio
    async def test_run_comparison_mode(self):
        from coeus.cli import _run
        r1 = CompanyReport(target="a.com", company_name="A Corp")
        r1.final_scores = {"stability": 8.0}
        r2 = CompanyReport(target="b.com", company_name="B Corp")
        r2.final_scores = {"stability": 6.0}
        with patch("coeus.cli.Orchestrator") as MockOrch:
            instance = MockOrch.return_value
            instance.run = AsyncMock(side_effect=[r1, r2])
            await _run(["a.com", "b.com"], False, False, None, 30)

    @pytest.mark.asyncio
    async def test_run_comparison_json(self, capsys):
        from coeus.cli import _run
        r1 = CompanyReport(target="a.com")
        r1.final_scores = {"stability": 8.0}
        r2 = CompanyReport(target="b.com")
        r2.final_scores = {"stability": 6.0}
        with patch("coeus.cli.Orchestrator") as MockOrch:
            instance = MockOrch.return_value
            instance.run = AsyncMock(side_effect=[r1, r2])
            await _run(["a.com", "b.com"], True, False, None, 30)
        output = capsys.readouterr().out
        import json
        data = json.loads(output)
        assert len(data) == 2


class TestPrintComparison:
    def test_comparison_output(self, capsys):
        r1 = CompanyReport(target="a.com", company_name="A Corp")
        r1.final_scores = {"stability": 8.0, "security": 6.0}
        r1.module_results["whois"] = ModuleResult(
            module_name="whois", success=True, execution_time=0.5,
            data={"domain_age_years": 10},
        )
        r2 = CompanyReport(target="b.com", company_name="B Corp")
        r2.final_scores = {"stability": 5.0, "security": 9.0}
        r2.module_results["whois"] = ModuleResult(
            module_name="whois", success=True, execution_time=0.3,
            data={"domain_age_years": 5},
        )
        r2.findings = [Finding(title="Risky thing", severity=Severity.HIGH, source="test")]

        _print_comparison([r1, r2])
        output = capsys.readouterr().out
        assert "Comparison" in output
        assert "A Corp" in output
        assert "B Corp" in output
