# README Demo Video Design

**Date:** 2026-03-24

**Goal:** Render a playable demo video in the GitHub README while removing the tracked repository copy of `insight-flow.mp4`.

## Context

The current README demo section only contains the literal text `insight-flow.mp4`, so GitHub renders plain text instead of a video player. GitHub README pages can autoplay-render a standalone `github.com/user-attachments/assets/...` video URL, which matches the pattern used by comparable repositories.

The repository also currently tracks `insight-flow.mp4`, which increases repo weight and risks future push failures because of GitHub's file-size limits.

## Decision

Use the provided GitHub `user-attachments` asset URL in both Chinese and English READMEs, replacing the plain filename line. Stop tracking `insight-flow.mp4` in git and add it to `.gitignore` so the local copy can stay on disk without reappearing in future commits.

## Verification

- Confirm both README files contain the standalone `user-attachments` URL.
- Confirm `git status` shows `insight-flow.mp4` removed from tracking and no longer re-added after `.gitignore` is updated.
- Push the branch and ensure the remote accepts the change.
