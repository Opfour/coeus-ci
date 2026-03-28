"""Tests for Pydantic data models."""

import json
from datetime import datetime
from coeus.models import (
    Severity, ScoreDimension, Finding, ScoreContribution,
    ModuleResult, CompanyReport,
)


class TestSeverity:
    def test_enum_values(self):
        assert Severity.INFO.value == "info"
        assert Severity.LOW.value == "low"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.HIGH.value == "high"
        assert Severity.CRITICAL.value == "critical"

    def test_enum_count(self):
        assert len(Severity) == 5


class TestScoreDimension:
    def test_enum_values(self):
        assert ScoreDimension.STABILITY.value == "stability"
        assert ScoreDimension.GROWTH.value == "growth"
        assert ScoreDimension.TECH_MATURITY.value == "tech_maturity"
        assert ScoreDimension.FINANCIAL.value == "financial"
        assert ScoreDimension.SECURITY.value == "security"
        assert ScoreDimension.TRANSPARENCY.value == "transparency"

    def test_enum_count(self):
        assert len(ScoreDimension) == 6


class TestFinding:
    def test_defaults(self):
        f = Finding(title="Test", source="test_mod")
        assert f.severity == Severity.INFO
        assert f.detail == ""

    def test_full_construction(self):
        f = Finding(
            title="Risk", detail="Details here",
            severity=Severity.HIGH, source="whois",
        )
        assert f.title == "Risk"
        assert f.detail == "Details here"
        assert f.severity == Severity.HIGH

    def test_roundtrip(self):
        f = Finding(title="Test", source="mod", severity=Severity.CRITICAL)
        d = f.model_dump()
        f2 = Finding(**d)
        assert f == f2


class TestScoreContribution:
    def test_weight_default(self):
        sc = ScoreContribution(
            dimension=ScoreDimension.SECURITY, points=7.0, reason="test",
        )
        assert sc.weight == 1.0

    def test_all_fields(self):
        sc = ScoreContribution(
            dimension=ScoreDimension.FINANCIAL, points=9.5, weight=3.0,
            reason="High revenue",
        )
        assert sc.points == 9.5
        assert sc.weight == 3.0


class TestModuleResult:
    def test_success(self):
        r = ModuleResult(
            module_name="test", success=True,
            data={"key": "val"},
            findings=[Finding(title="F", source="test")],
        )
        assert r.success is True
        assert r.data["key"] == "val"
        assert len(r.findings) == 1

    def test_failure(self):
        r = ModuleResult(module_name="test", success=False, error="boom")
        assert r.success is False
        assert r.error == "boom"
        assert r.data == {}
        assert r.findings == []
        assert r.scores == []

    def test_default_factories(self):
        r = ModuleResult(module_name="x", success=True)
        assert r.data == {}
        assert r.findings == []
        assert r.scores == []
        assert r.execution_time == 0.0


class TestCompanyReport:
    def test_defaults(self):
        r = CompanyReport(target="example.com")
        assert r.target == "example.com"
        assert r.company_name is None
        assert isinstance(r.generated_at, datetime)
        assert r.module_results == {}
        assert r.findings == []
        assert r.final_scores == {}

    def test_serialization_roundtrip(self):
        r = CompanyReport(target="x.com", company_name="X Corp")
        j = r.model_dump_json()
        parsed = json.loads(j)
        assert parsed["target"] == "x.com"
        assert parsed["company_name"] == "X Corp"

    def test_model_dump_mode_json(self):
        r = CompanyReport(target="x.com")
        d = r.model_dump(mode="json")
        assert isinstance(d["generated_at"], str)
