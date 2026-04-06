from fastapi.testclient import TestClient

from openflow.app import app
from openflow.service import (
    build_default_project_state,
    load_decisions,
    load_knowledge_items,
    load_workflow_blueprint,
)


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_project_endpoint_returns_seed_state() -> None:
    response = client.get("/project")

    assert response.status_code == 200
    body = response.json()

    assert body["project_id"] == "openflow-local"
    assert body["workflow_graph"]["nodes"][0]["role_name"] == "Bootstrap Strategist"
    assert body["task_tree"][0]["task_id"] == "m1-skeleton"


def test_default_project_state_has_confirm_gate() -> None:
    state = build_default_project_state()

    assert len(state.workflow_graph.nodes) == 2
    assert state.workflow_graph.nodes[1].handoff_policy == "confirm"
    assert state.sessions[0].status.value == "active"


def test_knowledge_endpoint_returns_documents_and_decisions() -> None:
    response = client.get("/knowledge")

    assert response.status_code == 200
    body = response.json()

    assert body["project_id"] == "openflow-local"
    assert "docs/product_hook.md" in body["documents"]
    assert any(item["decision_id"] == "dec-001" for item in body["decisions"])


def test_workflow_endpoint_returns_blueprint_and_roles() -> None:
    response = client.get("/workflow")

    assert response.status_code == 200
    body = response.json()

    assert body["project_id"] == "openflow-local"
    assert body["workflow_blueprint"]["stages"][0]["stage_id"] == "bootstrap"
    assert body["role_catalog"][0]["role_name"] == "Bootstrap Strategist"


def test_docs_backed_data_loaders_return_structured_records() -> None:
    knowledge_items = load_knowledge_items()
    decisions = load_decisions()
    blueprint = load_workflow_blueprint()

    assert any(item.knowledge_id == "ki-005" for item in knowledge_items)
    assert any(item.decision_id == "dec-005" for item in decisions)
    assert "page_flow" in blueprint
