"""Multi-dimensional scoring engine."""

from coeus.models import CompanyReport, ScoreDimension


class Scorer:
    @staticmethod
    def calculate(report: CompanyReport) -> dict[str, float]:
        """Weighted average of ScoreContribution objects per dimension."""
        buckets: dict[str, list[tuple[float, float]]] = {
            d.value: [] for d in ScoreDimension
        }

        for result in report.module_results.values():
            if not result.success:
                continue
            for sc in result.scores:
                buckets[sc.dimension.value].append((sc.points, sc.weight))

        scores = {}
        for dim, contributions in buckets.items():
            if not contributions:
                scores[dim] = 0.0
                continue
            total_weight = sum(w for _, w in contributions)
            weighted_sum = sum(p * w for p, w in contributions)
            scores[dim] = round(weighted_sum / total_weight, 1)

        return scores
