from __future__ import annotations

import json
from pathlib import Path

from openflow.repository import OpenFlowRepository
from openflow.models import (
    BootstrapRequest,
    ChatMessageRequest,
    DecisionUpdateRequest,
    DecisionRecord,
    HandoffRecord,
    HandoffReviewRequest,
    KnowledgeItem,
    ProjectState,
    ResearchPackBatchIngestRequest,
    ResearchPackIngestRequest,
    RoleInstanceSpec,
    SessionCompleteRequest,
    SessionCreateRequest,
    SessionRecord,
    SessionStatus,
    SourceType,
    TaskNode,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeType,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT_DIR / "docs"
repository = OpenFlowRepository(ROOT_DIR, DOCS_DIR)


def _load_json_file(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_knowledge_items() -> list[KnowledgeItem]:
    payload = _load_json_file(DOCS_DIR / "knowledge_index.json")
    return [KnowledgeItem.model_validate(item) for item in payload]


def load_decisions() -> list[DecisionRecord]:
    payload = _load_json_file(DOCS_DIR / "decision_registry.json")
    return [DecisionRecord.model_validate(item) for item in payload]


def load_workflow_blueprint() -> dict[str, object]:
    payload = _load_json_file(DOCS_DIR / "workflow_blueprint.json")
    return dict(payload)


def load_blueprint_alignment() -> dict[str, object]:
    payload = _load_json_file(DOCS_DIR / "blueprint_alignment.json")
    return dict(payload)


def build_default_project_state() -> ProjectState:
    workflow_graph = WorkflowGraph(
        nodes=[
            WorkflowNode(
                node_id="bootstrap",
                role_name="Bootstrap Strategist",
                node_type=WorkflowNodeType.stage,
                objective="Turn the initial request into a workflow graph and task tree.",
            ),
            WorkflowNode(
                node_id="architecture",
                role_name="System Architect",
                node_type=WorkflowNodeType.task,
                objective="Translate the workflow into implementation-ready system boundaries.",
                handoff_policy="confirm",
            ),
        ],
        edges=[
            WorkflowEdge(from_node="bootstrap", to_node="architecture"),
        ],
    )

    role_catalog = [
        RoleInstanceSpec(
            role_name="Bootstrap Strategist",
            objective="Derive roles, workflow stages, and task decomposition from the first conversation.",
            scope="Initial project modeling only.",
            input_requirements=["initial request transcript"],
            output_contract=["workflow_graph", "role_catalog", "task_tree"],
            preferred_workflow=["read transcript", "extract goals", "design workflow"],
            tools_guidance=["Use project files as memory, not runtime context."],
        ),
        RoleInstanceSpec(
            role_name="System Architect",
            objective="Define the implementation boundaries for the next milestone.",
            scope="Architecture and API contracts.",
            input_requirements=["workflow_graph", "task_tree", "handoff.json"],
            output_contract=["architecture report", "next handoff"],
            preferred_workflow=["inspect files", "refine interfaces", "emit handoff"],
            tools_guidance=["Require confirmation before major direction changes."],
        ),
    ]

    task_tree = [
        TaskNode(
            task_id="m1-skeleton",
            title="Create the initial web app scaffold and data contracts.",
            status=SessionStatus.active,
            owner_role="Bootstrap Strategist",
            success_criteria=[
                "FastAPI app starts",
                "Core models are importable",
                "Pytest contract passes",
            ],
        ),
    ]

    sessions = [
        SessionRecord(
            session_id="bootstrap-session-001",
            role_name="Bootstrap Strategist",
            objective="Model the workflow and seed the first implementation milestone.",
            status=SessionStatus.active,
            input_files=["README.md"],
        ),
    ]

    return ProjectState(
        project_id="openflow-local",
        project_type_label="Build And Delivery",
        collaboration_style="guided_multi_role",
        user_facing_roles=["Planner", "Builder", "Reviewer"],
        workflow_graph=workflow_graph,
        role_catalog=role_catalog,
        task_tree=task_tree,
        sessions=sessions,
        knowledge_items=load_knowledge_items(),
        decisions=load_decisions(),
    )


def build_knowledge_summary() -> dict[str, object]:
    state = build_default_project_state()
    return {
        "project_id": state.project_id,
        "themes": [
            "product_narrative",
            "landing_conversion",
            "demo_conversion",
            "role_orchestration",
            "session_isolation",
            "handoff_governance",
            "knowledge_indexing",
            "execution_tracking",
            "review_replanning",
        ],
        "knowledge_items": [item.model_dump(mode="json") for item in state.knowledge_items],
        "decisions": [item.model_dump(mode="json") for item in state.decisions],
        "documents": [
            "docs/product_hook.md",
            "docs/landing_blueprint.md",
            "docs/demo_flow.md",
            "docs/taxonomy.md",
            "docs/master_prd.md",
            "docs/research_master_outline.md",
            "docs/knowledge_index.json",
            "docs/decision_registry.json",
            "docs/workflow_blueprint.json",
            "docs/blueprint_alignment.json",
        ],
    }


def build_workflow_summary() -> dict[str, object]:
    blueprint = load_workflow_blueprint()
    state = build_default_project_state()
    return {
        "project_id": state.project_id,
        "workflow_blueprint": blueprint,
        "workflow_graph": state.workflow_graph.model_dump(mode="json"),
        "role_catalog": [role.model_dump(mode="json") for role in state.role_catalog],
    }


def build_blueprint_package() -> dict[str, object]:
    state = build_default_project_state()
    workflow = load_workflow_blueprint()
    alignment = load_blueprint_alignment()
    return {
        "project_id": state.project_id,
        "hook_documents": [
            "docs/product_hook.md",
            "docs/landing_blueprint.md",
            "docs/demo_flow.md",
            "docs/taxonomy.md",
            "docs/master_prd.md",
        ],
        "workflow_pages": workflow.get("page_flow", []),
        "landing_sections": workflow.get("landing_sections", []),
        "demo_sections": workflow.get("demo_sections", []),
        "claims": alignment.get("product_claims", []),
        "decisions": [item.model_dump(mode="json") for item in state.decisions],
    }


def create_project(request: BootstrapRequest) -> dict[str, object]:
    payload = repository.bootstrap_project(request)
    return {
        "project_id": payload["project_id"],
        "session_id": payload["session_id"],
        "project_name": payload["project_name"],
        "state": payload["project_state"].model_dump(mode="json"),
    }


def create_project_session(request: SessionCreateRequest) -> dict[str, object]:
    session = repository.create_session(request)
    return session.model_dump(mode="json")


def complete_project_session(session_id: str, request: SessionCompleteRequest) -> dict[str, object]:
    handoff = repository.complete_session(session_id, request)
    return handoff.model_dump(mode="json")


def advance_project_handoff(handoff_id: str) -> dict[str, object]:
    return repository.advance_handoff(handoff_id)


def review_project_handoff(handoff_id: str, request: HandoffReviewRequest) -> dict[str, object]:
    return repository.review_handoff(handoff_id, request)


def ingest_project_research_pack(request: ResearchPackIngestRequest) -> dict[str, object]:
    return repository.ingest_research_pack(request)


def ingest_project_research_pack_batch(request: ResearchPackBatchIngestRequest) -> dict[str, object]:
    return repository.ingest_research_pack_batch(request)


def get_project_decisions(project_id: str) -> dict[str, object]:
    return repository.get_project_decisions(project_id)


def update_project_decision(project_id: str, decision_id: str, request: DecisionUpdateRequest) -> dict[str, object]:
    return repository.update_decision(project_id, decision_id, request)


def get_project_state(project_id: str) -> dict[str, object]:
    return repository.get_project_summary(project_id)


def get_project_knowledge(
    project_id: str,
    q: str | None = None,
    source_family: str | None = None,
    entry_kind: str | None = None,
    adoption_status: str | None = None,
    linked_only: bool = False,
) -> dict[str, object]:
    return repository.get_project_knowledge(
        project_id,
        q=q,
        source_family=source_family,
        entry_kind=entry_kind,
        adoption_status=adoption_status,
        linked_only=linked_only,
    )


def get_project_workflow(project_id: str) -> dict[str, object]:
    return repository.get_project_workflow(project_id)


def get_project_tasks(project_id: str) -> dict[str, object]:
    return repository.get_project_tasks(project_id)


def get_project_session_detail(project_id: str, session_id: str) -> dict[str, object]:
    return repository.get_session_detail(project_id, session_id)


def get_project_timeline(project_id: str) -> dict[str, object]:
    return repository.get_project_timeline(project_id)


def get_system_graph(project_id: str) -> dict[str, object]:
    return repository.get_system_graph(project_id)


def get_node_capsule(project_id: str, node_id: str) -> dict[str, object]:
    return repository.get_node_capsule(project_id, node_id)


def get_memory_index(project_id: str) -> dict[str, object]:
    return repository.get_memory_index(project_id)


def get_observability(project_id: str) -> dict[str, object]:
    return repository.get_observability(project_id)


def get_improvement_log(project_id: str) -> dict[str, object]:
    return repository.get_improvement_log(project_id)


def get_role_profiles(project_id: str) -> dict[str, object]:
    return repository.get_role_profiles(project_id)


def get_capabilities(project_id: str) -> dict[str, object]:
    return repository.get_capabilities(project_id)


def get_mappings(project_id: str) -> dict[str, object]:
    return repository.get_mappings(project_id)


def get_session_factory_preview(project_id: str, node_id: str) -> dict[str, object]:
    return repository.get_session_factory_preview(project_id, node_id)


def get_chat_workspace(project_id: str) -> dict[str, object]:
    return repository.get_chat_workspace(project_id)


def get_config_workspace(project_id: str) -> dict[str, object]:
    return repository.get_config_workspace(project_id)


def post_chat_message(project_id: str, request: ChatMessageRequest) -> dict[str, object]:
    return repository.post_chat_message(project_id, request)
