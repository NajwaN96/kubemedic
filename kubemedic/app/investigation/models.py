"""Investigation records returned by the API and stored in SQLite."""

from datetime import datetime

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    label: str
    value: str


class EventItem(BaseModel):
    type: str = "Warning"
    reason: str
    message: str
    count: int = 1
    timestamp: str | None = None


class LogItem(BaseModel):
    source: str
    content: str


class TimelineItem(BaseModel):
    at: datetime
    message: str


class TransitionItem(BaseModel):
    at: datetime
    status: str
    reason: str


class RuleAnalysis(BaseModel):
    detected_issue: str
    summary: str
    likely_root_cause: str
    recommended_actions: list[str] = Field(default_factory=list)
    severity: str


class AIAnalysis(BaseModel):
    summary: str
    likely_root_cause: str
    supporting_evidence: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    contributing_factors: list[str] = Field(default_factory=list)
    confidence: str
    confidence_explanation: str


class Investigation(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    namespace: str
    resource_kind: str
    resource_name: str
    container: str | None = None
    severity: str
    status: str
    detected_issue: str
    summary: str
    likely_root_cause: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    events: list[EventItem] = Field(default_factory=list)
    logs: list[LogItem] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    timeline: list[TimelineItem] = Field(default_factory=list)
    transitions: list[TransitionItem] = Field(default_factory=list)
    occurrence_count: int = 1
    analysis_source: str = "rules"
    rule_analysis: RuleAnalysis | None = None
    ai_analysis: AIAnalysis | None = None
    ai_status: str | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_analyzed_at: datetime | None = None
    ai_input_signature: str = Field(default="", exclude=True)
    resolved_at: datetime | None = None
    resolution_reason: str | None = None
    recovery_duration_seconds: int | None = None
    last_failure_seen_at: datetime | None = None
    last_healthy_seen_at: datetime | None = None
    stable_restart_count: int | None = None
    fingerprint: str = Field(default="", exclude=True)


class ClusterStatus(BaseModel):
    status: str
    namespace: str
    mode: str
    demo_mode: bool = False
