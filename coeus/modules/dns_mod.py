"""DNS records analysis — mail provider, CDN, SPF/DMARC detection."""

import asyncio
from coeus.modules.base import BaseModule
from coeus.models import Finding, ScoreContribution, ScoreDimension, Severity

MAIL_PROVIDERS = {
    "google.com": "Google Workspace",
    "googlemail.com": "Google Workspace",
    "outlook.com": "Microsoft 365",
    "microsoft.com": "Microsoft 365",
    "pphosted.com": "Proofpoint",
    "mimecast.com": "Mimecast",
    "mailgun.org": "Mailgun",
    "sendgrid.net": "SendGrid",
    "zoho.com": "Zoho Mail",
    "fastmail.com": "Fastmail",
}

CDN_INDICATORS = {
    "cloudflare": "Cloudflare",
    "akamai": "Akamai",
    "fastly": "Fastly",
    "cloudfront": "Amazon CloudFront",
    "cdn77": "CDN77",
    "stackpath": "StackPath",
    "sucuri": "Sucuri",
    "incapsula": "Imperva/Incapsula",
}


class DnsModule(BaseModule):
    name = "dns"
    description = "DNS records, mail provider, CDN, SPF/DMARC"

    async def execute(self, target: str, context: dict):
        try:
            import dns.resolver
        except ImportError:
            return self._fail("dnspython not installed")

        resolver = dns.resolver.Resolver()
        resolver.timeout = 10
        resolver.lifetime = 10

        data = {
            "mx_records": [],
            "ns_records": [],
            "txt_records": [],
            "a_records": [],
            "spf": {"present": False},
            "dmarc": {"present": False},
            "mail_provider": None,
            "cdn_detected": None,
        }

        # MX
        try:
            mx = await asyncio.to_thread(resolver.resolve, target, "MX")
            for r in mx:
                data["mx_records"].append({
                    "priority": r.preference,
                    "host": str(r.exchange).rstrip("."),
                })
        except Exception:
            pass

        # NS
        try:
            ns = await asyncio.to_thread(resolver.resolve, target, "NS")
            data["ns_records"] = [str(r).rstrip(".") for r in ns]
        except Exception:
            pass

        # A records
        try:
            a = await asyncio.to_thread(resolver.resolve, target, "A")
            data["a_records"] = [str(r) for r in a]
        except Exception:
            pass

        # TXT records (SPF, DMARC, verification tokens)
        try:
            txt = await asyncio.to_thread(resolver.resolve, target, "TXT")
            data["txt_records"] = [str(r).strip('"') for r in txt]
        except Exception:
            pass

        # DMARC (separate subdomain)
        try:
            dmarc = await asyncio.to_thread(
                resolver.resolve, f"_dmarc.{target}", "TXT"
            )
            for r in dmarc:
                record = str(r).strip('"')
                if record.startswith("v=DMARC1"):
                    data["dmarc"] = {"present": True, "record": record}
                    policy = _extract_tag(record, "p")
                    if policy:
                        data["dmarc"]["policy"] = policy
                    break
        except Exception:
            pass

        # Parse SPF from TXT
        for txt in data["txt_records"]:
            if txt.startswith("v=spf1"):
                data["spf"] = {
                    "present": True,
                    "record": txt,
                    "policy": "~all" if "~all" in txt else
                              "-all" if "-all" in txt else
                              "+all" if "+all" in txt else "?all",
                }
                break

        # Detect mail provider
        for mx_rec in data["mx_records"]:
            host = mx_rec["host"].lower()
            for key, provider in MAIL_PROVIDERS.items():
                if key in host:
                    data["mail_provider"] = provider
                    break
            if data["mail_provider"]:
                break

        # Detect CDN from NS and A record reverse hints
        all_hosts = " ".join(
            data["ns_records"] +
            [m["host"] for m in data["mx_records"]] +
            data["txt_records"]
        ).lower()
        for key, cdn in CDN_INDICATORS.items():
            if key in all_hosts:
                data["cdn_detected"] = cdn
                break

        # Scoring and findings
        findings = []
        scores = []

        # SPF
        if not data["spf"]["present"]:
            findings.append(Finding(
                title="No SPF record",
                detail="Domain has no SPF record — vulnerable to email spoofing",
                severity=Severity.MEDIUM, source=self.name,
            ))
        elif data["spf"].get("policy") == "+all":
            findings.append(Finding(
                title="SPF allows all senders",
                detail="SPF policy is +all — effectively no protection",
                severity=Severity.CRITICAL, source=self.name,
            ))

        # DMARC
        if not data["dmarc"]["present"]:
            findings.append(Finding(
                title="No DMARC record",
                detail="No DMARC policy — email spoofing protection incomplete",
                severity=Severity.HIGH, source=self.name,
            ))

        # Security score
        sec_score = 5.0
        if data["spf"]["present"]:
            sec_score += 1.5
        if data["dmarc"]["present"]:
            sec_score += 2.0
            if data["dmarc"].get("policy") == "reject":
                sec_score += 1.0
        scores.append(ScoreContribution(
            dimension=ScoreDimension.SECURITY,
            points=min(10.0, sec_score), weight=2.0,
            reason="Email security (SPF/DMARC)",
        ))

        # Tech maturity
        tech_score = 5.0
        if data["mail_provider"] in ("Google Workspace", "Microsoft 365"):
            tech_score += 2.0
        if data["cdn_detected"]:
            tech_score += 2.0
        scores.append(ScoreContribution(
            dimension=ScoreDimension.TECH_MATURITY,
            points=min(10.0, tech_score), weight=1.0,
            reason="Mail provider and CDN usage",
        ))

        return self._ok(data, findings, scores)


def _extract_tag(record: str, tag: str) -> str | None:
    for part in record.split(";"):
        part = part.strip()
        if part.startswith(f"{tag}="):
            return part.split("=", 1)[1].strip()
    return None
