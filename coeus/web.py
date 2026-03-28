"""Web dashboard — local server for interactive company research."""

import asyncio
import json
from pathlib import Path
from aiohttp import web
from coeus.core import Orchestrator
from coeus.report import TerminalReport

STATIC_DIR = Path(__file__).parent.parent / "templates"


async def index(request):
    """Serve the dashboard page."""
    html = (STATIC_DIR / "dashboard.html").read_text()
    return web.Response(text=html, content_type="text/html")


async def api_scan(request):
    """Run a scan and return JSON results."""
    data = await request.json()
    target = data.get("target", "").strip()
    if not target:
        return web.json_response({"error": "No target provided"}, status=400)

    modules_str = data.get("modules")
    module_filter = ([m.strip() for m in modules_str.split(",")]
                     if modules_str else None)
    timeout = data.get("timeout", 30)

    orchestrator = Orchestrator(timeout=timeout)
    report = await orchestrator.run(target, module_filter=module_filter)

    result = json.loads(report.model_dump_json())
    return web.json_response(result)


async def api_scan_stream(request):
    """Run a scan with Server-Sent Events for live progress."""
    target = request.query.get("target", "").strip()
    if not target:
        return web.json_response({"error": "No target provided"}, status=400)

    resp = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )
    await resp.prepare(request)

    orchestrator = Orchestrator(timeout=30)

    async def send_event(event_type, data):
        msg = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        await resp.write(msg.encode())

    await send_event("status", {"message": "Starting scan...", "target": target})

    report = await orchestrator.run(target)

    # Send module results as they complete
    for name, result in report.module_results.items():
        await send_event("module", {
            "name": name,
            "success": result.success,
            "error": result.error,
            "time": round(result.execution_time, 1),
        })

    # Send final report
    result_json = json.loads(report.model_dump_json())
    await send_event("complete", result_json)

    await resp.write_eof()
    return resp


def create_app():
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_post("/api/scan", api_scan)
    app.router.add_get("/api/scan/stream", api_scan_stream)
    return app


def run_server(host=None, port=None):
    from coeus import DEFAULT_HOST, DEFAULT_WEB_PORT
    host = host or DEFAULT_HOST
    port = port or DEFAULT_WEB_PORT
    app = create_app()
    web.run_app(app, host=host, port=port, print=lambda msg: None)
