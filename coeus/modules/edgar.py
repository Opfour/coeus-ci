"""SEC EDGAR — public company filings, financials, insider trades."""

import asyncio
from coeus.modules.base import BaseModule
from coeus.models import Finding, ScoreContribution, ScoreDimension, Severity


class EdgarModule(BaseModule):
    name = "edgar"
    description = "SEC EDGAR filings and financials"

    async def execute(self, target: str, context: dict):
        company_name = context.get("company_name")
        if not company_name:
            # Try domain name as fallback
            company_name = target.split(".")[0].title()

        try:
            result = await asyncio.to_thread(_fetch_edgar, company_name, target)
        except Exception as e:
            return self._fail(f"EDGAR lookup failed: {e}")

        if not result["is_public"]:
            # Not an error — just a private company
            return self._ok(result)

        findings = []
        scores = []

        # Financial scoring
        fin = result.get("financials", {})
        if fin.get("revenue"):
            rev = fin["revenue"]
            if rev > 1_000_000_000:
                scores.append(ScoreContribution(
                    dimension=ScoreDimension.FINANCIAL,
                    points=9.0, weight=3.0,
                    reason=f"Revenue: ${rev:,.0f}",
                ))
            elif rev > 100_000_000:
                scores.append(ScoreContribution(
                    dimension=ScoreDimension.FINANCIAL,
                    points=7.0, weight=3.0,
                    reason=f"Revenue: ${rev:,.0f}",
                ))
            elif rev > 10_000_000:
                scores.append(ScoreContribution(
                    dimension=ScoreDimension.FINANCIAL,
                    points=5.0, weight=3.0,
                    reason=f"Revenue: ${rev:,.0f}",
                ))

        if fin.get("net_income") and fin.get("revenue"):
            margin = fin["net_income"] / fin["revenue"]
            if margin > 0.15:
                findings.append(Finding(
                    title="Strong profit margin",
                    detail=f"Net margin: {margin:.1%}",
                    severity=Severity.INFO, source=self.name,
                ))
            elif margin < 0:
                findings.append(Finding(
                    title="Unprofitable",
                    detail=f"Net margin: {margin:.1%}",
                    severity=Severity.MEDIUM, source=self.name,
                ))

        # Transparency: public company with filings
        scores.append(ScoreContribution(
            dimension=ScoreDimension.TRANSPARENCY,
            points=9.0, weight=2.0,
            reason="Public company with SEC filings",
        ))

        # Stability: has filing history
        filings = result.get("recent_filings", [])
        if len(filings) >= 5:
            scores.append(ScoreContribution(
                dimension=ScoreDimension.STABILITY,
                points=8.0, weight=1.5,
                reason=f"{len(filings)} recent SEC filings",
            ))

        # Insider trades
        trades = result.get("insider_trades_90d", {})
        if trades.get("sells", 0) > trades.get("buys", 0) * 3:
            findings.append(Finding(
                title="Heavy insider selling",
                detail=f"Sells: {trades['sells']}, Buys: {trades['buys']} (90 days)",
                severity=Severity.MEDIUM, source=self.name,
            ))

        return self._ok(result, findings, scores)


def _fetch_edgar(company_name: str, domain: str) -> dict:
    """Synchronous EDGAR lookup using edgartools."""
    result = {
        "is_public": False,
        "cik": None,
        "company_name_sec": None,
        "sic_code": None,
        "sic_description": None,
        "state_of_incorporation": None,
        "recent_filings": [],
        "financials": {},
        "insider_trades_90d": {},
    }

    try:
        from edgar import set_identity, Company

        set_identity(f"coeus-ci research@{domain}")

        company = Company(company_name)
        if not company:
            return result

        result["is_public"] = True
        result["cik"] = str(getattr(company, "cik", ""))
        result["company_name_sec"] = getattr(company, "name", company_name)
        result["sic_code"] = str(getattr(company, "sic", ""))
        result["sic_description"] = getattr(company, "sic_description", None)
        result["state_of_incorporation"] = getattr(
            company, "state_of_incorporation", None
        )

        # Recent filings
        try:
            filings = company.get_filings()
            recent = []
            for f in filings[:20]:
                recent.append({
                    "form": getattr(f, "form", ""),
                    "date": str(getattr(f, "filing_date", "")),
                    "description": getattr(f, "description", ""),
                })
            result["recent_filings"] = recent
        except Exception:
            pass

        # Financials from company facts
        try:
            facts = company.get_facts()
            if facts:
                result["financials"] = _extract_financials(facts)
        except Exception:
            pass

    except Exception:
        return result

    return result


def _extract_financials(facts) -> dict:
    """Extract key financial figures from EDGAR company facts."""
    financials = {}

    revenue_concepts = [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ]

    for concept in revenue_concepts:
        try:
            val = facts.get("us-gaap", concept)
            if val:
                entries = getattr(val, "data", [])
                if entries:
                    latest = entries[-1]
                    financials["revenue"] = getattr(latest, "value", None)
                    break
        except Exception:
            continue

    for concept, key in [
        ("NetIncomeLoss", "net_income"),
        ("Assets", "total_assets"),
        ("Liabilities", "total_liabilities"),
    ]:
        try:
            val = facts.get("us-gaap", concept)
            if val:
                entries = getattr(val, "data", [])
                if entries:
                    financials[key] = getattr(entries[-1], "value", None)
        except Exception:
            continue

    try:
        val = facts.get("dei", "EntityNumberOfEmployees")
        if val:
            entries = getattr(val, "data", [])
            if entries:
                financials["employees"] = getattr(entries[-1], "value", None)
    except Exception:
        pass

    return financials
