from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class AuthorizationInput(BaseModel):
    confirmed: bool
    customer_name: str = Field(min_length=1, max_length=200)
    authorized_by: str = Field(min_length=1, max_length=200)


class ScanCreate(BaseModel):
    target: HttpUrl
    profile: Literal["quick", "verified"] = "quick"
    authorization: AuthorizationInput


class ScanRead(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    target: str
    hostname: str
    profile: str
    status: str
    summary: dict
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class FindingRead(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    source: str
    source_rule_id: str | None
    title: str
    severity: str
    confidence: str
    affected_url: str
    category: str | None
    cwe: str | None
    owasp: str | None
    summary: str
    evidence: list
    remediation: str
    references: list
    status: str
