"""501(c)(3) nonprofit lookup via ProPublica Nonprofit Explorer API."""

import aiohttp
from coeus.modules.base import BaseModule
from coeus.models import Finding, ScoreContribution, ScoreDimension, Severity

PROPUBLICA_SEARCH = "https://projects.propublica.org/nonprofits/api/v2/search.json"
PROPUBLICA_ORG = "https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"


class NonprofitModule(BaseModule):
    name = "nonprofit"
    description = "501(c)(3) status and Form 990 financials"

    async def execute(self, target: str, context: dict):
        company_name = context.get("company_name")
        if not company_name:
            company_name = target.split(".")[0].title()

        data = {
            "is_nonprofit": False,
            "ein": None,
            "name": None,
            "city": None,
            "state": None,
            "ntee_code": None,
            "ruling_date": None,
            "subsection": None,
            "revenue": None,
            "expenses": None,
            "assets": None,
            "income": None,
        }

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            ) as session:
                # Search by company name
                async with session.get(
                    PROPUBLICA_SEARCH,
                    params={"q": company_name},
                ) as resp:
                    if resp.status != 200:
                        return self._ok(data)

                    result = await resp.json()
                    orgs = result.get("organizations", [])

                    if not orgs:
                        return self._ok(data)

                    # Find best match (first result is usually most relevant)
                    org = orgs[0]
                    data["is_nonprofit"] = True
                    data["ein"] = org.get("ein")
                    data["name"] = org.get("name")
                    data["city"] = org.get("city")
                    data["state"] = org.get("state")
                    data["ntee_code"] = org.get("ntee_code")
                    data["subsection"] = org.get("subsection_code")

                # Fetch detailed 990 data if we have an EIN
                if data["ein"]:
                    try:
                        detail_url = PROPUBLICA_ORG.format(ein=data["ein"])
                        async with session.get(detail_url) as resp:
                            if resp.status == 200:
                                detail = await resp.json()
                                org_detail = detail.get("organization", {})
                                data["ruling_date"] = org_detail.get("ruling_date")

                                # Get latest 990 filing
                                filings = detail.get("filings_with_data", [])
                                if filings:
                                    latest = filings[0]
                                    data["revenue"] = latest.get("totrevenue")
                                    data["expenses"] = latest.get("totfuncexpns")
                                    data["assets"] = latest.get("totassetsend")
                                    data["income"] = latest.get("totnetliabastend")
                    except Exception:
                        pass

        except Exception as e:
            return self._fail(f"Nonprofit lookup failed: {e}")

        if not data["is_nonprofit"]:
            return self._ok(data)

        findings = []
        scores = []

        # Transparency: 990 data available
        if data["revenue"] is not None:
            scores.append(ScoreContribution(
                dimension=ScoreDimension.TRANSPARENCY,
                points=9.0, weight=2.0,
                reason="Form 990 financial data publicly available",
            ))

            scores.append(ScoreContribution(
                dimension=ScoreDimension.FINANCIAL,
                points=7.0, weight=2.0,
                reason=f"Nonprofit revenue: ${data['revenue']:,.0f}",
            ))
        else:
            scores.append(ScoreContribution(
                dimension=ScoreDimension.TRANSPARENCY,
                points=6.0, weight=1.0,
                reason="Registered nonprofit but no 990 data found",
            ))

        # Check expense ratio
        if data["revenue"] and data["expenses"] and data["revenue"] > 0:
            expense_ratio = data["expenses"] / data["revenue"]
            if expense_ratio > 0.95:
                findings.append(Finding(
                    title="High expense ratio",
                    detail=f"Expenses are {expense_ratio:.0%} of revenue",
                    severity=Severity.MEDIUM, source=self.name,
                ))

        findings.append(Finding(
            title=f"Registered 501(c)({data.get('subsection', '?')})",
            detail=f"EIN: {data['ein']}, {data['city']}, {data['state']}",
            severity=Severity.INFO, source=self.name,
        ))

        return self._ok(data, findings, scores)
