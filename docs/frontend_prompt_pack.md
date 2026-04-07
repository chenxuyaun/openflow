# OpenFlow Frontend Prompt Pack

This file contains prompt packs for implementing new frontend functionality in a
separate frontend-focused chat. These prompts assume the backend now returns:

- `recommended_work_package`
- `goal_model`
- `cognitive_state`
- `plan_layers`
- `task_graph_v2`
- `current_execution_capsule_preview`
- `execution_capsule`
- `memory_pack_preview`
- `observability_snapshot`
- `improvement_snapshot`

## Prompt Pack A: Recommended Work Package Card

Use this prompt in the frontend chat:

```text
Implement a new "Recommended Work Package" module for OpenFlow using the existing frontend design system and project-specific frontend rules from this chat.

Context:
- Do not redesign the whole page.
- Integrate the module into the existing workspace and welcome views.
- The backend now returns `recommended_work_package` alongside the existing `recommendation` and `next_step`.

Consume these fields:
- recommended_role
- recommended_action
- recommended_reason
- recommended_files
- expected_output
- success_criteria
- risks
- blocking_items
- confidence
- secondary_note
- ready_for_auto_advance
- auto_advance_blockers
- human_action_required
- materials_snapshot

UI goals:
- Make the next recommended work package feel concrete and actionable.
- Show what role should act next, what it should read, what it should produce, and what may block it.
- Make the card readable for non-technical users first.
- Keep advanced detail visible but secondary.

Interaction requirements:
- Support collapsed and expanded states.
- Default to showing role, reason, expected output, and top 2 files.
- Expanded state must show full file list, success criteria, risks, blockers, and confidence.
- If `ready_for_auto_advance` is true, show a strong positive readiness state.
- If false, show blockers clearly and explain why human action is still required.

State branches:
- ready_for_auto_advance = true
- review_needed / blocked / replan style states
- no blockers but still manual review required
- large file list
- empty risks
- empty blocking_items

Copy direction:
- Plain work language, not system-internal jargon.
- Explain outcomes, not raw backend terms.
- Avoid "agent", "orchestration", or "governance" as primary labels unless already required by the surrounding screen.

Do not:
- Change backend field names.
- Collapse all detail behind tooltips only.
- Present the module like a developer debug panel.

Acceptance criteria:
- A user can understand the next role, next materials, expected output, and whether this step is actually ready.
- The component works in both workspace and welcome contexts.
- The component matches the frontend rules already established in this chat.
```

## Prompt Pack B: Auto-Advance Readiness Panel

Use this prompt in the frontend chat:

```text
Implement an "Auto-Advance Readiness" panel for the OpenFlow session detail page using the frontend conventions already defined in this chat.

Context:
- The backend returns `recommended_work_package`.
- This panel is informational only in this phase. Do not trigger automatic execution.

Consume these fields:
- ready_for_auto_advance
- auto_advance_blockers
- human_action_required
- next_step_state
- recommended_action
- suggested_session_objective
- success_criteria
- risks

UI goals:
- Tell the user whether the project is actually ready for automatic continuation.
- Separate "recommended next" from "safe to auto-advance".
- Make blockers explicit and scannable.

Interaction requirements:
- Show a binary readiness state at the top.
- If not ready, list blockers as first-class items.
- Show the suggested session objective and success criteria underneath.
- Risks should be visually separated from blockers.
- Keep this panel near the handoff/review area, not buried in advanced controls.

State branches:
- ready and no blockers
- review required
- blocked by task state
- blocked by decision conflict
- blocked by replan / changes requested

Copy direction:
- Focus on "what still needs to happen before continuation".
- Avoid promising automation that does not exist yet.

Do not:
- Add a fake "auto-run now" action.
- Hide blockers in secondary accordions.
- Mix blockers and risks into one undifferentiated list.

Acceptance criteria:
- A user can tell in seconds whether the system is merely suggesting a next step or is actually ready for automatic continuation.
- The panel reduces ambiguity around blocked vs ready states.
```

## Prompt Pack C: Recommendation Evidence View

Use this prompt in the frontend chat:

```text
Implement a "Why This Work Package Is Recommended" evidence view for OpenFlow using the frontend standards from this chat.

Context:
- This view should appear inside workspace-related screens without taking over the whole page.
- The goal is to connect recommendation quality to materials, decisions, and blockers.

Consume these fields:
- recommended_reason
- secondary_note
- recommendation_source
- confidence
- blocking_items
- materials_snapshot.organized_material_count
- materials_snapshot.raw_source_count
- materials_snapshot.synthesized_count
- materials_snapshot.linked_count

UI goals:
- Explain why the current recommendation exists.
- Show whether the recommendation is based on review state, blocked work, research imbalance, or current handoff.
- Help users trust the recommendation without reading raw JSON or debug text.

Interaction requirements:
- Present the primary reason first.
- Present the recommendation source in user-friendly language.
- Show materials evidence in a compact metric row.
- If blockers exist, connect them directly to the recommendation explanation.

State branches:
- handoff-driven recommendation
- confirm-gate-driven recommendation
- research/materials-gap recommendation
- decision-conflict recommendation
- blocked-task recommendation

Copy direction:
- Professional and rational.
- Explain tradeoffs and state, not internal implementation.

Do not:
- Repeat the same sentence already shown in the main work package card without adding explanatory value.
- Render raw enum values directly if better language can be derived.

Acceptance criteria:
- A user can understand not just what is next, but why the system chose that path.
- The recommendation feels evidence-backed rather than arbitrary.
```

## Prompt Pack D: System Planning Overview

Use this prompt in the frontend chat:

```text
Implement a backend-driven "System Planning Overview" view for OpenFlow using the frontend rules already defined in this chat.

Context:
- Do not redesign the entire workspace.
- This view should make the backend planning system understandable, not expose raw developer internals.
- The backend summary now returns:
  - goal_model
  - cognitive_state
  - plan_layers
  - task_graph_v2

Goals:
- Show what the system is trying to finish.
- Show how it currently understands the problem.
- Show the current multi-layer plan without overwhelming the user.
- Show how tasks connect to the active execution path.

Consume these fields:
- goal_model.core_goal
- goal_model.explicit_constraints
- goal_model.anti_goals
- goal_model.success_criteria
- cognitive_state.validated_facts
- cognitive_state.active_assumptions
- cognitive_state.open_questions
- cognitive_state.conflicts
- cognitive_state.current_gaps
- plan_layers.strategic
- plan_layers.phases
- plan_layers.milestones
- task_graph_v2.nodes
- task_graph_v2.edges

Interaction requirements:
- Present the goal and current cognitive state first.
- Present strategic / phase / milestone layers in a readable hierarchy.
- Present task graph in a way users can understand dependency and current state.
- Make conflicts and open questions clearly visible.
- Prefer readable work language over system jargon.

Do not:
- Dump raw JSON.
- Present this like an engineering admin console.
- Make graph structure the only readable representation.

Acceptance criteria:
- A user can understand the goal, current understanding, and execution path without reading implementation details.
- The screen feels like a planning control surface, not a debug page.
```

## Prompt Pack E: Execution Capsule View

Use this prompt in the frontend chat:

```text
Implement an "Execution Capsule" view for OpenFlow session-related screens using the design rules already defined in this chat.

Context:
- This module explains what a fresh session would be launched with.
- It is not a raw config dump.
- Backend fields now include:
  - execution_capsule
  - current_execution_capsule_preview

Consume these fields:
- role_name
- session_intent
- agent_profile
- mcp_set
- skill_set
- tool_set
- prompt_template
- required_files
- output_files
- memory_pack_refs
- verification_policy
- observability_policy

UI goals:
- Make it clear what the next session would receive.
- Explain role, inputs, tools, memory, and output contract.
- Keep prompt_template readable without making the screen look like a log terminal.

Interaction requirements:
- Show role and intent first.
- Group capabilities into agent / MCP / skills / tools.
- Show required files and memory packs as separate groups.
- Show output contract, verification, and observability expectations.
- Allow advanced expansion for prompt template and policy details.

Do not:
- Treat all capability lists as one flat blob.
- Show prompt text as the dominant visual element.
- Make this module feel purely technical.

Acceptance criteria:
- A user can understand what a fresh session is being equipped with.
- The screen makes clear that session continuity comes from injected files and memory packs.
```

## Prompt Pack F: Memory And Observability View

Use this prompt in the frontend chat:

```text
Implement a combined "Memory And Observability" view for OpenFlow using the frontend standards already established in this chat.

Context:
- Backend fields now include:
  - memory_pack_preview
  - observability_snapshot
  - improvement_snapshot
- The purpose is to show how continuity, execution visibility, and iterative improvement work together.

Consume these fields:
- memory_pack_preview[].layer
- memory_pack_preview[].title
- memory_pack_preview[].summary
- memory_pack_preview[].refs
- memory_pack_preview[].keywords
- observability_snapshot.current_phase
- observability_snapshot.current_node_id
- observability_snapshot.current_role
- observability_snapshot.progress_percent
- observability_snapshot.recent_events
- improvement_snapshot[].summary
- improvement_snapshot[].plan_updates
- improvement_snapshot[].mapping_updates
- improvement_snapshot[].next_focus

UI goals:
- Show how the system preserves memory across fresh sessions.
- Show current progress and recent execution visibility.
- Show that the system is improving its own plan and mapping after each step.

Interaction requirements:
- Present progress and current phase clearly.
- Show memory packs by layer, not as one undifferentiated list.
- Show recent events in a timeline or activity-feed style.
- Show improvement records as concrete adjustments, not generic encouragement.

Do not:
- Mix memory packs, logs, and improvements into a single card.
- Present raw refs without readable labeling.
- Make optimization history feel like low-value audit noise.

Acceptance criteria:
- A user can understand how past work is preserved, what the system recently did, and how the next cycle is improving.
- The interface supports trust and recovery, not just status display.
```

## Prompt Pack G: Two-Page Frontend Rewrite

Use this prompt in the frontend chat:

```text
Refactor the OpenFlow frontend into a clean two-page product structure using the frontend rules already established in this chat.

Product model:
- This is a file-driven, fresh-session execution system.
- The UI should not feel like a many-page admin dashboard.
- The user should mainly understand two things:
  1. what is happening now
  2. how the system is configured

Final page structure:
1. Chat Workspace
2. System Config

Page 1: Chat Workspace
- Use a two-column layout:
  - main chat column
  - right-side persistent context panel
- The main chat column should contain:
  - current session conversation
  - current role identity
  - input composer
  - recent step history
- The right context panel should contain:
  - current objective
  - recommended work package
  - launch readiness
  - memory summary
  - progress / observability
  - blockers
  - latest improvement

Consume these backend fields from GET /api/app/projects/{project_id}/chat:
- project
- project_stage
- goal_model
- recommendation
- recommended_work_package
- next_step
- governance
- materials
- latest_session
- latest_handoff
- timeline
- current_execution_capsule_preview
- current_session_factory_preview
- memory_pack_preview
- observability_snapshot
- improvement_snapshot
- session_detail
- complete_defaults

Page 2: System Config
- This is a full configuration surface, not a lightweight settings modal.
- Organize it into readable sections:
  - Project Definition
  - Workflow Definition
  - Role System
  - Capability Assembly
  - Memory Strategy
  - Session And Governance
- Keep each section readable and expandable.
- Avoid raw schema dumps and avoid table-heavy admin styling.

Consume these backend fields from GET /api/app/projects/{project_id}/config:
- project
- project_stage
- governance
- goal_model
- cognitive_state
- plan_layers
- task_graph_v2
- role_profiles
- capability_registry
- node_capability_map
- prewire_schemas

Design goals:
- Reduce navigation noise dramatically.
- Make the chat page feel like an execution cockpit.
- Make the config page feel powerful but understandable.
- Keep the interface professional, focused, and visually calm.
- Translate backend complexity into work language first.

Interaction rules:
- Default landing after project creation should move users toward Chat Workspace.
- System Config is a top-level sibling page, not a deep admin branch.
- Do not multiply tabs and subpages unless absolutely necessary.
- Preserve compatibility with the existing design system and component rules from this chat.

Do not:
- Rebuild a multi-page console around tasks, knowledge, workflow, and decisions.
- Lead with raw orchestration vocabulary.
- Dump JSON objects into the UI.
- Turn the config page into a developer-only control panel.

Deliverables:
- updated information architecture
- screen structure for both pages
- component tree for both pages
- state handling for empty / blocked / review / ready cases
- responsive behavior for desktop and mobile
- integration plan using the two aggregate APIs
```
