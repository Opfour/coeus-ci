"""WHOIS domain registration lookup."""

import asyncio
from datetime import datetime, timezone
from coeus.modules.base import BaseModule
from coeus.models import Finding, ScoreContribution, ScoreDimension, Severity


class WhoisModule(BaseModule):
    name = "whois"
    description = "Domain WHOIS registration data"

    async def execute(self, target: str, context: dict):
        try:
            import whois
            w = await asyncio.to_thread(whois.whois, target)
        except Exception as e:
            return self._fail(f"WHOIS lookup failed: {e}")

        creation = _first(w.creation_date)
        expiration = _first(w.expiration_date)
        registrar = w.registrar
        org = w.org

        domain_age_years = None
        if creation:
            try:
                created = creation.replace(tzinfo=timezone.utc) if creation.tzinfo is None else creation
                domain_age_years = round(
                    (datetime.now(timezone.utc) - created).days / 365.25, 1
                )
            except Exception:
                pass

        data = {
            "domain": target,
            "registrar": registrar,
            "org": org,
            "creation_date": str(creation) if creation else None,
            "expiration_date": str(expiration) if expiration else None,
            "domain_age_years": domain_age_years,
            "name_servers": w.name_servers,
            "dnssec": getattr(w, "dnssec", None),
        }

        if org and "company_name" not in context:
            context["company_name"] = org

        findings = []
        scores = []

        if domain_age_years is not None:
            if domain_age_years >= 10:
                score = 9.0
            elif domain_age_years >= 5:
                score = 7.0
            elif domain_age_years >= 2:
                score = 5.0
            else:
                score = 3.0
            scores.append(ScoreContribution(
                dimension=ScoreDimension.STABILITY,
                points=score, weight=2.0,
                reason=f"Domain registered {domain_age_years} years ago",
            ))

        if expiration:
            try:
                exp = expiration.replace(tzinfo=timezone.utc) if expiration.tzinfo is None else expiration
                days_left = (exp - datetime.now(timezone.utc)).days
                if days_left < 90:
                    findings.append(Finding(
                        title="Domain expiring soon",
                        detail=f"Expires in {days_left} days",
                        severity=Severity.HIGH, source=self.name,
                    ))
            except Exception:
                pass

        # Privacy guard detection
        if org and any(kw in org.lower() for kw in
                       ["privacy", "redacted", "proxy", "whoisguard", "domains by proxy"]):
            findings.append(Finding(
                title="WHOIS privacy guard active",
                detail=f"Organization: {org}",
                severity=Severity.INFO, source=self.name,
            ))
            scores.append(ScoreContribution(
                dimension=ScoreDimension.TRANSPARENCY,
                points=3.0, weight=1.0,
                reason="WHOIS info is privacy-guarded",
            ))
        elif org:
            scores.append(ScoreContribution(
                dimension=ScoreDimension.TRANSPARENCY,
                points=8.0, weight=1.0,
                reason="WHOIS organization is publicly visible",
            ))

        return self._ok(data, findings, scores)


def _first(val):
    """python-whois sometimes returns a list of dates."""
    return val[0] if isinstance(val, list) else val
