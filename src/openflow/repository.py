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
    AutoLaunchPrewire,
    BootstrapRequest,
    ChatMessageRequest,
    ChatMessageResponse,
    CapabilityRegistryEntry,
    CognitiveState,
    DecisionUpdateRequest,
    DecisionRecord,
    ExecutionCapsule,
    ExecutionResult,
    GoalModel,
    GovernancePrewire,
    HandoffRecord,
    HandoffReviewRequest,
    ImprovementRecord,
    KnowledgeItem,
    MemoryPack,
    MultiUserPrewire,
    NodeCapabilityMapEntry,
    ObservabilityEvent,
    ObservabilitySnapshot,
    ExportPrewire,
    PlanLayers,
    PlanStep,
    ProjectState,
    ResearchPackBatchIngestRequest,
    ResearchPackIngestRequest,
    RoleProfile,
    RoleInstanceSpec,
    SessionCompleteRequest,
    SessionCreateRequest,
    SessionRecord,
    SessionStatus,
    SourceType,
    TaskNode,
    TaskGraphNode,
    TaskGraphV2,
    RewriteIntent,
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

    def _system_dir(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "system"

    def _capsules_dir(self, project_id: str) -> Path:
        return self._system_dir(project_id) / "capsules"

    def _write_json(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True, default=_json_default)

    def _read_json(self, path: Path) -> object:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _read_json_if_exists(self, path: Path, default: object) -> object:
        if not path.exists():
            return default
        return self._read_json(path)

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

    def _normalize_project_mode(self, preferred_project_mode: Optional[str], profile: dict[str, bool]) -> str:
        allowed_modes = {"research", "experience", "delivery", "multimodal"}
        if preferred_project_mode in allowed_modes:
            return preferred_project_mode
        if profile["research"] and not profile["implementation"]:
            return "research"
        if profile["ui"] and not profile["multimodal"]:
            return "experience"
        if profile["multimodal"]:
            return "multimodal"
        return "delivery"

    def _profile_with_mode(self, profile: dict[str, bool], project_mode: str) -> dict[str, bool]:
        enriched = dict(profile)
        if project_mode == "research":
            enriched["research"] = True
            enriched["knowledge"] = True
        elif project_mode == "experience":
            enriched["ui"] = True
            enriched["planning"] = True
        elif project_mode == "multimodal":
            enriched["multimodal"] = True
            enriched["implementation"] = True
        else:
            enriched["implementation"] = True
            enriched["workflow"] = True
        return enriched

    def _derive_project_metadata(
        self,
        goal: str,
        initial_prompt: str,
        preferred_project_mode: Optional[str] = None,
    ) -> dict[str, object]:
        profile = self._profile_request(goal, initial_prompt)
        project_mode = self._normalize_project_mode(preferred_project_mode, profile)
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
        project_type_label = "General Work"
        collaboration_style = "guided_multi_role"
        user_facing_roles = ["Coordinator", "Executor", "Reviewer"]
        if project_mode == "research":
            project_type_label = "Research And Synthesis"
            user_facing_roles = ["Researcher", "Synthesizer", "Reviewer"]
            execution_priority = [
                "collect broad material without losing traceability",
                "separate raw notes from reusable synthesis",
                "surface the next evidence-backed decision clearly",
            ]
        elif project_mode == "experience":
            project_type_label = "Planning And Experience Design"
            user_facing_roles = ["Planner", "Designer", "Reviewer"]
            execution_priority = [
                "make the user journey understandable on first contact",
                "reduce workflow complexity before adding more controls",
                "prove the system through visible interaction, not only explanation",
            ]
        elif project_mode == "multimodal":
            project_type_label = "Multimodal Build"
            user_facing_roles = ["Planner", "Builder", "Reviewer"]
            execution_priority = [
                "connect multimodal input to planning and execution",
                "keep file-based continuity explicit at each handoff",
                "make the runnable loop easy to verify",
            ]
        elif profile["implementation"] or profile["workflow"] or project_mode == "delivery":
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

    def _derive_role_catalog(
        self,
        goal: str,
        initial_prompt: str,
        preferred_project_mode: Optional[str] = None,
    ) -> list[RoleInstanceSpec]:
        profile = self._profile_request(goal, initial_prompt)
        project_mode = self._normalize_project_mode(preferred_project_mode, profile)
        profile = self._profile_with_mode(profile, project_mode)
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

    def _decision_signal_summary(self, state: ProjectState) -> dict[str, int]:
        decision_status = {decision.decision_id: decision.status for decision in state.decisions}
        linked_items = [item for item in state.knowledge_items if item.decision_ids]
        supported = 0
        conflicted = 0
        unresolved = 0
        for item in linked_items:
            statuses = [decision_status.get(decision_id) for decision_id in item.decision_ids if decision_id in decision_status]
            if not statuses:
                unresolved += 1
                continue
            if any(status in {"rejected", "deferred"} for status in statuses):
                conflicted += 1
            elif any(status in {"accepted", "adopted"} for status in statuses):
                supported += 1
            else:
                unresolved += 1
        return {
            "linked_items": len(linked_items),
            "supported_items": supported,
            "conflicted_items": conflicted,
            "unresolved_items": unresolved,
        }

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
        decision_signals = self._decision_signal_summary(state)
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
            action = "open_details"
            confidence = "medium"
            secondary_note = "A blocked task is currently preventing a cleaner next-step recommendation."
            if blocked_task and blocked_task.governance_source == "confirm_gate_review":
                action = "continue_review"
                confidence = "high"
                secondary_note = f"This block comes from governance state: {blocked_task.governance_source}."
            return {
                "recommended_role": blocked_task.owner_role if blocked_task else (latest_handoff.next_role_recommendation if latest_handoff else state.role_catalog[0].role_name),
                "recommended_reason": blocked_now,
                "recommended_action": action,
                "recommendation_confidence": confidence,
                "recommendation_source": "blocked_task",
                "secondary_note": secondary_note,
            }
        if decision_signals["conflicted_items"] > 0:
            review_role = "Review Operator" if any(role.role_name == "Review Operator" for role in state.role_catalog) else state.role_catalog[0].role_name
            return {
                "recommended_role": review_role,
                "recommended_reason": "Some decision-linked materials are deferred or rejected, so the workspace should review the direction before continuing.",
                "recommended_action": "open_details",
                "recommendation_confidence": "high",
                "recommendation_source": "decision_conflict",
                "secondary_note": f"Conflicting decision-linked materials: {decision_signals['conflicted_items']}.",
            }
        if latest_handoff:
            confidence = "high"
            secondary_note = "This recommendation comes from the latest completed handoff."
            if decision_signals["supported_items"] > 0:
                secondary_note = f"{secondary_note} Decision-supported materials: {decision_signals['supported_items']}."
            return {
                "recommended_role": latest_handoff.next_role_recommendation,
                "recommended_reason": latest_handoff.next_role_reason,
                "recommended_action": "start",
                "recommendation_confidence": confidence,
                "recommendation_source": "latest_handoff",
                "secondary_note": secondary_note,
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
            if decision_signals["supported_items"] > 0:
                secondary_note = f"{secondary_note} Supported decision-linked materials: {decision_signals['supported_items']}."
            return {
                "recommended_role": "Research Curator",
                "recommended_reason": "This workspace is research-led and should organize materials before the next execution step.",
                "recommended_action": "organize_materials",
                "recommendation_confidence": "medium",
                "recommendation_source": "project_mode_research",
                "secondary_note": secondary_note,
            }
        mode_role_order = {
            "delivery": ["Implementation Lead", "System Architect", "Review Operator"],
            "experience": ["Experience Designer", "System Architect", "Review Operator"],
            "research": ["Research Curator", "System Architect", "Review Operator"],
            "multimodal": ["Implementation Lead", "System Architect", "Review Operator"],
        }
        allowed_order = mode_role_order.get(state.project_mode, ["Implementation Lead", "System Architect", "Review Operator"])
        preferred_roles = [role_name for role_name in allowed_order if any(role.role_name == role_name for role in state.role_catalog)]
        first_role = preferred_roles[0] if preferred_roles else (state.role_catalog[0].role_name if state.role_catalog else "Implementation Lead")
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
        if recommendation["recommended_action"] == "continue_review":
            return {
                "state": "review_needed",
                "message": "This next step needs a review before it can start.",
                "actions": ["continue", "needs_changes", "replan"],
                "primary_label": "Continue",
            }
        if recommendation["recommended_action"] == "open_details":
            return {
                "state": "blocked",
                "message": "This workspace should resolve the current block before starting the next step.",
                "actions": ["open_details"],
                "primary_label": "Open Details",
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

    def _default_files_for_role(self, project_id: str, role_name: str, project_mode: str) -> list[str]:
        if role_name == "Research Curator":
            return [
                f"projects/{project_id}/project.json",
                f"projects/{project_id}/knowledge/knowledge_items.json",
            ]
        if role_name == "Experience Designer":
            return [
                f"projects/{project_id}/project.json",
                f"projects/{project_id}/workflow_graph.json",
            ]
        if role_name == "System Architect":
            return [
                f"projects/{project_id}/workflow_graph.json",
                f"projects/{project_id}/task_tree.json",
            ]
        if role_name == "Review Operator":
            return [
                f"projects/{project_id}/task_tree.json",
                f"projects/{project_id}/decisions.json",
            ]
        if project_mode == "multimodal":
            return [
                f"projects/{project_id}/project.json",
                f"projects/{project_id}/workflow_graph.json",
            ]
        return [f"projects/{project_id}/workflow_graph.json"]

    def _default_expected_output(self, role_name: str, recommended_action: str, project_mode: str) -> str:
        if recommended_action == "continue_review":
            return "A review outcome that either approves, requests changes, or sends the work back to replanning."
        if recommended_action == "organize_materials":
            return "An organized material set with reusable summaries, linked decisions, and clear next-step evidence."
        if recommended_action == "replan":
            return "A revised role and task direction that explains how the project should continue."
        if role_name == "Experience Designer":
            return "A clearer user journey package with adjusted flow, proof points, and reduced friction."
        if role_name == "Research Curator":
            return "A synthesized research package that later roles can reuse without rereading raw material."
        if role_name == "System Architect":
            return "A stable execution package with explicit boundaries, file contracts, and confirmation points."
        if project_mode == "multimodal":
            return "A runnable multimodal work package that connects input, planning, and next execution."
        return "A structured handoff package that the next fresh session can execute from files only."

    def _default_success_criteria(
        self,
        state: ProjectState,
        role_name: str,
        recommended_action: str,
        next_step: dict[str, object],
    ) -> list[str]:
        matching_tasks = [task for task in state.task_tree if task.owner_role == role_name and task.success_criteria]
        if matching_tasks:
            return list(matching_tasks[0].success_criteria)
        if recommended_action == "continue_review":
            return [
                "Record an explicit review outcome.",
                "Explain whether the next step can advance safely.",
            ]
        if recommended_action == "organize_materials":
            return [
                "Raw material is separated from reusable synthesis.",
                "The next role can see which files to read first.",
            ]
        if next_step["state"] == "blocked":
            return [
                "Resolve the blocking condition.",
                "Return the workspace to a ready or reviewable state.",
            ]
        return ["Leave a structured result that the next fresh session can continue from."]

    def _blocking_items_view(
        self,
        governance: dict[str, object],
        blocked_now: Optional[str],
        decision_signals: dict[str, int],
        latest_handoff: Optional[HandoffRecord],
    ) -> list[str]:
        items: list[str] = []
        if governance.get("confirm_waiting"):
            items.append("A confirm-gated review is still waiting for an explicit outcome.")
        if latest_handoff and latest_handoff.acceptance_status == "changes_requested":
            items.append("The latest review requested changes before the project can advance.")
        if latest_handoff and latest_handoff.acceptance_status == "replan_required":
            items.append("The latest review required replanning before execution can continue.")
        if blocked_now:
            items.append(blocked_now)
        if decision_signals["conflicted_items"] > 0:
            items.append(f"{decision_signals['conflicted_items']} decision-linked material sets are in conflict.")
        return items

    def _work_package_view(
        self,
        state: ProjectState,
        latest_handoff: Optional[HandoffRecord],
        governance: dict[str, object],
        materials: dict[str, object],
        blocked_now: Optional[str],
        recommendation: dict[str, object],
        next_step: dict[str, object],
    ) -> dict[str, object]:
        decision_signals = self._decision_signal_summary(state)
        recommended_role = str(recommendation["recommended_role"])
        recommended_action = str(recommendation["recommended_action"])
        recommended_files = list(latest_handoff.required_input_files) if latest_handoff and latest_handoff.required_input_files else []
        if not recommended_files:
            recommended_files = self._default_files_for_role(state.project_id, recommended_role, state.project_mode)
        risks = list(latest_handoff.risks) if latest_handoff and latest_handoff.risks else []
        if not risks and blocked_now:
            risks = [blocked_now]
        if not risks and decision_signals["conflicted_items"] > 0:
            risks = ["Decision-linked materials conflict with the current direction."]
        if not risks and governance.get("confirm_waiting"):
            risks = ["A review outcome is still required before the next step can start."]
        success_criteria = list(latest_handoff.success_criteria) if latest_handoff and latest_handoff.success_criteria else []
        if not success_criteria:
            success_criteria = self._default_success_criteria(state, recommended_role, recommended_action, next_step)
        blocking_items = self._blocking_items_view(governance, blocked_now, decision_signals, latest_handoff)
        auto_advance_blockers = list(blocking_items)
        if not latest_handoff and recommended_action == "start_first_step":
            auto_advance_blockers.append("The project still needs a human-started first work step before automatic continuation can exist.")
        if next_step["state"] in {"blocked", "review_needed", "changes_requested", "replan_required"} and not auto_advance_blockers:
            auto_advance_blockers.append(next_step["message"])
        if recommended_action in {"open_details", "continue_review", "replan", "needs_changes"} and not auto_advance_blockers:
            auto_advance_blockers.append("The current recommendation still requires human review or intervention.")
        ready_for_auto_advance = not auto_advance_blockers and next_step["state"] == "ready"
        return {
            "recommended_role": recommended_role,
            "recommended_action": recommended_action,
            "recommended_reason": recommendation["recommended_reason"],
            "recommended_files": recommended_files,
            "expected_output": self._default_expected_output(recommended_role, recommended_action, state.project_mode),
            "success_criteria": success_criteria,
            "risks": risks,
            "blocking_items": blocking_items,
            "confidence": recommendation["recommendation_confidence"],
            "recommendation_source": recommendation["recommendation_source"],
            "secondary_note": recommendation.get("secondary_note"),
            "project_mode": state.project_mode,
            "next_step_state": next_step["state"],
            "ready_for_auto_advance": ready_for_auto_advance,
            "auto_advance_blockers": auto_advance_blockers,
            "suggested_session_objective": recommendation["recommended_reason"],
            "human_action_required": not ready_for_auto_advance,
            "materials_snapshot": {
                "organized_material_count": materials["organized_material_count"],
                "raw_source_count": materials["raw_source_count"],
                "synthesized_count": materials["synthesized_count"],
                "linked_count": materials["linked_count"],
            },
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

    def _goal_model_file(self, project_id: str) -> Path:
        return self._system_dir(project_id) / "goal_model.json"

    def _cognitive_state_file(self, project_id: str) -> Path:
        return self._system_dir(project_id) / "cognitive_state.json"

    def _workflow_graph_v2_file(self, project_id: str) -> Path:
        return self._system_dir(project_id) / "workflow_graph_v2.json"

    def _plan_layers_file(self, project_id: str) -> Path:
        return self._system_dir(project_id) / "plan_layers.json"

    def _task_graph_v2_file(self, project_id: str) -> Path:
        return self._system_dir(project_id) / "task_graph_v2.json"

    def _role_profiles_file(self, project_id: str) -> Path:
        return self._system_dir(project_id) / "role_profiles.json"

    def _capability_registry_file(self, project_id: str) -> Path:
        return self._system_dir(project_id) / "capability_registry.json"

    def _node_capability_map_file(self, project_id: str) -> Path:
        return self._system_dir(project_id) / "node_capability_map.json"

    def _memory_index_file(self, project_id: str) -> Path:
        return self._system_dir(project_id) / "memory" / "memory_index.json"

    def _observability_file(self, project_id: str) -> Path:
        return self._system_dir(project_id) / "observability.json"

    def _improvement_log_file(self, project_id: str) -> Path:
        return self._system_dir(project_id) / "improvement_log.json"

    def _prewire_file(self, project_id: str) -> Path:
        return self._system_dir(project_id) / "prewire_schemas.json"

    def _memory_ref(self, project_id: str, name: str) -> str:
        return str(self._system_dir(project_id).joinpath("memory", name).relative_to(self.data_dir)).replace("\\", "/")

    def _derive_goal_model(self, project_id: str, project_meta: dict[str, object]) -> GoalModel:
        goal = str(project_meta["goal"])
        initial_prompt = str(project_meta.get("initial_prompt", ""))
        constraints = []
        if "deadline" in initial_prompt.lower():
            constraints.append("A delivery or review deadline is implied by the request.")
        if str(project_meta.get("project_mode")) == "research":
            constraints.append("Preserve traceability from raw material to synthesized insight.")
        return GoalModel(
            project_id=project_id,
            core_goal=goal,
            explicit_constraints=constraints,
            implicit_constraints=[
                "Continuity must survive fresh sessions.",
                "Project state must remain recoverable from files.",
            ],
            anti_goals=[
                "Do not depend on hidden runtime chat context.",
                "Do not lose the reason for the next step.",
            ],
            success_criteria=[
                "The next role can continue from files only.",
                "Progress, decisions, and evidence remain inspectable.",
            ],
            milestone_signals=[
                "A stable role and task graph exists.",
                "A handoff or work package can be generated from current files.",
            ],
            risk_tolerance="medium",
            priority_policy=[
                "protect continuity",
                "make the next step explicit",
                "preserve evidence before speed",
            ],
        )

    def _derive_cognitive_state(
        self,
        state: ProjectState,
        project_meta: dict[str, object],
        governance: dict[str, object],
        materials: dict[str, object],
        blocked_now: Optional[str],
        latest_handoff: Optional[HandoffRecord],
    ) -> CognitiveState:
        validated_facts = [
            f"Project mode is {state.project_mode}.",
            f"{len(state.role_catalog)} roles are currently defined.",
            f"{len(state.task_tree)} task nodes are tracked.",
            f"{materials['organized_material_count']} organized material sets exist.",
        ]
        assumptions = []
        if not latest_handoff:
            assumptions.append("The first executable work package still needs to be started by a human.")
        if materials["raw_source_count"] >= materials["synthesized_count"]:
            assumptions.append("More source consolidation may be needed before later execution.")
        open_questions = []
        if not materials["organized_material_count"]:
            open_questions.append("Which materials should be organized first?")
        conflicts = []
        if blocked_now:
            conflicts.append(blocked_now)
        if governance.get("confirm_waiting"):
            conflicts.append("A confirm-gated review is still unresolved.")
        current_gaps = [
            "Need the next work package to stay aligned with durable memory.",
        ]
        if state.project_mode == "research":
            current_gaps.append("Need stronger synthesis than raw material volume.")
        return CognitiveState(
            project_id=state.project_id,
            validated_facts=validated_facts,
            inferred_facts=[
                f"The next active role is likely {state.user_facing_roles[0]}." if state.user_facing_roles else "The next active role must be inferred from the role catalog."
            ],
            active_assumptions=assumptions,
            open_questions=open_questions,
            conflicts=conflicts,
            current_gaps=current_gaps,
            evidence_refs=[
                f"projects/{state.project_id}/project.json",
                f"projects/{state.project_id}/task_tree.json",
                f"projects/{state.project_id}/knowledge/knowledge_items.json",
            ],
            focus_now=governance.get("why_current_state", project_meta["goal"]),
        )

    def _derive_plan_layers(self, state: ProjectState) -> PlanLayers:
        strategic = [
            PlanStep(
                step_id="strategic-continuity",
                title="Preserve continuity through files",
                objective="Keep progress readable across fresh sessions.",
                inputs=["project.json", "workflow_graph.json", "knowledge/knowledge_items.json"],
                outputs=["goal_model", "memory packs", "recommended work package"],
                completion_signals=["A fresh role can continue from files only."],
            )
        ]
        phases = [
            PlanStep(
                step_id=f"phase-{index + 1}",
                title=task.title,
                objective=task.title,
                inputs=task.depends_on,
                outputs=[task.task_id],
                risks=[task.blocked_reason] if task.blocked_reason else [],
                completion_signals=task.success_criteria,
            )
            for index, task in enumerate(state.task_tree)
        ]
        milestones = [
            PlanStep(
                step_id=f"milestone-{task.task_id}",
                title=f"{task.owner_role} milestone",
                objective=task.title,
                outputs=[f"session:{task.owner_role}", f"handoff:{task.task_id}"],
                completion_signals=task.success_criteria,
            )
            for task in state.task_tree
        ]
        node_plan = [
            PlanStep(
                step_id=f"node-{task.task_id}",
                title=task.title,
                objective=f"Complete node {task.task_id} with role {task.owner_role}.",
                inputs=task.depends_on,
                outputs=[f"task:{task.task_id}"],
                risks=[task.blocked_reason] if task.blocked_reason else [],
                completion_signals=task.success_criteria,
            )
            for task in state.task_tree
        ]
        phase_status = [f"{task.task_id}:{task.status.value}" for task in state.task_tree]
        return PlanLayers(
            project_id=state.project_id,
            strategic=strategic,
            phases=phases,
            milestones=milestones,
            node_plan=node_plan,
            phase_status=phase_status,
            last_rewritten_by="system_refresh",
        )

    def _derive_task_graph_v2(self, state: ProjectState) -> TaskGraphV2:
        nodes = [
            TaskGraphNode(
                node_id=f"node-{task.task_id}",
                task_id=task.task_id,
                title=task.title,
                phase=state.project_mode,
                node_type="review" if task.owner_role == "Review Operator" else ("research" if task.owner_role == "Research Curator" else "execution"),
                intent=task.title,
                owner_role=task.owner_role,
                dependency_nodes=[f"node-{item}" for item in task.depends_on],
                blocking_conditions=[task.blocked_reason] if task.blocked_reason else [],
                completion_conditions=task.success_criteria,
                rollback_conditions=["replan_required", "changes_requested"] if task.owner_role != "Bootstrap Strategist" else [],
                parallelizable=len(task.depends_on) == 0 and task.owner_role not in {"Review Operator", "System Architect"},
                needs_human_confirm=task.owner_role in {"System Architect", "Review Operator"},
                needs_material_refresh=task.owner_role == "Research Curator",
                status=task.status.value,
            )
            for task in state.task_tree
        ]
        edges = []
        for node in nodes:
            for dependency in node.dependency_nodes:
                edges.append(WorkflowEdge(from_node=dependency, to_node=node.node_id, condition="dependency"))
        replan_sources = [node.node_id for node in nodes if "replan_required" in node.rollback_conditions]
        return TaskGraphV2(project_id=state.project_id, nodes=nodes, edges=edges, replan_sources=replan_sources)

    def _derive_role_profiles(
        self,
        role_catalog: list[RoleInstanceSpec],
        dynamic_overrides: Optional[dict[str, RoleProfile]] = None,
    ) -> list[RoleProfile]:
        profiles = []
        overrides = dynamic_overrides or {}
        for role in role_catalog:
            if role.role_name in overrides:
                profiles.append(overrides[role.role_name])
                continue
            mindset = "Rational and traceable execution from files."
            if "Research" in role.role_name:
                mindset = "Separate raw material from reusable knowledge."
            elif "Review" in role.role_name:
                mindset = "Challenge weak assumptions and protect downstream quality."
            profiles.append(
                RoleProfile(
                    role_name=role.role_name,
                    mission=role.objective,
                    mindset=mindset,
                    authority_scope=["read_files", "produce_handoff", "update_memory"],
                    output_contract=role.output_contract,
                    focus_points=role.preferred_workflow,
                    guardrails=role.tools_guidance,
                    preferred_tools=["files", "handoff", "knowledge", "timeline"],
                )
            )
        return profiles

    def _dynamic_role_overrides(
        self,
        state: ProjectState,
        governance: dict[str, object],
        materials: dict[str, object],
        blocked_now: Optional[str],
    ) -> dict[str, RoleProfile]:
        overrides: dict[str, RoleProfile] = {}
        if blocked_now or governance.get("confirm_waiting"):
            overrides["Review Operator"] = RoleProfile(
                role_name="Review Operator",
                mission="Resolve the active blocker before downstream execution continues.",
                mindset="Act as a risk governor and contradiction resolver.",
                profile_source="dynamic",
                dynamic_profile=True,
                authority_scope=["read_files", "review_handoff", "request_replan", "approve_next_step"],
                output_contract=["review outcome", "block resolution note", "updated next-step path"],
                focus_points=["inspect blocker", "check governance state", "preserve downstream safety"],
                guardrails=["Do not advance execution without an explicit review outcome."],
                preferred_tools=["handoff", "timeline", "decision_registry", "task_graph"],
            )
        if materials["raw_source_count"] >= materials["synthesized_count"]:
            overrides["Research Curator"] = RoleProfile(
                role_name="Research Curator",
                mission="Collapse excess raw material into reusable synthesized memory for later fresh sessions.",
                mindset="Reduce cognitive load without losing traceability.",
                profile_source="dynamic",
                dynamic_profile=True,
                authority_scope=["read_files", "organize_materials", "update_memory"],
                output_contract=["synthesized material pack", "evidence map", "decision support summary"],
                focus_points=["find reusable signals", "reduce raw-material dominance", "prepare downstream files"],
                guardrails=["Keep raw and synthesized layers explicitly separate."],
                preferred_tools=["knowledge_index", "material_groups", "memory_pack"],
            )
        if state.project_mode == "multimodal":
            overrides["System Architect"] = RoleProfile(
                role_name="System Architect",
                mission="Stabilize multimodal execution boundaries before delivery expands.",
                mindset="Favor clear interface seams over speed.",
                profile_source="dynamic",
                dynamic_profile=True,
                authority_scope=["read_files", "set_contracts", "define_capsule"],
                output_contract=["execution contract", "file contract", "verification boundary"],
                focus_points=["input/output seams", "planning-to-execution bridge", "launch readiness"],
                guardrails=["Do not leave multimodal paths ambiguous."],
                preferred_tools=["workflow_graph", "task_graph", "session_factory"],
            )
        return overrides

    def _derive_capability_registry(self, state: ProjectState) -> list[CapabilityRegistryEntry]:
        registry = [
            CapabilityRegistryEntry(
                entry_id="agent-bootstrap-strategist",
                entry_type="agent",
                name="Bootstrap Strategist",
                purpose="Turn a request into a structured workflow and execution model.",
                template_type="dynamic_ready",
                applies_to=["bootstrap", "replan"],
                activation_rules=["Use when the project needs reframing or replanning."],
            ),
            CapabilityRegistryEntry(
                entry_id="mcp-file-memory",
                entry_type="mcp",
                name="File Memory Reader",
                purpose="Read durable project files instead of hidden session context.",
                template_type="core",
                applies_to=["all"],
                activation_rules=["Always available for fresh-session continuity."],
            ),
            CapabilityRegistryEntry(
                entry_id="mcp-project-state",
                entry_type="mcp",
                name="Project State Reader",
                purpose="Inspect current project state, task status, and workflow position.",
                template_type="core",
                applies_to=["all"],
                activation_rules=["Use before deciding the next node or verifying readiness."],
            ),
            CapabilityRegistryEntry(
                entry_id="skill-structured-summarization",
                entry_type="skill",
                name="Structured Summarization",
                purpose="Compress execution history into reusable memory packs.",
                template_type="core",
                applies_to=["all"],
                activation_rules=["Use after each node execution and review."],
            ),
            CapabilityRegistryEntry(
                entry_id="skill-progress-logging",
                entry_type="skill",
                name="Progress Logging",
                purpose="Record node inputs, outputs, progress, and failure reasons.",
                template_type="core",
                applies_to=["all"],
                activation_rules=["Use during every node execution."],
            ),
            CapabilityRegistryEntry(
                entry_id="tool-session-factory",
                entry_type="tool",
                name="Session Factory",
                purpose="Assemble launch-ready session configuration from capability mapping and memory packs.",
                template_type="prewire",
                applies_to=["all"],
                activation_rules=["Use when preparing a new fresh session."],
            ),
            CapabilityRegistryEntry(
                entry_id="prompt-node-execution",
                entry_type="prompt_template",
                name="Node Execution Template",
                purpose="Base prompt structure for executing a mapped node from files.",
                template_type="default",
                applies_to=["all"],
                activation_rules=["Used unless a dynamic prompt override exists."],
            ),
            CapabilityRegistryEntry(
                entry_id="verifier-launch-readiness",
                entry_type="verifier",
                name="Launch Readiness Verifier",
                purpose="Check whether a node has enough files, memory, and approvals to launch.",
                template_type="default",
                applies_to=["all"],
                activation_rules=["Run before session factory emits a launch-ready configuration."],
            ),
            CapabilityRegistryEntry(
                entry_id="summarizer-memory-pack",
                entry_type="summarizer",
                name="Memory Pack Summarizer",
                purpose="Generate summary, structured, semantic, and operational memory layers.",
                template_type="default",
                applies_to=["all"],
                activation_rules=["Use after each session completion and significant review action."],
            ),
        ]
        for role in state.role_catalog:
            registry.append(
                CapabilityRegistryEntry(
                    entry_id=f"agent-{self._slug(role.role_name)}",
                    entry_type="agent",
                    name=role.role_name,
                    purpose=role.objective,
                    template_type="role_default",
                    applies_to=[state.project_mode, role.role_name],
                    activation_rules=[f"Use when {role.role_name} owns the current node."],
                )
            )
        return registry

    def _node_prompt_template(self, role_name: str, node_title: str) -> str:
        return (
            f"You are {role_name}. Read the mapped files first, stay inside the declared output contract, "
            f"and complete the node objective: {node_title}. Preserve continuity through files, not hidden chat context."
        )

    def _derive_node_capability_map(
        self,
        state: ProjectState,
        task_graph: TaskGraphV2,
        role_profiles: list[RoleProfile],
        governance: dict[str, object],
        materials: dict[str, object],
        blocked_now: Optional[str],
        recommended_work_package: Optional[dict[str, object]] = None,
    ) -> list[NodeCapabilityMapEntry]:
        dynamic_overrides = self._dynamic_role_overrides(state, governance, materials, blocked_now)
        entries = []
        for node in task_graph.nodes:
            required_files = self._default_files_for_role(state.project_id, node.owner_role, state.project_mode)
            if recommended_work_package and recommended_work_package.get("recommended_role") == node.owner_role:
                recommended_files = list(recommended_work_package.get("recommended_files", []))
                if recommended_files:
                    required_files = recommended_files
            mcp_set = ["File Memory Reader", "Project State Reader"]
            skill_set = ["Structured Summarization", "Progress Logging"]
            resolution_source = "registry"
            if node.owner_role == "Research Curator":
                skill_set.append("Research Consolidation")
            if node.owner_role == "Review Operator":
                skill_set.append("Review And Risk Check")
            if node.owner_role in dynamic_overrides:
                resolution_source = node.owner_role in {"Review Operator", "Research Curator"} and "hybrid" or "dynamic"
                skill_set.extend(["Dynamic Role Override"])
            role_profile = next((item for item in role_profiles if item.role_name == node.owner_role), None)
            if role_profile and role_profile.dynamic_profile and resolution_source == "registry":
                resolution_source = "dynamic"
            fallback_roles = ["Review Operator"] if node.owner_role != "Review Operator" else ["Bootstrap Strategist"]
            entries.append(
                NodeCapabilityMapEntry(
                    node_id=node.node_id,
                    role_name=node.owner_role,
                    agent_profile=node.owner_role,
                    mcp_set=mcp_set,
                    skill_set=skill_set,
                    tool_set=["project_files", "knowledge_index", "timeline"],
                    prompt_template=self._node_prompt_template(node.owner_role, node.title),
                    required_files=required_files,
                    output_files=[
                        f"projects/{state.project_id}/sessions/{{session_id}}/handoff.json",
                        f"projects/{state.project_id}/system/memory/operational_memory.json",
                    ],
                    verification_policy=["Leave a structured result.", "Preserve the next-step reason."],
                    observability_policy=["log_capabilities", "log_inputs", "log_outputs", "log_progress"],
                    resolution_source=resolution_source,
                    precedence=10 if resolution_source in {"dynamic", "hybrid"} else 100,
                    fallback_roles=fallback_roles,
                    dynamic_override=resolution_source in {"dynamic", "hybrid"},
                    session_factory_policy=["require_memory_pack", "require_required_files", "check_governance_state"],
                )
            )
        return entries

    def _derive_memory_packs(
        self,
        state: ProjectState,
        project_meta: dict[str, object],
        latest_handoff: Optional[HandoffRecord],
        materials: dict[str, object],
        recommendation: dict[str, object],
    ) -> list[MemoryPack]:
        raw_refs = [f"projects/{state.project_id}/project.json"]
        if latest_handoff:
            raw_refs.append(f"projects/{state.project_id}/sessions/{latest_handoff.session_id}/handoff.json")
        return [
            MemoryPack(
                pack_id="raw-memory",
                layer="raw",
                title="Raw project memory",
                summary="Direct references to raw project artifacts and recent handoff/session files.",
                refs=raw_refs,
                keywords=["raw", "artifacts", "session_files"],
                payload={
                    "artifact_refs": raw_refs,
                    "latest_handoff_id": latest_handoff.handoff_id if latest_handoff else None,
                },
            ),
            MemoryPack(
                pack_id="summary-memory",
                layer="summary",
                title="Project summary memory",
                summary=str(project_meta["goal"]),
                refs=raw_refs,
                keywords=[state.project_mode, "project_goal", "next_step"],
                payload={
                    "project_mode": state.project_mode,
                    "latest_recommended_role": recommendation["recommended_role"],
                },
            ),
            MemoryPack(
                pack_id="structured-memory",
                layer="structured",
                title="Structured execution memory",
                summary=(
                    f"Roles: {', '.join(state.user_facing_roles)}. "
                    f"Organized materials: {materials['organized_material_count']}. "
                    f"Recommendation: {recommendation['recommended_role']}."
                ),
                refs=[
                    f"projects/{state.project_id}/task_tree.json",
                    f"projects/{state.project_id}/knowledge/knowledge_items.json",
                    f"projects/{state.project_id}/decisions.json",
                ],
                keywords=["roles", "materials", "decisions", "recommendation"],
                payload={
                    "roles": state.user_facing_roles,
                    "materials": materials,
                    "recommendation": {
                        "role": recommendation["recommended_role"],
                        "action": recommendation["recommended_action"],
                    },
                },
            ),
            MemoryPack(
                pack_id="semantic-memory",
                layer="semantic",
                title="Semantic memory pack",
                summary="Topic and relationship summary for the current project state.",
                refs=[
                    f"projects/{state.project_id}/knowledge/knowledge_items.json",
                    f"projects/{state.project_id}/system/task_graph_v2.json",
                ],
                keywords=[
                    state.project_mode,
                    "continuity",
                    "handoff",
                    str(recommendation["recommended_role"]),
                    str(recommendation["recommended_action"]),
                ],
                payload={
                    "themes": [state.project_mode, "workflow_continuity", "next_step_reasoning"],
                    "entities": state.user_facing_roles,
                    "relations": [
                        {"from": "materials", "to": recommendation["recommended_role"], "type": "influences"},
                        {"from": "workflow", "to": recommendation["recommended_action"], "type": "suggests"},
                    ],
                },
            ),
            MemoryPack(
                pack_id="operational-memory",
                layer="operational",
                title="Operational memory pack",
                summary=f"Next focus: {recommendation['recommended_reason']}",
                refs=self._default_files_for_role(state.project_id, str(recommendation["recommended_role"]), state.project_mode),
                keywords=[str(recommendation["recommended_role"]), str(recommendation["recommended_action"]), "next_focus"],
                payload={
                    "next_role": recommendation["recommended_role"],
                    "next_action": recommendation["recommended_action"],
                    "must_read_first": self._default_files_for_role(state.project_id, str(recommendation["recommended_role"]), state.project_mode),
                },
            ),
        ]

    def _session_factory_preview(
        self,
        state: ProjectState,
        node: TaskGraphNode,
        mapped: NodeCapabilityMapEntry,
        memory_packs: list[MemoryPack],
        latest_handoff: Optional[HandoffRecord],
    ) -> dict[str, object]:
        missing_dependencies: list[str] = []
        if node.needs_human_confirm:
            missing_dependencies.append("This node still requires human confirmation before launch.")
        if not mapped.required_files:
            missing_dependencies.append("No required input files were resolved for this node.")
        if mapped.memory_read_policy and not memory_packs:
            missing_dependencies.append("No memory packs are available for this node.")
        if node.owner_role == "Review Operator" and latest_handoff is None:
            missing_dependencies.append("Review cannot launch because no handoff exists yet.")
        launch_readiness = len(missing_dependencies) == 0
        return {
            "node_id": node.node_id,
            "launch_readiness": launch_readiness,
            "missing_dependencies": missing_dependencies,
            "required_files": mapped.required_files,
            "memory_pack_refs": [f"projects/{state.project_id}/system/memory/{item.pack_id}.json" for item in memory_packs],
            "session_config_payload": {
                "role_name": node.owner_role,
                "objective": node.intent,
                "agent_profile": mapped.agent_profile,
                "mcp_set": mapped.mcp_set,
                "skill_set": mapped.skill_set,
                "tool_set": mapped.tool_set,
                "prompt_template": mapped.prompt_template,
                "memory_read_policy": mapped.memory_read_policy,
                "memory_write_policy": mapped.memory_write_policy,
                "verification_policy": mapped.verification_policy,
            },
        }

    def _derive_execution_capsules(
        self,
        state: ProjectState,
        task_graph: TaskGraphV2,
        capability_map: list[NodeCapabilityMapEntry],
        memory_packs: list[MemoryPack],
        latest_handoff: Optional[HandoffRecord],
    ) -> list[ExecutionCapsule]:
        memory_refs = [self._memory_ref(state.project_id, "memory_index.json")] + [f"projects/{state.project_id}/system/memory/{item.pack_id}.json" for item in memory_packs]
        capsules = []
        for node in task_graph.nodes:
            mapped = next(item for item in capability_map if item.node_id == node.node_id)
            preview = self._session_factory_preview(state, node, mapped, memory_packs, latest_handoff)
            capsules.append(
                ExecutionCapsule(
                    project_id=state.project_id,
                    node_id=node.node_id,
                    role_name=node.owner_role,
                    session_intent=node.intent,
                    agent_profile=mapped.agent_profile,
                    mcp_set=mapped.mcp_set,
                    skill_set=mapped.skill_set,
                    tool_set=mapped.tool_set,
                    prompt_template=mapped.prompt_template,
                    required_files=mapped.required_files,
                    output_files=mapped.output_files,
                    memory_pack_refs=memory_refs,
                    verification_policy=mapped.verification_policy,
                    observability_policy=mapped.observability_policy,
                    session_config_payload=preview["session_config_payload"],
                    launch_readiness=preview["launch_readiness"],
                    missing_dependencies=preview["missing_dependencies"],
                    audit_requirements=["record_capabilities", "record_memory_refs", "record_output_files"],
                    source_resolution=mapped.resolution_source,
                )
            )
        return capsules

    def _derive_observability_snapshot(
        self,
        state: ProjectState,
        task_graph: TaskGraphV2,
        latest_handoff: Optional[HandoffRecord],
        recommendation: dict[str, object],
        governance: dict[str, object],
    ) -> ObservabilitySnapshot:
        completed = len([task for task in state.task_tree if task.status == SessionStatus.completed])
        progress_percent = int((completed / len(state.task_tree)) * 100) if state.task_tree else 0
        current_node_id = next((node.node_id for node in task_graph.nodes if node.owner_role == recommendation["recommended_role"]), None)
        events = [
            ObservabilityEvent(
                event_id=f"obs-{state.project_id}-bootstrap",
                event_type="project_state",
                title="Project state loaded",
                detail=f"Project is in mode {state.project_mode} with {len(state.task_tree)} task nodes.",
                refs=[f"projects/{state.project_id}/project.json"],
            ),
            ObservabilityEvent(
                event_id=f"obs-{state.project_id}-recommendation",
                event_type="recommendation",
                title="Next work package prepared",
                detail=str(recommendation["recommended_reason"]),
                refs=[f"projects/{state.project_id}/task_tree.json"],
            ),
        ]
        if latest_handoff:
            events.insert(
                0,
                ObservabilityEvent(
                    event_id=f"obs-{latest_handoff.handoff_id}",
                    event_type="handoff",
                    title="Latest handoff available",
                    detail=latest_handoff.session_summary,
                    refs=[f"projects/{state.project_id}/sessions/{latest_handoff.session_id}/handoff.json"],
                ),
            )
        return ObservabilitySnapshot(
            project_id=state.project_id,
            current_phase=state.project_mode,
            current_node_id=current_node_id,
            current_role=str(recommendation["recommended_role"]),
            progress_percent=progress_percent,
            recent_events=events[:5],
            current_status=governance.get("latest_review", "active"),
        )

    def _derive_improvement_record(
        self,
        state: ProjectState,
        recommendation: dict[str, object],
        next_step: dict[str, object],
        blocked_now: Optional[str],
    ) -> ImprovementRecord:
        plan_updates = [f"Keep the next focus on {recommendation['recommended_role']}."]
        mapping_updates = ["Refresh node-to-capability mappings after every state change."]
        next_focus = [str(recommendation["recommended_reason"])]
        summary = "Continue from current project state without losing file-based continuity."
        rewrite_intents = [
            RewriteIntent(
                target_type="node_capability_map",
                target_id=str(recommendation["recommended_role"]),
                action="refresh_priority",
                reason="Keep the capability map aligned with the current recommended role.",
                risk_level="low",
                auto_applied=True,
            )
        ]
        if blocked_now:
            summary = f"Resolve the current block before expanding execution: {blocked_now}"
            plan_updates.append("Address the explicit block before creating downstream work.")
            rewrite_intents.append(
                RewriteIntent(
                    target_type="plan_layers",
                    target_id="phase-status",
                    action="reprioritize_block_resolution",
                    reason=blocked_now,
                    risk_level="medium",
                    auto_applied=False,
                )
            )
        if next_step["state"] == "review_needed":
            summary = "Review feedback must be resolved before the next execution step."
            mapping_updates.append("Keep review-oriented capabilities at the top of the next node capsule.")
            rewrite_intents.append(
                RewriteIntent(
                    target_type="role_profile",
                    target_id="Review Operator",
                    action="elevate_review_authority",
                    reason="Review has become the gating condition for the next step.",
                    risk_level="low",
                    auto_applied=True,
                )
            )
        return ImprovementRecord(
            improvement_id=f"improvement-{uuid4().hex[:8]}",
            summary=summary,
            plan_updates=plan_updates,
            mapping_updates=mapping_updates,
            next_focus=next_focus,
            rewrite_intents=rewrite_intents,
        )

    def _derive_prewire_schemas(self) -> dict[str, object]:
        return {
            "multi_user": MultiUserPrewire().model_dump(mode="json"),
            "export": ExportPrewire().model_dump(mode="json"),
            "governance": GovernancePrewire().model_dump(mode="json"),
            "auto_launch": AutoLaunchPrewire().model_dump(mode="json"),
        }

    def _write_system_state(
        self,
        state: ProjectState,
        project_meta: dict[str, object],
        latest_handoff: Optional[HandoffRecord],
        recommendation: dict[str, object],
        next_step: dict[str, object],
        materials: dict[str, object],
        governance: dict[str, object],
        blocked_now: Optional[str],
    ) -> None:
        goal_model = self._derive_goal_model(state.project_id, project_meta)
        cognitive_state = self._derive_cognitive_state(state, project_meta, governance, materials, blocked_now, latest_handoff)
        plan_layers = self._derive_plan_layers(state)
        task_graph = self._derive_task_graph_v2(state)
        dynamic_overrides = self._dynamic_role_overrides(state, governance, materials, blocked_now)
        role_profiles = self._derive_role_profiles(state.role_catalog, dynamic_overrides)
        capability_registry = self._derive_capability_registry(state)
        capability_map = self._derive_node_capability_map(
            state,
            task_graph,
            role_profiles,
            governance,
            materials,
            blocked_now,
            {"recommended_role": recommendation["recommended_role"], "recommended_files": self._default_files_for_role(state.project_id, str(recommendation["recommended_role"]), state.project_mode)},
        )
        memory_packs = self._derive_memory_packs(state, project_meta, latest_handoff, materials, recommendation)
        observability = self._derive_observability_snapshot(state, task_graph, latest_handoff, recommendation, governance)
        improvement_record = self._derive_improvement_record(state, recommendation, next_step, blocked_now)
        capsules = self._derive_execution_capsules(state, task_graph, capability_map, memory_packs, latest_handoff)
        prewire_schemas = self._derive_prewire_schemas()

        self._write_json(self._goal_model_file(state.project_id), goal_model.model_dump(mode="json"))
        self._write_json(self._cognitive_state_file(state.project_id), cognitive_state.model_dump(mode="json"))
        self._write_json(self._workflow_graph_v2_file(state.project_id), state.workflow_graph.model_dump(mode="json"))
        self._write_json(self._plan_layers_file(state.project_id), plan_layers.model_dump(mode="json"))
        self._write_json(self._task_graph_v2_file(state.project_id), task_graph.model_dump(mode="json"))
        self._write_json(self._role_profiles_file(state.project_id), [item.model_dump(mode="json") for item in role_profiles])
        self._write_json(self._capability_registry_file(state.project_id), [item.model_dump(mode="json") for item in capability_registry])
        self._write_json(self._node_capability_map_file(state.project_id), [item.model_dump(mode="json") for item in capability_map])
        self._write_json(self._memory_index_file(state.project_id), [item.model_dump(mode="json") for item in memory_packs])
        for item in memory_packs:
            self._write_json(self._system_dir(state.project_id) / "memory" / f"{item.pack_id}.json", item.model_dump(mode="json"))
        self._write_json(self._observability_file(state.project_id), observability.model_dump(mode="json"))
        self._write_json(self._prewire_file(state.project_id), prewire_schemas)
        improvement_log = []
        if self._improvement_log_file(state.project_id).exists():
            improvement_log = list(self._read_json(self._improvement_log_file(state.project_id)))
        improvement_log.append(improvement_record.model_dump(mode="json"))
        self._write_json(self._improvement_log_file(state.project_id), improvement_log[-20:])
        for capsule in capsules:
            self._write_json(self._capsules_dir(state.project_id) / f"{capsule.node_id}.json", capsule.model_dump(mode="json"))

    def _refresh_system_state(self, project_id: str) -> None:
        state = self.get_project_state(project_id)
        project_meta = self._read_json(self._project_dir(project_id) / "project.json")
        latest_handoff = None
        for session in sorted(state.sessions, key=lambda item: item.created_at, reverse=True):
            handoff_path = self._session_dir(project_id, session.session_id) / "handoff.json"
            if handoff_path.exists():
                latest_handoff = HandoffRecord.model_validate(self._read_json(handoff_path))
                break
        governance = self._governance_summary(state, latest_handoff)
        blocked_now = next((task.blocked_reason for task in state.task_tree if task.blocked_reason), None)
        materials = self._materials_summary(state)
        recommendation = self._recommendation_view(state, latest_handoff, governance, materials, blocked_now)
        next_step = self._next_step_view(latest_handoff, governance, recommendation) if latest_handoff else {
            "state": recommendation["recommended_action"] == "organize_materials" and "research_gap" or "none",
            "message": recommendation["recommended_reason"] if recommendation["recommended_action"] == "organize_materials" else "No suggested next step has been written yet.",
            "actions": ["organize_materials"] if recommendation["recommended_action"] == "organize_materials" else ["start_first_step"],
            "primary_label": "Organize Materials" if recommendation["recommended_action"] == "organize_materials" else "Start First Work Step",
        }
        self._write_system_state(state, dict(project_meta), latest_handoff, recommendation, next_step, materials, governance, blocked_now)

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
        self._refresh_system_state(request.project_id)
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
        self._refresh_system_state(project_id)
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
        self._refresh_system_state(handoff.project_id)
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
        metadata = self._derive_project_metadata(request.goal, request.initial_prompt, request.preferred_project_mode)
        role_catalog = self._derive_role_catalog(request.goal, request.initial_prompt, request.preferred_project_mode)
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
        self._refresh_system_state(project_id)

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
        self._refresh_system_state(request.project_id)
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
        self._refresh_system_state(session.project_id)
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

    def get_system_graph(self, project_id: str) -> dict[str, object]:
        return {
            "project_id": project_id,
            "goal_model": self._read_json_if_exists(self._goal_model_file(project_id), {}),
            "cognitive_state": self._read_json_if_exists(self._cognitive_state_file(project_id), {}),
            "workflow_graph_v2": self._read_json_if_exists(self._workflow_graph_v2_file(project_id), {}),
            "plan_layers": self._read_json_if_exists(self._plan_layers_file(project_id), {}),
            "task_graph_v2": self._read_json_if_exists(self._task_graph_v2_file(project_id), {}),
            "role_profiles": self._read_json_if_exists(self._role_profiles_file(project_id), []),
            "capability_registry": self._read_json_if_exists(self._capability_registry_file(project_id), []),
            "node_capability_map": self._read_json_if_exists(self._node_capability_map_file(project_id), []),
            "prewire_schemas": self._read_json_if_exists(self._prewire_file(project_id), {}),
        }

    def get_node_capsule(self, project_id: str, node_id: str) -> dict[str, object]:
        capsule_path = self._capsules_dir(project_id) / f"{node_id}.json"
        if not capsule_path.exists():
            raise FileNotFoundError(f"Unknown execution capsule for node: {node_id}")
        return {
            "project_id": project_id,
            "node_id": node_id,
            "execution_capsule": self._read_json(capsule_path),
        }

    def get_memory_index(self, project_id: str) -> dict[str, object]:
        return {
            "project_id": project_id,
            "memory_packs": self._read_json_if_exists(self._memory_index_file(project_id), []),
        }

    def get_role_profiles(self, project_id: str) -> dict[str, object]:
        return {
            "project_id": project_id,
            "role_profiles": self._read_json_if_exists(self._role_profiles_file(project_id), []),
        }

    def get_capabilities(self, project_id: str) -> dict[str, object]:
        return {
            "project_id": project_id,
            "capability_registry": self._read_json_if_exists(self._capability_registry_file(project_id), []),
            "prewire_schemas": self._read_json_if_exists(self._prewire_file(project_id), {}),
        }

    def get_mappings(self, project_id: str) -> dict[str, object]:
        return {
            "project_id": project_id,
            "node_capability_map": self._read_json_if_exists(self._node_capability_map_file(project_id), []),
        }

    def get_session_factory_preview(self, project_id: str, node_id: str) -> dict[str, object]:
        capsule_path = self._capsules_dir(project_id) / f"{node_id}.json"
        if not capsule_path.exists():
            raise FileNotFoundError(f"Unknown session factory node: {node_id}")
        capsule = dict(self._read_json(capsule_path))
        return {
            "project_id": project_id,
            "node_id": node_id,
            "session_factory_preview": {
                "launch_readiness": capsule.get("launch_readiness", False),
                "missing_dependencies": capsule.get("missing_dependencies", []),
                "session_config_payload": capsule.get("session_config_payload", {}),
                "memory_pack_refs": capsule.get("memory_pack_refs", []),
                "audit_requirements": capsule.get("audit_requirements", []),
                "source_resolution": capsule.get("source_resolution", "registry"),
            },
        }

    def get_observability(self, project_id: str) -> dict[str, object]:
        return {
            "project_id": project_id,
            "observability": self._read_json_if_exists(self._observability_file(project_id), {}),
        }

    def get_improvement_log(self, project_id: str) -> dict[str, object]:
        return {
            "project_id": project_id,
            "improvements": self._read_json_if_exists(self._improvement_log_file(project_id), []),
        }

    def _append_transcript_entries(self, project_id: str, session_id: str, entries: list[dict[str, object]]) -> list[dict[str, object]]:
        transcript_path = self._session_dir(project_id, session_id) / "transcript.jsonl"
        transcript = list(self._read_json_if_exists(transcript_path, []))
        transcript.extend(entries)
        self._write_json(transcript_path, transcript)
        return transcript

    def _append_observability_event(self, project_id: str, event: ObservabilityEvent) -> dict[str, object]:
        snapshot_payload = dict(self._read_json_if_exists(self._observability_file(project_id), {}))
        if not snapshot_payload:
            return {}
        recent_events = list(snapshot_payload.get("recent_events", []))
        recent_events.insert(0, event.model_dump(mode="json"))
        snapshot_payload["recent_events"] = recent_events[:8]
        snapshot_payload["current_status"] = snapshot_payload.get("current_status", "active")
        self._write_json(self._observability_file(project_id), snapshot_payload)
        return snapshot_payload

    def _append_improvement_entry(self, project_id: str, improvement: ImprovementRecord) -> list[dict[str, object]]:
        log = list(self._read_json_if_exists(self._improvement_log_file(project_id), []))
        log.append(improvement.model_dump(mode="json"))
        self._write_json(self._improvement_log_file(project_id), log[-20:])
        return log[-20:]

    def _append_memory_update(
        self,
        project_id: str,
        session_id: str,
        node_id: str,
        summary: str,
    ) -> list[dict[str, object]]:
        memory_index = list(self._read_json_if_exists(self._memory_index_file(project_id), []))
        operational_pack = next((item for item in memory_index if item.get("layer") == "operational"), None)
        if operational_pack is None:
            return memory_index
        payload = dict(operational_pack.get("payload", {}))
        latest_updates = list(payload.get("latest_updates", []))
        latest_updates.append(
            {
                "session_id": session_id,
                "node_id": node_id,
                "summary": summary,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        payload["latest_updates"] = latest_updates[-10:]
        operational_pack["payload"] = payload
        if summary not in operational_pack.get("keywords", []):
            operational_pack.setdefault("keywords", []).append(summary[:48])
        self._write_json(self._memory_index_file(project_id), memory_index)
        self._write_json(self._system_dir(project_id) / "memory" / f"{operational_pack['pack_id']}.json", operational_pack)
        return memory_index

    def _resolve_chat_session(self, project_id: str, request: ChatMessageRequest) -> SessionRecord:
        if request.session_id:
            session = self._find_session(request.session_id)
            if session.project_id != project_id:
                raise ValueError("invalid_session")
            return session
        summary = self.get_project_summary(project_id)
        recommended_work_package = dict(summary.get("recommended_work_package", {}))
        recommended_role = str(recommended_work_package.get("recommended_role", "Bootstrap Strategist"))
        state = self.get_project_state(project_id)
        active_sessions = [
            session
            for session in sorted(state.sessions, key=lambda item: item.created_at, reverse=True)
            if session.role_name == recommended_role and session.status == SessionStatus.active
        ]
        if active_sessions:
            return active_sessions[0]
        objective = str(recommended_work_package.get("suggested_session_objective", summary.get("recommendation", {}).get("recommended_reason", "Continue the next recommended work step.")))
        input_files = list(recommended_work_package.get("recommended_files", []))
        return self.create_session(
            SessionCreateRequest(
                project_id=project_id,
                role_name=recommended_role,
                objective=objective,
                input_files=input_files,
            )
        )

    def _resolve_chat_node(self, project_id: str, session: SessionRecord) -> tuple[dict[str, object], dict[str, object]]:
        task_graph = dict(self._read_json_if_exists(self._task_graph_v2_file(project_id), {}))
        nodes = list(task_graph.get("nodes", []))
        candidates = [node for node in nodes if node.get("owner_role") == session.role_name]
        if not candidates:
            candidates = nodes
        if not candidates:
            raise ValueError("no_active_node")
        node = next((item for item in candidates if item.get("status") != "completed"), candidates[0])
        capsule = dict(self._read_json_if_exists(self._capsules_dir(project_id) / f"{node['node_id']}.json", {}))
        return node, capsule

    def _simulated_execution_result(
        self,
        project_id: str,
        session: SessionRecord,
        node: dict[str, object],
        capsule: dict[str, object],
        request: ChatMessageRequest,
    ) -> tuple[str, ExecutionResult]:
        action = request.action.strip().lower()
        base_summary = f"{session.role_name} processed the current {node.get('title', 'work step')} from files."
        assistant_message = (
            f"{session.role_name} is continuing from the current files. "
            f"Focus: {session.objective}. "
            f"Latest user instruction: {request.message.strip()}"
        )
        rewrite_intents: list[RewriteIntent] = []
        if action == "replan":
            base_summary = f"{session.role_name} flagged the current direction for replanning."
            assistant_message = "The current direction should be rewritten before downstream execution continues."
            rewrite_intents.append(
                RewriteIntent(
                    target_type="task_graph_v2",
                    target_id=str(node.get("node_id", "unknown-node")),
                    action="replan_node",
                    reason=request.message.strip() or "User requested replanning.",
                    risk_level="medium",
                    auto_applied=False,
                )
            )
        elif action == "review":
            base_summary = f"{session.role_name} reviewed the current work state and highlighted the next decision point."
            assistant_message = "Review notes were recorded. The next step should stay aligned with the current files and explicit risks."
        elif action == "complete":
            base_summary = f"{session.role_name} prepared a completion-ready summary for the current step."
            assistant_message = "A completion-ready summary was prepared. The next role can continue from the updated files."

        event = ObservabilityEvent(
            event_id=f"obs-chat-{uuid4().hex[:8]}",
            event_type="chat_execution",
            title=f"{session.role_name} handled a chat execution step",
            detail=base_summary,
            refs=[f"projects/{project_id}/sessions/{session.session_id}/transcript.jsonl"],
        )
        recommended_handoff = {
            "session_summary": base_summary,
            "next_role_recommendation": "Review Operator" if action == "complete" else session.role_name,
            "next_role_reason": "Validate the latest work from durable files." if action == "complete" else "Continue from the latest structured execution note.",
            "required_input_files": list(capsule.get("required_files", [])),
        }
        memory_updates = [
            {
                "layer": "operational",
                "summary": base_summary,
                "refs": [f"projects/{project_id}/sessions/{session.session_id}/transcript.jsonl"],
            }
        ]
        return assistant_message, ExecutionResult(
            status="completed",
            summary=base_summary,
            structured_outputs={
                "role_name": session.role_name,
                "node_id": node.get("node_id"),
                "action": action,
                "required_files": capsule.get("required_files", []),
            },
            recommended_handoff=recommended_handoff,
            memory_updates=memory_updates,
            observability_event=event.model_dump(mode="json"),
            rewrite_intents=rewrite_intents,
        )

    def _provider_execution_result(
        self,
        project_id: str,
        session: SessionRecord,
        node: dict[str, object],
        capsule: dict[str, object],
        request: ChatMessageRequest,
    ) -> tuple[str, ExecutionResult]:
        adapter = os.environ.get("OPENFLOW_PROVIDER_ADAPTER", "").strip().lower()
        if not adapter:
            return (
                "A real provider-backed execution path is not configured yet. Switch to simulated mode or configure a provider.",
                ExecutionResult(
                    status="not_configured",
                    summary="Provider execution is not configured.",
                    structured_outputs={"node_id": str(node.get("node_id")), "role_name": session.role_name},
                ),
            )
        if adapter == "mock":
            assistant_message, result = self._simulated_execution_result(project_id, session, node, capsule, request)
            result.summary = f"Provider adapter mock executed successfully. {result.summary}"
            result.structured_outputs["provider_adapter"] = "mock"
            return assistant_message, result
        return (
            f"The configured provider adapter '{adapter}' is not supported by this runtime yet.",
            ExecutionResult(
                status="not_configured",
                summary=f"Provider adapter '{adapter}' is not supported.",
                structured_outputs={"node_id": str(node.get('node_id')), "role_name": session.role_name, "provider_adapter": adapter},
            ),
        )

    def _build_auto_complete_request(
        self,
        project_id: str,
        session: SessionRecord,
        node: dict[str, object],
        capsule: dict[str, object],
        execution_result: ExecutionResult,
    ) -> SessionCompleteRequest:
        handoff_input_files = [f"projects/{project_id}/sessions/{session.session_id}/handoff.json"]
        for path in capsule.get("required_files", []):
            if path not in handoff_input_files:
                handoff_input_files.append(path)
        next_role = "Review Operator"
        next_reason = "A review pass should validate the latest execution result from durable files."
        if session.role_name == "Review Operator":
            next_role = "Bootstrap Strategist"
            next_reason = "Review is complete. Re-evaluate the next step from the updated files."
        return SessionCompleteRequest(
            session_summary=execution_result.summary,
            decision_updates=[],
            task_status_changes=[f"{node.get('task_id', 'unknown-task')}=completed"],
            next_role_recommendation=next_role,
            next_role_reason=next_reason,
            required_input_files=handoff_input_files,
            success_criteria=list(capsule.get("verification_policy", [])) or ["Review the latest execution result."],
            risks=["The resulting handoff may still require review or replanning."],
            review_outcome="pass",
            acceptance_status="accepted",
            followup_actions=["Advance to the recommended next role after review."],
        )

    def post_chat_message(self, project_id: str, request: ChatMessageRequest) -> dict[str, object]:
        if request.project_id != project_id:
            raise ValueError("validation_error")
        if not request.message.strip():
            raise ValueError("validation_error")
        if request.action not in {"continue", "complete", "review", "replan"}:
            raise ValueError("validation_error")

        session = self._resolve_chat_session(project_id, request)
        node, capsule = self._resolve_chat_node(project_id, session)
        node_id = str(node.get("node_id", "unknown-node"))
        missing_dependencies = list(capsule.get("missing_dependencies", []))
        is_blocked = bool(missing_dependencies) or bool(node.get("needs_human_confirm")) or capsule.get("launch_readiness") is False

        user_entry = {
            "role": "user",
            "content": request.message.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message_type": "chat_input",
            "node_id": node_id,
            "mode": request.mode,
            "action": request.action,
        }

        if request.mode == "provider":
            assistant_message, execution_result = self._provider_execution_result(project_id, session, node, capsule, request)
        elif is_blocked:
            assistant_message = "This step cannot run yet because launch readiness is blocked. Resolve the missing dependencies or confirmation gate first."
            execution_result = ExecutionResult(
                status="blocked",
                summary="Execution is blocked before the role can continue.",
                structured_outputs={
                    "node_id": node_id,
                    "role_name": session.role_name,
                    "missing_dependencies": missing_dependencies or ["Human confirmation is still required."],
                },
            )
        else:
            assistant_message, execution_result = self._simulated_execution_result(project_id, session, node, capsule, request)

        assistant_entry = {
            "role": "assistant",
            "content": assistant_message,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message_type": "chat_output",
            "node_id": node_id,
            "mode": request.mode,
            "action": request.action,
            "execution_status": execution_result.status,
        }
        self._append_transcript_entries(project_id, session.session_id, [user_entry, assistant_entry])
        self._refresh_system_state(project_id)

        if execution_result.observability_event:
            self._append_observability_event(project_id, ObservabilityEvent.model_validate(execution_result.observability_event))
        if execution_result.memory_updates:
            self._append_memory_update(project_id, session.session_id, node_id, execution_result.memory_updates[-1]["summary"])
        if execution_result.rewrite_intents:
            self._append_improvement_entry(
                project_id,
                ImprovementRecord(
                    improvement_id=f"improvement-{uuid4().hex[:8]}",
                    summary=execution_result.summary,
                    plan_updates=["Keep the next step aligned with the latest chat execution result."],
                    mapping_updates=["Refresh execution mapping after the latest interactive step."],
                    next_focus=[assistant_message],
                    rewrite_intents=execution_result.rewrite_intents,
                ),
            )
        if request.action == "complete" and execution_result.status == "completed":
            completion_request = self._build_auto_complete_request(project_id, session, node, capsule, execution_result)
            self.complete_session(session.session_id, completion_request)

        updated_chat_workspace = self.get_chat_workspace(project_id)
        return ChatMessageResponse(
            project_id=project_id,
            session_id=session.session_id,
            node_id=node_id,
            mode=request.mode,
            assistant_message=assistant_message,
            execution_result=execution_result,
            updated_chat_workspace=updated_chat_workspace,
        ).model_dump(mode="json")

    def get_chat_workspace(self, project_id: str) -> dict[str, object]:
        summary = self.get_project_summary(project_id)
        latest_session = summary.get("latest_session")
        session_payload = None
        complete_defaults = None
        if latest_session:
            session_id = str(latest_session["session_id"])
            session_payload = self.get_session_detail(project_id, session_id)
            complete_defaults = {
                "session_summary": "Summarize the work step outcome and what changed.",
                "next_role_recommendation": "Review Operator",
                "next_role_reason": "A review pass is needed before advancing.",
                "required_input_files": [f"projects/{project_id}/sessions/{session_id}/handoff.json"],
                "success_criteria": ["Review the evidence", "Decide whether to advance"],
                "risks": ["The review may trigger replanning."],
                "transcript_note": "Record the most important execution note from this session.",
                "task_status_changes": ["implementation-slice=completed"],
                "review_outcome": "pass",
                "acceptance_status": "accepted",
                "followup_actions": ["Start the recommended next role."],
            }
        return {
            "project_id": project_id,
            "project": summary.get("project", {}),
            "project_stage": summary.get("project_stage"),
            "goal_model": summary.get("goal_model", {}),
            "recommendation": summary.get("recommendation", {}),
            "recommended_work_package": summary.get("recommended_work_package", {}),
            "next_step": summary.get("next_step", {}),
            "governance": summary.get("governance", {}),
            "materials": summary.get("materials", {}),
            "latest_session": latest_session,
            "latest_handoff": summary.get("latest_handoff"),
            "timeline": summary.get("timeline", []),
            "current_execution_capsule_preview": summary.get("current_execution_capsule_preview", {}),
            "current_session_factory_preview": summary.get("current_session_factory_preview", {}),
            "memory_pack_preview": session_payload.get("memory_pack_preview", []) if session_payload else [],
            "observability_snapshot": session_payload.get("observability_snapshot", {}) if session_payload else self.get_observability(project_id).get("observability", {}),
            "improvement_snapshot": session_payload.get("improvement_snapshot", []) if session_payload else self.get_improvement_log(project_id).get("improvements", []),
            "session_detail": session_payload,
            "complete_defaults": complete_defaults,
        }

    def get_config_workspace(self, project_id: str) -> dict[str, object]:
        summary = self.get_project_summary(project_id)
        graph = self.get_system_graph(project_id)
        return {
            "project_id": project_id,
            "project": summary.get("project", {}),
            "project_stage": summary.get("project_stage"),
            "governance": summary.get("governance", {}),
            "goal_model": graph.get("goal_model", {}),
            "cognitive_state": graph.get("cognitive_state", {}),
            "plan_layers": graph.get("plan_layers", {}),
            "task_graph_v2": graph.get("task_graph_v2", {}),
            "role_profiles": graph.get("role_profiles", []),
            "capability_registry": graph.get("capability_registry", []),
            "node_capability_map": graph.get("node_capability_map", []),
            "prewire_schemas": graph.get("prewire_schemas", {}),
        }

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
        recommended_work_package = self._work_package_view(
            state,
            latest_handoff,
            governance,
            materials,
            blocked_now,
            recommendation,
            next_step,
        )
        project_stage = self._project_stage(state, latest_handoff, governance)
        next_role = recommendation["recommended_role"]
        why_next_role = recommendation["recommended_reason"]
        goal_model = self._read_json_if_exists(self._goal_model_file(project_id), {})
        cognitive_state = self._read_json_if_exists(self._cognitive_state_file(project_id), {})
        plan_layers = self._read_json_if_exists(self._plan_layers_file(project_id), {})
        task_graph_v2 = self._read_json_if_exists(self._task_graph_v2_file(project_id), {})
        current_execution_capsule_preview = {}
        current_session_factory_preview = {}
        if task_graph_v2:
            nodes = list(task_graph_v2.get("nodes", []))
            current_node = next((node for node in nodes if node.get("owner_role") == recommendation["recommended_role"]), None)
            if current_node:
                capsule_path = self._capsules_dir(project_id) / f"{current_node['node_id']}.json"
                current_execution_capsule_preview = self._read_json_if_exists(capsule_path, {})
                current_session_factory_preview = self.get_session_factory_preview(project_id, current_node["node_id"]).get("session_factory_preview", {})
        return {
            "project_id": project_id,
            "project": project_meta,
            "state": state.model_dump(mode="json"),
            "latest_session": latest_session.model_dump(mode="json") if latest_session else None,
            "latest_handoff": latest_handoff.model_dump(mode="json") if latest_handoff else None,
            "goal_model": goal_model,
            "cognitive_state": cognitive_state,
            "plan_layers": plan_layers,
            "task_graph_v2": task_graph_v2,
            "timeline": timeline["events"],
            "governance": governance,
            "project_stage": project_stage,
            "recommendation": recommendation,
            "recommended_work_package": recommended_work_package,
            "current_execution_capsule_preview": current_execution_capsule_preview,
            "current_session_factory_preview": current_session_factory_preview,
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
        recommended_work_package = self._work_package_view(
            state,
            handoff,
            governance,
            materials,
            blocked_now,
            recommendation,
            next_step,
        )
        task_graph_v2 = self._read_json_if_exists(self._task_graph_v2_file(project_id), {})
        execution_capsule = {}
        session_factory_preview = {}
        if task_graph_v2:
            current_node = next((node for node in task_graph_v2.get("nodes", []) if node.get("owner_role") == session.role_name), None)
            if current_node:
                execution_capsule = self._read_json_if_exists(self._capsules_dir(project_id) / f"{current_node['node_id']}.json", {})
                session_factory_preview = self.get_session_factory_preview(project_id, current_node["node_id"]).get("session_factory_preview", {})
        memory_pack_preview = self._read_json_if_exists(self._memory_index_file(project_id), [])
        observability_snapshot = self._read_json_if_exists(self._observability_file(project_id), {})
        improvement_log = self._read_json_if_exists(self._improvement_log_file(project_id), [])
        return {
            "project_id": project_id,
            "session": session.model_dump(mode="json"),
            "handoff": handoff.model_dump(mode="json") if handoff else None,
            "transcript": transcript,
            "role_policy": role_policy,
            "why_exists": why_exists,
            "project_stage": self._project_stage(state, handoff, governance),
            "recommendation": recommendation,
            "recommended_work_package": recommended_work_package,
            "review_state": next_step["state"],
            "review_feedback_message": self._review_feedback_message(handoff.acceptance_status if handoff else None),
            "next_step": next_step,
            "execution_capsule": execution_capsule,
            "session_factory_preview": session_factory_preview,
            "memory_pack_preview": memory_pack_preview,
            "observability_snapshot": observability_snapshot,
            "improvement_snapshot": improvement_log[-3:],
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
