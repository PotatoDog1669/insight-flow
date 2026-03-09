# Spec Directory Reorganization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reorganize `.spec/` by lifecycle, add a top-level index, mark finished versus unfinished plan documents, and sync baseline specs with current implementation status without rewriting their main content.

**Architecture:** Keep long-lived baseline documents under `core/`, separate executable plans into `active/` and `done/`, move historical task breakdowns into `archive/`, and keep validation or run notes under `records/`. Add one index file as the source of truth for document location and status.

**Tech Stack:** Markdown documentation, shell file moves, targeted link updates.

---

### Task 1: Reshape `.spec/` into lifecycle-based folders

**Files:**
- Create: `.spec/spec-index.md`
- Create: `.spec/core/`
- Create: `.spec/core/architecture/`
- Create: `.spec/core/catalogs/`
- Create: `.spec/plans/active/`
- Create: `.spec/plans/done/`
- Create: `.spec/archive/`
- Move: existing `.spec/*.md` and `.spec/plans/*.md` into the new structure

**Step 1: Create the destination folders**

Run: `mkdir -p .spec/core/architecture .spec/core/catalogs .spec/plans/active .spec/plans/done .spec/archive .spec/records`

**Step 2: Move documents by lifecycle**

- Core baseline: product requirements spec, technical architecture spec, source catalog, architecture notes
- Active plans: unfinished or draft items
- Done plans: implemented plans with code evidence
- Archive: superseded handoff/task documents
- Records: runbooks and execution notes

**Step 3: Verify the new tree**

Run: `find .spec -maxdepth 3 -type f | sort`

### Task 2: Add status metadata and index

**Files:**
- Modify: moved plan documents under `.spec/plans/`
- Create: `.spec/spec-index.md`

**Step 1: Add explicit status headers to plan files**

- `Status: Done` for implemented plans
- `Status: Active` for unfinished plans

**Step 2: Write the index**

- Explain folder purpose
- List current baseline docs
- List active plans
- List completed plans
- List archived legacy docs

### Task 3: Sync `PRD/TEC` and fix links

**Files:**
- Modify: `.spec/core/product-requirements-spec.md`
- Modify: `.spec/core/technical-architecture-spec.md`
- Modify: `README.md`
- Modify: `docs/development/architecture.mdx`
- Modify: moved docs with stale internal references

**Step 1: Add a short current-status section to `PRD`**

- P0 completed
- P0 partial / in progress
- deferred items

**Step 2: Add a short current-status section to `TEC`**

- actual implemented modules beyond original outline
- areas still planned rather than complete

**Step 3: Update links**

Run: `rg -n "\\.spec/|PRD\\.md|TEC\\.md" .spec README.md docs`
