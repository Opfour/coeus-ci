"""Tests for nonprofit module."""

import re
import pytest
from aioresponses import aioresponses
from coeus.modules.nonprofit import NonprofitModule


SEARCH_URL_PATTERN = re.compile(
    r"https://projects\.propublica\.org/nonprofits/api/v2/search\.json\?.*"
)
DETAIL_URL_PATTERN = re.compile(
    r"https://projects\.propublica\.org/nonprofits/api/v2/organizations/\d+\.json"
)

SEARCH_RESPONSE = {
    "organizations": [
        {"ein": 530196605, "name": "American Red Cross",
         "city": "Washington", "state": "DC",
         "ntee_code": "P20", "subsection_code": 3},
        {"ein": 999999999, "name": "Red Cross Society of Something",
         "city": "Chicago", "state": "IL",
         "ntee_code": "P20", "subsection_code": 3},
    ]
}

DETAIL_RESPONSE = {
    "organization": {"ruling_date": "1946-03-01"},
    "filings_with_data": [
        {"totrevenue": 3000000000, "totfuncexpns": 2800000000,
         "totassetsend": 5000000000, "totnetliabastend": 1000000000},
    ],
}


class TestNonprofitModule:
    @pytest.fixture
    def module(self):
        return NonprofitModule()

    @pytest.mark.asyncio
    async def test_found(self, module):
        with aioresponses() as m:
            m.get(SEARCH_URL_PATTERN, payload=SEARCH_RESPONSE)
            m.get(DETAIL_URL_PATTERN, payload=DETAIL_RESPONSE)
            ctx = {"company_name": "American Red Cross"}
            result = await module.execute("redcross.org", ctx)
            assert result.data["is_nonprofit"] is True
            assert result.data["ein"] == 530196605
            assert result.data["revenue"] == 3000000000

    @pytest.mark.asyncio
    async def test_not_found(self, module):
        with aioresponses() as m:
            m.get(SEARCH_URL_PATTERN, payload={"organizations": []})
            result = await module.execute("x.com", {"company_name": "Nonexistent Corp"})
            assert result.data["is_nonprofit"] is False

    @pytest.mark.asyncio
    async def test_fuzzy_match(self, module):
        with aioresponses() as m:
            m.get(SEARCH_URL_PATTERN, payload=SEARCH_RESPONSE)
            m.get(DETAIL_URL_PATTERN, payload=DETAIL_RESPONSE)
            ctx = {"company_name": "Red Cross"}
            result = await module.execute("redcross.org", ctx)
            assert result.data["is_nonprofit"] is True
            assert result.data["name"] == "American Red Cross"

    @pytest.mark.asyncio
    async def test_no_match_above_threshold(self, module):
        resp = {"organizations": [
            {"ein": 111111111, "name": "Totally Unrelated Org",
             "city": "NY", "state": "NY", "ntee_code": "A01", "subsection_code": 3},
        ]}
        with aioresponses() as m:
            m.get(SEARCH_URL_PATTERN, payload=resp)
            result = await module.execute("x.com", {"company_name": "Apple Inc"})
            assert result.data["is_nonprofit"] is False

    @pytest.mark.asyncio
    async def test_high_expense_ratio(self, module):
        detail = {
            "organization": {"ruling_date": "2000-01-01"},
            "filings_with_data": [
                {"totrevenue": 1000000, "totfuncexpns": 980000,
                 "totassetsend": 500000, "totnetliabastend": 100000},
            ],
        }
        with aioresponses() as m:
            m.get(SEARCH_URL_PATTERN, payload=SEARCH_RESPONSE)
            m.get(DETAIL_URL_PATTERN, payload=detail)
            ctx = {"company_name": "American Red Cross"}
            result = await module.execute("redcross.org", ctx)
            med = [f for f in result.findings if "expense ratio" in f.title.lower()]
            assert len(med) == 1

    @pytest.mark.asyncio
    async def test_transparency_with_990(self, module):
        with aioresponses() as m:
            m.get(SEARCH_URL_PATTERN, payload=SEARCH_RESPONSE)
            m.get(DETAIL_URL_PATTERN, payload=DETAIL_RESPONSE)
            ctx = {"company_name": "American Red Cross"}
            result = await module.execute("redcross.org", ctx)
            transp = [s for s in result.scores if s.dimension.value == "transparency"]
            assert transp[0].points == 9.0

    @pytest.mark.asyncio
    async def test_transparency_without_990(self, module):
        detail = {"organization": {}, "filings_with_data": []}
        with aioresponses() as m:
            m.get(SEARCH_URL_PATTERN, payload=SEARCH_RESPONSE)
            m.get(DETAIL_URL_PATTERN, payload=detail)
            ctx = {"company_name": "American Red Cross"}
            result = await module.execute("redcross.org", ctx)
            transp = [s for s in result.scores if s.dimension.value == "transparency"]
            assert transp[0].points == 6.0

    @pytest.mark.asyncio
    async def test_network_error(self, module):
        with aioresponses() as m:
            m.get(SEARCH_URL_PATTERN, exception=ConnectionError("nope"))
            result = await module.execute("x.com", {"company_name": "X"})
            assert result.success is False

    @pytest.mark.asyncio
    async def test_info_finding_registered(self, module):
        with aioresponses() as m:
            m.get(SEARCH_URL_PATTERN, payload=SEARCH_RESPONSE)
            m.get(DETAIL_URL_PATTERN, payload=DETAIL_RESPONSE)
            ctx = {"company_name": "American Red Cross"}
            result = await module.execute("redcross.org", ctx)
            info = [f for f in result.findings if "501(c)" in f.title]
            assert len(info) == 1
