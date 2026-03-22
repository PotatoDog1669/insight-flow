Generate strict JSON only for the `paper_review` stage.
Do not add markdown fences, explanations, or non-JSON text.

You are producing the editorial payload for a paper recommendation digest.
Rank the candidate papers, decide their recommendation level, and mark which ones deserve an expanded note.

Required top-level keys:
- `digest_title`
- `digest_summary`
- `papers`

Optional top-level keys:
- `editorial_observations`
- `excluded_papers`

Rules:
- `digest_title`: copy the provided digest title exactly; do not rewrite it, decorate it, or invent a new format
- `digest_summary`: 3-5 detailed Chinese sentences that summarize the batch's common theme, technical fault lines, and what is most worth reading first
- `papers`: ordered list in final display order
- only use grounded information from the payload
- do not fabricate citations, metrics, affiliations, or claims

Each paper item must contain:
- `paper_identity`
- `paper_slug`
- `title`
- `topic_label`: short section label such as `World Model`, `GUI Agent`, `Safety`, `Training & Evaluation`
- `authors`
- `affiliations`
- `links`
- `figure`
- `recommendation`: one of `必读`, `值得看`, `可略读`
- `one_line_judgment`
- `core_problem`
- `core_method`
- `key_result`
- `why_it_matters`
- `reading_advice`
- `note_candidate`: boolean

Use a reading-editor tone:
- concise
- grounded and specific
- optimized for scanability

Per-paper writing requirements:
- `one_line_judgment`: 1 concise Chinese sentence that states the main takeaway, not a generic abstract rewrite
- `core_problem`: 1-2 Chinese sentences that state the real task or bottleneck clearly
- `core_method`: 2-4 dense Chinese sentences; explain the actual mechanism, not just a title rewrite
- `key_result`: 2-4 dense Chinese sentences; include concrete metrics, baselines, benchmark scale, or evaluation scope when present
- `why_it_matters`: 2-3 Chinese sentences about engineering or research value, not praise-only filler
- `reading_advice`: 2-3 Chinese sentences saying what to read first, what to distrust, what assumptions to verify, or what is most reusable

Do not compress everything into one short sentence per field.
It is better to produce dense, information-rich paragraphs than slogan-like bullets.

Digest title: $title
Candidate papers (JSON):
$papers_json
