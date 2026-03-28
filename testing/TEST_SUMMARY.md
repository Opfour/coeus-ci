# Coeus CI - Test Summary Report

**Date:** 2026-03-27
**Version:** 0.1.0
**Python:** 3.13.7
**Test Runner:** pytest 9.0.2 + pytest-asyncio 1.3.0 + pytest-cov 7.1.0

---

## Results Overview

| Metric | Value |
|--------|-------|
| Total tests | 220 |
| Passed | 220 |
| Failed | 0 |
| Warnings | 4 (non-blocking deprecation notices) |
| Coverage | **94.23%** |
| Coverage threshold | 85% |
| Execution time | ~2.2 seconds |
| **Grade** | **PASS** |

### Pass/Fail Criteria

| Gate | Requirement | Actual | Status |
|------|-------------|--------|--------|
| All tests pass | 0 failures | 0 failures | PASS |
| Overall coverage | >= 85% | 94.23% | PASS |
| Critical path coverage | >= 95% | models 100%, core 100%, scorer 100%, cli 95% | PASS |
| Medium priority coverage | >= 80% | all modules 87-97% | PASS |
| Minor priority coverage | >= 70% | report 99%, web 90% | PASS |
| No file below 85% | floor check | lowest is tech.py at 87% | PASS |

---

## Coverage by File

| File | Statements | Missed | Coverage |
|------|-----------|--------|----------|
| `coeus/__init__.py` | 4 | 0 | 100% |
| `coeus/cli.py` | 198 | 10 | 95% |
| `coeus/core.py` | 49 | 0 | 100% |
| `coeus/matching.py` | 38 | 0 | 100% |
| `coeus/models.py` | 42 | 0 | 100% |
| `coeus/modules/__init__.py` | 9 | 0 | 100% |
| `coeus/modules/base.py` | 18 | 1 | 94% |
| `coeus/modules/dba.py` | 79 | 7 | 91% |
| `coeus/modules/dns_mod.py` | 96 | 3 | 97% |
| `coeus/modules/edgar.py` | 104 | 11 | 89% |
| `coeus/modules/headers.py` | 50 | 2 | 96% |
| `coeus/modules/nonprofit.py` | 67 | 5 | 93% |
| `coeus/modules/ssl_mod.py` | 56 | 6 | 89% |
| `coeus/modules/tech.py` | 89 | 12 | 87% |
| `coeus/modules/whois_mod.py` | 54 | 4 | 93% |
| `coeus/report.py` | 138 | 1 | 99% |
| `coeus/scorer.py` | 19 | 0 | 100% |
| `coeus/web.py` | 52 | 5 | 90% |
| **TOTAL** | **1162** | **67** | **94%** |

---

## Test Files and Test Counts

### 1. `tests/test_models.py` (15 tests)
Validates all Pydantic data models used across the application.

- **Severity enum** — verifies all 5 values (info, low, medium, high, critical)
- **ScoreDimension enum** — verifies all 6 dimensions (stability, growth, tech_maturity, financial, security, transparency)
- **Finding model** — defaults, full construction, JSON round-trip
- **ScoreContribution model** — default weight, all fields
- **ModuleResult model** — success/failure states, default factories
- **CompanyReport model** — defaults, serialization round-trip, model_dump JSON mode

### 2. `tests/test_scorer.py` (8 tests)
Tests the weighted-average scoring engine.

- Empty report returns no scores
- Single contribution passes through correctly
- Weighted average computed for same dimension
- Multiple dimensions scored independently
- Failed modules skipped in scoring
- All-failed report returns empty scores
- Score rounding to 1 decimal
- All six scoring dimensions handled

### 3. `tests/test_matching.py` (16 tests)
Tests fuzzy company name matching (Jaccard token similarity).

- **normalize()** — strips corporate suffixes (Inc, LLC, Corp, Ltd), punctuation, lowercases
- **name_similarity()** — identical names, suffix variations, completely different, partial overlap, empty inputs
- **is_match()** — above/below threshold, substring matching, exact match
- **best_match()** — finds closest candidate, respects threshold, handles empty list, custom name key, skips empty names

### 4. `tests/test_core.py` (8 tests)
Tests the async orchestrator (two-wave execution, concurrency, timeouts).

- Runs all registered modules
- Module filter restricts which modules run
- Timeout handling (modules exceeding limit return failure)
- Exception handling (crashing modules don't kill the scan)
- Context propagation between waves (Wave 1 results available to Wave 2)
- Findings aggregation from all modules into report
- Scorer integration (final_scores populated)
- Many modules complete concurrently

### 5. `tests/test_module_whois.py` (16 tests)
Tests WHOIS domain registration lookups.

- Successful lookup returns registrar, org, domain age
- Sets `context["company_name"]` from org field
- Does not overwrite existing company_name
- Domain age scoring: 4 brackets (10+ years, 5-10, 2-5, <2)
- Expiring soon detection (< 90 days)
- Not-expiring-soon (no false positive)
- Privacy guard detection (Domains By Proxy, etc.)
- Public org transparency score (8.0)
- Lookup failure returns success=False
- List dates (python-whois sometimes returns list)
- `_first()` helper: list, scalar, None

### 6. `tests/test_module_dns.py` (14 tests)
Tests DNS record analysis (MX, SPF, DMARC, NS).

- Google Workspace detection from MX records
- Microsoft 365 detection from MX records
- SPF softfail (~all) and hardfail (-all) parsing
- SPF +all generates critical finding
- Missing SPF generates medium finding
- DMARC reject policy parsing
- Missing DMARC generates high finding
- CDN detection (Cloudflare from NS records)
- Full security score calculation (SPF + DMARC + reject = 9.5)
- Graceful handling when all queries fail
- `_extract_tag()` helper: parses policy, missing tag, first tag

### 7. `tests/test_module_ssl.py` (10 tests)
Tests TLS certificate inspection.

- Valid cert extracts subject org, issuer, SANs, expiry
- Expired cert generates critical finding
- Expiring soon (< 30 days) generates high finding
- Sets company_name from certificate org
- Does not overwrite existing company_name
- Wildcard certificate detection
- SAN count extraction
- Connection failure returns success=False
- No cert available returns success=False
- Issuer-based stability score

### 8. `tests/test_module_headers.py` (10 tests)
Tests HTTP security header analysis.

- All 5 security headers present (HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Permissions-Policy)
- No security headers (all missing)
- Partial security headers
- Server header detection
- X-Powered-By detection
- HTTPS redirect detection
- No HTTPS redirect
- Connection failure returns success=False
- Security score with all headers + redirect = 9.0
- Tech maturity score for HSTS + CSP

### 9. `tests/test_module_tech.py` (10 tests)
Tests tech stack detection (robots.txt, sitemap, CMS, security.txt).

- WordPress detection from robots.txt (/wp-admin/)
- WordPress detection from meta generator tag
- Sitemap URL count
- security.txt present (security score 8.0)
- Missing security.txt generates low finding
- Large sitemap growth score (1500+ URLs = 8.0)
- All endpoints fail gracefully (success=True, empty data)
- `_parse_disallowed()`: basic parsing, empty input, no disallow lines

### 10. `tests/test_module_edgar.py` (18 tests)
Tests SEC EDGAR public company data.

- **EdgarModule** (11 tests):
  - High revenue (>$1B) scores 9.0, medium (>$100M) 7.0, low (>$10M) 5.0
  - Private company returns success with no findings/scores
  - Strong profit margin (>15%) info finding
  - Unprofitable (negative margin) medium finding
  - Transparency score (9.0 for public company)
  - Stability score with 5+ filings
  - Heavy insider selling finding
  - Fallback company name from domain
  - Lookup failure returns success=False
- **_fetch_edgar()** (3 tests):
  - Company found — extracts CIK, name, SIC, state
  - Company not found — returns is_public=False
  - Import error — handles missing edgartools gracefully
- **_extract_financials()** (4 tests):
  - Extracts revenue from XBRL concepts
  - Extracts net income, total assets, total liabilities
  - Extracts employee count from DEI taxonomy
  - Handles missing data (returns empty dict)

### 11. `tests/test_module_nonprofit.py` (9 tests)
Tests nonprofit 501(c)(3) detection via ProPublica API.

- Found nonprofit — returns EIN, name, revenue
- Not found — returns is_nonprofit=False
- Fuzzy name matching (partial match "Red Cross" finds "American Red Cross")
- No match above threshold
- High expense ratio generates finding
- Transparency score with 990 filings (9.0)
- Transparency score without 990 filings (6.0)
- Network error returns success=False
- Info finding for 501(c)(3) registration

### 12. `tests/test_module_dba.py` (9 tests)
Tests DBA/business registration via OpenCorporates.

- Found via API — business type, jurisdiction, status
- Active status stability score (7.0)
- Dissolved status generates high finding, score 2.0
- Transparency score (7.0)
- Recently incorporated generates medium finding
- No results — found=False
- Scrape fallback when API returns 403
- Network error returns success=False
- Info finding for business type

### 13. `tests/test_report.py` (19 tests)
Tests terminal output, JSON export, HTML report, and data highlights.

- **Helpers** (5 tests): score bar rendering (full, zero, partial), severity ordering, severity icons
- **TerminalReport** (5 tests): print scorecard no crash, print JSON valid output, save HTML creates file, default HTML path, HTML contains scores
- **_print_highlights** (9 tests): whois (domain age, registrar), dns (mail provider, CDN), ssl (cert org, CA), edgar (CIK, revenue, employees), nonprofit (name, revenue), dba (business type, status), tech (CMS), headers (server, security header count), failed module skipped

### 14. `tests/test_cli.py` (42 tests)
Tests CLI argument parsing, target resolution, and execution flow.

- **_is_domain()** (5 tests): valid .com, valid subdomain, no TLD, spaces, ticker
- **_looks_like_ticker()** (6 tests): uppercase valid, single char, lowercase rejected, mixed case rejected, too long, numbers rejected
- **_parse_targets()** (8 tests): single domain, multiple domains, ticker, multiple tickers, company name joined, mixed domain+company, quoted company, domain then ticker
- **CLI** (6 tests): no targets error, --help, --web flag, --modules option, port in use error, other OSError
- **_resolve_ticker()** (3 tests): found via SEC EDGAR, not found, network error
- **_resolve_company_name()** (5 tests): found .com, strips suffixes, not found, 500 skipped, 403 accepted
- **_run()** (8 tests): single domain, JSON output, module filter, ticker resolution, company name resolution, no resolved targets, comparison mode, comparison JSON
- **_print_comparison()** (1 test): comparison table output with winner highlighting

### 15. `tests/test_web.py` (9 tests)
Tests web dashboard HTTP endpoints.

- Index returns HTML with "Coeus"
- POST /api/scan missing target returns 400
- POST /api/scan empty target returns 400
- POST /api/scan success returns report JSON
- POST /api/scan with module filter
- GET /api/scan/stream missing target returns 400
- GET /api/scan/stream success returns SSE events (status, module, complete)
- POST /api/scan with custom timeout
- create_app() has all expected routes

### 16. `tests/conftest.py` (shared fixtures)
Provides reusable test fixtures:

- `sample_finding()` — factory for Finding objects
- `sample_score()` — factory for ScoreContribution objects
- `sample_module_result()` — factory for ModuleResult objects
- `mock_whois_result` — pre-built WHOIS result with scores
- `mock_ssl_result` — pre-built SSL result with scores
- `mock_edgar_result_public` — pre-built EDGAR result for public company
- `mock_edgar_result_private` — pre-built EDGAR result for private company
- `full_report` — complete CompanyReport combining whois + ssl + edgar

---

## Mocking Strategy

All tests run offline with no network access required.

| External Dependency | Mocking Approach |
|---------------------|------------------|
| python-whois | `patch("whois.whois")` — imported inside execute() at runtime |
| dnspython | `patch("dns.resolver.Resolver")` — imported at module top level |
| aiohttp HTTP calls | `aioresponses` library — regex URL patterns for query-param URLs |
| edgartools | `patch("coeus.modules.edgar._fetch_edgar")` for module tests; `patch("edgar.set_identity")` + `patch("edgar.Company")` for internal tests |
| SSL/TLS | `patch("coeus.modules.ssl_mod._get_cert")` — internal helper |
| Web dashboard | `aiohttp.test_utils.TestClient` + `TestServer` |
| CLI invocation | Click's `CliRunner` |

---

## Test Configuration

From `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.coverage.run]
source = ["coeus"]
omit = ["coeus/__main__.py"]

[tool.coverage.report]
fail_under = 85
show_missing = true
```

---

## Warnings

4 non-blocking warnings in the test run:

1. **RuntimeWarning** in `test_modules_option` — coroutine not awaited due to mocked `asyncio.run`. This test verifies CLI flag parsing, not async execution. Harmless.
2. **DeprecationWarning (x3)** from `edgartools` library — internal module deprecation notices for `HtmlDocument`, `html`, `htmltools`. These are upstream library warnings, not Coeus CI code issues. Will resolve when edgartools releases v6.0.

---

## How to Run

```bash
# Full suite
pytest tests/ -v

# With coverage
pytest --cov=coeus --cov-report=term-missing tests/

# Single file (incremental testing)
pytest tests/test_module_dns.py -v

# Specific test class
pytest tests/test_cli.py::TestResolveTicker -v
```
