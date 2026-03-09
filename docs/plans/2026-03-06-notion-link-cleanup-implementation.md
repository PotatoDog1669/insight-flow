# Notion Link Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Notion exports drop web-only event anchors and replace overview arrow links with clearer text links.

**Architecture:** Keep the change isolated inside the Notion sink normalization flow so web markdown stays unchanged. Normalize rendered Notion markdown before block conversion, and adjust auto-generated overview lines to match the new Notion-only presentation.

**Tech Stack:** Python 3.12, pytest, existing Notion sink markdown-to-block conversion

---

### Task 1: Lock the new Notion output with tests

**Files:**
- Modify: `backend/tests/sinks/test_notion_sink.py`
- Test: `backend/tests/sinks/test_notion_sink.py`

**Step 1: Write the failing test**

Add assertions that:
- `- 事件一 [↗](https://example.com/a) [#1](#event-1)` becomes `- 事件一 [原文](https://example.com/a)` in Notion-rendered content
- injected overview output becomes `- OpenAI 发布更新 [原文](https://openai.com/news)`

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/sinks/test_notion_sink.py -k notion_content -q`
Expected: FAIL because the current sink still preserves `[#1](#event-1)` and `↗`

### Task 2: Implement the minimal Notion-only cleanup

**Files:**
- Modify: `backend/app/sinks/notion.py`
- Test: `backend/tests/sinks/test_notion_sink.py`

**Step 1: Add normalization helpers**

Implement helpers that:
- remove internal event anchor markdown links
- replace `[↗](url)` with `[原文](url)`
- trim redundant double spaces left after anchor removal

**Step 2: Update injected overview formatting**

Change `_build_overview_section()` so Notion-generated overview items render:
- `- 标题 [原文](url)` when a source link exists
- `- 标题` when no source link exists

**Step 3: Run tests to verify they pass**

Run: `pytest backend/tests/sinks/test_notion_sink.py -k notion_content -q`
Expected: PASS

### Task 3: Verify the targeted Notion conversion path

**Files:**
- Test: `backend/tests/sinks/test_notion_sink.py`
- Test: `backend/tests/sinks/test_notion_client.py`

**Step 1: Run focused sink tests**

Run: `pytest backend/tests/sinks/test_notion_sink.py backend/tests/sinks/test_notion_client.py -q`
Expected: PASS

**Step 2: Record behavior**

Confirm:
- web-only `#event-*` links no longer appear in Notion content
- Notion overview uses `原文` instead of `↗`
- external URLs still survive markdown-to-Notion rich text conversion
