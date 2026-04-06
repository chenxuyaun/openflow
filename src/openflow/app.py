from __future__ import annotations

from fastapi import FastAPI

from openflow.service import (
    build_default_project_state,
    build_knowledge_summary,
    build_workflow_summary,
)

app = FastAPI(
    title="OpenFlow",
    version="0.1.0",
    description="Role-driven workflow engine with file-based session memory.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/project")
def project() -> dict[str, object]:
    state = build_default_project_state()
    return state.model_dump(mode="json")


@app.get("/knowledge")
def knowledge() -> dict[str, object]:
    return build_knowledge_summary()


@app.get("/workflow")
def workflow() -> dict[str, object]:
    return build_workflow_summary()
