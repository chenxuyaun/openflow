# OpenFlow V1 Product Blueprint

## 1. Product Definition

OpenFlow is a role-driven workflow system where each role operates in a fresh
session. Progress is preserved through files, indexes, decisions, and handoff
records rather than through persistent runtime chat context.

## 2. Product Narrative

OpenFlow exists to solve a specific failure mode in AI-driven projects:
important work disappears into chat context, role changes lose precision, and
teams cannot audit why the system chose the next action. The product answer is
not a larger context window. The answer is to make project memory explicit and
make role transitions structured.

The user-facing attraction is that OpenFlow turns a vague goal into visible
project structure: knowledge items, role graph, task tree, and next-step
handoffs. The team-facing attraction is that every session can be reviewed and
resumed from files.

## 3. Core Value

- Eliminate hidden context drift by treating files as the source of truth
- Turn every answer into a structured handoff for the next role
- Make role changes auditable through workflow graphs and session inputs
- Keep project knowledge reusable for development, operations, and creation

## 4. Target Users

- Solo builders managing long-running projects with AI
- Small teams that need auditable agent collaboration
- Operators who need planning, execution, review, and reprioritization loops

## 5. Primary Scenarios

### Scenario A: Product Build

1. The user describes a product idea and constraints
2. A bootstrap role creates workflow, roles, and task tree
3. Specialist roles work in fresh sessions using file inputs only
4. Every session emits a handoff for the next role
5. The project can be resumed without relying on hidden context

### Scenario B: Workflow Repair

1. A review role reads project files and detects blocked progress
2. It updates decision records and suggests role changes
3. A new specialist session is created to address the issue

## 6. Core System

### Bootstrap

- Read the first request and existing project files
- Produce `workflow_graph`, `role_catalog`, and `task_tree`

### Knowledge Base

- Store transcripts, decisions, docs, and references as indexed items
- Let each session declare which files it consumed
- Normalize internal and external materials into a shared research corpus

### Session Engine

- Create a new isolated session per role
- Never rely on hidden prior chat state

### Handoff Engine

- Require structured output for every completed session
- Decide whether to auto-advance or require confirmation

### Review Loop

- Allow replanning, conflict detection, and recovery from failed paths

## 7. Knowledge And Research System

- Research sources include chats, repo state, git history, internal docs,
  competitor references, and workflow methodology references
- Every source becomes a `KnowledgeItem` with themes, reliability, relevance,
  and open questions
- Product decisions cite knowledge items and remain visible in a decision
  registry until resolved
- Sessions consume files and indexes, not hidden conversation memory

## 8. UX Surfaces

- Landing / first impression
- Project dashboard
- Knowledge center
- Workflow graph
- Session detail
- Task board

## 9. Workflow And Page Flow

1. Landing explains the problem, mechanism, and first-use promise
2. User starts a project bootstrap request
3. Bootstrap role creates workflow, role catalog, task tree, and research map
4. Project dashboard shows current state and next role
5. Knowledge center exposes source items, decisions, and unresolved questions
6. Session detail shows declared inputs, outputs, and handoff
7. Workflow graph shows the current stage, auto-advance paths, and confirm gates
8. Task board shows ownership, dependencies, and blocked work

## 10. Demo Flow

1. Start from the landing promise and failure mode
2. Show bootstrap turning a goal into visible workflow artifacts
3. Show project dashboard and workflow graph as the first transformation
4. Show session detail as proof of isolated, file-driven execution
5. Show knowledge center as proof of auditability and continuity
6. Show confirm gate and review loop as governance
7. End on the V1 promise and next-step call to action

## 11. API Skeleton

- `POST /projects/bootstrap`
- `GET /project`
- `GET /knowledge`
- `GET /workflow`
- `POST /sessions`
- `POST /sessions/{id}/complete`
- `POST /handoffs/{id}/advance`

## 12. Core Types

- `KnowledgeItem`
- `DecisionRecord`
- `WorkflowGraph`
- `RoleInstanceSpec`
- `TaskNode`
- `SessionRecord`
- `HandoffRecord`
- `ProjectState`

## 13. V1 Non-Goals

- Fully autonomous external tool execution
- Realtime multiplayer editing
- Heavy vector infrastructure as a requirement for first release

## 14. Acceptance Criteria

- A new project can be bootstrapped into roles and tasks
- Each role session is isolated and file-driven
- Knowledge and progress are reconstructable from disk artifacts
- Workflow transitions are inspectable and reviewable
- Product narrative, research corpus, workflow graph, and API contract remain aligned
- Landing narrative can be derived directly from the product hook and workflow blueprint
- Demo flow can be derived directly from the same blueprint package without inventing new concepts
