"""Tests for tech stack detection module."""

import pytest
from aioresponses import aioresponses
from coeus.modules.tech import TechModule, _parse_disallowed


class TestTechModule:
    @pytest.fixture
    def module(self):
        return TechModule()

    @pytest.mark.asyncio
    async def test_wordpress_from_robots(self, module):
        with aioresponses() as m:
            m.get("https://x.com/robots.txt", status=200,
                   body="User-agent: *\nDisallow: /wp-admin/\nDisallow: /wp-includes/")
            m.get("https://x.com/sitemap.xml", status=404)
            m.get("https://x.com/.well-known/security.txt", status=404)
            m.get("https://x.com", status=200, body="<html></html>")
            result = await module.execute("x.com", {})
            assert result.data["cms_detected"] == "WordPress"

    @pytest.mark.asyncio
    async def test_wordpress_from_meta(self, module):
        html = '<html><head><meta name="generator" content="WordPress 6.4"></head></html>'
        with aioresponses() as m:
            m.get("https://x.com/robots.txt", status=404)
            m.get("https://x.com/sitemap.xml", status=404)
            m.get("https://x.com/.well-known/security.txt", status=404)
            m.get("https://x.com", status=200, body=html)
            result = await module.execute("x.com", {})
            assert result.data["cms_detected"] == "WordPress"
            assert "WordPress 6.4" in result.data["meta_generator"]

    @pytest.mark.asyncio
    async def test_sitemap_url_count(self, module):
        sitemap = "<urlset><url><loc>http://x.com/a</loc></url><url><loc>http://x.com/b</loc></url></urlset>"
        with aioresponses() as m:
            m.get("https://x.com/robots.txt", status=404)
            m.get("https://x.com/sitemap.xml", status=200, body=sitemap)
            m.get("https://x.com/.well-known/security.txt", status=404)
            m.get("https://x.com", status=200, body="<html></html>")
            result = await module.execute("x.com", {})
            assert result.data["sitemap_exists"] is True
            assert result.data["sitemap_url_count"] == 2

    @pytest.mark.asyncio
    async def test_security_txt_present(self, module):
        with aioresponses() as m:
            m.get("https://x.com/robots.txt", status=404)
            m.get("https://x.com/sitemap.xml", status=404)
            m.get("https://x.com/.well-known/security.txt", status=200,
                   body="Contact: security@x.com\nExpires: 2030-01-01")
            m.get("https://x.com", status=200, body="<html></html>")
            result = await module.execute("x.com", {})
            assert result.data["security_txt_exists"] is True
            sec = [s for s in result.scores if s.dimension.value == "security"]
            assert sec[0].points == 8.0

    @pytest.mark.asyncio
    async def test_no_security_txt(self, module):
        with aioresponses() as m:
            m.get("https://x.com/robots.txt", status=404)
            m.get("https://x.com/sitemap.xml", status=404)
            m.get("https://x.com/.well-known/security.txt", status=404)
            m.get("https://x.com", status=200, body="<html></html>")
            result = await module.execute("x.com", {})
            low = [f for f in result.findings if "security.txt" in f.title.lower()]
            assert len(low) == 1

    @pytest.mark.asyncio
    async def test_large_sitemap_growth_score(self, module):
        locs = "<url><loc>http://x.com/p</loc></url>" * 1500
        sitemap = f"<urlset>{locs}</urlset>"
        with aioresponses() as m:
            m.get("https://x.com/robots.txt", status=404)
            m.get("https://x.com/sitemap.xml", status=200, body=sitemap)
            m.get("https://x.com/.well-known/security.txt", status=404)
            m.get("https://x.com", status=200, body="<html></html>")
            result = await module.execute("x.com", {})
            growth = [s for s in result.scores if s.dimension.value == "growth"]
            assert growth[0].points == 8.0

    @pytest.mark.asyncio
    async def test_all_endpoints_fail_gracefully(self, module):
        """When individual endpoints fail, module still succeeds with empty data."""
        with aioresponses() as m:
            m.get("https://x.com/robots.txt", status=500)
            m.get("https://x.com/sitemap.xml", status=500)
            m.get("https://x.com/.well-known/security.txt", status=500)
            m.get("https://x.com", status=500)
            result = await module.execute("x.com", {})
            assert result.success is True
            assert result.data["cms_detected"] is None


class TestParseDisallowed:
    def test_basic(self):
        text = "User-agent: *\nDisallow: /admin/\nDisallow: /private/\nAllow: /public/"
        paths = _parse_disallowed(text)
        assert "/admin/" in paths
        assert "/private/" in paths
        assert "/public/" not in paths

    def test_empty(self):
        assert _parse_disallowed("") == []

    def test_no_disallow(self):
        assert _parse_disallowed("User-agent: *\nAllow: /") == []
