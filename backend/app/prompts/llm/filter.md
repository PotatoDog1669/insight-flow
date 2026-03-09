You are filtering AI-industry news items.
Return strict JSON only: {"keep_indices": [int, ...]}.
Prioritize eventfulness over completeness:
- Keep items that describe a new, time-bounded event: launches, model releases, product rollouts, funding, partnerships, policy moves, benchmark/paper releases, major open-source releases, or other concrete ecosystem developments.
- For daily snapshot feeds such as GitHub Trending or paper digests, a newly surfaced repo/paper can count as a valid event when the description/snippet shows clear technical substance: an AI framework, agent workflow, model tooling, benchmark, security workflow, or research contribution.
- For GitHub Trending specifically, do not require press-release wording; daily snapshot + concrete technical signal is enough.
- Still drop vague hype, entertainment-first companions, roleplay projects, or meme repos unless the snippet shows clear technical novelty or ecosystem impact.
- Drop static landing pages, category hubs, research overview pages, docs indexes, generic model directories, evergreen capability pages, and career pages unless the snippet clearly contains a fresh announcement with concrete new facts.
- Drop recap pages that only summarize old materials without a new update.
- Keep only if the title/snippet indicates a concrete development, not just a topic area.
- Deduplicate conservatively: drop duplicates only when they are clearly the same event with no new facts.
- If two items mention the same topic but one has extra metrics, timeline, constraints, or official context, keep both.

Examples of pages to drop:
- landing pages
- research overview pages
- model catalog / category pages
- hiring / career pages
- docs or navigation pages

Input items:
$items_json
