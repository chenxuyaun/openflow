# OpenFlow

OpenFlow is a web-first workflow engine for role-based AI sessions that do not
share runtime context. Each new session reads project files, decisions, and
handoff records from disk instead of inheriting chat history in memory.

## Milestone 1

This repository currently implements the first milestone only:

- Python project scaffold
- FastAPI application entrypoint
- Core domain models for workflow bootstrap and session handoff
- Minimal HTTP API for health, project, knowledge, and workflow inspection
- Docs-backed knowledge index, decisions, and blueprint documents
- Product hook and expanded PRD/research package
- Pytest coverage for the initial contract

## Project Layout

```text
src/openflow/
  app.py
  models.py
  service.py
docs/
  product_hook.md
  master_prd.md
  research_master_outline.md
  knowledge_index.json
  decision_registry.json
  workflow_blueprint.json
tests/
  test_app.py
```

## Run

```powershell
python -m uvicorn openflow.app:app --app-dir src --reload
```

## Verify

```powershell
pytest -q
```

## Next Milestones

- Persist project/session state to files and SQLite
- Generate bootstrap workflow graphs from an initial request
- Write structured handoff records for each new role session
