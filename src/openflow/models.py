from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional

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


class GoalModel(BaseModel):
    project_id: str
    core_goal: str
    explicit_constraints: List[str] = Field(default_factory=list)
    implicit_constraints: List[str] = Field(default_factory=list)
    anti_goals: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    milestone_signals: List[str] = Field(default_factory=list)
    risk_tolerance: str = "medium"
    priority_policy: List[str] = Field(default_factory=list)


class CognitiveState(BaseModel):
    project_id: str
    validated_facts: List[str] = Field(default_factory=list)
    inferred_facts: List[str] = Field(default_factory=list)
    active_assumptions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    current_gaps: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    focus_now: str = "Clarify the next safe step."


class PlanStep(BaseModel):
    step_id: str
    title: str
    objective: str
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    completion_signals: List[str] = Field(default_factory=list)


class PlanLayers(BaseModel):
    project_id: str
    strategic: List[PlanStep] = Field(default_factory=list)
    phases: List[PlanStep] = Field(default_factory=list)
    milestones: List[PlanStep] = Field(default_factory=list)
    node_plan: List[PlanStep] = Field(default_factory=list)
    phase_status: List[str] = Field(default_factory=list)
    last_rewritten_by: Optional[str] = None


class TaskGraphNode(BaseModel):
    node_id: str
    task_id: str
    title: str
    phase: str
    node_type: str = "execution"
    intent: str
    owner_role: str
    dependency_nodes: List[str] = Field(default_factory=list)
    blocking_conditions: List[str] = Field(default_factory=list)
    completion_conditions: List[str] = Field(default_factory=list)
    rollback_conditions: List[str] = Field(default_factory=list)
    parallelizable: bool = False
    needs_human_confirm: bool = False
    needs_material_refresh: bool = False
    status: str = "planned"


class TaskGraphV2(BaseModel):
    project_id: str
    nodes: List[TaskGraphNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)
    replan_sources: List[str] = Field(default_factory=list)


class RoleProfile(BaseModel):
    role_name: str
    mission: str
    mindset: str
    profile_source: str = "registry"
    dynamic_profile: bool = False
    authority_scope: List[str] = Field(default_factory=list)
    output_contract: List[str] = Field(default_factory=list)
    focus_points: List[str] = Field(default_factory=list)
    guardrails: List[str] = Field(default_factory=list)
    preferred_tools: List[str] = Field(default_factory=list)


class CapabilityRegistryEntry(BaseModel):
    entry_id: str
    entry_type: str
    name: str
    purpose: str
    template_type: str = "default"
    applies_to: List[str] = Field(default_factory=list)
    activation_rules: List[str] = Field(default_factory=list)


class NodeCapabilityMapEntry(BaseModel):
    node_id: str
    role_name: str
    agent_profile: str
    mcp_set: List[str] = Field(default_factory=list)
    skill_set: List[str] = Field(default_factory=list)
    tool_set: List[str] = Field(default_factory=list)
    prompt_template: str
    required_files: List[str] = Field(default_factory=list)
    output_files: List[str] = Field(default_factory=list)
    memory_read_policy: str = "operational_memory_first"
    memory_write_policy: str = "append_structured_memory"
    verification_policy: List[str] = Field(default_factory=list)
    observability_policy: List[str] = Field(default_factory=list)
    resolution_source: str = "registry"
    precedence: int = 100
    fallback_roles: List[str] = Field(default_factory=list)
    dynamic_override: bool = False
    session_factory_policy: List[str] = Field(default_factory=list)


class ExecutionCapsule(BaseModel):
    project_id: str
    node_id: str
    role_name: str
    session_intent: str
    agent_profile: str
    mcp_set: List[str] = Field(default_factory=list)
    skill_set: List[str] = Field(default_factory=list)
    tool_set: List[str] = Field(default_factory=list)
    prompt_template: str
    required_files: List[str] = Field(default_factory=list)
    output_files: List[str] = Field(default_factory=list)
    memory_pack_refs: List[str] = Field(default_factory=list)
    verification_policy: List[str] = Field(default_factory=list)
    observability_policy: List[str] = Field(default_factory=list)
    session_config_payload: dict[str, Any] = Field(default_factory=dict)
    launch_readiness: bool = False
    missing_dependencies: List[str] = Field(default_factory=list)
    audit_requirements: List[str] = Field(default_factory=list)
    source_resolution: str = "registry"


class MemoryPack(BaseModel):
    pack_id: str
    layer: str
    title: str
    summary: str
    refs: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class ObservabilityEvent(BaseModel):
    event_id: str
    event_type: str
    title: str
    detail: str
    created_at: datetime = Field(default_factory=utc_now)
    refs: List[str] = Field(default_factory=list)


class ObservabilitySnapshot(BaseModel):
    project_id: str
    current_phase: str
    current_node_id: Optional[str] = None
    current_role: Optional[str] = None
    progress_percent: int = 0
    recent_events: List[ObservabilityEvent] = Field(default_factory=list)
    current_status: str = "active"


class RewriteIntent(BaseModel):
    target_type: str
    target_id: str
    action: str
    reason: str
    risk_level: str = "medium"
    auto_applied: bool = False


class ImprovementRecord(BaseModel):
    improvement_id: str
    created_at: datetime = Field(default_factory=utc_now)
    summary: str
    plan_updates: List[str] = Field(default_factory=list)
    mapping_updates: List[str] = Field(default_factory=list)
    next_focus: List[str] = Field(default_factory=list)
    rewrite_intents: List[RewriteIntent] = Field(default_factory=list)


class MultiUserPrewire(BaseModel):
    actor_id_field: str = "actor_id"
    actor_type_field: str = "actor_type"
    attribution_enabled: bool = True


class ExportPrewire(BaseModel):
    export_job_schema: str = "export_job_v1"
    artifact_bundle_schema: str = "artifact_bundle_v1"
    supported_targets: List[str] = Field(default_factory=lambda: ["report", "plan", "stakeholder_summary"])


class GovernancePrewire(BaseModel):
    policy_schema: str = "governance_policy_v1"
    supports_multi_step_approval: bool = True
    approval_statuses: List[str] = Field(default_factory=lambda: ["pending", "approved", "changes_requested", "replan_required"])


class AutoLaunchPrewire(BaseModel):
    policy_schema: str = "auto_launch_policy_v1"
    simulation_schema: str = "auto_launch_simulation_v1"
    supports_boundary_checks: bool = True


class ExecutionResult(BaseModel):
    status: str
    summary: str
    structured_outputs: dict[str, Any] = Field(default_factory=dict)
    recommended_handoff: dict[str, Any] = Field(default_factory=dict)
    memory_updates: List[dict[str, Any]] = Field(default_factory=list)
    observability_event: dict[str, Any] = Field(default_factory=dict)
    rewrite_intents: List[RewriteIntent] = Field(default_factory=list)


class ChatMessageRequest(BaseModel):
    project_id: str
    session_id: Optional[str] = None
    message: str
    mode: str = "simulated"
    action: str = "continue"


class ChatMessageResponse(BaseModel):
    project_id: str
    session_id: str
    node_id: str
    mode: str
    assistant_message: str
    execution_result: ExecutionResult
    updated_chat_workspace: dict[str, Any] = Field(default_factory=dict)
