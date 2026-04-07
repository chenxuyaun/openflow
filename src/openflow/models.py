from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionStatus(str, Enum):
    planned = "planned"
    active = "active"
    waiting_confirmation = "waiting_confirmation"
    completed = "completed"


class WorkflowNodeType(str, Enum):
    stage = "stage"
    task = "task"


class SourceType(str, Enum):
    chat = "chat"
    repo = "repo"
    git = "git"
    doc = "doc"
    external = "external"


class WorkflowNode(BaseModel):
    node_id: str
    role_name: str
    node_type: WorkflowNodeType
    objective: str
    handoff_policy: str = Field(
        default="auto",
        description="auto or confirm",
    )


class WorkflowEdge(BaseModel):
    from_node: str
    to_node: str
    condition: str = "default"


class WorkflowGraph(BaseModel):
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)


class RoleInstanceSpec(BaseModel):
    role_name: str
    objective: str
    scope: str
    input_requirements: List[str] = Field(default_factory=list)
    output_contract: List[str] = Field(default_factory=list)
    preferred_workflow: List[str] = Field(default_factory=list)
    tools_guidance: List[str] = Field(default_factory=list)


class TaskNode(BaseModel):
    task_id: str
    title: str
    status: SessionStatus = SessionStatus.planned
    owner_role: str
    depends_on: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    blocked_reason: Optional[str] = None
    priority: str = "medium"
    evidence_refs: List[str] = Field(default_factory=list)
    governance_source: Optional[str] = None
    last_status_reason: Optional[str] = None


class SessionRecord(BaseModel):
    project_id: str = "openflow-local"
    session_id: str
    role_name: str
    objective: str
    status: SessionStatus
    created_at: datetime = Field(default_factory=utc_now)
    input_files: List[str] = Field(default_factory=list)


class KnowledgeItem(BaseModel):
    project_id: Optional[str] = None
    knowledge_id: str
    title: str
    source_type: SourceType
    source_family: str = "project_memory"
    entry_kind: str = "derived"
    adoption_status: str = "reference"
    source_ref: str
    summary: str
    themes: List[str] = Field(default_factory=list)
    reliability: str
    relevance: str
    decision_ids: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None
    handoff_id: Optional[str] = None
    generated_at: datetime = Field(default_factory=utc_now)
    open_questions: List[str] = Field(default_factory=list)


class DecisionRecord(BaseModel):
    project_id: Optional[str] = None
    decision_id: str
    title: str
    status: str
    rationale: str
    sources: List[str] = Field(default_factory=list)
    themes: List[str] = Field(default_factory=list)


class HandoffRecord(BaseModel):
    project_id: str
    session_id: str
    handoff_id: str
    status: str = "ready"
    created_at: datetime = Field(default_factory=utc_now)
    session_summary: str
    decision_updates: List[str] = Field(default_factory=list)
    task_status_changes: List[str] = Field(default_factory=list)
    next_role_recommendation: str
    next_role_reason: str
    required_input_files: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    review_outcome: Optional[str] = None
    acceptance_status: Optional[str] = None
    followup_actions: List[str] = Field(default_factory=list)
    review_note: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    resulting_role: Optional[str] = None


class ProjectState(BaseModel):
    project_id: str
    created_at: datetime = Field(default_factory=utc_now)
    project_mode: str = "delivery"
    project_type_label: str = "General Work"
    collaboration_style: str = "guided_multi_role"
    user_facing_roles: List[str] = Field(default_factory=list)
    attraction_focus: str = "visual_proof"
    research_slots: List[str] = Field(default_factory=list)
    governance_gates: List[str] = Field(default_factory=list)
    execution_priority: List[str] = Field(default_factory=list)
    workflow_graph: WorkflowGraph
    role_catalog: List[RoleInstanceSpec] = Field(default_factory=list)
    task_tree: List[TaskNode] = Field(default_factory=list)
    sessions: List[SessionRecord] = Field(default_factory=list)
    knowledge_items: List[KnowledgeItem] = Field(default_factory=list)
    decisions: List[DecisionRecord] = Field(default_factory=list)


class BootstrapRequest(BaseModel):
    goal: str
    initial_prompt: str
    project_name: Optional[str] = None
    preferred_project_mode: Optional[str] = None


class SessionCreateRequest(BaseModel):
    project_id: str
    role_name: str
    objective: str
    input_files: List[str] = Field(default_factory=list)


class SessionCompleteRequest(BaseModel):
    session_summary: str
    decision_updates: List[str] = Field(default_factory=list)
    task_status_changes: List[str] = Field(default_factory=list)
    next_role_recommendation: str
    next_role_reason: str
    required_input_files: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    review_outcome: Optional[str] = None
    acceptance_status: Optional[str] = None
    followup_actions: List[str] = Field(default_factory=list)
    transcript_note: Optional[str] = None


class HandoffReviewRequest(BaseModel):
    action: str
    note: Optional[str] = None


class ResearchPackIngestRequest(BaseModel):
    project_id: str
    pack_title: str
    source_family: str
    source_ref: str
    raw_notes: str
    synthesized_summary: str
    themes: List[str] = Field(default_factory=list)
    decision_ids: List[str] = Field(default_factory=list)
    adoption_status: str = "proposed"
    reliability: str = "medium"
    relevance: str = "high"


class ResearchPackBatchIngestRequest(BaseModel):
    project_id: str
    packs: List[ResearchPackIngestRequest] = Field(default_factory=list)


class DecisionUpdateRequest(BaseModel):
    status: str
