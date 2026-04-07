# OpenFlow Demo Runbook

This runbook shows the shortest path to see the current product working in a browser.

## Start The App

Run:

```powershell
python -m uvicorn openflow.app:app --app-dir src --reload --port 8001
```

Then open:

```text
http://127.0.0.1:8001/
```

Important:

- Run `run_demo.ps1` from PowerShell.
- Do not combine `src` and `--reload` into `src--reload`.

## Demo Path

### 1. Landing

On the landing page:

- keep the default workspace name, or enter a new one
- keep the default goal, or enter a new one
- keep the default materials/context text, or enter your own
- click `Create Workspace`

Expected result:

- the app creates a new project
- the browser redirects to `/projects/{project_id}/welcome`

### 2. Welcome

On the welcome page, confirm that you can see:

- current goal
- organized materials summary
- current progress
- suggested next step

Main actions:

- `Continue Recommended Step` when a next handoff is ready
- `Start First Work Step` when no handoff exists yet
- `Open Workspace`
- `Organize Materials`

### 3. Workspace Overview

Open `/projects/{project_id}` and verify:

- current goal
- available materials
- current progress
- suggested next step
- recommendation reason
- project timeline

If the project is research-heavy, the default recommendation may point to `Research Curator` and `Organize Materials`.

### 4. Materials Center

Open `/projects/{project_id}/knowledge` and verify:

- search
- filters
- grouped materials
- source groups
- organize materials form
- batch organize materials form

Recommended demo action:

- submit one `Organize Materials` form
- return to the workspace overview and confirm the materials summary changes

### 5. Work Step

From welcome or workspace:

- start the first work step, or start the recommended next step

On the session page:

- review materials used
- complete the step
- write the next role recommendation
- save the handoff

Expected result:

- the session shows completion feedback
- the handoff is preserved
- the workspace recommends the next step

### 6. Review And Advance

If the next step requires review:

- use `Continue`, `Needs Changes`, or `Replan`

If the next step is ready:

- click `Start Suggested Next Step`

Expected result:

- the next session starts fresh
- the project continues from files and handoff records

## What This Demo Proves

The current product already demonstrates:

- fresh-session role changes
- file-based continuity instead of hidden chat context
- visible next-step guidance
- materials organization
- review and replanning paths
- recommendation-driven workspace flow
