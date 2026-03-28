"""Tests for DBA / business registration module."""

import re
import pytest
from aioresponses import aioresponses
from coeus.modules.dba import DbaModule

OPENCORP_SEARCH = re.compile(r"https://api\.opencorporates\.com/v0\.4/companies/search\?.*")


API_RESPONSE = {
    "results": {
        "companies": [
            {"company": {
                "name": "Apple Inc",
                "company_type": "Corporation",
                "jurisdiction_code": "us_ca",
                "company_number": "C0806592",
                "current_status": "Active",
                "incorporation_date": "1977-01-03",
                "registered_address_in_full": "Cupertino, CA",
            }},
            {"company": {
                "name": "Apple Seeds Inc",
                "company_type": "LLC",
                "jurisdiction_code": "us_ny",
                "company_number": "12345",
                "current_status": "Active",
                "incorporation_date": "2020-06-01",
            }},
        ]
    }
}


class TestDbaModule:
    @pytest.fixture
    def module(self):
        return DbaModule()

    @pytest.mark.asyncio
    async def test_found_via_api(self, module):
        with aioresponses() as m:
            m.get(OPENCORP_SEARCH, payload=API_RESPONSE)
            ctx = {"company_name": "Apple Inc"}
            result = await module.execute("apple.com", ctx)
            assert result.data["found"] is True
            assert result.data["business_type"] == "Corporation"
            assert result.data["jurisdiction"] == "US_CA"
            assert result.data["status"] == "Active"

    @pytest.mark.asyncio
    async def test_active_status_scoring(self, module):
        with aioresponses() as m:
            m.get(OPENCORP_SEARCH, payload=API_RESPONSE)
            ctx = {"company_name": "Apple Inc"}
            result = await module.execute("apple.com", ctx)
            stab = [s for s in result.scores if s.dimension.value == "stability"]
            assert stab[0].points == 7.0

    @pytest.mark.asyncio
    async def test_dissolved_status(self, module):
        resp = {"results": {"companies": [{"company": {
            "name": "Dead Corp",
            "company_type": "LLC",
            "jurisdiction_code": "us_de",
            "company_number": "99999",
            "current_status": "Dissolved",
            "incorporation_date": "2010-01-01",
        }}]}}
        with aioresponses() as m:
            m.get(OPENCORP_SEARCH, payload=resp)
            ctx = {"company_name": "Dead Corp"}
            result = await module.execute("dead.com", ctx)
            high = [f for f in result.findings if f.severity.value == "high"]
            assert any("dissolved" in f.title.lower() for f in high)
            stab = [s for s in result.scores if s.dimension.value == "stability"]
            assert stab[0].points == 2.0

    @pytest.mark.asyncio
    async def test_transparency_score(self, module):
        with aioresponses() as m:
            m.get(OPENCORP_SEARCH, payload=API_RESPONSE)
            ctx = {"company_name": "Apple Inc"}
            result = await module.execute("apple.com", ctx)
            transp = [s for s in result.scores if s.dimension.value == "transparency"]
            assert transp[0].points == 7.0

    @pytest.mark.asyncio
    async def test_recently_incorporated(self, module):
        resp = {"results": {"companies": [{"company": {
            "name": "Newco Inc",
            "company_type": "LLC",
            "jurisdiction_code": "us_de",
            "company_number": "11111",
            "current_status": "Active",
            "incorporation_date": "2026-01-01",
        }}]}}
        with aioresponses() as m:
            m.get(OPENCORP_SEARCH, payload=resp)
            ctx = {"company_name": "Newco Inc"}
            result = await module.execute("newco.com", ctx)
            med = [f for f in result.findings if "recently" in f.title.lower()]
            assert len(med) == 1

    @pytest.mark.asyncio
    async def test_no_results(self, module):
        with aioresponses() as m:
            m.get(OPENCORP_SEARCH, payload={"results": {"companies": []}})
            result = await module.execute("x.com", {"company_name": "Nonexistent"})
            assert result.data["found"] is False

    @pytest.mark.asyncio
    async def test_scrape_fallback(self, module):
        import re as re_mod
        html = '''<div class="company_search_result">
            <a href="/companies/us_ca/123">Scraped Corp</a>
        </div>'''
        scrape_pattern = re_mod.compile(r"https://opencorporates\.com/companies\?.*")
        with aioresponses() as m:
            m.get(OPENCORP_SEARCH, status=403)
            m.get(scrape_pattern, status=200, body=html)
            result = await module.execute("test.com", {"company_name": "Test Corp"})
            assert result.data["found"] is True
            assert result.data["source"] == "OpenCorporates (web)"

    @pytest.mark.asyncio
    async def test_network_error(self, module):
        with aioresponses() as m:
            m.get(OPENCORP_SEARCH, exception=ConnectionError("timeout"))
            result = await module.execute("x.com", {"company_name": "X"})
            assert result.success is False

    @pytest.mark.asyncio
    async def test_info_finding_business_type(self, module):
        with aioresponses() as m:
            m.get(OPENCORP_SEARCH, payload=API_RESPONSE)
            ctx = {"company_name": "Apple Inc"}
            result = await module.execute("apple.com", ctx)
            info = [f for f in result.findings if "registered as" in f.title.lower()]
            assert len(info) == 1
            assert "Corporation" in info[0].title
