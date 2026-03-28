"""Tech stack detection from robots.txt, sitemap, HTML meta tags."""

import re
import aiohttp
from coeus.modules.base import BaseModule
from coeus.models import Finding, ScoreContribution, ScoreDimension, Severity

CMS_PATHS = {
    "/wp-admin": "WordPress",
    "/wp-includes": "WordPress",
    "/wp-content": "WordPress",
    "/administrator": "Joomla",
    "/components/com_": "Joomla",
    "/sites/default": "Drupal",
    "/core/misc": "Drupal",
    "/skin/frontend": "Magento",
    "/pub/static": "Magento",
    "/ghost/api": "Ghost",
    "/umbraco": "Umbraco",
}

META_GENERATORS = {
    "wordpress": "WordPress",
    "joomla": "Joomla",
    "drupal": "Drupal",
    "wix.com": "Wix",
    "squarespace": "Squarespace",
    "shopify": "Shopify",
    "hugo": "Hugo",
    "jekyll": "Jekyll",
    "ghost": "Ghost",
    "next.js": "Next.js",
}


class TechModule(BaseModule):
    name = "tech"
    description = "Tech stack detection (CMS, frameworks, security.txt)"

    async def execute(self, target: str, context: dict):
        base = f"https://{target}"
        data = {
            "robots_txt_exists": False,
            "robots_disallowed_paths": [],
            "sitemap_exists": False,
            "sitemap_url_count": 0,
            "cms_detected": None,
            "meta_generator": None,
            "security_txt_exists": False,
            "technologies": [],
        }

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            ) as session:
                # robots.txt
                try:
                    async with session.get(f"{base}/robots.txt", ssl=False) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            data["robots_txt_exists"] = True
                            data["robots_disallowed_paths"] = _parse_disallowed(text)

                            for path, cms in CMS_PATHS.items():
                                if path.lower() in text.lower():
                                    data["cms_detected"] = cms
                                    break
                except Exception:
                    pass

                # sitemap.xml
                try:
                    async with session.get(f"{base}/sitemap.xml", ssl=False) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            data["sitemap_exists"] = True
                            data["sitemap_url_count"] = text.count("<loc>")
                except Exception:
                    pass

                # security.txt
                try:
                    async with session.get(
                        f"{base}/.well-known/security.txt", ssl=False
                    ) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            if "contact:" in text.lower():
                                data["security_txt_exists"] = True
                except Exception:
                    pass

                # Homepage meta tags (first 100KB)
                try:
                    async with session.get(base, ssl=False) as resp:
                        if resp.status == 200:
                            html = await resp.text(encoding="utf-8", errors="ignore")
                            html = html[:100_000]

                            gen_match = re.search(
                                r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)',
                                html, re.IGNORECASE,
                            )
                            if gen_match:
                                data["meta_generator"] = gen_match.group(1)
                                for key, cms in META_GENERATORS.items():
                                    if key in gen_match.group(1).lower():
                                        data["cms_detected"] = cms
                                        break
                except Exception:
                    pass

        except Exception as e:
            return self._fail(f"Tech detection failed: {e}")

        # Build technologies list
        techs = set()
        if data["cms_detected"]:
            techs.add(data["cms_detected"])
        data["technologies"] = sorted(techs)

        findings = []
        scores = []

        if data["security_txt_exists"]:
            scores.append(ScoreContribution(
                dimension=ScoreDimension.SECURITY,
                points=8.0, weight=0.5,
                reason="security.txt present",
            ))
        else:
            findings.append(Finding(
                title="No security.txt",
                detail="No /.well-known/security.txt found",
                severity=Severity.LOW, source=self.name,
            ))

        # Tech maturity based on what we found
        tech_score = 5.0
        if data["sitemap_exists"]:
            tech_score += 1.0
        if data["robots_txt_exists"]:
            tech_score += 0.5
        if data["cms_detected"] in ("Next.js", "Hugo", "Jekyll", "Ghost"):
            tech_score += 2.0  # modern stack
        scores.append(ScoreContribution(
            dimension=ScoreDimension.TECH_MATURITY,
            points=min(10.0, tech_score), weight=0.5,
            reason="Site infrastructure and CMS",
        ))

        # Growth proxy: sitemap size
        if data["sitemap_url_count"] > 1000:
            scores.append(ScoreContribution(
                dimension=ScoreDimension.GROWTH,
                points=8.0, weight=0.5,
                reason=f"Sitemap has {data['sitemap_url_count']} URLs",
            ))
        elif data["sitemap_url_count"] > 100:
            scores.append(ScoreContribution(
                dimension=ScoreDimension.GROWTH,
                points=6.0, weight=0.5,
                reason=f"Sitemap has {data['sitemap_url_count']} URLs",
            ))

        return self._ok(data, findings, scores)


def _parse_disallowed(robots_text: str) -> list[str]:
    paths = []
    for line in robots_text.splitlines():
        line = line.strip()
        if line.lower().startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            if path:
                paths.append(path)
    return paths
