"""HTTP header analysis — server tech, security headers."""

import aiohttp
from coeus.modules.base import BaseModule
from coeus.models import Finding, ScoreContribution, ScoreDimension, Severity

SECURITY_HEADERS = [
    "strict-transport-security",
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
    "permissions-policy",
]


class HeadersModule(BaseModule):
    name = "headers"
    description = "HTTP headers, server tech, security posture"

    async def execute(self, target: str, context: dict):
        url = f"https://{target}"
        data = {
            "url_final": None,
            "status_code": None,
            "server": None,
            "powered_by": None,
            "security_headers": {},
            "security_header_count": 0,
            "https_redirect": False,
        }

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            ) as session:
                async with session.get(url, allow_redirects=True,
                                       ssl=False) as resp:
                    headers = resp.headers
                    data["url_final"] = str(resp.url)
                    data["status_code"] = resp.status
                    data["server"] = headers.get("Server")
                    data["powered_by"] = headers.get("X-Powered-By")

                    for h in SECURITY_HEADERS:
                        present = h in {k.lower() for k in headers.keys()}
                        short = h.replace("-", "_").replace(
                            "strict_transport_security", "hsts"
                        ).replace(
                            "content_security_policy", "csp"
                        )
                        data["security_headers"][short] = present

                    data["security_header_count"] = sum(
                        1 for v in data["security_headers"].values() if v
                    )

                # Check HTTP -> HTTPS redirect
                try:
                    async with session.get(
                        f"http://{target}",
                        allow_redirects=False,
                        ssl=False,
                    ) as http_resp:
                        location = http_resp.headers.get("Location", "")
                        if location.startswith("https://"):
                            data["https_redirect"] = True
                except Exception:
                    pass

        except Exception as e:
            return self._fail(f"HTTP request failed: {e}")

        findings = []
        scores = []

        # Flag missing security headers
        missing = [h for h, present in data["security_headers"].items()
                    if not present]
        if missing:
            findings.append(Finding(
                title=f"Missing security headers: {', '.join(missing)}",
                detail=f"{data['security_header_count']}/5 security headers present",
                severity=Severity.MEDIUM if len(missing) > 2 else Severity.LOW,
                source=self.name,
            ))

        if not data["https_redirect"]:
            findings.append(Finding(
                title="No HTTP to HTTPS redirect",
                severity=Severity.MEDIUM, source=self.name,
            ))

        # Security score based on header coverage
        sec_score = (data["security_header_count"] / 5) * 8 + 2
        if data["https_redirect"]:
            sec_score = min(10.0, sec_score + 1.0)
        scores.append(ScoreContribution(
            dimension=ScoreDimension.SECURITY,
            points=round(sec_score, 1), weight=1.5,
            reason=f"{data['security_header_count']}/5 security headers",
        ))

        # Tech maturity
        tech_score = 5.0
        if data["security_headers"].get("hsts"):
            tech_score += 2.0
        if data["security_headers"].get("csp"):
            tech_score += 2.0
        scores.append(ScoreContribution(
            dimension=ScoreDimension.TECH_MATURITY,
            points=min(10.0, tech_score), weight=1.0,
            reason="HTTP security header maturity",
        ))

        return self._ok(data, findings, scores)
