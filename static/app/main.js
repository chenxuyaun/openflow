const appRoot = document.getElementById("app");

const appState = {
  flash: null,
  landingPayload: null,
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function splitLines(value) {
  return String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function arrayify(value) {
  if (Array.isArray(value)) {
    return value;
  }
  if (!value) {
    return [];
  }
  return [value];
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    throw new Error((await response.text()) || `Request failed: ${response.status}`);
  }
  const contentType = response.headers.get("content-type") || "";
  return contentType.includes("application/json") ? response.json() : response.text();
}

function setFlash(kind, message) {
  appState.flash = { kind, message };
}

function consumeFlash() {
  const flash = appState.flash;
  appState.flash = null;
  return flash;
}

function navigate(path) {
  window.history.pushState({}, "", path);
  render();
}

window.addEventListener("popstate", render);

document.addEventListener("click", (event) => {
  const link = event.target.closest("[data-nav]");
  if (!link) {
    return;
  }
  event.preventDefault();
  navigate(link.getAttribute("href"));
});

function shell(content, projectId = "", active = "") {
  const nav = projectId
    ? `
      <div class="app-nav">
        <a class="nav-tab ${active === "workspace" ? "active" : ""}" href="/app/projects/${projectId}" data-nav>Chat Workspace</a>
        <a class="nav-tab ${active === "config" ? "active" : ""}" href="/app/projects/${projectId}/config" data-nav>System Config</a>
      </div>
    `
    : "";
  return `
    <div class="app-shell">
      <header class="topbar">
        <div class="brand">
          <div class="brand-title"><a href="/app" data-nav>OpenFlow</a></div>
          <div class="brand-subtitle">Fresh sessions continue through files, handoffs, memory, and saved decisions.</div>
        </div>
        <div class="topbar-links">
          <a href="/" target="_blank" rel="noreferrer">Legacy Pages</a>
          <a href="/blueprint" target="_blank" rel="noreferrer">Blueprint API</a>
        </div>
      </header>
      ${nav}
      <main class="page">${content}</main>
    </div>
  `;
}

function renderFlash() {
  const flash = consumeFlash();
  if (!flash) {
    return "";
  }
  return `
    <section class="notice-banner ${escapeHtml(flash.kind || "info")}">
      <strong>${escapeHtml(flash.message)}</strong>
    </section>
  `;
}

function oldRouteMessage(pathname, projectId) {
  const routeMap = [
    ["/welcome", "The welcome guide has been absorbed into Chat Workspace."],
    ["/sessions/", "Session detail now appears inside Chat Workspace."],
    ["/knowledge", "Materials and memory now appear inside Chat Workspace."],
    ["/tasks", "Task status and blockers now appear inside Chat Workspace."],
    ["/workflow", "Workflow definition now appears inside System Config."],
    ["/decisions", "Decision and review configuration now appears inside System Config."],
  ];
  const matched = routeMap.find(([segment]) => pathname.includes(segment));
  if (!matched) {
    return "";
  }
  const target = matched[0] === "/workflow" || matched[0] === "/decisions"
    ? `/app/projects/${projectId}/config`
    : `/app/projects/${projectId}`;
  return `
    <section class="notice-banner">
      <strong>Page structure has been simplified.</strong>
      <p>${escapeHtml(matched[1])}</p>
      <a class="button secondary" href="${target}" data-nav>Open the primary surface</a>
    </section>
  `;
}

function statusUi(state) {
  const map = {
    ready: { label: "Ready", className: "ready", explanation: "The next step is clear and can continue." },
    blocked: { label: "Blocked", className: "blocked", explanation: "A blocker is preventing the next step from continuing." },
    review_needed: { label: "Review Needed", className: "review", explanation: "The next step is known, but review still has to happen first." },
    changes_requested: { label: "Changes Requested", className: "review", explanation: "Another pass is required before the project should continue." },
    replan_required: { label: "Replan", className: "review", explanation: "The current route needs to be adjusted before the project moves on." },
    research_gap: { label: "More Material Needed", className: "blocked", explanation: "The current path is limited by missing organized material." },
    none: { label: "Not Ready Yet", className: "blocked", explanation: "The project does not yet have a stable saved next step." },
  };
  return map[state] || map.none;
}

function recommendationSourceLabel(source) {
  const map = {
    latest_handoff: "The latest saved handoff is driving this recommendation.",
    confirm_gate: "A review gate is shaping the recommended path.",
    review_replan: "A replan decision is shaping the recommended path.",
    review_changes_requested: "Requested changes are shaping the recommended path.",
    blocked_task: "Blocked work is influencing the recommended path.",
    decision_conflict: "Conflicting decision-linked material is influencing the recommended path.",
    raw_material_gap: "A material gap is influencing the recommended path.",
    project_mode_research: "The current project mode is steering the next step toward material work.",
    fallback: "The current project summary and next-step state are driving this recommendation.",
  };
  return map[source] || map.fallback;
}

function confidenceLabel(value) {
  const map = {
    high: "Current records strongly support this path.",
    medium: "Current records support this path, but more review or material could still change it.",
    low: "This path is provisional and based on limited evidence.",
  };
  return map[value] || map.medium;
}

function getWorkPackage(container) {
  if (container?.recommended_work_package) {
    return container.recommended_work_package;
  }
  const recommendation = container?.recommendation || {};
  const nextStep = container?.next_step || {};
  const blockers = nextStep.state && !["ready", "none"].includes(nextStep.state) ? [nextStep.message].filter(Boolean) : [];
  return {
    recommended_role: recommendation.recommended_role || "Implementation Lead",
    recommended_action: nextStep.primary_label || "Continue the recommended next step",
    recommended_reason: recommendation.recommended_reason || nextStep.message || "Continue with the next work package from the saved project state.",
    recommended_files: [`projects/${container?.project_id || "current"}/workflow_graph.json`],
    expected_output: nextStep.message || "Produce the next saved project result.",
    success_criteria: [],
    risks: [],
    blocking_items: blockers,
    confidence: "medium",
    recommendation_source: "fallback",
    secondary_note: recommendation.secondary_note || "",
    project_mode: container?.project_mode || container?.state?.project_mode || "delivery",
    next_step_state: nextStep.state || "none",
    ready_for_auto_advance: false,
    auto_advance_blockers: blockers,
    suggested_session_objective: nextStep.message || "Start the next recommended work package.",
    human_action_required: true,
    materials_snapshot: {
      organized_material_count: container?.materials?.organized_material_count || 0,
      raw_source_count: 0,
      synthesized_count: 0,
      linked_count: 0,
    },
  };
}

function tag(text, cls = "") {
  return `<span class="tag ${cls}">${escapeHtml(text)}</span>`;
}

function sectionCard(title, body, eyebrow = "", extra = "") {
  return `
    <section class="panel">
      ${eyebrow ? `<div class="eyebrow">${escapeHtml(eyebrow)}</div>` : ""}
      <div class="section-head">
        <h2>${escapeHtml(title)}</h2>
        ${extra}
      </div>
      ${body}
    </section>
  `;
}

function renderTurn(turn) {
  const roleLabel = turn.role === "assistant" ? "System response" : "User input";
  return `
    <article class="turn-card ${turn.role === "assistant" ? "assistant" : "user"}">
      <div class="turn-meta">
        <strong>${escapeHtml(roleLabel)}</strong>
        <span>${escapeHtml(turn.message_type || "conversation")}</span>
        <span>${escapeHtml(turn.execution_status || "saved")}</span>
      </div>
      <p>${escapeHtml(turn.content || "")}</p>
    </article>
  `;
}

function renderConversation(sessionDetail) {
  const transcript = sessionDetail?.transcript || [];
  if (!transcript.length) {
    return `<div class="empty-state">No conversation has been recorded for the current session yet.</div>`;
  }
  return `<div class="conversation-stream">${transcript.slice(-10).map(renderTurn).join("")}</div>`;
}

function renderKeyRounds(observability) {
  const events = observability?.recent_events || [];
  if (!events.length) {
    return `<div class="empty-state">No recent execution events have been recorded yet.</div>`;
  }
  return `
    <div class="timeline-list">
      ${events.slice(0, 5).map((event) => `
        <div class="timeline-item">
          <strong>${escapeHtml(event.title)}</strong>
          <p>${escapeHtml(event.detail)}</p>
        </div>
      `).join("")}
    </div>
  `;
}

function renderObjectivePanel(chat) {
  const goalModel = chat.goal_model || {};
  return `
    <div class="rail-card">
      <div class="eyebrow">Current Objective</div>
      <h3>${escapeHtml(goalModel.core_goal || chat.project?.goal || "Current project objective")}</h3>
      <p>${escapeHtml(chat.project?.goal || goalModel.core_goal || "Define and complete the next visible project outcome.")}</p>
      <div class="compact-tags">
        ${tag(`Stage: ${chat.project_stage || "unknown"}`)}
        ${tag(`Project: ${chat.project?.project_name || "Unnamed"}`)}
      </div>
    </div>
  `;
}

function renderWorkPackagePanel(workPackage) {
  const state = statusUi(workPackage.next_step_state);
  const files = arrayify(workPackage.recommended_files);
  const previewFiles = files.slice(0, 2);
  const extraFiles = files.slice(2);
  const blockers = arrayify(workPackage.blocking_items);
  const autoBlockers = arrayify(workPackage.auto_advance_blockers);
  const visibleBlockers = blockers.length ? blockers : autoBlockers;
  return `
    <div class="rail-card rail-feature">
      <div class="rail-card-head">
        <div>
          <div class="eyebrow">Recommended Work Package</div>
          <h3>${escapeHtml(workPackage.recommended_role || "Implementation Lead")}</h3>
        </div>
        <span class="status-chip ${state.className}">${escapeHtml(state.label)}</span>
      </div>
      <p class="feature-action">${escapeHtml(workPackage.recommended_action || "Continue with the next recommended step.")}</p>
      <p class="muted">${escapeHtml(workPackage.recommended_reason || "This is the strongest current next step.")}</p>
      <div class="mini-block">
        <strong>Read first</strong>
        ${previewFiles.length ? `<div class="file-list">${previewFiles.map((item) => `<code>${escapeHtml(item)}</code>`).join("")}</div>` : `<p class="muted">No file references are attached yet.</p>`}
      </div>
      <div class="mini-block">
        <strong>Expected output</strong>
        <p>${escapeHtml(workPackage.expected_output || "Produce the next saved result.")}</p>
      </div>
      ${visibleBlockers.length && !workPackage.ready_for_auto_advance ? `
        <div class="callout danger">
          <strong>Why it cannot continue automatically yet</strong>
          <ul class="bullet-list">${visibleBlockers.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </div>
      ` : workPackage.human_action_required && !workPackage.ready_for_auto_advance ? `
        <div class="callout warning">
          <strong>Human action is still required</strong>
          <p>The system has a recommendation, but a person still needs to start or confirm the next step.</p>
        </div>
      ` : `
        <div class="callout success">
          <strong>Auto-continue conditions are already in place</strong>
          <p>The saved project records satisfy the continuation checks, but this page does not trigger execution by itself.</p>
        </div>
      `}
      <details class="details-block">
        <summary>Open full work package details</summary>
        <div class="details-stack">
          ${extraFiles.length ? `<div><strong>Full file list</strong><div class="file-list">${extraFiles.map((item) => `<code>${escapeHtml(item)}</code>`).join("")}</div></div>` : ""}
          ${arrayify(workPackage.success_criteria).length ? `<div><strong>Success criteria</strong><ul class="bullet-list">${arrayify(workPackage.success_criteria).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>` : ""}
          ${arrayify(workPackage.risks).length ? `<div><strong>Risks</strong><ul class="bullet-list">${arrayify(workPackage.risks).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>` : ""}
          <div><strong>Confidence</strong><p>${escapeHtml(confidenceLabel(workPackage.confidence))}</p></div>
          ${workPackage.secondary_note ? `<div><strong>Additional note</strong><p>${escapeHtml(workPackage.secondary_note)}</p></div>` : ""}
        </div>
      </details>
    </div>
  `;
}

function renderReadinessPanel(workPackage) {
  const state = statusUi(workPackage.next_step_state);
  const blockers = arrayify(workPackage.auto_advance_blockers).length
    ? arrayify(workPackage.auto_advance_blockers)
    : arrayify(workPackage.blocking_items);
  return `
    <div class="rail-card">
      <div class="eyebrow">Launch Readiness</div>
      <h3>${workPackage.ready_for_auto_advance ? "Ready for continuation" : "Not ready for automatic continuation"}</h3>
      <p>${escapeHtml(state.explanation)}</p>
      ${!workPackage.ready_for_auto_advance
        ? (blockers.length
          ? `<ul class="bullet-list">${blockers.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
          : `<p class="muted">A person still needs to review, choose, or start the next step.</p>`)
        : `<p class="muted">Recommendation and readiness are aligned, but execution still remains a deliberate user action.</p>`}
    </div>
  `;
}

function renderMemoryPanel(chat, workPackage) {
  const snapshot = workPackage.materials_snapshot || {};
  const memoryPreview = chat.memory_pack_preview || [];
  return `
    <div class="rail-card">
      <div class="eyebrow">Memory Summary</div>
      <div class="metric-grid">
        <div class="metric-mini"><strong>${snapshot.organized_material_count || 0}</strong><span>Organized</span></div>
        <div class="metric-mini"><strong>${snapshot.raw_source_count || 0}</strong><span>Raw Sources</span></div>
        <div class="metric-mini"><strong>${snapshot.synthesized_count || 0}</strong><span>Synthesized</span></div>
        <div class="metric-mini"><strong>${snapshot.linked_count || 0}</strong><span>Linked</span></div>
      </div>
      <p class="muted">Continuity comes from files, memory packs, handoffs, decisions, and timeline records rather than hidden chat context.</p>
      ${memoryPreview.length ? `<details class="details-block"><summary>See preserved memory layers</summary><div class="details-stack">${memoryPreview.slice(0, 5).map((item) => `<div><strong>${escapeHtml(item.title || item.layer || "Layer")}</strong><p>${escapeHtml(item.summary || item.description || "")}</p></div>`).join("")}</div></details>` : ""}
    </div>
  `;
}

function renderObservabilityPanel(chat) {
  const latestSession = chat.latest_session;
  const latestHandoff = chat.latest_handoff;
  const observability = chat.observability_snapshot || {};
  return `
    <div class="rail-card">
      <div class="eyebrow">Progress / Observability</div>
      <h3>${escapeHtml(observability.current_phase || chat.project_stage || "Current phase")}</h3>
      <p>${escapeHtml(observability.current_role || latestSession?.role_name || "No active role yet")}</p>
      <div class="compact-tags">
        ${tag(`Progress ${observability.progress_percent || 0}%`)}
        ${latestSession ? tag(`Session ${latestSession.status}`) : ""}
        ${latestHandoff ? tag(`Handoff ${latestHandoff.acceptance_status || "saved"}`) : ""}
      </div>
      ${renderKeyRounds(observability)}
    </div>
  `;
}

function renderBlockersPanel(chat, workPackage) {
  const blockers = [
    ...arrayify(workPackage.blocking_items),
    ...arrayify(workPackage.auto_advance_blockers),
  ];
  const unique = [...new Set(blockers.filter(Boolean))];
  return `
    <div class="rail-card">
      <div class="eyebrow">Active Blockers</div>
      <h3>${unique.length ? "What is preventing smoother continuation" : "No active blockers are recorded right now"}</h3>
      ${unique.length ? `<ul class="bullet-list">${unique.slice(0, 5).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : `<p class="muted">The system still distinguishes recommendation from execution, but no explicit blocker has been recorded.</p>`}
      <p class="microcopy">${escapeHtml(recommendationSourceLabel(workPackage.recommendation_source))}</p>
    </div>
  `;
}

function renderImprovementPanel(chat) {
  const improvements = chat.improvement_snapshot || [];
  if (!improvements.length) {
    return `
      <div class="rail-card">
        <div class="eyebrow">Latest Improvement</div>
        <h3>No improvement records yet</h3>
        <p class="muted">When the system rewrites plans, mappings, or next-step logic, the latest improvement will appear here.</p>
      </div>
    `;
  }
  const latest = improvements[improvements.length - 1];
  return `
    <div class="rail-card">
      <div class="eyebrow">Latest Improvement</div>
      <h3>${escapeHtml(latest.summary || "Latest system improvement")}</h3>
      ${arrayify(latest.next_focus).length ? `<p>${escapeHtml(arrayify(latest.next_focus)[0])}</p>` : ""}
      ${arrayify(latest.plan_updates).length ? `<ul class="bullet-list">${arrayify(latest.plan_updates).slice(0, 3).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
    </div>
  `;
}

function renderActionPanel(projectId, chat, workPackage) {
  const nextStep = chat.next_step || {};
  const latestHandoff = chat.latest_handoff;
  const canContinue = latestHandoff && nextStep.state === "ready";
  const needsReview = latestHandoff && nextStep.state === "review_needed";
  const completeDefaults = chat.complete_defaults;
  const currentRole = chat.latest_session?.role_name || workPackage.recommended_role || "Next role";
  const createAction = !chat.latest_session
    ? `
      <form class="action-form" data-start-session="${projectId}">
        <input type="hidden" name="role_name" value="${escapeHtml(workPackage.recommended_role || "Implementation Lead")}" />
        <input type="hidden" name="objective" value="${escapeHtml(workPackage.suggested_session_objective || "Start the next recommended work package.")}" />
        <input type="hidden" name="input_files" value="${escapeHtml(arrayify(workPackage.recommended_files).join("\n"))}" />
        <button type="submit">Start the next work package</button>
      </form>
    `
    : "";
  const reviewAction = needsReview
    ? `
      <details class="details-block">
        <summary>Review the next step</summary>
        <form class="form-grid" data-review-handoff="${latestHandoff.handoff_id}" data-project="${projectId}">
          <div class="field">
            <label>Review note</label>
            <textarea name="note">Record what should happen next before this step continues.</textarea>
          </div>
          <div class="actions">
            <button type="submit" name="action" value="approve">Continue</button>
            <button class="secondary" type="submit" name="action" value="changes_requested">Needs Changes</button>
            <button class="secondary" type="submit" name="action" value="replan_required">Replan</button>
          </div>
        </form>
      </details>
    `
    : "";
  const completeAction = chat.latest_session && completeDefaults
    ? `
      <details class="details-block">
        <summary>Complete the current role and write the next handoff</summary>
        <form class="form-grid" data-complete-session="${chat.latest_session.session_id}" data-project="${projectId}">
          <div class="field"><label>What changed in this round?</label><textarea name="session_summary">${escapeHtml(completeDefaults.session_summary)}</textarea></div>
          <div class="field"><label>Which role should continue next?</label><input type="text" name="next_role_recommendation" value="${escapeHtml(completeDefaults.next_role_recommendation)}" /></div>
          <div class="field"><label>Why is that the right next step?</label><textarea name="next_role_reason">${escapeHtml(completeDefaults.next_role_reason)}</textarea></div>
          <div class="field"><label>What should the next step read?</label><textarea name="required_input_files">${escapeHtml(arrayify(completeDefaults.required_input_files).join("\n"))}</textarea></div>
          <div class="field"><label>What should success look like next?</label><textarea name="success_criteria">${escapeHtml(arrayify(completeDefaults.success_criteria).join("\n"))}</textarea></div>
          <div class="field"><label>Risks or blockers</label><textarea name="risks">${escapeHtml(arrayify(completeDefaults.risks).join("\n"))}</textarea></div>
          <div class="field"><label>Most important note to preserve</label><textarea name="transcript_note">${escapeHtml(completeDefaults.transcript_note || "")}</textarea></div>
          <div class="field"><label>Follow-up actions</label><textarea name="followup_actions">${escapeHtml(arrayify(completeDefaults.followup_actions).join("\n"))}</textarea></div>
          <details class="details-block">
            <summary>Advanced handoff controls</summary>
            <div class="details-stack">
              <div class="field"><label>Task status changes</label><textarea name="task_status_changes">${escapeHtml(arrayify(completeDefaults.task_status_changes).join("\n"))}</textarea></div>
              <div class="field"><label>Review outcome</label><input type="text" name="review_outcome" value="${escapeHtml(completeDefaults.review_outcome || "")}" /></div>
              <div class="field"><label>Acceptance status</label><input type="text" name="acceptance_status" value="${escapeHtml(completeDefaults.acceptance_status || "")}" /></div>
            </div>
          </details>
          <div class="actions"><button type="submit">Complete this role</button></div>
        </form>
      </details>
    `
    : "";
  return sectionCard(
    "Current working area",
    `
      <div class="focus-strip">
        <div>
          <strong>Current goal</strong>
          <p>${escapeHtml(chat.project?.goal || chat.goal_model?.core_goal || "Continue the project from the saved state.")}</p>
        </div>
        <div>
          <strong>Current role</strong>
          <p>${escapeHtml(currentRole)}</p>
        </div>
      </div>
      ${createAction}
      ${canContinue ? `<div class="actions"><button type="button" data-advance-handoff="${latestHandoff.handoff_id}" data-project="${projectId}">Continue the recommended step</button></div>` : ""}
      ${reviewAction}
      ${completeAction}
    `,
    "Current objective"
  );
}

function renderWorkspace(chat, pathname) {
  const projectId = chat.project_id;
  const workPackage = getWorkPackage(chat);
  const state = statusUi(chat.next_step?.state || workPackage.next_step_state || "none");
  const compatibility = oldRouteMessage(pathname, projectId);
  return shell(`
    ${renderFlash()}
    ${compatibility}
    <section class="hero workspace-hero">
      <div class="hero-header">
        <div>
          <div class="eyebrow">Chat Workspace</div>
          <h1>${escapeHtml(chat.project?.project_name || "OpenFlow Workspace")}</h1>
          <p class="lede">${escapeHtml(chat.project?.goal || chat.goal_model?.core_goal || "Continue the next saved project outcome.")}</p>
        </div>
        <div class="hero-status">
          <span class="status-chip ${state.className}">${escapeHtml(state.label)}</span>
          <p>${escapeHtml(state.explanation)}</p>
        </div>
      </div>
      <div class="hero-grid">
        <div class="hero-stat"><strong>Stage</strong><span>${escapeHtml(chat.project_stage || "unknown")}</span></div>
        <div class="hero-stat"><strong>Current role</strong><span>${escapeHtml(chat.latest_session?.role_name || workPackage.recommended_role || "No active role")}</span></div>
        <div class="hero-stat"><strong>Latest handoff</strong><span>${escapeHtml(chat.latest_handoff?.acceptance_status || "none")}</span></div>
        <div class="hero-stat"><strong>Progress</strong><span>${escapeHtml(String(chat.observability_snapshot?.progress_percent || 0) + "%")}</span></div>
      </div>
    </section>
    <section class="workspace-layout">
      <div class="workspace-main">
        ${renderActionPanel(projectId, chat, workPackage)}
        ${sectionCard("Chat input", `
          <div class="composer-context">
            <div class="compact-tags">
              ${tag(chat.project_stage || "Unknown stage")}
              ${tag(chat.latest_session?.role_name || workPackage.recommended_role || "No active role")}
              ${tag(statusUi(chat.next_step?.state || "none").label, "state")}
            </div>
            <p class="muted">Use this space to continue the current session, test the next move, or record the change that should be preserved.</p>
          </div>
          <form id="chat-message-form" class="form-grid" data-chat-project="${projectId}">
            <input type="hidden" name="project_id" value="${escapeHtml(projectId)}" />
            <input type="hidden" name="session_id" value="${escapeHtml(chat.latest_session?.session_id || "")}" />
            <div class="field">
              <label>What should happen in this round?</label>
              <textarea name="message" placeholder="Describe the next action, correction, or request for this session."></textarea>
            </div>
            <div class="form-row-inline">
              <div class="field">
                <label>Action</label>
                <select name="action">
                  <option value="continue">Continue current work</option>
                  <option value="complete">Complete current work</option>
                  <option value="review">Request a review response</option>
                  <option value="replan">Trigger replanning</option>
                </select>
              </div>
              <div class="field">
                <label>Mode</label>
                <select name="mode">
                  <option value="simulated">Simulated</option>
                  <option value="provider">Provider</option>
                </select>
              </div>
            </div>
            <div class="actions"><button type="submit">Send to current session</button></div>
          </form>
        `, "Current session")}
        ${sectionCard("Current session conversation", renderConversation(chat.session_detail), "Current session")}
        ${sectionCard("Recent execution record", renderKeyRounds(chat.observability_snapshot), "Recent execution")}
        ${sectionCard("Why continuity still holds", `
          <div class="continuity-panel">
            <p>Every role still starts in a fresh session. Continuity is carried by files, memory packs, handoffs, decisions, and timeline events rather than hidden runtime context.</p>
            <div class="compact-tags">
              ${tag(`Memory layers: ${(chat.memory_pack_preview || []).length}`)}
              ${tag(`Timeline events: ${(chat.timeline || []).length}`)}
              ${tag(`Latest session: ${chat.latest_session?.status || "none"}`)}
            </div>
          </div>
        `, "Continuity")}
      </div>
      <aside class="workspace-rail">
        ${renderObjectivePanel(chat)}
        ${renderWorkPackagePanel(workPackage)}
        ${renderReadinessPanel(workPackage)}
        ${renderMemoryPanel(chat, workPackage)}
        ${renderObservabilityPanel(chat)}
        ${renderBlockersPanel(chat, workPackage)}
        ${renderImprovementPanel(chat)}
      </aside>
    </section>
  `, projectId, "workspace");
}

function renderConfigSummary(config) {
  return `
    <section class="hero config-hero">
      <div class="eyebrow">System Config</div>
      <h1>${escapeHtml(config.project?.project_name || "System configuration")}</h1>
      <p class="lede">This page explains how the project is configured, how roles are assembled, how memory is preserved, and where human review still constrains execution.</p>
      <div class="hero-grid">
        <div class="hero-stat"><strong>Stage</strong><span>${escapeHtml(config.project_stage || "unknown")}</span></div>
        <div class="hero-stat"><strong>Plan layers</strong><span>${escapeHtml(String((config.plan_layers?.phases || []).length || 0))}</span></div>
        <div class="hero-stat"><strong>Roles</strong><span>${escapeHtml(String((config.role_profiles || []).length || 0))}</span></div>
        <div class="hero-stat"><strong>Capabilities</strong><span>${escapeHtml(String((config.capability_registry || []).length || 0))}</span></div>
      </div>
    </section>
  `;
}

function renderConfigSection(title, summary, detail, eyebrow) {
  return `
    <section class="panel config-section">
      <div class="eyebrow">${escapeHtml(eyebrow)}</div>
      <div class="section-head">
        <h2>${escapeHtml(title)}</h2>
      </div>
      <p>${summary}</p>
      <details class="details-block">
        <summary>Open details</summary>
        <div class="details-stack">${detail}</div>
      </details>
    </section>
  `;
}

function renderSystemConfig(config, pathname = "") {
  const projectId = config.project_id;
  const compatibility = oldRouteMessage(pathname, projectId);
  const projectDefinition = renderConfigSection(
    "Project Definition",
    escapeHtml(config.goal_model?.core_goal || config.project?.goal || "Define what this project is trying to finish and what success looks like."),
    `
      <div><strong>Core goal</strong><p>${escapeHtml(config.goal_model?.core_goal || "Not recorded")}</p></div>
      <div><strong>Explicit constraints</strong><ul class="bullet-list">${arrayify(config.goal_model?.explicit_constraints).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No explicit constraints recorded.</li>"}</ul></div>
      <div><strong>Anti-goals</strong><ul class="bullet-list">${arrayify(config.goal_model?.anti_goals).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No anti-goals recorded.</li>"}</ul></div>
      <div><strong>Success criteria</strong><ul class="bullet-list">${arrayify(config.goal_model?.success_criteria).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No success criteria recorded.</li>"}</ul></div>
    `,
    "Project definition"
  );
  const workflowDefinition = renderConfigSection(
    "Workflow Definition",
    "This section shows how the system layers strategy, phases, milestones, and execution nodes into one visible project path.",
    `
      <div><strong>Strategic layer</strong><ul class="bullet-list">${arrayify(config.plan_layers?.strategic).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No strategic layer recorded.</li>"}</ul></div>
      <div><strong>Phases</strong><ul class="bullet-list">${arrayify(config.plan_layers?.phases).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No phases recorded.</li>"}</ul></div>
      <div><strong>Milestones</strong><ul class="bullet-list">${arrayify(config.plan_layers?.milestones).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No milestones recorded.</li>"}</ul></div>
      <div><strong>Task graph</strong><ul class="bullet-list">${arrayify(config.task_graph_v2?.nodes).slice(0, 8).map((node) => `<li>${escapeHtml(node.title || node.node_id || "node")} | ${escapeHtml(node.owner_role || "n/a")} | ${escapeHtml(node.status || "unknown")}</li>`).join("") || "<li>No task graph nodes recorded.</li>"}</ul></div>
    `,
    "Workflow definition"
  );
  const roleSystem = renderConfigSection(
    "Role System",
    "This section explains which roles exist, what each role is expected to do, and how fresh sessions are assigned to those roles.",
    `
      <div class="card-grid dense-grid">
        ${arrayify(config.role_profiles).map((role) => `
          <div class="config-mini-card">
            <strong>${escapeHtml(role.role_name || "Role")}</strong>
            <p>${escapeHtml(role.session_intent || role.objective || "No role objective recorded.")}</p>
            <p class="microcopy">${escapeHtml(role.prompt_style || role.agent_profile || "Fresh session role profile")}</p>
          </div>
        `).join("") || `<div class="config-mini-card"><strong>No role profiles recorded.</strong></div>`}
      </div>
    `,
    "Role system"
  );
  const capabilityAssembly = renderConfigSection(
    "Capability Assembly",
    "This section explains which abilities are available in the project and which work nodes are wired to them.",
    `
      <div><strong>Registered capabilities</strong><ul class="bullet-list">${arrayify(config.capability_registry).slice(0, 10).map((item) => `<li>${escapeHtml(item.capability_name || item.name || "Capability")} | ${escapeHtml(item.capability_type || item.kind || "type")}</li>`).join("") || "<li>No capabilities recorded.</li>"}</ul></div>
      <div><strong>Which stages use which abilities</strong><ul class="bullet-list">${arrayify(config.node_capability_map).slice(0, 10).map((item) => `<li>${escapeHtml(item.node_id || "node")} -> ${escapeHtml(arrayify(item.capabilities).join(", ") || "No mapped capabilities")}</li>`).join("") || "<li>No capability mappings recorded.</li>"}</ul></div>
    `,
    "Capability assembly"
  );
  const memoryStrategy = renderConfigSection(
    "Memory Strategy",
    "This section explains what the system treats as facts, assumptions, open questions, and preserved memory structures for later sessions.",
    `
      <div><strong>Validated facts</strong><ul class="bullet-list">${arrayify(config.cognitive_state?.validated_facts).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No validated facts recorded.</li>"}</ul></div>
      <div><strong>Active assumptions</strong><ul class="bullet-list">${arrayify(config.cognitive_state?.active_assumptions).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No active assumptions recorded.</li>"}</ul></div>
      <div><strong>Open questions</strong><ul class="bullet-list">${arrayify(config.cognitive_state?.open_questions).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No open questions recorded.</li>"}</ul></div>
      <div><strong>System memory schemas</strong><ul class="bullet-list">${Object.entries(config.prewire_schemas || {}).map(([key, value]) => `<li>${escapeHtml(key)} | ${escapeHtml(value.policy_schema || value.schema || "configured")}</li>`).join("") || "<li>No prewired memory schemas recorded.</li>"}</ul></div>
    `,
    "Memory strategy"
  );
  const governance = renderConfigSection(
    "Session And Governance",
    "This section explains where human review is required, where confirmation gates exist, and how the system decides whether to continue or stop.",
    `
      <div><strong>Current governance view</strong><p>${escapeHtml(config.governance?.why_current_state || "No governance narrative recorded.")}</p></div>
      <div><strong>Latest review state</strong><p>${escapeHtml(config.governance?.latest_review || "No review status recorded.")}</p></div>
      <div><strong>Why the current role is active</strong><p>${escapeHtml(config.governance?.why_next_role || config.governance?.why_current_state || "No next-role explanation recorded.")}</p></div>
      <div><strong>Governance schemas</strong><ul class="bullet-list">${Object.entries(config.prewire_schemas?.governance || {}).map(([key, value]) => `<li>${escapeHtml(key)}: ${escapeHtml(String(value))}</li>`).join("") || "<li>No governance schema recorded.</li>"}</ul></div>
    `,
    "Session and governance"
  );
  return shell(`
    ${renderFlash()}
    ${compatibility}
    ${renderConfigSummary(config)}
    <section class="config-layout">
      ${projectDefinition}
      ${workflowDefinition}
      ${roleSystem}
      ${capabilityAssembly}
      ${memoryStrategy}
      ${governance}
    </section>
  `, projectId, "config");
}

async function renderLanding() {
  const payload = await apiFetch("/api/app/landing");
  appState.landingPayload = payload;
  const presets = payload.mode_presets || [];
  const defaultMode = payload.defaults.preferred_project_mode || presets[0]?.id || "delivery";
  return shell(`
    ${renderFlash()}
    <section class="hero landing-hero">
      <div class="eyebrow">OpenFlow</div>
      <h1>Start a fresh-session workspace that continues from files instead of hidden context.</h1>
      <p class="lede">Pick the kind of work you are doing, seed the project with the materials you already have, and OpenFlow will create the first working surface around the next practical step.</p>
      <div class="hero-grid">
        ${(payload.proof_points || []).map((item) => `<div class="hero-stat"><strong>${escapeHtml(item)}</strong></div>`).join("")}
      </div>
    </section>
    <section class="landing-layout">
      <section class="panel">
        <div class="eyebrow">Choose Mode</div>
        <h2>Start from the type of work you are actually doing</h2>
        <div class="mode-grid">
          ${presets.map((item) => `
            <button
              type="button"
              class="mode-card ${item.id === defaultMode ? "active" : ""}"
              data-mode-preset="${escapeHtml(item.id)}"
              data-goal="${escapeHtml(item.goal)}"
              data-prompt="${escapeHtml(item.initial_prompt)}"
            >
              <span class="mode-label">${escapeHtml(item.label)}</span>
              <strong>${escapeHtml(item.headline)}</strong>
              <span class="microcopy">${escapeHtml(item.summary)}</span>
            </button>
          `).join("")}
        </div>
      </section>
      <section class="panel">
        <div class="eyebrow">Create Workspace</div>
        <h2>Start from the materials you already have</h2>
        <form id="bootstrap-form" class="form-grid">
          <input type="hidden" name="preferred_project_mode" value="${escapeHtml(defaultMode)}" />
          <div class="field"><label>Workspace name</label><input type="text" name="project_name" value="${escapeHtml(payload.defaults.project_name)}" /></div>
          <div class="field"><label>What should this workspace finish?</label><input type="text" name="goal" value="${escapeHtml(payload.defaults.goal)}" /></div>
          <div class="field"><label>What materials, context, or constraints are already available?</label><textarea name="initial_prompt">${escapeHtml(payload.defaults.initial_prompt)}</textarea></div>
          <div class="actions">
            <button type="submit">Create Workspace</button>
            <button id="landing-demo-link" type="button" class="secondary">Use example inputs</button>
          </div>
        </form>
      </section>
      <aside class="panel">
        <div class="eyebrow">What the system makes visible</div>
        <h2>Only two primary surfaces</h2>
        <ul class="bullet-list">
          <li>Chat Workspace: what to do now, why this is the next step, and whether the project can continue.</li>
          <li>System Config: how the project is configured, constrained, and wired for fresh sessions.</li>
        </ul>
      </aside>
    </section>
  `);
}

function renderLoading(projectId = "", active = "") {
  appRoot.innerHTML = shell(`
    <section class="panel loading-panel">
      <div class="eyebrow">Loading</div>
      <h2>Preparing the workspace</h2>
      <p class="muted">Reading the latest project files, handoffs, memory, and saved execution state.</p>
    </section>
  `, projectId, active);
}

function renderError(error, projectId = "", active = "") {
  appRoot.innerHTML = shell(`
    <section class="panel error-panel">
      <div class="eyebrow">Error</div>
      <h2>Could not load this surface</h2>
      <p>${escapeHtml(error.message || String(error))}</p>
      <div class="actions">
        <button type="button" onclick="window.location.reload()">Reload</button>
        <a class="button secondary" href="/app" data-nav>Back to landing</a>
      </div>
    </section>
  `, projectId, active);
}

function bindLandingInteractions() {
  const form = document.getElementById("bootstrap-form");
  if (!form) {
    return;
  }
  const modeCards = [...document.querySelectorAll("[data-mode-preset]")];
  const hiddenMode = form.querySelector('input[name="preferred_project_mode"]');
  const goalInput = form.querySelector('input[name="goal"]');
  const promptInput = form.querySelector('textarea[name="initial_prompt"]');

  function activateMode(card, preserveContent = false) {
    modeCards.forEach((item) => item.classList.toggle("active", item === card));
    hiddenMode.value = card.dataset.modePreset || "delivery";
    if (!preserveContent) {
      goalInput.value = card.dataset.goal || "";
      promptInput.value = card.dataset.prompt || "";
    }
  }

  modeCards.forEach((card) => {
    card.addEventListener("click", () => activateMode(card));
  });

  const demoButton = document.getElementById("landing-demo-link");
  if (demoButton) {
    demoButton.addEventListener("click", () => {
      const activeCard = modeCards.find((card) => card.classList.contains("active")) || modeCards[0];
      if (activeCard) {
        activateMode(activeCard);
      }
      form.querySelector('input[name="project_name"]').value = "OpenFlow Workspace";
    });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitButton = form.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    try {
      const payload = {
        project_name: form.project_name.value.trim(),
        goal: form.goal.value.trim(),
        initial_prompt: form.initial_prompt.value.trim(),
        preferred_project_mode: hiddenMode.value,
      };
      const response = await apiFetch("/projects/bootstrap", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setFlash("success", "Workspace created. OpenFlow is now using the new two-surface layout.");
      navigate(`/app/projects/${response.project_id}`);
    } catch (error) {
      setFlash("error", error.message || "Could not create the workspace.");
      render();
    } finally {
      submitButton.disabled = false;
    }
  });
}

function bindWorkspaceActions(projectId) {
  const startForm = document.querySelector("[data-start-session]");
  if (startForm) {
    startForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      try {
        await apiFetch("/sessions", {
          method: "POST",
          body: JSON.stringify({
            project_id: projectId,
            role_name: form.role_name.value,
            objective: form.objective.value,
            input_files: splitLines(form.input_files.value),
          }),
        });
        setFlash("success", "The next work package has been started.");
        render();
      } catch (error) {
        setFlash("error", error.message || "Could not start the next work package.");
        render();
      } finally {
        button.disabled = false;
      }
    });
  }

  const chatForm = document.getElementById("chat-message-form");
  if (chatForm) {
    chatForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = chatForm.querySelector('button[type="submit"]');
      button.disabled = true;
      try {
        const result = await apiFetch(`/api/app/projects/${projectId}/chat/messages`, {
          method: "POST",
          body: JSON.stringify({
            project_id: projectId,
            session_id: chatForm.session_id.value || null,
            message: chatForm.message.value,
            mode: chatForm.mode.value,
            action: chatForm.action.value,
          }),
        });
        setFlash("success", result.assistant_message || "The current session has been updated.");
        appRoot.innerHTML = renderWorkspace(result.updated_chat_workspace, window.location.pathname);
        bindForms(projectId);
      } catch (error) {
        setFlash("error", error.message || "Could not send the message to the current session.");
        render();
      } finally {
        button.disabled = false;
      }
    });
  }

  document.querySelectorAll("[data-advance-handoff]").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await apiFetch(`/handoffs/${button.dataset.advanceHandoff}/advance`, { method: "POST" });
        setFlash("success", "The latest handoff has been advanced.");
        render();
      } catch (error) {
        setFlash("error", error.message || "Could not advance the handoff.");
        render();
      } finally {
        button.disabled = false;
      }
    });
  });

  document.querySelectorAll("[data-review-handoff]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitter = event.submitter;
      if (submitter) {
        submitter.disabled = true;
      }
      try {
        await apiFetch(`/handoffs/${form.dataset.reviewHandoff}/review`, {
          method: "POST",
          body: JSON.stringify({
            action: submitter?.value || "approve",
            note: form.note.value,
          }),
        });
        setFlash("success", "The handoff review has been saved.");
        render();
      } catch (error) {
        setFlash("error", error.message || "Could not save the review.");
        render();
      } finally {
        if (submitter) {
          submitter.disabled = false;
        }
      }
    });
  });

  document.querySelectorAll("[data-complete-session]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      try {
        await apiFetch(`/sessions/${form.dataset.completeSession}/complete`, {
          method: "POST",
          body: JSON.stringify({
            session_summary: form.session_summary.value,
            next_role_recommendation: form.next_role_recommendation.value,
            next_role_reason: form.next_role_reason.value,
            required_input_files: splitLines(form.required_input_files.value),
            success_criteria: splitLines(form.success_criteria.value),
            risks: splitLines(form.risks.value),
            transcript_note: form.transcript_note.value,
            followup_actions: splitLines(form.followup_actions.value),
            task_status_changes: splitLines(form.task_status_changes.value),
            review_outcome: form.review_outcome.value,
            acceptance_status: form.acceptance_status.value,
          }),
        });
        setFlash("success", "The current role has been completed and the next handoff was saved.");
        render();
      } catch (error) {
        setFlash("error", error.message || "Could not complete the current role.");
        render();
      } finally {
        button.disabled = false;
      }
    });
  });
}

function bindForms(projectId = "") {
  bindLandingInteractions();
  if (projectId) {
    bindWorkspaceActions(projectId);
  }
}

async function handleRenderPath() {
  const pathname = window.location.pathname.replace(/\/+$/, "") || "/app";
  if (pathname === "/app") {
    return renderLanding();
  }

  const match = pathname.match(/^\/app\/projects\/([^/]+)(?:\/(.*))?$/);
  if (!match) {
    return shell(`
      ${renderFlash()}
      <section class="panel error-panel">
        <div class="eyebrow">Not Found</div>
        <h2>This app route does not exist</h2>
        <p>OpenFlow now uses only Chat Workspace and System Config as formal surfaces.</p>
        <div class="actions">
          <a class="button" href="/app" data-nav>Open landing</a>
        </div>
      </section>
    `);
  }

  const projectId = decodeURIComponent(match[1]);
  const tail = match[2] || "";
  const useConfig = tail === "config" || tail.startsWith("workflow") || tail.startsWith("decisions");
  renderLoading(projectId, useConfig ? "config" : "workspace");
  if (useConfig) {
    const config = await apiFetch(`/api/app/projects/${projectId}/config`);
    return renderSystemConfig(config, pathname);
  }
  const chat = await apiFetch(`/api/app/projects/${projectId}/chat`);
  return renderWorkspace(chat, pathname);
}

async function render() {
  try {
    const html = await handleRenderPath();
    appRoot.innerHTML = html;
    const match = window.location.pathname.match(/^\/app\/projects\/([^/]+)/);
    bindForms(match ? decodeURIComponent(match[1]) : "");
    window.scrollTo({ top: 0, behavior: "auto" });
  } catch (error) {
    const match = window.location.pathname.match(/^\/app\/projects\/([^/]+)/);
    renderError(error, match ? decodeURIComponent(match[1]) : "", window.location.pathname.includes("/config") ? "config" : "workspace");
  }
}

render();
