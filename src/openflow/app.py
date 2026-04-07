from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi import Form
from fastapi import Query
from fastapi import Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from openflow.service import (
    advance_project_handoff,
    build_blueprint_package,
    build_default_project_state,
    build_knowledge_summary,
    build_workflow_summary,
    complete_project_session,
    create_project,
    create_project_session,
    get_project_decisions,
    get_project_knowledge,
    get_project_session_detail,
    get_project_state,
    get_project_tasks,
    get_project_timeline,
    get_project_workflow,
    ingest_project_research_pack_batch,
    ingest_project_research_pack,
    review_project_handoff,
    update_project_decision,
)
from openflow.models import (
    BootstrapRequest,
    DecisionUpdateRequest,
    HandoffReviewRequest,
    ResearchPackBatchIngestRequest,
    ResearchPackIngestRequest,
    SessionCompleteRequest,
    SessionCreateRequest,
)

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
STATIC_APP_DIR = STATIC_DIR / "app"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI(
    title="OpenFlow",
    version="0.1.0",
    description="AI collaboration workspace with file-based session memory.",
)
app.mount("/app-static", StaticFiles(directory=str(STATIC_APP_DIR)), name="app-static")


def _proof_points() -> list[str]:
    return [
        "Every role starts fresh",
        "Project memory stays in files",
        "Progress remains visible",
        "The next step stays clear",
    ]


def _mode_presets() -> list[dict[str, object]]:
    return [
        {
            "id": "research",
            "label": "Research",
            "headline": "Sort broad materials into reusable knowledge.",
            "summary": "Best for source collection, synthesis, briefs, strategy scans, and evidence-backed decisions.",
            "goal": "Turn scattered research into a clear briefing and next-step plan.",
            "initial_prompt": "I have interview notes, reference links, earlier summaries, and open questions. Organize the materials, preserve what matters, and show the next evidence-backed step.",
            "starter_role": "Research Curator",
        },
        {
            "id": "experience",
            "label": "Experience",
            "headline": "Shape a clearer journey before adding more process.",
            "summary": "Best for product planning, content flows, service design, page journeys, and user experience cleanup.",
            "goal": "Turn a rough product idea into a clearer user journey and staged execution plan.",
            "initial_prompt": "The current workflow feels complex and low-attraction. Reframe the experience, reduce friction, and organize the next steps into a cleaner workspace flow.",
            "starter_role": "Experience Designer",
        },
        {
            "id": "delivery",
            "label": "Delivery",
            "headline": "Move from draft material into executable work.",
            "summary": "Best for implementation, process rollout, operations work, and structured multi-role execution.",
            "goal": "Turn scattered notes into a deliverable with a visible next-step workflow.",
            "initial_prompt": "I have draft material, constraints, and partial decisions. Convert this into clear work steps, keep the handoffs visible, and drive execution without losing progress.",
            "starter_role": "Implementation Lead",
        },
        {
            "id": "multimodal",
            "label": "Multimodal",
            "headline": "Connect image, text, planning, and execution in one loop.",
            "summary": "Best for image-plus-text workflows, multimodal prototypes, and AI systems that need planning and runnable steps.",
            "goal": "Turn multimodal input into a file-driven plan and executable workflow.",
            "initial_prompt": "I want an AI workflow that can read image and text inputs, produce a plan, execute the next step, and preserve continuity through files instead of hidden context.",
            "starter_role": "Implementation Lead",
        },
    ]


def _first_step_defaults(project_id: str, summary: Optional[dict[str, object]] = None) -> dict[str, str]:
    state = dict(summary.get("state", {})) if summary else {}
    project_mode = str(state.get("project_mode", "delivery"))
    role_catalog = list(state.get("role_catalog", [])) if state else []
    input_files = [f"projects/{project_id}/workflow_graph.json"]
    defaults = {
        "role_name": "Implementation Lead",
        "objective": "Start the first practical step for this workspace and move the project toward a visible next result.",
        "input_files": "\n".join(input_files),
    }
    if project_mode == "research":
        defaults = {
            "role_name": "Research Curator",
            "objective": "Collect, sort, and synthesize the current materials so the next step can continue from reusable project knowledge.",
            "input_files": "\n".join([f"projects/{project_id}/project.json", f"projects/{project_id}/knowledge/knowledge_items.json"]),
        }
    elif project_mode == "experience":
        defaults = {
            "role_name": "Experience Designer",
            "objective": "Clarify the user journey, reduce friction, and turn the current idea into a more understandable staged flow.",
            "input_files": "\n".join([f"projects/{project_id}/project.json", f"projects/{project_id}/workflow_graph.json"]),
        }
    elif project_mode == "multimodal":
        defaults = {
            "role_name": "Implementation Lead",
            "objective": "Connect multimodal input, planning, and execution into one visible file-driven loop.",
            "input_files": "\n".join([f"projects/{project_id}/project.json", f"projects/{project_id}/workflow_graph.json"]),
        }
    available_roles = {str(item.get("role_name", "")) for item in role_catalog}
    if defaults["role_name"] not in available_roles and role_catalog:
        fallback_role = str(role_catalog[0].get("role_name", defaults["role_name"]))
        defaults["role_name"] = fallback_role
    return defaults


def _session_complete_defaults(project_id: str, session_id: str) -> dict[str, object]:
    return {
        "session_summary": "Summarize the work step outcome and what changed.",
        "next_role_recommendation": "Review Operator",
        "next_role_reason": "A review pass is needed before advancing.",
        "required_input_files": [f"projects/{project_id}/sessions/{session_id}/handoff.json"],
        "success_criteria": ["Review the evidence", "Decide whether to advance"],
        "risks": ["The review may trigger replanning."],
        "transcript_note": "Record the most important execution note from this session.",
        "task_status_changes": ["implementation-slice=completed"],
        "review_outcome": "pass",
        "acceptance_status": "accepted",
        "followup_actions": ["Start the recommended next role."],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def landing_page(request: Request):
    blueprint = build_blueprint_package()
    return templates.TemplateResponse(
        request,
        "landing.html",
        {
            "title": "OpenFlow",
            "blueprint": blueprint,
            "proof_points": _proof_points(),
        },
    )


@app.post("/")
def bootstrap_from_landing(
    goal: str = Form(...),
    initial_prompt: str = Form(...),
    project_name: str = Form("OpenFlow Project"),
    preferred_project_mode: str = Form("delivery"),
):
    payload = create_project(
        BootstrapRequest(
            goal=goal,
            initial_prompt=initial_prompt,
            project_name=project_name,
            preferred_project_mode=preferred_project_mode,
        )
    )
    return RedirectResponse(url=f"/projects/{payload['project_id']}/welcome", status_code=303)


@app.get("/project")
def project(project_id: Optional[str] = Query(default=None)) -> dict[str, object]:
    if project_id:
        return get_project_state(project_id)
    state = build_default_project_state()
    return state.model_dump(mode="json")


@app.get("/knowledge")
def knowledge(project_id: Optional[str] = Query(default=None)) -> dict[str, object]:
    if project_id:
        return get_project_knowledge(project_id)
    return build_knowledge_summary()


@app.get("/workflow")
def workflow(project_id: Optional[str] = Query(default=None)) -> dict[str, object]:
    if project_id:
        return get_project_workflow(project_id)
    return build_workflow_summary()


@app.get("/blueprint")
def blueprint() -> dict[str, object]:
    return build_blueprint_package()


@app.get("/api/app/landing")
def app_landing() -> dict[str, object]:
    blueprint = build_blueprint_package()
    return {
        "title": "OpenFlow",
        "proof_points": _proof_points(),
        "blueprint": blueprint,
        "mode_presets": _mode_presets(),
        "examples": [
            "Organize research into a briefing",
            "Turn scattered notes into a deliverable",
            "Create a reusable plan from draft material",
        ],
        "defaults": {
            "project_name": "OpenFlow Workspace",
            "preferred_project_mode": "experience",
            "goal": "Turn scattered research into a clear briefing and next-step plan.",
            "initial_prompt": "I have interview notes, reference links, an unfinished outline, and a review deadline next week. Help organize the materials, show the current progress, and guide the next step.",
        },
    }


@app.get("/api/app/projects/{project_id}/welcome")
def app_welcome(project_id: str) -> dict[str, object]:
    summary = get_project_state(project_id)
    return {
        "project_id": project_id,
        "summary": summary,
        "first_step_defaults": _first_step_defaults(project_id, summary),
    }


@app.get("/api/app/projects/{project_id}/workspace")
def app_workspace(project_id: str) -> dict[str, object]:
    return {
        "project_id": project_id,
        "summary": get_project_state(project_id),
        "timeline": get_project_timeline(project_id)["events"],
    }


@app.get("/api/app/projects/{project_id}/session/{session_id}")
def app_session(project_id: str, session_id: str) -> dict[str, object]:
    return {
        "project_id": project_id,
        "session_id": session_id,
        "payload": get_project_session_detail(project_id, session_id),
        "complete_defaults": _session_complete_defaults(project_id, session_id),
    }


@app.get("/api/app/projects/{project_id}/knowledge")
def app_knowledge(
    project_id: str,
    q: Optional[str] = Query(default=None),
    source_family: Optional[str] = Query(default=None),
    entry_kind: Optional[str] = Query(default=None),
    adoption_status: Optional[str] = Query(default=None),
    linked_only: bool = Query(default=False),
) -> dict[str, object]:
    return {
        "project_id": project_id,
        "payload": get_project_knowledge(
            project_id,
            q=q,
            source_family=source_family,
            entry_kind=entry_kind,
            adoption_status=adoption_status,
            linked_only=linked_only,
        ),
    }


@app.get("/api/app/projects/{project_id}/tasks")
def app_tasks(project_id: str) -> dict[str, object]:
    return {
        "project_id": project_id,
        "payload": get_project_tasks(project_id),
    }


@app.get("/api/app/projects/{project_id}/workflow")
def app_workflow(project_id: str) -> dict[str, object]:
    return {
        "project_id": project_id,
        "payload": get_project_workflow(project_id),
    }


@app.get("/api/app/projects/{project_id}/decisions")
def app_decisions(project_id: str) -> dict[str, object]:
    return {
        "project_id": project_id,
        "payload": get_project_decisions(project_id),
    }


@app.post("/projects/bootstrap")
def bootstrap(request: BootstrapRequest) -> dict[str, object]:
    return create_project(request)


@app.post("/sessions")
def create_session(request: SessionCreateRequest) -> dict[str, object]:
    return create_project_session(request)


@app.post("/sessions/{session_id}/complete")
def complete_session(session_id: str, request: SessionCompleteRequest) -> dict[str, object]:
    return complete_project_session(session_id, request)


@app.post("/handoffs/{handoff_id}/advance")
def advance_handoff(handoff_id: str) -> dict[str, object]:
    return advance_project_handoff(handoff_id)


@app.post("/handoffs/{handoff_id}/review")
def review_handoff(handoff_id: str, request: HandoffReviewRequest) -> dict[str, object]:
    return review_project_handoff(handoff_id, request)


@app.post("/research-packs")
def ingest_research_pack(request: ResearchPackIngestRequest) -> dict[str, object]:
    return ingest_project_research_pack(request)


@app.post("/research-packs/batch")
def ingest_research_pack_batch(request: ResearchPackBatchIngestRequest) -> dict[str, object]:
    return ingest_project_research_pack_batch(request)


@app.post("/projects/{project_id}/decisions/{decision_id}")
def update_decision(project_id: str, decision_id: str, request: DecisionUpdateRequest) -> dict[str, object]:
    return update_project_decision(project_id, decision_id, request)


@app.post("/projects/{project_id}/handoffs/{handoff_id}/advance")
def advance_handoff_from_page(project_id: str, handoff_id: str):
    result = advance_project_handoff(handoff_id)
    if result["status"] == "advanced":
        session_id = result["session"]["session_id"]
        return RedirectResponse(
            url=f"/projects/{project_id}/sessions/{session_id}?handoff_status=advanced",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/projects/{project_id}?handoff_status=waiting_confirmation&handoff_id={handoff_id}",
        status_code=303,
    )


@app.post("/projects/{project_id}/handoffs/{handoff_id}/review")
def review_handoff_from_page(
    project_id: str,
    handoff_id: str,
    action: str = Form(...),
    note: str = Form(""),
    return_to: str = Form("project"),
    session_id: str = Form(""),
):
    result = review_project_handoff(
        handoff_id,
        HandoffReviewRequest(action=action, note=note or None),
    )
    review_status = result["acceptance_status"]
    if return_to == "session" and session_id:
        url = f"/projects/{project_id}/sessions/{session_id}?review_status={review_status}"
    else:
        url = f"/projects/{project_id}?review_status={review_status}"
    return RedirectResponse(
        url=url,
        status_code=303,
    )


@app.get("/projects/{project_id}")
def project_page(project_id: str, request: Request):
    summary = get_project_state(project_id)
    timeline = get_project_timeline(project_id)
    return templates.TemplateResponse(
        request,
        "project.html",
        {
            "title": f"Project {project_id}",
            "project_id": project_id,
            "summary": summary,
            "timeline": timeline["events"],
            "handoff_status": request.query_params.get("handoff_status"),
            "review_status": request.query_params.get("review_status"),
        },
    )


@app.get("/projects/{project_id}/welcome")
def welcome_page(project_id: str, request: Request):
    summary = get_project_state(project_id)
    return templates.TemplateResponse(
        request,
        "welcome.html",
        {
            "title": f"Welcome {project_id}",
            "project_id": project_id,
            "summary": summary,
            "first_step_defaults": _first_step_defaults(project_id),
        },
    )


@app.post("/projects/{project_id}/sessions")
def create_session_from_page(
    project_id: str,
    role_name: str = Form(...),
    objective: str = Form(...),
    input_files: str = Form(""),
):
    payload = create_project_session(
        SessionCreateRequest(
            project_id=project_id,
            role_name=role_name,
            objective=objective,
            input_files=[item.strip() for item in input_files.splitlines() if item.strip()],
        )
    )
    return RedirectResponse(
        url=f"/projects/{project_id}/sessions/{payload['session_id']}",
        status_code=303,
    )


@app.get("/projects/{project_id}/knowledge")
def knowledge_page(
    project_id: str,
    request: Request,
    q: Optional[str] = Query(default=None),
    source_family: Optional[str] = Query(default=None),
    entry_kind: Optional[str] = Query(default=None),
    adoption_status: Optional[str] = Query(default=None),
    linked_only: bool = Query(default=False),
):
    payload = get_project_knowledge(
        project_id,
        q=q,
        source_family=source_family,
        entry_kind=entry_kind,
        adoption_status=adoption_status,
        linked_only=linked_only,
    )
    return templates.TemplateResponse(
        request,
        "knowledge.html",
        {
            "title": f"Knowledge {project_id}",
            "project_id": project_id,
            "payload": payload,
        },
    )


@app.get("/projects/{project_id}/decisions")
def decision_page(project_id: str, request: Request):
    payload = get_project_decisions(project_id)
    return templates.TemplateResponse(
        request,
        "decisions.html",
        {
            "title": f"Decisions {project_id}",
            "project_id": project_id,
            "payload": payload,
        },
    )


@app.post("/projects/{project_id}/decisions/{decision_id}/update")
def update_decision_from_page(
    project_id: str,
    decision_id: str,
    status: str = Form(...),
):
    update_project_decision(project_id, decision_id, DecisionUpdateRequest(status=status))
    return RedirectResponse(
        url=f"/projects/{project_id}/decisions",
        status_code=303,
    )


@app.post("/projects/{project_id}/research-packs")
def ingest_research_pack_from_page(
    project_id: str,
    pack_title: str = Form(...),
    source_family: str = Form(...),
    source_ref: str = Form(...),
    raw_notes: str = Form(...),
    synthesized_summary: str = Form(...),
    themes: str = Form(""),
    decision_ids: str = Form(""),
    adoption_status: str = Form("proposed"),
    reliability: str = Form("medium"),
    relevance: str = Form("high"),
):
    ingest_project_research_pack(
        ResearchPackIngestRequest(
            project_id=project_id,
            pack_title=pack_title,
            source_family=source_family,
            source_ref=source_ref,
            raw_notes=raw_notes,
            synthesized_summary=synthesized_summary,
            themes=[item.strip() for item in themes.splitlines() if item.strip()],
            decision_ids=[item.strip() for item in decision_ids.splitlines() if item.strip()],
            adoption_status=adoption_status,
            reliability=reliability,
            relevance=relevance,
        )
    )
    return RedirectResponse(
        url=f"/projects/{project_id}/knowledge",
        status_code=303,
    )


@app.post("/projects/{project_id}/research-packs/batch")
def ingest_research_pack_batch_from_page(
    project_id: str,
    batch_payload: str = Form(...),
):
    packs = []
    current: dict[str, object] = {}
    for raw_line in batch_payload.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                packs.append(
                    ResearchPackIngestRequest(
                        project_id=project_id,
                        pack_title=str(current.get("pack_title", "Batch pack")),
                        source_family=str(current.get("source_family", "workflow_handoff_methods")),
                        source_ref=str(current.get("source_ref", "batch-input")),
                        raw_notes=str(current.get("raw_notes", "")),
                        synthesized_summary=str(current.get("synthesized_summary", "")),
                        themes=[item.strip() for item in str(current.get("themes", "")).split(",") if item.strip()],
                        decision_ids=[item.strip() for item in str(current.get("decision_ids", "")).split(",") if item.strip()],
                        adoption_status=str(current.get("adoption_status", "proposed")),
                        reliability=str(current.get("reliability", "medium")),
                        relevance=str(current.get("relevance", "high")),
                    )
                )
                current = {}
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current[key.strip()] = value.strip()
    if current:
        packs.append(
            ResearchPackIngestRequest(
                project_id=project_id,
                pack_title=str(current.get("pack_title", "Batch pack")),
                source_family=str(current.get("source_family", "workflow_handoff_methods")),
                source_ref=str(current.get("source_ref", "batch-input")),
                raw_notes=str(current.get("raw_notes", "")),
                synthesized_summary=str(current.get("synthesized_summary", "")),
                themes=[item.strip() for item in str(current.get("themes", "")).split(",") if item.strip()],
                decision_ids=[item.strip() for item in str(current.get("decision_ids", "")).split(",") if item.strip()],
                adoption_status=str(current.get("adoption_status", "proposed")),
                reliability=str(current.get("reliability", "medium")),
                relevance=str(current.get("relevance", "high")),
            )
        )
    ingest_project_research_pack_batch(ResearchPackBatchIngestRequest(project_id=project_id, packs=packs))
    return RedirectResponse(
        url=f"/projects/{project_id}/knowledge",
        status_code=303,
    )


@app.get("/projects/{project_id}/workflow")
def workflow_page(project_id: str, request: Request):
    payload = get_project_workflow(project_id)
    return templates.TemplateResponse(
        request,
        "workflow.html",
        {
            "title": f"Workflow {project_id}",
            "project_id": project_id,
            "payload": payload,
        },
    )


@app.get("/projects/{project_id}/tasks")
def task_board_page(project_id: str, request: Request):
    payload = get_project_tasks(project_id)
    return templates.TemplateResponse(
        request,
        "tasks.html",
        {
            "title": f"Tasks {project_id}",
            "project_id": project_id,
            "payload": payload,
        },
    )


@app.get("/projects/{project_id}/sessions/{session_id}")
def session_page(project_id: str, session_id: str, request: Request):
    payload = get_project_session_detail(project_id, session_id)
    return templates.TemplateResponse(
        request,
        "session.html",
        {
            "title": f"Session {session_id}",
            "project_id": project_id,
            "payload": payload,
            "handoff_status": request.query_params.get("handoff_status"),
            "completed": request.query_params.get("completed"),
            "review_status": request.query_params.get("review_status"),
        },
    )


@app.post("/projects/{project_id}/sessions/{session_id}/complete")
def complete_session_from_page(
    project_id: str,
    session_id: str,
    session_summary: str = Form(...),
    next_role_recommendation: str = Form(...),
    next_role_reason: str = Form(...),
    required_input_files: str = Form(""),
    success_criteria: str = Form(""),
    risks: str = Form(""),
    task_status_changes: str = Form(""),
    review_outcome: str = Form(""),
    acceptance_status: str = Form(""),
    followup_actions: str = Form(""),
    transcript_note: str = Form(""),
):
    complete_project_session(
        session_id,
        SessionCompleteRequest(
            session_summary=session_summary,
            next_role_recommendation=next_role_recommendation,
            next_role_reason=next_role_reason,
            required_input_files=[item.strip() for item in required_input_files.splitlines() if item.strip()],
            success_criteria=[item.strip() for item in success_criteria.splitlines() if item.strip()],
            risks=[item.strip() for item in risks.splitlines() if item.strip()],
            task_status_changes=[item.strip() for item in task_status_changes.splitlines() if item.strip()],
            review_outcome=review_outcome or None,
            acceptance_status=acceptance_status or None,
            followup_actions=[item.strip() for item in followup_actions.splitlines() if item.strip()],
            transcript_note=transcript_note or None,
        ),
    )
    return RedirectResponse(
        url=f"/projects/{project_id}/sessions/{session_id}?completed=1",
        status_code=303,
    )


@app.get("/app")
def app_shell() -> FileResponse:
    return FileResponse(STATIC_APP_DIR / "index.html")


@app.get("/app/{path:path}")
def app_shell_paths(path: str) -> FileResponse:
    return FileResponse(STATIC_APP_DIR / "index.html")
