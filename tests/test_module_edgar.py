"""Tests for SEC EDGAR module."""

from unittest.mock import patch, MagicMock
import pytest
from coeus.modules.edgar import EdgarModule, _fetch_edgar, _extract_financials


class TestEdgarModule:
    @pytest.fixture
    def module(self):
        return EdgarModule()

    def _public_result(self, revenue=2_000_000_000, net_income=400_000_000,
                       filings_count=10, sells=5, buys=10):
        return {
            "is_public": True,
            "cik": "320193",
            "company_name_sec": "Apple Inc.",
            "sic_code": "3571",
            "sic_description": "Electronic Computers",
            "state_of_incorporation": "CA",
            "recent_filings": [{"form": "10-K"}] * filings_count,
            "financials": {"revenue": revenue, "net_income": net_income},
            "insider_trades_90d": {"sells": sells, "buys": buys},
        }

    def _private_result(self):
        return {
            "is_public": False, "cik": None, "company_name_sec": None,
            "sic_code": None, "sic_description": None,
            "state_of_incorporation": None, "recent_filings": [],
            "financials": {}, "insider_trades_90d": {},
        }

    @pytest.mark.asyncio
    async def test_public_high_revenue(self, module):
        with patch("coeus.modules.edgar._fetch_edgar", return_value=self._public_result()):
            ctx = {"company_name": "Apple Inc."}
            result = await module.execute("apple.com", ctx)
            fin = [s for s in result.scores if s.dimension.value == "financial"]
            assert fin[0].points == 9.0
            assert fin[0].weight == 3.0

    @pytest.mark.asyncio
    async def test_public_medium_revenue(self, module):
        with patch("coeus.modules.edgar._fetch_edgar",
                    return_value=self._public_result(revenue=500_000_000)):
            result = await module.execute("x.com", {"company_name": "X"})
            fin = [s for s in result.scores if s.dimension.value == "financial"]
            assert fin[0].points == 7.0

    @pytest.mark.asyncio
    async def test_public_low_revenue(self, module):
        with patch("coeus.modules.edgar._fetch_edgar",
                    return_value=self._public_result(revenue=50_000_000)):
            result = await module.execute("x.com", {"company_name": "X"})
            fin = [s for s in result.scores if s.dimension.value == "financial"]
            assert fin[0].points == 5.0

    @pytest.mark.asyncio
    async def test_private_company(self, module):
        with patch("coeus.modules.edgar._fetch_edgar",
                    return_value=self._private_result()):
            result = await module.execute("x.com", {"company_name": "Priv"})
            assert result.success is True
            assert result.findings == []
            assert result.scores == []

    @pytest.mark.asyncio
    async def test_strong_profit_margin(self, module):
        with patch("coeus.modules.edgar._fetch_edgar",
                    return_value=self._public_result(
                        revenue=1_000_000_000, net_income=200_000_000)):
            result = await module.execute("x.com", {"company_name": "X"})
            info = [f for f in result.findings if "profit margin" in f.title.lower()]
            assert len(info) == 1

    @pytest.mark.asyncio
    async def test_unprofitable(self, module):
        with patch("coeus.modules.edgar._fetch_edgar",
                    return_value=self._public_result(
                        revenue=1_000_000_000, net_income=-50_000_000)):
            result = await module.execute("x.com", {"company_name": "X"})
            med = [f for f in result.findings if "unprofitable" in f.title.lower()]
            assert len(med) == 1
            assert med[0].severity.value == "medium"

    @pytest.mark.asyncio
    async def test_transparency_score(self, module):
        with patch("coeus.modules.edgar._fetch_edgar",
                    return_value=self._public_result()):
            result = await module.execute("x.com", {"company_name": "X"})
            transp = [s for s in result.scores if s.dimension.value == "transparency"]
            assert transp[0].points == 9.0

    @pytest.mark.asyncio
    async def test_stability_many_filings(self, module):
        with patch("coeus.modules.edgar._fetch_edgar",
                    return_value=self._public_result(filings_count=10)):
            result = await module.execute("x.com", {"company_name": "X"})
            stab = [s for s in result.scores if s.dimension.value == "stability"]
            assert stab[0].points == 8.0

    @pytest.mark.asyncio
    async def test_heavy_insider_selling(self, module):
        with patch("coeus.modules.edgar._fetch_edgar",
                    return_value=self._public_result(sells=30, buys=5)):
            result = await module.execute("x.com", {"company_name": "X"})
            insider = [f for f in result.findings if "insider" in f.title.lower()]
            assert len(insider) == 1

    @pytest.mark.asyncio
    async def test_fallback_company_name(self, module):
        with patch("coeus.modules.edgar._fetch_edgar",
                    return_value=self._private_result()) as mock_fetch:
            await module.execute("acme.com", {})
            # Should have been called with "Acme" as fallback
            assert mock_fetch.call_args[0][0] == "Acme"

    @pytest.mark.asyncio
    async def test_lookup_failure(self, module):
        with patch("coeus.modules.edgar._fetch_edgar",
                    side_effect=Exception("network error")):
            result = await module.execute("x.com", {"company_name": "X"})
            assert result.success is False


class TestFetchEdgar:
    def test_company_found(self):
        mock_company = MagicMock()
        mock_company.cik = "320193"
        mock_company.name = "Apple Inc."
        mock_company.sic = "3571"
        mock_company.sic_description = "Electronic Computers"
        mock_company.state_of_incorporation = "CA"

        mock_filing = MagicMock()
        mock_filing.form = "10-K"
        mock_filing.filing_date = "2024-11-01"
        mock_filing.description = "Annual report"
        mock_filings = MagicMock()
        mock_filings.__getitem__ = lambda self, key: [mock_filing][key] if isinstance(key, int) else [mock_filing][:key.stop]
        mock_filings.__iter__ = lambda self: iter([mock_filing])
        mock_company.get_filings.return_value = mock_filings

        mock_company.get_facts.return_value = None

        with patch("edgar.set_identity"), \
             patch("edgar.Company", return_value=mock_company):
            result = _fetch_edgar("Apple Inc.", "apple.com")
            assert result["is_public"] is True
            assert result["cik"] == "320193"
            assert result["company_name_sec"] == "Apple Inc."

    def test_company_not_found(self):
        with patch("edgar.set_identity"), \
             patch("edgar.Company", return_value=None):
            result = _fetch_edgar("Unknown Corp", "x.com")
            assert result["is_public"] is False

    def test_import_error(self):
        with patch("edgar.set_identity", side_effect=ImportError("no edgar")), \
             patch.dict("sys.modules", {"edgar": None}):
            # _fetch_edgar catches all exceptions
            result = _fetch_edgar("X", "x.com")
            assert result["is_public"] is False


class TestExtractFinancials:
    def test_extracts_revenue(self):
        mock_entry = MagicMock()
        mock_entry.value = 394_000_000_000

        mock_concept = MagicMock()
        mock_concept.data = [mock_entry]

        mock_facts = MagicMock()
        def get_side_effect(taxonomy, concept):
            if taxonomy == "us-gaap" and concept == "Revenues":
                return mock_concept
            return None
        mock_facts.get = get_side_effect

        result = _extract_financials(mock_facts)
        assert result["revenue"] == 394_000_000_000

    def test_extracts_net_income_and_assets(self):
        mock_entry = MagicMock()
        mock_entry.value = 100_000_000

        mock_concept = MagicMock()
        mock_concept.data = [mock_entry]

        mock_facts = MagicMock()
        def get_side_effect(taxonomy, concept):
            if concept in ("NetIncomeLoss", "Assets", "Liabilities"):
                return mock_concept
            return None
        mock_facts.get = get_side_effect

        result = _extract_financials(mock_facts)
        assert result["net_income"] == 100_000_000
        assert result["total_assets"] == 100_000_000
        assert result["total_liabilities"] == 100_000_000

    def test_extracts_employees(self):
        mock_entry = MagicMock()
        mock_entry.value = 164000

        mock_concept = MagicMock()
        mock_concept.data = [mock_entry]

        mock_facts = MagicMock()
        def get_side_effect(taxonomy, concept):
            if taxonomy == "dei" and concept == "EntityNumberOfEmployees":
                return mock_concept
            return None
        mock_facts.get = get_side_effect

        result = _extract_financials(mock_facts)
        assert result["employees"] == 164000

    def test_handles_missing_data(self):
        mock_facts = MagicMock()
        mock_facts.get.return_value = None
        result = _extract_financials(mock_facts)
        assert result == {}
