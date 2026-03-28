"""DBA / business registration lookup via OpenCorporates."""

import re
import aiohttp
from coeus.modules.base import BaseModule
from coeus.models import Finding, ScoreContribution, ScoreDimension, Severity

OPENCORP_SEARCH = "https://api.opencorporates.com/v0.4/companies/search"


class DbaModule(BaseModule):
    name = "dba"
    description = "Business registration, DBA, LLC/Corp status"

    async def execute(self, target: str, context: dict):
        company_name = context.get("company_name")
        if not company_name:
            company_name = target.split(".")[0].title()

        data = {
            "found": False,
            "company_name_filed": None,
            "business_type": None,
            "jurisdiction": None,
            "company_number": None,
            "status": None,
            "incorporation_date": None,
            "registered_address": None,
            "source": None,
        }

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            ) as session:
                # Try OpenCorporates API (free tier, no key for basic search)
                async with session.get(
                    OPENCORP_SEARCH,
                    params={"q": company_name, "format": "json"},
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        companies = (result.get("results", {})
                                     .get("companies", []))

                        if companies:
                            best = companies[0].get("company", {})
                            data["found"] = True
                            data["company_name_filed"] = best.get("name")
                            data["business_type"] = best.get("company_type")
                            data["jurisdiction"] = best.get(
                                "jurisdiction_code", ""
                            ).upper()
                            data["company_number"] = best.get("company_number")
                            data["status"] = best.get("current_status")
                            data["incorporation_date"] = best.get(
                                "incorporation_date"
                            )
                            addr = best.get("registered_address_in_full")
                            if addr:
                                data["registered_address"] = addr
                            data["source"] = "OpenCorporates"

                    elif resp.status == 403:
                        # API rate limited — try scraping search page
                        data = await _scrape_opencorporates(
                            session, company_name, data
                        )

        except Exception as e:
            return self._fail(f"Business registration lookup failed: {e}")

        if not data["found"]:
            return self._ok(data)

        findings = []
        scores = []

        # Status checks
        status = (data.get("status") or "").lower()
        if status in ("active", "good standing"):
            scores.append(ScoreContribution(
                dimension=ScoreDimension.STABILITY,
                points=7.0, weight=1.0,
                reason=f"Business status: {data['status']}",
            ))
        elif status in ("dissolved", "inactive", "revoked"):
            findings.append(Finding(
                title=f"Business is {data['status']}",
                detail=f"Filed in {data['jurisdiction']}",
                severity=Severity.HIGH, source=self.name,
            ))
            scores.append(ScoreContribution(
                dimension=ScoreDimension.STABILITY,
                points=2.0, weight=2.0,
                reason=f"Business status: {data['status']}",
            ))

        # Transparency: public filing found
        scores.append(ScoreContribution(
            dimension=ScoreDimension.TRANSPARENCY,
            points=7.0, weight=1.0,
            reason=f"Business registration found ({data['source']})",
        ))

        # Incorporation age
        if data.get("incorporation_date"):
            try:
                from datetime import datetime, timezone
                inc = datetime.strptime(data["incorporation_date"], "%Y-%m-%d")
                age_years = (datetime.now(timezone.utc) -
                             inc.replace(tzinfo=timezone.utc)).days / 365.25
                if age_years < 1:
                    findings.append(Finding(
                        title="Very recently incorporated",
                        detail=f"Incorporated {data['incorporation_date']}",
                        severity=Severity.MEDIUM, source=self.name,
                    ))
            except Exception:
                pass

        findings.append(Finding(
            title=f"Registered as {data.get('business_type', 'Unknown')}",
            detail=(f"{data.get('jurisdiction', '')} — "
                    f"#{data.get('company_number', '?')}"),
            severity=Severity.INFO, source=self.name,
        ))

        return self._ok(data, findings, scores)


async def _scrape_opencorporates(session, company_name, data):
    """Fallback: scrape OpenCorporates search results page."""
    try:
        url = f"https://opencorporates.com/companies?q={company_name}"
        async with session.get(url, ssl=False) as resp:
            if resp.status == 200:
                html = await resp.text()
                # Look for first company result
                name_match = re.search(
                    r'class="company_search_result".*?'
                    r'<a[^>]*>([^<]+)</a>',
                    html, re.DOTALL,
                )
                if name_match:
                    data["found"] = True
                    data["company_name_filed"] = name_match.group(1).strip()
                    data["source"] = "OpenCorporates (web)"
    except Exception:
        pass
    return data
