import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from openflow.app import app
from openflow import service
from openflow.repository import OpenFlowRepository
from openflow.service import (
    build_default_project_state,
    get_project_timeline,
    load_blueprint_alignment,
    load_decisions,
    load_knowledge_items,
    load_workflow_blueprint,
)


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path) -> None:
    os.environ["OPENFLOW_DATA_DIR"] = str(tmp_path / "data")
    service.repository = OpenFlowRepository(service.ROOT_DIR, service.DOCS_DIR)
    yield
    os.environ.pop("OPENFLOW_DATA_DIR", None)
    service.repository = OpenFlowRepository(service.ROOT_DIR, service.DOCS_DIR)


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
    assert "docs/taxonomy.md" in body["documents"]
    assert any(item["decision_id"] == "dec-001" for item in body["decisions"])


def test_workflow_endpoint_returns_blueprint_and_roles() -> None:
    response = client.get("/workflow")

    assert response.status_code == 200
    body = response.json()

    assert body["project_id"] == "openflow-local"
    assert body["workflow_blueprint"]["stages"][0]["stage_id"] == "bootstrap"
    assert body["role_catalog"][0]["role_name"] == "Bootstrap Strategist"
    assert "landing" in body["workflow_blueprint"]["page_flow"]


def test_blueprint_endpoint_returns_claim_mappings() -> None:
    response = client.get("/blueprint")

    assert response.status_code == 200
    body = response.json()

    assert body["project_id"] == "openflow-local"
    assert "docs/landing_blueprint.md" in body["hook_documents"]
    assert "docs/demo_flow.md" in body["hook_documents"]
    assert "docs/taxonomy.md" in body["hook_documents"]
    assert "opening_frame" in body["demo_sections"]
    assert any(item["claim_id"] == "claim-001" for item in body["claims"])


def test_bootstrap_session_and_handoff_flow() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Build a file-driven role workflow.",
            "initial_prompt": "Turn this idea into a real OpenFlow project.",
            "project_name": "Flow Demo",
        },
    )
    assert bootstrap_response.status_code == 200
    bootstrap_body = bootstrap_response.json()
    project_id = bootstrap_body["project_id"]
    session_id = bootstrap_body["session_id"]

    project_response = client.get("/project", params={"project_id": project_id})
    assert project_response.status_code == 200
    assert project_response.json()["state"]["project_id"] == project_id

    session_response = client.post(
        "/sessions",
        json={
            "project_id": project_id,
            "role_name": "Implementation Lead",
            "objective": "Implement the next project slice.",
            "input_files": ["projects/project/workflow_graph.json"],
        },
    )
    assert session_response.status_code == 200
    created_session_id = session_response.json()["session_id"]

    complete_response = client.post(
        f"/sessions/{created_session_id}/complete",
        json={
            "session_summary": "Implemented the requested project slice.",
            "decision_updates": ["Keep file storage as source of truth."],
            "task_status_changes": ["implementation-slice=completed"],
            "next_role_recommendation": "Review Operator",
            "next_role_reason": "A review pass is needed.",
            "required_input_files": ["projects/project/session/handoff.json"],
            "success_criteria": ["Review the implementation evidence."],
            "risks": ["Review may request replanning."],
            "review_outcome": "pass",
            "acceptance_status": "accepted",
            "followup_actions": ["Advance to review."],
        },
    )
    assert complete_response.status_code == 200
    handoff_id = complete_response.json()["handoff_id"]

    advance_response = client.post(f"/handoffs/{handoff_id}/advance")
    assert advance_response.status_code == 200
    assert advance_response.json()["status"] == "advanced"
    assert advance_response.json()["session"]["role_name"] == "Review Operator"

    knowledge_response = client.get("/knowledge", params={"project_id": project_id})
    assert knowledge_response.status_code == 200
    knowledge_body = knowledge_response.json()
    assert len(knowledge_body["knowledge_items"]) >= 1
    assert any(item["source_ref"].endswith("/handoff.json") for item in knowledge_body["knowledge_items"])
    assert "README.md" in knowledge_body["blueprint_documents"]

    task_response = client.get(f"/projects/{project_id}/tasks")
    assert task_response.status_code == 200
    assert "Task Board" in task_response.text
    assert "Completed" in task_response.text


def test_read_only_pages_render_real_project_data() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Render project views from real files.",
            "initial_prompt": "Create a project so the read-only UI can load it.",
            "project_name": "UI Demo",
        },
    )
    body = bootstrap_response.json()
    project_id = body["project_id"]
    session_id = body["session_id"]

    landing_response = client.get("/")
    assert landing_response.status_code == 200
    assert "Every new role can start fresh without losing the work." in landing_response.text
    assert "What You Bring In" in landing_response.text
    assert "Why This Works Better Than Ordinary Chat Threads" in landing_response.text
    assert "Project memory stays in files" in landing_response.text
    assert "What You See In The Workspace" in landing_response.text

    welcome_response = client.get(f"/projects/{project_id}/welcome")
    assert welcome_response.status_code == 200
    assert "Workspace Ready" in welcome_response.text
    assert "Open Workspace" in welcome_response.text
    assert "Suggested Next Step" in welcome_response.text
    assert "Continue Recommended Step" in welcome_response.text or "Start First Work Step" in welcome_response.text

    project_response = client.get(f"/projects/{project_id}")
    assert project_response.status_code == 200
    assert "UI Demo" in project_response.text
    assert "Workspace Overview" in project_response.text
    assert "Current Goal" in project_response.text
    assert "Advanced Workspace Tools" in project_response.text
    assert "Open Welcome Guide" in project_response.text
    assert "Suggested Next Step" in project_response.text

    knowledge_response = client.get(f"/projects/{project_id}/knowledge")
    assert knowledge_response.status_code == 200
    assert "Materials Center" in knowledge_response.text
    assert "Blueprint Documents" in knowledge_response.text

    workflow_response = client.get(f"/projects/{project_id}/workflow")
    assert workflow_response.status_code == 200
    assert "Bootstrap Strategist" in workflow_response.text

    session_response = client.get(f"/projects/{project_id}/sessions/{session_id}")
    assert session_response.status_code == 200
    assert "Work Step Detail" in session_response.text


def test_docs_backed_data_loaders_return_structured_records() -> None:
    knowledge_items = load_knowledge_items()
    decisions = load_decisions()
    blueprint = load_workflow_blueprint()
    alignment = load_blueprint_alignment()

    assert any(item.knowledge_id == "ki-005" for item in knowledge_items)
    assert any(item.knowledge_id == "ki-007" for item in knowledge_items)
    assert any(item.knowledge_id == "ki-008" for item in knowledge_items)
    assert any(item.decision_id == "dec-006" for item in decisions)
    assert any(item.decision_id == "dec-007" for item in decisions)
    assert "page_flow" in blueprint
    assert "landing_sections" in blueprint
    assert "demo_sections" in blueprint
    assert any(item["claim_id"] == "claim-003" for item in alignment["product_claims"])
    assert "landing_sections" in alignment["product_claims"][0]["supports"]
    assert "demo_sections" in alignment["product_claims"][0]["supports"]
    assert "types" in alignment["product_claims"][0]["supports"]


def test_bootstrap_auto_ingests_project_knowledge_items() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Verify automatic project knowledge ingest.",
            "initial_prompt": "Seed project knowledge from bootstrap artifacts.",
            "project_name": "Knowledge Seed",
        },
    )
    project_id = bootstrap_response.json()["project_id"]

    knowledge_response = client.get("/knowledge", params={"project_id": project_id})
    assert knowledge_response.status_code == 200
    items = knowledge_response.json()["knowledge_items"]

    assert any(item["knowledge_id"] == f"project-meta-{project_id}" for item in items)
    assert any(item["knowledge_id"] == f"workflow-{project_id}" for item in items)
    assert any(item["knowledge_id"] == f"task-tree-{project_id}" for item in items)

    project_response = client.get("/project", params={"project_id": project_id})
    state = project_response.json()["state"]
    assert state["attraction_focus"] in {"visual_proof", "knowledge_proof", "experience_proof"}
    assert len(state["research_slots"]) >= 3
    assert len(state["governance_gates"]) >= 3
    assert state["project_type_label"]
    assert state["collaboration_style"]
    assert len(state["user_facing_roles"]) >= 3


def test_bootstrap_generation_changes_with_request_shape() -> None:
    research_bootstrap = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Collect broad research materials and organize them into reusable knowledge.",
            "initial_prompt": "Need a research-heavy flow that curates sources, records decisions, and keeps file-based memory.",
            "project_name": "Research Heavy",
        },
    )
    implementation_bootstrap = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Implement a session orchestration runtime with workflow execution.",
            "initial_prompt": "Need an implementation-heavy project with role handoffs, execution, and review.",
            "project_name": "Execution Heavy",
        },
    )

    research_state = research_bootstrap.json()["state"]
    implementation_state = implementation_bootstrap.json()["state"]

    research_roles = {item["role_name"] for item in research_state["role_catalog"]}
    implementation_roles = {item["role_name"] for item in implementation_state["role_catalog"]}
    research_titles = [item["title"] for item in research_state["task_tree"]]
    implementation_titles = [item["title"] for item in implementation_state["task_tree"]]

    assert len(research_state["task_tree"]) >= 4
    assert len(implementation_state["task_tree"]) >= 4
    assert "Research Curator" in research_roles
    assert "Implementation Lead" in implementation_roles
    assert research_roles != implementation_roles
    assert research_titles != implementation_titles
    assert any(edge["condition"] == "research-needed" for edge in research_state["workflow_graph"]["edges"])
    assert any(edge["to_node"] == "review" for edge in implementation_state["workflow_graph"]["edges"])


def test_form_driven_project_flow_and_transcript_summary() -> None:
    landing_response = client.post(
        "/",
        data={
            "project_name": "Form Project",
            "goal": "Drive the project from forms.",
            "initial_prompt": "Create an operable project from the landing page.",
        },
        follow_redirects=False,
    )
    assert landing_response.status_code == 303
    project_url = landing_response.headers["location"]
    assert project_url.endswith("/welcome")
    project_id = project_url.split("/")[-2]

    welcome_response = client.get(project_url)
    assert welcome_response.status_code == 200
    assert "Workspace Ready" in welcome_response.text
    assert "Start First Work Step" in welcome_response.text or "Continue Recommended Step" in welcome_response.text

    welcome_start_response = client.post(
        f"/projects/{project_id}/sessions",
        data={
            "role_name": "Implementation Lead",
            "objective": "Start the first practical step for this workspace and move the project toward a visible next result.",
            "input_files": f"projects/{project_id}/workflow_graph.json",
        },
        follow_redirects=False,
    )
    assert welcome_start_response.status_code == 303
    assert "/sessions/" in welcome_start_response.headers["location"]

    session_create_response = client.post(
        f"/projects/{project_id}/sessions",
        data={
            "role_name": "Implementation Lead",
            "objective": "Implement through the writable UI.",
            "input_files": f"projects/{project_id}/workflow_graph.json",
        },
        follow_redirects=False,
    )
    assert session_create_response.status_code == 303
    session_url = session_create_response.headers["location"]
    session_id = session_url.rsplit("/", 1)[-1]

    complete_response = client.post(
        f"/projects/{project_id}/sessions/{session_id}/complete",
        data={
            "session_summary": "Completed the writable UI session.",
            "next_role_recommendation": "Review Operator",
            "next_role_reason": "Review the submitted changes.",
            "required_input_files": f"projects/{project_id}/sessions/{session_id}/handoff.json",
            "success_criteria": "Check the implementation",
            "risks": "May need replanning",
            "task_status_changes": "implementation-slice=completed",
            "review_outcome": "pass",
            "acceptance_status": "accepted",
            "followup_actions": "Advance to review",
            "transcript_note": "Implemented the session through page forms.",
        },
        follow_redirects=False,
    )
    assert complete_response.status_code == 303
    assert complete_response.headers["location"].endswith(f"/projects/{project_id}/sessions/{session_id}?completed=1")

    completed_session_page = client.get(complete_response.headers["location"])
    assert completed_session_page.status_code == 200
    assert "This step has been saved." in completed_session_page.text
    assert "Start Suggested Next Step" in completed_session_page.text

    knowledge_response = client.get(f"/projects/{project_id}/knowledge")
    assert knowledge_response.status_code == 200
    assert "Evolution Feed" in knowledge_response.text
    assert "Transcript summary" in knowledge_response.text or "Tasks completed:" in knowledge_response.text

    task_board_response = client.get(f"/projects/{project_id}/tasks")
    assert task_board_response.status_code == 200
    assert "Task Board" in task_board_response.text


def test_transcript_summary_becomes_structured_knowledge() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Create structured session knowledge.",
            "initial_prompt": "Bootstrap a project that turns transcripts into reusable execution records.",
            "project_name": "Structured Transcript",
        },
    )
    session_id = bootstrap_response.json()["session_id"]
    project_id = bootstrap_response.json()["project_id"]

    complete_response = client.post(
        f"/sessions/{session_id}/complete",
        json={
            "session_summary": "Bootstrap analysis finished.",
            "next_role_recommendation": "System Architect",
            "next_role_reason": "Lock the execution contracts.",
            "transcript_note": "Implemented the bootstrap map. Keep file memory as the source of truth. Risk: research coverage is still shallow. Next review should confirm workflow edges.",
        },
    )
    assert complete_response.status_code == 200

    knowledge_response = client.get("/knowledge", params={"project_id": project_id})
    items = knowledge_response.json()["knowledge_items"]
    transcript_item = next(item for item in items if item["knowledge_id"] == f"transcript-summary-{session_id}")

    assert "Tasks completed:" in transcript_item["summary"]
    assert "Key decisions:" in transcript_item["summary"]
    assert "Risks or blockers:" in transcript_item["summary"]
    assert "Recommended next step:" in transcript_item["summary"]


def test_timeline_includes_git_and_handoff_events() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Build a timeline-rich project.",
            "initial_prompt": "Create timeline events from project activity.",
            "project_name": "Timeline Demo",
        },
    )
    project_id = bootstrap_response.json()["project_id"]
    session_id = bootstrap_response.json()["session_id"]

    complete_response = client.post(
        f"/sessions/{session_id}/complete",
        json={
            "session_summary": "Bootstrap session completed.",
            "next_role_recommendation": "System Architect",
            "next_role_reason": "Architecture review is required.",
            "transcript_note": "Captured a note for the timeline.",
        },
    )
    handoff_id = complete_response.json()["handoff_id"]

    timeline = get_project_timeline(project_id)
    assert any(item["event_type"] == "git_commit_ingested" for item in timeline["events"])
    assert any(item["event_type"] == "handoff_written" for item in timeline["events"])

    project_page = client.get(f"/projects/{project_id}")
    assert project_page.status_code == 200
    assert "Project Timeline" in project_page.text

    advance_response = client.post(
        f"/projects/{project_id}/handoffs/{handoff_id}/advance",
        follow_redirects=False,
    )
    assert advance_response.status_code == 303
    assert "handoff_status" in advance_response.headers["location"]


def test_confirm_gate_review_can_approve_and_then_advance() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Build a project that requires architecture confirmation.",
            "initial_prompt": "Create a workflow that hands off into System Architect.",
            "project_name": "Confirm Demo",
        },
    )
    session_id = bootstrap_response.json()["session_id"]
    project_id = bootstrap_response.json()["project_id"]

    complete_response = client.post(
        f"/sessions/{session_id}/complete",
        json={
            "session_summary": "Bootstrap complete.",
            "next_role_recommendation": "System Architect",
            "next_role_reason": "Architecture review is required.",
            "acceptance_status": "pending_review",
        },
    )
    handoff_id = complete_response.json()["handoff_id"]

    blocked_advance = client.post(f"/handoffs/{handoff_id}/advance")
    assert blocked_advance.status_code == 200
    assert blocked_advance.json()["status"] == "waiting_confirmation"

    review_response = client.post(
        f"/handoffs/{handoff_id}/review",
        json={"action": "approve", "note": "The architecture gate is satisfied."},
    )
    assert review_response.status_code == 200
    assert review_response.json()["acceptance_status"] == "approved"

    approved_advance = client.post(f"/handoffs/{handoff_id}/advance")
    assert approved_advance.status_code == 200
    assert approved_advance.json()["status"] == "advanced"
    assert approved_advance.json()["session"]["role_name"] == "System Architect"

    project_page = client.get(f"/projects/{project_id}")
    assert project_page.status_code == 200
    assert "approved" in project_page.text
    assert "Why This Step Is Recommended" in project_page.text

    reviewed_project_page = client.get(f"/projects/{project_id}?review_status=approved")
    assert reviewed_project_page.status_code == 200
    assert "Review complete. This next step is approved and ready to continue." in reviewed_project_page.text


def test_research_pack_ingest_creates_raw_and_synthesized_items() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Collect research and turn it into reusable project memory.",
            "initial_prompt": "Need a research-heavy project.",
            "project_name": "Research Pack Demo",
        },
    )
    project_id = bootstrap_response.json()["project_id"]

    ingest_response = client.post(
        "/research-packs",
        json={
            "project_id": project_id,
            "pack_title": "Adjacent workflow systems",
            "source_family": "competitor_and_adjacent_products",
            "source_ref": "manual-notes",
            "raw_notes": "Raw notes from reviewing adjacent workflow tools.",
            "synthesized_summary": "Adopt explicit handoff visibility and reject hidden state transitions.",
            "themes": ["product_narrative", "handoff_governance"],
            "adoption_status": "adopted",
            "reliability": "medium",
            "relevance": "high",
        },
    )
    assert ingest_response.status_code == 200
    assert len(ingest_response.json()["items"]) == 2

    knowledge_response = client.get("/knowledge", params={"project_id": project_id})
    assert knowledge_response.status_code == 200
    payload = knowledge_response.json()

    assert "competitor_and_adjacent_products" in payload["research_groups"]
    assert any(item["entry_kind"] == "raw_source" for item in payload["knowledge_items"])
    assert any(item["entry_kind"] == "synthesized_insight" for item in payload["knowledge_items"])
    assert "decision_support" in payload
    assert payload["materials"]["organized_material_count"] >= 2

    knowledge_page = client.get(f"/projects/{project_id}/knowledge")
    assert knowledge_page.status_code == 200
    assert "Organize Materials" in knowledge_page.text
    assert "Organize Many Materials At Once" in knowledge_page.text
    assert "Grouped Materials" in knowledge_page.text
    assert "Source Groups" in knowledge_page.text
    assert "Decisions Influenced By Research" in knowledge_page.text


def test_batch_research_pack_ingest_groups_multiple_packs() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Organize multiple research sources at once.",
            "initial_prompt": "Need batch research pack ingest.",
            "project_name": "Batch Research Demo",
        },
    )
    project_id = bootstrap_response.json()["project_id"]

    batch_response = client.post(
        "/research-packs/batch",
        json={
            "project_id": project_id,
            "packs": [
                {
                    "project_id": project_id,
                    "pack_title": "Workflow review",
                    "source_family": "workflow_handoff_methods",
                    "source_ref": "notes-a",
                    "raw_notes": "Raw notes A",
                    "synthesized_summary": "Summary A",
                },
                {
                    "project_id": project_id,
                    "pack_title": "Competitor scan",
                    "source_family": "competitor_and_adjacent_products",
                    "source_ref": "notes-b",
                    "raw_notes": "Raw notes B",
                    "synthesized_summary": "Summary B",
                },
            ],
        },
    )
    assert batch_response.status_code == 200
    assert len(batch_response.json()["items"]) == 4

    knowledge_response = client.get("/knowledge", params={"project_id": project_id})
    payload = knowledge_response.json()
    assert "workflow_handoff_methods" in payload["research_groups"]
    assert "competitor_and_adjacent_products" in payload["research_groups"]
    assert payload["materials"]["research_group_count"] >= 2


def test_knowledge_page_supports_search_and_filters() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Organize and search knowledge materials.",
            "initial_prompt": "Need a workspace with searchable materials and decision-linked notes.",
            "project_name": "Knowledge Filter Demo",
        },
    )
    project_id = bootstrap_response.json()["project_id"]
    project_payload = client.get("/project", params={"project_id": project_id}).json()
    decision_id = project_payload["state"]["decisions"][0]["decision_id"]

    ingest_response = client.post(
        "/research-packs",
        json={
            "project_id": project_id,
            "pack_title": "Decision-linked workflow review",
            "source_family": "workflow_handoff_methods",
            "source_ref": "search-notes",
            "raw_notes": "Raw notes for searchable workflow review.",
            "synthesized_summary": "Workflow summary linked to a decision.",
            "decision_ids": [decision_id],
            "adoption_status": "adopted",
        },
    )
    assert ingest_response.status_code == 200

    filtered_page = client.get(
        f"/projects/{project_id}/knowledge",
        params={
            "q": "decision-linked",
            "source_family": "workflow_handoff_methods",
            "entry_kind": "synthesized_insight",
            "adoption_status": "adopted",
            "linked_only": "true",
        },
    )
    assert filtered_page.status_code == 200
    assert "Showing 1 filtered items." in filtered_page.text
    assert "Decision-linked workflow review synthesized insight" in filtered_page.text
    assert "Only show decision-linked materials" in filtered_page.text


def test_decision_registry_can_update_status() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Track decision status changes.",
            "initial_prompt": "Need a decision governance surface.",
            "project_name": "Decision Demo",
        },
    )
    project_id = bootstrap_response.json()["project_id"]

    decisions_response = client.get(f"/projects/{project_id}/decisions")
    assert decisions_response.status_code == 200
    assert "Decision Registry" in decisions_response.text

    project_payload = client.get("/project", params={"project_id": project_id}).json()
    decision_id = project_payload["state"]["decisions"][0]["decision_id"]
    update_response = client.post(
        f"/projects/{project_id}/decisions/{decision_id}",
        json={"status": "deferred"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "deferred"

    decisions_payload = client.get(f"/projects/{project_id}/decisions").text
    assert "deferred" in decisions_payload


def test_project_dashboard_shows_governance_and_task_board_link() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Create a compelling, visible workflow system.",
            "initial_prompt": "Bootstrap roles, governance, and research-backed project memory.",
            "project_name": "Governance Demo",
        },
    )
    project_id = bootstrap_response.json()["project_id"]

    project_page = client.get(f"/projects/{project_id}")
    assert project_page.status_code == 200
    assert "Task Board" in project_page.text
    assert "Advanced Workspace Tools" in project_page.text
    assert "Suggested Next Step" in project_page.text
    assert "Why This Step Is Recommended" in project_page.text
    assert "Work type:" in project_page.text
    assert "Organize Materials" in project_page.text


def test_project_page_surfaces_confirm_review_in_main_path() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Create a project with a review-blocked next step.",
            "initial_prompt": "Create a workflow that hands off into System Architect for confirmation.",
            "project_name": "Main Path Review Demo",
        },
    )
    session_id = bootstrap_response.json()["session_id"]
    project_id = bootstrap_response.json()["project_id"]

    complete_response = client.post(
        f"/sessions/{session_id}/complete",
        json={
            "session_summary": "Bootstrap complete.",
            "next_role_recommendation": "System Architect",
            "next_role_reason": "Architecture confirmation is required.",
            "acceptance_status": "pending_review",
        },
    )
    assert complete_response.status_code == 200

    project_page = client.get(f"/projects/{project_id}")
    assert project_page.status_code == 200
    assert "This next step needs a review before it can start." in project_page.text
    assert "Continue" in project_page.text
    assert "Needs Changes" in project_page.text
    assert "Replan" in project_page.text
    assert "The review controls are surfaced in Suggested Next Step so the main path stays visible." in project_page.text


def test_welcome_page_handles_confirm_gated_next_step() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Create a project that requires a reviewed next step.",
            "initial_prompt": "Create a workflow that hands off into System Architect for confirmation.",
            "project_name": "Welcome Gate Demo",
        },
    )
    project_id = bootstrap_response.json()["project_id"]
    session_id = bootstrap_response.json()["session_id"]

    complete_response = client.post(
        f"/sessions/{session_id}/complete",
        json={
            "session_summary": "Bootstrap complete.",
            "next_role_recommendation": "System Architect",
            "next_role_reason": "Architecture confirmation is required.",
            "acceptance_status": "pending_review",
        },
    )
    assert complete_response.status_code == 200

    welcome_response = client.get(f"/projects/{project_id}/welcome")
    assert welcome_response.status_code == 200
    assert "needs review before it can continue" in welcome_response.text
    assert "Open Workspace" in welcome_response.text


def test_welcome_page_can_start_first_work_step_when_no_next_step_exists() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Create a project with no ready-made next step.",
            "initial_prompt": "Bootstrap the workspace and leave the first step to be started manually.",
            "project_name": "Welcome Start Demo",
        },
    )
    project_id = bootstrap_response.json()["project_id"]

    welcome_response = client.get(f"/projects/{project_id}/welcome")
    assert welcome_response.status_code == 200
    assert "Start First Work Step" in welcome_response.text

    start_response = client.post(
        f"/projects/{project_id}/sessions",
        data={
            "role_name": "Implementation Lead",
            "objective": "Start the first practical step for this workspace and move the project toward a visible next result.",
            "input_files": f"projects/{project_id}/workflow_graph.json",
        },
        follow_redirects=False,
    )
    assert start_response.status_code == 303
    session_location = start_response.headers["location"]
    session_page = client.get(session_location)
    assert session_page.status_code == 200
    assert "Work Step Detail" in session_page.text


def test_research_project_recommends_organizing_materials_first() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Collect research and organize sources into reusable knowledge.",
            "initial_prompt": "Need a research-heavy workspace that should organize materials before execution.",
            "project_name": "Research Recommendation Demo",
        },
    )
    project_id = bootstrap_response.json()["project_id"]

    project_page = client.get(f"/projects/{project_id}")
    assert project_page.status_code == 200
    assert "Research Curator" in project_page.text
    assert "This workspace should organize materials before the next execution step." in project_page.text
    assert "Organize Materials" in project_page.text

    welcome_page = client.get(f"/projects/{project_id}/welcome")
    assert welcome_page.status_code == 200
    assert "Research Curator" in welcome_page.text
    assert "Organize Materials" in welcome_page.text


def test_research_project_with_more_raw_than_synthesized_keeps_curator_recommendation() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Collect research and organize sources into reusable knowledge.",
            "initial_prompt": "Need a research-heavy workspace that should organize materials before execution.",
            "project_name": "Raw Gap Demo",
        },
    )
    project_id = bootstrap_response.json()["project_id"]

    ingest_response = client.post(
        "/research-packs",
        json={
            "project_id": project_id,
            "pack_title": "Raw-heavy source review",
            "source_family": "workflow_handoff_methods",
            "source_ref": "raw-gap-notes",
            "raw_notes": "Raw-heavy notes for the recommendation engine.",
            "synthesized_summary": "Short synthesis.",
        },
    )
    assert ingest_response.status_code == 200

    project_page = client.get(f"/projects/{project_id}")
    assert project_page.status_code == 200
    assert "Research Curator" in project_page.text
    assert "Raw sources:" in project_page.text


def test_session_page_shows_feedback_after_completion_and_after_advance() -> None:
    landing_response = client.post(
        "/",
        data={
            "project_name": "Feedback Demo",
            "goal": "Close the feedback loop after a work step is completed.",
            "initial_prompt": "Create a project with a clear next-step handoff experience.",
        },
        follow_redirects=False,
    )
    assert landing_response.status_code == 303
    project_id = landing_response.headers["location"].split("/")[-2]

    session_create_response = client.post(
        f"/projects/{project_id}/sessions",
        data={
            "role_name": "Implementation Lead",
            "objective": "Complete the first visible execution step.",
            "input_files": f"projects/{project_id}/workflow_graph.json",
        },
        follow_redirects=False,
    )
    assert session_create_response.status_code == 303
    session_url = session_create_response.headers["location"]
    session_id = session_url.rsplit("/", 1)[-1]

    complete_response = client.post(
        f"/projects/{project_id}/sessions/{session_id}/complete",
        data={
            "session_summary": "Completed the first execution step.",
            "next_role_recommendation": "Review Operator",
            "next_role_reason": "Review should continue next.",
            "required_input_files": f"projects/{project_id}/sessions/{session_id}/handoff.json",
            "success_criteria": "Review the execution output",
            "risks": "May require refinement",
            "followup_actions": "Start the review step",
        },
        follow_redirects=False,
    )
    assert complete_response.status_code == 303

    completed_page = client.get(complete_response.headers["location"])
    assert completed_page.status_code == 200
    assert "This step has been saved." in completed_page.text
    assert "What should happen next:" in completed_page.text
    assert "Start Suggested Next Step" in completed_page.text

    project_payload = client.get("/project", params={"project_id": project_id}).json()
    handoff_id = project_payload["latest_handoff"]["handoff_id"]
    advance_response = client.post(
        f"/projects/{project_id}/handoffs/{handoff_id}/advance",
        follow_redirects=False,
    )
    assert advance_response.status_code == 303

    next_session_page = client.get(advance_response.headers["location"])
    assert next_session_page.status_code == 200
    assert "The previous step handed work to this session." in next_session_page.text


def test_changes_requested_reactivates_task_with_governance_reason() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Build a workflow that will require changes.",
            "initial_prompt": "Create a workflow that hands off into System Architect for confirmation.",
            "project_name": "Changes Requested Demo",
        },
    )
    session_id = bootstrap_response.json()["session_id"]
    project_id = bootstrap_response.json()["project_id"]
    complete_response = client.post(
        f"/sessions/{session_id}/complete",
        json={
            "session_summary": "Bootstrap complete.",
            "next_role_recommendation": "System Architect",
            "next_role_reason": "Architecture confirmation is needed.",
            "acceptance_status": "pending_review",
        },
    )
    handoff_id = complete_response.json()["handoff_id"]
    review_response = client.post(
        f"/handoffs/{handoff_id}/review",
        json={"action": "changes_requested", "note": "The implementation package needs another pass."},
    )
    assert review_response.status_code == 200
    assert review_response.json()["next_role"] == "Bootstrap Strategist"

    task_board = client.get(f"/projects/{project_id}/tasks")
    assert task_board.status_code == 200
    assert "Governance-Affected Tasks" in task_board.text
    assert "confirm_gate_review" in task_board.text

    session_page = client.get(f"/projects/{project_id}/sessions/{session_id}")
    assert session_page.status_code == 200
    assert "Review note:" in session_page.text


def test_replan_required_updates_recommendation_to_replan_role() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Build a workflow that will require replanning.",
            "initial_prompt": "Create a workflow that hands off into System Architect for confirmation.",
            "project_name": "Replan Recommendation Demo",
        },
    )
    session_id = bootstrap_response.json()["session_id"]
    project_id = bootstrap_response.json()["project_id"]

    complete_response = client.post(
        f"/sessions/{session_id}/complete",
        json={
            "session_summary": "Bootstrap complete.",
            "next_role_recommendation": "System Architect",
            "next_role_reason": "Architecture confirmation is needed.",
            "acceptance_status": "pending_review",
        },
    )
    handoff_id = complete_response.json()["handoff_id"]

    review_response = client.post(
        f"/handoffs/{handoff_id}/review",
        json={"action": "replan_required", "note": "The direction should be replanned before execution continues."},
    )
    assert review_response.status_code == 200

    project_page = client.get(f"/projects/{project_id}")
    assert project_page.status_code == 200
    assert "The direction should be replanned before execution continues." in project_page.text
    assert "Research Curator" in project_page.text or "Bootstrap Strategist" in project_page.text


def test_decision_conflict_changes_recommendation_to_review() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Advance work only when supporting decisions are still valid.",
            "initial_prompt": "Need decision-linked materials that can force a review when direction changes.",
            "project_name": "Decision Conflict Demo",
        },
    )
    project_id = bootstrap_response.json()["project_id"]
    project_payload = client.get("/project", params={"project_id": project_id}).json()
    decision_id = project_payload["state"]["decisions"][0]["decision_id"]

    ingest_response = client.post(
        "/research-packs",
        json={
            "project_id": project_id,
            "pack_title": "Decision conflict notes",
            "source_family": "workflow_handoff_methods",
            "source_ref": "decision-conflict",
            "raw_notes": "Raw notes tied to an important decision.",
            "synthesized_summary": "This direction depends on a decision that may no longer hold.",
            "decision_ids": [decision_id],
        },
    )
    assert ingest_response.status_code == 200

    update_response = client.post(
        f"/projects/{project_id}/decisions/{decision_id}",
        json={"status": "deferred"},
    )
    assert update_response.status_code == 200

    project_page = client.get(f"/projects/{project_id}")
    assert project_page.status_code == 200
    assert "Review Operator" in project_page.text
    assert "deferred or rejected" in project_page.text
    assert "Conflicting decision-linked materials: 2." in project_page.text


def test_governance_blocked_task_does_not_offer_direct_start() -> None:
    landing_response = client.post(
        "/",
        data={
            "project_name": "Governance Block Demo",
            "goal": "Implement work only after governance review.",
            "initial_prompt": "Create an implementation-heavy project where the next step should be blocked by governance until reviewed.",
        },
        follow_redirects=False,
    )
    project_id = landing_response.headers["location"].split("/")[-2]

    session_create_response = client.post(
        f"/projects/{project_id}/sessions",
        data={
            "role_name": "Implementation Lead",
            "objective": "Create a handoff with a governance block.",
            "input_files": f"projects/{project_id}/workflow_graph.json",
        },
        follow_redirects=False,
    )
    session_id = session_create_response.headers["location"].rsplit("/", 1)[-1]

    complete_response = client.post(
        f"/projects/{project_id}/sessions/{session_id}/complete",
        data={
            "session_summary": "Completed the execution step but governance must inspect a blocked task first.",
            "next_role_recommendation": "Review Operator",
            "next_role_reason": "Review should continue next.",
            "required_input_files": f"projects/{project_id}/sessions/{session_id}/handoff.json",
            "task_status_changes": "implementation-slice=waiting_confirmation:Governance review must clear this task first.",
            "followup_actions": "Inspect the blocked task before advancing.",
        },
        follow_redirects=False,
    )
    assert complete_response.status_code == 303

    project_page = client.get(f"/projects/{project_id}")
    assert project_page.status_code == 200
    assert "This workspace should resolve the current block before starting the next step." in project_page.text
    assert "Open Details" in project_page.text
    assert "Start Suggested Next Step" not in project_page.text


def test_session_review_form_redirects_back_with_feedback() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Keep review feedback on the current session page.",
            "initial_prompt": "Create a workflow that hands off into System Architect for confirmation.",
            "project_name": "Session Review Feedback Demo",
        },
    )
    session_id = bootstrap_response.json()["session_id"]
    project_id = bootstrap_response.json()["project_id"]

    complete_response = client.post(
        f"/sessions/{session_id}/complete",
        json={
            "session_summary": "Bootstrap complete.",
            "next_role_recommendation": "System Architect",
            "next_role_reason": "Architecture confirmation is required.",
            "acceptance_status": "pending_review",
        },
    )
    handoff_id = complete_response.json()["handoff_id"]

    review_response = client.post(
        f"/projects/{project_id}/handoffs/{handoff_id}/review",
        data={
            "action": "changes_requested",
            "note": "Tighten the architecture package before continuing.",
            "return_to": "session",
            "session_id": session_id,
        },
        follow_redirects=False,
    )
    assert review_response.status_code == 303
    assert review_response.headers["location"].endswith(
        f"/projects/{project_id}/sessions/{session_id}?review_status=changes_requested"
    )

    session_page = client.get(review_response.headers["location"])
    assert session_page.status_code == 200
    assert "Review complete." in session_page.text
    assert "Another pass is needed before this work moves forward." in session_page.text
    assert "Tighten the architecture package before continuing." in session_page.text


def test_timeline_includes_because_explanations() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Create a timeline with clear reasons.",
            "initial_prompt": "Turn project activity into explainable events.",
            "project_name": "Because Demo",
        },
    )
    project_id = bootstrap_response.json()["project_id"]

    timeline = get_project_timeline(project_id)
    assert all("because" in item for item in timeline["events"])


def test_material_organization_creates_timeline_event() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Organize source material into reusable project memory.",
            "initial_prompt": "Need a materials workflow that preserves raw notes and synthesized insights.",
            "project_name": "Materials Timeline Demo",
        },
    )
    project_id = bootstrap_response.json()["project_id"]

    ingest_response = client.post(
        "/research-packs",
        json={
            "project_id": project_id,
            "pack_title": "Material organization pass",
            "source_family": "workflow_handoff_methods",
            "source_ref": "notes-c",
            "raw_notes": "Raw material collected from references.",
            "synthesized_summary": "Organize the references into reusable next-step guidance.",
        },
    )
    assert ingest_response.status_code == 200

    timeline = get_project_timeline(project_id)
    assert any(item["event_type"] == "materials_organized" for item in timeline["events"])


def test_workspace_language_appears_on_task_and_session_pages() -> None:
    bootstrap_response = client.post(
        "/projects/bootstrap",
        json={
            "goal": "Coordinate a research and planning effort.",
            "initial_prompt": "Need a workspace that feels like coordinated work, not just engineering screens.",
            "project_name": "Workspace Language Demo",
        },
    )
    project_id = bootstrap_response.json()["project_id"]
    session_id = bootstrap_response.json()["session_id"]

    task_page = client.get(f"/projects/{project_id}/tasks")
    assert task_page.status_code == 200
    assert "Work Board" in task_page.text
    assert "What Matters Most Right Now" in task_page.text

    session_page = client.get(f"/projects/{project_id}/sessions/{session_id}")
    assert session_page.status_code == 200
    assert "Complete Work Step" in session_page.text
    assert "Materials Used" in session_page.text
    assert "Advanced controls" in session_page.text
