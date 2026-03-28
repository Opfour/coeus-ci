# Coeus CI

*Competitive Intelligence that sees all.*

Named after **Coeus** (SEE-us), the Greek Titan of the inquisitive mind — whose name literally means "querying." CI stands for **Competitive Intelligence**.

A business intelligence OSINT tool that builds company profiles from free public data sources. Give it a domain — get back a scored report covering stability, growth, tech maturity, financial health, security posture, and transparency.

## Quick Start

```bash
# Clone and install
git clone https://github.com/Opfour/coeus-ci.git
cd coeus-ci
./setup.sh          # creates venv, installs everything

# Activate the environment
source venv/bin/activate

# Run a scan
coeus apple.com

# Compare companies
coeus apple.com microsoft.com

# Export HTML report
coeus apple.com --html

# Launch web dashboard
coeus --web
```

## Usage

```
coeus [OPTIONS] [TARGETS]...

Options:
  --json                 Output as JSON
  --html                 Save HTML report to ./reports/
  -m, --modules TEXT     Comma-separated module list (e.g., whois,dns,edgar)
  -t, --timeout INTEGER  Per-module timeout in seconds (default: 30)
  --web                  Launch interactive web dashboard
  --port INTEGER         Web dashboard port (default: 8147)
  --help                 Show this message and exit
```

### Examples

```bash
# Single target
coeus acme.com

# JSON output (pipe to jq, save to file, etc.)
coeus acme.com --json

# Run only specific modules
coeus acme.com --modules whois,dns,ssl

# Side-by-side comparison
coeus apple.com microsoft.com

# HTML report saved to ./reports/
coeus apple.com --html

# Web dashboard on default port
coeus --web

# Web dashboard on custom port
coeus --web --port 9090
```

## Configuration

Default settings are defined in one place for easy modification:

**`coeus/__init__.py`**
```python
DEFAULT_WEB_PORT = 8147          # --port: web dashboard port
DEFAULT_TIMEOUT = 30             # --timeout: per-module timeout (seconds)
DEFAULT_HOST = "127.0.0.1"      # bind address for web dashboard
```

Change these values to set new defaults for your environment. CLI flags (`--port`, `--timeout`) override these on a per-run basis.

## Data Sources (v0.1)

All modules are **free with no API key required**.

| Module | Source | What it provides |
|--------|--------|-----------------|
| `whois` | WHOIS records | Domain age, registrar, org name, creation/expiry dates |
| `dns` | DNS queries | MX, NS, SPF, DMARC, mail provider, CDN detection |
| `headers` | HTTP headers | Server tech, security headers (HSTS, CSP, etc.) |
| `ssl` | TLS certificate | Certificate org, CA, expiry, SANs |
| `tech` | robots.txt, sitemap, HTML | CMS detection, framework signatures, security.txt |
| `edgar` | SEC EDGAR | Public filings, revenue, net income, assets, employees |
| `nonprofit` | ProPublica API | 501(c)(3) status, Form 990 data, revenue, assets |
| `dba` | OpenCorporates | DBA/business registration, entity type, filing status |

## Scoring

Each target is scored across six dimensions (0-10):

| Dimension | Measures | Fed by |
|-----------|----------|--------|
| **Stability** | How established the organization is | whois, ssl, edgar |
| **Growth** | Expansion signals | edgar, tech |
| **Tech Maturity** | Modern infrastructure and stack | dns, headers, tech |
| **Financial** | Financial health indicators | edgar, nonprofit |
| **Security** | Security posture and hygiene | dns, headers, ssl, tech |
| **Transparency** | Public disclosure and accountability | edgar, nonprofit, whois |

## Output Formats

- **Terminal** — Rich-formatted scorecard with colored bars, findings, module details
- **JSON** (`--json`) — Full Pydantic model dump for piping or integration
- **HTML** (`--html`) — Self-contained dark-theme report saved to `./reports/`
- **Web Dashboard** (`--web`) — Interactive browser UI with live scan progress

## Architecture

```
coeus-ci/
├── coeus/
│   ├── __init__.py          # Version + configurable defaults (port, timeout, host)
│   ├── __main__.py          # python -m coeus entry
│   ├── cli.py               # Click CLI with comparison mode
│   ├── core.py              # Two-wave async orchestrator
│   ├── models.py            # Pydantic data models
│   ├── scorer.py            # Weighted scoring engine
│   ├── report.py            # Terminal, JSON, HTML formatters
│   ├── matching.py          # Fuzzy company name matching
│   ├── web.py               # aiohttp web dashboard server
│   └── modules/
│       ├── base.py          # ABC base class for modules
│       ├── whois_mod.py     # WHOIS lookup
│       ├── dns_mod.py       # DNS analysis
│       ├── headers.py       # HTTP header analysis
│       ├── ssl_mod.py       # TLS certificate inspection
│       ├── tech.py          # Tech stack detection
│       ├── edgar.py         # SEC EDGAR filings
│       ├── nonprofit.py     # 501(c)(3) / ProPublica
│       └── dba.py           # DBA / OpenCorporates
├── templates/
│   ├── dashboard.html       # Web dashboard SPA
│   └── report.html          # Jinja2 HTML report template
├── setup.sh                 # One-time setup script
├── pyproject.toml           # Python packaging
├── LICENSE                  # AGPL-3.0
└── README.md
```

### How it works

1. **Wave 1** — WHOIS and SSL run first to identify the company name
2. **Wave 2** — All other modules run in parallel using the company name from Wave 1
3. **Scoring** — Each module contributes weighted scores to the six dimensions
4. **Report** — Results are aggregated into a single scored report

## FAQ

### How do I change the default web dashboard port?

Edit `coeus/__init__.py` and change `DEFAULT_WEB_PORT`, or use the `--port` flag:
```bash
coeus --web --port 9090
```

### How do I change the default timeout?

Edit `coeus/__init__.py` and change `DEFAULT_TIMEOUT`, or use the `--timeout` flag:
```bash
coeus apple.com --timeout 60
```

### Do I need any API keys?

No. All v0.1 modules use free public data sources with no API keys required.

### Why does EDGAR show 0.0 for some companies?

The EDGAR module only finds data for SEC-registered public companies. Private companies, nonprofits, and foreign entities won't have EDGAR data — this is expected, not an error.

### Why does the nonprofit module sometimes match the wrong organization?

Common company names (like "Apple") can match small nonprofits with similar names. Fuzzy matching reduces false positives but very generic names are inherently ambiguous. The `--modules` flag lets you skip modules that aren't relevant.

### Can I run only specific modules?

Yes:
```bash
coeus apple.com --modules whois,dns,ssl
```

### How do I add a new module?

1. Create a new file in `coeus/modules/` extending `BaseModule`
2. Implement the `execute(target, context)` method
3. Register it in `coeus/modules/__init__.py`

## Roadmap

### v0.1 — Foundation (current)
- [x] 8-module intelligence pipeline (whois, dns, headers, ssl, tech, edgar, nonprofit, dba)
- [x] Six-dimension scoring engine
- [x] Terminal, JSON, and HTML output
- [x] Web dashboard with live scan progress
- [x] Comparison mode for multiple targets
- [x] Fuzzy company name matching

### v0.2 — Expansion
- [ ] Caching layer (don't re-fetch within 24h)
- [ ] Batch mode (`coeus --file targets.txt`)
- [ ] Rate limiting and retry logic
- [ ] API key integration for premium data sources
- [ ] Hunter.io, BuiltWith, Crunchbase, GitHub, Shodan modules

### v0.3 — Polish
- [ ] PDF report export
- [ ] Historical tracking (compare scans over time)
- [ ] Plugin system for community modules
- [ ] CI/CD integration (exit codes based on score thresholds)

## License

AGPL-3.0 — see [LICENSE](LICENSE) for details.
