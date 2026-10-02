"""Typed remediation records. Status values stay lowercase, matching investigations."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.investigation.models import TransitionItem


class Remediation(BaseModel):
    id: str
    investigation_id: str
    created_at: datetime
    updated_at: datetime
    action: str
    target_kind: str
    target_name: str
    namespace: str
    reason: str
    status: str
    replicas: int | None = None

    @field_validator("replicas", mode="before")
    @classmethod
    def _reject_bool_replicas(cls, value):
        if isinstance(value, bool):
            raise ValueError("replicas must be an integer")
        return value
    approved_by: str | None = None
    approved_at: datetime | None = None
    approval_reason: str | None = None
    executed_at: datetime | None = None
    verified_at: datetime | None = None
    before_state: dict = Field(default_factory=dict)
    after_state: dict = Field(default_factory=dict)
    result: str | None = None
    error: str | None = None
    transitions: list[TransitionItem] = Field(default_factory=list)
