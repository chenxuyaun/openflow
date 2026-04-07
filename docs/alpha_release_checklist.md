# OpenFlow Alpha Release Checklist

## Product

- Landing presents OpenFlow as an AI collaboration workspace
- Workspace entry uses natural-language goal input
- Project pages use dual-layer language:
  - simple work language by default
  - advanced governance language when needed

## Core Flow

- Bootstrap creates a project from `goal + initial_prompt`
- A work step can be created and completed
- Handoff advance works
- Confirm gate review works:
  - approve
  - changes_requested
  - replan_required

## Knowledge And Decisions

- Knowledge center shows project knowledge items
- Research pack ingest works
- Batch research pack ingest works
- Decision registry displays supporting knowledge
- Decision status update works

## Explainability

- Dashboard shows `Why The Project Is Here Now`
- Timeline events include `because`
- Work board shows governance-driven status explanations
- Work step detail explains why the step exists

## Verification

- `python -m py_compile src/openflow/app.py src/openflow/models.py src/openflow/service.py src/openflow/repository.py`
- `python -m pytest -q`

## Release Notes Readiness

- README reflects current product behavior
- Product hook matches landing direction
- PRD matches current Alpha scope
- Beta-only expansion items are moved to `docs/beta_backlog.md`
