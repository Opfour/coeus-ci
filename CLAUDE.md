# Coeus CI -- Business Intelligence OSINT Tool

Named after the Greek Titan of the inquisitive mind. Builds company profiles from free public data sources. Give it a domain, get a scored report.

## Stack

- Python 3.10+ (click, aiohttp, rich, pydantic)
- WHOIS, DNS, SEC EDGAR integration
- Installed via setuptools (pyproject.toml)

## Commands

```bash
source venv/bin/activate
coeus apple.com                  # Scan single company
coeus apple.com microsoft.com    # Compare companies
coeus apple.com --html           # Export HTML report
coeus --web                      # Launch web dashboard
./setup.sh                       # First-time setup
pytest                           # Run tests
```

## Key Directories

- `coeus/` -- Main package source
- `templates/` -- Report templates
- `reports/` -- Generated output
- `tests/` -- Test suite
- `testing/` -- Test utilities

## Report Scores

Stability, growth, tech maturity, financial health, security posture, transparency.


## Git Recon (run before reading code)

```bash
# Churn hotspots
git log --format=format: --name-only --since="1 year ago" | sort | uniq -c | sort -nr | head -20
# Bus factor
git shortlog -sn --no-merges
# Bug clusters
git log -i -E --grep="fix|bug|broken" --name-only --format= | sort | uniq -c | sort -nr | head -20
# Activity timeline
git log --format='%ad' --date=format:'%Y-%m' | sort | uniq -c
# Crisis patterns
git log --oneline --since="1 year ago" | grep -iE 'revert|hotfix|emergency|rollback'
```
