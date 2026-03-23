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
- `core_method`
- `baselines`
- `why_it_matters`
- `note_candidate`: boolean

Use a reading-editor tone:
- concise
- grounded and specific
- optimized for scanability

Per-paper writing requirements:
- `core_method`: 1 dense Chinese paragraph that can be rendered directly as `核心方法：...`; explain the actual mechanism, not just a title rewrite
- `baselines`: 1 dense Chinese paragraph that can be rendered directly as `对比方法 / Baselines：...`; cover the comparison setup, baseline families, evaluation scope, and which comparison claims are actually meaningful
- `why_it_matters`: 1 dense Chinese paragraph that can be rendered directly as `借鉴意义：...`; focus on engineering or research value, not praise-only filler

These three fields are final-form copy for the digest, not teaser + detail fragments.
Do not create extra helper sentences outside these three fields.
Do not prepend field labels like `核心方法：` inside the field content itself.
You may use sparse markdown bold such as `**TraceR1**`, `**7 个基准**`, `**5%-30.16%**` for truly key model names, benchmark scopes, or metrics, but do not overuse bold and do not bold full sentences.

Digest title: $title
Candidate papers (JSON):
$papers_json
