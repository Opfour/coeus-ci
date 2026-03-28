"""Tests for DNS module."""

from unittest.mock import patch, MagicMock
import pytest
from coeus.modules.dns_mod import DnsModule, _extract_tag


def _mock_mx(host, preference=10):
    r = MagicMock()
    r.exchange = MagicMock()
    r.exchange.__str__ = lambda s: host + "."
    r.preference = preference
    return r


def _mock_txt(text):
    r = MagicMock()
    r.__str__ = lambda s: text
    return r


def _mock_ns(host):
    r = MagicMock()
    r.__str__ = lambda s: host + "."
    return r


class TestDnsModule:
    @pytest.fixture
    def module(self):
        return DnsModule()

    def _make_resolver(self, mx=None, ns=None, txt=None, a=None, dmarc=None):
        """Create a mock resolver with configurable responses per record type."""
        def resolve_side_effect(domain, rdtype):
            if rdtype == "MX" and mx is not None:
                return mx
            if rdtype == "NS" and ns is not None:
                return ns
            if rdtype == "TXT":
                if "_dmarc." in domain and dmarc is not None:
                    return dmarc
                if txt is not None:
                    return txt
            if rdtype == "A" and a is not None:
                return a
            raise Exception("No record")

        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = resolve_side_effect
        mock_resolver.timeout = 10
        mock_resolver.lifetime = 10
        return mock_resolver

    @pytest.mark.asyncio
    async def test_google_workspace(self, module):
        resolver = self._make_resolver(
            mx=[_mock_mx("alt1.aspmx.l.google.com")],
            txt=[_mock_txt("v=spf1 include:_spf.google.com ~all")],
        )
        with patch("dns.resolver.Resolver", return_value=resolver):
            result = await module.execute("x.com", {})
            assert result.data["mail_provider"] == "Google Workspace"

    @pytest.mark.asyncio
    async def test_microsoft_365(self, module):
        resolver = self._make_resolver(
            mx=[_mock_mx("mail.protection.outlook.com")],
        )
        with patch("dns.resolver.Resolver", return_value=resolver):
            result = await module.execute("x.com", {})
            assert result.data["mail_provider"] == "Microsoft 365"

    @pytest.mark.asyncio
    async def test_spf_softfail(self, module):
        resolver = self._make_resolver(
            txt=[_mock_txt("v=spf1 include:_spf.google.com ~all")],
        )
        with patch("dns.resolver.Resolver", return_value=resolver):
            result = await module.execute("x.com", {})
            assert result.data["spf"]["present"] is True
            assert result.data["spf"]["policy"] == "~all"

    @pytest.mark.asyncio
    async def test_spf_hardfail(self, module):
        resolver = self._make_resolver(
            txt=[_mock_txt("v=spf1 include:example.com -all")],
        )
        with patch("dns.resolver.Resolver", return_value=resolver):
            result = await module.execute("x.com", {})
            assert result.data["spf"]["policy"] == "-all"

    @pytest.mark.asyncio
    async def test_spf_plus_all_critical(self, module):
        resolver = self._make_resolver(
            txt=[_mock_txt("v=spf1 +all")],
        )
        with patch("dns.resolver.Resolver", return_value=resolver):
            result = await module.execute("x.com", {})
            crit = [f for f in result.findings if f.severity.value == "critical"]
            assert len(crit) == 1
            assert "all senders" in crit[0].title.lower()

    @pytest.mark.asyncio
    async def test_no_spf(self, module):
        resolver = self._make_resolver(txt=[_mock_txt("google-site-verification=xxx")])
        with patch("dns.resolver.Resolver", return_value=resolver):
            result = await module.execute("x.com", {})
            assert result.data["spf"]["present"] is False
            med = [f for f in result.findings if f.severity.value == "medium"]
            assert any("spf" in f.title.lower() for f in med)

    @pytest.mark.asyncio
    async def test_dmarc_reject(self, module):
        resolver = self._make_resolver(
            dmarc=[_mock_txt("v=DMARC1; p=reject; rua=mailto:dmarc@x.com")],
        )
        with patch("dns.resolver.Resolver", return_value=resolver):
            result = await module.execute("x.com", {})
            assert result.data["dmarc"]["present"] is True
            assert result.data["dmarc"]["policy"] == "reject"

    @pytest.mark.asyncio
    async def test_no_dmarc(self, module):
        resolver = self._make_resolver()
        with patch("dns.resolver.Resolver", return_value=resolver):
            result = await module.execute("x.com", {})
            assert result.data["dmarc"]["present"] is False
            high = [f for f in result.findings if f.severity.value == "high"]
            assert any("dmarc" in f.title.lower() for f in high)

    @pytest.mark.asyncio
    async def test_cdn_detection_cloudflare(self, module):
        resolver = self._make_resolver(
            ns=[_mock_ns("carl.ns.cloudflare.com")],
        )
        with patch("dns.resolver.Resolver", return_value=resolver):
            result = await module.execute("x.com", {})
            assert result.data["cdn_detected"] == "Cloudflare"

    @pytest.mark.asyncio
    async def test_security_score_full(self, module):
        resolver = self._make_resolver(
            txt=[_mock_txt("v=spf1 -all")],
            dmarc=[_mock_txt("v=DMARC1; p=reject")],
        )
        with patch("dns.resolver.Resolver", return_value=resolver):
            result = await module.execute("x.com", {})
            sec = [s for s in result.scores if s.dimension.value == "security"]
            # 5.0 + 1.5(spf) + 2.0(dmarc) + 1.0(reject) = 9.5
            assert sec[0].points == 9.5

    @pytest.mark.asyncio
    async def test_always_succeeds(self, module):
        """DNS module should return _ok even if all queries fail."""
        resolver = self._make_resolver()
        with patch("dns.resolver.Resolver", return_value=resolver):
            result = await module.execute("x.com", {})
            assert result.success is True


class TestExtractTag:
    def test_parses_policy(self):
        assert _extract_tag("v=DMARC1; p=reject; rua=mailto:x", "p") == "reject"

    def test_missing_tag(self):
        assert _extract_tag("v=DMARC1; p=reject", "rua") is None

    def test_first_tag(self):
        assert _extract_tag("v=DMARC1; p=none", "v") == "DMARC1"
