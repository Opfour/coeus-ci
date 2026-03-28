"""Coeus CI - Business Intelligence OSINT"""
__version__ = "0.1.0"

# ── User-configurable defaults ────────────────────────────────────
# Override these here or via CLI flags (e.g. coeus --port 9090 --web)

DEFAULT_WEB_PORT = 8147          # --port: web dashboard port
DEFAULT_TIMEOUT = 30             # --timeout: per-module timeout (seconds)
DEFAULT_HOST = "127.0.0.1"      # bind address for web dashboard
