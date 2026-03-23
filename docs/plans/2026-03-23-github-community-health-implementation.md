# GitHub Community Health Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a production-quality `.github` collaboration package that gives contributors standard issue intake, PR guidance, basic review routing, dependency updates, and CI coverage.

**Architecture:** The implementation stays fully inside repository metadata and contributor docs. All new automation reuses existing backend and frontend entry points so GitHub workflows reflect current local development and validation commands.

**Tech Stack:** GitHub Issue Forms, GitHub Actions, Dependabot, Markdown, YAML

---

### Task 1: Add issue intake forms

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `.github/ISSUE_TEMPLATE/documentation.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`

**Step 1: Write the files**

- Add a bug form that asks for summary, impact, reproduction, expected behavior, environment, and logs/screenshots.
- Add a feature form that asks for problem statement, proposed solution, alternatives, and success criteria.
- Add a docs form that asks for the affected page, issue type, and proposed fix.
- Add issue template config that disables blank issues and links to docs, contributing guidance, and the security policy.

**Step 2: Verify the YAML syntax**

Run: `./.venv/bin/python -c "import pathlib, yaml; [yaml.safe_load(path.read_text()) for path in pathlib.Path('.github/ISSUE_TEMPLATE').glob('*.yml')]"`  
Expected: command exits `0`

**Step 3: Commit**

```bash
git add .github/ISSUE_TEMPLATE/bug_report.yml .github/ISSUE_TEMPLATE/feature_request.yml .github/ISSUE_TEMPLATE/documentation.yml .github/ISSUE_TEMPLATE/config.yml
git commit -m "chore: add github issue forms"
```

### Task 2: Add pull request guidance and ownership

**Files:**
- Create: `.github/pull_request_template.md`
- Create: `.github/CODEOWNERS`
- Modify: `CONTRIBUTING.md`

**Step 1: Write the files**

- Add a PR template that asks for summary, linked issue, validation, screenshots, breaking changes, and docs impact.
- Add a minimal `CODEOWNERS` file with the repository maintainer as default owner and explicit ownership for major top-level areas.
- Update `CONTRIBUTING.md` so contributors know to use the new issue forms and PR template.

**Step 2: Verify the docs read clearly**

Run: `git diff --check`  
Expected: no whitespace or conflict-marker errors

**Step 3: Commit**

```bash
git add .github/pull_request_template.md .github/CODEOWNERS CONTRIBUTING.md
git commit -m "docs: add github contribution workflow guidance"
```

### Task 3: Add repository automation

**Files:**
- Create: `.github/dependabot.yml`
- Create: `.github/workflows/ci.yml`

**Step 1: Write the files**

- Add weekly Dependabot updates for GitHub Actions, backend Python dependencies, and frontend npm dependencies.
- Add CI jobs for backend and frontend that use the repository's current install and verification commands.

**Step 2: Verify the YAML syntax**

Run: `./.venv/bin/python -c "import pathlib, yaml; [yaml.safe_load(path.read_text()) for path in pathlib.Path('.github').rglob('*.yml')]"`  
Expected: command exits `0`

**Step 3: Commit**

```bash
git add .github/dependabot.yml .github/workflows/ci.yml
git commit -m "ci: add github automation baseline"
```

### Task 4: Record the design and implementation docs

**Files:**
- Create: `docs/plans/2026-03-23-github-community-health-design.md`
- Create: `docs/plans/2026-03-23-github-community-health-implementation.md`

**Step 1: Save the records**

- Capture the design scope, non-goals, risks, and validation.
- Capture the task-by-task implementation plan for future contributors.

**Step 2: Verify repository status**

Run: `git status --short`  
Expected: only the intended docs and `.github` files appear as modified or new

**Step 3: Commit**

```bash
git add docs/plans/2026-03-23-github-community-health-design.md docs/plans/2026-03-23-github-community-health-implementation.md
git commit -m "docs: record github community health plan"
```
