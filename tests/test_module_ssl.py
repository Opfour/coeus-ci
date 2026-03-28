"""Tests for SSL/TLS module."""

from unittest.mock import patch
import pytest
from coeus.modules.ssl_mod import SslModule


def _make_cert(org="Apple Inc.", issuer="DigiCert", not_after="Jan  1 00:00:00 2027 GMT",
               sans=None):
    cert = {
        "subject": [[("organizationName", org)], [("commonName", "apple.com")]],
        "issuer": [[("organizationName", issuer)]],
        "notBefore": "Jan  1 00:00:00 2024 GMT",
        "notAfter": not_after,
        "subjectAltName": [(("DNS", s) if isinstance(s, str) else s) for s in (sans or ["apple.com"])],
        "serialNumber": "ABC123",
    }
    return cert


class TestSslModule:
    @pytest.fixture
    def module(self):
        return SslModule()

    @pytest.mark.asyncio
    async def test_valid_cert(self, module):
        cert = _make_cert()
        with patch("coeus.modules.ssl_mod._get_cert", return_value=cert):
            result = await module.execute("apple.com", {})
            assert result.success is True
            assert result.data["subject_org"] == "Apple Inc."
            assert result.data["issuer_org"] == "DigiCert"
            sec = [s for s in result.scores if s.dimension.value == "security"]
            assert sec[0].points == 9.0

    @pytest.mark.asyncio
    async def test_expired_cert(self, module):
        cert = _make_cert(not_after="Jan  1 00:00:00 2020 GMT")
        with patch("coeus.modules.ssl_mod._get_cert", return_value=cert):
            result = await module.execute("x.com", {})
            crit = [f for f in result.findings if f.severity.value == "critical"]
            assert any("expired" in f.title.lower() for f in crit)
            sec = [s for s in result.scores if s.dimension.value == "security"]
            assert sec[0].points == 1.0

    @pytest.mark.asyncio
    async def test_expiring_soon(self, module):
        from datetime import datetime, timezone, timedelta
        soon = (datetime.now(timezone.utc) + timedelta(days=15)).strftime("%b %d %H:%M:%S %Y GMT")
        cert = _make_cert(not_after=soon)
        with patch("coeus.modules.ssl_mod._get_cert", return_value=cert):
            result = await module.execute("x.com", {})
            high = [f for f in result.findings if f.severity.value == "high"]
            assert any("expiring" in f.title.lower() for f in high)
            sec = [s for s in result.scores if s.dimension.value == "security"]
            assert sec[0].points == 5.0

    @pytest.mark.asyncio
    async def test_sets_company_name(self, module):
        cert = _make_cert(org="Microsoft Corporation")
        with patch("coeus.modules.ssl_mod._get_cert", return_value=cert):
            ctx = {}
            await module.execute("microsoft.com", ctx)
            assert ctx["company_name"] == "Microsoft Corporation"

    @pytest.mark.asyncio
    async def test_no_overwrite_company_name(self, module):
        cert = _make_cert(org="Cert Org")
        with patch("coeus.modules.ssl_mod._get_cert", return_value=cert):
            ctx = {"company_name": "Existing"}
            await module.execute("x.com", ctx)
            assert ctx["company_name"] == "Existing"

    @pytest.mark.asyncio
    async def test_wildcard_detection(self, module):
        cert = _make_cert(sans=["*.example.com", "example.com"])
        with patch("coeus.modules.ssl_mod._get_cert", return_value=cert):
            result = await module.execute("example.com", {})
            assert result.data["is_wildcard"] is True

    @pytest.mark.asyncio
    async def test_san_count(self, module):
        cert = _make_cert(sans=["a.com", "b.com", "c.com"])
        with patch("coeus.modules.ssl_mod._get_cert", return_value=cert):
            result = await module.execute("x.com", {})
            assert result.data["san_count"] == 3

    @pytest.mark.asyncio
    async def test_connection_failure(self, module):
        with patch("coeus.modules.ssl_mod._get_cert", side_effect=Exception("timeout")):
            result = await module.execute("bad.com", {})
            assert result.success is False

    @pytest.mark.asyncio
    async def test_no_cert(self, module):
        with patch("coeus.modules.ssl_mod._get_cert", return_value=None):
            result = await module.execute("x.com", {})
            assert result.success is False

    @pytest.mark.asyncio
    async def test_issuer_stability_score(self, module):
        cert = _make_cert(issuer="DigiCert Inc")
        with patch("coeus.modules.ssl_mod._get_cert", return_value=cert):
            result = await module.execute("x.com", {})
            stab = [s for s in result.scores if s.dimension.value == "stability"]
            assert stab[0].points == 7.0
