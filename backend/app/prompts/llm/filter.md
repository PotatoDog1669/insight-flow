You are filtering AI-industry news items.
Return strict JSON only: {"keep_indices": [int, ...]}.
Completeness first:
- Keep any item clearly related to AI models, agents, releases, papers, benchmarks, tooling, infra, policy, or ecosystem moves.
- Remove only obvious noise/non-AI items.
- Deduplicate conservatively: drop duplicates only when they are clearly the same event with no new facts.
- If two items mention the same topic but one has extra metrics, timeline, constraints, or official context, keep both.
Input items:
$items_json
