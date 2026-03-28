"""Orchestrator: discovers modules, runs them, aggregates results."""

import asyncio
import time
from coeus.models import CompanyReport, ModuleResult
from coeus.modules.base import BaseModule
from coeus.scorer import Scorer
from rich.progress import Progress, SpinnerColumn, TextColumn


class Orchestrator:
    # Wave 1 modules populate company_name in context
    WAVE_1 = {"whois", "ssl"}

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def run(self, target: str,
                  module_filter: list[str] | None = None) -> CompanyReport:
        from coeus.modules import ALL_MODULES

        modules = ALL_MODULES
        if module_filter:
            modules = [m for m in modules if m.name in module_filter]

        context: dict = {}
        report = CompanyReport(target=target)

        wave1 = [m for m in modules if m.name in self.WAVE_1]
        wave2 = [m for m in modules if m.name not in self.WAVE_1]

        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Identifying company...", total=None)
            results_1 = await self._run_modules(wave1, target, context)
            for name, result in results_1.items():
                report.module_results[name] = result

            progress.update(task, description="Running intelligence modules...")
            results_2 = await self._run_modules(wave2, target, context)
            for name, result in results_2.items():
                report.module_results[name] = result

        report.company_name = context.get("company_name")

        for result in report.module_results.values():
            report.findings.extend(result.findings)

        report.final_scores = Scorer.calculate(report)
        return report

    async def _run_modules(
        self,
        modules: list[BaseModule],
        target: str,
        context: dict,
    ) -> dict[str, ModuleResult]:
        sem = asyncio.Semaphore(5)
        results: dict[str, ModuleResult] = {}

        async def run_one(mod: BaseModule):
            async with sem:
                start = time.monotonic()
                try:
                    result = await asyncio.wait_for(
                        mod.execute(target, context),
                        timeout=self.timeout,
                    )
                except asyncio.TimeoutError:
                    result = ModuleResult(
                        module_name=mod.name,
                        success=False,
                        error=f"Timed out after {self.timeout}s",
                    )
                except Exception as e:
                    result = ModuleResult(
                        module_name=mod.name,
                        success=False,
                        error=str(e),
                    )
                result.execution_time = time.monotonic() - start
                results[mod.name] = result

        await asyncio.gather(*(run_one(m) for m in modules))
        return results
