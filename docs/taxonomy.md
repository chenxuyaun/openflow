# OpenFlow Taxonomy

## Product Name

- Product name: OpenFlow
- Product category: Project operating system for role-driven AI work

## Core Terms

### Project Layer

- Project: the durable container for workflows, decisions, files, and sessions
- Workflow graph: the visible map of role stages and transitions
- Task tree: the decomposed work structure owned by roles
- Review loop: the mechanism for inspection, conflict detection, and replanning

### Session Layer

- Session: a single isolated role run
- Isolated session: a session that does not inherit hidden runtime chat context
- Input files: the declared files a role session reads before acting

### Handoff Layer

- Handoff: the structured output that drives the next role
- Next role: the recommended role or stage that should take over after a session
- Confirm gate: a required stop before continuing through high-risk transitions

### Knowledge Layer

- Knowledge item: a structured research or project fact with source metadata
- Decision record: a tracked decision with rationale and supporting sources
- Research corpus: the combined internal and external source base for the project

### Page Layer

- Landing: the first-use explanatory page
- Project dashboard: the main project status and next-step view
- Knowledge center: the view for sources, decisions, and unresolved questions
- Workflow graph: the visual role and transition map
- Session detail: the page for session inputs, outputs, and handoff
- Task board: the view for ownership, dependencies, and execution status

## Naming Rules

- Use the exact term `session`, not chat or thread, when describing role work
- Use `handoff`, not summary, when the artifact decides the next role
- Use `knowledge center`, not docs page, for the knowledge-facing surface
- Use `workflow graph`, not planner graph, in product and page language
- Use `confirm gate`, not approval modal, in the product model

## Binding Rule

These terms are implementation-facing standards. Later docs, routes, page names,
and UI labels should follow this taxonomy unless a new decision record changes
the vocabulary explicitly.
