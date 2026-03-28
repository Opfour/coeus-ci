"""TLS certificate inspection."""

import asyncio
import ssl
import socket
from datetime import datetime, timezone
from coeus.modules.base import BaseModule
from coeus.models import Finding, ScoreContribution, ScoreDimension, Severity


class SslModule(BaseModule):
    name = "ssl"
    description = "TLS certificate organization, CA, expiry"

    async def execute(self, target: str, context: dict):
        try:
            cert = await asyncio.to_thread(_get_cert, target)
        except Exception as e:
            return self._fail(f"SSL connection failed: {e}")

        if not cert:
            return self._fail("No certificate returned")

        subject = dict(x[0] for x in cert.get("subject", []))
        issuer = dict(x[0] for x in cert.get("issuer", []))

        not_before = cert.get("notBefore", "")
        not_after = cert.get("notAfter", "")

        # Parse dates
        expiry_dt = None
        days_until_expiry = None
        try:
            expiry_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
            days_until_expiry = (expiry_dt - datetime.now(timezone.utc)).days
        except Exception:
            pass

        # SANs
        sans = []
        for san_type, san_value in cert.get("subjectAltName", []):
            if san_type == "DNS":
                sans.append(san_value)

        subject_org = subject.get("organizationName")
        subject_cn = subject.get("commonName")
        issuer_org = issuer.get("organizationName")

        data = {
            "subject_cn": subject_cn,
            "subject_org": subject_org,
            "issuer_org": issuer_org,
            "not_before": not_before,
            "not_after": not_after,
            "days_until_expiry": days_until_expiry,
            "sans": sans,
            "san_count": len(sans),
            "serial_number": cert.get("serialNumber"),
            "is_wildcard": any(s.startswith("*.") for s in sans),
        }

        # Set company name from cert org (often more reliable than WHOIS)
        if subject_org and "company_name" not in context:
            context["company_name"] = subject_org

        findings = []
        scores = []

        if days_until_expiry is not None:
            if days_until_expiry < 0:
                findings.append(Finding(
                    title="SSL certificate expired",
                    detail=f"Expired {abs(days_until_expiry)} days ago",
                    severity=Severity.CRITICAL, source=self.name,
                ))
                scores.append(ScoreContribution(
                    dimension=ScoreDimension.SECURITY,
                    points=1.0, weight=2.0,
                    reason="Certificate is expired",
                ))
            elif days_until_expiry < 30:
                findings.append(Finding(
                    title="SSL certificate expiring soon",
                    detail=f"Expires in {days_until_expiry} days",
                    severity=Severity.HIGH, source=self.name,
                ))
                scores.append(ScoreContribution(
                    dimension=ScoreDimension.SECURITY,
                    points=5.0, weight=2.0,
                    reason=f"Certificate expires in {days_until_expiry} days",
                ))
            else:
                scores.append(ScoreContribution(
                    dimension=ScoreDimension.SECURITY,
                    points=9.0, weight=1.0,
                    reason=f"Valid certificate, {days_until_expiry} days remaining",
                ))

        # Stability: valid cert with known CA
        if issuer_org:
            scores.append(ScoreContribution(
                dimension=ScoreDimension.STABILITY,
                points=7.0, weight=1.0,
                reason=f"Certificate issued by {issuer_org}",
            ))

        return self._ok(data, findings, scores)


def _get_cert(hostname: str, port: int = 443) -> dict:
    ctx = ssl.create_default_context()
    with socket.create_connection((hostname, port), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            return ssock.getpeercert()
