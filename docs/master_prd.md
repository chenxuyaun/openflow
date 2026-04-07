# OpenFlow Alpha Product Blueprint

## 1. Product Definition

OpenFlow is an AI collaboration workspace for complex work that continues
through fresh sessions. Progress is preserved through files, materials,
decisions, handoffs, and timelines instead of hidden runtime chat context.

## 2. Product Narrative

The core failure mode is not limited to coding: once an AI-assisted project
gets large enough, continuity breaks. Users lose reasoning, specialists restart
from partial summaries, and nobody can clearly explain why the next step was
chosen.

OpenFlow addresses that by combining:

- workspace entry from a natural-language goal
- structured role and work-step decomposition
- visible handoffs and review flow
- durable materials, research, and decisions
- recoverable state from files

## 3. Product Position

OpenFlow should be positioned as an AI collaboration workspace with a dual
interface model:

- simple layer for ordinary users:
  - workspace
  - materials
  - work steps
  - work board
  - next step
- advanced layer for governance-oriented users:
  - workflow graph
  - decision registry
  - confirm gates
  - review actions
  - handoff chain

## 4. Target Users

- Individuals coordinating long-running research, writing, planning, or build work
- Small teams using AI roles but needing continuity and governance
- Operators who want both simple progress views and deeper auditability

## 5. Primary Scenarios

### Scenario A: Coordinated Delivery

1. A user describes what they want to finish
2. OpenFlow infers a work type and collaboration structure
3. Work steps are created across planning, execution, and review
4. Handoffs advance the work without losing continuity

### Scenario B: Research And Synthesis

1. A user starts from scattered notes or source materials
2. Research packs are ingested and split into raw and synthesized layers
3. Insights are linked to decisions and next actions
4. The project remains understandable after interruptions

### Scenario C: Review And Replanning

1. A confirm gate blocks the next step
2. A reviewer approves, requests changes, or sends the flow back to replanning
3. Task and timeline state update with visible reasons

## 6. Core System

### Workspace Bootstrap

- Input: goal + context
- Output: project mode, user-facing roles, workflow graph, task tree, work priorities

### Work Step Engine

- Every role step is a fresh session
- Every step starts from declared materials
- Every step writes a handoff

### Governance Layer

- Review actions:
  - approve
  - changes_requested
  - replan_required
- Confirm gates block advancement until a review outcome exists

### Materials And Decisions

- Knowledge items store project and research memory
- Research packs preserve both raw sources and synthesized insights
- Decisions can be updated and shown with supporting materials

### Explanation Layer

- Dashboard explains why the project is in its current state
- Timeline explains why each event happened
- Task board explains governance effects on work status

## 7. UX Surfaces

- Landing / workspace entry
- Workspace overview
- Materials and insights
- Decision registry
- Advanced workflow
- Work board
- Work step detail

## 8. Alpha Scope

- Natural-language workspace entry
- Dynamic project type and user-facing role mapping
- Work step creation and completion
- Handoff and review loop
- Research pack ingest and batch ingest
- Decision registry with status updates
- Explainable project timeline

## 9. Alpha Non-Goals

- Realtime multiplayer editing
- Fully autonomous external execution
- Heavy vector or retrieval infrastructure as a first requirement
- Deep per-vertical customization for every possible domain

Beta follow-on work should be tracked in `docs/beta_backlog.md` instead of
remaining as ambiguous Alpha scope.

## 10. Acceptance Criteria

- A user can start a workspace from an ordinary goal statement
- The generated project exposes both simple and advanced layers
- A work step can be completed, reviewed, and advanced
- Materials, decisions, and timeline remain linked
- The product can be explained as a general collaboration workspace, not only a developer system
- Documentation and product behavior stay aligned
