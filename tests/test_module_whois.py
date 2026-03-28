"""Tests for WHOIS module."""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
from coeus.modules.whois_mod import WhoisModule, _first


class TestWhoisModule:
    @pytest.fixture
    def module(self):
        return WhoisModule()

    @pytest.fixture
    def mock_whois_data(self):
        w = MagicMock()
        w.creation_date = datetime(2000, 1, 1, tzinfo=timezone.utc)
        w.expiration_date = datetime(2030, 1, 1, tzinfo=timezone.utc)
        w.registrar = "GoDaddy"
        w.org = "Acme Corp"
        w.name_servers = ["ns1.acme.com", "ns2.acme.com"]
        w.dnssec = "unsigned"
        return w

    @pytest.mark.asyncio
    async def test_successful_lookup(self, module, mock_whois_data):
        with patch("whois.whois") as mock_whois_fn:
            mock_whois_fn.return_value = mock_whois_data
            result = await module.execute("acme.com", {})
            assert result.success is True
            assert result.data["registrar"] == "GoDaddy"
            assert result.data["org"] == "Acme Corp"
            assert result.data["domain_age_years"] > 20

    @pytest.mark.asyncio
    async def test_sets_company_name(self, module, mock_whois_data):
        with patch("whois.whois") as mock_whois_fn:
            mock_whois_fn.return_value = mock_whois_data
            ctx = {}
            await module.execute("acme.com", ctx)
            assert ctx["company_name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_does_not_overwrite_company_name(self, module, mock_whois_data):
        with patch("whois.whois") as mock_whois_fn:
            mock_whois_fn.return_value = mock_whois_data
            ctx = {"company_name": "Existing"}
            await module.execute("acme.com", ctx)
            assert ctx["company_name"] == "Existing"

    @pytest.mark.asyncio
    async def test_domain_age_10plus(self, module, mock_whois_data):
        mock_whois_data.creation_date = datetime(2010, 1, 1, tzinfo=timezone.utc)
        with patch("whois.whois") as mock_whois_fn:
            mock_whois_fn.return_value = mock_whois_data
            result = await module.execute("x.com", {})
            stability = [s for s in result.scores
                         if s.dimension.value == "stability"]
            assert stability[0].points == 9.0

    @pytest.mark.asyncio
    async def test_domain_age_5_years(self, module, mock_whois_data):
        mock_whois_data.creation_date = datetime.now(timezone.utc) - timedelta(days=6*365)
        with patch("whois.whois") as mock_whois_fn:
            mock_whois_fn.return_value = mock_whois_data
            result = await module.execute("x.com", {})
            stability = [s for s in result.scores
                         if s.dimension.value == "stability"]
            assert stability[0].points == 7.0

    @pytest.mark.asyncio
    async def test_domain_age_2_years(self, module, mock_whois_data):
        mock_whois_data.creation_date = datetime.now(timezone.utc) - timedelta(days=3*365)
        with patch("whois.whois") as mock_whois_fn:
            mock_whois_fn.return_value = mock_whois_data
            result = await module.execute("x.com", {})
            stability = [s for s in result.scores
                         if s.dimension.value == "stability"]
            assert stability[0].points == 5.0

    @pytest.mark.asyncio
    async def test_domain_age_new(self, module, mock_whois_data):
        mock_whois_data.creation_date = datetime.now(timezone.utc) - timedelta(days=180)
        with patch("whois.whois") as mock_whois_fn:
            mock_whois_fn.return_value = mock_whois_data
            result = await module.execute("x.com", {})
            stability = [s for s in result.scores
                         if s.dimension.value == "stability"]
            assert stability[0].points == 3.0

    @pytest.mark.asyncio
    async def test_expiring_soon(self, module, mock_whois_data):
        mock_whois_data.expiration_date = datetime.now(timezone.utc) + timedelta(days=60)
        with patch("whois.whois") as mock_whois_fn:
            mock_whois_fn.return_value = mock_whois_data
            result = await module.execute("x.com", {})
            high_findings = [f for f in result.findings
                             if f.severity.value == "high"]
            assert any("expiring" in f.title.lower() for f in high_findings)

    @pytest.mark.asyncio
    async def test_not_expiring_soon(self, module, mock_whois_data):
        with patch("whois.whois") as mock_whois_fn:
            mock_whois_fn.return_value = mock_whois_data
            result = await module.execute("x.com", {})
            assert not any("expiring" in f.title.lower() for f in result.findings)

    @pytest.mark.asyncio
    async def test_privacy_guard(self, module, mock_whois_data):
        mock_whois_data.org = "Domains By Proxy, LLC"
        with patch("whois.whois") as mock_whois_fn:
            mock_whois_fn.return_value = mock_whois_data
            result = await module.execute("x.com", {})
            assert any("privacy" in f.title.lower() for f in result.findings)
            transp = [s for s in result.scores
                      if s.dimension.value == "transparency"]
            assert transp[0].points == 3.0

    @pytest.mark.asyncio
    async def test_public_org_transparency(self, module, mock_whois_data):
        with patch("whois.whois") as mock_whois_fn:
            mock_whois_fn.return_value = mock_whois_data
            result = await module.execute("x.com", {})
            transp = [s for s in result.scores
                      if s.dimension.value == "transparency"]
            assert transp[0].points == 8.0

    @pytest.mark.asyncio
    async def test_lookup_failure(self, module):
        with patch("whois.whois") as mock_whois_fn:
            mock_whois_fn.side_effect = Exception("Connection refused")
            result = await module.execute("bad.com", {})
            assert result.success is False
            assert "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_list_dates(self, module, mock_whois_data):
        d1 = datetime(2005, 1, 1, tzinfo=timezone.utc)
        d2 = datetime(2010, 1, 1, tzinfo=timezone.utc)
        mock_whois_data.creation_date = [d1, d2]
        with patch("whois.whois") as mock_whois_fn:
            mock_whois_fn.return_value = mock_whois_data
            result = await module.execute("x.com", {})
            # Should pick first date (2005)
            assert result.data["domain_age_years"] > 20


class TestFirstHelper:
    def test_list(self):
        assert _first([1, 2, 3]) == 1

    def test_scalar(self):
        assert _first(42) == 42

    def test_none(self):
        assert _first(None) is None
