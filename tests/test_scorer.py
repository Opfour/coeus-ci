"""Tests for the weighted scoring engine."""

from coeus.models import CompanyReport, ModuleResult, ScoreContribution, ScoreDimension
from coeus.scorer import Scorer


class TestScorer:
    def test_empty_report(self):
        report = CompanyReport(target="x.com")
        scores = Scorer.calculate(report)
        assert all(v == 0.0 for v in scores.values())
        assert len(scores) == 6

    def test_single_contribution(self):
        report = CompanyReport(target="x.com")
        report.module_results["mod1"] = ModuleResult(
            module_name="mod1", success=True,
            scores=[ScoreContribution(
                dimension=ScoreDimension.STABILITY, points=7.0,
                weight=1.0, reason="test",
            )],
        )
        scores = Scorer.calculate(report)
        assert scores["stability"] == 7.0
        assert scores["growth"] == 0.0

    def test_weighted_average_same_dimension(self):
        report = CompanyReport(target="x.com")
        report.module_results["a"] = ModuleResult(
            module_name="a", success=True,
            scores=[ScoreContribution(
                dimension=ScoreDimension.SECURITY, points=8.0,
                weight=2.0, reason="a",
            )],
        )
        report.module_results["b"] = ModuleResult(
            module_name="b", success=True,
            scores=[ScoreContribution(
                dimension=ScoreDimension.SECURITY, points=4.0,
                weight=1.0, reason="b",
            )],
        )
        scores = Scorer.calculate(report)
        # (8*2 + 4*1) / (2+1) = 20/3 = 6.666... → 6.7
        assert scores["security"] == 6.7

    def test_multiple_dimensions(self):
        report = CompanyReport(target="x.com")
        report.module_results["mod"] = ModuleResult(
            module_name="mod", success=True,
            scores=[
                ScoreContribution(dimension=ScoreDimension.STABILITY,
                                  points=9.0, weight=1.0, reason="a"),
                ScoreContribution(dimension=ScoreDimension.FINANCIAL,
                                  points=5.0, weight=2.0, reason="b"),
            ],
        )
        scores = Scorer.calculate(report)
        assert scores["stability"] == 9.0
        assert scores["financial"] == 5.0

    def test_skips_failed_modules(self):
        report = CompanyReport(target="x.com")
        report.module_results["ok"] = ModuleResult(
            module_name="ok", success=True,
            scores=[ScoreContribution(
                dimension=ScoreDimension.SECURITY, points=8.0,
                weight=1.0, reason="ok",
            )],
        )
        report.module_results["fail"] = ModuleResult(
            module_name="fail", success=False, error="boom",
            scores=[ScoreContribution(
                dimension=ScoreDimension.SECURITY, points=1.0,
                weight=1.0, reason="fail",
            )],
        )
        scores = Scorer.calculate(report)
        assert scores["security"] == 8.0  # only the successful module counted

    def test_all_failed(self):
        report = CompanyReport(target="x.com")
        report.module_results["a"] = ModuleResult(
            module_name="a", success=False, error="err",
            scores=[ScoreContribution(
                dimension=ScoreDimension.STABILITY, points=5.0,
                weight=1.0, reason="x",
            )],
        )
        scores = Scorer.calculate(report)
        assert scores["stability"] == 0.0

    def test_rounding(self):
        report = CompanyReport(target="x.com")
        report.module_results["a"] = ModuleResult(
            module_name="a", success=True,
            scores=[
                ScoreContribution(dimension=ScoreDimension.GROWTH,
                                  points=1.0, weight=1.0, reason="a"),
                ScoreContribution(dimension=ScoreDimension.GROWTH,
                                  points=2.0, weight=1.0, reason="b"),
                ScoreContribution(dimension=ScoreDimension.GROWTH,
                                  points=3.0, weight=1.0, reason="c"),
            ],
        )
        scores = Scorer.calculate(report)
        assert scores["growth"] == 2.0  # (1+2+3)/3 = 2.0

    def test_all_six_dimensions(self):
        report = CompanyReport(target="x.com")
        scores_list = [
            ScoreContribution(dimension=d, points=5.0, weight=1.0, reason="test")
            for d in ScoreDimension
        ]
        report.module_results["mod"] = ModuleResult(
            module_name="mod", success=True, scores=scores_list,
        )
        scores = Scorer.calculate(report)
        assert len(scores) == 6
        assert all(v == 5.0 for v in scores.values())
