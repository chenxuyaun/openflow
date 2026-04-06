from __future__ import annotations

import json
from pathlib import Path

from openflow.models import (
    DecisionRecord,
    KnowledgeItem,
    ProjectState,
    RoleInstanceSpec,
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
            "docs/master_prd.md",
            "docs/research_master_outline.md",
            "docs/knowledge_index.json",
            "docs/decision_registry.json",
            "docs/workflow_blueprint.json",
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
