# OpenFlow

OpenFlow is a file-driven workflow runtime for role-based AI delivery. Every
role runs in a fresh session. Previous chats are not implicit context; they are
turned into files, handoffs, knowledge items, and indexed project records that
the next role can inspect explicitly.

## Current Scope

- FastAPI app with JSON APIs and server-rendered Jinja pages
- Project bootstrap from `goal + initial_prompt`
- Dynamic role catalog, task tree, and workflow graph generation
- File-backed session storage with SQLite indexing
- Session completion and handoff advancement
- Knowledge center fed by docs, project artifacts, transcript summaries, and git
- Project timeline that surfaces bootstrap, sessions, handoffs, knowledge ingest,
  and git evolution

## Product Model

- Every role is a new session.
- Durable memory lives in files, not runtime chat context.
- Handoffs carry the minimum structured package needed for the next role.
- Knowledge items and timeline events make project evolution inspectable.

## Project Layout

```text
src/openflow/
  app.py
  models.py
  repository.py
  service.py
templates/
  base.html
  landing.html
  project.html
  knowledge.html
  workflow.html
  session.html
docs/
  product_hook.md
  taxonomy.md
  landing_blueprint.md
  demo_flow.md
  master_prd.md
  research_master_outline.md
  knowledge_index.json
  decision_registry.json
  workflow_blueprint.json
  blueprint_alignment.json
tests/
  test_app.py
```

## Run

```powershell
python -m uvicorn openflow.app:app --app-dir src --reload
```

## Verify

```powershell
python -m pytest -q
python -m py_compile src/openflow/app.py src/openflow/models.py src/openflow/service.py src/openflow/repository.py
```

## Next Slice

- Enrich request-driven planning with deeper dependency and risk modeling
- Expand transcript and handoff synthesis into more explicit decision/task state
- Add richer approval workflows for confirm-gated stages
