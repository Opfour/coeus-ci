"""Tests for the Orchestrator."""

import asyncio
from unittest.mock import patch, AsyncMock
import pytest
from coeus.core import Orchestrator
from coeus.models import ModuleResult, ScoreContribution, ScoreDimension, Finding, Severity
from coeus.modules.base import BaseModule


class FakeModule(BaseModule):
    def __init__(self, mod_name, result=None, delay=0, raise_exc=None):
        self._name = mod_name
        self._result = result
        self._delay = delay
        self._raise_exc = raise_exc

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return "fake"

    async def execute(self, target, context):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._raise_exc:
            raise self._raise_exc
        if self._result:
            return self._result
        return self._ok({"target": target})


class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_runs_all_modules(self):
        mods = [
            FakeModule("whois"),
            FakeModule("ssl"),
            FakeModule("dns"),
        ]
        with patch("coeus.core.Orchestrator.WAVE_1", {"whois", "ssl"}):
            with patch("coeus.modules.ALL_MODULES", mods):
                o = Orchestrator(timeout=10)
                report = await o.run("example.com")
                assert len(report.module_results) == 3
                assert all(r.success for r in report.module_results.values())

    @pytest.mark.asyncio
    async def test_module_filter(self):
        mods = [FakeModule("whois"), FakeModule("ssl"), FakeModule("dns")]
        with patch("coeus.modules.ALL_MODULES", mods):
            o = Orchestrator(timeout=10)
            report = await o.run("x.com", module_filter=["whois"])
            assert "whois" in report.module_results
            assert len(report.module_results) == 1

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        slow = FakeModule("slow", delay=5)
        with patch("coeus.modules.ALL_MODULES", [slow]):
            with patch("coeus.core.Orchestrator.WAVE_1", set()):
                o = Orchestrator(timeout=0.1)
                report = await o.run("x.com")
                r = report.module_results["slow"]
                assert r.success is False
                assert "Timed out" in r.error

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        broken = FakeModule("broken", raise_exc=RuntimeError("kaboom"))
        with patch("coeus.modules.ALL_MODULES", [broken]):
            with patch("coeus.core.Orchestrator.WAVE_1", set()):
                o = Orchestrator(timeout=10)
                report = await o.run("x.com")
                r = report.module_results["broken"]
                assert r.success is False
                assert "kaboom" in r.error

    @pytest.mark.asyncio
    async def test_context_propagation(self):
        class NameSetter(FakeModule):
            async def execute(self, target, context):
                context["company_name"] = "Test Corp"
                return self._ok({"org": "Test Corp"})

        class NameReader(FakeModule):
            async def execute(self, target, context):
                return self._ok({"got_name": context.get("company_name")})

        mods = [NameSetter("whois"), NameReader("dns")]
        with patch("coeus.modules.ALL_MODULES", mods):
            with patch("coeus.core.Orchestrator.WAVE_1", {"whois"}):
                o = Orchestrator(timeout=10)
                report = await o.run("x.com")
                assert report.company_name == "Test Corp"
                dns_data = report.module_results["dns"].data
                assert dns_data["got_name"] == "Test Corp"

    @pytest.mark.asyncio
    async def test_findings_aggregation(self):
        f1 = Finding(title="A", source="mod1", severity=Severity.LOW)
        f2 = Finding(title="B", source="mod2", severity=Severity.HIGH)
        r1 = ModuleResult(module_name="mod1", success=True, findings=[f1])
        r2 = ModuleResult(module_name="mod2", success=True, findings=[f2])
        m1 = FakeModule("whois", result=r1)
        m2 = FakeModule("dns", result=r2)
        with patch("coeus.modules.ALL_MODULES", [m1, m2]):
            with patch("coeus.core.Orchestrator.WAVE_1", {"whois"}):
                o = Orchestrator(timeout=10)
                report = await o.run("x.com")
                assert len(report.findings) == 2

    @pytest.mark.asyncio
    async def test_scorer_integration(self):
        sc = ScoreContribution(
            dimension=ScoreDimension.SECURITY, points=8.0,
            weight=1.0, reason="test",
        )
        result = ModuleResult(module_name="mod", success=True, scores=[sc])
        mod = FakeModule("whois", result=result)
        with patch("coeus.modules.ALL_MODULES", [mod]):
            o = Orchestrator(timeout=10)
            report = await o.run("x.com")
            assert report.final_scores["security"] == 8.0

    @pytest.mark.asyncio
    async def test_many_modules_complete(self):
        """Verify semaphore doesn't block completion."""
        mods = [FakeModule(f"mod{i}") for i in range(10)]
        with patch("coeus.modules.ALL_MODULES", mods):
            with patch("coeus.core.Orchestrator.WAVE_1", set()):
                o = Orchestrator(timeout=10)
                report = await o.run("x.com")
                assert len(report.module_results) == 10
