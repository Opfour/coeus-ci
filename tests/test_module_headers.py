"""Tests for HTTP headers module."""

import pytest
from aioresponses import aioresponses
from coeus.modules.headers import HeadersModule


class TestHeadersModule:
    @pytest.fixture
    def module(self):
        return HeadersModule()

    def _all_security_headers(self):
        return {
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self'",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Permissions-Policy": "camera=()",
        }

    @pytest.mark.asyncio
    async def test_all_security_headers(self, module):
        with aioresponses() as m:
            m.get("https://x.com", status=200, headers=self._all_security_headers())
            m.get("http://x.com", status=301, headers={"Location": "https://x.com"})
            result = await module.execute("x.com", {})
            assert result.data["security_header_count"] == 5
            # No "missing" finding
            assert not any("missing" in f.title.lower() for f in result.findings)

    @pytest.mark.asyncio
    async def test_no_security_headers(self, module):
        with aioresponses() as m:
            m.get("https://x.com", status=200, headers={"Server": "nginx"})
            m.get("http://x.com", status=200)
            result = await module.execute("x.com", {})
            assert result.data["security_header_count"] == 0
            med = [f for f in result.findings if f.severity.value == "medium"]
            assert len(med) >= 1  # missing headers + no redirect

    @pytest.mark.asyncio
    async def test_partial_security_headers(self, module):
        headers = {
            "Strict-Transport-Security": "max-age=31536000",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
        }
        with aioresponses() as m:
            m.get("https://x.com", status=200, headers=headers)
            m.get("http://x.com", status=301, headers={"Location": "https://x.com"})
            result = await module.execute("x.com", {})
            assert result.data["security_header_count"] == 3

    @pytest.mark.asyncio
    async def test_server_detection(self, module):
        with aioresponses() as m:
            m.get("https://x.com", status=200, headers={"Server": "nginx/1.25"})
            m.get("http://x.com", status=200)
            result = await module.execute("x.com", {})
            assert result.data["server"] == "nginx/1.25"

    @pytest.mark.asyncio
    async def test_powered_by(self, module):
        with aioresponses() as m:
            m.get("https://x.com", status=200, headers={"X-Powered-By": "Express"})
            m.get("http://x.com", status=200)
            result = await module.execute("x.com", {})
            assert result.data["powered_by"] == "Express"

    @pytest.mark.asyncio
    async def test_https_redirect(self, module):
        with aioresponses() as m:
            m.get("https://x.com", status=200, headers={})
            m.get("http://x.com", status=301, headers={"Location": "https://x.com/"})
            result = await module.execute("x.com", {})
            assert result.data["https_redirect"] is True

    @pytest.mark.asyncio
    async def test_no_https_redirect(self, module):
        with aioresponses() as m:
            m.get("https://x.com", status=200, headers={})
            m.get("http://x.com", status=200)
            result = await module.execute("x.com", {})
            assert result.data["https_redirect"] is False
            med = [f for f in result.findings if "redirect" in f.title.lower()]
            assert len(med) == 1

    @pytest.mark.asyncio
    async def test_connection_failure(self, module):
        with aioresponses() as m:
            m.get("https://x.com", exception=ConnectionError("nope"))
            result = await module.execute("x.com", {})
            assert result.success is False

    @pytest.mark.asyncio
    async def test_security_score_all_headers_plus_redirect(self, module):
        with aioresponses() as m:
            m.get("https://x.com", status=200, headers=self._all_security_headers())
            m.get("http://x.com", status=301, headers={"Location": "https://x.com"})
            result = await module.execute("x.com", {})
            sec = [s for s in result.scores if s.dimension.value == "security"]
            # (5/5)*8 + 2 + 1(redirect) = 11, capped to 10.0
            assert sec[0].points == 10.0

    @pytest.mark.asyncio
    async def test_tech_maturity_hsts_csp(self, module):
        headers = {
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self'",
        }
        with aioresponses() as m:
            m.get("https://x.com", status=200, headers=headers)
            m.get("http://x.com", status=200)
            result = await module.execute("x.com", {})
            tech = [s for s in result.scores if s.dimension.value == "tech_maturity"]
            # 5 + 2(hsts) + 2(csp) = 9.0
            assert tech[0].points == 9.0
