const appRoot = document.getElementById("app");

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

function getModeUi(mode) {
  const map = {
    research: {
      label: "Research Workspace",
      kicker: "Collect, compare, synthesize",
      narrative: "Use this when the real problem is scattered materials, weak synthesis, or unclear evidence for the next decision.",
      highlights: ["broad material intake", "source-to-summary traceability", "evidence-backed next step"],
    },
    experience: {
      label: "Experience Workspace",
      kicker: "Clarify the journey, reduce friction",
      narrative: "Use this when the work feels too complex, too technical, or not attractive enough for ordinary users.",
      highlights: ["simpler first-run flow", "clearer page sequencing", "higher product attraction"],
    },
    multimodal: {
      label: "Multimodal Workspace",
      kicker: "Connect image, text, planning, execution",
      narrative: "Use this when the workflow needs to move from multimodal input into a plan, then into runnable execution with preserved continuity.",
      highlights: ["image-plus-text intake", "plan-to-execution loop", "file-driven continuity"],
    },
    delivery: {
      label: "Delivery Workspace",
      kicker: "Turn intent into executable work",
      narrative: "Use this when the work already has enough direction and the main need is clear decomposition, execution, and review.",
      highlights: ["visible work slices", "role-based execution", "handoff and review loop"],
    },
  };
  return map[mode] || map.delivery;
}

function statline(items) {
  return `<div class="statline">${items.map((item) => `<div class="stat">${escapeHtml(item)}</div>`).join("")}</div>`;
}

function chips(items) {
  return `<div class="chips">${items.map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("")}</div>`;
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await response.text() || `Request failed: ${response.status}`);
  }
  return response.json();
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

function shell(content, projectId = "") {
  const pathname = window.location.pathname;
  const sessionActive = /^\/app\/projects\/[^/]+\/sessions\/[^/]+$/.test(pathname);
  const sidebar = projectId
    ? `
      <aside class="sidebar">
        <div class="sidebar-card">
          <div class="eyebrow">Project</div>
          <h3>${escapeHtml(projectId)}</h3>
          <div class="route-list">
            ${[
              ["Welcome", `/app/projects/${projectId}/welcome`],
              ["Workspace", `/app/projects/${projectId}`],
              ["Knowledge", `/app/projects/${projectId}/knowledge`],
              ["Tasks", `/app/projects/${projectId}/tasks`],
              ["Workflow", `/app/projects/${projectId}/workflow`],
              ["Decisions", `/app/projects/${projectId}/decisions`],
            ]
              .map(([label, href]) => `<a class="${pathname === href ? "active" : ""}" href="${href}" data-nav>${label}</a>`)
              .join("")}
            <a class="${sessionActive ? "active" : ""}" href="#" aria-disabled="true">Session</a>
          </div>
        </div>
        <div class="sidebar-card">
          <div class="eyebrow">Mode</div>
          <p class="muted">This frontend runs in parallel with the existing server-rendered pages while keeping the same FastAPI business logic.</p>
        </div>
      </aside>
    `
    : "";
  return `
    <div class="app-shell">
      <div class="topbar">
        <div class="brand">
          <div class="brand-title"><a href="/app" data-nav>OpenFlow App</a></div>
          <div class="brand-subtitle">Independent workspace shell with file-based continuity</div>
        </div>
        <div class="nav">
          <a href="/" target="_blank" rel="noreferrer">Legacy Pages</a>
          <a href="/blueprint" target="_blank" rel="noreferrer">Blueprint API</a>
        </div>
      </div>
      ${projectId ? `<div class="shell">${sidebar}<div class="page">${content}</div></div>` : `<div class="page">${content}</div>`}
    </div>
  `;
}

async function renderLanding() {
  const payload = await apiFetch("/api/app/landing");
  const presets = payload.mode_presets || [];
  const defaultMode = payload.defaults.preferred_project_mode || (presets[0] && presets[0].id) || "delivery";
  return `
    <section class="hero">
      <div class="grid grid-hero">
        <div class="hero-copy">
          <div class="eyebrow">AI Collaboration Workspace</div>
          <h1>Choose how this work should run before the system starts splitting roles and sessions.</h1>
          <p class="lede">OpenFlow is not a single long chat. Each role starts fresh. Continuity survives through files, handoffs, knowledge, decisions, and timeline records that every later session can read back.</p>
          ${statline(payload.proof_points)}
          <div class="hero-note">
            <strong>What changes here</strong>
            <p class="muted">Pick a work mode first so the workspace starts with a better first role, better defaults, and less unnecessary complexity.</p>
          </div>
        </div>
        <div class="panel story-panel">
          <div class="eyebrow">Why It Feels Different</div>
          <div class="story-list">
            <div class="story-item"><strong>Fresh sessions</strong><p class="microcopy">Roles never inherit hidden chat state.</p></div>
            <div class="story-item"><strong>Visible memory</strong><p class="microcopy">Files, decisions, and handoffs stay inspectable.</p></div>
            <div class="story-item"><strong>Clear next step</strong><p class="microcopy">Recommendations stay tied to project records.</p></div>
            <div class="story-item"><strong>Recoverable workflow</strong><p class="microcopy">Review, changes, and replan paths remain explicit.</p></div>
          </div>
        </div>
      </div>
    </section>
    <section class="grid grid-2">
      <article class="panel">
        <div class="eyebrow">Choose Mode</div>
        <h2>Start from the kind of work you are actually doing</h2>
        <div class="mode-grid">
          ${presets.map((item) => `
            <button
              type="button"
              class="mode-card ${item.id === defaultMode ? "active" : ""}"
              data-mode-preset="${escapeHtml(item.id)}"
              data-goal="${escapeHtml(item.goal)}"
              data-prompt="${escapeHtml(item.initial_prompt)}"
              data-role="${escapeHtml(item.starter_role)}"
            >
              <span class="mode-label">${escapeHtml(item.label)}</span>
              <strong>${escapeHtml(item.headline)}</strong>
              <span class="microcopy">${escapeHtml(item.summary)}</span>
            </button>
          `).join("")}
        </div>
      </article>
      <article class="panel">
        <div class="eyebrow">Create Workspace</div>
        <h2>Start from the materials you already have</h2>
        <form id="bootstrap-form" class="form-grid">
          <input type="hidden" name="preferred_project_mode" value="${escapeHtml(defaultMode)}" />
          <div class="field"><label>Workspace name</label><input name="project_name" type="text" value="${escapeHtml(payload.defaults.project_name)}" /></div>
          <div class="field"><label>What should this workspace finish?</label><input name="goal" type="text" value="${escapeHtml(payload.defaults.goal)}" /></div>
          <div class="field"><label>What materials, context, or constraints are already available?</label><textarea name="initial_prompt">${escapeHtml(payload.defaults.initial_prompt)}</textarea></div>
          <div class="actions">
            <button type="submit">Create Workspace</button>
            <button id="landing-demo-link" class="secondary" type="button">Use Example Inputs</button>
          </div>
        </form>
      </article>
      <aside class="grid">
        <section class="panel">
          <div class="eyebrow">Common Starts</div>
          <h3>What people usually bring in</h3>
          ${chips(payload.examples)}
        </section>
        <section class="panel">
          <div class="eyebrow">What You See Next</div>
          <p class="muted">After the first submit, the workspace shifts into one main track: current goal, organized materials, current progress, and the suggested next step.</p>
          ${chips(["Current goal", "Organized materials", "Current progress", "Suggested next step"])}
        </section>
        <section class="panel">
          <div class="eyebrow">Advanced Surfaces</div>
          <p class="muted">The main path stays simple, while workflow, materials, tasks, and governance remain accessible underneath when the project needs them.</p>
          ${chips(payload.blueprint.demo_sections)}
        </section>
      </aside>
    </section>
  `;
}

function renderFirstStepCard(projectId, defaults) {
  return `
    <section class="panel">
      <div class="eyebrow">Start First Work Step</div>
      <h2>Create the first practical step from this workspace</h2>
      <form class="form-grid" data-first-step="${projectId}">
        <div class="field"><label>Who should work on this first?</label><input name="role_name" type="text" value="${escapeHtml(defaults.role_name)}" /></div>
        <div class="field"><label>What should this first step accomplish?</label><textarea name="objective">${escapeHtml(defaults.objective)}</textarea></div>
        <div class="field"><label>Which materials should it read first?</label><textarea name="input_files">${escapeHtml(defaults.input_files)}</textarea></div>
        <div class="actions">
          <button type="submit">Start First Work Step</button>
          <a class="button secondary" href="/app/projects/${projectId}/knowledge" data-nav>Review Materials First</a>
        </div>
      </form>
    </section>
  `;
}

function renderReviewForm(projectId, handoffId, sessionId = "") {
  return `
    <form class="form-grid" data-review-handoff="${handoffId}" data-project="${projectId}" data-session="${sessionId}">
      <div class="field"><label>Review note</label><textarea name="note">Record what should happen next before this step continues.</textarea></div>
      <div class="actions">
        <button type="submit" name="action" value="approve">Continue</button>
        <button class="secondary" type="submit" name="action" value="changes_requested">Needs Changes</button>
        <button class="secondary" type="submit" name="action" value="replan_required">Replan</button>
      </div>
    </form>
  `;
}

async function renderWelcome(projectId) {
  const { summary, first_step_defaults } = await apiFetch(`/api/app/projects/${projectId}/welcome`);
  const recommendation = summary.recommendation;
  const handoff = summary.latest_handoff;
  const nextStep = summary.next_step;
  const modeUi = getModeUi(summary.state.project_mode);
  const actionArea = handoff && nextStep.state === "ready"
    ? `<button type="button" data-advance-handoff="${handoff.handoff_id}" data-project="${projectId}">Continue Recommended Step</button>
       <a class="button secondary" href="/app/projects/${projectId}" data-nav>Open Workspace</a>`
    : handoff && nextStep.state === "review_needed"
      ? `<a class="button" href="/app/projects/${projectId}" data-nav>Open Workspace</a>
         <a class="button secondary" href="/app/projects/${projectId}/workflow" data-nav>Open Review Context</a>`
      : nextStep.state === "research_gap"
        ? `<a class="button" href="/app/projects/${projectId}/knowledge" data-nav>Organize Materials</a>`
        : `<a class="button secondary" href="/app/projects/${projectId}" data-nav>Open Workspace</a>`;
  return `
    <section class="hero">
      <div class="eyebrow">Workspace Ready</div>
      <h1>${escapeHtml(summary.project.project_name)} is ready for the next action.</h1>
      <p class="lede">${escapeHtml(summary.project.goal)}</p>
      ${statline([
        `Work type: ${summary.state.project_type_label}`,
        `Stage: ${summary.project_stage}`,
        `Organized materials: ${summary.materials.organized_material_count}`,
        `Current progress: ${summary.governance.latest_review}`,
      ])}
    </section>
    <section class="grid grid-2">
      <article class="grid">
        <section class="panel">
          <div class="eyebrow">${escapeHtml(modeUi.label)}</div>
          <h2>${escapeHtml(modeUi.kicker)}</h2>
          <p class="muted">${escapeHtml(modeUi.narrative)}</p>
          ${chips(modeUi.highlights)}
        </section>
        <section class="panel">
          <div class="eyebrow">Suggested Next Step</div>
          <h2>Start where the current records say the work should continue</h2>
          <div class="callout">
            <strong>${escapeHtml(recommendation.recommended_role)}</strong>
            <p class="muted">${escapeHtml(recommendation.recommended_reason)}</p>
            <p class="microcopy">Why the system recommends this: ${escapeHtml(summary.why_next_role)}</p>
          </div>
          <div class="list">
            <div class="list-item"><strong>Why you are starting here</strong><p>${escapeHtml(summary.governance.why_current_state)}</p></div>
            <div class="list-item"><strong>Recommended action</strong><p>${escapeHtml(nextStep.message)}</p><div class="actions">${actionArea}</div></div>
          </div>
        </section>
        ${!handoff && nextStep.state !== "research_gap" ? renderFirstStepCard(projectId, first_step_defaults) : ""}
      </article>
      <aside class="grid">
        <section class="panel"><div class="eyebrow">Goal</div><h3>What this workspace is trying to finish</h3><p>${escapeHtml(summary.project.goal)}</p></section>
        <section class="panel"><div class="eyebrow">Materials</div><h3>What is already organized</h3><p>${escapeHtml(summary.materials.summary)}</p></section>
        <section class="panel"><div class="eyebrow">Progress</div><h3>Current state in ordinary work language</h3><p>${escapeHtml(summary.governance.why_current_state)}</p></section>
      </aside>
    </section>
  `;
}

async function renderProject(projectId) {
  const { summary, timeline } = await apiFetch(`/api/app/projects/${projectId}/workspace`);
  const handoff = summary.latest_handoff;
  const recommendation = summary.recommendation;
  const nextStep = summary.next_step;
  const modeUi = getModeUi(summary.state.project_mode);
  const actionArea = handoff && nextStep.state === "review_needed"
    ? renderReviewForm(projectId, handoff.handoff_id)
    : handoff && nextStep.state === "ready"
      ? `<button type="button" data-advance-handoff="${handoff.handoff_id}" data-project="${projectId}">${escapeHtml(nextStep.primary_label)}</button>`
      : nextStep.state === "research_gap"
        ? `<a class="button" href="/app/projects/${projectId}/knowledge" data-nav>${escapeHtml(nextStep.primary_label)}</a>`
        : nextStep.state === "blocked"
          ? `<a class="button" href="/app/projects/${projectId}/tasks" data-nav>${escapeHtml(nextStep.primary_label)}</a>`
          : `<a class="button secondary" href="/app/projects/${projectId}/knowledge" data-nav>Organize Materials</a>`;
  return `
    <section class="hero">
      <div class="eyebrow">Workspace Overview</div>
      <h1>${escapeHtml(summary.project.project_name)}</h1>
      <p class="lede">${escapeHtml(summary.project.goal)}</p>
      ${statline([
        `Work type: ${summary.state.project_type_label}`,
        `Stage: ${summary.project_stage}`,
        `Current progress: ${summary.governance.latest_review}`,
        `Suggested next owner: ${summary.next_role || "n/a"}`,
        `Organized materials: ${summary.materials.organized_material_count}`,
      ])}
    </section>
    <section class="grid grid-2">
      <article class="grid">
        <section class="panel">
          <div class="eyebrow">${escapeHtml(modeUi.label)}</div>
          <h2>${escapeHtml(modeUi.kicker)}</h2>
          <p class="muted">${escapeHtml(modeUi.narrative)}</p>
          ${chips(modeUi.highlights)}
        </section>
        <section class="panel">
          <div class="eyebrow">Main Track</div>
          <h2>Suggested Next Step</h2>
          <div class="callout">
            <strong>${escapeHtml(recommendation.recommended_role)}</strong>
            <p class="muted">${escapeHtml(recommendation.recommended_reason)}</p>
            <p class="microcopy">Why the system recommends this: ${escapeHtml(summary.why_next_role)}</p>
          </div>
          <div class="list">
            <div class="list-item"><strong>Current state</strong><p>${escapeHtml(summary.governance.why_current_state)}</p><p class="microcopy">Blocked now: ${escapeHtml(summary.blocked_now || "No explicit block recorded.")}</p></div>
            <div class="list-item"><strong>Recommended action</strong><p>${escapeHtml(nextStep.message)}</p><div class="actions">${actionArea}</div></div>
          </div>
        </section>
        <section class="panel">
          <div class="eyebrow">Progress Snapshot</div>
          <h2>Current goal and work board snapshot</h2>
          <div class="list">
            <div class="list-item"><strong>Material status</strong><p>${escapeHtml(summary.materials.summary)}</p></div>
            ${summary.state.task_tree.map((task) => `<div class="list-item"><strong>${escapeHtml(task.title)}</strong><p class="microcopy">${escapeHtml(task.status)} | ${escapeHtml(task.owner_role)} | Priority ${task.priority}</p>${task.blocked_reason ? `<p>Blocked: ${escapeHtml(task.blocked_reason)}</p>` : ""}</div>`).join("")}
          </div>
        </section>
      </article>
      <aside class="grid">
        <section class="panel">${summary.latest_session ? `<div class="eyebrow">Current Progress</div><h3>${escapeHtml(summary.latest_session.role_name)}</h3><p class="muted">${escapeHtml(summary.latest_session.status)}</p><a class="button secondary" href="/app/projects/${projectId}/sessions/${summary.latest_session.session_id}" data-nav>Open work step detail</a>` : `<p class="muted">No session exists yet.</p>`}</section>
        <section class="panel"><div class="eyebrow">Research Slots</div>${chips(summary.state.research_slots)}</section>
        <section class="panel"><div class="eyebrow">Timeline</div><div class="list">${timeline.slice(0, 3).map((item) => `<div class="result-block"><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.summary)}</p><p class="microcopy">Because: ${escapeHtml(item.because)}</p></div>`).join("")}</div></section>
      </aside>
    </section>
  `;
}

function selectHtml(name, values, selected) {
  return `
    <select name="${name}">
      <option value="">All</option>
      ${values.map((value) => `<option value="${escapeHtml(value)}" ${selected === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}
    </select>
  `;
}

async function renderSession(projectId, sessionId) {
  const { payload, complete_defaults } = await apiFetch(`/api/app/projects/${projectId}/session/${sessionId}`);
  const handoff = payload.handoff;
  const recommendation = payload.recommendation;
  return `
    <section class="hero">
      <div class="eyebrow">Work Step Detail</div>
      <h1>${escapeHtml(payload.session.role_name)}</h1>
      <p class="lede">${escapeHtml(payload.session.objective)}</p>
      ${statline([
        "Fresh step",
        `Stage: ${payload.project_stage}`,
        `Materials declared: ${payload.session.input_files.length}`,
        `Notes captured: ${payload.transcript.length}`,
        `Suggested next step ready: ${payload.handoff ? "yes" : "no"}`,
      ])}
    </section>
    <section class="grid grid-2">
      <article class="grid">
        <section class="panel">
          <div class="eyebrow">Materials</div>
          <h2>Materials used and preserved notes</h2>
          <div class="list">
            <div class="list-item"><strong>Materials used</strong>${payload.session.input_files.length ? `<p>${payload.session.input_files.map((item) => `<code>${escapeHtml(item)}</code>`).join("<br />")}</p>` : `<p class="muted">No input files declared.</p>`}</div>
            <div class="list-item"><strong>Captured notes</strong><p class="muted">${payload.transcript.length} transcript entries</p></div>
          </div>
        </section>
        <section class="panel">
          <div class="eyebrow">Next Step</div>
          <h2>Saved result and next action</h2>
          <div class="callout">
            <strong>${escapeHtml(recommendation.recommended_role)}</strong>
            <p class="muted">${escapeHtml(recommendation.recommended_reason)}</p>
            <p class="microcopy">${escapeHtml(payload.next_step.message)}</p>
          </div>
          <div class="list">
            ${handoff ? `<div class="list-item"><strong>Handoff state</strong><p class="microcopy">Advanced status: ${escapeHtml(handoff.acceptance_status || "not_set")} | Review: ${escapeHtml(handoff.review_outcome || "not_set")}</p>${payload.next_step.state === "review_needed" ? renderReviewForm(projectId, handoff.handoff_id, sessionId) : ""}${payload.next_step.state === "ready" ? `<div class="actions"><button type="button" data-advance-handoff="${handoff.handoff_id}" data-project="${projectId}">${escapeHtml(payload.next_step.primary_label)}</button></div>` : ""}</div>` : `<div class="list-item"><strong>No saved outcome has been written yet.</strong><p class="muted">Complete the work step to produce a handoff and next-step recommendation.</p></div>`}
          </div>
        </section>
        <section class="panel">
          <div class="eyebrow">Complete Step</div>
          <h2>Write the preserved result and next handoff</h2>
          <form class="form-grid" data-complete-session="${sessionId}" data-project="${projectId}">
            <div class="field"><label>What did this step complete?</label><textarea name="session_summary">${escapeHtml(complete_defaults.session_summary)}</textarea></div>
            <div class="field"><label>What kind of help should continue next?</label><input type="text" name="next_role_recommendation" value="${escapeHtml(complete_defaults.next_role_recommendation)}" /></div>
            <div class="field"><label>Why is that the right next step?</label><textarea name="next_role_reason">${escapeHtml(complete_defaults.next_role_reason)}</textarea></div>
            <div class="field"><label>What materials should the next step read?</label><textarea name="required_input_files">${escapeHtml(complete_defaults.required_input_files.join("\n"))}</textarea></div>
            <div class="field"><label>What would a good next result look like?</label><textarea name="success_criteria">${escapeHtml(complete_defaults.success_criteria.join("\n"))}</textarea></div>
            <div class="field"><label>Risks or blockers</label><textarea name="risks">${escapeHtml(complete_defaults.risks.join("\n"))}</textarea></div>
            <div class="field"><label>Most important note to preserve</label><textarea name="transcript_note">${escapeHtml(complete_defaults.transcript_note)}</textarea></div>
            <div class="field"><label>Follow-up actions</label><textarea name="followup_actions">${escapeHtml(complete_defaults.followup_actions.join("\n"))}</textarea></div>
            <details><summary>Advanced controls</summary><div class="form-grid" style="margin-top:12px"><div class="field"><label>Task status changes</label><textarea name="task_status_changes">${escapeHtml(complete_defaults.task_status_changes.join("\n"))}</textarea></div><div class="field"><label>Review outcome</label><input type="text" name="review_outcome" value="${escapeHtml(complete_defaults.review_outcome)}" /></div><div class="field"><label>Acceptance status</label><input type="text" name="acceptance_status" value="${escapeHtml(complete_defaults.acceptance_status)}" /></div></div></details>
            <div class="actions"><button type="submit">Complete Step And Write Handoff</button></div>
          </form>
        </section>
      </article>
      <aside class="grid">
        <section class="panel"><div class="eyebrow">Actions</div><div class="actions"><a class="button secondary" href="/app/projects/${projectId}" data-nav>Back To Workspace</a><a class="button secondary" href="/app/projects/${projectId}/knowledge" data-nav>Open Knowledge</a></div></section>
      </aside>
    </section>
  `;
}

async function renderKnowledge(projectId) {
  const params = new URLSearchParams(window.location.search);
  const query = params.toString();
  const { payload } = await apiFetch(`/api/app/projects/${projectId}/knowledge${query ? `?${query}` : ""}`);
  return `
    <section class="hero">
      <div class="eyebrow">Materials Center</div>
      <h1>Materials for ${escapeHtml(projectId)}</h1>
      <p class="lede">${escapeHtml(payload.materials.summary)}</p>
      ${statline([`Knowledge items: ${payload.materials.knowledge_count}`, `Organized materials: ${payload.materials.organized_material_count}`, `Material groups: ${payload.materials.research_group_count}`])}
    </section>
    <section class="grid grid-2">
      <article class="grid">
        <section class="panel">
          <div class="eyebrow">Filters</div>
          <h2>Find materials</h2>
          <form class="form-grid" data-knowledge-filter="${projectId}">
            <div class="field"><label>Search</label><input type="text" name="q" value="${escapeHtml(payload.filters.q || "")}" /></div>
            <div class="field"><label>Material group</label>${selectHtml("source_family", payload.available_filter_values.source_families, payload.filters.source_family)}</div>
            <div class="field"><label>Material kind</label>${selectHtml("entry_kind", payload.available_filter_values.entry_kinds, payload.filters.entry_kind)}</div>
            <div class="field"><label>Adoption status</label>${selectHtml("adoption_status", payload.available_filter_values.adoption_statuses, payload.filters.adoption_status)}</div>
            <label><input type="checkbox" name="linked_only" value="true" ${payload.filters.linked_only ? "checked" : ""} /> Only show decision-linked materials</label>
            <div class="actions"><button type="submit">Apply Filters</button></div>
          </form>
          <p class="microcopy">Showing ${payload.filtered_count} filtered items.</p>
        </section>
        <section class="panel">
          <div class="eyebrow">Operate</div>
          <h2>Organize materials into reusable project memory</h2>
          <form class="form-grid" data-organize-materials="${projectId}">
            <div class="field"><label>Material set name</label><input type="text" name="pack_title" value="${escapeHtml(payload.organize_defaults.pack_title)}" /></div>
            <div class="field"><label>Material group</label><input type="text" name="source_family" value="${escapeHtml(payload.organize_defaults.source_family)}" /></div>
            <div class="field"><label>Where these materials came from</label><input type="text" name="source_ref" value="${escapeHtml(payload.organize_defaults.source_ref)}" /></div>
            <div class="field"><label>Collected raw material</label><textarea name="raw_notes">${escapeHtml(payload.organize_defaults.raw_notes)}</textarea></div>
            <div class="field"><label>What should carry forward</label><textarea name="synthesized_summary">${escapeHtml(payload.organize_defaults.synthesized_summary)}</textarea></div>
            <div class="field"><label>Themes</label><textarea name="themes">knowledge_indexing\nhandoff_governance</textarea></div>
            <div class="field"><label>Decision ids</label><textarea name="decision_ids"></textarea></div>
            <div class="field"><label>Adoption status</label><input type="text" name="adoption_status" value="proposed" /></div>
            <div class="field"><label>Reliability</label><input type="text" name="reliability" value="medium" /></div>
            <div class="field"><label>Relevance</label><input type="text" name="relevance" value="high" /></div>
            <div class="actions"><button type="submit">Organize Materials</button></div>
          </form>
          <details><summary>Organize many materials at once</summary><form class="form-grid" data-organize-batch="${projectId}" style="margin-top:12px"><div class="field"><label>Batch payload</label><textarea name="batch_payload">${escapeHtml(payload.organize_defaults.batch_payload)}</textarea></div><div class="actions"><button type="submit">Organize Many Materials</button></div></form></details>
        </section>
      </article>
      <aside class="grid">
        <section class="panel"><div class="eyebrow">Evolution Feed</div><div class="list">${payload.evolution_feed.map((item) => `<div class="result-block"><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.summary)}</p><p class="microcopy">${escapeHtml(item.source_family)} | ${escapeHtml(item.entry_kind)} | ${escapeHtml(item.adoption_status)}</p></div>`).join("")}</div></section>
        <section class="panel"><div class="eyebrow">Grouped Materials</div>${Object.keys(payload.grouped_views).length ? Object.entries(payload.grouped_views).map(([group, items]) => `<div class="list-item"><strong>${escapeHtml(group)}</strong><p class="muted">${items.map((item) => escapeHtml(item.title)).join("<br />")}</p></div>`).join("") : `<div class="empty">No materials match the current filters.</div>`}</section>
      </aside>
    </section>
  `;
}

async function renderTasks(projectId) {
  const { payload } = await apiFetch(`/api/app/projects/${projectId}/tasks`);
  const modeUi = getModeUi(payload.project_mode);
  return `
    <section class="hero">
      <div class="eyebrow">Work Board</div>
      <h1>Work items for ${escapeHtml(projectId)}</h1>
      ${statline([
        `Mode: ${payload.project_mode}`,
        `Attraction: ${payload.attraction_focus}`,
        `Planned: ${payload.counts.planned}`,
        `Active: ${payload.counts.active}`,
        `Waiting: ${payload.counts.waiting_confirmation}`,
        `Completed: ${payload.counts.completed}`,
      ])}
    </section>
    <section class="panel">
      <div class="eyebrow">${escapeHtml(modeUi.label)}</div>
      <h2>${escapeHtml(modeUi.kicker)}</h2>
      <p class="muted">${escapeHtml(modeUi.narrative)}</p>
    </section>
    <section class="panel">
      <div class="eyebrow">What Matters Most Right Now</div>
      ${chips(payload.execution_priority)}
    </section>
    <section class="panel">
      <div class="eyebrow">Task Board</div>
      <div class="list">${payload.task_tree.map((task) => `<div class="result-block"><strong>${escapeHtml(task.title)}</strong><p class="microcopy">${escapeHtml(task.task_id)} | ${escapeHtml(task.status)} | ${escapeHtml(task.owner_role)} | Priority ${task.priority}</p>${task.success_criteria?.length ? `<p>Success: ${task.success_criteria.map(escapeHtml).join(", ")}</p>` : ""}${task.blocked_reason ? `<p>Blocked: ${escapeHtml(task.blocked_reason)}</p>` : ""}</div>`).join("")}</div>
    </section>
  `;
}

async function renderWorkflow(projectId) {
  const { payload } = await apiFetch(`/api/app/projects/${projectId}/workflow`);
  return `
    <section class="hero">
      <div class="eyebrow">Workflow Graph</div>
      <h1>Workflow for ${escapeHtml(projectId)}</h1>
      ${statline([`Attraction focus: ${payload.attraction_focus}`])}
    </section>
    <section class="grid grid-2">
      <section class="panel"><div class="eyebrow">Stages</div><div class="list">${payload.workflow_blueprint.stages.map((stage) => `<div class="result-block"><strong>${escapeHtml(stage.role_name)}</strong><p class="microcopy">${escapeHtml(stage.stage_id)} | ${escapeHtml(stage.handoff_policy)}</p><p>${escapeHtml(stage.objective)}</p></div>`).join("")}</div></section>
      <section class="panel"><div class="eyebrow">Page Flow</div>${chips(payload.workflow_blueprint.page_flow)}<div class="list" style="margin-top:16px">${payload.governance_gates.map((item) => `<div class="result-block"><strong>Confirm Gate</strong><p>${escapeHtml(item)}</p></div>`).join("")}</div></section>
    </section>
    <section class="panel"><div class="eyebrow">Role Transition Edges</div><div class="list">${payload.workflow_graph.edges.map((edge) => `<div class="result-block"><strong>${escapeHtml(edge.from_node)} -> ${escapeHtml(edge.to_node)}</strong><p class="microcopy">Condition: ${escapeHtml(edge.condition)}</p></div>`).join("")}</div></section>
  `;
}

async function renderDecisions(projectId) {
  const { payload } = await apiFetch(`/api/app/projects/${projectId}/decisions`);
  return `
    <section class="hero">
      <div class="eyebrow">Decision Registry</div>
      <h1>Decisions for ${escapeHtml(projectId)}</h1>
      <p class="lede">Track decision status, rationale, and supporting research from one governance surface.</p>
    </section>
    <section class="panel">
      <div class="list">
        ${payload.decisions.map((item) => `<div class="result-block"><strong>${escapeHtml(item.title)}</strong><p class="microcopy">${escapeHtml(item.decision_id)} | ${escapeHtml(item.status)}</p><p>${escapeHtml(item.rationale)}</p><p class="microcopy">${item.supporting_knowledge.length ? item.supporting_knowledge.map((support) => `${escapeHtml(support.entry_kind)} | ${escapeHtml(support.title)}`).join("<br />") : "No linked research items yet."}</p><form class="actions" data-update-decision="${projectId}" data-decision="${item.decision_id}"><select name="status">${["proposed", "adopted", "rejected", "deferred"].map((status) => `<option value="${status}" ${item.status === status ? "selected" : ""}>${status}</option>`).join("")}</select><button type="submit">Update Decision Status</button></form></div>`).join("")}
      </div>
    </section>
  `;
}

function parseBatchPayload(projectId, batchPayload) {
  const packs = [];
  let current = {};
  for (const rawLine of batchPayload.split("\n")) {
    const line = rawLine.trim();
    if (!line) {
      if (Object.keys(current).length) {
        packs.push(normalizePack(projectId, current));
        current = {};
      }
      continue;
    }
    if (!line.includes(":")) {
      continue;
    }
    const [key, ...rest] = line.split(":");
    current[key.trim()] = rest.join(":").trim();
  }
  if (Object.keys(current).length) {
    packs.push(normalizePack(projectId, current));
  }
  return packs;
}

function normalizePack(projectId, data) {
  return {
    project_id: projectId,
    pack_title: data.pack_title || "Batch pack",
    source_family: data.source_family || "workflow_handoff_methods",
    source_ref: data.source_ref || "batch-input",
    raw_notes: data.raw_notes || "",
    synthesized_summary: data.synthesized_summary || "",
    themes: String(data.themes || "").split(",").map((item) => item.trim()).filter(Boolean),
    decision_ids: String(data.decision_ids || "").split(",").map((item) => item.trim()).filter(Boolean),
    adoption_status: data.adoption_status || "proposed",
    reliability: data.reliability || "medium",
    relevance: data.relevance || "high",
  };
}

function bindForms() {
  const bootstrapForm = document.getElementById("bootstrap-form");
  if (bootstrapForm) {
    const applyModePreset = (button) => {
      document.querySelectorAll("[data-mode-preset]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      bootstrapForm.preferred_project_mode.value = button.dataset.modePreset || "delivery";
      bootstrapForm.goal.value = button.dataset.goal || bootstrapForm.goal.value;
      bootstrapForm.initial_prompt.value = button.dataset.prompt || bootstrapForm.initial_prompt.value;
    };
    document.querySelectorAll("[data-mode-preset]").forEach((button) => {
      button.addEventListener("click", () => applyModePreset(button));
    });
    const demoButton = document.getElementById("landing-demo-link");
    demoButton?.addEventListener("click", () => {
      const activePreset = document.querySelector("[data-mode-preset].active");
      if (activePreset) {
        applyModePreset(activePreset);
      }
      bootstrapForm.project_name.value = "OpenFlow Demo Workspace";
    });
    bootstrapForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(bootstrapForm).entries());
      const payload = await apiFetch("/projects/bootstrap", { method: "POST", body: JSON.stringify(values) });
      navigate(`/app/projects/${payload.project_id}/welcome`);
    });
  }

  document.querySelectorAll("[data-first-step]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const projectId = form.dataset.firstStep;
      const values = Object.fromEntries(new FormData(form).entries());
      const payload = await apiFetch("/sessions", {
        method: "POST",
        body: JSON.stringify({
          project_id: projectId,
          role_name: values.role_name,
          objective: values.objective,
          input_files: splitLines(values.input_files),
        }),
      });
      navigate(`/app/projects/${projectId}/sessions/${payload.session_id}`);
    });
  });

  document.querySelectorAll("[data-advance-handoff]").forEach((button) => {
    button.addEventListener("click", async () => {
      const handoffId = button.dataset.advanceHandoff;
      const projectId = button.dataset.project;
      const payload = await apiFetch(`/handoffs/${handoffId}/advance`, { method: "POST", body: "{}" });
      if (payload.status === "advanced") {
        navigate(`/app/projects/${projectId}/sessions/${payload.session.session_id}`);
      } else {
        navigate(`/app/projects/${projectId}`);
      }
    });
  });

  document.querySelectorAll("[data-review-handoff]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const action = event.submitter?.value || "approve";
      const handoffId = form.dataset.reviewHandoff;
      const projectId = form.dataset.project;
      const sessionId = form.dataset.session;
      const note = new FormData(form).get("note");
      await apiFetch(`/handoffs/${handoffId}/review`, {
        method: "POST",
        body: JSON.stringify({ action, note }),
      });
      navigate(sessionId ? `/app/projects/${projectId}/sessions/${sessionId}` : `/app/projects/${projectId}`);
    });
  });

  document.querySelectorAll("[data-complete-session]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const sessionId = form.dataset.completeSession;
      const projectId = form.dataset.project;
      const values = Object.fromEntries(new FormData(form).entries());
      await apiFetch(`/sessions/${sessionId}/complete`, {
        method: "POST",
        body: JSON.stringify({
          session_summary: values.session_summary,
          next_role_recommendation: values.next_role_recommendation,
          next_role_reason: values.next_role_reason,
          required_input_files: splitLines(values.required_input_files),
          success_criteria: splitLines(values.success_criteria),
          risks: splitLines(values.risks),
          task_status_changes: splitLines(values.task_status_changes),
          review_outcome: values.review_outcome || null,
          acceptance_status: values.acceptance_status || null,
          followup_actions: splitLines(values.followup_actions),
          transcript_note: values.transcript_note || null,
        }),
      });
      navigate(`/app/projects/${projectId}/sessions/${sessionId}`);
    });
  });

  document.querySelectorAll("[data-knowledge-filter]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const projectId = form.dataset.knowledgeFilter;
      const values = new FormData(form);
      const params = new URLSearchParams();
      for (const [key, value] of values.entries()) {
        if (value) {
          params.set(key, value);
        }
      }
      if (!values.get("linked_only")) {
        params.delete("linked_only");
      }
      navigate(`/app/projects/${projectId}/knowledge${params.toString() ? `?${params.toString()}` : ""}`);
    });
  });

  document.querySelectorAll("[data-organize-materials]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const projectId = form.dataset.organizeMaterials;
      const values = Object.fromEntries(new FormData(form).entries());
      await apiFetch("/research-packs", {
        method: "POST",
        body: JSON.stringify({
          project_id: projectId,
          pack_title: values.pack_title,
          source_family: values.source_family,
          source_ref: values.source_ref,
          raw_notes: values.raw_notes,
          synthesized_summary: values.synthesized_summary,
          themes: splitLines(values.themes),
          decision_ids: splitLines(values.decision_ids),
          adoption_status: values.adoption_status,
          reliability: values.reliability,
          relevance: values.relevance,
        }),
      });
      navigate(`/app/projects/${projectId}/knowledge`);
    });
  });

  document.querySelectorAll("[data-organize-batch]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const projectId = form.dataset.organizeBatch;
      const batchPayload = new FormData(form).get("batch_payload");
      await apiFetch("/research-packs/batch", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, packs: parseBatchPayload(projectId, String(batchPayload || "")) }),
      });
      navigate(`/app/projects/${projectId}/knowledge`);
    });
  });

  document.querySelectorAll("[data-update-decision]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const projectId = form.dataset.updateDecision;
      const decisionId = form.dataset.decision;
      const status = new FormData(form).get("status");
      await apiFetch(`/projects/${projectId}/decisions/${decisionId}`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      navigate(`/app/projects/${projectId}/decisions`);
    });
  });
}

async function render() {
  appRoot.innerHTML = shell(`<section class="hero"><p class="muted">Loading OpenFlow App...</p></section>`);
  try {
    const path = window.location.pathname;
    if (path === "/app" || path === "/app/") {
      appRoot.innerHTML = shell(await renderLanding());
    } else {
      const matchers = [
        [/^\/app\/projects\/([^/]+)\/welcome$/, async (match) => shell(await renderWelcome(match[1]), match[1])],
        [/^\/app\/projects\/([^/]+)$/, async (match) => shell(await renderProject(match[1]), match[1])],
        [/^\/app\/projects\/([^/]+)\/sessions\/([^/]+)$/, async (match) => shell(await renderSession(match[1], match[2]), match[1])],
        [/^\/app\/projects\/([^/]+)\/knowledge$/, async (match) => shell(await renderKnowledge(match[1]), match[1])],
        [/^\/app\/projects\/([^/]+)\/tasks$/, async (match) => shell(await renderTasks(match[1]), match[1])],
        [/^\/app\/projects\/([^/]+)\/workflow$/, async (match) => shell(await renderWorkflow(match[1]), match[1])],
        [/^\/app\/projects\/([^/]+)\/decisions$/, async (match) => shell(await renderDecisions(match[1]), match[1])],
      ];
      let handled = false;
      for (const [regex, renderer] of matchers) {
        const match = path.match(regex);
        if (!match) {
          continue;
        }
        appRoot.innerHTML = await renderer(match);
        handled = true;
        break;
      }
      if (!handled) {
        appRoot.innerHTML = shell(`<section class="hero"><div class="eyebrow">Not Found</div><h1>This frontend route does not exist.</h1><p class="muted">Return to the new app home or open the legacy pages.</p><div class="actions"><a class="button" href="/app" data-nav>Back To Home</a></div></section>`);
      }
    }
    bindForms();
  } catch (error) {
    appRoot.innerHTML = shell(`<section class="hero"><div class="eyebrow">Error</div><h1>The frontend shell could not load this page.</h1><p class="muted">${escapeHtml(error.message)}</p></section>`);
  }
}

render();
