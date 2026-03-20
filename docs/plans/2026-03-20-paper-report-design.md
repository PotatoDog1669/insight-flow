# Paper Report Design

**Date:** 2026-03-20  
**Status:** Approved  
**Scope:** Introduce a paper-centric report flow that produces a digest-style paper recommendation report plus linked detailed reading notes for selected papers.

---

## 1. Goal

Build a first-class `paper` reporting flow for academic reading.

The output should feel like a curated paper reading issue:

- one main report for the day or week
- multiple recommended papers presented as short reading notes
- optional detailed note pages for the most important papers
- clean mapping into Obsidian as one index note plus stable per-paper notes

This is intentionally different from the current `research` report type. `research` is event-centric and multi-source. `paper` is paper-centric and reading-oriented.

## 2. Product Definition

### 2.1 What `paper` is

`paper` is a unified report type for paper recommendation.

- `time_period` controls whether it is daily or weekly
- daily and weekly share one template skeleton
- weekly is a larger issue of the same structure, not a different product

### 2.2 What `paper` is not

`paper` is not:

- a renamed `research` report
- a plain ranked list of paper links
- a single-paper task type exposed in monitor creation

## 3. Core User Flow

1. The user creates a monitor with `report_type="paper"`.
2. The system collects candidate academic items.
3. The model ranks the candidates and decides:
   - which papers enter the digest
   - the order of the recommendations
   - which papers deserve detailed reading notes
4. The system generates one main `paper` digest report.
5. The system generates independent detailed note reports for selected papers.
6. The main report links to the detailed notes.
7. When published to Obsidian, the digest becomes one dated index note and each detailed note maps to a stable per-paper note path.

## 4. Information Architecture

### 4.1 Main digest report

The main report is the primary output of a `paper` monitor run.

Responsibilities:

- present the issue title and time context
- provide one top-level `本期导读`
- present every recommended paper as a compact reading note
- link to detailed note reports for selected papers

### 4.2 Detailed paper notes

Detailed notes are independent reports generated from a `paper` run.

Responsibilities:

- provide a full reading report for one paper
- expand the short note in the digest into a deeper explanation
- remain accessible from the main digest
- remain suitable for stable note reuse in Obsidian

### 4.3 Task-facing simplicity

The monitor UI should expose only one selectable type: `paper`.

Users do not select a second task type for detailed notes. Those notes are automatic derived outputs of the main paper digest flow.

## 5. Report Structure

### 5.1 Main `paper` digest template

Recommended structure:

- report title
- `本期导读`
- recommended papers list

Each paper entry in the digest should contain:

- title
- authors
- affiliations
- links: arXiv / PDF / Project / Code when available
- one core figure
- one-sentence judgment
- core problem
- core method
- key result
- why it matters
- reading recommendation: `必读 / 值得看 / 可略读`
- detailed note entry when one exists

This report should feel like a compact issue of reading notes, not a thin list of links.

### 5.2 Detailed paper note template

Recommended structure:

- title
- authors and affiliations
- links
- one-sentence conclusion
- paper positioning
- core figure
- key contributions
- method breakdown
- figure explanation
- experiments and results
- my interpretation
- limitations and open questions
- use cases
- related reading
- link back to the digest

The detailed note should read like a real paper reading report, not a copied abstract.

## 6. Model Responsibilities

The model should decide:

- which candidate papers make the digest
- how to order them
- the reading recommendation level for each paper
- which papers deserve a detailed note

The system should still enforce light execution guards:

- maximum paper count for the digest
- maximum number of detailed notes per run

This keeps costs bounded without taking ranking control away from the model.

## 7. Storage and Metadata

P0 should avoid a new top-level monitor type for detailed notes.

Recommended P0 persistence approach:

- store the main digest as `report_type="paper"`
- store each detailed note as an independent report row as well
- keep the task-facing type unified as `paper`
- use `metadata` to distinguish roles and relationships

Suggested metadata fields:

- `paper_mode`: `digest` or `note`
- `paper_candidates`
- `paper_recommendations`
- `paper_note_links`
- `parent_report_id`
- `source_paper_id`
- `paper_slug`
- `paper_identity`

This keeps the P0 implementation compatible with the current report table while preserving enough structure for UI and sinks.

## 8. Obsidian Mapping

The Obsidian output should reflect the reading workflow directly.

### 8.1 Digest note

Create one dated digest note per issue, for example:

- `DailyPapers/2026-03-20-论文推荐.md`

### 8.2 Per-paper notes

Detailed notes should use stable paper identity rather than date-based duplication, for example:

- `DailyPapers/Papers/<paper-slug>.md`

Identity order:

1. arXiv id
2. DOI
3. normalized title slug

### 8.3 Linking rules

- digest note links to detailed notes
- detailed notes link back to the digest that referenced them
- repeated appearance of the same paper should reuse the same Obsidian note path

## 9. Why This Design

This design is preferred because it gives us:

- one simple monitor type for users
- one readable digest as the primary output
- richer reading depth for important papers
- a natural Obsidian knowledge-base shape
- room to add better paper identity and note reuse later without redesigning the UX

## 10. P0 Scope

P0 includes:

- add `paper` as a first-class report type
- one shared digest template for daily and weekly
- short note sections for all recommended papers
- one core figure per paper in the digest
- independent detailed reports for selected papers
- links from the digest to detailed notes
- Obsidian output as one digest note plus stable paper note files

P0 excludes:

- a separately selectable detailed-note monitor type
- a special weekly-only template
- multi-figure automatic commentary in the digest
- full cross-run note merge logic inside the product database
- rich related-work graphs or citation exploration
