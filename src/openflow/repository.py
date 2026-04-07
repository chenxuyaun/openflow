from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Optional
from uuid import uuid4
from datetime import datetime, timezone

from openflow.models import (
    BootstrapRequest,
    DecisionUpdateRequest,
    DecisionRecord,
    HandoffRecord,
    HandoffReviewRequest,
    KnowledgeItem,
    ProjectState,
    ResearchPackBatchIngestRequest,
    ResearchPackIngestRequest,
    RoleInstanceSpec,
    SessionCompleteRequest,
    SessionCreateRequest,
    SessionRecord,
    SessionStatus,
    SourceType,
    TaskNode,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeType,
)


def _json_default(value: object) -> object:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Unsupported JSON value: {value!r}")


class OpenFlowRepository:
    def __init__(self, root_dir: Path, blueprint_dir: Path) -> None:
        self.root_dir = root_dir
        self.blueprint_dir = blueprint_dir
        self.data_dir = Path(os.environ.get("OPENFLOW_DATA_DIR", root_dir / "data"))
        self.projects_dir = self.data_dir / "projects"
        self.index_dir = self.data_dir / "index"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.index_dir / "openflow.db"
        self._ensure_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    project_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    goal TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    role_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS handoffs (
                    handoff_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    next_role TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    knowledge_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_type TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                """
            )

    def _project_dir(self, project_id: str) -> Path:
        return self.projects_dir / project_id

    def _session_dir(self, project_id: str, session_id: str) -> Path:
        return self._project_dir(project_id) / "sessions" / session_id

    def _write_json(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True, default=_json_default)

    def _read_json(self, path: Path) -> object:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _load_seed_knowledge(self, project_id: str) -> list[KnowledgeItem]:
        payload = self._read_json(self.blueprint_dir / "knowledge_index.json")
        items = []
        for item in payload:
            scoped = dict(item)
            scoped["project_id"] = project_id
            scoped["knowledge_id"] = f"{project_id}-{item['knowledge_id']}"
            items.append(KnowledgeItem.model_validate(scoped))
        return items

    def _load_seed_decisions(self, project_id: str) -> list[DecisionRecord]:
        payload = self._read_json(self.blueprint_dir / "decision_registry.json")
        items = []
        for item in payload:
            scoped = dict(item)
            scoped["project_id"] = project_id
            scoped["decision_id"] = f"{project_id}-{item['decision_id']}"
            items.append(DecisionRecord.model_validate(scoped))
        return items

    def _slug(self, value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return cleaned or "task"

    def _profile_request(self, goal: str, initial_prompt: str) -> dict[str, bool]:
        text = f"{goal} {initial_prompt}".lower()
        return {
            "research": any(word in text for word in ["research", "collect", "source", "资料", "调研"]),
            "implementation": any(word in text for word in ["build", "implement", "开发", "coding", "api", "system"]),
            "workflow": any(word in text for word in ["workflow", "flow", "orchestration", "handoff", "session", "角色"]),
            "ui": any(word in text for word in ["ui", "landing", "page", "experience", "design", "吸引"]),
            "knowledge": any(word in text for word in ["knowledge", "memory", "context", "file", "index", "记录"]),
            "multimodal": any(word in text for word in ["multimodal", "vlm", "image", "vision", "视觉"]),
            "planning": any(word in text for word in ["plan", "planner", "milestone", "任务", "规划"]),
        }

    def _derive_project_metadata(self, goal: str, initial_prompt: str) -> dict[str, object]:
        profile = self._profile_request(goal, initial_prompt)
        research_slots = [
            "internal_project_history",
            "competitor_and_adjacent_products",
            "workflow_handoff_methods",
            "knowledge_traceability_patterns",
        ]
        execution_priority = [
            "visualize the role-to-role workflow",
            "make the next role and next files explicit",
            "preserve decisions and evidence as durable project memory",
        ]
        project_mode = "delivery"
        project_type_label = "General Work"
        collaboration_style = "guided_multi_role"
        user_facing_roles = ["Coordinator", "Executor", "Reviewer"]
        if profile["research"] and not profile["implementation"]:
            project_mode = "research"
            project_type_label = "Research And Synthesis"
            user_facing_roles = ["Researcher", "Synthesizer", "Reviewer"]
        elif profile["ui"] and not profile["multimodal"]:
            project_mode = "experience"
            project_type_label = "Planning And Experience Design"
            user_facing_roles = ["Planner", "Designer", "Reviewer"]
        elif profile["multimodal"]:
            project_mode = "multimodal"
            project_type_label = "Multimodal Build"
            user_facing_roles = ["Planner", "Builder", "Reviewer"]
        elif profile["implementation"] or profile["workflow"]:
            project_type_label = "Build And Delivery"
            user_facing_roles = ["Planner", "Builder", "Reviewer"]
        governance_gates = [
            "architecture direction changes",
            "destructive migrations",
            "review-required role transitions",
        ]
        if profile["research"]:
            governance_gates.append("source reliability conflicts")
        attraction_focus = "visual_proof"
        if profile["ui"]:
            attraction_focus = "experience_proof"
        elif profile["research"]:
            attraction_focus = "knowledge_proof"
        return {
            "project_mode": project_mode,
            "project_type_label": project_type_label,
            "collaboration_style": collaboration_style,
            "user_facing_roles": user_facing_roles,
            "attraction_focus": attraction_focus,
            "research_slots": research_slots,
            "governance_gates": governance_gates,
            "execution_priority": execution_priority,
        }

    def _derive_role_catalog(self, goal: str, initial_prompt: str) -> list[RoleInstanceSpec]:
        profile = self._profile_request(goal, initial_prompt)
        roles = [
            RoleInstanceSpec(
                role_name="Bootstrap Strategist",
                objective="Derive the role map, workflow stages, and task decomposition from the current request files.",
                scope="Project bootstrap and orchestration framing.",
                input_requirements=["initial request transcript", "blueprint documents", "decision registry"],
                output_contract=["workflow_graph", "role_catalog", "task_tree"],
                preferred_workflow=["read request files", "extract constraints", "design role chain"],
                tools_guidance=["Treat files as durable memory and avoid relying on runtime chat context."],
            ),
            RoleInstanceSpec(
                role_name="System Architect",
                objective="Define stable boundaries, storage contracts, and handoff rules for the next execution slice.",
                scope="Architecture and interface governance.",
                input_requirements=["workflow_graph", "task_tree", "knowledge center", "handoff.json"],
                output_contract=["architecture contract", "risk gate review", "next handoff"],
                preferred_workflow=["inspect files", "reduce ambiguity", "lock interfaces"],
                tools_guidance=["Require confirmation before major direction changes."],
            ),
        ]
        if profile["research"] or profile["knowledge"]:
            roles.append(
                RoleInstanceSpec(
                    role_name="Research Curator",
                    objective="Collect and normalize source material into reusable project knowledge.",
                    scope="Research intake, evidence curation, and knowledge indexing.",
                    input_requirements=["goal statement", "existing project files", "source links or notes"],
                    output_contract=["knowledge item updates", "source map", "decision support notes"],
                    preferred_workflow=["collect sources", "extract evidence", "write normalized summaries"],
                    tools_guidance=["Separate raw material from synthesized knowledge so later roles can audit it."],
                )
            )
        if profile["implementation"] or profile["workflow"] or profile["multimodal"]:
            roles.append(
                RoleInstanceSpec(
                    role_name="Implementation Lead",
                    objective="Execute the approved work package and leave a structured handoff for the next fresh session.",
                    scope="Feature delivery, verification, and file updates.",
                    input_requirements=["architecture contract", "task tree", "project files"],
                    output_contract=["implementation delta", "verification evidence", "handoff record"],
                    preferred_workflow=["inspect requirements", "change code or content", "run verification", "emit handoff"],
                    tools_guidance=["Prefer small diffs with runnable evidence after each slice."],
                )
            )
        if profile["ui"]:
            roles.append(
                RoleInstanceSpec(
                    role_name="Experience Designer",
                    objective="Turn the product mechanism into an understandable and attractive user journey.",
                    scope="Landing narrative, flow clarity, and interface conversion.",
                    input_requirements=["product hook", "workflow graph", "knowledge center"],
                    output_contract=["experience blueprint", "interaction adjustments", "copy revisions"],
                    preferred_workflow=["map user friction", "clarify the mechanism", "align page flow to proof"],
                    tools_guidance=["Make the product attractive through visible workflow behavior, not marketing-only copy."],
                )
            )
        roles.append(
            RoleInstanceSpec(
                role_name="Review Operator",
                objective="Audit execution results, detect contradictions, and trigger replanning when quality gates fail.",
                scope="Review, verification interpretation, and risk escalation.",
                input_requirements=["verification evidence", "handoff record", "knowledge items"],
                output_contract=["review report", "decision updates", "replanning request"],
                preferred_workflow=["inspect deltas", "check criteria", "approve or redirect"],
                tools_guidance=["Escalate gaps instead of silently carrying inconsistent assumptions forward."],
            )
        )
        return roles

    def _derive_task_tree(
        self,
        goal: str,
        initial_prompt: str,
        roles: list[RoleInstanceSpec],
    ) -> list[TaskNode]:
        profile = self._profile_request(goal, initial_prompt)
        goal_fragment = goal.strip().rstrip(".")
        tasks = [
            TaskNode(
                task_id="bootstrap-request",
                title=f"Model the request into a role-driven project plan for: {goal_fragment}.",
                status=SessionStatus.active,
                owner_role="Bootstrap Strategist",
                success_criteria=[
                    "Workflow graph is written to project files",
                    "Role catalog reflects the request shape",
                    "Task tree exposes the first execution slices",
                ],
                priority="high",
            ),
            TaskNode(
                task_id="architecture-contract",
                title="Define storage, handoff, and execution contracts for the generated workflow.",
                owner_role="System Architect",
                depends_on=["bootstrap-request"],
                success_criteria=[
                    "Critical file contracts are explicit",
                    "Confirmation gates are identified",
                    "Next execution role can start from files only",
                ],
                priority="high",
            ),
        ]
        if any(role.role_name == "Research Curator" for role in roles):
            tasks.append(
                TaskNode(
                    task_id="research-intake",
                    title=f"Collect and normalize source material that strengthens: {goal_fragment}.",
                    owner_role="Research Curator",
                    depends_on=["bootstrap-request"],
                    success_criteria=[
                        "Sources are indexed as knowledge items",
                        "Key themes and open questions are extracted",
                        "Downstream roles can reuse the material without rereading raw notes",
                    ],
                    priority="high",
                )
            )
        if any(role.role_name == "Experience Designer" for role in roles):
            tasks.append(
                TaskNode(
                    task_id="experience-hook",
                    title="Shape a visible product journey that proves the workflow and makes the system compelling.",
                    owner_role="Experience Designer",
                    depends_on=["architecture-contract"],
                    success_criteria=[
                        "Landing and project flow express the mechanism clearly",
                        "The product attraction comes from real interaction proof",
                        "Copy and structure align with the workflow evidence",
                    ],
                    priority="medium",
                )
            )
        if any(role.role_name == "Implementation Lead" for role in roles):
            implementation_title = "Implement the highest-value execution slice from the generated plan."
            if profile["multimodal"]:
                implementation_title = "Implement the multimodal execution slice and connect it to file-driven planning."
            elif profile["workflow"]:
                implementation_title = "Implement the session, handoff, and workflow orchestration slice."
            tasks.append(
                TaskNode(
                    task_id="implementation-slice",
                    title=implementation_title,
                    owner_role="Implementation Lead",
                    depends_on=["architecture-contract"],
                    success_criteria=[
                        "The chosen slice is executable from project files",
                        "Verification evidence is recorded",
                        "The next fresh session can continue without hidden chat context",
                    ],
                    priority="high",
                )
            )
        tasks.append(
            TaskNode(
                task_id="review-gate",
                title="Review outputs, capture risks, and decide whether to advance or replan.",
                owner_role="Review Operator",
                depends_on=[task.task_id for task in tasks if task.owner_role != "Review Operator"],
                success_criteria=[
                    "Key risks are explicit",
                    "The next role recommendation is justified",
                    "The project can advance from durable records alone",
                ],
                priority="high",
            )
        )
        return tasks

    def _derive_workflow_graph(
        self,
        roles: list[RoleInstanceSpec],
        tasks: list[TaskNode],
    ) -> WorkflowGraph:
        node_specs = {
            "Bootstrap Strategist": ("bootstrap", WorkflowNodeType.stage, "auto"),
            "System Architect": ("architecture", WorkflowNodeType.task, "confirm"),
            "Research Curator": ("research", WorkflowNodeType.task, "auto"),
            "Experience Designer": ("experience", WorkflowNodeType.task, "auto"),
            "Implementation Lead": ("delivery", WorkflowNodeType.task, "auto"),
            "Review Operator": ("review", WorkflowNodeType.task, "auto"),
        }
        task_titles = {task.owner_role: task.title for task in tasks}
        ordered_roles = [role for role in roles if role.role_name in node_specs]
        nodes = [
            WorkflowNode(
                node_id=node_specs[role.role_name][0],
                role_name=role.role_name,
                node_type=node_specs[role.role_name][1],
                objective=task_titles.get(role.role_name, role.objective),
                handoff_policy=node_specs[role.role_name][2],
            )
            for role in ordered_roles
        ]
        edges: list[WorkflowEdge] = []
        role_ids = {role.role_name: node_specs[role.role_name][0] for role in ordered_roles}
        if "Bootstrap Strategist" in role_ids and "System Architect" in role_ids:
            edges.append(WorkflowEdge(from_node=role_ids["Bootstrap Strategist"], to_node=role_ids["System Architect"]))
        if "Bootstrap Strategist" in role_ids and "Research Curator" in role_ids:
            edges.append(
                WorkflowEdge(
                    from_node=role_ids["Bootstrap Strategist"],
                    to_node=role_ids["Research Curator"],
                    condition="research-needed",
                )
            )
        if "System Architect" in role_ids and "Experience Designer" in role_ids:
            edges.append(WorkflowEdge(from_node=role_ids["System Architect"], to_node=role_ids["Experience Designer"]))
        if "System Architect" in role_ids and "Implementation Lead" in role_ids:
            edges.append(WorkflowEdge(from_node=role_ids["System Architect"], to_node=role_ids["Implementation Lead"]))
        if "Research Curator" in role_ids and "Implementation Lead" in role_ids:
            edges.append(
                WorkflowEdge(
                    from_node=role_ids["Research Curator"],
                    to_node=role_ids["Implementation Lead"],
                    condition="research-pack-ready",
                )
            )
        if "Experience Designer" in role_ids and "Implementation Lead" in role_ids:
            edges.append(
                WorkflowEdge(
                    from_node=role_ids["Experience Designer"],
                    to_node=role_ids["Implementation Lead"],
                    condition="interaction-direction-locked",
                )
            )
        if "Implementation Lead" in role_ids and "Review Operator" in role_ids:
            edges.append(WorkflowEdge(from_node=role_ids["Implementation Lead"], to_node=role_ids["Review Operator"]))
        if "Review Operator" in role_ids and "Implementation Lead" in role_ids:
            edges.append(
                WorkflowEdge(
                    from_node=role_ids["Review Operator"],
                    to_node=role_ids["Implementation Lead"],
                    condition="changes-requested",
                )
            )
        if "Review Operator" in role_ids and "Bootstrap Strategist" in role_ids:
            edges.append(
                WorkflowEdge(
                    from_node=role_ids["Review Operator"],
                    to_node=role_ids["Bootstrap Strategist"],
                    condition="replan-required",
                )
            )
        return WorkflowGraph(nodes=nodes, edges=edges)

    def _parse_task_status_changes(self, changes: list[str]) -> dict[str, dict[str, Optional[str]]]:
        parsed: dict[str, dict[str, Optional[str]]] = {}
        for raw in changes:
            if "=" not in raw:
                continue
            task_id, remainder = raw.split("=", 1)
            task_id = task_id.strip()
            if not task_id:
                continue
            status_value = remainder.strip()
            blocked_reason: Optional[str] = None
            if ":" in status_value:
                status_value, blocked_reason = status_value.split(":", 1)
                blocked_reason = blocked_reason.strip() or None
            status_value = status_value.strip()
            if status_value not in {item.value for item in SessionStatus}:
                continue
            parsed[task_id] = {
                "status": status_value,
                "blocked_reason": blocked_reason,
            }
        return parsed

    def _apply_task_updates(
        self,
        project_id: str,
        session: SessionRecord,
        handoff: HandoffRecord,
    ) -> None:
        task_tree_path = self._project_dir(project_id) / "task_tree.json"
        task_tree = [TaskNode.model_validate(item) for item in self._read_json(task_tree_path)]
        updates = self._parse_task_status_changes(handoff.task_status_changes)
        evidence_path = f"projects/{project_id}/sessions/{session.session_id}/handoff.json"
        changed = False
        for task in task_tree:
            if task.owner_role == session.role_name and task.status == SessionStatus.active:
                task.status = SessionStatus.completed
                task.blocked_reason = None
                task.governance_source = "session_completion"
                task.last_status_reason = f"Completed by {session.role_name} and recorded in handoff {handoff.handoff_id}."
                if evidence_path not in task.evidence_refs:
                    task.evidence_refs.append(evidence_path)
                changed = True
            if task.task_id in updates:
                update = updates[task.task_id]
                task.status = SessionStatus(update["status"])
                task.blocked_reason = update["blocked_reason"]
                task.governance_source = "explicit_task_status_update"
                task.last_status_reason = f"Updated from handoff {handoff.handoff_id}."
                if evidence_path not in task.evidence_refs:
                    task.evidence_refs.append(evidence_path)
                changed = True
        if handoff.acceptance_status == "changes_requested":
            for task in task_tree:
                if task.owner_role == handoff.next_role_recommendation:
                    task.status = SessionStatus.active
                    task.governance_source = "confirm_gate_review"
                    task.last_status_reason = "Review requested another pass before advancing."
                    changed = True
                    break
        elif handoff.acceptance_status == "replan_required":
            for task in task_tree:
                if task.owner_role == "Bootstrap Strategist":
                    task.status = SessionStatus.waiting_confirmation
                    task.blocked_reason = "Review requested replanning before execution continues."
                    task.governance_source = "confirm_gate_review"
                    task.last_status_reason = "Workflow was sent back for replanning."
                    changed = True
                    break
        if changed:
            self._write_json(task_tree_path, [task.model_dump(mode="json") for task in task_tree])

    def _governance_summary(
        self,
        state: ProjectState,
        latest_handoff: Optional[HandoffRecord],
    ) -> dict[str, object]:
        confirm_waiting = False
        latest_review = None
        if latest_handoff:
            latest_review = latest_handoff.review_outcome or latest_handoff.acceptance_status
            workflow_roles = {node.role_name: node.handoff_policy for node in state.workflow_graph.nodes}
            if workflow_roles.get(latest_handoff.next_role_recommendation) == "confirm" and latest_handoff.acceptance_status != "approved":
                confirm_waiting = True
        why_current = "Project bootstrap created the initial role/task/workflow state."
        if latest_handoff:
            why_current = latest_handoff.next_role_reason
        return {
            "confirm_waiting": confirm_waiting,
            "latest_review": latest_review or "not_reviewed",
            "gates": state.governance_gates,
            "pending_handoff_id": latest_handoff.handoff_id if confirm_waiting and latest_handoff else None,
            "why_current_state": why_current,
        }

    def _review_feedback_message(self, review_status: Optional[str]) -> Optional[str]:
        if review_status == "approved":
            return "Review complete. This next step is approved and ready to continue."
        if review_status == "changes_requested":
            return "Review complete. Another pass is needed before this work moves forward."
        if review_status == "replan_required":
            return "Review complete. The workspace should replan the next step before continuing."
        return None

    def _materials_summary(self, state: ProjectState) -> dict[str, object]:
        research_items = [
            item
            for item in state.knowledge_items
            if item.source_family != "project_memory" or item.entry_kind != "derived"
        ]
        research_groups = sorted({item.source_family for item in research_items})
        raw_count = sum(1 for item in research_items if item.entry_kind == "raw_source")
        synthesized_count = sum(1 for item in research_items if item.entry_kind == "synthesized_insight")
        linked_count = sum(1 for item in research_items if item.decision_ids)
        return {
            "knowledge_count": len(state.knowledge_items),
            "organized_material_count": len(research_items),
            "research_group_count": len(research_groups),
            "research_groups": research_groups,
            "raw_source_count": raw_count,
            "synthesized_count": synthesized_count,
            "linked_count": linked_count,
            "summary": (
                f"{len(research_items)} organized materials across {len(research_groups)} groups."
                if research_items
                else "No organized materials yet. Start by turning notes and references into reusable project knowledge."
            ),
        }

    def _sort_knowledge_items(self, items: list[KnowledgeItem]) -> list[KnowledgeItem]:
        return sorted(
            items,
            key=lambda item: (
                item.generated_at,
                1 if item.entry_kind == "synthesized_insight" else 0,
            ),
            reverse=True,
        )

    def _filter_knowledge_items(
        self,
        items: list[KnowledgeItem],
        q: Optional[str] = None,
        source_family: Optional[str] = None,
        entry_kind: Optional[str] = None,
        adoption_status: Optional[str] = None,
        linked_only: bool = False,
    ) -> list[KnowledgeItem]:
        filtered = items
        if source_family:
            filtered = [item for item in filtered if item.source_family == source_family]
        if entry_kind:
            filtered = [item for item in filtered if item.entry_kind == entry_kind]
        if adoption_status:
            filtered = [item for item in filtered if item.adoption_status == adoption_status]
        if linked_only:
            filtered = [item for item in filtered if item.decision_ids]
        if q:
            q_lower = q.lower()
            filtered = [
                item
                for item in filtered
                if q_lower in item.title.lower()
                or q_lower in item.summary.lower()
                or q_lower in item.source_ref.lower()
                or any(q_lower in theme.lower() for theme in item.themes)
            ]
        return self._sort_knowledge_items(filtered)

    def _knowledge_filter_values(self, items: list[KnowledgeItem]) -> dict[str, list[str]]:
        return {
            "source_families": sorted({item.source_family for item in items}),
            "entry_kinds": sorted({item.entry_kind for item in items}),
            "adoption_statuses": sorted({item.adoption_status for item in items}),
        }

    def _grouped_knowledge_views(self, items: list[KnowledgeItem]) -> dict[str, list[dict[str, object]]]:
        grouped: dict[str, list[dict[str, object]]] = {}
        for item in items:
            key = f"{item.source_family} | {item.entry_kind} | {item.adoption_status}"
            grouped.setdefault(key, []).append(item.model_dump(mode="json"))
        return grouped

    def _project_stage(
        self,
        state: ProjectState,
        latest_handoff: Optional[HandoffRecord],
        governance: dict[str, object],
    ) -> str:
        if governance.get("confirm_waiting"):
            return "review"
        if latest_handoff and latest_handoff.acceptance_status == "replan_required":
            return "replan"
        if any(task.blocked_reason for task in state.task_tree):
            return "execution"
        if latest_handoff:
            return "execution"
        if state.project_mode == "research" or any(role.role_name == "Research Curator" for role in state.role_catalog):
            return "research_consolidation"
        return "bootstrap"

    def _recommendation_view(
        self,
        state: ProjectState,
        latest_handoff: Optional[HandoffRecord],
        governance: dict[str, object],
        materials: dict[str, object],
        blocked_now: Optional[str],
    ) -> dict[str, object]:
        if governance.get("confirm_waiting") and latest_handoff:
            return {
                "recommended_role": latest_handoff.next_role_recommendation,
                "recommended_reason": latest_handoff.next_role_reason,
                "recommended_action": "continue_review",
                "recommendation_confidence": "high",
                "recommendation_source": "confirm_gate",
                "secondary_note": "Review is required before the next step can continue.",
            }
        if latest_handoff and latest_handoff.acceptance_status == "replan_required":
            next_role = "Research Curator" if any(role.role_name == "Research Curator" for role in state.role_catalog) else "Bootstrap Strategist"
            return {
                "recommended_role": next_role,
                "recommended_reason": latest_handoff.review_note or latest_handoff.next_role_reason,
                "recommended_action": "replan",
                "recommendation_confidence": "high",
                "recommendation_source": "review_replan",
                "secondary_note": "The last review sent the project back for replanning.",
            }
        if latest_handoff and latest_handoff.acceptance_status == "changes_requested":
            return {
                "recommended_role": latest_handoff.next_role_recommendation,
                "recommended_reason": latest_handoff.review_note or latest_handoff.next_role_reason,
                "recommended_action": "needs_changes",
                "recommendation_confidence": "high",
                "recommendation_source": "review_changes_requested",
                "secondary_note": "The last review requested another execution pass before moving on.",
            }
        if blocked_now:
            blocked_task = next((task for task in state.task_tree if task.blocked_reason), None)
            return {
                "recommended_role": blocked_task.owner_role if blocked_task else (latest_handoff.next_role_recommendation if latest_handoff else state.role_catalog[0].role_name),
                "recommended_reason": blocked_now,
                "recommended_action": "open_details",
                "recommendation_confidence": "medium",
                "recommendation_source": "blocked_task",
                "secondary_note": "A blocked task is currently preventing a cleaner next-step recommendation.",
            }
        if latest_handoff:
            return {
                "recommended_role": latest_handoff.next_role_recommendation,
                "recommended_reason": latest_handoff.next_role_reason,
                "recommended_action": "start",
                "recommendation_confidence": "high",
                "recommendation_source": "latest_handoff",
                "secondary_note": "This recommendation comes from the latest completed handoff.",
            }
        research_role_exists = any(role.role_name == "Research Curator" for role in state.role_catalog)
        if research_role_exists and materials["organized_material_count"] > 0 and materials["raw_source_count"] >= materials["synthesized_count"]:
            return {
                "recommended_role": "Research Curator",
                "recommended_reason": "This workspace has more raw source material than reusable synthesis and should consolidate the materials first.",
                "recommended_action": "organize_materials",
                "recommendation_confidence": "medium",
                "recommendation_source": "raw_material_gap",
                "secondary_note": f"Raw sources: {materials['raw_source_count']} | Synthesized insights: {materials['synthesized_count']}.",
            }
        if research_role_exists and state.project_mode == "research":
            secondary_note = f"Current organized materials: {materials['organized_material_count']}."
            if materials["linked_count"] > 0:
                secondary_note = f"{secondary_note} Decision-linked materials: {materials['linked_count']}."
            return {
                "recommended_role": "Research Curator",
                "recommended_reason": "This workspace is research-led and should organize materials before the next execution step.",
                "recommended_action": "organize_materials",
                "recommendation_confidence": "medium",
                "recommendation_source": "project_mode_research",
                "secondary_note": secondary_note,
            }
        first_role = state.role_catalog[0].role_name if state.role_catalog else "Implementation Lead"
        return {
            "recommended_role": first_role,
            "recommended_reason": "No handoff exists yet, so the workspace should start the first executable step.",
            "recommended_action": "start_first_step",
            "recommendation_confidence": "medium",
            "recommendation_source": "bootstrap_fallback",
            "secondary_note": "This is the first role available from the current project state.",
        }

    def _next_step_view(
        self,
        latest_handoff: Optional[HandoffRecord],
        governance: dict[str, object],
        recommendation: dict[str, object],
    ) -> dict[str, object]:
        if not latest_handoff:
            if recommendation["recommended_action"] == "organize_materials":
                return {
                    "state": "research_gap",
                    "message": "This workspace should organize materials before the next execution step.",
                    "actions": ["organize_materials"],
                    "primary_label": "Organize Materials",
                }
            return {
                "state": "none",
                "message": "No suggested next step has been written yet.",
                "actions": ["start_first_step"],
                "primary_label": "Start First Work Step",
            }
        if governance.get("confirm_waiting"):
            return {
                "state": "review_needed",
                "message": "This next step needs a review before it can start.",
                "actions": ["continue", "needs_changes", "replan"],
                "primary_label": "Continue",
            }
        if latest_handoff.acceptance_status == "changes_requested":
            return {
                "state": "changes_requested",
                "message": "This work needs another pass before moving on.",
                "actions": [],
                "primary_label": None,
            }
        if latest_handoff.acceptance_status == "replan_required":
            return {
                "state": "replan_required",
                "message": "This work should be replanned before moving on.",
                "actions": [],
                "primary_label": None,
            }
        return {
            "state": "ready",
            "message": "This next step is ready to start.",
            "actions": ["start"],
            "primary_label": "Start Suggested Next Step",
        }

    def _decision_support_map(
        self,
        knowledge_items: list[KnowledgeItem],
        decisions: list[DecisionRecord],
    ) -> list[dict[str, object]]:
        support = []
        for decision in decisions:
            linked = [
                item.model_dump(mode="json")
                for item in knowledge_items
                if decision.decision_id in item.decision_ids
            ]
            normalized_status = decision.status
            if normalized_status == "accepted":
                normalized_status = "adopted"
            support.append(
                {
                    "decision_id": decision.decision_id,
                    "title": decision.title,
                    "status": normalized_status,
                    "rationale": decision.rationale,
                    "supporting_knowledge": linked,
                }
            )
        return support

    def _knowledge_file(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "knowledge" / "knowledge_items.json"

    def _blueprint_documents(self) -> list[str]:
        docs = ["README.md"]
        for path in sorted(self.blueprint_dir.glob("*")):
            if path.is_file():
                docs.append(str(path.relative_to(self.root_dir)).replace("\\", "/"))
        return docs

    def _git_commit_knowledge_items(self, project_id: str) -> list[KnowledgeItem]:
        command = [
            "git",
            "log",
            "--max-count=10",
            "--pretty=format:%H%x1f%aI%x1f%s%x1f%b",
        ]
        result = subprocess.run(
            command,
            cwd=self.root_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        items: list[KnowledgeItem] = []
        if result.returncode != 0:
            return [
                KnowledgeItem(
                    project_id=project_id,
                    knowledge_id=f"git-source-{project_id}",
                    title="Git source connected but unreadable",
                    source_type=SourceType.git,
                    source_ref="git-log",
                    summary="Git history could not be read for this project.",
                    themes=["execution_tracking", "project_evolution"],
                    reliability="low",
                    relevance="medium",
                )
            ]
        output = result.stdout or ""
        lines = [line for line in output.splitlines() if line.strip()]
        if not lines:
            return [
                KnowledgeItem(
                    project_id=project_id,
                    knowledge_id=f"git-source-{project_id}",
                    title="Git source connected but history shallow",
                    source_type=SourceType.git,
                    source_ref="git-log",
                    summary="No commit history was available when the project bootstrap ran.",
                    themes=["execution_tracking", "project_evolution"],
                    reliability="medium",
                    relevance="medium",
                )
            ]
        for index, line in enumerate(lines):
            parts = line.split("\x1f")
            commit_hash = parts[0]
            commit_date = parts[1] if len(parts) > 1 else ""
            subject = parts[2] if len(parts) > 2 else "Commit"
            body = parts[3].strip() if len(parts) > 3 else ""
            summary = subject if not body else f"{subject} | {body[:160]}"
            items.append(
                KnowledgeItem(
                    project_id=project_id,
                    knowledge_id=f"git-{project_id}-{index}",
                    title=f"Git commit {commit_hash[:7]}",
                    source_type=SourceType.git,
                    source_ref=commit_hash,
                    summary=summary,
                    themes=["execution_tracking", "project_evolution"],
                    reliability="high",
                    relevance="high",
                    generated_at=commit_date or None,
                )
            )
        return items

    def _project_file_knowledge_items(
        self,
        project_id: str,
        project_name: str,
        goal: str,
        session_id: str,
    ) -> list[KnowledgeItem]:
        return [
            KnowledgeItem(
                project_id=project_id,
                knowledge_id=f"project-meta-{project_id}",
                title=f"{project_name} bootstrap goal",
                source_type=SourceType.repo,
                source_ref=f"projects/{project_id}/project.json",
                summary=goal,
                themes=["project_bootstrap", "product_narrative"],
                reliability="high",
                relevance="high",
                session_id=session_id,
            ),
            KnowledgeItem(
                project_id=project_id,
                knowledge_id=f"workflow-{project_id}",
                title=f"{project_name} workflow graph",
                source_type=SourceType.repo,
                source_ref=f"projects/{project_id}/workflow_graph.json",
                summary="Initial workflow graph generated for the project bootstrap.",
                themes=["workflow_governance", "role_orchestration"],
                reliability="high",
                relevance="high",
                decision_ids=["dec-001", "dec-002"],
                session_id=session_id,
            ),
            KnowledgeItem(
                project_id=project_id,
                knowledge_id=f"task-tree-{project_id}",
                title=f"{project_name} task tree",
                source_type=SourceType.repo,
                source_ref=f"projects/{project_id}/task_tree.json",
                summary="Initial task decomposition for the project.",
                themes=["execution_tracking", "task_planning"],
                reliability="high",
                relevance="high",
                session_id=session_id,
            ),
        ]

    def _session_knowledge_items(
        self,
        project_id: str,
        session: SessionRecord,
        handoff: HandoffRecord,
    ) -> list[KnowledgeItem]:
        return [
            KnowledgeItem(
                project_id=project_id,
                knowledge_id=f"session-meta-{session.session_id}",
                title=f"Session {session.session_id} metadata",
                source_type=SourceType.repo,
                source_ref=f"projects/{project_id}/sessions/{session.session_id}/session.json",
                summary=f"{session.role_name} worked on: {session.objective}",
                themes=["session_isolation", "execution_tracking"],
                reliability="high",
                relevance="high",
                session_id=session.session_id,
            ),
            KnowledgeItem(
                project_id=project_id,
                knowledge_id=f"handoff-{handoff.handoff_id}",
                title=f"Handoff {handoff.handoff_id}",
                source_type=SourceType.repo,
                source_ref=f"projects/{project_id}/sessions/{session.session_id}/handoff.json",
                summary=handoff.session_summary,
                themes=["handoff_governance", "review_replanning"],
                reliability="high",
                relevance="high",
                session_id=session.session_id,
                handoff_id=handoff.handoff_id,
                decision_ids=[f"session:{session.session_id}"],
            ),
        ]

    def _transcript_summary_item(
        self,
        project_id: str,
        session: SessionRecord,
        transcript: list[dict[str, object]],
    ) -> KnowledgeItem:
        entry_count = len(transcript)
        snippets = []
        for entry in transcript[-4:]:
            content = str(entry.get("content", "")).strip()
            if content:
                snippets.append(content)
        text = " ".join(snippets)
        sentences = [
            part.strip(" -")
            for part in re.split(r"[。\n;!?]+", text)
            if part.strip(" -")
        ]
        completed = [item for item in sentences if any(token in item.lower() for token in ["done", "completed", "implemented", "finished", "shipped", "完成", "实现"])]
        decisions = [item for item in sentences if any(token in item.lower() for token in ["decide", "decision", "keep", "use", "choose", "adopt", "采用", "保持"])]
        risks = [item for item in sentences if any(token in item.lower() for token in ["risk", "block", "issue", "need", "todo", "pending", "风险", "阻塞", "待处理"])]
        next_steps = [item for item in sentences if any(token in item.lower() for token in ["next", "follow", "review", "handoff", "replan", "下一步", "继续", "review"])]

        if not completed and sentences:
            completed = [sentences[0]]
        if not next_steps and session.objective:
            next_steps = [f"Continue from the session objective: {session.objective}"]

        summary_parts = [
            f"{entry_count} transcript entries captured for {session.role_name}.",
            "Tasks completed: " + ("; ".join(completed[:2]) if completed else "No explicit completion notes recorded."),
            "Key decisions: " + ("; ".join(decisions[:2]) if decisions else "No explicit decision statements recorded."),
            "Risks or blockers: " + ("; ".join(risks[:2]) if risks else "No explicit blockers recorded."),
            "Recommended next step: " + ("; ".join(next_steps[:1]) if next_steps else "Review the handoff and decide the next role."),
        ]
        summary = " ".join(summary_parts)
        return KnowledgeItem(
            project_id=project_id,
            knowledge_id=f"transcript-summary-{session.session_id}",
            title=f"Transcript summary for {session.session_id}",
            source_type=SourceType.chat,
            source_ref=f"projects/{project_id}/sessions/{session.session_id}/transcript.jsonl",
            summary=summary,
            themes=["session_isolation", "knowledge_indexing", "execution_tracking"],
            reliability="medium",
            relevance="high",
            session_id=session.session_id,
        )

    def _append_knowledge_items(self, project_id: str, items: list[KnowledgeItem]) -> None:
        existing = [
            KnowledgeItem.model_validate(item)
            for item in self._read_json(self._knowledge_file(project_id))
        ]
        merged = existing + items
        self._write_json(
            self._knowledge_file(project_id),
            [item.model_dump(mode="json") for item in merged],
        )
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO knowledge_items(knowledge_id, project_id, title, source_type) VALUES (?, ?, ?, ?)",
                [
                    (item.knowledge_id, project_id, item.title, item.source_type.value)
                    for item in items
                ],
            )

    def _decision_file(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "decisions.json"

    def _normalize_decision_status(self, status: str) -> str:
        normalized = status.strip().lower()
        if normalized == "accepted":
            return "adopted"
        return normalized

    def ingest_research_pack(self, request: ResearchPackIngestRequest) -> dict[str, object]:
        pack_slug = self._slug(request.pack_title)
        raw_item = KnowledgeItem(
            project_id=request.project_id,
            knowledge_id=f"research-raw-{pack_slug}-{uuid4().hex[:6]}",
            title=f"{request.pack_title} raw source",
            source_type=SourceType.external,
            source_family=request.source_family,
            entry_kind="raw_source",
            adoption_status="reference",
            source_ref=request.source_ref,
            summary=request.raw_notes,
            themes=request.themes,
            reliability=request.reliability,
            relevance=request.relevance,
            decision_ids=request.decision_ids,
        )
        synthesized_item = KnowledgeItem(
            project_id=request.project_id,
            knowledge_id=f"research-derived-{pack_slug}-{uuid4().hex[:6]}",
            title=f"{request.pack_title} synthesized insight",
            source_type=SourceType.external,
            source_family=request.source_family,
            entry_kind="synthesized_insight",
            adoption_status=request.adoption_status,
            source_ref=request.source_ref,
            summary=request.synthesized_summary,
            themes=request.themes,
            reliability=request.reliability,
            relevance=request.relevance,
            decision_ids=request.decision_ids,
        )
        self._append_knowledge_items(request.project_id, [raw_item, synthesized_item])
        return {
            "project_id": request.project_id,
            "items": [
                raw_item.model_dump(mode="json"),
                synthesized_item.model_dump(mode="json"),
            ],
        }

    def ingest_research_pack_batch(self, request: ResearchPackBatchIngestRequest) -> dict[str, object]:
        items = []
        for pack in request.packs:
            normalized_pack = ResearchPackIngestRequest(
                project_id=request.project_id,
                pack_title=pack.pack_title,
                source_family=pack.source_family,
                source_ref=pack.source_ref,
                raw_notes=pack.raw_notes,
                synthesized_summary=pack.synthesized_summary,
                themes=pack.themes,
                decision_ids=pack.decision_ids,
                adoption_status=pack.adoption_status,
                reliability=pack.reliability,
                relevance=pack.relevance,
            )
            result = self.ingest_research_pack(normalized_pack)
            items.extend(result["items"])
        return {"project_id": request.project_id, "items": items}

    def get_project_decisions(self, project_id: str) -> dict[str, object]:
        state = self.get_project_state(project_id)
        decision_support = self._decision_support_map(state.knowledge_items, state.decisions)
        return {
            "project_id": project_id,
            "decisions": decision_support,
        }

    def update_decision(self, project_id: str, decision_id: str, request: DecisionUpdateRequest) -> dict[str, object]:
        allowed = {"proposed", "adopted", "rejected", "deferred"}
        normalized_status = self._normalize_decision_status(request.status)
        if normalized_status not in allowed:
            raise ValueError(f"Unsupported decision status: {request.status}")
        decisions = [
            DecisionRecord.model_validate(item)
            for item in self._read_json(self._decision_file(project_id))
        ]
        updated = None
        for decision in decisions:
            if decision.decision_id == decision_id:
                decision.status = normalized_status
                updated = decision
                break
        if updated is None:
            raise FileNotFoundError(f"Unknown decision: {decision_id}")
        self._write_json(self._decision_file(project_id), [item.model_dump(mode="json") for item in decisions])
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO decisions(decision_id, project_id, title, status) VALUES (?, ?, ?, ?)",
                (updated.decision_id, project_id, updated.title, updated.status),
            )
        return updated.model_dump(mode="json")

    def _apply_review_action_to_tasks(
        self,
        project_id: str,
        session: SessionRecord,
        handoff: HandoffRecord,
        action: str,
    ) -> None:
        task_tree_path = self._project_dir(project_id) / "task_tree.json"
        task_tree = [TaskNode.model_validate(item) for item in self._read_json(task_tree_path)]
        changed = False
        if action == "changes_requested":
            for task in task_tree:
                if task.owner_role == session.role_name:
                    task.status = SessionStatus.active
                    task.blocked_reason = "Confirm gate review requested changes before advance."
                    task.governance_source = "confirm_gate_review"
                    task.last_status_reason = handoff.review_note or "Review requested changes."
                    changed = True
        elif action == "replan_required":
            for task in task_tree:
                if task.owner_role == "Bootstrap Strategist":
                    task.status = SessionStatus.active
                    task.blocked_reason = "Confirm gate review sent the project back for replanning."
                    task.governance_source = "confirm_gate_review"
                    task.last_status_reason = handoff.review_note or "Review required replanning."
                    changed = True
        elif action == "approve":
            for task in task_tree:
                if task.owner_role == handoff.next_role_recommendation and task.status == SessionStatus.waiting_confirmation:
                    task.status = SessionStatus.active
                    task.blocked_reason = None
                    task.governance_source = "confirm_gate_review"
                    task.last_status_reason = handoff.review_note or "Review approved the next role."
                    changed = True
        if changed:
            self._write_json(task_tree_path, [task.model_dump(mode="json") for task in task_tree])

    def review_handoff(self, handoff_id: str, request: HandoffReviewRequest) -> dict[str, object]:
        handoff = self._find_handoff(handoff_id)
        session = self._find_session(handoff.session_id)
        action = request.action.strip().lower()
        if action not in {"approve", "changes_requested", "replan_required"}:
            raise ValueError(f"Unsupported review action: {request.action}")

        handoff.status = action
        handoff.review_outcome = action
        handoff.review_note = request.note
        handoff.followup_actions = list(handoff.followup_actions) + ([request.note] if request.note else [])
        if action == "approve":
            handoff.acceptance_status = "approved"
            handoff.resulting_role = handoff.next_role_recommendation
        elif action == "changes_requested":
            handoff.acceptance_status = "changes_requested"
            handoff.next_role_recommendation = session.role_name
            handoff.next_role_reason = request.note or "Confirm gate review requested another execution pass."
            handoff.required_input_files = sorted(
                set(handoff.required_input_files + [f"projects/{handoff.project_id}/sessions/{handoff.session_id}/handoff.json"])
            )
            handoff.resulting_role = session.role_name
        else:
            handoff.acceptance_status = "replan_required"
            handoff.next_role_recommendation = "Bootstrap Strategist"
            handoff.next_role_reason = request.note or "Confirm gate review requested replanning."
            handoff.required_input_files = sorted(
                set(handoff.required_input_files + [f"projects/{handoff.project_id}/sessions/{handoff.session_id}/handoff.json"])
            )
            handoff.resulting_role = "Bootstrap Strategist"
        handoff.reviewed_at = datetime.now(timezone.utc)

        self._write_json(
            self._session_dir(handoff.project_id, handoff.session_id) / "handoff.json",
            handoff.model_dump(mode="json"),
        )
        self._apply_review_action_to_tasks(handoff.project_id, session, handoff, action)
        return {
            "handoff_id": handoff.handoff_id,
            "status": handoff.status,
            "acceptance_status": handoff.acceptance_status,
            "next_role": handoff.next_role_recommendation,
        }

    def bootstrap_project(self, request: BootstrapRequest) -> dict[str, object]:
        project_id = f"project-{uuid4().hex[:8]}"
        session_id = f"session-{uuid4().hex[:8]}"
        project_name = request.project_name or "OpenFlow Project"
        project_dir = self._project_dir(project_id)
        metadata = self._derive_project_metadata(request.goal, request.initial_prompt)
        role_catalog = self._derive_role_catalog(request.goal, request.initial_prompt)
        task_tree = self._derive_task_tree(request.goal, request.initial_prompt, role_catalog)
        workflow_graph = self._derive_workflow_graph(role_catalog, task_tree)
        knowledge_items = self._load_seed_knowledge(project_id)
        decisions = self._load_seed_decisions(project_id)
        session = SessionRecord(
            project_id=project_id,
            session_id=session_id,
            role_name="Bootstrap Strategist",
            objective=request.goal,
            status=SessionStatus.active,
            input_files=["docs/product_hook.md", "docs/master_prd.md"],
        )
        project_state = ProjectState(
            project_id=project_id,
            project_mode=str(metadata["project_mode"]),
            project_type_label=str(metadata["project_type_label"]),
            collaboration_style=str(metadata["collaboration_style"]),
            user_facing_roles=list(metadata["user_facing_roles"]),
            attraction_focus=str(metadata["attraction_focus"]),
            research_slots=list(metadata["research_slots"]),
            governance_gates=list(metadata["governance_gates"]),
            execution_priority=list(metadata["execution_priority"]),
            workflow_graph=workflow_graph,
            role_catalog=role_catalog,
            task_tree=task_tree,
            sessions=[session],
            knowledge_items=knowledge_items,
            decisions=decisions,
        )

        self._write_json(
            project_dir / "project.json",
            {
                "project_id": project_id,
                "project_name": project_name,
                "goal": request.goal,
                "initial_prompt": request.initial_prompt,
                "created_at": project_state.created_at,
                "project_mode": project_state.project_mode,
                "project_type_label": project_state.project_type_label,
                "collaboration_style": project_state.collaboration_style,
                "user_facing_roles": project_state.user_facing_roles,
                "attraction_focus": project_state.attraction_focus,
                "research_slots": project_state.research_slots,
                "governance_gates": project_state.governance_gates,
                "execution_priority": project_state.execution_priority,
            },
        )
        self._write_json(project_dir / "workflow_graph.json", workflow_graph.model_dump(mode="json"))
        self._write_json(project_dir / "task_tree.json", [task.model_dump(mode="json") for task in task_tree])
        self._write_json(project_dir / "role_catalog.json", [role.model_dump(mode="json") for role in role_catalog])
        self._write_json(project_dir / "decisions.json", [item.model_dump(mode="json") for item in decisions])
        self._write_json(project_dir / "knowledge" / "knowledge_items.json", [item.model_dump(mode="json") for item in knowledge_items])
        self._write_json(self._session_dir(project_id, session_id) / "session.json", session.model_dump(mode="json"))
        self._write_json(
            self._session_dir(project_id, session_id) / "transcript.jsonl",
            [{"role": "user", "content": request.initial_prompt}],
        )

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO projects(project_id, project_name, created_at, goal) VALUES (?, ?, ?, ?)",
                (project_id, project_name, project_state.created_at.isoformat(), request.goal),
            )
            conn.execute(
                "INSERT INTO sessions(session_id, project_id, role_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, project_id, session.role_name, session.status.value, session.created_at.isoformat()),
            )
            conn.executemany(
                "INSERT INTO knowledge_items(knowledge_id, project_id, title, source_type) VALUES (?, ?, ?, ?)",
                [(item.knowledge_id, project_id, item.title, item.source_type.value) for item in knowledge_items],
            )
            conn.executemany(
                "INSERT INTO decisions(decision_id, project_id, title, status) VALUES (?, ?, ?, ?)",
                [(item.decision_id, project_id, item.title, item.status) for item in decisions],
            )

        self._append_knowledge_items(
            project_id,
            self._project_file_knowledge_items(project_id, project_name, request.goal, session_id)
            + self._git_commit_knowledge_items(project_id),
        )

        return {
            "project_id": project_id,
            "session_id": session_id,
            "project_name": project_name,
            "project_state": project_state,
        }

    def create_session(self, request: SessionCreateRequest) -> SessionRecord:
        session = SessionRecord(
            project_id=request.project_id,
            session_id=f"session-{uuid4().hex[:8]}",
            role_name=request.role_name,
            objective=request.objective,
            status=SessionStatus.active,
            input_files=request.input_files,
        )
        self._write_json(
            self._session_dir(request.project_id, session.session_id) / "session.json",
            session.model_dump(mode="json"),
        )
        self._write_json(
            self._session_dir(request.project_id, session.session_id) / "transcript.jsonl",
            [
                {
                    "role": "system",
                    "content": f"Session created for {request.role_name}: {request.objective}",
                }
            ],
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions(session_id, project_id, role_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
                (session.session_id, request.project_id, session.role_name, session.status.value, session.created_at.isoformat()),
            )
        return session

    def complete_session(self, session_id: str, request: SessionCompleteRequest) -> HandoffRecord:
        session = self._find_session(session_id)
        transcript_path = self._session_dir(session.project_id, session_id) / "transcript.jsonl"
        transcript = self._read_json(transcript_path)
        if request.transcript_note:
            transcript.append({"role": "assistant", "content": request.transcript_note})
            self._write_json(transcript_path, transcript)
        handoff = HandoffRecord(
            project_id=session.project_id,
            session_id=session_id,
            handoff_id=f"handoff-{uuid4().hex[:8]}",
            session_summary=request.session_summary,
            decision_updates=request.decision_updates,
            task_status_changes=request.task_status_changes,
            next_role_recommendation=request.next_role_recommendation,
            next_role_reason=request.next_role_reason,
            required_input_files=request.required_input_files,
            success_criteria=request.success_criteria,
            risks=request.risks,
            review_outcome=request.review_outcome,
            acceptance_status=request.acceptance_status,
            followup_actions=request.followup_actions,
        )
        self._write_json(
            self._session_dir(session.project_id, session_id) / "handoff.json",
            handoff.model_dump(mode="json"),
        )
        session.status = SessionStatus.completed
        self._write_json(
            self._session_dir(session.project_id, session_id) / "session.json",
            session.model_dump(mode="json"),
        )
        with self._connect() as conn:
            conn.execute("UPDATE sessions SET status = ? WHERE session_id = ?", (session.status.value, session_id))
            conn.execute(
                "INSERT INTO handoffs(handoff_id, project_id, session_id, next_role, status) VALUES (?, ?, ?, ?, ?)",
                (handoff.handoff_id, handoff.project_id, handoff.session_id, handoff.next_role_recommendation, handoff.status),
            )
        self._apply_task_updates(session.project_id, session, handoff)
        self._append_knowledge_items(
            session.project_id,
            self._session_knowledge_items(session.project_id, session, handoff)
            + [self._transcript_summary_item(session.project_id, session, transcript)],
        )
        return handoff

    def advance_handoff(self, handoff_id: str) -> dict[str, object]:
        handoff = self._find_handoff(handoff_id)
        workflow = self.get_project_workflow(handoff.project_id)
        next_policy = "auto"
        for stage in workflow.get("workflow_blueprint", {}).get("stages", []):
            if stage.get("role_name") == handoff.next_role_recommendation or stage.get("stage_id") == handoff.next_role_recommendation:
                next_policy = stage.get("handoff_policy", "auto")
                break
        if next_policy == "confirm" and handoff.acceptance_status != "approved":
            return {
                "status": "waiting_confirmation",
                "handoff_id": handoff.handoff_id,
                "next_role": handoff.next_role_recommendation,
                "acceptance_status": handoff.acceptance_status or "pending_review",
            }
        session = self.create_session(
            SessionCreateRequest(
                project_id=handoff.project_id,
                role_name=handoff.next_role_recommendation,
                objective=handoff.next_role_reason,
                input_files=handoff.required_input_files,
            )
        )
        return {
            "status": "advanced",
            "handoff_id": handoff.handoff_id,
            "session": session.model_dump(mode="json"),
        }

    def get_project_state(self, project_id: str) -> ProjectState:
        project_dir = self._project_dir(project_id)
        workflow_graph = WorkflowGraph.model_validate(self._read_json(project_dir / "workflow_graph.json"))
        role_catalog = [RoleInstanceSpec.model_validate(item) for item in self._read_json(project_dir / "role_catalog.json")]
        task_tree = [TaskNode.model_validate(item) for item in self._read_json(project_dir / "task_tree.json")]
        knowledge_items = [KnowledgeItem.model_validate(item) for item in self._read_json(project_dir / "knowledge" / "knowledge_items.json")]
        decisions = [DecisionRecord.model_validate(item) for item in self._read_json(project_dir / "decisions.json")]
        project_meta = self._read_json(project_dir / "project.json")
        sessions = []
        sessions_root = project_dir / "sessions"
        if sessions_root.exists():
            for path in sorted(sessions_root.glob("*/session.json")):
                sessions.append(SessionRecord.model_validate(self._read_json(path)))
        return ProjectState(
            project_id=project_id,
            project_mode=str(project_meta.get("project_mode", "delivery")),
            project_type_label=str(project_meta.get("project_type_label", "General Work")),
            collaboration_style=str(project_meta.get("collaboration_style", "guided_multi_role")),
            user_facing_roles=list(project_meta.get("user_facing_roles", [])),
            attraction_focus=str(project_meta.get("attraction_focus", "visual_proof")),
            research_slots=list(project_meta.get("research_slots", [])),
            governance_gates=list(project_meta.get("governance_gates", [])),
            execution_priority=list(project_meta.get("execution_priority", [])),
            workflow_graph=workflow_graph,
            role_catalog=role_catalog,
            task_tree=task_tree,
            sessions=sessions,
            knowledge_items=knowledge_items,
            decisions=decisions,
        )

    def get_project_summary(self, project_id: str) -> dict[str, object]:
        project_meta = self._read_json(self._project_dir(project_id) / "project.json")
        state = self.get_project_state(project_id)
        latest_session = None
        latest_handoff = None
        if state.sessions:
            latest_session = max(state.sessions, key=lambda item: item.created_at)
        for session in sorted(state.sessions, key=lambda item: item.created_at, reverse=True):
            handoff_path = self._session_dir(project_id, session.session_id) / "handoff.json"
            if handoff_path.exists():
                latest_handoff = HandoffRecord.model_validate(self._read_json(handoff_path))
                break
        timeline = self.get_project_timeline(project_id)
        governance = self._governance_summary(state, latest_handoff)
        blocked_now = None
        for task in state.task_tree:
            if task.blocked_reason:
                blocked_now = task.blocked_reason
                break
        materials = self._materials_summary(state)
        recommendation = self._recommendation_view(state, latest_handoff, governance, materials, blocked_now)
        next_step = self._next_step_view(latest_handoff, governance, recommendation)
        project_stage = self._project_stage(state, latest_handoff, governance)
        next_role = recommendation["recommended_role"]
        why_next_role = recommendation["recommended_reason"]
        return {
            "project_id": project_id,
            "project": project_meta,
            "state": state.model_dump(mode="json"),
            "latest_session": latest_session.model_dump(mode="json") if latest_session else None,
            "latest_handoff": latest_handoff.model_dump(mode="json") if latest_handoff else None,
            "timeline": timeline["events"],
            "governance": governance,
            "project_stage": project_stage,
            "recommendation": recommendation,
            "next_step": next_step,
            "materials": materials,
            "next_role": next_role,
            "why_next_role": why_next_role,
            "blocked_now": blocked_now,
        }

    def get_project_knowledge(
        self,
        project_id: str,
        q: Optional[str] = None,
        source_family: Optional[str] = None,
        entry_kind: Optional[str] = None,
        adoption_status: Optional[str] = None,
        linked_only: bool = False,
    ) -> dict[str, object]:
        state = self.get_project_state(project_id)
        project_files = []
        for path in sorted(self._project_dir(project_id).rglob("*")):
            if path.is_file():
                try:
                    display_path = path.relative_to(self.data_dir)
                except ValueError:
                    display_path = path
                project_files.append(str(display_path).replace("\\", "/"))
        sorted_items = self._sort_knowledge_items(state.knowledge_items)
        filtered_items = self._filter_knowledge_items(
            state.knowledge_items,
            q=q,
            source_family=source_family,
            entry_kind=entry_kind,
            adoption_status=adoption_status,
            linked_only=linked_only,
        )
        research_packs = [item for item in filtered_items if item.source_family != "project_memory" or item.entry_kind != "derived"]
        grouped_research: dict[str, list[dict[str, object]]] = {}
        for item in research_packs:
            grouped_research.setdefault(item.source_family, []).append(item.model_dump(mode="json"))
        decision_support = self._decision_support_map(state.knowledge_items, state.decisions)
        materials = self._materials_summary(state)
        available_filter_values = self._knowledge_filter_values(state.knowledge_items)
        return {
            "project_id": project_id,
            "blueprint_documents": self._blueprint_documents(),
            "knowledge_items": [item.model_dump(mode="json") for item in filtered_items],
            "evolution_feed": [item.model_dump(mode="json") for item in sorted_items],
            "decisions": [item.model_dump(mode="json") for item in state.decisions],
            "project_files": project_files,
            "research_groups": grouped_research,
            "grouped_views": self._grouped_knowledge_views(research_packs),
            "decision_support": decision_support,
            "materials": materials,
            "filtered_count": len(filtered_items),
            "filters": {
                "q": q or "",
                "source_family": source_family or "",
                "entry_kind": entry_kind or "",
                "adoption_status": adoption_status or "",
                "linked_only": linked_only,
            },
            "available_filter_values": available_filter_values,
            "organize_defaults": {
                "pack_title": "Collected source review",
                "source_family": "workflow_handoff_methods",
                "source_ref": "organized-notes",
                "raw_notes": "Paste raw notes, links, meeting notes, or earlier chat summaries here.",
                "synthesized_summary": "Summarize what should change in the product, process, or next decision.",
                "batch_payload": (
                    "pack_title: Collected source review\n"
                    "source_family: workflow_handoff_methods\n"
                    "source_ref: organized-notes\n"
                    "raw_notes: Raw notes from references and working files.\n"
                    "synthesized_summary: Make the next step and handoff state visible.\n"
                    "themes: handoff_governance,knowledge_indexing\n"
                    "decision_ids:\n"
                    "adoption_status: proposed\n"
                    "reliability: medium\n"
                    "relevance: high"
                ),
            },
        }

    def get_project_timeline(self, project_id: str) -> dict[str, object]:
        state = self.get_project_state(project_id)
        events = []
        project_meta = self._read_json(self._project_dir(project_id) / "project.json")
        events.append(
            {
                "event_type": "project_bootstrap",
                "timestamp": project_meta["created_at"],
                "title": f"Project {project_meta['project_name']} bootstrapped",
                "summary": project_meta["goal"],
                "because": "The initial request was turned into a role/task/workflow model.",
                "target_url": f"/projects/{project_id}",
            }
        )
        for session in state.sessions:
            session_reason = f"{session.role_name} was started because its declared objective was active."
            events.append(
                {
                    "event_type": "session_created",
                    "timestamp": session.created_at.isoformat(),
                    "title": f"Session {session.session_id} created",
                    "summary": f"{session.role_name} started work.",
                    "because": session_reason,
                    "target_url": f"/projects/{project_id}/sessions/{session.session_id}",
                }
            )
            handoff_path = self._session_dir(project_id, session.session_id) / "handoff.json"
            if handoff_path.exists():
                handoff = HandoffRecord.model_validate(self._read_json(handoff_path))
                events.append(
                    {
                        "event_type": "handoff_written",
                        "timestamp": handoff.created_at.isoformat(),
                        "title": f"Handoff {handoff.handoff_id} written",
                        "summary": handoff.session_summary,
                        "because": handoff.next_role_reason,
                        "target_url": f"/projects/{project_id}/sessions/{session.session_id}",
                    }
                )
        for item in state.knowledge_items:
            title = item.title
            event_type = "knowledge_ingested"
            if item.source_type == SourceType.git:
                event_type = "git_commit_ingested"
            elif item.handoff_id:
                event_type = "handoff_knowledge_ingested"
            elif item.session_id:
                event_type = "session_knowledge_ingested"
            elif item.entry_kind == "synthesized_insight" and item.source_family != "project_memory":
                event_type = "materials_organized"
            events.append(
                {
                    "event_type": event_type,
                    "timestamp": item.generated_at.isoformat(),
                    "title": title,
                    "summary": item.summary,
                    "because": (
                        "Materials were organized into reusable project knowledge."
                        if event_type == "materials_organized"
                        else f"{item.entry_kind} was preserved as durable project memory."
                    ),
                    "target_url": (
                        f"/projects/{project_id}/sessions/{item.session_id}"
                        if item.session_id
                        else f"/projects/{project_id}/knowledge"
                    ),
                }
            )
        events.sort(key=lambda item: item["timestamp"], reverse=True)
        return {"project_id": project_id, "events": events}

    def get_project_workflow(self, project_id: str) -> dict[str, object]:
        state = self.get_project_state(project_id)
        blueprint = self._read_json(self.blueprint_dir / "workflow_blueprint.json")
        return {
            "project_id": project_id,
            "workflow_blueprint": blueprint,
            "workflow_graph": state.workflow_graph.model_dump(mode="json"),
            "role_catalog": [item.model_dump(mode="json") for item in state.role_catalog],
            "governance_gates": state.governance_gates,
            "attraction_focus": state.attraction_focus,
        }

    def get_project_tasks(self, project_id: str) -> dict[str, object]:
        state = self.get_project_state(project_id)
        counts = {
            "planned": 0,
            "active": 0,
            "waiting_confirmation": 0,
            "completed": 0,
        }
        for task in state.task_tree:
            counts[task.status.value] += 1
        return {
            "project_id": project_id,
            "project_mode": state.project_mode,
            "attraction_focus": state.attraction_focus,
            "task_tree": [item.model_dump(mode="json") for item in state.task_tree],
            "counts": counts,
            "execution_priority": state.execution_priority,
            "blocked_tasks": [
                item.model_dump(mode="json")
                for item in state.task_tree
                if item.blocked_reason or item.governance_source
            ],
        }

    def get_session_detail(self, project_id: str, session_id: str) -> dict[str, object]:
        session_path = self._session_dir(project_id, session_id) / "session.json"
        session = SessionRecord.model_validate(self._read_json(session_path))
        handoff_path = self._session_dir(project_id, session_id) / "handoff.json"
        transcript_path = self._session_dir(project_id, session_id) / "transcript.jsonl"
        handoff: Optional[HandoffRecord] = None
        transcript = []
        if handoff_path.exists():
            handoff = HandoffRecord.model_validate(self._read_json(handoff_path))
        if transcript_path.exists():
            transcript = self._read_json(transcript_path)
        workflow = self.get_project_workflow(project_id)
        role_policy = "auto"
        for node in workflow["workflow_graph"]["nodes"]:
            if node["role_name"] == session.role_name:
                role_policy = node.get("handoff_policy", "auto")
                break
        why_exists = f"This session exists because {session.objective}"
        prior_handoff = None
        sessions_root = self._project_dir(project_id) / "sessions"
        if sessions_root.exists():
            for path in sorted(sessions_root.glob("*/handoff.json")):
                candidate = HandoffRecord.model_validate(self._read_json(path))
                if candidate.next_role_recommendation == session.role_name and candidate.session_id != session_id:
                    prior_handoff = candidate
        if prior_handoff:
            why_exists = f"This session exists because handoff {prior_handoff.handoff_id} recommended {session.role_name}: {prior_handoff.next_role_reason}"
        state = self.get_project_state(project_id)
        governance = self._governance_summary(state, handoff)
        blocked_now = None
        for task in state.task_tree:
            if task.blocked_reason:
                blocked_now = task.blocked_reason
                break
        materials = self._materials_summary(state)
        recommendation = self._recommendation_view(state, handoff, governance, materials, blocked_now)
        next_step = self._next_step_view(handoff, governance, recommendation) if handoff else {
            "state": recommendation["recommended_action"] == "organize_materials" and "research_gap" or "none",
            "message": recommendation["recommended_reason"] if recommendation["recommended_action"] == "organize_materials" else "No saved outcome has been written yet.",
            "actions": ["organize_materials"] if recommendation["recommended_action"] == "organize_materials" else ["start_first_step"],
            "primary_label": "Organize Materials" if recommendation["recommended_action"] == "organize_materials" else "Start First Work Step",
        }
        return {
            "project_id": project_id,
            "session": session.model_dump(mode="json"),
            "handoff": handoff.model_dump(mode="json") if handoff else None,
            "transcript": transcript,
            "role_policy": role_policy,
            "why_exists": why_exists,
            "project_stage": self._project_stage(state, handoff, governance),
            "recommendation": recommendation,
            "review_state": next_step["state"],
            "review_feedback_message": self._review_feedback_message(handoff.acceptance_status if handoff else None),
            "next_step": next_step,
        }

    def _find_session(self, session_id: str) -> SessionRecord:
        with self._connect() as conn:
            row = conn.execute("SELECT project_id FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"Unknown session: {session_id}")
        return SessionRecord.model_validate(self._read_json(self._session_dir(row[0], session_id) / "session.json"))

    def _find_handoff(self, handoff_id: str) -> HandoffRecord:
        with self._connect() as conn:
            row = conn.execute("SELECT project_id, session_id FROM handoffs WHERE handoff_id = ?", (handoff_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"Unknown handoff: {handoff_id}")
        return HandoffRecord.model_validate(self._read_json(self._session_dir(row[0], row[1]) / "handoff.json"))
