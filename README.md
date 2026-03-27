# Coeus CI

*Competitive Intelligence that sees all.*

Named after **Coeus** (SEE-us), the Greek Titan of the inquisitive mind — whose name literally means "querying." CI stands for **Competitive Intelligence**.

A business intelligence and OSINT tool that builds company profiles from public data sources. Give it a company name or domain — get back a scored report covering stability, growth, tech maturity, employee sentiment, and financial health.

## Goals

- **Single command, full picture** — `coeus acme.com` produces a comprehensive company report from public sources
- **Free by default** — every core data source is free or has a free tier. No API keys required to get started
- **Pluggable modules** — each data source is an independent module. Add or remove sources without touching core logic
- **Scored output** — multi-dimensional scorecard, not just raw data. Rate companies across stability, growth, tech stack, hiring signals, and sentiment
- **Multiple output formats** — terminal summary, JSON for piping, and HTML report for sharing

## Data Sources

### Free (no API key needed)
| Source | What it provides |
|--------|-----------------|
| WHOIS | Domain age, registrar, registration dates |
| DNS | MX records, SPF/DMARC, nameservers, CDN detection |
| HTTP headers | Server tech, frameworks, security headers |
| SSL/TLS | Certificate authority, expiry, organization info |
| robots.txt / sitemap | Site structure hints, tech stack clues |
| SEC EDGAR | Public company filings, financials, insider trades |

### Free tier (API key, no cost)
| Source | What it provides |
|--------|-----------------|
| Hunter.io | Email patterns, employee emails, department breakdown |
| BuiltWith | Full tech stack detection (CMS, analytics, frameworks) |
| Crunchbase Basic | Funding rounds, investors, company description |
| GitHub | Open source activity, team size, tech preferences |
| Shodan (limited) | Open ports, services, infrastructure |

### Paid (optional upgrades)
| Source | What it provides |
|--------|-----------------|
| LinkedIn (via proxycurl/similar) | Employee count trends, hiring velocity, department breakdown |
| Glassdoor | Employee ratings, salary data, sentiment |
| Crunchbase Pro | Full financial data, acquisitions, competitors |
| ZoomInfo / Apollo | Contact data, org charts, intent signals |

## Output

```
$ coeus acme.com

ACME Corporation
================
Domain: acme.com (registered 2008, 16 years old)
Industry: SaaS / Developer Tools
Employees: ~250 (estimated)
Funding: Series C, $45M total raised

Scorecard
---------
Stability:    [========--]  8/10  Mature domain, consistent DNS, funded
Growth:       [=======---]  7/10  12 open roles, 3 engineering
Tech Maturity:[=========-]  9/10  Modern stack, active GitHub, good security headers
Sentiment:    [======----]  6/10  Mixed Glassdoor reviews (3.8/5)
Financial:    [=======---]  7/10  Series C, 18mo runway estimated

Risk Flags
----------
- No DMARC policy (email spoofing risk)
- 2 critical CVEs on detected web server version
- High executive turnover (3 C-suite changes in 12mo)

Full report: ./reports/acme.com.html
```

## Architecture

```
coeus-ci/
├── coeus/
│   ├── __init__.py
│   ├── cli.py              # CLI entry point
│   ├── core.py             # Orchestrator: runs modules, aggregates, scores
│   ├── scorer.py           # Multi-dimensional scoring engine
│   ├── report.py           # Output formatters (terminal, JSON, HTML)
│   └── modules/
│       ├── __init__.py
│       ├── base.py         # Base module interface
│       ├── whois.py        # WHOIS lookup
│       ├── dns.py          # DNS records + CDN/mail detection
│       ├── headers.py      # HTTP header analysis
│       ├── ssl.py          # TLS certificate info
│       ├── tech.py         # Tech stack detection
│       ├── edgar.py        # SEC EDGAR filings
│       ├── hunter.py       # Hunter.io email intelligence
│       ├── builtwith.py    # BuiltWith tech detection
│       ├── crunchbase.py   # Crunchbase company data
│       ├── github.py       # GitHub org/repo analysis
│       └── shodan.py       # Shodan infrastructure scan
├── templates/
│   └── report.html         # HTML report template
├── tests/
│   └── ...
├── setup.sh                # One-time setup (venv, dependencies)
├── requirements.txt
├── LICENSE                  # AGPL-3.0
└── README.md
```

## Tech Stack

- **Python 3.10+** — async HTTP for parallel module execution
- **aiohttp** — async requests to multiple data sources simultaneously
- **click** — CLI framework
- **Jinja2** — HTML report templates
- **No database** — stateless tool, reports saved as files

## Roadmap

### v0.1 — Foundation
- [ ] Project scaffolding, CLI skeleton
- [ ] WHOIS module
- [ ] DNS module
- [ ] HTTP headers module
- [ ] SSL/TLS module
- [ ] Basic terminal output

### v0.2 — Intelligence
- [ ] Tech stack detection (robots.txt, meta tags, headers)
- [ ] SEC EDGAR module
- [ ] GitHub org analysis
- [ ] Multi-dimensional scoring engine
- [ ] JSON output format

### v0.3 — API Integrations
- [ ] Hunter.io module
- [ ] BuiltWith module
- [ ] Crunchbase module
- [ ] Shodan module
- [ ] HTML report generation

### v0.4 — Polish
- [ ] Async parallel module execution
- [ ] Caching layer (don't re-fetch within 24h)
- [ ] Comparison mode (`coeus acme.com vs competitor.com`)
- [ ] Batch mode (`coeus --file targets.txt`)
- [ ] Rate limiting and retry logic

## License

AGPL-3.0 — see [LICENSE](LICENSE) for details.
