# Reddit Custom Subreddits Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let the built-in Reddit source manage a user-editable `subreddits` list like X usernames while preserving the current default watchlist and continuing to collect via RSS.

**Architecture:** Keep Reddit on the existing `rss` collector, but make `subreddits` the canonical config field. Bootstrap merges stored and default subreddit values, the orchestrator derives `feed_url` from `subreddits`, and the source detail modal exposes immediate add/remove editing for Reddit only.

**Tech Stack:** FastAPI, SQLAlchemy bootstrap flow, React, TypeScript, Vitest, pytest

---

### Task 1: Lock backend config behavior with failing tests

**Files:**
- Modify: `backend/tests/test_bootstrap_seed_initial_data.py`
- Modify: `backend/tests/test_sources_api.py`

**Step 1: Write the failing bootstrap test**

Add coverage that proves the seeded Reddit source keeps default subreddit values and merges persisted custom values without dropping either set.

**Step 2: Run test to verify it fails**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/test_bootstrap_seed_initial_data.py -q
```

Expected:
- FAIL because Reddit does not yet merge `subreddits`

**Step 3: Write the failing runtime config test**

Add coverage around source config resolution or source test behavior that proves a Reddit source with `subreddits` produces a resolved RSS feed query from those subreddit names.

**Step 4: Run test to verify it fails**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/test_sources_api.py -q
```

Expected:
- FAIL because runtime still depends on stored `feed_url`

**Step 5: Commit**

```bash
git add backend/tests/test_bootstrap_seed_initial_data.py backend/tests/test_sources_api.py
git commit -m "test: define reddit subreddit config behavior"
```

### Task 2: Implement backend Reddit config normalization

**Files:**
- Modify: `backend/app/bootstrap.py`
- Modify: `backend/app/collectors/source_presets.yaml`
- Modify: `backend/app/scheduler/orchestrator.py`
- Test: `backend/tests/test_bootstrap_seed_initial_data.py`
- Test: `backend/tests/test_sources_api.py`

**Step 1: Add Reddit normalization helpers**

Implement helpers that:

- normalize a subreddit value by trimming and removing leading `r/`
- merge default and persisted subreddit lists case-insensitively
- build the Reddit RSS search URL from a normalized subreddit list

**Step 2: Update the preset**

Move the seeded Reddit source to `collect_config.subreddits` with the three current defaults and keep the existing RSS strategy settings.

**Step 3: Update bootstrap merge behavior**

When syncing the Reddit preset:

- merge stored and synced subreddit lists
- keep the result in `config.subreddits`
- allow `feed_url` to be derived later instead of being the only source of truth

**Step 4: Update runtime config resolution**

When preparing source config for an RSS-based Reddit source:

- derive `config.feed_url` from `config.subreddits`
- leave generic RSS sources untouched

**Step 5: Run the targeted backend tests**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/test_bootstrap_seed_initial_data.py backend/tests/test_sources_api.py -q
```

Expected:
- PASS

**Step 6: Commit**

```bash
git add backend/app/bootstrap.py backend/app/collectors/source_presets.yaml backend/app/scheduler/orchestrator.py
git commit -m "feat: support configurable reddit subreddits"
```

### Task 3: Lock Reddit modal behavior with failing frontend tests

**Files:**
- Modify: `frontend/src/components/SourceDetailModal.test.tsx`

**Step 1: Write the failing modal test**

Add coverage that proves:

- a Reddit source renders subreddit chips
- adding `r/OpenAI` persists `OpenAI`
- removing an existing subreddit persists the reduced list
- the generic RSS URL editor does not render for Reddit

**Step 2: Run test to verify it fails**

Run:
```bash
cd frontend && npm test -- --run SourceDetailModal.test.tsx
```

Expected:
- FAIL because Reddit still uses the generic RSS URL editor

**Step 3: Commit**

```bash
git add frontend/src/components/SourceDetailModal.test.tsx
git commit -m "test: define reddit subreddit modal behavior"
```

### Task 4: Implement Reddit-specific source editing in the modal

**Files:**
- Modify: `frontend/src/components/SourceDetailModal.tsx`
- Test: `frontend/src/components/SourceDetailModal.test.tsx`

**Step 1: Add Reddit modal state and helpers**

Implement:

- subreddit array state
- draft input state
- subreddit normalization helper
- immediate persist helper matching the X username flow

**Step 2: Update modal rendering**

Render a Reddit-only editor with:

- `Tracked Subreddits` label
- chip list
- add button
- remove buttons on chips

Keep the generic URL editor for non-Reddit RSS sources.

**Step 3: Run the targeted frontend test**

Run:
```bash
cd frontend && npm test -- --run SourceDetailModal.test.tsx
```

Expected:
- PASS

**Step 4: Commit**

```bash
git add frontend/src/components/SourceDetailModal.tsx frontend/src/components/SourceDetailModal.test.tsx
git commit -m "feat: add reddit subreddit editor"
```

### Task 5: Verify the end-to-end slice

**Files:**
- Verify only

**Step 1: Run focused backend and frontend verification**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/test_bootstrap_seed_initial_data.py backend/tests/test_sources_api.py -q
cd frontend && npm test -- --run SourceDetailModal.test.tsx
```

Expected:
- PASS on all targeted tests

**Step 2: Sanity-check seeded default values**

Confirm the Reddit preset still defaults to:

- `LocalLLaMA`
- `singularity`
- `OpenAI`

and that runtime config builds a valid Reddit RSS search query from them.

**Step 3: Commit**

```bash
git add docs/plans/2026-03-19-reddit-custom-subreddits-design.md docs/plans/2026-03-19-reddit-custom-subreddits-implementation.md
git commit -m "docs: add reddit custom subreddits design and plan"
```
