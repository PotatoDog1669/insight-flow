Generate strict JSON only for the `paper_note` stage.
Do not add markdown fences, explanations, or non-JSON text.

You are producing a structured single-paper reading note from abstract-level and metadata-level evidence.
Do not imply that you read the full PDF unless the payload clearly contains that information.

Required keys:
- `title`
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

Rules:
- keep the writing grounded and technical
- prefer concise sections over long essay paragraphs
- do not fabricate formulas, benchmarks, or implementation details
- when evidence is limited, state the interpretation conservatively inside the section text itself

Paper title: $title
Selected paper (JSON):
$paper_json
