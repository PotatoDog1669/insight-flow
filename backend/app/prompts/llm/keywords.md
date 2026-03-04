Extract 5-8 high-signal keywords, one concise summary sentence, an importance level, and a detailed analysis paragraph for this AI news item.
Return strict JSON only: {"keywords": ["..."], "summary": "...", "importance": "high|normal", "detail": "..."}.
Prefer product/model names, technical concepts, company/project names, and concrete metrics.

Rules:
- summary: one-sentence TL;DR in Chinese, <=60 characters
- importance: "high" only for major industry events (flagship model release, major platform move, high-impact policy/regulation, or widely cited benchmark milestone); otherwise "normal"
- detail: 220-520 Chinese characters with factual completeness:
  1) what happened
  2) who发布/受影响
  3) technical/product changes
  4) key numbers/dates/constraints when available
Do NOT fabricate facts. If details are missing, explicitly state unknowns.

Title: $title
Content: $content
