# OpenFlow Frontend Prompt Pack

This file contains prompt packs for implementing new frontend functionality in a
separate frontend-focused chat. These prompts assume the backend already returns
an enhanced `recommended_work_package` object from workspace, welcome, and
session endpoints.

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
