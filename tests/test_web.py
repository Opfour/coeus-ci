"""Tests for web dashboard endpoints."""

import json
from unittest.mock import patch, AsyncMock
import pytest
from aiohttp.test_utils import TestClient, TestServer
from coeus.web import create_app
from coeus.models import CompanyReport, ModuleResult


@pytest.fixture
async def client():
    app = create_app()
    async with TestClient(TestServer(app)) as client:
        yield client


class TestWebEndpoints:
    @pytest.mark.asyncio
    async def test_index_returns_html(self, client):
        resp = await client.get("/")
        assert resp.status == 200
        text = await resp.text()
        assert "Coeus" in text
        assert "text/html" in resp.content_type

    @pytest.mark.asyncio
    async def test_api_scan_missing_target(self, client):
        resp = await client.post("/api/scan", json={})
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_api_scan_empty_target(self, client):
        resp = await client.post("/api/scan", json={"target": "   "})
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_api_scan_success(self, client):
        report = CompanyReport(target="example.com", company_name="Example")
        report.module_results["whois"] = ModuleResult(
            module_name="whois", success=True, execution_time=0.1,
        )
        report.final_scores = {"stability": 5.0}

        with patch("coeus.web.Orchestrator") as MockOrch:
            instance = MockOrch.return_value
            instance.run = AsyncMock(return_value=report)
            resp = await client.post("/api/scan", json={"target": "example.com"})
            assert resp.status == 200
            data = await resp.json()
            assert data["target"] == "example.com"
            assert "module_results" in data

    @pytest.mark.asyncio
    async def test_api_scan_with_modules(self, client):
        report = CompanyReport(target="x.com")
        with patch("coeus.web.Orchestrator") as MockOrch:
            instance = MockOrch.return_value
            instance.run = AsyncMock(return_value=report)
            resp = await client.post("/api/scan",
                                      json={"target": "x.com", "modules": "whois,dns"})
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_api_scan_stream_missing_target(self, client):
        resp = await client.get("/api/scan/stream")
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_api_scan_stream_success(self, client):
        report = CompanyReport(target="example.com", company_name="Example")
        report.module_results["whois"] = ModuleResult(
            module_name="whois", success=True, execution_time=0.1,
        )
        report.final_scores = {"stability": 5.0}

        with patch("coeus.web.Orchestrator") as MockOrch:
            instance = MockOrch.return_value
            instance.run = AsyncMock(return_value=report)
            resp = await client.get("/api/scan/stream?target=example.com")
            assert resp.status == 200
            assert "text/event-stream" in resp.headers.get("Content-Type", "")
            body = await resp.text()
            assert "event: status" in body
            assert "event: module" in body
            assert "event: complete" in body

    @pytest.mark.asyncio
    async def test_api_scan_with_timeout(self, client):
        report = CompanyReport(target="x.com")
        with patch("coeus.web.Orchestrator") as MockOrch:
            instance = MockOrch.return_value
            instance.run = AsyncMock(return_value=report)
            resp = await client.post("/api/scan",
                                      json={"target": "x.com", "timeout": 10})
            assert resp.status == 200
            MockOrch.assert_called_once_with(timeout=10)

    @pytest.mark.asyncio
    async def test_create_app_has_routes(self):
        app = create_app()
        routes = [r.resource.canonical for r in app.router.routes()
                  if hasattr(r, 'resource') and r.resource]
        assert "/" in routes
        assert "/api/scan" in routes
        assert "/api/scan/stream" in routes
