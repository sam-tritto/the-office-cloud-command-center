"""
ScrantonOS — Pydantic Data Schemas
====================================
Typed models for inter-agent communication. Agents communicate solely
through these schemas passed over workflow edges, enforcing strict
context isolation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════
# Intent Classification
# ═══════════════════════════════════════════════════════════════════════

class CommandIntent(str, Enum):
    """Michael Scott classifies every user input into one of these intents."""
    SRE = "sre"                     # → Dwight (log analysis, crash detection)
    FINOPS = "finops"               # → Oscar (billing, cost analysis)
    FIREBASE = "firebase"           # → Angela (Crashlytics, Firebase monitoring)
    IAM = "iam"                     # → Stanley (access grants, role changes)
    TECH_DEBT = "tech_debt"         # → Jan (TODO/FIXME audits, sprint velocity)
    UI_REVIEW = "ui_review"         # → Jim (front-end linting, PR review)
    CHAOS_TEST = "chaos_test"       # → Meredith (fuzz testing, stress testing)
    DOCS = "docs"                   # → Gabe (RAG documentation search)
    LEGACY = "legacy"               # → Bob Vance (cold storage, migration)
    PURGE = "purge"                 # → Creed (PII erasure, data deletion)
    REPORT = "report"               # → Pam (artifact generation, markdown)
    GIT_OPS = "git_ops"             # → Erin (Git pipeline, CI/CD status)
    METRICS = "metrics"             # → Kevin (Dashboard, metrics, counting)
    MODERNIZE = "modernize"         # → Ryan (Tech recommendations, rewrite)
    GENERAL = "general"             # → Michael handles directly


class UserCommand(BaseModel):
    """Structured representation of a user's natural language input."""
    raw_input: str = Field(..., description="Original user message text")
    session_id: str = Field("default", description="Session ID for tracking history")
    intent: CommandIntent = Field(..., description="Classified intent")
    target_user: Optional[str] = Field(None, description="Target user email if applicable")
    target_role: Optional[str] = Field(None, description="Target IAM role if applicable")
    target_resource: Optional[str] = Field(None, description="Target resource identifier")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Extra extracted parameters")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════
# Dwight Schrute — SRE Log Analysis
# ═══════════════════════════════════════════════════════════════════════

class LogEntry(BaseModel):
    """A single parsed log entry from application crash logs."""
    timestamp: str
    severity: str  # ERROR, WARNING, CRITICAL
    service: str
    message: str
    container_id: Optional[str] = None
    memory_mb: Optional[float] = None


class LogAnalysisResult(BaseModel):
    """Dwight's output: structured analysis of application logs."""
    total_entries: int
    critical_count: int
    error_count: int
    warning_count: int
    memory_leak_detected: bool = False
    peak_memory_mb: Optional[float] = None
    top_errors: list[str] = Field(default_factory=list, description="Top 5 most frequent errors")
    threat_assessment: str = Field(..., description="Dwight's dramatic threat assessment")
    recommended_actions: list[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
# Oscar Martinez — FinOps Billing
# ═══════════════════════════════════════════════════════════════════════

class BillingLineItem(BaseModel):
    """A single line item from the GCP billing export."""
    service: str
    sku_description: str
    cost_usd: float
    usage_amount: float
    usage_unit: str
    date: str


class BillingReport(BaseModel):
    """Oscar's output: analytical breakdown of cloud spending."""
    period_start: str
    period_end: str
    total_cost_usd: float
    daily_average_usd: float
    top_services: list[dict[str, float]] = Field(
        default_factory=list,
        description="Top 5 services by cost: [{name: cost}]"
    )
    anomalies: list[str] = Field(default_factory=list, description="Detected cost anomalies")
    over_budget: bool = False
    budget_utilization_pct: float = 0.0
    oscar_commentary: str = Field(..., description="Oscar's 'Actually...' analysis")


# ═══════════════════════════════════════════════════════════════════════
# Stanley Hudson — IAM Compliance
# ═══════════════════════════════════════════════════════════════════════

class IAMRequest(BaseModel):
    """Request to grant an IAM role to a user."""
    requesting_agent: str = Field(..., description="Which agent requested this")
    target_user: str = Field(..., description="Email of the user to receive the role")
    target_role: str = Field(..., description="GCP IAM role string, e.g. 'roles/viewer'")
    justification: str = Field("", description="Why this access is needed")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class IAMVerdict(BaseModel):
    """Stanley's verdict on an IAM request."""
    approved: bool
    target_user: str
    target_role: str
    reason: str = Field(..., description="Why Stanley approved or denied")
    requires_hitl: bool = Field(
        False,
        description="If True, even approved requests must pass through Toby's HITL gate"
    )
    stanley_commentary: str = Field("", description="Stanley's characteristically flat response")


# ═══════════════════════════════════════════════════════════════════════
# Toby Flenderson — HITL Approval Gate
# ═══════════════════════════════════════════════════════════════════════

class HITLPayload(BaseModel):
    """Payload emitted when the workflow enters PAUSED state for human approval."""
    request_id: str = Field(..., description="Unique identifier for this approval request")
    action_type: str = Field(..., description="What kind of action needs approval")
    action_details: dict[str, Any] = Field(default_factory=dict)
    requesting_agent: str
    risk_level: str = Field("medium", description="low / medium / high / critical")
    toby_message: str = Field(..., description="Toby's apologetic explanation")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HITLResponse(BaseModel):
    """Human's response to an HITL approval request."""
    request_id: str
    approved: bool
    approver_note: str = ""
    approval_token: str = Field("", description="HMAC-signed token if approved")


# ═══════════════════════════════════════════════════════════════════════
# Jan Levinson — Tech Debt
# ═══════════════════════════════════════════════════════════════════════

class TechDebtItem(BaseModel):
    """A single TODO/FIXME found in the codebase."""
    file_path: str
    line_number: int
    tag: str  # TODO, FIXME, HACK, XXX
    text: str
    age_days: int
    sprint_tag: Optional[str] = None


class TechDebtReport(BaseModel):
    """Jan's output: uncompromising audit of engineering debt."""
    total_items: int
    overdue_items: int  # items older than 14 days
    items_by_tag: dict[str, int] = Field(default_factory=dict)
    oldest_item_days: int = 0
    items: list[TechDebtItem] = Field(default_factory=list)
    jan_verdict: str = Field(..., description="Jan's intense corporate assessment")


# ═══════════════════════════════════════════════════════════════════════
# Universal Chat Message (for the Web UI)
# ═══════════════════════════════════════════════════════════════════════

class AgentMessage(BaseModel):
    """
    A single message in the chatbot UI. Every agent response and user
    input is serialized as one of these and sent over the WebSocket.
    """
    session_id: str = Field("default", description="Session ID for tracking history")
    agent_name: str = Field(..., description="Display name of the character")
    agent_id: str = Field(..., description="Kebab-case identifier for avatar/color lookup")
    message: str = Field(..., description="The message text (may contain markdown)")
    message_type: str = Field(
        "agent_response",
        description="One of: user_input, agent_response, system, hitl_pause, hitl_resume, error"
    )
    flavor_quote: Optional[str] = Field(
        None,
        description="Random iconic quote from the character, injected for personality"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra data (e.g., HITL payload, structured results)"
    )

    def to_ws_json(self) -> dict:
        """Serialize for WebSocket transmission."""
        return {
            "agent_name": self.agent_name,
            "agent_id": self.agent_id,
            "message": self.message,
            "message_type": self.message_type,
            "flavor_quote": self.flavor_quote,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "session_id": self.session_id,
        }

class AuditLogEntry(BaseModel):
    """A single entry in the audit log database."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    action: str
    status: str
    details: str
    user: str = "system"
    agent: str = "system"
