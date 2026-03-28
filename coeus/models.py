"""Central data models shared by all modules."""

from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Any


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Finding(BaseModel):
    """A single observation or risk flag."""
    title: str
    detail: str = ""
    severity: Severity = Severity.INFO
    source: str


class ScoreDimension(str, Enum):
    STABILITY = "stability"
    GROWTH = "growth"
    TECH_MATURITY = "tech_maturity"
    FINANCIAL = "financial"
    SECURITY = "security"
    TRANSPARENCY = "transparency"


class ScoreContribution(BaseModel):
    """A module's contribution to a scoring dimension."""
    dimension: ScoreDimension
    points: float  # 0.0 to 10.0
    weight: float = 1.0
    reason: str


class ModuleResult(BaseModel):
    """Standard return type from every module."""
    module_name: str
    success: bool
    error: str | None = None
    execution_time: float = 0.0
    data: dict[str, Any] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    scores: list[ScoreContribution] = Field(default_factory=list)


class CompanyReport(BaseModel):
    """Aggregated report from all modules."""
    target: str
    company_name: str | None = None
    generated_at: datetime = Field(default_factory=datetime.now)
    module_results: dict[str, ModuleResult] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    final_scores: dict[str, float] = Field(default_factory=dict)
