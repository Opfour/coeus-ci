"""Shared fixtures for Coeus CI tests."""

import pytest
from datetime import datetime, timezone
from coeus.models import (
    CompanyReport, ModuleResult, Finding, ScoreContribution,
    Severity, ScoreDimension,
)


@pytest.fixture
def sample_finding():
    def _make(severity=Severity.INFO, title="Test finding", source="test"):
        return Finding(title=title, severity=severity, source=source)
    return _make


@pytest.fixture
def sample_score():
    def _make(dimension=ScoreDimension.STABILITY, points=5.0, weight=1.0):
        return ScoreContribution(
            dimension=dimension, points=points, weight=weight,
            reason="test reason",
        )
    return _make


@pytest.fixture
def sample_module_result():
    def _make(name="test_mod", success=True, data=None, findings=None, scores=None):
        return ModuleResult(
            module_name=name,
            success=success,
            data=data or {},
            findings=findings or [],
            scores=scores or [],
            execution_time=0.5,
        )
    return _make


@pytest.fixture
def mock_whois_result():
    return ModuleResult(
        module_name="whois", success=True, execution_time=0.8,
        data={
            "domain": "apple.com",
            "registrar": "NOM-IQ Ltd",
            "org": "Apple Inc.",
            "domain_age_years": 39.1,
            "creation_date": "1987-02-19",
            "expiration_date": "2028-02-20",
        },
        findings=[],
        scores=[
            ScoreContribution(
                dimension=ScoreDimension.STABILITY, points=9.0, weight=2.0,
                reason="Domain registered 39.1 years ago",
            ),
            ScoreContribution(
                dimension=ScoreDimension.TRANSPARENCY, points=8.0, weight=1.0,
                reason="WHOIS organization is publicly visible",
            ),
        ],
    )


@pytest.fixture
def mock_ssl_result():
    return ModuleResult(
        module_name="ssl", success=True, execution_time=0.1,
        data={"subject_org": "Apple Inc.", "issuer_org": "Apple Inc."},
        findings=[],
        scores=[
            ScoreContribution(
                dimension=ScoreDimension.SECURITY, points=9.0, weight=1.0,
                reason="Valid certificate",
            ),
            ScoreContribution(
                dimension=ScoreDimension.STABILITY, points=7.0, weight=1.0,
                reason="Certificate issued by Apple Inc.",
            ),
        ],
    )


@pytest.fixture
def mock_edgar_result_public():
    return ModuleResult(
        module_name="edgar", success=True, execution_time=1.5,
        data={
            "is_public": True, "cik": "320193",
            "company_name_sec": "Apple Inc.",
            "financials": {"revenue": 394_328_000_000, "net_income": 96_995_000_000},
            "recent_filings": [{"form": "10-K"}] * 10,
        },
        findings=[
            Finding(title="Strong profit margin", severity=Severity.INFO, source="edgar"),
        ],
        scores=[
            ScoreContribution(
                dimension=ScoreDimension.FINANCIAL, points=9.0, weight=3.0,
                reason="Revenue: $394B",
            ),
            ScoreContribution(
                dimension=ScoreDimension.TRANSPARENCY, points=9.0, weight=2.0,
                reason="Public company with SEC filings",
            ),
        ],
    )


@pytest.fixture
def mock_edgar_result_private():
    return ModuleResult(
        module_name="edgar", success=True, execution_time=0.3,
        data={"is_public": False},
        findings=[], scores=[],
    )


@pytest.fixture
def full_report(mock_whois_result, mock_ssl_result, mock_edgar_result_public):
    report = CompanyReport(target="apple.com", company_name="Apple Inc.")
    report.module_results = {
        "whois": mock_whois_result,
        "ssl": mock_ssl_result,
        "edgar": mock_edgar_result_public,
    }
    report.findings = (
        mock_whois_result.findings +
        mock_ssl_result.findings +
        mock_edgar_result_public.findings
    )
    return report
