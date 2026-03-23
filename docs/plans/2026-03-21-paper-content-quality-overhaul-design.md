# Paper Content Quality Overhaul Design

**Date:** 2026-03-21  
**Status:** Approved  
**Scope:** Upgrade the `paper` report workflow so the digest and per-paper notes are generated through paper-specific AI stages and render directly into Obsidian-friendly final-form markdown.

---

## 1. Goal

Improve the quality of `paper` outputs so they feel closer to a real paper recommendation workflow instead of a formatted summary dump.

The target P0 outcome is:

- a stronger daily or weekly paper recommendation page
- better per-paper reading notes
- consistent markdown that already looks close to the final Obsidian form
- no dependency on fulltext or PDF parsing in this phase

This work focuses on content production quality, not source acquisition quality.

## 2. Problem Statement

The current `paper` flow reuses general-purpose article processing outputs and then maps those fields into paper templates.

That creates a quality ceiling:

- the upstream `keywords` stage is designed for AI news and event briefs, not paper recommendation or paper reading
- the digest is assembled from generic `summary`, `detail`, `importance`, and `metrics` fields
- the note is an expanded structured card, but not the result of a dedicated single-paper reading task
- template changes alone cannot fully fix the mismatch because the wrong intermediate representation is being generated

In short, the current output is structurally neat but task-misaligned.

## 3. Product Direction

The `paper` workflow should behave like a lightweight editorial reading pipeline:

1. collect academic candidates
2. run a paper-specific review stage for ranking and digest writing
3. run a paper-specific note stage for selected papers
4. render the resulting markdown directly into product and sink outputs

This stays within the existing product model:

- one monitor type: `paper`
- one main digest per run
- a small number of linked note reports per run

## 4. P0 Scope Decisions

### 4.1 Included in P0

- add paper-specific AI stages
- upgrade both digest and note generation
- keep report content itself close to the final Obsidian markdown shape
- preserve current report storage shape: `report_type="paper"` with `paper_mode="digest" | "note"`

### 4.2 Explicitly excluded from P0

- fulltext, PDF, or HTML reading inside the `paper` report flow
- formula extraction and figure completeness guarantees
- concept-note generation or automatic double-link graph building
- Zotero-style single-paper ingestion
- full parity with `dailypaper-skills` paper-reader depth

P0 aims for higher quality structured reading output, not full paper-reader depth.

## 5. Recommended Architecture

The recommended design adds two dedicated content-generation stages inside the `paper` branch:

- `paper_review`
- `paper_note`

The existing collector, paper identity, and persistence layers remain in place.

### 5.1 Base extraction layer

Keep the current source and paper-linking pipeline responsible for:

- title
- abstract or summary text
- authors
- affiliations
- identifiers
- links
- core figure URL when available
- canonical paper identity

This layer remains the factual substrate for downstream generation.

### 5.2 Paper review layer

Add a new batch-oriented AI stage that consumes paper candidates and produces digest-ready editorial output.

Responsibilities:

- rank candidate papers
- decide display order
- assign recommendation level
- write digest introduction
- decide which papers deserve detailed notes
- produce concise paper-by-paper short-form copy

### 5.3 Paper note layer

Add a new single-paper AI stage that consumes one selected paper and produces note-ready structured reading content.

Responsibilities:

- explain the paper clearly
- organize the content into stable note sections
- provide interpretation and reading guidance
- support direct rendering into final markdown

## 6. Stage Contracts

## 6.1 `paper_review` output contract

The `paper_review` stage should return one JSON payload for the whole digest.

Suggested top-level fields:

- `digest_title`
- `digest_summary`
- `editorial_observations`
- `papers`
- `excluded_papers`

Each `papers` item should include:

- `paper_identity`
- `paper_slug`
- `title`
- `authors`
- `affiliations`
- `links`
- `figure`
- `recommendation`
- `one_line_judgment`
- `core_problem`
- `core_method`
- `key_result`
- `why_it_matters`
- `reading_advice`
- `note_candidate`

The stage owns editorial decisions:

- what gets included
- in what order
- how strongly it is recommended
- whether it gets a detailed note

## 6.2 `paper_note` output contract

The `paper_note` stage should return one JSON payload per selected paper.

Suggested fields:

- `title`
- `paper_identity`
- `paper_slug`
- `authors`
- `affiliations`
- `links`
- `summary`
- `core_contributions`
- `problem_background`
- `method_breakdown`
- `figure_notes`
- `experiments`
- `strengths`
- `limitations`
- `related_reading`
- `next_steps`

This contract should stay close to the final note template so the renderer remains thin.

## 7. Output Shape

## 7.1 Digest shape

The digest content should render directly into a final-form markdown structure:

- title
- `## 本期导读`
- `## 分流表`
- `## 推荐论文`

The digest should feel editorial and scannable:

- a short opening judgment
- a quick triage table
- then per-paper structured entries

Each paper entry should remain strongly structured for reliability, but the wording should come from `paper_review`, not from generic event summarization.

## 7.2 Note shape

The note should be rendered as a high-quality structured reading card, not a copied abstract and not a full paper-reader artifact.

Recommended note sections:

- frontmatter
- title
- metadata
- one-sentence summary
- core contributions
- problem background
- method breakdown
- figure interpretation
- experiments
- critical reading
- related reading
- next steps
- link back to digest

The markdown should be stable enough for product rendering and Obsidian export without sink-only reshaping.

## 8. Orchestration Flow

Inside the `paper` branch of the scheduler:

1. gather processed academic candidates
2. build a `paper_review` input payload
3. run the `paper_review` stage
4. render the digest from the `paper_review` output
5. select papers where `note_candidate=true`
6. run `paper_note` for each selected paper
7. render note reports
8. backfill note links into the digest
9. persist all reports using the current `paper_mode` contract

This preserves the current storage model while replacing the low-quality middle layer.

## 9. Rendering Responsibilities

Templates should become presentation-only rather than inference-heavy.

### 9.1 Digest renderer

The digest renderer should:

- trust `paper_review` ordering
- trust `paper_review` recommendation labels
- inject note links after note reports exist
- avoid inventing text from fallback heuristics unless generation truly fails

### 9.2 Note renderer

The note renderer should:

- render sections from `paper_note` output directly
- preserve stable structure
- keep a clean link back to the digest

## 10. Persistence and Metadata

The existing `report_type="paper"` storage model should stay intact.

Recommended metadata additions or strengthened usage:

- `paper_mode`
- `paper_identity`
- `paper_slug`
- `paper_note_links`
- `selected_paper_identities`
- `recommendation`
- `parent_report_id`
- `paper_parent_link`
- `paper_review_payload_version`
- `paper_note_payload_version`

P0 should not introduce a new top-level table just for paper digest versus note role separation.

## 11. Obsidian Alignment

The report body itself should already resemble the desired Obsidian result.

That means:

- digest markdown should read cleanly in product and export cleanly to `DailyPapers/<date>-论文推荐.md`
- note markdown should read cleanly in product and export cleanly to `DailyPapers/Papers/<paper-slug>.md`

The sink should mainly decide file path, not rewrite structure.

## 12. Why This Design

This design is preferred because it solves the actual mismatch:

- it stops reusing an AI news/event prompt for paper writing
- it separates batch recommendation from single-paper explanation
- it improves the content itself, not just the wrapper
- it preserves the current product model and publishing paths
- it keeps P0 realistic by avoiding fulltext complexity

## 13. Success Criteria

P0 should be considered successful when:

- the digest reads like a paper recommendation page rather than a generic summary list
- the digest includes clear recommendation levels and a scannable triage section
- note pages read like structured paper reading notes
- the same markdown works well in product surfaces and Obsidian publishing
- the implementation does not require fulltext ingestion to achieve visible quality gains
