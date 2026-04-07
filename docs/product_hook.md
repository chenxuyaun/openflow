# OpenFlow Product Hook

## One-Line Definition

OpenFlow is a project operating system where every AI role works in a fresh
session, yet nothing is lost because the project advances through files,
decisions, workflow graphs, and structured handoffs.

## The Problem

Long-running AI work breaks down when progress depends on hidden chat context.
Ideas drift, implementation details get lost, and new specialist roles start
from incomplete summaries. Teams and solo builders both end up rebuilding
context manually.

## Why This Product Exists

OpenFlow replaces hidden context with auditable project memory:

- every role gets a new session
- every session reads explicit files
- every result becomes a structured handoff
- every project state can be reconstructed from disk

This makes planning, development, review, and creative work durable instead of
fragile.

## Why It Is Not Just Another Chat Tool

- Chat tools preserve history, but history becomes noise over time
- Agent tools automate steps, but often hide why work progressed
- Knowledge tools store notes, but do not drive the next role and next action

OpenFlow combines all three: conversation capture, project memory, and
role-driven execution.

## End-to-End Story

1. A user describes a product or creative goal.
2. A bootstrap role analyzes the request and existing files.
3. OpenFlow creates a workflow graph, a role catalog, and a task tree.
4. A specialist role starts in a new session and reads only the declared files.
5. The role produces output and a structured handoff for the next role.
6. A review or architecture gate can stop auto-advance when risk is high.
7. The project resumes later without depending on hidden runtime context.

## First-Use Attraction

The first compelling experience is simple: a user sees their messy idea turned
into a visible workflow, a knowledge base, and a clear next role instead of yet
another long conversation thread.

## Why Teams Stay

The same mechanism that attracts a user on day one is what keeps a team aligned
later: every role can prove what it read, what it changed, and why the next
role should take over.

## Promise For Teams And Builders

- Fewer lost decisions
- Clearer role responsibility
- Easier recovery after interruptions
- Reusable knowledge for development, operations, and creation

## V1 Experience Promise

In the first release, OpenFlow should let a user bootstrap a project, inspect
its knowledge base, review the workflow graph, open a role session, and see the
handoff that drives the next role.

## Direct Conversion To Landing

This document is the source for the landing page hero, problem statement,
workflow preview, and V1 promise. The landing page should not introduce a new
story that conflicts with this hook.

## Direct Conversion To Demo

This hook also anchors the demo sequence: opening promise, problem framing,
visible workflow transformation, isolated session proof, and closing V1 promise.
