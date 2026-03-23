# README Demo Video Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the README demo placeholder text with a GitHub-hosted video embed URL and stop tracking the local demo video file.

**Architecture:** This change is documentation-only. Both README files will point at the same GitHub `user-attachments` asset URL, and git tracking for `insight-flow.mp4` will be removed while the filename is added to `.gitignore`.

**Tech Stack:** Markdown, git, `.gitignore`

---

### Task 1: Update README demo sections

**Files:**
- Modify: `README.md`
- Modify: `README.en.md`

**Step 1: Replace the demo placeholder text**

Use the standalone URL:

```text
https://github.com/user-attachments/assets/c3c22e77-2280-4103-88f5-9bf852318c0c
```

**Step 2: Verify the README diff**

Run: `git diff -- README.md README.en.md`
Expected: only the demo section line changes from `insight-flow.mp4` to the attachment URL.

### Task 2: Stop tracking the repository video file

**Files:**
- Modify: `.gitignore`
- Update git index for: `insight-flow.mp4`

**Step 1: Ignore the local demo video**

Add:

```text
insight-flow.mp4
```

**Step 2: Remove the file from git tracking without deleting the local file**

Run: `git rm --cached -- insight-flow.mp4`
Expected: git stages the file as deleted from the repository but keeps the working copy.

### Task 3: Verify and publish

**Files:**
- Verify: repository status

**Step 1: Check git status**

Run: `git status --short --branch`
Expected: README changes, `.gitignore` change, and `insight-flow.mp4` removed from tracking.

**Step 2: Commit and push**

Run:

```bash
git add -f docs/plans/2026-03-24-readme-demo-video-design.md docs/plans/2026-03-24-readme-demo-video-implementation.md
git add README.md README.en.md .gitignore
git commit -m "docs: embed README demo video"
git push origin codex/research-template
```

Expected: remote accepts the push without large-file upload warnings for `insight-flow.mp4`.
