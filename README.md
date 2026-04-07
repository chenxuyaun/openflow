# OpenFlow

OpenFlow is an AI collaboration workspace for long-running work that should not
break when roles, sessions, or time windows change. Each role starts in a fresh
session, while progress continues through files, handoffs, knowledge items,
decisions, and timeline records instead of hidden chat context.

## Alpha Scope

- FastAPI app with JSON APIs and server-rendered Jinja pages
- Natural-language workspace entry from `goal + initial_prompt`
- Dynamic role catalog, task tree, workflow graph, and user-facing role mapping
- File-backed project memory with SQLite indexing
- Session completion, handoff advancement, and confirm-gated review actions
- Knowledge center with research pack ingest, batch ingest, and decision linkage
- Decision registry with status updates
- Project timeline with `because` explanations
- Dual-layer UX:
  - default layer uses ordinary work language
  - advanced layer exposes workflow, handoff, governance, and decision surfaces

## Product Model

- Every role is a new session.
- Durable memory lives in files, not runtime chat context.
- Handoffs move work between fresh sessions.
- Knowledge and decisions remain visible and reusable.
- Users can stay in simple workspace language or open advanced governance views.

## Main Surfaces

- Landing / workspace entry
- Workspace overview
- Materials and insights
- Decision registry
- Advanced workflow
- Work board
- Work step detail

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
  decisions.html
  workflow.html
  tasks.html
  session.html
docs/
  product_hook.md
  taxonomy.md
  landing_blueprint.md
  demo_flow.md
  master_prd.md
  beta_backlog.md
  research_master_outline.md
  alpha_release_checklist.md
  knowledge_index.json
  decision_registry.json
  workflow_blueprint.json
  blueprint_alignment.json
tests/
  test_app.py
```

## Key APIs

- `POST /projects/bootstrap`
- `POST /sessions`
- `POST /sessions/{session_id}/complete`
- `POST /handoffs/{handoff_id}/advance`
- `POST /handoffs/{handoff_id}/review`
- `POST /research-packs`
- `POST /research-packs/batch`
- `POST /projects/{project_id}/decisions/{decision_id}`

## Run

```powershell
python -m uvicorn openflow.app:app --app-dir src --reload
```

## Verify

```powershell
python -m py_compile src/openflow/app.py src/openflow/models.py src/openflow/service.py src/openflow/repository.py
python -m pytest -q
```

## Alpha Focus

- Stable workspace entry and core collaboration loop
- Clear next-step guidance and recoverable project memory
- Explainable governance through reviews, decisions, and timelines
- Usable both as a simple work workspace and as an advanced coordination system
- Default workspace view centered on current goal, available materials, current progress, and suggested next step

## Beta Boundary

Alpha intentionally stops at the core workspace loop. Deferred follow-on work is
tracked in `docs/beta_backlog.md`.

## Release Notes

See `docs/alpha_release_notes.md` for the Alpha package summary.
